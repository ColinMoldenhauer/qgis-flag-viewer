"""Dock widget showing the decoded flag meaning(s) for every raster layer
under the cursor, one row per (layer, band).
"""
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject, QgsRasterLayer

from .core.flag_decoder import FlagMode
from .core.layer_property import clear_mapping_on_layer, save_mapping_to_layer


class FlagViewerDockWidget(QDockWidget):
    COLUMNS_CATEGORIZED = ("Layer", "Band", "Value", "Meaning")
    COLUMNS_BITMASK = ("Layer", "Band", "Value", "Bit(s)", "Meaning(s)")

    def __init__(self, iface, parent=None):
        super().__init__("Flag Viewer", parent)
        self.iface = iface
        self._mappings = {}  # layer id -> FlagDefinition

        container = QWidget()
        layout = QVBoxLayout(container)
        self.toolbar = QToolBar(container)
        layout.addWidget(self.toolbar)
        self.table = QTableWidget(0, len(self.COLUMNS_CATEGORIZED))
        self.table.setHorizontalHeaderLabels(self.COLUMNS_CATEGORIZED)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        self.setWidget(container)

    def set_mapping(self, layer, definition, persist=True):
        """Register ``definition`` as the mapping for ``layer``.

        ``persist`` also stores it as a layer custom property so it
        survives closing and reopening the project. Pass False for
        mappings that are cheap to rediscover (e.g. freshly auto-detected
        from the raster's own CF metadata) to avoid writing redundant
        state into the project file.
        """
        self._mappings[layer.id()] = definition
        if persist:
            save_mapping_to_layer(layer, definition)

    def mapping_for(self, layer_id):
        return self._mappings.get(layer_id)

    def clear_mapping(self, layer):
        self._mappings.pop(layer.id(), None)
        clear_mapping_on_layer(layer)

    def update_position(self, map_point):
        rows = []
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsRasterLayer) or not layer.isValid():
                continue
            if not layer.extent().contains(map_point):
                continue

            provider = layer.dataProvider()
            definition = self._mappings.get(layer.id())
            for band in range(1, layer.bandCount() + 1):
                sample, ok = provider.sample(map_point, band)
                if not ok:
                    continue
                if definition is not None:
                    hits = definition.decode_detailed(sample)
                    meaning_text = ", ".join(meaning for _, meaning in hits) if hits else "(no match)"
                    is_bitmask = definition.mode is FlagMode.BITMASK
                    bits_text = ", ".join(str(bit) for bit, _ in hits) if is_bitmask else ""
                else:
                    meaning_text = "(no mapping - see Flag Viewer > Load/Edit Mapping)"
                    is_bitmask = False
                    bits_text = ""
                rows.append((layer.name(), str(band), str(sample), bits_text, meaning_text, is_bitmask))
        self._populate(rows)

    def _populate(self, rows):
        show_bits = any(is_bitmask for *_, is_bitmask in rows)
        columns = self.COLUMNS_BITMASK if show_bits else self.COLUMNS_CATEGORIZED
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        self.table.setRowCount(len(rows))
        for row_index, (layer_name, band, value, bits_text, meaning_text, _) in enumerate(rows):
            values = (layer_name, band, value, bits_text, meaning_text) if show_bits else (layer_name, band, value, meaning_text)
            for column_index, cell_value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(cell_value))

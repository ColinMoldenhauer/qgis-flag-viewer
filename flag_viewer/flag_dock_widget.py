"""Dock widget showing the decoded flag meaning(s) for every raster/mesh
layer under the cursor, one row per (layer, band) or (layer, dataset group).
"""
import math

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMeshDatasetIndex, QgsMeshLayer, QgsProject, QgsRasterLayer

from .core.flag_decoder import FlagMode
from .core.layer_property import clear_mapping_on_layer, save_mapping_to_layer


class FlagViewerDockWidget(QDockWidget):
    COLUMNS_CATEGORIZED = ("Layer", "Band/Group", "Value", "Meaning")
    COLUMNS_BITMASK = ("Layer", "Band/Group", "Value", "Bit(s)", "Meaning(s)")

    TITLE = "Flag Viewer"

    SCOPE_ALL = "all"
    SCOPE_VISIBLE = "visible"
    SCOPE_SELECTED = "selected"
    SCOPE_SETTINGS_KEY = "FlagViewer/layer_scope"

    def __init__(self, iface, parent=None):
        super().__init__(self.TITLE, parent)
        self.iface = iface
        self._mappings = {}  # layer id -> FlagDefinition
        self._last_map_point = None

        container = QWidget()
        layout = QVBoxLayout(container)
        self.toolbar = QToolBar(container)
        # Not added to the toolbar here: the plugin appends these after its
        # own actions, so the combo ends up to the right of Load/Edit/Clear/Lock.
        self.layer_scope_label = QLabel("Layers: ")
        self.layer_scope_combo = QComboBox(container)
        self.layer_scope_combo.setToolTip("Which layers to sample under the cursor")
        self.layer_scope_combo.addItem("All", self.SCOPE_ALL)
        self.layer_scope_combo.addItem("Visible", self.SCOPE_VISIBLE)
        self.layer_scope_combo.addItem("Selected", self.SCOPE_SELECTED)
        saved_scope = QSettings().value(self.SCOPE_SETTINGS_KEY, self.SCOPE_ALL)
        index = self.layer_scope_combo.findData(saved_scope)
        self.layer_scope_combo.setCurrentIndex(index if index >= 0 else 0)
        self.layer_scope_combo.currentIndexChanged.connect(self._on_layer_scope_changed)
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

    def set_locked(self, locked):
        """Reflect the map tool's lock state in the dock's title bar."""
        self.setWindowTitle(f"{self.TITLE} (locked)" if locked else self.TITLE)

    def update_position(self, map_point):
        self._last_map_point = map_point
        rows = []
        canvas_temporal_range = self.iface.mapCanvas().temporalRange()
        for layer in self._layers_in_scope():
            if not layer.isValid() or not layer.extent().contains(map_point):
                continue
            if isinstance(layer, QgsRasterLayer):
                rows.extend(self._raster_rows(layer, map_point))
            elif isinstance(layer, QgsMeshLayer):
                rows.extend(self._mesh_rows(layer, map_point, canvas_temporal_range))
        self._populate(rows)

    def _on_layer_scope_changed(self, _index):
        QSettings().setValue(self.SCOPE_SETTINGS_KEY, self.layer_scope_combo.currentData())
        if self._last_map_point is not None:
            self.update_position(self._last_map_point)

    def _layers_in_scope(self):
        scope = self.layer_scope_combo.currentData()
        if scope == self.SCOPE_SELECTED:
            return self.iface.layerTreeView().selectedLayers()
        if scope == self.SCOPE_VISIBLE:
            root = QgsProject.instance().layerTreeRoot()
            layers = []
            for layer in QgsProject.instance().mapLayers().values():
                node = root.findLayer(layer.id())
                if node is not None and node.isVisible():
                    layers.append(layer)
            return layers
        return QgsProject.instance().mapLayers().values()

    def _raster_rows(self, layer, map_point):
        provider = layer.dataProvider()
        definition = self._mappings.get(layer.id())
        rows = []
        for band in range(1, layer.bandCount() + 1):
            sample, ok = provider.sample(map_point, band)
            if not ok:
                continue
            rows.append(self._build_row(layer.name(), str(band), sample, definition))
        return rows

    def _mesh_rows(self, layer, map_point, canvas_temporal_range):
        provider = layer.dataProvider()
        definition = self._mappings.get(layer.id())
        rows = []
        for group in range(provider.datasetGroupCount()):
            group_meta = provider.datasetGroupMetadata(group)
            if not group_meta.isScalar():
                continue  # flag decoding doesn't apply to vector (x/y) datasets
            if group_meta.isTemporal():
                dataset_index = layer.datasetIndexAtTime(canvas_temporal_range, group)
            else:
                dataset_index = QgsMeshDatasetIndex(group, 0)
            if not dataset_index.isValid():
                continue
            sample = layer.datasetValue(dataset_index, map_point).scalar()
            if math.isnan(sample):
                continue  # outside the mesh domain or an inactive/dry element
            group_label = group_meta.name() or f"Group {group}"
            rows.append(self._build_row(layer.name(), group_label, sample, definition))
        return rows

    def _build_row(self, layer_name, band_label, sample, definition):
        if definition is not None:
            hits = definition.decode_detailed(sample)
            meaning_text = ", ".join(meaning for _, meaning in hits) if hits else "(no match)"
            is_bitmask = definition.mode is FlagMode.BITMASK
            bits_text = ", ".join(str(bit) for bit, _ in hits) if is_bitmask else ""
        else:
            meaning_text = "(no mapping - see Flag Viewer > Load/Edit Mapping)"
            is_bitmask = False
            bits_text = ""
        return (layer_name, band_label, str(sample), bits_text, meaning_text, is_bitmask)

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

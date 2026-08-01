"""Dock widget showing the decoded flag meaning(s) for every raster/mesh
layer under the cursor, one row per (layer, band) or (layer, dataset group).
"""
import math

from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHeaderView,
    QLabel,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from qgis.core import Qgis, QgsMeshDatasetIndex, QgsMeshLayer, QgsProject, QgsRasterLayer

from .core.cf_metadata import band_is_integer_type
from .core.flag_decoder import FlagMode
from .core.layer_property import clear_mapping_on_layer, save_mapping_to_layer

# QGIS always samples raster/mesh values as double regardless of the
# underlying storage type, so displaying str(sample) directly would show
# e.g. "3.0" for data that's actually integer. These are the Qgis.DataType
# members that represent integer storage; look them up with getattr since
# not all of them exist in every QGIS version.
_INTEGER_RASTER_DATA_TYPES = frozenset(
    dt
    for dt in (
        getattr(Qgis.DataType, name, None)
        for name in ("Byte", "Int8", "UInt16", "Int16", "UInt32", "Int32", "CInt16", "CInt32")
    )
    if dt is not None
)


class FlagViewerDockWidget(QDockWidget):
    # (key, label) pairs, keyed on a stable identifier rather than the
    # label alone: "Meaning" (categorized) and "Meaning(s)" (bitmask) are
    # the same logical column shown under different names depending on
    # what's under the cursor, and a hide/show choice needs to survive
    # that mode switch instead of resetting.
    COLUMN_DEFS_CATEGORIZED = (
        ("layer", "Layer"),
        ("band_group", "Band/Group"),
        ("value", "Value"),
        ("meaning", "Meaning"),
    )
    COLUMN_DEFS_BITMASK = (
        ("layer", "Layer"),
        ("band_group", "Band/Group"),
        ("value", "Value"),
        ("bits", "Bit(s)"),
        ("meaning", "Meaning(s)"),
    )
    # Every column that can ever appear, for a header context menu that
    # offers the full set regardless of which mode happens to be showing
    # right now (e.g. so "Bit(s)" can be re-enabled even while the cursor
    # is over non-bitmask data and that column isn't currently on screen).
    COLUMN_MENU_LABELS = {
        "layer": "Layer",
        "band_group": "Band/Group",
        "value": "Value",
        "bits": "Bit(s)",
        "meaning": "Meaning",
    }

    TITLE = "Flag Viewer"

    SCOPE_ALL = "all"
    SCOPE_VISIBLE = "visible"
    SCOPE_SELECTED = "selected"
    SCOPE_SETTINGS_KEY = "FlagViewer/layer_scope"
    HIDDEN_COLUMNS_SETTINGS_KEY = "FlagViewer/hidden_columns"

    def __init__(self, iface, parent=None):
        super().__init__(self.TITLE, parent)
        self.iface = iface
        self._mappings = {}  # layer id -> FlagDefinition
        self._last_map_point = None
        self._column_keys = []  # key per current column index, set by _set_header_columns
        saved_hidden = QSettings().value(self.HIDDEN_COLUMNS_SETTINGS_KEY, "")
        self._hidden_columns = set(filter(None, saved_hidden.split(",")))

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
        self.table = QTableWidget(0, len(self.COLUMN_DEFS_CATEGORIZED))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)
        self.table.verticalHeader().setVisible(False)
        self._set_header_columns(self.COLUMN_DEFS_CATEGORIZED)
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
            is_integer = provider.dataType(band) in _INTEGER_RASTER_DATA_TYPES
            rows.append(self._build_row(layer.name(), str(band), sample, definition, is_integer))
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
            # MDAL normalizes every mesh dataset to double, so unlike
            # rasters there's no dtype to ask the provider for directly.
            # Same as the grid-as-mesh CF metadata fallback (see
            # FlagViewerPlugin._auto_detect_mesh_layer): a plain gridded
            # NetCDF loaded as a mesh bridges 1:1 to GDAL raster bands, so
            # that's checked here too. Genuine mesh formats (UGRID etc.)
            # have no such source band, so this stays unknown -> float.
            is_integer = bool(band_is_integer_type(layer.source(), band_no=group + 1))
            rows.append(self._build_row(layer.name(), group_label, sample, definition, is_integer))
        return rows

    def _build_row(self, layer_name, band_label, sample, definition, is_integer=False):
        if definition is not None:
            hits = definition.decode_detailed(sample)
            meaning_text = ", ".join(meaning for _, meaning in hits) if hits else "(no match)"
            is_bitmask = definition.mode is FlagMode.BITMASK
            bits_text = ", ".join(str(bit) for bit, _ in hits) if is_bitmask else ""
        else:
            meaning_text = "(no mapping - see Flag Viewer > Load/Edit Mapping)"
            is_bitmask = False
            bits_text = ""
        value_text = str(int(round(sample))) if is_integer else str(sample)
        return (layer_name, band_label, value_text, bits_text, meaning_text, is_bitmask)

    def _show_header_context_menu(self, pos):
        header = self.table.horizontalHeader()
        visible_count = sum(1 for key in self._column_keys if key not in self._hidden_columns)
        menu = QMenu(self.table)
        for key in self.COLUMN_MENU_LABELS:
            hidden = key in self._hidden_columns
            action = menu.addAction(self.COLUMN_MENU_LABELS[key])
            action.setCheckable(True)
            action.setChecked(not hidden)
            # Keep at least one currently-shown column visible so the table
            # never goes empty; a column not shown right now (e.g. "Bit(s)"
            # while looking at non-bitmask data) is always safe to toggle.
            shown_now = key in self._column_keys
            action.setEnabled(hidden or not shown_now or visible_count > 1)
            action.toggled.connect(
                lambda checked, key=key: self._set_column_hidden(key, not checked)
            )
        menu.exec_(header.mapToGlobal(pos))

    def _set_column_hidden(self, column_key, hidden):
        if hidden:
            self._hidden_columns.add(column_key)
        else:
            self._hidden_columns.discard(column_key)
        QSettings().setValue(self.HIDDEN_COLUMNS_SETTINGS_KEY, ",".join(sorted(self._hidden_columns)))
        self._apply_column_visibility()

    def _apply_column_visibility(self):
        header = self.table.horizontalHeader()
        for column_index, key in enumerate(self._column_keys):
            header.setSectionHidden(column_index, key in self._hidden_columns)

    def _set_header_columns(self, column_defs):
        self._column_keys = [key for key, _label in column_defs]
        self.table.setColumnCount(len(column_defs))
        self.table.setHorizontalHeaderLabels([label for _key, label in column_defs])
        self._apply_column_visibility()

    def _populate(self, rows):
        show_bits = any(is_bitmask for *_, is_bitmask in rows)
        self._set_header_columns(self.COLUMN_DEFS_BITMASK if show_bits else self.COLUMN_DEFS_CATEGORIZED)

        self.table.setRowCount(len(rows))
        for row_index, (layer_name, band, value, bits_text, meaning_text, _) in enumerate(rows):
            values = (layer_name, band, value, bits_text, meaning_text) if show_bits else (layer_name, band, value, meaning_text)
            for column_index, cell_value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(cell_value))

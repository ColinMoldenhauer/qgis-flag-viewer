"""Main plugin class: wires up the toolbar action, map tool and dock widget."""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QSizePolicy, QWidget
from qgis.core import QgsMeshLayer, QgsProject, QgsRasterLayer

from .core.cf_metadata import detect_from_band_metadata, detect_from_raster_path
from .core.layer_property import load_mapping_from_layer
from .core.mapping_io import load_mapping
from .flag_dock_widget import FlagViewerDockWidget
from .flag_map_tool import FlagIdentifyMapTool
from .mapping_dialog import MappingDialog

MENU_NAME = "Flag Viewer"


class FlagViewerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.map_tool = None
        self.dock_widget = None
        self.toggle_action = None
        self.load_mapping_action = None
        self.edit_mapping_action = None
        self.clear_mapping_action = None
        self.lock_action = None

    def _icon(self, name):
        return QIcon(os.path.join(self.plugin_dir, "resources", name))

    def initGui(self):
        self.toggle_action = QAction(self._icon("icon.svg"), "Flag Viewer", self.iface.mainWindow())
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggle)
        self.iface.addToolBarIcon(self.toggle_action)

        self.load_mapping_action = QAction(
            self._icon("load_mapping.svg"), "Load Flag Mapping...", self.iface.mainWindow()
        )
        self.load_mapping_action.triggered.connect(self.load_mapping_for_active_layer)

        self.edit_mapping_action = QAction(
            self._icon("edit_mapping.svg"), "Edit Flag Mapping...", self.iface.mainWindow()
        )
        self.edit_mapping_action.triggered.connect(self.edit_mapping_for_active_layer)

        self.clear_mapping_action = QAction(
            self._icon("clear_mapping.svg"), "Clear Flag Mapping", self.iface.mainWindow()
        )
        self.clear_mapping_action.triggered.connect(self.clear_mapping_for_active_layer)

        self.lock_action = QAction(self._icon("lock.svg"), "Lock Position", self.iface.mainWindow())
        self.lock_action.setCheckable(True)
        self._update_lock_tooltip(locked=False)
        self.lock_action.toggled.connect(self._set_map_tool_locked)

        self.dock_widget = FlagViewerDockWidget(self.iface)
        self.dock_widget.toolbar.addAction(self.load_mapping_action)
        self.dock_widget.toolbar.addAction(self.edit_mapping_action)
        self.dock_widget.toolbar.addAction(self.clear_mapping_action)
        self.dock_widget.toolbar.addSeparator()
        self.dock_widget.toolbar.addAction(self.lock_action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.dock_widget.toolbar.addWidget(spacer)
        self.dock_widget.toolbar.addWidget(self.dock_widget.layer_scope_label)
        self.dock_widget.toolbar.addWidget(self.dock_widget.layer_scope_combo)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()

        QgsProject.instance().layersAdded.connect(self._auto_detect_layers)

    def unload(self):
        QgsProject.instance().layersAdded.disconnect(self._auto_detect_layers)
        self.iface.removeToolBarIcon(self.toggle_action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
        self.map_tool = None

    def toggle(self, checked):
        canvas = self.iface.mapCanvas()
        if checked:
            self._auto_detect_layers(QgsProject.instance().mapLayers().values())
            self.map_tool = FlagIdentifyMapTool(canvas)
            self.map_tool.positionChanged.connect(self.dock_widget.update_position)
            self.map_tool.lockChanged.connect(self._on_lock_changed)
            canvas.setMapTool(self.map_tool)
            self.dock_widget.show()
        else:
            if self.map_tool is not None:
                canvas.unsetMapTool(self.map_tool)
            self.dock_widget.hide()

    def _set_map_tool_locked(self, locked):
        if self.map_tool is not None:
            self.map_tool.set_locked(locked)

    def _on_lock_changed(self, locked):
        self.dock_widget.set_locked(locked)
        self.lock_action.blockSignals(True)
        self.lock_action.setChecked(locked)
        self.lock_action.blockSignals(False)
        self._update_lock_tooltip(locked)

    def _update_lock_tooltip(self, locked):
        if locked:
            self.lock_action.setToolTip(
                "Position locked. Click to unlock (or right-click the map, or press Escape)."
            )
        else:
            self.lock_action.setToolTip("Click a location on the map to lock the reported position.")

    def _auto_detect_layers(self, layers):
        for layer in layers:
            if isinstance(layer, QgsRasterLayer):
                self._auto_detect_raster_layer(layer)
            elif isinstance(layer, QgsMeshLayer):
                self._auto_detect_mesh_layer(layer)

    def _auto_detect_raster_layer(self, layer):
        if self.dock_widget.mapping_for(layer.id()) is not None:
            return  # don't clobber a mapping the user already loaded/edited

        # A mapping saved on the layer (from a previous Load/Edit in this or
        # an earlier session) takes priority over re-running auto-detection,
        # since it may be a user-supplied mapping that auto-detection can't
        # reproduce (e.g. a plain GeoTIFF).
        definition = load_mapping_from_layer(layer)
        if definition is not None:
            self.dock_widget.set_mapping(layer, definition, persist=False)
            return

        definition = detect_from_raster_path(layer.source())
        if definition is not None:
            # Recoverable from the file's own CF metadata every time, so
            # there's no need to also duplicate it into the project.
            self.dock_widget.set_mapping(layer, definition, persist=False)

    def _auto_detect_mesh_layer(self, layer):
        if self.dock_widget.mapping_for(layer.id()) is not None:
            return

        definition = load_mapping_from_layer(layer)
        if definition is not None:
            self.dock_widget.set_mapping(layer, definition, persist=False)
            return

        # For genuine mesh formats (UGRID etc.), MDAL copies each dataset
        # group's NetCDF variable attributes into its extra options, so the
        # CF flag_* detection logic applies unchanged. But when a plain
        # gridded NetCDF is loaded as a mesh, MDAL bridges it from the GDAL
        # raster driver instead and that bridge drops custom attributes --
        # extraOptions() ends up with only a "name" like "GDAL Band Number
        # 1". In that case fall back to reading the flag_* attributes
        # straight from the source file's matching GDAL raster band (group
        # index and band number are 1:1 for this bridge).
        provider = layer.dataProvider()
        for group in range(provider.datasetGroupCount()):
            definition = detect_from_band_metadata(provider.datasetGroupMetadata(group).extraOptions())
            if definition is None:
                definition = detect_from_raster_path(layer.source(), band_no=group + 1)
            if definition is not None:
                self.dock_widget.set_mapping(layer, definition, persist=False)
                return

    def load_mapping_for_active_layer(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, (QgsRasterLayer, QgsMeshLayer)):
            QMessageBox.warning(self.iface.mainWindow(), MENU_NAME, "Select a raster or mesh layer first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self.iface.mainWindow(), "Load Flag Mapping", "", "Flag mapping (*.json *.yaml *.yml)"
        )
        if not path:
            return
        try:
            definition = load_mapping(path)
        except Exception as exc:
            QMessageBox.critical(self.iface.mainWindow(), MENU_NAME, f"Could not load mapping:\n{exc}")
            return
        self.dock_widget.set_mapping(layer, definition)

    def edit_mapping_for_active_layer(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, (QgsRasterLayer, QgsMeshLayer)):
            QMessageBox.warning(self.iface.mainWindow(), MENU_NAME, "Select a raster or mesh layer first.")
            return
        existing = self.dock_widget.mapping_for(layer.id())
        dialog = MappingDialog(existing, parent=self.iface.mainWindow(), layer_name=layer.name())
        if dialog.exec_():
            definition = dialog.to_definition()
            if definition is not None:
                self.dock_widget.set_mapping(layer, definition)

    def clear_mapping_for_active_layer(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, (QgsRasterLayer, QgsMeshLayer)):
            QMessageBox.warning(self.iface.mainWindow(), MENU_NAME, "Select a raster or mesh layer first.")
            return
        self.dock_widget.clear_mapping(layer)

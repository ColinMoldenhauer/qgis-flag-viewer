"""Main plugin class: wires up the toolbar action, map tool and dock widget."""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import QgsProject, QgsRasterLayer

from .core.cf_metadata import detect_from_raster_path
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

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "resources", "icon.svg"))

        self.toggle_action = QAction(icon, "Flag Viewer", self.iface.mainWindow())
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggle)
        self.iface.addToolBarIcon(self.toggle_action)
        self.iface.addPluginToRasterMenu(MENU_NAME, self.toggle_action)

        self.load_mapping_action = QAction("Load Flag Mapping...", self.iface.mainWindow())
        self.load_mapping_action.triggered.connect(self.load_mapping_for_active_layer)
        self.iface.addPluginToRasterMenu(MENU_NAME, self.load_mapping_action)

        self.edit_mapping_action = QAction("Edit Flag Mapping...", self.iface.mainWindow())
        self.edit_mapping_action.triggered.connect(self.edit_mapping_for_active_layer)
        self.iface.addPluginToRasterMenu(MENU_NAME, self.edit_mapping_action)

        self.dock_widget = FlagViewerDockWidget(self.iface)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()

    def unload(self):
        self.iface.removeToolBarIcon(self.toggle_action)
        self.iface.removePluginRasterMenu(MENU_NAME, self.toggle_action)
        self.iface.removePluginRasterMenu(MENU_NAME, self.load_mapping_action)
        self.iface.removePluginRasterMenu(MENU_NAME, self.edit_mapping_action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
        self.map_tool = None

    def toggle(self, checked):
        canvas = self.iface.mapCanvas()
        if checked:
            self._auto_detect_all_layers()
            self.map_tool = FlagIdentifyMapTool(canvas)
            self.map_tool.positionChanged.connect(self.dock_widget.update_position)
            canvas.setMapTool(self.map_tool)
            self.dock_widget.show()
        else:
            if self.map_tool is not None:
                canvas.unsetMapTool(self.map_tool)
            self.dock_widget.hide()

    def _auto_detect_all_layers(self):
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsRasterLayer):
                continue
            if self.dock_widget.mapping_for(layer.id()) is not None:
                continue  # don't clobber a mapping the user already loaded/edited
            definition = detect_from_raster_path(layer.source())
            if definition is not None:
                self.dock_widget.set_mapping(layer.id(), definition)

    def load_mapping_for_active_layer(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, QgsRasterLayer):
            QMessageBox.warning(self.iface.mainWindow(), MENU_NAME, "Select a raster layer first.")
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
        self.dock_widget.set_mapping(layer.id(), definition)

    def edit_mapping_for_active_layer(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, QgsRasterLayer):
            QMessageBox.warning(self.iface.mainWindow(), MENU_NAME, "Select a raster layer first.")
            return
        existing = self.dock_widget.mapping_for(layer.id())
        dialog = MappingDialog(existing, parent=self.iface.mainWindow())
        if dialog.exec_():
            definition = dialog.to_definition()
            if definition is not None:
                self.dock_widget.set_mapping(layer.id(), definition)

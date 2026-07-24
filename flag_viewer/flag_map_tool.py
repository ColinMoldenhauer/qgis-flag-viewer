"""Map tool that reports the map coordinate under the cursor as it moves.

Mirrors the approach Value Tool uses (a QgsMapTool driven by
canvasMoveEvent), but emits the map-CRS point directly instead of a screen
QPoint, since that's all the dock widget needs for dataProvider().sample().
"""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.gui import QgsMapTool


class FlagIdentifyMapTool(QgsMapTool):
    positionChanged = pyqtSignal(object)  # QgsPointXY, in the canvas' map CRS

    def __init__(self, canvas):
        super().__init__(canvas)
        self.setCursor(Qt.CrossCursor)

    def canvasMoveEvent(self, event):
        self.positionChanged.emit(event.mapPoint())

    def canvasReleaseEvent(self, event):
        self.positionChanged.emit(event.mapPoint())

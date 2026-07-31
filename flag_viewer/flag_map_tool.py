"""Map tool that reports the map coordinate under the cursor as it moves.

Mirrors the approach Value Tool uses (a QgsMapTool driven by
canvasMoveEvent), but emits the map-CRS point directly instead of a screen
QPoint, since that's all the dock widget needs for dataProvider().sample().

Left-clicking locks the reported position so the dock widget's table stops
following the cursor, which leaves it free to be inspected or interacted
with (e.g. selecting/copying cells, using the toolbar) without the values
changing underfoot. Right-click, Escape, or the dock widget's lock button
unlock it again and resume live tracking.
"""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.gui import QgsMapTool


class FlagIdentifyMapTool(QgsMapTool):
    positionChanged = pyqtSignal(object)  # QgsPointXY, in the canvas' map CRS
    lockChanged = pyqtSignal(bool)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.setCursor(Qt.CrossCursor)
        self._locked = False

    def is_locked(self):
        return self._locked

    def set_locked(self, locked):
        if locked == self._locked:
            return
        self._locked = locked
        self.lockChanged.emit(self._locked)

    def canvasMoveEvent(self, event):
        if not self._locked:
            self.positionChanged.emit(event.mapPoint())

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.set_locked(False)
            return
        self.positionChanged.emit(event.mapPoint())
        self.set_locked(True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._locked:
            self.set_locked(False)
            event.accept()
        else:
            event.ignore()

    def deactivate(self):
        self.set_locked(False)
        super().deactivate()

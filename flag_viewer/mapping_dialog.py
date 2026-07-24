"""Minimal GUI editor for a value/mask -> meaning mapping.

Used as a fallback when auto-detection (core/cf_metadata.py) fails and no
JSON/YAML sidecar exists yet. Edits happen in a plain table; "Save to
file..." writes the same JSON/YAML format core/mapping_io.py reads, so a
mapping created here can be reused across projects or checked into version
control next to the data.
"""
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .core.flag_decoder import FlagDefinition
from .core.mapping_io import save_mapping


class MappingDialog(QDialog):
    def __init__(self, definition=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Flag Mapping")
        self.resize(420, 360)

        layout = QVBoxLayout(self)

        mode_row = QHBoxLayout()
        self.categorized_radio = QRadioButton("Categorized (one value = one meaning)")
        self.bitmask_radio = QRadioButton("Bitmask (each bit = one meaning)")
        self.categorized_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.categorized_radio)
        mode_group.addButton(self.bitmask_radio)
        mode_row.addWidget(self.categorized_radio)
        mode_row.addWidget(self.bitmask_radio)
        layout.addLayout(mode_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Value / Mask", "Meaning"])
        layout.addWidget(self.table)

        row_buttons = QHBoxLayout()
        add_button = QPushButton("Add row")
        add_button.clicked.connect(lambda: self._add_row())
        remove_button = QPushButton("Remove selected row")
        remove_button.clicked.connect(self._remove_selected_row)
        row_buttons.addWidget(add_button)
        row_buttons.addWidget(remove_button)
        layout.addLayout(row_buttons)

        save_button = QPushButton("Save to file...")
        save_button.clicked.connect(self._save_to_file)
        layout.addWidget(save_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if definition is not None:
            self.bitmask_radio.setChecked(definition.masks is not None)
            self.categorized_radio.setChecked(definition.masks is None)
            numbers = definition.masks if definition.masks else definition.values
            for value, meaning in zip(numbers, definition.meanings):
                self._add_row(value, meaning)

    def _add_row(self, value="", meaning=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(value)))
        self.table.setItem(row, 1, QTableWidgetItem(str(meaning)))

    def _remove_selected_row(self):
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def to_definition(self):
        numbers, meanings = [], []
        for row in range(self.table.rowCount()):
            value_item = self.table.item(row, 0)
            meaning_item = self.table.item(row, 1)
            if not value_item or not meaning_item or not value_item.text().strip():
                continue
            numbers.append(int(value_item.text(), 0))  # base=0: allows "0x04" too
            meanings.append(meaning_item.text().strip())
        if not numbers:
            return None
        if self.bitmask_radio.isChecked():
            return FlagDefinition(meanings=meanings, masks=numbers)
        return FlagDefinition(meanings=meanings, values=numbers)

    def _save_to_file(self):
        definition = self.to_definition()
        if definition is None:
            QMessageBox.warning(self, "Flag Viewer", "Add at least one row first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Flag Mapping", "", "JSON (*.json);;YAML (*.yaml *.yml)"
        )
        if not path:
            return
        save_mapping(path, definition)

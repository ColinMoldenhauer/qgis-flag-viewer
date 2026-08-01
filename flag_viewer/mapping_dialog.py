"""Minimal GUI editor for a value/mask -> meaning mapping.

Used as a fallback when auto-detection (core/cf_metadata.py) fails and no
JSON/YAML sidecar exists yet. Edits happen in a plain table; "Save to
file..." writes the same JSON/YAML format core/mapping_io.py reads, so a
mapping created here can be reused across projects or checked into version
control next to the data.
"""
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .core.cf_metadata import CF_MASKS_KEY, CF_MEANINGS_KEY, CF_VALUES_KEY
from .core.flag_decoder import FlagDefinition, parse_cf_attributes
from .core.mapping_io import save_mapping


def _mask_to_bit_index(mask):
    """Inverse of the dialog's ``1 << index`` bit-index-to-mask conversion.

    Falls back to showing the raw mask value for masks that aren't a single
    bit (e.g. combined multi-bit fields loaded from a hand-written sidecar
    file) since those can't be expressed as one index -- editing and saving
    such a row here would need to be re-entered by hand anyway.
    """
    if mask > 0 and mask & (mask - 1) == 0:
        return mask.bit_length() - 1
    return mask


class MappingDialog(QDialog):
    def __init__(self, definition=None, parent=None, layer_name=None, metadata_sources=None):
        super().__init__(parent)
        title = "Edit Flag Mapping"
        if layer_name:
            title = f"{title} – {layer_name}"
        self.setWindowTitle(title)
        self.resize(420, 360)

        # {source label -> raw metadata dict}, e.g. {"Band 1": {...}}, used
        # by "From metadata...". Empty/None just disables that button, so
        # callers that can't offer metadata (or don't care to) can omit it.
        self._metadata_sources = metadata_sources or {}

        layout = QVBoxLayout(self)

        if layer_name:
            layout.addWidget(QLabel(f"Layer: <b>{layer_name}</b>"))

        mode_row = QHBoxLayout()
        self.categorized_radio = QRadioButton("Categorized (one value = one meaning)")
        self.categorized_radio.setToolTip(
            "Each field value maps to exactly one meaning, e.g. 0 = \"Draft\", "
            "1 = \"Published\", 2 = \"Archived\"."
        )
        self.bitmask_radio = QRadioButton("Bitmask (each bit = one meaning)")
        self.bitmask_radio.setToolTip(
            "<p>The field is a set of independent on/off flags packed into "
            "one integer.</p>"
            "<p>Each row's number is the bit's index (0, 1, 2, ...), not its "
            "value: bit 0 = 1, bit 1 = 2, bit 2 = 4, and so on.</p>"
            "<p>Several bits can be set at once, e.g. a value of 5 has bit 0 "
            "and bit 2 set.</p>"
        )
        self.categorized_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.categorized_radio)
        mode_group.addButton(self.bitmask_radio)
        mode_row.addWidget(self.categorized_radio)
        mode_row.addWidget(self.bitmask_radio)
        layout.addLayout(mode_row)

        self.table = QTableWidget(0, 2)
        self._update_value_column_header()
        layout.addWidget(self.table)

        self.categorized_radio.toggled.connect(self._update_value_column_header)

        row_buttons = QHBoxLayout()
        add_button = QPushButton("Add row")
        add_button.clicked.connect(lambda: self._add_row())
        remove_button = QPushButton("Remove selected row")
        remove_button.clicked.connect(self._remove_selected_row)
        row_buttons.addWidget(add_button)
        row_buttons.addWidget(remove_button)
        layout.addLayout(row_buttons)

        action_row = QHBoxLayout()
        from_metadata_button = QPushButton("From metadata...")
        from_metadata_button.setEnabled(bool(self._metadata_sources))
        from_metadata_button.setToolTip(
            "Pick which metadata fields hold the flag meanings/values/masks "
            "-- for files that carry this information under non-standard "
            "attribute names, so auto-detection didn't find it."
            if self._metadata_sources
            else "No metadata available for this layer."
        )
        from_metadata_button.clicked.connect(self._from_metadata)
        action_row.addWidget(from_metadata_button)
        save_button = QPushButton("Save to file...")
        save_button.clicked.connect(self._save_to_file)
        action_row.addWidget(save_button)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if definition is not None:
            self._load_definition(definition)

    def _load_definition(self, definition):
        self.bitmask_radio.setChecked(definition.masks is not None)
        self.categorized_radio.setChecked(definition.masks is None)
        self.table.setRowCount(0)
        if definition.masks:
            numbers = [_mask_to_bit_index(mask) for mask in definition.masks]
        else:
            numbers = definition.values
        for value, meaning in zip(numbers, definition.meanings):
            self._add_row(value, meaning)

    def _from_metadata(self):
        if self.table.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Flag Viewer",
                "This replaces the current rows with the mapping built from "
                "metadata. Continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        picker = MetadataFieldPickerDialog(self._metadata_sources, parent=self)
        if picker.exec_() and picker.definition() is not None:
            self._load_definition(picker.definition())

    def _update_value_column_header(self):
        label = "Value" if self.categorized_radio.isChecked() else "Bit"
        self.table.setHorizontalHeaderLabels([label, "Meaning"])

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
            return FlagDefinition(meanings=meanings, masks=[1 << n for n in numbers])
        return FlagDefinition(meanings=meanings, values=numbers)

    def _validate_and_accept(self):
        if self.bitmask_radio.isChecked():
            for row in range(self.table.rowCount()):
                value_item = self.table.item(row, 0)
                text = value_item.text().strip() if value_item else ""
                if not text:
                    continue
                if int(text, 0) < 0:
                    QMessageBox.warning(
                        self,
                        "Flag Viewer",
                        "Bit index must be 0 or greater (0 = value 1, 1 = value 2, "
                        "2 = value 4, ...).",
                    )
                    return
        self.accept()

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


class MetadataFieldPickerDialog(QDialog):
    """Lets the user build a FlagDefinition by picking which raw metadata
    attributes hold the meanings/values/masks.

    Auto-detection (core/cf_metadata.py) only recognizes the literal CF
    attribute names (flag_meanings/flag_values/flag_masks). Some files carry
    the same information under other names, or as attributes GDAL doesn't
    surface through the standard CF path -- this dialog lets the user browse
    all raw metadata and map arbitrary fields onto the three roles instead.
    """

    NONE_LABEL = "(none)"

    def __init__(self, metadata_sources, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Mapping From Metadata")
        self.resize(480, 420)
        self._sources = metadata_sources
        self._definition = None

        layout = QVBoxLayout(self)

        self.source_combo = None
        if len(self._sources) > 1:
            source_row = QHBoxLayout()
            source_row.addWidget(QLabel("Band/Group:"))
            self.source_combo = QComboBox(self)
            self.source_combo.addItems(list(self._sources.keys()))
            self.source_combo.currentTextChanged.connect(self._populate_fields)
            source_row.addWidget(self.source_combo)
            layout.addLayout(source_row)

        self.preview_table = QTableWidget(0, 2, self)
        self.preview_table.setHorizontalHeaderLabels(["Attribute", "Value"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.preview_table)

        form = QFormLayout()
        self.meanings_combo = QComboBox(self)
        self.values_combo = QComboBox(self)
        self.masks_combo = QComboBox(self)
        form.addRow("Meanings field:", self.meanings_combo)
        form.addRow("Values field:", self.values_combo)
        form.addRow("Masks field:", self.masks_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_fields(next(iter(self._sources)))

    def _populate_fields(self, label):
        metadata = self._sources[label]
        keys = list(metadata.keys())

        self.preview_table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            self.preview_table.setItem(row, 0, QTableWidgetItem(key))
            self.preview_table.setItem(row, 1, QTableWidgetItem(str(metadata[key])))

        self.meanings_combo.clear()
        self.meanings_combo.addItems(keys)
        self.values_combo.clear()
        self.values_combo.addItems([self.NONE_LABEL] + keys)
        self.masks_combo.clear()
        self.masks_combo.addItems([self.NONE_LABEL] + keys)

        self._select_default(self.meanings_combo, keys, CF_MEANINGS_KEY)
        self._select_default(self.values_combo, [self.NONE_LABEL] + keys, CF_VALUES_KEY)
        self._select_default(self.masks_combo, [self.NONE_LABEL] + keys, CF_MASKS_KEY)

    @staticmethod
    def _select_default(combo, options, preferred_key):
        if preferred_key in options:
            combo.setCurrentIndex(options.index(preferred_key))

    def _current_metadata(self):
        label = self.source_combo.currentText() if self.source_combo else next(iter(self._sources))
        return self._sources[label]

    def _validate_and_accept(self):
        metadata = self._current_metadata()
        meanings_key = self.meanings_combo.currentText()
        values_key = self.values_combo.currentText()
        masks_key = self.masks_combo.currentText()
        if not meanings_key:
            QMessageBox.warning(self, "Flag Viewer", "Select a meanings field.")
            return
        values_attr = metadata.get(values_key) if values_key != self.NONE_LABEL else None
        masks_attr = metadata.get(masks_key) if masks_key != self.NONE_LABEL else None
        try:
            self._definition = parse_cf_attributes(metadata[meanings_key], values_attr, masks_attr)
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Flag Viewer", f"Could not parse the selected fields:\n{exc}")
            return
        self.accept()

    def definition(self):
        return self._definition

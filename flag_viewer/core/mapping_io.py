"""Load/save a FlagDefinition as a JSON or YAML sidecar file.

Used when auto-detection (see cf_metadata.py) fails and the user supplies
or edits a mapping by hand -- either directly as a file, or through
mapping_dialog.MappingDialog, which writes out the same format.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .flag_decoder import FlagDefinition

PathLike = Union[str, Path]


def load_mapping(path: PathLike) -> FlagDefinition:
    path = Path(path)
    data = _read(path)
    return FlagDefinition(
        meanings=data["flag_meanings"],
        values=data.get("flag_values"),
        masks=data.get("flag_masks"),
    )


def save_mapping(path: PathLike, definition: FlagDefinition) -> None:
    path = Path(path)
    data = {"flag_meanings": list(definition.meanings)}
    if definition.values is not None:
        data["flag_values"] = list(definition.values)
    if definition.masks is not None:
        data["flag_masks"] = list(definition.masks)
    _write(path, data)


def _read(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(text)
    return json.loads(text)


def _write(path: Path, data: dict) -> None:
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

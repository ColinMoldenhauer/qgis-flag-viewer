"""Persist a FlagDefinition as a QGIS layer custom property, so a
user-supplied mapping travels with the ``.qgs``/``.qgz`` project file
itself instead of only living in a sidecar the user has to remember to
keep next to the data (see DESIGN.md section 4).

No ``qgis.core`` import here: these functions only need an object with
``setCustomProperty``/``customProperty``/``removeCustomProperty`` methods
(the relevant slice of ``QgsMapLayer``'s interface), which keeps this
unit-testable with a plain stub and consistent with the rest of
``flag_viewer.core`` staying QGIS-import-free.
"""
from __future__ import annotations

import json
from typing import Optional

from .flag_decoder import FlagDefinition
from .mapping_io import definition_from_dict, definition_to_dict

CUSTOM_PROPERTY_KEY = "flag_viewer/mapping"


def save_mapping_to_layer(layer, definition: FlagDefinition) -> None:
    layer.setCustomProperty(CUSTOM_PROPERTY_KEY, json.dumps(definition_to_dict(definition)))


def load_mapping_from_layer(layer) -> Optional[FlagDefinition]:
    """Return the mapping stored on ``layer``, or None if there isn't one
    or it can't be parsed (e.g. written by an incompatible future version).
    """
    raw = layer.customProperty(CUSTOM_PROPERTY_KEY)
    if not raw:
        return None
    try:
        return definition_from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def clear_mapping_on_layer(layer) -> None:
    layer.removeCustomProperty(CUSTOM_PROPERTY_KEY)

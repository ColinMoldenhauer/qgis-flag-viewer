"""Auto-detect CF flag_* attributes from a raster band.

GDAL's NetCDF/HDF5 drivers copy arbitrary variable attributes (including
``flag_meanings``, ``flag_values``, ``flag_masks``) into the corresponding
raster band's metadata domain, so for those formats we can read the mapping
straight out of the file with no user input. Plain GeoTIFF (and most other
formats) generally do not carry these attributes, so callers should treat a
``None`` result as "auto-detection failed, ask the user for a mapping"
rather than as an error.
"""
from __future__ import annotations

from typing import Optional

from .flag_decoder import FlagDefinition, parse_cf_attributes

CF_MEANINGS_KEY = "flag_meanings"
CF_VALUES_KEY = "flag_values"
CF_MASKS_KEY = "flag_masks"


def detect_from_band_metadata(metadata: dict) -> Optional[FlagDefinition]:
    """Build a FlagDefinition from a GDAL-style band metadata dict.

    Pure function, no GDAL dependency, so it is unit-testable on its own.
    """
    meanings = metadata.get(CF_MEANINGS_KEY)
    if not meanings:
        return None
    values = metadata.get(CF_VALUES_KEY)
    masks = metadata.get(CF_MASKS_KEY)
    try:
        return parse_cf_attributes(meanings, values, masks)
    except ValueError:
        return None


def detect_from_raster_path(path: str, band_no: int = 1) -> Optional[FlagDefinition]:
    """Open ``path`` with GDAL and try to auto-detect a flag mapping for
    the given band. Returns None if GDAL is unavailable, the file can't be
    opened, or no flag_meanings attribute is present.
    """
    return detect_from_band_metadata(get_band_metadata(path, band_no))


def get_band_metadata(path: str, band_no: int = 1) -> dict:
    """Open ``path`` with GDAL and return the raw metadata dict for the
    given band, e.g. for a "pick fields from metadata" UI where the caller
    wants to browse all attributes rather than only the recognized CF
    names. Empty if GDAL is unavailable, the file can't be opened, or the
    band doesn't exist.
    """
    try:
        from osgeo import gdal
    except ImportError:
        return {}

    dataset = gdal.Open(path)
    if dataset is None:
        return {}
    band = dataset.GetRasterBand(band_no)
    if band is None:
        return {}
    return band.GetMetadata() or {}


def band_is_integer_type(path: str, band_no: int = 1) -> Optional[bool]:
    """Open ``path`` with GDAL and report whether the given band's data type
    is an integer type (as opposed to floating point/complex). Returns None
    if GDAL is unavailable, the file can't be opened, or the band doesn't
    exist, i.e. "unknown" rather than "not integer".
    """
    try:
        from osgeo import gdal
    except ImportError:
        return None

    dataset = gdal.Open(path)
    if dataset is None:
        return None
    band = dataset.GetRasterBand(band_no)
    if band is None:
        return None
    type_name = gdal.GetDataTypeName(band.DataType)
    return "Int" in type_name or type_name == "Byte"

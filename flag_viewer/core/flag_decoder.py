"""Decode integer raster values into CF ``flag_meanings`` following the
CF Metadata Conventions section on flags:
https://cfconventions.org/cf-conventions/cf-conventions.html#flags

Three shapes are supported, mirroring the CF spec:

- ``flag_values`` only  -> "categorized": the raw value must equal one
  entry exactly, and maps to exactly one meaning.
- ``flag_masks`` only   -> "bitmask": each mask is tested against the value
  with a bitwise AND; a nonzero result means the flag is set. A value can
  match zero, one, or several meanings at once.
- both ``flag_masks`` and ``flag_values`` -> "bitmask with multi-bit
  fields": ``(value & flag_masks[i]) == flag_values[i]`` for each i. This
  also covers multi-bit sub-fields packed into one integer, not just
  single bits.

This module has no dependency on QGIS or GDAL so it can be unit tested in
isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class FlagMode(Enum):
    CATEGORIZED = "categorized"
    BITMASK = "bitmask"


@dataclass
class FlagDefinition:
    """A value/mask -> meaning mapping for one raster band."""

    meanings: Sequence[str]
    values: Optional[Sequence[int]] = None
    masks: Optional[Sequence[int]] = None

    def __post_init__(self) -> None:
        if not self.masks and not self.values:
            raise ValueError("FlagDefinition needs flag_values and/or flag_masks.")
        expected = len(self.meanings)
        for name, seq in (("flag_values", self.values), ("flag_masks", self.masks)):
            if seq is not None and len(seq) != expected:
                raise ValueError(
                    f"{name} has {len(seq)} entries, expected {expected} "
                    "to match flag_meanings."
                )

    @property
    def mode(self) -> FlagMode:
        return FlagMode.BITMASK if self.masks else FlagMode.CATEGORIZED

    def decode(self, value) -> list:
        """Return the list of meanings that apply to ``value``.

        Categorized mode returns at most one meaning. Bitmask mode may
        return several (or none, if no bit matches a known mask).
        """
        if value is None:
            return []
        value = int(value)

        if self.masks:
            hits = []
            for i, mask in enumerate(self.masks):
                bits = value & mask
                match = bits == self.values[i] if self.values else bits != 0
                if match:
                    hits.append(self.meanings[i])
            return hits

        for meaning, flag_value in zip(self.meanings, self.values):
            if value == flag_value:
                return [meaning]
        return []


def parse_cf_attributes(
    meanings_attr: str,
    values_attr: Optional[str] = None,
    masks_attr: Optional[str] = None,
) -> FlagDefinition:
    """Build a :class:`FlagDefinition` from raw CF attribute strings, e.g.
    as read from NetCDF/GDAL band metadata:

        flag_meanings = "low medium high"
        flag_values   = "1, 2, 4"   (or "1 2 4", or "{1, 2, 4}")
    """
    meanings = meanings_attr.split()
    values = _parse_numeric_list(values_attr) if values_attr else None
    masks = _parse_numeric_list(masks_attr) if masks_attr else None
    return FlagDefinition(meanings=meanings, values=values, masks=masks)


def _parse_numeric_list(raw: str) -> list:
    cleaned = raw.strip().strip("{}").replace(",", " ")
    return [int(float(token)) for token in cleaned.split()]

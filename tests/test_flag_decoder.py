import pytest

from flag_viewer.core.flag_decoder import FlagDefinition, FlagMode, parse_cf_attributes


def test_categorized_mode_exact_match():
    d = FlagDefinition(meanings=["land", "water", "cloud"], values=[1, 2, 3])
    assert d.mode is FlagMode.CATEGORIZED
    assert d.decode(2) == ["water"]


def test_categorized_mode_no_match_returns_empty():
    d = FlagDefinition(meanings=["land", "water"], values=[1, 2])
    assert d.decode(99) == []


def test_bitmask_mode_single_bits():
    d = FlagDefinition(meanings=["bit0", "bit1", "bit2"], masks=[1, 2, 4])
    assert d.mode is FlagMode.BITMASK
    assert d.decode(0b101) == ["bit0", "bit2"]
    assert d.decode(0) == []
    assert d.decode(0b111) == ["bit0", "bit1", "bit2"]


def test_bitmask_mode_with_multibit_fields():
    # e.g. a 2-bit quality field packed at bits 2-3, plus an independent
    # single-bit cloud flag at bit 0.
    d = FlagDefinition(
        meanings=["cloud", "quality_low", "quality_medium", "quality_high"],
        masks=[0b0001, 0b1100, 0b1100, 0b1100],
        values=[0b0001, 0b0100, 0b1000, 0b1100],
    )
    # cloud set, quality_medium (0b1000)
    assert d.decode(0b1001) == ["cloud", "quality_medium"]
    assert d.decode(0b0100) == ["quality_low"]


def test_decode_none_returns_empty():
    d = FlagDefinition(meanings=["a"], values=[1])
    assert d.decode(None) == []


def test_requires_values_or_masks():
    with pytest.raises(ValueError):
        FlagDefinition(meanings=["a", "b"])


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        FlagDefinition(meanings=["a", "b"], values=[1])


def test_parse_cf_attributes_space_separated():
    d = parse_cf_attributes("low medium high", "1 2 4")
    assert d.meanings == ["low", "medium", "high"]
    assert d.values == [1, 2, 4]


def test_parse_cf_attributes_brace_and_comma_separated():
    d = parse_cf_attributes("low medium high", "{1, 2, 4}")
    assert d.values == [1, 2, 4]


def test_parse_cf_attributes_with_masks():
    d = parse_cf_attributes("cloud shadow", "1, 2", "1, 2")
    assert d.masks == [1, 2]
    assert d.decode(3) == ["cloud", "shadow"]

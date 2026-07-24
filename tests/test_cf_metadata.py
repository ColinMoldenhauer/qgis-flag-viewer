from flag_viewer.core.cf_metadata import detect_from_band_metadata


def test_detect_from_band_metadata_categorized():
    metadata = {
        "flag_meanings": "clear cloud shadow",
        "flag_values": "0, 1, 2",
        "some_other_key": "ignored",
    }
    definition = detect_from_band_metadata(metadata)
    assert definition is not None
    assert definition.decode(1) == ["cloud"]


def test_detect_from_band_metadata_missing_returns_none():
    assert detect_from_band_metadata({"unrelated": "1"}) is None


def test_detect_from_band_metadata_bitmask():
    metadata = {
        "flag_meanings": "cloud shadow snow",
        "flag_masks": "1, 2, 4",
    }
    definition = detect_from_band_metadata(metadata)
    assert definition.decode(5) == ["cloud", "snow"]

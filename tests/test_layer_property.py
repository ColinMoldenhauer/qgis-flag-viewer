from flag_viewer.core.flag_decoder import FlagDefinition
from flag_viewer.core.layer_property import (
    clear_mapping_on_layer,
    load_mapping_from_layer,
    save_mapping_to_layer,
)


class FakeLayer:
    """Stands in for the slice of QgsMapLayer's custom-property interface
    that layer_property.py relies on."""

    def __init__(self):
        self._properties = {}

    def setCustomProperty(self, key, value):
        self._properties[key] = value

    def customProperty(self, key, default=None):
        return self._properties.get(key, default)

    def removeCustomProperty(self, key):
        self._properties.pop(key, None)


def test_roundtrip_categorized():
    layer = FakeLayer()
    definition = FlagDefinition(meanings=["clear", "cloud"], values=[0, 1])
    save_mapping_to_layer(layer, definition)

    loaded = load_mapping_from_layer(layer)
    assert loaded.meanings == ["clear", "cloud"]
    assert loaded.values == [0, 1]
    assert loaded.decode(1) == ["cloud"]


def test_roundtrip_bitmask():
    layer = FakeLayer()
    definition = FlagDefinition(meanings=["cloud", "shadow"], masks=[1, 2])
    save_mapping_to_layer(layer, definition)

    loaded = load_mapping_from_layer(layer)
    assert loaded.decode(3) == ["cloud", "shadow"]


def test_missing_property_returns_none():
    assert load_mapping_from_layer(FakeLayer()) is None


def test_corrupt_property_returns_none():
    layer = FakeLayer()
    layer.setCustomProperty("flag_viewer/mapping", "not json")
    assert load_mapping_from_layer(layer) is None


def test_clear_removes_property():
    layer = FakeLayer()
    definition = FlagDefinition(meanings=["a"], values=[1])
    save_mapping_to_layer(layer, definition)

    clear_mapping_on_layer(layer)

    assert load_mapping_from_layer(layer) is None

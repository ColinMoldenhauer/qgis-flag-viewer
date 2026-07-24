import json

from flag_viewer.core.flag_decoder import FlagDefinition
from flag_viewer.core.mapping_io import load_mapping, save_mapping


def test_json_roundtrip(tmp_path):
    definition = FlagDefinition(meanings=["a", "b"], values=[1, 2])
    path = tmp_path / "mapping.json"
    save_mapping(path, definition)

    loaded = load_mapping(path)
    assert loaded.meanings == ["a", "b"]
    assert loaded.values == [1, 2]
    assert loaded.decode(2) == ["b"]


def test_json_file_is_human_readable(tmp_path):
    definition = FlagDefinition(meanings=["cloud", "shadow"], masks=[1, 2])
    path = tmp_path / "mapping.json"
    save_mapping(path, definition)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"flag_meanings": ["cloud", "shadow"], "flag_masks": [1, 2]}


def test_yaml_roundtrip(tmp_path):
    yaml = __import__("pytest").importorskip("yaml")
    definition = FlagDefinition(meanings=["a", "b"], values=[10, 20])
    path = tmp_path / "mapping.yaml"
    save_mapping(path, definition)

    loaded = load_mapping(path)
    assert loaded.meanings == ["a", "b"]
    assert loaded.values == [10, 20]

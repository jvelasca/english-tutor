"""Tests de state_store.py (persistencia del estado visual del launcher)."""
import json

import state_store


def test_load_state_missing_file_returns_defaults(tmp_path):
    state = state_store.load_state(tmp_path / "no-existe.json")
    assert state["window"]["width"] == state_store.DEFAULTS["window"]["width"]
    assert state["window"]["height"] == state_store.DEFAULTS["window"]["height"]
    assert state["sash"] == state_store.DEFAULTS["sash"]
    assert state["sections"] == {}


def test_load_state_corrupt_json_returns_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not valid json", encoding="utf-8")
    state = state_store.load_state(path)
    assert state["sash"] == state_store.DEFAULTS["sash"]


def test_load_state_reads_valid_values(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "window": {"width": 1400, "height": 900, "x": 10, "y": 20},
                "sash": 700,
                "sections": {"Registros": False, "Servicios": True},
            }
        ),
        encoding="utf-8",
    )
    state = state_store.load_state(path)
    assert state["window"]["width"] == 1400
    assert state["window"]["height"] == 900
    assert state["window"]["x"] == 10
    assert state["window"]["y"] == 20
    assert state["sash"] == 700
    assert state["sections"] == {"Registros": False, "Servicios": True}


def test_load_state_ignores_invalid_fields(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "window": {"width": -5, "height": "alto", "x": "no"},
                "sash": -1,
                "sections": {"Servicios": "no-bool"},
            }
        ),
        encoding="utf-8",
    )
    state = state_store.load_state(path)
    assert state["window"]["width"] == state_store.DEFAULTS["window"]["width"]
    assert state["window"]["x"] is None
    assert state["sash"] == state_store.DEFAULTS["sash"]
    # Los valores de secciones que no son booleanos se descartan.
    assert state["sections"] == {}


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state = {
        "window": {"width": 1280, "height": 720, "x": 100, "y": 50},
        "sash": 640,
        "sections": {"Registros": False},
    }
    state_store.save_state(state, path)
    loaded = state_store.load_state(path)
    assert loaded == state

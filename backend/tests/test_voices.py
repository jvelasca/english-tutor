"""Tests de voces TTS (Configuración → Voces): catálogo instalado, resolución por
usuario y endpoint /api/voices."""
from fastapi.testclient import TestClient

import services.tts as tts
from main import app
from repositories import db
from repositories import settings as settings_repo
from repositories import users as users_repo


def _install(monkeypatch, tmp_path, *voice_ids):
    """Crea voces Piper falsas (onnx + onnx.json) en el PIPER_DIR simulado."""
    for vid in voice_ids:
        (tmp_path / f"{vid}.onnx").write_bytes(b"x")
        (tmp_path / f"{vid}.onnx.json").write_text("{}")
    monkeypatch.setattr(tts, "PIPER_DIR", tmp_path)
    # El default del sistema sigue siendo config.PIPER_VOICE (en_US-lessac-medium).
    return tts.DEFAULT_VOICE


def _setup_user(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Funciones puras ---------------------------------------------------------


def test_list_voices_default_first(monkeypatch, tmp_path):
    default = _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    assert tts.list_voices() == [default, "en_GB-alan-medium"]


def test_list_voices_empty_when_no_models(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    assert tts.list_voices() == []


def test_list_voices_ignores_incomplete(monkeypatch, tmp_path):
    # Un .onnx.json sin su .onnx no es una voz utilizable.
    (tmp_path / "en_US-lessac-medium.onnx.json").write_text("{}")
    monkeypatch.setattr(tts, "PIPER_DIR", tmp_path)
    assert tts.list_voices() == []


def test_resolve_voice_falls_back_to_default(monkeypatch, tmp_path):
    default = _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)
    assert tts.resolve_voice(None) == default
    assert tts.resolve_voice({}) == default
    # Preferencia apuntando a una voz no instalada → default.
    assert tts.resolve_voice({"tts_voice": "en_GB-nope-medium"}) == default


def test_resolve_voice_uses_preference_when_installed(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    assert tts.resolve_voice({"tts_voice": "en_GB-alan-medium"}) == "en_GB-alan-medium"


def test_resolve_voice_falls_back_to_any_installed_if_default_missing(
    monkeypatch, tmp_path,
):
    # Si el default del sistema no está instalado pero hay otra voz, se usa esa.
    _install(monkeypatch, tmp_path, "en_GB-alan-medium")
    assert tts.resolve_voice(None) == "en_GB-alan-medium"


def test_voice_name_known_and_derived():
    assert "Lessac" in tts.voice_name(tts.DEFAULT_VOICE)
    assert tts.voice_name("en_GB-nope-medium") == "en_GB · nope (medium)"


def test_is_ready_voice_specific(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    assert tts.is_ready("en_GB-alan-medium")
    assert tts.is_ready(tts.DEFAULT_VOICE)
    assert not tts.is_ready("en_GB-missing-medium")


# --- Endpoint -----------------------------------------------------------------


def test_voices_endpoint_with_user_selection(monkeypatch, tmp_path):
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    settings_repo.set_settings(uid, {"tts_voice": "en_GB-alan-medium"})
    with TestClient(app) as client:
        r = client.get("/api/voices", params={"user_id": uid})
    assert r.status_code == 200
    payload = r.json()
    assert [v["id"] for v in payload["voices"]] == [
        tts.DEFAULT_VOICE,
        "en_GB-alan-medium",
    ]
    assert payload["default"] == tts.DEFAULT_VOICE
    assert payload["selected"] == "en_GB-alan-medium"


def test_voices_endpoint_without_user_uses_default(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    with TestClient(app) as client:
        r = client.get("/api/voices")
    assert r.status_code == 200
    assert r.json()["selected"] == tts.DEFAULT_VOICE

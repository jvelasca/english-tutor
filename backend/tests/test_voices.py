"""Tests de voces TTS (Configuración → Voces): catálogo instalado, resolución por
usuario, endpoint /api/voices y descarga del catálogo curado."""
from fastapi.testclient import TestClient

import services.tts as tts
import services.voice_downloads as voice_downloads
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
    monkeypatch.setattr(voice_downloads, "PIPER_DIR", tmp_path)
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


# --- Catálogo curado (voice_downloads) ---------------------------------------


def test_catalog_has_english_medium_voices():
    # El catálogo solo ofrece voces de inglés; el set inicial está cubierto.
    ids = {s.id for s in voice_downloads.CATALOG}
    assert {"en_GB-alan-medium", "en_US-amy-medium"} <= ids
    assert all(s.id.startswith("en_") and s.id.endswith("-medium") for s in voice_downloads.CATALOG)


def test_available_to_download_excludes_installed():
    installed = ["en_GB-alan-medium", tts.DEFAULT_VOICE]
    available = voice_downloads.available_to_download(installed)
    assert all(s.id not in installed for s in available)
    # spec_for busca en el catálogo (no depende de lo instalado).
    assert voice_downloads.spec_for("en_GB-alan-medium") is not None
    assert voice_downloads.spec_for("en_GB-ghost-medium") is None


def test_download_voice_writes_onnx_pair(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    calls: list[str] = []

    def fake_download(url, dest):
        calls.append(url)
        dest.write_bytes(b"model")

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)
    voice_downloads.download_voice("en_GB-alan-medium")

    assert (tmp_path / "en_GB-alan-medium.onnx").read_bytes() == b"model"
    assert (tmp_path / "en_GB-alan-medium.onnx.json").read_bytes() == b"model"
    assert len(calls) == 2
    assert all("alan/medium/en_GB-alan-medium" in url for url in calls)


def test_download_voice_unknown_id_raises():
    try:
        voice_downloads.download_voice("en_GB-ghost-medium")
    except ValueError:
        return
    raise AssertionError("debería lanzar ValueError para ids fuera del catálogo")


def test_download_voice_idempotent(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    (tmp_path / "en_GB-alan-medium.onnx").write_bytes(b"x")
    (tmp_path / "en_GB-alan-medium.onnx.json").write_text("{}")
    called = False

    def fake_download(url, dest):
        nonlocal called
        called = True

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)
    voice_downloads.download_voice("en_GB-alan-medium")
    assert not called  # ya instalada: no vuelve a descargar


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
    # Las voces instaladas no se ofrecen como descargables; las demás sí.
    downloadable_ids = {v["id"] for v in payload["downloadable"]}
    assert "en_GB-alan-medium" not in downloadable_ids
    assert "en_GB-cori-medium" in downloadable_ids


def test_voices_endpoint_without_user_uses_default(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    with TestClient(app) as client:
        r = client.get("/api/voices")
    assert r.status_code == 200
    assert r.json()["selected"] == tts.DEFAULT_VOICE


def test_download_endpoint_installs_and_reflects_in_get(monkeypatch, tmp_path):
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)

    def fake_download(url, dest):
        dest.write_bytes(b"model")

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)

    with TestClient(app) as client:
        r = client.post("/api/voices/download", json={"voice_id": "en_GB-alan-medium"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Ya instalada → desaparece de "downloadable" y aparece en "voices".
        cat = client.get("/api/voices", params={"user_id": uid}).json()
    assert "en_GB-alan-medium" in {v["id"] for v in cat["voices"]}
    assert "en_GB-alan-medium" not in {v["id"] for v in cat["downloadable"]}


def test_download_endpoint_unknown_voice_400(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/voices/download", json={"voice_id": "en_GB-ghost"})
    assert r.status_code == 400


def test_download_endpoint_failure_502(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)

    def broken_download(url, dest):
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(voice_downloads, "_download_file", broken_download)
    with TestClient(app) as client:
        r = client.post("/api/voices/download", json={"voice_id": "en_GB-alan-medium"})
    assert r.status_code == 502
    assert "sin conexión" in r.json()["detail"]

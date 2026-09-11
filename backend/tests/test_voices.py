"""Tests de voces TTS (Configuración → Voces): catálogo instalado, resolución por
usuario, endpoint /api/voices y descarga del catálogo curado."""
import pytest
from fastapi.testclient import TestClient

import services.tts as tts
import services.voice_downloads as voice_downloads
from main import app
from repositories import db
from repositories import settings as settings_repo
from repositories import users as users_repo


@pytest.fixture(autouse=True)
def _clear_voice_ensure_cache():
    """Limpia la caché negativa de auto-descarga entre tests (V3.45)."""
    tts._VOICE_ENSURE_FAILED.clear()
    yield
    tts._VOICE_ENSURE_FAILED.clear()


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


# --- V3.39 (Fase 2): resolución por idioma (Traductor) -----------------------


def test_voice_language_extracts_locale_prefix():
    assert tts.voice_language("en_US-lessac-medium") == "en"
    assert tts.voice_language("es_MX-ald-medium") == "es"
    assert tts.voice_language("weird") == "weird"


def test_resolve_voice_language_skips_other_language_preference(
    monkeypatch, tmp_path,
):
    # Con language="es", una preferencia inglesa instalada NO se usa: se elige la
    # voz española instalada (el Traductor no debe leer español con voz inglesa).
    _install(
        monkeypatch, tmp_path,
        tts.DEFAULT_VOICE, "en_GB-alan-medium", "es_MX-ald-medium",
    )
    assert (
        tts.resolve_voice({"tts_voice": "en_GB-alan-medium"}, "es")
        == "es_MX-ald-medium"
    )


def test_resolve_voice_language_uses_matching_preference(monkeypatch, tmp_path):
    _install(
        monkeypatch, tmp_path,
        tts.DEFAULT_VOICE, "es_ES-davefx-medium", "es_MX-ald-medium",
    )
    assert (
        tts.resolve_voice({"tts_voice": "es_MX-ald-medium"}, "es")
        == "es_MX-ald-medium"
    )


def test_resolve_voice_language_defaults_to_installed_language_voice(
    monkeypatch, tmp_path,
):
    # Sin preferencia, la primera voz del idioma pedido (default primero si es
    # de ese idioma).
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", "es_MX-ald-medium")
    assert tts.resolve_voice(None, "es") == "es_MX-ald-medium"
    assert tts.resolve_voice(None, "en") == "en_GB-alan-medium"


def test_resolve_voice_language_falls_back_when_no_voice_of_language(
    monkeypatch, tmp_path,
):
    # Sin ninguna voz española instalada cae al fallback global (degradación
    # documentada: mejor sintetizar con otra voz que quedarse sin audio).
    _install(monkeypatch, tmp_path, "en_GB-alan-medium")
    assert tts.resolve_voice(None, "es") == "en_GB-alan-medium"


def test_voice_name_known_and_derived():
    assert "Lessac" in tts.voice_name(tts.DEFAULT_VOICE)
    assert tts.voice_name("en_GB-nope-medium") == "en_GB · nope (medium)"


def test_is_ready_voice_specific(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", tts.DEFAULT_VOICE)
    assert tts.is_ready("en_GB-alan-medium")
    assert tts.is_ready(tts.DEFAULT_VOICE)
    assert not tts.is_ready("en_GB-missing-medium")


# --- Catálogo curado (voice_downloads) ---------------------------------------


def test_catalog_has_english_and_spanish_medium_voices():
    # El catálogo ofrece voces medium de inglés (núcleo) y de español (V3.39,
    # Fase 2, Traductor); no se ofrecen calidades `high` ni `low`.
    ids = {s.id for s in voice_downloads.CATALOG}
    assert {"en_GB-alan-medium", "en_US-amy-medium"} <= ids
    assert {"es_ES-davefx-medium", "es_MX-ald-medium"} <= ids
    assert all(s.id.endswith("-medium") for s in voice_downloads.CATALOG)
    assert all(s.id.startswith(("en_", "es_")) for s in voice_downloads.CATALOG)


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


# --- V3.39 (Fase 2): /api/tts con idioma (Traductor) -------------------------


def test_tts_endpoint_uses_voice_of_requested_language(monkeypatch, tmp_path):
    # El Traductor pide `language="es"`: aunque la preferencia guardada sea
    # inglesa, la síntesis usa una voz española instalada.
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "es_MX-ald-medium")
    settings_repo.set_settings(uid, {"tts_voice": tts.DEFAULT_VOICE})
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post(
            "/api/tts",
            json={"text": "¿Dónde está el hotel?", "language": "es"},
            params={"user_id": uid},
        )
    assert r.status_code == 200
    assert captured["voice"] == "es_MX-ald-medium"


def test_tts_endpoint_without_user_uses_language_voice(monkeypatch, tmp_path):
    _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "es_ES-davefx-medium")
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post("/api/tts", json={"text": "Hola", "language": "es"})
    assert r.status_code == 200
    assert captured["voice"] == "es_ES-davefx-medium"


def test_tts_endpoint_defaults_to_english_without_language(monkeypatch, tmp_path):
    # Retrocompatible: sin `language` el contrato es el histórico (voz inglesa).
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "es_MX-ald-medium")
    settings_repo.set_settings(uid, {"tts_voice": tts.DEFAULT_VOICE})
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post(
            "/api/tts", json={"text": "Hello"}, params={"user_id": uid}
        )
    assert r.status_code == 200
    assert captured["voice"] == tts.DEFAULT_VOICE


# --- V3.45: voz por defecto de cada idioma y auto-descarga --------------------


def test_default_voice_for_known_and_unknown_languages():
    assert tts.default_voice_for("en") == tts.DEFAULT_VOICE
    assert tts.default_voice_for("es") == "es_ES-davefx-medium"
    # Idioma sin default declarado cae al default histórico.
    assert tts.default_voice_for("fr") == tts.DEFAULT_VOICE
    assert tts.default_voice_for("") == tts.DEFAULT_VOICE


def test_resolve_voice_prefers_language_default_over_first_alphabetical(
    monkeypatch, tmp_path,
):
    # El default del idioma manda aunque alfabéticamente no sea el primero.
    _install(
        monkeypatch, tmp_path,
        "en_GB-alan-medium", "es_ES-sharvard-medium", "es_MX-ald-medium",
    )
    monkeypatch.setattr(tts, "DEFAULT_VOICES", {"es": "es_MX-ald-medium"})
    assert tts.resolve_voice(None, "es") == "es_MX-ald-medium"


def test_resolve_voice_falls_back_to_any_installed_of_language(
    monkeypatch, tmp_path,
):
    # Sin el default del idioma instalado pero con otra voz del idioma, se usa esa.
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", "es_ES-sharvard-medium")
    assert tts.resolve_voice(None, "es") == "es_ES-sharvard-medium"


def test_ensure_voice_for_language_noop_when_installed(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, "en_GB-alan-medium", "es_MX-ald-medium")
    called = False

    def fake_download(url, dest):
        nonlocal called
        called = True

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)
    assert tts.ensure_voice_for_language("es") is True
    assert not called  # ya había voz española: no descarga


def test_ensure_voice_for_language_downloads_language_default(
    monkeypatch, tmp_path,
):
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)  # solo inglés instalado

    def fake_download(url, dest):
        dest.write_bytes(b"model")

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)
    assert tts.ensure_voice_for_language("es") is True
    assert (tmp_path / "es_ES-davefx-medium.onnx").exists()
    assert (tmp_path / "es_ES-davefx-medium.onnx.json").exists()
    assert tts.resolve_voice(None, "es") == "es_ES-davefx-medium"


def test_ensure_voice_for_language_returns_false_on_download_error(
    monkeypatch, tmp_path,
):
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)

    def broken_download(url, dest):
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(voice_downloads, "_download_file", broken_download)
    # No lanza: degrada y deja que el TTS use el fallback.
    assert tts.ensure_voice_for_language("es") is False
    assert tts.resolve_voice(None, "es") == tts.DEFAULT_VOICE


def test_ensure_voice_for_language_false_when_default_not_in_catalog(
    monkeypatch, tmp_path,
):
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)
    monkeypatch.setattr(tts, "DEFAULT_VOICES", {"es": "es_XX-ghost-medium"})
    assert tts.ensure_voice_for_language("es") is False


def test_ensure_voice_for_language_caches_failure(monkeypatch, tmp_path):
    # Un fallo de red no se reintenta en cada petición (caché negativa).
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)
    calls = {"n": 0}

    def broken_download(url, dest):
        calls["n"] += 1
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(voice_downloads, "_download_file", broken_download)
    assert tts.ensure_voice_for_language("es") is False
    assert tts.ensure_voice_for_language("es") is False
    assert calls["n"] == 1  # solo el primer intento llegó a descargar


def test_voices_endpoint_exposes_language_defaults(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)
    with TestClient(app) as client:
        r = client.get("/api/voices")
    assert r.status_code == 200
    assert r.json()["defaults"] == {
        "en": tts.DEFAULT_VOICE,
        "es": "es_ES-davefx-medium",
    }


def test_tts_endpoint_auto_downloads_missing_language_voice(monkeypatch, tmp_path):
    # Sin voz española instalada, /api/tts la descarga y sintetiza con ella.
    _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)

    def fake_download(url, dest):
        dest.write_bytes(b"model")

    monkeypatch.setattr(voice_downloads, "_download_file", fake_download)
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post("/api/tts", json={"text": "Hola", "language": "es"})
    assert r.status_code == 200
    assert captured["voice"] == "es_ES-davefx-medium"

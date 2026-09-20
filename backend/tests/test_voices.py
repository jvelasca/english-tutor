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


# --- V3.71 (eje RD): el timeout es real y la degradación es explícita --------


class _FakeResponse:
    """Respuesta mínima de `urlopen` para `_download_file`."""

    def __init__(self, body: bytes, content_length: str | None):
        self._body = body
        self.headers = (
            {} if content_length is None else {"Content-Length": content_length}
        )

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk, self._body = self._body, b""
            return chunk
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_file_pasa_el_timeout_real_a_urlopen(monkeypatch, tmp_path):
    """RD-01: el `timeout` deja de ser código muerto.

    Hasta V3.70 se declaraba `timeout=300.0` pero se llamaba a `urlretrieve`,
    que no lo acepta: la descarga quedaba sin límite alguno.
    """
    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["timeout"] = timeout
        return _FakeResponse(b"x", "1")

    monkeypatch.setattr(voice_downloads.urllib.request, "urlopen", fake_urlopen)
    voice_downloads._download_file(
        "https://example.invalid/v.onnx", tmp_path / "v.onnx"
    )

    assert captured["timeout"] == voice_downloads.VOICE_DOWNLOAD_TIMEOUT_SECONDS
    assert (tmp_path / "v.onnx").read_bytes() == b"x"


def test_el_timeout_de_descarga_es_acotado():
    """Un timeout `None` o enorme volvería a permitir el cuelgue sin red."""
    timeout = voice_downloads.VOICE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout is not None
    assert 0 < timeout <= 60


def test_download_file_rechaza_descarga_truncada(monkeypatch, tmp_path):
    """RD-02: no se acepta una descarga incompleta (ni una página de error)."""
    monkeypatch.setattr(
        voice_downloads.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(b"abc", "9999"),
    )
    dest = tmp_path / "v.onnx"

    with pytest.raises(RuntimeError, match="incompleta"):
        voice_downloads._download_file("https://example.invalid/v.onnx", dest)

    assert not dest.exists()
    assert not (tmp_path / "v.onnx.part").exists()  # sin restos a medio bajar


def test_download_file_rechaza_descarga_vacia(monkeypatch, tmp_path):
    monkeypatch.setattr(
        voice_downloads.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(b"", None),
    )
    dest = tmp_path / "v.onnx"

    with pytest.raises(RuntimeError, match="vacía"):
        voice_downloads._download_file("https://example.invalid/v.onnx", dest)

    assert not dest.exists()
    assert not (tmp_path / "v.onnx.part").exists()


def test_tts_declara_la_voz_usada_y_si_hubo_degradacion(monkeypatch, tmp_path):
    """RD-03: sin voz del idioma, la degradación se declara (no es silenciosa)."""
    _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)  # solo inglés
    monkeypatch.setattr(
        "routers.voz.ensure_voice_for_language", lambda language: False
    )
    monkeypatch.setattr(
        "routers.voz.synthesize_speech",
        lambda text, scale=1.0, voice=None: b"RIFFfake",
    )

    with TestClient(app) as client:
        r = client.post("/api/tts", json={"text": "Hola", "language": "es"})

    assert r.status_code == 200
    assert r.headers["X-TTS-Voice"] == tts.DEFAULT_VOICE
    assert r.headers["X-TTS-Degraded"] == "1"


def test_tts_no_declara_degradacion_cuando_la_voz_es_del_idioma(monkeypatch, tmp_path):
    _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "es_ES-davefx-medium")
    monkeypatch.setattr(
        "routers.voz.synthesize_speech",
        lambda text, scale=1.0, voice=None: b"RIFFfake",
    )

    with TestClient(app) as client:
        r = client.post("/api/tts", json={"text": "Hola", "language": "es"})

    assert r.status_code == 200
    assert r.headers["X-TTS-Voice"] == "es_ES-davefx-medium"
    assert r.headers["X-TTS-Degraded"] == "0"


# --- V3.75.5: voz pedida en la petición (dos acentos) -------------------------


def test_pick_requested_voice_accepts_only_installed_of_language(
    monkeypatch, tmp_path,
):
    """Función pura: el id del cliente solo vale instalado Y del idioma pedido."""
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "en_GB-alan-medium",
             "es_MX-ald-medium")

    assert tts.pick_requested_voice("en_GB-alan-medium", "en") == "en_GB-alan-medium"
    # Voz instalada pero de OTRO idioma: se ignora (no se lee inglés con voz ES).
    assert tts.pick_requested_voice("es_MX-ald-medium", "en") is None
    # Voz no instalada: el id entraría en el path de caché, así que no se acepta.
    assert tts.pick_requested_voice("en_GB-ghost-medium", "en") is None
    assert tts.pick_requested_voice("", "en") is None
    assert tts.pick_requested_voice(None, "en") is None


def test_tts_endpoint_honra_la_voz_pedida(monkeypatch, tmp_path):
    """Dos acentos: la voz pedida manda sobre la preferencia guardada."""
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "en_GB-alan-medium")
    settings_repo.set_settings(uid, {"tts_voice": tts.DEFAULT_VOICE})
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post(
            "/api/tts",
            json={"text": "Hello there", "voice": "en_GB-alan-medium"},
            params={"user_id": uid},
        )

    assert r.status_code == 200
    assert captured["voice"] == "en_GB-alan-medium"
    # Y se declara la voz que de verdad sonó (no la preferida).
    assert r.headers["X-TTS-Voice"] == "en_GB-alan-medium"


def test_tts_endpoint_ignora_una_voz_no_instalada(monkeypatch, tmp_path):
    """Una preferencia vieja / voz borrada no rompe: se cae a la del perfil."""
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE)
    settings_repo.set_settings(uid, {"tts_voice": tts.DEFAULT_VOICE})
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post(
            "/api/tts",
            json={"text": "Hello there", "voice": "en_GB-ghost-medium"},
            params={"user_id": uid},
        )

    assert r.status_code == 200
    assert captured["voice"] == tts.DEFAULT_VOICE


def test_tts_endpoint_ignora_una_voz_de_otro_idioma(monkeypatch, tmp_path):
    uid = _setup_user(monkeypatch, tmp_path)
    _install(monkeypatch, tmp_path, tts.DEFAULT_VOICE, "es_MX-ald-medium")
    captured: dict = {}

    def fake_synthesize(text, length_scale=1.0, voice=None):
        captured["voice"] = voice
        return b"RIFFfake"

    monkeypatch.setattr("routers.voz.synthesize_speech", fake_synthesize)
    with TestClient(app) as client:
        r = client.post(
            "/api/tts",
            json={
                "text": "Hello there",
                "language": "en",
                "voice": "es_MX-ald-medium",
            },
            params={"user_id": uid},
        )

    assert r.status_code == 200
    assert captured["voice"] == tts.DEFAULT_VOICE

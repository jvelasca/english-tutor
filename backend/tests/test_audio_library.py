"""Tests de la infraestructura de biblioteca de audio humano (P1.5–P1.8): manifest
versionado, resolución segura del WAV grabado y servido sin depender de Piper."""
from fastapi.testclient import TestClient

from domain import listening as listening_domain
from main import app
from repositories import db
from repositories import users as users_repo
from services.audio_library import (
    AUDIO_LIBRARY_VERSION,
    AudioLibraryEntry,
    AudioLibraryManifest,
    entry_for,
    is_recorded,
    library_summary,
    load_manifest,
    recorded_audio_path,
    resolve_file,
    validate_manifest,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _manifest_with(entries):
    return AudioLibraryManifest(version=AUDIO_LIBRARY_VERSION, entries=entries)


def _recorded_question():
    return {"id": "rec-1", "audio_type": "recorded", "audio_id": "a1"}


def _patch_library(monkeypatch, tmp_path, *, write_file=True):
    manifest = _manifest_with([AudioLibraryEntry(audio_id="a1", file="a1.wav")])
    monkeypatch.setattr("services.audio_library.load_manifest", lambda: manifest)
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    if write_file:
        (tmp_path / "a1.wav").write_bytes(b"RIFF-recorded-wav")
    monkeypatch.setattr(
        "domain.listening.get_question", lambda qid: _recorded_question()
    )


# --- Manifest: carga y consulta ---------------------------------------------


def test_load_manifest_from_file(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(
        '{"version": "1.0.0", "entries": [{"audio_id": "a1", "file": "a1.wav"}]}',
        encoding="utf-8",
    )
    m = load_manifest(p)
    assert m.version == "1.0.0"
    assert len(m.entries) == 1
    assert m.entries[0].audio_id == "a1"


def test_shipped_manifest_is_valid():
    # El manifest real (vacío) del repositorio debe ser estructuralmente válido.
    assert load_manifest().version == AUDIO_LIBRARY_VERSION
    assert validate_manifest() == []


def test_entry_for_finds_and_misses():
    e = AudioLibraryEntry(audio_id="a1", file="a1.wav")
    m = _manifest_with([e])
    assert entry_for(m, "a1") == e
    assert entry_for(m, "nope") is None


# --- Resolución de archivo (seguridad) --------------------------------------


def test_resolve_file_within_dir(tmp_path):
    entry = AudioLibraryEntry(audio_id="a1", file="a1.wav")
    assert resolve_file(entry, base=tmp_path) == tmp_path / "a1.wav"


def test_resolve_file_rejects_escape(tmp_path):
    entry = AudioLibraryEntry(audio_id="a1", file="../secret.wav")
    assert resolve_file(entry, base=tmp_path) is None


# --- is_recorded / recorded_audio_path --------------------------------------


def test_is_recorded_only_for_recorded_type():
    assert is_recorded({"audio_type": "recorded"}) is True
    assert is_recorded({"audio_type": "tts"}) is False
    assert is_recorded({}) is False


def test_recorded_audio_path_tts_returns_none():
    assert recorded_audio_path({"audio_type": "tts", "audio_id": "a1"}) is None


def test_recorded_audio_path_resolves(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.audio_library.load_manifest",
        lambda: _manifest_with([AudioLibraryEntry(audio_id="a1", file="a1.wav")]),
    )
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    assert recorded_audio_path(_recorded_question()) == tmp_path / "a1.wav"


def test_recorded_audio_path_missing_id(monkeypatch):
    monkeypatch.setattr(
        "services.audio_library.load_manifest", lambda: _manifest_with([])
    )
    assert recorded_audio_path({"audio_type": "recorded", "audio_id": ""}) is None


def test_recorded_audio_path_entry_missing(monkeypatch):
    monkeypatch.setattr(
        "services.audio_library.load_manifest", lambda: _manifest_with([])
    )
    assert recorded_audio_path(_recorded_question()) is None


def test_recorded_audio_path_rejects_escape(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.audio_library.load_manifest",
        lambda: _manifest_with([AudioLibraryEntry(audio_id="a1", file="../x.wav")]),
    )
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    assert recorded_audio_path(_recorded_question()) is None


# --- validate_manifest -------------------------------------------------------


def test_validate_manifest_valid():
    m = _manifest_with([AudioLibraryEntry(audio_id="a1", file="a1.wav")])
    assert validate_manifest(m) == []


def test_validate_manifest_version_mismatch():
    m = AudioLibraryManifest(version="0.0.1", entries=[])
    assert any("version" in e for e in validate_manifest(m))


def test_validate_manifest_duplicate_id():
    m = _manifest_with(
        [
            AudioLibraryEntry(audio_id="a1", file="a1.wav"),
            AudioLibraryEntry(audio_id="a1", file="b.wav"),
        ]
    )
    assert any("duplicate audio_id" in e for e in validate_manifest(m))


def test_validate_manifest_duplicate_file():
    m = _manifest_with(
        [
            AudioLibraryEntry(audio_id="a1", file="a.wav"),
            AudioLibraryEntry(audio_id="a2", file="a.wav"),
        ]
    )
    assert any("duplicate file" in e for e in validate_manifest(m))


def test_validate_manifest_escape(monkeypatch, tmp_path):
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    m = _manifest_with([AudioLibraryEntry(audio_id="a1", file="../x.wav")])
    assert any("escapes" in e for e in validate_manifest(m))


# --- library_summary ---------------------------------------------------------


def test_library_summary_metadata():
    e = AudioLibraryEntry(
        audio_id="a1",
        file="a1.wav",
        speaker_id="sp1",
        accent="neutral",
        speaker_count=2,
        noise_level=3,
        duration=4.5,
        transcript="Hi there.",
    )
    s = library_summary(_manifest_with([e]))
    assert s[0]["audio_id"] == "a1"
    assert s[0]["file"] == "a1.wav"
    assert s[0]["speaker_id"] == "sp1"
    assert s[0]["speaker_count"] == 2
    assert s[0]["noise_level"] == 3
    assert s[0]["duration"] == 4.5


# --- Servido de audio grabado (endpoint + domain) ----------------------------


def test_audio_endpoint_serves_recorded(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _patch_library(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/audio/rec-1", params={"user_id": uid})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content == b"RIFF-recorded-wav"


def test_audio_endpoint_recorded_missing_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _patch_library(monkeypatch, tmp_path, write_file=False)
    with TestClient(app) as client:
        r = client.get("/api/listening/audio/rec-1", params={"user_id": uid})
    assert r.status_code == 404


def test_audio_ready_recorded_when_file_exists(monkeypatch, tmp_path):
    _patch_library(monkeypatch, tmp_path)
    assert listening_domain.audio_ready(_recorded_question()) is True


def test_audio_ready_recorded_false_when_missing(monkeypatch, tmp_path):
    _patch_library(monkeypatch, tmp_path, write_file=False)
    assert listening_domain.audio_ready(_recorded_question()) is False

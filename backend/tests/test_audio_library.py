"""Tests de la infraestructura de biblioteca de audio humano (P1.5–P1.8): manifest
versionado, resolución segura del WAV grabado, servido sin depender de Piper y
esquema ampliado de metadatos (P0-1: corpus de audio humano 1.0)."""
import wave

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from domain import listening as listening_domain
from main import app
from repositories import db
from repositories import users as users_repo
from scripts.import_audio import wav_metadata
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
    validate_audio_entries,
    validate_audio_entry,
    validate_manifest,
    wav_probe,
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


def _write_wav(path, duration=1.0, framerate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * int(framerate * duration))


# --- Manifest: carga y consulta ---------------------------------------------


def test_load_manifest_from_file(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(
        '{"version": "1.1.0", "entries": [{"audio_id": "a1", "file": "a1.wav"}]}',
        encoding="utf-8",
    )
    m = load_manifest(p)
    assert m.version == "1.1.0"
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


# --- Esquema ampliado (P0-1) ------------------------------------------------


def test_audio_library_entry_new_fields_defaults():
    e = AudioLibraryEntry(audio_id="a1", file="a1.wav")
    assert e.gender == "unknown"
    assert e.age_band == "unknown"
    assert e.region == "unknown"
    assert e.speech_rate is None
    assert e.spontaneity == "scripted"
    assert e.recording_environment == "studio"
    assert e.overlap is False
    assert e.connected_speech is False
    assert e.prosody == "unknown"
    assert e.task_type == "unknown"
    assert e.cefr == "unknown"
    assert e.context == "unknown"


def test_audio_library_entry_rejects_invalid_literal():
    with pytest.raises(ValidationError):
        AudioLibraryEntry(audio_id="a1", file="a1.wav", cefr="C3")
    with pytest.raises(ValidationError):
        AudioLibraryEntry(audio_id="a1", file="a1.wav", gender="robot")
    with pytest.raises(ValidationError):
        AudioLibraryEntry(audio_id="a1", file="a1.wav", context="radio_show")


# --- Resolución de archivo (seguridad) --------------------------------------


def test_resolve_file_within_dir(tmp_path):
    entry = AudioLibraryEntry(audio_id="a1", file="a1.wav")
    assert resolve_file(entry, base=tmp_path) == tmp_path / "a1.wav"


def test_resolve_file_nested_dir(tmp_path):
    entry = AudioLibraryEntry(audio_id="a1", file="B1/speaker_003/dialogue.wav")
    assert resolve_file(entry, base=tmp_path) == (
        tmp_path / "B1" / "speaker_003" / "dialogue.wav"
    )


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


def test_validate_manifest_invalid_cefr_and_gender():
    entry = AudioLibraryEntry.model_construct(
        audio_id="a1",
        file="a1.wav",
        gender="robot",
        age_band="unknown",
        region="unknown",
        speech_rate=None,
        spontaneity="scripted",
        recording_environment="studio",
        overlap=False,
        connected_speech=False,
        prosody="unknown",
        task_type="unknown",
        cefr="C3",
    )
    m = AudioLibraryManifest.model_construct(
        version=AUDIO_LIBRARY_VERSION, entries=[entry]
    )
    errors = validate_manifest(m)
    assert any("invalid cefr" in e for e in errors)
    assert any("invalid gender" in e for e in errors)


def test_validate_manifest_speech_rate_must_be_positive():
    m = _manifest_with([AudioLibraryEntry(audio_id="a1", file="a1.wav", speech_rate=0)])
    assert any("speech_rate" in e for e in validate_manifest(m))


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
        cefr="B1",
        region="es",
    )
    s = library_summary(_manifest_with([e]))
    entry = s["entries"][0]
    assert entry["audio_id"] == "a1"
    assert entry["file"] == "a1.wav"
    assert entry["speaker_id"] == "sp1"
    assert entry["speaker_count"] == 2
    assert entry["noise_level"] == 3
    assert entry["duration"] == 4.5
    assert entry["cefr"] == "B1"
    assert entry["region"] == "es"


def test_library_summary_breakdowns():
    e1 = AudioLibraryEntry(
        audio_id="a1", file="a1.wav", cefr="A1", speaker_id="sp1", accent="neutral",
        region="es",
    )
    e2 = AudioLibraryEntry(
        audio_id="a2", file="a2.wav", cefr="A1", speaker_id="sp1", accent="br",
        region="es",
    )
    e3 = AudioLibraryEntry(
        audio_id="a3", file="a3.wav", cefr="B1", speaker_id="sp2", accent="br",
        region="uk",
    )
    s = library_summary(_manifest_with([e1, e2, e3]))
    assert s["by_cefr"] == {"A1": 2, "B1": 1}
    assert s["by_speaker_id"] == {"sp1": 2, "sp2": 1}
    assert s["by_accent"] == {"neutral": 1, "br": 2}
    assert s["by_region"] == {"es": 2, "uk": 1}


# --- wav_metadata (tooling de importación) -----------------------------------


def test_wav_metadata_reads_synthetic_wav(tmp_path):
    p = tmp_path / "x.wav"
    _write_wav(p, duration=2.0, framerate=8000)
    meta = wav_metadata(p)
    assert meta["channels"] == 1
    assert meta["framerate"] == 8000
    assert meta["sample_width"] == 2
    assert meta["duration"] == pytest.approx(2.0)


def test_wav_metadata_non_wav_returns_empty(tmp_path):
    p = tmp_path / "not_a_wav.bin"
    p.write_bytes(b"this is not a wav file")
    assert wav_metadata(p) == {}


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


# --- validate_audio_entry / validate_audio_entries (P0-2) --------------------


def test_wav_probe_reads_synthetic_wav(tmp_path):
    _write_wav(tmp_path / "x.wav", duration=2.0, framerate=8000)
    meta = wav_probe(tmp_path / "x.wav")
    assert meta["channels"] == 1
    assert meta["framerate"] == 8000
    assert meta["sample_width"] == 2
    assert meta["duration"] == pytest.approx(2.0)


def test_validate_audio_entry_no_duration_issue(tmp_path):
    _write_wav(tmp_path / "a1.wav", duration=2.0)
    entry = AudioLibraryEntry(audio_id="a1", file="a1.wav", duration=2.0)
    issues = validate_audio_entry(entry, base=tmp_path)
    assert not any(i.field == "duration" for i in issues)


def test_validate_audio_entry_duration_mismatch(tmp_path):
    _write_wav(tmp_path / "a1.wav", duration=1.0)
    entry = AudioLibraryEntry(audio_id="a1", file="a1.wav", duration=5.0)
    issues = validate_audio_entry(entry, base=tmp_path)
    duration_issues = [i for i in issues if i.field == "duration"]
    assert len(duration_issues) == 1
    issue = duration_issues[0]
    assert issue.severity == "error"
    assert issue.declared == "5.0"
    assert issue.measured == "1.0"


def test_validate_audio_entry_mono_speaker_count_warning(tmp_path):
    _write_wav(tmp_path / "a1.wav", duration=1.0)
    entry = AudioLibraryEntry(
        audio_id="a1", file="a1.wav", duration=1.0, speaker_count=3
    )
    issues = validate_audio_entry(entry, base=tmp_path)
    sc = [i for i in issues if i.field == "speaker_count"]
    assert len(sc) == 1
    assert sc[0].severity == "warning"
    assert not any(i.field == "speaker_count" and i.severity == "error" for i in issues)


def test_validate_audio_entry_not_verifiable_fields_are_info(tmp_path):
    _write_wav(tmp_path / "a1.wav", duration=1.0)
    entry = AudioLibraryEntry(
        audio_id="a1",
        file="a1.wav",
        duration=1.0,
        speech_rate=150.0,
        noise_level=2,
        accent="br",
    )
    issues = validate_audio_entry(entry, base=tmp_path)
    assert not any(i.severity == "error" for i in issues)
    by_field = {i.field: i for i in issues}
    assert by_field["speech_rate"].severity == "info"
    assert by_field["noise_level"].severity == "info"
    assert by_field["accent"].severity == "info"


def test_validate_audio_entry_non_wav_error(tmp_path):
    p = tmp_path / "not_a_wav.wav"
    p.write_bytes(b"this is not a wav file")
    entry = AudioLibraryEntry(audio_id="a1", file="not_a_wav.wav", duration=1.0)
    issues = validate_audio_entry(entry, base=tmp_path)
    assert any(i.severity == "error" for i in issues)


def test_validate_audio_entry_escapes_library_error(tmp_path):
    entry = AudioLibraryEntry(audio_id="a1", file="../secret.wav", duration=1.0)
    issues = validate_audio_entry(entry, base=tmp_path)
    assert any(
        i.severity == "error" and i.message == "invalid path (escapes library)"
        for i in issues
    )


def test_validate_audio_entries_maps_all_ids(tmp_path):
    _write_wav(tmp_path / "a1.wav", duration=1.0)
    _write_wav(tmp_path / "a2.wav", duration=1.0)
    manifest = _manifest_with(
        [
            AudioLibraryEntry(audio_id="a1", file="a1.wav", duration=1.0),
            AudioLibraryEntry(audio_id="a2", file="a2.wav", duration=5.0),
        ]
    )
    result = validate_audio_entries(manifest, base=tmp_path)
    assert set(result) == {"a1", "a2"}
    assert result["a1"] == []
    assert any(i.field == "duration" for i in result["a2"])

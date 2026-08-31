"""Tests de la gestión en-app de la biblioteca de audio humano: helpers de
escritura/borrado del manifest y endpoints de subir/listar/borrar WAV."""
import io
import json
import wave

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from services.audio_library import (
    AUDIO_LIBRARY_VERSION,
    AudioLibraryEntry,
    is_recorded,
    remove_entry,
    wav_probe_bytes,
    write_entry,
)
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    # Aísla la biblioteca y el manifest de la app en el tmp_path de la prueba.
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "services.audio_library.manifest_path", lambda: tmp_path / "manifest.json"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"version": AUDIO_LIBRARY_VERSION, "entries": []}),
        encoding="utf-8",
    )


def _wav_bytes(duration=1.0, framerate=8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * int(framerate * duration))
    return buf.getvalue()


def _manifest(tmp_path) -> dict:
    return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))


# --- wav_probe_bytes ---------------------------------------------------------


def test_wav_probe_bytes_reads_synthetic():
    meta = wav_probe_bytes(_wav_bytes(duration=2.0))
    assert meta["channels"] == 1
    assert meta["framerate"] == 8000
    assert meta["sample_width"] == 2
    assert meta["duration"] == pytest.approx(2.0)


def test_wav_probe_bytes_rejects_non_wav():
    with pytest.raises((wave.Error, EOFError)):
        wav_probe_bytes(b"this is not a wav file")


# --- write_entry / remove_entry ---------------------------------------------


def test_write_entry_upserts_and_persists(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    entry = AudioLibraryEntry(
        audio_id="audio-l15", file="audio-l15.wav", cefr="B1", duration=1.0
    )
    dest = write_entry(entry, _wav_bytes(duration=1.0))
    assert dest == tmp_path / "audio-l15.wav"
    assert dest.exists()
    assert [e["audio_id"] for e in _manifest(tmp_path)["entries"]] == ["audio-l15"]


def test_write_entry_replaces_existing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    write_entry(
        AudioLibraryEntry(audio_id="a1", file="a1.wav", duration=1.0),
        _wav_bytes(duration=1.0),
    )
    write_entry(
        AudioLibraryEntry(audio_id="a1", file="a1.wav", cefr="B2", duration=1.0),
        _wav_bytes(duration=1.0),
    )
    entries = _manifest(tmp_path)["entries"]
    assert len(entries) == 1
    assert entries[0]["cefr"] == "B2"


def test_write_entry_rejects_non_wav(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with pytest.raises((wave.Error, EOFError)):
        write_entry(AudioLibraryEntry(audio_id="a1", file="a1.wav"), b"nope")


def test_write_entry_rejects_escape(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        write_entry(
            AudioLibraryEntry(audio_id="a1", file="../x.wav"), _wav_bytes()
        )


def test_remove_entry_deletes_file_and_manifest(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    write_entry(
        AudioLibraryEntry(audio_id="a1", file="a1.wav"), _wav_bytes()
    )
    assert remove_entry("a1") is True
    assert not (tmp_path / "a1.wav").exists()
    assert _manifest(tmp_path)["entries"] == []
    assert remove_entry("a1") is False


# --- Endpoints ---------------------------------------------------------------


def test_slots_endpoint_lists_slots(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/audio-library/slots")
    assert r.status_code == 200
    slots = r.json()["slots"]
    ids = {s["audio_id"] for s in slots}
    assert "audio-l15" in ids
    assert "audio-l23" in ids
    # El corpus de audio humano (V1.36) también es grabable desde la app.
    assert "audio-c001" in ids
    expected = {
        q["audio_id"]
        for q in QUESTION_BANK
        if (q.get("audio_id") or "").strip()
    }
    assert ids == expected
    assert all(s["state"] == "empty" for s in slots)


def test_upload_endpoint_records_and_flips_to_recorded(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", _wav_bytes(duration=1.0), "audio/wav")},
            data={"audio_id": "audio-l15", "cefr": "B1", "transcript": "Hello"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["audio_id"] == "audio-l15"
    assert body["cefr"] == "B1"
    assert (tmp_path / "audio-l15.wav").exists()
    # El manifest es la fuente de verdad: el ítem pasa a considerarse grabado.
    assert is_recorded({"audio_id": "audio-l15"}) is True


def test_upload_endpoint_rejects_non_wav(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("x.wav", b"not a wav", "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 400


def test_upload_endpoint_rejects_unknown_audio_id(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("x.wav", _wav_bytes(), "audio/wav")},
            data={"audio_id": "nope"},
        )
    assert r.status_code == 400


def test_delete_endpoint_removes(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", _wav_bytes(), "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
        r = client.delete("/api/audio-library/audio-l15")
    assert r.status_code == 200
    assert r.json()["removed"] is True
    assert not (tmp_path / "audio-l15.wav").exists()
    assert is_recorded({"audio_id": "audio-l15"}) is False


def test_delete_endpoint_unknown_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.delete("/api/audio-library/nope")
    assert r.status_code == 404


def test_preview_endpoint_serves_wav(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    wav = _wav_bytes(duration=1.0)
    with TestClient(app) as client:
        client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", wav, "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
        r = client.get("/api/audio-library/audio-l15/audio")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content == wav


def test_preview_endpoint_missing_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/audio-library/audio-l15/audio")
    assert r.status_code == 404

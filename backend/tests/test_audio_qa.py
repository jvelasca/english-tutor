"""Tests de Audio QA + Content Audit (V1.37): QA acústica, candado admin (PIN),
backup/auditoría de borrado e integridad del contenido."""
import io
import json
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from services.audio_library import (
    AUDIO_LIBRARY_VERSION,
    AudioLibraryEntry,
    acoustic_metrics,
    classify_quality,
    remove_entry,
    wav_quality_bytes,
    write_entry,
)
from services.content_validation import run_content_validation
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    monkeypatch.setattr("services.audio_library.library_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "services.audio_library.manifest_path", lambda: tmp_path / "manifest.json"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"version": AUDIO_LIBRARY_VERSION, "entries": []}),
        encoding="utf-8",
    )


def _wav_from_samples(samples, framerate=8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return buf.getvalue()


def _tone(n=8000, amplitude=0.5, freq=440.0, framerate=8000) -> bytes:
    samples = [
        int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / framerate))
        for i in range(n)
    ]
    return _wav_from_samples(samples, framerate)


# --- QA acústica -------------------------------------------------------------


def test_acoustic_metrics_detects_silence():
    data = _wav_from_samples([0] * 8000)
    m = acoustic_metrics(data)
    assert m["silence_ratio"] == 1.0
    assert m["rms_dbFS"] == -120.0
    assert m["analyzed"] is True


def test_acoustic_metrics_tone_has_peak_and_rms():
    m = acoustic_metrics(_tone(amplitude=0.5))
    assert 0.4 < m["peak"] <= 0.5
    assert 0.3 < m["rms"] <= 0.5
    assert m["clipping_ratio"] == 0.0


def test_acoustic_metrics_detects_clipping():
    data = _wav_from_samples([32767, -32767] * 4000)
    m = acoustic_metrics(data)
    assert m["clipping_ratio"] == 1.0
    assert m["peak"] == 1.0


def test_acoustic_metrics_detects_dc_offset():
    data = _wav_from_samples([3000] * 8000)
    m = acoustic_metrics(data)
    assert m["dc_offset"] == pytest.approx(3000 / 32767, rel=0.01)


def test_classify_quality_reject_silence():
    assert classify_quality(acoustic_metrics(_wav_from_samples([0] * 8000))) == "REJECT"


def test_classify_quality_reject_clipping():
    data = _wav_from_samples([32767, -32767] * 4000)
    assert classify_quality(acoustic_metrics(data)) == "REJECT"


def test_classify_quality_warning_dc_offset():
    data = _wav_from_samples([3000] * 8000)
    assert classify_quality(acoustic_metrics(data)) == "WARNING"


def test_classify_quality_pass_clean_tone():
    assert classify_quality(acoustic_metrics(_tone())) == "PASS"


def test_wav_quality_bytes_returns_panel():
    panel = wav_quality_bytes(_tone())
    assert panel["grade"] == "PASS"
    for key in ("duration", "channels", "framerate", "peak_dbFS", "silence_ratio"):
        assert key in panel


# --- Subida: panel de QA y límites -------------------------------------------


def test_upload_returns_quality_panel(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", _tone(), "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "quality" in body
    assert body["quality"]["grade"] in ("PASS", "WARNING", "REJECT")
    assert body["audio_id"] == "audio-l15"


def test_upload_rejects_too_long(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "MAX_AUDIO_DURATION_SECONDS", 0.01)
    data = _wav_from_samples([0] * 8000, framerate=8000)  # 1s
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", data, "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 400


def test_upload_rejects_non_wav_mime(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", _tone(), "audio/mpeg")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 415


# --- Candado admin (PIN local) -----------------------------------------------


def test_admin_not_required_by_default(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/audio-library/status")
    assert r.json()["admin_required"] is False


def test_admin_required_blocks_upload_without_pin(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ADMIN_PIN", "1234")
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            files={"file": ("l15.wav", _tone(), "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 401
    assert client.get("/api/audio-library/status").json()["admin_required"] is True


def test_admin_upload_with_pin_succeeds(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ADMIN_PIN", "1234")
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            headers={"X-Admin-Pin": "1234"},
            files={"file": ("l15.wav", _tone(), "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 200


def test_admin_wrong_pin_rejected(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ADMIN_PIN", "1234")
    with TestClient(app) as client:
        r = client.post(
            "/api/audio-library/upload",
            headers={"X-Admin-Pin": "wrong"},
            files={"file": ("l15.wav", _tone(), "audio/wav")},
            data={"audio_id": "audio-l15"},
        )
    assert r.status_code == 401


# --- Backup + auditoría de borrado -------------------------------------------


def test_remove_entry_backs_up_and_audits(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    write_entry(AudioLibraryEntry(audio_id="a1", file="a1.wav"), _tone())
    assert remove_entry("a1") is True
    backups = tmp_path / "_backups"
    assert backups.exists()
    assert list(backups.glob("*.wav"))
    audit = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert '"action": "delete"' in audit
    assert '"audio_id": "a1"' in audit


# --- Content integrity check -------------------------------------------------


def test_content_validation_empty_library_is_ok():
    report = run_content_validation()
    assert report["total_items"] == len(QUESTION_BANK)
    assert report["tts"] >= report["recorded"]
    assert report["ok"] is True
    assert "error" not in report["by_severity"]


def test_content_validation_reports_cefr_mismatch(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    write_entry(
        AudioLibraryEntry(audio_id="audio-c001", file="audio-c001.wav", cefr="B2"),
        _tone(),
    )
    report = run_content_validation()
    categories = {i["category"] for i in report["issues"]}
    assert "cefr_mismatch" in categories

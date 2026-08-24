from fastapi.testclient import TestClient

import config
from main import app
from repositories import db


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


async def _raise(*args, **kwargs):
    raise RuntimeError("SECRET-INTERNAL")


def test_transcribe_audio_too_large_413(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "MAX_AUDIO_BYTES", 8)
    with TestClient(app) as client:
        r = client.post(
            "/api/transcribe",
            files={"file": ("a.webm", b"0123456789ABCDEF", "audio/webm")},
        )
    assert r.status_code == 413


def test_transcribe_bad_content_type_415(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/transcribe",
            files={"file": ("a.pdf", b"data", "application/pdf")},
        )
    assert r.status_code == 415


def test_models_error_not_leaked(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr("routers.models.list_ollama_models", _raise)
    with TestClient(app) as client:
        r = client.get("/api/models")
    assert r.status_code == 502
    assert "SECRET-INTERNAL" not in r.text


def test_chat_error_not_leaked(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr("routers.chat.chat_once", _raise)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "user", "content": "Hi"}]}
        )
    assert r.status_code == 502
    assert "SECRET-INTERNAL" not in r.text

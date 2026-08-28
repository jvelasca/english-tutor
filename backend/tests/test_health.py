from fastapi.testclient import TestClient

from config import VERSION
from main import app
from repositories import db
from services import audio_library, llm, stt, tts


def test_root():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["service"] == "english-tutor"
        assert r.json()["version"] == VERSION


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["version"] == VERSION


def _all_ok(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_true)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)
    monkeypatch.setattr(audio_library, "is_ready", lambda: True)


async def _async_true():
    return True


async def _async_false():
    return False


def test_health_live(monkeypatch):
    with TestClient(app) as client:
        r = client.get("/api/health/live")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_dependencies_all_ok(monkeypatch):
    _all_ok(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/health/dependencies")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "api": "ok",
            "database": "ok",
            "ollama": "ok",
            "stt": "ready",
            "tts": "ready",
            "audio_library": "ready",
        }


def test_ready_200_when_all_ok(monkeypatch):
    _all_ok(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_ready_503_when_ollama_down(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_false)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unavailable"
        assert body["dependencies"]["ollama"] == "error"

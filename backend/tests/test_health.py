from fastapi.testclient import TestClient

from main import app
from services import llm, store, stt, tts


def test_root():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["service"] == "english-tutor"


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def _all_ok(monkeypatch):
    monkeypatch.setattr(store, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_true)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)


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
        }


def test_ready_200_when_all_ok(monkeypatch):
    _all_ok(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_ready_503_when_ollama_down(monkeypatch):
    monkeypatch.setattr(store, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_false)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unavailable"
        assert body["dependencies"]["ollama"] == "error"

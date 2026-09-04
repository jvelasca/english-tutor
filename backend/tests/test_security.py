"""Tests de seguridad LAN (V1.41): protección de origen + rate limiting."""

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import security


def _app():
    app = FastAPI()

    @app.post("/x")
    async def create():
        return {"ok": True}

    @app.get("/y")
    async def read():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    return app


def test_origin_allowed():
    assert security.origin_allowed(None) is True
    assert security.origin_allowed("http://localhost:5173") is True
    assert security.origin_allowed("http://127.0.0.1:5173") is True
    assert security.origin_allowed("http://192.168.1.20:5173") is True
    assert security.origin_allowed("https://192.168.1.20") is True
    assert security.origin_allowed("http://10.0.0.5:3000") is True
    assert security.origin_allowed("http://172.16.0.9") is True
    assert security.origin_allowed("https://evil.example.com") is False
    assert security.origin_allowed("https://192.168.1.20.evil.com") is False


def test_unsafe_method_bad_origin_rejected():
    with TestClient(_app()) as client:
        r = client.post("/x", headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403


def test_unsafe_method_allowed_origin_passes():
    with TestClient(_app()) as client:
        r = client.post("/x", headers={"origin": "http://localhost:5173"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_unsafe_method_no_origin_passes():
    with TestClient(_app()) as client:
        r = client.post("/x")
    assert r.status_code == 200


def test_safe_method_ignores_origin():
    with TestClient(_app()) as client:
        r = client.get("/y", headers={"origin": "https://evil.example.com"})
    assert r.status_code == 200


def test_rate_limit_rejects_after_limit(monkeypatch):
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 2)
    security._clients.clear()
    with TestClient(_app()) as client:
        assert client.post("/x").status_code == 200
        assert client.post("/x").status_code == 200
        assert client.post("/x").status_code == 429
    security._clients.clear()


def test_health_exempt_never_rate_limited(monkeypatch):
    """Las sondas /api/health no consumen cupo ni pueden recibir 429 (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)

    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/y")
    async def read():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    with TestClient(app) as client:
        # Agotamos el cupo con rutas normales...
        assert client.get("/y").status_code == 200
        assert client.get("/y").status_code == 429
        # ...y /api/health sigue respondiendo aunque el cupo esté agotado.
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 200


def test_rate_limit_payload_and_retry_after(monkeypatch):
    """El 429 lleva body {detail, code} y cabecera Retry-After (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)
    security._clients.clear()
    with TestClient(_app()) as client:
        assert client.get("/y").status_code == 200
        r = client.get("/y")
        assert r.status_code == 429
        body = r.json()
        assert body["code"] == "RATE_LIMITED"
        assert "saturado" in body["detail"]
        assert r.headers.get("retry-after") == "5"
    security._clients.clear()


def test_rate_limit_snapshot_counts_rejections(monkeypatch):
    """rate_limit_snapshot cuenta los 429 de la ventana (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)
    security._clients.clear()
    assert security.rate_limit_snapshot() == 0
    with TestClient(_app()) as client:
        assert client.get("/y").status_code == 200
        for _ in range(3):
            assert client.get("/y").status_code == 429
    assert security.rate_limit_snapshot() == 3
    assert security.rate_limit_snapshot(window_seconds=0) == 0
    security._clients.clear()
    security._rejections.clear()


def test_rate_limit_snapshot_prunes_old_entries():
    security._rejections.append(time.monotonic() - 10_000)
    security._rejections.append(time.monotonic())
    assert security.rate_limit_snapshot() == 1
    security._rejections.clear()

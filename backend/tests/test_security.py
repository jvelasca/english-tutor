"""Tests de seguridad LAN (V1.41): protección de origen + rate limiting."""

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

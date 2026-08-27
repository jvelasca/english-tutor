import importlib
import sys

from fastapi.testclient import TestClient

from main import app


def _reload_app(monkeypatch, extra):
    """Reconstruye la app leyendo ALLOWED_ORIGINS_EXTRA (None = sin env)."""
    if extra is None:
        monkeypatch.delenv("ALLOWED_ORIGINS_EXTRA", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS_EXTRA", extra)
    importlib.reload(sys.modules["config"])
    importlib.reload(sys.modules["main"])
    return sys.modules["main"].app


def test_cors_allows_localhost_5173():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_allows_127_0_0_1_5173():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_allows_lan_ip_origin():
    with TestClient(app) as client:
        r = client.get(
            "/api/health", headers={"Origin": "http://192.168.1.42:5173"}
        )
        assert r.headers.get("access-control-allow-origin") == "http://192.168.1.42:5173"


def test_cors_rejects_unknown_origin():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers


def test_cors_allows_extra_origin_from_env(monkeypatch):
    fresh_app = _reload_app(monkeypatch, "https://my-app.vercel.app,https://alt.example")
    with TestClient(fresh_app) as client:
        r = client.get(
            "/api/health", headers={"Origin": "https://my-app.vercel.app"}
        )
        assert r.headers.get("access-control-allow-origin") == "https://my-app.vercel.app"


def test_cors_without_extra_env_keeps_default(monkeypatch):
    fresh_app = _reload_app(monkeypatch, None)
    with TestClient(fresh_app) as client:
        r = client.get(
            "/api/health", headers={"Origin": "https://my-app.vercel.app"}
        )
        assert "access-control-allow-origin" not in r.headers
        r2 = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert r2.headers.get("access-control-allow-origin") == "http://localhost:5173"

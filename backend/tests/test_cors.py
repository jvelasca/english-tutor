from fastapi.testclient import TestClient

from main import app


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

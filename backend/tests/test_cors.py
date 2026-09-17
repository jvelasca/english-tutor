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


def test_cors_allows_the_product_origin_8000():
    """V3.72 (RC-01): el producto sirve la UI en el mismo origen (HTTPS :8000)."""
    with TestClient(app) as client:
        r = client.get(
            "/api/health", headers={"Origin": "https://localhost:8000"}
        )
        assert (
            r.headers.get("access-control-allow-origin")
            == "https://localhost:8000"
        )


def test_cors_allows_the_dev_orgin_https_5173():
    """El modo de desarrollo (Vite con TLS) sigue dentro de la allow-list."""
    with TestClient(app) as client:
        r = client.get(
            "/api/health", headers={"Origin": "https://localhost:5173"}
        )
        assert (
            r.headers.get("access-control-allow-origin")
            == "https://localhost:5173"
        )


def test_cors_rejects_unknown_origin():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers

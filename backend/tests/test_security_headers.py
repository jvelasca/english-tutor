"""Tests de las cabeceras HTTP defensivas (V3.73.x)."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from security_headers import SecurityHeadersMiddleware


def _app():
    app = FastAPI()

    @app.get("/x")
    async def read():
        return {"ok": True}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


def test_las_cabeceras_defensivas_estan_presentes():
    with TestClient(_app()) as client:
        r = client.get("/x")

    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "object-src 'none'" in r.headers["content-security-policy"]
    assert "microphone=(self)" in r.headers["permissions-policy"]


def test_no_se_envia_hsts():
    """HSTS con certificado autofirmado dejaría el origen inutilizable.

    El producto sirve HTTPS con un certificado propio (`backend/data/certs/`), que
    ningún navegador acepta como de confianza: fijar `Strict-Transport-Security`
    ahí es irreversible para el usuario hasta que limpie el estado del navegador.
    """
    with TestClient(_app()) as client:
        r = client.get("/x")

    assert "strict-transport-security" not in r.headers


def test_no_pisa_una_cabecera_mas_especifica_de_la_ruta():
    """Si la respuesta ya trae una cabecera, el middleware no la duplica."""
    app = FastAPI()

    @app.get("/x")
    async def read():
        return JSONResponse({"ok": True}, headers={"X-Frame-Options": "SAMEORIGIN"})

    app.add_middleware(SecurityHeadersMiddleware)
    with TestClient(app) as client:
        r = client.get("/x")

    # `TestClient` une los duplicados con ", ": la igualdad prueba que solo hay uno.
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_las_cabeceras_estan_en_la_app_real():
    """Candado de integración: la app de verdad monta el middleware."""
    from main import app

    with TestClient(app) as client:
        r = client.get("/api/health")

    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_los_rechazos_del_otro_middleware_tambien_las_llevan():
    """El orden importa: `SecurityHeadersMiddleware` va por fuera y decora el 403.

    Un `Origin` no permitido lo corta `SecurityMiddleware` antes de enrutar; si el
    de cabeceras quedara por dentro, la respuesta de rechazo saldría sin ellas.
    """
    from main import app

    with TestClient(app) as client:
        r = client.post("/api/chat", headers={"Origin": "https://evil.example.com"})

    assert r.status_code == 403
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]

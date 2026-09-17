"""Servido de la UI compilada desde el backend (RC-01, V3.72).

Fija el contrato observable del servido estático: `index.html` en la raíz, los
assets bajo `/assets`, *fallback* SPA para rutas desconocidas, **404 real** para
`/api/*` sin ruta y **fail-open** cuando el artefacto no existe.

Los tests de montaje construyen su propia app sobre un `dist` de `tmp_path`, así
que son **herméticos**: no dependen de que el frontend se haya compilado.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.frontend_dist import (
    dist_available,
    mount_frontend,
    resolve_static_file,
)

INDEX_HTML = "<!doctype html><html><body>English Tutor</body></html>"


def _make_dist(root: Path) -> Path:
    """Artefacto mínimo con la forma real del build de Vite."""
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (root / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (root / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    return root


def _app_with_api_and_dist(dist: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    async def _health() -> dict:
        return {"version": "test"}

    assert mount_frontend(app, dist) is True
    return app


def test_dist_available_es_falso_sin_artefacto(tmp_path):
    assert dist_available(tmp_path) is False


def test_dist_available_es_cierto_con_index(tmp_path):
    _make_dist(tmp_path)
    assert dist_available(tmp_path) is True


def test_sin_artefacto_no_se_monta_nada_y_el_arranque_no_se_rompe(tmp_path, caplog):
    app = FastAPI()

    assert mount_frontend(app, tmp_path / "no-existe") is False

    client = TestClient(app)
    # La app sigue viva: sin fallback, la raíz es un 404 normal.
    assert client.get("/").status_code == 404


def test_sirve_el_index_en_la_raiz(tmp_path):
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/")

    assert response.status_code == 200
    assert "English Tutor" in response.text


def test_sirve_los_assets_del_build(tmp_path):
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/assets/index-abc.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"


def test_sirve_ficheros_sueltos_de_la_raiz_del_artefacto(tmp_path):
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.text == "<svg/>"


def test_fallback_spa_sirve_el_index_en_rutas_desconocidas(tmp_path):
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/diccionario")

    assert response.status_code == 200
    assert "English Tutor" in response.text


def test_la_api_tiene_prioridad_sobre_el_fallback(tmp_path):
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"version": "test"}


def test_un_api_desconocida_es_404_y_no_el_index(tmp_path):
    """Un endpoint inexistente no puede devolver 200 con la página de la app."""
    dist = _make_dist(tmp_path)
    client = TestClient(_app_with_api_and_dist(dist))

    response = client.get("/api/no-existe")

    assert response.status_code == 404


def test_una_ruta_codificada_con_puntos_no_escapa_del_artefacto(tmp_path):
    dist = _make_dist(tmp_path)
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("no debe servirse", encoding="utf-8")
    client = TestClient(_app_with_api_and_dist(dist))

    # Codificada a propósito: httpx normalizaría un `/../` literal antes de enviar.
    response = client.get("/%2E%2E/secreto.txt")

    assert "no debe servirse" not in response.text
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert "English Tutor" in response.text


def test_resolve_static_file_no_escapa_del_directorio(tmp_path):
    dist = _make_dist(tmp_path)
    (tmp_path / "fuera.txt").write_text("x", encoding="utf-8")

    assert resolve_static_file("../fuera.txt", dist) is None
    assert resolve_static_file("../../etc/passwd", dist) is None
    assert resolve_static_file("", dist) is None
    assert resolve_static_file("no-existe.js", dist) is None
    assert resolve_static_file("asset", dist) is None  # directorio, no fichero


def test_resolve_static_file_devuelve_el_fichero_dentro(tmp_path):
    dist = _make_dist(tmp_path)

    resolved = resolve_static_file("/assets/index-abc.js", dist)

    assert resolved is not None
    assert resolved.is_file()


def test_el_montaje_se_puede_omitir_sin_artefacto_y_no_afecta_a_la_api(tmp_path):
    app = FastAPI()

    @app.get("/api/health")
    async def _health() -> dict:
        return {"ok": True}

    assert mount_frontend(app, tmp_path / "vacio") is False
    assert TestClient(app).get("/api/health").json() == {"ok": True}


@pytest.mark.skipif(
    not dist_available(), reason="frontend/dist no está construido en este entorno"
)
def test_la_app_real_sirve_el_artefacto_sin_eclipsar_la_api():
    from main import app

    client = TestClient(app)
    root = client.get("/")
    api = client.get("/api/health")
    info = client.get("/api")

    assert root.status_code == 200
    assert "<html" in root.text.lower()
    assert api.status_code == 200
    assert "version" in api.json()
    # La información de servicio sigue disponible en `/api` (ya no compite con la UI).
    assert info.json()["service"] == "english-tutor"

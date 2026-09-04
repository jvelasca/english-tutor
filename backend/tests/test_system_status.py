"""Tests del endpoint operativo GET /api/system/status (V3.6.2).

El launcher de escritorio lo consulta para saber si el backend está generando
práctica extra (trabajos `running`) y si está rechazando peticiones por rate
limit. No exige admin (como /api/health) y no toca el modelo local.
"""
import time

from fastapi.testclient import TestClient

import security
from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_server_status_idle(monkeypatch, tmp_path):
    """Sin trabajos ni rechazos: generación en reposo y 0 rechazos."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/system/status").json()
    assert body["generation"]["running"] == 0
    assert body["generation"]["jobs"] == []
    assert body["rate_limited"]["rejected_last_minute"] == 0


def test_server_status_reports_running_job(monkeypatch, tmp_path):
    """Un trabajo de generación `running` aparece con su nivel y detalle."""
    uid = _setup(monkeypatch, tmp_path)
    job = listening_repo.create_generation_job(uid, "B1", 5)
    with TestClient(app) as client:
        body = client.get("/api/system/status").json()
    assert body["generation"]["running"] == 1
    assert body["generation"]["jobs"][0]["level"] == "B1"
    assert body["generation"]["jobs"][0]["requested"] == 5
    assert body["generation"]["jobs"][0]["id"] == job["id"]


def test_server_status_reports_rejections(monkeypatch, tmp_path):
    """Los 429 del último minuto salen en rate_limited.rejected_last_minute."""
    _setup(monkeypatch, tmp_path)
    # Simula dos rechazos del rate limiter.
    security._rejections.append(time.monotonic())
    security._rejections.append(time.monotonic())
    try:
        with TestClient(app) as client:
            body = client.get("/api/system/status").json()
        assert body["rate_limited"]["rejected_last_minute"] == 2
    finally:
        security._rejections.clear()

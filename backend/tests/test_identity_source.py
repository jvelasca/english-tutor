"""La identidad **no la elige el cliente** (V3.75, Fase 2 del P0).

Es el test que fija la vulnerabilidad, no un detalle de implementación: hasta
V3.74, `?user_id=` **era** la identidad, así que cualquiera que alcanzara la API
(por ejemplo, otro equipo de la LAN) leía de otro perfil. Con la Fase 2 el
parámetro ya no significa nada: manda la sesión firmada.

Por eso estos casos mandan a propósito las dos cosas a la vez —una sesión del
perfil A **y** un `?user_id=B`— y comprueban que responden los datos de A. Y por
eso el módulo va marcado `identidad_cruda`, que lo exime del adaptador de
`conftest.py`: el adaptador traduce justo ese parámetro a una sesión, así que
«`?user_id=` sin sesión» sería inexpresable con él. El resto de la suite lo usa;
aquí estorba.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import settings as settings_repo
from repositories import users as users_repo

pytestmark = pytest.mark.identidad_cruda


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ana = users_repo.create_user("Ana")["id"]
    beto = users_repo.create_user("Beto")["id"]
    settings_repo.set_settings(ana, {"model": "modelo-de-Ana"})
    settings_repo.set_settings(beto, {"model": "modelo-de-Beto"})
    return ana, beto


def test_con_sesion_de_ana_pedir_lo_de_beto_devuelve_lo_de_ana(monkeypatch, tmp_path):
    ana, beto = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": ana}).status_code == 200
        r = client.get("/api/settings", params={"user_id": beto})
        assert r.status_code == 200
        assert r.json()["settings"]["model"] == "modelo-de-Ana"


def test_y_al_reves_la_sesion_manda_igual(monkeypatch, tmp_path):
    ana, beto = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": beto}).status_code == 200
        r = client.get("/api/settings", params={"user_id": ana})
        assert r.json()["settings"]["model"] == "modelo-de-Beto"


def test_el_parametro_ya_no_abre_la_puerta_a_nadie(monkeypatch, tmp_path):
    """Sin sesión, `?user_id=` **no** da acceso: era exactamente la vulnerabilidad."""
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/settings", params={"user_id": ana})
        assert r.status_code == 401
        assert r.json()["detail"] == "SESSION_REQUIRED"


def test_tampoco_sirve_para_el_perfil_de_aprendizaje(monkeypatch, tmp_path):
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/profile", params={"user_id": ana}).status_code == 401


def test_con_sesion_de_ana_el_perfil_de_aprendizaje_es_el_de_ana(monkeypatch, tmp_path):
    ana, beto = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": ana}).status_code == 200
        assert client.get("/api/profile", params={"user_id": beto}).status_code == 200

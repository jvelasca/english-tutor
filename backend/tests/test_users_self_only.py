"""Bordes de autorización: cada uno edita lo suyo (V3.75, Fase 2 del P0).

Dos escrituras de la API elegían su destinatario sin credencial ninguna:

- `PATCH /api/users/{id}`: el `id` de la URL, y ya está. Renombrar o reescribir el
  perfil de otro alumno era cambiar un parámetro.
- `PUT /api/settings`: el `user_id` del **cuerpo**. El plan del P0 no la había
  contemplado; se cerró en la misma fase, porque dejarla viva habría hecho falsa
  la afirmación «con una sesión de A no se escriben datos de B».

Ojo con lo que **no** se cierra aquí: `POST /api/users` sigue abierto (alta de
perfil del primer arranque) y `GET /api/users` sigue enumerando perfiles sin
credencial. El producto no tiene autenticación, así que quien alcanza la API puede
**abrir sesión** para el perfil que quiera; lo que ya no puede es elegir la
identidad petición a petición. Autenticar de verdad es la Fase 3.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import settings as settings_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ana = users_repo.create_user("Ana")["id"]
    beto = users_repo.create_user("Beto")["id"]
    settings_repo.set_settings(beto, {"model": "modelo-de-Beto"})
    return ana, beto


# --- PATCH /api/users/{id} --------------------------------------------------


def test_cada_uno_edita_su_propio_perfil(monkeypatch, tmp_path):
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": ana})
        r = client.patch(f"/api/users/{ana}", json={"name": "Ana M"})
        assert r.status_code == 200
        assert r.json()["name"] == "Ana M"


def test_con_sesion_de_ana_no_se_edita_el_perfil_de_beto(monkeypatch, tmp_path):
    ana, beto = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": ana})
        r = client.patch(f"/api/users/{beto}", json={"name": "Renombrado"})
        assert r.status_code == 403
        # Y no basta con que diga 403: el dato no puede haber cambiado.
        assert users_repo.get_user(beto)["name"] == "Beto"


def test_sin_sesion_no_se_edita_ningun_perfil(monkeypatch, tmp_path):
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.patch(f"/api/users/{ana}", json={"name": "Renombrado"})
        assert r.status_code == 401
        assert users_repo.get_user(ana)["name"] == "Ana"


# --- PUT /api/settings ------------------------------------------------------


def test_las_preferencias_se_guardan_en_el_perfil_de_la_sesion(monkeypatch, tmp_path):
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": ana})
        r = client.put(
            "/api/settings",
            json={"user_id": ana, "settings": {"model": "modelo-de-Ana"}},
        )
        assert r.status_code == 200
        assert settings_repo.get_settings(ana)["model"] == "modelo-de-Ana"


def test_con_sesion_de_ana_no_se_escriben_las_de_beto(monkeypatch, tmp_path):
    ana, beto = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": ana})
        r = client.put(
            "/api/settings",
            json={"user_id": beto, "settings": {"model": "secuestrado"}},
        )
        assert r.status_code == 403
        assert settings_repo.get_settings(beto)["model"] == "modelo-de-Beto"


def test_sin_sesion_no_se_escriben_preferencias(monkeypatch, tmp_path):
    ana, _ = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/settings",
            json={"user_id": ana, "settings": {"model": "sin-sesion"}},
        )
        assert r.status_code == 401
        assert settings_repo.get_settings(ana) == {}

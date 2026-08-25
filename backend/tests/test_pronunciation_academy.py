"""Tests del puente pronunciation → mastery (Evidence Engine, tercera pata).

Espeja `test_speaking.py`: el read-aloud determinista registra evidencia con
source/skill 'pronunciation', alimenta el mastery del objetivo y queda aislado
por usuario, sin LLM ni red.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services.curriculum import load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _first_pronunciation_objective():
    objs = load_level("a1").objectives()
    for o in objs:
        if "pronunciation" in o.skills:
            return o
    return objs[0]


def test_pronunciation_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_pronunciation_objective()
    assert "pronunciation" in obj.skills, "ningún objetivo A1 declara 'pronunciation'"
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/pronunciation",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "Hello world",
                "heard": "Hello world",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 3
    assert body["pronunciation_mastery"] > 0

    pronunciation_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "pronunciation"
    ]
    assert pronunciation_rows, "no se registró evidencia de pronunciation"
    assert all(row["skill"] == "pronunciation" for row in pronunciation_rows)
    assert len(pronunciation_rows) >= 4  # 3 criterios + 1 overall
    assert academy_repo.get_objective_row(a, "a1", obj.id, "pronunciation") is not None


def test_pronunciation_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/pronunciation",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "expected": "Hello world",
                "heard": "Hello world",
            },
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


def test_pronunciation_evidence_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = _first_pronunciation_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/pronunciation",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "Hello world",
                "heard": "Hello world",
            },
        )
    assert academy_repo.list_evidence(b) == []

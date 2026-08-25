"""Tests del scorer determinista de speaking (rubric CEFR de 6 dimensiones)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import speaking as speaking_svc
from services.curriculum import load_level
from services.speaking import CRITERION_WEIGHTS, SPEAKING_CRITERIA


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _first_speaking_objective():
    objs = load_level("a1").objectives()
    for o in objs:
        if "speaking" in o.skills:
            return o
    return objs[0]


def test_score_speaking_keys_and_range():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert set(result.keys()) == {"heard", "expected", "criteria", "overall"}
    assert set(result["criteria"].keys()) == set(SPEAKING_CRITERIA)
    for criterion in SPEAKING_CRITERIA:
        assert 0.0 <= result["criteria"][criterion] <= 1.0
    assert 0.0 <= result["overall"] <= 1.0


def test_score_speaking_perfect_high():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert result["overall"] >= 0.7
    assert result["criteria"]["pronunciation"] >= 0.9


def test_score_speaking_mismatch_low():
    result = speaking_svc.score_speaking("banana banana banana", "I am a student")
    assert result["overall"] < 0.5
    assert result["criteria"]["task_achievement"] < 0.5
    assert result["criteria"]["lexical_resource"] < 0.5


def test_score_speaking_fluency_unknown():
    result = speaking_svc.score_speaking("I am a student", "I am a student", None)
    assert result["criteria"]["fluency"] == 0.5


def test_score_speaking_empty_expected():
    result = speaking_svc.score_speaking("anything", "")
    assert result["criteria"]["lexical_resource"] == 1.0
    assert result["criteria"]["task_achievement"] == 1.0


def test_rubric_weights_sum_to_one():
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Endpoint / integración (puente speaking → mastery) --------------------


def test_speaking_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    assert "speaking" in obj.skills, "ningún objetivo A1 declara 'speaking'"
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)
    assert len(speaking_rows) >= 7  # 6 criterios + 1 overall
    assert academy_repo.get_objective_row(a, "a1", obj.id, "speaking") is not None


def test_speaking_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


def test_speaking_evidence_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert academy_repo.list_evidence(b) == []

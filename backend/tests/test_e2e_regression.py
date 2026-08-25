"""Regresión E2E: cadena completa API → dominio → repositorio → DB → respuesta.

Cubre los huecos que los tests unitarios no garantizan: que el estado persiste en
SQLite (no solo que el endpoint responde 200) para Placement, Remediación y
Listening.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.curriculum import load_assessments, load_level
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Placement: el resultado final se persiste ----------------------------


def test_placement_loop_persists_assessment_result(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    correct_by_id = {it.id: it.correct_index for it in data.placement.items}
    answers = {}
    with TestClient(app) as client:
        while True:
            r = client.post(
                "/api/academy/placement/next",
                params={"user_id": a},
                json={"answers": answers},
            )
            assert r.status_code == 200
            body = r.json()
            if body["next_item"] is not None:
                answers[body["next_item"]["id"]] = correct_by_id[
                    body["next_item"]["id"]
                ]
            if body["done"]:
                assert body["result"] is not None
                break

    rows = academy_repo.list_assessment_results(a)
    assert rows, "el resultado adaptativo no se persistió"
    assert rows[0]["assessment_id"] == data.placement.id
    assert rows[0]["passed"] is True
    assert "level" in rows[0]["results"]
    assert "theta" in rows[0]["results"]


# --- Remediación: plan derivado del estado de la DB ------------------------


def test_remediation_endpoint_returns_weak_skill_after_failure(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    wrong = {c.id: (c.correct_index + 1) % len(c.options) for c in obj.checks}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": wrong},
        )
        assert r.status_code == 200
        resp = client.get(
            "/api/academy/remediation", params={"user_id": a, "level_id": "a1"}
        )
    assert resp.status_code == 200
    listed = {s["skill"] for s in resp.json()["skills"]}
    assessed = set(obj.assessable_skills())
    assert assessed, "el objetivo no tiene destrezas evaluables"
    assert listed & assessed, "ninguna destreza débil apareció en el plan"


# --- Listening: intento con métricas persiste y alimenta el diagnóstico ----


def test_listening_full_chain_persists_attempt_and_diagnostic(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        nxt = client.get("/api/listening/question", params={"user_id": a})
        assert nxt.status_code == 200
        assert "answer_index" not in nxt.json()

        ans = client.post(
            "/api/listening/answer",
            params={"user_id": a},
            json={
                "question_id": q["id"],
                "answer_index": q["answer_index"],
                "response_time_ms": 1200,
                "replay_count": 1,
            },
        )
        assert ans.status_code == 200
        assert ans.json()["correct"] is True

        diag = client.get("/api/listening/diagnostic", params={"user_id": a})
        assert diag.status_code == 200

    attempts = listening_repo.list_attempts(a)
    assert len(attempts) == 1
    assert attempts[0]["response_time_ms"] == 1200
    assert attempts[0]["replay_count"] == 1
    assert attempts[0]["correct"] == 1
    assert attempts[0]["skill"] == q["skill"]
    assert attempts[0]["difficulty"] == q["difficulty"]

    by_skill = {s["skill"]: s for s in diag.json()["subskills"]}
    assert by_skill[q["skill"]]["attempts"] == 1
    assert by_skill[q["skill"]]["correct"] == 1

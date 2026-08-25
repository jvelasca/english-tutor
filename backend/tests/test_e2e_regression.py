"""Regresión E2E: cadena completa API → dominio → repositorio → DB → respuesta.

Cubre los huecos que los tests unitarios no garantizan: que el estado persiste en
SQLite (no solo que el endpoint responde 200) para Placement, Remediación,
Listening, Speaking, Writing, Pronunciation y el perfil con olvido (review_due).
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.curriculum import load_assessments, load_level
from services.listening import QUESTION_BANK, difficulty_from_vector


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
    assert attempts[0]["difficulty"] == difficulty_from_vector(q["difficulty_vector"])

    by_skill = {s["skill"]: s for s in diag.json()["subskills"]}
    assert by_skill[q["skill"]]["attempts"] == 1
    assert by_skill[q["skill"]]["correct"] == 1


# --- Speaking/Writing/Pronunciation: evidencia + mastery persistidos ---------


def _first_objective_with(level_id, skill):
    return next(
        o for o in load_level(level_id).objectives() if skill in o.skills
    )


def test_speaking_full_chain_persists_evidence_and_mastery(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    obj = _first_objective_with("a1", "speaking")
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
    assert r.json()["speaking_mastery"] > 0

    rows = [row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"]
    assert rows, "no se persistió evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in rows)
    assert academy_repo.get_objective_row(a, "a1", obj.id, "speaking") is not None


def test_writing_full_chain_persists_evidence_and_mastery(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    obj = _first_objective_with("a1", "writing")
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "text": "I am a student",
            },
        )
    assert r.status_code == 200
    assert r.json()["writing_mastery"] > 0

    rows = [row for row in academy_repo.list_evidence(a) if row["source"] == "writing"]
    assert rows, "no se persistió evidencia de writing"
    assert all(row["skill"] == "writing" for row in rows)
    assert academy_repo.get_objective_row(a, "a1", obj.id, "writing") is not None


def test_pronunciation_full_chain_persists_evidence_and_mastery(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    obj = _first_objective_with("a1", "pronunciation")
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
    assert r.json()["pronunciation_mastery"] > 0

    rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "pronunciation"
    ]
    assert rows, "no se persistió evidencia de pronunciation"
    assert all(row["skill"] == "pronunciation" for row in rows)
    assert (
        academy_repo.get_objective_row(a, "a1", obj.id, "pronunciation") is not None
    )


# --- Perfil + olvido: review_due derivado del estado persistido -------------


def test_profile_exposes_review_due_after_evidence(monkeypatch, tmp_path):
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
        prof = client.get(
            "/api/academy/profile", params={"user_id": a, "level_id": "a1"}
        )
    assert prof.status_code == 200
    skills = prof.json()["skills"]
    assert all(isinstance(s["review_due"], bool) for s in skills)
    assert any(s["review_due"] for s in skills), "ninguna destreza marcada para repaso"

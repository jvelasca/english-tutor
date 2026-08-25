"""Tests de la Academy: currículum, mastery, progresión, adaptación y evaluación."""

import asyncio

from fastapi.testclient import TestClient

from domain import academy as academy_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import (
    CANONICAL_SKILLS,
    load_assessments,
    load_level,
    next_level_id,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


# --- Currículum -----------------------------------------------------------


def test_load_a1_has_ten_modules():
    lv = load_level("a1")
    assert lv.level == "A1"
    assert len(lv.modules) == 10
    assert lv.modules[0].id == "a1-m01"
    assert lv.modules[-1].id == "a1-m10"


def test_a1_objectives_are_valid():
    lv = load_level("a1")
    objs = lv.objectives()
    assert len(objs) > 20
    for o in objs:
        assert o.can_do.startswith("I can ")
        assert o.skills, o.id
        assert all(s in CANONICAL_SKILLS for s in o.skills)


def test_next_level_id_sequence():
    assert next_level_id("A1") == "a2"
    assert next_level_id("A2") == "b1"
    assert next_level_id("C2") is None


def test_a2_loads_reusing_same_schema():
    lv = load_level("a2")
    assert lv.level == "A2"
    assert len(lv.modules) >= 5
    for o in lv.objectives():
        assert o.can_do.startswith("I can ")
        assert all(s in CANONICAL_SKILLS for s in o.skills)


# --- Mastery y progresión -------------------------------------------------


def test_objective_progress_mastered_when_all_skills_met():
    lv = load_level("a1")
    obj = lv.objectives()[0]
    scores = {s: 1.0 for s in obj.skills}
    attempts = {s: obj.minimum_attempts for s in obj.skills}
    assert academy_svc.objective_progress(obj, scores, attempts)["mastered"] is True


def test_objective_progress_not_mastered_when_skill_low():
    lv = load_level("a1")
    obj = lv.objectives()[0]
    scores = {s: 0.0 for s in obj.skills}
    attempts = {s: obj.minimum_attempts for s in obj.skills}
    assert academy_svc.objective_progress(obj, scores, attempts)["mastered"] is False


def test_objective_progress_requires_minimum_attempts():
    lv = load_level("a1")
    obj = lv.objectives()[0]
    scores = {s: 1.0 for s in obj.skills}
    # Puntuación perfecta pero sin intentos suficientes → no dominado (consistencia).
    assert academy_svc.objective_progress(obj, scores, {})["mastered"] is False
    one = {s: 1 for s in obj.skills}
    assert academy_svc.objective_progress(obj, scores, one)["mastered"] is False


def test_mastery_is_per_objective_not_contagious():
    lv = load_level("a1")
    objs = lv.objectives()
    o1, o2 = objs[0], objs[1]
    assert set(o1.skills) & set(o2.skills), (
        "los dos primeros objetivos comparten destreza"
    )
    # Domina o1 (puntuación alta + intentos suficientes); o2 queda sin evidencia.
    objective_scores = {o1.id: {s: 1.0 for s in o1.skills}}
    objective_attempts = {o1.id: {s: o1.minimum_attempts for s in o1.skills}}
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    assert o1.id in mastered
    assert o2.id not in mastered  # el dominio de o1 no se contagia a o2


def test_unlock_state_is_gated():
    lv = load_level("a1")
    ids = [o.id for o in lv.objectives()]
    unlocked = academy_svc.unlock_state(lv, set())
    assert unlocked[ids[0]] is True
    assert all(not unlocked[oid] for oid in ids[1:])


def test_next_objective_returns_first_unmastered():
    lv = load_level("a1")
    first = lv.objectives()[0].id
    assert academy_svc.next_objective(lv, set()) == first


def test_adaptive_next_prefers_weakest_skill():
    lv = load_level("a1")
    ids = [o.id for o in lv.objectives()]
    # Primero dominado; el resto desbloqueado secuencialmente: el siguiente es ids[1].
    assert academy_svc.adaptive_next(lv, {ids[0]}, {}) == ids[1]


# --- Evaluación -----------------------------------------------------------


def test_placement_result_a1():
    data = load_assessments()
    items = data.placement.items
    answers = {
        it.id: it.correct_index
        if it.difficulty == 1
        else (it.correct_index + 1) % len(it.options)
        for it in items
    }
    result = academy_svc.placement_result(items, answers)
    assert result["level"] == "A1"
    assert result["answered"] == len(items)
    assert 0 < result["confidence"] <= 0.95


def test_exam_result_pass_and_fail():
    data = load_assessments()
    exam = data.exams["a1"]
    good = {it.id: it.correct_index for it in exam.items}
    assert academy_svc.exam_result(exam, good)["passed"] is True

    bad = {it.id: (it.correct_index + 1) % len(it.options) for it in exam.items}
    result = academy_svc.exam_result(exam, bad)
    assert result["passed"] is False
    assert result["failed_skills"]


def test_study_plan_spans_levels():
    plan = academy_svc.study_plan("A1", "B1", 12)
    assert [s["level"] for s in plan] == ["A1", "A2"]
    assert sum(s["weeks"] for s in plan) == 12


# --- AI Teacher -----------------------------------------------------------


def test_build_lesson_prompt_includes_objective():
    from services.context import build_lesson_prompt

    obj = {
        "can_do": "I can introduce myself and give basic personal information.",
        "concepts": ["I am", "My name is"],
        "vocabulary": ["name", "country"],
        "skills": ["grammar", "vocabulary"],
    }
    prompt = build_lesson_prompt(obj, "A1", {"grammar": 0.4, "vocabulary": 0.9}, [])
    assert "introduce myself" in prompt
    assert "I am" in prompt
    assert "grammar" in prompt  # destreza más débil priorizada


def test_lesson_prompt_for_valid_objective(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    prompt = asyncio.run(academy_domain.lesson_prompt(a, "a1-m01-u01-l01-o01"))
    assert prompt is not None
    assert "introduce myself" in prompt


def test_lesson_prompt_unknown_objective_none(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert asyncio.run(academy_domain.lesson_prompt(a, "no-existe")) is None


# --- Repositorio ----------------------------------------------------------


def test_next_mastery_state_decays_with_bad_evidence():
    s0 = academy_svc.next_mastery_state(None, 0.6, 0.8)
    s1 = academy_svc.next_mastery_state(s0, 0.9, 0.8)
    s2 = academy_svc.next_mastery_state(s1, 0.4, 0.8)
    assert s2["score"] < s1["score"]  # decaimiento (ya no es MAX)
    assert s2["streak"] == 0  # racha reiniciada
    assert s2["attempts"] == 3
    assert s2["recent_score"] < s1["recent_score"]


def test_next_mastery_state_streak_and_confidence():
    s = None
    for _ in range(3):
        s = academy_svc.next_mastery_state(s, 1.0, 0.8)
    assert s["streak"] == 3
    assert s["confidence"] == 1.0
    assert s["score"] >= 0.8  # dominado tras una racha consistente


def test_apply_skill_evidence_persists_and_decays(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert academy_repo.enroll(a, "a1", "A1") is True
    assert academy_repo.get_enrollment(a, "a1")["level"] == "A1"

    assert academy_repo.get_skill_row(a, "a1", "grammar") is None
    state = academy_svc.next_mastery_state(None, 0.9, 0.8)
    assert academy_repo.apply_skill_evidence(a, "a1", "grammar", state) is True
    assert academy_repo.get_skill_mastery(a, "a1")["grammar"] == state["score"]

    row = academy_repo.get_skill_row(a, "a1", "grammar")
    assert row["attempts"] == 1
    # Una evidencia mala posterior baja el mastery (no es el máximo histórico).
    worse = academy_svc.next_mastery_state(row, 0.4, 0.8)
    academy_repo.apply_skill_evidence(a, "a1", "grammar", worse)
    assert academy_repo.get_skill_mastery(a, "a1")["grammar"] < state["score"]


def test_lesson_completed_does_not_change_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    state = academy_svc.next_mastery_state(None, 1.0, 0.8)
    academy_repo.apply_skill_evidence(a, "a1", "grammar", state)

    assert academy_repo.record_lesson_completed(a, "a1", "o1") is True
    # Los 'lesson_completed' no se cuentan como intentos.
    assert academy_repo.list_attempts(a, "a1") == {}
    # Y no alteran el mastery.
    assert academy_repo.get_skill_mastery(a, "a1")["grammar"] == state["score"]


def test_certificate_and_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    academy_repo.award_certificate(a, "a1", "A1", 0.9)
    assert len(academy_repo.list_certificates(a)) == 1
    assert academy_repo.list_certificates(b) == []


# --- Endpoints ------------------------------------------------------------


def test_endpoint_levels_lists_a1(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/levels", params={"user_id": a})
    assert r.status_code == 200
    levels = {lv["level_id"]: lv for lv in r.json()["levels"]}
    assert levels["a1"]["available"] is True
    assert levels["a1"]["objective_count"] > 20
    assert levels["a2"]["available"] is True
    assert levels["b1"]["available"] is False


def test_endpoint_enroll_and_detail(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/enroll", params={"user_id": a}, json={"level_id": "a1"}
        )
        assert r.status_code == 200

        detail = client.get("/api/academy/levels/a1", params={"user_id": a}).json()
        assert detail["progress"]["total"] > 20
        first = detail["objectives"][0]
        assert first["status"] == "available"
        assert detail["objectives"][1]["status"] == "locked"

        nxt = client.get(
            "/api/academy/next", params={"user_id": a, "level_id": "a1"}
        ).json()
        assert nxt["objective_id"] == first["id"]


def test_endpoint_placement_submit(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    answers = {
        it.id: it.correct_index
        if it.difficulty == 1
        else (it.correct_index + 1) % len(it.options)
        for it in data.placement.items
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/placement/submit",
            params={"user_id": a},
            json={"answers": answers},
        )
    assert r.status_code == 200
    assert r.json()["level"] == "A1"


def test_endpoint_exam_pass_awards_certificate(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    exam = data.exams["a1"]
    answers = {it.id: it.correct_index for it in exam.items}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/exam/a1/submit",
            params={"user_id": a},
            json={"answers": answers},
        )
    assert r.status_code == 200
    assert r.json()["passed"] is True

    certs = client.get("/api/academy/certificates", params={"user_id": a}).json()
    assert certs["certificates"][0]["level"] == "A1"


def test_exam_pass_unlocks_next_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    exam = data.exams["a1"]
    answers = {it.id: it.correct_index for it in exam.items}
    with TestClient(app) as client:
        client.post(
            "/api/academy/exam/a1/submit",
            params={"user_id": a},
            json={"answers": answers},
        )
        enr = client.get("/api/academy/enrollment", params={"user_id": a}).json()
    by_level = {e["level_id"]: e["status"] for e in enr["enrollments"]}
    assert by_level["a1"] == "completed"
    assert "a2" in by_level  # desbloqueo en cascada


def test_endpoint_exam_fail_no_certificate(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    exam = data.exams["a1"]
    answers = {it.id: (it.correct_index + 1) % len(it.options) for it in exam.items}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/exam/a1/submit",
            params={"user_id": a},
            json={"answers": answers},
        )
    assert r.status_code == 200
    assert r.json()["passed"] is False

    certs = client.get("/api/academy/certificates", params={"user_id": a}).json()
    assert certs["certificates"] == []


def test_endpoint_study_plan(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/study-plan",
            json={"start_level": "A1", "target_level": "B2", "weeks": 12},
        )
    assert r.status_code == 200
    assert len(r.json()["steps"]) == 3


# --- Intentos y contadores ------------------------------------------------


def test_record_and_list_attempts(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert academy_repo.record_attempt(a, "a1", "o1", "grammar", "correct") is True
    assert academy_repo.record_attempt(a, "a1", "o1", "grammar", "incorrect") is True
    assert academy_repo.record_attempt(a, "a1", "o2", "grammar", "correct") is True
    agg = academy_repo.list_attempts(a, "a1")
    assert agg["o1"] == {"correct": 1, "incorrect": 1}
    assert agg["o2"] == {"correct": 1, "incorrect": 0}


def test_rollup_counters_classifies_states():
    lv = load_level("a1")
    ids = [o.id for o in lv.objectives()]
    attempts = {
        ids[0]: {"correct": 0, "incorrect": 1},
        ids[1]: {"correct": 1, "incorrect": 0},
    }
    counters = academy_svc.rollup_counters(ids, {ids[0]}, attempts)
    assert counters["correct"] == 1  # ids[0] dominado
    assert counters["to_review"] == 1  # ids[1] con aciertos pero sin dominar
    assert counters["incorrect"] == 0


def test_endpoint_attempts_updates_detail(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/attempts",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "results": [{"skill": obj.skills[0], "result": "incorrect"}],
            },
        )
    assert r.status_code == 200
    assert r.json()["recorded"] == 1

    with TestClient(app) as client:
        detail = client.get("/api/academy/levels/a1", params={"user_id": a}).json()
    first = detail["objectives"][0]
    assert first["attempts"] == 1
    assert first["incorrect"] == 1
    assert first["status"] == "review"
    assert detail["progress"]["incorrect"] == 1


def test_endpoint_attempts_rejects_invalid_result(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/attempts",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "results": [{"skill": obj.skills[0], "result": "maybe"}],
            },
        )
    assert r.status_code == 422


def test_endpoint_attempts_do_not_grant_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    results = [{"skill": s, "result": "correct"} for s in obj.skills for _ in range(3)]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/attempts",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "results": results,
            },
        )
    assert r.status_code == 200
    assert r.json()["recorded"] == len(results)

    with TestClient(app) as client:
        detail = client.get("/api/academy/levels/a1", params={"user_id": a}).json()
        mastery = client.get("/api/academy/mastery", params={"user_id": a}).json()
    # Los intentos binarios solo alimentan contadores, no conceden dominio.
    assert detail["objectives"][0]["status"] == "review"
    assert mastery["mastery"] == []


def test_endpoint_objective_assessment_updates_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    checks = {c.id: c.correct_index for c in obj.checks}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": checks},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == 1.0
    assert body["correct"] == len(checks)
    # Una única evidencia perfecta aún no consolida dominio total.
    assert body["mastery"]["grammar"] == 0.8


def test_endpoint_lesson_complete(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/lessons/complete",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id},
        )
    assert r.status_code == 200
    assert r.json()["recorded"] is True

    with TestClient(app) as client:
        detail = client.get("/api/academy/levels/a1", params={"user_id": a}).json()
    # Terminar una lección no declara acierto ni cambia contadores.
    assert detail["objectives"][0]["attempts"] == 0
    assert detail["objectives"][0]["status"] == "available"


def test_endpoint_isolation_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    checks = {c.id: c.correct_index for c in obj.checks}
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": checks},
        )
        certs_b = client.get("/api/academy/certificates", params={"user_id": b}).json()
    assert academy_repo.list_objective_mastery(a, "a1") != {}
    assert academy_repo.list_objective_mastery(b, "a1") == {}  # B no hereda datos de A
    assert certs_b["certificates"] == []


def test_endpoint_assessment_rejects_locked_objective(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    locked = objs[2]  # el tercer objetivo está bloqueado por gating
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": locked.id, "answers": {}},
        )
    assert r.status_code == 404
    # No se escribe evidencia para un objetivo bloqueado.
    assert academy_repo.list_objective_mastery(a, "a1") == {}


def test_endpoint_attempts_reject_locked_objective(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    locked = objs[2]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/attempts",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": locked.id,
                "results": [{"skill": "grammar", "result": "correct"}],
            },
        )
    assert r.status_code == 404


def test_endpoint_lesson_complete_rejects_locked_objective(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    locked = objs[2]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/lessons/complete",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": locked.id},
        )
    assert r.status_code == 404

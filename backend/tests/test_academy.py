"""Tests de la Academy: currículum, mastery, progresión, adaptación y evaluación."""

import asyncio
import sqlite3

from fastapi.testclient import TestClient

from domain import academy as academy_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import (
    ASSESSABLE_SKILLS,
    CANONICAL_SKILLS,
    PERFORMANCE_SKILLS,
    load_all_levels,
    load_assessments,
    load_level,
    next_level_id,
    validate_level,
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


def test_every_objective_has_checks_for_its_assessable_skills():
    """Invariante curricular (todos los niveles disponibles): cada objetivo debe
    tener checks que cubran exactamente sus destrezas evaluables
    (grammar/vocabulary/reading/listening) y ninguno que pretenda evaluar
    destrezas de performance (speaking/writing/pronunciation), para las que aún
    no existe evidencia determinista. Las destrezas deben ser canónicas, con
    umbrales válidos y un mínimo de evidencias ≥ 1."""
    levels = load_all_levels()
    assert levels, "no hay niveles disponibles"
    for lv in levels:
        assert lv.modules, lv.level_id
        for o in lv.objectives():
            assert o.can_do.startswith("I can "), (lv.level_id, o.id)
            assert o.skills, (lv.level_id, o.id)
            assert set(o.skills) <= set(CANONICAL_SKILLS), (lv.level_id, o.id)
            assert o.minimum_attempts >= 1, (lv.level_id, o.id)
            assert all(0 < t <= 1 for t in o.thresholds.values()), (
                lv.level_id,
                o.id,
            )
            assert o.checks, f"{lv.level_id}: {o.id} no tiene checks"
            check_skills = {c.skill for c in o.checks}
            expected = set(o.skills) & set(ASSESSABLE_SKILLS)
            assert check_skills == expected, (
                f"{lv.level_id}: {o.id} esperaba checks {expected} "
                f"pero tiene {check_skills}"
            )
            assert not (check_skills & set(PERFORMANCE_SKILLS))


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


def test_next_objective_returns_first_unmastered():
    lv = load_level("a1")
    first = lv.objectives()[0].id
    assert academy_svc.next_objective(lv, set()) == first


def test_adaptive_next_prefers_weakest_skill():
    lv = load_level("a1")
    ids = [o.id for o in lv.objectives()]
    # Primero dominado; el resto desbloqueado secuencialmente: el siguiente es ids[1].
    assert academy_svc.adaptive_next(lv, {ids[0]}, {}) == ids[1]


def test_recommend_next_prefers_remediation_over_progression():
    lv = load_level("a1")
    objs = [o for o in lv.objectives() if o.assessable_skills()]
    target = objs[1]
    skill = target.assessable_skills()[0]
    oid, reason = academy_svc.recommend_next(lv, set(), {target.id: {skill: 0.4}})
    assert oid == target.id
    assert reason == "remediation"


def test_recommend_next_picks_weakest_remediation():
    lv = load_level("a1")
    objs = [o for o in lv.objectives() if o.assessable_skills()]
    weak1, weak2 = objs[1], objs[2]
    s1 = weak1.assessable_skills()[0]
    s2 = weak2.assessable_skills()[0]
    scores = {weak1.id: {s1: 0.5}, weak2.id: {s2: 0.3}}
    oid, reason = academy_svc.recommend_next(lv, set(), scores)
    assert oid == weak2.id  # 0.3 < 0.5
    assert reason == "remediation"


def test_recommend_next_progression_when_no_evidence():
    lv = load_level("a1")
    first = lv.objectives()[0].id
    oid, reason = academy_svc.recommend_next(lv, set(), {})
    assert oid == first
    assert reason == "next-in-path"


def test_recommend_next_level_complete():
    lv = load_level("a1")
    all_ids = {o.id for o in lv.objectives()}
    oid, reason = academy_svc.recommend_next(lv, all_ids, {})
    assert oid is None
    assert reason == "level-complete"


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


def test_level_completion_and_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    academy_repo.record_level_completion(a, "a1", "A1", 0.9)
    assert len(academy_repo.list_level_completions(a)) == 1
    assert academy_repo.list_level_completions(b) == []


def test_certificates_to_level_completions_migration(monkeypatch, tmp_path):
    """Migración academy_certificates → academy_level_completions: copia filas y
    elimina la tabla antigua (idempotente en reinstalación)."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: solo la tabla academy_certificates con una fila.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE academy_certificates ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, "
        "level_id TEXT NOT NULL, level TEXT NOT NULL, overall REAL NOT NULL, "
        "awarded_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO academy_certificates "
        "(id, user_id, level_id, level, overall, awarded_at) "
        "VALUES (1, 'u1', 'a1', 'A1', 0.9, '2026-08-25')"
    )
    conn.commit()
    conn.close()

    db.init_db()  # aplica la migración en la fase 2

    conn = sqlite3.connect(db.DB_PATH)
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    rows = conn.execute(
        "SELECT level, overall FROM academy_level_completions"
    ).fetchall()
    conn.close()

    assert "academy_certificates" not in tables
    assert rows == [("A1", 0.9)]


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


# --- Gating de matrícula y examen (integridad curricular) -----------------


def test_enroll_a1_always_allowed(monkeypatch, tmp_path):
    """El primer nivel (A1) no exige prerequisito y siempre se puede matricular."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/enroll", params={"user_id": a}, json={"level_id": "a1"}
        )
    assert r.status_code == 200
    assert r.json()["level"] == "A1"


def test_enroll_rejects_uncompleted_prerequisite(monkeypatch, tmp_path):
    """A2 exige A1 completado: 403 antes de completarlo, 200 después."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/enroll", params={"user_id": a}, json={"level_id": "a2"}
        )
        assert r.status_code == 403

        data = load_assessments()
        exam = data.exams["a1"]
        answers = {it.id: it.correct_index for it in exam.items}
        client.post(
            "/api/academy/exam/a1/submit",
            params={"user_id": a},
            json={"answers": answers},
        )

        r2 = client.post(
            "/api/academy/enroll", params={"user_id": a}, json={"level_id": "a2"}
        )
        assert r2.status_code == 200


def test_levels_expose_unlocked(monkeypatch, tmp_path):
    """El listado de niveles expone `unlocked`: A1 sí, A2 no (usuario nuevo)."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/levels", params={"user_id": a})
    levels = {lv["level_id"]: lv for lv in r.json()["levels"]}
    assert levels["a1"]["unlocked"] is True
    assert levels["a2"]["unlocked"] is False


def test_level_detail_rejects_locked_level(monkeypatch, tmp_path):
    """El detalle de un nivel bloqueado (prerequisito no completado) se oculta."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/levels/a2", params={"user_id": a})
        assert r.status_code == 403

        # A1 (primer nivel) siempre es accesible.
        r1 = client.get("/api/academy/levels/a1", params={"user_id": a})
        assert r1.status_code == 200


def test_level_detail_unknown_level_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/levels/b1", params={"user_id": a})
    assert r.status_code == 404


def test_exam_does_not_bypass_enrollment():
    """El examen no salta la progresión: comparte el helper de gating.

    `submit_exam` auto-matricula solo si `enrollment_unlocked` lo permite; por eso
    la regla pura debe rechazar cualquier nivel sin su prerequisito completado."""
    assert academy_svc.enrollment_unlocked("a1", set()) is True
    assert academy_svc.enrollment_unlocked("a2", set()) is False
    assert academy_svc.enrollment_unlocked("a2", {"a1"}) is True
    assert academy_svc.enrollment_unlocked("b1", {"a1"}) is False
    assert academy_svc.enrollment_unlocked("b1", {"a1", "a2"}) is True
    assert academy_svc.enrollment_unlocked("zz", set()) is False


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
        assert detail["objectives"][1]["status"] == "available"

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


def test_endpoint_exam_pass_records_completion(monkeypatch, tmp_path):
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

    completions = client.get(
        "/api/academy/level-completions", params={"user_id": a}
    ).json()
    assert completions["completions"][0]["level"] == "A1"


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


def test_endpoint_exam_fail_no_completion(monkeypatch, tmp_path):
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

    completions = client.get(
        "/api/academy/level-completions", params={"user_id": a}
    ).json()
    assert completions["completions"] == []


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


def test_endpoint_assessment_can_master_and_unlock_next(monkeypatch, tmp_path):
    """Evidencia repetida sobre un objetivo lo domina y desbloquea el siguiente.

    Antes de este cambio, speaking (sin check) impedía dominar ningún objetivo,
    así que el gating bloqueaba toda la progresión en cadena."""
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a1").objectives()[0]
    checks = {c.id: c.correct_index for c in obj.checks}
    with TestClient(app) as client:
        for _ in range(obj.minimum_attempts):
            r = client.post(
                "/api/academy/objective/assessment",
                params={"user_id": a},
                json={"level_id": "a1", "objective_id": obj.id, "answers": checks},
            )
            assert r.status_code == 200
        detail = client.get("/api/academy/levels/a1", params={"user_id": a}).json()
    assert detail["objectives"][0]["status"] == "mastered"
    assert detail["objectives"][1]["status"] == "available"


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
        completions_b = client.get(
            "/api/academy/level-completions", params={"user_id": b}
        ).json()
    assert academy_repo.list_objective_mastery(a, "a1") != {}
    assert academy_repo.list_objective_mastery(b, "a1") == {}  # B no hereda datos de A
    assert completions_b["completions"] == []


def test_endpoint_assessment_allows_any_objective_in_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": objs[2].id, "answers": {}},
        )
    assert r.status_code == 200


def test_endpoint_attempts_allows_any_objective_in_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/attempts",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": objs[2].id,
                "results": [{"skill": "grammar", "result": "correct"}],
            },
        )
    assert r.status_code == 200


def test_endpoint_lesson_complete_allows_any_objective_in_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    objs = load_level("a1").objectives()
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/lessons/complete",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": objs[2].id},
        )
    assert r.status_code == 200


def test_endpoint_assessment_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a2", "objective_id": obj.id, "answers": {}},
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


# --- Evidencia por ítem (reproducible y versionada) ----------------------


def test_evidence_record_and_list(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert academy_repo.record_evidence(
        a,
        level_id="a1",
        objective_id="o1",
        skill="grammar",
        item_id="item-1",
        item_type="mcq",
        difficulty=2,
        source="objective_assessment",
        result=1.0,
        curriculum_version="1.2.3",
        assessment_version="",
    ) is True
    rows = academy_repo.list_evidence(a)
    assert len(rows) == 1
    r = rows[0]
    assert r["skill"] == "grammar"
    assert r["item_id"] == "item-1"
    assert r["item_type"] == "mcq"
    assert r["difficulty"] == 2
    assert r["source"] == "objective_assessment"
    assert r["result"] == 1.0
    assert r["curriculum_version"] == "1.2.3"
    assert r["assessment_version"] == ""


def test_objective_assessment_records_evidence(monkeypatch, tmp_path):
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
    rows = academy_repo.list_evidence(a)
    assert rows, "no se registró evidencia para la evaluación del objetivo"
    assert all(row["source"] == "objective_assessment" for row in rows)
    assert all(row["curriculum_version"] == "1.2.3" for row in rows)
    assert all(row["result"] in {0.0, 1.0} for row in rows)


def test_exam_records_evidence_with_versions(monkeypatch, tmp_path):
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
    exam_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "exam"
    ]
    assert exam_rows, "no se registró evidencia del examen"
    assert all(row["assessment_version"] == "a1-final" for row in exam_rows)
    assert all(row["curriculum_version"] == "1.2.3" for row in exam_rows)


def test_evidence_isolation_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    assert academy_repo.record_evidence(
        a,
        level_id="a1",
        objective_id="o1",
        skill="grammar",
        item_id="item-1",
        result=1.0,
    ) is True
    assert academy_repo.list_evidence(a) != []
    assert academy_repo.list_evidence(b) == []


# --- Agregación de mastery por destreza (vista derivada) ------------------


def test_aggregate_skill_mastery_derives_from_objectives():
    lv = load_level("a1")
    objs = lv.objectives()[:2]
    skills0 = objs[0].assessable_skills()
    skills1 = objs[1].assessable_skills()
    shared = [s for s in skills0 if s in skills1]
    assert shared, "los dos primeros objetivos comparten una destreza evaluable"
    skill = shared[0]

    objective_scores = {
        objs[0].id: {s: 0.0 for s in skills0},
        objs[1].id: {s: 0.0 for s in skills1},
    }
    objective_scores[objs[0].id][skill] = 0.8
    objective_scores[objs[1].id][skill] = 0.4

    mastery = academy_svc.aggregate_skill_mastery(lv, objective_scores)
    assert mastery[skill] == 0.6


def test_aggregate_skill_mastery_empty_when_no_scores():
    lv = load_level("a1")
    assert academy_svc.aggregate_skill_mastery(lv, {}) == {}


def test_all_levels_pass_curriculum_invariants():
    for lv in load_all_levels():
        violations = validate_level(lv)
        assert violations == [], f"{lv.level_id}: {violations}"

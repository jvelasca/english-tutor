"""V3.90 (Plan diario): objetivo por unidades/tiempo, política repaso-antes-que-nuevo
y métricas honestas del día.

Fija el contrato del incremento:

- la migración añade el plan diario a `learning_goal` y la metadata
  (`kind`/`skill`/`minutes`) a `session_completions`, de forma aditiva e
  idempotente;
- `services/daily_plan.py` traduce el objetivo a minutos/unidades y agrega las
  métricas (puro y determinista);
- `session_plan` acota el día (`max_new`, `max_units`, `include_listening`) y, al
  recortar por la cola, **deja el material nuevo fuera antes que el repaso**;
- el plan sirve lo que FALTA para el objetivo y, cumplido, no sirve nada;
- `/api/academy/daily-plan` publica objetivo, progreso, métricas y pendientes.
"""
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import adaptive, daily_plan


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Migración ---------------------------------------------------------------


def test_migration_adds_daily_plan_columns(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(learning_goal)")}
    assert {
        "plan_mode",
        "target_units",
        "max_new",
        "include_listening",
        "include_speaking",
    } <= cols


def test_migration_adds_completion_metadata_columns(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = {
        row[1] for row in db._conn().execute("PRAGMA table_info(session_completions)")
    }
    assert {"kind", "skill", "minutes"} <= cols


def test_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # re-arranque: no debe fallar ni duplicar
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(learning_goal)")}
    assert "plan_mode" in cols


# --- Objetivo del día (puro) -------------------------------------------------


def test_default_mode_is_time_and_uses_minutes():
    assert daily_plan.day_minutes_target(30, "time", 4) == 30


def test_units_mode_translates_units_to_minutes():
    assert (
        daily_plan.day_minutes_target(30, "units", 4)
        == 4 * daily_plan.MINUTES_PER_UNIT
    )


def test_units_mode_without_units_falls_back_to_minutes():
    """Un modo sin cifra no puede fijar presupuesto: cae a `time` en vez de
    inventarse un número."""
    assert daily_plan.day_minutes_target(25, "units", 0) == 25


def test_mixed_mode_takes_the_larger_budget():
    """En `mixed` el día se cumple con LAS DOS cosas, así que el presupuesto tiene
    que cubrir la mayor."""
    assert daily_plan.day_minutes_target(10, "mixed", 3) == 30
    assert daily_plan.day_minutes_target(45, "mixed", 3) == 45


def test_units_target_is_zero_in_time_mode():
    assert daily_plan.day_units_target("time", 5) == 0
    assert daily_plan.day_units_target("units", 5) == 5
    assert daily_plan.day_units_target("mixed", 5) == 5


def test_unknown_plan_mode_is_read_as_time():
    assert daily_plan.normalize_plan_mode("banana") == "time"


def test_targets_are_clamped_to_schema_bounds():
    assert daily_plan.clamp_minutes_per_day(1000) == daily_plan.MINUTES_MAX
    assert daily_plan.clamp_minutes_per_day(0) == daily_plan.MINUTES_MIN
    assert daily_plan.clamp_target_units(99) == daily_plan.TARGET_UNITS_MAX
    assert daily_plan.clamp_max_new(99) == daily_plan.MAX_NEW_MAX


def test_remaining_minutes_never_goes_negative():
    assert daily_plan.remaining_minutes(30, 10) == 20
    assert daily_plan.remaining_minutes(30, 30) == 0
    assert daily_plan.remaining_minutes(30, 45) == 0


def test_remaining_units_is_none_without_units_goal():
    assert daily_plan.remaining_units(0, 3) is None
    assert daily_plan.remaining_units(4, 1) == 3
    assert daily_plan.remaining_units(4, 9) == 0


# --- Progreso del objetivo (puro) --------------------------------------------


def test_progress_time_only_uses_minutes():
    p = daily_plan.goal_progress(
        minutes_target=30, minutes_done=15, units_target=0, units_done=0
    )
    assert p["percent"] == 0.5
    assert p["units_ratio"] is None
    assert p["done"] is False


def test_progress_mixed_is_the_weakest_target():
    """Con dos objetivos declarados, la barra no puede ir más rápido que el más
    atrasado (si no, diría «cumplido» con la mitad del día hecho)."""
    p = daily_plan.goal_progress(
        minutes_target=30, minutes_done=30, units_target=4, units_done=1
    )
    assert p["minutes_ratio"] == 1.0
    assert p["units_ratio"] == 0.25
    assert p["percent"] == 0.25
    assert p["done"] is False


def test_progress_done_requires_every_declared_target():
    p = daily_plan.goal_progress(
        minutes_target=30, minutes_done=30, units_target=4, units_done=4
    )
    assert p["percent"] == 1.0
    assert p["done"] is True


def test_progress_without_any_target_is_zero_not_one():
    """Sin objetivo declarado no se puede decir «hecho»: un 0 declarado, no un
    falso cumplido."""
    p = daily_plan.goal_progress(
        minutes_target=0, minutes_done=10, units_target=0, units_done=2
    )
    assert p["percent"] == 0.0
    assert p["done"] is False


# --- Métricas del día (puro) -------------------------------------------------


def test_metrics_separate_reviews_from_new_and_declare_unknown():
    completions = [
        {"step_key": "review:grammar", "kind": "review", "skill": "grammar",
         "minutes": 6},
        {"step_key": "listening:gist", "kind": "listening", "skill": "listening",
         "minutes": 4},
        {"step_key": "new:a1:o1", "kind": "new", "skill": "vocabulary",
         "minutes": 5},
        {"step_key": "weakness:grammar:o2", "kind": "weakness", "skill": "grammar",
         "minutes": 3},
        {"step_key": "easy_wins:reading", "kind": "easy_wins", "skill": "reading",
         "minutes": 2},
        # Fila anterior a V3.90: cuenta como unidad pero NO suma minutos.
        {"step_key": "review:reading", "kind": "", "skill": "", "minutes": 0},
    ]
    m = daily_plan.day_metrics(completions, [], [], "2026-09-29")
    assert m["units"] == 6
    assert m["unknown_units"] == 1
    assert m["minutes"] == 20
    assert m["reviews"] == 2
    assert m["new"] == 1
    assert m["listening"] == 1
    assert m["practice"] == 2
    assert m["accuracy"] is None


def test_metrics_count_speaking_units_by_skill():
    completions = [
        {"step_key": "s1", "kind": "weakness", "skill": "speaking", "minutes": 7},
        {"step_key": "s2", "kind": "new", "skill": "speaking", "minutes": 5},
        {"step_key": "s3", "kind": "new", "skill": "grammar", "minutes": 5},
    ]
    m = daily_plan.day_metrics(completions, [], [], "2026-09-29")
    assert m["speaking"] == 2


def test_metrics_accuracy_pools_evidence_and_listening_of_the_day():
    evidence = [
        {"result": 1.0, "created_at": "2026-09-29T09:00:00"},
        {"result": 0.0, "created_at": "2026-09-29T09:05:00"},
        # Otro día: no participa.
        {"result": 0.0, "created_at": "2026-09-28T09:05:00"},
    ]
    listening = [
        {"correct": 1, "created_at": "2026-09-29T10:00:00"},
        {"correct": 0, "created_at": "2026-09-28T10:00:00"},
    ]
    m = daily_plan.day_metrics([], evidence, listening, "2026-09-29")
    assert m["listening_attempts"] == 1
    assert m["listening_accuracy"] == 1.0
    # 3 resultados de hoy: 1.0 + 0.0 + 1.0
    assert m["accuracy"] == 0.667


def test_review_pending_declares_the_origin():
    p = daily_plan.review_pending(4, 3)
    assert p == {"fsrs": 4, "listening": 3, "total": 7}


# --- Política del Session Engine (puro) -------------------------------------


def _profile() -> list[dict]:
    return [
        {"skill": "grammar", "score": 0.4, "confidence": 0.5,
         "evidence_count": 3, "review_due": True, "stability": 0.2,
         "last_evidence": "2026-09-20T10:00:00"},
    ]


def _plan(**kwargs):
    defaults = {
        "profile": _profile(),
        "remediation": [{"skill": "grammar", "objective_ids": ["o1"]}],
        "next_objective_id": "o2",
        "listening_weak": ["gist"],
        "budget_minutes": 30,
    }
    defaults.update(kwargs)
    return adaptive.session_plan(**defaults)


def test_max_new_zero_leaves_a_pure_review_day():
    steps = _plan(max_new=0)
    kinds = [s["kind"] for s in steps]
    assert "new" not in kinds
    assert "review" in kinds


def test_max_new_above_one_cannot_add_more_new_material():
    """El motor solo conoce UN siguiente objetivo del currículo, así que `max_new`
    > 1 no añade más material nuevo: la subida es efectiva a 1 hasta que la
    progresión sirva más de un objetivo por día. Se fija aquí en vez de prometer
    en la documentación algo que el motor no hace."""
    steps = _plan(max_new=3)
    assert len(adaptive.steps_of(steps, "new")) == 1


def test_include_listening_false_removes_the_category():
    steps = _plan(include_listening=False)
    assert adaptive.steps_of(steps, "listening") == []


def test_max_units_caps_the_plan_by_the_tail():
    """Recortar por la cola ES «repaso antes que nuevo»: el plan ya viene en orden
    pedagógico, así que lo que se cae es lo menos prioritario."""
    full = _plan()
    assert len(full) > 2
    capped = _plan(max_units=2)
    assert len(capped) == 2
    assert [s["step_key"] for s in capped] == [
        s["step_key"] for s in full[:2]
    ]


def test_review_survives_the_unit_cap_before_new_does():
    """Con una sola unidad de presupuesto, el día se queda con el repaso."""
    capped = _plan(max_units=1)
    assert len(capped) == 1
    assert capped[0]["kind"] == "review"


def test_minutes_always_sum_the_budget():
    steps = _plan(budget_minutes=25)
    assert sum(s["minutes"] for s in steps) == 25


def test_include_speaking_false_drops_speaking_weakness_steps():
    """La casilla no puede mentir: si el día excluye Speaking, el plan no sirve
    pasos de Speaking aunque sean la debilidad pendiente."""
    steps = _plan(
        remediation=[
            {"skill": "speaking", "objective_ids": ["o1"]},
            {"skill": "grammar", "objective_ids": ["o2"]},
        ],
        include_speaking=False,
    )
    weakness = adaptive.steps_of(steps, "weakness")
    assert [s["skill"] for s in weakness] == ["grammar"]


def test_include_speaking_false_drops_the_speaking_quick_win():
    strong_speaking = [
        {"skill": "speaking", "score": 0.9, "confidence": 0.9,
         "evidence_count": 4, "review_due": False, "stability": 0.8,
         "last_evidence": "2026-09-28T10:00:00"},
    ]
    steps = _plan(
        profile=strong_speaking,
        remediation=[],
        next_objective_id=None,
        listening_weak=[],
        include_speaking=False,
    )
    assert adaptive.steps_of(steps, "easy_wins") == []


def test_include_speaking_true_keeps_the_speaking_steps():
    """Contra-prueba: con la preferencia activa nada cambia."""
    steps = _plan(remediation=[{"skill": "speaking", "objective_ids": ["o1"]}])
    assert [s["skill"] for s in adaptive.steps_of(steps, "weakness")] == [
        "speaking"
    ]


# --- Repositorio -------------------------------------------------------------


def test_upsert_goal_persists_the_daily_plan(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    assert (
        academy_repo.upsert_goal(
            a,
            "general",
            20,
            5,
            "B1",
            plan_mode="mixed",
            target_units=3,
            max_new=0,
            include_listening=False,
            include_speaking=True,
        )
        is True
    )
    row = academy_repo.get_goal(a)
    assert row["plan_mode"] == "mixed"
    assert row["target_units"] == 3
    assert row["max_new"] == 0
    assert row["include_listening"] == 0
    assert row["include_speaking"] == 1


def test_mark_session_step_freezes_metadata(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    assert academy_repo.mark_session_step(
        a, "review:grammar", "2026-09-29", kind="review", skill="grammar", minutes=6
    )
    rows = academy_repo.list_session_completions(a, "2026-09-29")
    assert rows == [
        {
            "step_key": "review:grammar",
            "kind": "review",
            "skill": "grammar",
            "minutes": 6,
            "completed_at": rows[0]["completed_at"],
        }
    ]


def test_remark_without_metadata_does_not_erase_it(monkeypatch, tmp_path):
    """«Desconocido» no debe pisar «conocido»: un re-marcado idempotente (el paso
    ya no está en el plan) conserva lo congelado."""
    a = _setup(monkeypatch, tmp_path)
    academy_repo.mark_session_step(
        a, "review:grammar", "2026-09-29", kind="review", skill="grammar", minutes=6
    )
    academy_repo.mark_session_step(a, "review:grammar", "2026-09-29")
    row = academy_repo.list_session_completions(a, "2026-09-29")[0]
    assert row["kind"] == "review"
    assert row["skill"] == "grammar"
    assert row["minutes"] == 6


def test_list_session_steps_still_returns_keys(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    academy_repo.mark_session_step(a, "review:grammar", "2026-09-29")
    assert academy_repo.list_session_steps(a, "2026-09-29") == {"review:grammar"}


# --- API ---------------------------------------------------------------------


def test_endpoint_goal_roundtrips_the_daily_plan(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        put = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 20,
                "days_per_week": 5,
                "target_level": "B1",
                "plan_mode": "mixed",
                "target_units": 3,
                "max_new": 0,
                "include_listening": False,
                "include_speaking": True,
            },
        )
        assert put.status_code == 200
        got = client.get("/api/academy/goal", params={"user_id": a}).json()
    assert got["plan_mode"] == "mixed"
    assert got["target_units"] == 3
    assert got["max_new"] == 0
    assert got["include_listening"] is False


def test_endpoint_goal_put_of_the_old_contract_still_works(monkeypatch, tmp_path):
    """El cliente anterior (4 claves) sigue siendo válido: los defaults cubren el
    plan diario."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        put = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "work",
                "minutes_per_day": 25,
                "days_per_week": 4,
                "target_level": "B2",
            },
        )
    assert put.status_code == 200
    assert put.json()["plan_mode"] == "time"
    assert put.json()["max_new"] == 1


def test_endpoint_goal_rejects_out_of_range_plan_fields(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 15,
                "days_per_week": 5,
                "target_level": "B1",
                "target_units": 99,
            },
        )
    assert r.status_code == 422


def test_endpoint_daily_plan_shape(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/daily-plan", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["plan_mode"] == "time"
    assert body["minutes_target"] == 15
    assert body["units_target"] == 0
    assert body["units_remaining"] is None
    assert body["minutes_remaining"] == 15
    assert body["progress"]["minutes_done"] == 0
    assert body["metrics"]["units"] == 0
    assert body["pending"] == {"fsrs": 0, "listening": 0, "total": 0}
    # La sesión del plan es la del Session Engine: no vacía y sumando lo que falta.
    assert body["session"]["items"], "el plan de un usuario nuevo no está vacío"
    assert body["session"]["total_minutes"] == body["minutes_remaining"]


def test_endpoint_daily_plan_shares_the_plan_with_session(monkeypatch, tmp_path):
    """La barra de progreso y la lista de pasos no pueden divergir: mismo motor."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
        session = client.get("/api/academy/session", params={"user_id": a}).json()
    assert [i["step_key"] for i in plan["session"]["items"]] == [
        i["step_key"] for i in session["items"]
    ]


def test_endpoint_completing_a_unit_advances_the_goal(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
        first = plan["session"]["items"][0]
        after = client.post(
            "/api/academy/session/complete",
            params={"user_id": a},
            json={"step_key": first["step_key"]},
        ).json()
        metrics = client.get(
            "/api/academy/daily-plan", params={"user_id": a}
        ).json()["metrics"]
    assert first["step_key"] not in {i["step_key"] for i in after["items"]}
    assert metrics["units"] == 1
    assert metrics["minutes"] == first["minutes"]
    assert metrics["by_kind"][first["kind"]] == 1


def test_endpoint_metrics_keep_the_minutes_frozen_at_completion(monkeypatch, tmp_path):
    """Los minutos del día son los que el motor asignó al completar, no los que el
    plan reparte después (el plan se recalcula y desaparecerían)."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 40,
                "days_per_week": 5,
                "target_level": "B1",
            },
        )
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
        first = plan["session"]["items"][0]
        client.post(
            "/api/academy/session/complete",
            params={"user_id": a},
            json={"step_key": first["step_key"]},
        )
        metrics = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    assert metrics["metrics"]["minutes"] == first["minutes"]
    # El plan vuelve a repartir solo lo que falta.
    assert metrics["session"]["total_minutes"] == 40 - first["minutes"]


def test_endpoint_units_mode_stops_serving_when_the_goal_is_met(
    monkeypatch, tmp_path
):
    """En modo `units`, cumplir las unidades cumple el día: no se sirve más plan."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 15,
                "days_per_week": 5,
                "target_level": "B1",
                "plan_mode": "units",
                "target_units": 1,
            },
        )
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
        assert plan["units_target"] == 1
        assert plan["minutes_target"] == daily_plan.MINUTES_PER_UNIT
        assert plan["session"]["items"], "el plan sirve la unidad pendiente"
        first = plan["session"]["items"][0]
        client.post(
            "/api/academy/session/complete",
            params={"user_id": a},
            json={"step_key": first["step_key"]},
        )
        after = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    assert after["progress"]["done"] is True
    assert after["session"]["items"] == []
    assert after["units_remaining"] == 0


def test_endpoint_max_new_zero_is_a_review_only_day(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 20,
                "days_per_week": 5,
                "target_level": "B1",
                "max_new": 0,
            },
        )
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    kinds = {i["kind"] for i in plan["session"]["items"]}
    assert "new" not in kinds


def test_endpoint_include_listening_false_removes_listening_steps(
    monkeypatch, tmp_path
):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 20,
                "days_per_week": 5,
                "target_level": "B1",
                "include_listening": False,
            },
        )
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    assert plan["include_listening"] is False
    assert "listening" not in {i["kind"] for i in plan["session"]["items"]}


def test_endpoint_include_speaking_false_is_published_and_applied(
    monkeypatch, tmp_path
):
    """La preferencia se guarda Y se ve en el plan (no es una casilla decorativa)."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 20,
                "days_per_week": 5,
                "target_level": "B1",
                "include_speaking": False,
            },
        )
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    assert plan["include_speaking"] is False
    assert all(
        i["skill"] != "speaking" for i in plan["session"]["items"]
    )


def test_endpoint_daily_plan_ignores_reviews_that_are_not_due_yet(
    monkeypatch, tmp_path
):
    """Un fallo de Listening de V3.89 se encola con su próxima fecha; si aún no
    vence, NO se cuenta como repaso pendiente del día (el intervalo es parte de la
    política, no un detalle de presentación)."""
    from services.listening import QUESTION_BANK

    a = _setup(monkeypatch, tmp_path)
    q = next(q for q in QUESTION_BANK if q["skill"] not in ("dictation", "shadowing"))
    wrong = (q["answer_index"] + 1) % len(q["options"])
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": a},
            json={
                "question_id": q["id"],
                "answer_index": wrong,
                "skill": q["skill"],
                "level": q.get("level", "A2"),
                "task_type": q.get("task_type", "mcq"),
            },
        )
        queued = client.get(
            "/api/listening/review-queue", params={"user_id": a}
        ).json()
        plan = client.get("/api/academy/daily-plan", params={"user_id": a}).json()
    assert queued["pending"] == 1, "el fallo queda en la cola"
    assert plan["pending"]["listening"] == 0, "pero todavía no vence"
    assert plan["pending"]["total"] == plan["pending"]["fsrs"]

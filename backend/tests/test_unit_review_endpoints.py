"""Tests de dominio/endpoints del Review/SRS por unidad (V3.16, Fases B–C).

Invariantes cubiertos:
- `sync_fsrs_cards` siembra cartas `objective` SOLO para objetivos de unidades
  completadas del nivel actual y no pisa cartas con `reps > 0`.
- El plan de unidades lista completadas o con plan activo (intentos) y reporta
  `due_count` con ventanas due_now/failed.
- El micro-review se puntúa en servidor contra los checks oficiales; NUNCA envía
  `correct_index` antes de responder y NO crea evidencia de mastery/currículo
  (D5). Una ventana `passed` no se puede repasar; `failed` sí (reintento).
- Aislamiento por usuario (premisa 13): los intentos de A nunca son visibles
  para B.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import load_level

UNIT_ID = "a1-m04-u01"
LEVEL_ID = "a1"


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _unit():
    lv = load_level(LEVEL_ID)
    return next(
        u
        for m in lv.modules
        if m.id == "a1-m04"
        for u in m.units
        if u.id == UNIT_ID
    )


def _correct_index_map(unit) -> dict[str, int]:
    return {
        c.id: c.correct_index
        for les in unit.lessons
        for o in les.objectives
        for c in o.checks
    }


def _master_unit(uid: str, unit, level_id: str = LEVEL_ID) -> None:
    """Domina todas las destrezas evaluables de todos los objetivos de la unidad."""
    for les in unit.lessons:
        for obj in les.objectives:
            for skill in obj.assessable_skills():
                state = None
                for _ in range(int(obj.minimum_attempts)):
                    state = academy_svc.next_mastery_state(
                        state, 1.0, obj.threshold(skill)
                    )
                academy_repo.apply_objective_evidence(
                    uid, level_id, obj.id, skill, state
                )


def _backdate_unit(uid: str, unit, days: int = 45, level_id: str = LEVEL_ID) -> None:
    """Retrasa la evidencia de la unidad a `days` atrás Y congela su ancla allí.

    Simula que la unidad se completó hace `days`: las filas de mastery quedan
    con `updated_at` antiguo y, si aún no hay ancla persistida (I2/V3.18), se
    inserta la fila de `unit_review_anchors` con ese momento (equivalente a que
    el dominio hubiera detectado la completitud entonces)."""
    iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    oids = [o.id for les in unit.lessons for o in les.objectives]
    conn = db._conn()
    try:
        with conn:
            for oid in oids:
                conn.execute(
                    "UPDATE academy_objective_mastery "
                    "SET updated_at = ?, last_seen_at = ? "
                    "WHERE user_id = ? AND level_id = ? AND objective_id = ?",
                    (iso, iso, uid, level_id, oid),
                )
            # Misma transacción: inserta el ancla congelada si aún no existe.
            existing = conn.execute(
                "SELECT anchor FROM unit_review_anchors "
                "WHERE user_id = ? AND level_id = ? AND unit_id = ?",
                (uid, level_id, unit.id),
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT OR IGNORE INTO unit_review_anchors "
                    "(user_id, level_id, unit_id, anchor, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (uid, level_id, unit.id, iso, iso, iso),
                )
    finally:
        conn.close()


def _degrade_objective(uid: str, objective_id: str, skills: list[str]) -> None:
    """Baja el mastery de un objetivo por debajo de su umbral (simula decay)."""
    iso = datetime.now(timezone.utc).isoformat()
    for skill in skills:
        state = {
            "score": 0.1,
            "recent_score": 0.1,
            "confidence": 0.0,
            "streak": 0,
            "attempts": 5,
            "last_seen_at": iso,
        }
        academy_repo.apply_objective_evidence(
            uid, LEVEL_ID, objective_id, skill, state
        )


def _objective_cards(uid: str) -> list[dict]:
    return [
        c for c in academy_repo.list_fsrs_cards(uid)
        if c["target_type"] == "objective"
    ]


def _flat_units(plan: dict) -> list[dict]:
    """Unidades del plan agregado (O3/V3.18) aplanadas por nivel."""
    return [
        u for lv in plan.get("levels") or [] for u in lv.get("units") or []
    ]


# --- Plan de unidades + siembra FSRS objective ------------------------------


def test_unit_plan_requires_completion_and_seeds_only_then(monkeypatch, tmp_path):
    """Criterio 2: `sync_fsrs_cards` siembra cartas `objective` solo cuando la
    unidad está completa; el plan lista la unidad solo al completarse."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    client = TestClient(app)

    # Sin unidades completadas: plan agregado vacío y cero cartas objective.
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}")
    assert plan.status_code == 200
    assert plan.json()["levels"] == []
    assert _objective_cards(uid) == []

    # Completamos la unidad y "envejecemos" evidencia + ancla 45 días ANTES de
    # que el plan la observe por primera vez (I2): la primera detección de
    # completitud congela el ancla en ese momento.
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}")
    assert plan.status_code == 200
    body = plan.json()
    assert body["due_count"] == 1
    units = _flat_units(body)
    assert len(units) == 1
    assert units[0]["unit_id"] == UNIT_ID
    assert units[0]["completed"] is True
    windows = units[0]["windows"]
    assert windows[0]["state"] == "due_now"
    assert windows[1]["state"] == "due_now"
    assert windows[2]["state"] == "upcoming"

    # El plan no siembra cartas por sí solo; solo /fsrs/sync (y solo al vencer).
    assert _objective_cards(uid) == []
    sync = client.post(f"/api/academy/fsrs/sync?user_id={uid}")
    assert sync.status_code == 200, sync.text
    assert sync.json()["by_type"].get("objective", 0) >= 2

    cards = _objective_cards(uid)
    oids = {o.id for les in unit.lessons for o in les.objectives}
    assert {c["target_id"] for c in cards} == oids
    # La siembra ya implica la primera revisión implícita (reps >= 1).
    assert all(c["reps"] >= 1 for c in cards)
    assert all(c["why"] == "unit-window-7" for c in cards)

    # Idempotencia: una segunda sync NO pisa cartas con reps > 0 (solo why/label).
    before = {
        c["target_id"]: (c["due_at"], c["stability"], c["reps"])
        for c in cards
    }
    sync2 = client.post(f"/api/academy/fsrs/sync?user_id={uid}")
    assert sync2.status_code == 200
    after = {
        c["target_id"]: (c["due_at"], c["stability"], c["reps"])
        for c in _objective_cards(uid)
    }
    assert after == before

    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}")
    assert plan.json()["due_count"] == 1
    windows = _flat_units(plan.json())[0]["windows"]
    assert windows[0]["state"] == "due_now"
    assert windows[1]["state"] == "due_now"
    assert windows[2]["state"] == "upcoming"


def test_sync_does_not_seed_objective_cards_while_windows_upcoming(
    monkeypatch, tmp_path
):
    """M4 (V3.18): con las ventanas aún `upcoming`, una sync NO crea cartas
    `objective` nuevas; nacen cuando su ventana vence o desde el micro-review."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    client = TestClient(app)

    # Unidad recién completada: ancla hoy, ventanas todas `upcoming`.
    _master_unit(uid, unit)
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}")
    body = plan.json()
    assert body["due_count"] == 0
    units = _flat_units(body)
    assert len(units) == 1
    assert units[0]["completed"] is True
    assert all(w["state"] == "upcoming" for w in units[0]["windows"])
    assert _objective_cards(uid) == []

    # Sync en ventana upcoming: NO se crea ninguna carta objective.
    sync = client.post(f"/api/academy/fsrs/sync?user_id={uid}")
    assert sync.status_code == 200
    assert sync.json()["by_type"].get("objective", 0) == 0
    assert _objective_cards(uid) == []


def test_unit_plan_404_on_unknown_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    r = client.get(
        f"/api/academy/review/unit-plan?user_id={uid}&level_id=zz"
    )
    assert r.status_code == 404


# --- Micro-review: sesión, puntuación y gating ------------------------------


def test_micro_review_flow_no_correct_index_and_no_evidence(monkeypatch, tmp_path):
    """Criterios 4 y 5: sin `correct_index` antes de responder, puntúa el
    servidor, persiste el intento y NO crea evidencia de mastery/currículo."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    before_evidence = academy_repo.list_evidence(uid, LEVEL_ID)

    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert session.status_code == 200, session.text
    body = session.json()
    assert body["unit_id"] == UNIT_ID
    assert body["window_days"] == 7
    items = body["items"]
    assert 0 < len(items) <= 8
    for item in items:
        assert "correct_index" not in item
        assert set(item) == {
            "item_id",
            "objective_id",
            "objective_title",
            "skill",
            "prompt",
            "options",
        }
    assert len({i["item_id"] for i in items}) == len(items)

    answers = {i["item_id"]: correct[i["item_id"]] for i in items}
    result = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": answers},
    )
    assert result.status_code == 200, result.text
    out = result.json()
    assert out["passed"] is True
    assert out["correct"] == len(items)
    assert out["total"] == len(items)
    assert out["plan"]["windows"][0]["state"] == "passed"
    assert len(out["per_objective"]) == 2
    assert all(p["correct"] == p["total"] for p in out["per_objective"])
    assert all(p["grade"] >= 3 for p in out["per_objective"])
    assert all(p["next_due_at"] for p in out["per_objective"])

    # D5: cero filas de evidencia del currículo nuevas.
    after_evidence = academy_repo.list_evidence(uid, LEVEL_ID)
    assert len(after_evidence) == len(before_evidence) == 0

    # Intento persistido con per_objective + failed_items (Fase B).
    attempts = academy_repo.list_unit_review_attempts(uid, LEVEL_ID, UNIT_ID, 7)
    assert len(attempts) == 1
    assert attempts[0]["passed"] is True
    assert attempts[0]["failed_items"] == []
    assert attempts[0]["per_objective"] and all(
        "objective_id" in b and "correct" in b and "total" in b
        for b in attempts[0]["per_objective"]
    )

    # Cartas FSRS objective reprogramadas (reps >= 1) tras el micro-review.
    cards = _objective_cards(uid)
    assert len(cards) == 2
    assert all(c["reps"] >= 1 for c in cards)


def test_micro_review_failed_then_retry_and_window_gating(monkeypatch, tmp_path):
    """D6 + gating: fallar deja la ventana `failed` (reintentable); una ventana
    `passed` o `upcoming` no se puede repasar (400)."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    # Ventana 90 aún upcoming → no repasable.
    upcoming = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=90"
    )
    assert upcoming.status_code == 400

    # Intentamos la ventana 30 y fallamos deliberadamente.
    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=30"
    )
    assert session.status_code == 200
    items = session.json()["items"]
    wrong = {
        i["item_id"]: (correct[i["item_id"]] + 1) % len(i["options"])
        for i in items
    }
    failed = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 30, "answers": wrong},
    )
    assert failed.status_code == 200
    assert failed.json()["passed"] is False
    assert failed.json()["plan"]["windows"][1]["state"] == "failed"

    attempts = academy_repo.list_unit_review_attempts(uid, LEVEL_ID, UNIT_ID, 30)
    assert len(attempts) == 1
    assert set(attempts[0]["failed_items"]) == {i["item_id"] for i in items}

    # Con la 30 aún FALLIDA (sin intento superado), la 7 (due_now, sin intento
    # propio) sigue siendo repasable: un fallo no cierra por cadena (O1).
    still_due = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert still_due.status_code == 200

    # Reintento de la MISMA ventana (failed) con respuestas correctas → pasa.
    good_answers = {
        i["item_id"]: correct[i["item_id"]] for i in items
    }
    retry = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 30, "answers": good_answers},
    )
    assert retry.status_code == 200
    assert retry.json()["passed"] is True
    assert retry.json()["plan"]["windows"][1]["state"] == "passed"

    # Una ventana ya pasada no se vuelve a repasar.
    passed_again = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=30"
    )
    assert passed_again.status_code == 400

    # Cadena O1 (V3.18): al superar la 30 TARDE (hoy, con la 7 ya vencida hace
    # 45 días), la 7 sin intento propio queda `passed` por cadena — el repaso
    # tardío de la 30 demuestra retención más allá del hito de la 7 → 400.
    cascade_closed = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert cascade_closed.status_code == 400


def test_micro_review_audit_keeps_index_zero(monkeypatch, tmp_path):
    """Regresión auditoría externa v3.16 (I1): elegir la opción A (índice 0)
    no debe serializarse como `selected_index = -1` en el audit del POST."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    client = TestClient(app)

    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert session.status_code == 200
    items = session.json()["items"]
    assert items

    # Respondemos TODOS los ítems con la opción A (índice 0), acierte o no.
    answers = {i["item_id"]: 0 for i in items}
    result = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": answers},
    )
    assert result.status_code == 200
    out = result.json()
    assert len(out["items"]) == len(items)
    for audit in out["items"]:
        assert audit["selected_index"] == 0, audit["item_id"]


def test_micro_review_rejects_answers_outside_sample_or_index_range(
    monkeypatch, tmp_path
):
    """M2 (auditoría v3.16): el POST valida que las claves de `answers` ⊆ ids
    de la muestra y que cada índice elegido esté en rango → 400."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert session.status_code == 200
    items = session.json()["items"]
    answers = {i["item_id"]: correct[i["item_id"]] for i in items}

    # Clave ajena a la muestra (stale/forjada) → 400 sin persistir nada.
    forged = dict(answers)
    forged["ghost-item"] = 0
    bad = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": forged},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "unit_review.invalid_answers"

    # Índice fuera de rango (>= nº de opciones) → 400.
    first = items[0]
    out_of_range = dict(answers)
    out_of_range[first["item_id"]] = len(first["options"])  # inválido
    bad2 = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": out_of_range},
    )
    assert bad2.status_code == 400
    assert bad2.json()["detail"] == "unit_review.invalid_answers"

    # Nada se persistió y la ventana sigue repasable.
    assert academy_repo.list_unit_review_attempts(uid, LEVEL_ID, UNIT_ID, 7) == []
    still = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert still.status_code == 200


def test_micro_review_partial_retry_get_equals_post(monkeypatch, tmp_path):
    """O2 (auditoría v3.16): reintento parcial GET==POST — tras fallar una
    parte, la muestra del reintento es idéntica y determinista entre llamadas
    GET y prioriza los ítems fallados; con ella el POST acierta y pasa."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert session.status_code == 200
    first_items = session.json()["items"]
    first_ids = [i["item_id"] for i in first_items]
    assert len(first_ids) >= 3

    # Fallamos deliberadamente los dos primeros ítems; el resto correcto.
    failed_ids = first_ids[:2]
    answers = {i["item_id"]: correct[i["item_id"]] for i in first_items}
    for iid in failed_ids:
        opt_count = len(next(i for i in first_items if i["item_id"] == iid)["options"])
        answers[iid] = (answers[iid] + 1) % opt_count
    partial = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": answers},
    )
    assert partial.status_code == 200
    out = partial.json()
    assert out["passed"] is False
    failed_in_audit = [
        a["item_id"] for a in out["items"] if a["correct"] is False
    ]
    assert sorted(failed_in_audit) == sorted(failed_ids)

    # Reintento parcial por GET: misma muestra determinista y fallidos primero.
    retry_a = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    retry_b = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert retry_a.status_code == 200 and retry_b.status_code == 200
    items_a = retry_a.json()["items"]
    items_b = retry_b.json()["items"]
    assert items_a == items_b  # GET es idéntico entre llamadas
    retry_ids = [i["item_id"] for i in items_a]
    assert set(retry_ids[: len(failed_ids)]) == set(failed_ids)

    # El POST sobre ESA muestra (GET==POST) acierta y pasa la ventana.
    good = {i["item_id"]: correct[i["item_id"]] for i in items_a}
    passed = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": good},
    )
    assert passed.status_code == 200
    assert passed.json()["passed"] is True
    assert passed.json()["plan"]["windows"][0]["state"] == "passed"


def test_micro_review_404_unit_not_in_level_and_bad_window(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    missing = client.get(
        f"/api/academy/review/unit/no-such-unit/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert missing.status_code == 404
    bad = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=12"
    )
    assert bad.status_code == 400


def test_unit_plan_keeps_active_unit_after_mastery_decay(monkeypatch, tmp_path):
    """Una unidad con intentos sigue en el plan aunque deje de estar completa."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    # Fallamos la ventana 7 a propósito (queda un intento activo).
    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    items = session.json()["items"]
    wrong = {
        i["item_id"]: (correct[i["item_id"]] + 1) % len(i["options"])
        for i in items
    }
    assert (
        client.post(
            f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
            json={"window_days": 7, "answers": wrong},
        ).status_code
        == 200
    )

    # El dominio decae: la unidad deja de estar completa.
    obj2 = next(
        o for les in unit.lessons for o in les.objectives
        if o.id.endswith("o02")
    )
    _degrade_objective(uid, obj2.id, obj2.assessable_skills())

    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}").json()
    units = _flat_units(plan)
    assert units  # la unidad sigue, gracias al intento activo
    entry = units[0]
    assert entry["unit_id"] == UNIT_ID
    assert entry["completed"] is False
    assert entry["windows"][0]["state"] == "failed"


def test_unit_review_isolation_between_users(monkeypatch, tmp_path):
    """Premisa 13: los intentos y el plan de A no contaminan a B."""
    uid_a = _setup(monkeypatch, tmp_path)
    uid_b = users_repo.create_user("B")["id"]
    academy_repo.enroll(uid_a, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid_a, unit)
    _backdate_unit(uid_a, unit)
    correct = _correct_index_map(unit)
    client = TestClient(app)

    session = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid_a}&window_days=7"
    )
    answers = {
        i["item_id"]: correct[i["item_id"]] for i in session.json()["items"]
    }
    assert (
        client.post(
            f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid_a}",
            json={"window_days": 7, "answers": answers},
        ).status_code
        == 200
    )

    # B no tiene intentos y su plan no incluye la unidad de A.
    assert academy_repo.list_unit_review_attempts(uid_b, LEVEL_ID) == []
    plan_b = client.get(f"/api/academy/review/unit-plan?user_id={uid_b}").json()
    assert _flat_units(plan_b) == []
    assert plan_b["due_count"] == 0


def test_unit_plan_anchor_frozen_after_reinforcement(monkeypatch, tmp_path):
    """I2 (V3.18): el ancla congelada no se mueve por refuerzos posteriores —
    re-masterizar (o re-datación de filas) NO desplaza las ventanas 7/30/90."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    client = TestClient(app)

    _master_unit(uid, unit)
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}").json()
    units = _flat_units(plan)
    assert len(units) == 1
    anchor_before = units[0]["anchor"]
    due_before = [w["due_at"] for w in units[0]["windows"]]

    # Refuerzo posterior: filas con `updated_at` 30 días en el futuro.
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    oids = [o.id for les in unit.lessons for o in les.objectives]
    conn = db._conn()
    try:
        with conn:
            for oid in oids:
                conn.execute(
                    "UPDATE academy_objective_mastery "
                    "SET updated_at = ?, last_seen_at = ? "
                    "WHERE user_id = ? AND level_id = ? AND objective_id = ?",
                    (future, future, uid, LEVEL_ID, oid),
                )
    finally:
        conn.close()

    plan2 = client.get(f"/api/academy/review/unit-plan?user_id={uid}").json()
    units2 = _flat_units(plan2)
    assert units2[0]["anchor"] == anchor_before
    assert [w["due_at"] for w in units2[0]["windows"]] == due_before


def test_unit_plan_and_micro_review_span_previous_levels(monkeypatch, tmp_path):
    """O3 (V3.18): el plan agrega el nivel actual + niveles anteriores y el
    micro-review valida la unidad en el nivel donde vive (`level_id`)."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    academy_repo.set_enrollment_status(uid, "a1", "completed")
    academy_repo.enroll(uid, "a2", "A2")  # nivel actual (CEFR más alto)
    unit_a1 = _unit()
    lv2 = load_level("a2")
    unit_a2 = next(u for m in lv2.modules for u in m.units)
    client = TestClient(app)

    # Unidad completada en a1 (nivel anterior) y hace tiempo (ventanas vencidas).
    _master_unit(uid, unit_a1)
    _backdate_unit(uid, unit_a1)
    # Unidad completada en a2 (nivel actual) hace nada (ventanas upcoming).
    _master_unit(uid, unit_a2, "a2")

    # Micro-review de la unidad de a1 SIN level_id → 404 (vive en a1, no en a2).
    miss = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7"
    )
    assert miss.status_code == 404

    # Con level_id=a1 → 200; y el POST con level_id=a1 supera la ventana.
    ok = client.get(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review"
        f"?user_id={uid}&window_days=7&level_id=a1"
    )
    assert ok.status_code == 200, ok.text
    items = ok.json()["items"]
    correct = _correct_index_map(unit_a1)
    answers = {i["item_id"]: correct[i["item_id"]] for i in items}

    # Antes de superar la 7: la unidad de a1 tiene su 7 due_now (due_count 1).
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}").json()
    assert [lv["level_id"] for lv in plan["levels"]] == ["a1", "a2"]
    assert plan["due_count"] == 1

    posted = client.post(
        f"/api/academy/review/unit/{UNIT_ID}/micro-review?user_id={uid}",
        json={"window_days": 7, "answers": answers, "level_id": "a1"},
    )
    assert posted.status_code == 200
    assert posted.json()["passed"] is True

    # Plan agregado tras superar la 7 de forma TARDÍA (45 días tras el ancla):
    # la cadena O1 cierra también la 30 (retención demostrada más allá de su
    # hito) y la 90 sigue upcoming; a2 no aporta unidades repasables.
    plan = client.get(f"/api/academy/review/unit-plan?user_id={uid}").json()
    assert [lv["level_id"] for lv in plan["levels"]] == ["a1", "a2"]
    assert plan["due_count"] == 0
    by_unit = {
        u["unit_id"]: u
        for lv in plan["levels"]
        for u in lv["units"]
    }
    assert UNIT_ID in by_unit and unit_a2.id in by_unit
    w_a1 = by_unit[UNIT_ID]["windows"]
    assert [w["state"] for w in w_a1] == ["passed", "passed", "upcoming"]


def test_fsrs_due_and_summary_exclude_objective_cards(monkeypatch, tmp_path):
    """M4 (V3.18): `objective` no entra en la cola del panel autograduable ni en
    el `due_count`, y el POST `/fsrs/review` la rechaza (single writer)."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, LEVEL_ID, "A1")
    unit = _unit()
    _master_unit(uid, unit)
    _backdate_unit(uid, unit)
    client = TestClient(app)

    sync = client.post(f"/api/academy/fsrs/sync?user_id={uid}")
    assert sync.status_code == 200
    # Hay cartas objective (>= 2) en el resumen de diagnóstico...
    assert sync.json()["by_type"].get("objective", 0) >= 2
    # ...pero su due_count NO las cuenta (el repaso vive en UnitReviewPanel).
    assert sync.json()["due_count"] == 0

    due = client.get(f"/api/academy/fsrs/due?user_id={uid}").json()
    assert due["due_count"] == 0
    assert all(c["target_type"] != "objective" for c in due["cards"])

    # Single writer: el panel no puede autograduar una carta objective (400).
    oid = next(
        o.id for les in unit.lessons for o in les.objectives
    )
    rejected = client.post(
        f"/api/academy/fsrs/review?user_id={uid}",
        json={"target_type": "objective", "target_id": oid, "grade": 3},
    )
    assert rejected.status_code == 400

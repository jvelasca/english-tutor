"""V3.68 — Adaptive Engine Hardening & Integrity.

Cierra los TRES P1 de segunda generación de la auditoría de V3.67 y el P2 de
calibración asociado:

- **P1-01 (Task vs Task Instance)** — la identidad de tarea se separa en
  DEFINICIÓN (`task_key`: ítem, actividad, apoyo, carga servida y competencia
  evaluada, SIN contexto) e INSTANCIA (`task_instance_key`: definición +
  contexto). V3.67 agrupaba por una firma de SEIS componentes y el candidato del
  Planner la construía con el contexto VACÍO (se elige en el GET del peldaño), de
  modo que las tareas contextuales NUNCA casaban: aquí está la regresión que lo
  demuestra.
- **P1-02 (Lifecycle FSM)** — las transiciones dejan de ser un `UPDATE` sin
  guard: ahora hay tabla declarada, compare-and-set por estado de origen,
  idempotencia exigente en `completed`, reapertura de terminales sin medición,
  barrido de servidas antiguas y el eslabón que faltaba en el cliente.
- **P1-03 (Provenance ownership/integrity)** — toda transición exige el
  `user_id` (propiedad) y el `target_id` ejecutado, con rechazo best-effort y
  contabilizado por motivo.
- **P2-08 (Calibración honesta)** — `unclear` y `abandoned` salen del
  denominador de calibración: son incertidumbre de medición y abandono, no fallo
  de dominio.

Sin ML ni suavizado: solo tasas descriptivas.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from repositories import db
from repositories import decision_records as decision_records_repo
from repositories import users as users_repo
from services import observed_difficulty, planner, task_semantics
from services import skill_state as skill_state_service

_BACKEND = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _ledger(
    *,
    day: str,
    target_id: str = "apple",
    activity_id: str = "",
    support: str = "independent",
    skill: str = "recall",
    assessed: str = "",
    success: bool = True,
    served: str = "lexical:3",
    earned: str = "lexical:3",
    context_id: str = "",
    context_instance: str = "",
    row_id: str = "1",
) -> dict:
    """Fila del ledger léxico como la entrega `list_attempt_rows`."""
    return {
        "id": row_id,
        "occurred_at": f"{day}T10:00:00+00:00",
        "skill": skill,
        "assessed_skill": assessed or skill,
        "success": 1 if success else 0,
        "target_id": target_id,
        "surface_form": target_id,
        "served_difficulty": served,
        "observed_task_difficulty": earned,
        "observed_difficulty": served,
        "support_level": support,
        "response_time_ms": None,
        "error_type": "",
        "context_instance": context_instance,
        "context_id": context_id,
        "activity_id": activity_id,
    }


def _rows(*rows: dict) -> list[dict]:
    return skill_state_service.skill_state_sources(lexicon=list(rows))


def _record(uid: str, **overrides) -> dict:
    """Decisión mínima registrada (con los campos que la identidad necesita)."""
    kwargs = dict(
        target_id="apple",
        task_key="apple|recall|cued|lexical:3|recall",
        task_signature="apple|recall|cued|lexical:3|recall|",
        decision_start_fingerprint="F1",
    )
    kwargs.update(overrides)
    record = decision_records_repo.record_decision(uid, **kwargs)
    assert record is not None
    return record


# ---------------------------------------------------------------------------
# A · P1-01: Task DEFINITION vs Task INSTANCE
# ---------------------------------------------------------------------------


def test_task_key_ignores_context_and_instance_key_includes_it():
    base = dict(
        target_id="apple",
        activity="transfer",
        support_level="spontaneous",
        served_difficulty={"lexical": 3},
        assessed_skill="spontaneous_use",
    )
    # La DEFINICIÓN no incluye el contexto: dos instancias distintas comparten
    # clave de tarea (es lo que el Planner puede conocer ANTES de elegir).
    first = observed_difficulty.task_key_parts(**base)
    assert first == observed_difficulty.task_key_parts(**base)  # determinista
    # La INSTANCIA sí: cada contexto es otra instancia.
    restaurant = observed_difficulty.task_instance_key_parts(
        **base, context="restaurant_negotiation"
    )
    airport = observed_difficulty.task_instance_key_parts(
        **base, context="airport_checkin"
    )
    assert restaurant != airport
    assert restaurant.startswith(first)
    assert airport.startswith(first)
    # Sin contexto declarado la instancia sigue siendo la definición + separador.
    assert observed_difficulty.task_instance_key_from(first) == f"{first}|"


def test_task_key_parts_distinguish_activity_support_and_difficulty():
    base = dict(
        target_id="apple",
        activity="recall",
        support_level="cued",
        served_difficulty={"lexical": 3},
        assessed_skill="recall",
    )
    a = observed_difficulty.task_key_parts(**base)
    assert a != observed_difficulty.task_key_parts(**{**base, "activity": "write"})
    assert a != observed_difficulty.task_key_parts(
        **{**base, "support_level": "independent"}
    )
    assert a != observed_difficulty.task_key_parts(
        **{**base, "served_difficulty": {"lexical": 5}}
    )


def test_task_key_parts_normalizes_missing_components():
    # Componentes ausentes se normalizan a "" sin lanzar: la clave es estable.
    assert observed_difficulty.task_key_parts(None, None, None, None, None) == "||||"
    assert (
        observed_difficulty.task_instance_key_parts(None, None, None, None, None, None)
        == "|||||"
    )


def test_task_key_row_adapters():
    rows = _rows(
        _ledger(
            day="2026-01-01",
            activity_id="drill:transfer",
            support="spontaneous",
            skill="spontaneous_use",
            context_id="transfer:story",
            context_instance="story:0",
            row_id="1",
        )
    )
    (row,) = rows
    key = observed_difficulty.task_key(row)
    instance = observed_difficulty.task_instance_key(row)
    assert instance != key
    assert instance == observed_difficulty.task_instance_key_from(key, "story:0")
    # Una fila no-Mapping no declara identidad (nunca lanza).
    assert observed_difficulty.task_key(None) == ""
    assert observed_difficulty.task_instance_key(None) == ""


def test_p1_01_regression_task_empirical_matches_a_contextual_task():
    """REGRESIÓN DEL P1-01: la tarea contextual del ledger AHORA casa.

    Con la firma de SEIS componentes de V3.67, la fila del ledger (que declara su
    contexto) y el candidato del Planner (que lo desconoce) producían claves
    DISTINTAS, así que `task_empirical` no estaba disponible justo en las tareas
    donde el contexto forma parte de la identidad. Al mover el contexto al nivel
    de INSTANCIA, la DEFINICIÓN las agrupa y el candidato casa.
    """
    rows = _rows(
        *[
            _ledger(
                day=f"2026-01-{1 + i:02d}",
                activity_id="drill:transfer",
                support="spontaneous",
                skill="spontaneous_use",
                context_id="transfer:story",
                context_instance="story:0",
                row_id=f"a{i}",
            )
            for i in range(2)
        ],
        *[
            _ledger(
                day=f"2026-02-{1 + i:02d}",
                activity_id="drill:transfer",
                support="spontaneous",
                skill="spontaneous_use",
                context_id="transfer:story",
                context_instance="story:1",
                row_id=f"b{i}",
            )
            for i in range(2)
        ],
    )
    by_task = observed_difficulty.empirical_success_by_task(rows)
    # La clave del CANDIDATO del Planner (contexto desconocido), derivada con la
    # MISMA función pura que el ledger y con el apoyo declarado de la actividad.
    candidate_key = observed_difficulty.task_key_parts(
        target_id="apple",
        activity="transfer",
        support_level=planner.ACTIVITY_SUPPORT_LEVEL["transfer"],
        served_difficulty={"lexical": 3},
        assessed_skill=task_semantics.assessed_skill_for("transfer"),
    )
    # El candidato casa y agrupa las DOS instancias: 2 + 2 intentos.
    assert candidate_key in by_task
    assert by_task[candidate_key]["attempts"] == 4
    assert by_task[candidate_key]["p_success"] == 1.0
    # El nivel de INSTANCIA las separa: cada superficie es su propia observación
    # (misma puerta espaciada, 2 intentos cada una, no 4).
    by_instance = observed_difficulty.empirical_success_by_task_instance(rows)
    assert len(by_instance) == 2
    assert all(entry["attempts"] == 2 for entry in by_instance.values())
    assert all(key.startswith(candidate_key) for key in by_instance)


def test_empirical_success_by_task_distinguishes_activity_of_same_target():
    rows = _rows(
        # recall (apoyo `cued`): 2 éxitos en 2 días → p = 1.0
        _ledger(
            day="2026-01-01",
            activity_id="drill:recall:translation",
            support="cued",
            row_id="r1",
        ),
        _ledger(
            day="2026-01-02",
            activity_id="drill:recall:translation",
            support="cued",
            row_id="r2",
        ),
        # write (apoyo `independent`): 9 éxitos + 1 fallo → p = 0.9
        *[
            _ledger(
                day=f"2026-02-{1 + i:02d}",
                activity_id="drill:write",
                support="independent",
                skill="written_production",
                row_id=f"w{i}",
            )
            for i in range(9)
        ],
        _ledger(
            day="2026-02-10",
            activity_id="drill:write",
            support="independent",
            skill="written_production",
            success=False,
            earned="",
            row_id="wf",
        ),
    )
    by_task = observed_difficulty.empirical_success_by_task(rows)
    recall_key = observed_difficulty.task_key_parts(
        "apple", "recall", "cued", {"lexical": 3}, "recall"
    )
    write_key = observed_difficulty.task_key_parts(
        "apple", "write", "independent", {"lexical": 3}, "written_production"
    )
    assert set(by_task) == {recall_key, write_key}
    assert by_task[recall_key]["p_success"] == 1.0
    assert by_task[write_key]["p_success"] == 0.9
    # MISMO target, DISTINTA actividad → estimaciones DISTINTAS (cierre P1-01).
    assert by_task[recall_key]["p_success"] != by_task[write_key]["p_success"]


def test_empirical_success_by_task_without_spaced_sample_declares_nothing():
    rows = _rows(
        _ledger(day="2026-01-01", activity_id="drill:recall:translation", row_id="1"),
        _ledger(
            day="2026-01-01",
            activity_id="drill:recall:translation",
            success=False,
            earned="",
            row_id="2",
        ),
    )
    assert observed_difficulty.empirical_success_by_task(rows) == {}
    assert observed_difficulty.empirical_success_by_task_instance(rows) == {}


# ---------------------------------------------------------------------------
# B · P1-02: FSM real del ciclo de vida
# ---------------------------------------------------------------------------


def test_fsm_accepts_the_declared_lifecycle():
    assert decision_records_repo._ALLOWED_TRANSITIONS["served"] == (
        "computed",
        "served",
    )
    assert "served" in decision_records_repo._ALLOWED_TRANSITIONS["started"]
    # `served → completed` es VÁLIDA y DECLARADA: sin inicio declarado el outcome
    # no se pierde (el round-trip del cliente es best-effort).
    assert "served" in decision_records_repo._ALLOWED_TRANSITIONS["completed"]
    assert "started" in decision_records_repo._ALLOWED_TRANSITIONS["completed"]
    # `computed` NO es origen de ninguna transición salvo `served`.
    assert decision_records_repo._ALLOWED_TRANSITIONS["served"] == (
        "computed",
        "served",
    )
    assert "computed" not in decision_records_repo._ALLOWED_TRANSITIONS["started"]
    assert "computed" not in decision_records_repo._ALLOWED_TRANSITIONS["completed"]
    assert "computed" not in decision_records_repo._ALLOWED_TRANSITIONS["abandoned"]


def test_lifecycle_full_path_served_started_completed(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    record = _record(uid)
    decision_id = record["decision_id"]
    assert decision_records_repo.mark_served(uid, decision_id) is True
    assert decision_records_repo.mark_started(uid, decision_id) is True
    assert decision_records_repo.mark_completed(uid, decision_id, "ok") is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "completed"
    assert row["outcome"] == "ok"
    assert row["served_at"] != ""
    assert row["started_at"] != ""
    assert row["completed_at"] != ""


def test_served_to_completed_is_valid_without_started(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    record = _record(uid)
    decision_id = record["decision_id"]
    assert decision_records_repo.mark_served(uid, decision_id) is True
    assert decision_records_repo.mark_completed(uid, decision_id, "ko") is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "completed"
    assert row["started_at"] == ""


def test_computed_cannot_jump_to_terminal_states(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid)["decision_id"]
    # `computed → started/completed/abandoned` son IMPOSIBLES.
    assert decision_records_repo.mark_started(uid, decision_id) is False
    assert decision_records_repo.mark_completed(uid, decision_id, "ok") is False
    assert decision_records_repo.mark_abandoned(uid, decision_id) is False
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "computed"
    assert row["started_at"] == ""
    assert row["completed_at"] == ""
    assert row["outcome"] == ""


def test_completed_is_terminal_but_idempotent_with_same_outcome(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid)["decision_id"]
    decision_records_repo.mark_served(uid, decision_id)
    assert decision_records_repo.mark_completed(uid, decision_id, "ok") is True
    # Repetir con el MISMO outcome es idempotente.
    assert decision_records_repo.mark_completed(uid, decision_id, "ok") is True
    # Con OTRO outcome se rechaza (la primera medición de la sesión manda).
    assert decision_records_repo.mark_completed(uid, decision_id, "ko") is False
    # Y ninguna transición hacia atrás es posible desde una terminal.
    assert decision_records_repo.mark_served(uid, decision_id) is False
    assert decision_records_repo.mark_started(uid, decision_id) is False
    assert decision_records_repo.mark_abandoned(uid, decision_id) is False
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "completed"
    assert row["outcome"] == "ok"
    health = decision_records_repo.transition_health()
    assert health["rejections"]["invalid_transition"] >= 3
    assert health["rejections"]["duplicate_outcome"] >= 1


def test_served_and_started_are_idempotent(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid)["decision_id"]
    assert decision_records_repo.mark_served(uid, decision_id) is True
    assert decision_records_repo.mark_served(uid, decision_id) is True
    assert decision_records_repo.mark_started(uid, decision_id) is True
    assert decision_records_repo.mark_started(uid, decision_id) is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "started"


def test_abandoned_is_valid_from_served_and_started(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    first = _record(uid, decision_start_fingerprint="F1")["decision_id"]
    second = _record(uid, decision_start_fingerprint="F2")["decision_id"]
    assert decision_records_repo.mark_served(uid, first) is True
    assert decision_records_repo.mark_abandoned(uid, first) is True
    assert decision_records_repo.mark_served(uid, second) is True
    assert decision_records_repo.mark_started(uid, second) is True
    assert decision_records_repo.mark_abandoned(uid, second) is True
    rows = {
        row["decision_id"]: row
        for row in decision_records_repo.list_decisions(uid)
    }
    assert rows[first]["decision_status"] == "abandoned"
    assert rows[second]["decision_status"] == "abandoned"
    # Un `abandoned` tampoco se reabre por `completed`.
    assert decision_records_repo.mark_completed(uid, first, "ok") is False


def test_missing_decision_id_never_raises(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert decision_records_repo.mark_served(uid, "missing-id") is False
    assert decision_records_repo.mark_started(uid, "missing-id") is False
    assert decision_records_repo.mark_completed(uid, "missing-id", "ok") is False
    assert decision_records_repo.mark_abandoned(uid, "missing-id") is False
    assert decision_records_repo.transition_health()["rejections"]["missing"] >= 4


# ---------------------------------------------------------------------------
# C · P1-03: propiedad, integridad y auditoría del target
# ---------------------------------------------------------------------------


def test_transition_rejects_another_users_decision(monkeypatch, tmp_path):
    owner = _setup(monkeypatch, tmp_path)
    intruder = users_repo.create_user("B")["id"]
    decision_id = _record(owner)["decision_id"]
    # El `decision_id` de A no puede modificarse desde B (propiedad exigida).
    assert decision_records_repo.mark_served(intruder, decision_id) is False
    assert decision_records_repo.mark_completed(intruder, decision_id, "ok") is False
    (row,) = decision_records_repo.list_decisions(owner)
    assert row["decision_status"] == "computed"
    assert row["outcome"] == ""
    # El listado de B nunca devuelve la fila de A.
    assert decision_records_repo.list_decisions(intruder) == []
    assert decision_records_repo.transition_health()["rejections"]["wrong_owner"] >= 2


def test_transition_rejects_a_mismatched_target(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid, target_id="apple")["decision_id"]
    # Un target que no es el de la decisión no puede servirla.
    assert (
        decision_records_repo.mark_served(uid, decision_id, target_id="banana")
        is False
    )
    assert (
        decision_records_repo.mark_served(
            uid, decision_id, target_id="apple"
        )
        is True
    )
    assert (
        decision_records_repo.mark_completed(
            uid, decision_id, "ok", target_id="banana"
        )
        is False
    )
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "served"
    health = decision_records_repo.transition_health()
    assert health["rejections"]["target_mismatch"] >= 2


def test_executed_activity_is_recorded_and_audited(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    record = _record(
        uid, selected_activity="recall", selected_skill="recall"
    )
    decision_id = record["decision_id"]
    # El alumno degradó el peldaño: la actividad ejecutada NO es la decidida. NO es
    # puerta (se registra), porque el drill degrada peldaños legítimamente.
    assert (
        decision_records_repo.mark_served(
            uid, decision_id, target_id="apple", activity="recognition"
        )
        is True
    )
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["selected_activity"] == "recall"
    assert row["executed_activity"] == "recognition"
    assert row["activity_match"] is False


def test_served_declares_the_instance_context(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    task_key = observed_difficulty.task_key_parts(
        "apple", "transfer", "spontaneous", {"lexical": 3}, "spontaneous_use"
    )
    record = _record(uid, task_key=task_key)
    decision_id = record["decision_id"]
    assert decision_records_repo.mark_served(
        uid,
        decision_id,
        target_id="apple",
        context_id="transfer:story",
        context_instance="story:0",
    ) is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["context_id"] == "transfer:story"
    assert row["context_instance"] == "story:0"
    assert row["instance_known"] is True
    # La INSTANCIA es la definición + el contexto servido.
    assert row["task_instance_key"] == observed_difficulty.task_instance_key_from(
        task_key, "story:0"
    )
    assert row["task_key"] == task_key


# ---------------------------------------------------------------------------
# D · P1-02: re-servicio, reapertura y barrido
# ---------------------------------------------------------------------------


def test_reservice_of_an_abandoned_decision_reopens_it(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    first = _record(uid)
    decision_id = first["decision_id"]
    decision_records_repo.mark_served(uid, decision_id)
    decision_records_repo.mark_abandoned(uid, decision_id)
    # Re-servir la MISMA decisión (contexto nuevo de la cola) la REABRE: una
    # decisión abandonada no tiene medición que preservar.
    again = _record(uid)
    assert again["decision_id"] == decision_id
    assert again["reopened"] is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "computed"
    assert row["provenance_status"] == decision_records_repo.PROVENANCE_REOPENED
    assert row["served_at"] == ""
    assert row["completed_at"] == ""
    assert len(decision_records_repo.list_decisions(uid)) == 1


def test_reservice_of_an_unclear_completed_decision_reopens_it(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid)["decision_id"]
    decision_records_repo.mark_served(uid, decision_id)
    decision_records_repo.mark_completed(uid, decision_id, "unclear")
    again = _record(uid)
    assert again["reopened"] is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "computed"
    assert row["outcome"] == ""


def test_reservice_of_a_measured_decision_is_not_overwritten(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid, p_success=0.4)["decision_id"]
    decision_records_repo.mark_served(uid, decision_id)
    decision_records_repo.mark_completed(uid, decision_id, "ok")
    # La MEDICIÓN manda: el re-servicio no la sobrescribe ni la reabre.
    again = _record(uid, p_success=0.9)
    assert again["decision_id"] == decision_id
    assert again["closed"] is True
    assert again["reopened"] is False
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "completed"
    assert row["outcome"] == "ok"
    assert row["p_success"] == 0.4
    assert decision_records_repo.transition_health()["closed_decision"] >= 1


def test_metadata_refresh_does_not_touch_a_non_terminal_state(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    decision_id = _record(uid, p_success=0.4)["decision_id"]
    decision_records_repo.mark_served(uid, decision_id)
    again = _record(uid, p_success=0.6, state_fingerprint="F9")
    assert again["reopened"] is False
    (row,) = decision_records_repo.list_decisions(uid)
    # El estado se conserva y la metadata se refresca.
    assert row["decision_status"] == "served"
    assert row["served_at"] != ""
    assert row["p_success"] == 0.6
    assert row["state_fingerprint"] == "F9"


def test_close_stale_only_closes_served_and_old_decisions(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    served = _record(uid, decision_start_fingerprint="SERVED")["decision_id"]
    started = _record(uid, decision_start_fingerprint="STARTED")["decision_id"]
    computed = _record(uid, decision_start_fingerprint="COMPUTED")["decision_id"]
    completed = _record(uid, decision_start_fingerprint="COMPLETED")["decision_id"]
    abandoned = _record(uid, decision_start_fingerprint="ABANDONED")["decision_id"]
    decision_records_repo.mark_served(uid, served)
    decision_records_repo.mark_served(uid, started)
    decision_records_repo.mark_started(uid, started)
    decision_records_repo.mark_served(uid, completed)
    decision_records_repo.mark_completed(uid, completed, "ok")
    decision_records_repo.mark_served(uid, abandoned)
    decision_records_repo.mark_abandoned(uid, abandoned)
    # El corte en el FUTURO deja viejas TODAS las servidas: se cierran las que
    # están en `served`/`started` y NUNCA las `computed` ni las terminales.
    assert (
        decision_records_repo.close_stale(
            uid, before_iso="9999-01-01T00:00:00+00:00"
        )
        == 2
    )
    rows = {
        row["decision_id"]: row
        for row in decision_records_repo.list_decisions(uid)
    }
    assert rows[served]["decision_status"] == "abandoned"
    assert rows[started]["decision_status"] == "abandoned"
    assert rows[computed]["decision_status"] == "computed"
    assert rows[completed]["decision_status"] == "completed"
    assert rows[abandoned]["decision_status"] == "abandoned"
    # Un corte en el PASADO (nada es más antiguo) no cierra nada.
    fresh = _record(uid, decision_start_fingerprint="FRESH")["decision_id"]
    decision_records_repo.mark_served(uid, fresh)
    assert (
        decision_records_repo.close_stale(
            uid, before_iso="1999-01-01T00:00:00+00:00"
        )
        == 0
    )
    rows = {
        row["decision_id"]: row
        for row in decision_records_repo.list_decisions(uid)
    }
    assert rows[fresh]["decision_status"] == "served"
    # Sin corte no hay barrido (nunca lanza).
    assert decision_records_repo.close_stale(uid, before_iso="") == 0


# ---------------------------------------------------------------------------
# E · P2-08: calibración honesta (unclear/abandoned fuera del denominador)
# ---------------------------------------------------------------------------


def test_calibration_excludes_unclear_and_abandoned(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    cases = [
        ("apple", 0.2, "ko"),
        ("banana", 0.8, "ok"),
        ("cherry", 0.5, "unclear"),
        ("damson", 0.5, "abandoned"),
    ]
    for target, p, outcome in cases:
        record = _record(
            uid, target_id=target, task_key=target, p_success=p
        )
        decision_id = record["decision_id"]
        decision_records_repo.mark_served(uid, decision_id)
        decision_records_repo.mark_completed(uid, decision_id, outcome)
    report = decision_records_repo.calibration_report(uid)
    # Todas cuentan como `completed`, pero SOLO las medibles calibran.
    assert report["completed_count"] == 4
    assert report["measured_count"] == 2
    assert report["unclear_count"] == 1
    assert report["abandoned_count"] == 1
    bands = {band["band"]: band for band in report["bands"]}
    assert bands[0.2]["observed_success_rate"] == 0.0
    assert bands[0.8]["observed_success_rate"] == 1.0
    # Si `unclear` contara como fallo, el error de la banda 0.5 sería −0.5.
    assert 0.5 not in bands
    assert report["calibration_error"] == 0.0


def test_calibration_report_empty_without_completed_rows(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _record(uid)
    report = decision_records_repo.calibration_report(uid)
    assert report["completed_count"] == 0
    assert report["measured_count"] == 0
    assert report["bands"] == []
    assert report["calibration_error"] is None


# ---------------------------------------------------------------------------
# F · Endpoints: el eslabón que hace real el ciclo de vida
# ---------------------------------------------------------------------------


def _client(monkeypatch, tmp_path) -> TestClient:
    _setup(monkeypatch, tmp_path)
    from main import app

    return TestClient(app)


def test_decision_lifecycle_endpoint_marks_started(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    uid = users_repo.list_users()[0]["id"]
    decision_id = _record(uid)["decision_id"]
    decision_records_repo.mark_served(uid, decision_id, target_id="apple")
    with client:
        response = client.post(
            "/api/vocabulary/drill/decision-lifecycle",
            params={"user_id": uid},
            json={
                "decision_id": decision_id,
                "event": "started",
                "target_id": "apple",
                "activity": "recall",
            },
        )
    assert response.status_code == 200
    assert response.json()["applied"] is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "started"
    assert row["executed_activity"] == "recall"


def test_decision_lifecycle_endpoint_rejects_an_impossible_event(
    monkeypatch, tmp_path
):
    client = _client(monkeypatch, tmp_path)
    uid = users_repo.list_users()[0]["id"]
    decision_id = _record(uid)["decision_id"]
    with client:
        # Sin `served` previo, `started` es una transición IMPOSIBLE: la FSM la
        # rechaza, pero el endpoint responde 200 con `applied=false`
        # (best-effort: el drill nunca se rompe).
        response = client.post(
            "/api/vocabulary/drill/decision-lifecycle",
            params={"user_id": uid},
            json={"decision_id": decision_id, "event": "started"},
        )
        # Un evento fuera del contrato sí es 422 (Literal cerrado).
        invalid = client.post(
            "/api/vocabulary/drill/decision-lifecycle",
            params={"user_id": uid},
            json={"decision_id": decision_id, "event": "exploded"},
        )
    assert response.status_code == 200
    assert response.json()["applied"] is False
    assert invalid.status_code == 422


def test_drill_recall_roundtrip_closes_the_cycle(monkeypatch, tmp_path):
    """Round-trip completo: el GET del peldaño marca la decisión servida y
    declara la actividad EJECUTADA (el `decision_id` viaja como query)."""
    client = _client(monkeypatch, tmp_path)
    uid = users_repo.list_users()[0]["id"]
    decision_id = _record(uid)["decision_id"]
    with client:
        served = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "apple", "decision_id": decision_id},
        )
    # El peldaño puede degradar (200) o no tener contenido (422): en AMBOS casos
    # el GET declara el servicio y no rompe el ciclo de vida.
    assert served.status_code in (200, 422)
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "served"
    assert row["executed_activity"] == "recall"

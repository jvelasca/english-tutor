"""V3.67 — Task Identity 2.0 + Decision Lifecycle + Provenance Analytics.

Cierra los dos P1 de la auditoría de V3.66 y los P2/P3 asociados:

- **P1-01** — `target_id` no era una identidad de tarea completa. Aquí se
  introduce `task_signature` (seis componentes) y `empirical_success_by_task`,
  con la jerarquía `task → target → skill → margin`.
- **P1-02** — el provenance era append-only y se escribía en el GET. Aquí el
  `decision_id` es DETERMINISTA, el registro es UPSERT idempotente y hay ciclo
  de vida `computed → served → started → completed`.
- **P2/P3** — tasas raw/recent/long-term, `p_success_observed`, metadata de
  tarea en el provenance, y analítica de calibración predicted vs observed.

Sin ML ni suavizado: solo tasas descriptivas.
"""

from __future__ import annotations

from pathlib import Path

from repositories import db
from repositories import decision_records as decision_records_repo
from repositories import users as users_repo
from services import observed_difficulty, planner
from services import skill_state as skill_state_service

_BACKEND = Path(__file__).resolve().parent.parent
NOW = "2026-09-13T10:00:00+00:00"


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
        "context_instance": "",
        "context_id": "",
        "activity_id": activity_id,
    }


def _rows(*rows: dict) -> list[dict]:
    return skill_state_service.skill_state_sources(lexicon=list(rows))


# ---------------------------------------------------------------------------
# A · Task Identity 2.0 (P1-01): firma canónica y agrupación por TAREA
# ---------------------------------------------------------------------------


def test_task_signature_parts_distinguish_activity_support_and_difficulty():
    base = dict(
        target_id="apple",
        activity="recall",
        support_level="cued",
        served_difficulty={"lexical": 3},
        context="",
        assessed_skill="recall",
    )
    a = observed_difficulty.task_signature_parts(**base)
    assert a == observed_difficulty.task_signature_parts(**base)  # determinista
    assert a != observed_difficulty.task_signature_parts(
        **{**base, "activity": "write"}
    )
    assert a != observed_difficulty.task_signature_parts(
        **{**base, "support_level": "independent"}
    )
    assert a != observed_difficulty.task_signature_parts(
        **{**base, "served_difficulty": {"lexical": 5}}
    )


def test_task_signature_parts_normalizes_missing_components():
    # Componentes ausentes se normalizan a "" sin lanzar: la firma es estable.
    sig = observed_difficulty.task_signature_parts(
        None, None, None, None, None, None
    )
    assert sig == "|||||"


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
    recall_sig = observed_difficulty.task_signature_parts(
        "apple", "recall", "cued", {"lexical": 3}, "", "recall"
    )
    write_sig = observed_difficulty.task_signature_parts(
        "apple", "write", "independent", {"lexical": 3}, "", "written_production"
    )
    assert set(by_task) == {recall_sig, write_sig}
    assert by_task[recall_sig]["p_success"] == 1.0
    assert by_task[write_sig]["p_success"] == 0.9
    # MISMO target, DISTINTA actividad → estimaciones DISTINTAS (cierre P1-01).
    assert by_task[recall_sig]["p_success"] != by_task[write_sig]["p_success"]


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


# ---------------------------------------------------------------------------
# B · Estadística honesta (P2): raw/recent/long-term y p_success_observed
# ---------------------------------------------------------------------------


def test_empirical_rates_raw_recent_long_term():
    rows = _rows(
        *[
            _ledger(day=f"2026-01-{1 + i:02d}", row_id=f"s{i}")
            for i in range(5)
        ],
        *[
            _ledger(
                day=f"2026-01-{6 + i:02d}",
                success=False,
                earned="",
                row_id=f"f{i}",
            )
            for i in range(5)
        ],
    )
    entry = observed_difficulty.empirical_success_by_target(rows)["apple"]
    assert entry["attempts"] == 10
    assert entry["successes"] == 5
    assert entry["raw_rate"] == 0.5
    assert entry["long_term_rate"] == 0.5
    assert entry["recent_rate"] == 0.0  # los últimos 5 son fallos
    assert entry["p_success_observed"] == 0.5
    assert entry["p_success"] == 0.5  # alias retrocompatible de V3.66


# ---------------------------------------------------------------------------
# C · Jerarquía de resolución de `p_success` (task → target → skill → margin)
# ---------------------------------------------------------------------------


def test_p_success_hierarchy_task_target_skill_margin():
    signals = {"forgetting": 1.0}
    kwargs = dict(task_difficulty={"lexical": 3}, learner_capacity={"lexical": 3})
    assert (
        planner.expected_learning_value(signals, **kwargs)["p_success_source"]
        == "margin"
    )
    skill = planner.expected_learning_value(
        signals, **kwargs, empirical_success={"p_success": 0.6}
    )
    assert skill["p_success_source"] == "skill_empirical"
    target = planner.expected_learning_value(
        signals,
        **kwargs,
        empirical_success={"p_success": 0.6},
        target_empirical_success={"p_success": 0.4},
    )
    assert target["p_success"] == 0.4
    assert target["p_success_source"] == "target_empirical"
    assert target["target_p_success"] == 0.4
    task = planner.expected_learning_value(
        signals,
        **kwargs,
        target_empirical_success={"p_success": 0.4},
        task_empirical_success={"p_success": 0.2},
    )
    assert task["p_success"] == 0.2
    assert task["p_success_source"] == "task_empirical"
    assert task["task_p_success"] == 0.2


def test_task_empirical_for_resolves_by_activity():
    by_activity = {
        "recall": {"p_success_observed": 0.2},
        "write": {"p_success_observed": 0.9},
    }
    assert (
        planner._task_empirical_for(by_activity, "recall")["p_success_observed"]
        == 0.2
    )
    assert (
        planner._task_empirical_for(by_activity, "write")["p_success_observed"]
        == 0.9
    )
    # Sin clave para la actividad → None (degrada al nivel siguiente).
    assert planner._task_empirical_for(by_activity, "transfer") is None
    # Un payload escalar retrocompatible se devuelve tal cual.
    scalar = {"p_success": 0.5}
    assert planner._task_empirical_for(scalar, "recall") == scalar


# ---------------------------------------------------------------------------
# D · Decision Lifecycle (P1-02): idempotencia, transiciones y metadata
# ---------------------------------------------------------------------------


def test_record_decision_upsert_is_idempotent(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    kwargs = dict(
        target_id="apple",
        task_signature="apple|recall|cued|lexical:3||recall",
        decision_start_fingerprint="F1",
        state_fingerprint="F2",
        p_success=0.2,
        p_success_source="task_empirical",
    )
    first = decision_records_repo.record_decision(uid, **kwargs)
    second = decision_records_repo.record_decision(uid, **kwargs)
    # Misma identidad → mismo `decision_id` y UNA sola fila (sin duplicar).
    assert first["decision_id"] == second["decision_id"]
    assert len(decision_records_repo.list_decisions(uid)) == 1


def test_record_decision_persists_task_metadata(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    decision_records_repo.record_decision(
        uid,
        target_id="apple",
        task_signature="apple|write|independent|lexical:4||written_production",
        served_load={"lexical": 4, "syntax": 2},
        support_level="independent",
        assessment_mode="written",
        decision_start_fingerprint="F1",
        state_fingerprint="F2",
        p_success=0.9,
        p_success_source="task_empirical",
    )
    (row,) = decision_records_repo.list_decisions(uid)
    assert (
        row["task_signature"]
        == "apple|write|independent|lexical:4||written_production"
    )
    assert row["served_load"] == {"lexical": 4, "syntax": 2}
    assert row["support_level"] == "independent"
    assert row["assessment_mode"] == "written"
    assert row["decision_status"] == "computed"


def test_decision_lifecycle_transitions(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    record = decision_records_repo.record_decision(
        uid, target_id="apple", task_signature="sig", decision_start_fingerprint="F1"
    )
    decision_id = record["decision_id"]
    assert decision_records_repo.mark_served(decision_id) is True
    assert decision_records_repo.mark_completed(decision_id, "ok") is True
    (row,) = decision_records_repo.list_decisions(uid)
    assert row["decision_status"] == "completed"
    assert row["outcome"] == "ok"
    assert row["served_at"] != ""
    assert row["completed_at"] != ""
    # Transición sobre un id inexistente → no actualiza nada.
    assert decision_records_repo.mark_served("missing-id") is False


def test_calibration_report_predicted_vs_observed(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    for target, p, outcome in [("apple", 0.2, "ko"), ("banana", 0.8, "ok")]:
        record = decision_records_repo.record_decision(
            uid,
            target_id=target,
            task_signature=target,
            decision_start_fingerprint="F1",
            p_success=p,
            p_success_source="target_empirical",
        )
        decision_records_repo.mark_completed(record["decision_id"], outcome)
    report = decision_records_repo.calibration_report(uid)
    assert report["completed_count"] == 2
    bands = {band["band"]: band for band in report["bands"]}
    assert bands[0.2]["observed_success_rate"] == 0.0
    assert bands[0.8]["observed_success_rate"] == 1.0
    # Errores simétricos: +0.2 en la banda baja y −0.2 en la alta.
    assert report["calibration_error"] == 0.0


def test_calibration_report_empty_without_completed_rows(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    decision_records_repo.record_decision(
        uid, target_id="apple", task_signature="sig", decision_start_fingerprint="F1"
    )
    report = decision_records_repo.calibration_report(uid)
    assert report["completed_count"] == 0
    assert report["bands"] == []
    assert report["calibration_error"] is None

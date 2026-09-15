"""V3.66 — Task-Level Empirical Success + Decision Provenance (cierre P1-01/P1-02).

Cierra dos hallazgos de la auditoría de V3.65:

- **P1-01** — el estimador por pareja existía (`empirical_success` por tarea)
  pero la decisión colapsaba a `skill`. Aquí se introduce
  `empirical_success_by_target` (por ITEM) y se cablea hasta el Planner 3.0 con
  la política de resolución `task_empirical → skill_empirical → margin`.
- **P1-02** — `snapshot_fingerprint` podía etiquetar un estado que no
  representaba. Aquí se separan `decision_start_fingerprint` y
  `state_fingerprint`, y el payload expone ambas con honestidad.

Fija además el PROVENANCE de decisión (`decision_records`, append-only).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from domain import decision as decision_domain
from repositories import db
from repositories import decision_records as decision_records_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from services import lexicon, observed_difficulty, planner
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


def _lexicon_ledger(
    *,
    day: str,
    skill: str = "recall",
    assessed: str = "",
    served: str = "lexical:3",
    earned: str = "lexical:3",
    success: bool = True,
    target_id: str = "apple",
    surface_form: str = "",
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
        "surface_form": surface_form or target_id,
        "served_difficulty": served,
        "observed_task_difficulty": earned,
        "observed_difficulty": served,
        "support_level": "independent",
        "response_time_ms": None,
        "error_type": "",
        "context_instance": "",
        "activity_id": "",
    }


def _rows(*rows: dict) -> list[dict]:
    return skill_state_service.skill_state_sources(lexicon=list(rows))


def _row(**overrides) -> dict:
    row = {
        "word": "apple",
        "cefr": "B1",
        "exposure_count": 3,
        "writing_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    row.update(overrides)
    return row


def _card(**overrides) -> dict:
    card = {
        "target_id": "apple",
        "due_at": "2026-09-12T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-09T10:00:00+00:00",
    }
    card.update(overrides)
    return card


# ---------------------------------------------------------------------------
# A · `empirical_success_by_target` (P1-01): granularidad por ITEM
# ---------------------------------------------------------------------------


def test_empirical_success_by_target_groups_by_item():
    rows = _rows(
        # apple: 2 éxitos + 8 fallos → p = 0.2
        _lexicon_ledger(day="2026-01-01", target_id="apple", row_id="1"),
        _lexicon_ledger(day="2026-01-02", target_id="apple", row_id="2"),
        *[
            _lexicon_ledger(
                day=f"2026-01-{3 + i:02d}",
                target_id="apple",
                success=False,
                earned="",
                row_id=f"a{i}",
            )
            for i in range(8)
        ],
        # banana: 9 éxitos + 1 fallo → p = 0.9
        *[
            _lexicon_ledger(
                day=f"2026-02-{1 + i:02d}",
                target_id="banana",
                row_id=f"b{i}",
            )
            for i in range(9)
        ],
        _lexicon_ledger(
            day="2026-02-10",
            target_id="banana",
            success=False,
            earned="",
            row_id="bf",
        ),
    )
    by_target = observed_difficulty.empirical_success_by_target(rows)
    assert set(by_target) == {"apple", "banana"}
    assert by_target["apple"]["successes"] == 2
    assert by_target["apple"]["attempts"] == 10
    assert by_target["apple"]["p_success"] == 0.2
    assert by_target["banana"]["successes"] == 9
    assert by_target["banana"]["attempts"] == 10
    assert by_target["banana"]["p_success"] == 0.9


def test_empirical_success_by_target_without_spaced_sample_declares_nothing():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", target_id="apple", row_id="1"),
        _lexicon_ledger(
            day="2026-01-01", target_id="apple", success=False, earned="", row_id="2"
        ),
    )
    assert observed_difficulty.empirical_success_by_target(rows) == {}


def test_empirical_success_by_target_ignores_items_without_identity():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", target_id="apple", row_id="1"),
        _lexicon_ledger(day="2026-01-02", target_id="apple", row_id="2"),
        # Filas sin target_id (fuente que no declara identidad) no forman clave.
        _lexicon_ledger(day="2026-01-03", target_id="", surface_form="", row_id="3"),
    )
    by_target = observed_difficulty.empirical_success_by_target(rows)
    assert set(by_target) == {"apple"}


# ---------------------------------------------------------------------------
# B · Política de resolución de `p_success` (task → skill → margin)
# ---------------------------------------------------------------------------


def test_task_empirical_overrides_skill_empirical_over_margin():
    signals = {"forgetting": 1.0}
    kwargs = dict(
        task_difficulty={"lexical": 3},
        learner_capacity={"lexical": 3},
    )
    margin_only = planner.expected_learning_value(signals, **kwargs)
    assert margin_only["p_success"] == 0.55
    assert margin_only["p_success_source"] == "margin"
    assert "task_p_success" not in margin_only

    skill = planner.expected_learning_value(
        signals, **kwargs, empirical_success={"p_success": 0.6}
    )
    assert skill["p_success"] == 0.6
    assert skill["p_success_source"] == "skill_empirical"
    assert "task_p_success" not in skill

    task = planner.expected_learning_value(
        signals,
        **kwargs,
        empirical_success={"p_success": 0.6},
        task_empirical_success={"p_success": 0.2},
    )
    assert task["p_success"] == 0.2
    assert task["p_success_source"] == "task_empirical"
    assert task["task_p_success"] == 0.2
    assert task["p_success_empirical"] is True


def test_invalid_task_and_skill_estimates_degrade_to_margin():
    signals = {"forgetting": 1.0}
    for bad_task, bad_skill in [
        ("nope", {"p_success": 0.8}),
        ({"p_success": 5.0}, {"p_success": 0.8}),
        ([], []),
    ]:
        payload = planner.expected_learning_value(
            signals,
            task_difficulty={"lexical": 3},
            learner_capacity={"lexical": 3},
            empirical_success=bad_skill,
            task_empirical_success=bad_task,
        )
        # Un estimado inválido se IGNORA; el otro (si es válido) sigue mandando.
        assert payload["p_success_source"] in ("margin", "skill_empirical")


def test_select_task_by_elv_injects_the_task_estimate():
    matrix = {"production": True}
    evidence = {"error_types": {"wrong_word": 2}, "skill_successes": {"recall": 2}}
    signals = planner.planned_signals(evidence, matrix)
    planned = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={"recall": {"lexical": 3}},
        task_difficulty={"lexical": 4},
        skill_values={"recall": 0.5},
        drivers={"recall": {"measured": True}},
        empirical_success={"recall": {"p_success": 0.8}},
        task_empirical_success={"p_success": 0.2},
    )
    decision = planned["decision"]
    assert decision["p_success"] == 0.2
    assert decision["p_success_source"] == "task_empirical"
    assert decision["task_p_success"] == 0.2
    assert decision["margin"] == -1  # el margen declarado no cambia


# ---------------------------------------------------------------------------
# C · E2E: la decisión DISTINGUE ítems del mismo skill (la prueba que faltaba)
# ---------------------------------------------------------------------------


def test_review_queue_item_distinguishes_a_and_b_by_task_empirical():
    # Mismo skill (recall), misma dificultad declarada, mismo alumno.
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", target_id="apple", row_id="1"),
        _lexicon_ledger(day="2026-01-02", target_id="apple", row_id="2"),
        *[
            _lexicon_ledger(
                day=f"2026-01-{3 + i:02d}",
                target_id="apple",
                success=False,
                earned="",
                row_id=f"a{i}",
            )
            for i in range(8)
        ],
        *[
            _lexicon_ledger(
                day=f"2026-02-{1 + i:02d}",
                target_id="banana",
                row_id=f"b{i}",
            )
            for i in range(9)
        ],
        _lexicon_ledger(
            day="2026-02-10",
            target_id="banana",
            success=False,
            earned="",
            row_id="bf",
        ),
    )
    state = skill_state_service.skill_state(rows)
    by_target = observed_difficulty.empirical_success_by_target(rows)
    payload = decision_domain.project_state(
        state, source="test", empirical_success_by_task=by_target
    )
    # El mapa por ítem está presente y la celda agregada por skill es la mezcla.
    assert payload["empirical_success_by_task"]["apple"]["p_success"] == 0.2
    assert payload["empirical_success_by_task"]["banana"]["p_success"] == 0.9

    evidence = {
        "error_types": {"wrong_word": 2},
        "skill_successes": {"recall": 11},
    }
    item_a = lexicon.review_queue_item(
        _row(word="apple"),
        _card(target_id="apple"),
        now=NOW,
        evidence=evidence,
        projection=payload,
    )
    item_b = lexicon.review_queue_item(
        _row(word="banana"),
        _card(target_id="banana"),
        now=NOW,
        evidence=evidence,
        projection=payload,
    )
    assert item_a["decision"]["p_success"] == 0.2
    assert item_a["decision"]["p_success_source"] == "task_empirical"
    assert item_b["decision"]["p_success"] == 0.9
    assert item_b["decision"]["p_success_source"] == "task_empirical"
    # El Planner YA distingue A y B: sus p_success son distintos.
    assert item_a["decision"]["p_success"] != item_b["decision"]["p_success"]


# ---------------------------------------------------------------------------
# D · P1-02: DOS huellas de fingerprint explícitas y honestas
# ---------------------------------------------------------------------------


def test_project_state_exposes_two_fingerprints():
    payload = decision_domain.project_state(
        skill_state_service.empty_skill_state(),
        source="test",
        snapshot_fingerprint="F1",
        state_fingerprint="F2",
    )
    assert payload["snapshot_fingerprint"] == "F1"
    assert payload["decision_start_fingerprint"] == "F1"
    assert payload["state_fingerprint"] == "F2"
    # El alias retrocompatible no cambia de significado.
    assert payload["decision_start_fingerprint"] == payload["snapshot_fingerprint"]


def test_project_state_can_carry_distinct_start_and_state_fingerprints():
    # Evidencia que entra a mitad de decisión: la huella de inicio y la del estado
    # proyectado pueden divergir, y AMBAS se exponen (sin etiquetar mal).
    payload = decision_domain.project_state(
        skill_state_service.empty_skill_state(),
        source="test",
        snapshot_fingerprint="F1",
        state_fingerprint="F2",
    )
    assert payload["decision_start_fingerprint"] == "F1"
    assert payload["state_fingerprint"] == "F2"


def test_decision_projection_cached_state_fingerprint_matches_the_seal(
    monkeypatch, tmp_path
):
    from domain import profile as profile_domain

    uid = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="apple",
        skill="recall",
        assessed_skill="recall",
        success=True,
        served_difficulty="lexical:3",
        observed_task_difficulty="lexical:3",
        occurred_at="2026-01-01T07:00:00+00:00",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="apple",
        skill="recall",
        assessed_skill="recall",
        success=True,
        served_difficulty="lexical:3",
        observed_task_difficulty="lexical:3",
        occurred_at="2026-01-02T07:00:00+00:00",
    )
    asyncio.run(profile_domain.get_profile_summary(uid))
    payload = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert payload["source"] == "cached"
    # En el camino cached, la huella del estado es el sello de la caché fresca,
    # que coincide con la huella de inicio (no hay evidencia nueva en medio).
    assert payload["state_fingerprint"] == payload["decision_start_fingerprint"]
    assert payload["state_fingerprint"] != ""


def test_decision_projection_recomputed_state_fingerprint_is_the_seal(
    monkeypatch, tmp_path
):
    from repositories import profile as profile_repo

    uid = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="apple",
        skill="recall",
        assessed_skill="recall",
        success=True,
        served_difficulty="lexical:3",
        observed_task_difficulty="lexical:3",
        occurred_at="2026-01-01T07:00:00+00:00",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="apple",
        skill="recall",
        assessed_skill="recall",
        success=True,
        served_difficulty="lexical:3",
        observed_task_difficulty="lexical:3",
        occurred_at="2026-01-02T07:00:00+00:00",
    )
    # Caché legacy sin sello: fuerza el recálculo.
    profile_repo.set_skill_state(
        uid,
        json.dumps(skill_state_service.empty_skill_state(), sort_keys=True),
    )
    payload = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert payload["source"] == "recomputed"
    # La huella del estado es el sello del recálculo (no vacía).
    assert payload["state_fingerprint"] != ""
    # Y coincide con la huella de inicio (sin carrera en este test).
    assert payload["state_fingerprint"] == payload["decision_start_fingerprint"]


# ---------------------------------------------------------------------------
# E · Decision Provenance
# ---------------------------------------------------------------------------


def test_record_decision_persists_an_append_only_row(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    row = decision_records_repo.record_decision(
        uid,
        target_id="apple",
        evidence_fingerprint="F1",
        decision_start_fingerprint="F1",
        state_fingerprint="F2",
        selected_skill="recall",
        selected_activity="recall",
        selected_reason="error_prone",
        p_success=0.2,
        p_success_source="task_empirical",
        expected_learning_value=0.64,
        candidates=[{"skill": "recall", "p_success": 0.2}],
        drivers={"measured": True},
    )
    assert row is not None
    assert row["policy_version"] == decision_records_repo.DECISION_POLICY_VERSION
    assert row["target_id"] == "apple"


def test_record_decision_returns_none_for_unknown_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert decision_records_repo.record_decision("nope") is None

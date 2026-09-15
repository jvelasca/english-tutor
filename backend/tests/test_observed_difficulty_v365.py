"""V3.65 — Observed Difficulty 3.0: P(éxito | alumno, tarea) empírica por pareja.

Hasta V3.64 el léxico devolvía SIEMPRE `success_rate = 1.0`: `list_observed_rows`
filtraba `success = 1` y `_lexicon_rows` fijaba `success = True`. La capa empírica
de V3.63 declaraba la dificultad pero nunca el RESULTADO (P(éxito)).

V3.65 cierra ese hueco con tres piezas aditivas:

- **telemetría completa** (`list_attempt_rows`): éxitos Y fallos, con identidad de
  ítem (`target_id`/`surface_form`), sin tocar `list_observed_rows`;
- **identidad de tarea** en la fila canónica (`target_id`) y fallos léxicos que
  ahora sí entran como INTENTOS en el estado (la puerta espaciada sigue leyendo
  SOLO `success`);
- **estimador puro** `empirical_success(rows)` (por clave de tarea, con la MISMA
  puerta espaciada de V3.54) y su **seam aditivo** en la Decision Projection
  (`empirical_success` por celda) y en el Planner 3.0 (parámetro opcional que,
  cuando existe, gobierna `p_success`).

Invariantes fijadas por los ficheros de guard que NO se tocan: pureza del planner
y de `observed_difficulty.py`, degradación byte-idéntica sin estimación, y la
subcadena `skill_state` fuera del camino de decisión.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from domain import decision as decision_domain
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import decision_projection as projection
from services import fsrs, lexicon, observed_difficulty, planner
from services import skill_state as skill_state_service
from services.evidence import LEXICAL_SKILLS

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
    served: str = "lexical:4",
    earned: str = "lexical:4",
    success: bool = True,
    target_id: str = "river",
    surface_form: str = "river",
    activity_id: str = "",
    row_id: str = "1",
    support_level: str = "independent",
    error_type: str = "",
    context_instance: str = "",
) -> dict:
    """Fila del ledger léxico como la entrega `list_attempt_rows` (éxitos Y fallos)."""
    return {
        "id": row_id,
        "occurred_at": f"{day}T10:00:00+00:00",
        "skill": skill,
        "assessed_skill": assessed or skill,
        "success": 1 if success else 0,
        "target_id": target_id,
        "surface_form": surface_form,
        "served_difficulty": served,
        "observed_task_difficulty": earned,
        "observed_difficulty": served,
        "support_level": support_level,
        "response_time_ms": None,
        "error_type": error_type,
        "context_instance": context_instance,
        "activity_id": activity_id,
    }


def _rows(*rows: dict) -> list[dict]:
    return skill_state_service.skill_state_sources(lexicon=list(rows))


def _seed_evidence(uid: str, skill: str, days: list[str], load: str) -> None:
    for day in days:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill=skill,
            assessed_skill=skill,
            success=True,
            served_difficulty=load,
            observed_task_difficulty=load,
            occurred_at=f"{day}T07:00:00+00:00",
        )


def _seed_word(uid: str, word: str, *, cefr: str = "B1") -> None:
    vocabulary_repo.seed_curriculum_items(
        uid,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(uid, [word])


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=days_ago)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


# ---------------------------------------------------------------------------
# A · El fallo léxico entra en la tasa empírica (premisa 12: falla en V3.64)
# ---------------------------------------------------------------------------


def test_lexicon_empirical_rate_counts_failures():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(
            day="2026-01-02", earned="", success=False, row_id="2"
        ),
    )
    # La fila canónica incluye el INTENTO fallido: la tasa ya no es 1.0.
    assert len(rows) == 2
    assert [row["success"] for row in rows] == [True, False]
    assert [row["target_id"] for row in rows] == ["river", "river"]
    difficulty = observed_difficulty.observed_task_difficulty_2(rows)
    assert difficulty["success_rate"] == round(1 / 2, 3)
    assert difficulty["success_rate"] < 1.0


def test_state_confidence_counts_lexicon_failures():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(day="2026-01-02", earned="lexical:4", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", earned="", success=False, row_id="3"
        ),
    )
    state = skill_state_service.skill_state(rows)
    entry = state["vocabulary"][""]
    assert entry["samples"] == 2
    assert entry["observations"] == 3
    assert entry["confidence"] == round(2 / 3, 3)
    # La puerta espaciada NO se rompe: sigue leyendo SOLO los éxitos.
    assert entry["days"] == 2
    assert entry["dimensions"] == {"lexical": 4}


# ---------------------------------------------------------------------------
# B · Estimador puro `empirical_success`
# ---------------------------------------------------------------------------


def test_empirical_success_groups_by_task_and_reuses_the_spaced_gate():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(
            day="2026-01-02", earned="", success=False, row_id="2"
        ),
        _lexicon_ledger(day="2026-01-03", earned="lexical:4", row_id="3"),
    )
    estimates = observed_difficulty.empirical_success(rows)
    assert len(estimates) == 1
    value = next(iter(estimates.values()))
    assert value["attempts"] == 3
    assert value["successes"] == 2
    assert value["p_success"] == round(2 / 3, 3)
    assert value["days"] == 2


def test_empirical_success_distinguishes_items_and_served_difficulty():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", target_id="river", row_id="1"),
        _lexicon_ledger(day="2026-01-02", target_id="river", row_id="2"),
        _lexicon_ledger(day="2026-01-01", target_id="stone", row_id="3"),
        _lexicon_ledger(day="2026-01-02", target_id="stone", row_id="4"),
    )
    estimates = observed_difficulty.empirical_success(rows)
    # Dos ítems distintos, misma dificultad servida: dos claves.
    assert len(estimates) == 2
    for value in estimates.values():
        assert value["p_success"] == 1.0
        assert value["attempts"] == 2


def test_empirical_success_without_spaced_sample_declares_nothing():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(
            day="2026-01-01", earned="", success=False, row_id="2"
        ),
    )
    assert observed_difficulty.empirical_success(rows) == {}


def test_empirical_success_is_deterministic_and_pure():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(day="2026-01-02", earned="lexical:4", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", earned="", success=False, row_id="3"
        ),
    )
    first = observed_difficulty.empirical_success(rows)
    second = observed_difficulty.empirical_success(rows)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # El módulo puro no lee reloj, aleatoriedad ni I/O.
    source = (_BACKEND / "services" / "observed_difficulty.py").read_text("utf-8")
    for forbidden in (
        "import time",
        "import datetime",
        "import random",
        "hash(",
        "open(",
        "sqlite",
        "requests",
    ):
        assert forbidden not in source, forbidden


def test_empirical_p_success_is_bounded():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(day="2026-01-02", earned="lexical:4", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", earned="", success=False, row_id="3"
        ),
    )
    for value in observed_difficulty.empirical_success(rows).values():
        assert 0.0 <= value["p_success"] <= 1.0


# ---------------------------------------------------------------------------
# C · Seam aditivo en la Decision Projection
# ---------------------------------------------------------------------------


def test_projection_cell_exposes_the_empirical_success():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", earned="lexical:4", row_id="1"),
        _lexicon_ledger(day="2026-01-02", earned="lexical:4", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", earned="", success=False, row_id="3"
        ),
    )
    cell = projection.project(skill_state_service.skill_state(rows))[
        "vocabulary"
    ][""]
    empirical = cell["empirical_success"]
    assert empirical["attempts"] == 3
    assert empirical["successes"] == 2
    assert empirical["p_success"] == round(2 / 3, 3)
    assert empirical["days"] == 2
    assert empirical["declared"] is True


def test_empirical_success_by_skill_maps_the_lexical_axes():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", skill="recall", row_id="1"),
        _lexicon_ledger(day="2026-01-02", skill="recall", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", skill="recall", success=False, row_id="3"
        ),
    )
    proj = projection.project(skill_state_service.skill_state(rows))
    by_skill = projection.empirical_success_by_skill(proj)
    assert set(by_skill) == set(LEXICAL_SKILLS)
    assert by_skill["recall"]["p_success"] == round(2 / 3, 3)
    # Un eje sin muestra no declara estimación.
    assert by_skill["written_production"] == {}


def test_project_state_payload_is_additive_with_empirical_success():
    rows = _rows(
        _lexicon_ledger(day="2026-01-01", skill="recall", row_id="1"),
        _lexicon_ledger(day="2026-01-02", skill="recall", row_id="2"),
        _lexicon_ledger(
            day="2026-01-03", skill="recall", success=False, row_id="3"
        ),
    )
    payload = decision_domain.project_state(
        skill_state_service.skill_state(rows), source="test"
    )
    assert set(payload["empirical_success"]) == set(LEXICAL_SKILLS)
    assert payload["empirical_success"]["recall"]["p_success"] == round(2 / 3, 3)
    # Todas las claves de V3.64 siguen presentes.
    assert set(payload["capacity_by_skill"]) == set(LEXICAL_SKILLS)
    assert set(payload["skill_values"]) == set(LEXICAL_SKILLS)
    assert set(payload["drivers"]) == set(LEXICAL_SKILLS)


# ---------------------------------------------------------------------------
# D · Seam aditivo en el planner
# ---------------------------------------------------------------------------


def test_expected_learning_value_uses_empirical_p_success_when_provided():
    signals = {"forgetting": 1.0}
    base = planner.expected_learning_value(
        signals,
        task_difficulty={"lexical": 3},
        learner_capacity={"lexical": 3},
    )
    assert base["p_success"] == 0.55  # success_probability(margin=0)
    assert "p_success_empirical" not in base

    empirical = planner.expected_learning_value(
        signals,
        task_difficulty={"lexical": 3},
        learner_capacity={"lexical": 3},
        empirical_success={"p_success": 0.8},
    )
    assert empirical["p_success"] == 0.8
    assert empirical["p_success_empirical"] is True
    assert empirical["margin"] == 0  # el margen se sigue midiendo igual


def test_expected_learning_value_ignores_an_invalid_estimate():
    signals = {"forgetting": 1.0}
    base = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 3}
    )
    for bad in ("nope", {"p_success": "x"}, {"p_success": 5.0}, []):
        payload = planner.expected_learning_value(
            signals,
            task_difficulty={"lexical": 3},
            learner_capacity={"lexical": 3},
            empirical_success=bad,
        )
        assert payload == base


def test_select_task_by_elv_is_byte_identical_without_the_estimate():
    matrix = {"production": True}
    evidence = {"error_types": {"wrong_word": 2}, "skill_successes": {"recall": 2}}
    signals = planner.planned_signals(evidence, matrix)
    # Sin la estimación: byte-idéntico a V3.64 (misma tarea, sin clave nueva).
    chosen = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={"recall": {"lexical": 3}},
        task_difficulty={"lexical": 4},
    )
    assert set(chosen) == {"skill", "activity", "reason", "support_level"}
    assert "decision" not in chosen


def test_select_task_by_elv_injects_the_estimate_into_the_decision():
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
    )
    decision = planned["decision"]
    assert decision["p_success_empirical"] is True
    assert decision["p_success"] == 0.8
    assert decision["margin"] == -1  # el margen declarado no cambia


# ---------------------------------------------------------------------------
# E · Cableado (proyección → planner) y no-regresión de guardas
# ---------------------------------------------------------------------------


def test_lexicon_wires_the_empirical_success_from_the_projection(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "river", cefr="B1")
    vocabulary_repo.record_production(uid, ["river"], channel="writing")
    vocabulary_repo.record_recalls(uid, ["river"])
    for _ in range(2):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            success=False,
            error_type="wrong_word",
        )
    _seed_evidence(uid, "recall", ["2026-01-01", "2026-01-02"], "lexical:3")
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)
    payload = asyncio.run(
        decision_domain.decision_projection(uid, level="", now=NOW)
    )

    item = lexicon.review_queue_item(
        {
            "word": "river",
            "cefr": "B1",
            "exposure_count": 3,
            "writing_prod": 1,
            "recall_successes": 2,
            "recall_days": 2,
        },
        {
            "target_id": "river",
            "due_at": "2026-09-12T10:00:00+00:00",
            "state": "review",
            "stability": 5.0,
            "last_review_at": "2026-09-09T10:00:00+00:00",
        },
        now=NOW,
        evidence={
            "error_types": {"wrong_word": 2},
            "skill_successes": {"recall": 2},
        },
        projection=payload,
    )
    # La estimación empírica (2 éxitos + 2 fallos → p=0.5) gobierna el p_success.
    assert item["task"]["activity"] == "recall"
    decision = item["decision"]
    assert decision["projected"] is True
    assert decision["p_success_empirical"] is True
    assert decision["p_success"] == round(2 / 4, 3)


def test_guarded_decision_modules_still_ignore_the_new_state():
    guarded = (
        "services/planner.py",
        "services/difficulty.py",
        "services/transfer.py",
        "services/lexicon.py",
        "services/expected_learning_value.py",
        "domain/learner_state.py",
        "domain/vocabulary.py",
    )
    for relative in guarded:
        path = _BACKEND / relative
        if not path.exists():
            continue
        assert "skill_state" not in path.read_text(encoding="utf-8"), relative


def test_list_attempt_rows_reads_failures_and_identity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(uid, "recall", ["2026-01-01"], "lexical:3")
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="recall",
        assessed_skill="recall",
        success=False,
        served_difficulty="lexical:3",
        occurred_at="2026-01-02T07:00:00+00:00",
    )
    attempts = evidence_repo.list_attempt_rows(uid)
    assert len(attempts) == 2
    assert {row["success"] for row in attempts} == {0, 1}
    assert all(row["target_id"] == "river" for row in attempts)
    assert all("surface_form" in row for row in attempts)
    # El lector de V3.53/V3.54 no se toca: sigue filtrando éxitos.
    assert len(evidence_repo.list_observed_rows(uid)) == 1


def test_canonical_sources_builds_the_state_with_failures(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(uid, "recall", ["2026-01-01", "2026-01-02"], "lexical:3")
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="recall",
        assessed_skill="recall",
        success=False,
        served_difficulty="lexical:3",
        occurred_at="2026-01-03T07:00:00+00:00",
    )
    sources = asyncio.run(decision_domain.canonical_sources(uid))
    # La fuente legacy sigue siendo solo éxitos (V3.53/V3.54 intacta)...
    assert len(sources["lexicon"]) == 2
    # ...pero el estado unificado cuenta el fallo como intento.
    state = skill_state_service.skill_state(sources["state_rows"])
    entry = state["vocabulary"][""]
    assert entry["observations"] == 3
    assert entry["confidence"] == round(2 / 3, 3)

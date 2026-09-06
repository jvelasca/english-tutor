"""Tests puros del servicio de review por unidad (V3.16, Fase A)."""

from __future__ import annotations

import pytest

from services import fsrs, unit_review
from services.curriculum import Lesson, Objective, ObjectiveCheck, Unit

NOW = "2026-03-01T10:00:00+00:00"


def _check(
    cid: str,
    *,
    skill: str = "grammar",
    options: tuple[str, ...] = ("alpha", "beta", "gamma"),
    correct: int = 0,
) -> ObjectiveCheck:
    return ObjectiveCheck(
        id=cid,
        skill=skill,
        prompt=f"prompt-{cid}",
        options=list(options),
        correct_index=correct,
    )


def _objective(
    oid: str,
    *,
    title: str = "",
    skill: str = "grammar",
    checks: tuple[ObjectiveCheck, ...] = (),
) -> Objective:
    return Objective(
        id=oid,
        can_do=f"can-do {oid}",
        title=title or oid,
        skills=[skill],
        checks=list(checks),
    )


def _unit(
    uid: str,
    objectives: list[Objective],
    *,
    title: str = "",
) -> Unit:
    return Unit(
        id=uid,
        title=title or uid,
        order=1,
        lessons=[
            Lesson(
                id=f"{uid}-les-{i}",
                title=f"lesson {i}",
                order=i + 1,
                objectives=[obj],
            )
            for i, obj in enumerate(objectives)
        ],
    )


def _sample_unit() -> Unit:
    """Unidad con 4 objetivos y checks distribuidos para muestreo balanceado."""
    objs = [
        _objective(
            "o1",
            title="Greetings",
            skill="vocabulary",
            checks=(
                _check("c1", skill="vocabulary", correct=1),
                _check("c2", skill="vocabulary",
                       options=("a", "b", "c", "d"), correct=2),
                _check("c3", skill="grammar"),
            ),
        ),
        _objective(
            "o2",
            title="Present simple",
            checks=(
                _check("c4", correct=1),
                _check("c5", options=("a", "b", "c", "d"), correct=0),
                _check("c6", correct=2),
            ),
        ),
        _objective(
            "o3",
            title="Plurals",
            checks=(
                _check("c7", options=("a", "b", "c", "d"), correct=3),
                _check("c8", correct=0),
            ),
        ),
        _objective(
            "o4",
            title="Questions",
            checks=(
                _check("c9", options=("a", "b", "c", "d"), correct=1),
                _check("c10", correct=2),
                _check("c11", correct=0),
            ),
        ),
    ]
    return _unit("u1", objs)


# --- Constantes -------------------------------------------------------------


def test_constants():
    assert unit_review.UNIT_REVIEW_WINDOWS_DAYS == (7, 30, 90)
    assert unit_review.MICRO_REVIEW_PASS_RATIO == 0.7
    assert unit_review.MICRO_REVIEW_TARGET_ITEMS == 8
    assert unit_review.MICRO_REVIEW_MAX_PER_OBJECTIVE == 2
    assert unit_review.UNIT_REVIEW_SOURCE == "unit_micro_review"


# --- Estados de ventana -----------------------------------------------------


def test_window_upcoming_and_due_now_with_fixed_now():
    anchor = "2026-01-01T00:00:00+00:00"
    # now antes del due (7 días) → upcoming.
    before = "2026-01-07T00:00:00+00:00"
    assert unit_review.window_due_at(anchor, 7, now=before) == {
        "window_days": 7,
        "due_at": "2026-01-08T00:00:00+00:00",
        "state": "upcoming",
    }
    # now == due → due_now.
    at_due = "2026-01-08T00:00:00+00:00"
    assert unit_review.window_due_at(anchor, 7, now=at_due)["state"] == "due_now"
    # now después → due_now.
    after = "2026-01-20T00:00:00+00:00"
    assert unit_review.window_due_at(anchor, 7, now=after)["state"] == "due_now"
    # ventana 30 días todavía upcoming.
    assert (
        unit_review.window_due_at(anchor, 30, now=after)["state"] == "upcoming"
    )


def test_window_passed_and_failed_from_attempts():
    anchor = "2026-01-01T00:00:00+00:00"
    attempt_passed = [
        {
            "unit_id": "u1",
            "window_days": 7,
            "accuracy": 0.875,
            "created_at": "2026-01-10T00:00:00+00:00",
        }
    ]
    assert unit_review.window_due_at(anchor, 7, now=NOW, attempts=attempt_passed)[
        "state"
    ] == "passed"
    attempt_failed = [
        {
            "unit_id": "u1",
            "window_days": 7,
            "accuracy": 0.5,
            "created_at": "2026-01-10T00:00:00+00:00",
        }
    ]
    assert unit_review.window_due_at(anchor, 7, now=NOW, attempts=attempt_failed)[
        "state"
    ] == "failed"
    # El intento fallido más reciente manda aunque haya uno superado antes.
    mixed = [
        {
            "unit_id": "u1",
            "window_days": 7,
            "accuracy": 0.875,
            "created_at": "2026-01-09T00:00:00+00:00",
        },
        {
            "unit_id": "u1",
            "window_days": 7,
            "accuracy": 0.5,
            "created_at": "2026-01-11T00:00:00+00:00",
        },
    ]
    assert (
        unit_review.window_due_at(anchor, 7, now=NOW, attempts=mixed)["state"]
        == "failed"
    )
    # Los intentos de OTRAS ventanas no afectan.
    other = [
        {"window_days": 30, "accuracy": 0.9,
         "created_at": "2026-01-10T00:00:00+00:00"}
    ]
    assert (
        unit_review.window_due_at(anchor, 7, now=NOW, attempts=other)["state"]
        == "due_now"
    )


def test_window_due_at_keeps_anchor_fixed_after_grades():
    """D3: un grade no mueve la ventana; `due_at` es siempre anchor + días."""
    anchor = "2026-01-01T00:00:00+00:00"
    failed = [
        {"window_days": 7, "accuracy": 0.5,
         "created_at": "2026-01-08T00:00:00+00:00"}
    ]
    w = unit_review.window_due_at(
        anchor, 7, now="2026-01-25T00:00:00+00:00", attempts=failed
    )
    assert w["due_at"] == "2026-01-08T00:00:00+00:00"


# --- Completitud y ancla ----------------------------------------------------


def test_unit_completed_requires_all_objectives_mastered():
    unit = _sample_unit()
    ids = {"o1", "o2", "o3", "o4"}
    assert unit_review.unit_completed(unit, ids) is True
    assert unit_review.unit_completed(unit, ids - {"o4"}) is False
    assert unit_review.unit_completed(unit, set()) is False


def test_unit_completed_empty_unit_is_false():
    unit = _unit("u-empty", [])
    assert unit_review.unit_completed(unit, set()) is False


def test_unit_anchor_is_max_updated_at_or_none():
    assert unit_review.unit_anchor([]) is None
    rows = [
        {"objective_id": "o1", "updated_at": "2026-01-05T00:00:00+00:00"},
        {"objective_id": "o1", "updated_at": "2026-01-03T00:00:00+00:00"},
        {"objective_id": "o2", "updated_at": "2026-01-07T00:00:00+00:00"},
    ]
    assert unit_review.unit_anchor(rows) == "2026-01-07T00:00:00+00:00"
    rows_bad = [{"objective_id": "o1", "updated_at": "no-es-fecha"}]
    assert unit_review.unit_anchor(rows_bad) is None


def test_build_unit_review_plan_structure():
    unit = _sample_unit()
    rows = [
        {"objective_id": "o1", "updated_at": "2026-02-01T00:00:00+00:00"},
        {"objective_id": "o2", "updated_at": "2026-02-02T00:00:00+00:00"},
        {"objective_id": "o3", "updated_at": "2026-02-03T00:00:00+00:00"},
        {"objective_id": "o4", "updated_at": "2026-02-04T00:00:00+00:00"},
    ]
    plan = unit_review.build_unit_review_plan(
        unit=unit,
        unit_mastery_rows=rows,
        mastered_ids={"o1", "o2", "o3", "o4"},
        now="2026-03-01T00:00:00+00:00",
        level_id="a1",
        module_id="m1",
        module_title="Module",
        attempts=[],
    )
    assert plan["level_id"] == "a1"
    assert plan["unit_id"] == "u1"
    assert plan["title"] == "u1"
    assert plan["module_title"] == "Module"
    assert plan["objectives_total"] == 4
    assert plan["objectives_mastered"] == 4
    assert plan["completed"] is True
    assert plan["anchor"] == "2026-02-04T00:00:00+00:00"
    assert [w["window_days"] for w in plan["windows"]] == [7, 30, 90]
    # 2026-02-04 + 7 = 2026-02-11; now (marzo) ya lo superó → due_now.
    assert plan["windows"][0]["state"] == "due_now"
    # La ventana 90 aún no ha llegado.
    assert plan["windows"][2]["state"] == "upcoming"


def test_build_unit_review_plan_incomplete_unit_without_rows():
    unit = _sample_unit()
    plan = unit_review.build_unit_review_plan(
        unit=unit,
        unit_mastery_rows=[],
        mastered_ids={"o1"},
        now=NOW,
        level_id="a1",
    )
    assert plan["completed"] is False
    assert plan["objectives_mastered"] == 1
    assert plan["anchor"] is None
    assert plan["windows"] == []


# --- Muestreo determinista y balanceado -------------------------------------


def test_sample_is_deterministic_and_never_leaks_correct_index():
    unit = _sample_unit()
    a = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    b = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    assert a == b
    assert len(a) == 8  # unit tiene 11 checks: se llega al target
    for item in a:
        assert set(item) == {
            "item_id",
            "objective_id",
            "objective_title",
            "skill",
            "prompt",
            "options",
        }
        assert "correct_index" not in item


def test_sample_balance_by_objective_caps_at_two():
    unit = _sample_unit()
    sample = unit_review.sample_micro_review(
        unit=unit, user_id="u2", window_days=7, previous_failed_ids=[], now=NOW
    )
    counts: dict[str, int] = {}
    for item in sample:
        counts[item["objective_id"]] = counts.get(item["objective_id"], 0) + 1
    assert len(sample) <= unit_review.MICRO_REVIEW_TARGET_ITEMS
    assert all(v <= unit_review.MICRO_REVIEW_MAX_PER_OBJECTIVE for v in counts.values())
    # Con 4 objetivos y tope 2/objetivo la muestra cubre los 4.
    assert set(counts) == {"o1", "o2", "o3", "o4"}


def test_sample_changes_with_seed_but_retry_keeps_stable_failed_first():
    unit = _sample_unit()
    # Semilla distinta → orden/rotación distinta (determinista por semilla).
    one = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    two = unit_review.sample_micro_review(
        unit=unit, user_id="u2", window_days=7, previous_failed_ids=[], now=NOW
    )
    ids_a = [i["item_id"] for i in one]
    ids_b = [i["item_id"] for i in two]
    assert ids_a != ids_b or ids_a != sorted(ids_a)

    # Reintento de la MISMA ventana: fallidos primero y estables entre llamadas.
    failed = ["c4", "c7"]
    retry_a = unit_review.sample_micro_review(
        unit=unit,
        user_id="u1",
        window_days=7,
        previous_failed_ids=failed,
        now=NOW,
    )
    retry_b = unit_review.sample_micro_review(
        unit=unit,
        user_id="u1",
        window_days=7,
        previous_failed_ids=failed,
        now=NOW,
    )
    assert retry_a == retry_b
    retry_ids = [i["item_id"] for i in retry_a]
    # Los fallidos del último intento abren la sesión (orden estable por rotación).
    assert set(retry_ids[:2]) == {"c4", "c7"}
    assert all(
        retry_ids.index(iid) >= 2 for iid in retry_ids if iid not in {"c4", "c7"}
    )
    # Sin fallos previos la sesión de reintento prioriza y mantiene el tamaño.
    assert len(retry_a) == unit_review.MICRO_REVIEW_TARGET_ITEMS


def test_sample_never_repeats_an_item():
    unit = _sample_unit()
    sample = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=90, previous_failed_ids=[], now=NOW
    )
    ids = [i["item_id"] for i in sample]
    assert len(ids) == len(set(ids))


# --- Puntuación del micro-review --------------------------------------------


def test_score_micro_review_counts_and_aggregates_by_objective():
    unit = _sample_unit()
    sample = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    # Contestamos TODO correcto salvo un ítem concreto.
    answers = {}
    for item in sample:
        # correct_index se obtiene del modelo del currículo (solo en tests).
        check = next(
            c
            for o in unit.lessons
            for obj in o.objectives
            if obj.id == item["objective_id"]
            for c in obj.checks
            if c.id == item["item_id"]
        )
        answers[item["item_id"]] = check.correct_index
    # Fallamos deliberadamente el primer ítem.
    first = sample[0]["item_id"]
    answers[first] = (answers[first] + 1) % 3

    result = unit_review.score_micro_review(
        answers=answers, unit=unit, sample=sample
    )
    assert result["total"] == len(sample)
    assert result["correct"] == len(sample) - 1
    assert result["accuracy"] == round((len(sample) - 1) / len(sample), 3)
    assert result["passed"] is True  # 7/8 = 0.875 >= 0.7
    assert sum(b["total"] for b in result["per_objective"]) == len(sample)
    assert sum(b["correct"] for b in result["per_objective"]) == result["correct"]
    assert len(result["items"]) == len(sample)


def test_score_micro_review_fails_below_threshold_and_missing_counts_wrong():
    unit = _unit(
        "u-small",
        [
            _objective(
                "os1",
                title="Only",
                checks=(_check("cs1", correct=1), _check("cs2", correct=0)),
            )
        ],
    )
    sample = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    assert len(sample) == 2
    result = unit_review.score_micro_review(
        answers={"cs1": 1}, unit=unit, sample=sample  # cs2 sin responder
    )
    assert result["total"] == 2
    assert result["correct"] == 1
    assert result["accuracy"] == 0.5
    assert result["passed"] is False
    assert [b["correct"] for b in result["per_objective"]] == [1]


def test_score_micro_review_rejects_unknown_or_out_of_range_answers():
    """M2 (puro): `score_micro_review` valida `answers` contra la muestra — clave
    ajena o índice fuera de rango lanzan `unit_review.invalid_answers`."""
    unit = _unit(
        "u-m2",
        [
            _objective(
                "om2",
                title="Only",
                checks=(_check("cm2", correct=1), _check("cm3", correct=0)),
            )
        ],
    )
    sample = unit_review.sample_micro_review(
        unit=unit, user_id="u1", window_days=7, previous_failed_ids=[], now=NOW
    )
    assert {i["item_id"] for i in sample} == {"cm2", "cm3"}

    # Clave que no está en la muestra.
    with pytest.raises(ValueError, match="unit_review.invalid_answers"):
        unit_review.score_micro_review(
            answers={"cm2": 1, "cm9": 0}, unit=unit, sample=sample
        )
    # Índice igual al nº de opciones (fuera de rango).
    cm2 = next(i for i in sample if i["item_id"] == "cm2")
    with pytest.raises(ValueError, match="unit_review.invalid_answers"):
        unit_review.score_micro_review(
            answers={"cm2": len(cm2["options"])}, unit=unit, sample=sample
        )
    # Índice negativo.
    with pytest.raises(ValueError, match="unit_review.invalid_answers"):
        unit_review.score_micro_review(
            answers={"cm2": -1}, unit=unit, sample=sample
        )


def test_grade_for_accuracy_delegates_to_fsrs():
    assert unit_review.grade_for_accuracy(0.2) == fsrs.grade_from_score(0.2)
    assert unit_review.grade_for_accuracy(0.95) == fsrs.GRADE_EASY
    assert unit_review.grade_for_accuracy(0.7) == fsrs.GRADE_GOOD  # >= 0.7 → good
    assert unit_review.grade_for_accuracy(0.69) == fsrs.GRADE_HARD


# --- why_for_objective (Fase B) ---------------------------------------------


def test_why_for_objective_maps_windows_and_maintenance():
    unit = _sample_unit()
    # Ventanas no superadas en orden ascendente: 7 pendiente → unit-window-7.
    assert fsrs.why_for_objective(unit, {"windows": []}) == "unit-maintenance"
    assert fsrs.why_for_objective(
        unit,
        {
            "windows": [
                {"window_days": 90, "state": "upcoming"},
                {"window_days": 30, "state": "passed"},
                {"window_days": 7, "state": "failed"},
            ]
        },
    ) == "unit-window-7"
    assert fsrs.why_for_objective(
        unit,
        {
            "windows": [
                {"window_days": 7, "state": "passed"},
                {"window_days": 30, "state": "due_now"},
                {"window_days": 90, "state": "upcoming"},
            ]
        },
    ) == "unit-window-30"
    # Las tres superadas → maintenance.
    assert fsrs.why_for_objective(
        unit,
        {
            "windows": [
                {"window_days": 7, "state": "passed"},
                {"window_days": 30, "state": "passed"},
                {"window_days": 90, "state": "passed"},
            ]
        },
    ) == "unit-maintenance"


def test_why_for_objective_orders_by_window_days_not_by_input():
    unit = _sample_unit()
    # Entrada desordenada: elige la menor ventana no superada.
    why = fsrs.why_for_objective(
        unit,
        {
            "windows": [
                {"window_days": 90, "state": "upcoming"},
                {"window_days": 7, "state": "passed"},
                {"window_days": 30, "state": "due_now"},
            ]
        },
    )
    assert why == "unit-window-30"

"""Auditoría V3.70 · Eje 5: instrumentos de nivelación.

Pinnean lo **medido** en `docs/audit/AE-PED-INSTRUMENTOS.md` y en
`docs/audit/generated/assessment-instruments.json`.

Se fijan tanto las **propiedades positivas** que no deben perderse (los tres
estimadores de banda coinciden; el banco de placement no tiene huecos de
dificultad) como los **defectos medidos** (el criterio de parada inalcanzable, el
sesgo de forma, el examen de B1 plano y los cuatro niveles sin examen).
"""

from __future__ import annotations

import math

from services import academy, adaptive, cefr, cefr_descriptors, course
from services.curriculum import CEFR_ORDER, load_assessments

# Techo de información de un ítem 1PL: p(1-p) <= 0.25.
MAX_ITEM_INFORMATION = 0.25


def _grid() -> list[float]:
    return [round(step * 0.25, 2) for step in range(2, 25)]


def test_placement_stop_rule_is_unreachable_with_the_declared_model() -> None:
    """Pide SE < 0.5 y la mejor cota con 8 ítems es 0.7071."""
    assert academy.MAX_PLACEMENT_ITEMS == 8
    assert academy.PLACEMENT_MIN_ITEMS == 4
    assert academy.PLACEMENT_SE_THRESHOLD == 0.5
    best_case = 1.0 / math.sqrt(
        academy.MAX_PLACEMENT_ITEMS * MAX_ITEM_INFORMATION
    )
    assert round(best_case, 4) == 0.7071
    assert best_case > academy.PLACEMENT_SE_THRESHOLD


def test_placement_bank_has_four_items_per_difficulty() -> None:
    """Propiedad positiva: el banco cubre 1..6 sin huecos."""
    placement = load_assessments().placement
    assert len(placement.items) == 24
    for difficulty in range(1, 7):
        assert sum(
            1 for item in placement.items if item.difficulty == difficulty
        ) == 4


def test_placement_has_form_bias() -> None:
    """La mitad del banco tiene la correcta como opción más larga ÚNICA."""
    placement = load_assessments().placement
    lengths = [
        [len(option) for option in item.options]
        for item in placement.items
    ]
    strictly_longest = sum(
        1
        for item, sizes in zip(placement.items, lengths, strict=True)
        if sizes[item.correct_index] == max(sizes) and sizes.count(max(sizes)) == 1
    )
    at_least_longest = sum(
        1
        for item, sizes in zip(placement.items, lengths, strict=True)
        if sizes[item.correct_index] == max(sizes)
    )
    assert strictly_longest == 12
    assert at_least_longest == 18
    positions = [item.correct_index for item in placement.items]
    assert positions.count(1) == 17
    assert 3 not in positions


def test_b1_exam_does_not_scale_above_a1_exam() -> None:
    """Los dos exámenes tienen TODOS sus ítems en dificultad 1."""
    exams = load_assessments().exams
    for exam_id in ("a1", "b1"):
        difficulties = {item.difficulty for item in exams[exam_id].items}
        assert difficulties == {1}
    assert len(exams["a1"].items) == 10
    assert len(exams["b1"].items) == 12


def test_only_a1_and_b1_have_final_exams() -> None:
    exams = load_assessments().exams
    assert set(exams) == {"a1", "b1"}
    assert set(CEFR_ORDER) - {level.upper() for level in exams} == {
        "A2",
        "B2",
        "C1",
        "C2",
    }


def test_exam_min_per_skill_is_declared() -> None:
    exams = load_assessments().exams
    assert exams["a1"].min_per_skill == 0.75
    assert exams["b1"].min_per_skill == 0.75


def test_remediation_banks_are_declared_and_reading_is_the_smallest() -> None:
    remediation = load_assessments().remediation
    sizes = {name: len(ids) for name, ids in remediation.items()}
    assert sizes == {
        "grammar": 6,
        "vocabulary": 6,
        "reading": 3,
        "listening": 5,
        "speaking": 6,
    }
    assert min(sizes, key=sizes.get) == "reading"


def test_unit_gate_thresholds_are_pinned() -> None:
    assert course.UNIT_GATE_THRESHOLDS == {
        "vocabulary": 0.8,
        "grammar": 0.8,
        "listening": 0.75,
        "speaking": 0.7,
    }
    assert len(course.UNIT_SECTIONS) == 7


def test_three_band_estimators_agree_on_the_whole_grid() -> None:
    """Propiedad positiva: el mismo corte de banda en los tres sitios."""
    for numeric in _grid():
        score = max(0.0, min(1.0, (numeric - 1.0) / 5.0))
        assert (
            adaptive.numeric_to_level(numeric)
            == academy.theta_to_level(numeric)
            == cefr.heuristic_band(score)
        )


def test_plus_bands_are_declared_but_never_emitted() -> None:
    """La escalera declara sub-bandas y ningun estimador las produce."""
    plus_bands = {band for band in cefr_descriptors.CEFR_LADDER if band.endswith("+")}
    assert plus_bands == {"a2+", "b1+", "b2+"}
    emitted = set()
    for numeric in _grid():
        score = max(0.0, min(1.0, (numeric - 1.0) / 5.0))
        emitted.add(adaptive.numeric_to_level(numeric))
        emitted.add(academy.theta_to_level(numeric))
        emitted.add(cefr.heuristic_band(score))
    assert emitted == {"A1", "A2", "B1", "B2", "C1", "C2"}
    assert not emitted & {band.upper() for band in plus_bands}
    # La escalera sí sabe expresarlas cuando se le pide directamente.
    assert cefr_descriptors.band_for_numeric(3.6) == "b1+"

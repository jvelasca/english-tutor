"""Auditoría V3.70 · Eje 4: validez de la afirmación de maestría.

Pinnean lo **medido** en `docs/audit/AD-PED-MAESTRIA.md` y en
`docs/audit/generated/mastery-claims.json`.

La pregunta protegida es «¿«demostrado» significa lo que dice?». Los tests
fijan: (a) las propiedades **correctas** que no deben perderse (sin evidencia no
se afirma nada, el gate espaciado, la escalera de transferencia), y (b) los
**huecos medidos** (tres registros de modalidades con tamaños distintos,
destrezas que no pueden acreditar, `novel` declarado e inerte, filas sin objetivo
que no acreditan éxito).
"""

from __future__ import annotations

from services import (
    cefr_matrix,
    competence,
    curriculum,
    evidence_depth,
    learner_skill,
    mastery,
    skill_axis,
    skill_state,
    speaking,
)

EXPECTED_STATES = ("not_started", "developing", "functional", "demonstrated")


def test_mastery_matrix_and_channel_registers_do_not_coincide() -> None:
    """Tres registros del mismo concepto, con tres tamaños distintos."""
    matrix = cefr_matrix.load_matrix()
    matrix_skills = {
        skill for level in matrix.levels.values() for skill in level.skills
    }
    assert len(mastery.MASTERY_SKILLS) == 9
    assert len(matrix_skills) == 8
    assert len(skill_state.MODALITY_CHANNEL) == 7
    assert set(mastery.MASTERY_SKILLS) - set(skill_state.MODALITY_CHANNEL) == {
        "interaction",
        "mediation",
    }
    assert set(mastery.MASTERY_SKILLS) - matrix_skills == {"pronunciation"}


def test_interaction_and_mediation_cannot_earn_evidence() -> None:
    """Declaradas evaluables y exigidas por la matriz, sin ninguna vía de evidencia."""
    for modality in ("interaction", "mediation"):
        assert modality in mastery.MASTERY_SKILLS
        assert modality not in skill_state.MODALITY_CHANNEL
        assert skill_axis.COMPETENCES_BY_MODALITY[modality] == ()


def test_novel_signal_exists_but_the_matrix_never_requires_it() -> None:
    """El emisor de `novel` existe desde V3.26; la matriz lo exige con valor 0."""
    assert speaking.NOVEL_MIN_CEFR == "B2"
    assert speaking.mission_evidence_kind(
        first_ever=True, cefr_target="B2"
    ) == "novel"
    assert speaking.mission_evidence_kind(
        first_ever=False, cefr_target="C1"
    ) == "familiar"
    assert speaking.mission_evidence_kind(
        first_ever=True, cefr_target="A2"
    ) == "familiar"
    matrix = cefr_matrix.load_matrix()
    total = sum(
        req.novel_required
        for level in matrix.levels.values()
        for req in level.skills.values()
    )
    assert total == 0


def test_transfer_requirement_grows_with_level() -> None:
    matrix = cefr_matrix.load_matrix()

    def transfer(level_id: str) -> set[int]:
        level = matrix.levels[level_id]
        return {req.transfer_required for req in level.skills.values()}

    assert transfer("A1") == {0}
    assert transfer("A2") == {0}
    assert transfer("B1") == {1}
    assert transfer("B2") == {2}
    assert transfer("C1") == {3}
    assert transfer("C2") == {4}


def test_spacing_gate_is_two_samples_two_days() -> None:
    assert learner_skill.OBSERVED_MIN_SAMPLES == 2
    assert learner_skill.OBSERVED_MIN_DAYS == 2


def test_no_evidence_means_not_started_and_no_band() -> None:
    """Propiedad anti-sobreafirmación: sin evidencia no se afirma nada."""
    rows = competence.competence_states([], "A1")
    assert len(rows) == len(mastery.MASTERY_SKILLS)
    for row in rows:
        assert row["state"] == "not_started"
        assert row["demonstrated"] is False
        assert row["estimated_band"] == "—"
    assert tuple(competence.STATE_ORDER) == EXPECTED_STATES


def test_evidence_depth_without_samples_is_low() -> None:
    report = evidence_depth.evidence_depth_report("grammar", "A1", 0)
    assert report["depth"] == "low"
    assert report["meets_matrix"] is False


def test_production_skills_are_the_three_declared() -> None:
    """R5: reconocimiento no demuestra. Y vocabulary es apoyo con tope."""
    assert tuple(competence.PRODUCTION_SKILLS) == (
        "grammar",
        "speaking",
        "writing",
    )
    assert tuple(competence.SUPPORT_SKILLS) == ("vocabulary",)
    assert "controlled_production" in evidence_depth.PRODUCTION_ITEM_TYPES


def test_rows_without_objective_do_not_accredit_success() -> None:
    """F-K3 medido: `result 1.0` acredita o no según el `objective_id`."""
    index = skill_axis.objective_competences_index()
    objective = next(
        obj
        for obj in curriculum.load_level("a1").objectives()
        if "grammar" in obj.skills
    )
    base = {
        "skill": "grammar",
        "level_id": "a1",
        "item_type": "mcq",
        "evidence_kind": "familiar",
        "created_at": "2026-01-01T00:00:00Z",
        "result": 1.0,
    }
    with_objective = {**base, "id": "r1", "objective_id": objective.id}
    without_objective = {**base, "id": "r2", "objective_id": ""}
    rows = skill_state.skill_state_sources(
        academy=[with_objective, without_objective],
        objectives=index,
    )
    by_evidence = {row["evidence_id"]: row for row in rows}
    assert by_evidence["r1"]["success"] is True
    assert by_evidence["r2"]["success"] is False


def test_pronunciation_has_no_matrix_requirements() -> None:
    """La exclusión de pronunciation de la matriz es deliberada y se pinnea."""
    matrix = cefr_matrix.load_matrix()
    for level in matrix.levels.values():
        assert "pronunciation" not in level.skills

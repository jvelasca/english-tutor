"""Golden tests de la escalera Assessment 2.0 (auditoría D).

Ejecuta los casos de frontera y de min_per_skill fijados en
`tests/golden/assessment/thresholds.json`. El propósito es que el comportamiento
de los umbrales (y su documentación de "por qué 75 / por qué 70") no cambie por
accidente en el futuro.
"""
from __future__ import annotations

from golden import loader

from services import assessment_v2


def _scored(overall: float, skill_scores: dict[str, float]) -> dict:
    return {
        "skills": {
            skill: {"correct": 0, "total": 0, "score": score}
            for skill, score in skill_scores.items()
        },
        "correct": int(round(overall * 20)),
        "total": 20,
        "overall": overall,
    }


def test_boundary_cases_match_frozen_semantics():
    fixture = loader.load_json("assessment/thresholds")
    assert (
        fixture["thresholds"]
        == {k: v for k, v in assessment_v2.PASS_THRESHOLDS.items()}
    ), "PASS_THRESHOLDS cambió sin actualizar el golden"
    for case in fixture["boundary_cases"]:
        scored = _scored(case["overall"], case["skill_scores"])
        result = assessment_v2.evaluate(case["kind"], scored)
        assert result["passed"] is case["expect_passed"], (
            f"{case['id']}: passed={result['passed']} (esperado "
            f"{case['expect_passed']})"
        )


def test_level_min_per_skill_gate():
    fixture = loader.load_json("assessment/thresholds")
    for case in fixture["level_min_per_skill_cases"]:
        scored = _scored(case["overall"], case["skill_scores"])
        result = assessment_v2.evaluate(
            case["kind"], scored, min_per_skill=case["min_per_skill"]
        )
        assert result["passed"] is case["expect_passed"], case["id"]
        assert sorted(result["failed_skills"]) == sorted(
            case["expect_failed_skills"]
        ), case["id"]


def test_retention_delta_stable_ratio():
    fixture = loader.load_json("assessment/thresholds")
    for case in fixture["retention_delta_cases"]:
        result = assessment_v2.retention_delta(
            {"overall": case["initial"], "skills": {}},
            {"overall": case["delayed"], "skills": {}},
        )
        assert result["stable"] is case["expect_stable"], case["id"]
        if "expect_rate" in case:
            assert result["retention_rate"] == case["expect_rate"], case["id"]


def test_mastery_gate_counts():
    fixture = loader.load_json("assessment/thresholds")
    for case in fixture["mastery_gate_cases"]:
        result = assessment_v2.mastery_evidence_gate(case["counts"])
        assert result["met"] is case["expect_met"], case["id"]
        assert result["missing"] == case["expect_missing"], case["id"]

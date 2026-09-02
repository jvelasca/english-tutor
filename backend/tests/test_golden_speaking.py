"""Golden tests de Speaking Mission / scoring (auditoría C).

Fijan el comportamiento del motor de misión (criterios débiles, frontera 0.6,
drills, mejora attempt→retry) y el determinismo del scoring dado el mismo
evidence LLM. La variabilidad *entre* extracciones del LLM no es determinista y
se mide aparte con `scripts/eval_speaking_variability.py`.
"""
from __future__ import annotations

from golden import loader

from services import speaking, speaking_llm, speaking_mission


def test_weak_criteria_and_drills_match_golden():
    fixture = loader.load_json("speaking/mission_probes")
    for probe in fixture["probes"]:
        criteria = probe.get("criteria")
        if criteria is None:
            continue
        weak = speaking_mission.weak_criteria(criteria)
        assert weak == probe["expect"]["weak"], probe["id"]
        drills = speaking_mission.targeted_drills(weak)
        if "drill_count" in probe["expect"]:
            assert len(drills) == probe["expect"]["drill_count"], probe["id"]
        if "drill_criteria" in probe["expect"]:
            assert [d["criterion"] for d in drills] == probe["expect"][
                "drill_criteria"
            ], probe["id"]
        # El intento se evalúa sin lanzar (el LLM no puntúa).
        evaluation = speaking_mission.evaluate_attempt(
            overall=criteria.get("fluency"), criteria=criteria
        )
        assert evaluation["phase"] == "evaluation"


def test_weak_threshold_boundary_is_exactly_60():
    assert speaking_mission.MISSION_WEAK_THRESHOLD == 0.6
    fixture = loader.load_json("speaking/mission_probes")
    below = next(
        p for p in fixture["probes"] if p["id"] == "weak-threshold-below-60"
    )
    at = next(p for p in fixture["probes"] if p["id"] == "weak-threshold-at-60")
    assert speaking_mission.weak_criteria(below["criteria"]) == below["expect"]["weak"]
    assert speaking_mission.weak_criteria(at["criteria"]) == at["expect"]["weak"]


def test_improvement_detection():
    fixture = loader.load_json("speaking/mission_probes")
    positive = next(
        p for p in fixture["probes"] if p["id"] == "improvement-positive"
    )
    none = next(
        p for p in fixture["probes"] if p["id"] == "no-improvement-not-improved"
    )

    for probe in (positive, none):
        result = speaking_mission.improvement(probe["first"], probe["retry"])
        assert result["delta"] == probe["expect"]["delta"], probe["id"]
        assert result["improved"] is probe["expect"]["improved"], probe["id"]

    # El desglose por criterio debe incluir fluency cuando sube.
    result = speaking_mission.improvement(positive["first"], positive["retry"])
    assert any(
        row["criterion"] == "fluency" for row in result["by_criterion"]
    )


def test_scoring_is_deterministic_given_same_evidence():
    fixture = loader.load_json("speaking/mission_probes")
    for entry in fixture["evidence_determinism"]:
        parsed_a = speaking_llm.parse_speaking_evidence(entry["raw"])
        parsed_b = speaking_llm.parse_speaking_evidence(entry["raw"])
        assert parsed_a is not None, entry["id"]
        assert parsed_a == parsed_b, entry["id"]

        score_a = speaking.scores_from_evidence(
            parsed_a,
            entry["heard"],
            duration_seconds=entry["duration_seconds"],
            task_type=entry["task_type"],
        )
        score_b = speaking.scores_from_evidence(
            parsed_b,
            entry["heard"],
            duration_seconds=entry["duration_seconds"],
            task_type=entry["task_type"],
        )
        assert score_a == score_b, entry["id"]
        assert 0.0 < score_a["overall"] <= 1.0, entry["id"]
        # Sin referencia, la pronunciación no se observa (honestidad del proxy).
        assert score_a["observed"]["pronunciation"] is False


def test_mission_from_scenario_is_deterministic():
    scenario = {
        "id": "persuasion",
        "title": "Persuade a sceptical audience",
        "prompt": "Build a subtle case.",
        "communicative_objective": "Persuade without appearing confrontational.",
        "cefr_target": "C2",
        "task_type": "discussion",
        "metrics": speaking_mission.MISSION_PHASES,
        "difficulty": 6,
        "difficulty_vector": {"cognitive_demand": 6},
    }
    a = speaking_mission.mission_from_scenario(scenario)
    b = speaking_mission.mission_from_scenario(scenario)
    assert a == b
    assert a["cefr_target"] == "C2"
    assert a["task_type"] == "discussion"

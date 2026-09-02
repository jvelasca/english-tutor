"""Golden tests del Evidence Graph (auditoría D).

Los perfiles sintéticos de `tests/golden/evidence_graph/profiles.json` fijan el
comportamiento del limiting factor: la dimensión declarada más débil (o la
evidencia transfer ausente) manda, nunca la destreza más alta.
"""
from __future__ import annotations

from golden import loader

from services import evidence_graph
from services.curriculum import Objective


def _objective(data: dict) -> Objective:
    payload = dict(data)
    payload.setdefault("activities", [])
    payload.setdefault("checks", [])
    payload.setdefault("vocabulary", [])
    payload.setdefault("concepts", [])
    payload.setdefault("listening_items", [])
    payload.setdefault("scenario_ids", [])
    return Objective(**payload)


def _run(scenario: dict) -> dict:
    objective = _objective(scenario["objective"])
    return evidence_graph.objective_node(
        objective,
        level_id="b1",
        level_label="B1",
        objective_scores=scenario.get("objective_scores") or {},
        profile=scenario["profile"],
        evidence_rows=scenario["evidence_rows"],
    )


def test_flagship_limits_to_interaction_not_vocabulary():
    """El caso de la auditoría: 88/91/85/63/58 → interaction es el limiting."""
    fixture = loader.load_json("evidence_graph/profiles")
    scenario = next(
        s for s in fixture["scenarios"] if s["id"] == "flagship-interaction"
    )
    node = _run(scenario)
    expect = scenario["expect"]

    limit = node["limiting_factor"]
    assert limit is not None
    assert limit["id"] == expect["limiting_factor"]
    assert limit["missing"] is False
    # vocabulary (91) no puede ser el limiting factor.
    assert limit["id"] != "vocabulary"

    focus = node["recommended_focus"]
    assert focus["dimension"] == expect["focus_dimension"]
    assert focus["phase"] == expect["focus_phase"]

    assert node["mastery"] >= expect["mastery_min"]

    bullets = evidence_graph.explain_because(node)
    assert any(
        f"{expect['because_mentions_weak']} mastery" in b for b in bullets
    )
    if expect.get("because_mentions_strong_vocabulary"):
        assert any(
            b.startswith("Your vocabulary is already") for b in bullets
        ), bullets


def test_missing_transfer_wins_over_weak_skills():
    fixture = loader.load_json("evidence_graph/profiles")
    scenario = next(
        s for s in fixture["scenarios"] if s["id"] == "missing-transfer-wins"
    )
    node = _run(scenario)
    expect = scenario["expect"]

    limit = node["limiting_factor"]
    assert limit["id"] == expect["limiting_factor"]
    assert limit["missing"] is expect.get("missing", False)
    assert node["recommended_focus"]["phase"] == expect["focus_phase"]

    bullets = evidence_graph.explain_because(node)
    if expect.get("because_mentions_missing"):
        assert any("missing" in b for b in bullets), bullets


def test_weak_vocabulary_limits_when_genuinely_weak():
    """Caso de control: si vocabulary es la más débil, el grafo lo señala."""
    fixture = loader.load_json("evidence_graph/profiles")
    scenario = next(
        s for s in fixture["scenarios"] if s["id"] == "vocabulary-weak-wins"
    )
    node = _run(scenario)
    expect = scenario["expect"]

    assert node["limiting_factor"]["id"] == expect["limiting_factor"]
    assert node["recommended_focus"]["dimension"] == expect["focus_dimension"]
    assert node["recommended_focus"]["phase"] == expect["focus_phase"]


def test_dimensions_are_canonical_and_transfer_last():
    fixture = loader.load_json("evidence_graph/profiles")
    scenario = fixture["scenarios"][0]
    node = _run(scenario)
    dims = [d["id"] for d in node["dimensions"]]
    assert dims[-1] == "transfer"
    assert set(dims) <= set(evidence_graph.GRAPH_DIMENSIONS)

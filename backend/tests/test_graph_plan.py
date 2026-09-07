"""Tests del puente Knowledge Graph ↔ plan diario (V3.17, Fase A).

Cubren las dos funciones puras nuevas del Evidence Graph:

- `rank_weakness_objectives`: la debilidad se practica eligiendo el objetivo cuyo
  nodo declara esa destreza como factor limitante (o con la dimensión `missing`)
  antes que el que no; después por `mastery` ascendente; empates estables por el
  orden recibido; ids sin nodo al final (D7).
- `enrich_item`: enriquecimiento aditivo de un ítem del plan con los campos del
  nodo; sin nodo el ítem NO se toca.

Invariante D5: no se cambia la salida de las funciones existentes del grafo.
"""

from __future__ import annotations

from services import evidence_graph as eg


def _node(
    objective_id: str,
    *,
    mastery: float,
    limiting: str | None = None,
    missing_dims: list[str] | None = None,
) -> dict:
    """Nodo mínimo con la forma que consume el ranking/enriquecimiento."""
    dims = []
    for name in ("vocabulary", "grammar", "speaking", "listening", "transfer"):
        if name in (missing_dims or []):
            dims.append({"id": name, "score": 0.0, "missing": True})
        elif name == limiting:
            dims.append({"id": name, "score": 0.3, "missing": False})
        else:
            dims.append({"id": name, "score": 0.8, "missing": False})
    return {
        "objective_id": objective_id,
        "can_do": f"I can {objective_id}.",
        "mastery": mastery,
        "dimensions": dims,
        "limiting_factor": (
            {"id": limiting, "score": 0.3, "missing": False, "kind": "skill"}
            if limiting is not None
            else None
        ),
        "graph_version": eg.GRAPH_VERSION,
    }


# --- rank_weakness_objectives (D1b) ---------------------------------------


def test_rank_puts_limiting_factor_objective_first():
    """La destreza débil es el limiting factor del B pero no del A → B primero."""
    nodes = {
        "A": _node("A", mastery=0.5, limiting="vocabulary"),
        "B": _node("B", mastery=0.7, limiting="grammar"),
    }
    ranked = eg.rank_weakness_objectives(
        objective_ids=["A", "B"], nodes_by_objective=nodes, skill="grammar"
    )
    assert ranked == ["B", "A"]


def test_rank_treats_missing_dimension_as_related():
    """Un objetivo con la dimensión de la destreza `missing` también va antes."""
    nodes = {
        "A": _node("A", mastery=0.6, limiting="vocabulary"),
        "B": _node("B", mastery=0.4, missing_dims=["grammar"]),
    }
    ranked = eg.rank_weakness_objectives(
        objective_ids=["A", "B"], nodes_by_objective=nodes, skill="grammar"
    )
    assert ranked == ["B", "A"]


def test_rank_sorts_within_groups_by_mastery_ascending():
    nodes = {
        "A": _node("A", mastery=0.5, limiting="grammar"),
        "B": _node("B", mastery=0.2, limiting="grammar"),
        "C": _node("C", mastery=0.1, limiting="vocabulary"),
        "D": _node("D", mastery=0.9, limiting="vocabulary"),
    }
    ranked = eg.rank_weakness_objectives(
        objective_ids=["A", "B", "C", "D"], nodes_by_objective=nodes, skill="grammar"
    )
    # Grammar-limitantes (B 0.2 < A 0.5) antes que vocabulary (C 0.1 < D 0.9).
    assert ranked == ["B", "A", "C", "D"]


def test_rank_is_stable_on_ties_preserving_input_order():
    nodes = {
        "A": _node("A", mastery=0.5, limiting="grammar"),
        "B": _node("B", mastery=0.5, limiting="grammar"),
    }
    ranked = eg.rank_weakness_objectives(
        objective_ids=["A", "B"], nodes_by_objective=nodes, skill="grammar"
    )
    assert ranked == ["A", "B"]


def test_rank_fallback_keeps_nodeless_ids_at_end_in_order():
    """D7: ids sin nodo no se reordenan y quedan al final en el orden recibido."""
    nodes = {
        "A": _node("A", mastery=0.8, limiting="vocabulary"),
        "B": _node("B", mastery=0.3, limiting="grammar"),
    }
    ranked = eg.rank_weakness_objectives(
        objective_ids=["C", "B", "A", "D"],
        nodes_by_objective=nodes,
        skill="grammar",
    )
    # B (grammar-limitante) primero; A después; C/D sin nodo al final en orden.
    assert ranked == ["B", "A", "C", "D"]


def test_rank_empty_inputs_is_deterministic():
    assert (
        eg.rank_weakness_objectives(
            objective_ids=[], nodes_by_objective={}, skill="x"
        )
        == []
    )


def test_rank_tolerates_non_numeric_mastery_without_throwing():
    """D7.2 (V3.18): un nodo con `mastery` no numérico (None/"n/a") no rompe el
    ranking: cae a 0.0 y se ordena al final de su grupo (empate estable)."""
    nodes = {
        "A": _node("A", mastery=0.5, limiting="grammar"),
        "B": {
            **_node("B", mastery=0.4, limiting="grammar"),
            "mastery": None,
        },
        "C": {
            **_node("C", mastery=0.4, limiting="grammar"),
            "mastery": "n/a",
        },
    }
    # Sin defensa esto lanzaría `TypeError`/`ValueError` en el `float()`.
    ranked = eg.rank_weakness_objectives(
        objective_ids=["A", "B", "C"], nodes_by_objective=nodes, skill="grammar"
    )
    # B y C (score no convertible → 0.0, los más débiles) primero en su orden de
    # entrada (estable); A (0.5 real) después.
    assert ranked == ["B", "C", "A"]


# --- enrich_item (D1b, aditivo) -------------------------------------------


def test_enrich_item_adds_graph_fields_only_when_node():
    item = {
        "kind": "weakness",
        "skill": "grammar",
        "objective_id": "o1",
        "level_id": "a1",
        "title": "Past simple",
        "reason": "weakest skill: grammar",
        "minutes": 9,
    }
    node = {
        "level": "A1",
        "can_do": "I can talk about the past.",
        "mastery": 0.42,
        "dimensions": [
            {"id": "vocabulary", "score": 0.9, "missing": False},
            {"id": "grammar", "score": 0.4, "missing": False},
        ],
        "limiting_factor": {"id": "grammar", "score": 0.4, "missing": False},
        "recommended_focus": {"dimension": "grammar", "phase": "practice"},
    }
    enriched = eg.enrich_item(item, node)
    assert enriched["can_do"] == "I can talk about the past."
    assert enriched["graph_mastery"] == 0.42
    assert enriched["limiting_factor"]["id"] == "grammar"
    assert isinstance(enriched["because"], list) and enriched["because"]
    # El ítem original no se muta (la copia gana campos).
    assert "can_do" not in item and "because" not in item


def test_enrich_item_untouched_without_node():
    """D7: sin nodo el ítem se queda exactamente como estaba (sin campos de grafo)."""
    item = {
        "kind": "review",
        "skill": "grammar",
        "objective_id": None,
        "title": "Review grammar",
        "reason": "due for review",
        "minutes": 9,
    }
    enriched = eg.enrich_item(item, None)
    assert enriched == item
    assert "can_do" not in enriched
    assert "limiting_factor" not in enriched
    assert "graph_mastery" not in enriched
    assert "because" not in enriched


def test_enrich_item_same_result_as_enrich_next_best_with_node():
    """Mismo nodo → `/session` y `/next-best` enriquecen igual (nunca divergen)."""
    item = {"kind": "new", "objective_id": "o1", "title": "Greetings"}
    node = {
        "level": "A1",
        "can_do": "I can greet people.",
        "mastery": 0.3,
        "dimensions": [
            {"id": "vocabulary", "score": 0.8, "missing": False},
            {"id": "transfer", "score": 0.0, "missing": True},
        ],
        "limiting_factor": {"id": "transfer", "score": 0.0, "missing": True},
        "recommended_focus": {"dimension": "transfer", "phase": "transfer"},
    }
    assert eg.enrich_item(item, node) == eg.enrich_next_best(item, node)

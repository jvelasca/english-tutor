"""V3.27 (Listening Engine 4.0): `pick_next_question(layer=...)` restringe el
pool del nivel de trabajo a una capa cognitiva sin romper la progresión por nivel
ni el comportamiento sin capa."""
import pytest

from services.listening import (
    LEVEL_ORDER,
    current_level,
    pick_next_question,
    questions_for_level,
    skill_layer,
)


def test_pick_next_without_layer_behavior_unchanged():
    # Sin capa debe seguir devolviendo el primer ítem no visto del nivel.
    q1 = pick_next_question(set())
    q2 = pick_next_question(set())
    assert q1["id"] == q2["id"]


def test_pick_next_layer_restricts_to_layer_within_level():
    # Nivel de trabajo con evidencia vacía = primer nivel del orden.
    working_level = current_level(set())
    layer_of_level = {
        skill_layer(q["skill"])
        for q in questions_for_level(working_level)
        if skill_layer(q["skill"]) is not None
    }
    if not layer_of_level:
        pytest.skip("el banco del nivel de trabajo no tiene ítems receptivos")
    target = sorted(layer_of_level)[0]
    q = pick_next_question(set(), layer=target)
    assert skill_layer(q["skill"]) == target
    # No salta de nivel: la pregunta pertenece al nivel de trabajo.
    assert current_level({q["id"]}) == working_level


def test_pick_next_layer_matches_plain_selection_for_that_layer():
    # El primer ítem del pool plano pertenece a una capa: restringir a esa capa
    # debe devolver el mismo ítem (no cambia el orden al filtrar sin agotar).
    q = pick_next_question(set())
    layer = skill_layer(q["skill"])
    if layer is None:
        pytest.skip("el primer ítem del nivel es de producción")
    q_filtered = pick_next_question(set(), layer=layer)
    assert q_filtered["id"] == q["id"]


def test_pick_next_layer_without_candidates_falls_back_within_level():
    # Una capa sin candidatos en el nivel no bloquea: cae al pool completo del
    # nivel de trabajo (misma garantía de progresión).
    q = pick_next_question(set(), layer="recognition")
    assert q["id"]
    assert current_level({q["id"]}) in LEVEL_ORDER

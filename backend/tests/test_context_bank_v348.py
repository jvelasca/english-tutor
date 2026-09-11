"""V3.48 — Context Bank 2.0 + diversidad 2.0 (P2-04/P2-05 del dossier P).

La auditoría externa de V3.43.0 dejó dos P2 abiertos sobre la transferencia:

- **Context Bank 2.0**: el banco curado tenía solo 6 contextos, insuficiente
  para rotar sin repetir y sin cobertura real de niveles altos.
- **Diversidad 2.0**: medir la variedad solo con `topic`/`goal`/`discourse`/
  `social_relation`/`time`/`interaction` deja fuera ejes como el registro o el
  entorno léxico/sintáctico.

V3.48 amplía el banco a 20 contextos con cobertura A1–C2 y añade una capa de
VARIEDAD **informativa** (`register`/`lexical_environment`/`syntactic_focus`)
que se expone en `context_diversity.variety` pero **NO entra en el gate de
evidencia**: `CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score` y
`diverse_dimensions` conservan la semántica de V3.47 (cero regresión). Los seis
contextos originales quedan CONGELADOS (mismos `id` y mismos valores core).
"""

from __future__ import annotations

import collections

from services import evidence as evidence_svc
from services import transfer
from services.cefr import CEFR_LEVELS

BANK_SIZE = 20

# Guardia de congelación: los seis contextos de V3.43–V3.47, en orden, con sus
# atributos core intactos (ampliar el banco NO puede reescribir la evidencia ya
# registrada que referencia estos `context_id`).
ORIGINAL_CONTEXTS = (
    (
        "story", "A2", "personal_experience", "narrate",
        "narrative", "friend", "past", "monologue",
    ),
    (
        "question", "A1", "friend_life", "ask",
        "dialogue", "friend", "present", "dialogue",
    ),
    (
        "work", "B1", "employment", "describe",
        "descriptive", "colleague", "present", "monologue",
    ),
    (
        "future", "A2", "personal_plans", "plan",
        "expository", "friend", "future", "monologue",
    ),
    (
        "opinion", "B1", "everyday_topics", "give_opinion",
        "argumentative", "friend", "present", "monologue",
    ),
    (
        "problem", "B1", "everyday_problems", "explain",
        "explanatory", "family", "past", "monologue",
    ),
)

VARIETY_VALUES = {
    "register": {"neutral", "informal", "formal"},
    "lexical_environment": {
        "concrete_everyday",
        "personal_experience",
        "professional",
        "academic",
        "abstract",
        "cultural",
    },
    "syntactic_focus": {
        "simple_present",
        "past_narrative",
        "future_forms",
        "questions",
        "modals",
        "conditionals",
        "complex_subordination",
        "passive",
    },
}


def _bank_ids() -> list[str]:
    return [transfer.context_id_for(context) for context in transfer.TRANSFER_CONTEXTS]


# ------------------------------------------------------------------ el banco


def test_bank_has_twenty_unique_contexts():
    assert len(transfer.TRANSFER_CONTEXTS) == BANK_SIZE
    ids = [context["id"] for context in transfer.TRANSFER_CONTEXTS]
    assert len(set(ids)) == len(ids)


def test_bank_covers_the_target_cefr_distribution():
    counts = collections.Counter(
        context["cefr"] for context in transfer.TRANSFER_CONTEXTS
    )
    assert counts == {"A1": 3, "A2": 4, "B1": 4, "B2": 3, "C1": 3, "C2": 3}
    assert set(counts) <= set(CEFR_LEVELS)


def test_every_context_declares_core_and_variety_attributes_without_the_target():
    for context in transfer.TRANSFER_CONTEXTS:
        for dimension in transfer.CONTEXT_DIMENSIONS:
            assert (context.get(dimension) or "").strip(), (
                context["id"],
                dimension,
            )
        for dimension in transfer.CONTEXT_VARIETY_DIMENSIONS:
            value = (context.get(dimension) or "").strip()
            assert value, (context["id"], dimension)
            assert value in VARIETY_VALUES[dimension], (context["id"], dimension, value)
        assert context["prompt"].strip()
        # La consigna da un ESCENARIO: nunca contiene el target ni una plantilla.
        assert "{word}" not in context["prompt"]


def test_the_six_original_contexts_are_frozen():
    for index, expected in enumerate(ORIGINAL_CONTEXTS):
        context = transfer.TRANSFER_CONTEXTS[index]
        assert context["id"] == expected[0]
        assert context["cefr"] == expected[1]
        assert context["topic"] == expected[2]
        assert context["communicative_goal"] == expected[3]
        assert context["discourse_type"] == expected[4]
        assert context["social_relation"] == expected[5]
        assert context["time_reference"] == expected[6]
        assert context["interaction_type"] == expected[7]


def test_minimum_pairwise_distance_stays_at_two():
    pairs = []
    contexts = transfer.TRANSFER_CONTEXTS
    for index, first in enumerate(contexts):
        for second in contexts[index + 1 :]:
            pairs.append(transfer.context_distance(first, second))
    assert min(pairs) >= transfer.CONTEXT_DIVERSITY_MIN
    # El par de referencia de V3.43 sigue exactamente igual.
    assert transfer.context_distance("transfer:story", "transfer:work") == 5


# ------------------------------------------- diversidad core vs variedad 2.0


def test_diverse_dimensions_still_counts_only_the_core_axes():
    ids = _bank_ids()
    diversity = transfer.context_diversity(ids)
    core = transfer.context_dimensions(ids)
    assert diversity["dimensions"] == core
    assert diversity["diverse_dimensions"] == sum(
        1 for values in core.values() if len(values) >= 2
    )
    # Los ejes de variedad NO se cuelan en el gate de evidencia.
    assert not (set(diversity["dimensions"]) & set(transfer.CONTEXT_VARIETY_DIMENSIONS))


def test_context_variety_is_deterministic_and_informative():
    ids = _bank_ids()
    variety = transfer.context_variety(ids)
    assert set(variety) == {"dimensions", "varied_dimensions", "score"}
    assert set(variety["dimensions"]) <= set(transfer.CONTEXT_VARIETY_DIMENSIONS)
    assert variety["varied_dimensions"] >= 2
    assert 0.0 < variety["score"] <= 1.0
    assert transfer.context_variety(ids) == variety
    assert transfer.context_variety([]) == {
        "dimensions": {},
        "varied_dimensions": 0,
        "score": 0.0,
    }


def test_context_dimensions_accepts_custom_axes():
    ids = _bank_ids()
    only_register = transfer.context_dimensions(ids, dimensions=("register",))
    assert set(only_register) == {"register"}
    assert set(only_register["register"]) == VARIETY_VALUES["register"]
    # Sin ejes válidos se cae a los core (nunca revienta).
    assert set(transfer.context_dimensions(ids, dimensions=())) == set(
        transfer.CONTEXT_DIMENSIONS
    )
    assert set(transfer.context_dimensions(ids, dimensions=42)) == set(
        transfer.CONTEXT_DIMENSIONS
    )


# ------------------------------------------------------------ selección (pura)


def test_context_for_is_deterministic_and_rotates_over_the_expanded_bank():
    first = transfer.context_for("travel")
    assert first["available"] is True
    assert first["context_id"] == transfer.context_for("travel")["context_id"]
    used = _bank_ids()
    rotated = transfer.context_for("travel", used_context_ids=used)
    assert rotated["exhausted"] is True
    assert rotated["context_id"] in used


def test_context_for_never_serves_a_context_above_the_student_level():
    for level in CEFR_LEVELS:
        got = transfer.context_for("travel", level=level)
        assert got["available"] is True
        assert transfer.cefr_index(got["cefr"]) <= transfer.cefr_index(level)


# -------------------------------------------------- no regresión del gate V3.47


def test_transfer_gate_is_not_regressed_by_the_expanded_bank():
    rows = [
        {
            "context_id": "transfer:story",
            "success": 1,
            "error_type": "correct",
            "transfer_condition": "open_context",
            "occurred_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "context_id": "transfer:future",
            "success": 1,
            "error_type": "correct",
            "transfer_condition": "open_context",
            "occurred_at": "2026-01-02T10:00:00+00:00",
        },
    ]
    summary = evidence_svc.with_transfer_state(evidence_svc.context_signals(rows))
    assert summary["transfer"] is True
    assert summary["transfer_state"] == "transfer_demonstrated"
    assert (
        summary["context_diversity"]["diverse_dimensions"]
        >= transfer.CONTEXT_DIVERSITY_MIN
    )
    # La variedad viaja como información, no como umbral.
    assert "variety" in summary["context_diversity"]


def test_empty_summary_carries_the_variety_default():
    diversity = evidence_svc.empty_summary()["context_diversity"]
    assert diversity["variety"] == {
        "dimensions": {},
        "varied_dimensions": 0,
        "score": 0.0,
    }

"""SENSE-CONTEXT-01 (V3.94.2): corpus de regresión de polisemia.

`resolver_expected` fija la heurística: si el resolver se aparta, CI falla.
`gold` es la etiqueta humana y puede diferir. Esas discrepancias se cuentan;
no se tratan como fallo del ítem. El conjunto queda congelado para que un
cambio de la heurística obligue a mirarlas, no para convertirlas en un gate
pedagógico.
"""
import json
from pathlib import Path

from services import sense_context as sc

CORPUS = Path(__file__).resolve().parent / "fixtures" / "sense_regression_corpus.json"

FAMILIES = frozenset(
    {
        "bank",
        "charge",
        "right",
        "match",
        "point",
        "light",
        "mean",
        "issue",
        "case",
        "change",
        "break",
        "run",
        "set",
        "turn",
        "play",
    }
)

# Límites conocidos de la heurística de solape. No son fallos de CI del resolver:
# el contrato es `resolver_expected`. Si este conjunto cambia, la heurística
# empezó a coincidir o a discrepar con la etiqueta humana y hay que mirarlo.
KNOWN_GOLD_DISAGREEMENTS = frozenset({"bank-07", "bank-08", "bank-10", "run-07"})


def _load() -> list[dict]:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert payload["version"] == "3.94.2"
    items = payload["items"]
    assert items
    return items


def _agrees(gold: str, verdict: dict) -> bool:
    if gold == "split":
        return verdict["reason"] == sc.REASON_OCCURRENCE_SPLIT
    if verdict["reason"] == sc.REASON_OCCURRENCE_SPLIT:
        return False
    return verdict["match"] == gold


def test_corpus_covers_the_polysemy_families():
    items = _load()
    lemmas = {item["lemma"] for item in items}
    assert lemmas == FAMILIES
    for lemma in FAMILIES:
        assert sum(1 for item in items if item["lemma"] == lemma) >= 4


def test_resolver_matches_the_pinned_expectation_and_gold_is_counted():
    disagreements = []
    for item in _load():
        verdict = sc.classify_sense_evidence(
            item["lemma"],
            item["sentence"],
            item["declared"],
            senses=item["alternatives"],
        )
        expected = item["resolver_expected"]
        assert verdict["match"] == expected["match"], item["id"]
        assert verdict["mismatch_strength"] == expected["strength"], item["id"]
        assert verdict["reason"] == expected["reason"], item["id"]
        if not _agrees(item["gold"], verdict):
            disagreements.append(item["id"])
    assert frozenset(disagreements) == KNOWN_GOLD_DISAGREEMENTS


def test_generic_gloss_traps_are_marked_and_not_treated_as_gold():
    """Dos tokens incidentales no se promocionan a verdad lingüística."""
    by_id = {item["id"]: item for item in _load()}
    for item_id in ("bank-10", "run-07"):
        item = by_id[item_id]
        assert item["note"]
        assert item["gold"] != item["resolver_expected"]["match"]
        assert item["resolver_expected"]["match"] == sc.SENSE_MISMATCH

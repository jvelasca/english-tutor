"""SENSE-CONTEXT-01 (V3.94.2): dos sentidos en la misma frase no se colapsan.

El resolver devolvía UN veredicto por palabra y se quedaba con la ocurrencia de
mayor margen. Si esa ocurrencia era un `mismatch` probado, la palabra entera
suprimía FSRS y contaba como exposición, aunque otra aparición fuera la acepción
aprendida.

V3.94.2 clasifica cada ocurrencia con la misma regla asimétrica. Si hay un
`mismatch` probado y otra ocurrencia que no lo es, el agregado es `ambiguous`
con razón `occurrence:split`: la duda no resta evidencia y no fabrica exposición.
"""
from services import sense_context as sc

FINANCE = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "a place where money is kept",
    "domain": "finance",
}
RIVER = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "the side of a river",
    "domain": "geography",
}

SPLIT_SENTENCE = (
    "On the river side, the bank was covered in mud, but I put my money in the bank."
)
AUDIT_SENTENCE = (
    "The bank by the river was closed, but the bank approved my loan."
)


def test_a_proven_mismatch_beside_a_matched_use_is_a_split():
    verdict = sc.classify_sense_evidence(
        "bank", SPLIT_SENTENCE, FINANCE, senses=[FINANCE, RIVER]
    )
    assert [item["match"] for item in verdict["occurrences"]] == [
        sc.SENSE_MISMATCH,
        sc.SENSE_MATCHED,
    ]
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_OCCURRENCE_SPLIT
    assert verdict["mismatch_strength"] == sc.MISMATCH_POSSIBLE
    assert sc.is_occurrence_split(verdict) is True
    assert sc.is_new_sense_exposure(verdict) is False
    assert sc.allows_difficulty_evidence(verdict) is True


def test_two_proven_mismatches_stay_a_mismatch():
    """Si todas las ocurrencias coinciden en el mismatch, no hay conflicto."""
    text = (
        "On the river side the bank lay quiet, "
        "and near the river side the bank was muddy."
    )
    verdict = sc.classify_sense_evidence(
        "bank", text, FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["occurrences"]
    assert all(item["match"] == sc.SENSE_MISMATCH for item in verdict["occurrences"])
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER


def test_the_audit_sentence_is_not_a_proven_split():
    """Con estas glosas la primera ocurrencia solo tiene un token (`river`).

    Un humano puede leer orilla y luego banco financiero. La heurística no llega
    a `mismatch` probado, así que no dispara `occurrence:split`. Queda como
    límite del solape, no como conflicto de ocurrencias.
    """
    verdict = sc.classify_sense_evidence(
        "bank", AUDIT_SENTENCE, FINANCE, senses=[FINANCE, RIVER]
    )
    assert len(verdict["occurrences"]) == 2
    assert sc.SENSE_MISMATCH not in {item["match"] for item in verdict["occurrences"]}
    assert verdict["reason"] != sc.REASON_OCCURRENCE_SPLIT
    assert sc.allows_difficulty_evidence(verdict) is True


def test_a_single_proven_mismatch_is_unchanged():
    verdict = sc.classify_sense_evidence(
        "bank",
        "On the river side, the bank was covered in mud.",
        FINANCE,
        senses=[FINANCE, RIVER],
    )
    assert len(verdict["occurrences"]) == 1
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER

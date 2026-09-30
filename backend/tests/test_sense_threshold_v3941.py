"""SENSE-CONTEXT-01 (V3.94.1): el `mismatch` exige PRUEBA, no una señal débil.

V3.94 declaraba `mismatch` con un único token de solape: bastaba que la alternativa
compartiera UNA palabra con la ventana para suprimir la evidencia de dificultad. Esa
simetría (declarada > otra → `matched`; otra > declarada → `mismatch`) confundía
«hay una pequeña señal a favor de otro sentido» con «hemos PROBADO otro sentido».

V3.94.1 hace la resolución ASIMÉTRICA, porque un `mismatch` SUPRIME evidencia y un
`matched` solo tolera duda:

    `matched`   → señal suficiente (la duda no resta evidencia)
    `mismatch`  → señal FUERTE (≥2 tokens, o desempate gramatical fuerte)
    `ambiguous` → todo lo demás, incluida la señal débil (`gloss:other:weak`)

Qué se fija aquí:

1. el umbral `PROVEN_OTHER_OVERLAP`: 1 token es `possible` (ambiguous), 2 es `proven`;
2. el desempate gramatical fuerte sigue probando un `mismatch` con 0 solape;
3. la frontera NO invierte el caso `matched` (declarada gana con 1 token);
4. un corpus de polisemia real (`bank`) con GLOSAS de diccionario, no el texto de
   la frase, para medir el resolver con lenguaje realista.
"""
from services import sense_context as sc

# Glosas de diccionario (NO el texto de la frase): es lo que evita el caso
# artificial de V3.94, donde `other_overlap >> declared_overlap` estaba garantizado.
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
BANK_VERB = {
    "lemma": "bank",
    "pos": "verb",
    "gloss": "to deposit funds",
    "domain": "finance",
}


# --- 1. El umbral de prueba --------------------------------------------------


def test_one_token_is_possible_but_not_proven():
    verdict = sc.classify_sense_evidence(
        "bank", "The bank was by the river.", FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["best_other_overlap"] == 1
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["mismatch_strength"] == sc.MISMATCH_POSSIBLE
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER_WEAK
    # Un posible mismatch NO suprime: la evidencia se conserva.
    assert sc.allows_difficulty_evidence(verdict) is True


def test_two_tokens_are_proven():
    verdict = sc.classify_sense_evidence(
        "bank",
        "On the river side, the bank was covered in mud.",
        FINANCE,
        senses=[FINANCE, RIVER],
    )
    assert verdict["best_other_overlap"] == 2
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["mismatch_strength"] == sc.MISMATCH_PROVEN
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER
    assert sc.allows_difficulty_evidence(verdict) is False


def test_the_threshold_constant_is_the_boundary():
    assert sc.PROVEN_OTHER_OVERLAP == 2


# --- 2. El desempate gramatical fuerte sigue probando ------------------------


def test_a_strong_role_contradiction_is_proven_without_lexical_overlap():
    verdict = sc.classify_sense_evidence(
        "bank",
        "I bank regularly",
        FINANCE,
        senses=[FINANCE, BANK_VERB],
    )
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["mismatch_strength"] == sc.MISMATCH_PROVEN
    assert verdict["reason"] == sc.REASON_ROLE_OTHER


def test_role_support_does_not_hide_a_weak_signal_toward_another_sense():
    """Un token de la alternativa gana a un desempate gramatical (V3.94.1).

    La gramática apoya la familia DECLARADA (rol nominal) y ninguna familia
    alternativa encaja, que es el desempate que autoriza `role:declared`. Pero hay
    UN token léxico a favor de otra acepción: con la regla anterior ese token se
    etiquetaba `matched` y la señal se perdía. Ahora baja a `possible`
    (`gloss:other:weak`) y la evidencia se conserva —no se declara `matched` una
    señal real a favor del otro sentido—.
    """
    verb_water = {"lemma": "bank", "pos": "verb", "gloss": "to water the plants"}
    verdict = sc.classify_sense_evidence(
        "bank",
        "The bank was full of water.",
        FINANCE,
        senses=[FINANCE, verb_water],
    )
    assert verdict["declared_overlap"] == 0
    assert verdict["best_other_overlap"] == 1
    assert verdict["role"] == "noun"
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["mismatch_strength"] == sc.MISMATCH_POSSIBLE
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER_WEAK
    assert sc.allows_difficulty_evidence(verdict) is True


# --- 3. La asimetría no invierte el caso `matched` ---------------------------


def test_matched_tolerates_uncertainty_with_a_single_token():
    verdict = sc.classify_sense_evidence(
        "bank",
        "I put my money in the bank.",
        FINANCE,
        senses=[FINANCE, RIVER],
    )
    assert verdict["declared_overlap"] == 1
    assert verdict["match"] == sc.SENSE_MATCHED
    assert verdict["reason"] == sc.REASON_GLOSS_DECLARED


# --- 4. Corpus de polisemia real (`bank`) ------------------------------------


def _verdict(text: str) -> dict:
    return sc.classify_sense_evidence("bank", text, FINANCE, senses=[FINANCE, RIVER])


def test_corpus_financial_context_is_matched():
    assert _verdict("I put my money in the bank.")["match"] == sc.SENSE_MATCHED
    assert _verdict("The bank keeps my money safe.")["match"] == sc.SENSE_MATCHED


def test_corpus_financial_context_without_gloss_tokens_is_ambiguous():
    """Contexto financiero sin palabras de la glosa: honesto `ambiguous`.

    «The bank approved the mortgage» es financiero, pero la glosa no comparte
    ningún token con la ventana. Preferimos perder evidencia a inventarla.
    """
    assert _verdict("The bank approved the mortgage.")["match"] == sc.SENSE_AMBIGUOUS


def test_corpus_closed_bank_is_ambiguous():
    """Dos sentidos del MISMO POS sin pistas léxicas: irresoluble (H12)."""
    verdict = _verdict("The bank was closed.")
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_TIE


def test_corpus_river_with_a_single_token_is_ambiguous_not_mismatch():
    assert _verdict("The bank was by the river.")["match"] == sc.SENSE_AMBIGUOUS
    assert _verdict("We sat on the bank of the river.")["match"] == sc.SENSE_AMBIGUOUS


def test_corpus_river_with_two_tokens_is_a_proven_mismatch():
    verdict = _verdict("On the river side, the bank was covered in mud.")
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["mismatch_strength"] == sc.MISMATCH_PROVEN

"""SENSE-CONTEXT-01 (diseño): identidad de acepción y resolución de sentido.

Fija, con tests, el DISEÑO de la fase. Nada de esto está cableado a producción
todavía (`test_sense_context_is_not_wired_into_production` lo garantiza), así que
el esquema de V3.92 sigue intacto: estos tests son el criterio de aceptación de la
implementación de V3.93+.

Qué se fija:

1. `semantics.sense_key` da una identidad determinista y normalizada (`lemma` +
   familia POS + dominio + glosa), y `''` cuando no consta nada;
2. el Sense Resolver clasifica en `matched` / `mismatch` / `ambiguous` siendo
   CONSERVADOR: `mismatch` exige una alternativa con evidencia léxica, y
   `ambiguous` (que NO penaliza) es el resultado por defecto ante la duda;
3. solo `matched` autoriza evidencia de dificultad.
"""
from pathlib import Path

from services import sense_context as sc
from services.semantics import sense_key, tokens_of

FINANCE = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "A place where money is kept",
    "domain": "finance",
}
RIVER = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "The side of a river",
    "domain": "geography",
}
BANK_VERB = {
    "lemma": "bank",
    "pos": "verb",
    "gloss": "to deposit funds",
    "domain": "finance",
}
FINANCE_NO_OVERLAP = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "a financial institution",
    "domain": "finance",
}


# --- Identidad de acepción (semantics.sense_key) ----------------------------


def test_sense_key_is_deterministic_and_content_addressed():
    assert sense_key(FINANCE) == "bank|noun|finance|a place where money is kept"


def test_sense_key_normalizes_case_and_whitespace():
    noisy = {"term": " Bank ", "pos": "Noun", "gloss": "  A  place ", "domain": "FIN"}
    clean = {"lemma": "bank", "pos": "noun", "gloss": "a place", "domain": "fin"}
    assert sense_key(noisy) == sense_key(clean)


def test_sense_key_distinguishes_senses_of_the_same_word():
    assert sense_key(FINANCE) != sense_key(RIVER)


def test_sense_key_is_empty_when_nothing_is_declared():
    assert sense_key({}) == ""
    assert sense_key({"pos": "", "gloss": "  "}) == ""
    assert sense_key(None) == ""
    assert sense_key("noun") == ""


def test_sense_key_falls_back_to_term_and_family():
    # Sin `lemma` cae a `term`; "phrasal verb" se normaliza a la familia "verb".
    assert sense_key({"term": "look up", "pos": "phrasal verb"}).startswith(
        "look up|verb|"
    )


def test_sense_key_neutralizes_the_field_separator():
    """Un valor con `|` no puede fingir ser otro campo (nota de la revisión).

    `lemma="bank|noun"` y `lemma="bank", pos="noun"` NO deben dar la misma clave.
    """
    smuggled = sense_key({"lemma": "bank|noun", "gloss": "x"})
    honest = sense_key({"lemma": "bank", "pos": "noun", "gloss": "x"})
    assert smuggled != honest


def test_tokens_of_is_public_and_tolerant():
    assert tokens_of("The bank, of the river!") == ["the", "bank", "of", "the", "river"]
    assert tokens_of(None) == []


# --- Sense Resolver: matriz matched / mismatch / ambiguous ------------------


def test_river_phrase_on_a_financial_sense_is_mismatch():
    verdict = sc.classify_sense_evidence(
        "bank", "We sat on the bank of the river", FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["declared_overlap"] == 0
    assert verdict["best_other_overlap"] == 1
    assert verdict["reason"] == sc.REASON_GLOSS_OTHER


def test_financial_context_is_matched_by_gloss_overlap():
    verdict = sc.classify_sense_evidence(
        "bank", "The bank keeps my money safe", FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["match"] == sc.SENSE_MATCHED
    assert verdict["reason"] == sc.REASON_GLOSS_DECLARED
    assert verdict["declared_overlap"] > verdict["best_other_overlap"]


def test_without_alternatives_a_mismatch_is_never_declared():
    """No se puede probar una acepción distinta si no se conocen alternativas."""
    verdict = sc.classify_sense_evidence(
        "bank", "We sat on the bank of the river", FINANCE, senses=[]
    )
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_NO_ALTERNATIVES


def test_same_pos_without_lexical_evidence_is_ambiguous():
    """El caso real: dos sentidos nominales y un contexto que no desempata."""
    verdict = sc.classify_sense_evidence(
        "bank", "The bank was closed.", FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_TIE


def test_role_disambiguates_a_cross_family_case():
    """Sin solape léxico, la gramática decide si las familias son distintas."""
    verdict = sc.classify_sense_evidence(
        "bank",
        "I bank every day",
        BANK_VERB,
        senses=[BANK_VERB, FINANCE_NO_OVERLAP],
    )
    assert verdict["match"] == sc.SENSE_MATCHED
    assert verdict["reason"] == sc.REASON_ROLE_DECLARED


def test_strong_role_contradiction_with_a_supported_alternative_is_mismatch():
    verdict = sc.classify_sense_evidence(
        "bank",
        "I bank regularly",
        FINANCE_NO_OVERLAP,
        senses=[FINANCE_NO_OVERLAP, BANK_VERB],
    )
    assert verdict["match"] == sc.SENSE_MISMATCH
    assert verdict["reason"] == sc.REASON_ROLE_OTHER


def test_declared_sense_missing_is_ambiguous():
    verdict = sc.classify_sense_evidence(
        "bank", "The bank was closed.", {}, senses=[RIVER]
    )
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_DECLARED_NONE
    assert verdict["declared_key"] == ""


def test_word_absent_from_the_phrase_is_ambiguous():
    verdict = sc.classify_sense_evidence(
        "bank", "This sentence has no target", FINANCE, senses=[FINANCE, RIVER]
    )
    assert verdict["match"] == sc.SENSE_AMBIGUOUS
    assert verdict["reason"] == sc.REASON_OCCURRENCE_NONE


def test_only_matched_authorizes_evidence():
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_MATCHED}) is True
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_MISMATCH}) is False
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_AMBIGUOUS}) is False
    assert sc.allows_difficulty_evidence(None) is False


def test_the_same_sense_repeated_is_not_an_alternative():
    """La misma acepción con otra forma de clave no debe fabricar un mismatch."""
    bare = {"pos": "noun", "gloss": "A place where money is kept"}
    verdict = sc.classify_sense_evidence(
        "bank", "The bank keeps my money safe", FINANCE, senses=[FINANCE, bare]
    )
    assert verdict["match"] == sc.SENSE_MATCHED


def test_classifier_is_total_with_junk():
    for badge in (None, 42, "", []):
        verdict = sc.classify_sense_evidence(badge, badge, badge, senses=badge)
        assert verdict["match"] in sc.MATCHES
    assert sc.classify_sense_evidence("bank", None, FINANCE)["match"] in sc.MATCHES


# --- Frontera de la fase: el resolver NO está cableado ----------------------


def test_sense_context_is_not_wired_into_production():
    """Mientras V3.92 siga siendo la versión publicada, el resolver es DISEÑO.

    Si algún camino de producción empieza a importar `sense_context`, este test
    cae: obliga a que el cableado llegue con su propia release y sus propias
    pruebas, en vez de colarse como cambio silencioso de comportamiento.
    """
    backend = Path(__file__).resolve().parents[1]
    skip = {"tests", ".venv", "__pycache__", "data"}
    offenders = []
    for path in backend.rglob("*.py"):
        if path.name == "sense_context.py":
            continue
        if skip & set(path.relative_to(backend).parts):
            continue
        if "sense_context" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(backend)))
    assert offenders == []

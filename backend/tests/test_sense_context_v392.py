"""SENSE-CONTEXT-01 (diseño): identidad de acepción y resolución de sentido.

Fija, con tests, el DISEÑO del resolver y su CONTRATO de decisión. V3.94 lo cablea
en ENFORCE: `domain/listening.py` registra el veredicto y **decide** con
`allows_difficulty_evidence`. La frontera del dark launch de V3.93 se cierra en
`test_sense_enforce_v394.py`.

Qué se fija:

1. `semantics.sense_key` da una identidad determinista y normalizada (`lemma` +
   familia POS + dominio + glosa), y `''` cuando no consta nada;
2. el Sense Resolver clasifica en `matched` / `mismatch` / `ambiguous` siendo
   CONSERVADOR: `mismatch` exige una alternativa con evidencia léxica, y
   `ambiguous` es el resultado por defecto ante la duda;
3. la política de V3.94 (ENFORCE) suprime la evidencia SOLO ante un `mismatch`
   PROBADO; `ambiguous` (incluido `declared:none`) la conserva.
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


def test_only_a_proven_mismatch_suppresses_evidence():
    """ENFORCE (V3.94): la evidencia se quita SOLO ante un `mismatch` PROBADO.

    Un `ambiguous` CONSERVA la evidencia (la duda no RESTA evidencia igual que no la
    FABRICA), y sin veredicto se comporta como antes de V3.94. El `mismatch` es la
    base de `new_sense_exposure`; la política es exactamente su negación.
    """
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_MATCHED}) is True
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_MISMATCH}) is False
    assert sc.allows_difficulty_evidence({"match": sc.SENSE_AMBIGUOUS}) is True
    assert sc.allows_difficulty_evidence(None) is True
    assert sc.is_new_sense_exposure({"match": sc.SENSE_MISMATCH}) is True
    assert sc.is_new_sense_exposure({"match": sc.SENSE_MATCHED}) is False
    assert sc.is_new_sense_exposure({"match": sc.SENSE_AMBIGUOUS}) is False
    assert sc.is_new_sense_exposure(None) is False


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


# --- Frontera de la fase: el resolver decide, y SOLO por el puente ----------


def test_sense_context_is_wired_only_through_the_listening_bridge():
    """V3.94 (ENFORCE): el resolver DECIDE, y solo a través del puente de Listening.

    El único importador de producción es `domain/listening.py`, y allí la política
    **sí** decide (`allows_difficulty_evidence`). Si otro camino importara el
    resolver, o si el puente dejara de aplicar la política, este test cae: es la
    frontera que el diseño dejó escrita y que V3.94 cierra.
    """
    backend = Path(__file__).resolve().parents[1]
    skip = {"tests", ".venv", "__pycache__", "data"}
    importers = []
    for path in backend.rglob("*.py"):
        if path.name == "sense_context.py":
            continue
        if skip & set(path.relative_to(backend).parts):
            continue
        if "sense_context" in path.read_text(encoding="utf-8"):
            importers.append(path.relative_to(backend).as_posix())
    assert importers == ["domain/listening.py"]
    listening = (backend / "domain" / "listening.py").read_text(encoding="utf-8")
    assert "allows_difficulty_evidence" in listening

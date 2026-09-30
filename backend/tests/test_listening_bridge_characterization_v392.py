"""SENSE-CONTEXT-01: caracterización del puente V3.92 (lemma-only) y umbrales.

Estos tests NO piden un comportamiento nuevo: FIJAN el que V3.92 tiene hoy, para
que la fase de diseño tenga una línea base verificable y para que el cableado
sense-aware (V3.93+) tenga que cambiar estos tests de forma deliberada y revisable.

Dos cosas quedan documentadas como hechos, no como opiniones:

1. `listening_bridge` empareja por `word`/`lemma` e IGNORA la acepción: una frase
   de «orilla» del río produce evidencia sobre una acepción «financiera» de `bank`
   sin que nada lo impida (hallazgo H1 de `docs/audit/SENSE-CONTEXT-01.md`).
2. El corte de carta «débil» es `difficulty >= 6.0`, y por tanto es discontinuo en
   el umbral (5.9 no recibe evidencia; 6.0 sí).
"""
from services import listening_bridge as bridge

FINANCE = {
    "lemma": "bank",
    "pos": "noun",
    "gloss": "A place where money is kept",
    "domain": "finance",
}


# --- H1: el puente es ciego al sentido --------------------------------------


def test_unit_index_ignores_the_declared_sense():
    """La acepción no forma parte del índice: solo la superficie y el lema."""
    with_sense = [{"word": "bank", "lemma": "bank", "sense": FINANCE}]
    without_sense = [{"word": "bank", "lemma": "bank"}]
    assert bridge.unit_index(with_sense) == bridge.unit_index(without_sense) == {
        "bank": "bank"
    }


def test_match_units_is_sense_blind():
    """El caso `bank`: acepción financiera, frase de orilla, evidencia igual.

    Es la limitación que motiva SENSE-CONTEXT-01. El test la declara para que
    nadie confunda «el puente funcionó» con «el puente entendió la acepción».
    """
    known = [{"word": "bank", "lemma": "bank", "sense": FINANCE}]
    matched = bridge.match_units("We sat on the bank of the river", known)
    assert matched == [{"word": "bank", "surface": "bank"}]


def test_morphology_matches_inflections_regardless_of_sense():
    known = [{"word": "bank", "lemma": "bank", "sense": FINANCE}]
    assert bridge.match_units("The banks are open", known) == [
        {"word": "bank", "surface": "banks"}
    ]


def test_match_cap_keeps_the_first_matches_in_phrase_order():
    """El tope `MAX_MATCHES` corta por orden de aparición, no por relevancia.

    Se fija como comportamiento conocido (hallazgo H9): una frase larga puede
    dejar fuera palabras del léxico que aparezcan después de la octava.
    """
    tokens = [f"{a}{b}zz" for a in "abcdef" for b in "ghij"]
    known = [{"word": token} for token in tokens]
    assert len(tokens) > bridge.MAX_MATCHES
    matched = bridge.match_units(" ".join(tokens), known)
    assert [m["word"] for m in matched] == tokens[: bridge.MAX_MATCHES]


# --- H10: el corte de carta «débil» es discontinuo en 6.0 -------------------


def test_weak_card_boundary_is_discontinuous():
    assert bridge.is_weak_card({"state": "review", "difficulty": 5.9}) is False
    assert bridge.is_weak_card({"state": "review", "difficulty": 6.0}) is True
    assert bridge.is_weak_card({"state": "review", "difficulty": 6.1}) is True


def test_weak_card_covers_non_review_states_at_any_difficulty():
    assert bridge.is_weak_card({"state": "new", "difficulty": 5.0}) is True
    assert bridge.is_weak_card({"state": "learning", "difficulty": 1.0}) is True
    assert bridge.is_weak_card({"state": "relearning", "difficulty": 9.9}) is True
    assert bridge.is_weak_card(None) is True


def test_select_targets_skips_only_demonstrated_cards():
    matches = [
        {"word": "bank", "surface": "bank"},
        {"word": "river", "surface": "river"},
    ]
    cards = {
        "bank": {"state": "review", "difficulty": 2.0},  # demostrada: no se toca
        "river": {"state": "review", "difficulty": 6.0},  # al límite: sí
    }
    targets = bridge.select_targets(matches, cards)
    assert [t["word"] for t in targets] == ["river"]

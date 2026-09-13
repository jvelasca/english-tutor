"""V3.58 — Sense Engine 2.0 (`surface → lemma → sense → semantic_fit`).

V3.44 introdujo los SENTIDOS (`[{pos, gloss}]`) pero la decisión siguió siendo de
FAMILIA POS: la glosa se generaba, se validaba, se cacheaba y **no la leía
nadie** —dato INERTE—. Con `bank` declarando `[{noun, "financial place"},
{noun, "river side"}]`, V3.44 no puede separar «el banco del río» de «el banco
financiero»: ambos usos son `noun` y ambos «encajan» con la familia nominal.

V3.58 añade las dos patas que faltaban —`surface → lemma` y `lemma → sense`— y
hace que la glosa RESUELVA qué sentido se entendió.

FRONTERA DECLARADA (invariante conservador de V3.44, probado aquí): la glosa
decide el SENTIDO, **no el veredicto**. `semantic_adequacy` conserva EXACTAMENTE
la adecuación de V3.44 —solo `incorrect` bloquea un clean success y no se amplía—
porque una glosa corta no DEMUESTRA incompatibilidad: la ausencia de
solapamiento no es una prueba, y el test
`test_polysemous...`/`test_a_legit_occurrence...` de V3.44 son la evidencia
(`"The bank is closed"` no comparte ni una palabra con «a financial place» y es
un uso correcto). Lo que cambia es que el motor ahora NOMBRA el sentido resuelto
y su confianza, y que el solapamiento se calcula sobre LEMAS, no sobre
superficies.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon, semantics

# ---------------------------------------------------------------- surface → lemma


def test_lemma_of_regular_morphology():
    assert semantics.lemma_of("banked") == "bank"
    assert semantics.lemma_of("banking") == "bank"
    assert semantics.lemma_of("banks") == "bank"
    assert semantics.lemma_of("studies") == "study"
    assert semantics.lemma_of("boxes") == "box"
    assert semantics.lemma_of("watches") == "watch"
    # `-ses` NO es plural sibilante: `closes` es `close`, no `clos`.
    assert semantics.lemma_of("closes") == "close"
    # Demasiado corto para tocarlo: se devuelve tal cual.
    assert semantics.lemma_of("go") == "go"
    assert semantics.lemma_of("BANKED") == "bank"


def test_lemma_of_never_raises_on_garbage():
    assert semantics.lemma_of(None) == ""
    assert semantics.lemma_of(123) == ""
    assert semantics.lemma_of("!!!") == ""
    assert semantics.lemma_of("") == ""


def test_lemma_variants_restore_the_silent_e():
    # `making` → stem `mak`; la variante con `e` es lo que permite que la glosa
    # «to make» solape con el texto aunque la forma esté flexionada.
    assert "make" in semantics.lemma_variants("making")
    assert "run" in semantics.lemma_variants("running")
    assert semantics.lemma_variants("bank") == frozenset({"bank"})


def test_gloss_tokens_drops_stopwords_and_deduplicates():
    assert semantics.gloss_tokens("a place for money and loans") == [
        "place",
        "money",
        "loans",
    ]
    assert semantics.gloss_tokens("to decide something") == ["decide"]
    assert semantics.gloss_tokens(None) == []
    assert semantics.gloss_tokens(123) == []


# --------------------------------------------------------------- ventana y solape


def test_context_window_is_bounded_and_inclusive():
    tokens = ["a", "b", "c", "d", "e"]
    assert semantics.context_window(tokens, 2, size=1) == ["b", "c", "d"]
    # En los bordes se recorta, no se inventa.
    assert semantics.context_window(tokens, 0, size=2) == ["a", "b", "c"]
    assert semantics.context_window([], 0, size=2) == []


def test_sense_overlap_matches_inflections_via_lemma():
    window = ["she", "decides", "the", "trip"]
    assert semantics.sense_overlap(window, "to decide") == 1


def test_sense_overlap_is_zero_without_lexical_contact():
    window = ["the", "river", "bank", "was", "beautiful"]
    assert semantics.sense_overlap(window, "a financial place") == 0
    assert semantics.sense_overlap(window, "river side") == 1


def test_sense_overlap_never_raises_on_garbage():
    assert semantics.sense_overlap(None, None) == 0
    assert semantics.sense_overlap(["x"], 123) == 0


# ------------------------------------------------------------------- lemma → sense

_FINANCIAL = {"pos": "noun", "gloss": "a place for money and loans"}
_RIVER = {"pos": "noun", "gloss": "river side"}


def test_select_sense_prefers_the_family_that_matches_the_role():
    senses = [
        {"pos": "noun", "gloss": "a financial place"},
        {"pos": "verb", "gloss": "to tilt an aircraft"},
    ]
    tokens = ["i", "bank", "money", "every", "day"]
    picked = semantics.select_sense("bank", tokens, 1, senses)
    assert picked["index"] == 1
    assert picked["pos"] == "verb"
    assert "role:verb/strong" in picked["reasons"]


def test_select_sense_breaks_the_tie_with_the_gloss_within_the_same_family():
    """El caso que motivó V3.58: dos sentidos de la MISMA familia y el contexto
    decide. Sin la glosa esto es imposible por construcción."""
    senses = [_FINANCIAL, _RIVER]
    river = semantics.select_sense(
        "bank", ["the", "bank", "of", "the", "river", "was"], 1, senses
    )
    money = semantics.select_sense(
        "bank", ["the", "bank", "manager", "explained", "the", "loan"], 1, senses
    )
    assert river["index"] == 1
    assert river["gloss"] == "river side"
    assert money["index"] == 0
    assert money["gloss"] == "a place for money and loans"


def test_select_sense_is_stable_without_any_signal():
    senses = [_FINANCIAL, _RIVER]
    picked = semantics.select_sense(
        "bank", ["the", "bank", "was", "closed"], 1, senses
    )
    # Empate real: gana el primer sentido declarado (estable, determinista).
    assert picked["index"] == 0
    assert picked["score"] == 0


def test_select_sense_without_senses_returns_none():
    picked = semantics.select_sense("bank", ["the", "bank"], 1, [])
    assert picked["index"] is None
    assert picked["gloss"] == ""
    assert picked["score"] == 0
    assert semantics.select_sense("bank", None, 0, None)["index"] is None


# ------------------------------------------- sense → semantic_fit (veredicto V3.44)


def test_sense_fit_resolves_the_sense_without_changing_the_verdict():
    payload = semantics.sense_fit(
        "bank",
        "The bank of the river was beautiful.",
        senses=[_FINANCIAL, _RIVER],
    )
    # La familia nominal encaja con el rol nominal → `fit`, como en V3.44.
    assert payload["adequacy"] == semantics.SENSE_FIT
    # Y V3.58 NOMBRA el sentido entendido.
    assert payload["sense_gloss"] == "river side"
    assert payload["sense_pos"] == "noun"
    assert payload["sense_index"] == 1


_V344_CORPUS = (
    (
        "look after",
        "I look after my sister every day.",
        [{"pos": "verb", "gloss": "to care for"}],
        "unknown",
    ),
    (
        "plan",
        "I plan my trip next week.",
        [
            {"pos": "noun", "gloss": "an arrangement"},
            {"pos": "verb", "gloss": "to decide to do something"},
        ],
        "fit",
    ),
    (
        "bank",
        "I bank there. The bank is closed.",
        [{"pos": "noun", "gloss": "a financial place"}],
        "fit",
    ),
    (
        "bank",
        "I bank money every day.",
        [{"pos": "noun", "gloss": "a financial place"}],
        "incorrect",
    ),
    (
        "take",
        "The take was long today.",
        [{"pos": "verb", "gloss": "to grab"}],
        "suspect",
    ),
    (
        "bank",
        "They will bank the money tomorrow.",
        [{"pos": "noun", "gloss": "a financial place"}],
        "incorrect",
    ),
    ("travel", "I go by train.", [{"pos": "verb", "gloss": "to journey"}], "unknown"),
    ("travel", "I travel by train.", [], "unknown"),
)


@pytest.mark.parametrize("word, text, senses, expected", _V344_CORPUS)
def test_sense_fit_verdict_is_exactly_the_v344_one(word, text, senses, expected):
    """Invariante de no-regresión: el veredicto NO cambia con la glosa.

    Se compara contra el literal histórico de V3.44 (no contra la propia
    implementación) para que el test siga valiendo aunque las dos rutas cambien
    a la vez."""
    assert semantics.semantic_adequacy(word, text, senses=senses) == expected
    assert semantics.sense_fit(word, text, senses=senses)["adequacy"] == expected


def test_sense_fit_degrades_exactly_without_gloss():
    """Sin glosa no hay desempate posible: el motor queda en V3.44 y el sentido
    resuelto es solo la familia (glosa vacía)."""
    senses = [{"pos": "noun"}, {"pos": "noun"}]
    payload = semantics.sense_fit("bank", "The bank is closed.", senses=senses)
    assert payload["adequacy"] == semantics.SENSE_FIT
    same = semantics.semantic_adequacy("bank", "The bank is closed.", senses=senses)
    assert same == semantics.SENSE_FIT
    assert payload["sense_gloss"] == ""
    assert payload["sense_score"] == 0


def test_sense_fit_keeps_the_pos_fallback_intact():
    payload = semantics.sense_fit("cat", "The cat sleeps.", pos="noun")
    assert payload["adequacy"] == semantics.SENSE_FIT
    assert payload["sense_gloss"] == ""


def test_sense_fit_never_raises_on_garbage():
    for senses in (None, "noun", [1, "x", {"pos": ""}], [{"pos": "noun"}]):
        payload = semantics.sense_fit(None, None, senses=senses)
        assert payload["adequacy"] in semantics.SEMANTIC_ADEQUACIES
        assert isinstance(payload["sense_score"], int)
        assert isinstance(payload["reasons"], tuple)


def test_semantic_adequacy_keeps_its_taxonomy_and_signature():
    assert semantics.semantic_adequacy("travel", "I travel by train.") == (
        semantics.SENSE_UNKNOWN
    )
    for word, text, senses, _expected in _V344_CORPUS:
        got = semantics.semantic_adequacy(word, text, senses=senses)
        assert got in semantics.SEMANTIC_ADEQUACIES


def test_incorrect_is_not_expanded_by_the_gloss():
    """La ausencia de solapamiento NO es una prueba de incompatibilidad: un uso
    correcto sin una sola palabra en común con la glosa sigue siendo `fit`."""
    got = lexicon.score_transfer_attempt(
        "bank",
        "I bank there. The bank is closed.",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )
    assert got["adequacy"] == semantics.SENSE_FIT
    assert got["error_type"] == "correct"


# ------------------------------------------------------------------- contrato


def test_transfer_payload_gains_the_sense_additively():
    got = lexicon.score_transfer_attempt(
        "bank",
        "The bank of the river was beautiful.",
        senses=[_FINANCIAL, _RIVER],
    )
    # Contrato V3.44 intacto…
    assert got["passed"] is True
    assert got["lexical_transfer"] is True
    assert got["adequacy"] == semantics.SENSE_FIT
    assert got["semantic_fit"] is True
    assert got["error_type"] == "correct"
    # …y el sentido resuelto, ADITIVO.
    assert got["sense_gloss"] == "river side"
    assert got["sense_pos"] == "noun"
    assert got["sense_index"] == 1


def test_transfer_payload_keeps_the_blocking_contract():
    got = lexicon.score_transfer_attempt(
        "bank",
        "I bank money every day.",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )
    assert got["adequacy"] == semantics.SENSE_INCORRECT
    assert got["semantic_fit"] is False
    assert got["error_type"] == "semantic_mismatch"


def test_transfer_payload_without_senses_reports_no_sense():
    got = lexicon.score_transfer_attempt("travel", "I travel by train.")
    assert got["adequacy"] == semantics.SENSE_UNKNOWN
    assert got["sense_gloss"] == ""
    assert got["sense_index"] is None


# ------------------------------------------------------------- end-to-end (HTTP)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(uid: str, word: str, *, cefr: str = "A1") -> None:
    vocabulary_repo.seed_curriculum_items(
        uid,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(uid, [word])


def test_transfer_endpoint_exposes_the_resolved_sense(monkeypatch, tmp_path):
    """El sentido resuelto entra en el CONTRATO HTTP: deja de ser dato inerte."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "bank")
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="a place for money and loans",
        senses=[_FINANCIAL, _RIVER],
    )

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "bank",
                "text": "The bank of the river was beautiful.",
                "context_id": "transfer:story",
            },
        )

    assert res.status_code == 200, res.text
    body = res.json()
    # La adecuación y el bloqueo NO cambian (contrato V3.44 intacto)…
    assert body["passed"] is True
    assert body["adequacy"] == "fit"
    assert body["error_type"] == "correct"
    # …y el sentido entendido viaja ya en la respuesta, ADITIVO.
    assert body["sense_gloss"] == "river side"
    assert body["sense_pos"] == "noun"
    assert body["sense_index"] == 1
    assert body["sense_score"] == 1

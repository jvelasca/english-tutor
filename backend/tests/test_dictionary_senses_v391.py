"""Tests del contrato de ACEPCIÓN del diccionario de sentidos (V3.91, fase 2).

V3.44 declaró los sentidos como `{pos, gloss}` y el Sense Engine los usó para
juzgar la adecuación semántica; el sentido nunca llegaba a la pantalla, así que
la ficha no podía DESAMBIGUAR. V3.91 convierte el sentido en la unidad que la
ficha pinta —`{term, pos, gloss, domain, proper_noun, example, context, lemma,
source}`— y esta suite fija las cuatro cosas que hacen que ese cambio sea
honesto:

1. **La forma del contrato.** Las nueve claves, siempre, en el orden de lectura
   (`SENSE_KEYS`): un campo que el modelo no dio queda `""`/`False`, nunca
   ausente, y una fila de la caché anterior se sirve TAL CUAL (sin inventar
   contenido: la política es regenerarla, no disfrazarla).
2. **Qué NO se copia del modelo.** `lemma` se acepta solo si la morfología pura
   de la app reconoce la relación con la cabeza, y `source` lo sella quien
   genera: los dos son DERIVADOS, así que un modelo no puede inventarse una
   forma base ni declarar una procedencia que no tiene.
3. **La identidad del scoring no cambia.** La deduplicación por `(pos, gloss)` y
   la regla de `pos` canónico son las de V3.44, y los campos nuevos no alteran ni
   las familias POS ni la resolución del sentido (`sense_fit`).
4. **La caché anterior se regenera.** `GENERATOR_VERSION` sube a 1.7.0 y una
   fila de 1.6.0 deja de ser fresca: se regenera una sola vez al primer lookup.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from services import dictionary_content, semantics

# Cabeza de la entrada de prueba: la relación de lema se verifica contra ella.
_WORD = "bank"


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


def _raw(**sense: object) -> list[dict]:
    """Una acepción cruda del modelo con todo lo que suele declarar."""
    base: dict = {
        "term": "banco",
        "pos": "noun",
        "gloss": "a financial place",
        "domain": "finance",
        "proper_noun": False,
        "example": "She works at the bank on the corner.",
        "context": "money and finance",
        "lemma": "bank",
    }
    base.update(sense)
    return [base]


# --- forma del contrato -------------------------------------------------------


def test_the_contract_has_nine_keys_in_reading_order():
    assert dictionary_content.SENSE_KEYS == (
        "term",
        "pos",
        "gloss",
        "domain",
        "proper_noun",
        "example",
        "context",
        "lemma",
        "source",
    )


def test_normalizer_always_emits_the_nine_keys():
    out = dictionary_content.normalize_senses(
        [{"pos": "noun", "gloss": "a financial place"}], word=_WORD
    )
    assert len(out) == 1
    assert tuple(out[0]) == dictionary_content.SENSE_KEYS
    assert out[0] == {
        "term": "",
        "pos": "noun",
        "gloss": "a financial place",
        "domain": "",
        "proper_noun": False,
        "example": "",
        "context": "",
        "lemma": "",
        "source": dictionary_content.SENSE_SOURCE_MODEL,
    }


def test_normalizer_keeps_the_declared_fields_and_collapses_whitespace():
    out = dictionary_content.normalize_senses(
        _raw(term="  banco   de   arena ", gloss=" a   river bank "),
        word=_WORD,
    )
    assert out[0]["term"] == "banco de arena"
    assert out[0]["gloss"] == "a river bank"


def test_normalizer_caps_the_example_and_the_context():
    out = dictionary_content.normalize_senses(
        _raw(
            example="x" * (dictionary_content.MAX_SENSE_EXAMPLE_CHARS + 40),
            context="c" * (dictionary_content.MAX_CONTEXT_CHARS + 20),
        ),
        word=_WORD,
    )
    assert len(out[0]["example"]) == dictionary_content.MAX_SENSE_EXAMPLE_CHARS
    assert len(out[0]["context"]) == dictionary_content.MAX_CONTEXT_CHARS


def test_proper_noun_accepts_only_a_real_boolean():
    """El string `"false"` es *truthy* en Python: solo el boolean marca."""
    out = dictionary_content.normalize_senses(
        [
            {"pos": "noun", "gloss": "a place", "proper_noun": "false"},
            {"pos": "noun", "gloss": "a brand", "proper_noun": True},
        ],
        word=_WORD,
    )
    assert out[0]["proper_noun"] is False
    assert out[1]["proper_noun"] is True


def test_identity_of_the_scoring_is_unchanged_dedupe_and_cap():
    """La identidad sigue siendo `(pos, gloss)`: el `term` no cambia el dedupe."""
    duplicated = [
        {"pos": "noun", "gloss": "a place", "term": "banco"},
        {"pos": "noun", "gloss": "a place", "term": "otro"},
    ]
    assert len(dictionary_content.normalize_senses(duplicated, word=_WORD)) == 1
    many = [
        {"pos": "noun", "gloss": f"sense {index}"}
        for index in range(dictionary_content.MAX_SENSES + 3)
    ]
    assert len(dictionary_content.normalize_senses(many, word=_WORD)) == (
        dictionary_content.MAX_SENSES
    )
    # La regla de V3.44 sigue en pie: sin `pos` canónico no hay acepción.
    assert dictionary_content.normalize_senses([{"pos": "adverbial"}]) == []


# --- lo que NO se copia del modelo -------------------------------------------


@pytest.mark.parametrize(
    ("declared", "expected"),
    (
        ("bank", "bank"),  # la propia cabeza
        ("banks", "banks"),  # la cabeza es una forma de él
        ("Bank", "bank"),  # normalizado
    ),
)
def test_lemma_is_accepted_when_the_engine_recognizes_the_relation(
    declared, expected
):
    out = dictionary_content.normalize_senses(_raw(lemma=declared), word=_WORD)
    assert out[0]["lemma"] == expected


def test_lemma_is_rejected_when_it_is_invented():
    """Un lema que la morfología no reconoce no se sirve: la ficha lo omite."""
    for invented in ("banca", "banquillo", "limar", "xyz"):
        out = dictionary_content.normalize_senses(_raw(lemma=invented), word=_WORD)
        assert out[0]["lemma"] == ""


def test_lemma_of_an_inflected_headword_accepts_the_base_form():
    out = dictionary_content.normalize_senses(_raw(lemma="bank"), word="banks")
    assert out[0]["lemma"] == "bank"


def test_lemma_is_empty_without_a_headword():
    """Sin cabeza no hay relación que verificar: el modelo no puede declararlo."""
    out = dictionary_content.normalize_senses(_raw(lemma="bank"))
    assert out[0]["lemma"] == ""


def test_source_is_stamped_by_the_caller():
    model = dictionary_content.normalize_senses(_raw(), word=_WORD)
    assert model[0]["source"] == dictionary_content.SENSE_SOURCE_MODEL
    # Reservado al lexicón offline de la fase 3: el contrato ya lo admite.
    lexicon = dictionary_content.normalize_senses(
        _raw(), word=_WORD, source=dictionary_content.SENSE_SOURCE_LEXICON
    )
    assert lexicon[0]["source"] == dictionary_content.SENSE_SOURCE_LEXICON


# --- parse_content: la cabeza correcta en cada dirección ----------------------


def test_parse_content_verifies_the_lemma_against_the_headword():
    out = dictionary_content.parse_content(
        json.dumps(
            {
                "pos": "noun",
                "definition": "A financial place.",
                "translation": "banco",
                "senses": _raw(lemma="bank"),
            }
        ),
        word="banks",
    )
    assert out["senses"][0]["lemma"] == "bank"
    assert out["senses"][0]["source"] == dictionary_content.SENSE_SOURCE_MODEL
    assert out["senses"][0]["example"] == "She works at the bank on the corner."
    assert out["senses"][0]["context"] == "money and finance"


def test_parse_reverse_content_verifies_the_lemma_against_the_english_side():
    out = dictionary_content.parse_reverse_content(
        json.dumps(
            {
                "english": "banks",
                "pos": "noun",
                "definition": "Financial places.",
                "senses": _raw(lemma="bank", term="bancos"),
            }
        ),
        word="bancos",
    )
    # La cabeza es el EQUIVALENTE INGLÉS, no el término español buscado.
    assert out["senses"][0]["lemma"] == "bank"
    assert out["senses"][0]["term"] == "bancos"


def test_both_prompts_ask_for_the_rich_sense_and_the_same_order():
    for prompt in (
        dictionary_content._SYSTEM_PROMPT,
        dictionary_content._REVERSE_SYSTEM_PROMPT,
    ):
        assert '"term"' in prompt
        assert '"example"' in prompt
        assert '"context"' in prompt
        assert "SAME order" in prompt
    assert dictionary_content.GENERATOR_VERSION == "1.7.0"


# --- persistencia ------------------------------------------------------------


def test_repository_round_trips_the_nine_fields(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    senses = dictionary_content.normalize_senses(_raw(), word=_WORD)
    assert dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="A financial place.",
        translation="banco",
        senses=senses,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    stored = dictionary_repo.get_entry("bank")
    assert stored["senses"] == senses
    assert stored["senses_json"] == json.dumps(
        senses, ensure_ascii=False, separators=(",", ":")
    )
    # Y la fila completa la devuelve también la consulta dirigida de la fase 1.
    assert dictionary_repo.find_by_words(["bank"])[0]["senses"] == senses


def test_legacy_row_is_served_as_declared_and_regenerated(monkeypatch, tmp_path):
    """Una fila de 1.6.0 (`{pos, gloss}`) no se rellena: se marca obsoleta."""
    _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="A financial place.",
        translation="banco",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
        generator_version="1.6.0",
    )
    stored = dictionary_repo.get_entry("bank")
    assert stored["senses"] == [{"pos": "noun", "gloss": "a financial place"}]
    # El contenido viejo ya no se sirve como fresco: se regenera al primer lookup.
    assert not vocabulary_domain._content_is_fresh(stored)


def test_decode_ignores_unknown_keys_and_coerces_types(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, senses_json, generator_version, "
            "created_at) VALUES ('bank', 'noun', 'def', 'banco', ?, '1.7.0', 'x')",
            (
                json.dumps(
                    [
                        {
                            "term": "banco",
                            "pos": "noun",
                            "gloss": "a place",
                            "proper_noun": "true",
                            "inventado": "no viaja",
                        }
                    ]
                ),
            ),
        )
    stored = dictionary_repo.get_entry("bank")
    assert stored["senses"] == [
        {"term": "banco", "pos": "noun", "gloss": "a place", "proper_noun": False}
    ]


# --- el contrato llega a la API ----------------------------------------------


def test_dictionary_lookup_exposes_the_rich_senses(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    senses = dictionary_content.normalize_senses(
        _raw(example="I sat on the bank of the river.", context="at a river"),
        word=_WORD,
    )
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="A financial place.",
        translation="banco",
        senses=senses,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}", json={"word": "bank"}
        )
    assert res.status_code == 200, res.text
    served = res.json()["senses"]
    assert served == senses
    assert served[0]["example"] == "I sat on the bank of the river."
    assert served[0]["context"] == "at a river"


# --- no-regresión del scoring semántico --------------------------------------


def test_rich_senses_do_not_change_the_semantic_verdict():
    """Los campos nuevos no entran en el juicio: `sense_fit` no puede cambiar.

    El Sense Engine lee `pos` y `gloss` (V3.44/V3.58) y la frontera es que la
    glosa decide el SENTIDO, nunca el VEREDICTO. Se comprueba comparando la
    acepción rica con la misma acepción reducida al contrato viejo.
    """
    rich = dictionary_content.normalize_senses(_raw(), word=_WORD)
    legacy = [{"pos": item["pos"], "gloss": item["gloss"]} for item in rich]
    text = "She works at the bank on the corner."
    for senses in (rich, legacy):
        assert semantics.semantic_adequacy("bank", text, senses=senses) == (
            semantics.semantic_adequacy("bank", text, senses=legacy)
        )
        assert semantics.families_from_senses(senses) == (
            semantics.families_from_senses(legacy)
        )
        assert semantics.sense_fit("bank", text, senses=senses) == (
            semantics.sense_fit("bank", text, senses=legacy)
        )

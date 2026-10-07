"""Tests de V3.88.0: el diccionario garantiza varios significados.

V3.86.0 construyó la plomería del diccionario polisémico (`meanings` hasta 6,
`meanings_json`, selector en la tarjeta), pero el prompt pedía «at most 6» sin
exigir ninguno: el modelo devolvía un solo significado para casi todo y el
selector nacía con una única opción. V3.88.0 cierra ese hueco por el lado del
contrato de contenido:

- `MIN_MEANINGS` se declara en AMBOS prompts (EN→ES y ES→EN);
- `GENERATOR_VERSION` subió a 1.6.0 (hoy es 1.8.0 desde V3.95.0), lo que invalida
  la caché anterior y la regenera una sola vez al primer lookup;
- la normalización y la frescura de caché conservan lo que ya garantizaban:
  orden del más común al menos, sin duplicados, con los nombres propios al
  final.
"""

import json

from domain import vocabulary as vocabulary_domain
from services import dictionary_content

# --- Contrato del prompt ----------------------------------------------------


def test_both_prompts_demand_a_minimum_of_meanings():
    """La regla de recuento es un literal verificable en los dos prompts."""
    assert dictionary_content.MIN_MEANINGS == 2
    assert dictionary_content.MAX_MEANINGS == 6
    rule = dictionary_content._MEANINGS_COUNT_RULE
    assert f"at least {dictionary_content.MIN_MEANINGS}" in rule
    assert f"at most {dictionary_content.MAX_MEANINGS}" in rule
    assert rule in dictionary_content._SYSTEM_PROMPT
    assert rule in dictionary_content._REVERSE_SYSTEM_PROMPT


def test_both_prompts_forbid_a_single_meaning_for_polysemous_words():
    """No basta con el número: el prompt dice que NO se devuelva solo uno."""
    for prompt in (
        dictionary_content._SYSTEM_PROMPT,
        dictionary_content._REVERSE_SYSTEM_PROMPT,
    ):
        assert "NEVER return only one" in prompt


def test_generator_version_bump_invalidates_previous_cache():
    """V3.95.0: 1.7.0 → 1.8.0 es la palanca que regenera la caché anterior.

    El salto acompaña al guardarraíl de retrotraducción: las filas antiguas
    (p. ej. «broca» → «rock») se tratan como no frescas y se regeneran al
    consultarlas, ya bajo verificación.
    """
    assert dictionary_content.GENERATOR_VERSION == "1.8.0"


# --- Frescura de caché ------------------------------------------------------


def _entry(version: str, definition: str = "A short definition.") -> dict:
    return {"definition": definition, "generator_version": version}


def test_freshness_accepts_current_version_and_rejects_the_previous_one():
    assert vocabulary_domain._content_is_fresh(
        _entry(dictionary_content.GENERATOR_VERSION)
    )
    # La caché de V3.86.0 ya no se sirve como fresca.
    assert not vocabulary_domain._content_is_fresh(_entry("1.5.0"))
    # Sin definición tampoco vale, aunque la versión coincida.
    assert not vocabulary_domain._content_is_fresh(_entry("1.6.0", definition=""))


# --- Normalización de significados ------------------------------------------


def test_normalize_meanings_keeps_order_and_pushes_proper_nouns_last():
    raw = [
        {"term": "file", "pos": "noun", "gloss": "tool", "domain": "tools"},
        {"term": "Lima", "pos": "noun", "gloss": "capital", "proper_noun": True},
        {"term": "lime", "pos": "noun", "gloss": "fruit", "domain": "food"},
    ]
    out = dictionary_content.normalize_meanings(raw)
    assert [m["term"] for m in out] == ["file", "lime", "Lima"]
    assert out[-1]["proper_noun"] is True


def test_normalize_meanings_dedupes_case_insensitively():
    raw = [
        {"term": "Bank", "pos": "noun", "gloss": "financial"},
        {"term": "bank", "pos": "noun", "gloss": "duplicate"},
    ]
    out = dictionary_content.normalize_meanings(raw)
    assert [m["term"] for m in out] == ["Bank"]


def test_normalize_meanings_truncates_to_the_hard_cap():
    raw = [
        {"term": f"term-{i}", "pos": "noun", "gloss": "x"} for i in range(10)
    ]
    out = dictionary_content.normalize_meanings(raw)
    assert len(out) == dictionary_content.MAX_MEANINGS


def test_default_meaning_is_the_first_common_one():
    """El defecto nunca es un nombre propio (contrato de V3.86.0, intacto)."""
    meanings = dictionary_content.normalize_meanings(
        [
            {"term": "Lima", "pos": "noun", "gloss": "capital", "proper_noun": True},
            {"term": "file", "pos": "noun", "gloss": "tool"},
        ]
    )
    assert dictionary_content.default_meaning_term(meanings) == "file"


def test_parse_content_keeps_every_meaning_the_model_returned():
    """El parseo no recorta la lista: si el modelo da 3, llegan 3."""
    payload = {
        "pos": "noun",
        "definition": "A flat object.",
        "translation": "hoja",
        "meanings": [
            {"term": "hoja", "pos": "noun", "gloss": "de planta"},
            {"term": "sábana", "pos": "noun", "gloss": "de cama", "domain": "home"},
            {"term": "folio", "pos": "noun", "gloss": "de papel"},
        ],
    }
    out = dictionary_content.parse_content(_dump(payload), word="sheet")
    assert [m["term"] for m in out["meanings"]] == ["hoja", "sábana", "folio"]


def test_parse_reverse_content_keeps_every_equivalent():
    payload = {
        "english": "sheet",
        "pos": "noun",
        "definition": "A flat object.",
        "meanings": [
            {"term": "sheet", "pos": "noun", "gloss": "of paper"},
            {"term": "leaf", "pos": "noun", "gloss": "of a plant", "domain": "botany"},
        ],
    }
    out = dictionary_content.parse_reverse_content(_dump(payload), word="hoja")
    assert [m["term"] for m in out["meanings"]] == ["sheet", "leaf"]


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)

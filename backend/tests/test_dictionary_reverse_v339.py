"""Tests del diccionario reversible ES→EN (V3.39).

Cubre las dos piezas de la dirección inversa:

- la búsqueda INSTANTÁNEA (`services.dictionary_reverse`, pura) sobre las
  traducciones ya cacheadas en `dictionary_entries`, y
- la GENERACIÓN ES→EN con el modelo local cuando no hay coincidencia, cacheada
  en la tabla propia `dictionary_reverse_entries`.

Invariantes del proyecto que se verifican aquí: la consulta sigue siendo SOLO
LECTURA (D3: ni `vocabulary` ni `vocabulary_events` cambian) y la caché inversa
está AISLADA de `dictionary_entries`, que es el banco de distractores del MCQ
de Recognition (`services/dictionary_mcq.py`).
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content, dictionary_reverse


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _payload(
    english: str = "cat",
    pos: str = "noun",
    definition: str = "A small domesticated carnivorous mammal.",
    situation: str = "",
) -> str:
    return json.dumps(
        {
            "english": english,
            "pos": pos,
            "definition": definition,
            "situation": situation,
        }
    )


def _stub_reverse_fetcher(monkeypatch, payload: str, calls: list):
    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return payload

    monkeypatch.setattr(dictionary_content, "_reverse_fetcher", _fake)


def _offline_reverse_fetcher(monkeypatch, calls: list):
    async def _offline(word: str, model: str | None) -> str:
        calls.append((word, model))
        raise dictionary_content.ContentUnavailableError("test: sin modelo")

    monkeypatch.setattr(dictionary_content, "_reverse_fetcher", _offline)


def _reverse_lookup(uid: str, word: str) -> dict:
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": word, "direction": "es-en"},
        )
        assert res.status_code == 200, res.text
        return res.json()


def _seed_direct(word: str, translation: str, definition: str = "A meaning.") -> None:
    assert dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=definition,
        translation=translation,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )


# --- matcher puro ------------------------------------------------------------


def test_normalize_term_folds_accents_but_keeps_ene():
    assert dictionary_reverse.normalize_term("  Camión, ") == "camion"
    # La eñe NO se pliega: "año" y "ano" son palabras distintas.
    assert dictionary_reverse.normalize_term("Mañana") == "mañana"
    assert dictionary_reverse.fold("AÑO") == "año"
    assert dictionary_reverse.normalize_term("…") == ""


def test_match_translation_exact_and_gloss_segments():
    entries = [{"word": "cat", "translation": "gato, felino"}]
    assert dictionary_reverse.match_translation("gato", entries) == ["cat"]
    assert dictionary_reverse.match_translation("felino", entries) == ["cat"]
    assert dictionary_reverse.match_translation("perro", entries) == []


def test_match_translation_ranks_exact_before_partial():
    entries = [
        {"word": "country house", "translation": "casa de campo"},
        {"word": "house", "translation": "casa"},
    ]
    # La coincidencia EXACTA ("casa" == "casa") va antes que la parcial
    # ("casa" ~ "casa de campo").
    assert dictionary_reverse.match_translation("casa", entries) == [
        "house",
        "country house",
    ]


def test_match_translation_strips_leading_articles_and_parentheses():
    entries = [{"word": "dog", "translation": "el perro (animal)"}]
    assert dictionary_reverse.match_translation("perro", entries) == ["dog"]


def test_match_translation_is_accent_tolerant():
    entries = [{"word": "truck", "translation": "camión"}]
    assert dictionary_reverse.match_translation("camion", entries) == ["truck"]
    assert dictionary_reverse.match_translation("camión", entries) == ["truck"]


def test_match_translation_dedupes_and_ignores_empty():
    entries = [
        {"word": "home", "translation": "casa"},
        {"word": "home", "translation": "hogar, casa"},
        {"word": "", "translation": "casa"},
    ]
    assert dictionary_reverse.match_translation("casa", entries) == ["home"]
    assert dictionary_reverse.match_translation("", entries) == []


# --- inversa instantánea (sin modelo) ----------------------------------------


def test_reverse_lookup_uses_cached_translation_without_model(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato, felino", definition="A small carnivorous mammal.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "gato")

    assert data["direction"] == "es-en"
    assert data["word"] == "gato"
    assert data["translation"] == "cat"
    assert data["definition_source"] == "llm"
    assert data["definition"] == "A small carnivorous mammal."
    assert data["alternatives"] == []
    # La inversa instantánea no llama al modelo ni escribe caché inversa.
    assert calls == []
    assert _count_rows("dictionary_reverse_entries") == 0


def test_reverse_lookup_exposes_alternatives(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")
    _seed_direct("kitty", "gato")
    _seed_direct("pussycat", "gato, felino")

    data = _reverse_lookup(a, "gato")

    assert data["translation"] == "cat"
    assert set(data["alternatives"]) == {"kitty", "pussycat"}


def test_reverse_lookup_tracks_english_word_usage(monkeypatch, tmp_path):
    """La marca de uso es la del EQUIVALENTE INGLÉS, no la del término español."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")
    assert vocabulary_repo.record_words(a, ["cat"]) is True

    data = _reverse_lookup(a, "gato")

    assert data["usage"]["tracked"] is True
    assert data["usage"]["surface"]["production_count"] == 1


# --- generación ES→EN --------------------------------------------------------


def test_reverse_lookup_generates_persists_and_caches(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(
        monkeypatch,
        _payload(
            english="house",
            definition="A building where people live.",
        ),
        calls,
    )

    first = _reverse_lookup(a, "casa")

    assert first["direction"] == "es-en"
    assert first["word"] == "casa"
    assert first["translation"] == "house"
    assert first["definition"] == "A building where people live."
    assert first["definition_source"] == "llm"
    assert calls == [("casa", None)]
    assert _count_rows("dictionary_reverse_entries") == 1

    # Segunda consulta: caché fresca, sin nueva llamada al modelo.
    second = _reverse_lookup(a, "Casa")
    assert second["translation"] == "house"
    assert calls == [("casa", None)]


def test_reverse_lookup_uses_reverse_cache_even_if_direct_cache_present(
    monkeypatch, tmp_path
):
    """Sin coincidencia de traducción se genera aunque haya caché directa."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("house", "casa, hogar")
    # El término "vivienda" no aparece en ninguna traducción cacheada.
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="dwelling"), calls)

    data = _reverse_lookup(a, "vivienda")

    assert calls == [("vivienda", None)]
    assert data["translation"] == "dwelling"
    assert data["definition_source"] == "llm"


def test_reverse_lookup_degrades_when_model_unavailable(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "vivienda")

    assert data["definition_source"] == "none"
    assert data["translation"] is None
    assert data["word"] == "vivienda"
    assert calls == [("vivienda", None)]
    assert _count_rows("dictionary_reverse_entries") == 0


def test_reverse_lookup_punctuation_only_is_422(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "…", "direction": "es-en"},
        )
    assert res.status_code == 422


def test_reverse_lookup_is_read_only_no_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)
    before_vocab = _count_rows("vocabulary")
    before_events = _count_rows("vocabulary_events")

    _reverse_lookup(a, "casa")

    assert _count_rows("vocabulary") == before_vocab
    assert _count_rows("vocabulary_events") == before_events


def test_reverse_cache_does_not_pollute_mcq_bank(monkeypatch, tmp_path):
    """`list_entries()` (banco de distractores) sigue solo con inglés."""
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)

    _reverse_lookup(a, "casa")

    assert dictionary_repo.list_entries() == []
    assert len(dictionary_repo.list_reverse_entries()) == 1


def test_reverse_content_version_is_current(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)

    _reverse_lookup(a, "casa")

    stored = dictionary_repo.get_reverse_entry("casa")
    assert stored is not None
    assert stored["english"] == "house"
    assert stored["generator_version"] == dictionary_content.GENERATOR_VERSION


# --- compatibilidad de la dirección por defecto ------------------------------


def test_direction_defaults_to_en_es(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")

    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "cat"},
        )
        assert res.status_code == 200, res.text
        data = res.json()

    assert data["direction"] == "en-es"
    assert data["word"] == "cat"
    assert data["translation"] == "gato"
    assert data["alternatives"] == []
    assert dictionary_repo.list_reverse_entries() == []


# --- parse_reverse_content (puro) --------------------------------------------


def test_parse_reverse_content_requires_english():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_reverse_content(
            json.dumps({"pos": "noun", "definition": "A meaning."})
        )


def test_parse_reverse_content_validates_definition():
    out = dictionary_content.parse_reverse_content(_payload())
    assert out["english"] == "cat"
    assert out["pos"] == "noun"
    assert out["definition"].startswith("A small")

    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_reverse_content(
            json.dumps({"english": "cat", "definition": ""})
        )


def test_generate_reverse_content_uses_injected_fetcher():
    import asyncio

    async def _fake(_word: str, _model: str | None) -> str:
        return _payload(english="house")

    out = asyncio.run(
        dictionary_content.generate_reverse_content("casa", fetcher=_fake)
    )
    assert out["english"] == "house"

"""Tests del generador de contenido del diccionario (V3.30, Fase B).

Cubre el parseo tolerante de la respuesta JSON del modelo local, la generación
con fetcher inyectable (sin red), la persistencia idempotente
(`INSERT OR IGNORE`) en la caché global `dictionary_entries` y la degradación a
`definition_source="none"` cuando el modelo no está disponible o la respuesta
no valida. Todo el contenido es idioma, no evidencia: `vocabulary` y
`vocabulary_events` nunca cambian por una consulta (D3).
"""

import asyncio
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
from services import dictionary_content


def _payload(
    pos: str = "noun",
    definition: str = "A small domesticated carnivorous mammal.",
    translation: str = "gato",
) -> str:
    return json.dumps(
        {"pos": pos, "definition": definition, "translation": translation}
    )


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _lookup(uid: str, word: str, *, model: str | None = None) -> dict:
    body = {"word": word}
    if model is not None:
        body["model"] = model
    with TestClient(app) as client:
        res = client.post(f"/api/vocabulary/dictionary?user_id={uid}", json=body)
        assert res.status_code == 200, res.text
        return res.json()


def _stub_fetcher(monkeypatch, payload: str, calls: list):
    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return payload

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)


# --- parse_content (puro, sin red) -------------------------------------------


def test_parse_returns_valid_content():
    out = dictionary_content.parse_content(_payload())
    assert out == {
        "pos": "noun",
        "definition": "A small domesticated carnivorous mammal.",
        "translation": "gato",
    }


def test_parse_strips_markdown_fences():
    raw = f"```json\n{_payload()}\n```"
    assert dictionary_content.parse_content(raw)["definition"].startswith("A small")


def test_parse_tolerates_surrounding_text():
    raw = f"Sure! Here you go:\n{_payload()}\nHope that helps."
    out = dictionary_content.parse_content(raw)
    assert out["translation"] == "gato"


def test_parse_lowercases_and_validates_pos():
    assert dictionary_content.parse_content(_payload(pos="Verb"))["pos"] == "verb"


def test_parse_unknown_pos_is_blank():
    out = dictionary_content.parse_content(_payload(pos="adverbio"))
    assert out["pos"] == ""


def test_parse_rejects_non_object_json():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content("[1, 2, 3]")


def test_parse_rejects_missing_definition():
    raw = json.dumps({"pos": "noun", "translation": "gato"})
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content(raw)


def test_parse_rejects_empty_definition():
    raw = json.dumps({"pos": "noun", "definition": "  ", "translation": "gato"})
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content(raw)


def test_parse_rejects_malformed_json():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content("{pos: noun, definition: hola}")


def test_parse_rejects_response_without_json():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content("Lo siento, no tengo esa palabra.")


def test_parse_rejects_oversized_definition():
    raw = _payload(definition="a" * (dictionary_content.MAX_DEFINITION_CHARS + 1))
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content(raw)


def test_parse_truncates_oversized_translation():
    raw = _payload(translation="t" * (dictionary_content.MAX_TRANSLATION_CHARS + 50))
    out = dictionary_content.parse_content(raw)
    assert len(out["translation"]) == dictionary_content.MAX_TRANSLATION_CHARS


def test_parse_rejects_empty_raw():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_content("   ")


# --- generate_content (fetcher inyectado, sin red) ----------------------------


def test_generate_content_uses_fetcher_and_parses():
    calls: list = []

    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return _payload()

    out = asyncio.run(
        dictionary_content.generate_content("cat", model="llama3.1:8b", fetcher=_fake)
    )
    assert calls == [("cat", "llama3.1:8b")]
    assert out["pos"] == "noun"
    assert out["translation"] == "gato"


def test_generate_content_propagates_unavailable():
    async def _down(_word: str, _model: str | None) -> str:
        raise dictionary_content.ContentUnavailableError("modelo caído")

    with pytest.raises(dictionary_content.ContentUnavailableError):
        asyncio.run(dictionary_content.generate_content("cat", fetcher=_down))


def test_generate_content_rejects_invalid_parse():
    async def _garbage(_word: str, _model: str | None) -> str:
        return "no json here"

    with pytest.raises(dictionary_content.ContentUnavailableError):
        asyncio.run(dictionary_content.generate_content("cat", fetcher=_garbage))


# --- persistencia y degradación en el endpoint --------------------------------


def test_first_lookup_generates_and_caches(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    data = _lookup(a, "cat")

    assert calls == [("cat", None)]
    assert data["definition_source"] == "llm"
    assert data["pos"] == "noun"
    assert data["definition"] == "A small domesticated carnivorous mammal."
    assert data["translation"] == "gato"
    row = (
        sqlite3.connect(db.DB_PATH)
        .execute("SELECT word, pos, definition, translation FROM dictionary_entries")
        .fetchone()
    )
    assert row == (
        "cat",
        "noun",
        "A small domesticated carnivorous mammal.",
        "gato",
    )


def test_second_lookup_serves_cache_without_regenerating(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    first = _lookup(a, "cat")
    second = _lookup(a, "cat")

    assert first["definition_source"] == "llm"
    assert second["definition"] == first["definition"]
    # El generador solo se invocó en la primera consulta: la caché es
    # determinista y no paga la latencia del modelo dos veces.
    assert len(calls) == 1
    assert _count_rows("dictionary_entries") == 1


def test_lookup_persists_normalized_word(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    data = _lookup(a, "  Cat,  ")

    assert data["word"] == "cat"
    assert calls == [("cat", None)]
    assert _count_rows("dictionary_entries") == 1


def test_lookup_passes_model_preference_to_generator(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    _lookup(a, "cat", model="llama3.1:8b")

    assert calls == [("cat", "llama3.1:8b")]


def test_lookup_degrades_then_recovers(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []

    async def _offline(_word: str, _model: str | None) -> str:
        calls.append("offline")
        raise dictionary_content.ContentUnavailableError("sin modelo")

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _offline)
    degraded = _lookup(a, "cat")
    assert degraded["definition_source"] == "none"
    assert degraded["definition"] is None
    assert _count_rows("dictionary_entries") == 0

    _stub_fetcher(monkeypatch, _payload(), calls)
    recovered = _lookup(a, "cat")
    assert recovered["definition_source"] == "llm"
    assert _count_rows("dictionary_entries") == 1


def test_lookup_content_is_not_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    before_vocab = _count_rows("vocabulary")
    before_events = _count_rows("vocabulary_events")
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    data = _lookup(a, "cat")

    assert data["definition_source"] == "llm"
    assert _count_rows("vocabulary") == before_vocab
    assert _count_rows("vocabulary_events") == before_events
    # Lo único que crece es la caché global de contenido.
    assert _count_rows("dictionary_entries") == 1


def test_insert_failure_still_serves_content_in_memory(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("BD de solo lectura")

    monkeypatch.setattr(dictionary_repo, "insert_entry", _boom)

    data = _lookup(a, "cat")

    # Persistir es opcional: si falla, la consulta sigue sirviendo el contenido
    # generado en memoria sin romper el flujo.
    assert data["definition_source"] == "llm"
    assert data["definition"] == "A small domesticated carnivorous mammal."
    assert _count_rows("dictionary_entries") == 0


def test_repository_insert_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    first = dictionary_repo.insert_entry(
        "cat", pos="noun", definition="def A", translation="gato"
    )
    second = dictionary_repo.insert_entry(
        "cat", pos="verb", definition="def B", translation="gato 2"
    )
    assert first is True
    assert second is False
    stored = dictionary_repo.get_entry("cat")
    assert stored["definition"] == "def A"
    assert stored["pos"] == "noun"


def test_domain_ensure_cached_content_reuses_existing(monkeypatch, tmp_path):
    """Si la caché ya tiene definición, el dominio ni llama al generador."""
    _setup(monkeypatch, tmp_path)
    dictionary_repo.insert_entry(
        "cat", pos="noun", definition="ya en caché", translation="gato"
    )
    called = False

    async def _fake(_word: str, _model: str | None) -> str:
        nonlocal called
        called = True
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)
    cached = dictionary_repo.get_entry("cat")
    out = asyncio.run(
        vocabulary_domain._ensure_cached_content("cat", cached, model=None)
    )
    assert out["definition"] == "ya en caché"
    assert called is False

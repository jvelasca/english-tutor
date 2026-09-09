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


@pytest.fixture(autouse=True)
def _clear_inflight():
    """Limpia el registro de vuelos del dominio entre tests.

    Es estado global por proceso: si una prueba dejara un Future sin resolver
    (p. ej. al fallar a mitad de un vuelo), la siguiente prueba con la misma
    palabra esperaría un Future muerto para siempre.
    """
    vocabulary_domain._inflight_content.clear()
    yield
    vocabulary_domain._inflight_content.clear()


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


def test_parse_picks_first_object_ignoring_trailing_text_and_object():
    """Con dos objetos JSON separados por texto, usa el PRIMERO (V3.30.1: la
    vieja regex greedy `{.*}` intentaba todo desde el primer `{` al último `}`)."""
    raw = (
        '{"pos": "noun", "definition": "first", "translation": "uno"} '
        "más texto entre medias "
        '{"pos": "verb", "definition": "second", "translation": "dos"}'
    )
    out = dictionary_content.parse_content(raw)
    assert out["definition"] == "first"
    assert out["translation"] == "uno"


def test_parse_skips_braces_in_prose_before_object():
    """Llaves sueltas en prosa (JSON no válido) no descarrilan el barrido."""
    raw = 'Nota: usa "{llaves}" sin JSON válido al principio.\n' + _payload()
    out = dictionary_content.parse_content(raw)
    assert out["translation"] == "gato"


def test_parse_ignores_valid_objects_after_invalid_first_one():
    """Si el primer `{…}` no es JSON válido, sigue hasta encontrar uno bueno."""
    raw = "{pos: noun, definition: hola} " + _payload()
    out = dictionary_content.parse_content(raw)
    assert out["definition"] == "A small domesticated carnivorous mammal."


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

    monkeypatch.setattr(dictionary_repo, "save_entry", _boom)

    data = _lookup(a, "cat")

    # Persistir es opcional: si falla, la consulta sigue sirviendo el contenido
    # generado en memoria sin romper el flujo.
    assert data["definition_source"] == "llm"
    assert data["definition"] == "A small domesticated carnivorous mammal."
    assert _count_rows("dictionary_entries") == 0


def test_repository_save_upserts_and_versions(monkeypatch, tmp_path):
    """`save_entry` escribe UNA fila tanto en la primera generación como al
    sobrescribir una versión obsoleta (V3.30.1, P1-03)."""
    _setup(monkeypatch, tmp_path)
    first = dictionary_repo.save_entry(
        "cat",
        pos="noun",
        definition="def A",
        translation="gato",
        generator_version="1.0.0",
    )
    second = dictionary_repo.save_entry(
        "cat",
        pos="verb",
        definition="def B",
        translation="gato 2",
        generator_version="1.1.0",
    )
    assert first is True
    assert second is True
    stored = dictionary_repo.get_entry("cat")
    assert stored["definition"] == "def B"
    assert stored["pos"] == "verb"
    assert stored["generator_version"] == "1.1.0"
    assert _count_rows("dictionary_entries") == 1


def test_domain_ensure_cached_content_reuses_fresh_version(monkeypatch, tmp_path):
    """Si la caché ya tiene definición generada con la versión actual, el
    dominio ni llama al generador (V3.30.1, P1-03)."""
    _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "cat",
        pos="noun",
        definition="ya en caché",
        translation="gato",
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    called = False

    async def _fake(_word: str, _model: str | None) -> str:
        nonlocal called
        called = True
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)
    out = asyncio.run(
        vocabulary_domain._ensure_cached_content("cat", model=None)
    )
    assert out["definition"] == "ya en caché"
    assert called is False


# --- single-flight (V3.30.1, P1-01) -------------------------------------------


def test_concurrent_same_word_generates_once(monkeypatch, tmp_path):
    """N consultas simultáneas de la misma palabra → UNA generación y UNA fila.

    Es la carrera que la persistencia `INSERT OR IGNORE` no deduplicaba: dos
    requests concurrentes llamaban al LLM dos veces. El vuelo comparte el
    Future y todos reciben el mismo resultado."""
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []

    async def _slow(word: str, model: str | None) -> str:
        calls.append(word)
        await asyncio.sleep(0.05)
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _slow)

    async def _run():
        return await asyncio.gather(
            vocabulary_domain._ensure_cached_content("cat", model=None),
            vocabulary_domain._ensure_cached_content("cat", model=None),
            vocabulary_domain._ensure_cached_content("cat", model=None),
        )

    outs = asyncio.run(_run())
    assert len(calls) == 1
    assert _count_rows("dictionary_entries") == 1
    assert {out["definition"] for out in outs} == {
        "A small domesticated carnivorous mammal."
    }


def test_concurrent_two_users_same_word_generates_once(monkeypatch, tmp_path):
    """El single-flight es global: A y B consultando la misma palabra a la vez
    comparten una generación; el contenido es global y la marca de uso queda
    aislada por usuario."""
    a, b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    calls: list = []

    async def _slow(word: str, model: str | None) -> str:
        calls.append(word)
        await asyncio.sleep(0.05)
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _slow)

    async def _run():
        return await asyncio.gather(
            vocabulary_domain.lookup_dictionary(a, "cat"),
            vocabulary_domain.lookup_dictionary(b, "cat"),
        )

    res_a, res_b = asyncio.run(_run())
    assert len(calls) == 1
    assert _count_rows("dictionary_entries") == 1
    assert res_a["definition_source"] == "llm"
    assert res_b["definition"] == res_a["definition"]
    assert res_a["usage"]["tracked"] is True
    assert res_b["usage"]["tracked"] is False


def test_concurrent_failure_generates_once_and_degrades(monkeypatch, tmp_path):
    """Si la generación falla, el vuelo la resuelve UNA vez y todos degradan a
    None, sin reintentos en cascada por cada waiter."""
    _setup(monkeypatch, tmp_path)
    calls: list = []

    async def _down(word: str, model: str | None) -> str:
        calls.append(word)
        raise dictionary_content.ContentUnavailableError("modelo caído")

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _down)

    async def _run():
        return await asyncio.gather(
            vocabulary_domain._ensure_cached_content("cat", model=None),
            vocabulary_domain._ensure_cached_content("cat", model=None),
        )

    outs = asyncio.run(_run())
    assert outs == [None, None]
    assert len(calls) == 1
    assert _count_rows("dictionary_entries") == 0


def test_inflight_leader_cancel_resolves_waiters_without_hanging(
    monkeypatch, tmp_path
):
    """V3.31: si el primer cliente (dueño del vuelo) se cancela a mitad de la
    generación (desconexión), los waiters reciben None en vez de quedarse
    esperando un Future que nunca se resuelve.

    La cancelación (`CancelledError`, BaseException) no la capturaba el
    `except Exception` previo y el `finally` retiraba la clave sin resolver el
    Future: los waiters colgaban. El tope de 1 s hace que el test falle si el
    bug regresa."""
    _setup(monkeypatch, tmp_path)
    calls: list = []
    gate = asyncio.Event()

    async def _blocked(word: str, model: str | None) -> str:
        calls.append(word)
        await gate.wait()
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _blocked)

    async def _run():
        leader = asyncio.create_task(
            vocabulary_domain._ensure_cached_content("cat", model=None)
        )
        # Espera determinista a que el líder entre en el fetcher (tras su
        # lectura inicial en threadpool) y quede bloqueado en la generación.
        for _ in range(200):
            if calls:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("el líder no llegó a la generación")
        waiter = asyncio.create_task(
            vocabulary_domain._ensure_cached_content("cat", model=None)
        )
        await asyncio.sleep(0)
        leader.cancel()
        return await asyncio.wait_for(waiter, timeout=1.0)

    out = asyncio.run(_run())
    assert out is None
    assert len(calls) == 1
    assert _count_rows("dictionary_entries") == 0


# --- versionado de la caché (V3.30.1, P1-03 / V3.31 LEGACY) -------------------


def test_stale_generator_version_regenerates_and_overwrites(monkeypatch, tmp_path):
    """Una entrada generada con una versión anterior de prompt/política no se
    sirve como obsoleta permanente: se regenera y sobrescribe en la misma fila."""
    _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "cat",
        pos="noun",
        definition="definición antigua (V3.30.0)",
        translation="gato",
        generator_version="0.9.0",
    )
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    out = asyncio.run(
        vocabulary_domain._ensure_cached_content("cat", model=None)
    )

    assert len(calls) == 1
    assert out["definition"] == "A small domesticated carnivorous mammal."
    stored = dictionary_repo.get_entry("cat")
    assert stored["definition"] == "A small domesticated carnivorous mammal."
    assert stored["generator_version"] == dictionary_content.GENERATOR_VERSION
    assert _count_rows("dictionary_entries") == 1


def test_legacy_content_regenerates_lazily_once(monkeypatch, tmp_path):
    """V3.31: una entrada marcada con la versión LEGACY (contenido previo a
    V3.31, p. ej. generado por el parser greedy de V3.30 o etiquetado por el
    backfill de V3.30.1) NO se sirve como fresca: al primer lookup regenera
    UNA vez y sobrescribe la fila con la versión actual."""
    _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "cat",
        pos="noun",
        definition="definición del parser V3.30",
        translation="gato",
        generator_version=db.DICTIONARY_LEGACY_VERSION,
    )
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    out = asyncio.run(
        vocabulary_domain._ensure_cached_content("cat", model=None)
    )

    assert len(calls) == 1
    assert out["definition"] == "A small domesticated carnivorous mammal."
    stored = dictionary_repo.get_entry("cat")
    assert stored["definition"] == "A small domesticated carnivorous mammal."
    assert stored["generator_version"] == dictionary_content.GENERATOR_VERSION
    assert _count_rows("dictionary_entries") == 1


def test_migration_upgrade_from_v330_adds_version_and_keeps_content(
    monkeypatch, tmp_path
):
    """V3.31: una BD creada por V3.30.0 (tabla `dictionary_entries` sin
    `generator_version`) migra de forma aditiva e idempotente: la columna se
    añade, el contenido se conserva y las filas legacy quedan marcadas con la
    versión LEGACY (distinta de la actual), por lo que el dominio NO las sirve
    como caché fresca y las regenera al primer lookup."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE dictionary_entries (
                word TEXT PRIMARY KEY,
                pos TEXT NOT NULL DEFAULT '',
                definition TEXT NOT NULL DEFAULT '',
                translation TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "cat",
                "noun",
                "definición V3.30",
                "gato",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    cols = {
        row[1]
        for row in db._conn().execute("PRAGMA table_info(dictionary_entries)")
    }
    assert "generator_version" in cols
    stored = dictionary_repo.get_entry("cat")
    assert stored["definition"] == "definición V3.30"  # contenido conservado
    assert stored["generator_version"] == db.DICTIONARY_LEGACY_VERSION
    assert db.DICTIONARY_LEGACY_VERSION != dictionary_content.GENERATOR_VERSION
    assert vocabulary_domain._content_is_fresh(stored) is False

    db.init_db()  # idempotente en re-arranque
    again = dictionary_repo.get_entry("cat")
    assert again["generator_version"] == db.DICTIONARY_LEGACY_VERSION
    assert again["definition"] == "definición V3.30"

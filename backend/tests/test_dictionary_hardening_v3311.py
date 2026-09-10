"""Tests del endurecimiento V3.31.1 del diccionario de consulta (auditoría V3.31.0).

Cubre las protecciones best-effort por proceso añadidas al generador de
contenido (`domain/vocabulary.py`), sin red y con fetcher inyectable:

- negative cache: un fallo reciente de generación no reintenta hasta pasado el
  TTL (`DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS`) — evita la tormenta de
  reintentos cuando Ollama está caído o devuelve contenido inválido;
- rate limit de generación por usuario y global (`…_PER_USER_MINUTE` /
  `…_PER_MINUTE_GLOBAL`): N palabras NUEVAS por ventana; lo cacheado no
  consume cupo;
- tope del dueño del vuelo (`DICTIONARY_GENERATION_TIMEOUT_SECONDS`): un
  generador colgado degrada y libera el vuelo, en vez de clavarlo;
- D3 intacto: ninguna de estas rutas crea evidencia en `vocabulary` /
  `vocabulary_events`.

Todo el estado nuevo es global por proceso y se limpia entre tests.
"""
import asyncio
import json
import sqlite3
import time

import pytest

from domain import vocabulary as vocabulary_domain
from repositories import db
from repositories import users as users_repo
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


def _lookup_domain(uid: str, word: str, *, model: str | None = None) -> dict:
    return asyncio.run(vocabulary_domain.lookup_dictionary(uid, word, model=model))


def _stub_fetcher(monkeypatch, payload: str, calls: list):
    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return payload

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)


def _offline_fetcher(monkeypatch, calls: list):
    async def _fake(_word: str, _model: str | None) -> str:
        calls.append("offline")
        raise dictionary_content.ContentUnavailableError("sin modelo")

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


# --- Negative cache -----------------------------------------------------------


def test_failure_marks_negative_cache_and_suppresses_immediate_retry(
    monkeypatch, tmp_path
):
    """Un fallo de generación marca la palabra; el reintento INMEDIATO dentro
    del TTL no vuelve a llamar al modelo (degradación, sin tormenta)."""
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _offline_fetcher(monkeypatch, calls)

    first = _lookup_domain(a, "cat")
    assert first["definition_source"] == "none"
    assert calls == ["offline"]
    assert _count_rows("dictionary_entries") == 0

    # El fetcher "vuelve a estar sano", pero la negative cache sigue vigente.
    _stub_fetcher(monkeypatch, _payload(), calls)
    second = _lookup_domain(a, "cat")
    assert second["definition_source"] == "none"
    assert calls == ["offline"]  # no se llamó al fetcher
    assert vocabulary_domain._cache_key("en-es", "cat") in (
        vocabulary_domain._negative_until
    )


def test_negative_cache_expires_and_recovers(monkeypatch, tmp_path):
    """Pasado el TTL, la palabra sale de la negative cache y la siguiente
    consulta reintenta: si el fetcher acierta, sirve definición y persiste."""
    monkeypatch.setattr("config.DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS", 0.05)
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _offline_fetcher(monkeypatch, calls)

    assert _lookup_domain(a, "cat")["definition_source"] == "none"
    assert calls == ["offline"]

    time.sleep(0.06)  # deja vencer el TTL de la negative cache

    _stub_fetcher(monkeypatch, _payload(), calls)
    recovered = _lookup_domain(a, "cat")
    assert recovered["definition_source"] == "llm"
    assert recovered["definition"] == "A small domesticated carnivorous mammal."
    assert len(calls) == 2  # offline + reintento tras expirar
    assert _count_rows("dictionary_entries") == 1
    assert vocabulary_domain._cache_key("en-es", "cat") not in (
        vocabulary_domain._negative_until
    )


def test_successful_generation_clears_negative_cache(monkeypatch, tmp_path):
    """Cuando una generación SÍ consigue contenido, la negative cache de la
    palabra se limpia (no puede quedar una marca obsoleta)."""
    monkeypatch.setattr("config.DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS", 0.0)
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_domain._mark_generation_failed(
        vocabulary_domain._cache_key("en-es", "cat")
    )

    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)
    out = _lookup_domain(a, "cat")

    assert out["definition_source"] == "llm"
    assert vocabulary_domain._cache_key("en-es", "cat") not in (
        vocabulary_domain._negative_until
    )


# --- Rate limit de generación ------------------------------------------------


def test_rate_limit_per_user_blocks_new_words_but_not_cached(
    monkeypatch, tmp_path
):
    """Con cupo de 2 generaciones por minuto, la 3.ª palabra nueva en la
    ventana NO genera (degradación, sin error); una palabra ya cacheada se
    sigue sirviendo sin consumir cupo."""
    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE", 2)
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    assert _lookup_domain(a, "alpha")["definition_source"] == "llm"
    assert _lookup_domain(a, "beta")["definition_source"] == "llm"
    assert len(calls) == 2

    # Tercera palabra nueva: cupo agotado → degrada sin llamar al fetcher.
    assert _lookup_domain(a, "gamma")["definition_source"] == "none"
    assert len(calls) == 2

    # Palabra ya cacheada: se sirve sin consumir cupo ni llamar al modelo.
    assert _lookup_domain(a, "alpha")["definition_source"] == "llm"
    assert len(calls) == 2


def test_rate_limit_global_shared_across_users(monkeypatch, tmp_path):
    """El cupo global limita también entre usuarios distintos: la generación
    que exceda el tope global degrada para el usuario que llegue tarde."""
    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE", 100)
    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_MINUTE_GLOBAL", 3)
    a, b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    assert _lookup_domain(a, "a1")["definition_source"] == "llm"
    assert _lookup_domain(a, "a2")["definition_source"] == "llm"
    assert _lookup_domain(b, "b1")["definition_source"] == "llm"
    assert len(calls) == 3

    # La 4.ª generación global se bloquea aunque al usuario B le quede cupo.
    assert _lookup_domain(b, "b2")["definition_source"] == "none"
    assert len(calls) == 3


def test_rate_limited_lookup_never_raises(monkeypatch, tmp_path):
    """Sin cupo de generación, la consulta es una degradación normal (200 con
    `definition_source="none"`), nunca un error 5xx."""
    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE", 0)
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_fetcher(monkeypatch, _payload(), calls)

    out = _lookup_domain(a, "dog")
    assert out["definition_source"] == "none"
    assert calls == []


# --- Tope del dueño del vuelo ------------------------------------------------


def test_owner_generation_timeout_degrades_and_releases_flight(
    monkeypatch, tmp_path
):
    """Si el generador del dueño del vuelo se cuelga más del tope servidor, la
    consulta degrada, la negative cache se marca y el vuelo se libera (ningún
    Future huérfano ni palabra clavada)."""
    monkeypatch.setattr("config.DICTIONARY_GENERATION_TIMEOUT_SECONDS", 0.2)
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []

    async def _hanging(_word: str, _model: str | None) -> str:
        calls.append("hang")
        await asyncio.sleep(5.0)
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _hanging)

    started = time.monotonic()
    out = _lookup_domain(a, "slowword")
    elapsed = time.monotonic() - started

    assert out["definition_source"] == "none"
    assert calls == ["hang"]
    assert elapsed < 2.0  # no esperó a los 5 s del fetcher
    assert vocabulary_domain._inflight_content == {}
    assert vocabulary_domain._cache_key("en-es", "slowword") in (
        vocabulary_domain._negative_until
    )
    assert _count_rows("dictionary_entries") == 0


# --- D3: ninguna ruta crea evidencia -----------------------------------------


def test_hardening_paths_never_create_evidence(monkeypatch, tmp_path):
    """Fallos, reintentos, cupos y timeouts del diccionario no crean filas en
    `vocabulary` ni eventos en `vocabulary_events` (la consulta es contenido,
    no evidencia — D3)."""
    monkeypatch.setattr("config.DICTIONARY_GENERATION_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr("config.DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS", 0.0)
    a, _b = _setup(monkeypatch, tmp_path)
    before_vocab = _count_rows("vocabulary")
    before_events = _count_rows("vocabulary_events")

    calls: list = []
    _offline_fetcher(monkeypatch, calls)
    assert _lookup_domain(a, "offlineword")["definition_source"] == "none"

    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE", 0)
    assert _lookup_domain(a, "quotaword")["definition_source"] == "none"

    monkeypatch.setattr("config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE", 100)

    async def _hanging(_word: str, _model: str | None) -> str:
        await asyncio.sleep(5.0)
        return _payload()

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _hanging)
    assert _lookup_domain(a, "slowword")["definition_source"] == "none"

    assert _count_rows("vocabulary") == before_vocab
    assert _count_rows("vocabulary_events") == before_events
    assert _count_rows("dictionary_entries") == 0

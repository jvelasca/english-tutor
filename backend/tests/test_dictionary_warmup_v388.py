"""Tests del precalentado del diccionario (V3.88.0).

El trabajo de fondo reutiliza el camino de la consulta
(`vocabulary.warm_dictionary_word` → `_ensure_cached_content`), así que lo que
se fija aquí es: el ciclo de vida del trabajo (202 + polling), que el resultado
es la caché global y no el registro, el aislamiento por usuario y que la lista
interna de palabras nunca sale en la respuesta.
"""

import asyncio
import json
import sqlite3

from fastapi.testclient import TestClient

import config
from domain import dictionary_warmup as warmup_service
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    # El registro de trabajos es de proceso: se limpia entre pruebas.
    warmup_service._JOBS.clear()
    warmup_service._JOB_ORDER.clear()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _payload(word: str = "cat") -> str:
    return json.dumps(
        {
            "pos": "noun",
            "definition": f"Definition of {word}.",
            "translation": f"{word}-es",
            "meanings": [
                {"term": f"{word}-es", "pos": "noun", "gloss": "acepción 1"},
                {"term": f"{word}-es-2", "pos": "noun", "gloss": "acepción 2"},
            ],
        }
    )


def _stub_fetcher(monkeypatch, payload_for, calls: list):
    async def _fake(word: str, model: str | None) -> str:
        calls.append(word)
        return payload_for(word)

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _fake)


def _post_warmup(uid: str, body: dict | None = None) -> dict:
    """POST del trabajo. Devuelve su estado INICIAL (el 202 no espera al fondo)."""
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary/warmup?user_id={uid}", json=body
        )
        assert res.status_code == 202, res.text
        return res.json()


def _poll_warmup(uid: str, job_id: str) -> dict:
    """Estado actual del trabajo (el polling que hará el frontend)."""
    with TestClient(app) as client:
        res = client.get(
            f"/api/vocabulary/dictionary/warmup/{job_id}?user_id={uid}"
        )
        assert res.status_code == 200, res.text
        return res.json()


def _run_warmup(uid: str, body: dict | None = None) -> dict:
    """POST + polling. `TestClient` ejecuta el fondo antes de devolver, así que
    el GET posterior ya ve el trabajo terminado."""
    job = _post_warmup(uid, body)
    return _poll_warmup(uid, job["id"])


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# --- Ciclo de vida del trabajo ----------------------------------------------


def test_empty_lexicon_finishes_with_nothing_to_do(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)

    out = _post_warmup(a)

    assert out["total"] == 0
    assert out["prepared"] == 0
    assert out["pending"] == 0
    assert out["status"] == "done"
    assert out["error"] is None


def test_prepares_the_lexicon_words_and_fills_the_cache(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat", "dog"]) is True
    calls: list[str] = []
    _stub_fetcher(monkeypatch, _payload, calls)

    out = _run_warmup(a)

    assert out["total"] == 2
    assert out["prepared"] == 2
    assert out["skipped"] == 0
    assert out["pending"] == 0
    assert out["status"] == "done"
    # El RESULTADO es la caché global, no el registro del trabajo.
    assert sorted(calls) == ["cat", "dog"]
    assert _count_rows("dictionary_entries") == 2
    stored = dictionary_repo.get_entry("cat")
    assert stored["generator_version"] == dictionary_content.GENERATOR_VERSION
    # V3.88.0: el precalentado trae los significados múltiples que exige el prompt.
    assert len(stored["meanings"]) == 2


def test_answer_never_exposes_the_internal_word_list(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    _stub_fetcher(monkeypatch, _payload, [])

    out = _post_warmup(a)

    assert "words" not in out
    assert set(out) == {
        "id",
        "status",
        "total",
        "prepared",
        "skipped",
        "pending",
        "error",
    }


def test_words_that_cannot_be_prepared_are_skipped_not_failed(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat", "dog"]) is True

    async def _broken(_word: str, _model: str | None) -> str:
        return "no es JSON"

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _broken)

    out = _run_warmup(a)

    # Best-effort: no se pudo preparar ninguna, pero el trabajo termina bien y
    # se puede reintentar más tarde.
    assert out["total"] == 2
    assert out["prepared"] == 0
    assert out["skipped"] == 2
    assert out["status"] == "done"
    assert out["error"] is None
    assert _count_rows("dictionary_entries") == 0


def test_limit_is_capped_by_the_server(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    words = [f"w{i}" for i in range(config.DICTIONARY_WARMUP_MAX_WORDS + 5)]
    assert vocabulary_repo.record_words(a, words) is True

    out = _post_warmup(a, {"limit": 500})

    assert out["total"] == config.DICTIONARY_WARMUP_MAX_WORDS


def test_a_running_job_is_reused_instead_of_starting_a_second_sweep(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True

    job1, new1 = asyncio.run(warmup_service.start_warmup_job(a))
    job2, new2 = asyncio.run(warmup_service.start_warmup_job(a))

    assert new1 is True
    assert new2 is False
    assert job1["id"] == job2["id"]
    assert job1["status"] == "running"


def test_nothing_to_prepare_is_declared_done_without_a_sweep(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)

    job, is_new = asyncio.run(warmup_service.start_warmup_job(a))

    assert is_new is True
    assert job["status"] == "done"
    assert job["total"] == 0
    # La lista interna no queda retenida cuando no hay nada que hacer.
    assert "words" not in job


# --- Polling y aislamiento --------------------------------------------------


def test_status_of_an_unknown_job_is_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)

    with TestClient(app) as client:
        res = client.get(
            f"/api/vocabulary/dictionary/warmup/does-not-exist?user_id={a}"
        )

    assert res.status_code == 404


def test_another_users_job_is_invisible(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    _stub_fetcher(monkeypatch, _payload, [])
    out = _post_warmup(a)

    with TestClient(app) as client:
        res = client.get(
            f"/api/vocabulary/dictionary/warmup/{out['id']}?user_id={b}"
        )

    assert res.status_code == 404


def test_the_owner_can_poll_the_job(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    _stub_fetcher(monkeypatch, _payload, [])
    out = _run_warmup(a)

    assert out["status"] == "done"
    assert out["prepared"] == 1

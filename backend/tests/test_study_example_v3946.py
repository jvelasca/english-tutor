"""V3.94.6: otra frase de la lección no escribe el estudio."""
from __future__ import annotations

import asyncio
from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import study_example


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_parse_rejects_a_sentence_that_misses_the_word():
    raw = '{"phrase": "Hello there.", "translation": "Hola."}'
    assert study_example.parse_example(raw, word="bank") is None


def test_parse_rejects_a_repeated_sentence():
    raw = '{"phrase": "I went to the bank.", "translation": "Fui al banco."}'
    parsed = study_example.parse_example(
        raw, word="bank", avoid=["I went to the bank."]
    )
    assert parsed is None


def test_fresh_example_retries_an_invalid_sentence():
    calls = {"n": 0}

    async def chat(word, avoid, model):
        del word, avoid, model
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"phrase": "No word here.", "translation": "Nada."}'
        return '{"phrase": "I went to the bank.", "translation": "Fui al banco."}'

    result = asyncio.run(study_example.fresh_example("bank", chat=chat))
    assert result is not None
    assert result["phrase"] == "I went to the bank."
    assert calls["n"] == 2


def test_example_endpoint_does_not_write_study_state(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)

    async def chat(word, avoid, model):
        del avoid, model
        return (
            '{"phrase": "I went to the '
            + word
            + '.", "translation": "Fui al banco."}'
        )

    monkeypatch.setattr(study_example, "_ask", chat)
    client = TestClient(app)
    response = client.post(
        "/api/vocabulary/study/example",
        params={"user_id": user_id},
        json={"word": "bank", "avoid": []},
    )
    assert response.status_code == 200, response.text
    assert response.json()["phrase"] == "I went to the bank."
    with closing(db._conn()) as conn:
        reviews = conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0]
        items = conn.execute("SELECT COUNT(*) FROM study_lesson_items").fetchone()[0]
        words = conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
    assert reviews == 0
    assert items == 0
    assert words == 0


def test_example_endpoint_rejects_a_bad_word_without_the_model(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)

    async def chat(word, avoid, model):
        del word, avoid, model
        raise AssertionError("el modelo no debía llamarse")

    monkeypatch.setattr(study_example, "_ask", chat)
    client = TestClient(app)
    response = client.post(
        "/api/vocabulary/study/example",
        params={"user_id": user_id},
        json={"word": "123", "avoid": []},
    )
    assert response.status_code == 400

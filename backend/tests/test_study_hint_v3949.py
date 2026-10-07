"""V3.94.9: la pista no es la traducción y queda guardada."""
from __future__ import annotations

import asyncio
from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import study_hint


def test_reverse_prompt_says_the_learner_already_sees_spanish():
    system, user = study_hint.hint_request("hammer", "martillo", "es-en")
    assert "already sees the Spanish word" in system
    assert "martillo" in user
    assert "Do not write it: hammer" in user
    assert "already sees" not in study_hint.hint_request("hammer", "martillo")[0]


def test_parse_rejects_a_hint_that_gives_the_translation():
    raw = '{"hint": "sirve para clavar, es un martillo"}'
    assert study_hint.parse_hint(raw, word="hammer", translation="martillo") is None


def test_fresh_hint_retries_when_the_first_answer_reveals_the_word():
    calls = {"n": 0}

    async def chat(word, translation, model):
        del translation, model
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"hint": "piensa en ' + word + '"}'
        return '{"hint": "sirve para clavar sin decir el nombre"}'

    result = asyncio.run(study_hint.fresh_hint("hammer", "martillo", chat=chat))
    assert result == "sirve para clavar sin decir el nombre"
    assert calls["n"] == 2


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_hint_endpoint_saves_the_lexicon_reminder(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO vocabulary "
            "(user_id, word, production_count, first_seen, last_seen) "
            "VALUES (?, 'hammer', 0, '2020-01-01', '2020-01-01')",
            (user_id,),
        )

    async def chat(word, translation, model, direction="en-es"):
        del word, translation, model, direction
        return '{"hint": "sirve para clavar sin decir el nombre"}'

    monkeypatch.setattr(study_hint, "_ask", chat)
    client = TestClient(app)
    response = client.post(
        "/api/vocabulary/study/hint",
        params={"user_id": user_id},
        json={
            "word": "hammer",
            "translation": "martillo",
            "card_type": "lexicon",
            "card_id": "hammer",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["hint"] == "sirve para clavar sin decir el nombre"
    with closing(db._conn()) as conn:
        row = conn.execute(
            "SELECT mnemonic FROM vocabulary WHERE user_id = ? AND word = 'hammer'",
            (user_id,),
        ).fetchone()
        items = conn.execute("SELECT COUNT(*) FROM study_lesson_items").fetchone()[0]
    assert row["mnemonic"] == "sirve para clavar sin decir el nombre"
    assert items == 0

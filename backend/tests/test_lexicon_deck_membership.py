"""Una palabra del diccionario es una sola carta FSRS, aunque esté en dos mazos."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _fsrs_lexicon(word: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM fsrs_cards "
            "WHERE target_type = 'lexicon' AND target_id = ?",
            (word,),
        ).fetchone()[0]
    finally:
        conn.close()


def _manual_cards() -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM flashcard_cards").fetchone()[0]
    finally:
        conn.close()


def test_one_fsrs_card_shared_by_two_decks_and_level_filter(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    decks = []
    for name in ("Herramientas", "Orografía"):
        res = client.post(
            "/api/vocabulary/decks",
            params={"user_id": user_id},
            json={"name": name},
        )
        assert res.status_code == 200, res.text
        decks.append(res.json()["id"])

    added = client.post(
        "/api/vocabulary/items",
        params={"user_id": user_id},
        json={
            "word": "saw",
            "translation": "sierra",
            "mnemonic": "la tercera sílaba son los dientes",
            "deck_ids": decks,
            "cefr": "A2",
        },
    )
    assert added.status_code == 200, added.text
    other = client.post(
        "/api/vocabulary/items",
        params={"user_id": user_id},
        json={"word": "ridge", "translation": "cordillera", "cefr": "B1"},
    )
    assert other.status_code == 200, other.text
    assert _manual_cards() == 0
    assert _fsrs_lexicon("saw") == 1

    queues = []
    for deck_id in decks:
        res = client.get(
            f"/api/vocabulary/decks/{deck_id}/queue",
            params={"user_id": user_id},
        )
        assert res.status_code == 200, res.text
        items = res.json()["items"]
        assert len(items) == 1
        assert items[0]["card_type"] == "lexicon"
        assert items[0]["card_id"] == "saw"
        assert "dientes" in items[0]["mnemonic"]
        queues.append(items[0]["card_id"])
    assert queues[0] == queues[1]

    graded = client.post(
        f"/api/vocabulary/decks/{decks[0]}/review",
        params={"user_id": user_id},
        json={"card_type": "lexicon", "card_id": "saw", "grade": 3},
    )
    assert graded.status_code == 200, graded.text
    again = client.get(
        f"/api/vocabulary/decks/{decks[1]}/queue",
        params={"user_id": user_id},
    )
    assert again.status_code == 200
    assert again.json()["items"] == []

    a2 = client.get(
        "/api/vocabulary/decks/0/queue",
        params={"user_id": user_id, "level": "A2"},
    )
    b1 = client.get(
        "/api/vocabulary/decks/0/queue",
        params={"user_id": user_id, "level": "B1"},
    )
    assert a2.status_code == 200 and b1.status_code == 200
    assert [item["card_id"] for item in a2.json()["items"]] == []
    assert [item["card_id"] for item in b1.json()["items"]] == ["ridge"]

    stats = client.get(
        "/api/vocabulary/decks/0/stats", params={"user_id": user_id}
    )
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["cards_total"] == 2
    assert len(body["forecast"]) == 7

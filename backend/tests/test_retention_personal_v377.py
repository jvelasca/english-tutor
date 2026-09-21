"""Tests de retención Personal: ingestión + sesión FSRS (D3/D5).

- Añadir palabra/lista/pack crea fila vocabulary + carta lexicon, sin
  production/exposure ni mastery.
- Grade retention reprograma due_at y escribe evento informativo.
- Aislamiento entre usuarios.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.evidence import classify_event_role


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count(table: str, where: str = "1=1", params=()) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
    finally:
        conn.close()


def test_add_item_seeds_vocab_and_fsrs_without_skill_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        before_events = _count("learning_events", "user_id = ?", (a,))
        before_vocab_events = _count("vocabulary_events", "user_id = ?", (a,))

        res = client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "Passport", "translation": "pasaporte"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["added"] == ["passport"]
        assert body["item"]["word"] == "passport"

        rows = vocabulary_repo.get_vocabulary(a)
        assert len(rows) == 1
        row = rows[0]
        assert row["word"] == "passport"
        assert int(row["production_count"] or 0) == 0
        assert int(row["exposure_count"] or 0) == 0
        assert row["source"] == "user"

        card = academy_repo.get_fsrs_card(a, "lexicon", "passport")
        assert card is not None
        assert card["target_type"] == "lexicon"
        assert int(card["reps"] or 0) == 0

        assert _count("learning_events", "user_id = ?", (a,)) == before_events
        assert (
            _count("vocabulary_events", "user_id = ?", (a,)) == before_vocab_events
        )


def test_bulk_and_enroll_theme_pack(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        packs = client.get(
            "/api/vocabulary/collections", params={"user_id": a}
        )
        assert packs.status_code == 200
        collections = packs.json()["collections"]
        assert any(c["slug"] == "travel" and c["is_global"] for c in collections)
        travel = next(c for c in collections if c["slug"] == "travel")

        enroll = client.post(
            f"/api/vocabulary/collections/{travel['id']}/enroll",
            params={"user_id": a},
        )
        assert enroll.status_code == 200, enroll.text
        data = enroll.json()
        assert data["count"] > 0
        assert "airport" in data["added"]

        rows = vocabulary_repo.get_vocabulary(a)
        assert len(rows) == data["count"]
        assert all(int(r["production_count"] or 0) == 0 for r in rows)

        bulk = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": a},
            json={"text": "hello\nworld\nhello\ngood morning", "title": "Basics"},
        )
        assert bulk.status_code == 200, bulk.text
        assert bulk.json()["count"] == 3
        assert set(bulk.json()["added"]) == {"hello", "world", "good morning"}


def test_retention_review_reschedules_and_informative_event(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "ticket"},
        )
        due = client.get(
            "/api/vocabulary/retention/due", params={"user_id": a}
        )
        assert due.status_code == 200
        items = due.json()["items"]
        assert any(i["word"] == "ticket" for i in items)

        review = client.post(
            "/api/vocabulary/retention/review",
            params={"user_id": a},
            json={"word": "ticket", "grade": 4},
        )
        assert review.status_code == 200, review.text
        out = review.json()
        assert out["grade"] == 4
        assert out["reps"] >= 1
        assert out["next_in_days"] > 0

        events = learning_repo.list_events(a, event_type="exercise")
        retention = [e for e in events if "retention:ticket:" in e["detail"]]
        assert retention
        assert retention[0]["event_role"] == "informative"
        assert classify_event_role("exercise", "retention:ticket:4") == "informative"

        row = vocabulary_repo.get_vocabulary(a)[0]
        assert int(row["production_count"] or 0) == 0


def test_add_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "luggage"},
        )
        assert len(vocabulary_repo.get_vocabulary(a)) == 1
        assert vocabulary_repo.get_vocabulary(b) == []

        due_b = client.get(
            "/api/vocabulary/retention/due", params={"user_id": b}
        )
        assert due_b.json()["due_count"] == 0

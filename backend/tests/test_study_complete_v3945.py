"""V3.94.5: un ítem servido admite una sola completion y una sola transición FSRS."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db, study_lessons
from repositories import flashcards as flashcards_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _reviews(user_id: str) -> list[dict]:
    with closing(db._conn()) as conn:
        rows = conn.execute(
            "SELECT card_type, card_id, grade, deck_id FROM flashcard_reviews "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _events(user_id: str) -> list[str]:
    with closing(db._conn()) as conn:
        rows = conn.execute(
            "SELECT detail FROM learning_events WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [str(row["detail"]) for row in rows]


def _item_status(item_id: str) -> str:
    with closing(db._conn()) as conn:
        row = conn.execute(
            "SELECT status FROM study_lesson_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
    return str(row["status"]) if row else ""


def _serve_manual(client: TestClient, user_id: str, deck_id: int) -> list[dict]:
    queued = client.get(
        "/api/vocabulary/study/queue",
        params={
            "user_id": user_id,
            "scope": "deck",
            "deck_id": deck_id,
            "mode": "all",
        },
    )
    assert queued.status_code == 200, queued.text
    return queued.json()["items"]


def _run_in_threads(work, n: int) -> list:
    results: list = []
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            results.append(work(i))
        except BaseException as exc:  # noqa: BLE001 - se re-lanza tras el join
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    return results


def test_double_post_of_the_same_item_schedules_once(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    deck = flashcards_repo.create_deck(user_id, name="Herramientas")
    assert deck is not None
    card = flashcards_repo.create_card(
        user_id, deck["id"], front="hammer", back="martillo"
    )
    assert card is not None
    client = TestClient(app)
    served = _serve_manual(client, user_id, deck["id"])
    assert len(served) == 1
    body = {
        "item_id": served[0]["item_id"],
        "grade": 3,
        "facets": {"meaning": "done"},
    }
    first = client.post(
        "/api/vocabulary/study/complete", params={"user_id": user_id}, json=body
    )
    second = client.post(
        "/api/vocabulary/study/complete",
        params={"user_id": user_id},
        json={**body, "grade": 1, "word": "mentira"},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["due_at"] == first.json()["due_at"]
    assert second.json()["grade"] == first.json()["grade"] == 3
    assert "mentira" not in vocabulary_repo.words_of(user_id)
    reviews = _reviews(user_id)
    assert reviews == [
        {
            "card_type": "flashcard",
            "card_id": str(card["id"]),
            "grade": 3,
            "deck_id": deck["id"],
        }
    ]
    manual = academy_repo.get_fsrs_card(user_id, "flashcard", str(card["id"]))
    lexicon = academy_repo.get_fsrs_card(user_id, "lexicon", "hammer")
    assert manual is not None and int(manual["reps"]) == 1
    assert lexicon is not None and int(lexicon["reps"]) == 0
    assert _events(user_id) == [f"flashcard:{card['id']}:3"]


def test_two_threads_on_the_same_item_schedule_once(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    deck = flashcards_repo.create_deck(user_id, name="Herramientas")
    assert deck is not None
    assert (
        flashcards_repo.create_card(user_id, deck["id"], front="nail", back="clavo")
        is not None
    )
    client = TestClient(app)
    served = _serve_manual(client, user_id, deck["id"])
    item_id = served[0]["item_id"]

    def once(i: int):
        return study_lessons.complete_item(
            user_id, item_id, 3 if i == 0 else 4, {"meaning": "done"}, "", []
        )

    done = _run_in_threads(once, 2)
    assert {code for code, _body in done} == {"ok"}
    grades = {body["grade"] for _code, body in done}
    assert grades == {done[0][1]["grade"]}
    assert len(_reviews(user_id)) == 1
    card = academy_repo.get_fsrs_card(user_id, "flashcard", served[0]["card_id"])
    assert card is not None and int(card["reps"]) == 1


def test_shared_membership_survives_a_grade_from_the_other_deck(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    tools = flashcards_repo.create_deck(user_id, name="Herramientas")
    hills = flashcards_repo.create_deck(user_id, name="Orografía")
    assert tools is not None and hills is not None
    card = flashcards_repo.create_card(
        user_id,
        deck_ids=[tools["id"], hills["id"]],
        front="saw",
        back="sierra",
    )
    assert card is not None
    client = TestClient(app)
    served = _serve_manual(client, user_id, tools["id"])
    assert [item["word"] for item in served] == ["saw"]
    done = client.post(
        "/api/vocabulary/study/complete",
        params={"user_id": user_id},
        json={
            "item_id": served[0]["item_id"],
            "grade": 3,
            "facets": {"meaning": "done"},
        },
    )
    assert done.status_code == 200, done.text
    assert set(flashcards_repo.decks_for_card(user_id, int(card["id"]))) == {
        tools["id"],
        hills["id"],
    }
    fronts = [
        row["front"] for row in flashcards_repo.list_cards(user_id, hills["id"])
    ]
    assert fronts == ["saw"]
    manual = academy_repo.get_fsrs_card(user_id, "flashcard", str(card["id"]))
    lexicon = academy_repo.get_fsrs_card(user_id, "lexicon", "saw")
    assert manual is not None and int(manual["reps"]) == 1
    assert lexicon is not None and int(lexicon["reps"]) == 0
    assert len(_reviews(user_id)) == 1
    assert "saw" in vocabulary_repo.words_of(user_id)


def test_deleted_deck_does_not_schedule(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    deck = flashcards_repo.create_deck(user_id, name="Temporal")
    assert deck is not None
    card = flashcards_repo.create_card(
        user_id, deck["id"], front="zzxboom", back="nada"
    )
    assert card is not None
    client = TestClient(app)
    served = _serve_manual(client, user_id, deck["id"])
    assert flashcards_repo.delete_deck(user_id, deck["id"]) is not None
    done = client.post(
        "/api/vocabulary/study/complete",
        params={"user_id": user_id},
        json={
            "item_id": served[0]["item_id"],
            "grade": 4,
            "facets": {"meaning": "done"},
        },
    )
    assert done.status_code == 404, done.text
    assert academy_repo.get_fsrs_card(user_id, "flashcard", str(card["id"])) is None
    assert academy_repo.get_fsrs_card(user_id, "lexicon", "zzxboom") is None
    assert "zzxboom" not in vocabulary_repo.words_of(user_id)
    assert _reviews(user_id) == []
    assert _item_status(served[0]["item_id"]) == "open"


def test_unknown_item_writes_nothing(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    done = client.post(
        "/api/vocabulary/study/complete",
        params={"user_id": user_id},
        json={"item_id": "no-existe", "grade": 3},
    )
    assert done.status_code == 400, done.text
    assert _reviews(user_id) == []


def test_a_failed_write_rolls_the_completion_back(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    deck = flashcards_repo.create_deck(user_id, name="Temporal")
    assert deck is not None
    assert (
        flashcards_repo.create_card(user_id, deck["id"], front="zzxboom", back="nada")
        is not None
    )
    client = TestClient(app)
    served = _serve_manual(client, user_id, deck["id"])
    item_id = served[0]["item_id"]

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(study_lessons, "_after_writes", boom)
    with pytest.raises(RuntimeError, match="boom"):
        study_lessons.complete_item(
            user_id, item_id, 3, {"meaning": "done"}, "nada", []
        )
    assert "zzxboom" not in vocabulary_repo.words_of(user_id)
    assert academy_repo.get_fsrs_card(user_id, "lexicon", "zzxboom") is None
    manual = academy_repo.get_fsrs_card(
        user_id, "flashcard", served[0]["card_id"]
    )
    assert manual is None
    assert _reviews(user_id) == []
    assert _events(user_id) == []
    assert _item_status(item_id) == "open"

    monkeypatch.setattr(study_lessons, "_after_writes", lambda: None)
    code, body = study_lessons.complete_item(
        user_id, item_id, 3, {"meaning": "done"}, "nada", []
    )
    assert code == "ok" and body is not None
    assert body["word"] == "zzxboom"
    assert _item_status(item_id) == "completed"
    assert len(_reviews(user_id)) == 1


@pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35, 0),
    reason="DROP COLUMN necesita SQLite >= 3.35 para simular el árbol anterior",
)
def test_migration_keeps_previous_rows_and_adds_empty_columns(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.execute("ALTER TABLE vocabulary DROP COLUMN cefr")
        conn.execute("ALTER TABLE vocabulary DROP COLUMN lesson_facets")
        conn.execute("ALTER TABLE dictionary_entries DROP COLUMN cefr")
        conn.execute("DROP TABLE study_lesson_items")
        conn.execute(
            "INSERT INTO vocabulary "
            "(user_id, word, production_count, first_seen, last_seen) "
            "VALUES (?, 'legacyword', 3, '2020-01-01', '2020-01-02')",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO dictionary_entries (word, translation, created_at) "
            "VALUES ('legacydict', 'vieja', '2020-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO fsrs_cards "
            "(user_id, target_type, target_id, reps, stability, "
            "created_at, updated_at) "
            "VALUES (?, 'lexicon', 'legacyword', 4, 3.5, "
            "'2020-01-01T00:00:00', '2020-01-01T00:00:00')",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO flashcard_decks (user_id, name, created_at, updated_at) "
            "VALUES (?, 'Herramientas', '2020-01-01T00:00:00', '2020-01-01T00:00:00')",
            (user_id,),
        )
        deck_id = conn.execute(
            "SELECT id FROM flashcard_decks WHERE user_id = ?",
            (user_id,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO flashcard_reviews "
            "(user_id, deck_id, card_type, card_id, grade, was_new, created_at) "
            "VALUES (?, ?, 'flashcard', '9', 2, 0, '2020-06-01T00:00:00')",
            (user_id, deck_id),
        )

    db.init_db()

    with closing(db._conn()) as conn:
        vocab = conn.execute(
            "SELECT word, production_count, cefr, lesson_facets FROM vocabulary "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        entry = conn.execute(
            "SELECT word, translation, cefr FROM dictionary_entries WHERE word = ?",
            ("legacydict",),
        ).fetchone()
        card = conn.execute(
            "SELECT reps, stability FROM fsrs_cards "
            "WHERE user_id = ? AND target_id = 'legacyword'",
            (user_id,),
        ).fetchone()
        deck = conn.execute(
            "SELECT name FROM flashcard_decks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        review = conn.execute(
            "SELECT grade FROM flashcard_reviews WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        served = conn.execute("SELECT COUNT(*) AS n FROM study_lesson_items").fetchone()
    assert dict(vocab) == {
        "word": "legacyword",
        "production_count": 3,
        "cefr": "",
        "lesson_facets": "",
    }
    assert dict(entry) == {"word": "legacydict", "translation": "vieja", "cefr": ""}
    assert int(card["reps"]) == 4
    assert float(card["stability"]) == pytest.approx(3.5)
    assert deck["name"] == "Herramientas"
    assert int(review["grade"]) == 2
    assert "study_lesson_items" in tables
    assert int(served["n"]) == 0

    db.init_db()
    with closing(db._conn()) as conn:
        again = conn.execute(
            "SELECT COUNT(*) AS n FROM vocabulary WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    assert int(again["n"]) == 1

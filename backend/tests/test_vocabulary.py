"""Tests de vocabulario: extracción, persistencia, aislamiento y endpoints."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.vocabulary import extract_words


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_vocabulary_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("vocabulary")


def test_extract_words_filters_and_sorts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    words = extract_words("Hello, World! The cat sat on the mat.")
    assert words == ["cat", "hello", "mat", "sat", "world"]


def test_extract_words_deduplicates(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert extract_words("Cat cat CAT") == ["cat"]


def test_extract_words_removes_short_tokens(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # "I", "a", "am" no cuentan como vocabulario.
    assert extract_words("I am a cat") == ["cat"]


def test_record_words_increments_occurrences(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat", "dog"]) is True
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    vocab = {v["word"]: v["occurrences"] for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"] == 2
    assert vocab["dog"] == 1


def test_record_words_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words("no-existe", ["cat"]) is False


def test_vocabulary_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat"])
    assert vocabulary_repo.get_vocabulary(b) == []


def test_get_vocabulary_ordered_by_occurrences(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["zebra"])
    vocabulary_repo.record_words(a, ["apple", "apple"])
    vocab = vocabulary_repo.get_vocabulary(a)
    assert [v["word"] for v in vocab] == ["apple", "zebra"]


def test_vocabulary_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/vocabulary/analyze",
            params={"user_id": a},
            json={"text": "The cat sat on the mat."},
        )
        assert r.status_code == 200
        assert r.json()["words"] == ["cat", "mat", "sat"]

        got = client.get("/api/vocabulary", params={"user_id": a})
        assert got.status_code == 200
        assert {v["word"] for v in got.json()} == {"cat", "mat", "sat"}


def test_vocabulary_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/vocabulary", params={"user_id": "no-existe"}).status_code
            == 404
        )
        assert (
            client.post(
                "/api/vocabulary/analyze",
                params={"user_id": "no-existe"},
                json={"text": "hello"},
            ).status_code
            == 404
        )

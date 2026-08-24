import sqlite3

import pytest

from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_conversations_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("conversations")


def test_pronunciation_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("pronunciation_attempts")


def test_conversation_fk_enforced(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO conversations "
                "(id, title, created_at, updated_at, user_id) "
                "VALUES (?, ?, ?, ?, ?)",
                ("c1", "t", "2024-01-01", "2024-01-01", "no-existe"),
            )
    finally:
        conn.close()


def test_pronunciation_fk_enforced(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO pronunciation_attempts "
                "(user_id, expected, heard, score, level, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("no-existe", "Hi", "Hi", 90, "good", "2024-01-01"),
            )
    finally:
        conn.close()


def test_fk_migration_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda llamada no debe fallar ni duplicar
    assert ("users", "user_id") in _fk_targets("conversations")
    assert ("users", "user_id") in _fk_targets("pronunciation_attempts")


def test_fk_migration_from_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: conversations sin user_id y messages sin mode/message_id.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE conversations ("
        "id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, "
        "role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) "
        "VALUES ('old1', 'vieja', '2024-01-01', '2024-01-01')"
    )
    conn.commit()
    conn.close()

    db.init_db()

    assert ("users", "user_id") in _fk_targets("conversations")
    uid = users_repo.list_users()[0]["id"]
    assert conversations_repo.get_conversation("old1", uid)["user_id"] == uid

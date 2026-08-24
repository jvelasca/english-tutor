import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import conversations as conversations_repo
from repositories import db
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def _uid():
    return users_repo.list_users()[0]["id"]


def test_progress_zero_state(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = _uid()
    p = pronunciation_repo.get_progress(uid)
    assert p["user_id"] == uid
    assert p["conversations"] == 0
    assert p["messages"] == 0
    assert p["exercises"] == 0
    assert p["corrections"] == 0
    pr = p["pronunciation"]
    assert pr["attempts"] == 0
    assert pr["best"] is None
    assert pr["average"] is None
    assert pr["last_score"] is None
    assert pr["last_level"] is None


def test_record_pronunciation_aggregates(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = _uid()
    pronunciation_repo.record_pronunciation(uid, "Hello", "Hello", 95, "good")
    pronunciation_repo.record_pronunciation(uid, "World", "Word", 70, "fair")
    pr = pronunciation_repo.get_progress(uid)["pronunciation"]
    assert pr["attempts"] == 2
    assert pr["best"] == 95
    assert pr["average"] == 82.5
    assert pr["last_score"] == 70
    assert pr["last_level"] == "fair"


def test_progress_counts_modes(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = _uid()
    cid = conversations_repo.create_conversation(uid)["id"]
    conversations_repo.save_conversation(
        cid,
        uid,
        "Clase",
        [
            {"role": "user", "content": "I have a question", "mode": "grammar"},
            {"role": "assistant", "content": "Go ahead"},
            {"role": "user", "content": "Do exercise 1", "mode": "exercises"},
            {"role": "assistant", "content": "Great job"},
        ],
    )
    p = pronunciation_repo.get_progress(uid)
    assert p["conversations"] == 1
    assert p["messages"] == 4
    assert p["user_messages"] == 2
    assert p["exercises"] == 1
    assert p["corrections"] == 1


def test_messages_roundtrip_mode(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = _uid()
    cid = conversations_repo.create_conversation(uid)["id"]
    conversations_repo.save_conversation(
        cid, uid, "Clase", [{"role": "user", "content": "Hi", "mode": "grammar"}]
    )
    got = conversations_repo.get_conversation(cid, uid)
    assert got["messages"][0]["mode"] == "grammar"


def test_migration_adds_mode_column(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: messages sin columna mode.
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

    conn = sqlite3.connect(db.DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    conn.close()
    assert "mode" in cols


def test_progress_endpoint_shape(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = _uid()
    cid = conversations_repo.create_conversation(uid)["id"]
    conversations_repo.save_conversation(
        cid, uid, "Clase", [{"role": "user", "content": "Hi", "mode": "exercises"}]
    )
    pronunciation_repo.record_pronunciation(uid, "Hi", "Hi", 100, "good")

    with TestClient(app) as client:
        r = client.get("/api/progress", params={"user_id": uid})
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == uid
        assert body["conversations"] == 1
        assert body["messages"] == 1
        assert body["exercises"] == 1
        assert body["corrections"] == 0
        assert body["pronunciation"]["attempts"] == 1
        assert body["pronunciation"]["best"] == 100


def test_progress_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/progress", params={"user_id": "no-existe"})
        assert r.status_code == 404

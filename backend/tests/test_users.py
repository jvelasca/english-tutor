import sqlite3

from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_default_user_created(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    users = users_repo.list_users()
    assert len(users) == 1
    assert users[0]["name"] == "Usuario"
    assert users[0]["id"]


def test_create_user_returns_id_and_name(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    user = users_repo.create_user("Ana")
    assert user["id"]
    assert user["name"] == "Ana"
    assert user["created_at"]


def test_list_users(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Ana")
    users_repo.create_user("Bob")
    names = [u["name"] for u in users_repo.list_users()]
    assert "Usuario" in names
    assert "Ana" in names
    assert "Bob" in names


def test_create_conversation_associates_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Ana")["id"]
    conv = conversations_repo.create_conversation(uid)
    assert conv["user_id"] == uid


def test_isolation_between_users(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    conversations_repo.create_conversation(a)
    assert conversations_repo.list_conversations(a) != []
    assert conversations_repo.list_conversations(b) == []


def test_create_conversation_unknown_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert conversations_repo.create_conversation("no-existe") is None


def test_migration_assigns_orphans_to_default_user(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: conversations sin columna user_id ni tabla users.
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

    users = users_repo.list_users()
    assert len(users) == 1
    assert (
        conversations_repo.get_conversation("old1", users[0]["id"])["user_id"]
        == users[0]["id"]
    )

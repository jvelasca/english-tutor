import sqlite3

from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()


def test_default_user_created(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    users = store.list_users()
    assert len(users) == 1
    assert users[0]["name"] == "Usuario"
    assert users[0]["id"]


def test_create_user_returns_id_and_name(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    user = store.create_user("Ana")
    assert user["id"]
    assert user["name"] == "Ana"
    assert user["created_at"]


def test_list_users(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    store.create_user("Ana")
    store.create_user("Bob")
    names = [u["name"] for u in store.list_users()]
    assert "Usuario" in names
    assert "Ana" in names
    assert "Bob" in names


def test_create_conversation_associates_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = store.create_user("Ana")["id"]
    conv = store.create_conversation(uid)
    assert conv["user_id"] == uid


def test_isolation_between_users(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    store.create_conversation(a)
    assert store.list_conversations(a) != []
    assert store.list_conversations(b) == []


def test_create_conversation_unknown_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert store.create_conversation("no-existe") is None


def test_migration_assigns_orphans_to_default_user(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: conversations sin columna user_id ni tabla users.
    conn = sqlite3.connect(store.DB_PATH)
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

    store.init_db()

    users = store.list_users()
    assert len(users) == 1
    assert store.get_conversation("old1", users[0]["id"])["user_id"] == users[0]["id"]

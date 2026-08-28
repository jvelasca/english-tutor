"""Tests de status.py (lectura de estado)."""
import sqlite3
from contextlib import closing

import status


def _make_db(path):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL "
            "DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "user_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT "
            "NULL, created_at TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO users VALUES ('u1','Ana','now'),('u2','Bob','now')")
        conn.execute(
            "INSERT INTO conversations VALUES ('c1','t','now','now','u1'),"
            "('c2','t2','now','now','u1')"
        )
        conn.execute(
            "INSERT INTO messages (conversation_id,role,content,created_at) VALUES "
            "('c1','user','hi','now'),('c1','assistant','hello','now'),"
            "('c1','user','bye','now')"
        )


def test_read_db_counts(tmp_path):
    db = tmp_path / "t.db"
    _make_db(db)
    assert status.read_db_counts(str(db)) == {
        "users": 2,
        "conversations": 2,
        "messages": 3,
    }


def test_read_users(tmp_path):
    db = tmp_path / "t.db"
    _make_db(db)
    users = status.read_users(str(db))
    assert len(users) == 2
    ana = [u for u in users if u[1] == "Ana"][0]
    assert ana[2] == 2
    assert ana[3] == 3


def test_read_db_counts_missing_file():
    assert status.read_db_counts("Z:/no/existe/tutor.db") == {
        "users": 0,
        "conversations": 0,
        "messages": 0,
    }


def test_read_db_details_counts_existing_tables(tmp_path):
    db = tmp_path / "t.db"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE vocabulary (id INTEGER)")
        conn.execute("CREATE TABLE learning_events (id INTEGER)")
        conn.execute("INSERT INTO vocabulary VALUES (1),(2),(3)")
        conn.execute("INSERT INTO learning_events VALUES (1)")
    details = status.read_db_details(str(db))
    assert details["vocabulario"] == 3
    assert details["eventos_aprendizaje"] == 1
    # Tablas no creadas → 0.
    assert details["errores_gramaticales"] == 0
    assert details["intentos_pronunciacion"] == 0


def test_read_db_details_missing_file_is_zeroed():
    details = status.read_db_details("Z:/no/existe/tutor.db")
    assert set(details.values()) == {0}


class _FakeResp:
    def __init__(self, payload=b"", code=200):
        self._payload = payload
        self.status = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def test_fetch_health_ok(monkeypatch):
    monkeypatch.setattr(
        "status.urllib.request.urlopen",
        lambda url, timeout: _FakeResp(
            b'{"database":"ok","ollama":"ok","stt":"ready","tts":"ready"}'
        ),
    )
    assert status.fetch_health()["database"] == "ok"


def test_fetch_health_unreachable(monkeypatch):
    def boom(url, timeout):
        raise OSError("refused")

    monkeypatch.setattr("status.urllib.request.urlopen", boom)
    assert status.fetch_health() is None


def test_fetch_frontend_ok(monkeypatch):
    monkeypatch.setattr(
        "status.urllib.request.urlopen",
        lambda url, timeout, context=None: _FakeResp(b"", 200),
    )
    assert status.fetch_frontend() is True


def test_fetch_frontend_down(monkeypatch):
    def boom(url, timeout, context=None):
        raise OSError("refused")

    monkeypatch.setattr("status.urllib.request.urlopen", boom)
    assert status.fetch_frontend() is False


def test_fetch_version_ok(monkeypatch):
    monkeypatch.setattr(
        "status.urllib.request.urlopen",
        lambda url, timeout: _FakeResp(b'{"status":"ok","version":"1.2.3"}'),
    )
    assert status.fetch_version() == "1.2.3"


def test_fetch_version_unreachable(monkeypatch):
    def boom(url, timeout):
        raise OSError("refused")

    monkeypatch.setattr("status.urllib.request.urlopen", boom)
    assert status.fetch_version() == ""


def test_human_size():
    assert status._human_size(0) == "0 B"
    assert status._human_size(512) == "512 B"
    assert status._human_size(1024) == "1.0 KB"
    assert status._human_size(5 * 1024 * 1024) == "5.0 MB"


def test_read_db_info_missing_file_is_not_found():
    info = status.read_db_info("Z:/no/existe/tutor.db")
    assert info["exists"] is False
    assert info["size_human"] == "—"
    assert info["tables"] == 0


def test_read_db_info_reports_size_and_tables(tmp_path):
    db = tmp_path / "t.db"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE vocabulary (id INTEGER)")
        conn.execute("CREATE TABLE users (id INTEGER)")
    info = status.read_db_info(str(db))
    assert info["exists"] is True
    assert info["size_bytes"] > 0
    assert info["size_human"].endswith(("B", "KB", "MB"))
    assert info["tables"] == 2
    assert info["modified"] != "—"

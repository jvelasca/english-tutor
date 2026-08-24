"""Tests de eventos de aprendizaje: tabla, CRUD, aislamiento y endpoints."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo


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


def test_learning_events_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("learning_events")


def test_record_event_unknown_user_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert learning_repo.record_event("no-existe", "message", "hola") is None


def test_record_event_append_only(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    e1 = learning_repo.record_event(a, "message", "hola")
    e2 = learning_repo.record_event(a, "message", "adios")
    assert e1["id"] < e2["id"]
    assert learning_repo.list_events(a) == [
        e2,
        e1,
    ]


def test_list_events_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    learning_repo.record_event(a, "message", "solo A")
    assert learning_repo.list_events(b) == []
    assert len(learning_repo.list_events(a)) == 1


def test_list_events_filter_by_type(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    learning_repo.record_event(a, "message", "uno")
    learning_repo.record_event(a, "exercise", "dos")
    learning_repo.record_event(a, "message", "tres")
    messages = learning_repo.list_events(a, "message")
    assert [e["detail"] for e in messages] == ["tres", "uno"]
    assert len(learning_repo.list_events(a, "exercise")) == 1


def test_record_and_list_roundtrip(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    event = learning_repo.record_event(a, "pronunciation", "Hello")
    assert event["user_id"] == a
    assert event["type"] == "pronunciation"
    assert event["detail"] == "Hello"
    assert event["created_at"]
    listed = learning_repo.list_events(a)
    assert listed == [event]


def test_events_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/learning/events",
            params={"user_id": a},
            json={"type": "exercise", "detail": "fill-in-the-blank"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "exercise"
        assert body["detail"] == "fill-in-the-blank"
        assert body["id"] > 0

        got = client.get("/api/learning/events", params={"user_id": a})
        assert got.status_code == 200
        assert got.json()[0]["type"] == "exercise"


def test_events_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/learning/events", params={"user_id": "no-existe"})
            .status_code
            == 404
        )
        assert (
            client.post(
                "/api/learning/events",
                params={"user_id": "no-existe"},
                json={"type": "message"},
            ).status_code
            == 404
        )

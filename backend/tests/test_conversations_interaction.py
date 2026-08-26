"""Tests del endpoint de evidencia objetiva de interacción de conversaciones."""

from fastapi.testclient import TestClient

from main import app
from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    cid = conversations_repo.create_conversation(a)["id"]
    return a, cid


def test_interaction_endpoint_404_unknown_conversation(monkeypatch, tmp_path):
    a, _cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/conversations/nope/interaction", params={"user_id": a})
    assert r.status_code == 404


def test_interaction_endpoint_returns_evidence(monkeypatch, tmp_path):
    a, cid = _setup(monkeypatch, tmp_path)
    conversations_repo.save_conversation(
        cid,
        a,
        "T",
        [
            {
                "id": "m1",
                "role": "user",
                "content": "Hi",
                "duration_ms": 2000,
                "latency_ms": 400,
            },
            {
                "id": "m2",
                "role": "assistant",
                "content": "Hello",
                "duration_ms": 1000,
                "latency_ms": 200,
            },
            {
                "id": "m3",
                "role": "user",
                "content": "Bye",
                "duration_ms": 3000,
                "latency_ms": 600,
            },
        ],
    )
    with TestClient(app) as client:
        r = client.get(f"/api/conversations/{cid}/interaction", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["student_turns"] == 2
    assert body["assistant_turns"] == 1
    assert body["turn_balance"] is not None
    assert body["turn_duration"] is not None
    assert body["avg_response_latency_ms"] == 400
    assert body["interruptions"] == 0


def test_interaction_endpoint_empty_conversation(monkeypatch, tmp_path):
    a, cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(f"/api/conversations/{cid}/interaction", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["student_turns"] == 0
    assert body["assistant_turns"] == 0
    assert body["turn_balance"] is None
    assert body["turn_duration"] is None


def test_interaction_endpoint_isolation(monkeypatch, tmp_path):
    a, cid = _setup(monkeypatch, tmp_path)
    b = users_repo.create_user("B")["id"]
    with TestClient(app) as client:
        r = client.get(f"/api/conversations/{cid}/interaction", params={"user_id": b})
    assert r.status_code == 404

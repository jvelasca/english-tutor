"""Tests del progreso histórico: repo, domain y endpoint."""
import asyncio

from fastapi.testclient import TestClient

from domain import progress as progress_service
from main import app
from repositories import conversations as conversations_repo
from repositories import db
from repositories import grammar as grammar_repo
from repositories import progress as progress_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _seed_message(uid: str, mode: str) -> None:
    cid = conversations_repo.create_conversation(uid)["id"]
    conversations_repo.save_conversation(
        cid, uid, "Clase", [{"role": "user", "content": "Hi", "mode": mode}]
    )


def test_activity_events_isolated_per_user(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    _seed_message(a, "grammar")
    pronunciation_repo.record_pronunciation(a, "Hi", "Hi", 90, "good")
    _seed_message(b, "exercises")

    a_events = progress_repo.activity_events(a)
    b_events = progress_repo.activity_events(b)

    assert len(a_events) == 2  # 1 mensaje + 1 pronunciación
    assert {e["kind"] for e in a_events} == {"message", "pronunciation"}
    assert len(b_events) == 1  # solo el mensaje de B
    assert b_events[0]["kind"] == "message"
    assert b_events[0]["mode"] == "exercises"


def test_get_progress_history_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_message(a, "grammar")
    pronunciation_repo.record_pronunciation(a, "Hi", "Hi", 90, "good")
    grammar_repo.record_errors(a, [{"rule": "r", "message": "m", "example": "x"}])

    result = asyncio.run(progress_service.get_progress_history(a, "week"))
    assert result["user_id"] == a
    assert result["bucket"] == "week"
    assert isinstance(result["series"], list)
    assert result["streak"]["current_days"] >= 1
    assert result["streak"]["last_active_date"] is not None
    assert result["mastery"]["active"][0]["rule"] == "r"
    assert result["mastery"]["resolved"] == []
    assert len(result["milestones"]) == 10


def test_progress_history_endpoint_200(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_message(a, "exercises")
    with TestClient(app) as client:
        r = client.get(
            "/api/progress/history", params={"user_id": a, "bucket": "week"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == a
        assert body["bucket"] == "week"
        assert "series" in body
        assert "streak" in body
        assert "mastery" in body
        assert "milestones" in body


def test_progress_history_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/progress/history", params={"user_id": "no-existe"})
        assert r.status_code == 404


def test_progress_history_invalid_bucket_422(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/progress/history", params={"user_id": a, "bucket": "year"}
        )
        assert r.status_code == 422

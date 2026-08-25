"""Tests del objetivo personal de aprendizaje (learning_goal)."""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_goal_not_set_by_default(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    assert academy_repo.get_goal(a) is None


def test_upsert_goal_creates_and_reads(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    assert academy_repo.upsert_goal(a, "travel", 20, 6, "B2") is True
    row = academy_repo.get_goal(a)
    assert row == {
        "goal_type": "travel",
        "minutes_per_day": 20,
        "days_per_week": 6,
        "target_level": "B2",
    }


def test_upsert_goal_updates_existing(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    academy_repo.upsert_goal(a, "travel", 20, 6, "B2")
    assert academy_repo.upsert_goal(a, "exam", 30, 7, "C1") is True
    row = academy_repo.get_goal(a)
    assert row["goal_type"] == "exam"
    assert row["minutes_per_day"] == 30
    assert row["days_per_week"] == 7
    assert row["target_level"] == "C1"


def test_upsert_goal_rejects_unknown_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert academy_repo.upsert_goal("no-existe", "general", 15, 5, "B1") is False


def test_endpoint_goal_defaults(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/goal", params={"user_id": a})
    assert r.status_code == 200
    assert r.json() == {
        "goal_type": "general",
        "minutes_per_day": 15,
        "days_per_week": 5,
        "target_level": "B1",
    }


def test_endpoint_goal_put_then_get(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        put = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "interview",
                "minutes_per_day": 25,
                "days_per_week": 3,
                "target_level": "B2",
            },
        )
        assert put.status_code == 200
        assert put.json()["target_level"] == "B2"

        get = client.get("/api/academy/goal", params={"user_id": a})
        assert get.json()["goal_type"] == "interview"
        assert get.json()["minutes_per_day"] == 25
        assert get.json()["days_per_week"] == 3


def test_endpoint_goal_rejects_invalid_type(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "gaming",
                "minutes_per_day": 15,
                "days_per_week": 5,
                "target_level": "B1",
            },
        )
    assert r.status_code == 422


def test_endpoint_goal_rejects_invalid_target_level(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 15,
                "days_per_week": 5,
                "target_level": "D1",
            },
        )
    assert r.status_code == 422


def test_today_plan_uses_goal_budget(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 45,
                "days_per_week": 5,
                "target_level": "B1",
            },
        )
        r = client.get("/api/academy/today", params={"user_id": a})
    assert r.status_code == 200
    assert r.json()["total_minutes"] == 45


def test_student_model_uses_goal_target(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "work",
                "minutes_per_day": 15,
                "days_per_week": 5,
                "target_level": "C1",
            },
        )
        r = client.get("/api/academy/student-model", params={"user_id": a})
    assert r.status_code == 200
    assert r.json()["target_level"] == "C1"


def test_endpoint_session_new_user(monkeypatch, tmp_path):
    """Un usuario nuevo tiene una sesión con material nuevo y listening acotado."""
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/session", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["items"], "la sesión no está vacía para un usuario nuevo"
    assert body["total_minutes"] == 15  # presupuesto por defecto
    assert body["total_minutes"] == sum(i["minutes"] for i in body["items"])
    kinds = {i["kind"] for i in body["items"]}
    assert "new" in kinds
    assert "listening" in kinds
    listening = [i for i in body["items"] if i["kind"] == "listening"]
    assert len(listening) <= 2
    assert body["review_count"] + body["practice_count"] <= len(body["items"])


def test_endpoint_session_uses_goal_budget(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/api/academy/goal",
            params={"user_id": a},
            json={
                "goal_type": "general",
                "minutes_per_day": 45,
                "days_per_week": 5,
                "target_level": "B1",
            },
        )
        r = client.get("/api/academy/session", params={"user_id": a})
    assert r.status_code == 200
    assert r.json()["total_minutes"] == 45

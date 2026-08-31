"""Tests de Speaking Scenarios 3.0 (catálogo de escenarios comunicativos)."""

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import speaking_scenarios as scenarios_svc
from services.speaking import CONVERSATIONAL_TASK_TYPES, TASK_TYPES
from services.speaking_scenarios import SCENARIO_METRICS


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Catálogo versionado ----------------------------------------------------


def test_catalog_has_eight_scenarios_with_valid_metadata():
    scenarios = scenarios_svc.list_scenarios()
    assert len(scenarios) == 8
    ids = [s["id"] for s in scenarios]
    assert len(set(ids)) == 8, "ids duplicados"
    for scenario in scenarios:
        assert scenario["communicative_objective"]
        assert scenario["prompt"]
        assert scenario["task_type"] in TASK_TYPES
        assert 1 <= scenario["difficulty"] <= 6
        # Los escenarios comunicativos son conversacionales por definición.
        assert scenario["task_type"] in CONVERSATIONAL_TASK_TYPES


def test_catalog_metrics_are_canonical():
    for scenario in scenarios_svc.list_scenarios():
        assert scenario["metrics"], f"{scenario['id']} sin métricas"
        for metric in scenario["metrics"]:
            assert metric in SCENARIO_METRICS


def test_validate_scenarios_returns_no_errors():
    assert scenarios_svc.validate_scenarios() == []


def test_get_scenario_by_id():
    restaurant = scenarios_svc.get_scenario("restaurant")
    assert restaurant is not None
    assert restaurant["title"] == "Restaurant"
    assert restaurant["task_type"] == "role_play"
    assert "task_completion" in restaurant["metrics"]


def test_get_scenario_unknown_returns_none():
    assert scenarios_svc.get_scenario("does-not-exist") is None


# --- Endpoint ---------------------------------------------------------------


def test_speaking_scenarios_endpoint(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/speaking/scenarios", params={"user_id": a})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"]
    assert len(body["scenarios"]) == 8
    first = body["scenarios"][0]
    assert first["communicative_objective"]
    assert first["metrics"]

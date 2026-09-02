"""Tests de Speaking Mission Performance (V2.9)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import llm
from services import speaking_mission as mission_svc
from services.speaking import SPEAKING_CRITERIA
from services.speaking_scenarios import list_scenarios


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


WEAK_EVIDENCE = (
    '{"task_achieved": false, "grammar_errors": 4, '
    '"lexical_tokens": ["i", "go", "shop"], '
    '"coherence": 0.3, "interaction": 0.2}'
)

STRONG_EVIDENCE = (
    '{"task_achieved": true, "grammar_errors": 0, '
    '"lexical_tokens": ["student", "live", "city", "name", "job", "weekend"], '
    '"coherence": 0.9, "interaction": 0.85}'
)


# --- Motor puro -------------------------------------------------------------


def test_mission_phases_are_six():
    assert mission_svc.MISSION_PHASES == (
        "mission",
        "attempt",
        "evaluation",
        "drill",
        "retry",
        "improvement",
    )


def test_mission_from_scenario_copies_core_fields():
    scenario = list_scenarios()[0]
    mission = mission_svc.mission_from_scenario(scenario)
    assert mission["scenario_id"] == scenario["id"]
    assert mission["prompt"] == scenario["prompt"]
    assert mission["communicative_objective"] == scenario["communicative_objective"]


def test_evaluate_attempt_flags_weak_criteria():
    criteria = {c: 0.9 for c in SPEAKING_CRITERIA}
    criteria["fluency"] = 0.4
    criteria["grammatical_control"] = 0.5
    evaluation = mission_svc.evaluate_attempt(overall=0.7, criteria=criteria)
    assert evaluation["weak"] == ["grammatical_control", "fluency"]
    assert "fluency" in evaluation["recommendation"].lower() or "grammatical" in (
        evaluation["recommendation"].lower()
    )
    assert evaluation["phase"] == "evaluation"


def test_targeted_drills_cap_and_order():
    drills = mission_svc.targeted_drills(
        ["fluency", "coherence", "interaction"], cap=2
    )
    assert len(drills) == 2
    assert drills[0]["criterion"] == "fluency"
    assert drills[1]["criterion"] == "coherence"
    assert drills[0]["prompt"]


def test_improvement_positive_delta():
    first = mission_svc.evaluate_attempt(
        overall=0.5,
        criteria={c: 0.5 for c in SPEAKING_CRITERIA},
    )
    retry = mission_svc.evaluate_attempt(
        overall=0.8,
        criteria={c: 0.8 for c in SPEAKING_CRITERIA},
    )
    delta = mission_svc.improvement(first, retry)
    assert delta["improved"] is True
    assert delta["delta"] == pytest.approx(0.3)
    assert len(delta["by_criterion"]) == len(SPEAKING_CRITERIA)
    assert all(c["delta"] == pytest.approx(0.3) for c in delta["by_criterion"])


def test_improvement_no_change_not_improved():
    same = mission_svc.evaluate_attempt(
        overall=0.7,
        criteria={c: 0.7 for c in SPEAKING_CRITERIA},
    )
    delta = mission_svc.improvement(same, same)
    assert delta["improved"] is False
    assert delta["delta"] == 0.0


# --- Flujo HTTP completo ----------------------------------------------------


def test_speaking_mission_full_loop(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    scenario_id = list_scenarios()[0]["id"]
    client = TestClient(app)

    # Start
    start = client.post(
        "/api/academy/speaking/mission/start",
        params={"user_id": user_id},
        json={"scenario_id": scenario_id},
    )
    assert start.status_code == 200
    body = start.json()
    assert body["status"] == "mission"
    assert body["scenario_id"] == scenario_id
    assert body["mission"]["prompt"]
    session_id = body["session_id"]

    # Attempt (weak)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(WEAK_EVIDENCE))
    attempt = client.post(
        "/api/academy/speaking/mission/attempt",
        params={"user_id": user_id},
        json={"session_id": session_id, "heard": "I go shop.", "duration_seconds": 8},
    )
    assert attempt.status_code == 200
    mid = attempt.json()
    assert mid["status"] == "drill"
    assert mid["evaluation"] is not None
    assert mid["evaluation"]["weak"]
    assert mid["drills"]
    assert mid["attempt"]["overall"] is not None

    # Retry (stronger)
    monkeypatch.setattr(
        llm, "get_client", lambda: FakeOllamaClient(STRONG_EVIDENCE)
    )
    retry = client.post(
        "/api/academy/speaking/mission/retry",
        params={"user_id": user_id},
        json={
            "session_id": session_id,
            "heard": "I would like to buy a jacket, please.",
            "duration_seconds": 12,
        },
    )
    assert retry.status_code == 200
    done = retry.json()
    assert done["status"] == "improvement"
    assert done["improvement"] is not None
    assert done["improvement"]["improved"] is True
    assert done["improvement"]["delta"] is not None
    assert done["improvement"]["delta"] > 0

    # Get state
    state = client.get(
        f"/api/academy/speaking/mission/{session_id}",
        params={"user_id": user_id},
    )
    assert state.status_code == 200
    assert state.json()["status"] == "improvement"

    session = academy_repo.get_speaking_mission_session(session_id)
    assert session is not None
    assert session["improvement"]["improved"] is True


def test_speaking_mission_unknown_scenario(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    res = client.post(
        "/api/academy/speaking/mission/start",
        params={"user_id": user_id},
        json={"scenario_id": "does-not-exist"},
    )
    assert res.status_code == 404

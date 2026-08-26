"""Tests de Speaking Assessment 1.0 (sesión trazable + instrumento versionado)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import llm
from services import speaking_assessment as assessment_svc
from services.speaking import SPEAKING_CRITERIA, TASK_TYPES


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


GOOD_EVIDENCE = (
    '{"task_achieved": true, "grammar_errors": 1, '
    '"lexical_tokens": ["student", "live", "city", "name", "job"], '
    '"coherence": 0.8}'
)


def _row(item_id, result, created_at="2026-08-01T00:00:00"):
    return {"item_id": item_id, "result": result, "created_at": created_at}


# --- Instrumento versionado -------------------------------------------------


def test_assessment_parts_are_four_with_valid_task_types():
    parts = assessment_svc.assessment_parts()
    assert len(parts) == 4
    for i, part in enumerate(parts):
        assert part["part_index"] == i
        assert part["task_type"] in TASK_TYPES
        assert 1 <= part["difficulty"] <= 6
        assert part["prompt"]


# --- Motor determinista: aggregate_assessment ------------------------------


def test_aggregate_assessment_empty():
    agg = assessment_svc.aggregate_assessment([])
    assert agg["level"] is None
    assert agg["numeric"] is None
    assert agg["score"] is None
    assert agg["confidence"] == 0.0
    assert agg["attempts"] == 0
    assert len(agg["criteria"]) == len(SPEAKING_CRITERIA)
    assert agg["rubric_version"]
    assert agg["assessment_version"]


def test_aggregate_assessment_coherent_cefr():
    rows = []
    for criterion in SPEAKING_CRITERIA:
        rows.append(_row(criterion, 0.8))
        rows.append(_row(criterion, 0.9))
    rows.append(_row("overall", 0.8))
    rows.append(_row("overall", 0.9))
    agg = assessment_svc.aggregate_assessment(rows)
    assert agg["level"] == "C1"
    assert agg["numeric"] == pytest.approx(5.25)
    assert agg["score"] == pytest.approx(0.85)
    assert agg["confidence"] == 1.0
    assert agg["attempts"] == 2
    assert len(agg["criteria"]) == len(SPEAKING_CRITERIA)
    assert agg["weak"] == []
    assert agg["recommendation"] == "All speaking criteria look strong."


# --- Flujo completo start → 4 parts → finish -------------------------------


def test_speaking_assessment_full_flow(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(GOOD_EVIDENCE))
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        assert start.status_code == 200, start.text
        start_body = start.json()
        session_id = start_body["session_id"]
        assert start_body["total_parts"] == 4
        assert start_body["part"]["part_index"] == 0

        for i in range(4):
            r = client.post(
                "/api/academy/speaking/assessment/part",
                params={"user_id": a},
                json={
                    "session_id": session_id,
                    "heard": "I am a student and I live in the city",
                    "duration_seconds": 30.0,
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["part_index"] == i
            assert body["done"] == (i == 3)
            assert "overall" in body["part_scores"]

        finish = client.post(
            "/api/academy/speaking/assessment/finish",
            params={"user_id": a},
            json={"session_id": session_id},
        )
        assert finish.status_code == 200, finish.text
        result = finish.json()
        assert result["attempts"] == 4
        assert result["level"] is not None
        assert 1.0 <= result["numeric"] <= 6.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["assessment_version"]
        assert result["rubric_version"]
        assert len(result["criteria"]) == len(SPEAKING_CRITERIA)

        state = client.get(
            f"/api/academy/speaking/assessment/{session_id}", params={"user_id": a}
        )
        assert state.status_code == 200
        assert state.json()["status"] == "finished"
        assert state.json()["final_result"]["attempts"] == 4

    speaking_rows = [
        row
        for row in academy_repo.list_evidence(a)
        if row["assessment_version"] == assessment_svc.SPEAKING_ASSESSMENT_VERSION
    ]
    assert speaking_rows, "no se registró evidencia de speaking assessment"
    assert all(row["skill"] == "speaking" for row in speaking_rows)
    assert (
        sum(1 for row in speaking_rows if row["item_id"] == "overall") == 4
    ), "cada parte debe aportar una fila 'overall'"

    # Trazabilidad: la sesión persiste con sus partes, evidencia y resultado.
    session = academy_repo.get_speaking_assessment_session(session_id)
    assert session["user_id"] == a
    assert len(session["parts"]) == 4
    assert session["final_result"]["level"] is not None


def test_speaking_assessment_evidence_is_isolated(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(GOOD_EVIDENCE))
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        session_id = start.json()["session_id"]
        client.post(
            "/api/academy/speaking/assessment/part",
            params={"user_id": a},
            json={
                "session_id": session_id,
                "heard": "I am a student and I live in the city",
                "duration_seconds": 30.0,
            },
        )
    # La evidencia del usuario A no contamina al usuario B.
    assert academy_repo.list_evidence(b) == []


# --- Casos límite -----------------------------------------------------------


def test_finish_without_parts_returns_no_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        session_id = start.json()["session_id"]
        finish = client.post(
            "/api/academy/speaking/assessment/finish",
            params={"user_id": a},
            json={"session_id": session_id},
        )
    assert finish.status_code == 200
    result = finish.json()
    assert result["attempts"] == 0
    assert result["level"] is None
    assert result["numeric"] is None
    assert result["confidence"] == 0.0


def test_submit_part_unknown_session_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(GOOD_EVIDENCE))
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/speaking/assessment/part",
            params={"user_id": a},
            json={"session_id": 999999, "heard": "hello"},
        )
    assert r.status_code == 404


def test_submit_part_other_users_session_404(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(GOOD_EVIDENCE))
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        session_id = start.json()["session_id"]
        r = client.post(
            "/api/academy/speaking/assessment/part",
            params={"user_id": b},
            json={"session_id": session_id, "heard": "hello"},
        )
    assert r.status_code == 404


def test_submit_part_after_finish_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient(GOOD_EVIDENCE))
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        session_id = start.json()["session_id"]
        for _ in range(4):
            client.post(
                "/api/academy/speaking/assessment/part",
                params={"user_id": a},
                json={
                    "session_id": session_id,
                    "heard": "I am a student and I live in the city",
                    "duration_seconds": 30.0,
                },
            )
        client.post(
            "/api/academy/speaking/assessment/finish",
            params={"user_id": a},
            json={"session_id": session_id},
        )
        r = client.post(
            "/api/academy/speaking/assessment/part",
            params={"user_id": a},
            json={"session_id": session_id, "heard": "extra"},
        )
    assert r.status_code == 404


def test_finish_unknown_session_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/speaking/assessment/finish",
            params={"user_id": a},
            json={"session_id": 999999},
        )
    assert r.status_code == 404


def test_get_assessment_other_users_session_404(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/speaking/assessment/start", params={"user_id": a}
        )
        session_id = start.json()["session_id"]
        r = client.get(
            f"/api/academy/speaking/assessment/{session_id}", params={"user_id": b}
        )
    assert r.status_code == 404

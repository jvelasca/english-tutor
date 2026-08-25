"""Tests del scorer determinista de writing (rubric CEFR de 6 dimensiones)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import llm
from services import writing as writing_svc
from services.curriculum import load_level
from services.writing import CRITERION_WEIGHTS, WRITING_CRITERIA


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _first_writing_objective():
    objs = load_level("a1").objectives()
    for o in objs:
        if "writing" in o.skills:
            return o
    return objs[0]


class FakeOllamaClient:
    def __init__(self, content="Hi!"):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


def test_score_writing_keys_and_range():
    result = writing_svc.score_writing("I am a student", "I am a student")
    assert set(result.keys()) == {"text", "expected", "criteria", "overall"}
    assert set(result["criteria"].keys()) == set(WRITING_CRITERIA)
    for criterion in WRITING_CRITERIA:
        assert 0.0 <= result["criteria"][criterion] <= 1.0
    assert 0.0 <= result["overall"] <= 1.0


def test_score_writing_perfect_high():
    result = writing_svc.score_writing("I am a student", "I am a student")
    assert result["overall"] >= 0.7
    assert result["criteria"]["task_completion"] == 1.0
    assert result["criteria"]["lexical_resource"] == 1.0


def test_score_writing_mismatch_low():
    result = writing_svc.score_writing("banana banana banana", "I am a student")
    assert result["overall"] < 0.5
    assert result["criteria"]["task_completion"] < 0.5
    assert result["criteria"]["lexical_resource"] < 0.5


def test_score_writing_empty_expected():
    result = writing_svc.score_writing("anything", "")
    assert result["criteria"]["lexical_resource"] == 1.0
    assert result["criteria"]["task_completion"] == 1.0
    assert result["criteria"]["coherence"] == 1.0
    assert result["criteria"]["organization"] == 1.0


def test_rubric_weights_sum_to_one():
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Endpoint / integración (puente writing → mastery) --------------------


def test_writing_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_writing_objective()
    assert "writing" in obj.skills, "ningún objetivo A1 declara 'writing'"
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "text": "I am a student",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["writing_mastery"] > 0

    writing_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "writing"
    ]
    assert writing_rows, "no se registró evidencia de writing"
    assert all(row["skill"] == "writing" for row in writing_rows)
    assert len(writing_rows) >= 7  # 6 criterios + 1 overall
    assert academy_repo.get_objective_row(a, "a1", obj.id, "writing") is not None


def test_writing_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "expected": "I am a student",
                "text": "I am a student",
            },
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


def test_writing_evidence_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = _first_writing_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/writing",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "text": "I am a student",
            },
        )
    assert academy_repo.list_evidence(b) == []


# --- Endpoint / integración (tarea abierta: LLM extrae, scorer puntúa) -------


def test_writing_task_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_writing_objective()
    assert "writing" in obj.skills, "ningún objetivo A1 declara 'writing'"
    fake = FakeOllamaClient(
        content='{"task_completed": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student", "live", "city"], "organization": 0.8, '
        '"coherence": 0.8, "register": 0.7}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "text": "I am a student",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["writing_mastery"] > 0
    assert body["evidence"]["task_completed"] is True

    writing_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "writing"
    ]
    assert writing_rows, "no se registró evidencia de writing"
    assert all(row["skill"] == "writing" for row in writing_rows)


def test_writing_task_llm_invalid_returns_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_writing_objective()
    fake = FakeOllamaClient(content="not json")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "text": "I am a student",
            },
        )
    assert r.status_code == 404


def test_writing_task_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    fake = FakeOllamaClient(
        content='{"task_completed": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "organization": 1.0, '
        '"coherence": 1.0, "register": 1.0}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/writing/task",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "text": "I am a student",
            },
        )
    assert r.status_code == 404

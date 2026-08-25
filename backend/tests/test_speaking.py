"""Tests del scorer determinista de speaking (rubric CEFR de 6 dimensiones)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from routers import academy as academy_router
from services import llm
from services import speaking as speaking_svc
from services.curriculum import load_level
from services.speaking import CRITERION_WEIGHTS, SPEAKING_CRITERIA


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _first_speaking_objective():
    objs = load_level("a1").objectives()
    for o in objs:
        if "speaking" in o.skills:
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


def test_score_speaking_keys_and_range():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert set(result.keys()) == {"heard", "expected", "criteria", "overall"}
    assert set(result["criteria"].keys()) == set(SPEAKING_CRITERIA)
    for criterion in SPEAKING_CRITERIA:
        assert 0.0 <= result["criteria"][criterion] <= 1.0
    assert 0.0 <= result["overall"] <= 1.0


def test_score_speaking_perfect_high():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert result["overall"] >= 0.7
    assert result["criteria"]["pronunciation"] >= 0.9


def test_score_speaking_mismatch_low():
    result = speaking_svc.score_speaking("banana banana banana", "I am a student")
    assert result["overall"] < 0.5
    assert result["criteria"]["task_achievement"] < 0.5
    assert result["criteria"]["lexical_resource"] < 0.5


def test_score_speaking_fluency_unknown():
    result = speaking_svc.score_speaking("I am a student", "I am a student", None)
    assert result["criteria"]["fluency"] == 0.5


def test_score_speaking_empty_expected():
    result = speaking_svc.score_speaking("anything", "")
    assert result["criteria"]["lexical_resource"] == 1.0
    assert result["criteria"]["task_achievement"] == 1.0


def test_rubric_weights_sum_to_one():
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Endpoint / integración (puente speaking → mastery) --------------------


def test_speaking_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    assert "speaking" in obj.skills, "ningún objetivo A1 declara 'speaking'"
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)
    assert len(speaking_rows) >= 7  # 6 criterios + 1 overall
    assert academy_repo.get_objective_row(a, "a1", obj.id, "speaking") is not None


def test_speaking_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


def test_speaking_evidence_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert academy_repo.list_evidence(b) == []


# --- Endpoint / integración (tarea abierta: LLM extrae, scorer puntúa) -------


def test_speaking_task_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    assert "speaking" in obj.skills, "ningún objetivo A1 declara 'speaking'"
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student", "live", "city"], "coherence": 0.8}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["speaking_mastery"] > 0
    assert body["evidence"]["task_achieved"] is True

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)


def test_speaking_task_llm_invalid_returns_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    fake = FakeOllamaClient(content="not json")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404


def test_speaking_task_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 1.0}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404


# --- Endpoint / integración (audio → Whisper → scorer) ----------------------


def test_speaking_audio_read_aloud_records_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "I am a student", "duration": 3.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
            },
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 6
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"


def test_speaking_task_audio_records_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student", "live", "city", "name", "job"], '
        '"coherence": 0.9}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "I am a student", "duration": 3.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task/audio",
            params={"user_id": a},
            data={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
            },
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["evidence"]["task_achieved"] is True
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"


def test_speaking_audio_transcribe_error_500(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()

    def boom(audio, language="en"):
        raise Exception("boom")

    monkeypatch.setattr(academy_router, "transcribe_with_timing", boom)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={"level_id": "a1", "objective_id": obj.id, "expected": "hi"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 500


def test_speaking_audio_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "hi", "duration": 1.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={"level_id": "a2", "objective_id": obj.id, "expected": "hi"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 404

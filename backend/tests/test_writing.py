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


# --- Diagnóstico longitudinal de writing (V1.17) ---------------------------


def _writing_evidence_row(item_id, result, created_at="2026-08-01T00:00:00"):
    return {
        "skill": "writing",
        "item_id": item_id,
        "result": result,
        "created_at": created_at,
    }


def test_writing_diagnostic_empty():
    diag = writing_svc.writing_diagnostic([])
    assert diag["attempts"] == 0
    assert diag["overall_mean"] is None
    assert diag["trend"]["direction"] == "n/a"
    assert len(diag["criteria"]) == len(WRITING_CRITERIA)
    assert all(c["attempts"] == 0 and c["mean"] is None for c in diag["criteria"])
    assert set(diag["weak"]) == set(WRITING_CRITERIA)
    assert diag["recommendation"].startswith("Focus on")


def test_writing_diagnostic_strong():
    rows = []
    for criterion in WRITING_CRITERIA:
        rows.append(_writing_evidence_row(criterion, 0.9))
        rows.append(_writing_evidence_row(criterion, 0.95))
    rows.append(_writing_evidence_row("overall", 0.9))
    rows.append(_writing_evidence_row("overall", 0.95))
    diag = writing_svc.writing_diagnostic(rows)
    assert diag["attempts"] == 2
    assert diag["overall_mean"] == 0.925
    assert diag["weak"] == []
    assert diag["recommendation"] == "All writing criteria look strong."


def test_writing_diagnostic_weak_criterion():
    rows = []
    for _ in range(3):
        rows.append(_writing_evidence_row("organization", 0.4))
        rows.append(_writing_evidence_row("coherence", 0.9))
    for _ in range(3):
        rows.append(_writing_evidence_row("overall", 0.5))
    diag = writing_svc.writing_diagnostic(rows)
    assert "organization" in diag["weak"]
    assert "coherence" not in diag["weak"]


def test_writing_diagnostic_trend_up():
    rows = []
    for i, value in enumerate([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]):
        rows.append(
            _writing_evidence_row("overall", value, created_at=f"2026-08-{i + 1:02d}")
        )
    diag = writing_svc.writing_diagnostic(rows)
    assert diag["trend"]["direction"] == "up"
    assert diag["trend"]["delta"] > 0


def test_writing_diagnostic_recent_score_is_ema_not_mean():
    rows = [
        _writing_evidence_row("coherence", 0.5, "2026-08-01T00:00:00"),
        _writing_evidence_row("coherence", 0.5, "2026-08-02T00:00:00"),
        _writing_evidence_row("coherence", 0.9, "2026-08-03T00:00:00"),
    ]
    diag = writing_svc.writing_diagnostic(rows)
    coherence = next(c for c in diag["criteria"] if c["criterion"] == "coherence")
    assert coherence["mean"] == pytest.approx(0.633)
    # EMA da más peso a lo reciente: 0.7 > media 0.633.
    assert coherence["recent_score"] == pytest.approx(0.7)
    assert coherence["recent_score"] > coherence["mean"]
    assert coherence["lifetime_score"] == coherence["mean"]


def test_writing_diagnostic_review_due_forgetting():
    rows = [_writing_evidence_row("organization", 0.9, "2026-08-01T00:00:00")]
    # 31 días después, la recuperación de un 0.9 ha caído bajo el umbral → due.
    diag = writing_svc.writing_diagnostic(rows, now="2026-09-01T00:00:00")
    org = next(c for c in diag["criteria"] if c["criterion"] == "organization")
    assert org["review_due"] is True
    # Sin decaimiento (now vacío), un 0.9 reciente no está para repasar.
    fresh = writing_svc.writing_diagnostic(rows)
    fresh_org = next(c for c in fresh["criteria"] if c["criterion"] == "organization")
    assert fresh_org["review_due"] is False


def test_writing_diagnostic_recent_failure_triggers_review():
    rows = [
        _writing_evidence_row("grammatical_accuracy", 0.9, "2026-08-01T00:00:00"),
        _writing_evidence_row("grammatical_accuracy", 0.9, "2026-08-02T00:00:00"),
        _writing_evidence_row("grammatical_accuracy", 0.4, "2026-08-03T00:00:00"),
    ]
    diag = writing_svc.writing_diagnostic(rows)
    ga = next(c for c in diag["criteria"] if c["criterion"] == "grammatical_accuracy")
    assert ga["mean"] > 0.6
    assert ga["review_due"] is True


def test_writing_diagnostic_exposes_model_signals():
    rows = [
        _writing_evidence_row("register", 0.8, "2026-08-01T00:00:00"),
        _writing_evidence_row("register", 0.9, "2026-08-02T00:00:00"),
    ]
    diag = writing_svc.writing_diagnostic(rows)
    register = next(c for c in diag["criteria"] if c["criterion"] == "register")
    assert register["confidence"] == 1.0
    assert register["stability"] is not None
    assert register["lifetime_score"] == register["mean"]


def test_writing_level_empty():
    level = writing_svc.writing_level([])
    assert level["level"] is None
    assert level["numeric"] is None
    assert level["score"] is None
    assert level["confidence"] == 0.0
    assert level["attempts"] == 0


def test_writing_level_computes_cefr():
    rows = [
        _writing_evidence_row("overall", 0.8, "2026-08-01T00:00:00"),
        _writing_evidence_row("overall", 0.9, "2026-08-02T00:00:00"),
    ]
    level = writing_svc.writing_level(rows)
    assert level["score"] == pytest.approx(0.85)
    assert level["numeric"] == pytest.approx(5.25)
    assert level["level"] == "C1"
    assert level["confidence"] == 1.0
    assert level["attempts"] == 2


def test_writing_journey_steps_chronological():
    rows = [
        _writing_evidence_row("overall", 0.5, "2026-08-01T00:00:00"),
        _writing_evidence_row("overall", 0.7, "2026-08-02T00:00:00"),
        _writing_evidence_row("overall", 0.9, "2026-08-03T00:00:00"),
    ]
    journey = writing_svc.writing_journey(rows)
    assert journey["attempts"] == 3
    assert len(journey["steps"]) == 3
    assert [s["numeric"] for s in journey["steps"]] == [3.5, 4.0, 4.75]
    assert [s["level"] for s in journey["steps"]] == ["B2", "B2", "C1"]
    assert [s["confidence"] for s in journey["steps"]] == [0.0, 0.5, 0.75]
    assert journey["current_level"] == "C1"
    assert journey["current_numeric"] == pytest.approx(4.75)
    assert journey["current_confidence"] == pytest.approx(0.75)


def test_writing_diagnostic_level_journey_endpoints(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
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
        diag = client.get("/api/academy/writing/diagnostic", params={"user_id": a})
        level = client.get("/api/academy/writing/level", params={"user_id": a})
        journey = client.get("/api/academy/writing/journey", params={"user_id": a})
    assert diag.status_code == 200
    body = diag.json()
    assert body["attempts"] == 1
    assert body["overall_mean"] is not None
    assert len(body["criteria"]) == len(WRITING_CRITERIA)
    assert "overall" not in [c["criterion"] for c in body["criteria"]]
    for criterion in body["criteria"]:
        assert set(criterion.keys()) >= {
            "criterion",
            "attempts",
            "mean",
            "min",
            "max",
            "review_due",
        }
    assert level.status_code == 200
    assert level.json()["attempts"] == 1
    assert level.json()["level"] is not None
    assert journey.status_code == 200
    assert journey.json()["attempts"] == 1
    assert len(journey.json()["steps"]) == 1

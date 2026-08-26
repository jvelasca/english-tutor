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
    assert set(result.keys()) == {
        "heard",
        "expected",
        "criteria",
        "observed",
        "overall",
    }
    assert set(result["criteria"].keys()) == set(SPEAKING_CRITERIA)
    assert set(result["observed"].keys()) == set(SPEAKING_CRITERIA)
    for criterion in SPEAKING_CRITERIA:
        score = result["criteria"][criterion]
        if score is not None:
            assert 0.0 <= score <= 1.0
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


def test_score_speaking_fluency_unknown_is_unobserved():
    result = speaking_svc.score_speaking("I am a student", "I am a student", None)
    assert result["criteria"]["fluency"] is None
    assert result["observed"]["fluency"] is False


def test_score_speaking_empty_expected():
    result = speaking_svc.score_speaking("anything", "")
    assert result["criteria"]["lexical_resource"] == 1.0
    assert result["criteria"]["task_achievement"] == 1.0


def test_rubric_weights_sum_to_one():
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Criterios no observados + diversidad léxica (P0 Speaking scoring) -------


def test_scores_from_evidence_pronunciation_unobserved():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 1,
        "lexical_tokens": ["student", "live", "city"],
        "coherence": 0.8,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 3.0)
    assert result["criteria"]["pronunciation"] is None
    assert result["observed"]["pronunciation"] is False
    # El overall se recalcula solo sobre criterios observados (pronunciación fuera).
    assert result["overall"] > 0.0


def test_scores_from_evidence_no_audio_pronunciation_never_half():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student")
    assert result["criteria"]["pronunciation"] is None
    assert result["criteria"]["fluency"] is None
    assert result["observed"]["fluency"] is False
    # Ningún criterio no observado entra en el overall.
    assert 0.0 <= result["overall"] <= 1.0


def test_lexical_diversity_measures_repetition():
    assert speaking_svc.lexical_diversity([]) == 0.0
    # Sin repetición → TTR = 1.0.
    assert speaking_svc.lexical_diversity(["i", "am", "a", "student"]) == 1.0
    # Repetición baja la diversidad.
    assert speaking_svc.lexical_diversity(["banana", "banana", "banana"]) < 0.5


def test_scores_from_evidence_lexical_resource_is_diversity_not_overlap():
    # Una respuesta rica en variedad (aunque no comparta tokens con un "expected"
    # inexistente aquí) debe puntuar alta en lexical_resource.
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
    }
    rich = "I travelled to Italy with my wife and we visited Rome for five days"
    result = speaking_svc.scores_from_evidence(evidence, rich, 60.0)
    assert result["criteria"]["lexical_resource"] >= 0.8


def test_sequence_coherence_preserves_order():
    # Orden exacto → coherencia total.
    assert speaking_svc._sequence_coherence(
        ["i", "am", "a", "student"], ["i", "am", "a", "student"]
    ) == 1.0
    # Palabras desordenadas → coherencia parcial (no total).
    scrambled = speaking_svc._sequence_coherence(
        ["student", "a", "am", "i"], ["i", "am", "a", "student"]
    )
    assert 0.0 < scrambled < 1.0
    # Repetir la frase entera no infla la coherencia (no mide longitud).
    repeated = speaking_svc._sequence_coherence(
        ["i", "am", "a", "student", "i", "am", "a", "student"],
        ["i", "am", "a", "student"],
    )
    assert repeated == 1.0
    # Sin solapamiento → coherencia cero.
    assert (
        speaking_svc._sequence_coherence(
            ["banana", "banana", "banana"], ["i", "am", "a", "student"]
        )
        == 0.0
    )


def test_score_speaking_interaction_unobserved_read_aloud():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert result["criteria"]["interaction"] is None
    assert result["observed"]["interaction"] is False


def test_scores_from_evidence_interaction_observed():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "interaction": 0.8,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 120.0)
    assert result["criteria"]["interaction"] == 0.8
    assert result["observed"]["interaction"] is True


def test_scores_from_evidence_interaction_absent_unobserved():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 120.0)
    assert result["criteria"]["interaction"] is None
    assert result["observed"]["interaction"] is False


def test_scores_from_evidence_discourse_penalties_reduce_fluency():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "self_corrections": 3,
        "hesitations": 4,
        "repetitions": 2,
    }
    clean = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    heard = "I am a student and I live in a city near the coast with my family"
    dirty = speaking_svc.scores_from_evidence(evidence, heard, 120.0)
    base = speaking_svc.scores_from_evidence(clean, heard, 120.0)
    assert dirty["criteria"]["fluency"] < base["criteria"]["fluency"]


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
    assert len(body["criteria"]) == 7
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)
    # 6 criterios observados + 1 overall (interaction no observada en read-aloud).
    assert len(speaking_rows) >= 7
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
    assert len(body["criteria"]) == 7
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
    assert len(body["criteria"]) == 7
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


# --- Diagnóstico longitudinal de speaking (V1.15) -------------------------


def _evidence_row(item_id, result, created_at="2026-08-01T00:00:00"):
    return {
        "skill": "speaking",
        "item_id": item_id,
        "result": result,
        "created_at": created_at,
    }


def test_speaking_diagnostic_empty():
    diag = speaking_svc.speaking_diagnostic([])
    assert diag["attempts"] == 0
    assert diag["overall_mean"] is None
    assert diag["trend"]["direction"] == "n/a"
    assert len(diag["criteria"]) == len(SPEAKING_CRITERIA)
    assert all(c["attempts"] == 0 and c["mean"] is None for c in diag["criteria"])
    assert set(diag["weak"]) == set(SPEAKING_CRITERIA)
    assert diag["recommendation"].startswith("Focus on")


def test_speaking_diagnostic_strong():
    rows = []
    for criterion in SPEAKING_CRITERIA:
        rows.append(_evidence_row(criterion, 0.9))
        rows.append(_evidence_row(criterion, 0.95))
    rows.append(_evidence_row("overall", 0.9))
    rows.append(_evidence_row("overall", 0.95))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert diag["attempts"] == 2
    assert diag["overall_mean"] == 0.925
    assert diag["weak"] == []
    assert diag["recommendation"] == "All speaking criteria look strong."


def test_speaking_diagnostic_weak_criterion():
    rows = []
    for _ in range(3):
        rows.append(_evidence_row("pronunciation", 0.4))
        rows.append(_evidence_row("fluency", 0.9))
    for _ in range(3):
        rows.append(_evidence_row("overall", 0.5))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert "pronunciation" in diag["weak"]
    assert "fluency" not in diag["weak"]


def test_speaking_diagnostic_trend_up():
    rows = []
    for i, value in enumerate([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]):
        rows.append(_evidence_row("overall", value, created_at=f"2026-08-{i + 1:02d}"))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert diag["trend"]["direction"] == "up"
    assert diag["trend"]["delta"] > 0


def test_speaking_diagnostic_endpoint(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
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
                "duration_seconds": 3.0,
            },
        )
        r = client.get("/api/academy/speaking/diagnostic", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["overall_mean"] is not None
    assert len(body["criteria"]) == len(SPEAKING_CRITERIA)
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

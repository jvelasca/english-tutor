"""Tests del indicador de resiliencia auditiva (Listening 2.0) y de la
clasificación del corpus (contexto comunicativo)."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    DIFFICULTY_FACTORS,
    LISTENING_CONTEXTS,
    QUESTION_BANK,
    RESILIENCE_DIMENSIONS,
    listening_diagnostic,
    listening_resilience,
    resilience_dimensions,
    validate_listening_bank,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _q(factors: dict, audio_type: str = "recorded") -> dict:
    """Ítem mínimo con un vector de dificultad dado; `recorded` para que el vector
    realizado confíe en lo declarado (independiente de la realización TTS)."""
    base = {f: 1 for f in DIFFICULTY_FACTORS}
    base.update(factors)
    return {
        "id": "x",
        "difficulty_vector": base,
        "audio_type": audio_type,
        "speaker_count": factors.get("speaker_count", 1),
    }


def _patch_questions(monkeypatch, by_id: dict) -> None:
    monkeypatch.setattr("services.listening.get_question", lambda qid: by_id.get(qid))


# --- Clasificación por dimensión ---------------------------------------------


def test_resilience_dimensions_are_canonical():
    assert RESILIENCE_DIMENSIONS == (
        "clear_speech",
        "natural_speech",
        "connected_speech",
        "fast_speech",
        "noise",
        "accents",
    )


def test_resilience_dimensions_clear_speech():
    q = _q({"speed": 1, "noise": 1, "connected_speech": 1, "accent": 1})
    assert resilience_dimensions(q) == ["clear_speech"]


def test_resilience_dimensions_natural_speech():
    q = _q({"speed": 3, "noise": 2, "connected_speech": 1, "accent": 1})
    dims = resilience_dimensions(q)
    assert "natural_speech" in dims
    assert "fast_speech" not in dims


def test_resilience_dimensions_connected_speech():
    q = _q({"speed": 3, "noise": 1, "connected_speech": 5, "accent": 1})
    assert "connected_speech" in resilience_dimensions(q)


def test_resilience_dimensions_fast_speech():
    q = _q({"speed": 6, "noise": 1, "connected_speech": 1, "accent": 1})
    assert "fast_speech" in resilience_dimensions(q)


def test_resilience_dimensions_noise():
    q = _q({"speed": 3, "noise": 5, "connected_speech": 1, "accent": 1})
    assert "noise" in resilience_dimensions(q)


def test_resilience_dimensions_accents():
    q = _q({"speed": 3, "noise": 1, "connected_speech": 1, "accent": 5})
    assert "accents" in resilience_dimensions(q)


def test_resilience_dimensions_can_span_multiple():
    # Rápido + conectado + ruidoso: un mismo ítem ejercita varias condiciones.
    q = _q({"speed": 6, "noise": 5, "connected_speech": 6, "accent": 1})
    dims = resilience_dimensions(q)
    assert "fast_speech" in dims
    assert "noise" in dims
    assert "connected_speech" in dims


# --- Agregación del indicador --------------------------------------------------


def test_listening_resilience_aggregates_by_dimension(monkeypatch):
    slow = _q({"speed": 1, "noise": 1, "connected_speech": 1, "accent": 1})
    fast = _q({"speed": 5, "noise": 1, "connected_speech": 1, "accent": 1})
    _patch_questions(monkeypatch, {"slow": slow, "fast": fast})
    rows = [
        {"question_id": "slow", "correct": True},
        {"question_id": "slow", "correct": True},
        {"question_id": "fast", "correct": False},
    ]
    res = listening_resilience(rows)
    dims = {d["dimension"]: d for d in res["dimensions"]}
    assert dims["clear_speech"]["accuracy"] == 100.0
    assert dims["fast_speech"]["accuracy"] == 0.0
    assert dims["noise"]["attempts"] == 0
    assert dims["noise"]["accuracy"] is None


def test_listening_resilience_main_weakness_and_recommendation(monkeypatch):
    fast = _q({"speed": 6, "noise": 1, "connected_speech": 1, "accent": 1})
    clear = _q({"speed": 1, "noise": 1, "connected_speech": 1, "accent": 1})
    _patch_questions(monkeypatch, {"fast": fast, "clear": clear})
    rows = (
        [{"question_id": "fast", "correct": False}] * 3
        + [{"question_id": "clear", "correct": True}] * 3
    )
    res = listening_resilience(rows)
    assert res["main_weakness"] == "fast_speech"
    assert "fast speech" in res["recommendation"]


def test_listening_resilience_requires_min_attempts(monkeypatch):
    fast = _q({"speed": 6, "noise": 1, "connected_speech": 1, "accent": 1})
    _patch_questions(monkeypatch, {"fast": fast})
    rows = [
        {"question_id": "fast", "correct": False},
        {"question_id": "fast", "correct": False},
    ]
    res = listening_resilience(rows)
    assert res["main_weakness"] is None
    assert "Not enough evidence" in res["recommendation"]


def test_listening_resilience_empty_rows():
    res = listening_resilience([])
    assert len(res["dimensions"]) == len(RESILIENCE_DIMENSIONS)
    assert all(d["attempts"] == 0 for d in res["dimensions"])
    assert res["main_weakness"] is None


def test_diagnostic_exposes_resilience(monkeypatch):
    slow = _q({"speed": 1, "noise": 1, "connected_speech": 1, "accent": 1})
    _patch_questions(monkeypatch, {"slow": slow})
    diag = listening_diagnostic(
        [
            {"question_id": "slow", "skill": "detail", "correct": True},
            {"question_id": "slow", "skill": "detail", "correct": True},
        ]
    )
    assert "resilience" in diag
    assert diag["resilience"]["dimensions"][0]["dimension"] == "clear_speech"
    assert diag["resilience"]["dimensions"][0]["accuracy"] == 100.0


# --- Clasificación del corpus (contexto) ---------------------------------------


def test_listening_contexts_constant():
    assert LISTENING_CONTEXTS == (
        "conversation",
        "announcement",
        "message",
        "instructions",
        "news",
        "interview",
        "narrative",
        "presentation",
    )


def test_validate_listening_bank_detects_invalid_context():
    bad = dict(QUESTION_BANK[0])
    bad["context"] = "nope"
    errors = validate_listening_bank([bad])
    assert any("invalid context" in e for e in errors)


def test_validate_listening_bank_accepts_valid_context():
    good = dict(QUESTION_BANK[0])
    good["context"] = "conversation"
    assert validate_listening_bank([good]) == []


# --- Endpoint --------------------------------------------------------------------


def test_diagnostic_endpoint_exposes_resilience(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert "resilience" in body
    assert len(body["resilience"]["dimensions"]) == len(RESILIENCE_DIMENSIONS)
    assert body["resilience"]["main_weakness"] is None

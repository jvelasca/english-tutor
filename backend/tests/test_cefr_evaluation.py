"""Tests de la evaluación CEFR multi-señal: bandas, descriptor y delegación."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import (
    MIN_SAMPLES,
    TRACKED_SKILLS,
    estimate_cefr,
    evaluate_cefr,
    grammar_band,
    listening_band,
    vocabulary_band,
)
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def test_evaluate_cefr_no_evidence_is_a1():
    result = evaluate_cefr({"vocab_size": 0, "pronunciation_avg": None})
    assert result["level"] == "A1"
    assert result["confidence"] == 0.0


def test_evaluate_cefr_level_is_binding_weakest_evidenced():
    # vocabulario B1 (200 ≥ 50) y fluidez B2 (60 ≥ 5) son la única evidencia;
    # la banda más baja de las evidenciadas (B1) limita el nivel.
    result = evaluate_cefr(
        {
            "vocab_size": 200,
            "pronunciation_avg": 75,
            "pronunciation_attempts": 0,
            "grammar_error_rate": 0.02,
            "user_messages": 0,
            "messages": 60,
        }
    )
    assert result["level"] == "B1"
    assert result["bands"]["grammar"] == "B2"
    assert result["bands"]["fluency"] == "B2"
    assert result["bands"]["vocabulary"] == "B1"


def test_evaluate_cefr_all_evidenced_uses_weakest_band():
    # Todas las destrezas con muestras suficientes: el nivel es la banda más baja.
    result = evaluate_cefr(
        {
            "vocab_size": 1000,  # C1
            "pronunciation_avg": 95,  # B2
            "pronunciation_attempts": 3,
            "grammar_error_rate": 0.02,  # B2
            "user_messages": 5,
            "messages": 100,  # C1
            "listening_accuracy": 90.0,  # B2
            "listening_attempts": 5,
        }
    )
    assert result["level"] == "B2"
    assert result["confidence"] == 1.0


def test_evaluate_cefr_partial_confidence_below_one():
    result = evaluate_cefr({"vocab_size": 1000, "pronunciation_avg": None})
    assert result["level"] == "C1"  # solo vocabulario evidenciado (C1)
    assert 0.0 < result["confidence"] < 1.0


def test_evaluate_cefr_evidence_has_five_tracked_skills():
    result = evaluate_cefr({"vocab_size": 0})
    skills = [e["skill"] for e in result["evidence"]]
    assert skills == list(TRACKED_SKILLS)
    assert all(0.0 <= e["confidence"] <= 1.0 for e in result["evidence"])
    assert set(TRACKED_SKILLS) == set(MIN_SAMPLES)


def test_evaluate_cefr_bands_and_descriptor():
    result = evaluate_cefr({"vocab_size": 200, "pronunciation_avg": 75})
    assert set(result["bands"]) == {
        "vocabulary",
        "grammar",
        "fluency",
        "pronunciation",
        "listening",
    }
    assert result["descriptor"]


def test_vocabulary_band_thresholds():
    assert vocabulary_band(0) == "A1"
    assert vocabulary_band(60) == "A2"
    assert vocabulary_band(200) == "B1"
    assert vocabulary_band(500) == "B2"
    assert vocabulary_band(1000) == "C1"
    assert vocabulary_band(2500) == "C2"


def test_grammar_band_unknown():
    assert grammar_band(None) == "—"


def test_listening_band_thresholds():
    assert listening_band(None) == "—"
    assert listening_band(0.0) == "A1"
    assert listening_band(60.0) == "A2"
    assert listening_band(75.0) == "B1"
    assert listening_band(90.0) == "B2"


def test_estimate_cefr_delegates():
    signals = {"vocab_size": 500, "pronunciation_avg": 80, "exercises": 30}
    assert estimate_cefr(signals) == evaluate_cefr(signals)["level"]


def test_profile_endpoint_has_estimated_bands_and_descriptor(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat", "dog"])
    grammar_repo.record_errors(a, find_errors("He go to school"))

    with TestClient(app) as client:
        r = client.get("/api/profile", params={"user_id": a})
        assert r.status_code == 200
        body = r.json()
        assert body["estimated_bands"]["vocabulary"]
        assert body["estimated_descriptor"]

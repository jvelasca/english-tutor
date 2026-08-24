"""Tests de la evaluación CEFR multi-señal: bandas, descriptor y delegación."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import (
    estimate_cefr,
    evaluate_cefr,
    grammar_band,
    vocabulary_band,
)
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def test_evaluate_cefr_low_a1():
    assert (
        evaluate_cefr({"vocab_size": 0, "pronunciation_avg": None, "exercises": 0})[
            "level"
        ]
        == "A1"
    )


def test_evaluate_cefr_medium_b2():
    assert (
        evaluate_cefr(
            {"vocab_size": 200, "pronunciation_avg": 75, "exercises": 10}
        )["level"]
        == "B2"
    )


def test_evaluate_cefr_high_c2():
    assert (
        evaluate_cefr(
            {"vocab_size": 1000, "pronunciation_avg": 95, "exercises": 100}
        )["level"]
        == "C2"
    )


def test_evaluate_cefr_grammar_fluency_boost():
    result = evaluate_cefr(
        {
            "vocab_size": 200,
            "pronunciation_avg": 75,
            "exercises": 10,
            "grammar_error_rate": 0.02,
            "messages": 60,
        }
    )
    assert result["level"] == "C2"
    assert result["bands"]["grammar"] == "B2"


def test_evaluate_cefr_bands_and_descriptor():
    result = evaluate_cefr(
        {"vocab_size": 200, "pronunciation_avg": 75, "exercises": 10}
    )
    assert set(result["bands"]) == {
        "vocabulary",
        "grammar",
        "fluency",
        "pronunciation",
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


def test_estimate_cefr_delegates():
    signals = {"vocab_size": 500, "pronunciation_avg": 80, "exercises": 30}
    assert estimate_cefr(signals) == evaluate_cefr(signals)["level"]


def test_profile_endpoint_has_cefr_bands_and_descriptor(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat", "dog"])
    grammar_repo.record_errors(a, find_errors("He go to school"))

    with TestClient(app) as client:
        r = client.get("/api/profile", params={"user_id": a})
        assert r.status_code == 200
        body = r.json()
        assert body["cefr_bands"]["vocabulary"]
        assert body["cefr_descriptor"]

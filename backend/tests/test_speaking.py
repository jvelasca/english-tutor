"""Tests del scorer determinista de speaking (rubric CEFR de 6 dimensiones)."""

import pytest

from services import speaking as speaking_svc
from services.speaking import CRITERION_WEIGHTS, SPEAKING_CRITERIA


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

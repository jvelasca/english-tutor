"""Tests de la política de corrección según CEFR y de la política formal de feedback."""
from services.cefr import CEFR_LEVELS, PRE_A1
from services.policy import (
    CORRECTNESS_GUIDANCE,
    FEEDBACK_CATEGORIES,
    correctness_guidance,
    feedback_policy,
)


def test_all_cefr_levels_have_guidance():
    # Todo nivel de curso (A1..C2) más el tramo Pre-A1 tienen guía de corrección.
    assert set(CORRECTNESS_GUIDANCE.keys()) == set(CEFR_LEVELS) | {PRE_A1}


def test_guidance_varies_by_level():
    assert correctness_guidance("A1") != correctness_guidance("C2")
    assert correctness_guidance(PRE_A1) != correctness_guidance("A1")


def test_guidance_known_level():
    assert correctness_guidance("B2") == CORRECTNESS_GUIDANCE["B2"]


def test_guidance_unknown_falls_back_to_b1():
    assert correctness_guidance("Z9") == CORRECTNESS_GUIDANCE["B1"]


def test_feedback_categories_have_exactly_five_keys():
    assert set(FEEDBACK_CATEGORIES.keys()) == {
        "CORRECT",
        "NATURAL",
        "OPTIONAL",
        "STYLE",
        "PRONUNCIATION",
    }


def test_feedback_policy_contains_all_categories():
    policy = feedback_policy()
    for category in FEEDBACK_CATEGORIES:
        assert category in policy


def test_feedback_policy_is_deterministic():
    assert feedback_policy() == feedback_policy()

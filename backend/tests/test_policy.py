"""Tests de la política de corrección según CEFR."""
from services.cefr import CEFR_LEVELS
from services.policy import CORRECTNESS_GUIDANCE, correctness_guidance


def test_all_cefr_levels_have_guidance():
    assert set(CORRECTNESS_GUIDANCE.keys()) == set(CEFR_LEVELS)


def test_guidance_varies_by_level():
    assert correctness_guidance("A1") != correctness_guidance("C2")


def test_guidance_known_level():
    assert correctness_guidance("B2") == CORRECTNESS_GUIDANCE["B2"]


def test_guidance_unknown_falls_back_to_b1():
    assert correctness_guidance("Z9") == CORRECTNESS_GUIDANCE["B1"]

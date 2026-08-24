"""Tests del Context Builder: composición del system prompt."""
from config import MODE_PROMPTS
from services.context import build_system_prompt


def test_no_profile_returns_base_mode_prompt():
    assert build_system_prompt("grammar", None) == MODE_PROMPTS["grammar"]


def test_unknown_mode_falls_back_to_conversation():
    assert build_system_prompt("nope", None) == MODE_PROMPTS["conversation"]


def test_profile_includes_estimated_level_guidance():
    prompt = build_system_prompt("conversation", {"estimated_level": "A1"})
    assert "beginner" in prompt


def test_profile_includes_recurring_errors():
    prompt = build_system_prompt(
        "conversation",
        {
            "estimated_level": "B1",
            "recurring_errors": [
                {"rule": "x", "message": "Falta la -s.", "count": 3}
            ],
        },
    )
    assert "Falta la -s." in prompt


def test_profile_includes_recommendations():
    prompt = build_system_prompt(
        "conversation",
        {"estimated_level": "B1", "recommendations": ["Practica pronunciación."]},
    )
    assert "Practica pronunciación." in prompt


def test_empty_profile_returns_base_mode_prompt():
    assert build_system_prompt("conversation", {}) == MODE_PROMPTS["conversation"]


def test_profile_excludes_unconfirmed_errors():
    prompt = build_system_prompt(
        "conversation",
        {
            "estimated_level": "B1",
            "recurring_errors": [
                {
                    "rule": "a_an",
                    "message": "Usa 'an'.",
                    "count": 3,
                    "confirmed": False,
                },
                {
                    "rule": "x",
                    "message": "Falta la -s.",
                    "count": 2,
                    "confirmed": True,
                },
            ],
        },
    )
    assert "Usa 'an'." not in prompt
    assert "Falta la -s." in prompt

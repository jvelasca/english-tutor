from config import DEFAULT_MODE, MODE_PROMPTS
from services.llm import system_prompt_for


def test_has_all_modes():
    assert set(MODE_PROMPTS.keys()) == {
        "conversation",
        "grammar",
        "exercises",
        "pronunciation",
    }


def test_known_mode_returns_its_prompt():
    assert system_prompt_for("grammar") == MODE_PROMPTS["grammar"]


def test_unknown_mode_falls_back_to_conversation():
    assert system_prompt_for("nope") == MODE_PROMPTS[DEFAULT_MODE]

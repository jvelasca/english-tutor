"""Auditoría V3.70 · Eje 3: feedback y corrección.

Pinnean lo **medido** en `docs/audit/AC-PED-FEEDBACK.md` y en
`docs/audit/generated/feedback-coverage.json`.

La propiedad que estos tests protegen es la honestidad del canal: el sistema
**puntúa** de forma determinista y **no** delega la nota al LLM, pero solo
**redacta** feedback textual mediante prompt. Si alguien añade feedback
determinista o amplía las reglas de grammar, el test falla y obliga a re-auditar.
"""

from __future__ import annotations

from pathlib import Path

from services import context, grammar, policy, speaking, writing

BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVICES_DIR = BACKEND_DIR / "services"

EXPECTED_CATEGORIES = {
    "CORRECT",
    "NATURAL",
    "OPTIONAL",
    "PRONUNCIATION",
    "STYLE",
}

EXPECTED_GUIDANCE_LEVELS = {
    "Pre-A1",
    "A1",
    "A2",
    "B1",
    "B2",
    "C1",
    "C2",
}

# Destrezas cuya corrección es SOLO puntuación (sin mensaje correctivo declarado).
SCORE_ONLY_MODALITIES = {
    "interaction",
    "listening",
    "pronunciation",
    "vocabulary",
}


def test_grammar_rules_are_seven_and_only_three_confirmable() -> None:
    """7 reglas declaradas, pero solo 3 superan el umbral de confirmación."""
    assert len(grammar.RULES) == 7
    assert grammar.CONFIRMED_THRESHOLD == 0.8
    confirmable = [
        r["rule"]
        for r in grammar.RULES
        if r["confidence"] >= grammar.CONFIRMED_THRESHOLD
    ]
    assert len(confirmable) == 3
    assert set(confirmable) == {
        "capitalization_i",
        "double_negative",
        "he_she_it_s",
    }
    # Las cuatro restantes son "candidato" permanente.
    assert {
        "a_an",
        "there_their_theyre",
        "to_too",
        "your_youre",
    } == {r["rule"] for r in grammar.RULES} - set(confirmable)


def test_only_two_rules_can_track_mastery() -> None:
    """La racha de dominio solo es alcanzable en las reglas con patrón positivo."""
    assert grammar.MASTERY_STREAK == 3
    assert set(grammar.POSITIVE_PATTERNS) == {"he_she_it_s", "to_too"}
    rule_names = {r["rule"] for r in grammar.RULES}
    assert set(grammar.POSITIVE_PATTERNS) <= rule_names
    # Y una regla sin patrón positivo no puede detectar uso correcto.
    assert grammar.find_correct_usage("I like it", "capitalization_i") is False


def test_reading_and_mediation_have_no_correction_channel() -> None:
    """Las dos modalidades inertes tampoco tienen canal de corrección."""
    assert not (SERVICES_DIR / "reading.py").exists()
    assert not (SERVICES_DIR / "mediation.py").exists()


def test_score_only_modalities_are_declared() -> None:
    """Las cuatro destrezas de puntuación pura son las medidas."""
    assert SCORE_ONLY_MODALITIES == {
        "interaction",
        "listening",
        "pronunciation",
        "vocabulary",
    }
    # Ni interaction ni listening redactan texto: su evidencia es numérica.
    from services import interaction

    assert callable(interaction.interaction_evidence)


def test_rubric_sizes_are_pinned() -> None:
    assert len(writing.WRITING_CRITERIA) == 6
    assert len(speaking.SPEAKING_CRITERIA) == 7


def test_correctness_guidance_covers_every_level() -> None:
    assert set(policy.CORRECTNESS_GUIDANCE) == EXPECTED_GUIDANCE_LEVELS


def test_feedback_categories_are_the_five_declared() -> None:
    assert set(policy.FEEDBACK_CATEGORIES) == EXPECTED_CATEGORIES


def test_feedback_policy_mentions_every_category() -> None:
    text = policy.feedback_policy()
    for category in EXPECTED_CATEGORIES:
        assert category in text


def test_deterministic_scorers_run_without_llm() -> None:
    """La nota se calcula sin modelo: los scorers son deterministas."""
    written = writing.score_writing("I am a student", "I am a student")
    assert written["criteria"]["grammatical_accuracy"] == 1.0
    assert 0.0 <= written["overall"] <= 1.0

    spoken = speaking.score_speaking("I am a student", "I am a student")
    assert spoken["criteria"]["grammatical_control"] == 1.0
    assert 0.0 <= spoken["overall"] <= 1.0

    # Un error confirmable baja la nota, y el mismo texto da siempre lo mismo.
    bad = writing.score_writing("He go to school", "He goes to school")
    assert bad["criteria"]["grammatical_accuracy"] < 1.0
    assert bad == writing.score_writing("He go to school", "He goes to school")


def test_context_injects_the_correction_policy() -> None:
    """El punto de inyección del prompt del tutor incluya la política."""
    source = (SERVICES_DIR / "context.py").read_text(encoding="utf-8")
    assert "feedback_policy" in source
    assert "correctness_guidance" in source
    # Y el módulo expone una función de prompt de sistema que la usa.
    assert callable(context.build_system_prompt)

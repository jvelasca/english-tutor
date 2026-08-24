"""Construcción del system prompt del tutor a partir del modo y el perfil."""

from __future__ import annotations

from config import DEFAULT_MODE, MODE_PROMPTS
from services.policy import correctness_guidance, feedback_policy

MAX_ERRORS_IN_PROMPT = 3
MAX_RECS_IN_PROMPT = 3


def build_system_prompt(mode: str, profile: dict | None = None) -> str:
    """Compone el system prompt: prompt base del modo + política formal de corrección
    + (si hay perfil) guía por nivel, errores recurrentes y áreas de enfoque."""
    base = MODE_PROMPTS.get(mode, MODE_PROMPTS[DEFAULT_MODE])

    parts = [base, feedback_policy()]
    if not profile:
        return "\n".join(parts)

    level = profile.get("estimated_level")
    if level:
        parts.append(correctness_guidance(level))

    errors = [
        e for e in (profile.get("recurring_errors") or []) if e.get("confirmed", True)
    ]
    if errors:
        top = "; ".join(e["message"] for e in errors[:MAX_ERRORS_IN_PROMPT])
        parts.append(
            f"The learner's most frequent mistakes: {top} "
            "Prioritize correcting these patterns."
        )

    recs = profile.get("recommendations") or []
    if recs:
        parts.append("Learner focus areas: " + "; ".join(recs[:MAX_RECS_IN_PROMPT]))

    return "\n".join(parts)


def build_lesson_prompt(
    objective: dict,
    level: str,
    mastery: dict[str, float] | None = None,
    errors: list[dict] | None = None,
) -> str:
    """Construye el system prompt del AI Teacher para una lección de la Academy.

    El tutor deja de ser "conversación libre" y pasa a enseñar un objetivo concreto
    ("Can Do" statement), guiando al alumno por los conceptos y vocabulario
    requeridos, respetando la política de corrección y su nivel estimado."""
    mastery = mastery or {}
    errors = errors or []

    parts = [
        "You are the English Tutor Academy AI teacher.",
        f"Today's objective ({level}): {objective['can_do']}",
    ]

    concepts = objective.get("concepts") or []
    if concepts:
        parts.append("Required structures: " + ", ".join(concepts) + ".")

    vocab = objective.get("vocabulary") or []
    if vocab:
        parts.append("Target vocabulary: " + ", ".join(vocab) + ".")

    if level:
        parts.append(correctness_guidance(level))

    skills = objective.get("skills") or []
    if skills and mastery:
        snap = ", ".join(f"{s}={round(mastery.get(s, 0.0) * 100)}%" for s in skills)
        parts.append(f"Current skill mastery: {snap}. Focus on the weakest skills.")
        weakest = min(skills, key=lambda s: mastery.get(s, 0.0))
        parts.append(f"Prioritize practising the skill '{weakest}'.")

    confirmed = [e for e in errors if e.get("confirmed", True)]
    if confirmed:
        top = "; ".join(e["message"] for e in confirmed[:MAX_ERRORS_IN_PROMPT])
        parts.append(
            f"The learner's recurring mistakes: {top}. "
            "Correct these patterns as they appear."
        )

    parts.append(
        "Teach through short interactive practice: give a small task, wait for the "
        "student's answer, then correct and praise. Keep turns short and focused on "
        "the objective."
    )
    parts.append(feedback_policy())

    return "\n".join(parts)

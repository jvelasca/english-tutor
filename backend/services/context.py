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

"""Política de corrección del tutor según el nivel CEFR (puro, determinista)."""
from __future__ import annotations

# Guía por nivel CEFR que se añade al system prompt del tutor (en inglés,
# coherente con MODE_PROMPTS).
CORRECTNESS_GUIDANCE: dict[str, str] = {
    "A1": (
        "The learner is a beginner (CEFR A1). Correct every error gently and in "
        "simple language; explain in Spanish when helpful."
    ),
    "A2": (
        "The learner is elementary (CEFR A2). Correct errors clearly and keep "
        "explanations brief."
    ),
    "B1": (
        "The learner is intermediate (CEFR B1). Correct errors but focus on the "
        "most important ones."
    ),
    "B2": (
        "The learner is upper-intermediate (CEFR B2). Correct subtle errors and "
        "idiomatic usage."
    ),
    "C1": (
        "The learner is advanced (CEFR C1). Only point out subtle errors or "
        "naturalness issues; do not over-explain."
    ),
    "C2": (
        "The learner is proficient (CEFR C2). Focus on nuance, register and style."
    ),
}


def correctness_guidance(cefr_level: str) -> str:
    """Devuelve la guía de corrección para un nivel CEFR; si el nivel no se
    reconoce, usa la del intermedio (B1)."""
    return CORRECTNESS_GUIDANCE.get(cefr_level, CORRECTNESS_GUIDANCE["B1"])

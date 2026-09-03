"""Política de corrección del tutor según el nivel CEFR (puro, determinista)."""
from __future__ import annotations

# Guía por nivel CEFR que se añade al system prompt del tutor (en inglés,
# coherente con MODE_PROMPTS).
CORRECTNESS_GUIDANCE: dict[str, str] = {
    "Pre-A1": (
        "The learner is a pre-beginner (below CEFR A1). Keep everything very "
        "short and simple; praise effort, correct gently and provide model "
        "sentences to repeat."
    ),
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


# Taxonomía formal de corrección: el tutor debe distinguir un error real de una
# sugerencia de estilo o una variante opcional, para no marcarlo como error.
FEEDBACK_CATEGORIES: dict[str, str] = {
    "CORRECT": "the sentence is grammatically correct; do not flag it",
    "NATURAL": "correct but unnatural; suggest a more idiomatic phrasing",
    "OPTIONAL": "an acceptable variation; do not mark it as a mistake",
    "STYLE": "a register or tone issue; label it as a style note, not an error",
    "PRONUNCIATION": "a sound, stress or intonation point; give pronunciation guidance",
}


def feedback_policy() -> str:
    """Devuelve la política formal de categorías de corrección para el system prompt.

    Instruye al tutor para clasificar cada corrección con una única categoría y para
    no presentar como error lo que es natural, opcional o de estilo."""
    lines = [
        "Classify each correction using exactly one of these categories:",
        *[f"- {name}: {desc}." for name, desc in FEEDBACK_CATEGORIES.items()],
        (
            "Only correct real errors. Never report natural, optional or stylistic "
            "phrasing as a mistake."
        ),
    ]
    return "\n".join(lines)

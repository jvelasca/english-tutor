"""Evaluación de pronunciación: compara texto esperado con el transcrito (puro,
testable)."""
from __future__ import annotations

import re

from services.phonetics import composite_score

# Umbral de "buena pronunciación" (porcentaje de similitud).
PASS_THRESHOLD = 80


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


def _level(score: int) -> str:
    if score >= PASS_THRESHOLD:
        return "good"
    if score >= 50:
        return "fair"
    return "needs_practice"


def score_pronunciation(expected: str, heard: str) -> dict:
    """Devuelve score/level/ok + word_accuracy + phonetic_score + breakdown."""
    comp = composite_score(expected, heard)
    score = comp["score"]
    return {
        "expected": expected.strip(),
        "heard": heard.strip(),
        "score": score,
        "level": _level(score),
        "ok": score >= PASS_THRESHOLD,
        "word_accuracy": comp["word_accuracy"],
        "phonetic_score": comp["phonetic_score"],
        "breakdown": comp["breakdown"],
    }

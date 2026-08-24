"""Evaluación de pronunciación: compara texto esperado con el transcrito (puro,
testable)."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

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
    """Devuelve un dict con score (0-100), level y ok, además de expected/heard."""
    e = _normalize(expected)
    h = _normalize(heard)
    ratio = SequenceMatcher(None, e, h).ratio() if (e and h) else 0.0
    score = round(ratio * 100)
    return {
        "expected": expected.strip(),
        "heard": heard.strip(),
        "score": score,
        "level": _level(score),
        "ok": score >= PASS_THRESHOLD,
    }

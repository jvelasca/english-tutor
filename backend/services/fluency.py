"""Métricas de fluidez oral (puro, determinista).

Calcula palabras por minuto (WPM) a partir del texto oído y la duración del audio.
"""
from __future__ import annotations


def compute_fluency(heard: str, duration_seconds: float | None) -> dict:
    """Devuelve word_count, duration_seconds, wpm (float|None) y level.

    level: "fluent" (wpm ≥ 120), "good" (60–119), "slow" (< 60), o "—" cuando no
    se puede calcular (sin audio válido o sin palabras).
    """
    words = [w for w in heard.split() if w.strip()]
    word_count = len(words)

    duration = (
        round(duration_seconds, 2) if duration_seconds is not None else None
    )
    wpm: float | None = None
    level = "—"
    if duration and duration > 0 and word_count > 0:
        wpm = round(word_count / (duration / 60), 1)
        if wpm >= 120:
            level = "fluent"
        elif wpm >= 60:
            level = "good"
        else:
            level = "slow"

    return {
        "word_count": word_count,
        "duration_seconds": duration,
        "wpm": wpm,
        "level": level,
    }

"""Estimación heurística de nivel CEFR y recomendaciones (puro, determinista)."""
from __future__ import annotations

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def estimate_cefr(signals: dict) -> str:
    """Estima el nivel CEFR a partir de señales: vocab_size, pronunciation_avg
    (float|None) y exercises. Heurística v1 (la evaluación CEFR real es la Fase 8)."""
    vocab = signals.get("vocab_size", 0)
    pron = signals.get("pronunciation_avg")
    exercises = signals.get("exercises", 0)

    points = 0
    if vocab >= 900:
        points += 4
    elif vocab >= 400:
        points += 3
    elif vocab >= 150:
        points += 2
    elif vocab >= 50:
        points += 1

    if pron is not None:
        if pron >= 85:
            points += 3
        elif pron >= 70:
            points += 2
        elif pron >= 50:
            points += 1

    if exercises >= 50:
        points += 3
    elif exercises >= 20:
        points += 2
    elif exercises >= 5:
        points += 1

    if points >= 9:
        return "C2"
    if points >= 7:
        return "C1"
    if points >= 5:
        return "B2"
    if points >= 3:
        return "B1"
    if points >= 1:
        return "A2"
    return "A1"


def recommendations(profile: dict) -> list[str]:
    """Genera recomendaciones en español a partir del perfil agregado."""
    recs: list[str] = []
    errors = profile.get("recurring_errors", [])
    if errors:
        recs.append(f"Refuerza: {errors[0]['message']} (error recurrente).")
    pron = profile.get("pronunciation_avg")
    if pron is not None and pron < 70:
        recs.append("Practica pronunciación con la tarjeta de pronunciación.")
    if profile.get("vocab_size", 0) < 50:
        recs.append("Amplía vocabulario: lee y describe imágenes o rutinas.")
    if not recs:
        recs.append("¡Buen trabajo! Sigue practicando conversación.")
    return recs

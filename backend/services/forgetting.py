"""Modelo de olvido y programación de repaso (V1.4).

Determinista y puro: recibe un `score`, el timestamp de la última evidencia y un
`now` ISO explícito para poder testear sin depender del reloj de pared. Usa una
curva de olvido exponencial (half-life): la probabilidad de recuperación decae
con el tiempo desde la última evidencia, más lento cuanto mayor es el score.

Cadena del modelo:
    memory_strength (score) -> time_since_review -> retrieval_probability -> review_due
"""

from __future__ import annotations

import math
from datetime import datetime

# Estabilidad (half-life) mínima en días (score ~ 0).
STABILITY_MIN_DAYS = 1.0
# Crecimiento exponencial de la estabilidad con el score: stability = MIN * e^(G*score).
STABILITY_GROWTH = 3.0
# La destreza se considera "para repasar" cuando la recuperación cae bajo este umbral.
REVIEW_THRESHOLD = 0.7


def stability_days(score: float) -> float:
    """Días de estabilidad (half-life) según el score: más dominio => más memoria."""
    s = max(0.0, min(1.0, score))
    return STABILITY_MIN_DAYS * math.exp(STABILITY_GROWTH * s)


def days_since(last_seen_at: str, now: str) -> float:
    """Días transcurridos entre dos timestamps ISO. 0.0 si falta alguno o son
    inválidos."""
    if not last_seen_at or not now:
        return 0.0
    try:
        last = datetime.fromisoformat(last_seen_at)
        current = datetime.fromisoformat(now)
    except ValueError:
        return 0.0
    return max(0.0, (current - last).total_seconds() / 86400.0)


def retrieval_probability(score: float, last_seen_at: str, now: str) -> float:
    """Probabilidad de recuperación actual (0..1) dada la curva de olvido."""
    s = max(0.0, min(1.0, score))
    t = days_since(last_seen_at, now)
    if t <= 0.0:
        return s
    return s * math.exp(-t / stability_days(s))


def review_due(score: float, last_seen_at: str, now: str) -> bool:
    """True si conviene repasar: la recuperación ha caído bajo el umbral.

    Sin timestamp de última evidencia no hay olvido medible: se considera due solo
    si la destreza es débil (score bajo el umbral)."""
    if not last_seen_at:
        return score < REVIEW_THRESHOLD
    return retrieval_probability(score, last_seen_at, now) < REVIEW_THRESHOLD

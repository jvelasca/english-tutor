"""Estimación heurística de nivel CEFR y recomendaciones (puro, determinista)."""
from __future__ import annotations

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _vocab_points(vocab: int) -> int:
    if vocab >= 900:
        return 4
    if vocab >= 400:
        return 3
    if vocab >= 150:
        return 2
    if vocab >= 50:
        return 1
    return 0


def _pron_points(pron: float | None) -> int:
    if pron is None:
        return 0
    if pron >= 85:
        return 3
    if pron >= 70:
        return 2
    if pron >= 50:
        return 1
    return 0


def _exercise_points(exercises: int) -> int:
    if exercises >= 50:
        return 3
    if exercises >= 20:
        return 2
    if exercises >= 5:
        return 1
    return 0


def _grammar_points(error_rate: float | None) -> int:
    if error_rate is None:
        return 0
    if error_rate <= 0.05:
        return 2
    if error_rate <= 0.15:
        return 1
    return 0


def _fluency_points(messages: int) -> int:
    if messages >= 50:
        return 2
    if messages >= 10:
        return 1
    return 0


def _level_from_points(points: int) -> str:
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


def vocabulary_band(vocab: int) -> str:
    if vocab >= 2000:
        return "C2"
    if vocab >= 900:
        return "C1"
    if vocab >= 400:
        return "B2"
    if vocab >= 150:
        return "B1"
    if vocab >= 50:
        return "A2"
    return "A1"


def grammar_band(error_rate: float | None) -> str:
    if error_rate is None:
        return "—"
    if error_rate <= 0.05:
        return "B2"
    if error_rate <= 0.15:
        return "B1"
    if error_rate <= 0.30:
        return "A2"
    return "A1"


def fluency_band(messages: int) -> str:
    if messages >= 100:
        return "C1"
    if messages >= 50:
        return "B2"
    if messages >= 20:
        return "B1"
    if messages >= 5:
        return "A2"
    return "A1"


def pronunciation_band(avg: float | None) -> str:
    if avg is None:
        return "—"
    if avg >= 85:
        return "B2"
    if avg >= 70:
        return "B1"
    if avg >= 50:
        return "A2"
    return "A1"


_LEVEL_DESCRIPTORS = {
    "A1": "Principiante: frases muy básicas y vocabulario esencial.",
    "A2": "Básico: comunicación en rutinas y temas cotidianos.",
    "B1": "Intermedio: desenvoltura en situaciones familiares y opiniones simples.",
    "B2": "Intermedio alto: argumentación clara y comprensión de textos complejos.",
    "C1": "Avanzado: uso flexible y preciso del idioma en contextos variados.",
    "C2": "Maestría: dominio cercano al nativo con precisión y matices.",
}


def level_descriptor(level: str) -> str:
    return _LEVEL_DESCRIPTORS.get(level, "")


def evaluate_cefr(signals: dict) -> dict:
    """Evalúa el nivel CEFR con señales múltiples y devuelve nivel + bandas +
    descriptor.

    Señales: vocab_size, pronunciation_avg, exercises, grammar_error_rate
    (errores/mensaje, float|None) y messages. Las nuevas señales (grammar y
    fluency) son opcionales: si faltan, aportan 0 puntos y el resultado coincide
    con la heurística v1 original.
    """
    vocab = signals.get("vocab_size", 0)
    pron = signals.get("pronunciation_avg")
    exercises = signals.get("exercises", 0)
    error_rate = signals.get("grammar_error_rate")
    messages = signals.get("messages", 0)

    points = (
        _vocab_points(vocab)
        + _pron_points(pron)
        + _exercise_points(exercises)
        + _grammar_points(error_rate)
        + _fluency_points(messages)
    )
    level = _level_from_points(points)
    return {
        "level": level,
        "bands": {
            "vocabulary": vocabulary_band(vocab),
            "grammar": grammar_band(error_rate),
            "fluency": fluency_band(messages),
            "pronunciation": pronunciation_band(pron),
        },
        "descriptor": level_descriptor(level),
    }


def estimate_cefr(signals: dict) -> str:
    """Estima el nivel CEFR (delega en `evaluate_cefr`, manteniendo la API v1)."""
    return evaluate_cefr(signals)["level"]


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

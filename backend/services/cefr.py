"""Estimación heurística de nivel CEFR y recomendaciones (puro, determinista).

IMPORTANTE (naming CEFR): las funciones de banda de este módulo
(`vocabulary_band`, `grammar_band`, `fluency_band`, `pronunciation_band`,
`listening_band` y `heuristic_band`) producen bandas **heurísticas alineadas con
CEFR**, NO equivalencias oficiales. Son proxies internos de visualización; la
certificación oficial CEFR es otra cosa. Esta distinción se refleja también en la
UI (`estimated_bands` → "banda heurística").
"""
from __future__ import annotations

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Versión del modelo unificado de estimación CEFR del Student Model (snapshot
# reproducible: cada snapshot de evaluación guarda esta versión como instrumento).
CEFR_MODEL_VERSION = "2.0.0"

# Mínimo de muestras por destreza para que su banda cuente como evidencia (P5).
# Una destreza sin muestras suficientes no limita el nivel, pero reduce la confianza.
MIN_SAMPLES: dict[str, int] = {
    "vocabulary": 50,  # palabras distintas producidas
    "grammar": 5,  # mensajes de usuario analizados
    "fluency": 5,  # mensajes totales
    "pronunciation": 3,  # intentos de pronunciación
    "listening": 5,  # intentos de listening
}

TRACKED_SKILLS: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "fluency",
    "pronunciation",
    "listening",
)


def _band_rank(level: str) -> int:
    """Posición de una banda CEFR; `"—"` (sin señal) vale -1."""
    if level in CEFR_LEVELS:
        return CEFR_LEVELS.index(level)
    return -1


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


def listening_band(accuracy: float | None) -> str:
    if accuracy is None:
        return "—"
    if accuracy >= 85:
        return "B2"
    if accuracy >= 70:
        return "B1"
    if accuracy >= 50:
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


def heuristic_band(score: float | None) -> str:
    """Banda CEFR-alineada **heurística** para un score de dominio continuo (0..1).

    Proxy interno de visualización (NO equivalencia oficial CEFR). Usa las mismas
    fronteras de media banda que `adaptive.numeric_to_level`, de modo que un score
    de destreza 0..1 mapea a A1..C2 de forma monotónica: 0.0→A1 … 1.0→C2. `None`
    (sin observación) devuelve "—".
    """
    if score is None:
        return "—"
    numeric = 1.0 + 5.0 * score
    if numeric < 1.5:
        return "A1"
    if numeric < 2.5:
        return "A2"
    if numeric < 3.5:
        return "B1"
    if numeric < 4.5:
        return "B2"
    if numeric < 5.5:
        return "C1"
    return "C2"


def evaluate_cefr(signals: dict) -> dict:
    """Evalúa el nivel CEFR con un modelo de evidencia (P5).

    Sustituye al antiguo "punto-sum": cada destreza aporta una banda y un número de
    muestras; una destreza solo cuenta como evidencia si alcanza su mínimo
    (`MIN_SAMPLES`). El nivel global es la banda más baja entre las destrezas con
    evidencia suficiente; si ninguna la tiene, se devuelve "A1" con confianza 0.

    Señales: vocab_size, pronunciation_avg, pronunciation_attempts,
    grammar_error_rate, messages, user_messages, listening_accuracy y
    listening_attempts. `exercises` se acepta por compatibilidad pero ya no
    participa en el modelo.
    """
    vocab = signals.get("vocab_size", 0)
    pron = signals.get("pronunciation_avg")
    pron_attempts = signals.get("pronunciation_attempts", 0)
    error_rate = signals.get("grammar_error_rate")
    messages = signals.get("messages", 0)
    user_messages = signals.get("user_messages", 0)
    listening_accuracy = signals.get("listening_accuracy")
    listening_attempts = signals.get("listening_attempts", 0)

    bands = {
        "vocabulary": vocabulary_band(vocab),
        "grammar": grammar_band(error_rate),
        "fluency": fluency_band(messages),
        "pronunciation": pronunciation_band(pron),
        "listening": listening_band(listening_accuracy),
    }
    samples = {
        "vocabulary": vocab,
        "grammar": user_messages,
        "fluency": messages,
        "pronunciation": pron_attempts,
        "listening": listening_attempts,
    }

    evidence: list[dict] = []
    for skill in TRACKED_SKILLS:
        required = MIN_SAMPLES[skill]
        n = samples[skill]
        confidence = round(min(1.0, n / required), 2) if required else 1.0
        evidence.append(
            {
                "skill": skill,
                "band": bands[skill],
                "samples": n,
                "required": required,
                "confidence": confidence,
            }
        )

    evidenced = [e for e in evidence if e["confidence"] >= 1.0 and e["band"] != "—"]
    if evidenced:
        level = min(evidenced, key=lambda e: _band_rank(e["band"]))["band"]
    else:
        level = "A1"

    overall_confidence = round(
        sum(e["confidence"] for e in evidence) / len(evidence), 2
    )

    return {
        "level": level,
        "bands": bands,
        "evidence": evidence,
        "confidence": overall_confidence,
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

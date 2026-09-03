"""Estimación heurística de nivel CEFR y recomendaciones (puro, determinista).

IMPORTANTE (naming CEFR): las funciones de banda de este módulo
(`vocabulary_band`, `grammar_band`, `fluency_band`, `pronunciation_band`,
`listening_band` y `heuristic_band`) producen bandas **heurísticas alineadas con
CEFR**, NO equivalencias oficiales. Son proxies internos de visualización; la
certificación oficial CEFR es otra cosa. Esta distinción se refleja también en la
UI (`estimated_bands` → "banda heurística").
"""
from __future__ import annotations

# Tramo por debajo de A1: alumnos sin evidencia consolidada aún. No tiene curso
# propio (la progresión curricular sigue siendo A1..C2), pero sí es la banda más
# baja de la escalera de competencia (ver `services.cefr_descriptors`).
PRE_A1 = "Pre-A1"

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Orden completo de bandas que pueden emitir las funciones de estimación de este
# módulo. `Pre-A1` es la banda más débil (rank 0), por delante de A1.
ESTIMATED_BANDS: tuple[str, ...] = (PRE_A1, "A1", "A2", "B1", "B2", "C1", "C2")

# Versión del modelo unificado de estimación CEFR del Student Model (snapshot
# reproducible: cada snapshot de evaluación guarda esta versión como instrumento).
# 2.1.0: recalibración pedagógica — se introduce `Pre-A1` y se endurecen los
# umbrales de vocabulario (A1 ya no se alcanza con unas decenas de palabras).
CEFR_MODEL_VERSION = "2.1.0"

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
    """Posición de una banda estimada; `"—"` (sin señal) vale -1.

    El orden incluye `Pre-A1` como banda más débil (rank 0), de modo que un
    `Pre-A1` evidenciado (p. ej. por vocabulario) limite el nivel global por
    debajo de cualquier A1..C2.
    """
    if level in ESTIMATED_BANDS:
        return ESTIMATED_BANDS.index(level)
    return -1


# Umbrales de la banda heurística de vocabulario (proxy = palabras distintas
# producidas por el alumno). Recalibrados según la evidencia pedagógica: el
# English Vocabulary Profile (Milton & Alexiou) sitúa A1 en cientos de familias de
# palabras y Cambridge/Busuu en ~90-100 h guiadas, así que "acertar un puñado de
# ítems" ya no puede leer como A1. Escala logarítmica orientativa:
# Pre-A1 < 150 · A1 150-399 · A2 400-899 · B1 900-1899 · B2 1900-2999 ·
# C1 3000-4999 · C2 >= 5000. Valores configurables (constantes) a ajustar con los
# datos reales de los perfiles.
VOCABULARY_BAND_EDGES: tuple[tuple[int, str], ...] = (
    (5000, "C2"),
    (3000, "C1"),
    (1900, "B2"),
    (900, "B1"),
    (400, "A2"),
    (150, "A1"),
)


def vocabulary_band(vocab: int) -> str:
    """Banda heurística de vocabulario según las palabras distintas producidas.

    NO es una equivalencia oficial CEFR: es un proxy de visualización. Un alumno
    por debajo del umbral mínimo de A1 queda en `Pre-A1`.
    """
    for floor, level in VOCABULARY_BAND_EDGES:
        if vocab >= floor:
            return level
    return PRE_A1


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
    "Pre-A1": (
        "Pre-beginner: primeras palabras y frases memorizadas; sin dominio "
        "consolidado aún."
    ),
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
    evidencia suficiente; si ninguna la tiene, se devuelve `Pre-A1` con confianza 0
    (un alumno sin evidencia consolidada aún no puede leerse como A1).

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
        # Sin ninguna destreza con muestras suficientes no hay nivel que sostener:
        # la lectura honesta es `Pre-A1`, no "A1 por defecto".
        level = PRE_A1

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
    # Bajo el umbral de A1 (150 palabras producidas) el foco sigue siendo ampliar
    # vocabulario básico.
    if profile.get("vocab_size", 0) < VOCABULARY_BAND_EDGES[-1][0]:
        recs.append("Amplía vocabulario: lee y describe imágenes o rutinas.")
    if not recs:
        recs.append("¡Buen trabajo! Sigue practicando conversación.")
    return recs

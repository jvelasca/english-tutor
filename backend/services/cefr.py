"""Símbolos CEFR compartidos y recomendaciones de perfil (puro, determinista).

Este módulo ya NO contiene un modelo de estimación propio: el nivel estimado y las
bandas por destreza los calcula el Student Model (`services.academy` +
`services.adaptive`), que es la única fuente de nivel de la aplicación
(Constitución pedagógica, `docs/CONSTITUCION-PEDAGOGICA.md`).

Histórico: hasta 3.2.x este módulo albergaba un modelo heurístico multi-señal
(`evaluate_cefr`) que derivaba bandas a partir de contadores crudos (p. ej.
"palabras distintas producidas → banda CEFR" con `VOCABULARY_BAND_EDGES`). Esa
interpretación **palabras → nivel** se eliminó en 3.3.0 (hallazgo H1 de
`docs/audit/H-NIVELACION-PEDAGOGICA.md`): un contador léxico es un indicador de
volumen/cobertura, nunca una banda CEFR.

Aquí solo viven: constantes compartidas (`PRE_A1`, `CEFR_LEVELS`,
`CEFR_MODEL_VERSION`), descriptores de banda, `heuristic_band` (proxy interno de
visualización para un score de destreza del Student Model) y las recomendaciones
de perfil.
"""
from __future__ import annotations

# Tramo por debajo de A1: alumnos sin evidencia consolidada aún. No tiene curso
# propio (la progresión curricular sigue siendo A1..C2), pero sí es la banda más
# baja de la escalera de competencia (ver `services.cefr_descriptors`).
PRE_A1 = "Pre-A1"

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Versión del instrumento de estimación CEFR (snapshot reproducible: cada
# snapshot de evaluación guarda esta versión como instrumento). Se conserva por
# historial aunque el modelo legacy que la originó haya sido retirado.
CEFR_MODEL_VERSION = "2.1.0"

# Umbral orientativo (palabras distintas producidas) a partir del cual se deja de
# recomendar "ampliar vocabulario" como foco principal. NO es una banda CEFR: es
# un indicador de cobertura léxica (volumen), no una demostración de nivel.
VOCAB_EXPANSION_HINT_WORDS = 150


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


# Fronteras de media banda del eje continuo CEFR (A1 = 1.0 … C2 = 6.0). **Única
# fuente del corte** (AE-06, V3.72): antes estaba triplicado en
# `adaptive.numeric_to_level`, `academy.theta_to_level` y `heuristic_band`, con la
# propiedad —correcta pero frágil— de coincidir en toda la rejilla.
BAND_BOUNDARIES: tuple[float, ...] = (1.5, 2.5, 3.5, 4.5, 5.5)


def numeric_for_score(score: float) -> float:
    """Nivel continuo equivalente a un score de dominio 0..1 (0.0→A1 … 1.0→C2)."""
    return 1.0 + 5.0 * score


def score_for_numeric(numeric: float) -> float:
    """Inversa de `numeric_for_score`, acotada a 0..1."""
    return max(0.0, min(1.0, (numeric - 1.0) / 5.0))


def level_for_numeric(numeric: float) -> str:
    """Etiqueta CEFR **discreta** (A1..C2) de un nivel continuo, por media banda.

    Decisión declarada (AE-06): los estimadores de **etiqueta** no emiten
    sub-bandas `+` —afirmarían más precisión de la que la evidencia sostiene— ni
    `Pre-A1` —que sí es una banda con emisor propio cuando no hay evidencia
    (`adaptive.estimated_level`) o como **posición** en la escalera de
    descriptores (`cefr_descriptors.band_for_numeric`)—.
    """
    for boundary, level in zip(BAND_BOUNDARIES, CEFR_LEVELS, strict=False):
        if numeric < boundary:
            return level
    return CEFR_LEVELS[-1]


def heuristic_band(score: float | None) -> str:
    """Banda CEFR-alineada **heurística** para un score de dominio continuo (0..1).

    Proxy interno de visualización (NO equivalencia oficial CEFR). Usa las mismas
    fronteras de media banda que el resto del sistema (`level_for_numeric`), de
    modo que un score de destreza 0..1 mapea a A1..C2 de forma monotónica:
    0.0→A1 … 1.0→C2. `None` (sin observación) devuelve "—".
    """
    if score is None:
        return "—"
    return level_for_numeric(numeric_for_score(score))


def recommendations(profile: dict) -> list[str]:
    """Genera recomendaciones en español a partir del perfil agregado."""
    recs: list[str] = []
    errors = profile.get("recurring_errors", [])
    if errors:
        recs.append(f"Refuerza: {errors[0]['message']} (error recurrente).")
    pron = profile.get("pronunciation_avg")
    if pron is not None and pron < 70:
        recs.append("Practica pronunciación con la tarjeta de pronunciación.")
    # Indicador de cobertura léxica (volumen de palabras distintas producidas),
    # no una banda CEFR: por debajo del umbral orientativo el foco sigue siendo
    # ampliar vocabulario básico.
    if profile.get("vocab_size", 0) < VOCAB_EXPANSION_HINT_WORDS:
        recs.append("Amplía vocabulario: lee y describe imágenes o rutinas.")
    if not recs:
        recs.append("¡Buen trabajo! Sigue practicando conversación.")
    return recs

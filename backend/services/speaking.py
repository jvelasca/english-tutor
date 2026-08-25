"""Scorer determinista de speaking (rubric CEFR de 6 dimensiones).

Reutiliza los evaluadores deterministas existentes (phonetics, fluency, grammar,
vocabulary) para producir un score por criterio y un overall ponderado. Sigue la
premisa del proyecto: la evidencia la extrae el LLM, pero el score lo calcula SIEMPRE
un scorer determinista (nunca "el LLM te pone B1").
"""
from __future__ import annotations

import re

from services.curriculum import RUBRIC_VERSION
from services.fluency import compute_fluency
from services.grammar import find_errors
from services.phonetics import composite_score

# Dimensiones del rubric de speaking (alineadas con CEFR).
SPEAKING_CRITERIA: tuple[str, ...] = (
    "task_achievement",
    "grammatical_control",
    "lexical_resource",
    "fluency",
    "pronunciation",
    "coherence",
)

# Pesos por defecto (suman 1). El overall es la media ponderada de los criterios.
CRITERION_WEIGHTS: dict[str, float] = {
    "task_achievement": 0.25,
    "grammatical_control": 0.20,
    "lexical_resource": 0.20,
    "fluency": 0.15,
    "pronunciation": 0.10,
    "coherence": 0.10,
}

# Referencia de fluidez: 120 palabras por minuto ≈ hablante fluido.
_FLUENT_WPM = 120.0

# Referencia léxica: 5 palabras de contenido ≈ vocabulario adecuado.
_LEXICAL_REFERENCE = 5.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    """Tokeniza en minúsculas, sin puntuación, conservando orden y repeticiones.

    No se apoya en vocabulary.extract_words a propósito: aquella devuelve palabras
    únicas ordenadas alfabéticamente y filtra stopwords, lo que anularía la
    semántica "con repetición/orden" de task_achievement. Aquí se conserva el flujo
    completo de tokens para que lexical (set) y task (lista) midan cosas distintas.
    """
    return re.findall(r"[a-z0-9']+", text.lower())


def _fluency_score(heard: str, duration_seconds: float | None) -> float:
    info = compute_fluency(heard, duration_seconds)
    wpm = info["wpm"]
    if wpm is None:
        return 0.5
    return round(_clamp(wpm / _FLUENT_WPM), 3)


def score_speaking(
    heard: str,
    expected: str,
    duration_seconds: float | None = None,
) -> dict:
    """Puntúa una producción oral frente a una frase/tarea esperada.

    Devuelve un dict con `heard`, `expected`, `criteria` (dict criterion → score
    0..1), y `overall` (media ponderada 0..1, redondeada a 3 decimales).
    """
    heard_tokens = _tokens(heard)
    expected_tokens = _tokens(expected)

    # pronunciation: similitud palabra/fonética con lo esperado (0-100 → 0-1).
    pronunciation = round(composite_score(expected, heard)["score"] / 100, 3)

    # fluency: wpm frente a 120 wpm ≈ fluido; 0.5 si no se puede calcular.
    fluency = _fluency_score(heard, duration_seconds)

    # grammatical_control: 0 errores = 1.0; cada error resta 0.25; suelo 0.0.
    grammatical_control = round(
        max(0.0, 1.0 - 0.25 * len(find_errors(heard))), 3
    )

    # lexical_resource: cobertura del léxico esperado (tokens únicos, sin orden).
    if expected_tokens:
        lexical_resource = round(
            _clamp(
                len(set(heard_tokens) & set(expected_tokens))
                / len(set(expected_tokens))
            ),
            3,
        )
    else:
        lexical_resource = 1.0

    # task_achievement: cobertura de tokens clave esperados (con repetición/orden).
    if expected_tokens:
        task_achievement = round(
            _clamp(
                len([t for t in expected_tokens if t in heard_tokens])
                / len(expected_tokens)
            ),
            3,
        )
    else:
        task_achievement = 1.0

    # coherence: longitud producida comparable a la esperada.
    coherence = round(_clamp(len(heard_tokens) / max(1, len(expected_tokens))), 3)

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in SPEAKING_CRITERIA), 3
    )

    return {
        "heard": heard,
        "expected": expected,
        "criteria": criteria,
        "overall": overall,
    }


def scores_from_evidence(
    evidence: dict,
    heard: str,
    duration_seconds: float | None = None,
) -> dict:
    """Convierte evidencia extraída por el LLM en los 6 criterios + overall.

    `evidence` es el dict normalizado de `speaking_llm.parse_speaking_evidence`.
    La pronunciación no es evaluable sin referencia de audio en este flujo, así que
    se fija en 0.5 (neutro/desconocido). La fluidez se calcula por WPM si hay
    duración; si no, 0.5. Devuelve {"criteria": {...}, "overall": float}."""
    task_achievement = 1.0 if evidence["task_achieved"] else 0.0
    grammatical_control = round(
        _clamp(1.0 - 0.25 * evidence["grammar_errors"]), 3
    )
    lexical_resource = round(
        _clamp(len(set(evidence["lexical_tokens"])) / _LEXICAL_REFERENCE), 3
    )
    coherence = round(float(evidence["coherence"]), 3)
    fluency = _fluency_score(heard, duration_seconds)
    pronunciation = 0.5

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in SPEAKING_CRITERIA), 3
    )

    return {
        "criteria": criteria,
        "overall": overall,
    }


def evidence_from_speaking(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
) -> list[dict]:
    """Convierte el resultado de score_speaking en registros de evidencia.

    Una fila por criterio del rubric (item_id = criterio) más una fila 'overall'.
    Todas con source='speaking', item_type='speaking', difficulty=1. El instrumento
    de medida es la rúbrica, versionada en `assessment_version`."""
    records = [
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "speaking",
            "item_id": criterion,
            "item_type": "speaking",
            "difficulty": 1,
            "source": "speaking",
            "result": float(result["criteria"][criterion]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
        for criterion in SPEAKING_CRITERIA
    ]
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "speaking",
            "item_id": "overall",
            "item_type": "speaking",
            "difficulty": 1,
            "source": "speaking",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
    )
    return records

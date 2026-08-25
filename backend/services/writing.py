"""Scorer determinista de writing (rubric CEFR de 6 dimensiones).

Reutiliza el evaluador de gramática determinista (find_errors) para producir un
score por criterio y un overall ponderado. Sigue la premisa del proyecto: la
evidencia la extrae el LLM, pero el score lo calcula SIEMPRE un scorer
determinista (nunca "el LLM te pone B1").
"""
from __future__ import annotations

import re

from services.curriculum import RUBRIC_VERSION
from services.grammar import find_errors

# Dimensiones del rubric de writing (alineadas con CEFR).
WRITING_CRITERIA: tuple[str, ...] = (
    "task_completion",
    "grammatical_accuracy",
    "lexical_resource",
    "organization",
    "coherence",
    "register",
)

# Pesos por defecto (suman 1).
CRITERION_WEIGHTS: dict[str, float] = {
    "task_completion": 0.25,
    "grammatical_accuracy": 0.20,
    "lexical_resource": 0.20,
    "organization": 0.15,
    "coherence": 0.10,
    "register": 0.10,
}

# Referencia léxica: 5 palabras de contenido ≈ vocabulario adecuado.
_LEXICAL_REFERENCE = 5.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    """Tokeniza en minúsculas, sin puntuación, conservando orden y repeticiones."""
    return re.findall(r"[a-z0-9']+", text.lower())


def _sentences(text: str) -> int:
    """Número de frases (grupos de puntuación final). 1 si hay texto sin puntuación."""
    return len(re.findall(r"[.!?]+", text)) or (1 if text.strip() else 0)


def score_writing(text: str, expected: str) -> dict:
    """Puntúa una producción escrita frente a un texto esperado (escritura controlada).

    Devuelve un dict con `text`, `expected`, `criteria` (dict criterion → score
    0..1), y `overall` (media ponderada 0..1, redondeada a 3 decimales).
    """
    text_tokens = _tokens(text)
    expected_tokens = _tokens(expected)

    grammatical_accuracy = round(
        max(0.0, 1.0 - 0.25 * len(find_errors(text))), 3
    )

    if expected_tokens:
        lexical_resource = round(
            _clamp(
                len(set(text_tokens) & set(expected_tokens))
                / len(set(expected_tokens))
            ),
            3,
        )
        task_completion = round(
            _clamp(
                len([t for t in expected_tokens if t in text_tokens])
                / len(expected_tokens)
            ),
            3,
        )
        coherence = round(_clamp(len(text_tokens) / max(1, len(expected_tokens))), 3)
        organization = round(
            _clamp(_sentences(text) / max(1, _sentences(expected))), 3
        )
    else:
        lexical_resource = 1.0
        task_completion = 1.0
        coherence = 1.0
        organization = 1.0

    # Sin contexto de tarea no hay señal determinista de registro: neutro.
    register = 0.5

    criteria = {
        "task_completion": task_completion,
        "grammatical_accuracy": grammatical_accuracy,
        "lexical_resource": lexical_resource,
        "organization": organization,
        "coherence": coherence,
        "register": register,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in WRITING_CRITERIA), 3
    )

    return {
        "text": text,
        "expected": expected,
        "criteria": criteria,
        "overall": overall,
    }


def scores_from_evidence(evidence: dict) -> dict:
    """Convierte evidencia extraída por el LLM en los 6 criterios + overall.

    `evidence` es el dict normalizado de `writing_llm.parse_writing_evidence`.
    Devuelve {"criteria": {...}, "overall": float}."""
    task_completion = 1.0 if evidence["task_completed"] else 0.0
    grammatical_accuracy = round(
        _clamp(1.0 - 0.25 * evidence["grammar_errors"]), 3
    )
    lexical_resource = round(
        _clamp(len(set(evidence["lexical_tokens"])) / _LEXICAL_REFERENCE), 3
    )
    organization = round(_clamp(float(evidence["organization"])), 3)
    coherence = round(_clamp(float(evidence["coherence"])), 3)
    register = round(_clamp(float(evidence["register"])), 3)

    criteria = {
        "task_completion": task_completion,
        "grammatical_accuracy": grammatical_accuracy,
        "lexical_resource": lexical_resource,
        "organization": organization,
        "coherence": coherence,
        "register": register,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in WRITING_CRITERIA), 3
    )

    return {
        "criteria": criteria,
        "overall": overall,
    }


def evidence_from_writing(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
) -> list[dict]:
    """Convierte el resultado de score_writing en registros de evidencia.

    Una fila por criterio del rubric (item_id = criterio) más una fila 'overall'.
    Todas con source='writing', item_type='writing', difficulty=1. El instrumento
    de medida es la rúbrica, versionada en `assessment_version`."""
    records = [
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "writing",
            "item_id": criterion,
            "item_type": "writing",
            "difficulty": 1,
            "source": "writing",
            "result": float(result["criteria"][criterion]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
        for criterion in WRITING_CRITERIA
    ]
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "writing",
            "item_id": "overall",
            "item_type": "writing",
            "difficulty": 1,
            "source": "writing",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
    )
    return records

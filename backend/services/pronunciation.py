"""Evaluación de pronunciación: compara texto esperado con el transcrito (puro,
testable)."""
from __future__ import annotations

import re

from services.curriculum import RUBRIC_VERSION
from services.phonetics import composite_score

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
    """Devuelve score/level/ok + word_accuracy + phonetic_score +
    phoneme_accuracy_proxy + prosody_proxy + breakdown + phoneme_breakdown.

    Las señales de fonemas y prosodia son un proxy sobre transcripción, marcado
    con `pronunciation_source: "transcript"`."""
    comp = composite_score(expected, heard)
    score = comp["score"]
    return {
        "expected": expected.strip(),
        "heard": heard.strip(),
        "score": score,
        "level": _level(score),
        "ok": score >= PASS_THRESHOLD,
        "word_accuracy": comp["word_accuracy"],
        "phonetic_score": comp["phonetic_score"],
        "phoneme_accuracy_proxy": comp["phoneme_accuracy_proxy"],
        "prosody_proxy": comp["prosody_proxy"],
        "pronunciation_source": "transcript",
        "breakdown": comp["breakdown"],
        "phoneme_breakdown": comp["phoneme_breakdown"],
    }


# Criterios del rubric de pronunciación (read-aloud) y sus pesos (suman 1).
PRONUNCIATION_CRITERIA: tuple[str, ...] = (
    "phoneme_accuracy_proxy",
    "word_accuracy",
    "phonetic_similarity",
    "prosody_proxy",
)

PRONUNCIATION_WEIGHTS: dict[str, float] = {
    "phoneme_accuracy_proxy": 0.35,
    "word_accuracy": 0.35,
    "phonetic_similarity": 0.15,
    "prosody_proxy": 0.15,
}


def score_pronunciation_cefr(expected: str, heard: str) -> dict:
    """Score de pronunciación 0..1 por criterio y overall ponderado (read-aloud).

    Reutiliza `composite_score` y normaliza sus componentes a 0..1:
    phoneme_accuracy_proxy, word_accuracy, phonetic_similarity (phonetic_score) y
    prosody_proxy. Devuelve {"expected", "heard", "criteria", "overall"} con
    overall redondeado a 3."""
    comp = composite_score(expected, heard)
    criteria = {
        "phoneme_accuracy_proxy": comp["phoneme_accuracy_proxy"] / 100,
        "word_accuracy": comp["word_accuracy"] / 100,
        "phonetic_similarity": comp["phonetic_score"] / 100,
        "prosody_proxy": comp["prosody_proxy"] / 100,
    }
    overall = round(
        sum(PRONUNCIATION_WEIGHTS[c] * criteria[c] for c in PRONUNCIATION_CRITERIA), 3
    )
    return {
        "expected": expected,
        "heard": heard,
        "criteria": criteria,
        "overall": overall,
    }


def evidence_from_pronunciation(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
    evidence_kind: str = "familiar",
) -> list[dict]:
    """Convierte el resultado en registros de evidencia (una fila por criterio
    + overall).

    Todas con source='pronunciation', skill='pronunciation', item_type='pronunciation',
    difficulty=1. El instrumento de medida es la rúbrica, versionada en
    `assessment_version`."""
    records = [
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "pronunciation",
            "item_id": criterion,
            "item_type": "pronunciation",
            "difficulty": 1,
            "source": "pronunciation",
            "result": float(result["criteria"][criterion]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
            "evidence_kind": evidence_kind,
        }
        for criterion in PRONUNCIATION_CRITERIA
    ]
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "pronunciation",
            "item_id": "overall",
            "item_type": "pronunciation",
            "difficulty": 1,
            "source": "pronunciation",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
            "evidence_kind": evidence_kind,
        }
    )
    return records

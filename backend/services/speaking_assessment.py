"""Speaking Assessment 1.0: instrumento versionado + motor determinista.

El instrumento (4 partes fijas: interview, individual task, interaction y
follow-up) vive como JSON versionado en `backend/curriculum/speaking_assessment.json`
(mismo patrón que el placement), y se carga con un modelo Pydantic. El motor es
puro: recibe las filas de evidencia de UNA sesión y reutiliza el scorer
determinista de speaking (`services.speaking.speaking_level` y
`speaking_diagnostic`) para producir el nivel CEFR, el score global, la confianza
y el resumen por criterio. El LLM no puntúa: solo extrae evidencia.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from services import speaking as speaking_svc
from services.curriculum import SPEAKING_ASSESSMENT_VERSION

SPEAKING_ASSESSMENT_PATH = (
    Path(__file__).resolve().parent.parent / "curriculum" / "speaking_assessment.json"
)


class SpeakingAssessmentPart(BaseModel):
    """Una parte del instrumento: qué tarea se pide, con qué dificultad y duración.

    `difficulty` es un campo derivado del `difficulty_vector` (media redondeada,
    clamp a 1..6), igual que `speaking.SpeakingTaskProfile`. `task_type` debe
    pertenecer a `speaking.TASK_TYPES` para elegir los pesos de rúbrica correctos.
    """

    id: str
    part_index: int
    title: str
    task_type: str
    cefr_target: str = "B1"
    duration_target: float = 60.0
    prompt: str
    difficulty_vector: dict[str, int] = Field(default_factory=dict)

    @computed_field
    @property
    def difficulty(self) -> int:
        return speaking_svc.difficulty_from_vector(self.difficulty_vector)


class SpeakingAssessmentInstrument(BaseModel):
    """Instrumento completo de Speaking Assessment (contenido estático versionado)."""

    id: str
    title: str
    description: str = ""
    version: str = SPEAKING_ASSESSMENT_VERSION
    parts: list[SpeakingAssessmentPart]


def load_speaking_assessment() -> SpeakingAssessmentInstrument:
    """Carga y valida el instrumento de Speaking Assessment desde JSON."""
    with SPEAKING_ASSESSMENT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return SpeakingAssessmentInstrument.model_validate(data)


def assessment_parts() -> list[dict]:
    """Devuelve las 4 partes del instrumento como dicts, ordenadas por `part_index`."""
    instrument = load_speaking_assessment()
    ordered = sorted(instrument.parts, key=lambda p: p.part_index)
    return [p.model_dump() for p in ordered]


def aggregate_assessment(evidence_rows: list[dict]) -> dict:
    """Agrega la evidencia de UNA sesión de Speaking Assessment en el resultado final.

    Reutiliza el scorer determinista sin duplicar cálculos:
    - `speaking.speaking_level` produce `level`/`numeric`/`score`/`confidence`/
      `attempts` a partir de las filas `item_id == "overall"`.
    - `speaking.speaking_diagnostic` produce el resumen por criterio (7 criterios de
      la rúbrica común) con `attempts`/`mean`/`recent_score`/`confidence`/
      `stability`/`review_due`, más `weak` y `recommendation`.

    Sin evidencia devuelve `level`/`numeric`/`score` None y `confidence` 0.0 (un
    criterio no observado no se inventa). Determinista, sin LLM ni red.
    """
    level = speaking_svc.speaking_level(evidence_rows)
    diagnostic = speaking_svc.speaking_diagnostic(evidence_rows)
    return {
        "level": level["level"],
        "numeric": level["numeric"],
        "score": level["score"],
        "confidence": level["confidence"],
        "attempts": level["attempts"],
        "criteria": diagnostic["criteria"],
        "weak": diagnostic["weak"],
        "recommendation": diagnostic["recommendation"],
        "rubric_version": diagnostic["rubric_version"],
        "assessment_version": SPEAKING_ASSESSMENT_VERSION,
    }

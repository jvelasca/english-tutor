"""Esquemas Pydantic de eventos de aprendizaje."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LearningEventType = Literal[
    "message", "exercise", "correction", "pronunciation", "conversation"
]


class LearningEventCreate(BaseModel):
    type: LearningEventType
    detail: str = Field(default="", max_length=500)


class LearningEvent(BaseModel):
    id: int
    user_id: str
    type: LearningEventType
    detail: str
    created_at: str
    # V3.35: rol del evento (evidence/telemetry/informative) derivado por
    # `services.evidence`. Default "" para filas legacy previas a la migración.
    event_role: str = ""


ReviewActivity = Literal["recognition", "recall", "sentence"]


class ReviewQueueItem(BaseModel):
    """Ítem de la cola de repaso léxico (V3.35, Longitudinal Learning Evidence).

    Una carta FSRS `lexicon` vencida, con la actividad que el motor recomienda
    según el hueco de competencia del ítem (`activity`) y la urgencia del
    scheduler (`retrievability`/`stability`). Es señal, nunca puerta (D5/E3), y
    nunca incluye el cue ni la forma esperada.
    """

    word: str
    lexical_unit: str = ""
    cefr: str = ""
    kind: str = "word"
    due_at: str = ""
    state: str = "new"
    stability: float = 0.0
    retrievability: float | None = None
    elapsed_days: float | None = None
    activity: ReviewActivity
    reason: str = ""
    competence: dict | None = None
    # V3.35: evidencia longitudinal (`attempts`/`successes`/`days`/`intervals`).
    evidence: dict | None = None


class ReviewQueueOut(BaseModel):
    """Cola de repaso del léxico: `due_count` + ítems ordenados por urgencia."""

    due_count: int
    items: list[ReviewQueueItem] = Field(default_factory=list)
    fsrs_version: str = ""

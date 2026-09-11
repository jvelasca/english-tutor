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


ReviewActivity = Literal[
    "recognition", "recall", "sentence", "write", "transfer"
]


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
    # V3.37 (cues graduados): peldaño recomendado para `recall` (nombre del
    # peldaño, NUNCA el cue) y si el ítem acumula éxito independiente y
    # espaciado (`services.evidence.is_automatic`). Aditivos.
    recommended_cue: str = ""
    automatic: bool = False
    # V3.38 (planner / Optimal Next Task): prioridad combinada 0..1, señales que
    # la producen (explicables), explicación legible y modalidades en las que el
    # ítem ya es automático (P1-03). Aditivos.
    priority: float = 0.0
    signals: dict | None = None
    why: str = ""
    automatic_skills: list[str] = Field(default_factory=list)
    # V3.39 (Fase 3, motor de tarea óptima): modalidad con mayor prioridad y la
    # DECISIÓN de tarea (`{skill, activity, reason, support_level}`). Aditivos:
    # `activity`/`reason` conservan su semántica.
    limiting_skill: str = ""
    # V3.51 (Task/Skill semantics): vector completo de prioridad por modalidad
    # (aditivo). `limiting_skill` es su argmax; el vector conserva la
    # información que el argmax descartaba.
    skill_priorities: dict[str, float] = Field(default_factory=dict)
    task: dict | None = None
    competence: dict | None = None
    # V3.40 (Fase 4, gobierno por unidad léxica): formas superficiales de la
    # unidad y transferencia contextual demostrada (éxito en contextos distintos).
    # Aditivos: el ítem sigue siendo UNA forma superficial (lo que práctica el
    # drill), pero su estado se lee también a nivel de unidad.
    unit_surfaces: list[str] = Field(default_factory=list)
    transfer: bool = False
    success_contexts: list[str] = Field(default_factory=list)
    # V3.43 (P1-03/P1-04): estado formalizado de transferencia (sustituto gradual
    # del booleano `transfer`) y diversidad contextual real de los contextos con
    # éxito limpio. Aditivos.
    transfer_state: str = "not_ready"
    context_diversity: dict | None = None
    # V3.49 (Transfer Evidence 3.0): confianza EXPLICABLE del eje
    # (`{score, level, sample, drivers, recency_days}`). Aditivo.
    transfer_confidence: dict | None = None
    # V3.35: evidencia longitudinal (`attempts`/`successes`/`days`/`intervals`).
    evidence: dict | None = None


class ReviewQueueOut(BaseModel):
    """Cola de repaso del léxico: `due_count` + ítems ordenados por urgencia.

    V3.40 añade `units` (aditivo): la evidencia agregada por `lexical_unit`
    (`services.lexicon.unit_evidence`), para que el estado pedagógico esté
    gobernado por la unidad (go/went/gone/going) y no solo por la forma.
    """

    due_count: int
    items: list[ReviewQueueItem] = Field(default_factory=list)
    fsrs_version: str = ""
    units: list[dict] = Field(default_factory=list)

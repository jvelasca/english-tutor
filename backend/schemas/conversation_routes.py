"""Esquemas Pydantic de las rutas de conversation (V3.10)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationDialogue(BaseModel):
    """Un mini-diálogo guiado servido para practicar.

    El diálogo plantea un contexto, el rol del alumno y el rol del tutor (que
    interpreta al otro hablante siguiendo la situación), una `opening_line` con
    la que arranca la conversación y las metas comunicativas que el alumno debe
    cumplir conversando varios turnos.
    """

    id: str
    level: str
    topic: str = ""
    context: str = ""
    student_role: str = ""
    tutor_role: str = ""
    opening_line: str = ""
    communicative_goals: list[str] = Field(default_factory=list)


class ConversationAttemptResponse(BaseModel):
    """Resultado de una conversación guiada terminada (V3.10).

    `overall` (0..1) es la media ponderada de `criteria` sobre los criterios
    observados (extracción LLM de evidencia sobre el transcripto + señal objetiva
    de interacción); `passed = overall >= 0.6`. `heard` es el transcripto del
    alumno (sus turnos) que se evaluó.
    """

    dialogue_id: str
    level: str
    opening_line: str
    heard: str = ""
    overall: float
    passed: bool
    criteria: dict = Field(default_factory=dict)
    observed: dict = Field(default_factory=dict)
    interaction_quality: dict = Field(default_factory=dict)
    topic: str = ""
    communicative_goals: list[str] = Field(default_factory=list)


class ConversationGate(BaseModel):
    """Puerta de ruta de conversation: qué exige la evidencia para declarar la
    ruta superada (práctica) y qué valores alcanza hoy.

    `passed` solo es cierto si `blockers` está vacío. Se calcula SIEMPRE sobre el
    banco curado oficial."""

    passed: bool = False
    total: int = 0
    mastered: int = 0
    coverage_pct: float = 0.0
    coverage_required_pct: float = 80.0
    accuracy: float | None = None
    accuracy_required: float = 70.0
    topics: int = 0
    topics_required: int = 0
    checkpoint: int = 0
    checkpoint_required: int = 0
    blockers: list[str] = Field(default_factory=list)


class ConversationLevelOut(BaseModel):
    """Progreso de una ruta de conversation para el mapa de niveles.

    `state` ∈ {not_started, developing, functional}: la ruta es práctica y nunca
    informa `demonstrated` (demostrar exige Speaking Assessment + evidencia)."""

    level: str
    total: int
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    gate: ConversationGate | None = None
    state: str = "not_started"


class ConversationItemOut(BaseModel):
    """Un diálogo del banco de una ruta con su estado para un usuario.

    `opening_line` es la línea con la que arranca la conversación y que
    identifica el diálogo en el panel."""

    dialogue_id: str
    level: str
    opening_line: str = ""
    topic: str = ""
    attempts: int = 0
    state: str


class ConversationLevelItemsOut(BaseModel):
    """Estado por diálogo de un nivel + resumen de contadores."""

    level: str
    total: int
    mastered: int
    failed: int
    unseen: int
    completed: bool
    items: list[ConversationItemOut]
    gate: ConversationGate | None = None


class ConversationStats(BaseModel):
    attempts: int
    passed: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[ConversationLevelOut]


class ConversationAttemptRequest(BaseModel):
    """Cuerpo del POST que entrega una conversación guiada para evaluarla."""

    dialogue_id: str
    conversation_id: str

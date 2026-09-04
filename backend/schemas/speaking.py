"""Esquemas Pydantic de las rutas de speaking (V3.8)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SpeakingPhrase(BaseModel):
    """Una tarjeta de micro-conversación servida para practicar.

    La tarjeta plantea una situación (`setup`) y el rol del alumno (`you`); el
    interlocutor habla (`app_line`, con voz modelo si `audio_ready`) y el alumno
    responde hablando con sus palabras. `model_response` NO viaja en la pregunta:
    la respuesta modelo se revela tras la evaluación, en el intento.
    """

    id: str
    level: str
    setup: str = ""
    you: str = ""
    app_line: str = ""
    topic: str = ""
    difficulty: int = 1
    difficulty_vector: dict[str, int] = Field(default_factory=dict)
    audio_ready: bool = False


class SpeakingAttemptResponse(BaseModel):
    """Resultado de un intento de respuesta abierta (V3.8).

    `overall` (0..1) es la media ponderada de `criteria` sobre los criterios
    observados (extracción LLM + scorer determinista); `passed = overall >= 0.6`.
    Incluye `model_response`, la respuesta modelo de la tarjeta que se revela
    después de que el alumno haya hablado.
    """

    phrase_id: str
    level: str
    app_line: str
    heard: str
    model_response: str = ""
    overall: float
    passed: bool
    criteria: dict = Field(default_factory=dict)
    observed: dict = Field(default_factory=dict)
    topic: str = ""
    difficulty: int = 1


class SpeakingGate(BaseModel):
    """Puerta de ruta de speaking: qué exige la evidencia para declarar la ruta
    superada (práctica) y qué valores alcanza hoy.

    `passed` solo es cierto si `blockers` está vacío. Se calcula SIEMPRE sobre el
    banco curado oficial; la práctica extra generada amplía el anillo pero no
    certifica."""

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


class SpeakingLevelOut(BaseModel):
    """Progreso de una ruta de speaking para el mapa de niveles.

    `total`/`mastered` incluyen las tarjetas extra activadas; `base_total`/
    `base_mastered` son el banco curado oficial (el único que decide la puerta).
    `state` ∈ {not_started, developing, functional}: la ruta es práctica y nunca
    informa `demonstrated` (demostrar exige Speaking Assessment + evidencia)."""

    level: str
    total: int
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    gate: SpeakingGate | None = None
    state: str = "not_started"
    base_total: int = 0
    base_mastered: int = 0
    extras: int = 0
    extras_mastered: int = 0


class SpeakingItemOut(BaseModel):
    """Una tarjeta del pool de una ruta con su estado para un usuario.

    `app_line` es la línea del interlocutor que identifica el intercambio."""

    phrase_id: str
    level: str
    app_line: str = ""
    topic: str = ""
    difficulty: int = 1
    attempts: int = 0
    state: str
    # "base" = banco curado oficial; "generated" = práctica extra generada.
    source: str = "base"


class SpeakingLevelItemsOut(BaseModel):
    """Estado por tarjeta de un nivel + resumen de contadores."""

    level: str
    total: int
    mastered: int
    failed: int
    unseen: int
    completed: bool
    items: list[SpeakingItemOut]
    gate: SpeakingGate | None = None


class SpeakingStats(BaseModel):
    attempts: int
    passed: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[SpeakingLevelOut]


class SpeakingAddExtrasRequest(BaseModel):
    """Cuerpo del POST que pide añadir `count` tarjetas extra a una ruta."""

    count: int = Field(default=10, ge=1, le=100)


class SpeakingExtrasJobOut(BaseModel):
    """Estado de un trabajo de generación en segundo plano."""

    job_id: str
    status: str = "running"
    level: str = ""
    requested: int = 0
    added: list[str] = Field(default_factory=list)
    error: str = ""


class SpeakingRouteExtrasOut(BaseModel):
    """Tarjetas extra activadas en una ruta."""

    level: str
    total: int = 0
    phrase_ids: list[str] = Field(default_factory=list)

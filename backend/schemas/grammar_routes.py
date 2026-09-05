"""Esquemas Pydantic de las rutas de grammar (V3.12).

Los ítems son checks MC del currículo (`objectives[].checks` con skill
"grammar"), sin corpus propio. La pregunta servida NUNCA incluye
`correct_index` (sería hacer trampa: el alumno debe elegir sin conocer la
respuesta); la respuesta del POST /attempt sí la revela para el feedback.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GrammarQuestion(BaseModel):
    """Un check MC servido para practicar (sin la respuesta correcta).

    `prompt` + `options[]` son la pregunta; `topic` agrupa por módulo del
    currículo. `check_id` identifica el check en el POST /attempt.
    """

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    options: list[str] = Field(default_factory=list)


class GrammarAttemptResponse(BaseModel):
    """Resultado determinista de un intento MC (V3.12).

    `passed = selected_index == correct_index`. Tras responder se revela
    `correct_index` y las opciones para que el alumno vea la respuesta correcta
    si falló. `score` es 100.0 (acierto) o 0.0 (fallo).
    """

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    options: list[str] = Field(default_factory=list)
    correct_index: int = -1
    selected_index: int = -1
    passed: bool
    score: float


class GrammarAttemptRequest(BaseModel):
    """Cuerpo del POST /attempt: la opción elegida para un check."""

    check_id: str
    selected_index: int


class GrammarGate(BaseModel):
    """Puerta de ruta de grammar: qué exige la evidencia para declarar la
    ruta superada (práctica) y qué valores alcanza hoy.

    `passed` solo es cierto si `blockers` está vacío. `short_bank` marca los
    bancos cortos (< 12 ítems, p. ej. B2 = 8 o C2 = 4), cuya puerta adapta el
    checkpoint (nota honesta)."""

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
    short_bank: bool = False
    blockers: list[str] = Field(default_factory=list)


class GrammarLevelOut(BaseModel):
    """Progreso de una ruta de grammar para el mapa de niveles.

    `state` ∈ {not_started, developing, functional}: la ruta es práctica y nunca
    informa `demonstrated` (demostrar exige examen/escalera del curso + evidencia)."""

    level: str
    total: int
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    gate: GrammarGate | None = None
    state: str = "not_started"


class GrammarItemOut(BaseModel):
    """Un check del banco de una ruta con su estado para un usuario.

    `prompt` es la pregunta que identifica el check en el panel."""

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    attempts: int = 0
    state: str


class GrammarLevelItemsOut(BaseModel):
    """Estado por check de un nivel + resumen de contadores."""

    level: str
    total: int
    mastered: int
    failed: int
    unseen: int
    completed: bool
    items: list[GrammarItemOut]
    gate: GrammarGate | None = None


class GrammarStats(BaseModel):
    attempts: int
    passed: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[GrammarLevelOut]

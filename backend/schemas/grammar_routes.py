"""Esquemas Pydantic de las rutas de grammar (V3.12, P1 V3.13).

Los ítems son checks deterministas del currículo: MC de grammar
(`objectives[].checks` con skill "grammar") y, desde V3.13 P1, producción
controlada (`production_checks`, el alumno escribe y la corrección es por
normalización determinista). La pregunta servida NUNCA incluye la respuesta
correcta (`correct_index` para MC, `accepted_answers` para producción — sería
hacer trampa); la respuesta del POST /attempt sí la revela para el feedback.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GrammarQuestion(BaseModel):
    """Un ítem servido para practicar (sin la respuesta correcta).

    `type` distingue el formato:
    - "mcq": `prompt` + `options[]`, el alumno elige una opción;
    - "controlled_production": `prompt` con hueco y sin opciones, el alumno
      escribe la respuesta (`accepted_answers` se oculta hasta el POST).

    `topic` agrupa por módulo del currículo; `check_id` identifica el ítem en el
    POST /attempt.
    """

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    type: str = "mcq"
    options: list[str] = Field(default_factory=list)


class GrammarAttemptResponse(BaseModel):
    """Resultado determinista de un intento (V3.12).

    `passed` es el acierto: MC (`selected_index == correct_index`) o producción
    controlada (`typed_answer` coincide por normalización con `accepted_answers`
    de las que, en producción, se muestran en `expected_answers` para el
    feedback). `score` es 100.0 (acierto) o 0.0 (fallo)."""

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    type: str = "mcq"
    options: list[str] = Field(default_factory=list)
    correct_index: int = -1
    selected_index: int = -1
    typed_answer: str = ""
    expected_answers: list[str] = Field(default_factory=list)
    passed: bool
    score: float


class GrammarAttemptRequest(BaseModel):
    """Cuerpo del POST /attempt: la respuesta elegida o escrita para un ítem.

    MC envía `selected_index`; producción controlada envía `typed_answer`. El
    servidor valida contra el tipo del ítem que sirvió `check_id`."""

    check_id: str
    selected_index: int = -1
    typed_answer: str = ""


class GrammarGate(BaseModel):
    """Puerta de ruta de grammar: qué exige la evidencia para declarar la
    ruta superada (práctica) y qué valores alcanza hoy.

    `passed` solo es cierto si `blockers` está vacío. `short_bank` marca los
    bancos cortos (menos de QUIZ_SHORT_BANK ítems) cuya puerta adapta el
    checkpoint (nota honesta: dominar un banco diminuto lee evidence depth
    LOW)."""

    passed: bool = False
    total: int = 0
    bank_size: int = 0
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
    practice_depth: str = "low"
    blockers: list[str] = Field(default_factory=list)


class GrammarLevelOut(BaseModel):
    """Progreso de una ruta de grammar para el mapa de niveles.

    `state` ∈ {not_started, developing, functional}: la ruta es práctica y nunca
    informa `demonstrated` (demostrar exige examen/escalera del curso + evidencia).
    `bank_size` y `evidence_depth` exponen el claim honesto de V3.13: un banco
    corto (menos de QUIZ_SHORT_BANK ítems) solo lee "practice coverage ·
    evidence depth LOW" aunque la puerta pase."""

    level: str
    total: int
    bank_size: int = 0
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    gate: GrammarGate | None = None
    state: str = "not_started"
    evidence_depth: str = "low"


class GrammarItemOut(BaseModel):
    """Un ítem del banco de una ruta con su estado para un usuario.

    `prompt` es la pregunta que identifica el ítem en el panel; `type` distingue
    los checks de reconocimiento ("mcq") de los de producción controlada
    ("controlled_production", V3.13 P1)."""

    check_id: str
    level: str
    topic: str = ""
    prompt: str = ""
    type: str = "mcq"
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

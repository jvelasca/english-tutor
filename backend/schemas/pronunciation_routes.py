"""Esquemas Pydantic de las rutas de pronunciation (V3.9)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.pronunciation import (
    FluencyStats,
    PhonemeBreakdown,
    PronunciationBreakdown,
)

Grade = Literal["good", "fair", "needs_practice"]


class PronunciationPhrase(BaseModel):
    """Una frase modelo servida para practicar el read-aloud.

    El alumno escucha la frase (`ListenButton` con TTS local) y la lee en voz
    alta. No hay respuesta oculta: la evaluación es determinista comparando la
    transcripción con el texto esperado.
    """

    id: str
    level: str
    script: str = ""
    topic: str = ""
    difficulty: int = 1
    difficulty_vector: dict[str, int] = Field(default_factory=dict)


class PronunciationAttemptResponse(BaseModel):
    """Resultado determinista de un intento de read-aloud (V3.9).

    `score` (0..100) y el desglose salen de `score_pronunciation` sobre la
    transcripción Whisper; `passed = score >= 80`. `grade` es good/fair/
    needs_practice para la presentación."""

    phrase_id: str
    level: str
    script: str = ""
    heard: str = ""
    score: int
    grade: Grade
    passed: bool
    word_accuracy: int = 0
    phonetic_score: int = 0
    phoneme_accuracy_proxy: int = 0
    prosody_proxy: int = 0
    pronunciation_source: str = "transcript"
    breakdown: PronunciationBreakdown = Field(default_factory=PronunciationBreakdown)
    phoneme_breakdown: PhonemeBreakdown = Field(
        default_factory=PhonemeBreakdown
    )
    fluency: FluencyStats | None = None
    topic: str = ""
    difficulty: int = 1


class PronunciationGate(BaseModel):
    """Puerta de ruta de pronunciation: qué exige la evidencia para declarar la
    ruta superada (práctica) y qué valores alcanza hoy.

    `passed` solo es cierto si `blockers` está vacío. Se calcula SIEMPRE sobre
    el banco curado oficial."""

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


class PronunciationLevelOut(BaseModel):
    """Progreso de una ruta de pronunciation para el mapa de niveles.

    `state` ∈ {not_started, developing, functional}: la ruta es práctica y nunca
    informa `demonstrated` (demostrar exige Speaking Assessment + evidencia)."""

    level: str
    total: int
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    gate: PronunciationGate | None = None
    state: str = "not_started"


class PronunciationItemOut(BaseModel):
    """Una frase del banco de una ruta con su estado para un usuario.

    `script` es el texto que identifica la frase y que se lee en voz alta."""

    phrase_id: str
    level: str
    script: str = ""
    topic: str = ""
    difficulty: int = 1
    attempts: int = 0
    state: str


class PronunciationLevelItemsOut(BaseModel):
    """Estado por frase de un nivel + resumen de contadores."""

    level: str
    total: int
    mastered: int
    failed: int
    unseen: int
    completed: bool
    items: list[PronunciationItemOut]
    gate: PronunciationGate | None = None


class PronunciationStats(BaseModel):
    attempts: int
    passed: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[PronunciationLevelOut]

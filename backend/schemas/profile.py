"""Esquemas Pydantic del perfil de aprendizaje."""
from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.academy import ReadinessOut
from schemas.grammar import GrammarRecurringError


class EstimatedBands(BaseModel):
    """Bandas CEFR-alineadas **heurísticas** por destreza (NO equivalencia oficial)."""

    vocabulary: str
    grammar: str
    pronunciation: str
    listening: str
    speaking: str
    reading: str
    writing: str


class SkillState(BaseModel):
    """Estado de una destreza en el Student Model: banda heurística, score continuo,
    confianza, nº de muestras (evidencia), estabilidad, tendencia y sub-destrezas."""

    skill: str
    band: str
    score: float
    confidence: float
    samples: int
    stability: float
    trend: float | None = None
    subskills: list[dict] = Field(default_factory=list)


class CefrSnapshot(BaseModel):
    """Snapshot histórico e inmutable de una evaluación CEFR (reproducible)."""

    id: int
    level: str
    numeric: float
    confidence: float
    instrument_version: str
    curriculum_version: str
    created_at: str
    skills: list[SkillState] = Field(default_factory=list)


class LearningProfile(BaseModel):
    user_id: str
    current_level: str
    estimated_level: str
    estimated_bands: EstimatedBands
    estimated_descriptor: str
    estimated_confidence: float
    overall_ability: float
    target_level: str
    skills: list[SkillState]
    readiness: ReadinessOut
    cefr_history: list[CefrSnapshot] = Field(default_factory=list)
    vocabulary_size: int
    vocabulary_exposed: int
    vocabulary_mastered: int
    top_words: list[str]
    recurring_errors: list[GrammarRecurringError]
    mastered_errors: list[GrammarRecurringError]
    mastered_count: int
    pronunciation_average: float | None
    recommendations: list[str]

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


class CompetenceGate(BaseModel):
    """Criterios del gate de competencia (Constitución §6): dominio, confianza,
    volumen de evidencia, repaso pendiente y retención retardada."""

    score_ok: bool
    confidence_ok: bool
    evidence_ok: bool
    review_due: bool
    retention_ok: bool


class CompetenceState(BaseModel):
    """Estado de competencia de UNA destreza en el nivel actual del Student Model.

    Los 4 estados (Constitución §2.1): not_started / developing / functional /
    demonstrated. `estimated_band` es la hipótesis heurística de visualización
    ("—" sin evidencia); `demonstrated` solo se concede con retención."""

    skill: str
    level: str
    state: str
    demonstrated: bool
    estimated_band: str
    score: float
    confidence: float
    evidence_count: int
    gate: CompetenceGate


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
    competence_states: list[CompetenceState] = Field(default_factory=list)
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

"""Esquemas Pydantic del perfil de aprendizaje."""
from __future__ import annotations

from pydantic import BaseModel

from schemas.grammar import GrammarRecurringError


class EstimatedBands(BaseModel):
    vocabulary: str
    grammar: str
    fluency: str
    pronunciation: str


class LearningProfile(BaseModel):
    user_id: str
    estimated_level: str
    estimated_bands: EstimatedBands
    estimated_descriptor: str
    vocabulary_size: int
    vocabulary_exposed: int
    vocabulary_mastered: int
    top_words: list[str]
    recurring_errors: list[GrammarRecurringError]
    mastered_errors: list[GrammarRecurringError]
    mastered_count: int
    pronunciation_average: float | None
    recommendations: list[str]

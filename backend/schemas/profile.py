"""Esquemas Pydantic del perfil de aprendizaje."""
from __future__ import annotations

from pydantic import BaseModel

from schemas.grammar import GrammarRecurringError


class LearningProfile(BaseModel):
    user_id: str
    cefr_level: str
    vocabulary_size: int
    top_words: list[str]
    recurring_errors: list[GrammarRecurringError]
    pronunciation_average: float | None
    recommendations: list[str]

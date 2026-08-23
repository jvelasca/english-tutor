"""Esquemas Pydantic del progreso del alumno."""
from __future__ import annotations

from pydantic import BaseModel


class PronunciationStats(BaseModel):
    attempts: int
    best: int | None = None
    average: float | None = None
    last_score: int | None = None
    last_level: str | None = None


class ProgressSummary(BaseModel):
    user_id: str
    conversations: int
    messages: int
    exercises: int
    corrections: int
    pronunciation: PronunciationStats

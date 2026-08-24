"""Esquemas Pydantic del progreso del alumno."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from schemas.grammar import GrammarRecurringError


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


Bucket = Literal["day", "week", "month"]


class SeriesPoint(BaseModel):
    bucket: str
    messages: int
    exercises: int
    corrections: int
    pronunciation: int


class Streak(BaseModel):
    current_days: int
    best_days: int
    last_active_date: str | None = None


class ErrorMastery(BaseModel):
    active: list[GrammarRecurringError]
    resolved: list[GrammarRecurringError]


class Milestone(BaseModel):
    id: str
    label: str
    achieved: bool


class ProgressHistory(BaseModel):
    user_id: str
    bucket: Bucket
    series: list[SeriesPoint]
    streak: Streak
    mastery: ErrorMastery
    milestones: list[Milestone]

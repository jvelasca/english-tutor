"""Esquemas Pydantic de listening."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ListeningQuestion(BaseModel):
    id: str
    level: str
    skill: str
    difficulty: int
    script: str
    question: str
    options: list[str]


class ListeningAnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(ge=0)
    response_time_ms: int | None = None
    replay_count: int = Field(default=0, ge=0)


class ListeningAnswerResponse(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    level: str


class ListeningLevelOut(BaseModel):
    level: str
    total: int
    mastered: int
    completed: bool


class ListeningStats(BaseModel):
    attempts: int
    correct: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[ListeningLevelOut]


class ListeningSubskillOut(BaseModel):
    skill: str
    attempts: int
    correct: int
    accuracy: float | None = None
    avg_response_ms: float | None = None
    avg_replay_count: float
    review_due: bool


class ListeningDiagnostic(BaseModel):
    subskills: list[ListeningSubskillOut]
    weak: list[str]
    recommendation: str

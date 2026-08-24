"""Esquemas Pydantic de listening."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ListeningQuestion(BaseModel):
    id: str
    level: str
    script: str
    question: str
    options: list[str]


class ListeningAnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(ge=0)


class ListeningAnswerResponse(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    level: str


class ListeningStats(BaseModel):
    attempts: int
    correct: int
    accuracy: float | None = None

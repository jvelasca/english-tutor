"""Esquemas Pydantic de eventos de aprendizaje."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LearningEventType = Literal[
    "message", "exercise", "correction", "pronunciation", "conversation"
]


class LearningEventCreate(BaseModel):
    type: LearningEventType
    detail: str = Field(default="", max_length=500)


class LearningEvent(BaseModel):
    id: int
    user_id: str
    type: LearningEventType
    detail: str
    created_at: str

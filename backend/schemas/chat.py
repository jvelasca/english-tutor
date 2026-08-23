"""Esquemas Pydantic del chat."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import DEFAULT_MODE, DEFAULT_MODEL

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """Un mensaje dentro de la conversación."""

    role: Role
    content: str = Field(min_length=1)
    mode: str | None = None


class ChatRequest(BaseModel):
    """Cuerpo de POST /api/chat."""

    messages: list[ChatMessage]
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    mode: str = Field(default=DEFAULT_MODE)


class ChatResponse(BaseModel):
    """Respuesta de POST /api/chat."""

    model: str
    content: str
    total_duration_ms: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None

"""Esquemas Pydantic del chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import DEFAULT_MODE, DEFAULT_MODEL, MAX_CHAT_MESSAGES, MAX_CONTENT_CHARS

Role = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    """Un mensaje dentro de la conversación."""

    role: Role
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    mode: str | None = None
    id: str | None = None


class ChatRequest(BaseModel):
    """Cuerpo de POST /api/chat."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_CHAT_MESSAGES)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    mode: str = Field(default=DEFAULT_MODE)
    # Objetivo de la Academy (opcional): activa el AI Teacher de la lección.
    objective_id: str | None = None
    # Identificadores opcionales para persistir telemetría de turno
    # (InteractionEvidence 2.0): `conversation_id` asocia el turno del asistente a
    # una conversación y `message_id` lo identifica para no duplicarlo al guardar la
    # historia completa después.
    conversation_id: str | None = None
    message_id: str | None = None


class ChatResponse(BaseModel):
    """Respuesta de POST /api/chat."""

    model: str
    content: str
    total_duration_ms: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None

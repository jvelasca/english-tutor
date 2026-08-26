"""Esquemas Pydantic de conversaciones."""
from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.chat import ChatMessage


class ConversationMeta(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    user_id: str


class Conversation(ConversationMeta):
    messages: list[ChatMessage] = Field(default_factory=list)


class ConversationUpsert(BaseModel):
    title: str = Field(default="Nueva conversación")
    messages: list[ChatMessage] = Field(default_factory=list)


class InteractionEvidence(BaseModel):
    """Evidencia objetiva de interacción de una conversación (Interaction 2.0)."""

    turn_balance: float | None = None
    avg_response_latency_ms: int | None = None
    turn_completion: float | None = None
    student_turns: int = 0
    assistant_turns: int = 0
    interruptions: int | None = None

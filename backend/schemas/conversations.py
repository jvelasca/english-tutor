"""Esquemas Pydantic de conversaciones."""
from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.chat import ChatMessage


class ConversationMeta(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class Conversation(ConversationMeta):
    messages: list[ChatMessage] = Field(default_factory=list)


class ConversationUpsert(BaseModel):
    title: str = Field(default="Nueva conversación")
    messages: list[ChatMessage] = Field(default_factory=list)

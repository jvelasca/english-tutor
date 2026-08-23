"""Contratos de datos (Pydantic) del backend."""
from schemas.chat import ChatMessage, ChatRequest, ChatResponse
from schemas.conversations import Conversation, ConversationMeta, ConversationUpsert
from schemas.pronunciation import PronunciationResponse
from schemas.users import User, UserCreate
from schemas.voz import TTSRequest, TranscribeResponse

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Conversation",
    "ConversationMeta",
    "ConversationUpsert",
    "PronunciationResponse",
    "TTSRequest",
    "TranscribeResponse",
    "User",
    "UserCreate",
]

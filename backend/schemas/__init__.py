"""Contratos de datos (Pydantic) del backend."""
from schemas.chat import ChatMessage, ChatRequest, ChatResponse
from schemas.conversations import Conversation, ConversationMeta, ConversationUpsert
from schemas.progress import ProgressSummary, PronunciationStats
from schemas.pronunciation import PronunciationResponse
from schemas.users import User, UserCreate
from schemas.voz import TranscribeResponse, TTSRequest

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Conversation",
    "ConversationMeta",
    "ConversationUpsert",
    "PronunciationResponse",
    "PronunciationStats",
    "ProgressSummary",
    "TTSRequest",
    "TranscribeResponse",
    "User",
    "UserCreate",
]

"""Esquemas Pydantic de voz."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import MAX_TTS_CHARS


class TranscribeResponse(BaseModel):
    text: str


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)

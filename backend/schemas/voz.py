"""Esquemas Pydantic de voz."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    text: str


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)

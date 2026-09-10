"""Esquemas Pydantic de voz."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import MAX_TTS_CHARS


class TranscribeResponse(BaseModel):
    text: str


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    language: str = Field(
        default="en",
        min_length=2,
        max_length=8,
        description=(
            "Idioma de la síntesis (ISO-639-1, p. ej. `en`/`es`). V3.39, Fase 2: "
            "permite que el Traductor lea la salida en el idioma destino."
        ),
    )

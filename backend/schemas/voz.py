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
    voice: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "V3.75.5 (dos acentos): id de la voz Piper con la que sintetizar. Es "
            "OPCIONAL y solo se acepta si está instalada Y es del idioma pedido "
            "(`services.tts.pick_requested_voice`); si no, se ignora y manda la "
            "voz del perfil. Permite oír el mismo texto con dos acentos sin "
            "cambiar la preferencia guardada."
        ),
    )

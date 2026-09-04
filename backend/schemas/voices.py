"""Esquemas Pydantic de voces TTS disponibles."""
from __future__ import annotations

from pydantic import BaseModel


class VoiceInfo(BaseModel):
    """Una voz Piper instalada: id técnico + etiqueta amigable."""

    id: str
    name: str


class VoicesResponse(BaseModel):
    """Catálogo de voces instaladas con la selección actual.

    `voices` son las voces Piper detectadas en `models/piper`; `default` es la
    voz por defecto del sistema y `selected` la del usuario (o `default` si el
    usuario no ha elegido / su elección no está instalada).
    """

    voices: list[VoiceInfo]
    default: str
    selected: str

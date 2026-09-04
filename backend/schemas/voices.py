"""Esquemas Pydantic de voces TTS disponibles."""
from __future__ import annotations

from pydantic import BaseModel


class VoiceInfo(BaseModel):
    """Una voz Piper: id técnico + etiqueta amigable."""

    id: str
    name: str


class DownloadableVoice(BaseModel):
    """Voz del catálogo curado que se puede descargar desde la UI."""

    id: str
    name: str
    size_mb: int


class VoicesResponse(BaseModel):
    """Catálogo de voces con la selección actual.

    `voices` son las voces Piper detectadas en `models/piper` (instaladas);
    `downloadable` son las voces del catálogo curado que aún no están instaladas
    (la UI ofrece descargarlas); `default` es la voz por defecto del sistema y
    `selected` la del usuario (o `default` si el usuario no ha elegido / su
    elección no está instalada).
    """

    voices: list[VoiceInfo]
    downloadable: list[DownloadableVoice]
    default: str
    selected: str


class VoiceDownloadRequest(BaseModel):
    """Petición de descarga de una voz del catálogo curado."""

    voice_id: str


class VoiceDownloadStatus(BaseModel):
    """Estado de una descarga (éxito o error legible)."""

    ok: bool
    error: str | None = None

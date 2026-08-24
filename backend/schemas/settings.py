"""Esquemas Pydantic de preferencias de usuario (settings por clave/valor)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    settings: dict[str, str] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    user_id: str = Field(min_length=1)
    settings: dict[str, str] = Field(default_factory=dict)

"""Esquemas Pydantic de usuarios (perfiles locales)."""
from __future__ import annotations

from pydantic import BaseModel, Field

# Límite para la imagen de avatar (data URL). Suficiente para una miniatura
# redimensionada en el cliente (~128 px) y evita abusos de tamaño en la BD.
MAX_AVATAR_IMAGE_CHARS = 500_000


class User(BaseModel):
    id: str
    name: str
    avatar_color: str = ""
    avatar_emoji: str = ""
    avatar_image: str = ""
    # V3.52.1: perfil de PRUEBA (tests visuales). Nunca aparece en el selector
    # de la app; se expone para que los tests puedan localizar y limpiar el suyo.
    is_test: bool = False
    created_at: str


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    # Solo los tests lo marcan; la app siempre crea perfiles reales.
    is_test: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_color: str | None = Field(default=None, max_length=32)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_image: str | None = Field(default=None, max_length=MAX_AVATAR_IMAGE_CHARS)

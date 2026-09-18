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
    # `max_length` alineado con `UserUpdate`: `POST /api/users` no exige
    # credencial, así que sin tope se pueden crear nombres de tamaño arbitrario.
    name: str = Field(min_length=1, max_length=80)
    # Solo los tests lo marcan; la app siempre crea perfiles reales.
    is_test: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_color: str | None = Field(default=None, max_length=32)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_image: str | None = Field(default=None, max_length=MAX_AVATAR_IMAGE_CHARS)


class SessionCreate(BaseModel):
    """Cuerpo de `POST /api/session`: el perfil que la petición **reclama**.

    No es una credencial —el producto no tiene ninguna (Fase 3)— y conviene no
    confundirlo: es la declaración de con quién quieres abrir sesión, y el
    servidor la firma. Lo que cambia respecto a V3.73.x es que, a partir de ahí,
    la identidad viaja en una cookie que el cliente **no puede forjar**, en vez
    de en la URL (`docs/audit/PLAN-P0-IDENTIDAD.md` §4).
    """

    user_id: str = Field(min_length=1, max_length=64)

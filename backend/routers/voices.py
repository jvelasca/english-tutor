"""Endpoints de voces TTS disponibles (Configuración → Voces)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user_optional
from domain import settings as settings_service
from schemas.voices import VoicesResponse
from services.tts import DEFAULT_VOICE, list_voices, resolve_voice, voice_name

router = APIRouter()


@router.get("/api/voices", response_model=VoicesResponse)
async def voices(
    user: dict | None = Depends(current_user_optional),
) -> VoicesResponse:
    """Catálogo de voces Piper instaladas y la selección del usuario.

    `user_id` es opcional: con usuario se resuelve su preferencia (`tts_voice`)
    contra lo instalado; sin usuario (o sin preferencia válida) `selected` es la
    voz por defecto del sistema.
    """
    prefs: dict[str, str] = {}
    if user is not None:
        prefs = await settings_service.get_settings(user["id"])
    installed = list_voices()
    return VoicesResponse(
        voices=[{"id": v, "name": voice_name(v)} for v in installed],
        default=DEFAULT_VOICE,
        selected=resolve_voice(prefs),
    )

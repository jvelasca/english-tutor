"""Endpoints de voces TTS disponibles (Configuración → Voces)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from dependencies import current_user_optional
from domain import settings as settings_service
from schemas.voices import (
    VoicesResponse,
    VoiceDownloadRequest,
    VoiceDownloadStatus,
)
from services import voice_downloads
from services.tts import DEFAULT_VOICE, list_voices, resolve_voice, voice_name

logger = logging.getLogger(__name__)

router = APIRouter()


def _response(selected: str) -> VoicesResponse:
    installed = list_voices()
    return VoicesResponse(
        voices=[{"id": v, "name": voice_name(v)} for v in installed],
        downloadable=[
            {"id": spec.id, "name": spec.name, "size_mb": spec.size_mb}
            for spec in voice_downloads.available_to_download(installed)
        ],
        default=DEFAULT_VOICE,
        selected=selected,
    )


@router.get("/api/voices", response_model=VoicesResponse)
async def voices(
    user: dict | None = Depends(current_user_optional),
) -> VoicesResponse:
    """Catálogo de voces instaladas + descargables y la selección del usuario.

    `user_id` es opcional: con usuario se resuelve su preferencia (`tts_voice`)
    contra lo instalado; sin usuario (o sin preferencia válida) `selected` es la
    voz por defecto del sistema.
    """
    prefs: dict[str, str] = {}
    if user is not None:
        prefs = await settings_service.get_settings(user["id"])
    return _response(resolve_voice(prefs))


@router.post("/api/voices/download", response_model=VoiceDownloadStatus)
async def download(body: VoiceDownloadRequest) -> VoiceDownloadStatus:
    """Descarga una voz del catálogo curado (~60 MB) desde Hugging Face.

    La descarga es bloqueante y corre en el threadpool; la UI muestra un estado
    mientras tanto y refresca el catálogo al terminar. Errores de red/escritura
    devuelven un mensaje legible (400 para ids fuera del catálogo, 502 si la
    descarga falla).
    """
    if voice_downloads.spec_for(body.voice_id) is None:
        raise HTTPException(status_code=400, detail="Voz desconocida en el catálogo")
    try:
        await run_in_threadpool(voice_downloads.download_voice, body.voice_id)
    except RuntimeError as exc:
        logger.warning("Fallo al descargar la voz %s: %s", body.voice_id, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return VoiceDownloadStatus(ok=True)

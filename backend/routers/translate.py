"""Endpoints de traducción de apoyo EN→ES (best-effort, no registra nada)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from schemas.translate import TranslateRequest, TranslateResponse
from services import translate as translate_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/translate", response_model=TranslateResponse)
async def translate(body: TranslateRequest) -> TranslateResponse:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text está vacío")
    try:
        translation = await translate_service.translate_text(body.text, body.model)
    except Exception:  # noqa: BLE001
        logger.exception("Error en /api/translate")
        raise HTTPException(
            status_code=502,
            detail="Traducción no disponible (¿está activo el modelo local?)",
        ) from None
    return TranslateResponse(translation=translation)

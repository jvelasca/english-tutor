"""Endpoints de voz (transcribir y sintetizar)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from dependencies import read_audio_limited
from schemas.voz import TranscribeResponse, TTSRequest
from services.stt import transcribe as transcribe_audio
from services.tts import synthesize as synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...), language: str = Form("en")
) -> TranscribeResponse:
    audio = await read_audio_limited(file)
    try:
        text = await run_in_threadpool(transcribe_audio, audio, language)
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    return TranscribeResponse(text=text)


@router.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    try:
        wav = await run_in_threadpool(synthesize_speech, req.text)
    except Exception:  # noqa: BLE001
        logger.exception("Error sintetizando la voz")
        raise HTTPException(
            status_code=500, detail="No se pudo sintetizar la voz"
        ) from None
    return Response(content=wav, media_type="audio/wav")

"""Endpoint de corrección de pronunciación."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from dependencies import read_audio_limited
from domain import learning as learning_service
from domain import pronunciation as pronunciation_service
from domain import users as user_service
from schemas.pronunciation import PronunciationResponse
from services.fluency import compute_fluency
from services.pronunciation import score_pronunciation
from services.stt import transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/pronunciation", response_model=PronunciationResponse)
async def pronunciation(
    file: UploadFile = File(...),
    expected: str = Form(...),
    language: str = Form("en"),
    user_id: str = Form(...),
) -> PronunciationResponse:
    if await user_service.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, language)
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    result = score_pronunciation(expected, heard)
    result["fluency"] = compute_fluency(heard, timed.get("duration"))
    await pronunciation_service.record_pronunciation(
        user_id, result["expected"], result["heard"], result["score"], result["level"]
    )
    await learning_service.record_event(user_id, "pronunciation", result["expected"])
    return PronunciationResponse(**result)

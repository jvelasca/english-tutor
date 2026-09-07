"""Endpoint de corrección de pronunciación."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

import config
from dependencies import current_user, read_audio_limited
from domain import learning as learning_service
from domain import pronunciation as pronunciation_service
from domain import vocabulary as vocabulary_service
from schemas.pronunciation import PronunciationResponse
from services.fluency import compute_fluency
from services.pronunciation import score_pronunciation
from services.stt import exceeds_max_duration, transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/pronunciation", response_model=PronunciationResponse)
async def pronunciation(
    file: UploadFile = File(...),
    expected: str = Form(...),
    language: str = Form("en"),
    user: dict = Depends(current_user),
) -> PronunciationResponse:
    user_id = user["id"]
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, language)
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    # V3.21 (V20-13): red de seguridad de duración (audio demasiado largo).
    if exceeds_max_duration(timed.get("duration")):
        raise HTTPException(
            status_code=400,
            detail=f"El audio dura {timed['duration']:.1f}s y supera el máximo de "
            f"{config.MAX_AUDIO_DURATION_SECONDS:.0f}s permitido. Grábalo de nuevo.",
        )
    heard = timed["text"]
    result = score_pronunciation(expected, heard)
    result["fluency"] = compute_fluency(heard, timed.get("duration"))
    asr_status = timed.get("asr_status", "ok")
    asr_confidence = timed.get("confidence")
    result["asr_status"] = asr_status
    result["asr_confidence"] = asr_confidence
    if asr_status == "ok":
        # Solo con ASR fiable se registra el intento y se vuelca al léxico: un
        # fallo de reconocimiento no es un fallo lingüístico del alumno (V3.21,
        # V20-14/15).
        await pronunciation_service.record_pronunciation(
            user_id,
            result["expected"],
            result["heard"],
            result["score"],
            result["level"],
        )
        await learning_service.record_event(
            user_id, "pronunciation", result["expected"]
        )
        # V3.19: la lectura en voz alta es producción oral; volcarla al léxico
        # por destreza (canal speaking). No bloquea la respuesta (nunca lanza).
        await vocabulary_service.record_production_text(
            user_id, result["heard"], "speaking"
        )
    return PronunciationResponse(**result)

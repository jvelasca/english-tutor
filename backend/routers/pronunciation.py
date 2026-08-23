"""Endpoint de corrección de pronunciación."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from schemas.pronunciation import PronunciationResponse
from services import store
from services.pronunciation import score_pronunciation
from services.stt import transcribe as transcribe_audio

router = APIRouter()


@router.post("/api/pronunciation", response_model=PronunciationResponse)
async def pronunciation(
    file: UploadFile = File(...),
    expected: str = Form(...),
    language: str = Form("en"),
    user_id: str = Form(None),
) -> PronunciationResponse:
    audio = await file.read()
    try:
        heard = await run_in_threadpool(transcribe_audio, audio, language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Error transcribiendo el audio: {exc}"
        ) from exc
    result = score_pronunciation(expected, heard)
    if user_id:
        store.record_pronunciation(
            user_id, result["expected"], result["heard"], result["score"], result["level"]
        )
    return PronunciationResponse(**result)

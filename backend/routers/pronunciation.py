"""Endpoint de corrección de pronunciación."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from schemas.pronunciation import PronunciationResponse
from services.pronunciation import score_pronunciation
from services.stt import transcribe as transcribe_audio

router = APIRouter()


@router.post("/api/pronunciation", response_model=PronunciationResponse)
async def pronunciation(
    file: UploadFile = File(...),
    expected: str = Form(...),
    language: str = Form("en"),
) -> PronunciationResponse:
    audio = await file.read()
    try:
        heard = await run_in_threadpool(transcribe_audio, audio, language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Error transcribiendo el audio: {exc}"
        ) from exc
    return PronunciationResponse(**score_pronunciation(expected, heard))

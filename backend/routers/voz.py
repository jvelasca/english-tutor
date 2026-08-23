"""Endpoints de voz (transcribir y sintetizar)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from schemas.voz import TTSRequest, TranscribeResponse
from services.stt import transcribe as transcribe_audio
from services.tts import synthesize as synthesize_speech

router = APIRouter()


@router.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...), language: str = Form("en")
) -> TranscribeResponse:
    audio = await file.read()
    try:
        text = await run_in_threadpool(transcribe_audio, audio, language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Error transcribiendo el audio: {exc}"
        ) from exc
    return TranscribeResponse(text=text)


@router.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    try:
        wav = await run_in_threadpool(synthesize_speech, req.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Error sintetizando la voz: {exc}"
        ) from exc
    return Response(content=wav, media_type="audio/wav")

"""Endpoints de vocabulario."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from dependencies import current_user, read_audio_limited
from domain import learning as learning_service
from domain import vocabulary as vocabulary_service
from schemas.vocabulary import (
    DrillAttemptOut,
    DrillCandidatesOut,
    LexiconOut,
    VocabularyAnalyzeRequest,
    VocabularyAnalyzeResponse,
    VocabularyItem,
)
from services.stt import transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/vocabulary/analyze", response_model=VocabularyAnalyzeResponse)
async def analyze(
    body: VocabularyAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    words = await vocabulary_service.analyze_text(user["id"], body.text)
    return {"words": words}


@router.get("/api/vocabulary", response_model=list[VocabularyItem])
async def get_vocabulary(user: dict = Depends(current_user)) -> list[dict]:
    return await vocabulary_service.get_vocabulary(user["id"])


@router.get("/api/vocabulary/lexicon", response_model=LexiconOut)
async def get_lexicon(user: dict = Depends(current_user)) -> dict:
    return await vocabulary_service.get_lexicon(user["id"])


@router.get("/api/vocabulary/drill/candidates", response_model=DrillCandidatesOut)
async def drill_candidates(
    limit: int = 8, user: dict = Depends(current_user)
) -> dict:
    """Candidatos al speaking micro-drill (V3.19): expuestas (exposures > 0) y
    nunca producidas en práctica de speaking (`speaking_prod == 0`), por recuerdo
    ascendente. Señal determinista en servidor (premisa 21)."""
    words = await vocabulary_service.get_drill_candidates(user["id"], limit=limit)
    return {"words": words}


@router.post("/api/vocabulary/drill/attempt", response_model=DrillAttemptOut)
async def drill_attempt(
    word: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    """Intento de speaking micro-drill: transcribe el audio (Whisper) y puntúa la
    palabra con `score_pronunciation`. Si el alumno la dijo (aparece alineada en
    `breakdown.correct`) se registra `speaking_prod += 1` y sale de la lista de
    candidatas. No crea evidencia curricular ni FSRS (D5/E3)."""
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, "en")
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio del drill")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    result = await vocabulary_service.submit_drill_attempt(
        user["id"], word, heard, duration_seconds=timed.get("duration")
    )
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"drill:{word}:{'ok' if result['produced'] else 'ko'}",
    )
    return result

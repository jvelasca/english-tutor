"""Endpoints de las rutas de pronunciation (V3.9).

Práctica read-aloud guiada por nivel CEFR con frases modelo: siguiente frase
(nueva/failed/mastered), estado del nivel, intentos (transcripción Whisper +
`score_pronunciation` determinista) y progreso del mapa. La ruta es un hito de
práctica con techo `functional`; demostrar el nivel exige el Speaking Assessment
y evidencia formal, nunca esta ruta.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from dependencies import current_user, read_audio_limited
from domain import learning as learning_service
from domain import pronunciation_routes as pronunciation_routes_service
from schemas.pronunciation_routes import (
    PronunciationAttemptResponse,
    PronunciationLevelItemsOut,
    PronunciationPhrase,
    PronunciationStats,
)
from services.pronunciation_routes import LEVEL_ORDER
from services.stt import transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_MODES = ("all", "failed", "mastered")


def _valid_level_or_400(level: str) -> None:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")


@router.get("/api/pronunciation/routes/question", response_model=PronunciationPhrase)
async def question(
    level: str | None = None,
    mode: str = "all",
    user: dict = Depends(current_user),
) -> dict:
    if level is not None:
        _valid_level_or_400(level)
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Modo no válido: {mode}")
    try:
        return await pronunciation_routes_service.next_phrase(
            user["id"], level=level, mode=mode
        )
    except ValueError as exc:
        if str(exc) == "pronunciation.no_failed":
            raise HTTPException(
                status_code=404, detail="pronunciation.no_failed"
            ) from None
        raise


@router.get(
    "/api/pronunciation/routes/items", response_model=PronunciationLevelItemsOut
)
async def level_items(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    _valid_level_or_400(level)
    return await pronunciation_routes_service.phrases_for_level_out(user["id"], level)


@router.get("/api/pronunciation/routes/stats", response_model=PronunciationStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await pronunciation_routes_service.get_stats(user["id"])


@router.post(
    "/api/pronunciation/routes/attempt", response_model=PronunciationAttemptResponse
)
async def attempt(
    phrase_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    """Graba la lectura de una frase: transcribe (Whisper) y puntúa determinista.

    A diferencia de speaking (respuesta abierta con LLM), la evaluación read-aloud
    es determinista (`score_pronunciation`), así que nunca hay 503 por extractor.
    """
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, "en")
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio de pronunciation")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    duration = timed.get("duration")
    result = await pronunciation_routes_service.submit_attempt(
        user["id"], phrase_id, heard, duration
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Frase no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"pronunciation:{phrase_id}:{'ok' if result['passed'] else 'ko'}",
    )
    return result

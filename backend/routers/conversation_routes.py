"""Endpoints de las rutas de conversation (V3.10).

Conversación guiada por nivel CEFR con mini-diálogos multi-turno: siguiente
diálogo (nuevo/failed/mastered), estado del nivel e intentos de conversación
terminada (el transcripto persistido se evalúa con el pipeline LLM de evidencia
+ señal objetiva de interacción). La conversación en vivo se mantiene en el chat
libre y en el mini-chat guiado del frontend; aquí solo se entrega y se puntúa.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import learning as learning_service
from domain import conversation_routes as conversation_routes_service
from domain.conversation_routes import is_valid_level
from domain.speaking_routes import EvidenceExtractionError
from schemas.conversation_routes import (
    ConversationAttemptRequest,
    ConversationAttemptResponse,
    ConversationDialogue,
    ConversationLevelItemsOut,
    ConversationStats,
)

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_MODES = ("all", "failed", "mastered")


@router.get(
    "/api/conversation/routes/question", response_model=ConversationDialogue
)
async def question(
    level: str | None = None,
    mode: str = "all",
    user: dict = Depends(current_user),
) -> dict:
    if level is not None and not is_valid_level(level):
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Modo no válido: {mode}")
    try:
        return await conversation_routes_service.next_dialogue(
            user["id"], level=level, mode=mode
        )
    except ValueError as exc:
        if str(exc) == "conversation.no_failed":
            raise HTTPException(
                status_code=404, detail="conversation.no_failed"
            ) from None
        raise


@router.get(
    "/api/conversation/routes/items",
    response_model=ConversationLevelItemsOut,
)
async def level_items(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    if not is_valid_level(level):
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    return await conversation_routes_service.dialogues_for_level_out(
        user["id"], level
    )


@router.get("/api/conversation/routes/stats", response_model=ConversationStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await conversation_routes_service.get_stats(user["id"])


@router.post(
    "/api/conversation/routes/attempt",
    response_model=ConversationAttemptResponse,
)
async def attempt(
    body: ConversationAttemptRequest,
    user: dict = Depends(current_user),
) -> dict:
    """Entrega una conversación guiada terminada y la evalúa sobre su transcripto.

    La evaluación usa el pipeline LLM+evidencia (mismo que speaking/misiones): si
    el extractor no produce evidencia válida se responde 503 (transitorio) para
    que el alumno reintente; nunca se puntúa en falso.
    """
    try:
        result = await conversation_routes_service.submit_attempt(
            user["id"], body.dialogue_id, body.conversation_id
        )
    except ValueError as exc:
        if str(exc) == "conversation.too_short":
            raise HTTPException(
                status_code=400,
                detail="conversation.too_short",
            ) from None
        raise
    except EvidenceExtractionError:
        logger.warning(
            "Intento de conversación sin evidencia válida del LLM; 503"
        )
        raise HTTPException(
            status_code=503, detail="speaking.evidence_failed"
        ) from None
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Diálogo o conversación no encontrados",
        )
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"conversation:{body.dialogue_id}:{'ok' if result['passed'] else 'ko'}",
    )
    return result

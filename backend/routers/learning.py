"""Endpoints de eventos de aprendizaje y cola de repaso."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dependencies import current_user
from domain import learning as learning_service
from domain import review as review_service
from schemas.learning import (
    LearningEvent,
    LearningEventCreate,
    LearningEventType,
    ReviewQueueOut,
)

router = APIRouter()


@router.post("/api/learning/events", response_model=LearningEvent)
async def record_event(
    body: LearningEventCreate, user: dict = Depends(current_user)
) -> dict:
    return await learning_service.record_event(user["id"], body.type, body.detail)


@router.get("/api/learning/events", response_model=list[LearningEvent])
async def list_events(
    user: dict = Depends(current_user),
    event_type: LearningEventType | None = Query(None),
) -> list[dict]:
    return await learning_service.list_events(user["id"], event_type)


@router.get("/api/learning/review", response_model=ReviewQueueOut)
async def review_queue(
    limit: int = Query(default=20, ge=1, le=50),
    user: dict = Depends(current_user),
) -> dict:
    """Cola de repaso léxico (V3.35, P1-2).

    Cartas FSRS `lexicon` vencidas con la actividad recomendada por hueco de
    competencia (recognition / recall / sentence), ordenadas por urgencia
    (`retrievability` ascendente). Sustituye la inyección de cartas FSRS dentro
    del speaking micro-drill: separa el repaso espaciado de la producción oral.
    Señal, nunca puerta; nunca expone la respuesta esperada."""
    return await review_service.get_review_queue(user["id"], limit=limit)

"""Endpoints de eventos de aprendizaje."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dependencies import current_user
from domain import learning as learning_service
from schemas.learning import LearningEvent, LearningEventCreate, LearningEventType

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

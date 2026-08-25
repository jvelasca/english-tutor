"""Endpoints de evaluación: placement test, examen de nivel y completitud de niveles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import academy as academy_service
from schemas.academy import (
    AssessmentSubmit,
    ExamOut,
    ExamResultOut,
    LevelCompletionsOut,
    PlacementAdaptiveOut,
    PlacementOut,
    PlacementResultOut,
    PlacementStartOut,
)

router = APIRouter()


@router.get("/api/academy/placement", response_model=PlacementOut)
async def placement() -> dict:
    return await academy_service.get_placement()


@router.post("/api/academy/placement/submit", response_model=PlacementResultOut)
async def submit_placement(
    body: AssessmentSubmit, user: dict = Depends(current_user)
) -> dict:
    result = await academy_service.submit_placement(user["id"], body.answers)
    if result is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return result


@router.post("/api/academy/placement/next", response_model=PlacementAdaptiveOut)
async def next_placement(
    body: AssessmentSubmit, user: dict = Depends(current_user)
) -> dict:
    result = await academy_service.next_placement(
        user["id"], body.answers, body.session_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return result


@router.post("/api/academy/placement/start", response_model=PlacementStartOut)
async def start_placement(user: dict = Depends(current_user)) -> dict:
    result = await academy_service.start_placement(user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return result


@router.get("/api/academy/exam/{level_id}", response_model=ExamOut)
async def exam(level_id: str) -> dict:
    result = await academy_service.get_exam(level_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    return result


@router.post("/api/academy/exam/{level_id}/submit", response_model=ExamResultOut)
async def submit_exam(
    level_id: str, body: AssessmentSubmit, user: dict = Depends(current_user)
) -> dict:
    result = await academy_service.submit_exam(user["id"], level_id, body.answers)
    if result is None:
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    return result


@router.get("/api/academy/level-completions", response_model=LevelCompletionsOut)
async def level_completions(user: dict = Depends(current_user)) -> dict:
    return {"completions": await academy_service.list_level_completions(user["id"])}

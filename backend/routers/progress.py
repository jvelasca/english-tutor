"""Endpoint de consulta del progreso del alumno."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dependencies import current_user
from domain import progress as progress_service
from domain import pronunciation as pronunciation_service
from schemas.progress import Bucket, ProgressHistory, ProgressSummary

router = APIRouter()


@router.get("/api/progress", response_model=ProgressSummary)
async def progress(user: dict = Depends(current_user)) -> dict:
    return await pronunciation_service.get_progress(user["id"])


@router.get("/api/progress/history", response_model=ProgressHistory)
async def progress_history(
    user: dict = Depends(current_user),
    bucket: Bucket = Query("week"),
) -> dict:
    return await progress_service.get_progress_history(user["id"], bucket)

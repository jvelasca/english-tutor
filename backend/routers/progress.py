"""Endpoint de consulta del progreso del alumno."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from schemas.progress import ProgressSummary
from services import store_async

router = APIRouter()


@router.get("/api/progress", response_model=ProgressSummary)
async def progress(user: dict = Depends(current_user)) -> dict:
    return await store_async.get_progress(user["id"])

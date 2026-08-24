"""Endpoint de consulta del progreso del alumno."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import pronunciation as pronunciation_service
from schemas.progress import ProgressSummary

router = APIRouter()


@router.get("/api/progress", response_model=ProgressSummary)
async def progress(user: dict = Depends(current_user)) -> dict:
    return await pronunciation_service.get_progress(user["id"])

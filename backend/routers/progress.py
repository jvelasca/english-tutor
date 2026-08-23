"""Endpoint de consulta del progreso del alumno."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas.progress import ProgressSummary
from services import store

router = APIRouter()


@router.get("/api/progress", response_model=ProgressSummary)
async def progress(user_id: str) -> dict:
    if store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return store.get_progress(user_id)

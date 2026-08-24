"""Endpoints de estado y modelos disponibles."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from config import VERSION
from services.llm import list_models as list_ollama_models

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "english-tutor",
        "version": VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/api/models")
async def models() -> dict[str, list[str]]:
    try:
        return {"models": await list_ollama_models()}
    except Exception:  # noqa: BLE001
        logger.exception("Error en /api/models")
        raise HTTPException(
            status_code=502, detail="No se pudo contactar con Ollama"
        ) from None

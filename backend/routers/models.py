"""Endpoints de estado y modelos disponibles."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.llm import list_models as list_ollama_models

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "english-tutor",
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "english-tutor"}


@router.get("/api/models")
async def models() -> dict[str, list[str]]:
    try:
        return {"models": await list_ollama_models()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Ollama error: {exc}") from exc

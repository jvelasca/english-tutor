"""Endpoints de estado y modelos disponibles."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from config import DEFAULT_MODEL, UNUSABLE_MODELS, VERSION
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
async def models() -> dict:
    """Modelos ofertados + modelo por defecto (fuente única en `config.py`).

    `models` excluye los marcados como no utilizables en
    `config.UNUSABLE_MODELS` (instalados en Ollama pero demasiado lentos). Así el
    selector de Ajustes → IA nunca ofrece un modelo que no se puede usar.

    V3.21 (V20-05): `default_model` (de `config.DEFAULT_MODEL`) se expone de
    forma aditiva para que el frontend NO duplique la constante: los flujos
    conversacionales resuelven el modelo por defecto desde este endpoint.
    """
    try:
        found = await list_ollama_models()
    except Exception:  # noqa: BLE001
        logger.exception("Error en /api/models")
        raise HTTPException(
            status_code=502, detail="No se pudo contactar con Ollama"
        ) from None
    usable = [m for m in found if m not in UNUSABLE_MODELS]
    return {"models": usable, "default_model": DEFAULT_MODEL}

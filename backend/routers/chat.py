"""Endpoints de chat."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from dependencies import current_user_optional
from domain import learning as learning_service
from domain import profile as profile_service
from schemas.chat import ChatRequest, ChatResponse
from services.context import build_system_prompt
from services.llm import chat_once, chat_stream

logger = logging.getLogger(__name__)

router = APIRouter()


async def _system_prompt(req: ChatRequest, user_id: str | None) -> str:
    """Construye el system prompt del tutor a partir del modo y, si hay un
    usuario activo, del perfil del alumno."""
    profile = None
    if user_id:
        profile = await profile_service.get_profile_context(user_id)
    return build_system_prompt(req.mode, profile)


async def _record_activity(req: ChatRequest, user_id: str | None) -> None:
    """Registra la actividad del alumno si hay un usuario activo (opcional)."""
    if not user_id:
        return
    detail = req.messages[-1].content[:200] if req.messages else ""
    await learning_service.record_chat_activity(user_id, req.mode, detail)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, user: dict | None = Depends(current_user_optional)
) -> ChatResponse:
    user_id = user["id"] if user else None
    system_prompt = await _system_prompt(req, user_id)
    await _record_activity(req, user_id)
    try:
        return await chat_once(
            req.messages, req.model, req.temperature, req.mode, system_prompt
        )
    except Exception:  # noqa: BLE001
        logger.exception("Error en /api/chat")
        raise HTTPException(
            status_code=502, detail="No se pudo completar la respuesta"
        ) from None


@router.post("/api/chat/stream")
async def chat_stream_endpoint(
    req: ChatRequest, user: dict | None = Depends(current_user_optional)
) -> StreamingResponse:
    """Emite la respuesta como Server-Sent Events (texto incremental)."""
    user_id = user["id"] if user else None
    system_prompt = await _system_prompt(req, user_id)
    await _record_activity(req, user_id)

    async def generate():
        try:
            async for content in chat_stream(
                req.messages, req.model, req.temperature, req.mode, system_prompt
            ):
                data = json.dumps({"content": content}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield 'data: {"done": true}\n\n'
        except Exception:  # noqa: BLE001
            logger.exception("Error en /api/chat/stream")
            yield 'data: {"error": "No se pudo completar la respuesta"}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")

"""Endpoints de chat."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from domain import profile as profile_service
from schemas.chat import ChatRequest, ChatResponse
from services.context import build_system_prompt
from services.llm import chat_once, chat_stream

logger = logging.getLogger(__name__)

router = APIRouter()


async def _system_prompt(req: ChatRequest) -> str:
    """Construye el system prompt del tutor a partir del modo y, si hay un
    user_id válido, del perfil del alumno."""
    profile = None
    if req.user_id:
        profile = await profile_service.get_profile_context(req.user_id)
    return build_system_prompt(req.mode, profile)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    system_prompt = await _system_prompt(req)
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
async def chat_stream_endpoint(req: ChatRequest) -> StreamingResponse:
    """Emite la respuesta como Server-Sent Events (texto incremental)."""
    system_prompt = await _system_prompt(req)

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

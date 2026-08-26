"""Endpoints de chat."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from dependencies import current_user_optional
from domain import academy as academy_service
from domain import conversations as conversation_service
from domain import learning as learning_service
from domain import profile as profile_service
from domain import vocabulary as vocabulary_service
from schemas.chat import ChatRequest, ChatResponse
from services.context import build_system_prompt
from services.llm import chat_once, chat_stream

logger = logging.getLogger(__name__)

router = APIRouter()


async def _system_prompt(req: ChatRequest, user_id: str | None) -> str:
    """Construye el system prompt del tutor a partir del modo y, si hay un
    usuario activo, del perfil del alumno. Si la petición trae `objective_id`,
    activa el AI Teacher de la Academy para esa lección."""
    if req.objective_id and user_id:
        lesson = await academy_service.lesson_prompt(user_id, req.objective_id)
        if lesson is not None:
            return lesson
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
        reply = await chat_once(
            req.messages, req.model, req.temperature, req.mode, system_prompt
        )
    except Exception:  # noqa: BLE001
        logger.exception("Error en /api/chat")
        raise HTTPException(
            status_code=502, detail="No se pudo completar la respuesta"
        ) from None
    if user_id:
        await vocabulary_service.record_exposure(user_id, reply.content)
    return reply


@router.post("/api/chat/stream")
async def chat_stream_endpoint(
    req: ChatRequest, user: dict | None = Depends(current_user_optional)
) -> StreamingResponse:
    """Emite la respuesta como Server-Sent Events (texto incremental).

    Mide el tiempo-hasta-primer-token (`latency_ms`) y la duración total
    (`duration_ms`), los incluye en el evento final `done` y, si la petición trae
    `conversation_id`, persiste la telemetría del turno del asistente.
    """
    user_id = user["id"] if user else None
    system_prompt = await _system_prompt(req, user_id)
    await _record_activity(req, user_id)

    async def generate():
        chunks: list[str] = []
        started = time.perf_counter()
        latency_ms: int | None = None
        duration_ms: int | None = None
        try:
            async for content in chat_stream(
                req.messages, req.model, req.temperature, req.mode, system_prompt
            ):
                if latency_ms is None:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(content)
                data = json.dumps({"content": content}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            duration_ms = int((time.perf_counter() - started) * 1000)
            if user_id and chunks:
                await vocabulary_service.record_exposure(user_id, "".join(chunks))
            if user_id and req.conversation_id and chunks:
                await conversation_service.save_message(
                    req.conversation_id,
                    user_id,
                    role="assistant",
                    content="".join(chunks),
                    mode=req.mode,
                    message_id=req.message_id,
                    duration_ms=duration_ms,
                    latency_ms=latency_ms,
                )
            final: dict = {"done": True, "duration_ms": duration_ms}
            if latency_ms is not None:
                final["latency_ms"] = latency_ms
            yield f"data: {json.dumps(final)}\n\n"
        except Exception:  # noqa: BLE001
            logger.exception("Error en /api/chat/stream")
            yield 'data: {"error": "No se pudo completar la respuesta"}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")

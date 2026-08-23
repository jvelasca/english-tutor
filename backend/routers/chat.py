"""Endpoints de chat."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.chat import ChatRequest, ChatResponse
from services.llm import chat_once, chat_stream

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        return await chat_once(req.messages, req.model, req.temperature, req.mode)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"No se pudo hablar con Ollama: {exc}"
        ) from exc


@router.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest) -> StreamingResponse:
    """Emite la respuesta como Server-Sent Events (texto incremental)."""

    async def generate():
        try:
            async for content in chat_stream(
                req.messages, req.model, req.temperature, req.mode
            ):
                data = json.dumps({"content": content}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield 'data: {"done": true}\n\n'
        except Exception as exc:  # noqa: BLE001
            data = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

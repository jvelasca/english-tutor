"""Cliente de Ollama: lógica de chat y listado de modelos."""
from __future__ import annotations

from collections.abc import AsyncIterator

import ollama

from config import DEFAULT_MODE, MODE_PROMPTS
from schemas.chat import ChatMessage, ChatResponse


def system_prompt_for(mode: str) -> str:
    """Devuelve el system prompt del modo; si el modo no existe, usa el de conversación."""
    return MODE_PROMPTS.get(mode, MODE_PROMPTS[DEFAULT_MODE])


def _messages(messages: list[ChatMessage], mode: str = DEFAULT_MODE) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt_for(mode)},
        *[m.model_dump() for m in messages],
    ]


async def chat_once(
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    mode: str = DEFAULT_MODE,
) -> ChatResponse:
    response = await ollama.AsyncClient().chat(
        model=model,
        messages=_messages(messages, mode),
        options={"temperature": temperature},
    )

    message = response.get("message", {})
    return ChatResponse(
        model=model,
        content=message.get("content", "").strip(),
        total_duration_ms=response.get("total_duration"),
        prompt_eval_count=response.get("prompt_eval_count"),
        eval_count=response.get("eval_count"),
    )


async def chat_stream(
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    mode: str = DEFAULT_MODE,
) -> AsyncIterator[str]:
    """Emite el contenido incremental del modelo (un chunk de texto a la vez)."""
    stream = await ollama.AsyncClient().chat(
        model=model,
        messages=_messages(messages, mode),
        options={"temperature": temperature},
        stream=True,
    )
    async for chunk in stream:
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield content


async def list_models() -> list[str]:
    result = await ollama.AsyncClient().list()
    return [m["model"] for m in result.get("models", [])]

"""Cliente de Ollama: lógica de chat y listado de modelos."""
from __future__ import annotations

from collections.abc import AsyncIterator

import ollama

from config import DEFAULT_MODE, MODE_PROMPTS
from schemas.chat import ChatMessage, ChatResponse

_client: ollama.AsyncClient | None = None


def get_client() -> ollama.AsyncClient:
    """Devuelve el cliente Ollama (inyectable para tests)."""
    global _client
    if _client is None:
        _client = ollama.AsyncClient()
    return _client


def set_client(client: ollama.AsyncClient | None) -> None:
    """Sustituye el cliente (DI) para tests. Pasa None para restaurar el por defecto."""
    global _client
    _client = client


def system_prompt_for(mode: str) -> str:
    """Devuelve el system prompt del modo; si el modo no existe, usa el de
    conversación."""
    return MODE_PROMPTS.get(mode, MODE_PROMPTS[DEFAULT_MODE])


def _messages(
    messages: list[ChatMessage],
    mode: str = DEFAULT_MODE,
    system_prompt: str | None = None,
) -> list[dict]:
    prompt = system_prompt if system_prompt is not None else system_prompt_for(mode)
    return [
        {"role": "system", "content": prompt},
        *[m.model_dump() for m in messages],
    ]


async def chat_once(
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    mode: str = DEFAULT_MODE,
    system_prompt: str | None = None,
) -> ChatResponse:
    response = await get_client().chat(
        model=model,
        messages=_messages(messages, mode, system_prompt),
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
    system_prompt: str | None = None,
) -> AsyncIterator[str]:
    """Emite el contenido incremental del modelo (un chunk de texto a la vez)."""
    stream = await get_client().chat(
        model=model,
        messages=_messages(messages, mode, system_prompt),
        options={"temperature": temperature},
        stream=True,
    )
    async for chunk in stream:
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield content


async def list_models() -> list[str]:
    result = await get_client().list()
    return [m["model"] for m in result.get("models", [])]


async def ping() -> bool:
    """Comprueba que Ollama responde."""
    try:
        await get_client().list()
        return True
    except Exception:  # noqa: BLE001
        return False

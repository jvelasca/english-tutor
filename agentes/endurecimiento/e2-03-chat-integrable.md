# Subagente E2.3 — Backend: chat integrable + tests con Ollama mockeado (DI)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Hoy `services/llm.py` instancia `ollama.AsyncClient()` **dentro** de `chat_once`, `chat_stream`,
`list_models` y `ping`, lo que impide testear la integración del chat sin un Ollama real. Añadir
**inyección del cliente** (DI) y tests de integración de `/api/chat` y `/api/chat/stream` con un
cliente Ollama **mockeado** (modo correcto, modo inválido, role inválido, mensajes vacíos,
Ollama caído, error en stream).

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` y `docs/ARQUITECTURA.md`.
- `services/llm.py` actual (LEERLO): `system_prompt_for`, `_messages`, `chat_once`, `chat_stream`,
  `list_models`, `ping` (añadido en E2.2). Los 4 últimos usan `ollama.AsyncClient()` directo.
- `routers/chat.py` importa `from services.llm import chat_once, chat_stream`; `routers/models.py`
  importa `from services.llm import list_models as list_ollama_models`. Estos imports **no cambian**.
- `schemas/chat.py`: `Role = Literal["user", "assistant"]`, `ChatRequest.messages` con
  `min_length=1` y `max_length=MAX_CHAT_MESSAGES`. Ya hay tests en `test_schemas.py` para roles
  y límites (a nivel Pydantic); aquí se prueban **a nivel API**.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. Refactor DI en `services/llm.py`
Añadir un cliente inyectable a nivel de módulo y usarlo en los 4 call sites. El archivo completo
queda así (mantener TODO lo demás idéntico):

```python
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
    response = await get_client().chat(
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
    stream = await get_client().chat(
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
    result = await get_client().list()
    return [m["model"] for m in result.get("models", [])]


async def ping() -> bool:
    """Comprueba que Ollama responde."""
    try:
        await get_client().list()
        return True
    except Exception:  # noqa: BLE001
        return False
```

> Los routers y el health siguen importando las mismas funciones (`chat_once`, `chat_stream`,
> `list_models`, `ping`), así que no hay cambios en `routers/` ni `main.py`.

### 2. Test nuevo `backend/tests/test_chat_integration.py`
Cliente fake + tests de integración. Código completo:

```python
import json

from fastapi.testclient import TestClient

from config import MODE_PROMPTS
from main import app
from services import llm


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _RaisingStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("SECRET-STREAM")


class FakeOllamaClient:
    def __init__(self, content="Hello!", chunks=None, error=None, stream_error=False):
        self.content = content
        self.chunks = chunks
        self.error = error
        self.stream_error = stream_error
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append(
            {"model": model, "messages": messages, "options": options, "stream": stream}
        )
        if self.error:
            raise self.error
        if stream:
            if self.stream_error:
                return _RaisingStream()
            return _FakeStream(self.chunks or [{"message": {"content": self.content}}])
        return {
            "message": {"content": self.content},
            "total_duration": 123,
            "prompt_eval_count": 1,
            "eval_count": 2,
        }

    async def list(self):
        if self.error:
            raise self.error
        return {"models": [{"model": "qwen3.5:9b"}]}


def test_chat_ok_injects_system_prompt_and_mode(monkeypatch):
    fake = FakeOllamaClient(content="Hi there!")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}], "mode": "grammar"},
        )
    assert r.status_code == 200
    assert r.json()["content"] == "Hi there!"
    sent = fake.calls[0]["messages"]
    assert sent[0] == {"role": "system", "content": MODE_PROMPTS["grammar"]}
    assert sent[1]["role"] == "user"
    assert sent[1]["content"] == "Hello"


def test_chat_unknown_mode_falls_back_to_conversation(monkeypatch):
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}], "mode": "nope"},
        )
    assert r.status_code == 200
    assert fake.calls[0]["messages"][0]["content"] == MODE_PROMPTS["conversation"]


def test_chat_stream_ok(monkeypatch):
    fake = FakeOllamaClient(
        chunks=[{"message": {"content": "Hel"}}, {"message": {"content": "lo"}}]
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    assert '{"content": "Hel"}' in r.text
    assert '{"content": "lo"}' in r.text
    assert '"done": true' in r.text


def test_chat_invalid_role_422(monkeypatch):
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "system", "content": "hack"}]}
        )
    assert r.status_code == 422


def test_chat_empty_messages_422(monkeypatch):
    with TestClient(app) as client:
        r = client.post("/api/chat", json={"messages": []})
    assert r.status_code == 422


def test_chat_ollama_unavailable_502_no_leak(monkeypatch):
    fake = FakeOllamaClient(error=RuntimeError("SECRET-INTERNAL"))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "user", "content": "Hi"}]}
        )
    assert r.status_code == 502
    assert "SECRET-INTERNAL" not in r.text


def test_chat_stream_error_emits_error_event_no_leak(monkeypatch):
    fake = FakeOllamaClient(stream_error=True)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    assert '"error"' in r.text
    assert "SECRET-STREAM" not in r.text
```

> `monkeypatch.setattr(llm, "get_client", lambda: fake)` parchea la fábrica; `chat_once`/`chat_stream`
> llaman `get_client()` en runtime, así que usan el fake. Se restaura automáticamente al acabar
> cada test.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (52 previos + 7 nuevos = 59 tests).
- Los tests existentes (`test_robustness.py`, `test_health.py`, `test_modes.py`, etc.) siguen verdes.

## Restricciones
- NO tocar `routers/`, `schemas/`, `main.py`, ni el frontend.
- NO cambiar el contrato de las respuestas de `/api/chat` y `/api/chat/stream`.
- NO añadir dependencias (el fake es código de test).
- Mantener `system_prompt_for`, `_messages`, `chat_once`, `chat_stream`, `list_models`, `ping`
  con las mismas firmas y comportamiento público.

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.

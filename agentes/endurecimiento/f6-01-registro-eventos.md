# Subagente F6.1 — Registro automático de eventos de aprendizaje

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Activar la tabla `learning_events` (que hoy está **dormida**: nadie la alimenta automáticamente)
para que la línea de tiempo de actividad tenga datos reales. Este subagente **no** crea ningún
endpoint nuevo ni toca el frontend; solo hace que los endpoints existentes registren eventos
automáticamente, de forma **determinista y sin LLM**.

La Fase 6 ("progreso pedagógico real") necesita que los eventos existan de verdad: este
subagente es el primer eslabón. Los subagentes F6.2 (progreso histórico) y F6.3 (frontend)
consumirán estos eventos después.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/repositories/learning.py` (LEERLO): `record_event(user_id, event_type, detail) -> dict | None`
  y `list_events(user_id, event_type=None) -> list[dict]`. `record_event` devuelve `None` si el
  usuario no existe (`get_user`). Los tipos válidos son `Literal["message", "exercise",
  "correction", "pronunciation", "conversation"]`.
- `backend/domain/learning.py` (LEERLO): `record_event`/`list_events` async que delegan en el repo
  vía `run_in_threadpool`.
- `backend/routers/chat.py` (LEERLO): `ChatRequest.user_id: str | None = None` (opcional). Tiene
  `_system_prompt(req)` y dos endpoints: `chat(req)` y `chat_stream_endpoint(req)`. Ambos hacen
  `system_prompt = await _system_prompt(req)` al inicio. NO usan `current_user` (leen `req.user_id`).
- `backend/routers/pronunciation.py` (LEERLO): valida el usuario (`404` si no existe), transcribe,
  puntúa y llama `await pronunciation_service.record_pronunciation(user_id, ...)`.
- `backend/routers/conversations.py` (LEERLO): `create(user_id: str)` llama
  `conversation_service.create_conversation(user_id)` y lanza `404` si devuelve `None`.
- Tests existentes que NO debes romper: `tests/test_chat_profile.py` (usa `FakeOllamaClient` y
  `monkeypatch.setattr(llm, "get_client", lambda: fake)`), `tests/test_api_security.py`
  (usa `monkeypatch.setattr("routers.pronunciation.transcribe_audio", lambda audio, language="en": "...")`
  y `client.post("/api/pronunciation", data={...}, files={"file": ("a.webm", b"fake", "audio/webm")})`).
- `backend/main.py`: NO hace falta tocarlo (no se añaden routers nuevos).
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/domain/learning.py` — helper de actividad de chat
Añade un mapeo modo→tipo y una función `record_chat_activity` (mantén el estilo actual del
archivo: `from __future__ import annotations`, `run_in_threadpool`):

```python
_MODE_TO_EVENT = {
    "exercises": "exercise",
    "grammar": "correction",
}


async def record_chat_activity(user_id: str, mode: str, detail: str) -> dict | None:
    """Registra la actividad del chat como evento de aprendizaje según el modo.
    Los modos `exercises` y `grammar` mapean a `exercise` y `correction`; el resto
    (conversation, pronunciation, desconocido) mapea a `message`."""
    event_type = _MODE_TO_EVENT.get(mode, "message")
    return await run_in_threadpool(
        learning_repo.record_event, user_id, event_type, detail
    )
```

> La semántica es coherente con el progreso existente: `exercises` cuenta mensajes con
> `mode='exercises'`, `corrections` con `mode='grammar'`; el resto son mensajes normales. El tipo
> `pronunciation` queda reservado para intentos reales de `/api/pronunciation`.

### 2. `backend/routers/chat.py` — registrar actividad
- Añade el import: `from domain import learning as learning_service`.
- Añade un helper privado (tras `_system_prompt`):

```python
async def _record_activity(req: ChatRequest) -> None:
    """Registra la actividad del alumno si viene un user_id (opcional)."""
    if not req.user_id:
        return
    detail = req.messages[-1].content[:200] if req.messages else ""
    await learning_service.record_chat_activity(req.user_id, req.mode, detail)
```

- En `chat(req)`, justo después de `system_prompt = await _system_prompt(req)`, añade
  `await _record_activity(req)`.
- En `chat_stream_endpoint(req)`, justo después de `system_prompt = await _system_prompt(req)`,
  añade `await _record_activity(req)`.

> IMPORTANTE: no cambies el comportamiento del chat. Si `user_id` es `None` o no existe, no debe
> fallar: `record_chat_activity` devuelve `None` de forma silenciosa y el chat sigue con prompt
> base (igual que en F5.3).

### 3. `backend/routers/pronunciation.py` — registrar intento
- Añade el import: `from domain import learning as learning_service`.
- Justo después de `await pronunciation_service.record_pronunciation(...)`, añade:

```python
    await learning_service.record_event(user_id, "pronunciation", result["expected"])
```

### 4. `backend/routers/conversations.py` — registrar nueva conversación
- Añade el import: `from domain import learning as learning_service`.
- En `create(user_id: str)`, después de comprobar `if conv is None:` y antes del `return conv`,
  añade:

```python
    await learning_service.record_event(user_id, "conversation", conv["id"])
```

### 5. Test nuevo `backend/tests/test_activity.py`
Usa los patrones ya establecidos (`monkeypatch` + `tmp_path`, `TestClient`, `FakeOllamaClient`,
`monkeypatch.setattr("routers.pronunciation.transcribe_audio", ...)`). `_setup` crea la DB temporal
y devuelve los ids de usuario:

```python
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
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
            raise StopAsyncIteration from None


class FakeOllamaClient:
    def __init__(self, content="Hi!"):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        if stream:
            return _FakeStream([{"message": {"content": self.content}}])
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]
```

Añade **al menos** estos tests (8):

- `test_chat_conversation_mode_records_message_event`: `POST /api/chat` con `user_id` y
  `mode="conversation"` (FakeOllamaClient) → `learning_repo.list_events(uid)` contiene un evento
  `type == "message"`.
- `test_chat_exercises_mode_records_exercise_event`: `mode="exercises"` → `type == "exercise"`.
- `test_chat_grammar_mode_records_correction_event`: `mode="grammar"` → `type == "correction"`.
- `test_chat_without_user_id_records_nothing`: `POST /api/chat` sin `user_id` →
  `list_events(uid) == []` (y el chat sigue 200).
- `test_chat_unknown_user_id_records_nothing`: `user_id="no-existe"` → no se registra nada y
  el chat sigue 200.
- `test_pronunciation_records_event`: `POST /api/pronunciation` con `user_id` válido y
  `monkeypatch.setattr("routers.pronunciation.transcribe_audio", lambda audio, language="en": "Hello world")`
  → `list_events(uid)` contiene `type == "pronunciation"` con `detail == "Hello world"`.
- `test_conversation_create_records_event`: `POST /api/conversations?user_id=<uid>` →
  `list_events(uid)` contiene `type == "conversation"`.
- `test_events_isolated_per_user`: la actividad del usuario A no aparece en `list_events(B)`.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 136 tests** (128 previos + 8 nuevos).
- `python -m ruff check .` **sin errores**.
- Los 128 tests existentes siguen verdes. No se modifica ningún test ni módulo existente salvo
  `domain/learning.py`, `routers/chat.py`, `routers/pronunciation.py` y `routers/conversations.py`.

## Restricciones
- NO tocar el frontend.
- NO crear endpoints nuevos ni tocar `main.py`, `schemas/`, `repositories/` ni `services/`.
- NO cambiar firmas públicas existentes ni el comportamiento de `/api/chat`, `/api/pronunciation`
  ni `/api/conversations` (mismos códigos de estado y cuerpos).
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  `run_in_threadpool`, imports ordenados (ruff/isort).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.

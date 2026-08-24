# Subagente E2.1 — Backend: store no bloqueante (threadpool)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Eliminar el bloqueo del event loop: los routers son `async def` pero llaman directamente a
`services/store.py`, que usa `sqlite3` **síncrono**. Con streaming + STT + TTS + manos libres
esas operaciones bloqueantes pueden congelar el servidor. Solución de mínimo riesgo (opción A
del plan): envolver cada llamada a `store.*` en `run_in_threadpool` mediante una capa async.
**`aiosqlite` se difiere a la fase de dominio (Fase 3).**

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (premisas 5, 8, 12) y `docs/ARQUITECTURA.md`.
- `starlette.concurrency.run_in_threadpool` ya se usa en `routers/voz.py` y
  `routers/pronunciation.py` (para `transcribe` y `synthesize`). NO añade dependencia.
- `services/store.py` es **síncrono y debe quedarse intacto** (puro, sin cambios). Sus funciones
  públicas: `create_user`, `list_users`, `get_user`, `create_conversation`, `list_conversations`,
  `get_conversation`, `save_conversation`, `delete_conversation`, `record_pronunciation`,
  `get_progress`, `init_db` (esta última solo se usa en el arranque, NO envolver).
- Archivos a tocar (LEERLOS antes de editar):
  - `backend/services/store.py` — SOLO leer, NO modificar.
  - `backend/dependencies.py` — `current_user` llama a `store.get_user` (síncrono).
  - `backend/routers/users.py` — llama a `store.list_users()` y `store.create_user()`.
  - `backend/routers/conversations.py` — llama a `store.create_conversation/list_conversations/
    get_conversation/save_conversation/delete_conversation`.
  - `backend/routers/progress.py` — llama a `store.get_progress()`.
  - `backend/routers/pronunciation.py` — llama a `store.get_user()` y `store.record_pronunciation()`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. Crear `backend/services/store_async.py`
Capa async que delega en `store` mediante `run_in_threadpool`. Código completo:

```python
"""Envolturas async del store síncrono para no bloquear el event loop."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from services import store


async def create_user(name: str) -> dict:
    return await run_in_threadpool(store.create_user, name)


async def list_users() -> list[dict]:
    return await run_in_threadpool(store.list_users)


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(store.get_user, uid)


async def create_conversation(user_id: str) -> dict | None:
    return await run_in_threadpool(store.create_conversation, user_id)


async def list_conversations(user_id: str) -> list[dict]:
    return await run_in_threadpool(store.list_conversations, user_id)


async def get_conversation(cid: str, user_id: str) -> dict | None:
    return await run_in_threadpool(store.get_conversation, cid, user_id)


async def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    return await run_in_threadpool(store.save_conversation, cid, user_id, title, messages)


async def delete_conversation(cid: str, user_id: str) -> bool:
    return await run_in_threadpool(store.delete_conversation, cid, user_id)


async def record_pronunciation(
    user_id: str, expected: str, heard: str, score: int, level: str
) -> bool:
    return await run_in_threadpool(
        store.record_pronunciation, user_id, expected, heard, score, level
    )


async def get_progress(user_id: str) -> dict:
    return await run_in_threadpool(store.get_progress, user_id)
```

> Importante: llamar a `store.<función>` **dentro** de `run_in_threadpool` (referencia resuelta
> en tiempo de ejecución), para que los `monkeypatch.setattr(store, ...)` de los tests sigan
> funcionando.

### 2. `backend/dependencies.py`
- Sustituir `from services import store` por `from services import store_async`.
- Convertir `current_user` a corrutina y usar `store_async`:
  ```python
  async def current_user(user_id: str = Query(...)) -> dict:
      """Resuelve y valida el perfil activo. 404 si no existe."""
      user = await store_async.get_user(user_id)
      if user is None:
          raise HTTPException(status_code=404, detail="Usuario no encontrado")
      return user
  ```
- Mantener el resto del archivo igual (`read_audio_limited`, `_ALLOWED_AUDIO_TYPES`, etc.).

### 3. `backend/routers/users.py`
- Cambiar el import a `from services import store_async`.
- `list_users`: `return await store_async.list_users()`.
- `create_user`: `return await store_async.create_user(body.name)`.

### 4. `backend/routers/conversations.py`
- Cambiar el import a `from services import store_async`.
- `create`: `conv = await store_async.create_conversation(user_id)`.
- `list_all`: `return await store_async.list_conversations(user_id)`.
- `get_one`: `conv = await store_async.get_conversation(cid, user["id"])`.
- `save`: `conv = await store_async.save_conversation(cid, user["id"], body.title, [...])`.
- `delete`: `if not await store_async.delete_conversation(cid, user["id"]):`.
- **NO cambies** la firma de `create`/`list_all` (siguen recibiendo `user_id: str`). No los
  conviertas a `Depends(current_user)`: eso cambiaría el contrato (list devolvería 404 en vez
  de lista vacía para un usuario inexistente).

### 5. `backend/routers/progress.py`
- Cambiar el import a `from services import store_async`.
- `progress`: `return await store_async.get_progress(user["id"])`.

### 6. `backend/routers/pronunciation.py`
- Cambiar el import de store: sustituir `from services import store` por
  `from services import store_async` (mantener los demás imports).
- `if await store_async.get_user(user_id) is None:` (la validación 404).
- `await store_async.record_pronunciation(...)`.

### 7. Test nuevo `backend/tests/test_store_async.py`
Comprueba que las envolturas delegan correctamente (mismos resultados que el store síncrono).
Usar `asyncio.run(...)` (NO requiere pytest-asyncio). Helper `_setup` igual que el resto de tests:

```python
import asyncio

from services import store, store_async


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()


def test_async_wrappers_match_store(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = asyncio.run(store_async.create_user("A"))
    b = asyncio.run(store_async.create_user("B"))
    assert a["name"] == "A" and b["name"] == "B"

    names = {u["name"] for u in asyncio.run(store_async.list_users())}
    assert {"Usuario", "A", "B"} <= names

    cid = asyncio.run(store_async.create_conversation(a["id"]))["id"]
    assert asyncio.run(store_async.get_conversation(cid, a["id"]))["user_id"] == a["id"]
    assert asyncio.run(store_async.get_conversation(cid, b["id"])) is None

    saved = asyncio.run(
        store_async.save_conversation(cid, a["id"], "T", [{"role": "user", "content": "hi"}])
    )
    assert saved["title"] == "T"

    assert asyncio.run(store_async.record_pronunciation(a["id"], "x", "y", 90, "good")) is True
    assert asyncio.run(store_async.record_pronunciation("no-existe", "x", "y", 90, "good")) is False

    prog = asyncio.run(store_async.get_progress(a["id"]))
    assert prog["pronunciation"]["attempts"] == 1

    assert asyncio.run(store_async.delete_conversation(cid, a["id"])) is True
    assert asyncio.run(store_async.get_conversation(cid, a["id"])) is None
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (47 previos + 1 nuevo = 48 tests).
- Comportamiento de la API idéntico (los tests existentes `test_api_security.py`,
  `test_users.py`, `test_progress.py`, `test_pronunciation.py`, `test_store*.py` siguen verdes).
- Ninguna llamada a `store.*` queda **directa** dentro de un endpoint `async def` (solo vía
  `store_async`).

## Restricciones
- NO modificar `services/store.py` (síncrono, intacto).
- NO tocar `services/llm.py`, `services/stt.py`, `services/tts.py`, `services/pronunciation.py`,
  `schemas/`, `main.py` ni el frontend.
- NO cambiar contratos de respuesta (200/404/etc. se mantienen; `create`/`list_all` conservan
  su firma con `user_id: str`).
- NO añadir dependencias (usar `starlette.concurrency.run_in_threadpool`).
- Mantener el estilo del repo.

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.

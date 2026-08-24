# Subagente E1.3 — Backend: LocalUserContext + tests canónicos de seguridad de API

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Hacer **explícito** el concepto de "usuario autorizado" en la capa HTTP mediante una
dependencia `current_user`, y añadir los **tests canónicos de aislamiento a nivel API** que
la auditoría exige: con el `cid` de otro usuario no se puede leer, modificar ni borrar, y la
pronunciación solo se registra para el usuario declarado.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (premisas 5, 8, 12, 13) y `docs/ARQUITECTURA.md`.
- E1.1 (ya hecho) añadió ownership en `services/store.py` (`get_conversation(cid, user_id)`,
  `save_conversation(cid, user_id, …)`, `delete_conversation(cid, user_id)`, y
  `record_pronunciation(...) -> bool` que valida el usuario) y `routers/conversations.py` y
  `routers/pronunciation.py` ya exigen/validan `user_id`.
- Estado actual de los routers (LEERLOS antes de editar):
  - `backend/routers/progress.py`: hace `if store.get_user(user_id) is None: raise 404` manual.
  - `backend/routers/conversations.py`: `get_one(cid, user_id)`, `save(cid, user_id, body)`,
    `delete(cid, user_id)` reciben `user_id` y lo pasan al store (que aplica ownership).
  - `backend/routers/pronunciation.py`: `user_id: str = Form(...)` y valida `store.get_user`
    al inicio (dejarlo así, NO tocar).
- `backend/services/store.py` tiene `get_user(uid) -> dict | None`.
- Tests: `backend/tests/conftest.py` garantiza el import desde `backend/`. `test_progress.py`
  usa `TestClient(app)` tras hacer `monkeypatch` sobre `store.DATA_DIR`/`store.DB_PATH`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. Nueva dependencia `backend/dependencies.py`
```python
"""Dependencias HTTP compartidas (contexto de usuario local)."""
from __future__ import annotations

from fastapi import HTTPException, Query

from services import store


def current_user(user_id: str = Query(...)) -> dict:
    """Resuelve y valida el perfil activo. 404 si no existe."""
    user = store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user
```

### 2. Refactor DRY (sin cambiar el nombre del query param `user_id`)
- `backend/routers/progress.py`: quitar el chequeo manual; firmar
  `async def progress(user: dict = Depends(current_user))` y llamar
  `store.get_progress(user["id"])`. Importar `Depends` y `current_user`.
- `backend/routers/conversations.py`: en `get_one`, `save` y `delete`, sustituir
  `user_id: str` por `user: dict = Depends(current_user)` y usar `user["id"]` al llamar al
  store. **NO tocar** `create` ni `list_all` (ya filtran/validan; `list_all` devuelve lista
  vacía para usuario inexistente, comportamiento aceptado).

> El query param sigue llamándose `user_id` (la dependencia lo declara como `Query(...)`),
> así que el frontend (E1.2) y los tests existentes NO se rompen.

### 3. Test nuevo `backend/tests/test_api_security.py`
Helper de setup (mismo patrón que `test_progress.py`):
```python
from fastapi.testclient import TestClient
from main import app
from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    cid = store.create_conversation(a)["id"]
    return a, b, cid
```

Tests:
- `test_cannot_read_other_user_conversation`: GET `/{cid}?user_id=B` → 404; GET `/{cid}?user_id=A` → 200.
- `test_cannot_update_other_user_conversation`: PUT `/{cid}?user_id=B` con body JSON
  `{"title": "Hacked", "messages": [{"role": "user", "content": "x"}]}` → 404; luego GET con A
  devuelve el título original (`"Nueva conversación"`).
- `test_cannot_delete_other_user_conversation`: DELETE `/{cid}?user_id=B` → 404; GET con A → 200.
- `test_conversation_crud_unknown_user_404`: GET/PUT/DELETE `/{cid}?user_id=zzz` → 404.
- `test_pronunciation_unknown_user_404`: POST `/api/pronunciation` con
  `data={"expected": "Hello world", "user_id": "no-existe"}` y
  `files={"file": ("a.webm", b"fake", "audio/webm")}` → 404 (el router valida usuario antes
  de transcribir; no hace falta mockear nada para este caso).
- `test_pronunciation_records_only_for_declared_user`: mockear la transcripción para no
  ejecutar Whisper:
  ```python
  monkeypatch.setattr(
      "routers.pronunciation.transcribe_audio",
      lambda audio, language="en": "Hello world",
  )
  ```
  POST con `user_id=A` → 200; después `store.get_progress(a)["pronunciation"]["attempts"] == 1`
  y `store.get_progress(b)["pronunciation"]["attempts"] == 0`.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (los 32 previos + 6 nuevos ≈ 38 tests).
- Los tests de seguridad fallan si se elimina la condición `AND user_id = ?` (regresión real).

## Restricciones
- NO tocar `services/llm.py`, `services/stt.py`, `services/tts.py`,
  `services/pronunciation.py`, `schemas/`, `config.py`, `main.py` ni el frontend.
- NO cambiar el nombre del query param `user_id` ni el `Form` de pronunciación.
- NO añadir dependencias ni autenticación (esto es contexto de usuario local, no JWT/cuentas).
- Mantener estilo del repo: comentarios solo donde aporten; tests deterministas y sin red.

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.

# Subagente F4.1 — Eventos de aprendizaje (tabla + CRUD)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Crear la primera pieza del **Learning Profile** (Fase 4): una línea de tiempo de **eventos de
aprendizaje** por usuario. Cada evento es un registro append-only (no se edita ni se borra) de
algo que hizo el alumno (mensaje, ejercicio, corrección, pronunciación, conversación nueva).
Este subagente solo construye la infraestructura de eventos (tabla + CRUD); el frontend y las
demás entidades (vocabulario, gramática, CEFR) llegan en F4.2–F4.5.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/repositories/db.py` (LEERLO): `_conn()`, `_now()`, `init_db()`, `ping()`. `init_db()`
  crea tablas, aplica migraciones idempotentes, índices, y al final (fase 2) reconstruye
  `conversations` y `pronunciation_attempts` para añadir `FOREIGN KEY user_id → users(id)`.
  `messages` YA usa FK inline en su `CREATE TABLE IF NOT EXISTS`.
- `backend/repositories/users.py`: `get_user(uid) -> dict | None`.
- `backend/repositories/pronunciation.py`: patrón de `record_pronunciation` (valida usuario
  existente con `get_user`, devuelve `False`/`bool`). Este subagente usa el mismo patrón pero
  devolviendo el evento creado (`dict | None`).
- `backend/domain/*.py`: servicios async que delegan en repos con `run_in_threadpool`.
- `backend/routers/progress.py`: usa `Depends(current_user)` (dependencia en
  `backend/dependencies.py` que resuelve `user_id` por query param y devuelve 404 si no existe).
- `backend/main.py`: registra routers con `app.include_router(...)`.
- Tests: usan `monkeypatch.setattr(db, "DATA_DIR", tmp_path)` y
  `monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")` antes de `db.init_db()`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/schemas/learning.py` (nuevo)
```python
"""Esquemas Pydantic de eventos de aprendizaje."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LearningEventType = Literal[
    "message", "exercise", "correction", "pronunciation", "conversation"
]


class LearningEventCreate(BaseModel):
    type: LearningEventType
    detail: str = Field(default="", max_length=500)


class LearningEvent(BaseModel):
    id: int
    user_id: str
    type: LearningEventType
    detail: str
    created_at: str
```

### 2. `backend/repositories/db.py` — tabla + índice
Dentro del primer bloque `with closing(_conn()) as conn, conn:` de `init_db()`, tras la
`CREATE TABLE IF NOT EXISTS pronunciation_attempts`, añade la tabla con **FK inline** (igual que
`messages`):
```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
```
Y junto a los demás índices (tras `idx_pronunciation_user_id`):
```python
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_events_user_id "
            "ON learning_events(user_id)"
        )
```
> No toques las sentencias `CREATE TABLE IF NOT EXISTS` existentes ni la fase 2 de migración.

### 3. `backend/repositories/learning.py` (nuevo)
```python
"""Repositorio de eventos de aprendizaje (SQLite, append-only)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_event(user_id: str, event_type: str, detail: str) -> dict | None:
    """Registra un evento de aprendizaje para un usuario existente. Devuelve el
    evento creado o None si el usuario no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO learning_events (user_id, type, detail, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, event_type, detail, now),
        )
    return {
        "id": cur.lastrowid,
        "user_id": user_id,
        "type": event_type,
        "detail": detail,
        "created_at": now,
    }


def list_events(user_id: str, event_type: str | None = None) -> list[dict]:
    """Lista los eventos de un usuario (más recientes primero), opcionalmente
    filtrados por tipo."""
    with closing(_conn()) as conn:
        if event_type is not None:
            rows = conn.execute(
                "SELECT id, user_id, type, detail, created_at FROM learning_events "
                "WHERE user_id = ? AND type = ? ORDER BY id DESC",
                (user_id, event_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, type, detail, created_at FROM learning_events "
                "WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]
```

### 4. `backend/domain/learning.py` (nuevo)
```python
"""Servicio de dominio de eventos de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import learning as learning_repo


async def record_event(user_id: str, event_type: str, detail: str) -> dict | None:
    return await run_in_threadpool(learning_repo.record_event, user_id, event_type, detail)


async def list_events(user_id: str, event_type: str | None = None) -> list[dict]:
    return await run_in_threadpool(learning_repo.list_events, user_id, event_type)
```

### 5. `backend/routers/learning.py` (nuevo)
```python
"""Endpoints de eventos de aprendizaje."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dependencies import current_user
from domain import learning as learning_service
from schemas.learning import LearningEvent, LearningEventCreate, LearningEventType

router = APIRouter()


@router.post("/api/learning/events", response_model=LearningEvent)
async def record_event(
    body: LearningEventCreate, user: dict = Depends(current_user)
) -> dict:
    return await learning_service.record_event(user["id"], body.type, body.detail)


@router.get("/api/learning/events", response_model=list[LearningEvent])
async def list_events(
    user: dict = Depends(current_user),
    event_type: LearningEventType | None = Query(None),
) -> list[dict]:
    return await learning_service.list_events(user["id"], event_type)
```

### 6. `backend/main.py` — registrar el router
Añade `from routers.learning import router as learning_router` y
`app.include_router(learning_router)`.

### 7. Test nuevo `backend/tests/test_learning_events.py`
Cubre: FK presente en la tabla; `record_event` con usuario inexistente → `None`; append-only
(varios eventos acumulan con ids crecientes); aislamiento entre usuarios; roundtrip ordenado;
filtro por tipo; endpoint 200 + forma; endpoint 404 (usuario inexistente).

Estructura de referencia (usa `monkeypatch`/`tmp_path` como los demás tests):
```python
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}
```
Añade al menos estos tests:
- `test_learning_events_table_has_user_fk`
- `test_record_event_unknown_user_returns_none`
- `test_record_event_append_only`
- `test_list_events_isolation`
- `test_list_events_filter_by_type`
- `test_record_and_list_roundtrip`
- `test_events_endpoint_shape` (POST 200 y GET 200 con body correcto)
- `test_events_endpoint_404`

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 79 tests** (71 previos + 8 nuevos).
- `python -m ruff check .` **sin errores**.
- Los 71 tests existentes siguen verdes (no se modifica ningún test ni módulo existente salvo
  `db.py` y `main.py`).

## Restricciones
- NO tocar el frontend.
- NO tocar `schemas/` existentes, `domain/users.py`, `domain/conversations.py`,
  `domain/pronunciation.py`, `repositories/users.py`, `repositories/conversations.py`,
  `repositories/pronunciation.py`, `services/`, `routers/` existentes (salvo `main.py`).
- NO cambiar las sentencias `CREATE TABLE IF NOT EXISTS` existentes ni la fase 2 de migración.
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  `run_in_threadpool`, respetar isort/ruff (imports ordenados).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.

# Subagente E3.3 — Capa de dominio (Router → Service → Repository)

## Rol
Programador backend Python (FastAPI). Sin acceso a Git ni al frontend.

## Objetivo
Hoy el backend es `Router → Store` (un módulo `services/store.py` "dios" que mezcla conexión,
SQL y reglas). Separarlo en:
- `repositories/` (acceso a datos puro: conexión/esquema + CRUD por entidad).
- `domain/` (servicios asíncronos por entidad, que los routers consumen).
Los routers dejan de depender de `store`/`store_async` y dependen de `domain/`.
Es un **refactor sin cambio de comportamiento**: los 65 tests deben seguir verdes.

## Contexto (autocontenido)
- `backend/services/store.py` (LEERLO): contiene `DATA_DIR`, `DB_PATH`, `DEFAULT_USER_NAME`,
  `_now`, `_conn`, `init_db`, `ping`, y el CRUD: `create_user`, `list_users`, `get_user`,
  `create_conversation`, `list_conversations`, `get_conversation`, `save_conversation`,
  `delete_conversation`, `record_pronunciation`, `get_progress`.
- `backend/services/store_async.py`: envolturas async de `store` vía `run_in_threadpool`.
- Routers: `routers/users.py`, `routers/conversations.py`, `routers/progress.py`,
  `routers/pronunciation.py`, `routers/health.py` importan `store` o `store_async`.
- `dependencies.py` usa `store_async.get_user`. `main.py` usa `from services.store import init_db`.
- Los tests importan `store`/`store_async` y hacen `monkeypatch.setattr(store, "DATA_DIR", ...)`
  y `monkeypatch.setattr(store, "DB_PATH", ...)` antes de `store.init_db()`.

## Tarea detallada

### A. Crear `backend/repositories/` (acceso a datos puro)

Mueve el código de `store.py` a módulos por entidad. **Copia el código tal cual**, solo cambia
los imports. NO cambies ninguna lógica SQL ni de validación.

#### `backend/repositories/__init__.py`
```python
"""Capa de acceso a datos (SQLite, 100% local)."""
```

#### `backend/repositories/db.py`
Contiene TODA la infraestructura (conexión + esquema + migraciones + ping). Copia de
`store.py` las partes: imports, `DB_PATH`, `DEFAULT_USER_NAME`, `_now`, `_conn`, `init_db`,
`ping`:
```python
"""Infraestructura de datos: conexión, esquema y migraciones (SQLite, 100% local)."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from config import DATA_DIR

DB_PATH = DATA_DIR / "tutor.db"

DEFAULT_USER_NAME = "Usuario"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Crea la carpeta y las tablas si no existen. Idempotente y no destructiva."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(_conn()) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pronunciation_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                expected TEXT NOT NULL,
                heard TEXT NOT NULL,
                score INTEGER NOT NULL,
                level TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Migración idempotente: SQLite no soporta ADD COLUMN IF NOT EXISTS.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")

        msg_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "mode" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN mode TEXT")

        if "message_id" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_message_id "
            "ON messages(conversation_id, message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_id "
            "ON conversations(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id "
            "ON pronunciation_attempts(user_id)"
        )

        # Usuario por defecto para no perder conversaciones previas (huérfanas).
        default = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if default is None:
            uid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
                (uid, DEFAULT_USER_NAME, _now()),
            )
            conn.execute(
                "UPDATE conversations SET user_id = ? WHERE user_id IS NULL", (uid,)
            )


def ping() -> bool:
    """Comprueba que SQLite responde (SELECT 1)."""
    try:
        with closing(_conn()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False
```

#### `backend/repositories/users.py`
```python
"""Repositorio de usuarios (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now


def create_user(name: str) -> dict:
    uid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
            (uid, name, now),
        )
    return {"id": uid, "name": name, "created_at": now}


def list_users() -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(uid: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM users WHERE id = ?", (uid,)
        ).fetchone()
    return dict(row) if row is not None else None
```

#### `backend/repositories/conversations.py`
Copia de `store.py` las funciones `create_conversation`, `list_conversations`,
`get_conversation`, `save_conversation`, `delete_conversation`, SIN cambios de lógica:
```python
"""Repositorio de conversaciones y mensajes (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def create_conversation(user_id: str) -> dict | None:
    if get_user(user_id) is None:
        return None
    cid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, "Nueva conversación", now, now, user_id),
        )
    return {
        "id": cid,
        "title": "Nueva conversación",
        "created_at": now,
        "updated_at": now,
        "user_id": user_id,
    }


def list_conversations(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at, user_id FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str, user_id: str) -> dict | None:
    with closing(_conn()) as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at, user_id "
            "FROM conversations WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        msgs = conn.execute(
            "SELECT role, content, mode, message_id FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    result = dict(conv)
    result["messages"] = [
        {
            "id": m["message_id"],
            "role": m["role"],
            "content": m["content"],
            "mode": m["mode"],
        }
        for m in msgs
    ]
    return result


def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    """Guarda título y mensajes de una conversación (solo del propietario).

    Si todos los mensajes traen `id`, el guardado es append-only: se insertan solo los
    mensajes cuyo `id` no existe aún en la conversación (los ya existentes conservan su
    timestamp original). Si algún mensaje no trae `id` (cliente legacy), se mantiene el
    comportamiento anterior de reemplazar todos los mensajes.
    """
    now = _now()
    append_only = all(m.get("id") for m in messages)
    with closing(_conn()) as conn, conn:
        conv = conn.execute(
            "SELECT created_at, user_id FROM conversations "
            "WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ?",
            (title, now, cid, user_id),
        )
        if append_only:
            conn.executemany(
                "INSERT OR IGNORE INTO messages "
                "(conversation_id, role, content, mode, created_at, message_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (cid, m["role"], m["content"], m.get("mode"), now, m.get("id"))
                    for m in messages
                ],
            )
        else:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.executemany(
                "INSERT INTO messages "
                "(conversation_id, role, content, mode, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [(cid, m["role"], m["content"], m.get("mode"), now) for m in messages],
            )
    return {
        "id": cid,
        "title": title,
        "created_at": conv["created_at"],
        "updated_at": now,
        "user_id": conv["user_id"],
    }


def delete_conversation(cid: str, user_id: str) -> bool:
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?", (cid, user_id)
        )
    return cur.rowcount > 0
```

#### `backend/repositories/pronunciation.py`
Copia de `store.py` las funciones `record_pronunciation` y `get_progress`, SIN cambios:
```python
"""Repositorio de pronunciación y progreso (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_pronunciation(
    user_id: str, expected: str, heard: str, score: int, level: str
) -> bool:
    """Persiste un intento de pronunciación evaluado para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO pronunciation_attempts "
            "(user_id, expected, heard, score, level, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, expected, heard, score, level, _now()),
        )
    return True


def get_progress(user_id: str) -> dict:
    """Agrega el progreso del alumno: conversaciones, mensajes, modos y pronunciación."""
    with closing(_conn()) as conn:
        conversations = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        def _count(where: str, params: tuple) -> int:
            return conn.execute(
                "SELECT COUNT(*) FROM messages m "
                "JOIN conversations c ON m.conversation_id = c.id "
                f"WHERE c.user_id = ? {where}",
                (user_id, *params),
            ).fetchone()[0]

        messages = _count("", ())
        exercises = _count("AND m.role = 'user' AND m.mode = 'exercises'", ())
        corrections = _count("AND m.role = 'user' AND m.mode = 'grammar'", ())

        attempts = conn.execute(
            "SELECT COUNT(*) FROM pronunciation_attempts WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        best = conn.execute(
            "SELECT MAX(score) FROM pronunciation_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(score) FROM pronunciation_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        last = conn.execute(
            "SELECT score, level FROM pronunciation_attempts "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    return {
        "user_id": user_id,
        "conversations": conversations,
        "messages": messages,
        "exercises": exercises,
        "corrections": corrections,
        "pronunciation": {
            "attempts": attempts,
            "best": best,
            "average": round(avg, 1) if avg is not None else None,
            "last_score": last["score"] if last is not None else None,
            "last_level": last["level"] if last is not None else None,
        },
    }
```

### B. Crear `backend/domain/` (servicios asíncronos)

#### `backend/domain/__init__.py`
```python
"""Capa de dominio: servicios asíncronos que orquestan la lógica de negocio."""
```

#### `backend/domain/users.py`
```python
"""Servicio de dominio de usuarios."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import users as users_repo


async def create_user(name: str) -> dict:
    return await run_in_threadpool(users_repo.create_user, name)


async def list_users() -> list[dict]:
    return await run_in_threadpool(users_repo.list_users)


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(users_repo.get_user, uid)
```

#### `backend/domain/conversations.py`
```python
"""Servicio de dominio de conversaciones."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import conversations as conversations_repo


async def create_conversation(user_id: str) -> dict | None:
    return await run_in_threadpool(conversations_repo.create_conversation, user_id)


async def list_conversations(user_id: str) -> list[dict]:
    return await run_in_threadpool(conversations_repo.list_conversations, user_id)


async def get_conversation(cid: str, user_id: str) -> dict | None:
    return await run_in_threadpool(conversations_repo.get_conversation, cid, user_id)


async def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    return await run_in_threadpool(
        conversations_repo.save_conversation, cid, user_id, title, messages
    )


async def delete_conversation(cid: str, user_id: str) -> bool:
    return await run_in_threadpool(conversations_repo.delete_conversation, cid, user_id)
```

#### `backend/domain/pronunciation.py`
```python
"""Servicio de dominio de pronunciación y progreso."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import pronunciation as pronunciation_repo


async def record_pronunciation(
    user_id: str, expected: str, heard: str, score: int, level: str
) -> bool:
    return await run_in_threadpool(
        pronunciation_repo.record_pronunciation, user_id, expected, heard, score, level
    )


async def get_progress(user_id: str) -> dict:
    return await run_in_threadpool(pronunciation_repo.get_progress, user_id)
```

### C. Recablear (routers + dependencias + main + health)

Cambia SOLO los imports y las referencias, no la lógica de cada endpoint.

1. `backend/dependencies.py`:
   - `from services import store_async` → `from domain import users as user_service`
   - `await store_async.get_user(user_id)` → `await user_service.get_user(user_id)`

2. `backend/routers/users.py`:
   - `from services import store_async` → `from domain import users as user_service`
   - `store_async.list_users()` → `user_service.list_users()`
   - `store_async.create_user(body.name)` → `user_service.create_user(body.name)`

3. `backend/routers/conversations.py`:
   - `from services import store_async` → `from domain import conversations as conversation_service`
   - reemplaza `store_async.create_conversation/list_conversations/get_conversation/save_conversation/delete_conversation` por `conversation_service.*` (mismos argumentos).

4. `backend/routers/progress.py`:
   - `from services import store_async` → `from domain import pronunciation as pronunciation_service`
   - `store_async.get_progress(user["id"])` → `pronunciation_service.get_progress(user["id"])`

5. `backend/routers/pronunciation.py`:
   - `from services import store_async` → `from domain import pronunciation as pronunciation_service` + `from domain import users as user_service`
   - `store_async.get_user(user_id)` → `user_service.get_user(user_id)`
   - `store_async.record_pronunciation(...)` → `pronunciation_service.record_pronunciation(...)`

6. `backend/routers/health.py`:
   - `from services import llm, store, stt, tts` → `from repositories import db` + `from services import llm, stt, tts`
   - `store.ping` → `db.ping`

7. `backend/main.py`:
   - `from services.store import init_db` → `from repositories.db import init_db`

### D. Eliminar los módulos sustituidos

Borra `backend/services/store.py` y `backend/services/store_async.py`.

### E. Actualizar los tests (cambio mecánico de imports)

Aplica esta TABLA DE REEMPLAZO en los tests. No cambies ninguna aserción ni el número de tests.

| Antes | Después |
|---|---|
| `from services import store` | `from repositories import db` + `from repositories import users as users_repo` + `from repositories import conversations as conversations_repo` + `from repositories import pronunciation as pronunciation_repo` (importa solo los que uses) |
| `store.DATA_DIR` | `db.DATA_DIR` |
| `store.DB_PATH` | `db.DB_PATH` |
| `store.init_db()` | `db.init_db()` |
| `store.list_users()` | `users_repo.list_users()` |
| `store.create_user(x)` | `users_repo.create_user(x)` |
| `store.create_conversation(x)` | `conversations_repo.create_conversation(x)` |
| `store.list_conversations(x)` | `conversations_repo.list_conversations(x)` |
| `store.get_conversation(...)` | `conversations_repo.get_conversation(...)` |
| `store.save_conversation(...)` | `conversations_repo.save_conversation(...)` |
| `store.delete_conversation(...)` | `conversations_repo.delete_conversation(...)` |
| `store.record_pronunciation(...)` | `pronunciation_repo.record_pronunciation(...)` |
| `store.get_progress(...)` | `pronunciation_repo.get_progress(...)` |
| `store.ping` | `db.ping` |

Archivos a actualizar (todos los que toquen `store`):
- `tests/test_store.py`
- `tests/test_store_isolation.py`
- `tests/test_store_append_only.py`
- `tests/test_users.py`
- `tests/test_progress.py`
- `tests/test_api_security.py`
- `tests/test_robustness.py`
- `tests/test_health.py`

**Caso especial `tests/test_store_async.py`**: renómbralo a `tests/test_domain_async.py` y
sustituye:
- `from services import store, store_async` → `from repositories import db` + `from domain import users as user_service, conversations as conversation_service, pronunciation as pronunciation_service`
- `monkeypatch.setattr(store, "DATA_DIR", ...)` → `monkeypatch.setattr(db, "DATA_DIR", ...)`; igual `DB_PATH`.
- `store.init_db()` → `db.init_db()`
- `store_async.X` → el servicio correspondiente (`user_service.create_user`, `user_service.list_users`, `conversation_service.create_conversation`, `conversation_service.get_conversation`, `conversation_service.save_conversation`, `conversation_service.delete_conversation`, `pronunciation_service.record_pronunciation`, `pronunciation_service.get_progress`).
- Renombra la función de test a `test_domain_services_match_repositories` (o similar).

**Nota `test_health.py`**: además del reemplazo de tabla, sus dos `monkeypatch.setattr(store,
"ping", lambda: True)` pasan a `monkeypatch.setattr(db, "ping", lambda: True)`.

**Verificación final anti-referencias**: al terminar, busca que NO quede ninguna referencia a
`store` ni `store_async` en `backend/` salvo en los nombres de archivo borrados. Comando
sugerido (en PowerShell):
```powershell
rg -n "\bstore\b|store_async" backend --glob '*.py'
```
No debe devolver coincidencias (los archivos `services/store*.py` ya no existen).

## Verificación obligatoria (desde `backend/`)
```powershell
python -c "import main"
python -m pytest tests/ -q
python -m ruff check .
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 65 tests** (el mismo número; es un refactor puro).
- `python -m ruff check .` **sin errores** (respeta `isort` en los imports nuevos; si ruff
  reporta orden de imports o E501, corrígelo de forma mecánica).
- `services/store.py` y `services/store_async.py` eliminados; routers dependen de `domain/`;
  el acceso a datos vive en `repositories/`.

## Restricciones
- NO tocar el frontend, `schemas/`, `config.py`, `services/llm.py`, `services/stt.py`,
  `services/tts.py`, `services/pronunciation.py` (scoring).
- NO cambiar el comportamiento: mismas firmas, mismos retornos, mismo número de tests.
- NO cambiar ninguna consulta SQL ni validación de ownership (solo moverlas de archivo).
- Mantener el estilo (docstrings en español, `from __future__ import annotations`,
  `run_in_threadpool`).

## Salida
Lista de archivos creados/modificados/eliminados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, el resultado de `rg "\bstore\b"`,
y cualquier desviación.

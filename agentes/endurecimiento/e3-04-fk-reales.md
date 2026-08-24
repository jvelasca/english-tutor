# Subagente E3.4 — FKs reales (user_id → users.id)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Las tablas `conversations` y `pronunciation_attempts` tienen `user_id` pero **sin** Foreign Key
real hacia `users(id)`. Añadir esas FKs con una **migración idempotente** (SQLite no permite
`ALTER TABLE ADD CONSTRAINT`, así que hay que reconstruir la tabla). Es defensa en profundidad:
la capa de aplicación ya valida ownership, la FK lo garantiza en la base.

## Contexto (autocontenido)
- `backend/repositories/db.py` (LEERLO): contiene `_conn()`, `init_db()`, `ping()`. `_conn()`
  hace `PRAGMA foreign_keys=ON`. `init_db()` crea las tablas, aplica migraciones idempotentes
  de columnas (`user_id`, `mode`, `message_id`), índices, y crea el usuario por defecto
  asignando conversaciones huérfanas. `messages` YA tiene FK `conversation_id →
  conversations(id) ON DELETE CASCADE`.
- `backend/repositories/users.py`, `conversations.py`, `pronunciation.py`: el CRUD.
- Tests de migración existentes simulan esquemas legacy (sin `user_id`/`mode`) y luego llaman
  `init_db()`; deben seguir pasando.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/repositories/db.py` — `_conn` con parámetro
Sustituye:
```python
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```
por:
```python
def _conn(foreign_keys: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys=ON")
    return conn
```
> Con `foreign_keys=False` la conexión queda con FKs desactivadas (default de SQLite), necesario
> para reconstruir tablas sin que `DROP TABLE conversations` dispare el `ON DELETE CASCADE` de
> `messages` ni errores por referencias.

### 2. `backend/repositories/db.py` — fase 2 en `init_db`
Al final de `init_db`, justo DESPUÉS del bloque `with closing(_conn()) as conn, conn:` (es
decir, después del bloque del usuario por defecto, como bloque independiente), añade:
```python
    # Fase 2: FKs reales (reconstrucción idempotente con foreign_keys OFF).
    with closing(_conn(foreign_keys=False)) as conn, conn:
        _migrate_conversations_fk(conn)
        _migrate_pronunciation_fk(conn)
```

### 3. `backend/repositories/db.py` — helpers de migración
Añade estas tres funciones entre `init_db` y `ping`:
```python
def _has_user_fk(conn: sqlite3.Connection, table: str) -> bool:
    return any(
        row[3] == "user_id" for row in conn.execute(f"PRAGMA foreign_key_list({table})")
    )


def _migrate_conversations_fk(conn: sqlite3.Connection) -> None:
    """Añade FK user_id → users(id) reconstruyendo la tabla (idempotente)."""
    if _has_user_fk(conn, "conversations"):
        return
    conn.execute(
        """
        CREATE TABLE conversations_new (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "INSERT INTO conversations_new (id, title, created_at, updated_at, user_id) "
        "SELECT id, title, created_at, updated_at, user_id FROM conversations"
    )
    conn.execute("DROP TABLE conversations")
    conn.execute("ALTER TABLE conversations_new RENAME TO conversations")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"
    )


def _migrate_pronunciation_fk(conn: sqlite3.Connection) -> None:
    """Añade FK user_id → users(id) reconstruyendo la tabla (idempotente)."""
    if _has_user_fk(conn, "pronunciation_attempts"):
        return
    conn.execute(
        """
        CREATE TABLE pronunciation_attempts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            expected TEXT NOT NULL,
            heard TEXT NOT NULL,
            score INTEGER NOT NULL,
            level TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "INSERT INTO pronunciation_attempts_new "
        "(id, user_id, expected, heard, score, level, created_at) "
        "SELECT id, user_id, expected, heard, score, level, created_at "
        "FROM pronunciation_attempts"
    )
    conn.execute("DROP TABLE pronunciation_attempts")
    conn.execute("ALTER TABLE pronunciation_attempts_new RENAME TO pronunciation_attempts")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id "
        "ON pronunciation_attempts(user_id)"
    )
```

> NOTA: no cambies las sentencias `CREATE TABLE IF NOT EXISTS` existentes. La FK se añade solo
> por reconstrucción, de forma uniforme para BD nuevas y legacy.

### 4. Test nuevo `backend/tests/test_foreign_keys.py`
```python
import sqlite3

import pytest

from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_conversations_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("conversations")


def test_pronunciation_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("pronunciation_attempts")


def test_conversation_fk_enforced(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at, user_id) "
                "VALUES (?, ?, ?, ?, ?)",
                ("c1", "t", "2024-01-01", "2024-01-01", "no-existe"),
            )
    finally:
        conn.close()


def test_pronunciation_fk_enforced(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO pronunciation_attempts "
                "(user_id, expected, heard, score, level, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("no-existe", "Hi", "Hi", 90, "good", "2024-01-01"),
            )
    finally:
        conn.close()


def test_fk_migration_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda llamada no debe fallar ni duplicar
    assert ("users", "user_id") in _fk_targets("conversations")
    assert ("users", "user_id") in _fk_targets("pronunciation_attempts")


def test_fk_migration_from_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Base antigua: conversations sin user_id y messages sin mode/message_id.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE conversations ("
        "id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, "
        "role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) "
        "VALUES ('old1', 'vieja', '2024-01-01', '2024-01-01')"
    )
    conn.commit()
    conn.close()

    db.init_db()

    assert ("users", "user_id") in _fk_targets("conversations")
    uid = users_repo.list_users()[0]["id"]
    assert conversations_repo.get_conversation("old1", uid)["user_id"] == uid
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 71 tests** (65 previos + 6 nuevos).
- `python -m ruff check .` **sin errores**.
- Los tests de migración legacy existentes (`test_users.py`, `test_progress.py`) siguen verdes.

## Restricciones
- NO tocar el frontend ni `domain/` ni `routers/` ni `schemas/`.
- NO cambiar el comportamiento del CRUD (las FKs son defensa en profundidad; la validación en
  `repositories/users.py`/`conversations.py`/`pronunciation.py` se mantiene).
- NO cambiar las sentencias `CREATE TABLE IF NOT EXISTS` existentes.
- Mantener el estilo (docstrings en español, `from __future__ import annotations`).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.

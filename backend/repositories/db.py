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


def _conn(foreign_keys: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if foreign_keys:
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

    # Fase 2: FKs reales (reconstrucción idempotente con foreign_keys OFF).
    with closing(_conn(foreign_keys=False)) as conn, conn:
        _migrate_conversations_fk(conn)
        _migrate_pronunciation_fk(conn)


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
    conn.execute(
        "ALTER TABLE pronunciation_attempts_new RENAME TO pronunciation_attempts"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id "
        "ON pronunciation_attempts(user_id)"
    )


def ping() -> bool:
    """Comprueba que SQLite responde (SELECT 1)."""
    try:
        with closing(_conn()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False

"""Persistencia de usuarios y conversaciones en SQLite (stdlib, 100% local)."""
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
            "SELECT role, content, mode FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    result = dict(conv)
    result["messages"] = [dict(m) for m in msgs]
    return result


def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    """Reemplaza título y mensajes de una conversación existente (solo del
    propietario)."""
    now = _now()
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
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        conn.executemany(
            "INSERT INTO messages (conversation_id, role, content, mode, created_at) "
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
    """Agrega el progreso del alumno: conversaciones, mensajes, modos y
    pronunciación."""
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
            "SELECT MAX(score) FROM pronunciation_attempts "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(score) FROM pronunciation_attempts "
            "WHERE user_id = ?",
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


def ping() -> bool:
    """Comprueba que SQLite responde (SELECT 1)."""
    try:
        with closing(_conn()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False

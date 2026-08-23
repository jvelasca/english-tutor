"""Persistencia de conversaciones en SQLite (stdlib, 100% local)."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from config import DATA_DIR

DB_PATH = DATA_DIR / "tutor.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Crea la carpeta y las tablas si no existen. Idempotente."""
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


def create_conversation() -> dict:
    cid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (cid, "Nueva conversación", now, now),
        )
    return {"id": cid, "title": "Nueva conversación", "created_at": now, "updated_at": now}


def list_conversations() -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations "
            "ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str) -> dict | None:
    with closing(_conn()) as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (cid,),
        ).fetchone()
        if conv is None:
            return None
        msgs = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    result = dict(conv)
    result["messages"] = [dict(m) for m in msgs]
    return result


def save_conversation(cid: str, title: str, messages: list[dict]) -> dict | None:
    """Reemplaza título y mensajes de una conversación existente."""
    now = _now()
    with closing(_conn()) as conn, conn:
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (cid,)
        ).fetchone()
        if exists is None:
            return None
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, cid),
        )
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        conn.executemany(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            [(cid, m["role"], m["content"], now) for m in messages],
        )
    return {"id": cid, "title": title, "created_at": now, "updated_at": now}


def delete_conversation(cid: str) -> bool:
    with closing(_conn()) as conn, conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    return cur.rowcount > 0

"""Lectura de estado: HTTP (health) y SQLite (contadores/usuarios), solo lectura."""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from contextlib import closing

from core import backend_url, frontend_url


def _get_json(url: str, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def fetch_health() -> dict | None:
    """Devuelve el dict de /api/health/dependencies, o None si no hay backend."""
    return _get_json(backend_url() + "/api/health/dependencies")


def fetch_frontend() -> bool:
    """True si el frontend responde (GET /)."""
    try:
        with urllib.request.urlopen(frontend_url(), timeout=1.5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _connect_readonly(path: str) -> sqlite3.Connection:
    uri_path = path.replace("\\", "/")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_db_counts(db_path: str) -> dict:
    """Contadores globales de la BD (0 si no se puede abrir)."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {
            "users": int(users),
            "conversations": int(conversations),
            "messages": int(messages),
        }
    except Exception:  # noqa: BLE001
        return {"users": 0, "conversations": 0, "messages": 0}


def read_users(db_path: str) -> list[tuple]:
    """Lista de (id, name, conversations, messages) por usuario."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.name,
                       COUNT(DISTINCT c.id) AS conversations,
                       COUNT(m.id) AS messages
                FROM users u
                LEFT JOIN conversations c ON c.user_id = u.id
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY u.id
                ORDER BY u.name
                """
            ).fetchall()
        return [(r["id"], r["name"], r["conversations"], r["messages"]) for r in rows]
    except Exception:  # noqa: BLE001
        return []

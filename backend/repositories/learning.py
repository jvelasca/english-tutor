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

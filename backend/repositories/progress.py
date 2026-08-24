"""Repositorio de progreso histórico (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn


def activity_events(user_id: str) -> list[dict]:
    """Devuelve los eventos de actividad crudos del usuario (mensajes con su modo
    y pronunciaciones), con su timestamp ISO."""
    with closing(_conn()) as conn:
        msgs = conn.execute(
            "SELECT m.created_at, m.mode FROM messages m "
            "JOIN conversations c ON m.conversation_id = c.id "
            "WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()
        pron = conn.execute(
            "SELECT created_at FROM pronunciation_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    events = [
        {"created_at": r["created_at"], "kind": "message", "mode": r["mode"]}
        for r in msgs
    ]
    events += [
        {"created_at": r["created_at"], "kind": "pronunciation", "mode": None}
        for r in pron
    ]
    return events

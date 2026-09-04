"""Repositorio de las rutas de conversation (SQLite).

Almacena los intentos de conversaciones guiadas terminadas
(`conversation_route_attempts`). El estado por diálogo se deriva en vivo desde
esa tabla, igual que en las demás rutas (sin migración adicional).
"""
from __future__ import annotations

import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    dialogue_id: str,
    level: str,
    overall: float,
    passed: bool,
    criteria: dict | None = None,
    topic: str = "",
) -> bool:
    """Persiste un intento de conversación guiada para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO conversation_route_attempts "
            "(user_id, dialogue_id, level, overall, passed, criteria_json, "
            "topic, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                dialogue_id,
                level,
                float(overall),
                int(bool(passed)),
                json.dumps(criteria or {}),
                topic,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de conversación del usuario, en orden."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT dialogue_id, level, overall, passed, criteria_json, topic, "
            "created_at FROM conversation_route_attempts "
            "WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def passed_dialogue_ids(user_id: str) -> set[str]:
    """Ids de diálogos dominados al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT dialogue_id FROM conversation_route_attempts "
            "WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchall()
    return {r["dialogue_id"] for r in rows}

"""Repositorio de las rutas de grammar (SQLite).

Almacena los intentos MC deterministas contra checks del currículo
(`grammar_route_attempts`). El estado por check se deriva en vivo desde esa
tabla, igual que en las demás rutas (sin migración adicional).
"""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    check_id: str,
    level: str,
    score: float,
    passed: bool,
    topic: str = "",
) -> bool:
    """Persiste un intento MC de grammar para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO grammar_route_attempts "
            "(user_id, check_id, level, score, passed, topic, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                check_id,
                level,
                float(score),
                int(bool(passed)),
                topic,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos MC del usuario, en orden."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT check_id, level, score, passed, topic, created_at "
            "FROM grammar_route_attempts "
            "WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def passed_check_ids(user_id: str) -> set[str]:
    """Ids de checks acertados al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT check_id FROM grammar_route_attempts "
            "WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchall()
    return {r["check_id"] for r in rows}

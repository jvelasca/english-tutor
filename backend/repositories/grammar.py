"""Repositorio de errores gramaticales recurrentes (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_errors(user_id: str, errors: list[dict]) -> bool:
    """Incrementa el recuento de cada error detectado (upsert por regla).
    Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not errors:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO grammar_errors "
            "(user_id, rule, message, count, last_example, last_seen) "
            "VALUES (?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(user_id, rule) DO UPDATE SET "
            "count = count + 1, last_example = excluded.last_example, "
            "last_seen = excluded.last_seen",
            [
                (user_id, e["rule"], e["message"], e.get("example", ""), now)
                for e in errors
            ],
        )
    return True


def get_recurring_errors(user_id: str) -> list[dict]:
    """Devuelve los errores recurrentes del usuario ordenados por recuento (desc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT rule, message, count, last_example, last_seen "
            "FROM grammar_errors WHERE user_id = ? ORDER BY count DESC, rule ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]

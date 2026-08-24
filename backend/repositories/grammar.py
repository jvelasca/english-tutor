"""Repositorio de errores gramaticales recurrentes (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_errors(user_id: str, errors: list[dict]) -> bool:
    """Incrementa el recuento de cada error detectado (upsert por regla) y guarda
    su confianza y estado de confirmación. Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not errors:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO grammar_errors "
            "(user_id, rule, message, count, last_example, last_seen, "
            " confidence, source, confirmed) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, rule) DO UPDATE SET "
            "count = count + 1, last_example = excluded.last_example, "
            "last_seen = excluded.last_seen, confidence = excluded.confidence, "
            "source = excluded.source, confirmed = excluded.confirmed",
            [
                (
                    user_id,
                    e["rule"],
                    e["message"],
                    e.get("example", ""),
                    now,
                    e.get("confidence", 1.0),
                    e.get("source", "heuristic"),
                    1 if e.get("confirmed", True) else 0,
                )
                for e in errors
            ],
        )
    return True


def get_recurring_errors(user_id: str) -> list[dict]:
    """Devuelve los errores recurrentes del usuario ordenados por recuento (desc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT rule, message, count, last_example, last_seen, "
            "confidence, source, confirmed "
            "FROM grammar_errors WHERE user_id = ? ORDER BY count DESC, rule ASC",
            (user_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["confirmed"] = bool(d["confirmed"])
        result.append(d)
    return result

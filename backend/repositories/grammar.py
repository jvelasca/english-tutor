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
            "(user_id, rule, message, count, last_example, last_seen, first_seen, "
            " confidence, source, confirmed, correct_after, streak, mastered) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, 0, 0, 0) "
            "ON CONFLICT(user_id, rule) DO UPDATE SET "
            "count = count + 1, last_example = excluded.last_example, "
            "last_seen = excluded.last_seen, confidence = excluded.confidence, "
            "source = excluded.source, confirmed = excluded.confirmed, "
            "streak = 0, mastered = 0",
            [
                (
                    user_id,
                    e["rule"],
                    e["message"],
                    e.get("example", ""),
                    now,
                    now,
                    e.get("confidence", 1.0),
                    e.get("source", "heuristic"),
                    1 if e.get("confirmed", True) else 0,
                )
                for e in errors
            ],
        )
    return True


def record_correct_usage(user_id: str, rule: str, mastery_streak: int) -> bool:
    """Registra evidencia positiva (uso correcto) de una regla: incrementa
    `correct_after` y `streak`, y marca `mastered` al alcanzar el umbral.
    Devuelve False si el usuario no existe o la regla no está registrada."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE grammar_errors SET "
            "correct_after = correct_after + 1, streak = streak + 1, "
            "mastered = CASE WHEN streak + 1 >= ? THEN 1 ELSE mastered END "
            "WHERE user_id = ? AND rule = ?",
            (mastery_streak, user_id, rule),
        )
    return cur.rowcount > 0


def get_recurring_errors(user_id: str) -> list[dict]:
    """Devuelve los errores recurrentes del usuario ordenados por recuento (desc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT rule, message, count, last_example, last_seen, first_seen, "
            "confidence, source, confirmed, correct_after, streak, mastered "
            "FROM grammar_errors WHERE user_id = ? ORDER BY count DESC, rule ASC",
            (user_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["confirmed"] = bool(d["confirmed"])
        d["mastered"] = bool(d["mastered"])
        result.append(d)
    return result

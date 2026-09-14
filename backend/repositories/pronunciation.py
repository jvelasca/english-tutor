"""Repositorio de pronunciación y progreso (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


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


def list_attempts(user_id: str) -> list[dict]:
    """Intentos de pronunciación del usuario en orden de creación (V3.62).

    Alimenta el estado por modalidad × competencia (`services.skill_state`), que
    lee `score` (0..100 en este esquema) y `created_at`. Solo lectura: la tabla no
    se migra ni se toca.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT expected, heard, score, level, created_at "
            "FROM pronunciation_attempts WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


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
        user_messages = _count("AND m.role = 'user'", ())
        exercises = _count("AND m.role = 'user' AND m.mode = 'exercises'", ())
        corrections = _count("AND m.role = 'user' AND m.mode = 'grammar'", ())

        attempts = conn.execute(
            "SELECT COUNT(*) FROM pronunciation_attempts WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        best = conn.execute(
            "SELECT MAX(score) FROM pronunciation_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(score) FROM pronunciation_attempts WHERE user_id = ?",
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
        "user_messages": user_messages,
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

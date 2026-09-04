"""Repositorio de las rutas de pronunciation (SQLite).

Almacena los intentos read-aloud (`pronunciation_route_attempts`). El estado por
frase (unseen/failed/mastered) se deriva en vivo desde esa tabla, igual que en
listening/speaking.
"""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    phrase_id: str,
    level: str,
    score: int,
    passed: bool,
    difficulty: int = 1,
    topic: str = "",
) -> bool:
    """Persiste un intento de pronunciation read-aloud de un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO pronunciation_route_attempts "
            "(user_id, phrase_id, level, score, passed, difficulty, topic, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                phrase_id,
                level,
                int(score),
                int(bool(passed)),
                difficulty,
                topic,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de pronunciation del usuario, por orden."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT phrase_id, level, score, passed, difficulty, topic, created_at "
            "FROM pronunciation_route_attempts WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def passed_phrase_ids(user_id: str) -> set[str]:
    """Ids de frases superadas al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT phrase_id FROM pronunciation_route_attempts "
            "WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchall()
    return {r["phrase_id"] for r in rows}

"""Repositorio de vocabulario (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_words(user_id: str, words: list[str]) -> bool:
    """Incrementa el recuento de cada palabra para el usuario (upsert). Devuelve
    False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO vocabulary "
            "(user_id, word, occurrences, first_seen, last_seen) "
            "VALUES (?, ?, 1, ?, ?) "
            "ON CONFLICT(user_id, word) DO UPDATE SET "
            "occurrences = occurrences + 1, last_seen = excluded.last_seen",
            [(user_id, w, now, now) for w in words],
        )
    return True


def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario ordenado por apariciones (desc) y
    palabra (asc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, occurrences, first_seen, last_seen FROM vocabulary "
            "WHERE user_id = ? ORDER BY occurrences DESC, word ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]

"""Repositorio del perfil de aprendizaje (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def get_profile(user_id: str) -> dict | None:
    """Devuelve el perfil almacenado o None si no existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, cefr_level, updated_at FROM learning_profile "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_cefr(user_id: str, level: str) -> dict | None:
    """Persiste (upsert) el nivel CEFR del usuario. Devuelve None si el usuario
    no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile (user_id, cefr_level, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "cefr_level = excluded.cefr_level, updated_at = excluded.updated_at",
            (user_id, level, now),
        )
    return {"user_id": user_id, "cefr_level": level, "updated_at": now}

"""Repositorio de preferencias de usuario (clave/valor en SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now


def get_settings(user_id: str) -> dict[str, str]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_settings(user_id: str, settings: dict[str, str]) -> dict[str, str]:
    """Guarda (upsert) las claves indicadas y devuelve el mapa completo."""
    now = _now()
    with closing(_conn()) as conn, conn:
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO settings (user_id, key, value, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET "
                "value = excluded.value, updated_at = excluded.updated_at",
                (user_id, key, value, now),
            )
    return get_settings(user_id)

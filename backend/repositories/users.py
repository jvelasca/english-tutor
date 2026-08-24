"""Repositorio de usuarios (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now

_COLUMNS = "id, name, avatar_color, avatar_emoji, avatar_image, created_at"


def create_user(name: str) -> dict:
    uid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
            (uid, name, now),
        )
    return {
        "id": uid,
        "name": name,
        "avatar_color": "",
        "avatar_emoji": "",
        "avatar_image": "",
        "created_at": now,
    }


def list_users() -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM users ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(uid: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM users WHERE id = ?", (uid,)
        ).fetchone()
    return dict(row) if row is not None else None


def update_user(
    uid: str,
    *,
    name: str | None = None,
    avatar_color: str | None = None,
    avatar_emoji: str | None = None,
    avatar_image: str | None = None,
) -> dict | None:
    """Actualiza solo los campos indicados. Devuelve el usuario actualizado o
    None si no existe."""
    existing = get_user(uid)
    if existing is None:
        return None
    new_name = name if name is not None else existing["name"]
    new_color = avatar_color if avatar_color is not None else existing["avatar_color"]
    new_emoji = avatar_emoji if avatar_emoji is not None else existing["avatar_emoji"]
    new_image = avatar_image if avatar_image is not None else existing["avatar_image"]
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET name = ?, avatar_color = ?, avatar_emoji = ?, "
            "avatar_image = ? WHERE id = ?",
            (new_name, new_color, new_emoji, new_image, uid),
        )
    return get_user(uid)

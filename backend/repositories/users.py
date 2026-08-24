"""Repositorio de usuarios (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now


def create_user(name: str) -> dict:
    uid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
            (uid, name, now),
        )
    return {"id": uid, "name": name, "created_at": now}


def list_users() -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(uid: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM users WHERE id = ?", (uid,)
        ).fetchone()
    return dict(row) if row is not None else None

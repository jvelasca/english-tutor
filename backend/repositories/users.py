"""Repositorio de usuarios (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now

_COLUMNS = "id, name, avatar_color, avatar_emoji, avatar_image, is_test, created_at"


def create_user(name: str, is_test: bool = False) -> dict:
    uid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users (id, name, created_at, is_test) VALUES (?, ?, ?, ?)",
            (uid, name, now, 1 if is_test else 0),
        )
    return {
        "id": uid,
        "name": name,
        "avatar_color": "",
        "avatar_emoji": "",
        "avatar_image": "",
        "is_test": is_test,
        "created_at": now,
    }


def list_users(include_test: bool = False) -> list[dict]:
    """Perfiles locales. Por defecto EXCLUYE los marcados como prueba.

    V3.52.1: los perfiles de test (p. ej. «Visual Tester» de los tests visuales
    de Playwright) no deben aparecer en el selector de la app. Con
    `include_test=True` se listan también (lo usan los propios tests para
    localizar/limpiar su perfil).
    """
    where = "" if include_test else " WHERE is_test = 0"
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM users{where} ORDER BY created_at ASC"
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


def delete_test_user(uid: str) -> bool:
    """Borra un perfil de PRUEBA y sus filas dependientes (V3.52.1).

    Lo usa el teardown de los tests visuales para no dejar residuos en la BD
    local. Muy acotado: si el id no está marcado como `is_test = 1` devuelve
    False sin tocar nada (nunca puede borrar un perfil real). Las tablas con
    `user_id` se enumeran dinámicamente, igual que
    `scripts/purge_virtual_testers.py`, porque el esquema no tiene
    `ON DELETE CASCADE` (salvo `messages`); se abre la conexión con las FKs
    desactivadas, como el script de purga, para que el orden de borrado no
    importe.
    """
    with closing(_conn(foreign_keys=False)) as conn, conn:
        row = conn.execute("SELECT is_test FROM users WHERE id = ?", (uid,)).fetchone()
        if row is None or not row["is_test"]:
            return False
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]
        tables = []
        for name in names:
            columns = {
                c[1] for c in conn.execute(f'PRAGMA table_info("{name}")')
            }
            if "user_id" in columns:
                tables.append(name)
        conversation_ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM conversations WHERE user_id = ?", (uid,)
            )
        ]
        if conversation_ids:
            marks = ", ".join("?" for _ in conversation_ids)
            conn.execute(
                f"DELETE FROM messages WHERE conversation_id IN ({marks})",
                conversation_ids,
            )
        for name in tables:
            safe = '"' + name.replace('"', '""') + '"'
            conn.execute(f"DELETE FROM {safe} WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ? AND is_test = 1", (uid,))
        return True

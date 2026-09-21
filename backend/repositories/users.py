"""Repositorio de usuarios (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now

_COLUMNS = (
    "id, name, avatar_color, avatar_emoji, avatar_image, is_test, created_at, status"
)

# V3.76: `pin_hash` se LEE para saber si el perfil tiene PIN, pero **nunca** sale
# en el diccionario del perfil: de él solo se deriva `has_pin`. Exponerlo en
# `GET /api/users` no aporta nada y le da material al atacante.
_PIN_COLUMN = "pin_hash"

# V3.77: estado de servicio del perfil. Son los dos únicos valores válidos y
# viven aquí (no en el esquema) para que el repositorio los pueda comparar sin
# inventarse cadenas sueltas por el código.
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
STATUSES = (STATUS_ACTIVE, STATUS_DISABLED)


def _row_to_user(row: object) -> dict:
    """Fila de `users` → perfil de la API, con `has_pin` en vez del hash."""
    data = dict(row)  # type: ignore[arg-type]
    pin_hash = data.pop(_PIN_COLUMN, "") or ""
    data["has_pin"] = bool(pin_hash)
    return data


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
        "has_pin": False,
        "created_at": now,
        "status": STATUS_ACTIVE,
    }


def list_users(
    include_test: bool = False, include_disabled: bool = False
) -> list[dict]:
    """Perfiles locales. Por defecto EXCLUYE los de prueba y los desactivados.

    V3.52.1: los perfiles de test (p. ej. «Visual Tester» de los tests visuales
    de Playwright) no deben aparecer en el selector de la app. Con
    `include_test=True` se listan también (lo usan los propios tests para
    localizar/limpiar su perfil).

    V3.77: un perfil **desactivado** tampoco aparece en el selector —eso es
    justo lo que significa desactivar— y `include_disabled=True` lo recupera
    para el lanzador, que es quien puede reactivarlo o purgarlo.
    """
    clauses: list[str] = []
    if not include_test:
        clauses.append("is_test = 0")
    if not include_disabled:
        clauses.append(f"status = '{STATUS_ACTIVE}'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS}, {_PIN_COLUMN} FROM users{where} "
            "ORDER BY created_at ASC"
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def get_user(uid: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS}, {_PIN_COLUMN} FROM users WHERE id = ?", (uid,)
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def get_pin_hash(uid: str) -> str | None:
    """Hash del PIN del perfil (`""` si no tiene), o `None` si no existe.

    Consulta aparte a propósito: separa «quién es este perfil» (lo que la API
    sirve) de «con qué secreto entra» (lo que solo mira la apertura de sesión).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_PIN_COLUMN} FROM users WHERE id = ?", (uid,)
        ).fetchone()
    if row is None:
        return None
    return row[_PIN_COLUMN] or ""


def set_pin_hash(uid: str, pin_hash: str) -> bool:
    """Escribe (o retira, con `""`) el hash del PIN. `False` si no existe."""
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (pin_hash, uid))
    return True


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


def set_status(uid: str, status: str) -> dict | None:
    """Desactiva o reactiva un perfil. `None` si no existe o el estado no vale.

    Desactivar es la mitad **reversible** de un borrado: el perfil sale del
    selector y no puede abrir sesión, pero no se toca ni una fila de su
    evidencia. Es el camino por defecto del webmaster.
    """
    if status not in STATUSES:
        return None
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, uid))
    return get_user(uid)


def _purge_user_rows(conn, uid: str) -> None:
    """Borra las filas de TODAS las tablas con `user_id` para un perfil.

    Se enumeran dinámicamente (igual que `scripts/purge_virtual_testers.py`)
    porque el esquema **no** tiene `ON DELETE CASCADE` salvo en `messages`, y se
    abre la conexión con las FKs desactivadas para que el orden de borrado no
    importe. No borra la fila de `users`: eso lo decide quien llama.
    """
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    ]
    tables = []
    for name in names:
        columns = {c[1] for c in conn.execute(f'PRAGMA table_info("{name}")')}
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


def delete_test_user(uid: str) -> bool:
    """Borra un perfil de PRUEBA y sus filas dependientes (V3.52.1).

    Lo usa el teardown de los tests visuales para no dejar residuos en la BD
    local. Muy acotado: si el id no está marcado como `is_test = 1` devuelve
    False sin tocar nada (nunca puede borrar un perfil real).
    """
    with closing(_conn(foreign_keys=False)) as conn, conn:
        row = conn.execute("SELECT is_test FROM users WHERE id = ?", (uid,)).fetchone()
        if row is None or not row["is_test"]:
            return False
        _purge_user_rows(conn, uid)
        conn.execute("DELETE FROM users WHERE id = ? AND is_test = 1", (uid,))
        return True


def purge_user(uid: str) -> bool:
    """Borra un perfil REAL y toda su evidencia (V3.77). Irreversible.

    Es la mitad **no reversible** del borrado y por eso no la llama nadie por su
    cuenta: el webmaster la ejecuta desde el lanzador, tras una confirmación por
    nombre y **después** de que `services.backup` haya tomado una copia. Admite
    cualquier perfil, también uno desactivado (es el caso normal).
    """
    if get_user(uid) is None:
        return False
    with closing(_conn(foreign_keys=False)) as conn, conn:
        _purge_user_rows(conn, uid)
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    return True

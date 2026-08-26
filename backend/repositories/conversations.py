"""Repositorio de conversaciones y mensajes (SQLite)."""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def create_conversation(user_id: str) -> dict | None:
    if get_user(user_id) is None:
        return None
    cid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, "Nueva conversación", now, now, user_id),
        )
    return {
        "id": cid,
        "title": "Nueva conversación",
        "created_at": now,
        "updated_at": now,
        "user_id": user_id,
    }


def list_conversations(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at, user_id FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str, user_id: str) -> dict | None:
    with closing(_conn()) as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at, user_id "
            "FROM conversations WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        msgs = conn.execute(
            "SELECT role, content, mode, message_id FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    result = dict(conv)
    result["messages"] = [
        {
            "id": m["message_id"],
            "role": m["role"],
            "content": m["content"],
            "mode": m["mode"],
        }
        for m in msgs
    ]
    return result


def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    """Guarda título y mensajes de una conversación (solo del propietario).

    Si todos los mensajes traen `id`, el guardado es append-only: se insertan solo los
    mensajes cuyo `id` no existe aún en la conversación (los ya existentes conservan su
    timestamp original). Si algún mensaje no trae `id` (cliente legacy), se mantiene el
    comportamiento anterior de reemplazar todos los mensajes.
    """
    now = _now()
    append_only = all(m.get("id") for m in messages)
    with closing(_conn()) as conn, conn:
        conv = conn.execute(
            "SELECT created_at, user_id FROM conversations "
            "WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ?",
            (title, now, cid, user_id),
        )
        if append_only:
            conn.executemany(
                "INSERT OR IGNORE INTO messages "
                "(conversation_id, role, content, mode, created_at, message_id, "
                "duration_ms, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        cid,
                        m["role"],
                        m["content"],
                        m.get("mode"),
                        now,
                        m.get("id"),
                        m.get("duration_ms"),
                        m.get("latency_ms"),
                    )
                    for m in messages
                ],
            )
        else:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.executemany(
                "INSERT INTO messages "
                "(conversation_id, role, content, mode, created_at, "
                "duration_ms, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        cid,
                        m["role"],
                        m["content"],
                        m.get("mode"),
                        now,
                        m.get("duration_ms"),
                        m.get("latency_ms"),
                    )
                    for m in messages
                ],
            )
    return {
        "id": cid,
        "title": title,
        "created_at": conv["created_at"],
        "updated_at": now,
        "user_id": conv["user_id"],
    }


def delete_conversation(cid: str, user_id: str) -> bool:
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?", (cid, user_id)
        )
    return cur.rowcount > 0


def save_message(
    cid: str,
    user_id: str,
    *,
    role: str,
    content: str,
    mode: str | None = None,
    message_id: str | None = None,
    duration_ms: int | None = None,
    latency_ms: int | None = None,
) -> bool:
    """Inserta un mensaje (append-only) con telemetría de turno opcional.

    Usa `INSERT OR IGNORE` sobre `(conversation_id, message_id)` para no duplicar un
    turno ya persistido (p. ej. cuando el frontend guarda después la historia
    completa con el mismo `message_id`). Devuelve False si la conversación no existe
    o no pertenece al usuario.
    """
    with closing(_conn()) as conn, conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return False
        conn.execute(
            "INSERT OR IGNORE INTO messages "
            "(conversation_id, role, content, mode, created_at, message_id, "
            "duration_ms, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, role, content, mode, _now(), message_id, duration_ms, latency_ms),
        )
    return True


def get_turns(cid: str, user_id: str) -> list[dict] | None:
    """Telemetría de turnos de una conversación (o None si no existe / no es suya).

    Devuelve una lista ordenada (por id ASC) de turnos `{role, duration_ms,
    latency_ms, created_at}` lista para `services.interaction.interaction_evidence`.
    El `role` de la BD ("user"/"assistant") se normaliza a "student"/"assistant".
    """
    with closing(_conn()) as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        rows = conn.execute(
            "SELECT role, duration_ms, latency_ms, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    return [
        {
            "role": "student" if r["role"] == "user" else r["role"],
            "duration_ms": r["duration_ms"],
            "latency_ms": r["latency_ms"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

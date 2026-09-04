"""Repositorio de las rutas de speaking (SQLite).

Almacena los intentos read-aloud (`speaking_attempts`) y la práctica extra
generada (catálogo global `speaking_generated`, activación por usuario en
`speaking_route_extras` y trabajos en segundo plano en
`speaking_generation_jobs`). El estado por frase se deriva en vivo desde
`speaking_attempts`, igual que en listening.
"""
from __future__ import annotations

import json
import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    phrase_id: str,
    level: str,
    result: float,
    passed: bool,
    difficulty: int = 1,
    topic: str = "",
) -> bool:
    """Persiste un intento de speaking read-aloud para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO speaking_attempts "
            "(user_id, phrase_id, level, result, passed, difficulty, topic, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                phrase_id,
                level,
                float(result),
                int(bool(passed)),
                difficulty,
                topic,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de speaking del usuario, en orden de creación."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT phrase_id, level, result, passed, difficulty, topic, created_at "
            "FROM speaking_attempts WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def passed_phrase_ids(user_id: str) -> set[str]:
    """Ids de frases superadas al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT phrase_id FROM speaking_attempts "
            "WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchall()
    return {r["phrase_id"] for r in rows}


# --- Práctica extra generada (V3.7) ------------------------------------------
# Frases modelo extra generadas con IA local: catálogo global en
# `speaking_generated`, activación por usuario en `speaking_route_extras` y
# trabajos de generación en segundo plano en `speaking_generation_jobs`. El
# contenido extra nunca participa en la puerta de ruta ni en la certificación.


def insert_generated(item: dict, generator_version: str) -> bool:
    """Persiste una frase extra en el catálogo global (deduplicada por contenido).

    El `id` vive en su propia columna y se guarda FUERA del `payload_json` para
    que `UNIQUE(level, payload_json)` deduplique por contenido.
    """
    payload = {k: v for k, v in item.items() if k != "id"}
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO speaking_generated "
            "(id, level, payload_json, generator_version, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                item["id"],
                item.get("level", ""),
                json.dumps(payload),
                generator_version,
                _now(),
            ),
        )
        return cur.rowcount > 0


def list_generated_by_ids(ids: list[str]) -> list[dict]:
    """Filas del catálogo global para los ids indicados."""
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT id, level, payload_json, generator_version, created_at "
            f"FROM speaking_generated WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    return [dict(r) for r in rows]


def get_generated(item_id: str) -> dict | None:
    """Fila del catálogo global por id (None si no existe)."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM speaking_generated WHERE id = ?",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None


def list_generated(level: str) -> list[dict]:
    """Filas del catálogo global de un nivel (orden de creación)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM speaking_generated WHERE level = ? ORDER BY id ASC",
            (level,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_route_extras(user_id: str, level: str | None = None) -> list[dict]:
    """Extras activados por un usuario, opcionalmente de un nivel concreto."""
    with closing(_conn()) as conn:
        if level is None:
            rows = conn.execute(
                "SELECT user_id, level, phrase_id, added_at "
                "FROM speaking_route_extras WHERE user_id = ? ORDER BY added_at ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT user_id, level, phrase_id, added_at "
                "FROM speaking_route_extras "
                "WHERE user_id = ? AND level = ? ORDER BY added_at ASC",
                (user_id, level),
            ).fetchall()
    return [dict(r) for r in rows]


def add_route_extras(user_id: str, level: str, phrase_ids: list[str]) -> int:
    """Activa frases extra en la ruta de un usuario. Devuelve cuántas eran nuevas."""
    if not phrase_ids:
        return 0
    added = 0
    with closing(_conn()) as conn, conn:
        for qid in phrase_ids:
            cur = conn.execute(
                "INSERT OR IGNORE INTO speaking_route_extras "
                "(user_id, level, phrase_id, added_at) VALUES (?, ?, ?, ?)",
                (user_id, level, qid, _now()),
            )
            if cur.rowcount > 0:
                added += 1
    return added


def remove_route_extra(user_id: str, level: str, phrase_id: str) -> bool:
    """Desactiva una frase extra de la ruta de un usuario. True si existía."""
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM speaking_route_extras "
            "WHERE user_id = ? AND level = ? AND phrase_id = ?",
            (user_id, level, phrase_id),
        )
        return cur.rowcount > 0


def create_generation_job(user_id: str, level: str, requested: int) -> dict:
    """Crea un trabajo de generación en segundo plano y devuelve su fila."""
    job_id = "sj-" + uuid.uuid4().hex[:12]
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO speaking_generation_jobs "
            "(id, user_id, level, requested, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (job_id, user_id, level, requested, now, now),
        )
    return get_generation_job(job_id)  # type: ignore[return-value]


def running_generation_job(user_id: str, level: str) -> dict | None:
    """Trabajo en curso (running) del usuario para un nivel, si existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM speaking_generation_jobs "
            "WHERE user_id = ? AND level = ? AND status = 'running' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, level),
        ).fetchone()
    return dict(row) if row else None


def get_generation_job(job_id: str) -> dict | None:
    """Fila de trabajo de generación por id."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM speaking_generation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def list_running_generation_jobs() -> list[dict]:
    """Trabajos de generación en curso (para el estado del sistema)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM speaking_generation_jobs "
            "WHERE status = 'running' ORDER BY created_at DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def finish_generation_job(
    job_id: str, added_ids: list[str], error: str = ""
) -> None:
    """Cierra un trabajo: `done` con los ids activados o `error` con el mensaje."""
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE speaking_generation_jobs SET status = ?, added_ids_json = ?, "
            "error = ?, updated_at = ? WHERE id = ?",
            (
                "error" if error else "done",
                json.dumps(added_ids),
                error,
                _now(),
                job_id,
            ),
        )

"""Repositorio de listening (SQLite)."""
from __future__ import annotations

import json
import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    question_id: str,
    answer_index: int,
    correct: bool,
    skill: str = "",
    difficulty: int = 1,
    response_time_ms: int | None = None,
    replay_count: int = 0,
    topic: str = "",
    realized_difficulty: int = 0,
    task_type: str = "mcq",
    score: float | None = None,
) -> bool:
    """Persiste un intento de listening para un usuario existente.

    Los kwargs `task_type` y `score` son opcionales y compatibles hacia atrás: el
    flujo MCQ no los pasa (queda `task_type="mcq"` y `score=None`); las tareas de
    producción (dictado/shadowing) sí, dejando `score` como evidencia continua 0..1.
    """
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, topic, realized_difficulty, "
            "task_type, score, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                question_id,
                answer_index,
                int(correct),
                skill,
                difficulty,
                response_time_ms,
                replay_count,
                topic,
                realized_difficulty,
                task_type,
                score,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de listening del usuario, en orden de creación."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, topic, realized_difficulty, "
            "task_type, score, created_at "
            "FROM listening_attempts WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def seen_question_ids(user_id: str) -> set[str]:
    """Ids de preguntas ya respondidas por el usuario."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM listening_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {r["question_id"] for r in rows}


def correct_question_ids(user_id: str) -> set[str]:
    """Ids de preguntas respondidas correctamente al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM listening_attempts "
            "WHERE user_id = ? AND correct = 1",
            (user_id,),
        ).fetchall()
    return {r["question_id"] for r in rows}


def get_stats(user_id: str) -> dict:
    """Intentos, aciertos y precisión del usuario."""
    with closing(_conn()) as conn:
        attempts = conn.execute(
            "SELECT COUNT(*) FROM listening_attempts WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        correct = conn.execute(
            "SELECT COUNT(*) FROM listening_attempts "
            "WHERE user_id = ? AND correct = 1",
            (user_id,),
        ).fetchone()[0]
    accuracy = round(correct / attempts * 100, 1) if attempts else None
    return {"attempts": attempts, "correct": correct, "accuracy": accuracy}


# --- Listening extra generado (V3.6) ------------------------------------------
# Ítems de práctica extra generados con IA local: catálogo global en
# `listening_generated`, activación por usuario en `listening_route_extras` y
# trabajos de generación en segundo plano en `listening_generation_jobs`.
# El contenido extra nunca participa en la puerta de ruta ni en la certificación
# (siempre se calculan sobre el banco curado).


def insert_generated(item: dict, generator_version: str) -> bool:
    """Persiste un ítem generado en el catálogo global.

    Devuelve True si se insertó (nuevo contenido); False si ya existía un ítem
    con el mismo `level` y contenido (se ignora). El `id` vive en su propia
    columna y se guarda FUERA del `payload_json` para que la restricción
    `UNIQUE(level, payload_json)` deduplique por contenido aunque dos ids
    distintos tengan el mismo texto (una segunda generación no crea copias).
    """
    payload = {k: v for k, v in item.items() if k != "id"}
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO listening_generated "
            "(id, level, payload_json, generator_version, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (item["id"], item.get("level", ""), json.dumps(payload),
             generator_version, _now()),
        )
        return cur.rowcount > 0


def list_generated_by_ids(ids: list[str]) -> list[dict]:
    """Devuelve las filas del catálogo global para los ids indicados."""
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT id, level, payload_json, generator_version, created_at "
            f"FROM listening_generated WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    return [dict(r) for r in rows]


def get_generated(item_id: str) -> dict | None:
    """Devuelve una fila del catálogo global por id, o None si no existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM listening_generated WHERE id = ?",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None


def list_generated(level: str) -> list[dict]:
    """Todas las filas del catálogo global de un nivel (orden de creación)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM listening_generated WHERE level = ? ORDER BY id ASC",
            (level,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_route_extras(user_id: str, level: str | None = None) -> list[dict]:
    """Extras activados por un usuario, opcionalmente de un nivel concreto."""
    with closing(_conn()) as conn:
        if level is None:
            rows = conn.execute(
                "SELECT user_id, level, question_id, added_at "
                "FROM listening_route_extras WHERE user_id = ? ORDER BY added_at ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT user_id, level, question_id, added_at "
                "FROM listening_route_extras "
                "WHERE user_id = ? AND level = ? ORDER BY added_at ASC",
                (user_id, level),
            ).fetchall()
    return [dict(r) for r in rows]


def add_route_extras(user_id: str, level: str, question_ids: list[str]) -> int:
    """Activa ítems extra en la ruta de un usuario. Devuelve cuántos eran nuevos.

    INSERT OR IGNORE: activar un ítem ya activado no cuenta como nuevo.
    """
    if not question_ids:
        return 0
    added = 0
    with closing(_conn()) as conn, conn:
        for qid in question_ids:
            cur = conn.execute(
                "INSERT OR IGNORE INTO listening_route_extras "
                "(user_id, level, question_id, added_at) VALUES (?, ?, ?, ?)",
                (user_id, level, qid, _now()),
            )
            if cur.rowcount > 0:
                added += 1
    return added


def remove_route_extra(user_id: str, level: str, question_id: str) -> bool:
    """Desactiva un ítem extra de la ruta de un usuario. True si existía."""
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM listening_route_extras "
            "WHERE user_id = ? AND level = ? AND question_id = ?",
            (user_id, level, question_id),
        )
        return cur.rowcount > 0


def create_generation_job(user_id: str, level: str, requested: int) -> dict:
    """Crea un trabajo de generación en segundo plano y devuelve su fila."""
    job_id = "gj-" + uuid.uuid4().hex[:12]
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_generation_jobs "
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
            "created_at, updated_at FROM listening_generation_jobs "
            "WHERE user_id = ? AND level = ? AND status = 'running' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, level),
        ).fetchone()
    return dict(row) if row else None


def get_generation_job(job_id: str) -> dict | None:
    """Devuelve una fila de trabajo por id."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM listening_generation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def finish_generation_job(job_id: str, added_ids: list[str], error: str = "") -> None:
    """Cierra un trabajo: `done` con los ids activados o `error` con el mensaje."""
    status = "error" if error else "done"
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE listening_generation_jobs "
            "SET status = ?, added_ids_json = ?, error = ?, updated_at = ? "
            "WHERE id = ?",
            (status, json.dumps(added_ids), error, _now(), job_id),
        )

"""Repositorio de listening (SQLite)."""
from __future__ import annotations

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
) -> bool:
    """Persiste un intento de listening para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                question_id,
                answer_index,
                int(correct),
                skill,
                difficulty,
                response_time_ms,
                replay_count,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de listening del usuario, en orden de creación."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, created_at "
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

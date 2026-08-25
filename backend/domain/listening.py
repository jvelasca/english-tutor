"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import listening as listening_repo
from services.listening import (
    current_level,
    difficulty_from_vector,
    get_question,
    level_status,
    listening_diagnostic,
    pick_next_question,
    score_answer,
)


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index) y añade la dificultad derivada del vector."""
    out = {k: v for k, v in question.items() if k != "answer_index"}
    out["difficulty"] = difficulty_from_vector(question.get("difficulty_vector", {}))
    return out


async def next_question(user_id: str) -> dict:
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    return _public(pick_next_question(seen, correct))


async def submit_answer(
    user_id: str,
    question_id: str,
    answer_index: int,
    response_time_ms: int | None = None,
    replay_count: int = 0,
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe."""
    question = get_question(question_id)
    if question is None:
        return None
    correct = score_answer(answer_index, question["answer_index"])
    difficulty = difficulty_from_vector(question.get("difficulty_vector", {}))
    await run_in_threadpool(
        listening_repo.record_attempt,
        user_id,
        question_id,
        answer_index,
        correct,
        question.get("skill", ""),
        difficulty,
        response_time_ms,
        replay_count,
        question.get("topic", ""),
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
        "skill": question.get("skill", ""),
        "difficulty": difficulty,
    }


async def get_stats(user_id: str) -> dict:
    stats = await run_in_threadpool(listening_repo.get_stats, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    levels = level_status(correct)
    stats["level"] = current_level(correct)
    stats["completed"] = all(s["completed"] for s in levels)
    stats["levels"] = levels
    return stats


async def get_diagnostic(user_id: str) -> dict:
    """Diagnóstico de sub-destrezas derivado de los intentos registrados."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    return listening_diagnostic(attempts)

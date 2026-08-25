"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import listening as listening_repo
from services.listening import (
    current_level,
    get_question,
    level_status,
    pick_next_question,
    score_answer,
)


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index) antes de exponerla al cliente."""
    return {k: v for k, v in question.items() if k != "answer_index"}


async def next_question(user_id: str) -> dict:
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    return _public(pick_next_question(seen, correct))


async def submit_answer(
    user_id: str, question_id: str, answer_index: int
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe."""
    question = get_question(question_id)
    if question is None:
        return None
    correct = score_answer(answer_index, question["answer_index"])
    await run_in_threadpool(
        listening_repo.record_attempt, user_id, question_id, answer_index, correct
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
    }


async def get_stats(user_id: str) -> dict:
    stats = await run_in_threadpool(listening_repo.get_stats, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    levels = level_status(correct)
    stats["level"] = current_level(correct)
    stats["completed"] = all(s["completed"] for s in levels)
    stats["levels"] = levels
    return stats

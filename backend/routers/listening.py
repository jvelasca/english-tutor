"""Endpoints de listening (comprensión auditiva)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import learning as learning_service
from domain import listening as listening_service
from schemas.listening import (
    ListeningAnswerRequest,
    ListeningAnswerResponse,
    ListeningQuestion,
    ListeningStats,
)

router = APIRouter()


@router.get("/api/listening/question", response_model=ListeningQuestion)
async def question(user: dict = Depends(current_user)) -> dict:
    return await listening_service.next_question(user["id"])


@router.post("/api/listening/answer", response_model=ListeningAnswerResponse)
async def answer(
    body: ListeningAnswerRequest, user: dict = Depends(current_user)
) -> dict:
    result = await listening_service.submit_answer(
        user["id"], body.question_id, body.answer_index
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"listening:{body.question_id}:{'ok' if result['correct'] else 'ko'}",
    )
    return result


@router.get("/api/listening/stats", response_model=ListeningStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await listening_service.get_stats(user["id"])

"""Endpoints de errores gramaticales."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import grammar as grammar_service
from schemas.grammar import (
    GrammarAnalyzeRequest,
    GrammarAnalyzeResponse,
    GrammarRecurringError,
)

router = APIRouter()


@router.post("/api/grammar/analyze", response_model=GrammarAnalyzeResponse)
async def analyze(
    body: GrammarAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    errors = await grammar_service.analyze_text(user["id"], body.text)
    return {"errors": errors}


@router.get("/api/grammar/errors", response_model=list[GrammarRecurringError])
async def get_errors(user: dict = Depends(current_user)) -> list[dict]:
    return await grammar_service.get_recurring_errors(user["id"])

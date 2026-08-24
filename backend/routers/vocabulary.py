"""Endpoints de vocabulario."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import vocabulary as vocabulary_service
from schemas.vocabulary import (
    VocabularyAnalyzeRequest,
    VocabularyAnalyzeResponse,
    VocabularyItem,
)

router = APIRouter()


@router.post("/api/vocabulary/analyze", response_model=VocabularyAnalyzeResponse)
async def analyze(
    body: VocabularyAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    words = await vocabulary_service.analyze_text(user["id"], body.text)
    return {"words": words}


@router.get("/api/vocabulary", response_model=list[VocabularyItem])
async def get_vocabulary(user: dict = Depends(current_user)) -> list[dict]:
    return await vocabulary_service.get_vocabulary(user["id"])

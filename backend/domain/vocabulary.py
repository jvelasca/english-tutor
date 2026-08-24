"""Servicio de dominio de vocabulario."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary as vocabulary_repo
from services.vocabulary import extract_words


async def analyze_text(user_id: str, text: str) -> list[str]:
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_words, user_id, words)
    return words


async def get_vocabulary(user_id: str) -> list[dict]:
    return await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)

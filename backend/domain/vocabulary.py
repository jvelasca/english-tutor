"""Servicio de dominio de vocabulario."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary as vocabulary_repo
from services.vocabulary import classify, extract_words


async def analyze_text(user_id: str, text: str) -> list[str]:
    """Registra producción del alumno y devuelve las palabras extraídas."""
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_words, user_id, words)
    return words


async def record_exposure(user_id: str, text: str) -> list[str]:
    """Registra exposición (palabras de la respuesta del tutor)."""
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_exposures, user_id, words)
    return words


async def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario con el estado de dominio calculado."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    for row in rows:
        row["status"] = classify(row["appearances"], row["production_days"])
    return rows

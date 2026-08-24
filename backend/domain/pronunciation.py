"""Servicio de dominio de pronunciación y progreso."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import pronunciation as pronunciation_repo


async def record_pronunciation(
    user_id: str, expected: str, heard: str, score: int, level: str
) -> bool:
    return await run_in_threadpool(
        pronunciation_repo.record_pronunciation, user_id, expected, heard, score, level
    )


async def get_progress(user_id: str) -> dict:
    return await run_in_threadpool(pronunciation_repo.get_progress, user_id)

"""Servicio de dominio de eventos de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import learning as learning_repo


async def record_event(user_id: str, event_type: str, detail: str) -> dict | None:
    return await run_in_threadpool(
        learning_repo.record_event, user_id, event_type, detail
    )


async def list_events(user_id: str, event_type: str | None = None) -> list[dict]:
    return await run_in_threadpool(learning_repo.list_events, user_id, event_type)

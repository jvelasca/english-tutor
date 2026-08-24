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


_MODE_TO_EVENT = {
    "exercises": "exercise",
    "grammar": "correction",
}


async def record_chat_activity(user_id: str, mode: str, detail: str) -> dict | None:
    """Registra la actividad del chat como evento de aprendizaje según el modo.
    Los modos `exercises` y `grammar` mapean a `exercise` y `correction`; el resto
    (conversation, pronunciation, desconocido) mapea a `message`."""
    event_type = _MODE_TO_EVENT.get(mode, "message")
    return await run_in_threadpool(
        learning_repo.record_event, user_id, event_type, detail
    )

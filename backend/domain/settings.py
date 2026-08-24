"""Servicio de dominio de preferencias de usuario."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import settings as settings_repo


async def get_settings(user_id: str) -> dict[str, str]:
    return await run_in_threadpool(settings_repo.get_settings, user_id)


async def set_settings(user_id: str, settings: dict[str, str]) -> dict[str, str]:
    return await run_in_threadpool(settings_repo.set_settings, user_id, settings)

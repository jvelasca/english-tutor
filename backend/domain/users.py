"""Servicio de dominio de usuarios."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import users as users_repo


async def create_user(name: str) -> dict:
    return await run_in_threadpool(users_repo.create_user, name)


async def list_users() -> list[dict]:
    return await run_in_threadpool(users_repo.list_users)


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(users_repo.get_user, uid)


async def update_user(uid: str, fields: dict) -> dict | None:
    return await run_in_threadpool(users_repo.update_user, uid, **fields)

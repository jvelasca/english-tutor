"""Envolturas async del store síncrono para no bloquear el event loop."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from services import store


async def create_user(name: str) -> dict:
    return await run_in_threadpool(store.create_user, name)


async def list_users() -> list[dict]:
    return await run_in_threadpool(store.list_users)


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(store.get_user, uid)


async def create_conversation(user_id: str) -> dict | None:
    return await run_in_threadpool(store.create_conversation, user_id)


async def list_conversations(user_id: str) -> list[dict]:
    return await run_in_threadpool(store.list_conversations, user_id)


async def get_conversation(cid: str, user_id: str) -> dict | None:
    return await run_in_threadpool(store.get_conversation, cid, user_id)


async def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    return await run_in_threadpool(
        store.save_conversation, cid, user_id, title, messages
    )


async def delete_conversation(cid: str, user_id: str) -> bool:
    return await run_in_threadpool(store.delete_conversation, cid, user_id)


async def record_pronunciation(
    user_id: str, expected: str, heard: str, score: int, level: str
) -> bool:
    return await run_in_threadpool(
        store.record_pronunciation, user_id, expected, heard, score, level
    )


async def get_progress(user_id: str) -> dict:
    return await run_in_threadpool(store.get_progress, user_id)

"""Servicio de dominio de conversaciones."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import conversations as conversations_repo


async def create_conversation(user_id: str) -> dict | None:
    return await run_in_threadpool(conversations_repo.create_conversation, user_id)


async def list_conversations(user_id: str) -> list[dict]:
    return await run_in_threadpool(conversations_repo.list_conversations, user_id)


async def get_conversation(cid: str, user_id: str) -> dict | None:
    return await run_in_threadpool(conversations_repo.get_conversation, cid, user_id)


async def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    return await run_in_threadpool(
        conversations_repo.save_conversation, cid, user_id, title, messages
    )


async def delete_conversation(cid: str, user_id: str) -> bool:
    return await run_in_threadpool(conversations_repo.delete_conversation, cid, user_id)


async def save_message(
    cid: str,
    user_id: str,
    *,
    role: str,
    content: str,
    mode: str | None = None,
    message_id: str | None = None,
    duration_ms: int | None = None,
    latency_ms: int | None = None,
) -> bool:
    return await run_in_threadpool(
        conversations_repo.save_message,
        cid,
        user_id,
        role=role,
        content=content,
        mode=mode,
        message_id=message_id,
        duration_ms=duration_ms,
        latency_ms=latency_ms,
    )


async def get_turns(cid: str, user_id: str) -> list[dict] | None:
    return await run_in_threadpool(conversations_repo.get_turns, cid, user_id)

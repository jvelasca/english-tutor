"""Servicio de dominio de errores gramaticales."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from services.grammar import find_errors


async def analyze_text(user_id: str, text: str) -> list[dict]:
    errors = find_errors(text)
    await run_in_threadpool(grammar_repo.record_errors, user_id, errors)
    return errors


async def get_recurring_errors(user_id: str) -> list[dict]:
    return await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)

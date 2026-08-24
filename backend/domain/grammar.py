"""Servicio de dominio de errores gramaticales."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from services.grammar import (
    MASTERY_STREAK,
    POSITIVE_PATTERNS,
    find_correct_usage,
    find_errors,
)


async def analyze_text(user_id: str, text: str) -> list[dict]:
    errors = find_errors(text)
    await run_in_threadpool(grammar_repo.record_errors, user_id, errors)

    # Evidencia positiva: para las reglas ya registradas (y con patrón positivo)
    # que no aparecen como error en este mensaje, se detecta uso correcto y se
    # registra progreso (correct_after/streak/mastered).
    error_rules = {e["rule"] for e in errors}
    tracked = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    tracked_rules = {e["rule"] for e in tracked}
    for rule in POSITIVE_PATTERNS:
        if rule in error_rules or rule not in tracked_rules:
            continue
        if find_correct_usage(text, rule):
            await run_in_threadpool(
                grammar_repo.record_correct_usage, user_id, rule, MASTERY_STREAK
            )
    return errors


async def get_recurring_errors(user_id: str) -> list[dict]:
    return await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)

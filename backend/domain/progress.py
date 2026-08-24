"""Servicio de dominio del progreso histórico."""
from __future__ import annotations

from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from repositories import progress as progress_repo
from repositories import pronunciation as pronunciation_repo
from repositories import vocabulary as vocabulary_repo
from services.mastery import classify_errors, compute_milestones
from services.trends import (
    active_days,
    aggregate_series,
    compute_streak,
    daily_activity,
)


async def get_progress_history(user_id: str, bucket: str) -> dict:
    events = await run_in_threadpool(progress_repo.activity_events, user_id)
    daily = daily_activity(events)
    series = aggregate_series(daily, bucket)
    streak = compute_streak(active_days(events))

    errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    mastery = classify_errors(errors, now_iso)

    progress = await run_in_threadpool(pronunciation_repo.get_progress, user_id)
    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    milestones = compute_milestones(
        {
            "messages": progress["messages"],
            "conversations": progress["conversations"],
            "pronunciation": progress["pronunciation"]["attempts"],
            "vocab_size": len(vocab),
            "streak_best": streak["best_days"],
        }
    )

    return {
        "user_id": user_id,
        "bucket": bucket,
        "series": series,
        "streak": streak,
        "mastery": mastery,
        "milestones": milestones,
    }

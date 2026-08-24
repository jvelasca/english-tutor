"""Servicio de dominio del perfil de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import estimate_cefr, recommendations


async def get_profile_summary(user_id: str) -> dict | None:
    """Compone el perfil del alumno: vocabulario, errores, pronunciación, CEFR
    estimado y recomendaciones. Devuelve None si el usuario no existe."""
    if await run_in_threadpool(users_repo.get_user, user_id) is None:
        return None

    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    progress = await run_in_threadpool(pronunciation_repo.get_progress, user_id)

    pron_avg = progress["pronunciation"]["average"]
    level = estimate_cefr(
        {
            "vocab_size": len(vocab),
            "pronunciation_avg": pron_avg,
            "exercises": progress["exercises"],
        }
    )
    await run_in_threadpool(profile_repo.set_cefr, user_id, level)

    recs = recommendations(
        {
            "recurring_errors": errors,
            "pronunciation_avg": pron_avg,
            "vocab_size": len(vocab),
        }
    )
    return {
        "user_id": user_id,
        "cefr_level": level,
        "vocabulary_size": len(vocab),
        "top_words": [v["word"] for v in vocab[:5]],
        "recurring_errors": errors,
        "pronunciation_average": pron_avg,
        "recommendations": recs,
    }

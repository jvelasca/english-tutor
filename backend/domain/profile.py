"""Servicio de dominio del perfil de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from repositories import listening as listening_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import evaluate_cefr, recommendations
from services.vocabulary import classify


async def _compute_profile(user_id: str) -> dict | None:
    """Calcula el perfil del alumno (vocabulario, errores, pronunciación, CEFR y
    recomendaciones) sin persistir nada. Devuelve None si el usuario no existe."""
    if await run_in_threadpool(users_repo.get_user, user_id) is None:
        return None

    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    produced = [v for v in vocab if v["appearances"] > 0]
    mastered_words = [
        v
        for v in produced
        if classify(v["appearances"], v["production_days"]) == "mastered"
    ]
    exposed_only = len(vocab) - len(produced)

    errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    progress = await run_in_threadpool(pronunciation_repo.get_progress, user_id)
    listening_stats = await run_in_threadpool(listening_repo.get_stats, user_id)

    pron_avg = progress["pronunciation"]["average"]
    messages = progress["messages"]
    user_messages = progress["user_messages"]

    confirmed = [e for e in errors if e.get("confirmed", True)]
    active_errors = [e for e in confirmed if not e.get("mastered")]
    mastered_errors = [e for e in confirmed if e.get("mastered")]
    total_errors = sum(e["count"] for e in confirmed)
    grammar_error_rate = (total_errors / user_messages) if user_messages > 0 else None

    evaluation = evaluate_cefr(
        {
            "vocab_size": len(produced),
            "pronunciation_avg": pron_avg,
            "pronunciation_attempts": progress["pronunciation"]["attempts"],
            "grammar_error_rate": grammar_error_rate,
            "messages": messages,
            "user_messages": user_messages,
            "listening_accuracy": listening_stats["accuracy"],
            "listening_attempts": listening_stats["attempts"],
        }
    )

    recs = recommendations(
        {
            "recurring_errors": active_errors,
            "pronunciation_avg": pron_avg,
            "vocab_size": len(produced),
        }
    )
    return {
        "user_id": user_id,
        "estimated_level": evaluation["level"],
        "estimated_bands": evaluation["bands"],
        "estimated_descriptor": evaluation["descriptor"],
        "estimated_confidence": evaluation["confidence"],
        "estimated_evidence": evaluation["evidence"],
        "vocabulary_size": len(produced),
        "vocabulary_exposed": exposed_only,
        "vocabulary_mastered": len(mastered_words),
        "top_words": [v["word"] for v in produced[:5]],
        "recurring_errors": active_errors,
        "mastered_errors": mastered_errors,
        "mastered_count": len(mastered_errors),
        "pronunciation_average": pron_avg,
        "recommendations": recs,
    }


async def get_profile_summary(user_id: str) -> dict | None:
    """Compone el perfil del alumno y persiste el nivel estimado como caché.
    Devuelve None si el usuario no existe."""
    profile = await _compute_profile(user_id)
    if profile is None:
        return None
    await run_in_threadpool(profile_repo.set_cefr, user_id, profile["estimated_level"])
    return profile


async def get_profile_context(user_id: str) -> dict | None:
    """Devuelve el perfil para construir el prompt del tutor (sin persistir).
    Devuelve None si el usuario no existe."""
    return await _compute_profile(user_id)

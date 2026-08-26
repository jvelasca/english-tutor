"""Servicio de dominio del perfil de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from domain import academy as academy_service
from repositories import grammar as grammar_repo
from repositories import listening as listening_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import (
    CEFR_MODEL_VERSION,
    heuristic_band,
    level_descriptor,
    recommendations,
)
from services.curriculum import CURRICULUM_VERSION
from services.vocabulary import classify

# Cambio de confianza (en puntos, 0..1) por debajo del cual NO se guarda un nuevo
# snapshot: evita escribir historial por fluctuaciones de ruido.
_SNAPSHOT_CONFIDENCE_DELTA = 0.1


async def _activity_stats(user_id: str) -> dict:
    """Estadísticas de actividad del alumno (vocabulario, errores, pronunciación,
    listening) que alimentan el perfil (no el nivel CEFR, que viene del Student
    Model)."""
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
    user_messages = progress["user_messages"]

    confirmed = [e for e in errors if e.get("confirmed", True)]
    active_errors = [e for e in confirmed if not e.get("mastered")]
    mastered_errors = [e for e in confirmed if e.get("mastered")]

    return {
        "produced": produced,
        "mastered_words": mastered_words,
        "exposed_only": exposed_only,
        "pron_avg": pron_avg,
        "user_messages": user_messages,
        "active_errors": active_errors,
        "mastered_errors": mastered_errors,
        "listening_stats": listening_stats,
    }


def _bands_from_skills(skills: list[dict]) -> dict[str, str]:
    """Banda heurística por destreza canónica (score continuo → banda)."""
    by_skill = {entry["skill"]: entry for entry in skills}
    return {
        skill: heuristic_band(by_skill[skill]["score"] if skill in by_skill else 0.0)
        for skill in (
            "vocabulary",
            "grammar",
            "pronunciation",
            "listening",
            "speaking",
            "reading",
            "writing",
        )
    }


def _skill_states(skills: list[dict]) -> list[dict]:
    """Proyección por destreza del Student Model para el perfil (con banda)."""
    result = []
    for entry in skills:
        result.append(
            {
                "skill": entry["skill"],
                "band": heuristic_band(entry["score"]),
                "score": round(float(entry.get("score", 0.0)), 3),
                "confidence": round(float(entry.get("confidence", 0.0)), 3),
                "samples": int(entry.get("evidence_count", 0)),
                "stability": round(float(entry.get("stability", 0.0)), 3),
                "trend": entry.get("trend"),
                "subskills": entry.get("subskills", []),
            }
        )
    return result


async def _compute_profile(user_id: str) -> dict | None:
    """Calcula el perfil del alumno sin persistir nada. Devuelve None si el
    usuario no existe.

    El nivel CEFR y el desglose por destreza derivan del Student Model (fuente
    única, vía `domain.academy.build_student_model`); el resto (vocabulario,
    errores, pronunciación, recomendaciones) son estadísticas de actividad."""
    if await run_in_threadpool(users_repo.get_user, user_id) is None:
        return None

    stats = await _activity_stats(user_id)
    student_model = await academy_service.build_student_model(user_id)

    skills = _skill_states(student_model["skills"])
    bands = _bands_from_skills(student_model["skills"])
    level = student_model["estimated_level"]

    recs = recommendations(
        {
            "recurring_errors": stats["active_errors"],
            "pronunciation_avg": stats["pron_avg"],
            "vocab_size": len(stats["produced"]),
        }
    )

    return {
        "user_id": user_id,
        "current_level": student_model["current_level"],
        "estimated_level": level,
        "estimated_bands": bands,
        "estimated_descriptor": level_descriptor(level),
        "estimated_confidence": student_model["confidence"],
        "overall_ability": student_model["estimated_numeric"],
        "target_level": student_model["target_level"],
        "skills": skills,
        "readiness": student_model["readiness"],
        "vocabulary_size": len(stats["produced"]),
        "vocabulary_exposed": stats["exposed_only"],
        "vocabulary_mastered": len(stats["mastered_words"]),
        "top_words": [v["word"] for v in stats["produced"][:5]],
        "recurring_errors": stats["active_errors"],
        "mastered_errors": stats["mastered_errors"],
        "mastered_count": len(stats["mastered_errors"]),
        "pronunciation_average": stats["pron_avg"],
        "recommendations": recs,
    }


async def _maybe_record_snapshot(user_id: str, profile: dict) -> None:
    """Guarda un snapshot inmutable del nivel CEFR si cambió de forma material.

    Se escribe solo cuando: no hay snapshot previo, cambió el nivel, o la confianza
    varió en `_SNAPSHOT_CONFIDENCE_DELTA` o más. Así el histórico refleja la
    evolución real (no ruido de redondeo en cada petición)."""
    last = await run_in_threadpool(profile_repo.last_cefr_snapshot, user_id)
    level = profile["estimated_level"]
    confidence = profile["estimated_confidence"]
    changed = (
        last is None
        or last["level"] != level
        or abs(last["confidence"] - confidence) >= _SNAPSHOT_CONFIDENCE_DELTA
    )
    if not changed:
        return
    await run_in_threadpool(
        profile_repo.record_cefr_snapshot,
        user_id,
        level=level,
        numeric=profile["overall_ability"],
        confidence=confidence,
        instrument_version=CEFR_MODEL_VERSION,
        curriculum_version=CURRICULUM_VERSION,
        skills=profile["skills"],
    )


async def get_profile_summary(user_id: str) -> dict | None:
    """Compone el perfil del alumno, persiste el nivel estimado como caché y un
    snapshot histórico si cambió de forma material. Devuelve None si el usuario no
    existe."""
    profile = await _compute_profile(user_id)
    if profile is None:
        return None
    await run_in_threadpool(profile_repo.set_cefr, user_id, profile["estimated_level"])
    await _maybe_record_snapshot(user_id, profile)
    history = await run_in_threadpool(profile_repo.list_cefr_history, user_id)
    profile["cefr_history"] = [
        {
            "id": s["id"],
            "level": s["level"],
            "numeric": s["numeric"],
            "confidence": s["confidence"],
            "instrument_version": s["instrument_version"],
            "curriculum_version": s["curriculum_version"],
            "created_at": s["created_at"],
        }
        for s in history
    ]
    return profile


async def get_profile_context(user_id: str) -> dict | None:
    """Devuelve el perfil para construir el prompt del tutor (sin persistir).
    Devuelve None si el usuario no existe."""
    return await _compute_profile(user_id)

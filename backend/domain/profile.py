"""Servicio de dominio del perfil de aprendizaje."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from domain import academy as academy_service
from repositories import academy as academy_repo
from repositories import evidence as evidence_repo
from repositories import grammar as grammar_repo
from repositories import listening as listening_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, learner_skill, skill_axis
from services import skill_state as skill_state_service
from services.cefr import (
    CEFR_MODEL_VERSION,
    heuristic_band,
    level_descriptor,
    recommendations,
)
from services.competence import competence_states
from services.curriculum import CURRICULUM_VERSION
from services.evidence import observed_signals
from services.evidence_depth import evidence_depth_report
from services.vocabulary import classify

# Cambio de confianza (en puntos, 0..1) por debajo del cual NO se guarda un nuevo
# snapshot: evita escribir historial por fluctuaciones de ruido.
_SNAPSHOT_CONFIDENCE_DELTA = 0.1


async def _activity_stats(user_id: str) -> dict:
    """Estadísticas de actividad del alumno (vocabulario, errores, pronunciación,
    listening) que alimentan el perfil (no el nivel CEFR, que viene del Student
    Model)."""
    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    produced = [v for v in vocab if v["production_count"] > 0]
    mastered_words = [
        v
        for v in produced
        if classify(v["production_count"], v["production_days"]) == "mastered"
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


def _skill_band(entry: dict | None) -> str:
    """Banda heurística por destreza con coherencia Pre-A1 (H7).

    Una destreza SIN evidencia consolidada se muestra "—" (sin señal), nunca "A1"
    por defecto: solo un score apoyado en evidencia del Student Model produce una
    banda heurística.
    """
    if entry is None or int(entry.get("evidence_count", 0) or 0) == 0:
        return "—"
    return heuristic_band(entry.get("score"))


def _bands_from_skills(skills: list[dict]) -> dict[str, str]:
    """Banda heurística por destreza canónica (score continuo → banda)."""
    by_skill = {entry["skill"]: entry for entry in skills}
    return {
        skill: _skill_band(by_skill.get(skill))
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
                "band": _skill_band(entry),
                "score": round(float(entry.get("score", 0.0)), 3),
                "confidence": round(float(entry.get("confidence", 0.0)), 3),
                "samples": int(entry.get("evidence_count", 0)),
                "stability": round(float(entry.get("stability", 0.0)), 3),
                "trend": entry.get("trend"),
                "subskills": entry.get("subskills", []),
            }
        )
    return result


def _evidence_depth_out(skills: list[dict], level: str) -> dict[str, dict]:
    """Mapa destreza → profundidad de evidencia en `level` (Constitución §6.4).

    Calcula la profundidad de la evidencia formal de cada destreza del Student
    Model en el nivel actual con `services.evidence_depth` (mínimos de la matriz
    CEFR, retención retardada y muestras de producción)."""
    return {
        entry["skill"]: evidence_depth_report(
            entry["skill"],
            level,
            int(entry.get("evidence_count", 0) or 0),
            entry.get("evidence_by_kind"),
            production_count=int(entry.get("production_count", 0) or 0),
        )
        for entry in skills
    }


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

    # V3.53 (Learner Skill State 2.0): capacidad OBSERVADA por dimensión desde la
    # dificultad de la TAREA servida en el ledger léxico. Se deriva aquí (una vez
    # por refresco de perfil) y se cachea en `learning_profile`; el camino
    # caliente del drill solo lee la fila única. Sin muestra queda vacío y todo
    # se comporta como V3.52.2.
    # V3.54 (Learner Skill State 3.0): además se conserva la modalidad, `skill ×
    # dimensión` (fuente de verdad); `observed_capacity` es la proyección legacy.
    observed_rows = await run_in_threadpool(
        evidence_repo.list_observed_rows, user_id
    )
    observed = learner_skill.observed_skill_state(observed_signals(observed_rows))

    # V3.62 (Student Skill State 4.0): UN modelo del alumno por modalidad ×
    # competencia, alimentado por las CUATRO fuentes de evidencia (ledger léxico,
    # `academy_evidence`, `listening_attempts` y `pronunciation_attempts`) con la
    # MISMA puerta espaciada. Es ADITIVO: ninguna decisión de tareas lo lee (el
    # drill, el ELV, el planner y `transfer.context_for` siguen leyendo el estado
    # de V3.61), y `dimensions` del camino léxico es idéntico a
    # `observed_skill_capacity` (test de paridad).
    academy_rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    listening_rows = await run_in_threadpool(listening_repo.list_attempts, user_id)
    pronunciation_rows = await run_in_threadpool(
        pronunciation_repo.list_attempts, user_id
    )
    state_rows = skill_state_service.skill_state_sources(
        lexicon=observed_rows,
        academy=academy_rows,
        listening=listening_rows,
        pronunciation=pronunciation_rows,
        objectives=skill_axis.objective_competences_index(),
    )
    state = skill_state_service.skill_state(
        state_rows,
        level=student_model["current_level"],
        now=datetime.now(timezone.utc).isoformat(),
    )

    skills = _skill_states(student_model["skills"])
    bands = _bands_from_skills(student_model["skills"])
    level = student_model["estimated_level"]
    current_level = student_model["current_level"]
    # La profundidad se mide en el nivel del Student Model actual (el mismo de
    # `competence_states` y de las muestras por destreza del perfil).
    depth_by_skill = _evidence_depth_out(student_model["skills"], current_level)
    # La profundidad de evidencia también se expone por destreza en `skills`.
    for skill_state in skills:
        report = depth_by_skill.get(skill_state["skill"])
        if report is not None:
            skill_state["evidence_depth"] = report["depth"]
            skill_state["minimum_evidence"] = report["minimum_evidence"]

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
        # V3.52 (P1-01): el nivel DEMOSTRADO se expone aparte del estimado. Es
        # `None` mientras no haya certificación con retención (nunca hipotético).
        "demonstrated_level": student_model["demonstrated_level"],
        # V3.53 (Learner Skill State 2.0): estado OBSERVADO (nivel equivalente y
        # capacidad por dimensión) derivado de la evidencia de dificultad.
        # V3.54 (Learner Skill State 3.0): además por SKILL × dimensión (fuente
        # de verdad) con su cobertura y nivel por skill; `observed_capacity` se
        # conserva como proyección legacy.
        "observed_level": observed["observed_level"],
        "observed_capacity": observed["observed_capacity"],
        "observed_skill_capacity": observed["observed_skill_capacity"],
        "observed_skill_level": observed["observed_skill_level"],
        "skill_coverage": observed["skill_coverage"],
        # V3.62 (Student Skill State 4.0): estado unificado por modalidad ×
        # competencia y su resumen derivado. Aditivo: no cambia ninguna decisión.
        "skill_state": state,
        "skill_state_summary": skill_state_service.skill_state_summary(state),
        "estimated_bands": bands,
        "estimated_descriptor": level_descriptor(level),
        "estimated_confidence": student_model["confidence"],
        "overall_ability": student_model["estimated_numeric"],
        "target_level": student_model["target_level"],
        "skills": skills,
        "evidence_depth": list(depth_by_skill.values()),
        "competence_states": competence_states(
            student_model["skills"], student_model["current_level"]
        ),
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
    # V3.52 (P1-01): la caché guarda AMBOS niveles. `cefr_level` se mantiene con
    # el estimado por compatibilidad; el suelo del drill lee `demonstrated_level`
    # (certificación) y cae al estimado solo si no existe.
    # V3.53: además se cachea el estado OBSERVADO (`observed_level` +
    # `observed_capacity`, vector serializado) para el suelo del drill en O(1).
    # V3.54: `observed_skill_capacity` guarda la capacidad por skill × dimensión
    # (JSON determinista) que el drill lee para no mezclar modalidades.
    await run_in_threadpool(
        profile_repo.set_level_state,
        user_id,
        estimated_level=profile["estimated_level"],
        demonstrated_level=profile["demonstrated_level"] or "",
        cefr_level=profile["estimated_level"],
        observed_level=profile["observed_level"] or "",
        observed_capacity=difficulty.format_vector(profile["observed_capacity"]),
        observed_skill_capacity=json.dumps(
            profile["observed_skill_capacity"], ensure_ascii=False, sort_keys=True
        ),
    )
    # V3.62: el estado unificado se cachea con un escritor DEDICADO (columna
    # aditiva) en JSON determinista (`sort_keys=True`), para que el contrato sea
    # estable entre refrescos y el drill no pague el coste de recomputarlo.
    await run_in_threadpool(
        profile_repo.set_skill_state,
        user_id,
        json.dumps(profile["skill_state"], ensure_ascii=False, sort_keys=True),
    )
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
            "skills": s["skills"],
        }
        for s in history
    ]
    return profile


async def get_profile_context(user_id: str) -> dict | None:
    """Devuelve el perfil para construir el prompt del tutor (sin persistir).
    Devuelve None si el usuario no existe."""
    return await _compute_profile(user_id)

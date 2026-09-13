"""Lectura O(1) del estado del alumno desde la caché del Student Model.

V3.56 (Planner 2.0) necesita en la cola de repaso la MISMA lectura que el drill
de transferencia (`domain.vocabulary`): suelo por modalidad y capacidad observada
por skill para predecir el éxito de la tarea. Tener dos derivaciones distintas
permitiría que la cola y el drill discrepasen sobre el mismo alumno (premisa 10),
así que la lectura vive aquí, en UN solo sitio, y `domain.vocabulary` delega.

No se ubica en `domain.profile` (el candidato natural) porque `domain.academy`
importa `domain.vocabulary`, que a su vez delegaría aquí: ponerlo en
`domain.profile` crearía el ciclo `vocabulary → profile → academy → vocabulary`.

Lee `learning_profile` (fila única, coste O(1)) y aplica
`student_state.level_state`: la caché guarda los niveles SEPARADOS que escribe
`domain.profile.get_profile_summary` — `estimated_level` (banda de práctica
continua), `demonstrated_level` (certificación con retención) y
`observed_level`/`observed_skill_capacity` (capacidad OBSERVADA por skill ×
dimensión) — y conserva `cefr_level` como nivel DECLARADO/legacy.

NO recalcula el Student Model en el camino caliente. Nunca lanza.
"""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import profile as profile_repo
from services import difficulty, learner_skill, student_state
from services.evidence import LEXICAL_SKILLS


def empty_learner_level_state() -> dict:
    """Estado de nivel neutro (sin caché): MISMA forma que el camino normal.

    Une el estado neutro de nivel (`student_state.empty_state`) con el observado
    (`learner_skill.empty_state`, V3.54) y añade las claves derivadas del drill,
    para que el contrato no cambie de forma entre el camino con perfil y el
    camino degradado. Dict nuevo en cada llamada. Nunca lanza.
    """
    return {
        **student_state.empty_state(),
        "observed_capacity": {},
        "learner_capacity": {},
        "observed_skill_capacity": {},
        "observed_skill_level": {},
        "skill_coverage": {},
        "floor_level_by_skill": {skill: "" for skill in LEXICAL_SKILLS},
        "floor_source_by_skill": {skill: "none" for skill in LEXICAL_SKILLS},
    }


async def learner_level_state(user_id: str) -> dict:
    """Estado de nivel del alumno desde la caché del Student Model (V3.54).

    Devuelve `{practice_level, estimated_cefr, demonstrated_cefr, observed_cefr,
    floor_level, floor_source, observed_capacity, learner_capacity,
    observed_skill_capacity, observed_skill_level, skill_coverage,
    floor_level_by_skill, floor_source_by_skill}`. El suelo global prioriza lo
    DEMOSTRADO, luego lo OBSERVADO, luego lo estimado y lo declarado; sin nivel
    conocido devuelve el estado vacío y el drill conserva el comportamiento de
    V3.46/V3.47 (el motor de dificultad no filtra). `learner_capacity` es el
    suelo efectivo por dimensión (proyección legacy).

    V3.54 (Learner Skill State 3.0): `observed_skill_capacity` (skill ×
    dimensión, JSON cacheado) es la fuente de verdad por modalidad y
    `floor_level_by_skill`/`floor_source_by_skill` dan el suelo de CADA skill
    (una capacidad escrita NO eleva el suelo oral). Nunca lanza.
    """
    try:
        row = await run_in_threadpool(profile_repo.get_profile, user_id)
    except Exception:  # noqa: BLE001 — preferencia no bloqueante
        return empty_learner_level_state()
    row = row or {}
    observed_capacity = difficulty.parse_vector(row.get("observed_capacity"))
    observed_skill_capacity = learner_skill.normalize_skill_capacity(
        row.get("observed_skill_capacity")
    )
    observed_skill_level = learner_skill.level_from_skill_capacity(
        observed_skill_capacity
    )
    coverage = learner_skill.skill_coverage(observed_skill_capacity)
    state = student_state.level_state(
        practice_level=row.get("cefr_level") or "",
        estimated_cefr=row.get("estimated_level") or "",
        demonstrated_cefr=row.get("demonstrated_level") or "",
        observed_cefr=row.get("observed_level") or "",
    )
    floor_by_skill: dict[str, str] = {}
    source_by_skill: dict[str, str] = {}
    for skill in LEXICAL_SKILLS:
        level, source = student_state.floor_level_for_skill(
            skill,
            practice_level=state["practice_level"],
            estimated_cefr=state["estimated_cefr"],
            demonstrated_cefr=state["demonstrated_cefr"],
            observed_skill_level=observed_skill_level,
            observed_cefr=state["observed_cefr"],
        )
        floor_by_skill[skill] = level
        source_by_skill[skill] = source
    return {
        **state,
        "observed_capacity": observed_capacity,
        "learner_capacity": learner_skill.learner_capacity(
            state["floor_level"], observed_capacity
        ),
        "observed_skill_capacity": observed_skill_capacity,
        "observed_skill_level": observed_skill_level,
        "skill_coverage": coverage,
        "floor_level_by_skill": floor_by_skill,
        "floor_source_by_skill": source_by_skill,
    }

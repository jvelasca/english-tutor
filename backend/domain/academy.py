"""Servicio de dominio de la Academy: orquesta currículum, repositorios y lógica."""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import academy as academy_repo
from repositories import grammar as grammar_repo
from schemas.academy import (
    AttemptOut,
    EnrollmentOut,
    ExamItemOut,
    ExamOut,
    ExamResultOut,
    LessonCompletedOut,
    LevelCompletionOut,
    LevelDetailOut,
    LevelProgressOut,
    LevelSummaryOut,
    MasteryOut,
    ModuleProgressOut,
    NextObjectiveOut,
    ObjectiveAssessmentOut,
    ObjectiveProgressOut,
    ObjectiveStateOut,
    PlacementItemOut,
    PlacementOut,
    PlacementResultOut,
    SkillScoreOut,
)
from services import academy as academy_svc
from services.context import build_lesson_prompt
from services.curriculum import (
    CEFR_ORDER,
    Level,
    get_objective,
    load_all_levels,
    load_assessments,
    next_level_id,
)

_LEVEL_TITLES = {
    "A1": ("Beginner", "Introduce yourself, everyday life, family, home and plans."),
    "A2": ("Elementary", "Past, future and common situations."),
    "B1": ("Intermediate", "Opinions, experiences and connected speech."),
    "B2": ("Upper-Intermediate", "Argumentation and complex texts."),
    "C1": ("Advanced", "Nuance, register and abstract topics."),
    "C2": ("Proficiency", "Precision, subtlety and near-native command."),
}

def _iter_objectives(level: Level):
    """Recorre (module, unit, lesson, objective, order) en orden de aparición."""
    order = 0
    for mod in level.modules:
        for unit in mod.units:
            for lesson in unit.lessons:
                for obj in lesson.objectives:
                    order += 1
                    yield mod, unit, lesson, obj, order


def _split_objective_mastery(
    obj_mastery: dict[str, dict[str, dict]],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, int]]]:
    """Separa el mapa {objective_id: {skill: estado}} en scores y attempts.

    El estado por destreza incluye `score` y `attempts`, necesarios para que la
    lógica pura decida el dominio con el mínimo de intentos."""
    objective_scores = {
        oid: {skill: state["score"] for skill, state in skills.items()}
        for oid, skills in obj_mastery.items()
    }
    objective_attempts = {
        oid: {skill: state["attempts"] for skill, state in skills.items()}
        for oid, skills in obj_mastery.items()
    }
    return objective_scores, objective_attempts


def _objective_state(
    level: Level,
    mod,
    unit,
    lesson,
    obj,
    order: int,
    mastered_ids: set[str],
    skill_scores: dict[str, float],
    skill_attempts: dict[str, int],
    attempts: dict[str, dict[str, int]],
) -> ObjectiveStateOut:
    progress = academy_svc.objective_progress(obj, skill_scores, skill_attempts)
    att = academy_svc.objective_attempts(obj.id, attempts)
    if obj.id in mastered_ids:
        status = "mastered"
    elif att["attempts"] > 0:
        status = "review"
    else:
        status = "available"
    return ObjectiveStateOut(
        id=obj.id,
        can_do=obj.can_do,
        title=obj.title,
        skills=obj.skills,
        concepts=obj.concepts,
        vocabulary=obj.vocabulary,
        thresholds=obj.thresholds,
        activities=[
            {
                "id": a.id,
                "type": a.type,
                "instruction": a.instruction,
                "target": a.target,
            }
            for a in obj.activities
        ],
        checks=[
            {
                "id": c.id,
                "skill": c.skill,
                "prompt": c.prompt,
                "options": c.options,
            }
            for c in obj.checks
        ],
        module_id=mod.id,
        module_title=mod.title,
        unit_id=unit.id,
        unit_title=unit.title,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        order=order,
        status=status,
        attempts=att["attempts"],
        correct=att["correct"],
        incorrect=att["incorrect"],
        progress=ObjectiveProgressOut(
            objective_id=obj.id,
            skills=[SkillScoreOut(**s) for s in progress["skills"]],
            mastered=progress["mastered"],
        ),
    )


def _level_summary(
    level_id: str,
    enrolled: bool,
    objective_scores: dict[str, dict[str, float]],
    objective_attempts: dict[str, dict[str, int]],
    attempts: dict[str, dict[str, int]],
    completed_level_ids: set[str],
) -> LevelSummaryOut:
    available = level_id in {lv.level_id for lv in _loaded_levels}
    meta = _LEVEL_TITLES.get(level_id.upper(), ("", ""))
    level = level_id.upper()
    objective_count = 0
    progress = 0.0
    counters = {"correct": 0, "incorrect": 0, "to_review": 0}
    if available:
        lv = next(x for x in _loaded_levels if x.level_id == level_id)
        objective_count = len(lv.objectives())
        mastered = academy_svc.mastered_objective_ids(
            lv, objective_scores, objective_attempts
        )
        counters = academy_svc.rollup_counters(
            [o.id for o in lv.objectives()], mastered, attempts
        )
        progress = (
            round(counters["correct"] / objective_count, 3) if objective_count else 0.0
        )
    return LevelSummaryOut(
        level_id=level_id,
        level=level,
        title=meta[0],
        description=meta[1],
        objective_count=objective_count,
        available=available,
        unlocked=academy_svc.enrollment_unlocked(level_id, completed_level_ids),
        enrolled=enrolled,
        progress=progress,
        **counters,
    )


# Cache de niveles cargados (contenido estático; se carga una vez por proceso).
_loaded_levels: list[Level] = load_all_levels()
_levels_by_id = {lv.level_id: lv for lv in _loaded_levels}


async def list_levels(user_id: str) -> list[LevelSummaryOut]:
    enrollments = await run_in_threadpool(academy_repo.list_enrollments, user_id)
    enrolled_ids = {e["level_id"] for e in enrollments}
    completed_level_ids = {
        e["level_id"] for e in enrollments if e["status"] == "completed"
    }
    summaries = []
    for lv in _loaded_levels:
        obj_mastery = await run_in_threadpool(
            academy_repo.list_objective_mastery, user_id, lv.level_id
        )
        objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
        attempts = await run_in_threadpool(
            academy_repo.list_attempts, user_id, lv.level_id
        )
        summaries.append(
            _level_summary(
                lv.level_id,
                lv.level_id in enrolled_ids,
                objective_scores,
                objective_attempts,
                attempts,
                completed_level_ids,
            )
        )
    # Añade los niveles CEFR aún no disponibles (p. ej. B1..C2 sin contenido).
    existing = {s.level_id for s in summaries}
    for code in CEFR_ORDER:
        lid = code.lower()
        if lid not in existing:
            summaries.append(
                _level_summary(
                    lid, lid in enrolled_ids, {}, {}, {}, completed_level_ids
                )
            )
    order = {lid: i for i, lid in enumerate(code.lower() for code in CEFR_ORDER)}
    summaries.sort(key=lambda s: order.get(s.level_id, 99))
    return summaries


async def get_level_detail(level_id: str, user_id: str) -> LevelDetailOut | None:
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    attempts = await run_in_threadpool(academy_repo.list_attempts, user_id, level_id)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    objectives = [
        _objective_state(
            lv,
            mod,
            unit,
            lesson,
            obj,
            order,
            mastered,
            objective_scores.get(obj.id, {}),
            objective_attempts.get(obj.id, {}),
            attempts,
        )
        for mod, unit, lesson, obj, order in _iter_objectives(lv)
    ]
    return LevelDetailOut(
        level_id=lv.level_id,
        level=lv.level,
        title=lv.title,
        description=lv.description,
        objectives=objectives,
        modules_progress=[
            ModuleProgressOut(**m)
            for m in academy_svc.module_progress_with_counters(lv, mastered, attempts)
        ],
        progress=LevelProgressOut(
            **academy_svc.level_progress_with_counters(lv, mastered, attempts)
        ),
    )


async def _completed_level_ids(user_id: str) -> set[str]:
    """Ids de nivel cuyo estado de matrícula es 'completed'."""
    enrollments = await run_in_threadpool(academy_repo.list_enrollments, user_id)
    return {e["level_id"] for e in enrollments if e["status"] == "completed"}


async def enrollment_blocked(user_id: str, level_id: str) -> bool:
    """True si el nivel existe pero no está desbloqueado (para 403 vs 404)."""
    if level_id not in _levels_by_id:
        return False
    completed = await _completed_level_ids(user_id)
    return not academy_svc.enrollment_unlocked(level_id, completed)


async def enroll(user_id: str, level_id: str) -> EnrollmentOut | None:
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    completed = await _completed_level_ids(user_id)
    if not academy_svc.enrollment_unlocked(level_id, completed):
        return None
    ok = await run_in_threadpool(academy_repo.enroll, user_id, level_id, lv.level)
    if not ok:
        return None
    row = await run_in_threadpool(academy_repo.get_enrollment, user_id, level_id)
    return EnrollmentOut(**row) if row else None


async def list_enrollments(user_id: str) -> list[EnrollmentOut]:
    rows = await run_in_threadpool(academy_repo.list_enrollments, user_id)
    return [EnrollmentOut(**r) for r in rows]


async def get_mastery(user_id: str) -> list[MasteryOut]:
    rows = await run_in_threadpool(academy_repo.list_skill_mastery, user_id)
    by_level: dict[str, dict[str, float]] = {}
    for r in rows:
        by_level.setdefault(r["level_id"], {})[r["skill"]] = r["score"]
    return [MasteryOut(level_id=k, skills=v) for k, v in by_level.items()]


async def next_objective(user_id: str, level_id: str) -> NextObjectiveOut | None:
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    oid, reason = academy_svc.recommend_next(lv, mastered, objective_scores)
    return NextObjectiveOut(objective_id=oid, level_id=level_id, reason=reason)


async def lesson_prompt(user_id: str, objective_id: str) -> str | None:
    """System prompt del AI Teacher para la lección de un objetivo, o None si el
    objetivo no existe (el chat cae al prompt genérico)."""
    for lv in _loaded_levels:
        obj = get_objective(lv, objective_id)
        if obj is not None:
            mastery = await run_in_threadpool(
                academy_repo.get_objective_mastery, user_id, lv.level_id, objective_id
            )
            errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
            return build_lesson_prompt(obj.model_dump(), lv.level, mastery, errors)
    return None


async def record_attempts(
    user_id: str,
    level_id: str,
    objective_id: str,
    results: list[dict],
) -> AttemptOut | None:
    """Registra los intentos de una actividad (solo alimentan contadores).

    Los intentos binarios ('correct'/'incorrect') NO conceden mastery: la evidencia
    determinista que mueve el modelo de mastery llega por `/objective/assessment`
    y el examen de nivel. Así se separa "actividad completada" de "evidencia".
    """
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    recorded = 0
    for r in results:
        skill = r["skill"]
        result = r["result"]
        if skill not in obj.skills or result not in ("correct", "incorrect"):
            continue
        ok = await run_in_threadpool(
            academy_repo.record_attempt,
            user_id,
            level_id,
            objective_id,
            skill,
            result,
        )
        if ok:
            recorded += 1
    return AttemptOut(recorded=recorded)


async def record_lesson_completed(
    user_id: str, level_id: str, objective_id: str
) -> LessonCompletedOut | None:
    """Registra que el alumno terminó una lección (sin declarar acierto)."""
    lv = _levels_by_id.get(level_id)
    if lv is None or get_objective(lv, objective_id) is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    ok = await run_in_threadpool(
        academy_repo.record_lesson_completed, user_id, level_id, objective_id
    )
    if not ok:
        return None
    return LessonCompletedOut(
        level_id=level_id, objective_id=objective_id, recorded=True
    )


async def submit_objective_assessment(
    user_id: str, level_id: str, objective_id: str, answers: dict[str, int]
) -> ObjectiveAssessmentOut | None:
    """Puntúa los checks deterministas de un objetivo y aplica la evidencia.

    El cliente envía respuestas (item_id → índice elegido), nunca puntuaciones.
    El servidor puntúa con `correct_index` y alimenta el modelo de mastery
    determinista por destreza."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    scored = academy_svc.score_items(obj.checks, answers)
    # Evidencia por ítem (reproducible y versionada), antes de agregar mastery.
    for ev in academy_svc.evidence_from_items(
        obj.checks,
        answers,
        level_id=level_id,
        objective_id=objective_id,
        source="objective_assessment",
        curriculum_version=lv.version,
    ):
        await run_in_threadpool(academy_repo.record_evidence, user_id, **ev)
    mastery_updates: dict[str, float] = {}
    for skill, b in scored["skills"].items():
        row = await run_in_threadpool(
            academy_repo.get_objective_row, user_id, level_id, objective_id, skill
        )
        state = academy_svc.next_mastery_state(
            row, b["score"], obj.threshold(skill)
        )
        await run_in_threadpool(
            academy_repo.apply_objective_evidence,
            user_id,
            level_id,
            objective_id,
            skill,
            state,
        )
        mastery_updates[skill] = state["score"]
    return ObjectiveAssessmentOut(
        level_id=level_id,
        objective_id=objective_id,
        overall=scored["overall"],
        correct=scored["correct"],
        total=scored["total"],
        skills=scored["skills"],
        mastery=mastery_updates,
    )


async def get_placement() -> PlacementOut:
    data = load_assessments()
    p = data.placement
    return PlacementOut(
        id=p.id,
        title=p.title,
        description=p.description,
        items=[
            PlacementItemOut(
                id=it.id,
                skill=it.skill,
                difficulty=it.difficulty,
                prompt=it.prompt,
                options=it.options,
            )
            for it in p.items
        ],
    )


async def submit_placement(
    user_id: str, answers: dict[str, int]
) -> PlacementResultOut | None:
    data = load_assessments()
    items = data.placement.items
    result = academy_svc.placement_result(items, answers)
    await run_in_threadpool(
        academy_repo.record_assessment_result,
        user_id,
        data.placement.id,
        "",
        result,
        True,
    )
    return PlacementResultOut(**result)


async def get_exam(level_id: str) -> ExamOut | None:
    data = load_assessments()
    exam = data.exams.get(level_id)
    if exam is None:
        return None
    return ExamOut(
        id=exam.id,
        title=exam.title,
        min_per_skill=exam.min_per_skill,
        skills=exam.skills,
        items=[
            ExamItemOut(id=it.id, skill=it.skill, prompt=it.prompt, options=it.options)
            for it in exam.items
        ],
    )


async def submit_exam(
    user_id: str, level_id: str, answers: dict[str, int]
) -> ExamResultOut | None:
    data = load_assessments()
    exam = data.exams.get(level_id)
    lv = _levels_by_id.get(level_id)
    if exam is None or lv is None:
        return None
    # El examen de un nivel no salta la progresión: solo puede presentarse si el
    # nivel ya está matriculado o desbloqueado (nivel anterior completado).
    already_enrolled = await run_in_threadpool(
        academy_repo.get_enrollment, user_id, level_id
    )
    if already_enrolled is None:
        completed = await _completed_level_ids(user_id)
        if not academy_svc.enrollment_unlocked(level_id, completed):
            return None
        await run_in_threadpool(academy_repo.enroll, user_id, level_id, lv.level)
    result = academy_svc.exam_result(exam, answers)
    # Evidencia por ítem del examen (reproducible y versionada).
    for ev in academy_svc.evidence_from_items(
        exam.items,
        answers,
        level_id=level_id,
        source="exam",
        assessment_version=exam.id,
        curriculum_version=lv.version,
    ):
        await run_in_threadpool(academy_repo.record_evidence, user_id, **ev)
    await run_in_threadpool(
        academy_repo.record_assessment_result,
        user_id,
        exam.id,
        level_id,
        result,
        result["passed"],
    )
    if result["passed"]:
        # Persiste evidencia por destreza vía el modelo de mastery determinista,
        # completitud del nivel y desbloqueo del siguiente nivel.
        for skill, b in result["skills"].items():
            row = await run_in_threadpool(
                academy_repo.get_skill_row, user_id, level_id, skill
            )
            state = academy_svc.next_mastery_state(row, b["score"], exam.min_per_skill)
            await run_in_threadpool(
                academy_repo.apply_skill_evidence, user_id, level_id, skill, state
            )
        await run_in_threadpool(
            academy_repo.record_level_completion,
            user_id,
            level_id,
            lv.level,
            result["overall"],
        )
        await run_in_threadpool(
            academy_repo.set_enrollment_status, user_id, level_id, "completed"
        )
        nxt = next_level_id(lv.level)
        if nxt and nxt in _levels_by_id:
            await run_in_threadpool(academy_repo.enroll, user_id, nxt, nxt.upper())
    else:
        # Remediation pack: objetivos del nivel dirigidos a cada destreza suspendida.
        result["remediation"] = {
            skill: data.remediation.get(skill, []) for skill in result["failed_skills"]
        }
    return ExamResultOut(**result)


async def list_level_completions(user_id: str) -> list[LevelCompletionOut]:
    rows = await run_in_threadpool(academy_repo.list_level_completions, user_id)
    return [
        LevelCompletionOut(
            id=r["id"],
            level_id=r["level_id"],
            level=r["level"],
            overall=r["overall"],
            awarded_at=r["awarded_at"],
        )
        for r in rows
    ]

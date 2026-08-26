"""Servicio de dominio de la Academy: orquesta currículum, repositorios y lógica."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from domain.errors import EvidenceInvariantError
from repositories import academy as academy_repo
from repositories import grammar as grammar_repo
from repositories import listening as listening_repo
from schemas.academy import (
    AttemptOut,
    CefrProfileOut,
    EnrollmentOut,
    ExamItemOut,
    ExamOut,
    ExamResultOut,
    LearningGoalIn,
    LearningGoalOut,
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
    PlacementAdaptiveOut,
    PlacementItemOut,
    PlacementOut,
    PlacementProfileOut,
    PlacementResultOut,
    PlacementStartOut,
    PronunciationResultOut,
    ReadinessOut,
    ReassessmentOut,
    RemediationPlanOut,
    SessionOut,
    SessionStepOut,
    SkillScoreOut,
    SpeakingResultOut,
    SpeakingTaskResultOut,
    StudentModelOut,
    TodayItemOut,
    TodayPlanOut,
    WritingResultOut,
    WritingTaskResultOut,
)
from services import academy as academy_svc
from services import adaptive, speaking_llm, writing_llm
from services import pronunciation as pronunciation_svc
from services import speaking as speaking_svc
from services import writing as writing_svc
from services.context import build_lesson_prompt
from services.curriculum import (
    ASSESSMENT_VERSION,
    CEFR_ORDER,
    PLACEMENT_VERSION,
    Level,
    get_objective,
    load_all_levels,
    load_assessments,
    next_level_id,
)
from services.listening import listening_diagnostic

logger = logging.getLogger(__name__)

_LEVEL_TITLES = {
    "A1": ("Beginner", "Introduce yourself, everyday life, family, home and plans."),
    "A2": ("Elementary", "Past, future and common situations."),
    "B1": ("Intermediate", "Opinions, experiences and connected speech."),
    "B2": ("Upper-Intermediate", "Argumentation and complex texts."),
    "C1": ("Advanced", "Nuance, register and abstract topics."),
    "C2": ("Proficiency", "Precision, subtlety and near-native command."),
}

DEFAULT_GOAL = {
    "goal_type": "general",
    "minutes_per_day": 15,
    "days_per_week": 5,
    "target_level": "B1",
}


def _today() -> str:
    """Fecha UTC de hoy en `YYYY-MM-DD` (reseteo diario de la sesión)."""
    return datetime.now(timezone.utc).date().isoformat()


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


async def _record_evidence_validated(
    user_id: str, level: Level, records: list[dict]
) -> int:
    """Valida y persiste registros de evidencia; rechaza los que violen invariantes.

    Punto único por el que pasa toda la evidencia del dominio. Cualquier
    violación es un bug de servidor (la evidencia la genera internamente el
    dominio), así que se registra en logs y se eleva `EvidenceInvariantError`
    sin persistir nada. Devuelve el nº de registros persistidos.
    """
    violations: list[str] = []
    for ev in records:
        violations.extend(
            academy_svc.evidence_record_errors(ev, user_id=user_id, level=level)
        )
    if violations:
        logger.error(
            "Evidence rejected user=%s level=%s: %s",
            user_id,
            level.level_id,
            "; ".join(violations),
        )
        raise EvidenceInvariantError(user_id, level.level_id, violations)
    recorded = 0
    for ev in records:
        await run_in_threadpool(academy_repo.record_evidence, user_id, **ev)
        recorded += 1
    return recorded


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


async def _skill_trends(user_id: str) -> dict[str, float | None]:
    """Tendencia por destreza (% de variación de accuracy, últimos 7d vs anterior).

    Se calcula sobre toda la evidencia del usuario (no solo del nivel actual): la
    precisión media de los últimos 7 días comparada con la de los 7 días previos.
    Devuelve `None` cuando no hay línea base comparable.
    """
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    now = datetime.now(timezone.utc)
    cutoff7 = (now - timedelta(days=7)).isoformat()
    cutoff14 = (now - timedelta(days=14)).isoformat()
    recent: dict[str, list[float]] = {}
    previous: dict[str, list[float]] = {}
    for r in rows:
        skill = r["skill"]
        created = r["created_at"]
        if created >= cutoff7:
            recent.setdefault(skill, []).append(r["result"])
        elif created >= cutoff14:
            previous.setdefault(skill, []).append(r["result"])
    trends: dict[str, float | None] = {}
    for skill in set(recent) | set(previous):
        r = recent.get(skill, [])
        p = previous.get(skill, [])
        recent_acc = sum(r) / len(r) if r else None
        previous_acc = sum(p) / len(p) if p else None
        if recent_acc is not None and previous_acc is not None:
            trends[skill] = round((recent_acc - previous_acc) * 100, 1)
        else:
            trends[skill] = None
    return trends


async def _annotated_profile(user_id: str, lv: Level) -> list[dict]:
    """Perfil CEFR por destreza del nivel `lv`, anotado con stability y trend."""
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    evidence_rows = await run_in_threadpool(
        academy_repo.list_evidence, user_id, lv.level_id
    )
    now = datetime.now(timezone.utc).isoformat()
    skills = academy_svc.build_skill_profile(lv, obj_mastery, evidence_rows, now)
    # Puente con el motor de listening: expone sus sub-destrezas dentro de 'listening'.
    listening_attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    subskills = listening_diagnostic(listening_attempts)["subskills"]
    trends = await _skill_trends(user_id)
    for entry in skills:
        if entry["skill"] == "listening":
            entry["subskills"] = subskills
        entry["stability"] = adaptive.skill_stability(
            entry["score"], entry["confidence"], entry["last_evidence"], now
        )
        entry["trend"] = trends.get(entry["skill"])
    return skills


async def _current_level_id(user_id: str) -> str:
    """Nivel CEFR más alto en el que el alumno está matriculado (o `a1` si ninguno)."""
    enrollments = await run_in_threadpool(academy_repo.list_enrollments, user_id)
    best = None
    for e in enrollments:
        if e["level"] in CEFR_ORDER:
            if best is None or CEFR_ORDER.index(e["level"]) > CEFR_ORDER.index(
                best["level"]
            ):
                best = e
    return best["level_id"] if best is not None else "a1"


async def get_skill_profile(user_id: str, level_id: str) -> CefrProfileOut | None:
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    skills = await _annotated_profile(user_id, lv)
    overall = academy_svc.overall_cefr_score(skills)
    return CefrProfileOut(
        level_id=level_id,
        level=lv.level,
        overall=overall,
        skills=skills,
        critical_skills=academy_svc.critical_skills(skills),
    )


async def get_student_model(user_id: str) -> StudentModelOut:
    """Student Model 2.0: nivel actual/estimado, perfil por destreza con stability
    y trend, readiness hacia el siguiente nivel y reevaluación pendiente (si hay)."""
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)
    est = adaptive.estimated_level(skills)
    goal_row = await run_in_threadpool(academy_repo.get_goal, user_id)
    target = (
        goal_row["target_level"]
        if goal_row
        else (next_level_id(lv.level) or lv.level)
    )
    target = target.upper()
    history = await run_in_threadpool(academy_repo.list_assessment_results, user_id)
    now = datetime.now(timezone.utc).isoformat()
    reassessment = adaptive.reassessment_due(skills, history, now)
    return StudentModelOut(
        level_id=lv.level_id,
        current_level=lv.level,
        estimated_level=est["level"],
        estimated_numeric=est["numeric"],
        confidence=est["confidence"],
        target_level=target,
        skills=skills,
        critical_skills=academy_svc.critical_skills(skills),
        readiness=ReadinessOut(**adaptive.readiness(skills, target)),
        reassessment=ReassessmentOut(**reassessment) if reassessment else None,
    )


async def get_readiness(user_id: str, target_level: str) -> ReadinessOut:
    """Preparación por destreza para un nivel objetivo (p. ej. B1)."""
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)
    return ReadinessOut(**adaptive.readiness(skills, target_level))


async def get_today_plan(user_id: str) -> TodayPlanOut:
    """Plan de estudio de hoy: equilibrio weakness/review/new/easy_wins con minutos."""
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    remediation = academy_svc.remediation_plan(
        lv, skills, objective_scores, mastered
    )
    oid, _reason = academy_svc.recommend_next(lv, mastered, objective_scores)
    goal = await get_learning_goal(user_id)
    items = adaptive.today_plan(
        skills, lv, remediation, mastered, oid, budget_minutes=goal.minutes_per_day
    )
    return TodayPlanOut(
        items=[TodayItemOut(**i) for i in items],
        total_minutes=sum(i["minutes"] for i in items),
    )


async def get_session(user_id: str) -> SessionOut:
    """Sesión diaria (Session Engine): repaso vencido → listening → debilidad →
    nuevo → refuerzo, unificando las señales CEFR y de listening en una secuencia
    accionable con presupuesto del objetivo personal. Los pasos ya completados hoy
    se omiten (filtro por `step_key`)."""
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    remediation = academy_svc.remediation_plan(
        lv, skills, objective_scores, mastered
    )
    oid, _reason = academy_svc.recommend_next(lv, mastered, objective_scores)
    goal = await get_learning_goal(user_id)

    listening_rows = await run_in_threadpool(listening_repo.list_attempts, user_id)
    listening_weak = listening_diagnostic(listening_rows)["weak"]

    done = await run_in_threadpool(
        academy_repo.list_session_steps, user_id, _today()
    )
    steps = adaptive.session_plan(
        skills,
        lv,
        remediation,
        mastered,
        oid,
        listening_weak=listening_weak,
        budget_minutes=goal.minutes_per_day,
        exclude_keys=done,
    )
    summary = adaptive.session_summary(steps)
    return SessionOut(
        items=[SessionStepOut(**s) for s in steps],
        total_minutes=sum(s["minutes"] for s in steps),
        review_count=summary["review_count"],
        practice_count=summary["practice_count"],
    )


async def set_session_step_done(user_id: str, step_key: str) -> SessionOut | None:
    """Marca un paso de la sesión como completado hoy y devuelve la sesión actualizada.

    None si el usuario no existe."""
    ok = await run_in_threadpool(
        academy_repo.mark_session_step, user_id, step_key, _today()
    )
    if not ok:
        return None
    return await get_session(user_id)


async def get_learning_goal(user_id: str) -> LearningGoalOut:
    """Objetivo personal del usuario, con valores por defecto si aún no lo fija."""
    row = await run_in_threadpool(academy_repo.get_goal, user_id)
    if row is None:
        return LearningGoalOut(**DEFAULT_GOAL)
    return LearningGoalOut(**row)


async def set_learning_goal(
    user_id: str, goal: LearningGoalIn
) -> LearningGoalOut | None:
    """Crea o actualiza el objetivo personal. None si el usuario no existe."""
    ok = await run_in_threadpool(
        academy_repo.upsert_goal,
        user_id,
        goal.goal_type,
        goal.minutes_per_day,
        goal.days_per_week,
        goal.target_level,
    )
    if not ok:
        return None
    return await get_learning_goal(user_id)


async def get_remediation(user_id: str, level_id: str) -> RemediationPlanOut | None:
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, level_id
    )
    evidence_rows = await run_in_threadpool(
        academy_repo.list_evidence, user_id, level_id
    )
    now = datetime.now(timezone.utc).isoformat()
    profile = academy_svc.build_skill_profile(lv, obj_mastery, evidence_rows, now)
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    skills = academy_svc.remediation_plan(lv, profile, objective_scores, mastered)
    return RemediationPlanOut(level_id=level_id, level=lv.level, skills=skills)


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
            obj_mastery = await run_in_threadpool(
                academy_repo.list_objective_mastery, user_id, lv.level_id
            )
            evidence_rows = await run_in_threadpool(
                academy_repo.list_evidence, user_id, lv.level_id
            )
            now = datetime.now(timezone.utc).isoformat()
            skill_profile = academy_svc.build_skill_profile(
                lv, obj_mastery, evidence_rows, now
            )
            return build_lesson_prompt(
                obj.model_dump(), lv.level, mastery, errors, skill_profile
            )
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
    await _record_evidence_validated(
        user_id,
        lv,
        academy_svc.evidence_from_items(
            obj.checks,
            answers,
            level_id=level_id,
            objective_id=objective_id,
            source="objective_assessment",
            curriculum_version=lv.version,
            assessment_version=ASSESSMENT_VERSION,
        ),
    )
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


async def submit_speaking(
    user_id: str,
    level_id: str,
    objective_id: str,
    expected: str,
    heard: str,
    duration_seconds: float | None = None,
) -> SpeakingResultOut | None:
    """Puntúa una producción oral y alimenta el mastery de la destreza 'speaking'.

    El cliente envía la transcripción (`heard`) y la frase/tarea esperada
    (`expected`); el scorer determinista calcula los criterios y el overall, que se
    registran como evidencia estructurada y mueven el modelo de mastery sin que el
    LLM decida el score."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    result = speaking_svc.score_speaking(heard, expected, duration_seconds)
    await _record_evidence_validated(
        user_id,
        lv,
        speaking_svc.evidence_from_speaking(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
        ),
    )
    row = await run_in_threadpool(
        academy_repo.get_objective_row, user_id, level_id, objective_id, "speaking"
    )
    state = academy_svc.next_mastery_state(
        row, result["overall"], obj.threshold("speaking")
    )
    await run_in_threadpool(
        academy_repo.apply_objective_evidence,
        user_id,
        level_id,
        objective_id,
        "speaking",
        state,
    )
    return SpeakingResultOut(
        level_id=level_id,
        objective_id=objective_id,
        expected=result["expected"],
        heard=result["heard"],
        overall=result["overall"],
        criteria=result["criteria"],
        observed=result["observed"],
        speaking_mastery=state["score"],
    )


async def submit_speaking_task(
    user_id: str,
    level_id: str,
    objective_id: str,
    task: str,
    heard: str,
    model: str,
    duration_seconds: float | None = None,
) -> SpeakingTaskResultOut | None:
    """Puntúa una respuesta oral libre (tarea) usando evidencia extraída por el LLM.

    El LLM extrae la evidencia estructurada (`speaking_llm.extract_speaking_evidence`)
    y el scorer determinista (`scores_from_evidence`) calcula los criterios y el
    overall, que se registran como evidencia y mueven el mastery de 'speaking' sin
    que el LLM decida el score."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    evidence = await speaking_llm.extract_speaking_evidence(task, heard, model)
    if evidence is None:
        return None
    result = speaking_svc.scores_from_evidence(evidence, heard, duration_seconds)
    await _record_evidence_validated(
        user_id,
        lv,
        speaking_svc.evidence_from_speaking(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
        ),
    )
    row = await run_in_threadpool(
        academy_repo.get_objective_row, user_id, level_id, objective_id, "speaking"
    )
    state = academy_svc.next_mastery_state(
        row, result["overall"], obj.threshold("speaking")
    )
    await run_in_threadpool(
        academy_repo.apply_objective_evidence,
        user_id,
        level_id,
        objective_id,
        "speaking",
        state,
    )
    return SpeakingTaskResultOut(
        level_id=level_id,
        objective_id=objective_id,
        overall=result["overall"],
        criteria=result["criteria"],
        observed=result["observed"],
        speaking_mastery=state["score"],
        evidence=evidence,
    )


async def submit_writing(
    user_id: str, level_id: str, objective_id: str, expected: str, text: str
) -> WritingResultOut | None:
    """Puntúa una producción escrita controlada y alimenta el mastery de 'writing'."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    result = writing_svc.score_writing(text, expected)
    await _record_evidence_validated(
        user_id,
        lv,
        writing_svc.evidence_from_writing(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
        ),
    )
    row = await run_in_threadpool(
        academy_repo.get_objective_row, user_id, level_id, objective_id, "writing"
    )
    state = academy_svc.next_mastery_state(
        row, result["overall"], obj.threshold("writing")
    )
    await run_in_threadpool(
        academy_repo.apply_objective_evidence,
        user_id,
        level_id,
        objective_id,
        "writing",
        state,
    )
    return WritingResultOut(
        level_id=level_id,
        objective_id=objective_id,
        expected=result["expected"],
        text=result["text"],
        overall=result["overall"],
        criteria=result["criteria"],
        writing_mastery=state["score"],
    )


async def submit_pronunciation(
    user_id: str, level_id: str, objective_id: str, expected: str, heard: str
) -> PronunciationResultOut | None:
    """Puntúa una lectura en voz alta y alimenta el mastery de 'pronunciation'."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    result = pronunciation_svc.score_pronunciation_cefr(expected, heard)
    await _record_evidence_validated(
        user_id,
        lv,
        pronunciation_svc.evidence_from_pronunciation(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
        ),
    )
    row = await run_in_threadpool(
        academy_repo.get_objective_row, user_id, level_id, objective_id, "pronunciation"
    )
    state = academy_svc.next_mastery_state(
        row, result["overall"], obj.threshold("pronunciation")
    )
    await run_in_threadpool(
        academy_repo.apply_objective_evidence,
        user_id, level_id, objective_id, "pronunciation", state,
    )
    return PronunciationResultOut(
        level_id=level_id,
        objective_id=objective_id,
        expected=result["expected"],
        heard=result["heard"],
        overall=result["overall"],
        criteria=result["criteria"],
        pronunciation_mastery=state["score"],
    )


async def submit_writing_task(
    user_id: str,
    level_id: str,
    objective_id: str,
    task: str,
    text: str,
    model: str,
) -> WritingTaskResultOut | None:
    """Puntúa una producción escrita libre (tarea) con evidencia extraída por el LLM."""
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    evidence = await writing_llm.extract_writing_evidence(task, text, model)
    if evidence is None:
        return None
    result = writing_svc.scores_from_evidence(evidence)
    await _record_evidence_validated(
        user_id,
        lv,
        writing_svc.evidence_from_writing(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
        ),
    )
    row = await run_in_threadpool(
        academy_repo.get_objective_row, user_id, level_id, objective_id, "writing"
    )
    state = academy_svc.next_mastery_state(
        row, result["overall"], obj.threshold("writing")
    )
    await run_in_threadpool(
        academy_repo.apply_objective_evidence,
        user_id,
        level_id,
        objective_id,
        "writing",
        state,
    )
    return WritingTaskResultOut(
        level_id=level_id,
        objective_id=objective_id,
        overall=result["overall"],
        criteria=result["criteria"],
        writing_mastery=state["score"],
        evidence=evidence,
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


async def _record_placement_calibration(
    items: list, answers: dict[str, int]
) -> None:
    """Registra en la calibración observacional cada respuesta de `answers`.

    Solo los ítems conocidos del instrumento; los ids desconocidos se ignoran.
    La calibración es poblacional (no por usuario): acumula respuestas para poder
    estimar la dificultad/discriminación real de cada ítem en un paso posterior.
    """
    item_by_id = {it.id: it for it in items}
    for item_id, answer_index in answers.items():
        item = item_by_id.get(item_id)
        if item is None:
            continue
        await run_in_threadpool(
            academy_repo.record_placement_response,
            item_id,
            answer_index == item.correct_index,
        )


async def submit_placement(
    user_id: str, answers: dict[str, int]
) -> PlacementResultOut | None:
    data = load_assessments()
    items = data.placement.items
    result = academy_svc.placement_result(items, answers)
    await _record_placement_calibration(items, answers)
    await run_in_threadpool(
        academy_repo.record_assessment_result,
        user_id,
        data.placement.id,
        "",
        result,
        True,
    )
    return PlacementResultOut(**result)


async def start_placement(user_id: str) -> PlacementStartOut | None:
    """Inicia una sesión de placement adaptativo trazable y devuelve el primer ítem.

    Persiste una fila en `placement_sessions` con los ítems del instrumento (y su
    `placement_version`) para poder reconstruir qué se evaluó, con qué dificultad y
    bajo qué algoritmo, aunque el núcleo del motor siga siendo stateless. El primer
    ítem se elige por máxima información en θ inicial."""
    data = load_assessments()
    items = data.placement.items
    session = await run_in_threadpool(
        academy_repo.create_placement_session,
        user_id,
        PLACEMENT_VERSION,
        [it.model_dump() for it in items],
    )
    if session is None:
        return None
    next_item = academy_svc.select_next_item(
        items, set(), academy_svc.PLACEMENT_START_THETA
    )
    next_out = None
    if next_item is not None:
        next_out = PlacementItemOut(
            id=next_item.id,
            skill=next_item.skill,
            difficulty=next_item.difficulty,
            prompt=next_item.prompt,
            options=next_item.options,
        )
    return PlacementStartOut(
        session_id=session["id"],
        next_item=next_out,
        placement_version=PLACEMENT_VERSION,
    )


async def get_placement_profile(answers: dict[str, int]) -> PlacementProfileOut:
    """Perfil multiskill del placement a partir de las respuestas dadas.

    Cálculo puro (sin persistencia): reutiliza `placement_profile` para devolver
    θ/nivel/confianza por destreza más los agregados globales. No depende del
    usuario; el endpoint exige `current_user` solo para autenticar la llamada.
    """
    data = load_assessments()
    items = data.placement.items
    return PlacementProfileOut(**academy_svc.placement_profile(items, answers))


async def next_placement(
    user_id: str, answers: dict[str, int], session_id: int | None = None
) -> PlacementAdaptiveOut | None:
    """Siguiente ítem del placement adaptativo (IRT-lite/1PL) y resultado al
    terminar.

    El núcleo es stateless: el cliente envía sus respuestas parciales; el servidor
    recalcula la habilidad θ, elige el siguiente ítem por máxima información
    (Fisher; en la 1PL, dificultad más cercana a θ) y se detiene al agotar ítems,
    alcanzar el máximo, o cuando el error estándar de θ baja del umbral (tras un
    mínimo de ítems). Si se pasa `session_id`, además persiste la traza de la
    sesión (respuestas, historial de θ y resultado final, con el perfil multiskill)
    en `placement_sessions`, y registra en la calibración observacional solo las
    respuestas nuevas de esta llamada (delta contra la sesión, para no duplicar
    contadores)."""
    data = load_assessments()
    items = data.placement.items
    answered_ids = set(answers)
    responses = [
        (it.difficulty, answers[it.id] == it.correct_index)
        for it in items
        if it.id in answers
    ]
    theta = academy_svc.ability_theta(responses)
    se = academy_svc.placement_standard_error(theta, responses)
    done = academy_svc.placement_should_stop(len(answered_ids), len(items), se)

    theta_trace: list[dict] | None = None
    session = None
    if session_id is not None:
        session = await run_in_threadpool(
            academy_repo.get_placement_session, session_id
        )
        if session is None:
            return None
        theta_trace = list(session["theta_trace"]) + [
            {"answered": len(answered_ids), "theta": theta, "standard_error": se}
        ]

    # Calibración observacional: solo las respuestas nuevas de esta llamada.
    new_answers = dict(answers)
    if session is not None:
        new_answers = {
            k: v for k, v in answers.items() if k not in session["answers"]
        }
    await _record_placement_calibration(items, new_answers)

    if done:
        result = academy_svc.placement_result_adaptive(items, answers)
        await run_in_threadpool(
            academy_repo.record_assessment_result,
            user_id,
            data.placement.id,
            "",
            result,
            True,
        )
        if session_id is not None:
            await run_in_threadpool(
                academy_repo.update_placement_session,
                session_id,
                answers=answers,
                theta_trace=theta_trace,
                final_result=result,
            )
        return PlacementAdaptiveOut(
            session_id=session_id,
            next_item=None,
            theta=theta,
            standard_error=se,
            answered=result["answered"],
            done=True,
            result=result,
        )

    if session_id is not None:
        await run_in_threadpool(
            academy_repo.update_placement_session,
            session_id,
            answers=answers,
            theta_trace=theta_trace,
        )

    next_item = academy_svc.select_next_item(items, answered_ids, theta)
    next_out = None
    if next_item is not None:
        next_out = PlacementItemOut(
            id=next_item.id,
            skill=next_item.skill,
            difficulty=next_item.difficulty,
            prompt=next_item.prompt,
            options=next_item.options,
        )
    return PlacementAdaptiveOut(
        session_id=session_id,
        next_item=next_out,
        theta=theta,
        standard_error=se,
        answered=len(answered_ids),
        done=False,
        result=None,
    )


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
    await _record_evidence_validated(
        user_id,
        lv,
        academy_svc.evidence_from_items(
            exam.items,
            answers,
            level_id=level_id,
            source="exam",
            assessment_version=exam.id,
            curriculum_version=lv.version,
        ),
    )
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

"""Servicio de dominio de la Academy: orquesta currículum, repositorios y lógica."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from config import DEFAULT_MODEL
from domain import vocabulary as vocabulary_domain
from domain.errors import EvidenceInvariantError
from repositories import academy as academy_repo
from repositories import conversations as conversations_repo
from repositories import grammar as grammar_repo
from repositories import listening as listening_repo
from repositories import vocabulary as vocabulary_repo
from schemas.academy import (
    AssessmentV2InstrumentOut,
    AssessmentV2ItemOut,
    AssessmentV2LadderOut,
    AssessmentV2MasteryGateOut,
    AssessmentV2ReadinessOut,
    AssessmentV2ResultOut,
    AssessmentV2RetentionOut,
    AssessmentV2RetentionSkillOut,
    AssessmentV2SkillScoreOut,
    AssessmentV2StateOut,
    AssessmentV2StepOut,
    AttemptOut,
    CefrProfileOut,
    CourseMapOut,
    DashboardOut,
    EnrollmentOut,
    EvidenceGraphNodeOut,
    EvidenceGraphOut,
    ExamItemOut,
    ExamOut,
    ExamResultOut,
    FsrsCardOut,
    FsrsDueOut,
    FsrsExplainOut,
    FsrsReviewOut,
    FsrsSummaryOut,
    LearningGoalIn,
    LearningGoalOut,
    LessonCompletedOut,
    LevelCompletionOut,
    LevelDetailOut,
    LevelProgressOut,
    LevelSummaryOut,
    MasteryRecordOut,
    ModuleProgressOut,
    NextBestActivityOut,
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
    SpeakingAssessmentPartInfo,
    SpeakingAssessmentPartOut,
    SpeakingAssessmentPartScores,
    SpeakingAssessmentResultOut,
    SpeakingAssessmentStartOut,
    SpeakingAssessmentStateOut,
    SpeakingMissionAttemptOut,
    SpeakingMissionDrillOut,
    SpeakingMissionEvaluationOut,
    SpeakingMissionImprovementOut,
    SpeakingMissionOut,
    SpeakingMissionStateOut,
    SpeakingResultOut,
    SpeakingTaskResultOut,
    StudentModelOut,
    TodayItemOut,
    TodayPlanOut,
    WritingResultOut,
    WritingTaskResultOut,
)
from services import academy as academy_svc
from services import (
    adaptive,
    assessment_v2,
    cefr_descriptors,
    evidence_graph,
    fsrs,
    lexicon,
    speaking_assessment,
    speaking_llm,
    speaking_mission,
    speaking_scenarios,
    writing_llm,
)
from services import course as course_svc
from services import pronunciation as pronunciation_svc
from services import speaking as speaking_svc
from services import writing as writing_svc
from services.cefr import PRE_A1
from services.context import build_lesson_prompt
from services.curriculum import (
    ASSESSMENT_VERSION,
    CEFR_ORDER,
    PLACEMENT_VERSION,
    SPEAKING_ASSESSMENT_VERSION,
    SPEAKING_SCENARIOS_VERSION,
    Level,
    get_objective,
    load_all_levels,
    load_assessments,
    next_level_id,
)
from services.interaction import interaction_evidence
from services.listening import listening_diagnostic, route_competence
from services.mastery import mastery_records

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
    status: str,
) -> ObjectiveStateOut:
    progress = academy_svc.objective_progress(obj, skill_scores, skill_attempts)
    att = academy_svc.objective_attempts(obj.id, attempts)
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
    statuses = course_svc.objective_gated_status(lv, mastered, attempts)
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
            statuses[obj.id],
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


async def get_course_map(level_id: str, user_id: str) -> CourseMapOut | None:
    """Mapa del curso (V1.38): secuencia Course→Unit→Lesson + posición actual.

    Inyecta el perfil anotado para que cada unidad exponga sus 7 secciones,
    Learning Objectives y Mastery Gates (V2.2)."""
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
    profile = await _annotated_profile(user_id, lv)
    return CourseMapOut(
        **course_svc.course_map(lv, mastered, attempts, profile=profile)
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
    # Puente con el motor de speaking (V1.15): expone sus criterios de rúbrica como
    # sub-destrezas de 'speaking' (mismo patrón que listening).
    speaking_rows = [r for r in evidence_rows if r.get("skill") == "speaking"]
    speaking_subskills = speaking_svc.speaking_diagnostic(speaking_rows, now=now)[
        "criteria"
    ]
    trends = await _skill_trends(user_id)
    for entry in skills:
        if entry["skill"] == "listening":
            entry["subskills"] = subskills
            # Competencia de listening por ruta de práctica (H3/H5): la puerta de
            # ruta pasa a ser el gate FUNCTIONAL de la destreza y se consolida con
            # la retención retardada para DEMONSTRATED (ver `route_competence`).
            entry["routes"] = route_competence(listening_attempts)
        elif entry["skill"] == "speaking":
            entry["subskills"] = speaking_subskills
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


async def build_student_model(user_id: str) -> dict:
    """Fuente única del Student Model (sin proyección a un schema concreto).

    Construye el perfil CEFR por destreza anotado (score/confidence/stability/
    trend/subskills), el nivel estimado continuo y la preparación hacia el
    siguiente nivel. Tanto `/api/academy/student-model` como `/api/profile`
    proyectan sobre este mismo dict, de modo que comparten nivel, `overall_ability`
    y confianza (única fuente de verdad).
    """
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
    return {
        "level_id": lv.level_id,
        "current_level": lv.level,
        "estimated_level": est["level"],
        "estimated_numeric": est["numeric"],
        "confidence": est["confidence"],
        "target_level": target,
        "skills": skills,
        "critical_skills": academy_svc.critical_skills(skills),
        "readiness": adaptive.readiness(skills, target),
        "reassessment": reassessment,
        "mastery": mastery_records(skills, now),
    }


async def get_student_model(user_id: str) -> StudentModelOut:
    """Student Model 2.0: nivel actual/estimado, perfil por destreza con stability
    y trend, readiness hacia el siguiente nivel y reevaluación pendiente (si hay)."""
    sm = await build_student_model(user_id)
    return StudentModelOut(
        level_id=sm["level_id"],
        current_level=sm["current_level"],
        estimated_level=sm["estimated_level"],
        estimated_numeric=sm["estimated_numeric"],
        confidence=sm["confidence"],
        target_level=sm["target_level"],
        skills=sm["skills"],
        critical_skills=sm["critical_skills"],
        readiness=ReadinessOut(**sm["readiness"]),
        reassessment=(
            ReassessmentOut(**sm["reassessment"]) if sm["reassessment"] else None
        ),
        mastery=[MasteryRecordOut(**m.model_dump()) for m in sm["mastery"]],
    )


async def get_cefr_ladder(user_id: str) -> dict:
    """Escalera CEFR completa (Curriculum 2.0) con descriptores Can-Do.

    Devuelve el marco de descriptores (Pre-A1 → C2, incluyendo las bandas "plus")
    con las 9 dimensiones comunicativas y sitúa al alumno en la escalera continua:
    `estimated_band`/`estimated_numeric` derivan del Student Model y `is_current`
    marca la banda correspondiente en `bands`. Cada dimensión expone su `state`
    (V2.2) frente al dominio real del alumno: `mastered`/`in_progress`/
    `not_started` (✓/●/○), conectando el descriptor estático al Student Model.
    No certifica CEFR: es una referencia interna alineada al marco.
    """
    fw = cefr_descriptors.load_framework()
    sm = await build_student_model(user_id)
    numeric = float(sm["estimated_numeric"])
    # Sin evidencia el nivel estimado es `Pre-A1`: la escalera lo marca como banda
    # actual aunque `numeric` se mantenga en el suelo (1.0) de la escala continua.
    estimated_band = (
        "pre-a1"
        if sm["estimated_level"] == PRE_A1
        else cefr_descriptors.band_for_numeric(numeric)
    )
    dims = cefr_descriptors.dimensions()
    mastery = [m.model_dump() for m in sm["mastery"]]
    return {
        "dimensions": [
            {
                "id": d,
                "label": label,
                "state": adaptive.dimension_state(mastery, d),
            }
            for d, label in dims.items()
        ],
        "bands": [
            {
                "id": b.id,
                "label": b.label,
                "numeric": b.numeric,
                "title": b.title,
                "description": b.description,
                "can_do": b.can_do,
                "is_current": b.id == estimated_band,
            }
            for b in fw.bands
        ],
        "estimated_band": estimated_band,
        "estimated_numeric": numeric,
    }


async def get_readiness(user_id: str, target_level: str) -> ReadinessOut:
    """Preparación por destreza para un nivel objetivo (p. ej. B1)."""
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)
    return ReadinessOut(**adaptive.readiness(skills, target_level))


async def get_dashboard(user_id: str) -> DashboardOut:
    """Tríada Progress / Mastery / Readiness (V2.2) en una única fuente.

    Reutiliza el Student Model (mastery + readiness) y el progreso objetivo del
    nivel para que Home/Progress/Course muestren las mismas cifras.
    """
    sm = await build_student_model(user_id)
    lv = _levels_by_id.get(sm["level_id"]) or _levels_by_id["a1"]
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    objs = lv.objectives()
    progress = round(len(mastered) / len(objs), 3) if objs else 0.0
    mastery = [m.model_dump() for m in sm["mastery"]]
    return DashboardOut(
        **adaptive.student_dashboard(progress, mastery, sm["readiness"])
    )


async def get_speaking_diagnostic(user_id: str) -> dict:
    """Diagnóstico longitudinal de speaking (V1.15).

    Deriva el perfil por criterio de rúbrica (fluency/grammar/lexical/pronunciation/
    coherence/interaction) a partir de la evidencia de speaking registrada en
    `academy_evidence`, y lo expone con tendencia temporal y criterios débiles.
    """
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    speaking_rows = [r for r in rows if r.get("skill") == "speaking"]
    now = datetime.now(timezone.utc).isoformat()
    return speaking_svc.speaking_diagnostic(speaking_rows, now=now)


async def get_speaking_level(user_id: str) -> dict:
    """Speaking Assessment 1.0: nivel CEFR continuo de speaking + confianza."""
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    speaking_rows = [r for r in rows if r.get("skill") == "speaking"]
    return speaking_svc.speaking_level(speaking_rows)


async def get_speaking_journey(user_id: str) -> dict:
    """Speaking Journey (CEFR): trayectoria de nivel y confianza de speaking."""
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    speaking_rows = [r for r in rows if r.get("skill") == "speaking"]
    return speaking_svc.speaking_journey(speaking_rows)


async def get_speaking_endurance(user_id: str) -> dict:
    """Conversation Endurance (Speaking 2.0): resistencia a mantener una conversación.

    Deriva los hitos (30s→3min) de la telemetría de turnos hablados del alumno
    (duración por conversación) sin LLM ni red.
    """
    sessions = await run_in_threadpool(
        conversations_repo.student_speaking_sessions, user_id
    )
    return speaking_svc.conversation_endurance(sessions)


def list_speaking_scenarios() -> dict:
    """Catálogo de escenarios comunicativos (Speaking 3.0): contenido estático.

    No depende del usuario: son los escenarios disponibles para practicar
    conversación con objetivo comunicativo y métricas declaradas.
    """
    return {
        "version": SPEAKING_SCENARIOS_VERSION,
        "scenarios": speaking_scenarios.list_scenarios(),
    }


async def get_writing_diagnostic(user_id: str) -> dict:
    """Diagnóstico longitudinal de writing (V1.17).

    Deriva el perfil por criterio de rúbrica a partir de la evidencia de writing
    registrada en `academy_evidence`, y lo expone con tendencia temporal y
    criterios débiles.
    """
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    writing_rows = [r for r in rows if r.get("skill") == "writing"]
    now = datetime.now(timezone.utc).isoformat()
    return writing_svc.writing_diagnostic(writing_rows, now=now)


async def get_writing_level(user_id: str) -> dict:
    """Writing Assessment 1.0: nivel CEFR continuo de writing + confianza."""
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    writing_rows = [r for r in rows if r.get("skill") == "writing"]
    return writing_svc.writing_level(writing_rows)


async def get_writing_journey(user_id: str) -> dict:
    """Writing Journey (CEFR): trayectoria de nivel y confianza de writing."""
    rows = await run_in_threadpool(academy_repo.list_evidence, user_id)
    writing_rows = [r for r in rows if r.get("skill") == "writing"]
    return writing_svc.writing_journey(writing_rows)


# --- Speaking Assessment 1.0 (sesión trazable + instrumento versionado) ----


def _speaking_part_info(part: dict) -> SpeakingAssessmentPartInfo:
    """Proyecta una parte del instrumento al schema de presentación."""
    return SpeakingAssessmentPartInfo(
        id=part["id"],
        part_index=part["part_index"],
        title=part["title"],
        task_type=part["task_type"],
        cefr_target=part["cefr_target"],
        duration_target=part["duration_target"],
        prompt=part["prompt"],
        difficulty=part["difficulty"],
    )


def _speaking_result_out(
    session_id: int, aggregated: dict
) -> SpeakingAssessmentResultOut:
    """Proyecta el dict de `aggregate_assessment` al schema de resultado final."""
    return SpeakingAssessmentResultOut(
        session_id=session_id,
        level=aggregated["level"],
        numeric=aggregated["numeric"],
        score=aggregated["score"],
        confidence=aggregated["confidence"],
        attempts=aggregated["attempts"],
        criteria=aggregated["criteria"],
        weak=aggregated["weak"],
        recommendation=aggregated["recommendation"],
        assessment_version=aggregated["assessment_version"],
        rubric_version=aggregated["rubric_version"],
    )


async def start_speaking_assessment(
    user_id: str,
) -> SpeakingAssessmentStartOut | None:
    """Inicia una sesión de Speaking Assessment trazable y devuelve la 1ª parte.

    Persiste una fila en `speaking_assessment_sessions` con las 4 partes del
    instrumento (y su `assessment_version`) para reconstruir qué se evaluó y con
    qué dificultad. El motor de scoring sigue siendo stateless y determinista.
    """
    parts = speaking_assessment.assessment_parts()
    session = await run_in_threadpool(
        academy_repo.create_speaking_assessment_session,
        user_id,
        SPEAKING_ASSESSMENT_VERSION,
        parts,
    )
    if session is None:
        return None
    first = parts[0] if parts else None
    return SpeakingAssessmentStartOut(
        session_id=session["id"],
        assessment_version=SPEAKING_ASSESSMENT_VERSION,
        total_parts=len(parts),
        part=_speaking_part_info(first) if first else None,
    )


async def _inject_interaction_objective(
    evidence: dict, conversation_id: str | None, user_id: str
) -> None:
    """Inyecta la señal objetiva de interacción en la evidencia si hay conversación.

    Si `conversation_id` está presente, recupera los turnos de esa conversación y,
    cuando `interaction_evidence` observa al menos una sub-dimensión objetiva
    (`turn_balance` o `turn_duration`), asigna el resultado a
    `evidence["interaction_objective"]` para que el scorer determinista lo fusione
    con la señal semántica del LLM (`INTERACTION_OBJECTIVE_WEIGHT`). Sin
    conversación (o sin telemetría observable), la evidencia queda intacta
    (backward-compatible).
    """
    if not conversation_id:
        return
    turns = await run_in_threadpool(
        conversations_repo.get_turns, conversation_id, user_id
    )
    if turns is None:
        return
    objective = interaction_evidence(turns)
    if (
        objective["turn_balance"] is not None
        or objective["turn_duration"] is not None
    ):
        evidence["interaction_objective"] = objective


async def submit_speaking_assessment_part(
    user_id: str,
    session_id: int,
    heard: str,
    duration_seconds: float | None = None,
    model: str = DEFAULT_MODEL,
    conversation_id: str | None = None,
) -> SpeakingAssessmentPartOut | None:
    """Puntúa la siguiente parte de una sesión y avanza la traza.

    El LLM extrae la evidencia (`speaking_llm.extract_speaking_evidence`) y el
    scorer determinista (`scores_from_evidence`) calcula criterios y overall con el
    `task_type`/`difficulty` de la parte. La evidencia se persiste en
    `academy_evidence` (vía `_record_evidence_validated`) y se anexa a la sesión
    para que `aggregate_assessment` sea trazable. Devuelve None si la sesión no
    existe, no pertenece al usuario, ya terminó, no quedan partes o el LLM no
    produjo evidencia válida.
    """
    session = await run_in_threadpool(
        academy_repo.get_speaking_assessment_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    if session["status"] == "finished":
        return None
    parts = session["parts"]
    next_index = session["next_part_index"]
    if next_index >= len(parts):
        return None  # ya se enviaron todas las partes; llamar a finish
    part = parts[next_index]

    evidence = await speaking_llm.extract_speaking_evidence(
        part["prompt"], heard, model
    )
    if evidence is None:
        return None

    await _inject_interaction_objective(evidence, conversation_id, user_id)

    result = speaking_svc.scores_from_evidence(
        evidence, heard, duration_seconds, task_type=part["task_type"]
    )

    lv = _levels_by_id.get(await _current_level_id(user_id)) or _levels_by_id["a1"]
    evidence_rows = speaking_svc.evidence_from_speaking(
        result,
        level_id=lv.level_id,
        objective_id="",
        curriculum_version=lv.version,
        assessment_version=SPEAKING_ASSESSMENT_VERSION,
        difficulty=part["difficulty"],
    )
    await _record_evidence_validated(user_id, lv, evidence_rows)

    now = datetime.now(timezone.utc).isoformat()
    part_evidence = [
        {
            "part_index": next_index,
            "task_type": part["task_type"],
            "skill": "speaking",
            "item_id": row["item_id"],
            "result": row["result"],
            "difficulty": row["difficulty"],
            "created_at": now,
            "assessment_version": row["assessment_version"],
        }
        for row in evidence_rows
    ]
    combined = session["evidence"] + part_evidence
    new_next = next_index + 1
    done = new_next >= len(parts)
    await run_in_threadpool(
        academy_repo.update_speaking_assessment_session,
        session_id,
        next_part_index=new_next,
        evidence=combined,
    )
    next_part = parts[new_next] if new_next < len(parts) else None
    return SpeakingAssessmentPartOut(
        session_id=session_id,
        part_index=next_index,
        task_type=part["task_type"],
        cefr_target=part["cefr_target"],
        prompt=part["prompt"],
        part_scores=SpeakingAssessmentPartScores(
            overall=result["overall"],
            criteria=result["criteria"],
            observed=result["observed"],
        ),
        done=done,
        next_part=_speaking_part_info(next_part) if next_part else None,
    )


async def finish_speaking_assessment(
    user_id: str, session_id: int
) -> SpeakingAssessmentResultOut | None:
    """Agrega la evidencia de la sesión y devuelve el resultado final.

    `aggregate_assessment` reutiliza el scorer determinista (`speaking_level` +
    `speaking_diagnostic`) sobre las filas de evidencia de la sesión, produciendo
    nivel CEFR continuo, score, confianza y resumen por criterio. El resultado se
    persiste en la sesión y su `status` pasa a 'finished'. Es idempotente: si ya
    está terminada, devuelve el resultado guardado.
    """
    session = await run_in_threadpool(
        academy_repo.get_speaking_assessment_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    if session["status"] == "finished" and session["final_result"] is not None:
        return _speaking_result_out(session_id, session["final_result"])
    aggregated = speaking_assessment.aggregate_assessment(session["evidence"])
    await run_in_threadpool(
        academy_repo.update_speaking_assessment_session,
        session_id,
        final_result=aggregated,
        status="finished",
    )
    return _speaking_result_out(session_id, aggregated)


async def get_speaking_assessment(
    user_id: str, session_id: int
) -> SpeakingAssessmentStateOut | None:
    """Estado/resultado de una sesión de Speaking Assessment."""
    session = await run_in_threadpool(
        academy_repo.get_speaking_assessment_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    return SpeakingAssessmentStateOut(
        session_id=session_id,
        status=session["status"],
        assessment_version=session["assessment_version"],
        total_parts=len(session["parts"]),
        next_part_index=session["next_part_index"],
        final_result=(
            _speaking_result_out(session_id, session["final_result"])
            if session["final_result"] is not None
            else None
        ),
    )


def _mission_state_out(session: dict) -> SpeakingMissionStateOut:
    """Serializa una sesión de misión al schema de respuesta."""
    mission = session["mission"]
    evaluation = session.get("evaluation")
    attempt = session.get("attempt")
    retry = session.get("retry")
    improvement = session.get("improvement")
    return SpeakingMissionStateOut(
        session_id=session["id"],
        status=session["status"],
        scenario_id=session["scenario_id"],
        mission=SpeakingMissionOut(
            scenario_id=mission.get("scenario_id", session["scenario_id"]),
            title=mission.get("title", ""),
            prompt=mission.get("prompt", ""),
            communicative_objective=mission.get("communicative_objective", ""),
            cefr_target=mission.get("cefr_target", "B1"),
            task_type=mission.get("task_type", "role_play"),
            metrics=list(mission.get("metrics") or []),
            difficulty=mission.get("difficulty"),
        ),
        attempt=(
            SpeakingMissionAttemptOut.model_validate(attempt) if attempt else None
        ),
        evaluation=(
            SpeakingMissionEvaluationOut.model_validate(evaluation)
            if evaluation
            else None
        ),
        drills=[
            SpeakingMissionDrillOut.model_validate(d)
            for d in (session.get("drills") or [])
        ],
        retry=SpeakingMissionAttemptOut.model_validate(retry) if retry else None,
        improvement=(
            SpeakingMissionImprovementOut.model_validate(improvement)
            if improvement
            else None
        ),
    )


async def start_speaking_mission(
    user_id: str, scenario_id: str
) -> SpeakingMissionStateOut | None:
    """Abre una misión de speaking (V2.9) a partir de un escenario del catálogo.

    Estado inicial: `mission` (el alumno aún no ha hablado). Devuelve None si el
    escenario no existe o el usuario no es válido.
    """
    scenario = speaking_scenarios.get_scenario(scenario_id)
    if scenario is None:
        return None
    mission = speaking_mission.mission_from_scenario(scenario)
    session = await run_in_threadpool(
        academy_repo.create_speaking_mission_session,
        user_id,
        scenario_id,
        mission,
    )
    if session is None:
        return None
    return _mission_state_out(session)


async def _score_mission_utterance(
    user_id: str,
    mission: dict,
    heard: str,
    duration_seconds: float | None,
    model: str,
    conversation_id: str | None,
) -> dict | None:
    """Extrae evidencia (LLM) + puntúa (scorer determinista) una producción oral."""
    evidence = await speaking_llm.extract_speaking_evidence(
        mission.get("prompt") or mission.get("communicative_objective") or "",
        heard,
        model,
    )
    if evidence is None:
        return None
    await _inject_interaction_objective(evidence, conversation_id, user_id)
    result = speaking_svc.scores_from_evidence(
        evidence,
        heard,
        duration_seconds,
        mission.get("task_type") or "role_play",
    )
    lv = _levels_by_id.get(await _current_level_id(user_id)) or _levels_by_id["a1"]
    await _record_evidence_validated(
        user_id,
        lv,
        speaking_svc.evidence_from_speaking(
            result,
            level_id=lv.level_id,
            objective_id="",
            curriculum_version=lv.version,
            difficulty=mission.get("difficulty"),
        ),
    )
    return result


async def submit_speaking_mission_attempt(
    user_id: str,
    session_id: int,
    heard: str,
    duration_seconds: float | None = None,
    model: str = DEFAULT_MODEL,
    conversation_id: str | None = None,
) -> SpeakingMissionStateOut | None:
    """Primer intento de la misión: Evaluation + Targeted drills.

    Avanza el status a `drill` (listo para practicar y luego hacer retry).
    """
    session = await run_in_threadpool(
        academy_repo.get_speaking_mission_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    if session["status"] not in ("mission", "attempt"):
        return None
    result = await _score_mission_utterance(
        user_id,
        session["mission"],
        heard,
        duration_seconds,
        model,
        conversation_id,
    )
    if result is None:
        return None
    evaluation = speaking_mission.evaluate_attempt(
        overall=result["overall"],
        criteria=result["criteria"],
        observed=result["observed"],
    )
    drills = speaking_mission.targeted_drills(evaluation["weak"])
    attempt = {
        "heard": heard,
        "overall": result["overall"],
        "criteria": result["criteria"],
        "observed": result["observed"],
        "duration_seconds": duration_seconds,
    }
    updated = await run_in_threadpool(
        academy_repo.update_speaking_mission_session,
        session_id,
        status="drill",
        attempt=attempt,
        evaluation=evaluation,
        drills=drills,
    )
    return _mission_state_out(updated) if updated else None


async def submit_speaking_mission_retry(
    user_id: str,
    session_id: int,
    heard: str,
    duration_seconds: float | None = None,
    model: str = DEFAULT_MODEL,
    conversation_id: str | None = None,
) -> SpeakingMissionStateOut | None:
    """Retry tras el drill: calcula Improvement y cierra la sesión."""
    session = await run_in_threadpool(
        academy_repo.get_speaking_mission_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    if session["status"] not in ("drill", "retry", "evaluation"):
        return None
    if session.get("evaluation") is None:
        return None
    result = await _score_mission_utterance(
        user_id,
        session["mission"],
        heard,
        duration_seconds,
        model,
        conversation_id,
    )
    if result is None:
        return None
    retry_eval = speaking_mission.evaluate_attempt(
        overall=result["overall"],
        criteria=result["criteria"],
        observed=result["observed"],
    )
    delta = speaking_mission.improvement(session["evaluation"], retry_eval)
    retry = {
        "heard": heard,
        "overall": result["overall"],
        "criteria": result["criteria"],
        "observed": result["observed"],
        "duration_seconds": duration_seconds,
    }
    updated = await run_in_threadpool(
        academy_repo.update_speaking_mission_session,
        session_id,
        status="improvement",
        retry=retry,
        improvement=delta,
    )
    return _mission_state_out(updated) if updated else None


async def get_speaking_mission(
    user_id: str, session_id: int
) -> SpeakingMissionStateOut | None:
    """Estado completo de una sesión de misión (V2.9)."""
    session = await run_in_threadpool(
        academy_repo.get_speaking_mission_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    return _mission_state_out(session)


# --- Assessment 2.0 (V2.10) -----------------------------------------------


def _checks_index(level: Level) -> dict[str, object]:
    """Mapa id → ObjectiveCheck del nivel (para puntuar sin filtrar correct_index)."""
    return {c.id: c for o in level.objectives() for c in o.checks}


def _assessment_v2_state_out(session: dict) -> AssessmentV2StateOut:
    instrument = session["instrument"] or {}
    result = session.get("result")
    retention = session.get("retention")
    items = [
        AssessmentV2ItemOut.model_validate(it)
        for it in instrument.get("items") or []
    ]
    skills_out: dict[str, AssessmentV2SkillScoreOut] = {}
    result_out = None
    if result:
        for skill, block in (result.get("skills") or {}).items():
            skills_out[skill] = AssessmentV2SkillScoreOut.model_validate(block)
        result_out = AssessmentV2ResultOut(
            kind=result["kind"],
            overall=result["overall"],
            threshold=result["threshold"],
            passed=result["passed"],
            correct=result["correct"],
            total=result["total"],
            skills=skills_out,
            failed_skills=list(result.get("failed_skills") or []),
            phase=result.get("phase") or "evaluation",
        )
    retention_out = None
    if retention:
        retention_out = AssessmentV2RetentionOut(
            initial_overall=retention["initial_overall"],
            delayed_overall=retention["delayed_overall"],
            retention_rate=retention.get("retention_rate"),
            stable=bool(retention.get("stable")),
            by_skill=[
                AssessmentV2RetentionSkillOut.model_validate(row)
                for row in retention.get("by_skill") or []
            ],
            phase=retention.get("phase") or "retention",
        )
    return AssessmentV2StateOut(
        session_id=session["id"],
        status=session["status"],
        kind=session["kind"],
        level_id=session["level_id"],
        unit_id=session.get("unit_id") or "",
        objective_id=session.get("objective_id") or "",
        assessment_version=session.get("assessment_version") or "",
        instrument=AssessmentV2InstrumentOut(
            kind=instrument.get("kind") or session["kind"],
            title=instrument.get("title") or session["kind"],
            objective_id=instrument.get("objective_id") or "",
            unit_id=instrument.get("unit_id") or "",
            unit_ids=list(instrument.get("unit_ids") or []),
            items=items,
            threshold=float(
                instrument.get("threshold")
                or assessment_v2.PASS_THRESHOLDS.get(session["kind"], 0.7)
            ),
            assessment_version=instrument.get("assessment_version")
            or assessment_v2.ASSESSMENT_VERSION,
            exam_id=instrument.get("exam_id"),
            source_kind=instrument.get("source_kind"),
            source_session_id=instrument.get("source_session_id"),
        ),
        result=result_out,
        retention=retention_out,
        source_session_id=session.get("source_session_id"),
    )


async def get_assessment_v2_ladder(
    user_id: str, level_id: str | None = None
) -> AssessmentV2LadderOut | None:
    """Escalera Assessment 2.0 + readiness + mastery gate para el nivel actual."""
    lid = level_id or await _current_level_id(user_id)
    lv = _levels_by_id.get(lid)
    if lv is None:
        return None
    sessions = await run_in_threadpool(
        academy_repo.list_assessment_v2_sessions, user_id, level_id=lv.level_id
    )
    completed_kinds = {
        s["kind"] for s in sessions if s.get("status") == "done" and s.get("result")
    }
    # Unidades "done" vía course engine (objetivos dominados).
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    sequence = course_svc.unit_sequence(lv, mastered, objective_attempts)
    units_done = sum(1 for u in sequence if u.get("status") == "done")

    data = load_assessments()
    has_exam = lv.level_id in data.exams

    formal = [
        s
        for s in sessions
        if s.get("status") == "done"
        and s.get("kind") in ("unit", "progress", "level")
        and s.get("result")
    ]
    last_formal_at = formal[0]["created_at"] if formal else ""
    now = datetime.now(timezone.utc).isoformat()
    retention_ready = assessment_v2.retention_due(last_formal_at, now=now)

    evidence_rows = await run_in_threadpool(
        academy_repo.list_evidence, user_id, lv.level_id
    )
    by_kind: dict[str, int] = {
        "familiar": 0,
        "transfer": 0,
        "novel": 0,
        "delayed": 0,
    }
    for row in evidence_rows:
        kind = row.get("evidence_kind") or "familiar"
        if kind in by_kind:
            by_kind[kind] += 1
    gate = assessment_v2.mastery_evidence_gate(by_kind)
    status = assessment_v2.ladder_status(
        completed_kinds=completed_kinds,
        units_done=units_done,
        has_exam=has_exam,
        retention_ready=retention_ready,
        mastery_gate=gate,
    )
    recent = [_assessment_v2_state_out(s) for s in sessions[:5]]
    return AssessmentV2LadderOut(
        level_id=lv.level_id,
        steps=[AssessmentV2StepOut.model_validate(s) for s in status["steps"]],
        readiness=AssessmentV2ReadinessOut.model_validate(status["readiness"]),
        mastery_gate=AssessmentV2MasteryGateOut.model_validate(gate),
        assessment_version=assessment_v2.ASSESSMENT_VERSION,
        recent=recent,
    )


async def start_assessment_v2(
    user_id: str,
    kind: str,
    level_id: str,
    *,
    unit_id: str | None = None,
    objective_id: str | None = None,
    source_session_id: int | None = None,
) -> AssessmentV2StateOut | None:
    """Abre un peldaño de la escalera Assessment 2.0."""
    if kind not in assessment_v2.ASSESSMENT_KINDS:
        return None
    lv = _levels_by_id.get(level_id)
    if lv is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None

    instrument: dict | None = None
    source_id = source_session_id
    obj_id = objective_id or ""
    uid = unit_id or ""

    if kind == "formative":
        if not objective_id:
            return None
        obj = get_objective(lv, objective_id)
        if obj is None or not obj.checks:
            return None
        instrument = assessment_v2.build_formative(obj)
        obj_id = obj.id
    elif kind == "unit":
        if not unit_id:
            units = assessment_v2.ordered_units(lv)
            if not units:
                return None
            unit_id = units[0].id
        instrument = assessment_v2.build_unit(lv, unit_id)
        if instrument is None or not instrument["items"]:
            return None
        uid = unit_id
    elif kind == "progress":
        units = assessment_v2.ordered_units(lv)
        if not units:
            return None
        anchor = unit_id or units[
            min(len(units) - 1, assessment_v2.PROGRESS_UNIT_SPAN - 1)
        ].id
        instrument = assessment_v2.build_progress(lv, anchor)
        if instrument is None or not instrument["items"]:
            return None
        uid = anchor
    elif kind == "level":
        data = load_assessments()
        exam = data.exams.get(level_id)
        if exam is None:
            return None
        instrument = assessment_v2.build_level(
            exam.items, exam_id=exam.id, title=exam.title
        )
    elif kind == "retention":
        if source_session_id is None:
            sessions = await run_in_threadpool(
                academy_repo.list_assessment_v2_sessions,
                user_id,
                level_id=level_id,
                status="done",
            )
            formal = [
                s
                for s in sessions
                if s.get("kind") in ("unit", "progress", "level") and s.get("result")
            ]
            if not formal:
                return None
            source = formal[0]
            source_id = source["id"]
        else:
            source = await run_in_threadpool(
                academy_repo.get_assessment_v2_session, source_session_id
            )
            if (
                source is None
                or source["user_id"] != user_id
                or source.get("status") != "done"
            ):
                return None
            source_id = source["id"]
        previous = {
            **(source.get("instrument") or {}),
            "kind": source["kind"],
            "session_id": source["id"],
            "title": (source.get("instrument") or {}).get("title"),
        }
        instrument = assessment_v2.build_retention(previous)
        uid = previous.get("unit_id") or ""
        obj_id = previous.get("objective_id") or ""

    if instrument is None or not instrument.get("items"):
        return None

    session = await run_in_threadpool(
        academy_repo.create_assessment_v2_session,
        user_id,
        kind=kind,
        level_id=level_id,
        instrument=instrument,
        unit_id=uid,
        objective_id=obj_id,
        assessment_version=assessment_v2.ASSESSMENT_VERSION,
        source_session_id=source_id,
    )
    if session is None:
        return None
    return _assessment_v2_state_out(session)


async def submit_assessment_v2(
    user_id: str, session_id: int, answers: dict[str, int]
) -> AssessmentV2StateOut | None:
    """Puntúa y cierra un peldaño Assessment 2.0; registra evidencia."""
    session = await run_in_threadpool(
        academy_repo.get_assessment_v2_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    if session.get("status") != "open":
        return None
    lv = _levels_by_id.get(session["level_id"])
    if lv is None:
        return None

    kind = session["kind"]
    instrument = session["instrument"] or {}
    raw_ids = instrument.get("item_ids") or [
        i["id"] for i in instrument.get("items") or []
    ]
    item_ids = set(raw_ids)

    # Resolver correct_index desde currículo / examen (nunca confiar en el cliente).
    checks: list = []
    min_per_skill = None
    if kind == "level":
        data = load_assessments()
        exam = data.exams.get(session["level_id"])
        if exam is None:
            return None
        checks = [it for it in exam.items if it.id in item_ids]
        min_per_skill = exam.min_per_skill
    else:
        index = _checks_index(lv)
        for iid in instrument.get("item_ids") or [
            i["id"] for i in instrument.get("items") or []
        ]:
            check = index.get(iid)
            if check is not None:
                checks.append(check)

    if not checks:
        return None

    scored = assessment_v2.score_answers(checks, answers)
    result = assessment_v2.evaluate(kind, scored, min_per_skill=min_per_skill)

    retention_payload = None
    if kind == "retention" and session.get("source_session_id"):
        source = await run_in_threadpool(
            academy_repo.get_assessment_v2_session, session["source_session_id"]
        )
        if source and source.get("result"):
            retention_payload = assessment_v2.retention_delta(
                source["result"], result
            )

    evidence_kind = assessment_v2.evidence_kind_for(kind)
    await _record_evidence_validated(
        user_id,
        lv,
        academy_svc.evidence_from_items(
            checks,
            answers,
            level_id=lv.level_id,
            objective_id=session.get("objective_id") or "",
            source="assessment_v2",
            curriculum_version=lv.version,
            assessment_version=assessment_v2.ASSESSMENT_VERSION,
            evidence_kind=evidence_kind,
        ),
    )

    # Actualiza mastery por destreza del instrumento (umbral del peldaño).
    threshold = float(result["threshold"])
    for skill, block in result["skills"].items():
        if session.get("objective_id"):
            row = await run_in_threadpool(
                academy_repo.get_objective_row,
                user_id,
                lv.level_id,
                session["objective_id"],
                skill,
            )
            state = academy_svc.next_mastery_state(row, block["score"], threshold)
            await run_in_threadpool(
                academy_repo.apply_objective_evidence,
                user_id,
                lv.level_id,
                session["objective_id"],
                skill,
                state,
            )
        else:
            row = await run_in_threadpool(
                academy_repo.get_skill_row, user_id, lv.level_id, skill
            )
            state = academy_svc.next_mastery_state(row, block["score"], threshold)
            await run_in_threadpool(
                academy_repo.apply_skill_evidence, user_id, lv.level_id, skill, state
            )

    await run_in_threadpool(
        academy_repo.record_assessment_result,
        user_id,
        f"assessment-v2-{kind}",
        lv.level_id,
        result,
        result["passed"],
    )

    updated = await run_in_threadpool(
        academy_repo.update_assessment_v2_session,
        session_id,
        status="done",
        answers=answers,
        result=result,
        retention=retention_payload,
    )
    return _assessment_v2_state_out(updated) if updated else None


async def get_assessment_v2(
    user_id: str, session_id: int
) -> AssessmentV2StateOut | None:
    session = await run_in_threadpool(
        academy_repo.get_assessment_v2_session, session_id
    )
    if session is None or session["user_id"] != user_id:
        return None
    return _assessment_v2_state_out(session)


# --- FSRS-lite (V2.11) ----------------------------------------------------


def _fsrs_card_out(card: dict, *, now: str = "") -> FsrsCardOut:
    explained = fsrs.explain(card, now=now)
    return FsrsCardOut(
        target_type=card["target_type"],
        target_id=card["target_id"],
        label=card.get("label") or card["target_id"],
        state=card.get("state") or "new",
        difficulty=float(card.get("difficulty") or 5.0),
        stability=float(card.get("stability") or 0.1),
        reps=int(card.get("reps") or 0),
        lapses=int(card.get("lapses") or 0),
        due_at=card.get("due_at") or "",
        last_review_at=card.get("last_review_at") or "",
        last_evidence_at=card.get("last_evidence_at") or "",
        last_grade=card.get("last_grade"),
        why=card.get("why") or "",
        fsrs_version=card.get("fsrs_version") or fsrs.FSRS_VERSION,
        explain=FsrsExplainOut.model_validate(explained),
    )


async def sync_fsrs_cards(user_id: str, *, now: str | None = None) -> list[dict]:
    """Siembra/actualiza cartas desde perfil CEFR + léxico débil/learning.

    No pisa cartas ya revisadas (reps > 0): solo actualiza `why` y, si la carta
    es nueva, la estabiliza desde la evidencia.
    """
    now_iso = now or datetime.now(timezone.utc).isoformat()
    level_id = await _current_level_id(user_id)
    lv = _levels_by_id.get(level_id) or _levels_by_id["a1"]
    skills = await _annotated_profile(user_id, lv)

    existing = {
        (c["target_type"], c["target_id"]): c
        for c in await run_in_threadpool(academy_repo.list_fsrs_cards, user_id)
    }

    for entry in skills:
        if int(entry.get("evidence_count") or 0) <= 0:
            continue
        if not (
            entry.get("review_due")
            or float(entry.get("score") or 0.0) < 0.7
            or int((entry.get("evidence_by_kind") or {}).get("delayed", 0)) == 0
        ):
            # Solo maintenance ocasional: si ya hay carta, déjala; si no, no crear.
            key = ("skill", entry["skill"])
            if key not in existing:
                continue
        why = fsrs.why_for_skill(entry)
        key = ("skill", entry["skill"])
        prev = existing.get(key)
        if prev and int(prev.get("reps") or 0) > 0:
            # Conserva scheduling; solo refresca la razón pedagógica.
            updated = dict(prev)
            updated["why"] = why
            updated["label"] = entry["skill"]
            await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, updated)
            continue
        card = fsrs.seed_card_from_evidence(
            target_type="skill",
            target_id=entry["skill"],
            label=entry["skill"],
            score=float(entry.get("score") or 0.0),
            last_evidence_at=entry.get("last_evidence") or "",
            why=why,
            now=now_iso,
        )
        # Si review_due, forzar due ahora.
        if entry.get("review_due"):
            card["due_at"] = now_iso
        await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, card)

    vocab_rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    for row in vocab_rows:
        status = lexicon.item_status(row, now_iso)
        if status not in ("weak", "learning", "known"):
            continue
        if status == "known" and int(row.get("exposures") or 0) < 2:
            continue
        word = row.get("word") or ""
        if not word:
            continue
        why = fsrs.why_for_lexicon(status)
        key = ("lexicon", word)
        prev = existing.get(key)
        if prev and int(prev.get("reps") or 0) > 0:
            updated = dict(prev)
            updated["why"] = why
            updated["label"] = word
            await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, updated)
            continue
        score = lexicon.item_mastery(row)
        card = fsrs.seed_card_from_evidence(
            target_type="lexicon",
            target_id=word,
            label=word,
            score=score,
            last_evidence_at=row.get("last_seen") or row.get("last_exposed_at") or "",
            why=why,
            now=now_iso,
        )
        if status == "weak":
            card["due_at"] = now_iso
        await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, card)

    return await run_in_threadpool(academy_repo.list_fsrs_cards, user_id)


async def get_fsrs_due(user_id: str, limit: int = 20) -> FsrsDueOut:
    now_iso = datetime.now(timezone.utc).isoformat()
    cards = await sync_fsrs_cards(user_id, now=now_iso)
    due = fsrs.due_queue(cards, now=now_iso, limit=limit)
    return FsrsDueOut(
        due_count=len(due),
        cards=[_fsrs_card_out(c, now=now_iso) for c in due],
        fsrs_version=fsrs.FSRS_VERSION,
    )


async def get_fsrs_summary(user_id: str) -> FsrsSummaryOut:
    now_iso = datetime.now(timezone.utc).isoformat()
    cards = await sync_fsrs_cards(user_id, now=now_iso)
    by_state: dict[str, int] = {}
    by_type: dict[str, int] = {}
    due_count = 0
    for card in cards:
        state = card.get("state") or "new"
        by_state[state] = by_state.get(state, 0) + 1
        t = card.get("target_type") or "skill"
        by_type[t] = by_type.get(t, 0) + 1
        if fsrs.is_due(card, now=now_iso):
            due_count += 1
    return FsrsSummaryOut(
        total=len(cards),
        due_count=due_count,
        by_state=by_state,
        by_type=by_type,
        fsrs_version=fsrs.FSRS_VERSION,
    )


async def review_fsrs_card(
    user_id: str,
    target_type: str,
    target_id: str,
    grade: int | None = None,
    score: float | None = None,
) -> FsrsReviewOut | None:
    """Aplica un grade (o lo deriva de score) y reprograma la carta."""
    if target_type not in fsrs.TARGET_TYPES:
        return None
    if grade is None:
        if score is None:
            return None
        grade = fsrs.grade_from_score(score)
    if grade not in fsrs.GRADES:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    card = await run_in_threadpool(
        academy_repo.get_fsrs_card, user_id, target_type, target_id
    )
    if card is None:
        # Siembra mínima al vuelo.
        card = fsrs.empty_card(
            target_type=target_type,
            target_id=target_id,
            label=target_id,
            why="manual-review",
            now=now_iso,
        )

    updated = fsrs.schedule(card, grade, now=now_iso)
    saved = await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, updated)
    if saved is None:
        return None
    explained = fsrs.explain(saved, now=now_iso)
    return FsrsReviewOut(
        card=_fsrs_card_out(saved, now=now_iso),
        explain=FsrsExplainOut.model_validate(explained),
    )


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


async def _session_steps(user_id: str) -> tuple[list[dict], list[dict]]:
    """Pasos de la sesión diaria (Session Engine) y su perfil CEFR anotado.

    Repaso vencido → listening → debilidad → nuevo → refuerzo, unificando las
    señales CEFR y de listening en una secuencia accionable con presupuesto del
    objetivo personal. Los pasos ya completados hoy se omiten (filtro por
    `step_key`). Devuelve `(steps, skills)`: el perfil anotado se reutiliza para
    alimentar el Priority Engine en `get_next_best_activity`. Compartida por
    `get_session` y `get_next_best_activity`.
    """
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
    return steps, skills


async def get_session(user_id: str) -> SessionOut:
    """Sesión diaria (Session Engine): repaso vencido → listening → debilidad →
    nuevo → refuerzo, unificando las señales CEFR y de listening en una secuencia
    accionable con presupuesto del objetivo personal. Los pasos ya completados hoy
    se omiten (filtro por `step_key`)."""
    steps, _ = await _session_steps(user_id)
    summary = adaptive.session_summary(steps)
    return SessionOut(
        items=[SessionStepOut(**s) for s in steps],
        total_minutes=sum(s["minutes"] for s in steps),
        review_count=summary["review_count"],
        practice_count=summary["practice_count"],
    )


async def get_next_best_activity(user_id: str) -> NextBestActivityOut | None:
    """Siguiente mejor actividad (Learning UX 2.0): proyección del primer paso de
    la sesión enriquecida con las señales del Priority Engine (`signals`), la
    prioridad compuesta (`priority`) y su explicación (`why`). La UI no decide
    pedagógicamente; consume esta única acción.

    V2.12: añade `because[]` + `limiting_factor` desde el Evidence Graph del
    objetivo asociado (Adaptive Engine explicable).
    """
    steps, skills = await _session_steps(user_id)
    now = datetime.now(timezone.utc).isoformat()
    best = adaptive.next_best_activity(steps, skills, now)
    if best is None:
        return None

    node = None
    oid = best.get("objective_id")
    lid = best.get("level_id") or await _current_level_id(user_id)
    lv = _levels_by_id.get(lid)
    if oid and lv is not None:
        obj = get_objective(lv, oid)
        if obj is not None:
            obj_mastery = await run_in_threadpool(
                academy_repo.list_objective_mastery, user_id, lv.level_id
            )
            evidence_rows = await run_in_threadpool(
                academy_repo.list_evidence, user_id, lv.level_id
            )
            objective_scores, _attempts = _split_objective_mastery(obj_mastery)
            node = evidence_graph.objective_node(
                obj,
                level_id=lv.level_id,
                level_label=lv.level,
                objective_scores=objective_scores,
                profile=skills,
                evidence_rows=evidence_rows,
            )
            best = evidence_graph.enrich_next_best(best, node)
    else:
        best = evidence_graph.enrich_next_best(best, None)
    return NextBestActivityOut(**best)


async def get_evidence_graph(
    user_id: str, level_id: str | None = None
) -> EvidenceGraphOut | None:
    """Grafo can-do → dimensiones → limiting factor del nivel actual."""
    lid = level_id or await _current_level_id(user_id)
    lv = _levels_by_id.get(lid)
    if lv is None:
        return None
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    evidence_rows = await run_in_threadpool(
        academy_repo.list_evidence, user_id, lv.level_id
    )
    now = datetime.now(timezone.utc).isoformat()
    profile = academy_svc.build_skill_profile(lv, obj_mastery, evidence_rows, now)
    objective_scores, objective_attempts = _split_objective_mastery(obj_mastery)
    mastered = academy_svc.mastered_objective_ids(
        lv, objective_scores, objective_attempts
    )
    graph = evidence_graph.build_level_graph(
        lv,
        objective_scores=objective_scores,
        profile=profile,
        evidence_rows=evidence_rows,
        mastered_ids=mastered,
    )
    return EvidenceGraphOut.model_validate(graph)


async def get_evidence_graph_node(
    user_id: str, objective_id: str, level_id: str | None = None
) -> EvidenceGraphNodeOut | None:
    """Nodo del Evidence Graph para un can-do concreto."""
    lid = level_id or await _current_level_id(user_id)
    lv = _levels_by_id.get(lid)
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        # Buscar el objetivo en cualquier nivel cargado.
        for candidate in _levels_by_id.values():
            obj = get_objective(candidate, objective_id)
            if obj is not None:
                lv = candidate
                break
    if obj is None or lv is None:
        return None
    obj_mastery = await run_in_threadpool(
        academy_repo.list_objective_mastery, user_id, lv.level_id
    )
    evidence_rows = await run_in_threadpool(
        academy_repo.list_evidence, user_id, lv.level_id
    )
    now = datetime.now(timezone.utc).isoformat()
    profile = academy_svc.build_skill_profile(lv, obj_mastery, evidence_rows, now)
    objective_scores, _attempts = _split_objective_mastery(obj_mastery)
    node = evidence_graph.objective_node(
        obj,
        level_id=lv.level_id,
        level_label=lv.level,
        objective_scores=objective_scores,
        profile=profile,
        evidence_rows=evidence_rows,
    )
    return EvidenceGraphNodeOut.model_validate(node)


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
    if lv is None:
        return None
    obj = get_objective(lv, objective_id)
    if obj is None:
        return None
    if await enrollment_blocked(user_id, level_id):
        return None
    ok = await run_in_threadpool(
        academy_repo.record_lesson_completed, user_id, level_id, objective_id
    )
    if not ok:
        return None
    # V2.3: sembrar el léxico del objetivo (vocabulario + estructuras) para que
    # el diccionario personal se pueble automáticamente al avanzar.
    await vocabulary_domain.seed_objective_vocabulary(user_id, lv, obj)
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
    # V2.3: sembrar el léxico del objetivo tras validar la evidencia de dominio.
    await vocabulary_domain.seed_objective_vocabulary(user_id, lv, obj)
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
    task_type: str | None = None,
    difficulty: int | None = None,
    difficulty_vector: dict[str, int] | None = None,
    expected: str | None = None,
    conversation_id: str | None = None,
) -> SpeakingTaskResultOut | None:
    """Puntúa una respuesta oral libre (tarea) usando evidencia extraída por el LLM.

    El LLM extrae la evidencia estructurada (`speaking_llm.extract_speaking_evidence`)
    y el scorer determinista (`scores_from_evidence`) calcula los criterios y el
    overall, que se registran como evidencia y mueven el mastery de 'speaking' sin
    que el LLM decida el score. `task_type` (V1.16) elige los pesos de rúbrica;
    `difficulty`/`difficulty_vector` fijan la dificultad registrada en la evidencia;
    `expected` (opcional) integra el módulo de pronunciación en el flujo libre.
    """
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
    await _inject_interaction_objective(evidence, conversation_id, user_id)
    profile_difficulty = (
        difficulty
        if difficulty is not None
        else speaking_svc.difficulty_from_vector(difficulty_vector or {})
    )
    result = speaking_svc.scores_from_evidence(
        evidence, heard, duration_seconds, task_type, expected
    )
    await _record_evidence_validated(
        user_id,
        lv,
        speaking_svc.evidence_from_speaking(
            result,
            level_id=level_id,
            objective_id=objective_id,
            curriculum_version=lv.version,
            difficulty=profile_difficulty,
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
        # H5/P1: completado ≠ certificado. Aprobar desbloquea el siguiente nivel;
        # la certificación exige retención retardada (≥7 días, ratio estable) por
        # destreza del examen, reflejada aquí como gate explícito.
        evidence_rows = await run_in_threadpool(
            academy_repo.list_evidence, user_id, level_id
        )
        result["certification"] = assessment_v2.certification_gate(
            list(exam.skills), evidence_rows
        )
    else:
        # Remediation pack: objetivos del nivel dirigidos a cada destreza suspendida.
        result["remediation"] = {
            skill: data.remediation.get(skill, []) for skill in result["failed_skills"]
        }
    return ExamResultOut(**result)


async def list_level_completions(user_id: str) -> list[LevelCompletionOut]:
    rows = await run_in_threadpool(academy_repo.list_level_completions, user_id)
    if not rows:
        return []
    data = load_assessments()
    evidence = await run_in_threadpool(academy_repo.list_evidence, user_id)
    by_level: dict[str, list[dict]] = {}
    for ev in evidence:
        by_level.setdefault(ev.get("level_id") or "", []).append(ev)
    out: list[LevelCompletionOut] = []
    for r in rows:
        exam = data.exams.get(r["level_id"])
        certification = None
        if exam is not None:
            # H5/P1: el listado distingue completado (examen aprobado) de
            # certificado (completado + retención retardada por destreza).
            certification = assessment_v2.certification_gate(
                list(exam.skills), by_level.get(r["level_id"], [])
            )
        out.append(
            LevelCompletionOut(
                id=r["id"],
                level_id=r["level_id"],
                level=r["level"],
                overall=r["overall"],
                awarded_at=r["awarded_at"],
                certification=certification,
            )
        )
    return out

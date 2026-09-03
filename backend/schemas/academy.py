"""Esquemas Pydantic de la Academy (estado, mastery y evaluación)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import DEFAULT_MODEL
from schemas.curriculum import CurriculumActivityOut


class EnrollRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)


class EnrollmentOut(BaseModel):
    level_id: str
    level: str
    status: str
    enrolled_at: str
    updated_at: str


class EnrollmentsOut(BaseModel):
    enrollments: list[EnrollmentOut]


class SkillScoreOut(BaseModel):
    skill: str
    score: float
    required: float
    met: bool


class ObjectiveProgressOut(BaseModel):
    objective_id: str
    skills: list[SkillScoreOut]
    mastered: bool


class ObjectiveCheckOut(BaseModel):
    """Check determinista expuesto al cliente (sin la respuesta correcta)."""

    id: str
    skill: str
    prompt: str
    options: list[str]


class ObjectiveStateOut(BaseModel):
    id: str
    can_do: str
    title: str
    skills: list[str]
    concepts: list[str]
    vocabulary: list[str]
    thresholds: dict[str, float]
    activities: list[CurriculumActivityOut]
    checks: list[ObjectiveCheckOut]
    module_id: str
    module_title: str
    unit_id: str
    unit_title: str
    lesson_id: str
    lesson_title: str
    order: int
    status: str
    attempts: int
    correct: int
    incorrect: int
    progress: ObjectiveProgressOut


class ModuleProgressOut(BaseModel):
    module_id: str
    title: str
    order: int
    mastered: int
    total: int
    progress: float
    correct: int
    incorrect: int
    to_review: int


class LevelProgressOut(BaseModel):
    level: str
    mastered: int
    total: int
    progress: float
    correct: int
    incorrect: int
    to_review: int


class LevelDetailOut(BaseModel):
    level_id: str
    level: str
    title: str
    description: str
    objectives: list[ObjectiveStateOut]
    modules_progress: list[ModuleProgressOut]
    progress: LevelProgressOut


class LevelSummaryOut(BaseModel):
    level_id: str
    level: str
    title: str
    description: str
    objective_count: int
    available: bool
    unlocked: bool
    enrolled: bool
    progress: float
    correct: int
    incorrect: int
    to_review: int


class LevelsOut(BaseModel):
    levels: list[LevelSummaryOut]


class CourseObjectiveRefOut(BaseModel):
    objective_id: str
    title: str
    status: str


class CourseLessonOut(BaseModel):
    lesson_id: str
    lesson_title: str
    lesson_order: int
    mastered: int
    total: int
    progress: float
    status: str
    objectives: list[CourseObjectiveRefOut]


class CourseUnitOut(BaseModel):
    module_id: str
    module_title: str
    module_order: int
    unit_id: str
    unit_title: str
    unit_order: int
    mastered: int
    total: int
    progress: float
    status: str
    # V2.2: Learning Objectives ("By the end of this unit..."), plantilla de 7
    # secciones con huecos visibles y desglose de Mastery Gates.
    objectives: list[str] = Field(default_factory=list)
    sections: list[dict] = Field(default_factory=list)
    gates: list[dict] = Field(default_factory=list)
    gate_mastered: bool = False
    lessons: list[CourseLessonOut]


class CoursePositionOut(BaseModel):
    level_id: str
    level: str
    title: str
    objective_id: str | None
    objective_title: str | None
    objective_order: int
    module_id: str | None
    module_title: str | None
    unit_id: str | None
    unit_title: str | None
    lesson_id: str | None
    lesson_title: str | None
    unit_index: int
    unit_count: int
    mastered: int
    total: int
    progress: float
    complete: bool


class CourseProgressOut(BaseModel):
    mastered: int
    total: int
    progress: float


class CourseMapOut(BaseModel):
    level_id: str
    level: str
    title: str
    description: str
    units: list[CourseUnitOut]
    position: CoursePositionOut
    progress: CourseProgressOut


class NextObjectiveOut(BaseModel):
    objective_id: str | None
    level_id: str
    reason: str


class PlacementItemOut(BaseModel):
    id: str
    skill: str
    difficulty: int
    prompt: str
    options: list[str]


class PlacementOut(BaseModel):
    id: str
    title: str
    description: str
    items: list[PlacementItemOut]


class AssessmentSubmit(BaseModel):
    answers: dict[str, int] = Field(default_factory=dict)
    session_id: int | None = None


class PlacementSkillResultOut(BaseModel):
    correct: int
    total: int
    score: float


class PlacementSkillProfileOut(BaseModel):
    """Perfil de una destreza en el placement multiskill (θ, nivel y confianza)."""

    skill: str
    theta: float | None
    level: str | None
    confidence: float | None
    answered: int


class PlacementProfileOut(BaseModel):
    """Perfil multiskill del placement: θ por destreza + agregados globales."""

    profile: list[PlacementSkillProfileOut]
    overall_level: str
    overall_theta: float
    overall_confidence: float | None
    placement_version: str = ""


class PlacementResultOut(BaseModel):
    level: str
    confidence: float
    answered: int
    correct: int
    theta: float | None = None
    skills: dict[str, PlacementSkillResultOut] = Field(default_factory=dict)
    profile: list[PlacementSkillProfileOut] = Field(default_factory=list)
    placement_version: str = ""


class PlacementAdaptiveOut(BaseModel):
    session_id: int | None = None
    next_item: PlacementItemOut | None
    theta: float
    standard_error: float | None = None
    answered: int
    done: bool
    result: PlacementResultOut | None


class PlacementStartOut(BaseModel):
    session_id: int
    next_item: PlacementItemOut | None
    placement_version: str


class ExamItemOut(BaseModel):
    id: str
    skill: str
    prompt: str
    options: list[str]


class ExamOut(BaseModel):
    id: str
    title: str
    min_per_skill: float
    skills: list[str]
    items: list[ExamItemOut]


class ExamSkillResultOut(BaseModel):
    correct: int
    total: int
    score: float
    passed: bool


class CertificationOut(BaseModel):
    """Estado de certificación de un nivel superado (P1/H5).

    Aprobar el examen de nivel otorga la *completitud* del nivel; la
    certificación plena exige además evidencia `delayed` por cada destreza del
    examen (escrita solo tras un retention reassessment ≥ `window_min_days` con
    ratio estable). `certified` es False hasta que todas las destrezas del examen
    acumulan el mínimo de evidencias de retención.
    """

    required: bool = True
    certified: bool
    window_min_days: int
    min_delayed: int
    delayed_by_skill: dict[str, int] = Field(default_factory=dict)
    pending_skills: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class ExamResultOut(BaseModel):
    overall: float
    passed: bool
    failed_skills: list[str]
    skills: dict[str, ExamSkillResultOut]
    remediation: dict[str, list[str]] = Field(default_factory=dict)
    # H5/P1: aprobar completa el nivel (desbloquea el siguiente); certificar
    # exige además retención retardada estable por destreza (ver CertificationOut).
    certification: CertificationOut | None = None


class LevelCompletionOut(BaseModel):
    id: int
    level_id: str
    level: str
    overall: float
    awarded_at: str
    # H5/P1: distingue completado (examen aprobado) de certificado (retention).
    certification: CertificationOut | None = None


class LevelCompletionsOut(BaseModel):
    completions: list[LevelCompletionOut]


class StudyPlanRequest(BaseModel):
    start_level: str = Field(min_length=2, max_length=2)
    target_level: str = Field(min_length=2, max_length=2)
    weeks: int = Field(ge=1, le=520)


class StudyPlanStepOut(BaseModel):
    level: str
    weeks: int
    next_level_id: str | None


class StudyPlanOut(BaseModel):
    steps: list[StudyPlanStepOut]


class AttemptResultIn(BaseModel):
    skill: str
    result: Literal["correct", "incorrect"]


class AttemptRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    results: list[AttemptResultIn] = Field(min_length=1)


class AttemptOut(BaseModel):
    recorded: int


class LessonCompleteRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)


class LessonCompletedOut(BaseModel):
    level_id: str
    objective_id: str
    recorded: bool


class ObjectiveAssessmentRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    answers: dict[str, int] = Field(default_factory=dict)


class ObjectiveSkillResultOut(BaseModel):
    correct: int
    total: int
    score: float


class ObjectiveAssessmentOut(BaseModel):
    level_id: str
    objective_id: str
    overall: float
    correct: int
    total: int
    skills: dict[str, ObjectiveSkillResultOut]
    mastery: dict[str, float]


class SpeakingSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    expected: str = Field(min_length=1, max_length=2000)
    heard: str = Field(min_length=1, max_length=2000)
    duration_seconds: float | None = None


class SpeakingResultOut(BaseModel):
    level_id: str
    objective_id: str
    expected: str
    heard: str
    overall: float
    criteria: dict[str, float | None]
    observed: dict[str, bool] = Field(default_factory=dict)
    speaking_mastery: float


class SpeakingTaskSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=2000)
    heard: str = Field(min_length=1, max_length=2000)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    duration_seconds: float | None = None
    # Perfil de tarea (V1.16): tipo determina los pesos de rúbrica; `difficulty` o
    # `difficulty_vector` fijan la dificultad escalar (1..6) que se registra en la
    # evidencia. Opcionales por backward-compat (sin ellos, difficulty=1).
    task_type: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=6)
    difficulty_vector: dict[str, int] | None = None
    # Referencia opcional para integrar pronunciación en el flujo libre (V1.16):
    # si se aporta (p. ej. una lectura o frase modelo), el scorer calcula el
    # criterio `pronunciation` con el módulo de fonética; si no, queda no observado.
    expected: str | None = Field(default=None, max_length=2000)
    # Conversación opcional (InteractionEvidence 2.0): si se aporta, el scorer de
    # speaking fusiona la señal objetiva de turnos en el criterio `interaction`.
    conversation_id: str | None = None


class SpeakingTaskResultOut(BaseModel):
    level_id: str
    objective_id: str
    overall: float
    criteria: dict[str, float | None]
    observed: dict[str, bool] = Field(default_factory=dict)
    speaking_mastery: float
    evidence: dict


class SpeakingCriterionOut(BaseModel):
    criterion: str
    attempts: int
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    review_due: bool
    # Señales del Student Model (V1.16 S5): EMA, lifetime, consistencia y
    # estabilidad por criterio. El diagnóstico es una VISTA de estas señales.
    recent_score: float | None = None
    lifetime_score: float | None = None
    confidence: float | None = None
    stability: float | None = None
    # Speaking 2.0 (V1.34): True si el score es un PROXY (p. ej. `pronunciation`
    # derivado de similitud fonética de texto, no de análisis acústico real).
    proxy: bool = False


class SpeakingInteractionQualityOut(BaseModel):
    """Sub-dimensión de Interaction Quality (Speaking 2.0): desglose longitudinal
    de la interacción conversacional (initiation/response/follow_up/repair/
    turn_taking)."""

    dimension: str
    attempts: int
    mean: float | None = None
    recent_score: float | None = None


class SpeakingTrend(BaseModel):
    recent_mean: float | None = None
    prior_mean: float | None = None
    delta: float | None = None
    direction: str


class SpeakingDiagnostic(BaseModel):
    criteria: list[SpeakingCriterionOut]
    weak: list[str]
    recommendation: str
    attempts: int
    overall_mean: float | None = None
    overall_recent: float | None = None
    trend: SpeakingTrend
    rubric_version: str = ""
    interaction_quality: list[SpeakingInteractionQualityOut] = Field(
        default_factory=list
    )


class EnduranceMilestoneOut(BaseModel):
    """Hito de Conversation Endurance: duración objetivo y si se ha alcanzado."""

    seconds: int
    achieved: bool


class ConversationEnduranceOut(BaseModel):
    """Conversation Endurance (Speaking 2.0): hasta cuánto puede sostener una
    conversación el alumno, derivado de la telemetría de turnos hablados."""

    milestones: list[EnduranceMilestoneOut] = Field(default_factory=list)
    longest_session_seconds: float = 0.0
    longest_turn_seconds: float = 0.0
    total_speaking_seconds: float = 0.0
    turns: int = 0
    current_goal_seconds: int | None = None


class SpeakingLevelOut(BaseModel):
    level: str | None = None
    numeric: float | None = None
    score: float | None = None
    confidence: float = 0.0
    attempts: int = 0


class SpeakingJourneyStep(BaseModel):
    at: str
    numeric: float
    level: str
    confidence: float


class SpeakingJourneyOut(BaseModel):
    current_level: str | None = None
    current_numeric: float | None = None
    current_confidence: float = 0.0
    attempts: int = 0
    steps: list[SpeakingJourneyStep] = Field(default_factory=list)


# --- Speaking Assessment 1.0 ---------------------------------------------


class SpeakingAssessmentPartInfo(BaseModel):
    """Descripción de una parte del instrumento (para presentar al alumno)."""

    id: str
    part_index: int
    title: str
    task_type: str
    cefr_target: str
    duration_target: float
    prompt: str
    difficulty: int


class SpeakingAssessmentStartOut(BaseModel):
    session_id: int
    assessment_version: str
    total_parts: int
    part: SpeakingAssessmentPartInfo | None = None


class SpeakingAssessmentPartSubmit(BaseModel):
    """Envío de la siguiente parte: `session_id` identifica la sesión trazable."""

    session_id: int
    heard: str = Field(min_length=1, max_length=2000)
    duration_seconds: float | None = None
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    # Conversación opcional (InteractionEvidence 2.0): si se aporta, el scorer de
    # speaking fusiona la señal objetiva de turnos en el criterio `interaction`.
    conversation_id: str | None = None


class SpeakingAssessmentFinishRequest(BaseModel):
    session_id: int


class SpeakingAssessmentPartScores(BaseModel):
    overall: float
    criteria: dict[str, float | None]
    observed: dict[str, bool] = Field(default_factory=dict)


class SpeakingAssessmentPartOut(BaseModel):
    """Resultado de enviar una parte del Speaking Assessment."""

    session_id: int
    part_index: int
    task_type: str
    cefr_target: str
    prompt: str
    part_scores: SpeakingAssessmentPartScores
    done: bool
    next_part: SpeakingAssessmentPartInfo | None = None


class SpeakingAssessmentResultOut(BaseModel):
    """Resultado final agregado de un Speaking Assessment."""

    session_id: int
    level: str | None = None
    numeric: float | None = None
    score: float | None = None
    confidence: float = 0.0
    attempts: int = 0
    criteria: list[SpeakingCriterionOut] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    recommendation: str = ""
    assessment_version: str = ""
    rubric_version: str = ""


class SpeakingAssessmentStateOut(BaseModel):
    """Estado/resultado de una sesión de Speaking Assessment."""

    session_id: int
    status: str
    assessment_version: str
    total_parts: int
    next_part_index: int
    final_result: SpeakingAssessmentResultOut | None = None


# --- Speaking Scenarios 3.0 ------------------------------------------------
class SpeakingScenarioOut(BaseModel):
    """Un escenario comunicativo (Speaking 3.0): objetivo + métricas observadas."""

    id: str
    title: str
    category: str = "Everyday life"
    cefr_target: str = "B1"
    task_type: str = "role_play"
    communicative_objective: str
    prompt: str
    metrics: list[str] = Field(default_factory=list)
    difficulty: int = 1


class SpeakingScenariosOut(BaseModel):
    version: str
    scenarios: list[SpeakingScenarioOut] = Field(default_factory=list)


# --- Speaking Mission Performance (V2.9) ------------------------------------


class SpeakingMissionStartRequest(BaseModel):
    scenario_id: str


class SpeakingMissionDrillOut(BaseModel):
    criterion: str
    title: str
    instruction: str
    prompt: str


class SpeakingMissionCriterionDelta(BaseModel):
    criterion: str
    before: float
    after: float
    delta: float


class SpeakingMissionImprovementOut(BaseModel):
    before_overall: float | None = None
    after_overall: float | None = None
    delta: float | None = None
    improved: bool = False
    by_criterion: list[SpeakingMissionCriterionDelta] = Field(default_factory=list)
    phase: str = "improvement"


class SpeakingMissionEvaluationOut(BaseModel):
    overall: float | None = None
    criteria: dict[str, float | None] = Field(default_factory=dict)
    observed: dict[str, bool] = Field(default_factory=dict)
    weak: list[str] = Field(default_factory=list)
    recommendation: str = ""
    phase: str = "evaluation"


class SpeakingMissionAttemptOut(BaseModel):
    heard: str = ""
    overall: float | None = None
    criteria: dict[str, float | None] = Field(default_factory=dict)
    observed: dict[str, bool] = Field(default_factory=dict)
    duration_seconds: float | None = None


class SpeakingMissionOut(BaseModel):
    scenario_id: str
    title: str
    prompt: str
    communicative_objective: str
    cefr_target: str = "B1"
    task_type: str = "role_play"
    metrics: list[str] = Field(default_factory=list)
    difficulty: int | None = None


class SpeakingMissionStateOut(BaseModel):
    session_id: int
    status: str
    scenario_id: str
    mission: SpeakingMissionOut
    attempt: SpeakingMissionAttemptOut | None = None
    evaluation: SpeakingMissionEvaluationOut | None = None
    drills: list[SpeakingMissionDrillOut] = Field(default_factory=list)
    retry: SpeakingMissionAttemptOut | None = None
    improvement: SpeakingMissionImprovementOut | None = None


class SpeakingMissionAttemptSubmit(BaseModel):
    session_id: int
    heard: str
    duration_seconds: float | None = None
    model: str | None = None
    conversation_id: str | None = None


# --- Assessment 2.0 (V2.10) -----------------------------------------------


class AssessmentV2ItemOut(BaseModel):
    id: str
    skill: str
    prompt: str
    options: list[str]


class AssessmentV2SkillScoreOut(BaseModel):
    correct: int
    total: int
    score: float


class AssessmentV2ResultOut(BaseModel):
    kind: str
    overall: float
    threshold: float
    passed: bool
    correct: int
    total: int
    skills: dict[str, AssessmentV2SkillScoreOut] = Field(default_factory=dict)
    failed_skills: list[str] = Field(default_factory=list)
    phase: str = "evaluation"


class AssessmentV2RetentionSkillOut(BaseModel):
    skill: str
    initial: float | None = None
    delayed: float | None = None
    delta: float | None = None


class AssessmentV2RetentionOut(BaseModel):
    initial_overall: float
    delayed_overall: float
    retention_rate: float | None = None
    stable: bool = False
    by_skill: list[AssessmentV2RetentionSkillOut] = Field(default_factory=list)
    phase: str = "retention"


class AssessmentV2InstrumentOut(BaseModel):
    kind: str
    title: str
    objective_id: str = ""
    unit_id: str = ""
    unit_ids: list[str] = Field(default_factory=list)
    items: list[AssessmentV2ItemOut] = Field(default_factory=list)
    threshold: float
    assessment_version: str
    exam_id: str | None = None
    source_kind: str | None = None
    source_session_id: int | None = None


class AssessmentV2StateOut(BaseModel):
    session_id: int
    status: str
    kind: str
    level_id: str
    unit_id: str = ""
    objective_id: str = ""
    assessment_version: str
    instrument: AssessmentV2InstrumentOut
    result: AssessmentV2ResultOut | None = None
    retention: AssessmentV2RetentionOut | None = None
    source_session_id: int | None = None


class AssessmentV2StartRequest(BaseModel):
    kind: str
    level_id: str
    unit_id: str | None = None
    objective_id: str | None = None
    source_session_id: int | None = None


class AssessmentV2SubmitRequest(BaseModel):
    session_id: int
    answers: dict[str, int]


class AssessmentV2StepOut(BaseModel):
    kind: str
    available: bool
    completed: bool
    reason: str


class AssessmentV2ReadinessOut(BaseModel):
    ladder_complete: bool
    mastery_eligible: bool
    mastery_missing: list[str] = Field(default_factory=list)
    next_kind: str | None = None
    retention_due: bool = False
    # H5/P1: certificación plena = nivel (examen) + retention reassessment.
    level_certified: bool = False


class AssessmentV2MasteryGateOut(BaseModel):
    met: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class AssessmentV2LadderOut(BaseModel):
    level_id: str
    steps: list[AssessmentV2StepOut]
    readiness: AssessmentV2ReadinessOut
    mastery_gate: AssessmentV2MasteryGateOut
    assessment_version: str
    recent: list[AssessmentV2StateOut] = Field(default_factory=list)


# --- FSRS-lite (V2.11) ----------------------------------------------------


class FsrsWhatOut(BaseModel):
    target_type: str
    target_id: str
    label: str


class FsrsWhenOut(BaseModel):
    due_at: str
    due: bool
    next_in_days: float


class FsrsHowStrongOut(BaseModel):
    stability: float
    retrievability: float
    difficulty: float
    state: str
    reps: int
    lapses: int


class FsrsLastEvidenceOut(BaseModel):
    at: str | None = None
    grade: int | None = None
    grade_label: str | None = None


class FsrsNextEvidenceOut(BaseModel):
    due_at: str
    suggested_interval_days: float


class FsrsExplainOut(BaseModel):
    what: FsrsWhatOut
    why: str
    when: FsrsWhenOut
    how_strong: FsrsHowStrongOut
    last_evidence: FsrsLastEvidenceOut
    next_evidence: FsrsNextEvidenceOut
    fsrs_version: str


class FsrsCardOut(BaseModel):
    target_type: str
    target_id: str
    label: str
    state: str
    difficulty: float
    stability: float
    reps: int
    lapses: int
    due_at: str
    last_review_at: str = ""
    last_evidence_at: str = ""
    last_grade: int | None = None
    why: str = ""
    fsrs_version: str = ""
    explain: FsrsExplainOut | None = None


class FsrsDueOut(BaseModel):
    due_count: int
    cards: list[FsrsCardOut] = Field(default_factory=list)
    fsrs_version: str


class FsrsSummaryOut(BaseModel):
    total: int
    due_count: int
    by_state: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    fsrs_version: str


class FsrsReviewRequest(BaseModel):
    target_type: str
    target_id: str
    grade: int
    score: float | None = None


class FsrsReviewOut(BaseModel):
    card: FsrsCardOut
    explain: FsrsExplainOut


class SkillProfileOut(BaseModel):
    skill: str
    score: float
    confidence: float
    evidence_count: int
    last_evidence: str
    review_due: bool
    stability: float = 0.0
    trend: float | None = None
    subskills: list[dict] = Field(default_factory=list)


class CefrProfileOut(BaseModel):
    level_id: str
    level: str
    overall: float
    skills: list[SkillProfileOut]
    critical_skills: list[str] = Field(default_factory=list)


class ReadinessSkillOut(BaseModel):
    skill: str
    score: float
    confidence: float
    evidence_count: int
    minimum: float
    ready: bool
    transfer_required: int = 0
    novel_required: int = 0
    transfer_count: int = 0
    novel_count: int = 0


class ReadinessOut(BaseModel):
    target_level: str
    skills: list[ReadinessSkillOut]
    overall: float
    blocking_skills: list[str]
    ready: bool
    band: str = "developing"


class DashboardReadinessOut(BaseModel):
    overall: float
    band: str = "developing"


class DashboardOut(BaseModel):
    """Tríada Progress / Mastery / Readiness (V2.2).

    Tres métricas explícitas y consistentes reutilizadas por Home/Progress/Course:
    `progress` (cobertura del nivel), `mastery` (dominio sobre destrezas con
    evidencia) y `readiness` (preparación para el siguiente nivel).
    """

    progress: float
    mastery: float
    readiness: DashboardReadinessOut


class ReassessmentOut(BaseModel):
    skill: str
    level: str
    reason: str


class MasteryRecordOut(BaseModel):
    skill: str
    score: float = 0.0
    confidence: float = 0.0
    evidence_count: int = 0
    last_seen_at: str = ""
    retention: float = 0.0
    stability: float = 0.0
    review_due: bool = False
    review_in_days: int | None = None
    transfer_count: int = 0
    novel_count: int = 0
    stage: str = "acquire"


class StudentModelOut(BaseModel):
    level_id: str
    current_level: str
    estimated_level: str
    estimated_numeric: float
    confidence: float
    target_level: str
    skills: list[SkillProfileOut]
    critical_skills: list[str] = Field(default_factory=list)
    readiness: ReadinessOut
    reassessment: ReassessmentOut | None = None
    mastery: list[MasteryRecordOut] = Field(default_factory=list)


class TodayItemOut(BaseModel):
    kind: str
    skill: str | None = None
    objective_id: str | None = None
    title: str
    reason: str
    minutes: int


class TodayPlanOut(BaseModel):
    items: list[TodayItemOut]
    total_minutes: int


class SessionStepOut(BaseModel):
    kind: str
    step_key: str
    skill: str | None = None
    subskill: str | None = None
    objective_id: str | None = None
    level_id: str | None = None
    skills: list[str] = Field(default_factory=list)
    title: str
    reason: str
    minutes: int


class SessionCompleteRequest(BaseModel):
    step_key: str = Field(min_length=1, max_length=128)


class SessionOut(BaseModel):
    items: list[SessionStepOut]
    total_minutes: int
    review_count: int
    practice_count: int


class NextBestActivityOut(BaseModel):
    """Proyección de UX del primer paso de la sesión (Learning UX 2.0).

    El frontend no necesita saber cómo se calculó, pero recibe transparencia: una
    única acción dominante con su destreza/sub-destreza, minutos, una `priority`
    compuesta determinista (Priority Engine 2.0), las `signals` que la sustentan y
    una explicación pedagógica `why` en inglés.
    """

    kind: str
    step_key: str
    skill: str | None = None
    subskill: str | None = None
    objective_id: str | None = None
    level_id: str | None = None
    title: str
    reason: str
    minutes: int
    priority: float
    signals: dict = Field(default_factory=dict)
    why: str = ""
    because: list[str] = Field(default_factory=list)
    limiting_factor: dict | None = None
    graph_mastery: float | None = None
    can_do: str | None = None


class EvidenceGraphDimensionOut(BaseModel):
    id: str
    kind: str
    score: float
    evidence_count: int = 0
    missing: bool = False


class EvidenceGraphLimitingOut(BaseModel):
    id: str
    score: float
    missing: bool = False
    kind: str = "skill"


class EvidenceGraphFocusOut(BaseModel):
    dimension: str | None = None
    phase: str = "practice"
    reason: str = ""


class EvidenceGraphNodeOut(BaseModel):
    objective_id: str
    can_do: str
    title: str
    level_id: str
    level: str
    dimensions: list[EvidenceGraphDimensionOut] = Field(default_factory=list)
    limiting_factor: EvidenceGraphLimitingOut | None = None
    mastery: float = 0.0
    recommended_focus: EvidenceGraphFocusOut
    graph_version: str


class EvidenceGraphTopLimitingOut(BaseModel):
    id: str
    count: int


class EvidenceGraphOut(BaseModel):
    level_id: str
    level: str
    nodes: list[EvidenceGraphNodeOut] = Field(default_factory=list)
    open_count: int = 0
    mastered_count: int = 0
    average_mastery: float = 0.0
    top_limiting_factor: EvidenceGraphTopLimitingOut | None = None
    graph_version: str


class RemediationSkillOut(BaseModel):
    skill: str
    score: float
    objective_ids: list[str]


class CefrBandOut(BaseModel):
    """Banda de la escalera CEFR (Curriculum 2.0) con sus descriptores Can-Do."""

    id: str
    label: str
    numeric: float
    title: str
    description: str = ""
    can_do: dict[str, list[str]] = Field(default_factory=dict)
    is_current: bool = False


class CefrDimensionOut(BaseModel):
    """Dimensión comunicativa CEFR con su estado frente al dominio del alumno.

    `state` ∈ `mastered` / `in_progress` / `not_started` (✓/●/○), conectando el
    descriptor estático "Can-Do" al Student Model (contrato CEFR V2.2).
    """

    id: str
    label: str
    state: str = "not_started"


class CefrLadderOut(BaseModel):
    """Escalera CEFR completa (Pre-A1 → C2) con descriptores por dimensión.

    `estimated_band`/`estimated_numeric` sitúan al alumno en la escalera continua,
    y `is_current` marca la banda correspondiente en `bands`. Cada `dimension`
    expone su `state` real (contrato CEFR conectado al dominio).
    """

    dimensions: list[CefrDimensionOut]
    bands: list[CefrBandOut]
    estimated_band: str | None = None
    estimated_numeric: float | None = None


class RemediationPlanOut(BaseModel):
    level_id: str
    level: str
    skills: list[RemediationSkillOut]


class WritingSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    expected: str = Field(min_length=1, max_length=2000)
    text: str = Field(min_length=1, max_length=2000)


class WritingResultOut(BaseModel):
    level_id: str
    objective_id: str
    expected: str
    text: str
    overall: float
    criteria: dict[str, float]
    writing_mastery: float


class WritingTaskSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=2000)
    text: str = Field(min_length=1, max_length=2000)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)


class WritingTaskResultOut(BaseModel):
    level_id: str
    objective_id: str
    overall: float
    criteria: dict[str, float]
    writing_mastery: float
    evidence: dict


class WritingCriterionOut(BaseModel):
    criterion: str
    attempts: int
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    review_due: bool
    # Señales del Student Model (V1.17): EMA, lifetime, consistencia y
    # estabilidad por criterio. El diagnóstico es una VISTA de estas señales.
    recent_score: float | None = None
    lifetime_score: float | None = None
    confidence: float | None = None
    stability: float | None = None


class WritingTrend(BaseModel):
    recent_mean: float | None = None
    prior_mean: float | None = None
    delta: float | None = None
    direction: str


class WritingDiagnostic(BaseModel):
    criteria: list[WritingCriterionOut]
    weak: list[str]
    recommendation: str
    attempts: int
    overall_mean: float | None = None
    overall_recent: float | None = None
    trend: WritingTrend
    rubric_version: str = ""


class WritingLevelOut(BaseModel):
    level: str | None = None
    numeric: float | None = None
    score: float | None = None
    confidence: float = 0.0
    attempts: int = 0


class WritingJourneyStep(BaseModel):
    at: str
    numeric: float
    level: str
    confidence: float


class WritingJourneyOut(BaseModel):
    current_level: str | None = None
    current_numeric: float | None = None
    current_confidence: float = 0.0
    attempts: int = 0
    steps: list[WritingJourneyStep] = Field(default_factory=list)


class PronunciationSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    expected: str = Field(min_length=1, max_length=2000)
    heard: str = Field(min_length=1, max_length=2000)


class PronunciationResultOut(BaseModel):
    level_id: str
    objective_id: str
    expected: str
    heard: str
    overall: float
    criteria: dict[str, float]
    pronunciation_mastery: float


# --- Objetivo personal de aprendizaje -------------------------------------

GoalType = Literal["general", "travel", "work", "interview", "exam"]
CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class LearningGoalIn(BaseModel):
    goal_type: GoalType = "general"
    minutes_per_day: int = Field(default=15, ge=5, le=180)
    days_per_week: int = Field(default=5, ge=1, le=7)
    target_level: CefrLevel = "B1"


class LearningGoalOut(BaseModel):
    goal_type: str
    minutes_per_day: int
    days_per_week: int
    target_level: str

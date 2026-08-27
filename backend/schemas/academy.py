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


class MasteryOut(BaseModel):
    level_id: str
    skills: dict[str, float]


class MasteryListOut(BaseModel):
    mastery: list[MasteryOut]


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


class ExamResultOut(BaseModel):
    overall: float
    passed: bool
    failed_skills: list[str]
    skills: dict[str, ExamSkillResultOut]
    remediation: dict[str, list[str]] = Field(default_factory=dict)


class LevelCompletionOut(BaseModel):
    id: int
    level_id: str
    level: str
    overall: float
    awarded_at: str


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


class ReassessmentOut(BaseModel):
    skill: str
    level: str
    reason: str


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

    El frontend no necesita saber cómo se calculó: recibe una única acción
    dominante con su destreza/sub-destreza, minutos y un `priority` determinista
    derivado del orden pedagógico del Adaptive Engine (no es un score predictivo).
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


class RemediationSkillOut(BaseModel):
    skill: str
    score: float
    objective_ids: list[str]


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

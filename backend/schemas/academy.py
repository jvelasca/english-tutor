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


class PlacementResultOut(BaseModel):
    level: str
    confidence: float
    answered: int
    correct: int


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
    criteria: dict[str, float]
    speaking_mastery: float


class SpeakingTaskSubmitRequest(BaseModel):
    level_id: str = Field(min_length=1, max_length=16)
    objective_id: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=2000)
    heard: str = Field(min_length=1, max_length=2000)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    duration_seconds: float | None = None


class SpeakingTaskResultOut(BaseModel):
    level_id: str
    objective_id: str
    overall: float
    criteria: dict[str, float]
    speaking_mastery: float
    evidence: dict


class SkillProfileOut(BaseModel):
    skill: str
    score: float
    confidence: float
    evidence_count: int
    last_evidence: str
    review_due: bool


class CefrProfileOut(BaseModel):
    level_id: str
    level: str
    overall: float
    skills: list[SkillProfileOut]


class RemediationSkillOut(BaseModel):
    skill: str
    score: float
    objective_ids: list[str]


class RemediationPlanOut(BaseModel):
    level_id: str
    level: str
    skills: list[RemediationSkillOut]

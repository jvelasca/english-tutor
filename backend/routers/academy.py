"""Endpoints de la Academy: currículum, matrícula, mastery, siguiente paso y plan."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import academy as academy_service
from schemas.academy import (
    AttemptOut,
    AttemptRequest,
    EnrollmentOut,
    EnrollmentsOut,
    EnrollRequest,
    LessonCompletedOut,
    LessonCompleteRequest,
    LevelDetailOut,
    LevelsOut,
    MasteryListOut,
    NextObjectiveOut,
    ObjectiveAssessmentOut,
    ObjectiveAssessmentRequest,
    SpeakingResultOut,
    SpeakingSubmitRequest,
    StudyPlanOut,
    StudyPlanRequest,
)
from services.academy import study_plan

router = APIRouter()


@router.get("/api/academy/levels", response_model=LevelsOut)
async def levels(user: dict = Depends(current_user)) -> dict:
    return {"levels": await academy_service.list_levels(user["id"])}


@router.get("/api/academy/levels/{level_id}", response_model=LevelDetailOut)
async def level_detail(level_id: str, user: dict = Depends(current_user)) -> dict:
    # El contenido curricular de un nivel bloqueado no debe filtrarse: el gating
    # se valida en el backend (no solo en el frontend), como en enroll/exam.
    if await academy_service.enrollment_blocked(user["id"], level_id):
        raise HTTPException(
            status_code=403, detail="Nivel bloqueado: completa el nivel anterior"
        )
    detail = await academy_service.get_level_detail(level_id, user["id"])
    if detail is None:
        raise HTTPException(status_code=404, detail="Nivel no encontrado")
    return detail


@router.post("/api/academy/enroll", response_model=EnrollmentOut)
async def enroll(body: EnrollRequest, user: dict = Depends(current_user)) -> dict:
    enrollment = await academy_service.enroll(user["id"], body.level_id)
    if enrollment is None:
        if await academy_service.enrollment_blocked(user["id"], body.level_id):
            raise HTTPException(
                status_code=403, detail="Nivel bloqueado: completa el nivel anterior"
            )
        raise HTTPException(
            status_code=404, detail="Nivel no encontrado o usuario no existe"
        )
    return enrollment


@router.get("/api/academy/enrollment", response_model=EnrollmentsOut)
async def enrollment_list(user: dict = Depends(current_user)) -> dict:
    return {"enrollments": await academy_service.list_enrollments(user["id"])}


@router.get("/api/academy/mastery", response_model=MasteryListOut)
async def mastery(user: dict = Depends(current_user)) -> dict:
    return {"mastery": await academy_service.get_mastery(user["id"])}


@router.get("/api/academy/next", response_model=NextObjectiveOut)
async def next_step(level_id: str, user: dict = Depends(current_user)) -> dict:
    nxt = await academy_service.next_objective(user["id"], level_id)
    if nxt is None:
        raise HTTPException(status_code=404, detail="Nivel no encontrado")
    return nxt


@router.post("/api/academy/study-plan", response_model=StudyPlanOut)
async def make_study_plan(body: StudyPlanRequest) -> dict:
    return {"steps": study_plan(body.start_level, body.target_level, body.weeks)}


@router.post("/api/academy/attempts", response_model=AttemptOut)
async def record_attempts(
    body: AttemptRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.record_attempts(
        user["id"],
        body.level_id,
        body.objective_id,
        [r.model_dump() for r in body.results],
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post("/api/academy/lessons/complete", response_model=LessonCompletedOut)
async def complete_lesson(
    body: LessonCompleteRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.record_lesson_completed(
        user["id"], body.level_id, body.objective_id
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post(
    "/api/academy/objective/assessment", response_model=ObjectiveAssessmentOut
)
async def objective_assessment(
    body: ObjectiveAssessmentRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_objective_assessment(
        user["id"], body.level_id, body.objective_id, body.answers
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post("/api/academy/objective/speaking", response_model=SpeakingResultOut)
async def objective_speaking(
    body: SpeakingSubmitRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_speaking(
        user["id"],
        body.level_id,
        body.objective_id,
        body.expected,
        body.heard,
        body.duration_seconds,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out

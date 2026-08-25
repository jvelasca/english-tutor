"""Endpoints de la Academy: currículum, matrícula, mastery, siguiente paso y plan."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from config import DEFAULT_MODEL
from dependencies import current_user, read_audio_limited
from domain import academy as academy_service
from schemas.academy import (
    AttemptOut,
    AttemptRequest,
    CefrProfileOut,
    EnrollmentOut,
    EnrollmentsOut,
    EnrollRequest,
    LearningGoalIn,
    LearningGoalOut,
    LessonCompletedOut,
    LessonCompleteRequest,
    LevelDetailOut,
    LevelsOut,
    MasteryListOut,
    NextObjectiveOut,
    ObjectiveAssessmentOut,
    ObjectiveAssessmentRequest,
    PronunciationResultOut,
    PronunciationSubmitRequest,
    ReadinessOut,
    RemediationPlanOut,
    SessionOut,
    SpeakingResultOut,
    SpeakingSubmitRequest,
    SpeakingTaskResultOut,
    SpeakingTaskSubmitRequest,
    StudentModelOut,
    StudyPlanOut,
    StudyPlanRequest,
    TodayPlanOut,
    WritingResultOut,
    WritingSubmitRequest,
    WritingTaskResultOut,
    WritingTaskSubmitRequest,
)
from services.academy import study_plan
from services.stt import transcribe_with_timing

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


@router.get("/api/academy/profile", response_model=CefrProfileOut)
async def skill_profile(level_id: str, user: dict = Depends(current_user)) -> dict:
    if await academy_service.enrollment_blocked(user["id"], level_id):
        raise HTTPException(
            status_code=403, detail="Nivel bloqueado: completa el nivel anterior"
        )
    out = await academy_service.get_skill_profile(user["id"], level_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel no encontrado")
    return out


@router.get("/api/academy/remediation", response_model=RemediationPlanOut)
async def remediation(level_id: str, user: dict = Depends(current_user)) -> dict:
    if await academy_service.enrollment_blocked(user["id"], level_id):
        raise HTTPException(
            status_code=403, detail="Nivel bloqueado: completa el nivel anterior"
        )
    out = await academy_service.get_remediation(user["id"], level_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel no encontrado")
    return out


@router.get("/api/academy/student-model", response_model=StudentModelOut)
async def student_model(user: dict = Depends(current_user)) -> dict:
    return await academy_service.get_student_model(user["id"])


@router.get("/api/academy/readiness", response_model=ReadinessOut)
async def readiness(
    target_level: str = "B1", user: dict = Depends(current_user)
) -> dict:
    return await academy_service.get_readiness(user["id"], target_level)


@router.get("/api/academy/today", response_model=TodayPlanOut)
async def today(user: dict = Depends(current_user)) -> dict:
    return await academy_service.get_today_plan(user["id"])


@router.get("/api/academy/session", response_model=SessionOut)
async def session(user: dict = Depends(current_user)) -> dict:
    return await academy_service.get_session(user["id"])


@router.get("/api/academy/goal", response_model=LearningGoalOut)
async def get_goal(user: dict = Depends(current_user)) -> dict:
    return await academy_service.get_learning_goal(user["id"])


@router.put("/api/academy/goal", response_model=LearningGoalOut)
async def put_goal(
    body: LearningGoalIn, user: dict = Depends(current_user)
) -> dict:
    goal = await academy_service.set_learning_goal(user["id"], body)
    if goal is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return goal


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


@router.post(
    "/api/academy/objective/speaking/task", response_model=SpeakingTaskResultOut
)
async def objective_speaking_task(
    body: SpeakingTaskSubmitRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_speaking_task(
        user["id"],
        body.level_id,
        body.objective_id,
        body.task,
        body.heard,
        body.model,
        body.duration_seconds,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post("/api/academy/objective/writing", response_model=WritingResultOut)
async def objective_writing(
    body: WritingSubmitRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_writing(
        user["id"], body.level_id, body.objective_id, body.expected, body.text
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post(
    "/api/academy/objective/pronunciation", response_model=PronunciationResultOut
)
async def objective_pronunciation(
    body: PronunciationSubmitRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_pronunciation(
        user["id"], body.level_id, body.objective_id, body.expected, body.heard
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post("/api/academy/objective/writing/task", response_model=WritingTaskResultOut)
async def objective_writing_task(
    body: WritingTaskSubmitRequest, user: dict = Depends(current_user)
) -> dict:
    out = await academy_service.submit_writing_task(
        user["id"], body.level_id, body.objective_id, body.task, body.text, body.model
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post(
    "/api/academy/objective/speaking/audio", response_model=SpeakingResultOut
)
async def objective_speaking_audio(
    file: UploadFile = File(...),
    level_id: str = Form(...),
    objective_id: str = Form(...),
    expected: str = Form(...),
    language: str = Form("en"),
    user: dict = Depends(current_user),
) -> dict:
    """Read-aloud: audio → Whisper → score_speaking → mastery de speaking."""
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, language)
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    out = await academy_service.submit_speaking(
        user["id"], level_id, objective_id, expected, heard, timed.get("duration")
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out


@router.post(
    "/api/academy/objective/speaking/task/audio", response_model=SpeakingTaskResultOut
)
async def objective_speaking_task_audio(
    file: UploadFile = File(...),
    level_id: str = Form(...),
    objective_id: str = Form(...),
    task: str = Form(...),
    model: str = Form(DEFAULT_MODEL),
    language: str = Form("en"),
    user: dict = Depends(current_user),
) -> dict:
    """Tarea libre: audio → Whisper → LLM extrae evidencia → mastery de speaking."""
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, language)
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    out = await academy_service.submit_speaking_task(
        user["id"], level_id, objective_id, task, heard, model, timed.get("duration")
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Nivel u objetivo no encontrado")
    return out

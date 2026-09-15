"""Endpoints de eventos de aprendizaje y cola de repaso."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from dependencies import current_user
from domain import learning as learning_service
from domain import review as review_service
from repositories import decision_records as decision_records_repo
from schemas.learning import (
    LearningEvent,
    LearningEventCreate,
    LearningEventType,
    ReviewQueueOut,
)

router = APIRouter()


@router.post("/api/learning/events", response_model=LearningEvent)
async def record_event(
    body: LearningEventCreate, user: dict = Depends(current_user)
) -> dict:
    return await learning_service.record_event(user["id"], body.type, body.detail)


@router.get("/api/learning/events", response_model=list[LearningEvent])
async def list_events(
    user: dict = Depends(current_user),
    event_type: LearningEventType | None = Query(None),
) -> list[dict]:
    return await learning_service.list_events(user["id"], event_type)


@router.get("/api/learning/review", response_model=ReviewQueueOut)
async def review_queue(
    limit: int = Query(default=20, ge=1, le=50),
    user: dict = Depends(current_user),
) -> dict:
    """Cola de repaso léxico (V3.35, P1-2).

    Cartas FSRS `lexicon` vencidas con la actividad recomendada por hueco de
    competencia (recognition / recall / sentence), ordenadas por urgencia
    (`retrievability` ascendente). Sustituye la inyección de cartas FSRS dentro
    del speaking micro-drill: separa el repaso espaciado de la producción oral.
    Señal, nunca puerta; nunca expone la respuesta esperada."""
    return await review_service.get_review_queue(user["id"], limit=limit)


@router.get("/api/learning/decisions")
async def decision_analytics(
    status: str = Query(default="", max_length=32),
    target_id: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(current_user),
) -> dict:
    """Analítica del Decision Provenance (V3.67, P3-11/P3-12; solo lectura).

    Responde tres preguntas del ciclo decision → outcome → evidencia:
    - `decisions` — qué recomendó el Planner (tarea, `p_success`, fuente, estado
      del ciclo de vida y resultado), más reciente primero, con filtros por
      `status` y `target_id`;
    - `calibration` — informe descriptivo predicted vs observed por banda de
      `p_success` sobre las filas `completed` (¿el Planner heurístico predice?);
    - `provenance_health` — contador local de pérdida silenciosa del registro.
    """
    decisions = await run_in_threadpool(
        decision_records_repo.list_decisions,
        user["id"],
        status=status,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    calibration = await run_in_threadpool(
        decision_records_repo.calibration_report, user["id"]
    )
    return {
        "decisions": decisions,
        "calibration": calibration,
        "provenance_health": review_service.provenance_health(),
    }

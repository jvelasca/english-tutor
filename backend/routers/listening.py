"""Endpoints de listening (comprensión auditiva)."""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from dependencies import current_user
from domain import learning as learning_service
from domain import listening as listening_service
from domain import listening_extras as listening_extras_service
from schemas.listening import (
    ListeningAddExtrasRequest,
    ListeningAnswerRequest,
    ListeningAnswerResponse,
    ListeningDiagnostic,
    ListeningExtrasJobOut,
    ListeningLevelItemsOut,
    ListeningProductionRequest,
    ListeningProductionResult,
    ListeningQuestion,
    ListeningRouteExtrasOut,
    ListeningStats,
)
from services.listening import LEVEL_ORDER

router = APIRouter()

VALID_MODES = ("all", "failed", "mastered")


def _job_out(job: dict) -> ListeningExtrasJobOut:
    """Convierte una fila de trabajo de generación al modelo de respuesta."""
    added = json.loads(job.get("added_ids_json") or "[]")
    if not isinstance(added, list):
        added = []
    return ListeningExtrasJobOut(
        job_id=job["id"],
        status=job.get("status", "running"),
        level=job.get("level", ""),
        requested=int(job.get("requested", 0)),
        added=[str(a) for a in added],
        error=job.get("error", ""),
    )


@router.get("/api/listening/question", response_model=ListeningQuestion)
async def question(
    level: str | None = None,
    mode: str = "all",
    user: dict = Depends(current_user),
) -> dict:
    if level is not None and level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Modo no válido: {mode}")
    try:
        return await listening_service.next_question(
            user["id"], level=level, mode=mode
        )
    except ValueError as exc:
        if str(exc) == "listening.no_failed":
            raise HTTPException(
                status_code=404, detail="listening.no_failed"
            ) from None
        raise


@router.get("/api/listening/items", response_model=ListeningLevelItemsOut)
async def level_items(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    return await listening_service.level_items(user["id"], level)


@router.get("/api/listening/audio/{question_id}")
async def audio(
    question_id: str,
    variant: str = "normal",
    user: dict = Depends(current_user),
) -> Response:
    data, status = await listening_service.get_audio(
        user["id"], question_id, variant
    )
    if status is not None:
        detail = (
            "Variante no válida"
            if status == 400
            else "Audio no disponible"
            if status == 503
            else "Pregunta no encontrada"
        )
        raise HTTPException(status_code=status, detail=detail)
    return Response(content=data, media_type="audio/wav")


@router.post("/api/listening/answer", response_model=ListeningAnswerResponse)
async def answer(
    body: ListeningAnswerRequest, user: dict = Depends(current_user)
) -> dict:
    result = await listening_service.submit_answer(
        user["id"],
        body.question_id,
        body.answer_index,
        body.response_time_ms,
        body.replay_count,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"listening:{body.question_id}:{'ok' if result['correct'] else 'ko'}",
    )
    return result


@router.post("/api/listening/dictation", response_model=ListeningProductionResult)
async def dictation(
    body: ListeningProductionRequest, user: dict = Depends(current_user)
) -> dict:
    result = await listening_service.submit_production(
        user["id"], body.question_id, body.transcript, "dictation"
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"listening:dictation:{body.question_id}:{'ok' if result['correct'] else 'ko'}",
    )
    return result


@router.post("/api/listening/shadowing", response_model=ListeningProductionResult)
async def shadowing(
    body: ListeningProductionRequest, user: dict = Depends(current_user)
) -> dict:
    result = await listening_service.submit_production(
        user["id"], body.question_id, body.transcript, "shadowing"
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"listening:shadowing:{body.question_id}:{'ok' if result['correct'] else 'ko'}",
    )
    return result


@router.get("/api/listening/stats", response_model=ListeningStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await listening_service.get_stats(user["id"])


@router.get("/api/listening/diagnostic", response_model=ListeningDiagnostic)
async def diagnostic(user: dict = Depends(current_user)) -> dict:
    return await listening_service.get_diagnostic(user["id"])


# --- Práctica extra generada (V3.6) -------------------------------------------
# Añadir "X más" de práctica a una ruta crea un trabajo de generación en segundo
# plano (modelo local + validación determinista) cuyo estado el frontend hace
# polling. Los ítems generados se activan en la ruta del usuario al terminar;
# la puerta de ruta / certificación no cambia (solo banco curado).


@router.post(
    "/api/listening/routes/{level}/extras",
    response_model=ListeningExtrasJobOut,
    status_code=202,
)
async def add_route_extras(
    level: str,
    body: ListeningAddExtrasRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(current_user),
) -> ListeningExtrasJobOut:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    job, is_new = await listening_extras_service.start_extras_job(
        user["id"], level, body.count
    )
    if is_new:
        # La generación es lenta (modelo local): corre tras responder 202.
        background_tasks.add_task(
            listening_extras_service.run_extras_job, job["id"]
        )
    return _job_out(job)


@router.get(
    "/api/listening/routes/{level}/extras/jobs/{job_id}",
    response_model=ListeningExtrasJobOut,
)
async def extras_job_status(
    level: str,
    job_id: str,
    user: dict = Depends(current_user),
) -> ListeningExtrasJobOut:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    job = await listening_extras_service.extras_job(job_id)
    if job is None or job.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return _job_out(job)


@router.get(
    "/api/listening/routes/{level}/extras",
    response_model=ListeningRouteExtrasOut,
)
async def route_extras(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    return await listening_extras_service.route_extras(user["id"], level)


@router.delete(
    "/api/listening/routes/{level}/extras/{question_id}",
    response_model=ListeningRouteExtrasOut,
)
async def delete_route_extra(
    level: str,
    question_id: str,
    user: dict = Depends(current_user),
) -> dict:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    removed = await listening_extras_service.remove_route_extra(
        user["id"], level, question_id
    )
    if not removed:
        raise HTTPException(
            status_code=404, detail="El ítem extra no estaba activado en la ruta"
        )
    return await listening_extras_service.route_extras(user["id"], level)

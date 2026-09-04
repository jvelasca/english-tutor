"""Endpoints de las rutas de speaking (V3.8).

Práctica oral guiada por nivel CEFR con tarjetas de micro-conversación: siguiente
tarjeta (nueva/failed/mastered), estado del nivel, intentos de respuesta abierta
(transcripción Whisper + extracción de evidencia LLM + `scores_from_evidence`),
audio modelo TTS por tipo (`opening`/`model`) y práctica extra generada en segundo
plano.
"""
from __future__ import annotations

import json
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool

from dependencies import current_user, read_audio_limited
from domain import learning as learning_service
from domain import speaking_routes as speaking_routes_service
from domain.speaking_routes import EvidenceExtractionError
from schemas.speaking import (
    SpeakingAddExtrasRequest,
    SpeakingAttemptResponse,
    SpeakingExtrasJobOut,
    SpeakingLevelItemsOut,
    SpeakingPhrase,
    SpeakingRouteExtrasOut,
    SpeakingStats,
)
from services.speaking_routes import LEVEL_ORDER
from services.stt import transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_MODES = ("all", "failed", "mastered")


def _job_out(job: dict) -> SpeakingExtrasJobOut:
    """Convierte una fila de trabajo de generación al modelo de respuesta."""
    added = json.loads(job.get("added_ids_json") or "[]")
    if not isinstance(added, list):
        added = []
    return SpeakingExtrasJobOut(
        job_id=job["id"],
        status=job.get("status", "running"),
        level=job.get("level", ""),
        requested=int(job.get("requested", 0)),
        added=[str(a) for a in added],
        error=job.get("error", ""),
    )


def _valid_level_or_400(level: str) -> None:
    if level not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")


@router.get("/api/speaking/question", response_model=SpeakingPhrase)
async def question(
    level: str | None = None,
    mode: str = "all",
    user: dict = Depends(current_user),
) -> dict:
    if level is not None:
        _valid_level_or_400(level)
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Modo no válido: {mode}")
    try:
        return await speaking_routes_service.next_phrase(
            user["id"], level=level, mode=mode
        )
    except ValueError as exc:
        if str(exc) == "speaking.no_failed":
            raise HTTPException(
                status_code=404, detail="speaking.no_failed"
            ) from None
        raise


@router.get("/api/speaking/items", response_model=SpeakingLevelItemsOut)
async def level_items(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    _valid_level_or_400(level)
    return await speaking_routes_service.phrases_for_level_out(user["id"], level)


@router.get("/api/speaking/stats", response_model=SpeakingStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await speaking_routes_service.get_stats(user["id"])


@router.get("/api/speaking/audio/{phrase_id}")
async def audio(
    phrase_id: str,
    kind: str = "opening",
    user: dict = Depends(current_user),
):
    """Voz modelo de una tarjeta: `kind=opening` (interlocutor) o `kind=model`."""
    data, status = await speaking_routes_service.get_audio(
        user["id"], phrase_id, kind
    )
    if status is not None:
        detail = (
            "Audio no disponible"
            if status == 503
            else "Tarjeta o tipo de audio no encontrado"
        )
        raise HTTPException(status_code=status, detail=detail)
    from fastapi.responses import Response

    return Response(content=data, media_type="audio/wav")


@router.post("/api/speaking/attempt", response_model=SpeakingAttemptResponse)
async def attempt(
    phrase_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    """Graba la respuesta a un intercambio: transcribe (Whisper) y evalúa abierta.

    La evaluación usa el pipeline LLM+evidencia (mismo que misiones/assessment):
    si el extractor no produce evidencia válida se responde 503 (transitorio)
    para que el alumno reintente; nunca se puntúa en falso.
    """
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, "en")
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio de speaking")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    heard = timed["text"]
    duration = timed.get("duration")
    try:
        result = await speaking_routes_service.submit_attempt(
            user["id"], phrase_id, heard, duration
        )
    except EvidenceExtractionError:
        logger.warning("Intento de speaking sin evidencia válida del LLM; 503")
        raise HTTPException(
            status_code=503, detail="speaking.evidence_failed"
        ) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"speaking:{phrase_id}:{'ok' if result['passed'] else 'ko'}",
    )
    return result


# --- Práctica extra generada (V3.7) ------------------------------------------


@router.post(
    "/api/speaking/routes/{level}/extras",
    response_model=SpeakingExtrasJobOut,
    status_code=202,
)
async def add_route_extras(
    level: str,
    body: SpeakingAddExtrasRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(current_user),
) -> SpeakingExtrasJobOut:
    _valid_level_or_400(level)
    job, is_new = await speaking_routes_service.start_extras_job(
        user["id"], level, body.count
    )
    if is_new:
        # La generación es lenta (modelo local): corre tras responder 202.
        background_tasks.add_task(
            speaking_routes_service.run_extras_job, job["id"]
        )
    return _job_out(job)


@router.get(
    "/api/speaking/routes/{level}/extras/jobs/{job_id}",
    response_model=SpeakingExtrasJobOut,
)
async def extras_job_status(
    level: str,
    job_id: str,
    user: dict = Depends(current_user),
) -> SpeakingExtrasJobOut:
    _valid_level_or_400(level)
    job = await speaking_routes_service.extras_job(job_id)
    if job is None or job.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return _job_out(job)


@router.get(
    "/api/speaking/routes/{level}/extras",
    response_model=SpeakingRouteExtrasOut,
)
async def route_extras(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    _valid_level_or_400(level)
    return await speaking_routes_service.route_extras(user["id"], level)


@router.delete(
    "/api/speaking/routes/{level}/extras/{phrase_id}",
    response_model=SpeakingRouteExtrasOut,
)
async def delete_route_extra(
    level: str,
    phrase_id: str,
    user: dict = Depends(current_user),
) -> dict:
    _valid_level_or_400(level)
    removed = await speaking_routes_service.remove_route_extra(
        user["id"], level, phrase_id
    )
    if not removed:
        raise HTTPException(
            status_code=404, detail="La frase extra no estaba activada en la ruta"
        )
    return await speaking_routes_service.route_extras(user["id"], level)

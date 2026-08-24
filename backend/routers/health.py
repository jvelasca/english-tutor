"""Endpoints de salud: liveness, readiness y estado de dependencias."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from config import VERSION
from repositories import db
from services import llm, stt, tts

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "english-tutor", "version": VERSION}


@router.get("/api/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


async def _dependencies() -> dict[str, str]:
    db_ok = await run_in_threadpool(db.ping)
    ollama_ok = await llm.ping()
    stt_ready = await run_in_threadpool(stt.is_ready)
    tts_ready = await run_in_threadpool(tts.is_ready)
    return {
        "api": "ok",
        "database": "ok" if db_ok else "error",
        "ollama": "ok" if ollama_ok else "error",
        "stt": "ready" if stt_ready else "unavailable",
        "tts": "ready" if tts_ready else "unavailable",
    }


@router.get("/api/health/dependencies")
async def dependencies() -> dict[str, str]:
    return await _dependencies()


@router.get("/api/health/ready")
async def ready() -> JSONResponse:
    deps = await _dependencies()
    ok = (
        deps["database"] == "ok"
        and deps["ollama"] == "ok"
        and deps["stt"] == "ready"
        and deps["tts"] == "ready"
    )
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "unavailable", "dependencies": deps},
    )

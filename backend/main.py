"""Punto de entrada: crea la app y monta los routers. Código mínimo."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGIN_REGEX, ALLOWED_ORIGINS, VERSION
from domain.errors import EvidenceInvariantError
from repositories.db import init_db
from routers.academy import router as academy_router
from routers.assessment import router as assessment_router
from routers.audio_library import router as audio_library_router
from routers.chat import router as chat_router
from routers.conversations import router as conversations_router
from routers.grammar import router as grammar_router
from routers.health import router as health_router
from routers.learning import router as learning_router
from routers.listening import router as listening_router
from routers.models import router as models_router
from routers.network import router as network_router
from routers.profile import router as profile_router
from routers.progress import router as progress_router
from routers.pronunciation import router as pronunciation_router
from routers.pronunciation_routes import router as pronunciation_routes_router
from routers.settings import router as settings_router
from routers.speaking_routes import router as speaking_routes_router
from routers.system import router as system_router
from routers.translate import router as translate_router
from routers.users import router as users_router
from routers.voices import router as voices_router
from routers.vocabulary import router as vocabulary_router
from routers.voz import router as voz_router
from security import SecurityMiddleware

logger = logging.getLogger(__name__)

_AUTO_BACKUP_INTERVAL_SECONDS = 3600


def _auto_backup_daemon() -> None:
    """Auto-backup diario (keep 7) en un hilo daemon; verifica cada hora."""
    from services import backup as backup_svc

    while True:
        time.sleep(_AUTO_BACKUP_INTERVAL_SECONDS)
        try:
            backup_svc.auto_backup_if_due()
        except Exception:  # noqa: BLE001
            logger.exception("auto-backup falló")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    threading.Thread(target=_auto_backup_daemon, daemon=True).start()
    yield


app = FastAPI(title="English Tutor API", version=VERSION, lifespan=lifespan)


@app.exception_handler(EvidenceInvariantError)
async def evidence_invariant_handler(
    _request: Request, exc: EvidenceInvariantError
) -> JSONResponse:
    """Expone la evidencia rechazada como error controlado y visible en logs."""
    return JSONResponse(
        status_code=500,
        content={
            "code": "EVIDENCE_INVARIANT",
            "message": "Evidencia rechazada por violación de invariantes",
            "violations": exc.violations,
        },
    )

# CORS para desarrollo local + acceso desde la LAN (frontend Vite en :5173,
# accesible desde cualquier equipo de la red por su IP privada).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Protección de origen (CSRF) + rate limiting (V1.41).
app.add_middleware(SecurityMiddleware)

app.include_router(chat_router)
app.include_router(grammar_router)
app.include_router(health_router)
app.include_router(learning_router)
app.include_router(listening_router)
app.include_router(models_router)
app.include_router(network_router)
app.include_router(profile_router)
app.include_router(voz_router)
app.include_router(pronunciation_router)
app.include_router(pronunciation_routes_router)
app.include_router(progress_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(translate_router)
app.include_router(users_router)
app.include_router(voices_router)
app.include_router(vocabulary_router)
app.include_router(academy_router)
app.include_router(assessment_router)
app.include_router(audio_library_router)
app.include_router(system_router)
app.include_router(speaking_routes_router)

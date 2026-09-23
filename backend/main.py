"""Punto de entrada: crea la app y monta los routers. Código mínimo."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGIN_REGEX, ALLOWED_ORIGINS, VERSION, lan_mode
from domain.errors import (
    EvidenceInvariantError,
    ObjectiveLockedError,
    RetentionNotDueError,
)
from repositories.db import init_db
from routers.academy import router as academy_router
from routers.account import router as account_router
from routers.admin import router as admin_router
from routers.assessment import router as assessment_router
from routers.audio_library import router as audio_library_router
from routers.chat import router as chat_router
from routers.conversation_routes import router as conversation_routes_router
from routers.conversations import router as conversations_router
from routers.cross_skill import router as cross_skill_router
from routers.grammar import router as grammar_router
from routers.grammar_routes import router as grammar_routes_router
from routers.health import router as health_router
from routers.learning import router as learning_router
from routers.listening import router as listening_router
from routers.models import router as models_router
from routers.network import router as network_router
from routers.profile import router as profile_router
from routers.progress import router as progress_router
from routers.pronunciation import router as pronunciation_router
from routers.pronunciation_routes import router as pronunciation_routes_router
from routers.session import router as session_router
from routers.settings import router as settings_router
from routers.speaking_routes import router as speaking_routes_router
from routers.system import router as system_router
from routers.translate import router as translate_router
from routers.users import router as users_router
from routers.vocabulary import router as vocabulary_router
from routers.vocabulary_routes import router as vocabulary_routes_router
from routers.voices import router as voices_router
from routers.voz import router as voz_router
from security import SecurityMiddleware
from security_headers import SecurityHeadersMiddleware
from services.frontend_dist import mount_frontend, require_ui_from_env

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


@app.exception_handler(RetentionNotDueError)
async def retention_not_due_handler(
    _request: Request, exc: RetentionNotDueError
) -> JSONResponse:
    """R6-01: la retención no es debida (ventana/ratio) → 409 conflicto."""
    return JSONResponse(
        status_code=409,
        content={
            "code": "RETENTION_NOT_DUE",
            "message": "Retención no debida: ventana de ≥7 días o ratio estable",
            "reason": exc.reason,
        },
    )


@app.exception_handler(ObjectiveLockedError)
async def objective_locked_handler(
    _request: Request, exc: ObjectiveLockedError
) -> JSONResponse:
    """GATE-01: objetivo locked evaluable por API → 409 conflicto."""
    return JSONResponse(
        status_code=409,
        content={
            "code": "OBJECTIVE_LOCKED",
            "message": "Objetivo locked: no se puede evaluar ni completar",
            "objective_id": exc.objective_id,
        },
    )

# CORS para desarrollo local + acceso desde la LAN. En V3.72 el producto sirve
# la UI y la API desde el MISMO origen (`https://<host>:8000`), así que CORS es
# irrelevante en ese camino; se mantiene para el modo de desarrollo (`npm run
# dev` en :5173, que habla con la API por el proxy de Vite) y para clientes
# externos legítimos de la LAN.
# V3.73.x: `ALLOWED_ORIGIN_REGEX` trae las IPs privadas **solo en modo LAN**
# (`ENGLISH_TUTOR_LAN`, ver `config.py`). El patrón se resuelve al importar
# porque este middleware lo compila una sola vez; el proceso arranca con el modo
# ya declarado por el launcher. La comprobación que corta la petición con 403
# (`security.origin_allowed`) sí vuelve a consultar el modo en cada llamada.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # V3.71 (eje RD): el TTS declara la voz usada y si hubo degradación; sin
    # exponerlas, el navegador no puede leerlas desde otro origen.
    expose_headers=["X-TTS-Voice", "X-TTS-Degraded"],
)

# Protección de origen (CSRF) + rate limiting (V1.41).
app.add_middleware(SecurityMiddleware)

# Cabeceras defensivas (V3.73.x). Se añade en último lugar para quedar por FUERA
# de `SecurityMiddleware` y decorar también sus 403/429.
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(chat_router)
app.include_router(admin_router)
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
app.include_router(conversation_routes_router)
app.include_router(cross_skill_router)
app.include_router(vocabulary_routes_router)
app.include_router(grammar_routes_router)
app.include_router(progress_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(session_router)
app.include_router(translate_router)
app.include_router(users_router)
app.include_router(voices_router)
app.include_router(vocabulary_router)
app.include_router(academy_router)
app.include_router(account_router)
app.include_router(assessment_router)
app.include_router(audio_library_router)
app.include_router(system_router)
app.include_router(speaking_routes_router)

# V3.72 (RC-01): servir la UI compilada desde el mismo origen que la API. Va al
# final a propósito: los routers registrados arriba tienen prioridad y el
# *fallback* SPA nunca puede eclipsar un `/api/*`. Sin artefacto (clon limpio sin
# `npm run build`) el arranque no se rompe: simplemente no se sirve UI.
# V3.73: el launcher arranca el producto con `ENGLISH_TUTOR_REQUIRE_UI=1`, y en
# ese modo la falta del artefacto es **fail-closed** (no una app vacía que parece
# lista). Un `uvicorn main:app` manual sigue siendo fail-open (modo desarrollo).
mount_frontend(app, require_ui=require_ui_from_env())

# V3.73.x: el modo de red queda escrito en el arranque. Si un equipo de la red no
# consigue entrar, la causa («escucho en loopback» frente a «escucho en la LAN»)
# está en el log del backend en lugar de en una hipótesis. Ojo: esta línea
# informa del modo **declarado**; la interfaz real la fija el launcher al elegir
# el `--host`.
logger.info(
    "Modo de red: %s",
    "LAN (acepta orígenes de la red local)" if lan_mode() else "solo loopback",
)

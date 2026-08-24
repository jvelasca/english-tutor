"""Punto de entrada: crea la app y monta los routers. Código mínimo."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS
from routers.chat import router as chat_router
from routers.conversations import router as conversations_router
from routers.health import router as health_router
from routers.models import router as models_router
from routers.progress import router as progress_router
from routers.pronunciation import router as pronunciation_router
from routers.users import router as users_router
from routers.voz import router as voz_router
from services.store import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="English Tutor API", version="0.3.0", lifespan=lifespan)

# CORS abierto solo para desarrollo local (frontend Vite en :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(voz_router)
app.include_router(pronunciation_router)
app.include_router(progress_router)
app.include_router(conversations_router)
app.include_router(users_router)

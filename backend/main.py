"""Punto de entrada: crea la app y monta los routers. Código mínimo."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS, VERSION
from repositories.db import init_db
from routers.chat import router as chat_router
from routers.conversations import router as conversations_router
from routers.grammar import router as grammar_router
from routers.health import router as health_router
from routers.learning import router as learning_router
from routers.listening import router as listening_router
from routers.models import router as models_router
from routers.profile import router as profile_router
from routers.progress import router as progress_router
from routers.pronunciation import router as pronunciation_router
from routers.users import router as users_router
from routers.vocabulary import router as vocabulary_router
from routers.voz import router as voz_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="English Tutor API", version=VERSION, lifespan=lifespan)

# CORS abierto solo para desarrollo local (frontend Vite en :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(grammar_router)
app.include_router(health_router)
app.include_router(learning_router)
app.include_router(listening_router)
app.include_router(models_router)
app.include_router(profile_router)
app.include_router(voz_router)
app.include_router(pronunciation_router)
app.include_router(progress_router)
app.include_router(conversations_router)
app.include_router(users_router)
app.include_router(vocabulary_router)

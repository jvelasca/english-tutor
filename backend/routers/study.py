"""Configuración de estudio del alumno (V3.87.0 · FASE 2, incremento 1).

Es la superficie que deja al alumno decir CÓMO estudia: dirección EN↔ES, si
reconoce o produce, qué ayuda ve antes de voltear y cuánta carga entra. La
preferencia es del ALUMNO (la sesión de flashcards y la cola de repaso léxico la
comparten); no se abre por mazo porque el mazo por defecto es virtual.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import study_config as study_config_service
from schemas.study import StudyConfigOut, StudyConfigUpdate

router = APIRouter()


def _out(state: dict) -> StudyConfigOut:
    return StudyConfigOut(**state["config"], configured=bool(state["configured"]))


@router.get("/api/study/config", response_model=StudyConfigOut)
async def get_study_config(user: dict = Depends(current_user)) -> StudyConfigOut:
    """Configuración vigente (con los defectos cuando el alumno no ha guardado)."""
    return _out(await study_config_service.get_study_config(user["id"]))


@router.put("/api/study/config", response_model=StudyConfigOut)
async def save_study_config(
    body: StudyConfigUpdate, user: dict = Depends(current_user)
) -> StudyConfigOut:
    """Guarda (merge parcial) la configuración de la SESIÓN, no la de un ajeno."""
    patch = body.model_dump(exclude_none=True)
    return _out(await study_config_service.set_study_config(user["id"], patch))

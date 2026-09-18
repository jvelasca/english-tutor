"""Endpoints de preferencias de usuario (modelo, layout, etc.)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import settings as settings_service
from schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("/api/settings", response_model=SettingsResponse)
async def get_settings(user: dict = Depends(current_user)) -> SettingsResponse:
    return SettingsResponse(settings=await settings_service.get_settings(user["id"]))


@router.put("/api/settings", response_model=SettingsResponse)
async def save_settings(
    body: SettingsUpdate, user: dict = Depends(current_user)
) -> SettingsResponse:
    """Guarda las preferencias del perfil de la **sesión** (V3.75, Fase 2 del P0).

    Hasta V3.74 esta ruta escribía las preferencias del `user_id` que viniera en
    el **cuerpo**, sin credencial ninguna: era la última escritura de la API que
    elegía su destinatario, y dejarla viva habría hecho falsa la afirmación «con
    una sesión de A no se escriben datos de B». Se exige que coincida (403 si no),
    igual que en `PATCH /api/users/{id}`; el campo del cuerpo se retira en la
    Fase 2b junto con los `userId` de la capa `api/` del frontend.
    """
    if body.user_id != user["id"]:
        raise HTTPException(
            status_code=403, detail="Solo puedes editar tus propias preferencias"
        )
    settings = await settings_service.set_settings(user["id"], body.settings)
    return SettingsResponse(settings=settings)

"""Endpoints de preferencias de usuario (modelo, layout, etc.)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import settings as settings_service
from domain import users as user_service
from schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("/api/settings", response_model=SettingsResponse)
async def get_settings(user: dict = Depends(current_user)) -> SettingsResponse:
    return SettingsResponse(settings=await settings_service.get_settings(user["id"]))


@router.put("/api/settings", response_model=SettingsResponse)
async def save_settings(body: SettingsUpdate) -> SettingsResponse:
    # Valida que el usuario exista (404 si no) y guarda las claves indicadas.
    if await user_service.get_user(body.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    settings = await settings_service.set_settings(body.user_id, body.settings)
    return SettingsResponse(settings=settings)

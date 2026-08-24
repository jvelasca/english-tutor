"""Endpoint del perfil de aprendizaje."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import profile as profile_service
from schemas.profile import LearningProfile

router = APIRouter()


@router.get("/api/profile", response_model=LearningProfile)
async def get_profile(user: dict = Depends(current_user)) -> dict:
    return await profile_service.get_profile_summary(user["id"])

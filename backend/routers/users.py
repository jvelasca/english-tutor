"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from domain import users as user_service
from schemas.users import User, UserCreate, UserUpdate

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users() -> list[dict]:
    return await user_service.list_users()


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    return await user_service.create_user(body.name)


@router.patch("/api/users/{user_id}", response_model=User)
async def update_user(user_id: str, body: UserUpdate) -> dict:
    fields = body.model_dump(exclude_unset=True)
    updated = await user_service.update_user(user_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return updated

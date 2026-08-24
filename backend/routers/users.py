"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter

from domain import users as user_service
from schemas.users import User, UserCreate

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users() -> list[dict]:
    return await user_service.list_users()


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    return await user_service.create_user(body.name)

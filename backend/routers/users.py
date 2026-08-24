"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter

from schemas.users import User, UserCreate
from services import store_async

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users() -> list[dict]:
    return await store_async.list_users()


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    return await store_async.create_user(body.name)

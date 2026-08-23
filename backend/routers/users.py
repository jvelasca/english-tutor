"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter

from schemas.users import User, UserCreate
from services import store

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users() -> list[dict]:
    return store.list_users()


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    return store.create_user(body.name)

"""Esquemas Pydantic de usuarios (perfiles locales)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    id: str
    name: str
    created_at: str


class UserCreate(BaseModel):
    name: str = Field(min_length=1)

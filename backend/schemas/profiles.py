"""Esquemas de solicitudes de perfil y de su administración (V3.77).

Los dos lados hablan idiomas distintos a propósito: el alumno **pide** (nombre o
nota, nada más) y el webmaster **decide** (nota y, en un alta, el PIN opcional).
Separarlos evita que el cuerpo de la petición pública acabe teniendo campos que
solo tienen sentido al resolver, como el PIN o el nombre de confirmación de un
purga.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.users import User

MAX_NOTE_CHARS = 200


class ProfileRequestCreate(BaseModel):
    """Petición de alta. Se responde **sin sesión**, así que todo va acotado."""

    display_name: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class ProfileRequestDelete(BaseModel):
    """Petición de baja del propio perfil (requiere sesión)."""

    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class ProfileRequestOut(BaseModel):
    id: int
    kind: str
    display_name: str = ""
    user_id: str = ""
    note: str = ""
    requested_at: str
    status: str
    decided_at: str = ""
    decided_note: str = ""
    resolved_user_id: str = ""


class ProfileRequestsOut(BaseModel):
    requests: list[ProfileRequestOut]
    # Cuántas siguen pendientes en total, para que el lanzador pueda enseñar el
    # contador sin recorrer una lista que puede venir filtrada.
    pending: int


class ProfileRequestDecision(BaseModel):
    """Resolver una petición: nota del webmaster y PIN si el alta lo lleva."""

    note: str = Field(default="", max_length=MAX_NOTE_CHARS)
    pin: str = Field(default="", max_length=16)


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    pin: str = Field(default="", max_length=16)


class AdminUserStatus(BaseModel):
    status: Literal["active", "disabled"]


class AdminPurge(BaseModel):
    """Confirmación de borrado: hay que teclear el nombre exacto del perfil."""

    confirm_name: str = Field(min_length=1, max_length=80)


class AdminUsersOut(BaseModel):
    users: list[User]
    pending: int

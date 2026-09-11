"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from domain import users as user_service
from schemas.users import User, UserCreate, UserUpdate

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users(include_test: bool = False) -> list[dict]:
    # V3.52.1: por defecto los perfiles de prueba quedan fuera del selector.
    return await user_service.list_users(include_test=include_test)


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    return await user_service.create_user(body.name, is_test=body.is_test)


@router.patch("/api/users/{user_id}", response_model=User)
async def update_user(user_id: str, body: UserUpdate) -> dict:
    fields = body.model_dump(exclude_unset=True)
    updated = await user_service.update_user(user_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return updated


@router.delete("/api/users/{user_id}")
async def delete_test_user(user_id: str) -> dict:
    """Borra un perfil de PRUEBA y sus datos (V3.52.1, teardown de tests).

    Solo elimina perfiles con `is_test = 1`: un id real devuelve 404 y no se
    toca. Es la contraparte del POST con `is_test` para que los tests visuales
    no dejen residuos en la base de datos local.
    """
    if not await user_service.delete_test_user(user_id):
        raise HTTPException(status_code=404, detail="Perfil de prueba no encontrado")
    return {"deleted": True}

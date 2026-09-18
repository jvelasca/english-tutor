"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import users as user_service
from schemas.users import User, UserCreate, UserUpdate

router = APIRouter()


@router.get("/api/users", response_model=list[User])
async def list_users(include_test: bool = False) -> list[dict]:
    # V3.52.1: por defecto los perfiles de prueba quedan fuera del selector.
    #
    # Sigue SIN credencial a propósito (V3.75): es el selector de perfiles de la
    # pantalla de entrada, y tiene que poder listar antes de que exista ninguna
    # sesión. En modo LAN, eso significa que un equipo de la red puede enumerar
    # los nombres de los perfiles: es una consecuencia **declarada** del producto
    # sin cuentas, y la cierra la Fase 3 (autenticación), no esta.
    return await user_service.list_users(include_test=include_test)


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate) -> dict:
    # Abierto a propósito: es el alta de perfil del primer arranque (y el que usan
    # los tests visuales para crear su perfil `is_test`).
    return await user_service.create_user(body.name, is_test=body.is_test)


@router.patch("/api/users/{user_id}", response_model=User)
async def update_user(
    user_id: str, body: UserUpdate, session_user: dict = Depends(current_user)
) -> dict:
    """Edita un perfil: **solo el de la propia sesión** (V3.75, Fase 2 del P0).

    Hasta V3.74 esta ruta no pedía identidad ninguna y el `id` de la URL era la
    única autoridad: alcanzaba con cambiar la URL para renombrar o reescribir el
    perfil de otro alumno. Ahora la sesión manda y el `id` de la ruta solo puede
    coincidir con ella (403 si no). Es el borde de autorización que el dossier de
    seguridad señalaba como P0.
    """
    if session_user["id"] != user_id:
        raise HTTPException(
            status_code=403, detail="Solo puedes editar tu propio perfil"
        )
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

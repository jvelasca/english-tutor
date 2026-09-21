"""Endpoints de perfiles de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

import config
from dependencies import current_user
from domain import profile_requests as requests_service
from domain import users as user_service
from schemas.profiles import (
    ProfileRequestCreate,
    ProfileRequestDelete,
    ProfileRequestOut,
)
from schemas.users import User, UserCreate, UserUpdate

router = APIRouter()

# Códigos de las peticiones → estado HTTP. El 409 de «ya pedido» y el 429 de
# «cola llena» son distintos a propósito: la UI dice cosas distintas con ellos
# («ya está pedido» vs «prueba más tarde»), y ninguna de las dos revela nada de
# perfiles ajenos.
_REQUEST_OUTCOME_STATUS = {
    requests_service.OUTCOME_INVALID: (422, "Nombre de perfil no válido"),
    requests_service.OUTCOME_DUPLICATE: (
        409,
        "Ya hay una solicitud pendiente",
    ),
    requests_service.OUTCOME_FULL: (
        429,
        "Hay demasiadas solicitudes pendientes",
    ),
}


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
async def create_user(body: UserCreate, request: Request) -> dict:
    """Alta de perfil. V3.77: **solo desde el propio equipo**.

    Hasta V3.76 esta ruta estaba abierta a propósito («es el alta de perfil del
    primer arranque»), y en modo LAN eso significaba que **cualquier equipo de la
    red podía crear perfiles** en la base de datos del alumno. V3.77 cierra esa
    mitad: crear un perfil es una decisión del webmaster, y por LAN se
    **solicita** (`POST /api/profile-requests`), que es una cola inerte hasta que
    alguien con el equipo la aprueba.

    Lo que **no** cambia: el primer arranque en el propio equipo sigue creando su
    perfil igual, y los tests visuales siguen creando el suyo (`is_test`) porque
    también corren en el equipo. La frontera es la misma que la de la
    administración: `config.is_admin_loopback_host`.
    """
    client_host = request.client.host if request.client else None
    if not config.is_admin_loopback_host(client_host):
        raise HTTPException(
            status_code=403,
            detail=(
                "Un perfil nuevo lo autoriza el webmaster desde este equipo: "
                "envía una solicitud"
            ),
        )
    return await user_service.create_user(body.name, is_test=body.is_test)


@router.post(
    "/api/profile-requests", response_model=ProfileRequestOut, status_code=201
)
async def request_profile(body: ProfileRequestCreate) -> dict:
    """Pide un perfil nuevo (**sin sesión**: quien pide no tiene ninguno).

    Es la única escritura de la app que no exige sesión, y por eso es la más
    acotada: cupo estrecho por IP (`security._PATH_LIMITS`), tope de pendientes y
    una petición por nombre. Y sobre todo: **no crea nada**. Lo peor que puede
    hacer quien la llame es dejar una fila que el webmaster verá y podrá
    rechazar.

    Está declarada en `docs/ARQUITECTURA.md` §«Superficie sin sesión» y su
    candado vive en `tests/test_public_surface.py`.
    """
    outcome = await requests_service.request_create(body.display_name, body.note)
    if outcome.code != requests_service.OUTCOME_OK:
        status_code, detail = _REQUEST_OUTCOME_STATUS[outcome.code]
        raise HTTPException(status_code=status_code, detail=detail)
    assert outcome.request is not None  # ok siempre trae la solicitud
    return outcome.request


@router.post(
    "/api/profile-requests/delete",
    response_model=ProfileRequestOut,
    status_code=201,
)
async def request_profile_delete(
    body: ProfileRequestDelete, user: dict = Depends(current_user)
) -> dict:
    """El perfil **de la sesión** pide que se le borre. No borra nada aún.

    Va con sesión y sin `{id}` en la ruta —igual que `PUT /api/session/pin`—
    porque no existe la forma de pedir la baja del perfil de otro.
    """
    outcome = await requests_service.request_delete(user["id"], body.note)
    if outcome.code != requests_service.OUTCOME_OK:
        status_code, detail = _REQUEST_OUTCOME_STATUS[outcome.code]
        raise HTTPException(status_code=status_code, detail=detail)
    assert outcome.request is not None  # ok siempre trae la solicitud
    return outcome.request


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

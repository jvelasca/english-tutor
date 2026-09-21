"""Administración de perfiles (V3.77) — el webmaster, desde el lanzador.

Estas rutas **crean, desactivan y purgan** perfiles, así que van detrás del
candado más estrecho de la app (`dependencies.require_admin_local`): PIN de
administración **y** que la petición venga del propio equipo. Las dos cosas son
necesarias y ninguna basta sola — el PIN viaja en una cabecera y en una red
compartida eso es material expuesto; estar en el equipo sin el PIN no debería
bastar para borrarle el historial a nadie.

Lo que **no** hace este router es decidir por su cuenta: resolver una petición,
desactivar o purgar es un acto explícito del webmaster, y todas sus acciones
quedan en la propia tabla de solicitudes (quién, cuándo y con qué nota).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import require_admin_local
from domain import profile_requests as requests_service
from domain import users as user_service
from repositories import profile_requests as requests_repo
from schemas.profiles import (
    AdminPurge,
    AdminUserCreate,
    AdminUsersOut,
    AdminUserStatus,
    ProfileRequestDecision,
    ProfileRequestOut,
    ProfileRequestsOut,
)
from schemas.users import User

router = APIRouter()

# `None` = todas las solicitudes. `pending` es el defecto porque es lo que el
# webmaster tiene que atender; el histórico se pide a propósito.
_STATUS_FILTERS = (None, *requests_repo.STATUSES)


@router.get("/api/admin/profile-requests", response_model=ProfileRequestsOut)
async def list_profile_requests(
    status: str | None = Query(default=requests_repo.STATUS_PENDING),
    _: None = Depends(require_admin_local),
) -> dict:
    if status not in _STATUS_FILTERS:
        raise HTTPException(status_code=422, detail="Estado de solicitud no válido")
    return await requests_service.list_requests(status)


@router.post(
    "/api/admin/profile-requests/{request_id}/approve",
    response_model=ProfileRequestOut,
)
async def approve_profile_request(
    request_id: int,
    body: ProfileRequestDecision,
    _: None = Depends(require_admin_local),
) -> dict:
    """Aprueba: un alta **crea** el perfil; una baja **desactiva** (reversible).

    Purgar no ocurre aquí, ni siquiera cuando la petición era de borrado: es un
    acto aparte, con confirmación por nombre y copia previa. Aprobar una baja es
    «este perfil deja de usarse», que es lo que el alumno puede pedir; destruir
    su evidencia es lo que decide el webmaster.
    """
    resolved = await requests_service.approve(
        request_id,
        pin=body.pin,
        note=body.note,
    )
    if resolved is None:
        raise HTTPException(
            status_code=409,
            detail="La solicitud no existe o ya estaba resuelta",
        )
    return resolved["request"]


@router.post(
    "/api/admin/profile-requests/{request_id}/reject",
    response_model=ProfileRequestOut,
)
async def reject_profile_request(
    request_id: int,
    body: ProfileRequestDecision,
    _: None = Depends(require_admin_local),
) -> dict:
    resolved = await requests_service.reject(request_id, note=body.note)
    if resolved is None:
        raise HTTPException(
            status_code=409,
            detail="La solicitud no existe o ya estaba resuelta",
        )
    return resolved


@router.get("/api/admin/users", response_model=AdminUsersOut)
async def list_admin_users(
    include_disabled: bool = Query(default=True),
    include_test: bool = Query(default=False),
    _: None = Depends(require_admin_local),
) -> dict:
    """Todos los perfiles, desactivados incluidos, con el contador de pendientes.

    El lanzador lo pinta junto a las solicitudes, así que devolver el contador
    aquí ahorra un viaje y, sobre todo, evita que los dos números se pinten de
    momentos distintos y se contradigan.
    """
    users = await user_service.list_users(
        include_test=include_test, include_disabled=include_disabled
    )
    return {
        "users": users,
        "pending": await requests_service.count_pending(),
    }


@router.post("/api/admin/users", response_model=User)
async def create_admin_user(
    body: AdminUserCreate,
    _: None = Depends(require_admin_local),
) -> dict:
    """Alta directa del webmaster (sin pasar por la cola de solicitudes)."""
    created = await requests_service.create_profile(body.name, pin=body.pin)
    if created is None:
        raise HTTPException(
            status_code=422,
            detail="Nombre no válido o PIN con mala forma (4-6 dígitos)",
        )
    return created


@router.post("/api/admin/users/{user_id}/status", response_model=User)
async def set_admin_user_status(
    user_id: str,
    body: AdminUserStatus,
    _: None = Depends(require_admin_local),
) -> dict:
    updated = await requests_service.set_status(user_id, body.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return updated


@router.post("/api/admin/users/{user_id}/purge")
async def purge_admin_user(
    user_id: str,
    body: AdminPurge,
    _: None = Depends(require_admin_local),
) -> dict:
    """Purga irreversible, con copia previa. `confirm_name` debe coincidir.

    Un fallo aquí no dice cuál de las condiciones falló (nombre que no cuadra,
    perfil inexistente, perfil todavía activo, o que la copia no se pudo escribir)
    a propósito: el lanzador ya sabe qué pidió y ya comprueba la desactivación
    antes de llamar, así que distinguirlas hacia fuera solo daría un oráculo sobre
    qué perfiles existen.
    """
    result = await requests_service.purge_profile(user_id, body.confirm_name)
    if result is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se purgó: el perfil no existe, sigue activo (desactívalo "
                "antes), el nombre de confirmación no coincide o la copia de "
                "seguridad no se pudo crear"
            ),
        )
    return result

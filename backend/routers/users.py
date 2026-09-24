"""Endpoints de cuentas de usuario locales."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import profile_requests as requests_service
from domain import users as user_service
from schemas.profiles import (
    ProfileRequestCreate,
    ProfileRequestDelete,
    ProfileRequestOut,
)
from schemas.users import User, UserUpdate

router = APIRouter()

# Códigos de las peticiones → estado HTTP. El 409 de «ya pedido» y el 429 de
# «cola llena» son distintos a propósito: la UI dice cosas distintas con ellos
# («ya está pedido» vs «prueba más tarde»), y ninguna de las dos revela nada de
# perfiles ajenos.
_REQUEST_OUTCOME_STATUS = {
    requests_service.OUTCOME_INVALID: (422, "Nombre de perfil no válido"),
    requests_service.OUTCOME_EMAIL_INVALID: (422, "EMAIL_FORMAT"),
    requests_service.OUTCOME_DUPLICATE: (
        409,
        "Ya hay una solicitud pendiente",
    ),
    requests_service.OUTCOME_EMAIL_TAKEN: (
        409,
        "EMAIL_TAKEN",
    ),
    requests_service.OUTCOME_FULL: (
        429,
        "Hay demasiadas solicitudes pendientes",
    ),
}


@router.get("/api/users", response_model=list[User])
async def list_users(
    include_test: bool = False, session_user: dict = Depends(current_user)
) -> list[dict]:
    """Cuentas activas de la app. **V3.82: exige sesión.**

    Hasta V3.81 esto era público a propósito: la puerta de entrada era un
    **selector** con avatares que tenía que pintar los nombres antes de que
    existiera ninguna sesión. Con el login por email esa necesidad desaparece, así
    que la lista vuelve a estar detrás de la puerta y deja de enumerar quién
    existe a cualquiera que alcance la API. Es el último resto del modelo
    «selector» que la Fase D retira.

    V3.52.1: por defecto los perfiles de prueba quedan fuera.

    V3.81: los nombres se ven, el **email no** salvo el de la propia cuenta. Sigue
    siendo PII y esta lista la consume la app para pintar el menú de usuario; sin
    el recorte, cualquier sesión podría cosechar los correos de todas las cuentas.
    Lo que la app necesita de las demás —nombre, avatar— sigue llegando entero.
    """
    users = await user_service.list_users(include_test=include_test)
    own_id = session_user["id"]
    return [_without_foreign_email(row, own_id) for row in users]


def _without_foreign_email(row: dict, own_id: str | None) -> dict:
    """Tapa el email (y el aviso de contraseña temporal, que es de la cuenta) de
    las filas que no son de quien pregunta.

    Se recorta aquí, en el borde HTTP, y no en el repositorio: la consola de
    gestión (`/api/admin/users`) lee las **mismas** filas detrás del candado de
    administración y necesita el email completo.
    """
    if own_id is not None and row.get("id") == own_id:
        return row
    masked = dict(row)
    masked["email"] = ""
    masked["must_change_password"] = False
    return masked


@router.post(
    "/api/profile-requests", response_model=ProfileRequestOut, status_code=201
)
async def request_profile(body: ProfileRequestCreate) -> dict:
    """Pide un perfil nuevo (**sin sesión**: quien pide no tiene ninguno).

    Es una de las escrituras sin sesión de la app —las otras canjean un token de
    correo, así que esta es la única que **no** trae ninguna prueba de nada— y por
    eso es la más estrecha: cupo por IP (`security._PATH_LIMITS`), tope de
    pendientes y una petición por nombre y por email. Y sobre todo: **no crea
    nada**. Lo peor que puede hacer quien la llame es dejar una fila que el
    webmaster verá y podrá rechazar.

    V3.82: la solicitud trae el email (con el que se manda la invitación) y el
    avatar elegido, así que al aprobarla no hay que teclear nada a mano.

    Está declarada en `docs/ARQUITECTURA.md` §«Superficie sin sesión» y su
    candado vive en `tests/test_public_surface.py`.
    """
    outcome = await requests_service.request_create(
        body.display_name,
        body.note,
        email=body.email,
        avatar_color=body.avatar_color,
        avatar_emoji=body.avatar_emoji,
        avatar_image=body.avatar_image,
    )
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
    """La cuenta **de la sesión** pide que se le borre. No borra nada aún.

    Va con sesión y sin `{id}` en la ruta —igual que `PUT /api/session/password`—
    porque no existe la forma de pedir la baja de la cuenta de otro.
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

"""Endpoints de cuentas de usuario locales."""
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
from services import credentials, mailer, sessions

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
async def list_users(request: Request, include_test: bool = False) -> list[dict]:
    # V3.52.1: por defecto los perfiles de prueba quedan fuera del selector.
    #
    # Sigue SIN sesión a propósito (V3.75) y sigue siéndolo en V3.81: la puerta de
    # entrada es un **selector** con avatares y tiene que pintar los nombres antes
    # de que exista ninguna sesión. En modo LAN eso significa que un equipo de la
    # red puede enumerar los nombres de las cuentas; es una consecuencia
    # **declarada** del diseño elegido (selector estilo Netflix en un producto de
    # casa) y lo que la acota es que cada cuenta con credencial **no entra** sin
    # su contraseña. Quien quiera cerrar también los nombres tiene la vía del
    # modo LAN con solicitudes.
    #
    # V3.81: los nombres se declaran, el **email no**. El correo es PII nueva y
    # esta lista es la única superficie que no exige sesión, así que solo se
    # devuelve el de la **propia** cuenta (el de la sesión, que ya lo conoce):
    # sin este recorte, cualquier dispositivo de la red podría cosechar los
    # correos de toda la casa sin escribir una contraseña. Lo que la puerta
    # necesita de las demás cuentas —nombre, avatar y `has_password`— sigue
    # llegando entero.
    users = await user_service.list_users(include_test=include_test)
    return [_without_foreign_email(row, await _own_user_id(request)) for row in users]


async def _own_user_id(request: Request) -> str | None:
    """El id de la **propia** cuenta si la sesión es buena, y `None` si no.

    Se resuelve a mano en vez de con `current_user_optional` porque esa
    dependencia **propaga el 404** de una sesión que apunta a una cuenta purgada,
    y aquí eso sería letal: esta lista la pide el arranque de la app, así que un
    404 la dejaría vacía y la puerta de entrada volvería a quedarse sin salida
    —exactamente el cuelgue que V3.80.2 desatascó—. Para lo que se decide aquí
    (qué email se tapa) cualquier fallo de sesión significa lo mismo: «no sé
    quién eres», así que no hay nada que propagar.
    """
    resolved = sessions.verify_session(request.cookies.get(sessions.SESSION_COOKIE))
    if resolved is None:
        return None
    user_id, epoch = resolved
    if await user_service.get_auth_epoch(user_id) != epoch:
        return None
    return user_id


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


@router.post("/api/users", response_model=User)
async def create_user(body: UserCreate, request: Request) -> dict:
    """**Registro** de una cuenta. V3.77: solo desde el propio equipo.

    Hasta V3.76 esta ruta estaba abierta a propósito («es el alta de perfil del
    primer arranque»), y en modo LAN eso significaba que **cualquier equipo de la
    red podía crear perfiles** en la base de datos del alumno. V3.77 cierra esa
    mitad: crear una cuenta es una decisión del webmaster, y por LAN se
    **solicita** (`POST /api/profile-requests`), que es una cola inerte hasta que
    alguien con el equipo la aprueba.

    V3.81: el alta deja de ser «un nombre y a correr» y pasa a ser un **registro
    real** —nombre, email y contraseña—, que es la Fase 3 del P0. La contraseña se
    hashea con PBKDF2 (sal por cuenta) y nunca se guarda ni se registra en claro;
    el email nace sin verificar y, si hay SMTP configurado, sale el enlace de
    confirmación (sin SMTP la app funciona igual y confirma el webmaster).

    Los dos 409 son distintos a propósito y la UI dice cosas distintas con ellos:
    `USER_NAME_TAKEN` (hay que elegir otro nombre, porque el selector identifica
    por nombre) y `EMAIL_TAKEN` (esa cuenta ya existe: toca entrar o recuperarla).
    """
    client_host = request.client.host if request.client else None
    if not config.is_admin_loopback_host(client_host):
        raise HTTPException(
            status_code=403,
            detail=(
                "Una cuenta nueva la autoriza el webmaster desde este equipo: "
                "envía una solicitud"
            ),
        )
    # V3.80.2: dos usuarios activos con el mismo nombre son indistinguibles en el
    # selector (y en la consola de gestión, que es donde se decide a quién se le
    # borra el historial). El nombre se trata como identificador visible, así que
    # no se admite repetido. La comprobación vive aquí y no en el repositorio
    # porque los tests crean perfiles homónimos a propósito para probar el
    # aislamiento entre usuarios.
    if not body.is_test and await user_service.name_in_use(body.name):
        raise HTTPException(status_code=409, detail="USER_NAME_TAKEN")

    email = credentials.normalize_email(body.email)
    if not email:
        raise HTTPException(status_code=400, detail="EMAIL_FORMAT")
    if await user_service.email_in_use(email):
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")

    if not credentials.is_valid_password(body.password):
        raise HTTPException(status_code=400, detail="PASSWORD_FORMAT")

    created = await user_service.create_user(
        body.name,
        is_test=body.is_test,
        email=email,
        password_hash=credentials.hash_password(body.password),
    )
    await user_service.record_event(
        subject_id=created["id"],
        subject_name=created["name"],
        action=user_service.EVENT_CREATED,
        note=email,
        actor="alumno",
    )

    # El enlace de confirmación sale **después** de que la cuenta exista: si el
    # correo falla (o no hay SMTP), el alta sigue en pie. El correo es una señal,
    # no un requisito (decisión híbrida de la Fase 3).
    if email:
        token = credentials.new_email_token()
        if await user_service.set_email_verification(
            created["id"], credentials.hash_email_token(token)
        ):
            mailer.send(
                kind=mailer.KIND_VERIFICATION,
                to=email,
                link=mailer.verification_link(
                    str(request.base_url).rstrip("/"), token
                ),
            )
    return created


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

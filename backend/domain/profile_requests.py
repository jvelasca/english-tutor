"""Solicitudes de perfil y su resolución (V3.77).

Este módulo es la **frontera** entre lo que el alumno puede pedir y lo que el
webmaster puede decidir, y lo dice en la forma de sus funciones:

- `request_*` solo **registra** una petición. Nunca crea ni borra un perfil, ni
  toca una fila de evidencia. Cualquiera puede llamarlas (la de alta, incluso sin
  sesión) y lo peor que puede pasar es que la cola de pendientes crezca.
- `approve_*` y `reject_*` **resuelven** una petición y son las únicas que
  cambian el mundo. Solo las llama el router de administración, que exige PIN y
  que la petición venga del propio equipo.

Aprobar un alta crea el perfil. Aprobar un **borrado** *desactiva*: es la mitad
reversible de la decisión, y la irreversible (purgar) es un acto aparte, con
confirmación por nombre y copia previa, que el webmaster ejecuta cuando quiere
(`agentes/v377-perfiles-webmaster.md`).
"""
from __future__ import annotations

from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

import config
from domain import users as user_service
from repositories import profile_requests as requests_repo
from repositories import users as users_repo
from services import backup as backup_service
from services import pins

# Desenlaces de una petición. Son códigos y no excepciones porque el router los
# tiene que traducir a estados HTTP distintos (201, 409, 422, 429) y quien decide
# el estado es el router, no el dominio.
OUTCOME_OK = "ok"
OUTCOME_INVALID = "invalid"
OUTCOME_FULL = "full"
OUTCOME_DUPLICATE = "duplicate"


@dataclass(frozen=True)
class RequestOutcome:
    """Resultado de registrar una petición: qué pasó y, si se registró, cuál es."""

    code: str
    request: dict | None = None


def normalize_name(raw: str | None) -> str:
    """Nombre de perfil normalizado, o `""` si no sirve.

    Se colapsan los espacios internos además de recortar los extremos: «  Ana
    María  » y «Ana  María» tienen que ser el mismo nombre para la regla de «una
    petición pendiente por nombre», o la regla se esquiva escribiendo un espacio
    de más.
    """
    text = " ".join((raw or "").split())
    if not text or len(text) > config.PROFILE_REQUEST_NAME_MAX:
        return ""
    return text


def normalize_note(raw: str | None) -> str:
    """Nota acotada. No se valida su contenido: es texto del solicitante."""
    return " ".join((raw or "").split())[: config.PROFILE_REQUEST_NOTE_MAX]


async def request_create(display_name: str, note: str = "") -> RequestOutcome:
    """Registra una petición de alta. **No** crea el perfil.

    Las tres vallas van antes de escribir nada, y en este orden: el nombre tiene
    que servir, la cola no puede estar llena y no se admite dos veces la misma
    petición. La última no es por el alumno —pedir dos veces no es un error suyo—
    sino por el webmaster: una cola con «Ana» cinco veces no es una cola.
    """
    name = normalize_name(display_name)
    if not name:
        return RequestOutcome(OUTCOME_INVALID)
    if await count_pending() >= config.PROFILE_REQUEST_MAX_PENDING:
        return RequestOutcome(OUTCOME_FULL)
    repeated = await run_in_threadpool(
        requests_repo.has_pending_create_for_name, name
    )
    if repeated:
        return RequestOutcome(OUTCOME_DUPLICATE)
    created = await run_in_threadpool(
        requests_repo.create_request,
        requests_repo.KIND_CREATE,
        display_name=name,
        note=normalize_note(note),
    )
    return RequestOutcome(OUTCOME_OK, created)


async def request_delete(user_id: str, note: str = "") -> RequestOutcome:
    """Registra la petición de baja de un perfil. **No** borra ni desactiva nada.

    Devuelve `duplicate` si ya había una pendiente: la baja repetida no es un
    error del alumno, pero tampoco debe llenar la cola con la misma petición.
    """
    if await run_in_threadpool(requests_repo.pending_delete_for_user, user_id):
        return RequestOutcome(OUTCOME_DUPLICATE)
    created = await run_in_threadpool(
        requests_repo.create_request,
        requests_repo.KIND_DELETE,
        user_id=user_id,
        note=normalize_note(note),
    )
    return RequestOutcome(OUTCOME_OK, created)


async def list_requests(status: str | None = None) -> dict:
    """Cola de solicitudes (pendientes por defecto) + cuántas hay pendientes."""
    rows = await run_in_threadpool(requests_repo.list_requests, status)
    pending = await run_in_threadpool(requests_repo.count_pending)
    return {"requests": rows, "pending": pending}


async def count_pending() -> int:
    return await run_in_threadpool(requests_repo.count_pending)


async def approve(
    request_id: int, *, pin: str = "", note: str = ""
) -> dict | None:
    """Resuelve una petición **hacia delante**. `None` si no está pendiente.

    El orden importa: primero se hace el efecto y solo después se marca la
    petición como resuelta. Al revés, un fallo al crear el perfil dejaría la
    petición «aprobada» sin perfil y el webmaster no tendría forma de reintentar.
    """
    request = await run_in_threadpool(requests_repo.get_request, request_id)
    if request is None or request["status"] != requests_repo.STATUS_PENDING:
        return None

    if request["kind"] == requests_repo.KIND_CREATE:
        created = await create_profile(request["display_name"], pin=pin)
        if created is None:
            return None
        resolved = await run_in_threadpool(
            requests_repo.resolve,
            request_id,
            requests_repo.STATUS_APPROVED,
            decided_note=normalize_note(note),
            resolved_user_id=created["id"],
        )
        return {"request": resolved, "user": created}

    # Baja: se **desactiva** (reversible). Purgar es un acto aparte y deliberado.
    target = request["user_id"]
    disabled = await run_in_threadpool(
        users_repo.set_status, target, users_repo.STATUS_DISABLED
    )
    if disabled is None:
        return None
    resolved = await run_in_threadpool(
        requests_repo.resolve,
        request_id,
        requests_repo.STATUS_APPROVED,
        decided_note=normalize_note(note),
        resolved_user_id=target,
    )
    return {"request": resolved, "user": disabled}


async def reject(request_id: int, note: str = "") -> dict | None:
    return await run_in_threadpool(
        requests_repo.resolve,
        request_id,
        requests_repo.STATUS_REJECTED,
        decided_note=normalize_note(note),
    )


async def create_profile(name: str, *, pin: str = "") -> dict | None:
    """Alta directa del webmaster. `None` si el nombre no sirve o el PIN no vale.

    El PIN es **opcional** aquí igual que en el alta del primer arranque: si el
    webmaster no lo pone, el perfil entra sin credencial (la consecuencia que
    V3.76 ya declaró). Si lo pone, se guarda hasheado con `services.pins`.
    """
    clean = normalize_name(name)
    if not clean:
        return None
    if pin and not pins.is_valid_pin(pin):
        return None
    created = await user_service.create_user(clean)
    if pin:
        await user_service.set_pin_hash(created["id"], pins.hash_pin(pin))
        created = await user_service.get_user(created["id"]) or created
    return created


async def set_status(user_id: str, status: str) -> dict | None:
    """Desactiva o reactiva un perfil (el webmaster, desde el lanzador)."""
    return await run_in_threadpool(users_repo.set_status, user_id, status)


async def purge_profile(user_id: str, confirm_name: str) -> dict | None:
    """Borra un perfil **y toda su evidencia**. Irreversible.

    Cuatro cosas tienen que cuadrar antes de que se borre nada:

    1. El perfil existe.
    2. `confirm_name` coincide con su nombre: es lo que impide que un clic de más
       o un id copiado por error se lleve por delante al perfil equivocado. La
       comparación ignora mayúsculas y espacios sobrantes (no es un examen de
       tecleo, es una confirmación de intención).
    3. El perfil está **desactivado**. Purgar un perfil activo es destruir
       evidencia de alguien que puede estar usándola ahora mismo; pasar por la
       desactivación obliga a que exista un momento —y un día— en que la decisión
       se puede deshacer. Es barato para el webmaster (dos clics) y es la
       diferencia entre un borrado deliberado y un clic de más.
    4. **La copia**: se toma un backup ZIP antes de purgar y se devuelve su
       nombre. Si la copia falla, no se purga. Es la única red que existe, y por
       eso la copia manda sobre la comodidad.

    `None` si algo de lo anterior no se cumple.
    """
    user = await user_service.get_user(user_id)
    if user is None:
        return None
    if normalize_name(confirm_name).casefold() != normalize_name(
        user["name"]
    ).casefold():
        return None
    if user.get("status") != users_repo.STATUS_DISABLED:
        return None
    snapshot = await run_in_threadpool(backup_service.create_backup)
    if not await run_in_threadpool(users_repo.purge_user, user_id):
        return None
    return {
        "purged": True,
        "user_id": user_id,
        "name": user["name"],
        "backup": snapshot.get("name", ""),
    }

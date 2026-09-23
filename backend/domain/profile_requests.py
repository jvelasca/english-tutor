"""Solicitudes de cuenta y su resolución (V3.77 · cuentas en V3.81).

Este módulo es la **frontera** entre lo que el alumno puede pedir y lo que el
webmaster puede decidir, y lo dice en la forma de sus funciones:

- `request_*` solo **registra** una petición. Nunca crea ni borra una cuenta, ni
  toca una fila de evidencia. Cualquiera puede llamarlas (la de alta, incluso sin
  sesión) y lo peor que puede pasar es que la cola de pendientes crezca.
- `approve_*` y `reject_*` **resuelven** una petición. Solo las llama el router de
  administración, que exige PIN de administración y que la petición venga del
  propio equipo.
- V3.81 añade las operaciones de **consola de gestión** (`set_credentials`,
  `verify_email_by_hand`, `force_unenroll`, `reenroll`, `edit_user`, `history`),
  que son las que le dan al webmaster «control y prioridad sobre todo». Todas
  anotan lo que hacen en `user_events`: una decisión que se le impone a un alumno
  tiene que poder explicarse después.

Aprobar un alta crea la cuenta **sin credencial** (y la consola ofrece asignarla).
Aprobar un **borrado** *desactiva*: es la mitad reversible de la decisión, y la
irreversible (purgar) es un acto aparte, con confirmación por nombre y copia
previa, que el webmaster ejecuta cuando quiere
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


async def approve(request_id: int, *, note: str = "") -> dict | None:
    """Resuelve una petición **hacia delante**. `None` si no está pendiente.

    El orden importa: primero se hace el efecto y solo después se marca la
    petición como resuelta. Al revés, un fallo al crear la cuenta dejaría la
    petición «aprobada» sin cuenta y el webmaster no tendría forma de reintentar.

    V3.81: aprobar un alta crea la cuenta **sin credencial** y la consola ofrece a
    continuación asignarle email y contraseña temporal. Son dos decisiones
    distintas —«esta persona puede tener cuenta» y «con qué entra»— y juntarlas
    obligaba a teclear el PIN antes de saber si la cuenta se iba a crear siquiera.
    """
    request = await run_in_threadpool(requests_repo.get_request, request_id)
    if request is None or request["status"] != requests_repo.STATUS_PENDING:
        return None

    if request["kind"] == requests_repo.KIND_CREATE:
        created = await create_profile(request["display_name"])
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
    if disabled is not None:
        await user_service.record_event(
            subject_id=target,
            subject_name=disabled["name"],
            action=user_service.EVENT_DISABLED,
            note=normalize_note(note),
        )
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


async def create_profile(
    name: str,
    *,
    email: str = "",
    password_hash: str = "",
    must_change: bool = True,
) -> dict | None:
    """Alta del webmaster. `None` si el nombre no sirve o el email ya está cogido.

    V3.81: la cuenta puede nacer **con** credenciales (nombre + email + contraseña
    ya hasheada) o **sin** ellas. Sin credencial es el caso de una petición
    aprobada: entra en la lista de tareas de la consola («asígnale contraseña»)
    mientras la compatibilidad le siga permitiendo entrar nombrando.

    La comprobación de email duplicado no es cosmética: el índice único de la BD
    lo rechazaría al escribir, y sin esta comprobación el error llegaría como un
    `IntegrityError` sin mensaje útil.
    """
    clean = normalize_name(name)
    if not clean:
        return None
    if email and await user_service.email_in_use(email):
        return None
    created = await user_service.create_user(
        clean,
        email=email,
        password_hash=password_hash,
        must_change_password=must_change if password_hash else False,
    )
    await user_service.record_event(
        subject_id=created["id"],
        subject_name=created["name"],
        action=user_service.EVENT_CREATED,
    )
    return created


async def set_credentials(
    user_id: str, *, email: str, password: str, must_change: bool = True
) -> dict | None:
    """Asigna o restablece email + contraseña de una cuenta (consola de gestión).

    Devuelve la cuenta actualizada o `None` si el email no vale o ya lo usa otra.
    La contraseña llega **en claro** desde el router y se hashea aquí mismo: es el
    único punto donde existe sin hash, y vive solo el tiempo de esta llamada.
    """
    from services import credentials  # import local: evita el ciclo con el router

    clean = credentials.normalize_email(email)
    if not clean or not credentials.is_valid_password(password):
        return None
    if await user_service.email_in_use(clean, exclude_uid=user_id):
        return None
    updated = await user_service.set_credentials(
        user_id,
        email=clean,
        password_hash=credentials.hash_password(password),
        must_change=must_change,
    )
    if updated is None:
        return None
    await user_service.record_event(
        subject_id=user_id,
        subject_name=updated["name"],
        action=user_service.EVENT_CREDENTIALS,
        note="credencial asignada" + (" · temporal" if must_change else ""),
    )
    return updated


async def verify_email_by_hand(user_id: str) -> dict | None:
    """Sella el email sin pasar por el correo (modo híbrido, sin SMTP).

    Es la pieza que hace que la verificación no sea un muro: en una instalación de
    casa sin proveedor de correo, el webmaster confirma a mano —habitualmente
    porque tiene delante a la persona— y el resto del producto no se entera.
    """
    user = await user_service.get_user(user_id)
    if user is None:
        return None
    if not user.get("email"):
        return None
    updated = await user_service.mark_email_verified(user_id)
    if updated is None:
        return None
    await user_service.record_event(
        subject_id=user_id,
        subject_name=updated["name"],
        action=user_service.EVENT_EMAIL_VERIFIED,
        note="email verificado",
    )
    return updated


async def force_unenroll(user_id: str, reason: str) -> dict | None:
    """**Fuerza** la baja de una cuenta. El motivo es obligatorio y queda escrito.

    No es lo mismo que desactivar: desactivar es «esta cuenta está fuera de
    servicio» (una decisión de mantenimiento, reversible y silenciosa) y forzar la
    baja es «esta persona deja la app», con un motivo que el alumno puede
    preguntar. Las dos cierran la sesión al instante (suben la época).
    """
    motivo = normalize_note(reason) or "sin motivo indicado"
    updated = await user_service.set_unenrolled(user_id, enrolled=False)
    if updated is None:
        return None
    await user_service.record_event(
        subject_id=user_id,
        subject_name=updated["name"],
        action=user_service.EVENT_FORCE_UNENROLLED,
        note=motivo,
    )
    return updated


async def reenroll(user_id: str, note: str = "") -> dict | None:
    """Reinscribe una cuenta dada de baja (o desactivada) y la deja activa."""
    updated = await user_service.set_unenrolled(user_id, enrolled=True)
    if updated is None:
        return None
    await user_service.record_event(
        subject_id=user_id,
        subject_name=updated["name"],
        action=user_service.EVENT_ENROLLED,
        note=normalize_note(note),
    )
    return updated


async def edit_user(user_id: str, fields: dict) -> dict | None:
    """Edición de los datos de una cuenta por parte del webmaster.

    Tiene la misma autoridad que el propio alumno (nombre y avatar) y una más: el
    **email**, que el alumno solo puede cambiar con su contraseña delante. Si el
    email cambia, su verificación se reinicia —heredar el sello del correo
    anterior convertiría apuntar a otro correo en un atajo para saltarse el
    trámite—.
    """
    current = await user_service.get_user(user_id)
    if current is None:
        return None

    email = fields.pop("email", None)
    changed: list[str] = []
    # Un nombre repetido rompería la regla del selector; se comprueba también al
    # editar, no solo al crear (si no, la regla tendría una puerta abierta).
    new_name = fields.get("name")
    if new_name is not None and await user_service.name_in_use(
        new_name, exclude_uid=user_id
    ):
        return None

    updated = await user_service.update_user(user_id, fields)
    if updated is None:
        return None
    changed.extend(f"{k}={v}" for k, v in fields.items() if v is not None)

    if email is not None:
        from services import credentials

        clean = credentials.normalize_email(email)
        if not clean or await user_service.email_in_use(clean, exclude_uid=user_id):
            return None
        with_email = await user_service.set_email(user_id, clean)
        if with_email is None:
            return None
        updated = with_email
        changed.append("email actualizado")
        # Cambiar el email **reinicia** la verificación: el sello pertenecía al
        # correo anterior, no a la persona.
        await user_service.set_email_verification(user_id, "")

    await user_service.record_event(
        subject_id=user_id,
        subject_name=updated["name"],
        action=user_service.EVENT_EDITED,
        note=" · ".join(changed)[:200],
    )
    return updated


async def history(user_id: str, limit: int = 50) -> list[dict]:
    return await user_service.list_events(user_id, limit)


async def set_status(user_id: str, status: str, note: str = "") -> dict | None:
    """Desactiva o reactiva una cuenta (el webmaster, desde la consola).

    V3.81 añade el valor `unenrolled` a los estados válidos, pero forzar la baja
    tiene su propia función (`force_unenroll`) porque **exige motivo**. Aquí solo
    se registran `active` y `disabled`; cualquier otro valor lo rechaza el
    repositorio.
    """
    updated = await run_in_threadpool(users_repo.set_status, user_id, status)
    if updated is None:
        return None
    if status != users_repo.STATUS_ACTIVE:
        await user_service.record_event(
            subject_id=user_id,
            subject_name=updated["name"],
            action=user_service.EVENT_DISABLED,
            note=normalize_note(note),
        )
    return updated


async def purge_profile(user_id: str, confirm_name: str) -> dict | None:
    """Borra una cuenta **y toda su evidencia**. Irreversible.

    Cuatro cosas tienen que cuadrar antes de que se borre nada:

    1. La cuenta existe.
    2. `confirm_name` coincide con su nombre: es lo que impide que un clic de más
       o un id copiado por error se lleve por delante a la cuenta equivocada. La
       comparación ignora mayúsculas y espacios sobrantes (no es un examen de
       tecleo, es una confirmación de intención).
    3. La cuenta está **fuera de servicio** (desactivada o dada de baja, V3.81).
       Purgar una cuenta activa es destruir evidencia de alguien que puede estar
       usándola ahora mismo; pasar por la desactivación o por la baja obliga a que
       exista un momento —y un día— en que la decisión se puede deshacer. Es
       barato para el webmaster (dos clics) y es la diferencia entre un borrado
       deliberado y un clic de más.
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
    if user.get("status") not in (
        users_repo.STATUS_DISABLED,
        users_repo.STATUS_UNENROLLED,
    ):
        return None
    snapshot = await run_in_threadpool(backup_service.create_backup)
    # Primero se borra y **solo después** se registra. Al revés, un fallo de la
    # purga dejaría escrito «datos purgados» sin haber purgado nada, que es la
    # peor clase de evidencia: la que afirma lo que no ocurrió. El nombre se
    # captura en memoria porque a partir de aquí la fila de `users` ya no existe;
    # `user_events` sobrevive porque su columna es `subject_id`.
    if not await run_in_threadpool(users_repo.purge_user, user_id):
        return None
    await user_service.record_event(
        subject_id=user_id,
        subject_name=user["name"],
        action=user_service.EVENT_PURGED,
        note=f"copia {snapshot.get('name', '')}",
    )
    return {
        "purged": True,
        "user_id": user_id,
        "name": user["name"],
        "backup": snapshot.get("name", ""),
    }

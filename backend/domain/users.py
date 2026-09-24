"""Servicio de dominio de usuarios (V3.81: el perfil es una **cuenta**)."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import users as users_repo

# La lista canónica de estados vive en el repositorio, que es quien la valida al
# escribir; el dominio la reexpone para que las capas de arriba no tengan que
# importar el repositorio solo por dos cadenas.
STATUS_ACTIVE = users_repo.STATUS_ACTIVE
STATUS_DISABLED = users_repo.STATUS_DISABLED
STATUS_UNENROLLED = users_repo.STATUS_UNENROLLED

# Acciones del historial (reexpuestas por el mismo motivo que los estados).
EVENT_CREDENTIALS = users_repo.EVENT_CREDENTIALS
EVENT_EMAIL_VERIFIED = users_repo.EVENT_EMAIL_VERIFIED
EVENT_PASSWORD_CHANGED = users_repo.EVENT_PASSWORD_CHANGED
EVENT_INVITED = users_repo.EVENT_INVITED
EVENT_ACTIVATED = users_repo.EVENT_ACTIVATED
EVENT_PASSWORD_RESET = users_repo.EVENT_PASSWORD_RESET
EVENT_UNENROLLED = users_repo.EVENT_UNENROLLED
EVENT_ENROLLED = users_repo.EVENT_ENROLLED
EVENT_DISABLED = users_repo.EVENT_DISABLED
EVENT_FORCE_UNENROLLED = users_repo.EVENT_FORCE_UNENROLLED
EVENT_PURGED = users_repo.EVENT_PURGED
EVENT_EDITED = users_repo.EVENT_EDITED
EVENT_CREATED = users_repo.EVENT_CREATED


def is_disabled(user: dict | None) -> bool:
    """¿Esta cuenta la sacó de servicio el webmaster? Cerrado por defecto: una
    cuenta que no existe tampoco está activa."""
    return user is None or user.get("status") == STATUS_DISABLED


def is_unenrolled(user: dict | None) -> bool:
    """¿Esta cuenta pidió la baja el propio usuario? (V3.81)

    Es un estado distinto de `disabled` a propósito: la baja autoservicio es un
    derecho del alumno y la desactivación es una decisión del webmaster. La
    consecuencia práctica es la misma —no entra— pero el lanzador tiene que poder
    decir por qué y ofrecer lo que toca en cada caso.
    """
    return user is not None and user.get("status") == STATUS_UNENROLLED


def can_start_session(user: dict | None) -> bool:
    """¿Puede esta cuenta abrir sesión? Solo `active`, y tiene que existir."""
    return user is not None and user.get("status") == STATUS_ACTIVE


def is_password_change_due(user: dict | None) -> bool:
    """¿La contraseña de esta cuenta es temporal y hay que cambiarla? (V3.81)

    La pone el webmaster al asignar credenciales (`must_change_password`): sirve
    para que exista un momento en que la contraseña definitiva la elija el alumno
    y no la sepa nadie más. Se comprueba **en el servidor** y no solo en la UI
    porque una regla que solo vive en el cliente no es una regla.
    """
    return user is not None and bool(user.get("must_change_password"))


async def create_user(
    name: str,
    is_test: bool = False,
    *,
    email: str = "",
    password_hash: str = "",
    must_change_password: bool = False,
    avatar_color: str = "",
    avatar_emoji: str = "",
    avatar_image: str = "",
) -> dict:
    return await run_in_threadpool(
        users_repo.create_user,
        name,
        is_test,
        email=email,
        password_hash=password_hash,
        must_change_password=must_change_password,
        avatar_color=avatar_color,
        avatar_emoji=avatar_emoji,
        avatar_image=avatar_image,
    )


async def list_users(
    include_test: bool = False, include_disabled: bool = False
) -> list[dict]:
    """Cuentas locales. V3.77/V3.81: `include_disabled` devuelve también las
    desactivadas y las dadas de baja, que es lo que necesita la consola de
    gestión para poder reactivarlas."""
    return await run_in_threadpool(
        users_repo.list_users,
        include_test=include_test,
        include_disabled=include_disabled,
    )


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(users_repo.get_user, uid)


async def name_in_use(name: str, *, exclude_uid: str | None = None) -> bool:
    """¿Otro usuario activo ya usa ese nombre? (V3.80.2)

    Se consulta en el borde HTTP y no en el alta del repositorio: medio centenar
    de tests crean perfiles con el mismo nombre de forma deliberada (para probar
    el aislamiento entre usuarios) y esa puerta no tiene que cambiar por una
    regla de presentación.
    """
    return await run_in_threadpool(
        users_repo.name_in_use, name, exclude_uid=exclude_uid
    )


async def email_in_use(email: str, *, exclude_uid: str | None = None) -> bool:
    """¿Otra cuenta ya usa ese email? (V3.81)"""
    return await run_in_threadpool(
        users_repo.email_in_use, email, exclude_uid=exclude_uid
    )


async def find_by_email(email: str) -> dict | None:
    return await run_in_threadpool(users_repo.find_by_email, email)


async def find_by_email_token(token_hash: str) -> dict | None:
    return await run_in_threadpool(users_repo.find_by_email_token, token_hash)


# V3.81: el hash de la contraseña no forma parte del perfil que la API sirve
# (`has_password` sí), así que tiene su propio par de operaciones, y **fuera** del
# diccionario del perfil: así es imposible serializarlo por descuido. Es la misma
# separación que V3.76 hacía con el PIN.
async def get_password_hash(uid: str) -> str | None:
    return await run_in_threadpool(users_repo.get_password_hash, uid)


async def get_auth_epoch(uid: str) -> int | None:
    return await run_in_threadpool(users_repo.get_auth_epoch, uid)


async def set_password_hash(
    uid: str, password_hash: str, *, must_change: bool = False
) -> bool:
    return await run_in_threadpool(
        users_repo.set_password_hash, uid, password_hash, must_change=must_change
    )


async def set_credentials(
    uid: str, *, email: str, password_hash: str, must_change: bool = True
) -> dict | None:
    return await run_in_threadpool(
        users_repo.set_credentials,
        uid,
        email=email,
        password_hash=password_hash,
        must_change=must_change,
    )


async def set_email(uid: str, email: str, *, verified: bool = False) -> dict | None:
    return await run_in_threadpool(
        users_repo.set_email, uid, email, verified=verified
    )


async def set_email_verification(uid: str, token_hash: str) -> bool:
    return await run_in_threadpool(users_repo.set_email_verification, uid, token_hash)


async def get_email_verification(uid: str) -> tuple[str, str] | None:
    return await run_in_threadpool(users_repo.get_email_verification, uid)


async def mark_email_verified(uid: str) -> dict | None:
    return await run_in_threadpool(users_repo.mark_email_verified, uid)


# --- Activación (invitación, V3.82) ------------------------------------------


async def set_activation(uid: str, token_hash: str) -> bool:
    return await run_in_threadpool(users_repo.set_activation, uid, token_hash)


async def get_activation(uid: str) -> tuple[str, str] | None:
    return await run_in_threadpool(users_repo.get_activation, uid)


async def find_by_activation_token(token_hash: str) -> dict | None:
    return await run_in_threadpool(
        users_repo.find_by_activation_token, token_hash
    )


async def mark_activated(uid: str, *, email_verified: bool = True) -> dict | None:
    return await run_in_threadpool(
        users_repo.mark_activated, uid, email_verified=email_verified
    )


# --- Restablecimiento de contraseña (V3.82) ----------------------------------


async def set_password_reset(uid: str, token_hash: str) -> bool:
    return await run_in_threadpool(users_repo.set_password_reset, uid, token_hash)


async def get_password_reset(uid: str) -> tuple[str, str] | None:
    return await run_in_threadpool(users_repo.get_password_reset, uid)


async def find_by_password_reset_token(token_hash: str) -> dict | None:
    return await run_in_threadpool(
        users_repo.find_by_password_reset_token, token_hash
    )


async def clear_password_reset(uid: str) -> bool:
    return await run_in_threadpool(users_repo.clear_password_reset, uid)


async def set_unenrolled(uid: str, *, enrolled: bool) -> dict | None:
    return await run_in_threadpool(users_repo.set_unenrolled, uid, enrolled=enrolled)


async def update_user(uid: str, fields: dict) -> dict | None:
    return await run_in_threadpool(users_repo.update_user, uid, **fields)


async def delete_test_user(uid: str) -> bool:
    return await run_in_threadpool(users_repo.delete_test_user, uid)


async def record_event(
    *,
    subject_id: str,
    subject_name: str,
    action: str,
    note: str = "",
    actor: str = "webmaster",
) -> None:
    """Anota una decisión (nunca lanza: ver el repositorio).

    `actor` distingue lo que decidió el webmaster de lo que hizo el propio alumno
    («alumno»). En un historial que se lee para reconstruir quién hizo qué, esa
    columna es la mitad del dato: «se dio de baja» y «se le dio de baja» son la
    misma fila y dos historias distintas.
    """
    await run_in_threadpool(
        users_repo.record_event,
        subject_id=subject_id,
        subject_name=subject_name,
        action=action,
        note=note,
        actor=actor,
    )


async def list_events(uid: str, limit: int = 50) -> list[dict]:
    return await run_in_threadpool(users_repo.list_events, uid, limit)

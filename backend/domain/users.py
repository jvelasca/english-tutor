"""Servicio de dominio de usuarios."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import users as users_repo

# La lista canónica de estados vive en el repositorio, que es quien la valida al
# escribir; el dominio la reexpone para que las capas de arriba no tengan que
# importar el repositorio solo por dos cadenas.
STATUS_ACTIVE = users_repo.STATUS_ACTIVE
STATUS_DISABLED = users_repo.STATUS_DISABLED


def is_disabled(user: dict | None) -> bool:
    """¿Este perfil está fuera de servicio? Cerrado por defecto: un perfil que no
    existe tampoco está activo."""
    return user is None or user.get("status") == STATUS_DISABLED


async def create_user(name: str, is_test: bool = False) -> dict:
    return await run_in_threadpool(users_repo.create_user, name, is_test)


async def list_users(
    include_test: bool = False, include_disabled: bool = False
) -> list[dict]:
    """Perfiles locales. V3.77: `include_disabled` los devuelve también a los
    desactivados, que es lo que necesita el lanzador para poder reactivarlos."""
    return await run_in_threadpool(
        users_repo.list_users,
        include_test=include_test,
        include_disabled=include_disabled,
    )


async def get_user(uid: str) -> dict | None:
    return await run_in_threadpool(users_repo.get_user, uid)


# V3.76 (Fase 3 del P0): el PIN no forma parte del perfil que la API sirve
# (`has_pin` sí), así que tiene su propio par de operaciones, y **fuera** del
# diccionario del perfil: así es imposible serializarlo por descuido.
async def get_pin_hash(uid: str) -> str | None:
    return await run_in_threadpool(users_repo.get_pin_hash, uid)


async def set_pin_hash(uid: str, pin_hash: str) -> bool:
    return await run_in_threadpool(users_repo.set_pin_hash, uid, pin_hash)


async def update_user(uid: str, fields: dict) -> dict | None:
    return await run_in_threadpool(users_repo.update_user, uid, **fields)


async def delete_test_user(uid: str) -> bool:
    return await run_in_threadpool(users_repo.delete_test_user, uid)

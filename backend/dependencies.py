"""Dependencias HTTP compartidas (contexto de usuario local)."""
from __future__ import annotations

from fastapi import Header, HTTPException, Request, UploadFile

import config
from domain import users as user_service
from services import sessions


async def require_admin(
    x_admin_pin: str | None = Header(default=None),
) -> None:
    """Candado local de administración (V1.37; fail-closed desde ADMIN-01 V3.19).

    Secure-by-default: si `config.ADMIN_PIN` está vacío, los endpoints admin quedan
    DESHABILITADOS (401) porque no hay secreto configurado con el que autenticarse.
    Con `ADMIN_PIN` definido, exige la cabecera `X-Admin-Pin` coincidente. Sin
    OAuth/cloud: separa `student` (aprender) de `admin` (gestionar
    audio/curriculum/diagnostics). Nunca abre la gestión por defecto (fail-open).
    """
    if not config.ADMIN_PIN:
        raise HTTPException(
            status_code=401,
            detail="Administración deshabilitada (configurar ADMIN_PIN)",
        )
    if x_admin_pin != config.ADMIN_PIN:
        raise HTTPException(status_code=401, detail="PIN de administración requerido")


async def current_user(request: Request) -> dict:
    """Resuelve el perfil activo desde la **sesión firmada** (V3.75, Fase 2 del P0).

    Es el **único** sitio donde la API decide quién eres: los 138 usos de esta
    dependencia en los 20 routers no cambian. 401 `SESSION_REQUIRED` si no hay
    cookie o la firma no cuadra; 404 si el perfil de una sesión válida ya no
    existe (mismo contrato que antes).

    El `?user_id=` que aceptaba hasta V3.74 **ya no se lee**: era la
    vulnerabilidad —cualquiera que alcanzara la API podía pedir los datos de otro
    perfil con solo cambiar un parámetro—, y dejarlo como respaldo habría sido
    cambiar la forma del arreglo sin arreglarlo (`PLAN-P0-IDENTIDAD.md` §4).
    """
    user_id = sessions.verify(request.cookies.get(sessions.SESSION_COOKIE))
    if user_id is None:
        raise HTTPException(status_code=401, detail="SESSION_REQUIRED")
    user = await user_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


async def current_user_optional(request: Request) -> dict | None:
    """Igual que `current_user`, pero **sin** sesión resuelve `None` en vez de 401:
    para los endpoints que saben funcionar sin perfil (su semántica no cambia)."""
    if sessions.verify(request.cookies.get(sessions.SESSION_COOKIE)) is None:
        return None
    return await current_user(request)


_ALLOWED_AUDIO_TYPES = {
    "application/octet-stream",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-wav",
}


def _content_type_ok(content_type: str | None) -> bool:
    if not content_type:
        return True
    base = content_type.split(";")[0].strip().lower()
    return base.startswith("audio/") or base in _ALLOWED_AUDIO_TYPES


async def read_audio_limited(file: UploadFile) -> bytes:
    """Lee un audio con límite de tamaño y tipo. 415 si el tipo no es audio, 413 si
    excede."""
    if not _content_type_ok(file.content_type):
        raise HTTPException(status_code=415, detail="Formato de audio no soportado")
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > config.MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio demasiado grande")
    return bytes(data)

"""Dependencias HTTP compartidas (contexto de usuario local)."""
from __future__ import annotations

from fastapi import HTTPException, Query, UploadFile

import config
from services import store_async


async def current_user(user_id: str = Query(...)) -> dict:
    """Resuelve y valida el perfil activo. 404 si no existe."""
    user = await store_async.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


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

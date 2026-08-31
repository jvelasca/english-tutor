"""Endpoints de sistema: backup / restore / export del estado local (V1.41).

Protegidos por el candado local de administración (`require_admin`, PIN local),
igual que la gestión de la biblioteca de audio. Sin OAuth/cloud: separan el rol
`admin` (copias de seguridad y restauración) del `student`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

import config
from dependencies import require_admin
from services import backup

router = APIRouter()

_BACKUP_MIME = "application/zip"


@router.get("/api/system/backup/status")
async def backup_status(_: None = Depends(require_admin)) -> dict:
    """Estado del subsistema de backup: si exige PIN y cuántos se conservan."""
    return {
        "admin_required": bool(config.ADMIN_PIN),
        "keep_backups": backup.KEEP_BACKUPS,
        "backup_count": len(backup.list_backups()),
    }


@router.post("/api/system/backup")
async def create_backup(_: None = Depends(require_admin)) -> dict:
    """Crea un backup completo del estado local (SQLite + audio) y poda a 7."""
    return await run_in_threadpool(backup.create_backup)


@router.get("/api/system/backups")
async def list_backups(_: None = Depends(require_admin)) -> dict:
    return {"backups": await run_in_threadpool(backup.list_backups)}


@router.get("/api/system/backup/export")
async def export_backup(
    name: str | None = None, _: None = Depends(require_admin)
) -> Response:
    """Descarga un backup ZIP (el más reciente si no se indica nombre)."""
    try:
        if name is None:
            latest = backup.latest_backup()
            if latest is None:
                raise HTTPException(status_code=404, detail="No hay backups")
            name = latest["name"]
        data = await run_in_threadpool(backup.read_backup, name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Backup no encontrado") from None
    return Response(
        content=data,
        media_type=_BACKUP_MIME,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/api/system/restore")
async def restore_backup(
    file: UploadFile, _: None = Depends(require_admin)
) -> dict:
    """Restaura el estado desde un backup ZIP subido."""
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in {_BACKUP_MIME, "application/octet-stream"} and mime:
        raise HTTPException(status_code=415, detail="El backup debe ser un ZIP")

    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > 512 * 1024 * 1024:  # 512 MB, holgado para audio local
            raise HTTPException(status_code=413, detail="Backup demasiado grande")

    try:
        return await run_in_threadpool(backup.restore_backup, bytes(data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

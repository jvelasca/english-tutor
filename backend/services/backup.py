"""Backup / restore / export del estado local (V1.41).

Cubre todo lo que el alumno puede generar o subir y que no vive en el código:
- Base de datos SQLite (`tutor.db`) — perfiles, conversaciones, progreso,
  vocabulario, errores, evidencia, settings, mastery, etc.
- Biblioteca de audio humano (`audio_library/`) — manifest + WAV reales.

El backup es un ZIP determinista con un `backup.json` de metadatos (versión de la
app y timestamp). El auto-backup diario conserva los últimos `KEEP_BACKUPS` (7).
Restaurar reemplaza el estado actual por el del ZIP (con checkpoint previo de
SQLite para no perder el WAL). Todo stdlib, sin dependencias y sin red.
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR, VERSION
from repositories.db import DB_PATH
from services.audio_library import AUDIO_LIBRARY_DIR

KEEP_BACKUPS = 7
_BACKUP_MANIFEST_NAME = "backup.json"
_DB_ARCNAME = "data/tutor.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backups_dir() -> Path:
    return DATA_DIR / "backups"


def _checkpoint_sqlite() -> None:
    """Fuerza un checkpoint de WAL para que `tutor.db` sea autónomo en el backup."""
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
    except sqlite3.Error:
        # La base aún no existe o no se puede abrir; no es fatal para el backup.
        return


def _write_zip(dest: Path) -> None:
    """Escribe el backup como ZIP (data/ + audio_library/ + backup.json)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        # Carpeta data/ completa, excluyendo la subcarpeta de backups (evita
        # copias recursivas y bloat).
        for p in sorted(DATA_DIR.iterdir()):
            if p.name == "backups":
                continue
            if p.is_file():
                zf.write(p, arcname=f"data/{p.name}")
            elif p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        zf.write(f, arcname=f"data/{p.name}/{f.relative_to(p)}")
        # Biblioteca de audio, excluyendo _backups (grabaciones borradas).
        for p in sorted(AUDIO_LIBRARY_DIR.rglob("*")):
            if p.is_file() and "_backups" not in p.parts:
                zf.write(p, arcname=f"audio_library/{p.relative_to(AUDIO_LIBRARY_DIR)}")
        zf.writestr(
            _BACKUP_MANIFEST_NAME,
            json.dumps(
                {"app": "english-tutor", "version": VERSION, "created_at": _now()},
                ensure_ascii=False,
                indent=2,
            ),
        )


def create_backup() -> dict:
    """Crea un backup ZIP, poda a `KEEP_BACKUPS` y devuelve su descriptor."""
    _checkpoint_sqlite()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = f"backup_{stamp}.zip"
    dest = backups_dir() / name
    _write_zip(dest)
    prune_backups(KEEP_BACKUPS)
    return {
        "name": name,
        "created_at": _now(),
        "size_bytes": dest.stat().st_size,
    }


def list_backups() -> list[dict]:
    """Lista los backups existentes, del más reciente al más antiguo."""
    if not backups_dir().exists():
        return []
    entries: list[dict] = []
    for p in backups_dir().glob("backup_*.zip"):
        entries.append(
            {
                "name": p.name,
                "size_bytes": p.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    p.stat().st_mtime, timezone.utc
                ).isoformat(),
            }
        )
    return sorted(entries, key=lambda e: e["name"], reverse=True)


def prune_backups(keep: int = KEEP_BACKUPS) -> list[str]:
    """Borra los backups más antiguos dejando como máximo `keep`. Devuelve los
    nombres borrados."""
    entries = list_backups()
    removed: list[str] = []
    for entry in entries[keep:]:
        (backups_dir() / entry["name"]).unlink(missing_ok=True)
        removed.append(entry["name"])
    return removed


def read_backup(name: str) -> bytes:
    """Lee los bytes de un backup por nombre. `FileNotFoundError` si no existe.

    `name` debe ser un nombre de archivo plano (sin separadores de ruta) y acabar
    en `.zip`; así el acceso queda confinado a `backups_dir()` (anti path
    traversal). `FileNotFoundError` en cualquier otro caso.
    """
    if not name.endswith(".zip") or Path(name).name != name:
        raise FileNotFoundError(name)
    base = backups_dir().resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise FileNotFoundError(name)
    return path.read_bytes()


def latest_backup() -> dict | None:
    entries = list_backups()
    return entries[0] if entries else None


def auto_backup_if_due(now: datetime | None = None) -> dict | None:
    """Crea un backup si no existe ninguno del día UTC actual (auto-backup diario).

    Devuelve el descriptor del backup creado, o None si ya había uno hoy.
    """
    today = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    for entry in list_backups():
        if entry["name"].startswith(f"backup_{today}"):
            return None
    return create_backup()


def _copy_path(src: Path, dest: Path) -> None:
    """Copia recursivamente un archivo o carpeta de `src` a `dest` (sobrescribe)."""
    if src.is_dir():
        for child in src.rglob("*"):
            if child.is_file():
                rel = child.relative_to(src)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _replace_tree(src: Path, dest: Path, keep_top: set[str]) -> None:
    """Reemplaza el contenido de `dest` con el de `src` (semántica de restore).

    Borra de `dest` los archivos que ya no están en `src` y copia `src` encima.
    Los hijos directos de `dest` listados en `keep_top` se conservan (p. ej.
    `backups/` o `_backups/`), para no destruir copias de seguridad ni la
    recuperación de grabaciones borradas.
    """
    src_files = {str(p.relative_to(src)) for p in src.rglob("*") if p.is_file()}

    if dest.exists():
        for p in sorted(dest.rglob("*"), reverse=True):
            if p.is_file():
                rel = p.relative_to(dest)
                if rel.parts and rel.parts[0] in keep_top:
                    continue
                if str(rel) not in src_files:
                    p.unlink()
        for p in sorted(dest.rglob("*"), reverse=True):
            if p.is_dir() and not any(p.iterdir()):
                try:
                    p.rmdir()
                except OSError:
                    pass

    for child in src.iterdir():
        if child.name in keep_top:
            continue
        _copy_path(child, dest / child.name)


def restore_backup(zip_bytes: bytes) -> dict:
    """Restaura el estado desde un backup ZIP.

    Reemplaza `tutor.db` (con checkpoint y limpieza de WAL/SHM), la carpeta `data/`
    (conservando `backups/` y la propia DB) y la biblioteca de audio (conservando
    `_backups/`). Los archivos que no están en el backup se eliminan, de modo que
    la restauración reproduce el estado guardado y no solo lo superpone. Devuelve
    un resumen. Lanza `ValueError` si el ZIP no es un backup válido.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no es un backup ZIP válido") from exc

    with zf:
        names = set(zf.namelist())
        if _DB_ARCNAME not in names:
            raise ValueError("El backup no contiene la base de datos")
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            root = Path(tmp)

            db_src = root / _DB_ARCNAME
            _checkpoint_sqlite()
            for suffix in ("-wal", "-shm"):
                (DB_PATH.parent / f"{DB_PATH.name}{suffix}").unlink(missing_ok=True)
            shutil.copy2(db_src, DB_PATH)

            data_src = root / "data"
            if data_src.exists():
                _replace_tree(data_src, DATA_DIR, keep_top={"backups", DB_PATH.name})

            audio_src = root / "audio_library"
            if audio_src.exists():
                _replace_tree(audio_src, AUDIO_LIBRARY_DIR, keep_top={"_backups"})

    return {"restored": True, "version": VERSION, "created_at": _now()}

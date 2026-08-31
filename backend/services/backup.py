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
    """Lee los bytes de un backup por nombre. `FileNotFoundError` si no existe."""
    path = backups_dir() / name
    if not path.exists() or not name.endswith(".zip"):
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


def restore_backup(zip_bytes: bytes) -> dict:
    """Restaura el estado desde un backup ZIP.

    Reemplaza `tutor.db` (con checkpoint y limpieza de WAL/SHM) y la biblioteca de
    audio. Devuelve un resumen. Lanza `ValueError` si el ZIP no es un backup válido.
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
                for child in data_src.iterdir():
                    if child.name == "tutor.db":
                        continue
                    _copy_path(child, DATA_DIR / child.name)

            audio_src = root / "audio_library"
            if audio_src.exists():
                for child in audio_src.rglob("*"):
                    if child.is_file():
                        rel = child.relative_to(audio_src)
                        target = AUDIO_LIBRARY_DIR / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(child, target)

    return {"restored": True, "version": VERSION, "created_at": _now()}

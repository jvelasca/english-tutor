"""Tests de Backup/Restore/Export (V1.41)."""

import io
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from services import backup as backup_svc


def _setup(monkeypatch, tmp_path):
    data = tmp_path / "data"
    audio = tmp_path / "audio"
    data.mkdir(parents=True)
    audio.mkdir(parents=True)
    monkeypatch.setattr(backup_svc, "DATA_DIR", data)
    monkeypatch.setattr(backup_svc, "DB_PATH", data / "tutor.db")
    monkeypatch.setattr(backup_svc, "AUDIO_LIBRARY_DIR", audio)
    # Base de datos y WAV de ejemplo.
    (data / "tutor.db").write_bytes(b"SQLITE-DATA")
    (audio / "manifest.json").write_text('{"version": "1.2.0", "entries": []}')
    (audio / "a1" / "speaker1" / "audio-l1.wav").parent.mkdir(parents=True)
    (audio / "a1" / "speaker1" / "audio-l1.wav").write_bytes(b"RIFF-WAV")
    return data, audio


def test_create_and_list_backup(monkeypatch, tmp_path):
    data, _audio = _setup(monkeypatch, tmp_path)
    created = backup_svc.create_backup()
    assert created["name"].startswith("backup_")
    assert created["name"].endswith(".zip")
    assert created["size_bytes"] > 0

    backups = backup_svc.list_backups()
    assert len(backups) == 1
    assert backups[0]["name"] == created["name"]

    path = backup_svc.backups_dir() / created["name"]
    assert path.exists()
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
    assert "data/tutor.db" in names
    assert "audio_library/manifest.json" in names
    assert "audio_library/a1/speaker1/audio-l1.wav" in names
    assert "backup.json" in names


def test_restore_backup_roundtrip(monkeypatch, tmp_path):
    data, audio = _setup(monkeypatch, tmp_path)
    backup_svc.create_backup()
    archive = backup_svc.read_backup(backup_svc.list_backups()[0]["name"])

    # Corrompemos el estado actual.
    (data / "tutor.db").write_bytes(b"CORRUPTED")
    (audio / "a1" / "speaker1" / "audio-l1.wav").unlink()

    result = backup_svc.restore_backup(archive)
    assert result["restored"] is True
    assert (data / "tutor.db").read_bytes() == b"SQLITE-DATA"
    assert (audio / "a1" / "speaker1" / "audio-l1.wav").read_bytes() == b"RIFF-WAV"


def test_restore_rejects_non_backup(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        backup_svc.restore_backup(b"not-a-zip")


def test_restore_rejects_zip_without_db(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hola")
    with pytest.raises(ValueError):
        backup_svc.restore_backup(buf.getvalue())


def test_prune_backups_keeps_seven(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    for _ in range(9):
        backup_svc.create_backup()
    backups = backup_svc.list_backups()
    assert len(backups) == backup_svc.KEEP_BACKUPS == 7


def test_auto_backup_if_due(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc)
    first = backup_svc.auto_backup_if_due(now=today)
    assert first is not None
    # El mismo día no crea otro.
    assert backup_svc.auto_backup_if_due(now=today) is None
    # Un día distinto sí.
    tomorrow = today.replace(day=(today.day % 28) + 1)
    assert backup_svc.auto_backup_if_due(now=tomorrow) is not None


def test_read_backup_missing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError):
        backup_svc.read_backup("backup_unknown.zip")


def test_read_backup_rejects_path_traversal(monkeypatch, tmp_path):
    """El nombre debe ser un basename .zip confinado a backups_dir (anti CWE-22)."""
    _setup(monkeypatch, tmp_path)
    backup_svc.create_backup()
    for evil in (
        "../../etc/passwd.zip",
        "..\\..\\Windows\\win.ini.zip",
        "/etc/shadow.zip",
        "sub/backup.zip",
        "tutor.db",
        "",
    ):
        with pytest.raises(FileNotFoundError):
            backup_svc.read_backup(evil)


def test_export_rejects_path_traversal(monkeypatch, tmp_path):
    """El endpoint de export no lee archivos fuera de backups_dir."""
    data, _audio = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(db, "DATA_DIR", data)
    monkeypatch.setattr(db, "DB_PATH", data / "app.db")
    db.init_db()

    with TestClient(app) as client:
        resp = client.get(
            "/api/system/backup/export",
            params={"name": "../../etc/passwd.zip"},
        )
        assert resp.status_code == 404


def test_restore_removes_stale_files(monkeypatch, tmp_path):
    """Restaurar reemplaza el estado: borra lo que no estaba en el backup."""
    data, audio = _setup(monkeypatch, tmp_path)
    backup_svc.create_backup()
    archive = backup_svc.read_backup(backup_svc.list_backups()[0]["name"])

    (audio / "stale.wav").write_bytes(b"STALE")
    (data / "stale.txt").write_bytes(b"STALE")

    result = backup_svc.restore_backup(archive)
    assert result["restored"] is True

    assert not (audio / "stale.wav").exists()
    assert not (data / "stale.txt").exists()
    # Lo que sí estaba en el backup se conserva.
    assert (audio / "manifest.json").exists()
    assert (data / "tutor.db").read_bytes() == b"SQLITE-DATA"


def test_backup_endpoints(monkeypatch, tmp_path):
    """Flujo completo por API: crear → listar → exportar → restaurar."""
    data, _audio = _setup(monkeypatch, tmp_path)
    # Aísla también la base real de la app para que `init_db` no toque el disco real.
    monkeypatch.setattr(db, "DATA_DIR", data)
    monkeypatch.setattr(db, "DB_PATH", data / "app.db")
    db.init_db()

    with TestClient(app) as client:
        created = client.post("/api/system/backup")
        assert created.status_code == 200, created.text
        name = created.json()["name"]
        assert name.startswith("backup_")

        listed = client.get("/api/system/backups")
        assert listed.status_code == 200
        assert listed.json()["backups"][0]["name"] == name

        exported = client.get("/api/system/backup/export")
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/zip"

        # Restaurar el propio export (idempotente) con un multipart UploadFile.
        restored = client.post(
            "/api/system/restore",
            files={
                "file": (
                    name,
                    exported.content,
                    "application/zip",
                )
            },
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["restored"] is True

        status = client.get("/api/system/backup/status")
        assert status.status_code == 200
        assert status.json()["keep_backups"] == 7

"""Tests de Backup/Restore/Export (V1.41)."""

import io
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from services import backup as backup_svc

# Fail-closed (ADMIN-01 V3.19): los endpoints de backup exigen PIN local.
_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}


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
    monkeypatch.setattr(config, "ADMIN_PIN", _ADMIN_PIN)
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
            headers=_ADMIN_HEADERS,
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
        created = client.post("/api/system/backup", headers=_ADMIN_HEADERS)
        assert created.status_code == 200, created.text
        name = created.json()["name"]
        assert name.startswith("backup_")

        listed = client.get("/api/system/backups", headers=_ADMIN_HEADERS)
        assert listed.status_code == 200
        assert listed.json()["backups"][0]["name"] == name

        exported = client.get(
            "/api/system/backup/export", headers=_ADMIN_HEADERS
        )
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/zip"

        # Restaurar el propio export (idempotente) con un multipart UploadFile.
        restored = client.post(
            "/api/system/restore",
            headers=_ADMIN_HEADERS,
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

        status = client.get("/api/system/backup/status", headers=_ADMIN_HEADERS)
        assert status.status_code == 200
        assert status.json()["keep_backups"] == 7


# --- Endurecimiento de backup/restore (V3.73.x) ------------------------------


def _archive(*entries: tuple[str, bytes]) -> bytes:
    """ZIP en memoria con las entradas dadas (para probar los rechazos)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


def test_backup_excludes_tls_private_key(monkeypatch, tmp_path):
    """La clave privada TLS no viaja en el ZIP: el backup no se cifra."""
    data, _audio = _setup(monkeypatch, tmp_path)
    certs = data / "certs"
    certs.mkdir()
    (certs / "cert.pem").write_text("CERT")
    (certs / "key.pem").write_text("PRIVATE-KEY")

    backup_svc.create_backup()
    path = backup_svc.backups_dir() / backup_svc.list_backups()[0]["name"]
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())

    assert not any(name.startswith("data/certs/") for name in names), (
        "el backup sigue incluyendo el certificado TLS y su clave privada"
    )
    assert "data/tutor.db" in names  # el resto del estado sí viaja


def test_backup_excludes_session_secret(monkeypatch, tmp_path):
    """El secreto de firma de sesiones no viaja en el ZIP (V3.75).

    Es la misma familia de secreto que `key.pem`: un backup sin cifrar con esta
    clave dentro permite **forjar sesiones** para cualquier perfil.
    """
    data, _audio = _setup(monkeypatch, tmp_path)
    (data / "session.secret").write_text("SECRETO-DE-FIRMA")

    backup_svc.create_backup()
    path = backup_svc.backups_dir() / backup_svc.list_backups()[0]["name"]
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())

    assert "data/session.secret" not in names, (
        "el backup incluye la clave con la que se firman las sesiones"
    )
    assert "data/tutor.db" in names  # el resto del estado sí viaja


def test_restore_preserves_local_session_secret(monkeypatch, tmp_path):
    """Restaurar no borra el secreto: las sesiones abiertas siguen valiendo."""
    data, _audio = _setup(monkeypatch, tmp_path)
    (data / "session.secret").write_text("SECRETO-DE-FIRMA")
    backup_svc.create_backup()
    archive = backup_svc.read_backup(backup_svc.list_backups()[0]["name"])

    backup_svc.restore_backup(archive)

    assert (data / "session.secret").read_text() == "SECRETO-DE-FIRMA", (
        "restaurar borró el secreto de sesión: invalidaría todas las sesiones abiertas"
    )


def test_restore_preserves_local_certs(monkeypatch, tmp_path):
    """Restaurar no borra el certificado del equipo (no está en el backup)."""
    data, _audio = _setup(monkeypatch, tmp_path)
    certs = data / "certs"
    certs.mkdir()
    (certs / "key.pem").write_text("PRIVATE-KEY")
    backup_svc.create_backup()
    archive = backup_svc.read_backup(backup_svc.list_backups()[0]["name"])

    backup_svc.restore_backup(archive)

    assert (certs / "key.pem").read_text() == "PRIVATE-KEY", (
        "restaurar borró la clave TLS: el producto se quedaría sin HTTPS"
    )


def test_restore_rejects_oversized_expansion(monkeypatch, tmp_path):
    """Un ZIP pequeño que expande muy por encima de la cota se rechaza."""
    _setup(monkeypatch, tmp_path)
    archive = _archive(
        ("data/tutor.db", b"SQLITE-DATA"),
        ("data/relleno.bin", b"\0" * 100_000),
    )
    monkeypatch.setattr(backup_svc, "_MAX_UNCOMPRESSED_BYTES", 1_000)
    with pytest.raises(ValueError, match="expandido"):
        backup_svc.restore_backup(archive)


def test_restore_rejects_too_many_entries(monkeypatch, tmp_path):
    """Un ZIP con muchísimas entradas se rechaza antes de extraer."""
    _setup(monkeypatch, tmp_path)
    archive = _archive(
        ("data/tutor.db", b"SQLITE-DATA"),
        ("data/a.txt", b"a"),
        ("data/b.txt", b"b"),
    )
    monkeypatch.setattr(backup_svc, "_MAX_ENTRIES", 2)
    with pytest.raises(ValueError, match="entradas"):
        backup_svc.restore_backup(archive)


@pytest.mark.parametrize(
    "evil",
    [
        "../evil.txt",
        "data/../../evil.txt",
        "/etc/evil.txt",
        "C:/evil.txt",
    ],
)
def test_restore_rejects_unsafe_member_path(monkeypatch, tmp_path, evil):
    """Rutas que escapan del temporal se rechazan de forma explícita (CWE-22)."""
    _setup(monkeypatch, tmp_path)
    archive = _archive(("data/tutor.db", b"SQLITE-DATA"), (evil, b"x"))
    with pytest.raises(ValueError, match="insegura"):
        backup_svc.restore_backup(archive)

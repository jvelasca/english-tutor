"""Lectura de cookies del navegador (solo lectura, sin dependencias externas).

El launcher muestra, a modo de diagnóstico, qué cookies guarda el navegador
para la app (origins ``localhost`` / ``127.0.0.1`` / IPs de red privada). Se
detectan los perfiles de Chrome, Edge y Firefox y se leen sus bases de datos
SQLite en modo solo lectura.

Nota: Chrome/Edge cifran el valor de las cookies (``encrypted_value``), así que
aquí se muestra su tamaño en bytes y no el valor en claro; Firefox las guarda
en claro y sí se puede leer el valor. Como los navegadores mantienen sus bases
de cookies bloqueadas mientras están abiertos, se copian a un temporal antes de
leerlas. Esto se degrada con elegancia: si un navegador no existe o su base no
se puede leer, simplemente no aparece.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_COOKIE_NAME = "et_user_id"

# Épocas usadas por los navegadores (días/segundos desde una fecha base).
_WEBKIT_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _is_app_host(host: str) -> bool:
    """True si el host corresponde a la app (loopback o IP privada LAN)."""
    if not host:
        return False
    host = host.strip().lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        a, b = int(parts[0]), int(parts[1])
        return (
            a == 10
            or a == 127
            or (a == 172 and 16 <= b <= 31)
            or (a == 192 and b == 168)
        )
    return False


def _format_expiry_webkit(micros: int | None) -> str:
    """Fecha de caducidad a partir de microsegundos WebKit (0 = sesión)."""
    if not micros:
        return "sesión"
    try:
        dt = _WEBKIT_EPOCH + timedelta(microseconds=int(micros))
        return dt.strftime("%Y-%m-%d")
    except (OverflowError, ValueError):
        return ""


def _format_expiry_unix(seconds: int | None) -> str:
    """Fecha de caducidad a partir de segundos Unix (0 = sesión)."""
    if not seconds:
        return "sesión"
    try:
        dt = datetime.fromtimestamp(int(seconds), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (OverflowError, ValueError, OSError):
        return ""


def _connect_ro(path: str) -> sqlite3.Connection:
    """Abre una base SQLite en modo solo lectura e inmutable (no bloquea)."""
    uri_path = path.replace("\\", "/")
    return sqlite3.connect(f"file:{uri_path}?mode=ro&immutable=1", uri=True)


# --- Detección de perfiles de navegador ---


def _discover_chromium(browser: str, user_data: Path) -> list[dict]:
    if not user_data.is_dir():
        return []
    stores: list[dict] = []
    for child in sorted(user_data.iterdir()):
        if not child.is_dir():
            continue
        db = child / "Network" / "Cookies"
        if db.is_file():
            stores.append(
                {
                    "browser": browser,
                    "profile": child.name,
                    "kind": "chromium",
                    "db": str(db),
                }
            )
    return stores


def _discover_firefox(profiles: Path) -> list[dict]:
    if not profiles.is_dir():
        return []
    stores: list[dict] = []
    for child in sorted(profiles.iterdir()):
        if not child.is_dir():
            continue
        db = child / "cookies.sqlite"
        if db.is_file():
            stores.append(
                {
                    "browser": "Firefox",
                    "profile": child.name,
                    "kind": "firefox",
                    "db": str(db),
                }
            )
    return stores


# Raíces de datos de usuario de los navegadores Chromium soportados.
# (nombre, variable de entorno base, ruta relativa). Opera/Opera GX no usan la
# subcarpeta "User Data": sus perfiles viven directamente en la carpeta raíz.
_BROWSER_ROOTS: list[tuple[str, str, str]] = [
    ("Chrome", "LOCALAPPDATA", "Google/Chrome/User Data"),
    ("Edge", "LOCALAPPDATA", "Microsoft/Edge/User Data"),
    ("Brave", "LOCALAPPDATA", "BraveSoftware/Brave-Browser/User Data"),
    ("Vivaldi", "LOCALAPPDATA", "Vivaldi/User Data"),
    ("Opera", "APPDATA", "Opera Software/Opera Stable"),
    ("Opera GX", "APPDATA", "Opera Software/Opera GX Stable"),
]


def discover_stores() -> list[dict]:
    """Perfiles de navegador con su base de datos de cookies (Windows)."""
    stores: list[dict] = []
    for browser, env, rel in _BROWSER_ROOTS:
        base = os.environ.get(env)
        if not base:
            continue
        stores.extend(_discover_chromium(browser, Path(base) / rel))

    appdata = os.environ.get("APPDATA")
    if appdata:
        stores.extend(
            _discover_firefox(Path(appdata) / "Mozilla" / "Firefox" / "Profiles")
        )
    return stores


def diagnose_stores() -> list[dict]:
    """Estado de cada navegador soportado: si está instalado y qué perfiles tiene.

    Sirve para explicar por qué no se ven cookies (p. ej. navegador no instalado
    o sin base de cookies), en lugar de mostrar solo "0 cookies"."""
    diagnosis: list[dict] = []
    for browser, env, rel in _BROWSER_ROOTS:
        base = os.environ.get(env)
        root = Path(base) / rel if base else None
        item = {
            "browser": browser,
            "found": bool(root and root.is_dir()),
            "root": str(root) if root else "",
            "profiles": [],
        }
        if item["found"]:
            item["profiles"] = [
                s["profile"] for s in _discover_chromium(browser, root)
            ]
        diagnosis.append(item)

    appdata = os.environ.get("APPDATA")
    ff_root = Path(appdata) / "Mozilla" / "Firefox" / "Profiles" if appdata else None
    ff_item = {
        "browser": "Firefox",
        "found": bool(ff_root and ff_root.is_dir()),
        "root": str(ff_root) if ff_root else "",
        "profiles": [],
    }
    if ff_item["found"]:
        ff_item["profiles"] = [s["profile"] for s in _discover_firefox(ff_root)]
    diagnosis.append(ff_item)
    return diagnosis


# --- Lectura de una base de cookies ---


def _chromium_value(row: sqlite3.Row) -> str:
    """Valor de una cookie de Chromium (cifrada → tamaño en bytes)."""
    keys = row.keys()
    enc = row["encrypted_value"] if "encrypted_value" in keys else None
    if enc:
        return f"(cifrado · {len(enc)} bytes)"
    value = row["value"] if "value" in keys else None
    return value or ""


def _read_chromium(conn: sqlite3.Connection, store: dict) -> list[dict]:
    conn.row_factory = sqlite3.Row
    existing = {r[1] for r in conn.execute("PRAGMA table_info(cookies)")}
    cols = ["host_key", "name", "path", "expires_utc", "is_secure", "is_httponly"]
    cols += [c for c in ("encrypted_value", "value") if c in existing]
    query = "SELECT " + ", ".join(cols) + " FROM cookies"
    rows = conn.execute(query).fetchall()

    out: list[dict] = []
    for r in rows:
        host = r["host_key"] or ""
        if not _is_app_host(host):
            continue
        out.append(
            {
                "browser": store["browser"],
                "profile": store["profile"],
                "name": r["name"] or "",
                "host": host,
                "path": r["path"] or "",
                "expires": _format_expiry_webkit(r["expires_utc"]),
                "value": _chromium_value(r),
                "secure": bool(r["is_secure"]),
                "httponly": bool(r["is_httponly"]),
            }
        )
    return out


def _read_firefox(conn: sqlite3.Connection, store: dict) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, value, host, path, expiry, isSecure, isHttpOnly "
        "FROM moz_cookies"
    ).fetchall()

    out: list[dict] = []
    for r in rows:
        host = r["host"] or ""
        if not _is_app_host(host):
            continue
        out.append(
            {
                "browser": store["browser"],
                "profile": store["profile"],
                "name": r["name"] or "",
                "host": host,
                "path": r["path"] or "",
                "expires": _format_expiry_unix(r["expiry"]),
                "value": r["value"] or "",
                "secure": bool(r["isSecure"]),
                "httponly": bool(r["isHttpOnly"]),
            }
        )
    return out


def read_store(store: dict) -> list[dict]:
    """Lee las cookies de la app desde una base de datos de navegador.

    Los navegadores bloquean sus bases de cookies mientras están abiertos, así
    que primero se copia el archivo (y sus ``-wal``/``-shm`` en Firefox) a un
    directorio temporal y se lee la copia. Si el archivo no existe o no se puede
    leer, devuelve una lista vacía (se degrada con elegancia).
    """
    src = Path(store["db"])
    if not src.is_file():
        return []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / src.name
            shutil.copy2(src, dst)
            for suffix in ("-wal", "-shm"):
                side = Path(str(src) + suffix)
                if side.is_file():
                    shutil.copy2(side, Path(str(dst) + suffix))
            conn = _connect_ro(str(dst))
            try:
                if store["kind"] == "firefox":
                    return _read_firefox(conn, store)
                return _read_chromium(conn, store)
            finally:
                conn.close()
    except (sqlite3.Error, OSError):
        return []


# --- Agregación ---


def cookie_summary(rows: list[dict]) -> dict:
    """Resumen de las cookies leídas: total, por navegador y usuario recordado."""
    browsers: dict[str, int] = {}
    remembered: str | None = None
    for c in rows:
        browsers[c["browser"]] = browsers.get(c["browser"], 0) + 1
        if c["name"] == APP_COOKIE_NAME and not c["value"].startswith("(cifrado"):
            remembered = c["value"]
    return {"total": len(rows), "browsers": browsers, "remembered": remembered}


def collect_cookies() -> tuple[list[dict], dict]:
    """Detecta navegadores y lee todas las cookies de la app (rows, summary).

    El `summary` incluye la clave `diagnosis` con el estado de cada navegador
    (instalado/no y perfiles), para explicar un posible "0 cookies"."""
    rows: list[dict] = []
    for store in discover_stores():
        rows.extend(read_store(store))
    summary = cookie_summary(rows)
    summary["diagnosis"] = diagnose_stores()
    return rows, summary

"""Lectura de cookies del navegador (solo lectura, sin dependencias externas).

El launcher muestra, a modo de diagnóstico, qué cookies guarda el navegador
para la app (origins ``localhost`` / ``127.0.0.1`` / IPs de red privada). Se
detectan los perfiles de Chrome, Edge y Firefox y se leen sus bases de datos
SQLite en modo solo lectura.

Nota: Chrome/Edge cifran el valor de las cookies (``encrypted_value``), así que
aquí se muestra su tamaño en bytes y no el valor en claro; Firefox las guarda
en claro y sí se puede leer el valor. Esto se degrada con elegancia: si un
navegador no existe o su base de datos está bloqueada, simplemente no aparece.
"""
from __future__ import annotations

import os
import sqlite3
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


def discover_stores() -> list[dict]:
    """Perfiles de navegador con su base de datos de cookies (Windows)."""
    stores: list[dict] = []
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        for browser, root in (
            ("Chrome", Path(localappdata) / "Google" / "Chrome" / "User Data"),
            ("Edge", Path(localappdata) / "Microsoft" / "Edge" / "User Data"),
        ):
            stores.extend(_discover_chromium(browser, root))

    appdata = os.environ.get("APPDATA")
    if appdata:
        stores.extend(
            _discover_firefox(Path(appdata) / "Mozilla" / "Firefox" / "Profiles")
        )
    return stores


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
    """Lee las cookies de la app desde una base de datos de navegador."""
    try:
        conn = _connect_ro(store["db"])
    except (sqlite3.Error, OSError):
        return []
    try:
        if store["kind"] == "firefox":
            return _read_firefox(conn, store)
        return _read_chromium(conn, store)
    except sqlite3.Error:
        return []
    finally:
        conn.close()


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
    """Detecta navegadores y lee todas las cookies de la app (rows, summary)."""
    rows: list[dict] = []
    for store in discover_stores():
        rows.extend(read_store(store))
    return rows, cookie_summary(rows)

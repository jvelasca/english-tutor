"""Lectura de estado: HTTP (health) y SQLite (contadores/usuarios), solo lectura."""
from __future__ import annotations

import json
import sqlite3
import ssl
import urllib.request
from contextlib import closing
from datetime import datetime
from pathlib import Path

from core import backend_url, frontend_url


def _get_json(url: str, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def fetch_health() -> dict | None:
    """Devuelve el dict de /api/health/dependencies, o None si no hay backend."""
    return _get_json(backend_url() + "/api/health/dependencies")


def fetch_version() -> str:
    """Versión de la app desde /api/health ('' si el backend está caído)."""
    data = _get_json(backend_url() + "/api/health")
    if not data:
        return ""
    return str(data.get("version", ""))


def _frontend_ssl_context() -> ssl.SSLContext:
    """Contexto SSL que acepta el certificado autofirmado del frontend local."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_frontend() -> bool:
    """True si el frontend responde (GET / sobre HTTPS autofirmado)."""
    try:
        with urllib.request.urlopen(
            frontend_url(), timeout=1.5, context=_frontend_ssl_context()
        ) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _connect_readonly(path: str) -> sqlite3.Connection:
    uri_path = path.replace("\\", "/")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_db_counts(db_path: str) -> dict:
    """Contadores globales de la BD (0 si no se puede abrir)."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {
            "users": int(users),
            "conversations": int(conversations),
            "messages": int(messages),
        }
    except Exception:  # noqa: BLE001
        return {"users": 0, "conversations": 0, "messages": 0}


def read_db_details(db_path: str) -> dict[str, int]:
    """Contadores de tablas opcionales (0 si la tabla aún no existe).

    Estas tablas se crean al arrancar el backend; en una BD recién inicializada
    pueden no existir todavía, por lo que se comprueban contra ``sqlite_master``.
    """
    tables = {
        "vocabulary": "vocabulario",
        "grammar_errors": "errores_gramaticales",
        "learning_events": "eventos_aprendizaje",
        "pronunciation_attempts": "intentos_pronunciacion",
        "listening_attempts": "intentos_listening",
        "settings": "preferencias",
    }
    result: dict[str, int] = {}
    try:
        with closing(_connect_readonly(db_path)) as conn:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for table, key in tables.items():
                if table in existing:
                    result[key] = int(
                        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    )
                else:
                    result[key] = 0
    except Exception:  # noqa: BLE001
        return {key: 0 for key in tables.values()}
    return result


def _human_size(num: int) -> str:
    """Tamaño legible en bytes/KB/MB/GB/TB."""
    value = float(num)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def read_db_info(db_path: str) -> dict:
    """Metadatos del archivo de base de datos (tamaño, tablas, modificación).

    Devuelve ``exists``, ``size_bytes``, ``size_human``, ``modified`` y
    ``tables`` (tablas reales, sin las internas ``sqlite_*``). Se degrada con
    elegancia si el archivo no existe o no se puede leer.
    """
    info = {
        "exists": False,
        "size_bytes": 0,
        "size_human": "—",
        "modified": "—",
        "tables": 0,
    }
    path = Path(db_path)
    try:
        if not path.is_file():
            return info
        st = path.stat()
        info["exists"] = True
        info["size_bytes"] = int(st.st_size)
        info["size_human"] = _human_size(st.st_size)
        info["modified"] = datetime.fromtimestamp(st.st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )
    except OSError:
        return info
    try:
        with closing(_connect_readonly(db_path)) as conn:
            info["tables"] = int(
                conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone()[0]
            )
    except Exception:  # noqa: BLE001
        pass
    return info


def read_users(db_path: str) -> list[tuple]:
    """Lista de (id, name, conversations, messages) por usuario."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.name,
                       COUNT(DISTINCT c.id) AS conversations,
                       COUNT(m.id) AS messages
                FROM users u
                LEFT JOIN conversations c ON c.user_id = u.id
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY u.id
                ORDER BY u.name
                """
            ).fetchall()
        return [(r["id"], r["name"], r["conversations"], r["messages"]) for r in rows]
    except Exception:  # noqa: BLE001
        return []

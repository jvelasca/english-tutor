"""Núcleo puro del launcher de escritorio (sin GUI, sin red, sin procesos).

Funciones deterministas para resolver rutas, construir comandos de arranque y
normalizar el estado de la app, las dependencias y la base de datos. Testeable
sin lanzar nada.
"""
from __future__ import annotations

import os
import socket
from pathlib import Path

# El launcher vive en <repo>/launcher/, así que el repo raíz es el padre del padre.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DB_PATH = BACKEND_DIR / "data" / "tutor.db"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173


def backend_command() -> list[str]:
    """Comando para arrancar el backend con el venv del proyecto (uvicorn).

    Se enlaza a ``0.0.0.0`` para que otros equipos de la LAN puedan acceder.
    """
    exe = "python.exe" if os.name == "nt" else "python"
    python = BACKEND_DIR / ".venv" / "Scripts" / exe
    return [
        str(python),
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(BACKEND_PORT),
    ]


def frontend_command() -> list[str]:
    """Comando para arrancar el frontend (Vite dev)."""
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return [npm, "run", "dev"]


def backend_url() -> str:
    return f"http://127.0.0.1:{BACKEND_PORT}"


def frontend_url() -> str:
    return f"http://localhost:{FRONTEND_PORT}"


def lan_ip() -> str:
    """IP IPv4 de la LAN desde la que se sirve la app (o 127.0.0.1)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect es perezoso: no envía paquetes, solo elige la ruta.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def lan_url() -> str:
    """URL de acceso desde otros equipos de la red local."""
    return f"http://{lan_ip()}:{FRONTEND_PORT}"


def app_summary(backend_up: bool, frontend_up: bool) -> dict[str, str]:
    """Estado on/off de cada servicio."""
    return {
        "backend": "on" if backend_up else "off",
        "frontend": "on" if frontend_up else "off",
    }


def health_status(deps: dict | None) -> dict[str, str]:
    """Normaliza el dict de /api/health/dependencies a estados por dependencia."""
    unknown = {
        "database": "unknown",
        "ollama": "unknown",
        "stt": "unknown",
        "tts": "unknown",
    }
    if deps is None:
        return {"api": "off", **unknown}

    def _norm(value: str | None) -> str:
        if value in ("ok", "ready"):
            return "ok"
        if value == "error":
            return "error"
        return "unavailable"

    return {
        "api": "ok",
        "database": _norm(deps.get("database")),
        "ollama": _norm(deps.get("ollama")),
        "stt": _norm(deps.get("stt")),
        "tts": _norm(deps.get("tts")),
    }


def db_summary(counts: dict) -> dict[str, int]:
    """Normaliza los contadores de la BD (entero, 0 si falta)."""
    return {
        "users": int(counts.get("users", 0)),
        "conversations": int(counts.get("conversations", 0)),
        "messages": int(counts.get("messages", 0)),
    }


def user_overview(rows: list[tuple]) -> list[dict]:
    """Convierte filas (id, name, conversations, messages) a dicts legibles."""
    return [
        {
            "id": row[0],
            "name": row[1],
            "conversations": int(row[2]),
            "messages": int(row[3]),
        }
        for row in rows
    ]

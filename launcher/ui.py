"""Helpers de la GUI del launcher: iconos, paleta de estado y lectura de logs.

Funciones puras y deterministas (sin tkinter, sin red, sin procesos) para poder
testearlas sin abrir ventanas. La GUI (`launcher.py`) solo las consume.
"""
from __future__ import annotations

from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"

# Paleta de la GUI (tema claro, acento índigo como la web).
COLORS = {
    "bg": "#f8fafc",
    "surface": "#ffffff",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "text_dim": "#64748b",
    "accent": "#4f46e5",
    "accent_hover": "#4338ca",
    "on_accent": "#ffffff",
    "success": "#16a34a",
    "success_hover": "#15803d",
    "error": "#dc2626",
    "error_hover": "#b91c1c",
    "warning": "#d97706",
    "neutral": "#94a3b8",
}

# Iconos (emoji) por servicio, sección y acción. Renderizados con Segoe UI Emoji.
SERVICE_ICONS = {
    "Backend": "🖥️",
    "Frontend": "🌐",
    "Ollama": "🦙",
    "STT": "🎙️",
    "TTS": "🔊",
    "Base de datos": "🗄️",
}

SECTION_ICONS = {
    "Servicios": "🛠️",
    "Acceso a la app": "📡",
    "Base de datos": "💾",
    "Usuarios": "👥",
    "Cookies navegador": "🍪",
    "Registros": "📄",
}

ACTION_ICONS = {
    "start": "▶️",
    "stop": "⏹️",
    "restart": "🔁",
    "open": "🔗",
    "refresh": "🔄",
}

STATUS_DOT = {
    "ok": "🟢",
    "ready": "🟢",
    "error": "🔴",
    "unavailable": "🟡",
    "unknown": "⚪",
    "off": "🔴",
}

TAIL_LINES = 250


def status_dot(value: str) -> str:
    """Emoji de punto para un estado normalizado (ok/ready/error/...)."""
    return STATUS_DOT.get(value, STATUS_DOT["unknown"])


def status_color(value: str) -> str:
    """Color (hex) de la paleta para un estado normalizado (ok/error/...).

    Se usa para teñir el texto de estado de los servicios y la cabecera,
    de modo que el color no dependa de que el emoji se renderice a color.
    """
    mapping = {
        "ok": COLORS["success"],
        "ready": COLORS["success"],
        "on": COLORS["success"],
        "error": COLORS["error"],
        "off": COLORS["error"],
        "unavailable": COLORS["warning"],
        "unknown": COLORS["neutral"],
    }
    return mapping.get(value, COLORS["neutral"])


def read_log_tail(name: str, max_lines: int = TAIL_LINES) -> str:
    """Últimas ``max_lines`` líneas de ``logs/<name>.log`` (``""`` si no existe)."""
    path = LOG_DIR / f"{name}.log"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])

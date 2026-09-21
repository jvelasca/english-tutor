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
    "Interfaz": "🌐",
    "Ollama": "🦙",
    "STT": "🎙️",
    "TTS": "🔊",
    "Base de datos": "🗄️",
}

SECTION_ICONS = {
    "Servicios": "🛠️",
    "Actividad del servidor": "📊",
    "Acceso a la app": "📡",
    "Base de datos": "💾",
    "Perfiles": "🔐",
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
# V3.75.3: bytes como mucho que se leen del final del log por refresco. Es el
# techo que hace que el coste de `read_log_tail` no dependa del tamaño del
# fichero; con 250 líneas de uvicorn por delante, sobra de largo.
TAIL_BYTES = 64 * 1024


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
        "busy": COLORS["warning"],
        "unknown": COLORS["neutral"],
    }
    return mapping.get(value, COLORS["neutral"])


def server_activity(status: dict | None) -> tuple[str, int]:
    """Resumen de la «Actividad del servidor» a partir de /api/system/status.

    Devuelve (línea de actividad, rechazos_429_último_minuto). Si `status` es
    None (backend caído) la línea lo indica y los rechazos son 0. Función pura
    para poder testearla sin abrir ventanas.
    """
    if not status:
        return ("No disponible (backend apagado)", 0)
    gen = status.get("generation") or {}
    jobs = gen.get("jobs") or []
    running = int(gen.get("running", 0) or 0)
    if running:
        levels = ", ".join(j.get("level", "") for j in jobs)
        if levels:
            detail = f"Generando práctica extra ({levels})…"
        else:
            detail = "Generando práctica extra…"
        line = detail
    else:
        line = "En reposo"
    rejected = int(
        (status.get("rate_limited") or {}).get("rejected_last_minute", 0) or 0
    )
    return line, rejected


# --- Perfiles y solicitudes (V3.77) -----------------------------------------
#
# Vistas puras de lo que el webmaster ve en la sección «Perfiles». Se separan de
# la GUI por la razón de siempre: la disposición de la ventana no se puede probar
# sin pantalla, pero **lo que dice cada fila sí**, y es justo donde un cambio
# puede mentir al usuario («Desactivado» pintado como activo, una baja mostrada
# sin nombre de perfil, un contador mal).
REQUEST_KIND_LABELS = {"create": "🆕 Alta", "delete": "🗑️ Baja"}
PROFILE_STATUS_LABELS = {"active": "Activo", "disabled": "Desactivado"}


def pending_summary(count: int) -> str:
    """Frase del contador de solicitudes pendientes (concordancia incluida)."""
    if count <= 0:
        return "Sin solicitudes pendientes"
    if count == 1:
        return "1 solicitud pendiente"
    return f"{count} solicitudes pendientes"


def request_row(
    request: dict, names: dict[str, str] | None = None
) -> tuple[str, str, str]:
    """Fila de una solicitud: (tipo, a quién se refiere, cuándo llegó).

    En una baja, la solicitud guarda el `user_id`, no el nombre: se traduce con
    `names` (el mapa de la lista de perfiles ya cargada) para que el webmaster no
    tenga que decidir sobre un identificador. Si el perfil ya no está, se dice
    «(perfil que ya no existe)» en vez de enseñar el id crudo.
    """
    kind = REQUEST_KIND_LABELS.get(str(request.get("kind")), str(request.get("kind")))
    if request.get("kind") == "delete":
        uid = str(request.get("user_id") or "")
        target = (names or {}).get(uid) or "(perfil que ya no existe)"
    else:
        target = str(request.get("display_name") or "")
        if request.get("note"):
            target = f"{target} — {request['note']}"
    when = str(request.get("requested_at") or "").replace("T", " ")[:16]
    return (kind, target, when)


def profile_row(profile: dict) -> tuple[str, str, str, str]:
    """Fila de un perfil: (nombre, estado, PIN, creado).

    El PIN se informa como booleano —«Con PIN» / «Sin PIN»— y nunca como valor:
    el backend no lo manda en claro ni hasheado, y esta pantalla no inventa una
    forma de mostrarlo.
    """
    status = str(profile.get("status") or "active")
    return (
        "👤 " + str(profile.get("name") or ""),
        PROFILE_STATUS_LABELS.get(status, status),
        "🔑 Con PIN" if profile.get("has_pin") else "Sin PIN",
        str(profile.get("created_at") or "").replace("T", " ")[:16],
    )


def admin_state_label(pin_set: bool) -> str:
    """Estado del candado de administración, en una frase."""
    if pin_set:
        return "🔐 Administración habilitada (PIN configurado)"
    return (
        "🔒 Administración deshabilitada: define un PIN para poder crear, "
        "desactivar o borrar perfiles"
    )


def interface_state(served: bool, dist_available: bool) -> str:
    """Etiqueta del servicio «Interfaz»: tres situaciones, no dos.

    V3.75.3: «servida» lo decide una **sonda de red**, así que su ausencia no
    significa «sin compilar». El artefacto se comprueba en **disco**
    (`core.frontend_dist_available`), y confundir los dos casos manda al usuario a
    arreglar lo que no está roto: un puerto ocupado, o un servidor HTTP donde se
    espera HTTPS, se leían como «🔴 No compilada» con la UI perfectamente
    compilada. Función pura para poder testearla sin abrir ventanas.

    - `served` → la UI responde en el origen de producto.
    - no servida, con artefacto → está compilada, pero el origen no responde.
    - no servida, sin artefacto → falta de verdad: sí hay que compilar.
    """
    if served:
        return "🟢 Servida"
    return "🔴 No responde" if dist_available else "🔴 No compilada"


# V3.75.3: firmas conocidas de un fallo de arranque del backend. Se traducen a una
# frase accionable. Gana la primera que casa, así que el orden importa. Las agujas
# son deliberadamente específicas: una palabra genérica como «error» casaría con
# cualquier log.
_FAILURE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("10048", "address already in use", "only one usage of each socket"),
        "El puerto ya estaba ocupado por otro proceso justo al arrancar.",
    ),
    (
        ("load_cert_chain", "sslerror", "[ssl:"),
        "El certificado TLS local no se pudo cargar. Bórralo en "
        "`backend/data/certs/` y vuelve a pulsar «Iniciar app» para regenerarlo.",
    ),
    (
        ("modulenotfounderror", "no module named", "importerror"),
        "Falta una dependencia en el entorno del backend (`backend/.venv`). "
        "Reinstala los requisitos para arreglarlo.",
    ),
    (
        ("the system cannot find the file", "no such file or directory"),
        "El backend no encontró un fichero necesario (o el Python de "
        "`backend/.venv` no existe).",
    ),
)


def backend_failure_hint(log_text: str) -> str | None:
    """Traduce un fallo de arranque del backend a una frase accionable.

    V3.75.3: cuando el backend moría al arrancar, la GUI solo mostraba «🔴
    Detenido» y el motivo —que ya estaba en `logs/backend.log`— no llegaba nunca
    al usuario. Devuelve ``None`` si el log no contiene ninguna firma conocida.
    Función pura para poder testearla sin abrir ventanas.
    """
    lowered = log_text.lower()
    for needles, message in _FAILURE_HINTS:
        if any(needle in lowered for needle in needles):
            return message
    return None



def read_log_tail(name: str, max_lines: int = TAIL_LINES) -> str:
    """Últimas ``max_lines`` líneas de ``logs/<name>.log`` (``""`` si no existe).

    V3.75.3: se lee **solo la cola** del fichero (``TAIL_BYTES``), no el fichero
    entero. Antes se hacía ``read_text()`` completo y se descartaba todo menos
    ``max_lines``: con `backend.log` en 87 MB y un refresco cada 2 s, eso era leer
    87 MB de disco, decodificarlos y trocearlos en 1,3 M de líneas cada dos
    segundos (586 ms medidos por lectura) para quedarse con 250 líneas. Con la
    lectura por cola el coste **no depende del tamaño histórico** del log.

    La primera línea del bloque leído puede estar cortada a media palabra: se
    descarta cuando se ha hecho *seek*, para no mostrar una línea falsa.
    """
    path = LOG_DIR / f"{name}.log"
    try:
        size = path.stat().st_size
        with open(path, "rb") as handle:
            truncated = size > TAIL_BYTES
            if truncated:
                handle.seek(size - TAIL_BYTES)
            data = handle.read()
    except OSError:
        return ""
    lines = data.decode("utf-8", errors="replace").splitlines()
    if truncated and lines:
        lines = lines[1:]
    return "\n".join(lines[-max_lines:])

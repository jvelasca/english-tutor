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
    "Usuarios": "👥",
    "Actividad por usuario": "📈",
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


# --- Cuentas y solicitudes (V3.77, V3.81) -------------------------------------
#
# Vistas puras de lo que el webmaster ve en la sección «Usuarios» (la consola de
# gestión). Se separan de la GUI por la razón de siempre: la disposición de la
# ventana no se puede probar sin pantalla, pero **lo que dice cada fila sí**, y es
# justo donde un cambio puede mentir al usuario («Desactivado» pintado como
# activo, una cuenta sin contraseña pintada como protegida, una baja mostrada sin
# nombre, un contador mal).
REQUEST_KIND_LABELS = {"create": "🆕 Alta", "delete": "🗑️ Baja"}
USER_STATUS_LABELS = {
    "active": "Activo",
    "disabled": "Desactivado",
    "unenrolled": "Dado de baja",
}

# Acciones de `user_events` (códigos, ver `repositories/users.py`) traducidas a lo
# que lee una persona. El historial es lo que responde «¿por qué mi cuenta está
# así?», así que no puede salir en códigos.
EVENT_ACTION_LABELS = {
    "created": "🆕 Cuenta creada",
    "credentials": "🔑 Credencial asignada",
    "password_changed": "🔒 Contraseña cambiada",
    "email_verified": "✉️ Email verificado",
    "unenrolled": "🚪 Baja pedida por el alumno",
    "force_unenrolled": "🚫 Baja forzada por el webmaster",
    "reenrolled": "↩️ Cuenta reactivada",
    "disabled": "⏸️ Cuenta desactivada",
    "edited": "✏️ Datos editados",
    "purged": "🗑️ Datos purgados",
}


def _fold_user_name(user: dict) -> str:
    """Nombre comparable: espacios colapsados y sin distinguir mayúsculas."""
    return " ".join(str(user.get("name", "")).split()).casefold()


def duplicate_user_ids(users: list[dict]) -> set[str]:
    """Ids de los usuarios que comparten nombre con otro (V3.80.2).

    El nombre se compara colapsando espacios y sin distinguir mayúsculas, que es
    la misma regla con la que el backend rechaza un alta repetida: si el alta no
    admite «ana» junto a «Ana  », el marcado tiene que verlas igual.
    """
    counts: dict[str, int] = {}
    for user in users:
        folded = _fold_user_name(user)
        if folded:
            counts[folded] = counts.get(folded, 0) + 1
    return {
        str(user.get("id"))
        for user in users
        if _fold_user_name(user) and counts[_fold_user_name(user)] > 1
    }


def user_row_label(user: dict, duplicates: set[str]) -> str:
    """Etiqueta de la fila de un usuario, marcando los nombres repetidos.

    La app y esta tabla pintan a los usuarios **por nombre**: con dos «J.A» el
    webmaster no puede saber a cuál le está dando de baja, que es exactamente el
    error que esta consola existe para evitar. Se marca y no se renombra nada
    por su cuenta: renombrar es una decisión suya.
    """
    name = str(user.get("name", ""))
    if str(user.get("id")) in duplicates:
        return f"⚠️ {name} (nombre repetido)"
    return f"👤 {name}"


def credential_label(user: dict) -> str:
    """¿La cuenta tiene contraseña? Se informa como sello, **nunca** como valor.

    Es la columna que convierte el agujero de seguridad en una tarea visible: una
    cuenta sin contraseña entra nombrando, y mientras el contador no llegue a cero
    el webmaster tiene trabajo pendiente aquí.
    """
    if user.get("has_password"):
        return "🔑 Con contraseña"
    return "⚠️ Sin contraseña"


def email_label(user: dict) -> str:
    """Email con su sello de verificación, o «—» si la cuenta no tiene.

    El chip «sin verificar» no es un error: en modo híbrido una cuenta funciona
    sin verificar, y lo que hace este texto es que el webmaster pueda sellarla a
    mano cuando tenga a la persona delante.
    """
    email = str(user.get("email") or "")
    if not email:
        return "—"
    if user.get("email_verified"):
        return f"✉️ {email}"
    return f"✉️ {email} · sin verificar"


def user_row(user: dict, duplicates: set[str]) -> tuple[str, str, str, str, str]:
    """Fila de una cuenta: (nombre, estado, email, credencial, creado).

    El orden de las columnas es el del árbol de la consola. La credencial va como
    booleano y el email con su sello, nunca el hash ni la contraseña: el backend no
    los manda, y esta pantalla no inventa una forma de mostrarlos.
    """
    status = str(user.get("status") or "active")
    return (
        user_row_label(user, duplicates),
        USER_STATUS_LABELS.get(status, status),
        email_label(user),
        credential_label(user),
        str(user.get("created_at") or "").replace("T", " ")[:16],
    )


def accounts_tasks(without_password: int, unverified_email: int) -> str:
    """Lista de tareas del webmaster, en una frase.

    Los dos números que importan de verdad: cuentas **sin contraseña** (heredadas,
    siguen entrando nombrando) y cuentas con email **sin verificar** (en modo
    híbrido, las sella él). Un contador que se ve es un contador que baja; si esto
    dijera «todo en orden» con cuentas sin credencial, la consola estaría mintiendo
    justo en el punto que esta release viene a cerrar.
    """
    if without_password <= 0 and unverified_email <= 0:
        return "✅ Todas las cuentas tienen contraseña y email verificado."
    partes = []
    if without_password == 1:
        partes.append("1 cuenta sin contraseña")
    elif without_password > 1:
        partes.append(f"{without_password} cuentas sin contraseña")
    if unverified_email == 1:
        partes.append("1 email sin verificar")
    elif unverified_email > 1:
        partes.append(f"{unverified_email} emails sin verificar")
    return "⚠️ Pendiente: " + " · ".join(partes) + "."


def event_row(event: dict) -> tuple[str, str, str, str]:
    """Fila del historial: (cuándo, qué, quién, motivo).

    Una acción desconocida se enseña **en crudo** en vez de ocultarse: si el
    backend añade un tipo de evento y esta tabla no lo conoce, quien mire el
    historial tiene que ver que pasó algo, no una fila vacía.
    """
    action = str(event.get("action") or "")
    return (
        str(event.get("created_at") or "").replace("T", " ")[:16],
        EVENT_ACTION_LABELS.get(action, action),
        str(event.get("actor") or ""),
        str(event.get("note") or ""),
    )


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
    `names` (el mapa de la lista de cuentas ya cargada) para que el webmaster no
    tenga que decidir sobre un identificador. Si la cuenta ya no está, se dice
    «(cuenta que ya no existe)» en vez de enseñar el id crudo.
    """
    kind = REQUEST_KIND_LABELS.get(str(request.get("kind")), str(request.get("kind")))
    if request.get("kind") == "delete":
        uid = str(request.get("user_id") or "")
        target = (names or {}).get(uid) or "(cuenta que ya no existe)"
    else:
        target = str(request.get("display_name") or "")
        if request.get("note"):
            target = f"{target} — {request['note']}"
    when = str(request.get("requested_at") or "").replace("T", " ")[:16]
    return (kind, target, when)


def pending_view(
    *,
    pin_set: bool,
    db_count: int | None,
    ok: bool,
    error: str = "",
    requests: list[dict] | None = None,
    names: dict[str, str] | None = None,
) -> tuple[str, list[tuple[str, str, str]]]:
    """Qué decir de la cola de solicitudes: (frase del contador, filas).

    Existe por un fallo concreto y no por gusto de partir la GUI: `_apply_profiles`
    decidía la frase en línea y **nunca miraba si la consulta al backend había
    fallado**, así que un 401 (administración sin PIN), un 403 (petición que no
    viene del equipo) o un servidor caído se pintaban como «Sin solicitudes
    pendientes» con la lista vacía — indistinguible de una cola realmente vacía.
    Aquí los estados no se pueden confundir porque cada uno se decide aparte:

    - **Sin PIN**: no se consulta al backend (fail-closed), pero el contador sí se
      lee de la BD en solo-lectura. Si hay pendientes, se dice cuántas hay y que
      hace falta el PIN para verlas y resolverlas: es la frase que faltaba cuando
      la baja del alumno «no aparecía».
    - **Sin PIN y sin poder leer la BD** (`db_count is None`): cerrada *y* sin
      contador. Se admite que no se sabe.
    - **Con PIN y consulta fallida**: el motivo, no un cero. `error` es la frase
      que ya resuelve `AdminResult.message()` para 401/403/red.
    - **Con PIN y consulta correcta**: el contador de las filas que se van a
      pintar (`len(requests)`, para que el número y la lista no se contradigan) y
      las filas vía `request_row`.

    Función pura: sin tkinter, sin red. La GUI solo pinta lo que devuelve.
    """
    rows = requests or []
    if not pin_set:
        if db_count is None:
            return (
                "🔒 Administración deshabilitada y no se pudo leer el contador "
                "de solicitudes (¿BD no accesible?)",
                [],
            )
        if db_count > 0:
            return (
                f"🗳️ {pending_summary(db_count)} · define el PIN de administración "
                "para ver y resolverlas",
                [],
            )
        return (
            "🔒 Administración deshabilitada: define un PIN para ver y resolver "
            "la cola",
            [],
        )
    if not ok:
        motivo = error or "el servidor no dio detalle"
        return (f"⚠️ No se pudo consultar la cola: {motivo}", [])
    return (
        pending_summary(len(rows)),
        [request_row(request, names) for request in rows],
    )


def admin_state_label(pin_set: bool) -> str:
    """Estado del candado de administración, en una frase."""
    if pin_set:
        return "🔐 Administración habilitada (PIN configurado)"
    return (
        "🔒 Administración deshabilitada: define un PIN para poder crear "
        "cuentas, asignar credenciales, forzar bajas y purgar datos"
    )


def smtp_state_label(configured: bool, has_password: bool) -> str:
    """Estado del correo saliente, en una frase.

    Se distinguen **tres** estados y no dos: «configurado» es tener host y
    remitente; tener contraseña guardada es otra cosa (un servidor local de
    reenvío no la necesita). Confundirlos mandaría al webmaster a buscar una
    contraseña que su servidor no pide, o a creer que el correo funciona sin
    remitente.
    """
    if not configured:
        return (
            "📭 Correo sin configurar: no se envía nada y la verificación la "
            "sellamos a mano."
        )
    if has_password:
        return "📬 Correo configurado (con contraseña guardada)."
    return "📬 Correo configurado (el servidor no pide contraseña)."


def smtp_reconcile_label(
    local_configured: bool, has_password: bool, backend: dict | None
) -> str:
    """Frase del correo, conciliando lo que el launcher guarda y lo que el
    servidor **en marcha** ve.

    Son dos cosas distintas y por eso pueden discrepar, que es lo que esta función
    existe para no esconder: el launcher escribe el JSON y le pasa los ajustes al
    backend **al arrancarlo**, así que un cambio recién guardado no lo ve el
    servidor hasta que reinicia —`_save_smtp` reinicia, pero la frase tiene que
    decir la verdad también durante ese hueco—, y unas variables de entorno
    puestas a mano no pasan por esta consola. Enseñar el estado local como si
    fuera el del servidor es exactamente el error que V3.80.1 tuvo que arreglar en
    la cola de solicitudes (un «cero» que no se había preguntado).

    `backend` es la respuesta de `GET /api/admin/smtp`, o `None` cuando **no se
    pudo preguntar** (sin PIN, servidor caído): ahí se enseña lo local y no se
    afirma nada sobre el servidor.
    """
    base = smtp_state_label(local_configured, has_password)
    if backend is None:
        return base
    if bool(backend.get("configured")) == local_configured:
        return base
    if local_configured:
        return (
            base + " El servidor en marcha todavía no lo ve: se aplica al arrancar."
        )
    return (
        "📬 El servidor tiene correo configurado (variables de entorno), pero no "
        "está guardado en esta consola: aquí no se puede gestionar."
    )


def purge_block_reason(user: dict) -> str:
    """Por qué no se puede purgar todavía, o `""` si sí se puede.

    El backend exige la cuenta **fuera de servicio** para purgar: borrar todo
    rastro de una persona no se hace sin un paso previo revisable. La consola lo
    comprueba antes de pedir la confirmación por nombre, para no hacer teclear un
    nombre y luego rechazarlo.
    """
    status = str(user.get("status") or "active")
    if status == "active":
        return (
            "Antes de purgar hay que dejar la cuenta fuera de servicio "
            "(desactivarla o darle de baja) y comprobar que nadie la echa de menos."
        )
    return ""


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

"""Núcleo puro del launcher de escritorio (sin GUI, sin red, sin procesos).

Funciones deterministas para resolver rutas, construir comandos de arranque y
normalizar el estado de la app, las dependencias y la base de datos. Testeable
sin lanzar nada.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path

# El launcher vive en <repo>/launcher/, así que el repo raíz es el padre del padre.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DB_PATH = BACKEND_DIR / "data" / "tutor.db"

BACKEND_PORT = 8000
# V3.72 (RC-01): el producto sirve la UI y la API desde el MISMO origen, así que
# no hay un segundo puerto. `npm run dev` (Vite en :5173) queda como **modo de
# desarrollo**, no como runtime de producto. Se conserva el nombre como alias
# para que las URLs anunciadas sigan siendo una sola.
FRONTEND_PORT = BACKEND_PORT

# Certificado TLS autofirmado con el que uvicorn sirve HTTPS. Lo genera
# `backend/scripts/ensure_tls_cert.py` (invocado por el launcher) y es un
# artefacto de máquina: vive en `backend/data/`, que está ignorado por git.
TLS_CERT_PATH = BACKEND_DIR / "data" / "certs" / "cert.pem"
TLS_KEY_PATH = BACKEND_DIR / "data" / "certs" / "key.pem"

# Artefacto compilado de la UI (lo construye `npm run build`, no se versiona).
FRONTEND_DIST = FRONTEND_DIR / "dist"

AUTHOR_NAME = "José Alberto Velasco"
AUTHOR_EMAIL = "josealberto.vel@gmail.com"

ICON_PATH = Path(__file__).resolve().parent / "icon.ico"


def author_line() -> str:
    """Crédito del autor para mostrar en el launcher."""
    return f"{AUTHOR_NAME} · {AUTHOR_EMAIL}"


def icon_file() -> str:
    """Ruta del icono de la ventana (icon.ico generado por make_icon.ps1)."""
    return str(ICON_PATH)


def backend_python() -> Path:
    """Intérprete del venv del backend (resuelto por `os.name`)."""
    exe = "python.exe" if os.name == "nt" else "python"
    return BACKEND_DIR / ".venv" / "Scripts" / exe


def npm_command() -> str:
    """Ejecutable de npm (solo se usa para COMPILAR la UI o en desarrollo)."""
    return "npm.cmd" if os.name == "nt" else "npm"


# V3.73: el launcher declara el runtime de **producto** al backend. Con esta
# variable activa, la falta de `frontend/dist` es un error explícito (fail-closed)
# en vez de una app que arranca sin interfaz y parece lista.
REQUIRE_UI_ENV = "ENGLISH_TUTOR_REQUIRE_UI"

# V3.73: override declarado de la IP de LAN (equipos con varias NIC o VPN, donde
# la elección automática puede no ser la interfaz de la app).
LAN_IP_ENV = "ENGLISH_TUTOR_LAN_IP"

# V3.73.x: el **modo LAN** es opt-in declarado. Sin esta variable (o con un valor
# que no sea afirmativo) uvicorn escucha en loopback y el backend no acepta
# orígenes de la red local: la app deja de ser alcanzable desde otro equipo.
# El launcher es quien la declara al backend en `backend_env()`, así que la
# interfaz a la que se enlaza y el entorno que recibe el proceso **no pueden
# discrepar** (salen de la misma función, `lan_mode`).
LAN_ENV = "ENGLISH_TUTOR_LAN"

# Valores que activan un flag booleano. Se replica el criterio de
# `backend/services/frontend_dist.py` (`_TRUTHY`) para que las dos mitades del
# contrato lean igual; `launcher/tests/test_lan_mode.py` comprueba que el nombre
# de la variable coincide en ambos lados.
_TRUTHY = frozenset({"1", "true", "yes", "on", "si", "sí"})


def lan_mode(env: dict[str, str] | None = None) -> bool:
    """¿Modo LAN activo? **Fail-closed**: ausente o no reconocido ⇒ False.

    Ausente ⇒ loopback. Es una decisión de producto, no un detalle: exponer la
    API en la red local tiene que ser algo que el usuario declare, porque
    mientras no haya autenticación (P0 abierto, ver `PARKED.md`) cualquiera que
    alcance el puerto ve y escribe los datos del alumno.
    """
    source = os.environ if env is None else env
    return str(source.get(LAN_ENV, "")).strip().lower() in _TRUTHY


def backend_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Entorno del proceso de producto: exige la UI y declara el modo de red.

    Se copia el entorno (``os.environ`` o ``base``) para no perder PATH ni las
    variables del usuario; se añade la exigencia de la UI y se **canoniza** el
    modo LAN a ``"1"``/``"0"``. Que el valor viaje siempre (aunque sea ``"0"``) y
    no se borre es deliberado: el backend recibe una decisión explícita del
    launcher en vez de deducirla de una variable ausente.
    """
    env = dict(os.environ) if base is None else dict(base)
    env[REQUIRE_UI_ENV] = "1"
    env[LAN_ENV] = "1" if lan_mode(env) else "0"
    return env


def backend_host(env: dict[str, str] | None = None) -> str:
    """Interfaz a la que se enlaza uvicorn: la LAN solo si está declarada.

    Se devuelve ``127.0.0.1`` (no ``localhost``) para no depender de la
    resolución de nombres del equipo y dejar claro que es loopback.
    """
    return "0.0.0.0" if lan_mode(env) else "127.0.0.1"


def set_lan_mode(enabled: bool, env: dict[str, str] | None = None) -> None:
    """Declara (o retira) el modo LAN en el entorno del launcher.

    Es lo que hace el botón del panel de acceso. Se escribe aquí, en `core`, y no
    en la GUI porque la GUI no se puede probar sin pantalla: así la decisión que
    cambia la frontera de red tiene test. El backend **no** ve este cambio hasta
    que se reinicia (`backend_env` lee el entorno al arrancarlo).
    """
    source = os.environ if env is None else env
    if enabled:
        source[LAN_ENV] = "1"
    else:
        # Se retira en vez de escribir "0": el modo por defecto es cerrar, y un
        # valor ausente no puede leerse mal (`lan_mode` es fail-closed).
        source.pop(LAN_ENV, None)


def apply_lan_config(config: dict, env: dict[str, str] | None = None) -> None:
    """Declara en el entorno el modo LAN que el launcher dejó guardado (V3.75.3).

    Es el arranque de la GUI, y por eso vive aquí y no en `launcher.py`: la
    decisión que cambia la frontera de red tiene que poder probarse sin pantalla
    (la GUI no se testea). La preferencia persistida **manda** sobre el entorno
    heredado —es lo que hace que «red local» sobreviva al cierre— y cualquier
    valor que no sea `True` se lee como cerrado, con el mismo criterio
    fail-closed que `lan_mode`.
    """
    # `is True` y no `bool(...)`: una cadena no vacía (`"sí"`) es *truthy*, y aquí
    # «declarado» tiene que significar el booleano `True`, no «algo que suena
    # afirmativo». `config.json` es un fichero de texto que se puede editar a mano.
    set_lan_mode(config.get("lan") is True, env)


def apply_stored_lan_config(
    path: Path | None = None, env: dict[str, str] | None = None
) -> dict:
    """Arranque del launcher: lee la preferencia guardada y la declara en el entorno.

    Es `load_config` + `apply_lan_config` en **una sola llamada** a propósito: la
    GUI no puede reordenar las dos mitades ni saltarse una, y el orden que importa
    —leer **antes** de pintar, porque el panel de acceso muestra el modo vigente—
    queda fijado por un test que no necesita pantalla. Devuelve la config cargada,
    que es la que la GUI conserva en memoria para escribirla al cambiarla.
    """
    # Import diferido: `config_store` es el módulo de E/S y `core` el núcleo puro;
    # se importa aquí para que el núcleo siga pudiéndose importar sin tocar disco.
    from config_store import load_config

    config = load_config(path)
    apply_lan_config(config, env)
    return config


def toggle_lan_config(
    config: dict, path: Path | None = None, env: dict[str, str] | None = None
) -> dict:
    """Invierte el modo LAN, lo declara y **persiste** la preferencia (V3.75.3).

    Es el único sitio donde la preferencia se escribe, y vive aquí —y no en la
    GUI— porque el cableado «invertir → declarar → guardar» tiene que poder
    probarse sin pantalla: si se saltara el guardado, el launcher dejaría de
    recordar el modo y ninguna prueba pura lo notaría. Se relee `lan_mode()` para
    guardar lo que **de verdad** quedó declarado, no lo que se creía declarar.
    """
    from config_store import save_config

    set_lan_mode(not lan_mode(env), env)
    config["lan"] = lan_mode(env)
    save_config(config, path)
    return config


def backend_command() -> list[str]:
    """Comando para arrancar el backend con el venv del proyecto (uvicorn).

    Se enlaza a **loopback** salvo en modo LAN (``ENGLISH_TUTOR_LAN``): exponer
    la API en la red local es opt-in. En los dos casos se sirve por **HTTPS
    autofirmado**: sin *secure context* el navegador no expone
    `navigator.mediaDevices` y se rompe la grabación (micrófono), también en el
    propio equipo. El backend sirve además la UI compilada (V3.72, RC-01).
    """
    return [
        str(backend_python()),
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        backend_host(),
        "--port",
        str(BACKEND_PORT),
        "--ssl-certfile",
        str(TLS_CERT_PATH),
        "--ssl-keyfile",
        str(TLS_KEY_PATH),
    ]


def ensure_cert_command() -> list[str]:
    """Comando que genera el certificado TLS autofirmado si falta (idempotente)."""
    return [str(backend_python()), "-m", "scripts.ensure_tls_cert"]


def frontend_build_command() -> list[str]:
    """Comando para COMPILAR la UI (`frontend/dist`). No es el runtime."""
    return [npm_command(), "run", "build"]


def frontend_dev_command() -> list[str]:
    """Comando del **modo desarrollo** (Vite dev server con HMR, puerto 5173).

    Ya no lo usa el launcher: se conserva porque es el flujo de trabajo de
    desarrollo (`.vscode/launch.json`) y la frontera está declarada por test.
    """
    return [npm_command(), "run", "dev"]


def frontend_dist_available() -> bool:
    """True si existe el artefacto compilado de la UI (index.html)."""
    return (FRONTEND_DIST / "index.html").is_file()


def port_in_use(
    host: str = "127.0.0.1",
    port: int = BACKEND_PORT,
    timeout: float = 0.5,
) -> bool:
    """True si algo acepta conexiones TCP en ``host:port``.

    V3.75.3: distingue «no hay backend» de «el puerto está ocupado por otro
    proceso». No es lo mismo y no se arreglan igual: si el puerto está tomado,
    arrancar no sirve —uvicorn muere con ``WinError 10048`` y la GUI solo puede
    decir «Detenido»— y lo que hay que hacer es liberar el puerto.

    Se comprueba la **conexión TCP**, no el esquema: un backend HTTP en el mismo
    puerto ocupa el socket igual, y las sondas del launcher son HTTPS
    (`fetch_health`), así que serían ciegas a él. Cualquier fallo se lee como
    «libre» para no bloquear un arranque legítimo.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def backend_url() -> str:
    return f"https://127.0.0.1:{BACKEND_PORT}"


def frontend_url() -> str:
    # V3.72: la UI la sirve el propio backend en el mismo origen HTTPS. Sigue
    # siendo HTTPS con certificado autofirmado (por el micrófono en la LAN).
    return f"https://localhost:{BACKEND_PORT}"


def lan_ip() -> str:
    """IP IPv4 de la LAN desde la que se sirve la app (o 127.0.0.1).

    V3.73: se enumeran las direcciones del propio equipo, sin consultar ninguna
    dirección externa (hasta V3.72 se usaba un socket UDP a `8.8.8.8`, perezoso
    pero con una referencia pública). El launcher no puede importar el backend
    (son proyectos separados), así que el algoritmo se replica aquí; el contrato
    compartido lo fija `launcher/tests/test_preflight_v373.py`.
    """
    override = os.environ.get(LAN_IP_ENV, "").strip()
    if override and is_usable_lan_address(override):
        return override
    return select_lan_ipv4(candidate_addresses())


def is_usable_lan_address(value: str) -> bool:
    """True si la dirección sirve para anunciar la app en la LAN.

    Descarta loopback, link-local (`169.254/16`), `0.0.0.0` y multicast.
    """
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.version != 4:
        return False
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
    )


def select_lan_ipv4(addresses: list[str]) -> str:
    """Primera IPv4 utilizable, prefiriendo rangos privados. Nunca vacío."""
    usable = [value for value in addresses if is_usable_lan_address(value)]
    for value in usable:
        if ipaddress.ip_address(value).is_private:
            return value
    if usable:
        return usable[0]
    return "127.0.0.1"


def candidate_addresses(hostname: str | None = None) -> list[str]:
    """Direcciones IPv4 que el sistema asocia a este equipo (solo local)."""
    name = hostname if hostname is not None else socket.gethostname()
    seen: list[str] = []

    def _add(value: object) -> None:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)

    try:
        for info in socket.getaddrinfo(name, None, socket.AF_INET):
            _add(info[4][0])
    except OSError:
        pass
    try:
        _, _, addresses = socket.gethostbyname_ex(name)
        for value in addresses:
            _add(value)
    except OSError:
        pass
    return seen


def lan_hostname() -> str:
    """Nombre del host en la red local (sin dominio), para acceso mDNS."""
    return socket.gethostname().split(".")[0]


def lan_url() -> str:
    """URL de acceso desde otros equipos de la red local (por IP).

    Solo es alcanzable en **modo LAN** (`lan_mode()`): con el bind en loopback
    esta URL no responde. Quien la muestre debe decir en qué modo está, o el
    usuario verá un enlace muerto sin explicación.
    """
    return f"https://{lan_ip()}:{FRONTEND_PORT}"


def local_url() -> str:
    """URL de acceso por nombre local mDNS (p. ej. https://mi-pc.local:8000)."""
    return f"https://{lan_hostname()}.local:{FRONTEND_PORT}"


def mdns_available() -> bool:
    """Comprueba si ``<hostname>.local`` resuelve realmente (mDNS activo).

    Generar la URL no instala un servicio mDNS; sin Bonjour/Avahi/mDNS en
    Windows el nombre no resolverá. Se devuelve ``False`` ante cualquier fallo.
    """
    try:
        socket.getaddrinfo(f"{lan_hostname()}.local", None)
        return True
    except OSError:
        return False


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

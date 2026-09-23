"""Núcleo puro del launcher de escritorio (sin GUI, sin red, sin procesos).

Funciones deterministas para resolver rutas, construir comandos de arranque y
normalizar el estado de la app, las dependencias y la base de datos. Testeable
sin lanzar nada.
"""
from __future__ import annotations

import ipaddress
import os
import secrets
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

    El PIN de administración viaja por aquí igual: lo declara
    `apply_admin_config` en el entorno del launcher y esta copia lo lleva al
    backend, que es lo que hace que **la misma** credencial sirva para las
    acciones del lanzador y para las pantallas admin de la app (V3.77).
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


# --- PIN de administración (V3.77) ------------------------------------------
#
# Hasta V3.77 el candado admin del backend (`dependencies.require_admin`) leía
# una constante sin fuente: `config.ADMIN_PIN = ""`, y por tanto la administración
# estaba **deshabilitada de facto** en el producto (honestidad declarada en
# `agentes/v371-runtime-offline-instalacion.md`). El lanzador es ahora quien la
# declara, y esta es la mitad pura de esa decisión: qué PIN vale, de dónde sale y
# cómo viaja al backend. La GUI solo pinta el campo y llama aquí.
ADMIN_PIN_ENV = "ENGLISH_TUTOR_ADMIN_PIN"
# Seis caracteres: por debajo, el PIN es un adorno; por encima de 64, ya no es un
# secreto que nadie teclee. El máximo también acota lo que se guarda en el JSON.
_ADMIN_PIN_MIN = 6
_ADMIN_PIN_MAX = 64


def is_valid_admin_pin(pin: object) -> bool:
    """¿Sirve como PIN de administración?

    Se admite cualquier carácter (no solo dígitos, al contrario que el PIN de un
    perfil): este no se teclea en el móvil de un alumno, se configura una vez. Lo
    que sí se exige es que no lleve espacios en los extremos: un espacio pegado no
    es un secreto más fuerte, es un error de tecleo que produce «PIN incorrecto»
    sin que nadie entienda por qué.
    """
    if not isinstance(pin, str):
        return False
    if pin != pin.strip():
        return False
    return _ADMIN_PIN_MIN <= len(pin) <= _ADMIN_PIN_MAX


def generate_admin_pin() -> str:
    """PIN de administración aleatorio (lo ofrece el botón «Generar»)."""
    return secrets.token_urlsafe(18)


def admin_pin(config: dict | None = None, env: dict[str, str] | None = None) -> str:
    """PIN vigente: manda la preferencia guardada; si no la hay, el entorno.

    El orden no es un detalle. La preferencia guardada manda porque es la decisión
    explícita del webmaster y tiene que sobrevivir al cierre (igual que el modo
    LAN); el entorno queda como vía para un arranque manual
    (`ENGLISH_TUTOR_ADMIN_PIN=… python launcher.py`) y para los tests. Y si no hay
    ninguna de las dos, `""`: **fail-closed**, la administración no se abre sola.

    Las dos fuentes pasan por la misma criba: devolver un valor con mala forma
    equivaldría a declararlo en el entorno del backend y tener administración con
    un PIN que nadie puede teclear bien. Un `config.json` editado a mano entra por
    aquí, así que la criba no es un lujo.
    """
    source = os.environ if env is None else env
    saved = (config or {}).get("admin_pin")
    if isinstance(saved, str) and is_valid_admin_pin(saved):
        return saved
    inherited = str(source.get(ADMIN_PIN_ENV, "") or "")
    return inherited if is_valid_admin_pin(inherited) else ""


def _declare_admin_pin(pin: str, env: dict[str, str]) -> None:
    """Declara (o retira) el PIN en el entorno. `pin` ya viene cribado.

    Retirar se hace con `pop` y no escribiendo `""`: un valor ausente no se puede
    leer mal, y el backend también es fail-closed.
    """
    if pin:
        env[ADMIN_PIN_ENV] = pin
    else:
        env.pop(ADMIN_PIN_ENV, None)


def apply_admin_config(config: dict, env: dict[str, str] | None = None) -> None:
    """Declara en el entorno el PIN vigente al arrancar, para que el backend lo reciba.

    `backend_env()` copia este entorno al arrancar el backend, así que declararlo
    aquí es lo que hace que el PIN del lanzador y el del backend sean el mismo.
    Declara el **vigente**, no solo el guardado: un arranque manual
    (`ENGLISH_TUTOR_ADMIN_PIN=… python launcher.py`) tiene que seguir sirviendo
    sin escribir ninguna preferencia.
    """
    source = os.environ if env is None else env
    _declare_admin_pin(admin_pin(config, source), source)


def set_admin_pin(
    pin: str,
    config: dict,
    path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict | None:
    """Guarda (o retira, con `""`) el PIN de administración. `None` si no vale.

    Es el único sitio donde se escribe, y vive aquí —no en la GUI— por la misma
    razón que `toggle_lan_config`: el cableado «validar → declarar → guardar»
    tiene que poder probarse sin pantalla.

    Retirar retira **de verdad**, también en el entorno: si solo se vaciara la
    preferencia, un `ENGLISH_TUTOR_ADMIN_PIN` que este mismo proceso hubiera
    declarado al guardar seguiría ahí y la administración no se habría cerrado —
    el botón diría «retirado» y el candado seguiría abierto.
    """
    from config_store import save_config

    source = os.environ if env is None else env
    if pin == "":
        config["admin_pin"] = ""
        _declare_admin_pin("", source)
    elif is_valid_admin_pin(pin):
        config["admin_pin"] = pin
        _declare_admin_pin(pin, source)
    else:
        return None
    save_config(config, path)
    return config


# --- Correo saliente (V3.81) ---------------------------------------------------
#
# El producto puede **no tener Internet**, así que la verificación de email es una
# señal, no un muro: sin SMTP configurado la app funciona igual y la verificación
# la sella el webmaster a mano. Esta es la mitad pura del cableado: qué ajustes
# valen, dónde se guardan y cómo llegan al backend.
#
# La separación es deliberada y no una manía: **host, puerto, usuario y remitente**
# van a `config.json` (configuración, se puede leer y copiar sin peligro), y la
# **contraseña** va a `backend/data/mail.secret`, que está ignorado por git y que
# `services/backup.py` deja fuera de las copias, igual que `session.secret` y la
# clave TLS. Una copia puede acabar en un USB o en una nube, y ahí una contraseña
# de correo en claro es el material con el que se ataca esa cuenta.
SMTP_HOST_ENV = "ENGLISH_TUTOR_SMTP_HOST"
SMTP_PORT_ENV = "ENGLISH_TUTOR_SMTP_PORT"
SMTP_USER_ENV = "ENGLISH_TUTOR_SMTP_USER"
SMTP_FROM_ENV = "ENGLISH_TUTOR_SMTP_FROM"

# Ruta de la contraseña del SMTP: la misma que lee `services/mailer.py`
# (`config.DATA_DIR / config.SMTP_SECRET_NAME`). Si se cambia una, la otra deja de
# encontrarla, y el síntoma sería un «no se pudo enviar» sin explicación.
MAIL_SECRET_PATH = BACKEND_DIR / "data" / "mail.secret"

# 587 (SUBMISSION con STARTTLS) es el que usan los proveedores normales; el 465
# implícito se soporta tecleándolo, que es la razón de exponer el puerto.
DEFAULT_SMTP_PORT = 587


def is_valid_smtp_port(port: object) -> bool:
    """¿Sirve como puerto SMTP? Entero entre 1 y 65535.

    Se rechaza el 0 y lo que no sea entero: un puerto inventado no da un error de
    configuración, da un «no se pudo enviar» que parece un problema de credenciales.
    """
    if isinstance(port, bool):
        return False
    try:
        value = int(port)
    except (TypeError, ValueError):
        return False
    return 1 <= value <= 65535


def is_valid_smtp_settings(host: str, sender: str) -> bool:
    """¿Hay SMTP utilizable? Se exige host **y** remitente.

    Es la misma condición que `backend/config.py::smtp_settings` deriva en
    `configured`, escrita aquí para que la consola pueda decir «falta el remitente»
    antes de mandar una prueba condenada.
    """
    return bool(str(host).strip() and str(sender).strip())


def smtp_settings(config: dict | None = None) -> dict:
    """Ajustes SMTP declarados en el launcher (contraseña **no** incluida).

    Se leen de `config.json` y no del entorno a propósito: el entorno es el canal
    por el que el launcher **declara** al backend, no una fuente de verdad para la
    consola. Si se leyeran del entorno, un `ENGLISH_TUTOR_SMTP_HOST` heredado de un
    arranque manual aparecería en la pantalla como si estuviera guardado.
    """
    stored = config if isinstance(config, dict) else {}
    host = str(stored.get("smtp_host") or "").strip()
    user = str(stored.get("smtp_user") or "").strip()
    sender = str(stored.get("smtp_sender") or "").strip() or user
    port = stored.get("smtp_port")
    if not is_valid_smtp_port(port):
        port = DEFAULT_SMTP_PORT
    return {
        "host": host,
        "port": int(port),
        "user": user,
        "sender": sender,
        "configured": is_valid_smtp_settings(host, sender),
    }


def mail_secret() -> str:
    """Contraseña del SMTP guardada, o `""`. Nunca se enseña (solo `bool`)."""
    try:
        if not MAIL_SECRET_PATH.is_file():
            return ""
        return MAIL_SECRET_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_mail_secret(password: str, path: Path | None = None) -> bool:
    """Escribe (o retira, con `""`) la contraseña del SMTP. `False` si no se pudo.

    Se escribe **en cada guardado** y no al cerrar: una credencial de correo no
    debería depender de que la ventana se cierre bien. Los permisos se aprietan a
    `0o600` donde el sistema los respete (en Windows el flag es inocuo, y por eso
    no se exige que funcione).
    """
    target = path or MAIL_SECRET_PATH
    try:
        if not password:
            target.unlink(missing_ok=True)
            return True
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(password, encoding="utf-8")
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False


def _declare_smtp(config: dict, env: dict[str, str]) -> None:
    """Declara (o retira) los ajustes SMTP en el entorno. Sin host, se retira todo.

    Retirar de verdad —y no escribir cadenas vacías— es lo que hace que apagar el
    correo se note: si solo se vaciara el JSON, un `ENGLISH_TUTOR_SMTP_HOST`
    heredado seguiría ahí y la consola diría «sin correo» mientras el backend
    seguiría enviando.
    """
    settings = smtp_settings(config)
    if not settings["configured"]:
        for name in (SMTP_HOST_ENV, SMTP_PORT_ENV, SMTP_USER_ENV, SMTP_FROM_ENV):
            env.pop(name, None)
        return
    env[SMTP_HOST_ENV] = settings["host"]
    env[SMTP_PORT_ENV] = str(settings["port"])
    env[SMTP_USER_ENV] = settings["user"]
    env[SMTP_FROM_ENV] = settings["sender"]


def apply_smtp_config(config: dict, env: dict[str, str] | None = None) -> None:
    """Declara en el entorno los ajustes SMTP al arrancar.

    `backend_env()` copia este entorno al arrancar el backend, así que declararlo
    aquí es lo que hace que el correo del launcher y el del backend sean el mismo.
    Mismo patrón que `apply_admin_config`.
    """
    source = os.environ if env is None else env
    _declare_smtp(config, source)


def set_smtp_settings(
    config: dict,
    *,
    host: str,
    port: object,
    user: str,
    sender: str,
    password: str | None = None,
    path: Path | None = None,
    secret_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict | None:
    """Guarda los ajustes SMTP (y la contraseña, si se da). `None` si no valen.

    `password=None` significa «no la toques» (dejar la que hubiera) y `""` significa
    «bórrala». La distinción importa: la consola nunca enseña la contraseña, así que
    no puede reenviarla al guardar; si `""` se tratara como «no la toques», apagar
    el correo dejaría la credencial guardada y el `GET` seguiría diciendo que hay.
    """
    from config_store import save_config

    normalized_host = str(host).strip()
    normalized_sender = str(sender).strip() or str(user).strip()
    if normalized_host and not is_valid_smtp_settings(
        normalized_host, normalized_sender
    ):
        return None
    if normalized_host and not is_valid_smtp_port(port):
        return None

    config["smtp_host"] = normalized_host
    config["smtp_port"] = int(port) if is_valid_smtp_port(port) else DEFAULT_SMTP_PORT
    config["smtp_user"] = str(user).strip()
    config["smtp_sender"] = normalized_sender

    if password is not None:
        if not write_mail_secret(password, secret_path):
            return None

    source = os.environ if env is None else env
    _declare_smtp(config, source)
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

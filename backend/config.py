"""Configuración del backend (sin lógica)."""
from __future__ import annotations

import os
from pathlib import Path

# Modelo por defecto del chat y de las tareas de IA. Debe ser *utilizable* en
# este equipo (respuesta interactiva en pocos segundos) y no pertenecer a
# UNUSABLE_MODELS. Si no está instalado, el frontend cae al primer modelo
# disponible de Ollama.
DEFAULT_MODEL = "llama3.1:8b"

# Modelos instalados en Ollama pero NO utilizables en este equipo (p. ej.
# demasiado lentos en CPU: tardan decenas de segundos por turno y se
# descargan/recargan entre llamadas). Se excluyen del selector de modelos de la
# app (GET /api/models → Ajustes → IA), no se usan como modelo por defecto y la
# traducción a demanda no los elige. Ampliar esta lista si otro modelo deja de
# ser utilizable.
UNUSABLE_MODELS = frozenset({"qwen3.5:9b"})

# Endurecimiento del diccionario de consulta (V3.31.1, auditoría V3.31.0, P2).
# Son límites LOCALES de generación a demanda (contenido nuevo = llamada al
# modelo local en CPU); el caché global `dictionary_entries` evita repeticiones
# pero no cardinalidad. Aplican por proceso (best-effort, como el single-flight
# de `domain/vocabulary.py`), en memoria, y degradan a `definition_source="none"`
# sin romper la consulta:
DICTIONARY_GENERATION_TIMEOUT_SECONDS = 90.0  # tope del dueño del vuelo (waiters: 60 s)
DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS = 30.0  # palabra fallida → no reintentar hasta T
DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE = 10  # palabras NUEVAS por usuario/min
DICTIONARY_MAX_GENERATIONS_PER_MINUTE_GLOBAL = 40  # y tope global de seguridad


VERSION = "3.84.1"

# Orígenes permitidos para CORS. El runtime de producto sirve UI y API desde el
# mismo origen (`:8000`, V3.72), así que estos orígenes son el modo de desarrollo
# (dev server de Vite en `:5173`) y el acceso desde el propio equipo.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://localhost:5173",
    "https://127.0.0.1:5173",
    "https://localhost:8000",
    "http://localhost:8000",
]

# --- Modo LAN (V3.73.x) ------------------------------------------------------
#
# Hasta V3.73.6 el producto se enlazaba **siempre** a `0.0.0.0` y aceptaba
# cualquier origen de la red privada: exponerse a la LAN era el comportamiento
# por defecto sin que nadie lo hubiera pedido. Ahora es **opt-in declarado** por
# el launcher (`ENGLISH_TUTOR_LAN=1`), y el backend lo lee **fail-closed**: lo que
# no está declarado, no se permite.
LAN_MODE_ENV = "ENGLISH_TUTOR_LAN"

# Mismo criterio que `launcher/core.py::_TRUTHY` y
# `services/frontend_dist.py::_TRUTHY` (el nombre de la variable los une: ver
# `tests/test_lan_mode.py`).
_TRUTHY = frozenset({"1", "true", "yes", "on", "si", "sí"})


def lan_mode(env: dict[str, str] | None = None) -> bool:
    """¿Modo LAN activo? Se consulta al decidir, **no se cachea al importar**.

    Cachearlo ataría la política al orden de importación de los módulos y haría
    que la decisión dependiera de cuándo se leyó el entorno. Leerlo aquí la deja
    comprobable sin recargar nada (`monkeypatch.setenv` en los tests) y es un
    `os.environ.get` por petición: ruido frente al trabajo real de la ruta.
    """
    source = os.environ if env is None else env
    return str(source.get(LAN_MODE_ENV, "")).strip().lower() in _TRUTHY


# Orígenes del **propio equipo**, por cualquier puerto. No dependen del modo: el
# dev server de Vite puede cambiar de puerto y el acceso local nunca es el riesgo
# que este cambio cierra.
LOCAL_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

# Orígenes de la **red local** (IPs privadas IPv4, por el puerto que sea). Solo
# cuentan en modo LAN; la consulta la hace `security.origin_allowed`, que además
# los rechaza con 403 en métodos no seguros.
LAN_ORIGIN_REGEX = (
    r"https?://("
    r"(10\.\d{1,3}\.\d{1,3}\.\d{1,3})|"
    r"(192\.168\.\d{1,3}\.\d{1,3})|"
    r"(172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    r")(:\d+)?"
)

# Lo que consume `CORSMiddleware` (`main.py`). **Fuera del modo LAN no incluye
# las IPs privadas**, y el patrón se resuelve aquí al importar porque el
# middleware lo compila una sola vez. Es seguro hacerlo así porque el launcher
# declara el modo **antes** de arrancar el proceso, que es cuando esto se lee; la
# comprobación de origen de `security.py` —la que corta la petición con 403—
# vuelve a consultar `lan_mode()` en cada llamada, sin cachear.
def cors_origin_regex(env: dict[str, str] | None = None) -> str:
    """Patrón de orígenes para `CORSMiddleware` según el modo declarado.

    Existe como función (y no solo como constante) para que el modo LAN sea
    comprobable sin recargar módulos, y para que el candado de deriva pueda
    comparar esta política con la de `security.origin_allowed` sobre los mismos
    orígenes: las dos mitades tienen que decir lo mismo.
    """
    if lan_mode(env):
        return f"^({LAN_ORIGIN_REGEX}|{LOCAL_ORIGIN_REGEX})$"
    return f"^{LOCAL_ORIGIN_REGEX}$"


ALLOWED_ORIGIN_REGEX = cors_origin_regex()

# Límites de payload para evitar abusos de RAM/CPU/contexto.
MAX_CHAT_MESSAGES = 100
MAX_CONTENT_CHARS = 8000
MAX_TTS_CHARS = 4000
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_AUDIO_DURATION_SECONDS = 120.0  # duración máxima aceptada por grabación

# PIN de administración local (V1.37). V3.21 (V20-09): el comportamiento es
# FAIL-CLOSED: si está vacío, los endpoints de administración de la biblioteca
# de audio quedan DESHABILITADOS (401 `Administración deshabilitada`); si se
# define, exigen la cabecera `X-Admin-Pin`. Sin OAuth/cloud: es un candado
# local para separar el rol `student` (aprender) del rol `admin` (gestionar
# audio, copias y, desde V3.77, perfiles).
#
# V3.77: la constante deja de ser el **único** sitio del que puede salir el PIN
# y pasa a ser el valor por defecto, porque hasta ahora no había **ninguna**
# forma de fijarlo en el producto y la administración estaba deshabilitada de
# facto (una honestidad declarada en `agentes/v371-runtime-offline-instalacion.md`).
# El lanzador es quien lo declara (`ENGLISH_TUTOR_ADMIN_PIN` en el entorno del
# backend que él mismo arranca) y quien lo usa en sus llamadas. La precedencia
# es: entorno > constante, y se resuelve **en cada llamada**, no al importar
# (misma doctrina que `lan_mode()`: una decisión de entorno no se cachea al
# importar un módulo).
ADMIN_PIN = ""
ADMIN_PIN_ENV = "ENGLISH_TUTOR_ADMIN_PIN"


def admin_pin(env: dict[str, str] | None = None) -> str:
    """PIN de administración vigente (`""` = administración deshabilitada)."""
    source = os.environ if env is None else env
    value = source.get(ADMIN_PIN_ENV)
    if value is not None:
        return value.strip()
    # El global se lee en cada llamada a propósito: así un test puede seguir
    # haciendo `monkeypatch.setattr(config, "ADMIN_PIN", ...)` sin ceremonia.
    return str(ADMIN_PIN).strip()


# Hosts desde los que se acepta administración de PERFILES (V3.77). No es una
# lista de IPs permitidas en el sentido de la red: es «el lanzador, que corre en
# este equipo». La administración de perfiles crea, desactiva y **purga** la
# evidencia de un alumno, así que no se sirve a la LAN ni con el PIN correcto: el
# PIN viaja en una cabecera y en una red compartida eso es material expuesto.
#
# `testclient` está en la lista a propósito y no debilita nada: es el nombre de
# cliente del `TestClient` de Starlette, **no** una IP ni un nombre resolvable
# desde una conexión real, así que ningún cliente de red puede presentarlo. Lo
# que permite es que la suite ejerza el camino verdadero en vez de un atajo.
ADMIN_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def is_admin_loopback_host(host: str | None) -> bool:
    """¿La petición llega desde el propio equipo? (fail-closed: `None` no)."""
    return str(host or "").strip().lower() in ADMIN_LOOPBACK_HOSTS


# --- Correo saliente (V3.81, verificación de email opcional) -------------------
# La verificación de email es una **señal**, no un muro: el producto es local y
# puede no tener SMTP. Sin configurar, `services/mailer.py` no envía nada y la app
# sigue funcionando igual —el webmaster sella la verificación a mano desde la
# consola de gestión—. Eso es el «híbrido» que se decidió para esta fase.
#
# La configuración no secreta la declara el lanzador en el entorno del backend que
# él mismo arranca (mismo canal que `ENGLISH_TUTOR_ADMIN_PIN`); la **contraseña**
# del SMTP no viaja por el entorno ni por el JSON del lanzador: vive en
# `data/mail.secret`, en la misma familia que `session.secret` y por tanto fuera
# de las copias (`services/backup.py::_NON_PORTABLE_TOP_NAMES`).
SMTP_HOST_ENV = "ENGLISH_TUTOR_SMTP_HOST"
SMTP_PORT_ENV = "ENGLISH_TUTOR_SMTP_PORT"
SMTP_USER_ENV = "ENGLISH_TUTOR_SMTP_USER"
SMTP_FROM_ENV = "ENGLISH_TUTOR_SMTP_FROM"
SMTP_SECRET_NAME = "mail.secret"

# Puerto por defecto: 587 (SUBMISSION con STARTTLS) es el que usan los proveedores
# normales; el 465 implícito se soporta poniéndolo a mano, que es la razón de
# exponer el puerto en vez de fijarlo.
DEFAULT_SMTP_PORT = 587


def smtp_settings(env: dict[str, str] | None = None) -> dict:
    """Config del SMTP (`configured` falso mientras no haya host y remitente).

    Se resuelve **en cada llamada**, no al importar: una decisión de entorno no se
    cachea (misma doctrina que `lan_mode()` y `admin_pin()`), y así el webmaster
    puede configurar el correo sin reiniciar el backend.
    """
    source = os.environ if env is None else env
    host = (source.get(SMTP_HOST_ENV) or "").strip()
    user = (source.get(SMTP_USER_ENV) or "").strip()
    sender = (source.get(SMTP_FROM_ENV) or "").strip() or user
    raw_port = (source.get(SMTP_PORT_ENV) or "").strip()
    try:
        port = int(raw_port) if raw_port else DEFAULT_SMTP_PORT
    except ValueError:
        port = DEFAULT_SMTP_PORT
    return {
        "host": host,
        "port": port,
        "user": user,
        "sender": sender,
        # Sin host o sin remitente no hay envío posible: es la única condición que
        # se exige, y por eso `configured` es derivado y no un campo aparte.
        "configured": bool(host and sender),
    }


# V3.77: topes de las solicitudes de perfil. Son la valla de un endpoint que
# responde **sin sesión** (quien pide un perfil aún no tiene ninguno), así que
# sin ellos la cola de pendientes sería un sumidero de disco y una tarea
# molesta para el webmaster en vez de una petición legible. El cupo por minuto y
# por IP **no** se declara aquí: vive en `security._PATH_LIMITS`, que es el único
# sitio donde el rate limiting se decide (una sola fuente de verdad).
PROFILE_REQUEST_MAX_PENDING = 20
PROFILE_REQUEST_NOTE_MAX = 200
PROFILE_REQUEST_NAME_MAX = 80

SYSTEM_PROMPT = (
    "You are a friendly, patient English tutor. Help the user practice English: "
    "converse naturally, correct mistakes gently, and explain briefly. "
    "If the user writes in Spanish, you may switch to Spanish to explain grammar, "
    "but always bring the conversation back to English practice."
)

# Rutas de modelos de voz (descargados una sola vez; ver download_models.py).
MODELS_DIR = Path(__file__).resolve().parent / "models"
WHISPER_DIR = MODELS_DIR / "whisper"
WHISPER_SIZE = "small"
PIPER_DIR = MODELS_DIR / "piper"
PIPER_VOICE = "en_US-lessac-medium"
# V3.45 (Traductor de viaje): voz española por defecto. Antes, `language="es"`
# caía en silencio a una voz inglesa porque no había ninguna `es_*` instalada;
# esta es la voz que se instala/auto-descarga para el idioma español.
SPANISH_VOICE = "es_ES-davefx-medium"
# Voz por defecto de cada idioma soportado por `/api/tts` (`resolve_voice`).
DEFAULT_VOICES: dict[str, str] = {"en": PIPER_VOICE, "es": SPANISH_VOICE}

# Persistencia local (SQLite).
DATA_DIR = Path(__file__).resolve().parent / "data"

# V3.72: TLS autofirmado para servir la UI y la API por HTTPS en la LAN.
# HTTPS es requisito de producto, no cosmético: sin *secure context* el navegador
# no expone `navigator.mediaDevices` y se rompe `getUserMedia` (micrófono) desde
# cualquier equipo que no sea el propio host. El certificado se genera una sola
# vez con `scripts/ensure_tls_cert.py` y NO se versiona (`backend/data/` está
# ignorado): es un artefacto de máquina.
CERTS_DIR = DATA_DIR / "certs"
TLS_CERT_PATH = CERTS_DIR / "cert.pem"
TLS_KEY_PATH = CERTS_DIR / "key.pem"
# Nombre público alternativo de la app en la LAN (coincide con el que usaba el
# certificado del dev server de Vite, para que no cambien las URLs anunciadas).
TLS_ALT_HOSTNAME = "english-tutor.local"

# Modos de tutor (M4). Cada modo define su propio system prompt.
DEFAULT_MODE = "conversation"

MODE_PROMPTS: dict[str, str] = {
    "conversation": (
        "You are a friendly, patient English tutor. Help the user practice English: "
        "converse naturally, correct mistakes gently, and explain briefly. "
        "If the user writes in Spanish, you may switch to Spanish to explain grammar, "
        "but always bring the conversation back to English practice."
    ),
    "grammar": (
        "You are an English grammar coach. The user will write sentences. "
        "Correct any grammar mistakes, explain the rule briefly, and give the "
        "corrected sentence. Use Spanish for explanations when helpful, but always "
        "provide the corrected sentence in English."
    ),
    "exercises": (
        "You are an English teacher who creates exercises. Ask the user what topic or "
        "level they want, then generate a short exercise (fill-in-the-blank, "
        "vocabulary, or a short translation) and give feedback on their answers. Keep "
        "exercises short and focused."
    ),
    "pronunciation": (
        "You are an English pronunciation coach. Guide the user on how to "
        "pronounce words and sentences correctly: explain difficult sounds, "
        "stress, and intonation. Provide phonetic hints and tips. Use Spanish for "
        "explanations when helpful."
    ),
}

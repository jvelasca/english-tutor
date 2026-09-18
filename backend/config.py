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


VERSION = "3.74.0"

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
# local para separar el rol `student` (aprender) del `admin` (gestionar audio).
ADMIN_PIN = ""

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

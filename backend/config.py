"""Configuración del backend (sin lógica)."""
from __future__ import annotations

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


VERSION = "3.47.0"

# Orígenes permitidos para CORS (frontend de desarrollo local).
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Regex adicional para permitir el acceso desde cualquier equipo de la red local
# (IPs privadas IPv4, por el puerto que sea) sin abrir CORS a dominios arbitrarios.
# La app es 100% local y se sirve en la LAN, así que aceptamos localhost + IPs.
ALLOWED_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|"
    r"(10\.\d{1,3}\.\d{1,3}\.\d{1,3})|"
    r"(192\.168\.\d{1,3}\.\d{1,3})|"
    r"(172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    r")(:\d+)?$"
)

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

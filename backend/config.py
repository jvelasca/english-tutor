"""Configuración del backend (sin lógica)."""
from __future__ import annotations

from pathlib import Path

DEFAULT_MODEL = "qwen3.5:9b"

# Orígenes permitidos para CORS (solo el frontend de desarrollo local).
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Límites de payload para evitar abusos de RAM/CPU/contexto.
MAX_CHAT_MESSAGES = 100
MAX_CONTENT_CHARS = 8000
MAX_TTS_CHARS = 4000
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB

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

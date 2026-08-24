"""Transcripción de voz a texto (faster-whisper, CPU)."""
from __future__ import annotations

import io
import threading

from faster_whisper import WhisperModel

from config import WHISPER_DIR, WHISPER_SIZE

_lock = threading.Lock()
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = WhisperModel(
                    WHISPER_SIZE,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(WHISPER_DIR),
                )
    return _model


def transcribe_with_timing(audio_bytes: bytes, language: str = "en") -> dict:
    """Convierte audio a texto y devuelve también la duración en segundos.

    Bloqueante: ejecutar en un threadpool.
    """
    model = _get_model()
    segments, info = model.transcribe(
        io.BytesIO(audio_bytes), language=language, beam_size=5
    )
    text = "".join(segment.text for segment in segments).strip()
    duration = round(info.duration, 2) if info.duration else 0.0
    return {"text": text, "duration": duration}


def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """Convierte audio (WAV/WebM) a texto. Bloqueante: ejecutar en un threadpool."""
    return transcribe_with_timing(audio_bytes, language)["text"]


def is_ready() -> bool:
    """True si el modelo Whisper está descargado (directorio no vacío)."""
    try:
        return WHISPER_DIR.exists() and any(WHISPER_DIR.iterdir())
    except OSError:
        return False

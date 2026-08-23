"""Síntesis de texto a voz (piper-tts, CPU)."""
from __future__ import annotations

import io
import threading
import wave

from piper import PiperVoice

from config import PIPER_DIR, PIPER_VOICE

_lock = threading.Lock()
_voice: PiperVoice | None = None


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        with _lock:
            if _voice is None:
                model_path = PIPER_DIR / f"{PIPER_VOICE}.onnx"
                config_path = PIPER_DIR / f"{PIPER_VOICE}.onnx.json"
                _voice = PiperVoice.load(
                    str(model_path), str(config_path), use_cuda=False
                )
    return _voice


def synthesize(text: str) -> bytes:
    """Devuelve audio WAV en memoria. Bloqueante: ejecutar en un threadpool."""
    voice = _get_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buf.getvalue()

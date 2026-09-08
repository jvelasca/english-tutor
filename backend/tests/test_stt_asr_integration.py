"""Integración opt-in del pipeline ASR con el modelo Whisper local (V3.22).

Solo se ejecuta si el modelo whisper (`config.WHISPER_SIZE` en `WHISPER_DIR`)
está descargado (`services.stt.is_ready()`); en CI sin modelo se omite con
`skip`. La "voz limpia" se sintetiza con piper-tts si está instalada
(`services.tts.is_ready()`); si no, el test de voz se omite también.

Aserciones tolerantes a propósito (no flakiness): se verifica la señal ASR
agregada, no la transcripción palabra a palabra.
"""
import io
import wave

import pytest

from services.stt import (
    ASR_NO_SPEECH,
    ASR_OK,
    ASR_UNINTELLIGIBLE,
    is_ready,
    transcribe_with_timing,
)

pytestmark = pytest.mark.skipif(
    not is_ready(), reason="Modelo Whisper no descargado: integración ASR opt-in"
)


def _wav_pcm(frames: bytes, rate: int = 16000) -> bytes:
    """Envuelve muestras PCM mono 16-bit en un WAV válido."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return buf.getvalue()


def _silence_wav(seconds: float, rate: int = 16000) -> bytes:
    return _wav_pcm(b"\x00\x00" * int(rate * seconds), rate=rate)


def test_silence_is_never_ok():
    """Silencio digital de ~2.5 s: no hay habla -> no_speech (o unintelligible),
    nunca `ok` (no se debe puntuar como fallo lingüístico). Whisper puede
    alucinar un segmento corto sobre el silencio; la agregación debe detectarlo
    por la marca de no-habla y seguir sin penalizar."""
    result = transcribe_with_timing(_silence_wav(2.5))
    assert result["asr_status"] in (ASR_NO_SPEECH, ASR_UNINTELLIGIBLE)
    assert result["asr_status"] != ASR_OK
    assert (result["duration"] or 0.0) >= 2.0


def test_clean_synthesized_voice_is_ok():
    """Voz limpia sintetizada (si piper está instalada): texto no vacío y la
    señal ASR es fiable (`ok`)."""
    from services.tts import is_ready as tts_ready
    from services.tts import synthesize

    if not tts_ready():
        pytest.skip("Voz piper no instalada: no hay audio limpio para el test")
    audio = synthesize("The quick brown fox jumps over the lazy dog.")
    result = transcribe_with_timing(audio)
    assert result["text"].strip(), "La voz limpia no produjo transcripción"
    assert result["asr_status"] == ASR_OK
    assert result["mean_logprob"] is not None
    assert result["segment_count"] >= 1

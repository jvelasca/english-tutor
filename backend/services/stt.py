"""Transcripción de voz a texto (faster-whisper, CPU)."""
from __future__ import annotations

import io
import math
import threading

from faster_whisper import WhisperModel

from config import MAX_AUDIO_DURATION_SECONDS, WHISPER_DIR, WHISPER_SIZE

_lock = threading.Lock()
_model: WhisperModel | None = None

# V3.21 (V20-14/V20-15): umbrales de la taxonomía ASR. Se mantienen como
# constantes para que la clasificación sea determinista y auditable.
# `no_speech_prob >= NO_SPEECH_PROB_THRESHOLD` con transcripción vacía indica
# que el modelo cree que no había habla (silencio/ruido de fondo).
NO_SPEECH_PROB_THRESHOLD = 0.6
# `avg_logprob` medio por token por debajo de LOW_LOGPROB_THRESHOLD indica una
# transcripción poco fiable (audio ilegible, otro idioma, mala captura).
LOW_LOGPROB_THRESHOLD = -1.0

# Estados ASR devueltos en `transcribe_with_timing` (V3.21):
# - "ok":              transcripción fiable; se puede puntuar lingüísticamente.
# - "no_speech":       no había habla (silencio o ruido): NO es un fallo del alumno.
# - "unintelligible":  había audio pero no se reconoció habla clara.
# - "low_confidence":  hay texto pero la confianza del ASR es baja.
ASR_OK = "ok"
ASR_NO_SPEECH = "no_speech"
ASR_UNINTELLIGIBLE = "unintelligible"
ASR_LOW_CONFIDENCE = "low_confidence"


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


def classify_asr_status(
    *,
    text: str,
    avg_logprob: float | None,
    no_speech_prob: float | None,
) -> str:
    """Clasifica el estado de reconocimiento de un intento por voz (V3.21).

    Puro y determinista. Distingue un fallo del ASR (silencio, audio ilegible o
    confianza baja) de un fallo lingüístico del alumno, para que la evaluación no
    penalice al alumno cuando el audio no se pudo reconocer.

    - Sin texto y `no_speech_prob` alto -> `no_speech`.
    - Sin texto y sin marca clara de no-habla -> `unintelligible`.
    - Con texto pero `avg_logprob` muy bajo -> `low_confidence`.
    - En cualquier otro caso -> `ok`.
    """
    stripped = (text or "").strip()
    if not stripped:
        if no_speech_prob is not None and no_speech_prob >= NO_SPEECH_PROB_THRESHOLD:
            return ASR_NO_SPEECH
        return ASR_UNINTELLIGIBLE
    if avg_logprob is not None and avg_logprob < LOW_LOGPROB_THRESHOLD:
        return ASR_LOW_CONFIDENCE
    return ASR_OK


def _asr_confidence(avg_logprob: float | None) -> float | None:
    """Confianza ASR 0..1 aproximada a partir de `avg_logprob`.

    faster-whisper expone `avg_logprob` (log-verosimilitud media por token,
    típicamente en [-2.0, 0]); su exponencial es una probabilidad media por
    token razonable. None si el modelo no la reporta."""
    if avg_logprob is None or not math.isfinite(avg_logprob):
        return None
    return round(min(1.0, max(0.0, math.exp(avg_logprob))), 3)


def exceeds_max_duration(duration_seconds: float | None) -> bool:
    """V3.21 (V20-13): red de seguridad de duración.

    True si la duración medida del audio supera `MAX_AUDIO_DURATION_SECONDS`
    (120 s). Puro y determinista: permite a los endpoints puntuados rechazar con
    400 un audio excesivamente largo tras el STT, cubriendo webm/opus que no se
    pueden medir por probing antes de transcribir. `None` (duración no medida o
    fake en tests) nunca se considera excedida."""
    return (
        duration_seconds is not None
        and duration_seconds > MAX_AUDIO_DURATION_SECONDS
    )


def transcribe_with_timing(audio_bytes: bytes, language: str = "en") -> dict:
    """Convierte audio a texto y devuelve duración + metadatos ASR (V3.21).

    Devuelve `{text, duration, asr_status, confidence, avg_logprob,
    no_speech_prob, language_probability}`. `asr_status` y `confidence`
    permiten distinguir un fallo de reconocimiento (V20-14/V20-15) de un fallo
    lingüístico del alumno: la UI no debe marcar en rojo ni penalizar cuando
    `asr_status != "ok"`.

    Bloqueante: ejecutar en un threadpool. Retrocompatible: los consumidores que
    solo usan `text`/`duration` siguen funcionando.
    """
    model = _get_model()
    segments, info = model.transcribe(
        io.BytesIO(audio_bytes), language=language, beam_size=5
    )
    text = "".join(segment.text for segment in segments).strip()
    duration = round(info.duration, 2) if info.duration else 0.0
    # Metadatos de confianza del ASR (faster-whisper los expone de forma
    # acumulada en `info`). `getattr` con valor por defecto: versiones o
    # backends pueden no reportar alguno de ellos.
    avg_logprob = getattr(info, "avg_logprob", None)
    no_speech_prob = getattr(info, "no_speech_prob", None)
    language_probability = getattr(info, "language_probability", None)
    asr_status = classify_asr_status(
        text=text, avg_logprob=avg_logprob, no_speech_prob=no_speech_prob
    )
    return {
        "text": text,
        "duration": duration,
        "asr_status": asr_status,
        "confidence": _asr_confidence(avg_logprob),
        "avg_logprob": avg_logprob,
        "no_speech_prob": no_speech_prob,
        "language_probability": language_probability,
    }


def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """Convierte audio (WAV/WebM) a texto. Bloqueante: ejecutar en un threadpool."""
    return transcribe_with_timing(audio_bytes, language)["text"]


def is_ready() -> bool:
    """True si el modelo Whisper está descargado (directorio no vacío)."""
    try:
        return WHISPER_DIR.exists() and any(WHISPER_DIR.iterdir())
    except OSError:
        return False

"""Transcripción de voz a texto (faster-whisper, CPU)."""
from __future__ import annotations

import io
import math
import threading

from faster_whisper import WhisperModel

from config import MAX_AUDIO_DURATION_SECONDS, WHISPER_DIR, WHISPER_SIZE

_lock = threading.Lock()
_model: WhisperModel | None = None

# V3.21 (V20-14/V20-15) / V3.22 (ASR-01): umbrales de la taxonomía ASR. Se
# mantienen como constantes para que la clasificación sea determinista y
# auditable.
# `no_speech_prob >= NO_SPEECH_PROB_THRESHOLD` marca una ventana que el modelo
# cree sin habla: con transcripción vacía (0 segmentos emitidos) el audio se
# clasifica como silencio/ruido (`no_speech`); con texto decodificado pese a la
# marca, el texto es una alucinación de Whisper sobre no-habla y NO se acredita
# como producción.
NO_SPEECH_PROB_THRESHOLD = 0.6
# `avg_logprob` medio por token por debajo de LOW_LOGPROB_THRESHOLD indica una
# transcripción poco fiable (audio ilegible, otro idioma, mala captura).
LOW_LOGPROB_THRESHOLD = -1.0
# V3.22 (ASR-01): duración mínima (s) de un intento para poder declarar
# "no_speech". Un audio más corto no da señal suficiente para distinguir
# silencio real de una captura fallida (micrófono no abierto, permiso
# denegado, corte prematuro): en ese rango el estado es "unintelligible".
MIN_SPEECH_ATTEMPT_SECONDS = 0.5
# V3.22 (ASR-01): fracción mínima de la señal decodificada marcada como
# no-habla (`no_speech_ratio`) para tratar el texto presente como alucinación
# sobre silencio/ruido en lugar de habla real.
NO_SPEECH_RATIO_HALLUCINATION_THRESHOLD = 0.5

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


def _seg_duration(segment) -> float:
    """Duración (s) de un segmento de Whisper (duck-typed, nunca lanza)."""
    try:
        start = float(segment.start)
        end = float(segment.end)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, end - start)


def _float_or_none(value) -> float | None:
    """Convierte a float acotando errores de tipo/valor; None si no es numérico."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, ndigits: int = 4) -> float | None:
    """Redondeo defensivo para serialización estable; None pasa como None."""
    if value is None or not math.isfinite(value):
        return None
    return round(value, ndigits)


def aggregate_asr_segments(segments, info=None) -> dict:
    """Agrega las métricas ASR de los `Segment` en un dict de señales (V3.22).

    faster-whisper expone `avg_logprob`, `no_speech_prob` y `compression_ratio`
    por **Segment**, no en `TranscriptionInfo` (que solo reporta
    `language_probability`, `duration`, etc.). Esta función materializa los
    segmentos y calcula señales agregadas:

    - `mean_logprob` / `min_logprob`: log-verosimilitud media por token,
      ponderada por duración de segmento, y mínima entre segmentos.
    - `max_no_speech_prob`: máximo `no_speech_prob` entre segmentos.
    - `no_speech_ratio`: fracción de la duración de los segmentos clasificada
      como no-habla (`no_speech_prob >= NO_SPEECH_PROB_THRESHOLD`).
    - `speech_ratio`: duración de los segmentos / duración total del audio.
    - `compression_ratio`: media por segmento (señal de alucinación).
    - `segment_count`, `language_probability` (de `info`) y `duration`.

    Duck-typed: acepta cualquier iterable de objetos con
    `.start/.end/.avg_logprob/.no_speech_prob/.compression_ratio` y un `info`
    con `.duration`/`.language_probability` (los tests usan fakes ligeros).
    Sin segmentos devuelve `segment_count=0` y el resto de señales en None
    salvo `language_probability`/`duration` si `info` los reporta.
    """
    segments = list(segments)
    duration = _float_or_none(getattr(info, "duration", None)) if info else None
    language_probability = (
        _float_or_none(getattr(info, "language_probability", None))
        if info
        else None
    )
    if not segments:
        return {
            "duration": _round(duration, 2),
            "language_probability": language_probability,
            "segment_count": 0,
            "mean_logprob": None,
            "min_logprob": None,
            "max_no_speech_prob": None,
            "no_speech_ratio": None,
            "speech_ratio": None,
            "compression_ratio": None,
        }
    total_dur = 0.0
    weighted_logprob = 0.0
    logprobs: list[float] = []
    no_speech_dur = 0.0
    max_no_speech_prob = 0.0
    has_no_speech_prob = False
    compression_values: list[float] = []
    for segment in segments:
        dur = _seg_duration(segment)
        total_dur += dur
        logprob = _float_or_none(getattr(segment, "avg_logprob", None))
        if logprob is not None:
            weighted_logprob += dur * logprob
            logprobs.append(logprob)
        no_speech_prob = _float_or_none(getattr(segment, "no_speech_prob", None))
        if no_speech_prob is not None:
            has_no_speech_prob = True
            max_no_speech_prob = max(max_no_speech_prob, no_speech_prob)
            if no_speech_prob >= NO_SPEECH_PROB_THRESHOLD:
                no_speech_dur += dur
        compression = _float_or_none(getattr(segment, "compression_ratio", None))
        if compression is not None:
            compression_values.append(compression)
    # Media ponderada por duración de segmento; si ningún segmento aporta
    # duración (>0, típico de fakes en tests), media simple como respaldo.
    if logprobs:
        mean_logprob = (
            weighted_logprob / total_dur
            if total_dur > 0
            else sum(logprobs) / len(logprobs)
        )
        min_logprob = min(logprobs)
    else:
        mean_logprob = None
        min_logprob = None
    return {
        "duration": _round(duration, 2),
        "language_probability": language_probability,
        "segment_count": len(segments),
        "mean_logprob": _round(mean_logprob),
        "min_logprob": _round(min_logprob),
        "max_no_speech_prob": _round(max_no_speech_prob)
        if has_no_speech_prob
        else None,
        "no_speech_ratio": _round(no_speech_dur / total_dur)
        if total_dur > 0
        else None,
        "speech_ratio": _round(min(1.0, total_dur / duration))
        if (duration is not None and duration > 0)
        else None,
        "compression_ratio": _round(sum(compression_values) / len(compression_values))
        if compression_values
        else None,
    }


def classify_asr_status(*, text: str, metrics: dict) -> str:
    """Clasifica el estado de reconocimiento de un intento por voz (V3.22).

    Puro y determinista. Distingue un fallo del ASR (silencio, audio ilegible o
    confianza baja) de un fallo lingüístico del alumno, para que la evaluación no
    penalice al alumno cuando el audio no se pudo reconocer.

    `metrics` es el dict devuelto por `aggregate_asr_segments`. Política:

    - Sin texto:
      - `segment_count == 0` y audio < `MIN_SPEECH_ATTEMPT_SECONDS` (o sin
        duración medida) -> `unintelligible`: intento casi vacío o captura
        fallida, no hay señal para distinguir silencio.
      - `segment_count == 0` y audio >= umbral -> `no_speech`: Whisper
        descartó todo el audio como no-habla (silencio o ruido).
      - `segment_count > 0` sin texto -> `unintelligible` (defensivo).
    - Con texto:
      - El grueso de la señal decodificada está marcado como no-habla
        (`max_no_speech_prob` alto y `no_speech_ratio` >= umbral de
        alucinación): el texto es una alucinación de Whisper sobre
        silencio/ruido, no habla real -> `no_speech`. Se evalúa ANTES que la
        confianza baja (V3.23, P1-03): un texto alucinado sobre silencio con
        `avg_logprob` bajo sigue siendo no-habla y nunca se penaliza al alumno
        por algo que no se oyó.
      - `mean_logprob` muy bajo (sin predominio de no-habla) -> `low_confidence`
        (hay habla pero la confianza agregada es insuficiente).
      - En cualquier otro caso -> `ok`.
    """
    stripped = (text or "").strip()
    segment_count = int(metrics.get("segment_count") or 0)
    if not stripped:
        if segment_count == 0:
            duration = metrics.get("duration")
            if duration is None or duration < MIN_SPEECH_ATTEMPT_SECONDS:
                return ASR_UNINTELLIGIBLE
            return ASR_NO_SPEECH
        return ASR_UNINTELLIGIBLE
    # V3.23 (P1-03): la alucinación sobre no-habla se evalúa ANTES que la
    # confianza baja. Whisper puede decodificar texto inventado sobre silencio
    # con `avg_logprob` bajo; ese texto no es producción del alumno y debe ser
    # `no_speech`, nunca `low_confidence` (regla: silencio no penaliza).
    max_no_speech_prob = metrics.get("max_no_speech_prob")
    no_speech_ratio = metrics.get("no_speech_ratio")
    if (
        max_no_speech_prob is not None
        and max_no_speech_prob >= NO_SPEECH_PROB_THRESHOLD
        and no_speech_ratio is not None
        and no_speech_ratio >= NO_SPEECH_RATIO_HALLUCINATION_THRESHOLD
    ):
        return ASR_NO_SPEECH
    mean_logprob = metrics.get("mean_logprob")
    if mean_logprob is not None and mean_logprob < LOW_LOGPROB_THRESHOLD:
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
    """Convierte audio a texto y devuelve duración + metadatos ASR (V3.21/V3.22).

    Devuelve `{text, duration, asr_status, confidence, avg_logprob,
    no_speech_prob, language_probability}` más telemetría de segmentos (V3.22):
    `segment_count, mean_logprob, min_logprob, max_no_speech_prob,
    no_speech_ratio, speech_ratio, compression_ratio`. `asr_status` y
    `confidence` permiten distinguir un fallo de reconocimiento (V20-14/V20-15)
    de un fallo lingüístico del alumno: la UI no debe marcar en rojo ni
    penalizar cuando `asr_status != "ok"`.

    Las métricas de confianza se leen de los **Segment** (faster-whisper las
    expone por segmento, no en `TranscriptionInfo`) y se agregan con
    `aggregate_asr_segments`; la clasificación usa esas señales agregadas
    (`classify_asr_status`). Retrocompatible: los consumidores que solo usan
    `text`/`duration`/`asr_status` siguen funcionando.

    Bloqueante: ejecutar en un threadpool.
    """
    model = _get_model()
    segments_gen, info = model.transcribe(
        io.BytesIO(audio_bytes), language=language, beam_size=5
    )
    # V3.22 (ASR-01): materializar los segmentos es obligatorio: sin list()
    # no se pueden leer `avg_logprob`/`no_speech_prob`/`compression_ratio`,
    # que viven en cada Segment y no en `info`.
    segments = list(segments_gen)
    text = "".join(segment.text for segment in segments).strip()
    duration = round(info.duration, 2) if info.duration else 0.0
    metrics = aggregate_asr_segments(segments, info)
    asr_status = classify_asr_status(text=text, metrics=metrics)
    mean_logprob = metrics["mean_logprob"]
    return {
        "text": text,
        "duration": duration,
        "asr_status": asr_status,
        "confidence": _asr_confidence(mean_logprob),
        # Aliases retrocompatibles con V3.21 (agregados de los segmentos).
        "avg_logprob": mean_logprob,
        "no_speech_prob": metrics["max_no_speech_prob"],
        "language_probability": metrics["language_probability"],
        # Telemetría V3.22 (señal para el Student Model; no clasifica aún).
        "segment_count": metrics["segment_count"],
        "mean_logprob": mean_logprob,
        "min_logprob": metrics["min_logprob"],
        "max_no_speech_prob": metrics["max_no_speech_prob"],
        "no_speech_ratio": metrics["no_speech_ratio"],
        "speech_ratio": metrics["speech_ratio"],
        "compression_ratio": metrics["compression_ratio"],
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

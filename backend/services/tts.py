"""Síntesis de texto a voz (piper-tts, CPU) con soporte multi-voz.

Históricamente la voz era única (`config.PIPER_VOICE`, instancia global cargada
una vez). Ahora la app admite varias voces Piper instaladas en `PIPER_DIR`
(Configuración → Voces): cada usuario guarda su preferencia (`tts_voice`) y el
TTS resuelve la voz instalada o cae al default (`config.PIPER_VOICE`) sin romper.

Invariante de cache de listening: la voz forma parte del path de cache
(`DATA_DIR/listening/{bank}/{voice}/…`), de modo que cambiar de voz no invalida
los WAV de la voz anterior; los nuevos se sintetizan bajo demanda.
"""
from __future__ import annotations

import io
import logging
import threading
import time
import wave

from piper import PiperVoice
from piper.config import SynthesisConfig

from config import DEFAULT_VOICES, PIPER_DIR, PIPER_VOICE

logger = logging.getLogger(__name__)

DEFAULT_VOICE = PIPER_VOICE

# Etiquetas amigables para las voces oficiales más comunes de Piper (inglés).
# Los ids no listados se presentan con su nombre derivado del propio id.
VOICE_LABELS: dict[str, str] = {
    "en_US-lessac-medium": "American English · Lessac (default)",
    "en_US-lessac-high": "American English · Lessac (high)",
    "en_US-amy-medium": "American English · Amy",
    "en_US-amy-high": "American English · Amy (high)",
    "en_US-kristin-medium": "American English · Kristin",
    "en_US-ryan-high": "American English · Ryan (high)",
    "en_GB-alan-medium": "British English · Alan",
    "en_GB-alba-medium": "Northern English · Alba",
    "en_GB-cori-medium": "Scottish English · Cori",
    "en_GB-northern_english_male-medium": "Northern English · Male",
    "en_GB-southern_english_female-medium": "Southern English · Female",
    "en_GB-jenny_dioco-medium": "British English · Jenny (dioco)",
    # V3.39 (Fase 2, Traductor): voces de español del catálogo descargable.
    "es_ES-davefx-medium": "Español (España) · DaveFX",
    "es_ES-sharvard-medium": "Español (España) · Sharvard",
    "es_MX-ald-medium": "Español (México) · Ald",
}

_lock = threading.Lock()
_voices: dict[str, PiperVoice] = {}

# V3.45: caché negativa de la auto-descarga de voces por idioma. Si un intento
# falla (sin red), no se reintenta en cada `/api/tts` durante este TTL: evita
# sumar la latencia del fallo de red a cada petición en español.
_VOICE_ENSURE_FAILED: dict[str, float] = {}
_VOICE_ENSURE_FAILED_TTL_SECONDS = 300.0


def list_voices() -> list[str]:
    """Ids de voces Piper instaladas en `PIPER_DIR` (scan de `*.onnx.json`).

    Devuelve el default primero y el resto ordenado; solo ids con su `.onnx`
    presente (voz utilizable). Vacío si no hay ninguna voz instalada.
    """
    if not PIPER_DIR.is_dir():
        return []
    installed = sorted(
        p.name.removesuffix(".onnx.json")
        for p in PIPER_DIR.glob("*.onnx.json")
        if (PIPER_DIR / f"{p.name.removesuffix('.onnx.json')}.onnx").exists()
    )
    if not installed:
        return []
    if DEFAULT_VOICE in installed:
        return [DEFAULT_VOICE] + [v for v in installed if v != DEFAULT_VOICE]
    return installed


def voice_name(voice_id: str) -> str:
    """Etiqueta legible de un id de voz (mapa conocido o nombre derivado)."""
    if voice_id in VOICE_LABELS:
        return VOICE_LABELS[voice_id]
    parts = voice_id.split("-")
    locale = parts[0] if len(parts) > 1 else voice_id
    name = parts[1] if len(parts) > 1 else ""
    quality = parts[-1] if len(parts) > 2 else ""
    label = f"{locale} · {name}"
    if quality:
        label = f"{label} ({quality})"
    return label.strip(" ·")


def _fallback_voice() -> str:
    """Voz por defecto utilizable: el default del sistema si está instalado, si no
    la primera voz instalada (si la hay), si no el default (quedará en 503)."""
    installed = list_voices()
    if DEFAULT_VOICE in installed:
        return DEFAULT_VOICE
    if installed:
        return installed[0]
    return DEFAULT_VOICE


def voice_language(voice_id: str) -> str:
    """Código de idioma de un id de voz Piper: `"en_US-lessac-medium"` → `"en"`.

    El locale va antes del primer guion (`en_US`, `es_MX`) y el idioma antes del
    guion bajo. Función pura, tolerante a ids inesperados.
    """
    locale = voice_id.split("-", 1)[0]
    return locale.split("_", 1)[0].lower()


def default_voice_for(language: str) -> str:
    """Voz por defecto del idioma (`config.DEFAULT_VOICES`), pura.

    `"en"` → `en_US-lessac-medium`, `"es"` → `es_ES-davefx-medium`; idiomas sin
    default declarado caen al default histórico (`config.PIPER_VOICE`).
    """
    lang = (language or "en").strip().lower()[:2]
    return DEFAULT_VOICES.get(lang, DEFAULT_VOICE)


def resolve_voice(prefs: dict[str, str] | None, language: str = "en") -> str:
    """Resuelve la voz preferida de un usuario frente a lo instalado y al idioma.

    Función pura. Prioridad (V3.39 Fase 2; V3.45: default por idioma):
    1. `prefs["tts_voice"]` si está instalada Y es del idioma pedido;
    2. la voz por defecto DE ESE IDIOMA (`default_voice_for`) si está instalada;
    3. la primera voz instalada de ese idioma;
    4. fallback global (default instalado o la primera instalada) — con un aviso
       implícito: si no hay ninguna voz del idioma, se sintetizará con otra, que
       es la degradación menos mala (nunca se devuelve una voz no instalada salvo
       que no haya ninguna, en cuyo caso el sistema quedará en 503).

    Con `language="en"` el comportamiento es el histórico (la preferencia del
    usuario manda y si no está se usa la voz por defecto o la primera instalada).
    """
    lang = (language or "en").strip().lower()[:2]
    installed = list_voices()
    if prefs:
        preferred = prefs.get("tts_voice")
        if (
            preferred
            and preferred in installed
            and voice_language(preferred) == lang
        ):
            return preferred
    same_language = [v for v in installed if voice_language(v) == lang]
    language_default = default_voice_for(lang)
    if language_default in same_language:
        return language_default
    if same_language:
        return same_language[0]
    return _fallback_voice()


def ensure_voice_for_language(language: str) -> bool:
    """Garantiza que hay una voz instalada del idioma (auto-descarga si falta).

    V3.45 (Traductor): evita que `language="es"` caiga en silencio a una voz
    inglesa. Si ya hay una voz del idioma, no hace nada. Si falta, descarga el
    default del idioma cuando está en el catálogo curado (`voice_downloads`).

    Devuelve `True` si ya había voz del idioma o si se descargó con éxito;
    `False` si no se pudo (sin red, disco, o default fuera del catálogo).
    NUNCA lanza: el TTS degrada al fallback en lugar de romper la petición.
    Un fallo se recuerda `_VOICE_ENSURE_FAILED_TTL_SECONDS` para no reintentar la
    descarga en cada petición.
    """
    lang = (language or "en").strip().lower()[:2]
    installed = list_voices()
    if any(voice_language(v) == lang for v in installed):
        return True
    failed_at = _VOICE_ENSURE_FAILED.get(lang)
    recently_failed = (
        failed_at is not None
        and time.monotonic() - failed_at < _VOICE_ENSURE_FAILED_TTL_SECONDS
    )
    if recently_failed:
        return False
    target = default_voice_for(lang)
    # Import local: `voice_downloads` solo hace falta en la descarga perezosa.
    from services import voice_downloads  # noqa: PLC0415

    if voice_downloads.spec_for(target) is None:
        return False
    try:
        voice_downloads.download_voice(target)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "No se pudo auto-descargar la voz %s para %s: %s", target, lang, exc
        )
        _VOICE_ENSURE_FAILED[lang] = time.monotonic()
        return False
    _VOICE_ENSURE_FAILED.pop(lang, None)
    return True


def _load_voice(voice_id: str) -> PiperVoice:
    model_path = PIPER_DIR / f"{voice_id}.onnx"
    config_path = PIPER_DIR / f"{voice_id}.onnx.json"
    return PiperVoice.load(str(model_path), str(config_path), use_cuda=False)


def _get_voice(voice_id: str | None) -> PiperVoice:
    """Instancia de una voz con caché por id (thread-safe). Cae al default."""
    name = voice_id if voice_id in list_voices() else _fallback_voice()
    cached = _voices.get(name)
    if cached is not None:
        return cached
    with _lock:
        cached = _voices.get(name)
        if cached is None:
            cached = _load_voice(name)
            _voices[name] = cached
    return cached


def synthesize(
    text: str, length_scale: float = 1.0, voice: str | None = None
) -> bytes:
    """Devuelve audio WAV en memoria. Bloqueante: ejecutar en un threadpool.

    `length_scale` controla la velocidad (Piper): < 1.0 más rápido, > 1.0 más lento.
    `voice` selecciona la voz instalada; si es None o no está instalada usa el
    default (`config.PIPER_VOICE`).
    """
    selected = _get_voice(voice)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        selected.synthesize_wav(
            text, wav_file, SynthesisConfig(length_scale=length_scale)
        )
    return buf.getvalue()


def is_ready(voice: str | None = None) -> bool:
    """True si el modelo Piper (onnx + config) de esa voz está presente.

    Con `voice=None` comprueba la voz por defecto; con una voz concreta devuelve
    False si no está instalada (no cae silenciosamente al default).
    """
    if voice is not None and voice not in list_voices():
        return False
    name = voice if voice is not None else DEFAULT_VOICE
    return (PIPER_DIR / f"{name}.onnx").exists() and (
        PIPER_DIR / f"{name}.onnx.json"
    ).exists()

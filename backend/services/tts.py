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
import threading
import wave

from piper import PiperVoice
from piper.config import SynthesisConfig

from config import PIPER_DIR, PIPER_VOICE

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
}

_lock = threading.Lock()
_voices: dict[str, PiperVoice] = {}


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


def resolve_voice(prefs: dict[str, str] | None) -> str:
    """Resuelve la voz preferida de un usuario frente a lo instalado.

    Función pura: `prefs["tts_voice"]` si está instalada; si no hay preferencia
    o no está disponible, la voz por defecto utilizable (default instalado o, si
    el default no está, la primera voz instalada). Nunca devuelve una voz no
    instalada salvo que no haya ninguna instalada (el sistema quedará en 503
    hasta instalar una).
    """
    if prefs:
        preferred = prefs.get("tts_voice")
        if preferred and preferred in list_voices():
            return preferred
    return _fallback_voice()


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

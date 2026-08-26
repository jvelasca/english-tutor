"""Manifest y resolución de la biblioteca de audio humano (grabaciones reales).

Premisa local-first: el audio humano (varios hablantes, connected speech real,
acentos reales, ruido real) es un **límite de contenido**, no de código. Este módulo
aporta la *infraestructura* que faltaba para servir esas grabaciones cuando existan:

- Un **manifest versionado** (`backend/audio_library/manifest.json`) que declara,
  para cada `audio_id`, qué archivo WAV lo respalda y sus metadatos reales
  (hablante, acento, nº de hablantes, ruido, duración, transcripción y, desde 1.1.0,
  los metadatos ampliados de la auditoría: género, banda de edad, región, velocidad,
  espontaneidad, entorno, solapamiento, connected speech, prosodia, tipo de tarea y
  CEFR).
- La **resolución** del WAV grabado a partir de un ítem de listening que declare
  `audio_type="recorded"` y un `audio_id` presente en el manifest.

Separación conceptual (espejo de `services/curriculum.py`):
- Aquí vive el contenido estático de audio grabado (qué se puede servir).
- `domain/listening.py` decide qué servir (grabado vs TTS Piper) y cachea el TTS.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, Field

# Versión del esquema/contenido del manifest de la biblioteca de audio humano.
# Independiente de la versión de la app: identifica QUÉ manifest se sirvió.
AUDIO_LIBRARY_VERSION = "1.1.0"

# Directorio de contenido de la biblioteca de audio humano (sibling de curriculum).
AUDIO_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "audio_library"

# Valores normalizados de los metadatos ampliados (auditoría P0-1). `unknown` marca
# "sin declarar"; el resto son categorías acotadas para que el futuro selector de voz
# pueda diversificar hablantes/dificultad.
Gender = Literal["female", "male", "unknown"]
AgeBand = Literal["child", "teen", "adult", "senior", "unknown"]
Spontaneity = Literal["scripted", "semi_scripted", "spontaneous"]
RecordingEnvironment = Literal["studio", "quiet_room", "noisy", "field"]
Cefr = Literal["A1", "A2", "B1", "B2", "unknown"]


class AudioLibraryEntry(BaseModel):
    """Una grabación humana real declarada en el manifest.

    `file` es la ruta relativa del WAV dentro de `AUDIO_LIBRARY_DIR`; desde 1.1.0
    puede incluir subcarpetas (p. ej. `B1/speaker_003/dialogue_shop.wav`). La
    resolución valida que no escape del directorio. El resto son metadatos auditivos
    reales que respaldan la dificultad declarada del ítem que la referencia.
    """

    audio_id: str
    file: str = Field(
        description="Ruta relativa del WAV dentro de AUDIO_LIBRARY_DIR (subcarpetas ok)"
    )
    speaker_id: str = ""
    accent: str = "neutral"
    speaker_count: int = Field(default=1, ge=1)
    noise_level: int = Field(default=0, ge=0, le=5)
    duration: float = Field(default=0.0, ge=0)
    transcript: str = ""
    gender: Gender = "unknown"
    age_band: AgeBand = "unknown"
    region: str = "unknown"
    speech_rate: float | None = None
    spontaneity: Spontaneity = "scripted"
    recording_environment: RecordingEnvironment = "studio"
    overlap: bool = False
    connected_speech: bool = False
    prosody: str = "unknown"
    task_type: str = "unknown"
    cefr: Cefr = "unknown"


class AudioLibraryManifest(BaseModel):
    """Manifest versionado de la biblioteca de audio humano."""

    version: str
    entries: list[AudioLibraryEntry] = Field(default_factory=list)


def manifest_path() -> Path:
    """Ruta del manifest (`backend/audio_library/manifest.json`)."""
    return AUDIO_LIBRARY_DIR / "manifest.json"


def library_dir() -> Path:
    """Directorio raíz de las grabaciones reales (los WAV del manifest)."""
    return AUDIO_LIBRARY_DIR


def load_manifest(path: Path | None = None) -> AudioLibraryManifest:
    """Carga y valida el manifest. Lanza `FileNotFoundError` si no existe el archivo."""
    p = path or manifest_path()
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    return AudioLibraryManifest.model_validate(data)


def entry_for(
    manifest: AudioLibraryManifest, audio_id: str
) -> AudioLibraryEntry | None:
    """Devuelve la entrada del manifest por `audio_id`, o None si no existe."""
    for entry in manifest.entries:
        if entry.audio_id == audio_id:
            return entry
    return None


def resolve_file(entry: AudioLibraryEntry, base: Path | None = None) -> Path | None:
    """Resuelve la ruta del WAV de una entrada, o None si escapa de la biblioteca.

    `entry.file` es una ruta relativa dentro de `base` (puede incluir subcarpetas,
    p. ej. `B1/speaker_003/dialogue_shop.wav`). Rechaza rutas que salgan de `base`
    (p. ej. `../`) para que un manifest malicioso o mal formado no pueda leer
    archivos arbitrarios del sistema.
    """
    base = (base or library_dir()).resolve()
    target = (base / entry.file).resolve()
    if not target.is_relative_to(base):
        return None
    return target


def is_recorded(question: dict) -> bool:
    """True si el ítem declara audio humano grabado (`audio_type="recorded"`)."""
    return (question.get("audio_type") or "tts") == "recorded"


def recorded_audio_path(question: dict) -> Path | None:
    """Ruta al WAV grabado del ítem, o None si no es grabado o no hay entrada.

    Devuelve None también cuando el ítem es `recorded` pero no tiene `audio_id`, no
    está en el manifest, o la ruta resuelta escapa de la biblioteca. En ese caso el
    llamador debe tratar el audio como no disponible (no caer a TTS).
    """
    if not is_recorded(question):
        return None
    audio_id = (question.get("audio_id") or "").strip()
    if not audio_id:
        return None
    entry = entry_for(load_manifest(), audio_id)
    if entry is None:
        return None
    return resolve_file(entry)


def library_summary(manifest: AudioLibraryManifest | None = None) -> dict:
    """Resumen del manifest (sin audio) para exponer qué grabaciones existen.

    Devuelve las entradas con sus metadatos ampliados (`entries`) y desgloses
    agregados para el futuro selector de voz: recuento por `cefr`, `speaker_id`,
    `accent` y `region`.
    """
    m = manifest or load_manifest()
    entries = [
        {
            "audio_id": e.audio_id,
            "file": e.file,
            "speaker_id": e.speaker_id,
            "accent": e.accent,
            "speaker_count": e.speaker_count,
            "noise_level": e.noise_level,
            "duration": e.duration,
            "transcript": e.transcript,
            "gender": e.gender,
            "age_band": e.age_band,
            "region": e.region,
            "speech_rate": e.speech_rate,
            "spontaneity": e.spontaneity,
            "recording_environment": e.recording_environment,
            "overlap": e.overlap,
            "connected_speech": e.connected_speech,
            "prosody": e.prosody,
            "task_type": e.task_type,
            "cefr": e.cefr,
        }
        for e in m.entries
    ]
    return {
        "entries": entries,
        "by_cefr": dict(Counter(e.cefr for e in m.entries)),
        "by_speaker_id": dict(Counter(e.speaker_id for e in m.entries)),
        "by_accent": dict(Counter(e.accent for e in m.entries)),
        "by_region": dict(Counter(e.region for e in m.entries)),
    }


def validate_manifest(manifest: AudioLibraryManifest | None = None) -> list[str]:
    """Invariantes del manifest (devuelve violaciones, vacía = ok).

    Garantiza: versión coincidente con `AUDIO_LIBRARY_VERSION`, `audio_id` únicos,
    `file` únicos y no vacíos, que cada `file` resuelve dentro de la biblioteca, y
    que los metadatos ampliados respetan sus valores normalizados (`gender`,
    `age_band`, `spontaneity`, `recording_environment`, `cefr`) y `speech_rate > 0`
    si se declara.
    """
    m = manifest or load_manifest()
    errors: list[str] = []
    if m.version != AUDIO_LIBRARY_VERSION:
        errors.append(f"version {m.version!r} != {AUDIO_LIBRARY_VERSION!r}")
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for entry in m.entries:
        if entry.audio_id in seen_ids:
            errors.append(f"duplicate audio_id: {entry.audio_id}")
        seen_ids.add(entry.audio_id)
        if entry.file in seen_files:
            errors.append(f"duplicate file: {entry.file}")
        seen_files.add(entry.file)
        if not entry.file:
            errors.append(f"{entry.audio_id}: empty file")
        elif resolve_file(entry) is None:
            errors.append(f"{entry.audio_id}: file escapes library dir")
        if entry.gender not in get_args(Gender):
            errors.append(f"{entry.audio_id}: invalid gender {entry.gender!r}")
        if entry.age_band not in get_args(AgeBand):
            errors.append(f"{entry.audio_id}: invalid age_band {entry.age_band!r}")
        if entry.spontaneity not in get_args(Spontaneity):
            errors.append(
                f"{entry.audio_id}: invalid spontaneity {entry.spontaneity!r}"
            )
        if entry.recording_environment not in get_args(RecordingEnvironment):
            errors.append(
                f"{entry.audio_id}: invalid recording_environment "
                f"{entry.recording_environment!r}"
            )
        if entry.cefr not in get_args(Cefr):
            errors.append(f"{entry.audio_id}: invalid cefr {entry.cefr!r}")
        if entry.speech_rate is not None and entry.speech_rate <= 0:
            errors.append(f"{entry.audio_id}: speech_rate must be > 0")
    return errors

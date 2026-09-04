"""Catálogo curado de voces Piper descargables (Configuración → Voces).

La descarga se hace una sola vez por voz desde el repo oficial de Piper en
Hugging Face (`rhasspy/piper-voices`). Cada voz pesa ~60 MB (calidad medium) y
se guarda como `{PIPER_DIR}/{voice_id}.onnx` + `.onnx.json`, el mismo formato
que las voces colocadas a mano; el resto de la app las detecta igual
(`services.tts.list_voices`).

El catálogo solo incluye voces *de inglés* en calidad `medium`: son las que
tienen sentido pedagógico para esta app (comprensión de acentos) sin inflar el
disco con modelos `high` (~100 MB+). Los ids no listados aquí no se ofrecen en
la UI, pero si se colocan a mano en `models/piper` se siguen detectando.
"""
from __future__ import annotations

import dataclasses
import threading
import urllib.error
import urllib.request

from config import PIPER_DIR

# Base del repo oficial de voces Piper (solo lectura, sin auth).
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"


@dataclasses.dataclass(frozen=True)
class PiperVoiceSpec:
    """Voz del catálogo curado: id técnico + etiqueta + subcarpeta en HF."""

    id: str
    name: str
    path: str  # p. ej. "en/en_GB/alan/medium"

    @property
    def size_mb(self) -> int:
        return 63  # las voces medium del catálogo rondan ~63 MB


CATALOG: list[PiperVoiceSpec] = [
    PiperVoiceSpec(
        "en_GB-alan-medium",
        "British English · Alan (male)",
        "en/en_GB/alan/medium",
    ),
    PiperVoiceSpec(
        "en_GB-alba-medium",
        "Northern English · Alba (female)",
        "en/en_GB/alba/medium",
    ),
    PiperVoiceSpec(
        "en_GB-cori-medium",
        "Scottish English · Cori (female)",
        "en/en_GB/cori/medium",
    ),
    PiperVoiceSpec(
        "en_US-amy-medium",
        "American English · Amy (female)",
        "en/en_US/amy/medium",
    ),
    PiperVoiceSpec(
        "en_US-kristin-medium",
        "American English · Kristin (female)",
        "en/en_US/kristin/medium",
    ),
    PiperVoiceSpec(
        "en_GB-northern_english_male-medium",
        "Northern English · Male",
        "en/en_GB/northern_english_male/medium",
    ),
    PiperVoiceSpec(
        "en_GB-jenny_dioco-medium",
        "British English · Jenny (dioco)",
        "en/en_GB/jenny_dioco/medium",
    ),
]

_BY_ID: dict[str, PiperVoiceSpec] = {spec.id: spec for spec in CATALOG}
_lock = threading.Lock()


def spec_for(voice_id: str) -> PiperVoiceSpec | None:
    return _BY_ID.get(voice_id)


def available_to_download(installed_ids: list[str]) -> list[PiperVoiceSpec]:
    """Especificaciones del catálogo que aún no están instaladas."""
    return [spec for spec in CATALOG if spec.id not in installed_ids]


def _url(spec: PiperVoiceSpec, suffix: str) -> str:
    return f"{_HF_BASE}{spec.path}/{spec.id}{suffix}"


def _download_file(url: str, dest, timeout: float = 300.0) -> None:
    """Descarga a un fichero temporal y lo mueve al destino (atómico).

    El temporal (`*.part`) garantiza que un fichero a medio descargar nunca se
    detecte como voz instalada ni se sirva a Piper.
    """
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)  # noqa: S310 - URL de HF fija del catálogo
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo descargar {dest.name}: {exc}") from exc
    tmp.replace(dest)


def download_voice(voice_id: str) -> None:
    """Descarga una voz del catálogo (`.onnx` + `.onnx.json`) si falta.

    Thread-safe (una descarga simultánea por voz). Lanza `ValueError` si el id no
    está en el catálogo y `RuntimeError` si la descarga falla (red, disco).
    """
    spec = _BY_ID.get(voice_id)
    if spec is None:
        raise ValueError(f"Voz desconocida en el catálogo: {voice_id}")
    with _lock:
        PIPER_DIR.mkdir(parents=True, exist_ok=True)
        for suffix in (".onnx", ".onnx.json"):
            dest = PIPER_DIR / f"{voice_id}{suffix}"
            if dest.exists() and dest.stat().st_size > 0:
                continue
            _download_file(_url(spec, suffix), dest)

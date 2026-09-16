"""Catálogo curado de voces Piper descargables (Configuración → Voces).

La descarga se hace una sola vez por voz desde el repo oficial de Piper en
Hugging Face (`rhasspy/piper-voices`). Cada voz pesa ~60 MB (calidad medium) y
se guarda como `{PIPER_DIR}/{voice_id}.onnx` + `.onnx.json`, el mismo formato
que las voces colocadas a mano; el resto de la app las detecta igual
(`services.tts.list_voices`).

El catálogo incluye voces *medium* de inglés (el núcleo pedagógico de esta app)
y, desde V3.39 (Fase 2, Traductor), voces de español para poder escuchar la
salida ES→EN y leer en voz alta el texto español. Se evitan las calidades `high`
(~100 MB+) para no inflar el disco. Los ids no listados aquí no se ofrecen en la
UI, pero si se colocan a mano en `models/piper` se siguen detectando.
"""
from __future__ import annotations

import dataclasses
import shutil
import threading
import urllib.error
import urllib.request

from config import PIPER_DIR

# Base del repo oficial de voces Piper (solo lectura, sin auth).
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"

# V3.71 (eje RD): timeout REAL de la descarga. Se aplica por OPERACIÓN de socket
# (la conexión y cada lectura), no al total, así que un valor corto **no** corta
# una descarga lenta que progresa: solo evita quedarse colgado cuando el host no
# responde. Hasta V3.70 el `timeout` se declaraba pero se pasaba a
# `urlretrieve`, que **no acepta timeout**: la descarga quedaba sin límite.
VOICE_DOWNLOAD_TIMEOUT_SECONDS = 15.0

_USER_AGENT = "english-tutor (descarga de voces Piper)"


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
    # V3.71 (eje RB): la voz INGLESA POR DEFECTO (`config.PIPER_VOICE`) tiene que
    # estar en el catálogo. No lo estaba, así que `spec_for(PIPER_VOICE)` devolvía
    # `None` y `ensure_voice_for_language("en")` salía por ahí **sin descargar**:
    # en una instalación limpia, la voz con la que la app da clase solo se podía
    # obtener por `download_models.py` (o a mano), mientras el español sí se
    # auto-descargaba. Con la voz en el catálogo, las dos vías (bootstrap y
    # descarga en caliente) usan la MISMA lista.
    PiperVoiceSpec(
        "en_US-lessac-medium",
        "American English · Lessac (default de la app)",
        "en/en_US/lessac/medium",
    ),
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
    # V3.39 (Fase 2): voces de español para el Traductor (salida EN→ES leída y
    # entrada ES leída en voz alta). Calidad medium, como el resto del catálogo.
    PiperVoiceSpec(
        "es_ES-davefx-medium",
        "Español (España) · DaveFX (masculina)",
        "es/es_ES/davefx/medium",
    ),
    PiperVoiceSpec(
        "es_ES-sharvard-medium",
        "Español (España) · Sharvard (femenina)",
        "es/es_ES/sharvard/medium",
    ),
    PiperVoiceSpec(
        "es_MX-ald-medium",
        "Español (México) · Ald (masculina)",
        "es/es_MX/ald/medium",
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


def _download_file(url: str, dest, timeout: float | None = None) -> None:
    """Descarga a un fichero temporal y lo mueve al destino (atómico).

    El temporal (`*.part`) garantiza que un fichero a medio descargar nunca se
    detecte como voz instalada ni se sirva a Piper.

    V3.71 (eje RD): el `timeout` es **real**. Hasta V3.70 se declaraba pero se
    pasaba a `urllib.request.urlretrieve`, que **no acepta timeout**, así que la
    descarga se quedaba sin límite y sin red podía colgarse indefinidamente.
    Ahora se usa `urlopen(timeout=...)`. Además se comprueba lo recibido contra
    el `Content-Length` declarado (cuando el servidor lo dice) para no aceptar
    una página de error como si fuera un `.onnx`.
    """
    if timeout is None:
        timeout = VOICE_DOWNLOAD_TIMEOUT_SECONDS
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # URL fija
            declared = resp.headers.get("Content-Length")
            with open(tmp, "wb") as fh:
                shutil.copyfileobj(resp, fh)
        written = tmp.stat().st_size
        if written == 0:
            raise OSError("descarga vacía")
        if declared is not None and int(declared) != written:
            raise OSError(f"descarga incompleta: {written} de {declared} bytes")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
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

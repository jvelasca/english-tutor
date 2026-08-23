"""Descarga los modelos de voz una sola vez (requiere internet la primera vez)."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from config import PIPER_DIR, PIPER_VOICE, WHISPER_DIR, WHISPER_SIZE

PIPER_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/lessac/medium"
)


def download_piper() -> None:
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        name = f"{PIPER_VOICE}{suffix}"
        dest = PIPER_DIR / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  {name} ya existe, omitiendo")
            continue
        url = f"{PIPER_BASE}/{name}"
        print(f"  Descargando {name}...")
        urllib.request.urlretrieve(url, dest)
        print(f"  OK {dest} ({dest.stat().st_size} bytes)")


def download_whisper() -> None:
    from faster_whisper import WhisperModel

    print("  Instanciando Whisper small (descarga si falta)...")
    WhisperModel(
        WHISPER_SIZE, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR)
    )
    print(f"  Whisper listo en {WHISPER_DIR}")


def main() -> None:
    print("Descargando voz Piper...")
    download_piper()
    print("Descargando Whisper...")
    download_whisper()
    print("Listo.")


if __name__ == "__main__":
    main()

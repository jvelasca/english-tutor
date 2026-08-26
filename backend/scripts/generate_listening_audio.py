"""Pre-renderiza el audio de referencia de todo el banco de listening.

Genera un WAV por ítem (respetando `speech_rate` → `length_scale` y la
`repetition_policy` "twice") y lo cachea en `DATA_DIR/listening/{id}.wav`, de modo
que el endpoint `/api/listening/audio/{id}` sirva el audio al instante sin
sintetizar en cada petición.

Uso:
    .venv\\Scripts\\python.exe scripts/generate_listening_audio.py [--force]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows usa cp1252 por defecto; forzamos UTF-8 para evitar UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DATA_DIR  # noqa: E402
from services import tts  # noqa: E402
from services.listening import (  # noqa: E402
    QUESTION_BANK,
    audio_text,
    length_scale_for_rate,
)

CACHE_DIR = DATA_DIR / "listening"


def spoken_text(question: dict) -> str:
    text = audio_text(question)
    if question.get("repetition_policy") == "twice":
        text = f"{text}. {text}"
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="Regenerar aunque exista el WAV"
    )
    args = parser.parse_args()

    if not tts.is_ready():
        print("Piper no está listo. Verifica PIPER_DIR y PIPER_VOICE en config.")
        return 1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    generated, skipped, errors = 0, 0, 0

    for question in QUESTION_BANK:
        path = CACHE_DIR / f"{question['id']}.wav"
        if path.exists() and not args.force:
            skipped += 1
            continue
        text = spoken_text(question)
        if not text:
            print(f"[SKIP] {question['id']}: sin texto para sintetizar")
            skipped += 1
            continue
        try:
            length_scale = length_scale_for_rate(question.get("speech_rate") or 0.0)
            data = tts.synthesize(text, length_scale)
            tmp = path.with_suffix(".wav.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            generated += 1
            print(
                f"[OK] {question['id']} "
                f"(rate={question.get('speech_rate') or 0}, "
                f"scale={length_scale}, {len(data)} bytes)"
            )
        except Exception as exc:  # noqa: BLE001 - informe por ítem, no aborta el lote
            errors += 1
            print(f"[FAIL] {question['id']}: {exc}")

    print(f"\nGenerados: {generated} · Omitidos (cache): {skipped} · Errores: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

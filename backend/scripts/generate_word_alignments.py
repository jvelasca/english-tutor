"""Backfill de sidecars `word_alignment_proxy` para la caché de audio existente.

Recorre los WAV ya pre-renderizados (`DATA_DIR/listening/{bank}/{voice}/*.wav`) y,
para cada uno, genera su sidecar `{wav}.words.json` transcribiendo el WAV con
faster-whisper (`word_timestamps=True`) y alineando contra el texto audible del
ítem que lo originó. Idempotente: si el sidecar ya existe no re-transcribe (salvo
`--force`).

Uso:
    .venv\\Scripts\\python.exe scripts/generate_word_alignments.py [--force]
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

from config import DATA_DIR, PIPER_VOICE  # noqa: E402
from services.curriculum import LISTENING_BANK_VERSION  # noqa: E402
from services.listening import QUESTION_BANK, spoken_text  # noqa: E402
from services.word_alignment_proxy import (  # noqa: E402
    ensure_word_alignment,
    sidecar_path,
)

# Cache versionado por banco + voz (igual que generate_listening_audio.py).
CACHE_DIR = DATA_DIR / "listening" / LISTENING_BANK_VERSION / PIPER_VOICE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="Regenerar aunque exista el sidecar"
    )
    args = parser.parse_args()

    # Índice ítem -> texto audible (los ítems derivados `d-` reutilizan el WAV
    # del padre, así que el texto audible a alinear es el del padre).
    text_by_id = {q["id"]: spoken_text(q) for q in QUESTION_BANK}

    if not CACHE_DIR.exists():
        print(f"No hay caché de audio en {CACHE_DIR}.")
        return 0

    wavs = sorted(CACHE_DIR.glob("*.wav"))
    if not wavs:
        print(f"No hay WAV en {CACHE_DIR}.")
        return 0

    generated, skipped, no_text, errors = 0, 0, 0, 0
    for wav in wavs:
        if sidecar_path(wav).exists() and not args.force:
            skipped += 1
            continue
        # cache_id = {id}-{digest}.wav -> el id puede contener guiones (l18-c1…),
        # así que se busca el prefijo más largo que case con un ítem del banco.
        stem = wav.stem
        source_text = next(
            (t for item_id, t in text_by_id.items() if stem.startswith(item_id + "-")),
            "",
        )
        if not source_text:
            no_text += 1
            continue
        if ensure_word_alignment(wav, source_text, force=args.force) is None:
            errors += 1
            print(f"[WARN] {wav.name}: sin word_alignment_proxy")
            continue
        generated += 1
        print(f"[OK] {wav.name}")

    print(
        f"\nSidecars: {generated} · Omitidos (ya existen): {skipped} · "
        f"Sin texto audible: {no_text} · Errores/degradados: {errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

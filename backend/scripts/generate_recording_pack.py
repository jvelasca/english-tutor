"""Genera el pack de grabación del corpus de audio humano.

Lee todos los ítems grabables del banco de listening (los que declaran
`audio_id`: los 9 slots heredados `l15`–`l23` y el corpus `c001`–`cNNN`) y produce,
sin tocar la lógica de la app:

- Un **CSV de grabación** (uno por ítem) con lo que hay que grabar: transcripción
  literal, velocidad objetivo (wpm), notas de connected speech, entorno, ruido,
  espontaneidad, hablante y duración objetivo.
- Un **resumen de progreso** (`recording_pack_summary.json`) con el recuento actual
  por nivel frente al objetivo del auditor (A1 30–40, A2 40–50, B1 60–80, B2 60–80)
  y la convención de ruta `{cefr}/{speaker_id}/{audio_id}.wav`.

Este script es el puente entre "corpus especificado" y "corpus grabado": el equipo
humano usa el CSV como guion y el `import_audio.py --batch` para incorporar los WAV.

Uso:
    python scripts/generate_recording_pack.py [--out-dir ruta]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Windows usa cp1252 por defecto; forzamos UTF-8 para evitar UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.listening import QUESTION_BANK  # noqa: E402

# Objetivo de tamaño del corpus por nivel (mínimo, máximo) según la auditoría
# externa a V1.35. Es una guía de producción, no un límite funcional.
CORPUS_TARGET: dict[str, tuple[int, int]] = {
    "A1": (30, 40),
    "A2": (40, 50),
    "B1": (60, 80),
    "B2": (60, 80),
}

# Columnas del CSV de grabación, en orden estable y legible para no ingenieros.
CSV_FIELDS: tuple[str, ...] = (
    "audio_id",
    "id",
    "level",
    "skill",
    "speaker_id",
    "gender",
    "age_band",
    "region",
    "accent",
    "speaker_count",
    "context",
    "task_type",
    "speech_rate",
    "duration",
    "noise_level",
    "spontaneity",
    "recording_environment",
    "connected_speech",
    "overlap",
    "prosody",
    "transcript",
    "clean_transcript",
)


def grabbable_items(bank: list[dict] | None = None) -> list[dict]:
    """Ítems con `audio_id` (los que admiten grabación humana)."""
    bank = bank if bank is not None else QUESTION_BANK
    return [q for q in bank if (q.get("audio_id") or "").strip()]


def file_for(item: dict) -> str:
    """Ruta relativa convencional del WAV dentro de la biblioteca."""
    return f"{item['level']}/{item['speaker_id']}/{item['audio_id']}.wav"


def build_summary(bank: list[dict] | None = None) -> dict:
    """Resumen de producción: recuento por nivel frente al objetivo y totales."""
    items = grabbable_items(bank)
    by_level: dict[str, int] = {}
    for item in items:
        level = item["level"]
        by_level[level] = by_level.get(level, 0) + 1
    levels = []
    for level, (lo, hi) in CORPUS_TARGET.items():
        count = by_level.get(level, 0)
        levels.append(
            {
                "level": level,
                "specified": count,
                "target_min": lo,
                "target_max": hi,
                "on_target": lo <= count <= hi,
                "remaining": max(0, lo - count),
            }
        )
    return {
        "total_grabbable": len(items),
        "by_level": levels,
        "path_convention": "{cefr}/{speaker_id}/{audio_id}.wav",
    }


def write_recording_pack(bank: list[dict] | None, out_dir: Path) -> dict:
    """Escribe el CSV de grabación y el resumen JSON. Devuelve el resumen."""
    items = grabbable_items(bank)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "recording_pack.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "audio_id": item.get("audio_id", ""),
                    "id": item["id"],
                    "level": item["level"],
                    "skill": item.get("skill", ""),
                    "speaker_id": item.get("speaker_id", ""),
                    "gender": item.get("gender", "unknown"),
                    "age_band": item.get("age_band", "unknown"),
                    "region": item.get("region", "unknown"),
                    "accent": item.get("accent", "neutral"),
                    "speaker_count": item.get("speaker_count", 1),
                    "context": item.get("context", ""),
                    "task_type": item.get("task_type", "unknown"),
                    "speech_rate": item.get("speech_rate", 0.0),
                    "duration": item.get("duration", 0.0),
                    "noise_level": item.get("noise_level", 0),
                    "spontaneity": item.get("spontaneity", "scripted"),
                    "recording_environment": item.get(
                        "recording_environment", "studio"
                    ),
                    "connected_speech": bool(item.get("connected_speech", False)),
                    "overlap": bool(item.get("overlap", False)),
                    "prosody": item.get("prosody", "unknown"),
                    "transcript": item.get("transcript", ""),
                    "clean_transcript": item.get("clean_transcript", ""),
                }
            )

    summary = build_summary(bank)
    summary["csv"] = str(csv_path)
    summary["csv_rows"] = len(items)
    summary_path = out_dir / "recording_pack_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera el pack de grabación del corpus de audio humano."
    )
    parser.add_argument(
        "--out-dir",
        default="recording_pack",
        help="Directorio de salida (por defecto ./recording_pack)",
    )
    args = parser.parse_args(argv)

    summary = write_recording_pack(None, Path(args.out_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] CSV en {summary['csv']} ({summary['csv_rows']} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

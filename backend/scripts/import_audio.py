"""Importación determinista de un WAV humano a la biblioteca de audio.

Lee un WAV real (solo con `wave`, stdlib), calcula su duración real, compone un
`AudioLibraryEntry` con el resto de metadatos pasados por flags, valida el manifest
resultante y copia el WAV a su ruta definitiva dentro de la biblioteca. Los campos
no pasados por flag toman su default (no se inventan valores).

Uso:
    python scripts/import_audio.py --wav grabacion.wav --audio-id a1 \\
        --speaker-id speaker_001 --cefr B1 --accent br

El helper puro `wav_metadata(path)` es reutilizable y testeable sin side effects.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import wave
from pathlib import Path

# Windows usa cp1252 por defecto; forzamos UTF-8 para evitar UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Permite ejecutar el script desde cualquier directorio resolviendo `services`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from services.audio_library import (  # noqa: E402
    AudioLibraryEntry,
    library_dir,
    load_manifest,
    manifest_path,
    validate_audio_entries,
    validate_manifest,
    write_entry,
)
from services.listening import QUESTION_BANK  # noqa: E402


def wav_metadata(path: Path) -> dict:
    """Lee los metadatos reales de un WAV usando solo `wave` (stdlib).

    Devuelve `{"duration", "channels", "framerate", "sample_width"}`. Si `path` no
    es un WAV válido (o no se puede abrir), devuelve `{}` (fallo limpio, sin lanzar).
    """
    try:
        with wave.open(str(path), "rb") as w:
            framerate = w.getframerate()
            nframes = w.getnframes()
            return {
                "duration": nframes / framerate if framerate else 0.0,
                "channels": w.getnchannels(),
                "framerate": framerate,
                "sample_width": w.getsampwidth(),
            }
    except (wave.Error, EOFError, OSError):
        return {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importa un WAV humano a la biblioteca (manifest + copia)."
    )
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Valida audio↔metadata de todo el manifest y vuelca issues en JSON",
    )
    parser.add_argument("--wav", help="Ruta al WAV a importar")
    parser.add_argument("--audio-id", help="Identificador único de audio")
    parser.add_argument("--speaker-id", help="Identificador del hablante")
    parser.add_argument(
        "--file",
        help="Ruta relativa destino (por defecto {cefr}/{speaker_id}/{audio_id}.wav)",
    )
    parser.add_argument("--cefr", default="unknown", help="CEFR: A1/A2/B1/B2/unknown")
    parser.add_argument("--accent", default="neutral", help="Acento (etiqueta libre)")
    parser.add_argument("--gender", default="unknown", help="female/male/unknown")
    parser.add_argument(
        "--age-band", default="unknown", help="child/teen/adult/senior/unknown"
    )
    parser.add_argument(
        "--region", default="unknown", help="Región geográfica/dialecto"
    )
    parser.add_argument(
        "--speech-rate",
        type=float,
        default=None,
        help="WPM declarado (None = sin declarar)",
    )
    parser.add_argument(
        "--spontaneity", default="scripted", help="scripted/semi_scripted/spontaneous"
    )
    parser.add_argument(
        "--recording-environment",
        default="studio",
        help="studio/quiet_room/noisy/field",
    )
    parser.add_argument(
        "--overlap", action="store_true", help="¿Solapamiento de voces?"
    )
    parser.add_argument(
        "--connected-speech",
        action="store_true",
        help="¿Presenta connected speech?",
    )
    parser.add_argument(
        "--prosody", default="unknown", help="Etiqueta libre de rasgos prosódicos"
    )
    parser.add_argument(
        "--task-type", default="unknown", help="Tipo de tarea de listening"
    )
    parser.add_argument("--speaker-count", type=int, default=1, help="Nº de hablantes")
    parser.add_argument("--noise-level", type=int, default=0, help="Ruido (0..5)")
    parser.add_argument("--transcript", default="", help="Transcripción literal")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Importación masiva desde un directorio de WAV (ver --wav-dir)",
    )
    parser.add_argument(
        "--wav-dir",
        help="Directorio raíz de los WAV a importar en modo --batch",
    )
    parser.add_argument(
        "--level",
        help="Filtrar la importación masiva por nivel CEFR (A1/A2/B1/B2)",
    )
    return parser


def _validate_all() -> int:
    """Audita todo el manifest: resuelve cada WAV y vuelca issues por `audio_id`."""
    manifest = load_manifest()
    if not manifest.entries:
        print("No hay entradas en el manifest.")
        return 0
    result = validate_audio_entries(manifest)
    print(
        json.dumps(
            {
                audio_id: [issue.model_dump() for issue in issues]
                for audio_id, issues in result.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def entry_from_item(item: dict, duration: float) -> AudioLibraryEntry:
    """Compone un `AudioLibraryEntry` a partir de un ítem grabable y su duración real.

    Mapea los metadatos del ítem del banco (incluidos los descriptivos ampliados del
    corpus: `gender`, `age_band`, `region`, `spontaneity`, `recording_environment`,
    `overlap`, `connected_speech`, `prosody`, `task_type`) a la entrada del manifest.
    `cefr` se deriva del `level` del ítem (fuente única, sin posible desfase) y
    `file` sigue la convención `{cefr}/{speaker_id}/{audio_id}.wav`.
    """
    audio_id = (item.get("audio_id") or "").strip()
    level = item.get("level") or "unknown"
    speaker_id = item.get("speaker_id") or ""
    return AudioLibraryEntry(
        audio_id=audio_id,
        file=f"{level}/{speaker_id}/{audio_id}.wav",
        speaker_id=speaker_id,
        accent=item.get("accent", "neutral"),
        speaker_count=int(item.get("speaker_count", 1)),
        noise_level=int(item.get("noise_level", 0)),
        duration=duration,
        transcript=item.get("transcript", ""),
        gender=item.get("gender", "unknown"),
        age_band=item.get("age_band", "unknown"),
        region=item.get("region", "unknown"),
        speech_rate=item.get("speech_rate"),
        spontaneity=item.get("spontaneity", "scripted"),
        recording_environment=item.get("recording_environment", "studio"),
        overlap=bool(item.get("overlap", False)),
        connected_speech=bool(item.get("connected_speech", False)),
        prosody=item.get("prosody", "unknown"),
        task_type=item.get("task_type", "unknown"),
        cefr=level if level in ("A1", "A2", "B1", "B2") else "unknown",
        context=item.get("context", "unknown"),
    )


def _batch_import(wav_dir: Path, level: str | None) -> int:
    """Importa en lote los WAV grabados del corpus a la biblioteca (manifest + copia).

    Recorre los ítems grabables del banco (los que declaran `audio_id`) y, para cada
    uno, localiza su WAV por convención (`{wav_dir}/{cefr}/{speaker_id}/{audio_id}.wav`
    con fallback plano `{wav_dir}/{audio_id}.wav`), mide su duración real y hace
    *upsert* de la entrada en el manifest. Devuelve 0 si todo ok, 1 si hubo errores.
    """
    items = [q for q in QUESTION_BANK if (q.get("audio_id") or "").strip()]
    if level:
        items = [q for q in items if q.get("level") == level]

    imported, skipped, errors = 0, 0, 0
    for item in items:
        audio_id = item["audio_id"].strip()
        candidates = [
            wav_dir
            / item.get("level", "")
            / item.get("speaker_id", "")
            / f"{audio_id}.wav",
            wav_dir / f"{audio_id}.wav",
        ]
        wav_path = next((c for c in candidates if c.exists()), None)
        if wav_path is None:
            skipped += 1
            print(f"[SKIP] {audio_id}: WAV no encontrado")
            continue
        meta = wav_metadata(wav_path)
        if not meta:
            errors += 1
            print(f"[FAIL] {audio_id}: {wav_path} no es un WAV válido")
            continue
        entry = entry_from_item(item, meta["duration"])
        try:
            write_entry(entry, wav_path.read_bytes())
        except (ValueError, wave.Error, OSError, EOFError) as exc:
            errors += 1
            print(f"[FAIL] {audio_id}: {exc}")
            continue
        imported += 1
        print(f"[OK] {audio_id} -> {entry.file}")

    print(f"\nImportados: {imported} · Omitidos: {skipped} · Errores: {errors}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.validate_all:
        return _validate_all()

    if args.batch:
        if not args.wav_dir:
            print("[FAIL] --batch requiere --wav-dir", file=sys.stderr)
            return 2
        return _batch_import(Path(args.wav_dir), args.level)

    if not args.wav or not args.audio_id or not args.speaker_id:
        print(
            "[FAIL] --wav, --audio-id y --speaker-id son obligatorios para importar",
            file=sys.stderr,
        )
        return 2

    wav_path = Path(args.wav)
    meta = wav_metadata(wav_path)
    if not meta:
        print(
            f"[FAIL] {wav_path} no es un WAV válido o no se puede leer.",
            file=sys.stderr,
        )
        return 1

    file_rel = args.file or f"{args.cefr}/{args.speaker_id}/{args.audio_id}.wav"

    try:
        entry = AudioLibraryEntry(
            audio_id=args.audio_id,
            file=file_rel,
            speaker_id=args.speaker_id,
            accent=args.accent,
            speaker_count=args.speaker_count,
            noise_level=args.noise_level,
            duration=meta["duration"],
            transcript=args.transcript,
            gender=args.gender,
            age_band=args.age_band,
            region=args.region,
            speech_rate=args.speech_rate,
            spontaneity=args.spontaneity,
            recording_environment=args.recording_environment,
            overlap=args.overlap,
            connected_speech=args.connected_speech,
            prosody=args.prosody,
            task_type=args.task_type,
            cefr=args.cefr,
        )
    except ValidationError as exc:
        print(f"[FAIL] metadatos inválidos: {exc}", file=sys.stderr)
        return 1

    manifest = load_manifest()
    manifest.entries = [e for e in manifest.entries if e.audio_id != entry.audio_id]
    manifest.entries.append(entry)

    problems = validate_manifest(manifest)
    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}", file=sys.stderr)
        return 1

    dest = library_dir() / file_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(wav_path, dest)

    manifest_path().write_text(
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(entry.model_dump(), ensure_ascii=False, indent=2))
    print(f"[OK] importado a {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

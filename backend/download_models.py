"""Descarga los modelos de voz una sola vez (requiere internet la primera vez).

V3.71 (eje RB, absorbe RA-04 y RD-06): el bootstrap de instalación deja de tener
su propia copia de las URLs y de descargar sin límite de tiempo.

- **RD-06 (timeout).** `download_piper()` usaba `urllib.request.urlretrieve` con
  una URL escrita a mano y **sin timeout**: si Hugging Face no respondía, la
  instalación se quedaba colgada sin decir nada. Ahora delega en el catálogo
  curado (`services.voice_downloads.download_voice`), que aplica un timeout real,
  mueve el fichero de forma atómica y verifica el tamaño contra `Content-Length`.
- **RD-06 (catálogo).** La voz inglesa por defecto (`config.PIPER_VOICE`) **no
  estaba en el catálogo**, así que `ensure_voice_for_language("en")` no podía
  auto-descargarla nunca. Ahora está (RB-01) y este script y la descarga en
  caliente usan **la misma lista**.
- **RA-04 (verificación previa).** `--check` informa de lo que falta **sin
  descargar nada** y distingue lo que es **descarga** de lo que es **local**, en
  el sitio donde el README ya manda al usuario. Es la verificación previa que el
  eje RA pedía para un clon limpio, donde `backend/models/` está vacío.

Uso:
    python download_models.py            # descarga lo que falte
    python download_models.py --check    # solo informa (no descarga nada)

Ollama **no** se bootstrapea aquí a propósito: `ollama pull` es un paso explícito
del runbook (decisión B del briefing de V3.71), porque el modelo lo gestiona el
servicio de Ollama, no el árbol del proyecto.
"""
from __future__ import annotations

import argparse
import sys

from config import (
    DEFAULT_MODEL,
    DEFAULT_VOICES,
    PIPER_DIR,
    WHISPER_DIR,
    WHISPER_SIZE,
)

# El fichero SQLite lo crea la app al arrancar (dato LOCAL: no se descarga, no se
# versiona). Su ruta NO se escribe aquí: se toma de `repositories.db`, que es la
# única fuente de verdad (escribirla a mano sería justo una deriva documental).
from repositories.db import DB_PATH as DB_FILE

DOWNLOAD = "descarga"
LOCAL = "local"


def _mb(size: int) -> float:
    return round(size / 1_048_576, 1)


def _size_label(size: int) -> str:
    """Tamaño legible: KB por debajo de 1 MB, MB a partir de ahí."""
    if size <= 0:
        return "-"
    if size < 1_048_576:
        return f"{max(1, round(size / 1024))} KB"
    return f"{_mb(size)} MB"


def _piper_artifacts() -> list[dict]:
    """Los ficheros de cada voz por defecto, derivados de `config.DEFAULT_VOICES`.

    Se deriva de la configuración (no se escribe una lista aparte) para que una
    voz por defecto nueva no pueda quedarse sin instalar.
    """
    items: list[dict] = []
    for language, voice_id in sorted(DEFAULT_VOICES.items()):
        for suffix in (".onnx", ".onnx.json"):
            path = PIPER_DIR / f"{voice_id}{suffix}"
            items.append(
                {
                    "id": f"piper:{voice_id}{suffix}",
                    "label": f"Voz Piper ({language}): {voice_id}{suffix}",
                    "kind": DOWNLOAD,
                    "origin": "huggingface.co (rhasspy/piper-voices)",
                    "path": path,
                }
            )
    return items


def _whisper_artifact() -> dict:
    files = (
        [p for p in WHISPER_DIR.rglob("*") if p.is_file()]
        if WHISPER_DIR.is_dir()
        else []
    )
    return {
        "id": f"whisper:{WHISPER_SIZE}",
        "label": f"Whisper `{WHISPER_SIZE}` (STT, caché en disco)",
        "kind": DOWNLOAD,
        "origin": "huggingface.co (vía faster-whisper)",
        "path": WHISPER_DIR,
        "_files": len(files),
        "_bytes": sum(p.stat().st_size for p in files),
    }


def _local_artifact() -> dict:
    return {
        "id": f"sqlite:{DB_FILE.name}",
        "label": "Base de datos (usuarios, evidencia, léxico)",
        "kind": LOCAL,
        "origin": "se crea sola al arrancar la app",
        "path": DB_FILE,
    }


def install_report() -> list[dict]:
    """Qué hace falta para arrancar, qué es descarga y qué es local (solo lectura).

    No descarga, no crea directorios y no toca la BD: solo mira el disco. Cada
    elemento declara `kind` (`descarga` / `local`) y `origin`, y `exists` es
    `None` cuando este script **no puede** comprobarlo (el modelo de Ollama lo
    gestiona el servicio de Ollama, no el árbol del proyecto).
    """
    items: list[dict] = list(_piper_artifacts())
    items.append(_whisper_artifact())
    items.append(_local_artifact())

    report: list[dict] = []
    for item in items:
        path = item["path"]
        size = item["_bytes"] if "_bytes" in item else (
            path.stat().st_size if path.is_file() else 0
        )
        report.append(
            {
                "id": item["id"],
                "label": item["label"],
                "kind": item["kind"],
                "origin": item["origin"],
                "exists": size > 0,
                "mb": _mb(size),
                "bytes": size,
            }
        )

    report.append(
        {
            "id": f"ollama:{DEFAULT_MODEL}",
            "label": f"Modelo de Ollama `{DEFAULT_MODEL}` (chat y definiciones)",
            "kind": DOWNLOAD,
            "origin": "ollama pull (paso manual del runbook)",
            "exists": None,
            "mb": 0.0,
            "bytes": 0,
        }
    )
    return report


def missing_offline_artifacts(report: list[dict] | None = None) -> list[dict]:
    """Elementos que deben estar EN DISCO y no están (excluye lo no comprobable)."""
    report = install_report() if report is None else report
    return [item for item in report if item["exists"] is False]


def print_report(as_json: bool = False) -> int:
    """Imprime el informe de instalación. Devuelve 0 si no falta nada en disco."""
    report = install_report()
    missing = missing_offline_artifacts(report)
    if as_json:
        import json  # noqa: PLC0415

        print(json.dumps({"items": report, "missing": len(missing)}, indent=2))
        return 0 if not missing else 1

    print("Estado de la instalación (solo lectura, no descarga nada)\n")
    for item in report:
        if item["exists"] is None:
            mark = "??"
        elif item["exists"]:
            mark = "OK"
        else:
            mark = "FALTA"
        size = _size_label(item["bytes"])
        print(f"  [{mark:>5}] {item['label']}")
        print(f"          tipo: {item['kind']} · origen: {item['origin']} · {size}")

    print()
    if missing:
        print(f"Faltan {len(missing)} artefacto(s) en disco.")
        print("Ejecuta sin `--check` para descargarlos (la 1.ª vez necesita internet).")
    else:
        print("Todo lo que debe estar en disco está en disco.")
    print("\nModelo de Ollama: compruébalo con `ollama list`.")
    print(f"Debe estar instalado: {DEFAULT_MODEL}")
    return 0 if not missing else 1


def _ensure_voice(voice_id: str) -> bool:
    """Instala una voz del catálogo si falta. `True` si quedó instalada."""
    from services.voice_downloads import download_voice, spec_for  # noqa: PLC0415

    if spec_for(voice_id) is None:
        print(f"  {voice_id} no está en el catálogo, omitiendo")
        return False
    print(f"  Descargando {voice_id}...")
    download_voice(voice_id)
    print("  OK")
    return True


def download_piper() -> None:
    """Instala las voces Piper por defecto (una de inglés y una de español).

    V3.71 (eje RB): delegado en el catálogo curado. Antes bajaba solo la inglesa
    con una URL escrita a mano y `urlretrieve` (sin timeout); ahora recorre
    `config.DEFAULT_VOICES`, así que una voz por defecto nueva entra sola.
    """
    for voice_id in sorted(set(DEFAULT_VOICES.values())):
        _ensure_voice(voice_id)


def download_whisper() -> None:
    from faster_whisper import WhisperModel  # noqa: PLC0415

    print(f"  Instanciando Whisper {WHISPER_SIZE} (descarga si falta)...")
    WhisperModel(
        WHISPER_SIZE, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR)
    )
    print(f"  Whisper listo en {WHISPER_DIR}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga los modelos de voz (1.ª vez) o comprueba qué falta."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="solo informa de lo que falta, sin descargar nada",
    )
    parser.add_argument(
        "--json", action="store_true", help="informe en JSON (implica --check)"
    )
    args = parser.parse_args()

    if args.check or args.json:
        return print_report(as_json=args.json)

    print("Voces Piper por defecto (inglés + español)...")
    download_piper()
    print("Whisper...")
    download_whisper()
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

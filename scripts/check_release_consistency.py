"""Verifica la consistencia de versión entre todas las fuentes de release.

La versión de la app es una única fuente de verdad (`backend/config.py::VERSION`).
Este script comprueba que backend, frontend (`package.json` y `package-lock.json`),
`README.md`, `CHANGELOG.md` y `PLAN.md` declaran exactamente esa versión, y falla
(exit code 1) si hay cualquier desfase. Está pensado para ejecutarse en CI como
guard de higiene de release (premisa 9).

Uso:
    python scripts/check_release_consistency.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# El script vive en <repo>/scripts/, así que la raíz es el padre de `scripts`.
ROOT = Path(__file__).resolve().parents[1]

# (ruta relativa a ROOT, patrón con UN grupo de captura de versión, etiqueta)
SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "frontend/package.json",
        r'"version": "(\d+\.\d+\.\d+)"',
        "frontend/package.json",
    ),
    (
        "frontend/package-lock.json",
        r'"version": "(\d+\.\d+\.\d+)"',
        "frontend/package-lock.json",
    ),
    (
        "README.md",
        r"versión estable: \*\*v?(\d+\.\d+\.\d+)\*\*",
        "README.md",
    ),
    (
        "CHANGELOG.md",
        r"^## \[(\d+\.\d+\.\d+)\]",
        "CHANGELOG.md",
    ),
    (
        "PLAN.md",
        r"Versión estable `(\d+\.\d+\.\d+)`",
        "PLAN.md",
    ),
)


def source_of_truth() -> str:
    """Devuelve la versión canónica desde `backend/config.py`."""
    text = (ROOT / "backend" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("No se encontró VERSION en backend/config.py")
    return match.group(1)


def main() -> int:
    expected = source_of_truth()
    failures: list[str] = []

    for rel, pattern, label in SOURCES:
        path = ROOT / rel
        if not path.exists():
            failures.append(f"{label}: archivo no encontrado")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            failures.append(f"{label}: versión no localizada")
            continue
        if match.group(1) != expected:
            failures.append(f"{label}: {match.group(1)} != {expected}")

    if failures:
        print("FAIL: Release consistency failed")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"OK: Release consistency ({expected}) en todos los orígenes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

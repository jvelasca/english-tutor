"""Chequeo del ESPACIO de instancias del banco de transferencia (V3.61) desde CI.

Recorre las 20 familias de `services.transfer` y emite el "TRANSFER INSTANCE SPACE
CHECK": invariantes de contenido (mínimo/máximo, llaves, slugs, deltas, register,
competencias) y avisos heurísticos de equivalencia. Sale con código 1 si hay
issues de severidad `error` (para poder usarlo como guard en CI).

Uso:
    python -m scripts.transfer_validation
    python -m scripts.transfer_validation --target supermarket
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.transfer_audit import validate_bank  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        default="",
        help="unidad objetivo con la que comprobar el guard anti-spoiler",
    )
    args = parser.parse_args()
    report = validate_bank(target=args.target)
    print("TRANSFER INSTANCE SPACE CHECK")
    print(json.dumps(
        {
            "families": report["families"],
            "surfaces": report["surfaces"],
            "errors": len(report["errors"]),
            "warnings": len(report["warnings"]),
            "ok": report["ok"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    for entry in report["errors"]:
        print(
            f"[ERROR  ] {entry['code']}: {entry['family']}:"
            f"{entry['surface'] or '-'}: {entry['detail']}"
        )
    for entry in report["warnings"]:
        print(
            f"[WARNING] {entry['code']}: {entry['family']}:"
            f"{entry['surface'] or '-'}: {entry['detail']}"
        )
    print(f"\nOK={report['ok']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

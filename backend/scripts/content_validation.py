"""Chequeo de integridad del contenido (V1.37) desde terminal/CI.

Recorre `question → audio_id → manifest → WAV → metadata → CEFR → difficulty →
subskills` y emite el "CONTENT INTEGRITY CHECK". Sale con código 1 si hay issues
de severidad `error` (para poder usarlo como guard en CI).

Uso:
    python -m scripts.content_validation
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.content_validation import run_content_validation  # noqa: E402


def main() -> int:
    report = run_content_validation()
    print("CONTENT INTEGRITY CHECK")
    print(json.dumps(
        {
            "total_items": report["total_items"],
            "recorded": report["recorded"],
            "tts": report["tts"],
            "by_severity": report["by_severity"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    for issue in report["issues"]:
        print(f"[{issue['severity'].upper():7}] {issue['category']}: "
              f"{issue['id'] or '-'}: {issue['message']}")
    print(f"\nOK={report['ok']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

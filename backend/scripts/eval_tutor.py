"""Evaluación objetiva de un modelo como tutor de inglés.

Envía el corpus canónico de errores (EVAL_CASES) al modelo indicado, puntúa cada
respuesta con `evaluate_tutor_reply` y compone un informe agregado con medias por
señal y veredicto.

Uso:
    .venv\\Scripts\\python.exe scripts/eval_tutor.py --model qwen3.5:9b
    .venv\\Scripts\\python.exe scripts/eval_tutor.py --model qwen3.5:9b --json

No depende de la red salvo Ollama local; no usa Whisper/Piper.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ollama

# Permite importar services/ al ejecutar el script desde cualquier cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.evaluation import (  # noqa: E402
    EVAL_CASES,
    build_report,
    build_tutor_prompt,
    evaluate_tutor_reply,
    format_report,
)

# Windows: forzar UTF-8 para imprimir acentos/símbolos sin error de cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_batch(model: str) -> list[dict]:
    """Envía cada caso al modelo y devuelve la lista de resultados puntuados."""
    results: list[dict] = []
    for case in EVAL_CASES:
        system = build_tutor_prompt(case)
        try:
            resp = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": case["student"]},
                ],
                options={"temperature": 0.7},
            )
            reply = resp.get("message", {}).get("content", "").strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR en caso {case['id']}] {exc}", file=sys.stderr)
            reply = ""
        results.append(evaluate_tutor_reply(reply, case))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalúa objetivamente a un modelo como tutor de inglés."
    )
    parser.add_argument("--model", required=True, help="Nombre del modelo en Ollama")
    parser.add_argument("--json", action="store_true", help="Emitir el informe en JSON")
    args = parser.parse_args()

    results = run_batch(args.model)
    report = build_report(results)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()

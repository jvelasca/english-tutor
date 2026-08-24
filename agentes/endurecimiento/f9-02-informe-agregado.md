# Subagente F9.2 — Informe agregado + script por lotes (backend)

## Rol
Programador backend Python (FastAPI). Sin acceso a Git (no hagas commit) ni al frontend.

## Objetivo
Añadir el **informe agregado** de la evaluación del tutor y un **script por lotes**
(`scripts/eval_tutor.py`) que puntúa un modelo contra el corpus canónico (`EVAL_CASES`)
usando el evaluador de F9.1. Todo determinista, sin LLM-juez (premisa 12). La lógica pura
vive en `services/evaluation.py`; el script es fino (CLI + bucle Ollama, sin testear, como
`scripts/eval_model.py` de M5).

## Contexto (autocontenido)
- Estilo: `from __future__ import annotations`, docstrings en español, imports ordenados,
  línea ≤ 88 (ruff E501). `services/evaluation.py` ya existe y contiene `EVAL_CASES`,
  `summarize`, `evaluate_tutor_reply`, etc. (F9.1, commit `2c96dd5`). NO borres ni modifiques
  el código existente; solo **añade** al final del archivo.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  python scripts/eval_tutor.py --help
  ```
  Si `python` no funciona, usa `.venv\Scripts\python.exe` (Python 3.13.7).

## Tarea

### 1. `backend/services/evaluation.py` — AÑADIR al final (sin tocar lo existente)

```python
TUTOR_PROMPTS: dict[str, str] = {
    "conversation": (
        "You are a friendly, patient English tutor. Answer in English, keep it "
        "brief, and ask a follow-up question to keep the conversation going."
    ),
    "grammar": (
        "You are an English grammar coach. Correct mistakes clearly and explain "
        "briefly, always in English."
    ),
    "exercises": (
        "You are an English teacher who creates short, focused exercises. Reply "
        "in English and keep it concise."
    ),
    "pronunciation": (
        "You are an English pronunciation coach. Reply in English with clear, "
        "concise guidance."
    ),
}


def build_tutor_prompt(case: dict) -> str:
    """Devuelve el system prompt del tutor según el modo del caso."""
    mode = case.get("mode", "conversation")
    return TUTOR_PROMPTS.get(mode, TUTOR_PROMPTS["conversation"])


def _verdict(summary: dict) -> str:
    avg = summary.get("avg_total")
    if avg is None:
        return "sin datos"
    if avg >= 80:
        return "excelente"
    if avg >= 60:
        return "bueno"
    if avg >= 40:
        return "regular"
    return "deficiente"


def _fmt(value: float | int | None) -> str:
    return "-" if value is None else str(value)


def build_report(results: list[dict]) -> dict:
    """Compone el informe agregado: resumen + desglose por caso + veredicto."""
    summary = summarize(results)
    per_case = [
        {
            "case_id": r.get("case_id"),
            "correction": r.get("correction"),
            "english": r.get("english"),
            "conciseness": r.get("conciseness"),
            "engagement": r.get("engagement"),
            "total": r.get("total"),
        }
        for r in results
    ]
    return {"summary": summary, "per_case": per_case, "verdict": _verdict(summary)}


def format_report(report: dict) -> str:
    """Convierte el informe a texto legible para consola."""
    s = report["summary"]
    lines = [
        "== Informe de evaluacion del tutor ==",
        f"Casos evaluados: {s['cases']}",
        f"Total medio: {_fmt(s['avg_total'])}",
        f"Correccion media: {_fmt(s['avg_correction'])}",
        f"Ingles medio: {_fmt(s['avg_english'])}",
        f"Concision media: {_fmt(s['avg_conciseness'])}",
        f"Engagement medio: {_fmt(s['avg_engagement'])}",
        f"Veredicto: {report['verdict']}",
        "",
    ]
    for case in report["per_case"]:
        lines.append(
            f"- [{case['case_id']}] total={_fmt(case['total'])} "
            f"(corr={_fmt(case['correction'])}, en={_fmt(case['english'])}, "
            f"conc={_fmt(case['conciseness'])}, eng={_fmt(case['engagement'])})"
        )
    return "\n".join(lines)
```

### 2. `backend/scripts/eval_tutor.py` (nuevo)

```python
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
```

> **Nota:** la línea `from services.evaluation import ...` va precedida de
> `sys.path.insert(...)`, por eso lleva `# noqa: E402`. Es intencional.

### 3. `backend/tests/test_evaluation_report.py` (nuevo, 10 tests)

```python
"""Tests del informe agregado y el prompt del tutor (services/evaluation.py)."""
from services.evaluation import (
    TUTOR_PROMPTS,
    build_report,
    build_tutor_prompt,
    format_report,
)


def _result(total: int, case_id: str = "age") -> dict:
    return {
        "case_id": case_id,
        "correction": 100,
        "english": 100,
        "conciseness": 100,
        "engagement": 100,
        "total": total,
    }


def test_build_tutor_prompt_grammar():
    prompt = build_tutor_prompt({"mode": "grammar", "level": "A1"})
    assert "grammar" in prompt


def test_build_tutor_prompt_conversation():
    prompt = build_tutor_prompt({"mode": "conversation", "level": "A2"})
    assert "conversation" in prompt


def test_build_tutor_prompt_fallback_unknown():
    prompt = build_tutor_prompt({"mode": "unknown"})
    assert prompt == TUTOR_PROMPTS["conversation"]


def test_build_report_empty():
    report = build_report([])
    assert report["summary"]["cases"] == 0
    assert report["verdict"] == "sin datos"
    assert report["per_case"] == []


def test_build_report_verdict_excellent():
    report = build_report([_result(85)])
    assert report["verdict"] == "excelente"


def test_build_report_verdict_good():
    report = build_report([_result(65)])
    assert report["verdict"] == "bueno"


def test_build_report_verdict_regular():
    report = build_report([_result(45)])
    assert report["verdict"] == "regular"


def test_build_report_verdict_deficient():
    report = build_report([_result(20)])
    assert report["verdict"] == "deficiente"


def test_build_report_per_case_fields():
    report = build_report([_result(85, "age"), _result(20, "modal")])
    assert [c["case_id"] for c in report["per_case"]] == ["age", "modal"]
    assert report["per_case"][0]["correction"] == 100
    assert report["summary"]["cases"] == 2


def test_format_report_includes_verdict_and_cases():
    report = build_report([_result(85, "age")])
    text = format_report(report)
    assert "Veredicto: excelente" in text
    assert "[age]" in text
    assert "Casos evaluados: 1" in text
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 217 tests** (207 previos + 10 nuevos).
- `python -m ruff check .` **sin errores**.
- `python scripts/eval_tutor.py --help` termina con código 0 (no llama a Ollama).
- Ningún test existente se rompe.

## Restricciones
- NO tocar el frontend.
- NO tocar `routers/`, `domain/`, `repositories/`, `schemas/`, `main.py`, `config.py`,
  ni otros `services/*`.
- En `services/evaluation.py`, **solo añadir** las funciones nuevas al final; no modificar
  el código existente de F9.1.
- NO hagas commit ni toques documentación.

## Salida
Lista de archivos creados/modificados, salida de `python -m pytest tests/ -q` y de
`python -m ruff check .`, resultado de `python scripts/eval_tutor.py --help`, y cualquier
desviación.

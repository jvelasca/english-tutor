"""Protocolo de variabilidad del extracción LLM de speaking (auditoría C).

Mide empíricamente cuánto cambia `extract_speaking_evidence` (y por tanto el
overall determinista que depende de él) al repetir la MISMA transcripción N
veces contra el mismo modelo. Es la pieza que los tests golden no pueden cubrir
(no es determinista) y que requiere Ollama local con el modelo cargado.

Uso (con Ollama arrancado y el modelo descargado):

    python -m scripts.eval_speaking_variability --model llama3.1:8b --repeats 10
    python -m scripts.eval_speaking_variability --model llama3.1:8b --temperature 0.7

Salida: `docs/audit/generated/speaking-variability.{json,md}` + resumen stdout.

Criterios que la auditoría C comprueba con este protocolo (ver dossier):
- temperature=0: la variabilidad residual debería ser ~0 (overall idéntico o
  ±0.01). Si no, el proveedor no respeta temperature y hay que documentarlo.
- temperature>0: solo medición exploratoria de cuánto degrada la estabilidad.
- `std(overall)` documentado como tolerancia del sistema; si supera ~0.05, el
  dossier recomienda mitigación (re-extracción/votación) para tu decisión.

Modo `--mock`: cliente determinista en memoria para validar el harness sin
Ollama (variabilidad 0 por construcción; no sirve como medición real).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parents[0]
GENERATED_DIR = REPO_DIR / "docs" / "audit" / "generated"

sys.path.insert(0, str(BACKEND_DIR))

from services import (  # noqa: E402
    llm,
    speaking,
    speaking_llm,
)

# Transcripciones tipo por nivel (mismas que el golden speaking).
_PROBES = [
    {
        "id": "b1-casual-opinion",
        "level": "B1",
        "task": "Give your opinion about studying English with an app.",
        "heard": (
            "I think it's a good idea because we can meet more people and "
            "practice our English every day."
        ),
        "duration_seconds": 12.4,
        "task_type": "discussion",
    },
    {
        "id": "b2-negotiated-view",
        "level": "B2",
        "task": "Discuss whether investing in long-term projects is wiser "
        "than chasing short-term gains.",
        "heard": (
            "Well, I take your point, but I'd argue the long-term costs "
            "outweigh the short-term benefits."
        ),
        "duration_seconds": 9.8,
        "task_type": "discussion",
    },
]


class _MockClient:
    """Cliente Ollama determinista en memoria (solo valida el harness)."""

    def __init__(self) -> None:
        self._n = 0

    async def chat(self, **kwargs) -> dict:
        heard = kwargs["messages"][1]["content"]
        self._n += 1
        words = heard.lower().split()
        raw = json.dumps(
            {
                "task_achieved": True,
                "grammar_errors": 1 if self._n % 2 == 0 else 1,
                "lexical_tokens": words[:6],
                "coherence": 0.7,
                "discourse_markers": 2,
                "self_corrections": 0,
                "hesitations": 1,
                "repetitions": 0,
            }
        )
        return {"message": {"content": raw}}


async def _one(probe: dict, model: str, temperature: float) -> dict:
    evidence = await speaking_llm.extract_speaking_evidence(
        probe["task"], probe["heard"], model=model, temperature=temperature
    )
    if evidence is None:
        return {"ok": False}
    score = speaking.scores_from_evidence(
        evidence,
        probe["heard"],
        duration_seconds=probe["duration_seconds"],
        task_type=probe["task_type"],
    )
    return {"ok": True, "overall": score["overall"], "evidence": evidence}


async def _measure(probe: dict, model: str, temperature: float, repeats: int) -> dict:
    results = []
    failures = 0
    for _ in range(repeats):
        out = await _one(probe, model, temperature)
        if not out.get("ok"):
            failures += 1
            continue
        results.append(round(float(out["overall"]), 4))
    if not results:
        return {"id": probe["id"], "level": probe["level"], "valid": 0,
                "failures": failures, "note": "sin extracciones válidas"}
    return {
        "id": probe["id"],
        "level": probe["level"],
        "valid": len(results),
        "failures": failures,
        "mean": round(statistics.mean(results), 4),
        "std": round(statistics.pstdev(results), 4),
        "min": min(results),
        "max": max(results),
        "range": round(max(results) - min(results), 4),
        "distinct": len(set(results)),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Variabilidad de extracción LLM speaking."
    )
    parser.add_argument(
        "--model", default="", help="modelo Ollama (obligatorio sin --mock)"
    )
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--mock", action="store_true", help="cliente determinista de prueba"
    )
    args = parser.parse_args()

    if args.mock:
        llm.set_client(_MockClient())
    elif not args.model:
        parser.error("--model es obligatorio salvo con --mock")
    else:
        ok = await llm.ping()
        if not ok:
            print("Ollama no responde. Arranca Ollama y carga el modelo "
                  "(`ollama pull <model>`).", file=sys.stderr)
            return 2

    rows = []
    for probe in _PROBES:
        rows.append(await _measure(probe, args.model, args.temperature, args.repeats))
        r = rows[-1]
        print(
            f"{r['id']:<22} valid={r.get('valid')}/{args.repeats} "
            f"failures={r.get('failures', '-')} mean={r.get('mean', '-')} "
            f"std={r.get('std', '-')} range={r.get('range', '-')} "
            f"distinct={r.get('distinct', '-')}"
        )

    data = {
        "audit": "C-2026-09-02",
        "model": args.model or "mock",
        "temperature": args.temperature,
        "repeats": args.repeats,
        "probes": rows,
    }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    md = (
        "# Variabilidad de extracción LLM (speaking)\n\n"
        "> Generado por `python -m scripts.eval_speaking_variability`. "
        "Modelo/temperatura/repeats en el JSON adjunto.\n\n"
        "```json\n" + json.dumps(data, ensure_ascii=False, indent=1) + "\n```\n"
    )
    (GENERATED_DIR / "speaking-variability.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (GENERATED_DIR / "speaking-variability.md").write_text(md, encoding="utf-8")
    print(f"  → {GENERATED_DIR / 'speaking-variability.{json,md}'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

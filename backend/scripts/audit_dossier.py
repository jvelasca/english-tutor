"""Utilidades de dossier de auditoría (V3.0, post-freeze).

Genera las métricas reproducibles que sustentan los dossieres `docs/audit/*.md`:

    python -m scripts.audit_dossier corpus-stats
        Métricas cuantitativas del corpus de listening por nivel (velocidad,
        dificultad, longitud, connected speech, destrezas, acentos) y escribe
        `docs/audit/generated/listening-corpus-stats.{md,json}`.

    python -m scripts.audit_dossier sample --bank listening --level B2 --count 5
        Muestreo determinista (semilla fija) de ítems para revisión cualitativa.

    python -m scripts.audit_dossier sample --bank objectives --level C1 --count 5

    python -m scripts.audit_dossier curriculum-stats
        Resumen por nivel de objetivos curriculares (checks, actividades, fases,
        referencias a bancos).

    python -m scripts.audit_dossier speaking-stats
        Distribución de escenarios speaking por cefr_target y tipo de tarea.

Salida legible en stdout y versionada en `docs/audit/generated/` para que las
cifras de los dossieres sean reproducibles (sección "Regenerar").
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parents[0]
GENERATED_DIR = REPO_DIR / "docs" / "audit" / "generated"

sys.path.insert(0, str(BACKEND_DIR))

from services.curriculum import load_all_levels, load_level  # noqa: E402
from services.listening import QUESTION_BANK, difficulty_from_vector  # noqa: E402
from services.speaking_scenarios import list_scenarios  # noqa: E402

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
DEFAULT_SEED = 7


def _mean(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else 0.0


def corpus_items() -> list[dict]:
    return [q for q in QUESTION_BANK if str(q["id"]).startswith("c")]


def _by_level(items: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for q in items:
        out[q["level"]].append(q)
    return out


def listening_stats() -> dict:
    corpus = corpus_items()
    by = _by_level(corpus)
    stats = {}
    for lv in LEVELS:
        qs = by.get(lv, [])
        if not qs:
            stats[lv] = {"n": 0}
            continue
        sr = [q.get("speech_rate") or 0 for q in qs]
        diff = [difficulty_from_vector(q.get("difficulty_vector") or {}) for q in qs]
        words = [
            len((q.get("clean_transcript") or q.get("script") or "").split())
            for q in qs
        ]
        dur = [q.get("duration") or 0 for q in qs]
        connected = sum(1 for q in qs if q.get("connected_speech"))
        prosody = Counter(q.get("prosody") or "neutral" for q in qs)
        stats[lv] = {
            "n": len(qs),
            "speech_rate": {
                "mean": _mean(sr),
                "min": min(sr),
                "max": max(sr),
            },
            "difficulty": {
                "mean": _mean(diff),
                "min": min(diff),
                "max": max(diff),
            },
            "words_per_script": {
                "mean": _mean(words),
                "min": min(words),
                "max": max(words),
            },
            "duration_s": {"mean": _mean(dur)},
            "connected_speech_items": connected,
            "skills": dict(Counter(q.get("skill") for q in qs)),
            "accent_variety": len({q.get("accent") for q in qs}),
            "prosody": dict(prosody),
            "speech_rate_out_of_reference_band": bool(
                min(sr) > 0
                and (max(sr) > REFERENCE_BANDS[lv]["wpm"][1])
            ),
        }
    return {"area": "listening", "levels": stats}


# Bandas de referencia (docs/audit/CEFR-REFERENCE.md). Solo para el flag que
# avisa de velocidad fuera de banda; la auditoría cualitativa decide el resto.
REFERENCE_BANDS: dict[str, dict] = {
    "A1": {"wpm": (80, 115)},
    "A2": {"wpm": (110, 135)},
    "B1": {"wpm": (130, 160)},
    "B2": {"wpm": (150, 185)},
    "C1": {"wpm": (165, 195)},
    "C2": {"wpm": (175, 200)},
}


def listening_stats_markdown(stats: dict) -> str:
    lines = [
        "# Métricas del corpus de listening por nivel",
        "",
        "> Generado por `python -m scripts.audit_dossier corpus-stats`. ",
        "> Banda de velocidad de referencia: `docs/audit/CEFR-REFERENCE.md`.",
        "",
        "| Nivel | N | wpm media (min–max) | dificultad (min–max) |",
        "| palabras/script (min–max) | connected | acentos | skills (top 3) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for lv in LEVELS:
        s = stats["levels"][lv]
        if not s.get("n"):
            lines.append(f"| {lv} | 0 | — | — | — | — | — | — |")
            continue
        sr = s["speech_rate"]
        df = s["difficulty"]
        w = s["words_per_script"]
        top = sorted(s["skills"].items(), key=lambda kv: -kv[1])[:3]
        lines.append(
            f"| {lv} | {s['n']} | {sr['mean']} ({sr['min']}–{sr['max']}) | "
            f"{df['mean']} ({df['min']}–{df['max']}) | "
            f"{w['mean']} ({w['min']}–{w['max']}) | "
            f"{s['connected_speech_items']} | {s['accent_variety']} | "
            f"{', '.join(f'{k} {v}' for k, v in top)} |"
        )
    lines += [
        "",
        "Fuente: `services.listening.QUESTION_BANK` (solo ítems `cNNN` del corpus).",
    ]
    return "\n".join(lines)


def sample_items(bank: str, level: str, count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    if bank == "listening":
        pool = [q for q in corpus_items() if q["level"] == level]
        idx = sorted(rng.sample(range(len(pool)), min(count, len(pool))))
        return [
            {
                "id": q["id"],
                "skill": q.get("skill"),
                "topic": q.get("topic"),
                "context": q.get("context"),
                "speech_rate": q.get("speech_rate"),
                "difficulty": difficulty_from_vector(q.get("difficulty_vector") or {}),
                "connected_speech": bool(q.get("connected_speech")),
                "prosody": q.get("prosody"),
                "accent": q.get("accent"),
                "script": q.get("script"),
                "question": q.get("question"),
                "options": q.get("options"),
                "answer_index": q.get("answer_index"),
            }
            for i in idx
            for q in [pool[i]]
        ]
    if bank == "objectives":
        lv = load_level(level.lower())
        objs = lv.objectives()
        idx = sorted(rng.sample(range(len(objs)), min(count, len(objs))))
        return [
            {
                "id": o.id,
                "can_do": o.can_do,
                "skills": o.skills,
                "subskills": o.subskills,
                "checks": len(o.checks),
                "activities": len(o.activities),
                "phases": sorted({(a.phase or "practice") for a in o.activities}),
                "listening_items": len(o.listening_items),
                "scenarios": len(o.scenario_ids),
            }
            for i in idx
            for o in [objs[i]]
        ]
    raise ValueError(f"banco desconocido: {bank}")


def curriculum_stats() -> dict:
    levels: list[dict] = []
    for lv in load_all_levels():
        objs = lv.objectives()
        units = sum(len(m.units) for m in lv.modules)
        phases = Counter(a.phase or "practice" for o in objs for a in o.activities)
        levels.append(
            {
                "level": lv.level,
                "objectives": len(objs),
                "units": units,
                "checks_per_objective": _mean(len(o.checks) for o in objs),
                "activities_per_objective": _mean(len(o.activities) for o in objs),
                "objectives_with_listening": sum(1 for o in objs if o.listening_items),
                "objectives_with_scenario": sum(1 for o in objs if o.scenario_ids),
                "phases": dict(phases),
            }
        )
    return {"area": "curriculum", "levels": levels}


def speaking_stats() -> dict:
    scenarios = list_scenarios()
    return {
        "area": "speaking",
        "total": len(scenarios),
        "by_cefr": dict(
            Counter(s.get("cefr_target") for s in scenarios)
        ),
        "by_task_type": dict(Counter(s.get("task_type") for s in scenarios)),
        "metrics": sorted({m for s in scenarios for m in (s.get("metrics") or [])}),
    }


def mc_position_bias() -> dict:
    """Distribución de la posición de la respuesta correcta en los ítems MC."""
    corpus = corpus_items()
    groups: list[dict] = [
        {"name": "corpus listening (c*)", "items": len(corpus),
         "counts": dict(Counter(q["answer_index"] for q in corpus))},
    ]
    for lv in LEVELS:
        qs = [q for q in corpus if q["level"] == lv]
        groups.append(
            {"name": f"corpus {lv}", "items": len(qs),
             "counts": dict(Counter(q["answer_index"] for q in qs))}
        )
    ck = Counter()
    for lv in load_all_levels():
        for o in lv.objectives():
            for c in o.checks:
                if len(c.options) >= 2:
                    ck[c.correct_index] += 1
    groups.append({"name": "checks currículo (niveles)", "items": sum(ck.values()),
                   "counts": dict(sorted(ck.items()))})
    # Exámenes/placement de assessments.json (sin tocar; solo medir).
    from services.curriculum import load_assessments

    ad = load_assessments()
    ex = Counter()
    for exam in ad.exams.values():
        for it in exam.items:
            ex[it.correct_index] += 1
    total_ex = sum(ex.values())
    groups.append({"name": "exámenes level/placement", "items": total_ex,
                   "counts": dict(sorted(ex.items()))})
    return {"area": "mc-bias", "groups": groups}


def _write_generated(name: str, markdown: str, data: dict) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / f"{name}.md").write_text(markdown, encoding="utf-8")
    (GENERATED_DIR / f"{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"  → {GENERATED_DIR / name}.{{md,json}}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Utilidades de dossier de auditoría.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("corpus-stats", help="métricas cuantitativas del corpus")
    p2 = sub.add_parser(
        "sample", help="muestreo determinista para revisión cualitativa"
    )
    p2.add_argument("--bank", required=True, choices=("listening", "objectives"))
    p2.add_argument("--level", required=True, choices=LEVELS)
    p2.add_argument("--count", type=int, default=5)
    p2.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p2.add_argument("--json", action="store_true")

    sub.add_parser("curriculum-stats", help="resumen de objetivos por nivel")
    sub.add_parser("speaking-stats", help="distribución de escenarios speaking")
    sub.add_parser(
        "mc-bias",
        help="sesgo posicional de respuestas (corpus, checks, exámenes)",
    )
    args = parser.parse_args()

    if args.command == "corpus-stats":
        stats = listening_stats()
        md = listening_stats_markdown(stats)
        print(md)
        _write_generated("listening-corpus-stats", md, stats)
        return 0

    if args.command == "sample":
        items = sample_items(args.bank, args.level, args.count, args.seed)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=1))
        else:
            for it in items:
                print(f"- {it.get('id')}: {it.get('script', '')[:120]}")
        return 0

    if args.command == "curriculum-stats":
        data = curriculum_stats()
        for lv in data["levels"]:
            print(
                f"{lv['level']}: {lv['objectives']} objetivos, "
                f"{lv['checks_per_objective']} checks/obj, "
                f"{lv['activities_per_objective']} act/obj · "
                f"listen {lv['objectives_with_listening']}, "
                f"scen {lv['objectives_with_scenario']}"
            )
        _write_generated("curriculum-stats", "# Resumen curricular por nivel\n\n" + (
            "\n".join(
                f"- {lv['level']}: {lv['objectives']} objetivos, "
                f"{lv['checks_per_objective']} checks/obj, "
                f"{lv['activities_per_objective']} act/obj, "
                f"{lv['objectives_with_listening']} con listening, "
                f"{lv['objectives_with_scenario']} con escenario."
                for lv in data["levels"]
            )
        ), data)
        return 0

    if args.command == "speaking-stats":
        data = speaking_stats()
        print(json.dumps(data, ensure_ascii=False, indent=1))
        _write_generated("speaking-stats", "# Escenarios speaking\n\n```json\n" +
                         json.dumps(data, ensure_ascii=False, indent=1) + "\n```", data)
        return 0

    if args.command == "mc-bias":
        data = mc_position_bias()
        for group in data["groups"]:
            total = sum(group["counts"].values())
            shares = {
                str(k): f"{100.0 * v / total:.1f}%" if total else "0%"
                for k, v in sorted(group["counts"].items())
            }
            print(
                f"{group['name']:<28} n={group['items']:<4} "
                f"{'  '.join(f'{k}:{v}' for k, v in shares.items())}"
            )
        _write_generated(
            "mc-position-bias",
            "# Sesgo posicional de respuestas (opción marcada)\n\n"
            "> Distribución de `correct_index`/`answer_index`. Un reparto "
            "equilibrado rondaría ~25% por posición (opciones de 4).\n\n```json\n"
            + json.dumps(data, ensure_ascii=False, indent=1)
            + "\n```",
            data,
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

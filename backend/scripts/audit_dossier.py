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
import math
import random
import re
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


# =============================================================================
# V3.70 · Auditoría pedagógica + CEFR — cinco ejes, SOLO LECTURA
# =============================================================================
# Instrumentos de medición de la release V3.70. NO son ruta de producto: leen
# contenido, instrumentos y constantes declaradas, y dejan la evidencia
# reproducible en `docs/audit/generated/`. Ninguno escribe en `data/` ni en
# `curriculum/`.

# Bandas de dificultad escalar por nivel, columna «difficulty_vector típico» de
# `docs/audit/CEFR-REFERENCE.md`.
DIFFICULTY_BANDS: dict[str, tuple[int, int]] = {
    "A1": (1, 2),
    "A2": (2, 3),
    "B1": (2, 4),
    "B2": (3, 5),
    "C1": (4, 5),
    "C2": (4, 6),
}

# Marcadores léxicos de connected speech REAL: la referencia exige
# «reducciones/linking, no solo contracciones suaves».
CONNECTED_SPEECH_MARKERS: tuple[str, ...] = (
    "gonna",
    "wanna",
    "gotta",
    "dunno",
    "whaddaya",
    "whatcha",
    "kinda",
    "sorta",
    "lemme",
    "gimme",
    "ain't",
    "oughta",
    "shoulda",
    "woulda",
    "coulda",
    "y'know",
)

STOPWORDS = frozenset(
    (
        "a an the of to in on at for and or but is are was were am be been "
        "being i you he she it we they me him her us them my your his its our "
        "their this that these those do does did done have has had with from "
        "by as not no yes so if then than there here what which who whom "
        "whose when where why how can could should would will shall may might "
        "must"
    ).split()
)

# Artefactos declarados por modalidad (Eje 2). La EXISTENCIA se comprueba en
# disco: `None` significa «no hay artefacto declarado».
MODALITY_ARTIFACTS: dict[str, dict[str, str | None]] = {
    "vocabulary": {"scorer": "lexicon.py", "ui": "vocabulary"},
    "grammar": {"scorer": "grammar.py", "ui": "grammar"},
    "pronunciation": {"scorer": "pronunciation.py", "ui": "pronunciation"},
    "listening": {"scorer": "listening.py", "ui": "listening"},
    "speaking": {"scorer": "speaking.py", "ui": "speaking"},
    # V3.73.1 (Opción A): la UI de `reading` dejó de ser el directorio de
    # feature `features/reading` (retirado con `ReadingPractice`) y pasa a ser
    # el **chat con destreza** `/chat/lectura`. La asimetría no cambia: UI sí,
    # scorer propio no y corpus no (ver `UI_ARTIFACT_PATHS`).
    "reading": {"scorer": "reading.py", "ui": "chat:lectura"},
    "writing": {"scorer": "writing.py", "ui": "writing"},
    "interaction": {"scorer": "interaction.py", "ui": "conversation"},
    "mediation": {"scorer": None, "ui": None},
}

SERVICES_DIR = BACKEND_DIR / "services"
FRONTEND_FEATURES_DIR = REPO_DIR / "frontend" / "src" / "features"

# Dónde se comprueba la existencia de cada artefacto de UI declarado. Por
# defecto, un artefacto es un **directorio** de `frontend/src/features`; las
# entradas de aquí lo sobreescriben con (tipo, ruta) porque su UI vive en otro
# sitio. V3.73.1: `reading` se sirve desde el router de chat con destreza.
UI_ARTIFACT_PATHS: dict[str, tuple[str, str]] = {
    "chat:lectura": ("file", "frontend/src/router/chat.ts"),
}


def _ui_exists(ui: str | None) -> bool:
    """Existencia real del artefacto de UI declarado (regla de medición)."""
    if not ui:
        return False
    override = UI_ARTIFACT_PATHS.get(ui)
    if override is not None:
        kind, rel = override
        path = REPO_DIR / rel
        return path.is_dir() if kind == "dir" else path.is_file()
    return (FRONTEND_FEATURES_DIR / str(ui)).is_dir()

# Canal de corrección declarado por destreza (Eje 3): las dos vías del proyecto
# son «determinista» y «LLM»; `None` = sin canal propio.
FEEDBACK_CHANNELS: dict[str, dict[str, str | None]] = {
    "grammar": {
        "deterministic": "services/grammar.py (regex + confidence)",
        "llm": "policy.CORRECTNESS_GUIDANCE via context.build_system_prompt",
    },
    "writing": {
        "deterministic": "services/writing.py (rubrica)",
        "llm": "services/writing_llm.py (solo extrae evidencia)",
    },
    "speaking": {
        "deterministic": "services/speaking.py (rubrica)",
        "llm": "services/speaking_llm.py (solo extrae evidencia)",
    },
    "pronunciation": {
        "deterministic": "services/phonetics.py + pronunciation.py",
        "llm": None,
    },
    "listening": {"deterministic": "scoring por respuesta (MC)", "llm": None},
    "vocabulary": {
        "deterministic": "lexicon/evidence (ledger lexico)",
        "llm": None,
    },
    "reading": {"deterministic": None, "llm": None},
    "interaction": {
        "deterministic": "services/interaction.py (telemetria)",
        "llm": None,
    },
    "mediation": {"deterministic": None, "llm": None},
}


def _content_words(text: object) -> list[str]:
    words = re.findall(r"[a-z']+", str(text or "").lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def _has_realized_connected_speech(item: dict) -> bool:
    """True si la transcripción contiene una reducción REAL, no una contracción."""
    text = " ".join(
        str(item.get(key) or "")
        for key in ("transcript", "clean_transcript", "script")
    ).lower()
    return any(marker in text for marker in CONNECTED_SPEECH_MARKERS)


def _inference_needs_integration(item: dict) -> bool:
    """False si el ítem de inferencia se resuelve con una palabra literal."""
    transcript = (
        item.get("clean_transcript")
        or item.get("transcript")
        or item.get("script")
        or ""
    )
    options = item.get("options") or []
    index = item.get("answer_index")
    if not transcript or not isinstance(index, int):
        return True
    if not 0 <= index < len(options):
        return True
    correct = _content_words(options[index])
    if not correct:
        return True
    heard = set(_content_words(transcript))
    matched = sum(1 for word in correct if word in heard)
    return matched / len(correct) < 0.6


def _correct_is_longest(options: list, correct_index: int) -> bool:
    lengths = [len(str(o)) for o in options or []]
    if not lengths or not 0 <= correct_index < len(lengths):
        return False
    longest = max(lengths)
    return lengths.count(longest) == 1 and lengths[correct_index] == longest


def _mc_summary(pairs: list) -> dict:
    pairs = list(pairs)
    if not pairs:
        return {"n": 0}
    longest = sum(1 for opts, idx in pairs if _correct_is_longest(opts, idx))
    positions = Counter(idx for _, idx in pairs)
    return {
        "n": len(pairs),
        "correct_is_longest": longest,
        "correct_is_longest_pct": round(100.0 * longest / len(pairs), 1),
        "positions": {str(k): v for k, v in sorted(positions.items())},
    }


def _json_entries(name: str) -> list:
    path = BACKEND_DIR / "curriculum" / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "entries", "corpus", "scenarios", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _objective_summary() -> dict:
    out: dict[str, dict] = {}
    for level in load_all_levels():
        objs = level.objectives()
        phases = Counter(a.phase or "practice" for o in objs for a in o.activities)
        out[level.level] = {
            "modules": len(level.modules),
            "units": sum(len(m.units) for m in level.modules),
            "objectives": len(objs),
            "checks": sum(len(o.checks) for o in objs),
            "activities": sum(len(o.activities) for o in objs),
            "production_checks": len(level.production_checks),
            "phases": dict(phases),
            "objectives_without_activities": sum(
                1 for o in objs if not o.activities
            ),
            "objectives_without_checks": sum(1 for o in objs if not o.checks),
            "objectives_with_listening": sum(1 for o in objs if o.listening_items),
            "objectives_with_scenario": sum(1 for o in objs if o.scenario_ids),
            "checks_out_of_objective_skills": sum(
                1
                for o in objs
                for c in o.checks
                if c.skill not in set(o.skills)
            ),
        }
    return out


# --- Eje 1 · Adecuación CEFR real del contenido -----------------------------


def cefr_adequacy() -> dict:
    """¿El contenido A1..C2 es de su nivel? (V3.70 · Eje 1)."""
    from services.curriculum import load_assessments

    corpus = corpus_items()
    by = _by_level(corpus)
    levels: dict[str, dict] = {}
    previous: dict | None = None
    monotonic_wpm = True
    monotonic_difficulty = True
    for level in LEVELS:
        items = by.get(level, [])
        if not items:
            levels[level] = {"n": 0}
            continue
        d_band = DIFFICULTY_BANDS[level]
        w_band = REFERENCE_BANDS[level]["wpm"]
        diffs = [
            difficulty_from_vector(q.get("difficulty_vector") or {}) for q in items
        ]
        rates = [float(q.get("speech_rate") or 0) for q in items]
        out_d = [
            q["id"]
            for q, d in zip(items, diffs, strict=True)
            if not d_band[0] <= d <= d_band[1]
        ]
        out_w = [
            q["id"]
            for q, w in zip(items, rates, strict=True)
            if w and not w_band[0] <= w <= w_band[1]
        ]
        declared = [q for q in items if q.get("connected_speech")]
        realized = [q for q in declared if _has_realized_connected_speech(q)]
        inference = [q for q in items if q.get("skill") == "inference"]
        levels[level] = {
            "n": len(items),
            "difficulty_band": list(d_band),
            "difficulty_mean": _mean(diffs),
            "difficulty_min": min(diffs),
            "difficulty_max": max(diffs),
            "difficulty_out_of_band": len(out_d),
            "difficulty_out_of_band_ids": out_d[:20],
            "wpm_band": list(w_band),
            "wpm_mean": _mean(rates),
            "wpm_min": min(rates),
            "wpm_max": max(rates),
            "wpm_out_of_band": len(out_w),
            "wpm_out_of_band_ids": out_w[:20],
            "connected_speech_declared": len(declared),
            "connected_speech_realized": len(realized),
            "connected_speech_unrealized_ids": [
                q["id"] for q in declared if q not in realized
            ][:20],
            "inference_items": len(inference),
            "inference_requiring_integration": sum(
                1 for q in inference if _inference_needs_integration(q)
            ),
            "speakers": len({q.get("speaker_id") for q in items}),
            "accents": len({q.get("accent") for q in items}),
        }
        if previous is not None:
            if levels[level]["wpm_max"] < previous["wpm_max"]:
                monotonic_wpm = False
            if levels[level]["difficulty_mean"] < previous["difficulty_mean"]:
                monotonic_difficulty = False
        previous = levels[level]

    assessments = load_assessments()
    exam_pairs = [
        (item.options, item.correct_index)
        for exam in assessments.exams.values()
        for item in exam.items
    ]
    placement_pairs = [
        (item.options, item.correct_index) for item in assessments.placement.items
    ]
    checks_pairs = [
        (c.options, c.correct_index)
        for level in load_all_levels()
        for o in level.objectives()
        for c in o.checks
    ]
    return {
        "area": "cefr-adequacy",
        "levels": levels,
        "monotonic_max_wpm": monotonic_wpm,
        "monotonic_mean_difficulty": monotonic_difficulty,
        "mc": {
            "corpus": _mc_summary(
                [(q.get("options") or [], q.get("answer_index")) for q in corpus]
            ),
            "curriculum_checks": _mc_summary(checks_pairs),
            "exams": _mc_summary(exam_pairs),
            "placement": _mc_summary(placement_pairs),
        },
        "objectives": _objective_summary(),
    }


def cefr_adequacy_markdown(data: dict) -> str:
    lines = [
        "# Adecuación CEFR del contenido (V3.70 · Eje 1)",
        "",
        "> Generado por `python -m scripts.audit_dossier cefr-adequacy`.",
        "> Criterio: `docs/audit/CEFR-REFERENCE.md` — referencia INTERNA del",
        "> proyecto, no un documento CEFR normativo. Solo lectura.",
        "",
        "## Corpus de listening por nivel",
        "",
        (
            "| Nivel | N | dificultad media (min–max) | banda | fuera | "
            "wpm media (min–max) | banda wpm | fuera |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for level in LEVELS:
        s = data["levels"][level]
        if not s.get("n"):
            lines.append(f"| {level} | 0 | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {level} | {s['n']} | {s['difficulty_mean']} "
            f"({s['difficulty_min']}–{s['difficulty_max']}) | "
            f"{s['difficulty_band'][0]}–{s['difficulty_band'][1]} | "
            f"{s['difficulty_out_of_band']} | {s['wpm_mean']} "
            f"({s['wpm_min']}–{s['wpm_max']}) | "
            f"{s['wpm_band'][0]}–{s['wpm_band'][1]} | "
            f"{s['wpm_out_of_band']} |"
        )
    lines += [
        "",
        "## Propiedades declaradas frente a realizadas",
        "",
        "| Nivel | CS declarado | CS realizado | inference | con integración |",
        "|---|---|---|---|---|",
    ]
    for level in LEVELS:
        s = data["levels"][level]
        if not s.get("n"):
            lines.append(f"| {level} | — | — | — | — |")
            continue
        lines.append(
            f"| {level} | {s['connected_speech_declared']} | "
            f"{s['connected_speech_realized']} | {s['inference_items']} | "
            f"{s['inference_requiring_integration']} |"
        )
    lines += [
        "",
        f"- **Monotonía de wpm máximo entre niveles:** "
        f"{data['monotonic_max_wpm']}",
        f"- **Monotonía de dificultad media entre niveles:** "
        f"{data['monotonic_mean_difficulty']}",
        "",
        "## Ítems de opción múltiple",
        "",
        "| Fuente | N | correcta = opción más larga | reparto de posiciones |",
        "|---|---|---|---|",
    ]
    for name, summary in data["mc"].items():
        if not summary.get("n"):
            lines.append(f"| {name} | 0 | — | — |")
            continue
        positions = ", ".join(
            f"{k}:{v}" for k, v in summary["positions"].items()
        )
        lines.append(
            f"| {name} | {summary['n']} | "
            f"{summary['correct_is_longest']} "
            f"({summary['correct_is_longest_pct']}%) | {positions} |"
        )
    lines += [
        "",
        "## Currículo por nivel",
        "",
        (
            "| Nivel | Módulos | Unidades | Objetivos | Checks | Actividades | "
            "Production | Sin act. | Sin checks | Con listening | Con escenario |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for level, s in data["objectives"].items():
        lines.append(
            f"| {level} | {s['modules']} | {s['units']} | {s['objectives']} | "
            f"{s['checks']} | {s['activities']} | {s['production_checks']} | "
            f"{s['objectives_without_activities']} | "
            f"{s['objectives_without_checks']} | "
            f"{s['objectives_with_listening']} | "
            f"{s['objectives_with_scenario']} |"
        )
    lines += [
        "",
        "Fuente: `services.listening.QUESTION_BANK` (ítems `cNNN`),",
        "`services.curriculum.load_all_levels()` y `load_assessments()`.",
    ]
    return "\n".join(lines)


# --- Eje 2 · Cobertura de destrezas -----------------------------------------


def _modality_content_counts(modalities) -> dict[str, dict]:
    counts = {
        m: {"objectives": 0, "checks": 0, "corpus": 0} for m in modalities
    }
    for level in load_all_levels():
        for obj in level.objectives():
            for skill in set(obj.skills):
                if skill in counts:
                    counts[skill]["objectives"] += 1
            for check in obj.checks:
                if check.skill in counts:
                    counts[check.skill]["checks"] += 1
    corpus_map = {
        "listening": len(corpus_items()),
        "speaking": len(_json_entries("speaking_corpus.json"))
        + len(list_scenarios()),
        "pronunciation": len(_json_entries("pronunciation_corpus.json")),
        "interaction": len(_json_entries("conversation_corpus.json")),
    }
    for modality, total in corpus_map.items():
        if modality in counts:
            counts[modality]["corpus"] = total
    return counts


def skill_coverage() -> dict:
    """¿Están cubiertas las 9 modalidades? (V3.70 · Eje 2)."""
    from services import audio_library, cefr_matrix, mastery, skill_axis, skill_state

    matrix = cefr_matrix.load_matrix()
    matrix_skills = sorted(
        {s for lv in matrix.levels.values() for s in lv.skills}
    )
    content = _modality_content_counts(mastery.MASTERY_SKILLS)
    per_modality: dict[str, dict] = {}
    for modality in mastery.MASTERY_SKILLS:
        artifacts = MODALITY_ARTIFACTS.get(modality, {})
        scorer = artifacts.get("scorer")
        ui = artifacts.get("ui")
        entry = {
            "competences": len(
                skill_axis.COMPETENCES_BY_MODALITY.get(modality, ())
            ),
            "declared_in_matrix": modality in matrix_skills,
            "evidence_channel": skill_state.MODALITY_CHANNEL.get(modality),
            "scorer_module": scorer,
            "scorer_exists": bool(scorer)
            and (SERVICES_DIR / str(scorer)).exists(),
            "ui_feature": ui,
            "ui_exists": _ui_exists(ui),
        }
        entry.update(content.get(modality, {}))
        per_modality[modality] = entry

    gaps: list[dict] = []
    for modality, entry in per_modality.items():
        if not entry["competences"] and not entry["corpus"]:
            gaps.append(
                {"modality": modality, "reason": "sin competencias ni corpus"}
            )
        if not entry["evidence_channel"]:
            gaps.append(
                {"modality": modality, "reason": "sin canal de evidencia"}
            )
        if not entry["scorer_exists"]:
            gaps.append({"modality": modality, "reason": "sin scorer propio"})
        if not entry["ui_exists"]:
            gaps.append({"modality": modality, "reason": "sin feature de UI"})

    try:
        manifest = audio_library.load_manifest()
        recorded = len(manifest.entries)
        manifest_version = manifest.version
    except (FileNotFoundError, ValueError, OSError):
        recorded, manifest_version = 0, ""

    from services import content_validation
    from services.curriculum import LISTENING_CORPUS_TARGETS

    corpus_by_level = dict(Counter(q["level"] for q in corpus_items()))
    listening_targets = {
        level: {
            "declared": corpus_by_level.get(level, 0),
            "target": target,
            "pct": round(
                100.0 * corpus_by_level.get(level, 0) / target, 1
            )
            if target
            else 0.0,
        }
        for level, target in LISTENING_CORPUS_TARGETS.items()
    }
    scenarios = Counter(
        s.get("cefr_target") for s in list_scenarios()
    )
    return {
        "area": "skill-coverage",
        "modalities": per_modality,
        "gaps": gaps,
        "matrix_version": matrix.version,
        "matrix_skills": matrix_skills,
        "audio_library": {
            "manifest_version": manifest_version,
            "recorded_entries": recorded,
            "content_stats": content_validation.content_stats(),
        },
        "listening_targets": listening_targets,
        "scenarios_by_level": dict(scenarios),
    }


def skill_coverage_markdown(data: dict) -> str:
    lines = [
        "# Cobertura de destrezas (V3.70 · Eje 2)",
        "",
        "> Generado por `python -m scripts.audit_dossier skill-coverage`.",
        "> Matriz modalidad × artefacto declarado, con la EXISTENCIA comprobada",
        "> en disco. Solo lectura.",
        "",
        (
            "| Modalidad | Competencias | Matriz | Canal | Objetivos | Checks | "
            "Corpus | Scorer | UI |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for modality, s in data["modalities"].items():
        lines.append(
            f"| {modality} | {s['competences']} | "
            f"{'sí' if s['declared_in_matrix'] else 'NO'} | "
            f"{s['evidence_channel'] or 'NO'} | {s['objectives']} | "
            f"{s['checks']} | {s['corpus']} | "
            f"{s['scorer_module'] or '—'}"
            f"{'' if s['scorer_exists'] else ' (AUSENTE)'} | "
            f"{s['ui_feature'] or '—'}"
            f"{'' if s['ui_exists'] else ' (AUSENTE)'} |"
        )
    lines += [
        "",
        "## Huecos medidos",
        "",
        "| Modalidad | Hueco |",
        "|---|---|",
    ]
    for gap in data["gaps"]:
        lines.append(f"| {gap['modality']} | {gap['reason']} |")
    audio = data["audio_library"]
    lines += [
        "",
        "## Audio y objetivos de corpus",
        "",
        f"- Manifest de audio humano `{audio['manifest_version']}`: "
        f"**{audio['recorded_entries']}** entradas grabadas.",
        f"- Ítems de aprendizaje validados: "
        f"**{audio['content_stats']['total_validated_learning_items']}**.",
        "",
        "| Nivel | Corpus declarado | Objetivo | % del objetivo |",
        "|---|---|---|---|",
    ]
    for level, s in data["listening_targets"].items():
        lines.append(
            f"| {level} | {s['declared']} | {s['target']} | {s['pct']}% |"
        )
    scenarios = ", ".join(
        f"{k}:{v}" for k, v in sorted(data["scenarios_by_level"].items())
    )
    lines += [
        "",
        f"- Escenarios speaking por `cefr_target`: {scenarios}",
    ]
    return "\n".join(lines)


# --- Eje 3 · Feedback y corrección ------------------------------------------


def feedback_coverage() -> dict:
    """¿Qué se corrige, con qué mecanismo y con qué granularidad? (Eje 3)."""
    from services import grammar, policy
    from services import speaking as speaking_svc
    from services import writing as writing_svc

    per_modality: dict[str, dict] = {}
    for modality, channels in FEEDBACK_CHANNELS.items():
        deterministic = channels.get("deterministic")
        llm = channels.get("llm")
        per_modality[modality] = {
            "deterministic": deterministic,
            "llm": llm,
            "has_deterministic": bool(deterministic),
            "has_llm": bool(llm),
        }
    expected_levels = ["Pre-A1", *LEVELS]
    guidance_levels = sorted(policy.CORRECTNESS_GUIDANCE)
    return {
        "area": "feedback-coverage",
        "modalities": per_modality,
        "without_channel": sorted(
            m
            for m, e in per_modality.items()
            if not e["has_deterministic"] and not e["has_llm"]
        ),
        "score_only": sorted(
            m
            for m, e in per_modality.items()
            if e["has_deterministic"] and not e["has_llm"]
        ),
        "grammar_rules": len(grammar.RULES),
        "grammar_confirmed_threshold": grammar.CONFIRMED_THRESHOLD,
        "grammar_mastery_streak": grammar.MASTERY_STREAK,
        "writing_criteria": list(writing_svc.WRITING_CRITERIA),
        "speaking_criteria": list(speaking_svc.SPEAKING_CRITERIA),
        "correctness_guidance_levels": guidance_levels,
        "correctness_guidance_missing": [
            lv for lv in expected_levels if lv not in guidance_levels
        ],
        "feedback_categories": sorted(policy.FEEDBACK_CATEGORIES),
        "feedback_categories_count": len(policy.FEEDBACK_CATEGORIES),
    }


def feedback_coverage_markdown(data: dict) -> str:
    lines = [
        "# Feedback y corrección (V3.70 · Eje 3)",
        "",
        "> Generado por `python -m scripts.audit_dossier feedback-coverage`.",
        "> Declara el CANAL de corrección por destreza: determinista, LLM o",
        "> ninguno. Solo lectura.",
        "",
        "| Destreza | Determinista | LLM |",
        "|---|---|---|",
    ]
    for modality, s in data["modalities"].items():
        lines.append(
            f"| {modality} | {s['deterministic'] or 'NO'} | "
            f"{s['llm'] or 'NO'} |"
        )
    lines += [
        "",
        "## Cobertura de la política de corrección",
        "",
        f"- Reglas deterministas de grammar: **{data['grammar_rules']}** "
        f"(umbral de confirmación "
        f"{data['grammar_confirmed_threshold']}, racha de dominio "
        f"{data['grammar_mastery_streak']}).",
        f"- Criterios de rúbrica: writing **{len(data['writing_criteria'])}**, "
        f"speaking **{len(data['speaking_criteria'])}**.",
        f"- Categorías formales de feedback: "
        f"**{data['feedback_categories_count']}** "
        f"({', '.join(data['feedback_categories'])}).",
        f"- Niveles con guía de corrección: "
        f"{', '.join(data['correctness_guidance_levels'])}.",
        f"- Niveles SIN guía declarada: "
        f"{', '.join(data['correctness_guidance_missing']) or 'ninguno'}.",
        "",
        f"- Destrezas SIN ningún canal de corrección: "
        f"**{', '.join(data['without_channel']) or 'ninguna'}**.",
        f"- Destrezas con canal SOLO de puntuación (sin feedback textual): "
        f"**{', '.join(data['score_only']) or 'ninguna'}**.",
    ]
    return "\n".join(lines)


# --- Eje 4 · Validez de la afirmación de maestría ---------------------------


def mastery_claims() -> dict:
    """¿«Demostrado» significa lo que dice? (V3.70 · Eje 4)."""
    from services import (
        cefr_matrix,
        competence,
        evidence_depth,
        learner_skill,
        mastery,
        skill_axis,
        skill_state,
    )

    matrix = cefr_matrix.load_matrix()
    matrix_skills = sorted(
        {s for lv in matrix.levels.values() for s in lv.skills}
    )
    per_level: dict[str, dict] = {}
    novel_total = 0
    transfer_total = 0
    for level_id, level in matrix.levels.items():
        per_level[level_id] = {}
        for skill, req in level.skills.items():
            per_level[level_id][skill] = req.model_dump()
            novel_total += req.novel_required
            transfer_total += req.transfer_required
    empty_states = competence.competence_states([], "A1")
    return {
        "area": "mastery-claims",
        "states": list(competence.STATE_ORDER),
        "production_skills": list(competence.PRODUCTION_SKILLS),
        "support_skills": list(competence.SUPPORT_SKILLS),
        "mastery_modalities": list(mastery.MASTERY_SKILLS),
        "matrix_version": matrix.version,
        "matrix_skills": matrix_skills,
        "modality_channel_keys": sorted(skill_state.MODALITY_CHANNEL),
        "modalities_without_channel": sorted(
            set(mastery.MASTERY_SKILLS) - set(skill_state.MODALITY_CHANNEL)
        ),
        "modalities_without_matrix": sorted(
            set(mastery.MASTERY_SKILLS) - set(matrix_skills)
        ),
        "modalities_without_competences": sorted(
            m for m, c in skill_axis.COMPETENCES_BY_MODALITY.items() if not c
        ),
        "spacing_gate": {
            "min_samples": learner_skill.OBSERVED_MIN_SAMPLES,
            "min_days": learner_skill.OBSERVED_MIN_DAYS,
        },
        "production_item_types": list(evidence_depth.PRODUCTION_ITEM_TYPES),
        "matrix_novel_required_total": novel_total,
        "matrix_transfer_required_total": transfer_total,
        "matrix_per_level": per_level,
        "no_evidence_baseline": [
            {
                "skill": row["skill"],
                "state": row["state"],
                "demonstrated": row["demonstrated"],
                "estimated_band": row["estimated_band"],
            }
            for row in empty_states
        ],
        "evidence_depth_baseline": evidence_depth.evidence_depth_report(
            "grammar", "A1", 0
        ),
    }


def mastery_claims_markdown(data: dict) -> str:
    lines = [
        "# Validez de la afirmación de maestría (V3.70 · Eje 4)",
        "",
        "> Generado por `python -m scripts.audit_dossier mastery-claims`.",
        "> Contrasta las modalidades declaradas con la matriz CEFR, el canal de",
        "> evidencia y los mínimos del gate. Solo lectura.",
        "",
        "## Tres registros que deben coincidir",
        "",
        f"- Modalidades de `MASTERY_SKILLS`: **{len(data['mastery_modalities'])}**.",
        f"- Destrezas de la matriz CEFR "
        f"(`{data['matrix_version']}`): **{len(data['matrix_skills'])}**.",
        f"- Canales de evidencia (`MODALITY_CHANNEL`): "
        f"**{len(data['modality_channel_keys'])}**.",
        "",
        f"- Sin canal de evidencia: "
        f"**{', '.join(data['modalities_without_channel']) or 'ninguna'}**.",
        f"- Sin requisitos en matriz: "
        f"**{', '.join(data['modalities_without_matrix']) or 'ninguna'}**.",
        f"- Sin competencias declaradas: "
        f"**{', '.join(data['modalities_without_competences']) or 'ninguna'}**.",
        "",
        "## Gates declarados",
        "",
        f"- Estados: {', '.join(data['states'])}.",
        f"- Destrezas de producción: "
        f"{', '.join(data['production_skills'])}.",
        f"- Destrezas de apoyo (tope `functional`): "
        f"{', '.join(data['support_skills'])}.",
        f"- Gate espaciado: {data['spacing_gate']['min_samples']} muestras × "
        f"{data['spacing_gate']['min_days']} días.",
        f"- Tipos de ítem de producción: "
        f"{', '.join(data['production_item_types'])}.",
        f"- `novel_required` sumado en la matriz: "
        f"**{data['matrix_novel_required_total']}**.",
        f"- `transfer_required` sumado en la matriz: "
        f"**{data['matrix_transfer_required_total']}**.",
        "",
        "## Mínimos por nivel y destreza",
        "",
        "| Nivel | Destreza | Maestría | Confianza | Evidencia | Transfer | Novel |",
        "|---|---|---|---|---|---|---|",
    ]
    for level, skills in data["matrix_per_level"].items():
        for skill, req in skills.items():
            lines.append(
                f"| {level} | {skill} | {req['minimum_mastery']} | "
                f"{req['minimum_confidence']} | {req['minimum_evidence']} | "
                f"{req['transfer_required']} | {req['novel_required']} |"
            )
    lines += [
        "",
        "## Línea base sin evidencia",
        "",
        "| Destreza | Estado | Demostrado | Banda |",
        "|---|---|---|---|",
    ]
    for row in data["no_evidence_baseline"]:
        lines.append(
            f"| {row['skill']} | {row['state']} | "
            f"{row['demonstrated']} | {row['estimated_band']} |"
        )
    depth = data["evidence_depth_baseline"]
    lines += [
        "",
        f"- Profundidad de evidencia sin muestras (grammar A1): "
        f"`depth = {depth['depth']}`, `meets_matrix = "
        f"{depth['meets_matrix']}`.",
    ]
    return "\n".join(lines)


# --- Eje 5 · Instrumentos de nivelación -------------------------------------


def assessment_instruments() -> dict:
    """¿Son suficientes los instrumentos de nivelación? (V3.70 · Eje 5)."""
    from services import academy, adaptive, cefr, cefr_descriptors
    from services.curriculum import CEFR_ORDER, load_assessments

    assessments = load_assessments()
    exams: dict[str, dict] = {}
    for level_id, exam in assessments.exams.items():
        exams[level_id.upper()] = {
            "exam_id": level_id,
            "items": len(exam.items),
            "skills": sorted({i.skill for i in exam.items}),
            "min_per_skill": getattr(exam, "min_per_skill", None),
            "difficulties": dict(
                sorted(Counter(i.difficulty for i in exam.items).items())
            ),
        }
    remediation = {
        name: len(items)
        for name, items in (assessments.remediation or {}).items()
    }
    placement = assessments.placement

    # Techo de información de un ítem 1PL: p(1-p) ≤ 0.25 ⇒ SE ≥ 1/sqrt(n·0.25).
    max_info = 0.25
    se_best_case = round(
        1.0 / math.sqrt(academy.MAX_PLACEMENT_ITEMS * max_info), 4
    )

    disagreements: list[dict] = []
    emitted: set[str] = set()
    for step in range(2, 25):
        numeric = round(step * 0.25, 2)
        a = adaptive.numeric_to_level(numeric)
        b = academy.theta_to_level(numeric)
        score = max(0.0, min(1.0, (numeric - 1.0) / 5.0))
        c = cefr.heuristic_band(score)
        emitted.update({a, b, c})
        if not a == b == c:
            disagreements.append(
                {"numeric": numeric, "adaptive": a, "academy": b, "cefr": c}
            )
    ladder_emitted = sorted(
        {cefr_descriptors.band_for_numeric(step * 0.25) for step in range(2, 25)}
    )
    plus_bands = [
        b for b in cefr_descriptors.CEFR_LADDER if b.endswith("+")
    ]
    from services import course as course_svc

    return {
        "area": "assessment-instruments",
        "placement": {
            "items": len(placement.items),
            "skills": sorted({i.skill for i in placement.items}),
            "difficulties": dict(
                sorted(Counter(i.difficulty for i in placement.items).items())
            ),
            "mc": _mc_summary(
                [(i.options, i.correct_index) for i in placement.items]
            ),
            "max_items": academy.MAX_PLACEMENT_ITEMS,
            "min_items": academy.PLACEMENT_MIN_ITEMS,
            "se_threshold": academy.PLACEMENT_SE_THRESHOLD,
            "se_best_case_with_max_items": se_best_case,
            "se_threshold_reachable": se_best_case
            <= academy.PLACEMENT_SE_THRESHOLD,
        },
        "exams": exams,
        "levels_without_exam": sorted(set(CEFR_ORDER) - set(exams)),
        "remediation": remediation,
        "unit_sections": list(course_svc.UNIT_SECTIONS),
        "unit_gate_thresholds": dict(course_svc.UNIT_GATE_THRESHOLDS),
        "band_thresholds": {
            "levels_emitted": sorted(emitted),
            "disagreements": disagreements,
            "ladder_bands_emitted": ladder_emitted,
            "plus_bands_declared": plus_bands,
            "plus_bands_emitted_by_estimators": sorted(
                emitted.intersection(plus_bands)
            ),
        },
    }


def assessment_instruments_markdown(data: dict) -> str:
    placement = data["placement"]
    bands = data["band_thresholds"]
    plus_declared = ", ".join(bands["plus_bands_declared"]) or "ninguna"
    plus_emitted = (
        ", ".join(bands["plus_bands_emitted_by_estimators"]) or "ninguna"
    )
    lines = [
        "# Instrumentos de nivelación (V3.70 · Eje 5)",
        "",
        "> Generado por `python -m scripts.audit_dossier "
        "assessment-instruments`.",
        "> Mide placement, exámenes, remediación, gate de unidad y la",
        "> equivalencia de los umbrales de banda. Solo lectura.",
        "",
        "## Placement",
        "",
        f"- Ítems: **{placement['items']}** · máximo por sesión "
        f"{placement['max_items']} · mínimo {placement['min_items']}.",
        f"- Umbral de parada `SE < {placement['se_threshold']}`: mejor caso "
        f"alcanzable con {placement['max_items']} ítems **"
        f"SE ≥ {placement['se_best_case_with_max_items']}** ⇒ "
        f"alcanzable = **{placement['se_threshold_reachable']}**.",
        f"- Dificultades: "
        f"{', '.join(f'{k}:{v}' for k, v in placement['difficulties'].items())}.",
        f"- Correcta = opción más larga: "
        f"{placement['mc']['correct_is_longest']} de "
        f"{placement['mc']['n']} "
        f"({placement['mc']['correct_is_longest_pct']}%).",
        "",
        "## Exámenes finales",
        "",
        "| Nivel | Ítems | Destrezas | Mínimo por destreza |",
        "|---|---|---|---|",
    ]
    for level_id, exam in data["exams"].items():
        lines.append(
            f"| {level_id} | {exam['items']} | "
            f"{', '.join(exam['skills'])} | {exam['min_per_skill']} |"
        )
    lines += [
        "",
        f"- Niveles SIN examen final: "
        f"**{', '.join(data['levels_without_exam']) or 'ninguno'}**.",
        "",
        "## Remediación y gate de unidad",
        "",
    ]
    for name, count in data["remediation"].items():
        lines.append(f"- Banco de remediación `{name}`: {count} ítems.")
    lines += [
        "",
        f"- Secciones de unidad: {', '.join(data['unit_sections'])}.",
        f"- Umbrales de gate: "
        f"{', '.join(f'{k} {v}' for k, v in data['unit_gate_thresholds'].items())}.",
        "",
        "## Umbrales de banda",
        "",
        f"- Niveles emitidos por los tres estimadores: "
        f"{', '.join(data['band_thresholds']['levels_emitted'])}.",
        f"- Desacuerdos entre los tres estimadores: "
        f"**{len(data['band_thresholds']['disagreements'])}**.",
        f"- Bandas de la escalera alcanzables por `band_for_numeric`: "
        f"{', '.join(data['band_thresholds']['ladder_bands_emitted'])}.",
        f"- Sub-bandas declaradas (`+`): "
        f"{plus_declared} · emitidas por los estimadores: "
        f"{plus_emitted}.",
    ]
    return "\n".join(lines)


# =============================================================================
# V3.71 · Eje RA — auditoría de offline real (SOLO LECTURA)
# =============================================================================
# Instrumento del eje RA: NO es ruta de producto. No abre conexiones salientes,
# no descarga nada y no escribe en `data/` ni en `curriculum/`: lee codigo y
# disco, y sondea Ollama por loopback (que es justo lo que hace la app).
#
# Mide las dos preguntas del eje:
#   1. que puntos tocan la red y de que tipo son (loopback / lan / internet).
#      Los que importan son los `hidden`: dependencias que NO son un paso de
#      instalacion explicito y que pueden dispararse en TIEMPO DE USO.
#   2. si esta TODO lo que hace falta para funcionar sin Internet (manifiesto de
#      modelos: Piper ingles/espanol, Whisper y el modelo por defecto de Ollama).

# `kind`: loopback (misma maquina) · lan (red local) · internet (fuera).
# `hidden=True`: no es paso de instalacion, puede dispararse en tiempo de uso.
RUNTIME_TOUCHPOINTS: tuple[dict[str, object], ...] = (
    {
        "file": "services/llm.py",
        "needle": "ollama.AsyncClient()",
        "kind": "loopback",
        "hidden": False,
        "note": (
            "Cliente Ollama SIN argumentos: el endpoint es el default de la "
            "libreria (127.0.0.1:11434), no una constante de config.py"
        ),
    },
    {
        "file": "services/net_interfaces.py",
        "needle": "socket.getaddrinfo",
        "kind": "lan",
        "hidden": False,
        "note": (
            "V3.73: descubrimiento de la IP de LAN enumerando las direcciones "
            "del propio equipo. SIN salida a Internet (antes: socket UDP "
            "perezoso a 8.8.8.8, retirado en V3.73)"
        ),
    },
    {
        "file": "services/network.py",
        "needle": "socket.getaddrinfo",
        "kind": "lan",
        "hidden": False,
        "note": (
            "Resolucion mDNS real de <host>.local; sin respondedor devuelve "
            "False y la UI cae a la URL por IP"
        ),
    },
    {
        "file": "services/voice_downloads.py",
        "needle": "urllib.request.urlopen",
        "kind": "internet",
        "hidden": False,
        "note": (
            "Descarga de voces Piper desde huggingface.co "
            "(rhasspy/piper-voices). V3.71 (eje RD): usa urlopen con timeout "
            "REAL y verifica el Content-Length"
        ),
    },
    {
        "file": "services/tts.py",
        "needle": "from services import voice_downloads",
        "kind": "internet",
        "hidden": True,
        "note": (
            "DEPENDENCIA OCULTA: el TTS importa el descargador de voces en la "
            "descarga perezosa; el disparador real esta en routers/voz.py"
        ),
    },
    {
        "file": "routers/voz.py",
        "needle": "ensure_voice_for_language",
        "kind": "internet",
        "hidden": True,
        "note": (
            "DEPENDENCIA OCULTA EN RUTA DE PRODUCTO: un POST /api/tts de un "
            "idioma sin voz instalada dispara una descarga en caliente"
        ),
    },
    {
        "file": "services/stt.py",
        "needle": "download_root=str(WHISPER_DIR)",
        "kind": "internet",
        "hidden": True,
        "note": (
            "DEPENDENCIA OCULTA: si el modelo Whisper no esta en disco, "
            "faster_whisper lo descarga en la primera transcripcion"
        ),
    },
    {
        "file": "download_models.py",
        "needle": "from services.voice_downloads import download_voice, spec_for",
        "kind": "internet",
        "hidden": False,
        "note": (
            "Bootstrap EXPLICITO: voces Piper por defecto. V3.71 (eje RB): delega "
            "en el catalogo curado en vez de tener URL y urlretrieve propios; la "
            "primitiva de red vive en services/voice_downloads.py (timeout real)"
        ),
    },
    {
        "file": "download_models.py",
        "needle": "download_root=str(WHISPER_DIR)",
        "kind": "internet",
        "hidden": False,
        "note": "Bootstrap EXPLICITO: modelo Whisper",
    },
)

# Endpoint de Ollama: no vive en `config.py`, es el DEFAULT de la libreria. Se
# declara aqui para poder afirmarlo y para sondearlo (solo lectura).
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def network_touchpoints() -> list[dict]:
    """Puntos de red del backend, con su tipo y si el codigo sigue cuadrando.

    `match=False` significa que la declaracion DERIVO del codigo: el instrumento
    se autocomprueba en lugar de afirmar cosas que el arbol ya no dice.
    """
    out: list[dict] = []
    for declared in RUNTIME_TOUCHPOINTS:
        rel = str(declared["file"])
        path = BACKEND_DIR / rel
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        out.append(
            {
                **declared,
                "exists": path.is_file(),
                "match": str(declared["needle"]) in text,
            }
        )
    return out


def _artifact(artifact_id: str, label: str, path: Path) -> dict:
    size = path.stat().st_size if path.is_file() else 0
    try:
        rel = str(path.relative_to(REPO_DIR))
    except ValueError:
        rel = str(path)
    return {
        "id": artifact_id,
        "label": label,
        "path": rel.replace("\\", "/"),
        "exists": size > 0,
        "mb": round(size / 1_048_576, 1),
    }


def model_manifest() -> list[dict]:
    """Artefactos que deben estar EN DISCO para funcionar con la red cortada."""
    from config import (  # noqa: PLC0415 - import perezoso del backend
        PIPER_DIR,
        PIPER_VOICE,
        SPANISH_VOICE,
        WHISPER_DIR,
        WHISPER_SIZE,
    )

    items: list[dict] = []
    for voice_id, label in (
        (PIPER_VOICE, "Piper · voz inglesa por defecto"),
        (SPANISH_VOICE, "Piper · voz espanola por defecto"),
    ):
        for suffix in (".onnx", ".onnx.json"):
            items.append(
                _artifact(
                    f"piper:{voice_id}{suffix}",
                    f"{label} ({suffix})",
                    PIPER_DIR / f"{voice_id}{suffix}",
                )
            )
    whisper_files = (
        sorted(p for p in WHISPER_DIR.rglob("*") if p.is_file())
        if WHISPER_DIR.is_dir()
        else []
    )
    whisper_bytes = sum(p.stat().st_size for p in whisper_files)
    try:
        whisper_rel = str(WHISPER_DIR.relative_to(REPO_DIR)).replace("\\", "/")
    except ValueError:
        whisper_rel = str(WHISPER_DIR)
    items.append(
        {
            "id": f"whisper:{WHISPER_SIZE}",
            "label": f"faster-whisper `{WHISPER_SIZE}` (cache en disco)",
            "path": whisper_rel,
            "exists": len(whisper_files) > 0,
            "mb": round(whisper_bytes / 1_048_576, 1),
            "files": len(whisper_files),
        }
    )
    return items


def ollama_probe(timeout: float = 1.0) -> dict:
    """Sondea `/api/tags` por loopback. Sin Ollama en marcha, lo dice y sigue."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {
            "url": OLLAMA_TAGS_URL,
            "reachable": False,
            "error": type(exc).__name__,
            "models": [],
        }
    models = sorted(str(m.get("name", "")) for m in payload.get("models", []))
    return {"url": OLLAMA_TAGS_URL, "reachable": True, "error": None, "models": models}


def runtime_audit(probe_ollama: bool = False) -> dict:
    """Medicion del eje RA (solo lectura).

    Por defecto es **determinista**: no sondea Ollama, asi que su par en
    `docs/audit/generated/` se regenera byte a byte. El sondeo en vivo de Ollama
    es una medicion aparte y explicita (`--probe-ollama`) porque su resultado
    depende de la maquina.
    """
    from config import DEFAULT_MODEL  # noqa: PLC0415

    touchpoints = network_touchpoints()
    manifest = model_manifest()
    return {
        "touchpoints": touchpoints,
        "kinds": dict(Counter(str(t["kind"]) for t in touchpoints)),
        "hidden_internet": [
            f"{t['file']}:{t['needle']}"
            for t in touchpoints
            if t["hidden"] and t["kind"] == "internet"
        ],
        "drifted": [
            f"{t['file']}:{t['needle']}" for t in touchpoints if not t["match"]
        ],
        "manifest": manifest,
        "missing_artifacts": [a["id"] for a in manifest if not a["exists"]],
        "ollama": ollama_probe() if probe_ollama else None,
        "default_model": DEFAULT_MODEL,
    }


def runtime_audit_markdown(data: dict) -> str:
    lines = [
        "# Manifiesto de runtime y offline (eje RA de V3.71)",
        "",
        "> Generado por `python -m scripts.audit_dossier runtime-audit`.",
        "> Instrumento de SOLO LECTURA: no descarga ni escribe en `data/`.",
        "",
        "## 1. Puntos de red del backend",
        "",
        "| Fichero | needle | tipo | oculto | cuadra | nota |",
        "|---|---|---|---|---|---|",
    ]
    for t in data["touchpoints"]:
        lines.append(
            f"| `{t['file']}` | `{t['needle']}` | {t['kind']} | "
            f"{'SI' if t['hidden'] else 'no'} | {'si' if t['match'] else 'NO'} | "
            f"{t['note']} |"
        )
    lines += [
        "",
        f"- Reparto por tipo: {data['kinds']}",
        "- Dependencias de Internet NO declaradas (ocultas): "
        f"**{len(data['hidden_internet'])}**",
    ]
    for item in data["hidden_internet"]:
        lines.append(f"  - `{item}`")
    drifted = data["drifted"] or "ninguna"
    lines.append(f"- Declaraciones que ya NO cuadran con el codigo: {drifted}")
    lines += [
        "",
        "## 2. Manifiesto de modelos (debe estar en disco sin Internet)",
        "",
        "| id | artefacto | ruta | presente | MB |",
        "|---|---|---|---|---|",
    ]
    for a in data["manifest"]:
        lines.append(
            f"| `{a['id']}` | {a['label']} | `{a['path']}` | "
            f"{'si' if a['exists'] else 'NO'} | {a['mb']} |"
        )
    missing = data["missing_artifacts"]
    lines += [
        "",
        f"- Ausentes: **{len(missing)}**"
        + (f" -> {missing}" if missing else " (nada que descargar)"),
        "",
        "## 3. Ollama (loopback)",
        "",
        "- Endpoint: `http://127.0.0.1:11434` (default de la libreria `ollama`, "
        "**no** declarado en `config.py`)",
    ]
    ollama = data["ollama"]
    if ollama is None:
        lines.append(
            "- Estado: **no sondeado** (medicion determinista). El sondeo en vivo "
            "es `runtime-audit --probe-ollama`."
        )
    else:
        lines += [
            f"- Alcanzable: {'si' if ollama['reachable'] else 'NO'}"
            + (f" ({ollama['error']})" if ollama["error"] else ""),
            f"- Modelo por defecto `{data['default_model']}` instalado: "
            f"{'si' if data['default_model'] in ollama['models'] else 'NO'}",
            f"- Modelos visibles: {ollama['models'] or 'ninguno'}",
        ]
    lines.append("")
    return "\n".join(lines)


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
    # V3.70 · auditoría pedagógica + CEFR (cinco ejes, solo lectura).
    sub.add_parser(
        "cefr-adequacy",
        help="adecuación CEFR del contenido (V3.70 · eje 1)",
    )
    sub.add_parser(
        "skill-coverage",
        help="cobertura de las 9 modalidades (V3.70 · eje 2)",
    )
    sub.add_parser(
        "feedback-coverage",
        help="canales de feedback y corrección (V3.70 · eje 3)",
    )
    sub.add_parser(
        "mastery-claims",
        help="validez de la afirmación de maestría (V3.70 · eje 4)",
    )
    sub.add_parser(
        "assessment-instruments",
        help="placement, exámenes y umbrales de banda (V3.70 · eje 5)",
    )
    # V3.71 · eje RA — manifiesto de runtime y offline (solo lectura).
    p_ra = sub.add_parser(
        "runtime-audit",
        help="puntos de red y manifiesto de modelos offline (V3.71 · eje RA)",
    )
    p_ra.add_argument(
        "--probe-ollama",
        action="store_true",
        help="sondea Ollama por loopback (rompe el determinismo del par generado)",
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
                label = it.get("script") or it.get("can_do") or ""
                print(f"- {it.get('id')}: {label[:120]}")
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

    if args.command == "cefr-adequacy":
        data = cefr_adequacy()
        md = cefr_adequacy_markdown(data)
        print(md)
        _write_generated("cefr-adequacy", md, data)
        return 0

    if args.command == "skill-coverage":
        data = skill_coverage()
        md = skill_coverage_markdown(data)
        print(md)
        _write_generated("skill-coverage", md, data)
        return 0

    if args.command == "feedback-coverage":
        data = feedback_coverage()
        md = feedback_coverage_markdown(data)
        print(md)
        _write_generated("feedback-coverage", md, data)
        return 0

    if args.command == "mastery-claims":
        data = mastery_claims()
        md = mastery_claims_markdown(data)
        print(md)
        _write_generated("mastery-claims", md, data)
        return 0

    if args.command == "assessment-instruments":
        data = assessment_instruments()
        md = assessment_instruments_markdown(data)
        print(md)
        _write_generated("assessment-instruments", md, data)
        return 0

    if args.command == "runtime-audit":
        data = runtime_audit(probe_ollama=args.probe_ollama)
        md = runtime_audit_markdown(data)
        print(md)
        _write_generated("runtime-audit", md, data)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

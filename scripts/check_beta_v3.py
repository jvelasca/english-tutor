"""Gate automatizado de Beta V3.0 (feature freeze pedagógico).

Comprueba que el stack V2.7–V2.12 sigue presente y que el Curriculum Quality
Dashboard cumple los umbrales del freeze. Falla (exit 1) si falta un módulo,
una ruta o una métrica mínima.

Uso:
    python scripts/check_beta_v3.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Umbrales del freeze (docs/BETA_V3.md).
MIN_OVERALL = 90.0
MIN_DEPTH = 80.0
MIN_LOOP = 99.0
MIN_SECTION = 99.0  # listening/speaking/interaction/assessment/review
MIN_LISTENING_ALIGN = 99.0

REQUIRED_MODULES: tuple[str, ...] = (
    "services.speaking_mission",
    "services.assessment_v2",
    "services.fsrs",
    "services.evidence_graph",
    "services.curriculum_coverage",
)

REQUIRED_ATTRS: dict[str, tuple[str, ...]] = {
    "services.speaking_mission": ("MISSION_PHASES", "evaluate_attempt"),
    "services.assessment_v2": ("ASSESSMENT_KINDS", "mastery_evidence_gate"),
    "services.fsrs": ("schedule", "explain", "due_queue"),
    "services.evidence_graph": ("build_level_graph", "explain_because"),
    "services.curriculum": ("LISTENING_FOCUS_BY_LEVEL",),
}

REQUIRED_DOCS: tuple[str, ...] = (
    "docs/BETA_V3.md",
    "docs/UNIT_ARCHITECTURE.md",
    "docs/LISTENING_CURRICULUM.md",
    "docs/SPEAKING_MISSION.md",
    "docs/ASSESSMENT_2.md",
    "docs/FSRS.md",
    "docs/EVIDENCE_GRAPH.md",
)

REQUIRED_ROUTES: tuple[str, ...] = (
    "/api/academy/speaking/mission/start",
    "/api/academy/assessment/v2/ladder",
    "/api/academy/fsrs/due",
    "/api/academy/evidence-graph",
)


def _fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)


def check_modules(failures: list[str]) -> None:
    sys.path.insert(0, str(BACKEND))
    for name in REQUIRED_MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 — gate de release
            _fail(f"módulo ausente {name}: {exc}", failures)
            continue
        for attr in REQUIRED_ATTRS.get(name, ()):
            if not hasattr(mod, attr):
                _fail(f"{name} sin atributo {attr}", failures)
    # curriculum attrs
    try:
        curriculum = importlib.import_module("services.curriculum")
        for attr in REQUIRED_ATTRS["services.curriculum"]:
            if not hasattr(curriculum, attr):
                _fail(f"services.curriculum sin {attr}", failures)
    except Exception as exc:  # noqa: BLE001
        _fail(f"services.curriculum: {exc}", failures)


def check_docs(failures: list[str]) -> None:
    for rel in REQUIRED_DOCS:
        if not (ROOT / rel).is_file():
            _fail(f"doc ausente: {rel}", failures)


def check_routes(failures: list[str]) -> None:
    sys.path.insert(0, str(BACKEND))
    try:
        from fastapi.routing import APIRoute
        from main import app  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _fail(f"no se pudo cargar FastAPI app: {exc}", failures)
        return

    paths: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            paths.add(route.path)
            continue
        # FastAPI reciente envuelve los APIRouter en `_IncludedRouter`.
        original = getattr(route, "original_router", None)
        if original is None:
            continue
        for nested in original.routes:
            if isinstance(nested, APIRoute):
                paths.add(nested.path)

    for required in REQUIRED_ROUTES:
        if required not in paths:
            _fail(f"ruta ausente: {required}", failures)


def check_quality(failures: list[str]) -> None:
    sys.path.insert(0, str(BACKEND))
    try:
        from services.curriculum_coverage import curriculum_quality_report
    except Exception as exc:  # noqa: BLE001
        _fail(f"curriculum_quality_report: {exc}", failures)
        return
    report = curriculum_quality_report()
    overall = float(report.get("overall") or 0.0)
    if overall < MIN_OVERALL:
        _fail(f"overall {overall} < {MIN_OVERALL}", failures)

    dims = report.get("dimensions") or {}
    depth = float((dims.get("depth") or {}).get("score") or 0.0)
    if depth < MIN_DEPTH:
        _fail(f"depth {depth} < {MIN_DEPTH}", failures)

    for key in (
        "listening",
        "speaking",
        "interaction",
        "assessment",
        "review",
    ):
        score = float((dims.get(key) or {}).get("score") or 0.0)
        if score < MIN_SECTION:
            _fail(f"{key} {score} < {MIN_SECTION}", failures)

    loop = report.get("learning_loop") or {}
    mean_loop = float(loop.get("mean_loop_pct") or 0.0)
    if mean_loop < MIN_LOOP:
        _fail(f"loop {mean_loop} < {MIN_LOOP}", failures)

    listening = report.get("listening_curriculum") or {}
    align = float((listening.get("overall") or {}).get("alignment_pct") or 0.0)
    if align < MIN_LISTENING_ALIGN:
        _fail(f"listening alignment {align} < {MIN_LISTENING_ALIGN}", failures)


def main() -> int:
    failures: list[str] = []
    check_docs(failures)
    check_modules(failures)
    check_routes(failures)
    check_quality(failures)

    if failures:
        print("FAIL: Beta V3.0 gate")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("OK: Beta V3.0 gate (feature freeze pedagógico V2.7–V2.12)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

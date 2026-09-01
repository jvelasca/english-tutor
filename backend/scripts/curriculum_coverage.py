"""Auditoría de cobertura curricular (V2.4) desde terminal/CI.

Recorre Pre-A1 → C2 × 7 secciones, cruza el contenido del curso con los bancos de
destrezas (listening + speaking) y emite `curriculum_coverage_report.json` (el
JSON completo) más un resumen legible por nivel. Sale con código 1 si existe
algún hueco `empty` en una sección de un nivel con curso (para poder usarlo como
guard en CI).

Uso:
    python -m scripts.curriculum_coverage
    python -m scripts.curriculum_coverage --strict   # exit 1 si hay huecos `empty`
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

from services.curriculum_coverage import (  # noqa: E402
    EMPTY,
    curriculum_coverage_report,
    curriculum_quality_report,
)

# Mapa estado → marcador corto para el resumen legible.
_STATUS_MARK: dict[str, str] = {"complete": "OK ", "partial": "~  ", "empty": "-- "}


def _human_summary(report: dict) -> None:
    """Resumen legible: tabla nivel × sección con OK/~ /-- y conteos."""
    section_order = report["levels"][0]["sections"]
    header = ["nivel"] + [s["section"][:9] for s in section_order]
    print()
    print("CURRICULUM COVERAGE (nivel x seccion)")
    print("  " + "  ".join(f"{h:>10}" for h in header))
    for lv in report["levels"]:
        cells = [lv["level"]]
        for s in lv["sections"]:
            mark = _STATUS_MARK[s["status"]]
            cells.append(f"{mark}{s['count']}")
        print("  " + "  ".join(f"{c:>10}" for c in cells))
    print("\nLeyenda: OK = todas las unidades, ~ = parcial, -- = vacio.")


def _human_quality(report: dict) -> None:
    """Resumen legible del Curriculum Quality Dashboard (V2.6)."""
    dims = report["dimensions"]
    print("\nCURRICULUM QUALITY DASHBOARD")
    print(f"  {'Overall':<14}{report['overall']:>6}")
    for key in ("coverage", "depth", "listening", "speaking", "interaction",
                "assessment", "review"):
        print(f"  {key.capitalize():<14}{dims[key]['score']:>6}")
    print("\n  Nivel  Depth  UnitCov")
    for lv in report["by_level"]:
        print(f"  {lv['level']:<6}{lv['depth']:>7}{lv['unit_coverage_mean']:>9}")

    loop = report["learning_loop"]
    print(f"\nUNIT LEARNING LOOP (media por unidad: {loop['mean_loop_pct']}%)")
    for entry in loop["by_phase"]:
        print(
            f"  {entry['phase']:<12}{entry['coverage_pct']:>6} "
            f"({entry['covered_units']}/{entry['units']} unidades)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría de cobertura curricular.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 si existe algún hueco `empty` en una sección con curso",
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        help="imprime además el Curriculum Quality Dashboard (V2.6) como JSON",
    )
    args = parser.parse_args()

    report = curriculum_coverage_report()

    print("CURRICULUM COVERAGE REPORT")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    _human_summary(report)

    metric = report["metric"]["total_curriculum_coverage"]
    print(
        "\nTOTAL CURRICULUM COVERAGE: "
        f"{metric['populated_cells']}/{metric['total_cells']} celdas "
        f"({metric['coverage_pct']}%)"
    )
    print(
        "TOTAL VALIDATED LEARNING ITEMS: "
        f"{report['metric']['total_validated_learning_items']}"
    )

    quality = curriculum_quality_report()
    _human_quality(quality)
    if args.quality:
        print("\nCURRICULUM QUALITY REPORT")
        print(json.dumps(quality, ensure_ascii=False, indent=2))

    # Huecos reales: sección `empty` en un nivel que SÍ tiene curso.
    gaps = [
        (lv["level"], s["section"])
        for lv in report["levels"]
        if lv["has_course"]
        for s in lv["sections"]
        if s["status"] == EMPTY
    ]
    if gaps:
        print(f"\nHUECOS ({len(gaps)}):")
        for level, section in gaps:
            print(f"  - {level}: {section} (vacio)")
        return 1 if args.strict else 0

    print("\nSin huecos `empty` en niveles con curso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

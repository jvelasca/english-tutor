"""Auditoría de cobertura curricular (V2.4).

Recorre el curso completo (Pre-A1 → C2) por las 7 secciones canónicas y cruza el
contenido del curso (`curriculum/<level>.json`) con los bancos de destrezas
(listening corpus + speaking scenarios), para responder con datos a la pregunta
"¿el alumno puede recorrer completo A1→C2?".

Distingue dos métricas complementarias:
- `total_validated_learning_items` (V2.2, en `content_validation`): cuántos
  ejercicios fiables existen.
- `total_curriculum_coverage` (aquí): cuánto del curso completo está cubierto.

Separación de responsabilidades:
- `services.course` expone la plantilla de 7 secciones *por unidad*.
- Este módulo la agrega *por nivel* y añade el cruce con los bancos de destrezas,
  de modo que un hueco (p. ej. "listening tiene 0 ítems en C1") sea visible.

Puro y determinista: solo lee contenido estático; no escribe nada ni toca la base
de datos.
"""
from __future__ import annotations

from collections import Counter

from services import course as course_svc
from services.curriculum import CEFR_ORDER, Level, load_level
from services.listening import QUESTION_BANK
from services.speaking_scenarios import list_scenarios

# Versión del instrumento de auditoría de cobertura. Identifica QUÉ instrumento
# produjo el reporte, para que dos reportes sean comparables aunque el contenido
# evolucione.
COVERAGE_REPORT_VERSION = "1.0.0"

# Ids de nivel en el orden del informe. Pre-A1 es una banda de competencia
# (descriptor Can-Do) sin curso propio; el resto son cursos con contenido.
COVERAGE_LEVEL_IDS: tuple[str, ...] = (
    "pre-a1",
    "a1",
    "a2",
    "b1",
    "b2",
    "c1",
    "c2",
)

# Estados tri-estado de una sección a nivel de curso completo.
COMPLETE = "complete"
PARTIAL = "partial"
EMPTY = "empty"


def _units_with_sections(level: Level) -> list[list[dict]]:
    """Plantilla de 7 secciones por cada unidad del nivel (de `services.course`)."""
    return [
        course_svc.unit_sections(level, unit)
        for mod in level.modules
        for unit in mod.units
    ]


def coverage_sections(level: Level) -> list[dict]:
    """Conteo por sección a nivel de curso completo (todo el nivel).

    Agrega `unit_sections` de todas las unidades del nivel. Para cada sección
    canónica devuelve `count` (ítems totales del nivel), `populated_units`
    (unidades con contenido en esa sección), `total_units`, el tri-estado
    `status` y `needs_content` (status == empty).

    El tri-estado es honesto por construcción:
    - `complete`: todas las unidades del nivel tienen contenido en la sección.
    - `partial`: algunas unidades la tienen (p. ej. review/assessment solo en el
      módulo Final).
    - `empty`: ninguna unidad la tiene.
    """
    units_sections = _units_with_sections(level)
    total_units = len(units_sections)
    counts: dict[str, int] = {s: 0 for s in course_svc.UNIT_SECTIONS}
    populated: dict[str, int] = {s: 0 for s in course_svc.UNIT_SECTIONS}

    for sections in units_sections:
        for s in sections:
            key = s["section"]
            counts[key] += s["count"]
            if s["count"] > 0:
                populated[key] += 1

    result: list[dict] = []
    for section in course_svc.UNIT_SECTIONS:
        count = counts[section]
        populated_units = populated[section]
        if populated_units == 0:
            status = EMPTY
        elif populated_units == total_units:
            status = COMPLETE
        else:
            status = PARTIAL
        result.append(
            {
                "section": section,
                "count": count,
                "populated_units": populated_units,
                "total_units": total_units,
                "status": status,
                "needs_content": status == EMPTY,
            }
        )
    return result


def bank_intersection() -> dict[str, dict[str, int]]:
    """Cruce de los bancos de destrezas contra cada nivel CEFR (A1..C2).

    Devuelve `{level: {"listening": n, "speaking": n}}`. El listening cuenta ítems
    del banco por su `level`; el speaking cuenta escenarios por su `cefr_target`.
    Los niveles sin contenido en el banco (listening C1/C2, speaking C2) quedan en
    0, haciendo visible el hueco entre banco y curso.
    """
    listening_by_level = Counter(q["level"] for q in QUESTION_BANK)
    speaking_by_level = Counter(s["cefr_target"] for s in list_scenarios())
    return {
        level: {
            "listening": listening_by_level.get(level, 0),
            "speaking": speaking_by_level.get(level, 0),
        }
        for level in CEFR_ORDER
    }


def _level_count(level: Level) -> int:
    return sum(1 for mod in level.modules for _unit in mod.units)


def level_coverage(level_id: str) -> dict:
    """Cobertura de un nivel de curso (a1..c2) por las 7 secciones.

    Devuelve `{level_id, level, has_course, band_only, units, objectives,
    sections}`. A las secciones listening/speaking se les añade `bank_count`
    (ítems disponibles en su banco) para distinguir "contenido del curso" de
    "contenido del banco no integrado".
    """
    level = load_level(level_id)
    banks = bank_intersection()
    sections = coverage_sections(level)
    sections_with_bank = [
        {**s, "bank_count": banks.get(level.level, {}).get(s["section"], 0)}
        for s in sections
    ]
    return {
        "level_id": level.level_id,
        "level": level.level,
        "has_course": True,
        "band_only": False,
        "units": _level_count(level),
        "objectives": len(level.objectives()),
        "sections": sections_with_bank,
    }


def _pre_a1_coverage() -> dict:
    """Entrada Pre-A1: banda de competencia (Can-Do) sin curso propio."""
    sections = [
        {
            "section": s,
            "count": 0,
            "populated_units": 0,
            "total_units": 0,
            "status": EMPTY,
            "needs_content": True,
            "bank_count": 0,
        }
        for s in course_svc.UNIT_SECTIONS
    ]
    return {
        "level_id": "pre-a1",
        "level": "Pre-A1",
        "has_course": False,
        "band_only": True,
        "units": 0,
        "objectives": 0,
        "sections": sections,
    }


def _all_level_coverages() -> list[dict]:
    """Cobertura de todos los niveles en el orden del informe (Pre-A1 → C2)."""
    return [_pre_a1_coverage()] + [
        level_coverage(level_id) for level_id in COVERAGE_LEVEL_IDS[1:]
    ]


def coverage_metric() -> dict:
    """Métrica TOTAL CURRICULUM COVERAGE sobre la matriz 7 niveles × 7 secciones.

    Una celda (nivel, sección) está "poblada" si la sección tiene contenido en el
    curso (`count > 0`). Pre-A1 (sin curso) aporta 7 celdas vacías de forma
    honesta. Devuelve `{populated_cells, total_cells, coverage_pct, by_level,
    by_section}`.
    """
    levels = _all_level_coverages()
    total_cells = 0
    populated_cells = 0
    by_level: dict[str, dict[str, int]] = {}
    by_section: dict[str, dict[str, int]] = {
        s: {"populated": 0, "total": 0} for s in course_svc.UNIT_SECTIONS
    }

    for lv in levels:
        level_id = lv["level_id"]
        populated = 0
        total = 0
        for s in lv["sections"]:
            total += 1
            total_cells += 1
            by_section[s["section"]]["total"] += 1
            if s["count"] > 0:
                populated += 1
                populated_cells += 1
                by_section[s["section"]]["populated"] += 1
        by_level[level_id] = {"populated": populated, "total": total}

    coverage_pct = (
        round(populated_cells / total_cells * 100, 1) if total_cells else 0.0
    )
    return {
        "populated_cells": populated_cells,
        "total_cells": total_cells,
        "coverage_pct": coverage_pct,
        "by_level": by_level,
        "by_section": by_section,
    }


def curriculum_coverage_report() -> dict:
    """Reporte completo de cobertura curricular (curriculum_coverage_report.json).

    Incluye las dos métricas (validated items + coverage) y el desglose por nivel.
    El `total_validated_learning_items` se toma de `content_validation` (fuente
    única, anti-drift) mediante un import diferido para evitar ciclos de import.
    """
    from services.content_validation import content_stats  # noqa: F401 (late import)

    stats = content_stats()
    return {
        "version": COVERAGE_REPORT_VERSION,
        "metric": {
            "total_validated_learning_items": stats["total_validated_learning_items"],
            "total_curriculum_coverage": stats["total_curriculum_coverage"],
        },
        "levels": _all_level_coverages(),
    }

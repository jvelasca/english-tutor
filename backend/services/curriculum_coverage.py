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
from services.curriculum import (
    CEFR_ORDER,
    LEARNING_PHASES,
    LISTENING_FOCUS_BY_LEVEL,
    SUBSKILLS,
    Level,
    load_level,
)
from services.listening import QUESTION_BANK
from services.speaking_scenarios import list_scenarios

# Versión del instrumento de auditoría de cobertura. Identifica QUÉ instrumento
# produjo el reporte, para que dos reportes sean comparables aunque el contenido
# evolucione.
COVERAGE_REPORT_VERSION = "1.0.0"

# Versión del Curriculum Quality Dashboard (V2.6). Independiente de la versión del
# instrumento de cobertura: mide profundidad/unidad, no celdas de la matriz.
QUALITY_REPORT_VERSION = "1.0.0"

# Alias de las fases canónicas del Unit Learning Loop. La fuente de verdad vive en
# `services.curriculum.LEARNING_PHASES`; se re-exporta aquí con el nombre histórico
# para no romper a los consumidores del instrumento (tests y CLI).
LEARNING_LOOP_PHASES: tuple[str, ...] = LEARNING_PHASES

# Referencia de "curso denso" para normalizar la densidad de objetivos por unidad
# (V2.6). Un nivel con ~3 objetivos por unidad (≈ una lección con 3 objetivos) se
# considera completo; por debajo, el nivel queda "fino".
OBJECTIVE_DENSITY_TARGET = 3.0

# Referencia de "curso serio" para el volumen total de objetivos por nivel (V2.6).
# A1 —el único nivel con curso completo de 10 unidades— tiene 23 objetivos; un
# nivel CEFR serio ronda los ~20. Captura que C2 (5) es mucho más fino que A1 (23),
# algo que la densidad por unidad no detecta (B2 tiene 3 unidades densas y 9
# objetivos).
OBJECTIVE_VOLUME_TARGET = 20.0

# Pesos del CEFR DEPTH SCORE (V2.6). Suman 1.0; cada componente vale 0..1 y se
# documenta en `depth_score()` para que la cifra sea auditable, no una caja negra.
# Ajuste V2.6-C1b: se sube el peso del *volumen* (tamaño total de objetivos) y se
# baja el de la *densidad* (objetivos/unidad). La densidad por sí sola premiaba a
# B2 (3 unidades densas con 9 objetivos) por encima de A2 (7 unidades con 11), lo
# que es contra-intuitivo: un curso "serio" necesita volumen, no solo unidades
# llenas. Con estos pesos C2 (5 objetivos) cae claramente por debajo de A1 (23).
DEPTH_WEIGHTS: dict[str, float] = {
    "objective_density": 0.20,
    "objective_volume": 0.35,
    "section_coverage": 0.35,
    "subskill_breadth": 0.10,
}

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


# --- UNIT COVERAGE (V2.6) ----------------------------------------------------
# Segunda métrica: "cobertura" (¿hay algo en cada celda nivel×sección?) ≠
# "unidad completa" (¿todas las unidades del nivel integran cada sección?). Aquí
# el grano es la unidad: 42/49 celdas no dice que A1 Listening esté en 3 de 10
# unidades. `unit_coverage` lo hace explícito.

def _unit_objectives(unit) -> list:
    """Objetivos de una unidad en orden de aparición (aplanando lecciones)."""
    return [o for les in unit.lessons for o in les.objectives]


def _unit_module(level: Level, unit) -> object | None:
    """Módulo que contiene a la unidad, o None."""
    for mod in level.modules:
        if any(u.id == unit.id for u in mod.units):
            return mod
    return None


def unit_coverage(level: Level) -> dict:
    """Cobertura por unidad (V2.6): la métrica "UNIT COVERAGE".

    Para cada unidad del nivel: cuántas de las 7 secciones canónicas están
    pobladas (`covered_sections`), su `coverage_pct` (0..100) y qué secciones
    faltan (`missing`). Agrega `by_section` (de `units` unidades, en cuántas hay
    contenido en cada sección) y `overall` (unidades completas + media de
    cobertura por unidad). Pre-A1 (sin curso) no pasa por aquí.
    """
    units: list[dict] = []
    section_units = {s: 0 for s in course_svc.UNIT_SECTIONS}
    section_populated = {s: 0 for s in course_svc.UNIT_SECTIONS}
    for mod in level.modules:
        for unit in mod.units:
            sections = course_svc.unit_sections(level, unit)
            units.append(
                {
                    "unit_id": unit.id,
                    "unit_title": unit.title,
                    "module_id": mod.id,
                    "module_title": mod.title,
                    "unit_order": unit.order,
                    "objectives": len(_unit_objectives(unit)),
                    "sections": [
                        {"section": s["section"], "count": s["count"],
                         "populated": s["count"] > 0}
                        for s in sections
                    ],
                    "covered_sections": sum(1 for s in sections if s["count"] > 0),
                    "coverage_pct": round(
                        sum(1 for s in sections if s["count"] > 0)
                        / len(course_svc.UNIT_SECTIONS)
                        * 100,
                        1,
                    ),
                    "missing": [s["section"] for s in sections if s["count"] == 0],
                }
            )
            for s in sections:
                section_units[s["section"]] += 1
                if s["count"] > 0:
                    section_populated[s["section"]] += 1

    by_section: list[dict] = []
    for section in course_svc.UNIT_SECTIONS:
        su = section_units[section]
        sp = section_populated[section]
        if sp == 0:
            status = EMPTY
        elif sp == su:
            status = COMPLETE
        else:
            status = PARTIAL
        by_section.append(
            {
                "section": section,
                "units": su,
                "with_content": sp,
                "coverage_pct": round(sp / su * 100, 1) if su else 0.0,
                "status": status,
            }
        )

    total_units = len(units)
    return {
        "level_id": level.level_id,
        "level": level.level,
        "total_units": total_units,
        "units": units,
        "by_section": by_section,
        "overall": {
            "complete_units": sum(1 for u in units if not u["missing"]),
            "mean_unit_coverage_pct": round(
                sum(u["coverage_pct"] for u in units) / total_units, 1
            )
            if total_units
            else 0.0,
        },
    }


# --- CEFR DEPTH SCORE (V2.6) -------------------------------------------------

def depth_score(level: Level) -> dict:
    """CEFR DEPTH SCORE (V2.6): profundidad curricular de un nivel (0..100).

    Complementa `coverage_metric` ("¿hay algo en cada celda nivel×sección?") con
    "¿es un curso denso, grande y completo, no una colección fina de contenidos?".
    Cuatro componentes ponderados (ver `DEPTH_WEIGHTS`), todos 0..1 y auditables:

    - `objective_density`: objetivos por unidad frente a `OBJECTIVE_DENSITY_TARGET`
      (estructura: ¿las unidades están llenas?).
    - `objective_volume`: objetivos totales del nivel frente a
      `OBJECTIVE_VOLUME_TARGET` (tamaño: ¿es un curso serio o una muestra?). Captura
      que C2 (5) es mucho más fino que A1 (23), algo que la densidad no ve.
    - `section_coverage`: media de `populated_units/total_units` sobre las 7
      secciones (¿todas las unidades integran listening/review/assessment?).
    - `subskill_breadth`: subskills distintos declarados / subskills posibles de
      las destrezas declaradas (¿entrena matiz/registro/discurso, no solo lo básico?).
    """
    sections = coverage_sections(level)
    objectives = level.objectives()
    total_units = _level_count(level)

    per_unit = len(objectives) / total_units if total_units else 0.0
    density = min(per_unit / OBJECTIVE_DENSITY_TARGET, 1.0)

    volume = min(len(objectives) / OBJECTIVE_VOLUME_TARGET, 1.0)

    ratios = [
        s["populated_units"] / s["total_units"] if s["total_units"] else 1.0
        for s in sections
    ]
    section_cov = sum(ratios) / len(ratios) if ratios else 1.0

    declared_skills = {s for o in objectives for s in o.skills}
    possible = {ss for s in declared_skills for ss in SUBSKILLS.get(s, ())}
    distinct = {ss for o in objectives for ss in o.subskills}
    breadth = len(distinct) / len(possible) if possible else 1.0

    components = {
        "objective_density": {
            "value": round(density, 3),
            "weight": DEPTH_WEIGHTS["objective_density"],
            "objectives": len(objectives),
            "units": total_units,
            "per_unit": round(per_unit, 3),
            "target_per_unit": OBJECTIVE_DENSITY_TARGET,
        },
        "objective_volume": {
            "value": round(volume, 3),
            "weight": DEPTH_WEIGHTS["objective_volume"],
            "objectives": len(objectives),
            "target_objectives": OBJECTIVE_VOLUME_TARGET,
        },
        "section_coverage": {
            "value": round(section_cov, 3),
            "weight": DEPTH_WEIGHTS["section_coverage"],
        },
        "subskill_breadth": {
            "value": round(breadth, 3),
            "weight": DEPTH_WEIGHTS["subskill_breadth"],
            "distinct_subskills": len(distinct),
            "possible_subskills": len(possible),
        },
    }
    # El score se deriva de los valores *redondeados* que se exponen en
    # `components`, para que la cifra sea reproducible a partir del JSON del
    # reporte (auditable, no una caja negra).
    score = round(
        100
        * sum(
            DEPTH_WEIGHTS[k] * components[k]["value"] for k in DEPTH_WEIGHTS
        ),
        1,
    )
    return {
        "level_id": level.level_id,
        "level": level.level,
        "score": score,
        "components": components,
    }


# --- UNIT LEARNING LOOP (V2.6) ------------------------------------------------
# El bucle pedagógico por unidad (auditoría externa, PRIORIDAD Nº1). Mide, por
# unidad, cuáles de las 9 fases canónicas están presentes con evidencia real. No
# reestructura el contenido (eso es V2.7+); hace el hueco visible y medible.

def unit_learning_loop(level: Level, unit) -> dict:
    """Fases del Unit Learning Loop presentes en una unidad (V2.6).

    Mapea cada fase canónica a la evidencia real de la unidad:
    - `introduce`: ítems de presentación (`concepts` + `vocabulary`).
    - `practice`: actividades + checks (práctica controlada).
    - `listen`: referencias al banco de listening + skill/checks de listening.
    - `speak`: referencias a escenarios + skill/checks de speaking.
    - `interact`: objetivos con subskills de interacción/turnos.
    - `retrieve`/`transfer`/`review`/`assess`: actividades con `phase` explícito
      (marcador V2.6). Sin contenido etiquetado aún quedan en 0 (retrieve/transfer)
      o solo en el módulo "Final" (assess/review, su realización histórica).

    Devuelve `{phases, covered_phases, total_phases, loop_pct}`. Es la tercera
    dimensión (LEVEL → UNIT → fase) que `coverage_metric`/`depth_score` no ven.
    """
    objs = _unit_objectives(unit)
    mod = _unit_module(level, unit)
    is_final = bool(mod) and "final" in (mod.title or "").lower()
    checks = [c for o in objs for c in o.checks]
    activities = [a for o in objs for a in o.activities]

    introduce = sum(len(o.concepts) + len(o.vocabulary) for o in objs)
    practice = sum(len(o.activities) + len(o.checks) for o in objs)
    listen = (
        sum(len(o.listening_items) for o in objs)
        + sum(1 for o in objs if "listening" in o.skills)
        + sum(1 for c in checks if c.skill == "listening")
    )
    speak = (
        sum(len(o.scenario_ids) for o in objs)
        + sum(1 for o in objs if "speaking" in o.skills)
        + sum(1 for c in checks if c.skill == "speaking")
    )
    interact = sum(
        1
        for o in objs
        if any(s in ("interaction", "turn_taking") for s in o.subskills)
    )
    # Fases con marcador explícito (V2.6): se leen del `phase` de las actividades.
    # Las fases `assess`/`review` siguen contando además el módulo Final (checks y
    # objetivos de repaso), que es su realización histórica.
    retrieve = sum(1 for a in activities if a.phase == "retrieve")
    transfer = sum(1 for a in activities if a.phase == "transfer")
    assess = (len(checks) if is_final else 0) + sum(
        1 for a in activities if a.phase == "assess"
    )
    review = (len(objs) if is_final else 0) + sum(
        1 for a in activities if a.phase == "review"
    )

    evidence = {
        "introduce": introduce,
        "practice": practice,
        "listen": listen,
        "speak": speak,
        "interact": interact,
        "retrieve": retrieve,
        "transfer": transfer,
        "assess": assess,
        "review": review,
    }
    phases = [
        {"phase": phase, "evidence": evidence[phase], "covered": evidence[phase] > 0}
        for phase in LEARNING_LOOP_PHASES
    ]
    covered = sum(1 for p in phases if p["covered"])
    return {
        "unit_id": unit.id,
        "unit_title": unit.title,
        "module_id": mod.id if mod is not None else None,
        "is_final": is_final,
        "phases": phases,
        "covered_phases": covered,
        "total_phases": len(LEARNING_LOOP_PHASES),
        "loop_pct": round(covered / len(LEARNING_LOOP_PHASES) * 100, 1),
    }


def loop_coverage(level: Level) -> dict:
    """Cobertura del Unit Learning Loop a nivel de curso (V2.6).

    Agrega `unit_learning_loop` sobre todas las unidades del nivel: `by_phase`
    (cuántas unidades cubren cada fase) y `mean_loop_pct` (media de fases cubiertas
    por unidad). Devuelve el hueco explícito: `retrieve`/`transfer` en 0 (aún sin
    contenido etiquetado) y `assess`/`review` solo en el módulo Final.
    """
    units = [
        unit_learning_loop(level, unit)
        for mod in level.modules
        for unit in mod.units
    ]
    phase_units = {p: 0 for p in LEARNING_LOOP_PHASES}
    phase_covered = {p: 0 for p in LEARNING_LOOP_PHASES}
    for loop in units:
        for p in loop["phases"]:
            phase_units[p["phase"]] += 1
            if p["covered"]:
                phase_covered[p["phase"]] += 1

    total_units = len(units)
    by_phase = [
        {
            "phase": phase,
            "units": phase_units[phase],
            "covered_units": phase_covered[phase],
            "coverage_pct": (
                round(phase_covered[phase] / phase_units[phase] * 100, 1)
                if phase_units[phase]
                else 0.0
            ),
        }
        for phase in LEARNING_LOOP_PHASES
    ]
    return {
        "level_id": level.level_id,
        "level": level.level,
        "total_units": total_units,
        "phases": list(LEARNING_LOOP_PHASES),
        "by_phase": by_phase,
        "units": units,
        "mean_loop_pct": (
            round(sum(u["loop_pct"] for u in units) / total_units, 1)
            if total_units
            else 0.0
        ),
    }


# --- DRILL-DOWN (V2.6) -------------------------------------------------------
# Tercera dimensión: LEVEL → UNIT → LESSON → OBJECTIVE → {actividad, check,
# evidencia}. Permite afirmar "esta unidad está realmente completa" revisando
# cada objetivo, no solo el tri-estado agregado de la sección.

def unit_detail(level_id: str, unit_id: str) -> dict:
    """Drill-down jerárquico (V2.6): LEVEL → UNIT → LESSON → OBJECTIVE.

    Expone la dimensión que `coverage_metric`/`depth_score` no muestran: cada
    objetivo de la unidad con sus destrezas, subskills, nº de actividades/checks y
    referencias a bancos (`listening_items`/`scenario_ids`), más las 7 secciones
    canónicas de la unidad. Lanza `KeyError` si la unidad no existe en el nivel.
    """
    level = load_level(level_id)
    mod_obj = None
    unit = None
    for mod in level.modules:
        for u in mod.units:
            if u.id == unit_id:
                mod_obj = mod
                unit = u
                break
        if unit is not None:
            break
    if unit is None:
        raise KeyError(f"unidad '{unit_id}' no encontrada en '{level_id}'")

    lessons: list[dict] = []
    for les in unit.lessons:
        objectives = [
            {
                "objective_id": o.id,
                "title": o.title,
                "can_do": o.can_do,
                "skills": o.skills,
                "subskills": o.subskills,
                "activities": len(o.activities),
                "checks": len(o.checks),
                "listening_items": o.listening_items,
                "scenario_ids": o.scenario_ids,
            }
            for o in les.objectives
        ]
        lessons.append(
            {
                "lesson_id": les.id,
                "lesson_title": les.title,
                "lesson_order": les.order,
                "objectives": objectives,
            }
        )

    sections = course_svc.unit_sections(level, unit)
    return {
        "level_id": level.level_id,
        "level": level.level,
        "unit_id": unit.id,
        "unit_title": unit.title,
        "module_id": mod_obj.id,
        "module_title": mod_obj.title,
        "unit_order": unit.order,
        "lessons": lessons,
        "sections": [
            {"section": s["section"], "count": s["count"], "populated": s["count"] > 0}
            for s in sections
        ],
    }


# --- LISTENING CURRICULUM (V2.8) ----------------------------------------------

def _listening_objectives(level: Level) -> list:
    """Objetivos con evidencia real de escucha (skill, checks o banco)."""
    return [
        o
        for o in level.objectives()
        if "listening" in o.skills
        and (
            o.listening_items
            or any(c.skill == "listening" for c in o.checks)
        )
    ]


def listening_curriculum(level: Level) -> dict:
    """Alineación del listening curricular con el foco del nivel (V2.8).

    Complementa la cobertura por unidad (`listening` en las 7 secciones) con
    *qué* subskills de escucha entrena cada nivel (progresión CEFR). Un objetivo
    está alineado si declara al menos un subskill del foco de su nivel.
    """
    focus = LISTENING_FOCUS_BY_LEVEL.get(level.level_id.lower(), ())
    objs = _listening_objectives(level)
    aligned = [
        o
        for o in objs
        if any(ss in focus for ss in o.subskills)
    ]
    return {
        "level_id": level.level_id,
        "level": level.level,
        "focus_subskills": list(focus),
        "listening_objectives": len(objs),
        "aligned_objectives": len(aligned),
        "alignment_pct": round(len(aligned) / len(objs) * 100, 1) if objs else 100.0,
        "missing_objectives": [
            o.id for o in objs if not any(ss in focus for ss in o.subskills)
        ],
    }


def listening_curriculum_report() -> dict:
    """Informe agregado de progresión de listening (V2.8)."""
    level_ids = COVERAGE_LEVEL_IDS[1:]
    by_level = [listening_curriculum(load_level(lid)) for lid in level_ids]
    aligned = sum(lv["aligned_objectives"] for lv in by_level)
    total = sum(lv["listening_objectives"] for lv in by_level)
    return {
        "by_level": by_level,
        "overall": {
            "listening_objectives": total,
            "aligned_objectives": aligned,
            "alignment_pct": round(aligned / total * 100, 1) if total else 100.0,
        },
    }


# --- CURRICULUM QUALITY DASHBOARD (V2.6) -------------------------------------

def curriculum_quality_report() -> dict:
    """Curriculum Quality Dashboard (V2.6): una única cifra por dimensión.

    Agrega sobre los 6 niveles con curso (A1..C2; Pre-A1 es banda sin curso):
    - `coverage`: cobertura de la matriz nivel×sección (`coverage_metric`).
    - `depth`: media del CEFR DEPTH SCORE.
    - `listening`/`speaking`/`interaction`/`assessment`/`review`: media de la
      cobertura por unidad de cada sección (`populated_units/total_units`).
    `overall` es la media de las 7 dimensiones. `by_level` desglosa profundidad y
    cobertura media de unidad por nivel, para ver exactamente dónde flaquea.
    """
    level_ids = COVERAGE_LEVEL_IDS[1:]  # a1..c2
    coverages = {lid: unit_coverage(load_level(lid)) for lid in level_ids}
    depths = {lid: depth_score(load_level(lid)) for lid in level_ids}
    loops = {lid: loop_coverage(load_level(lid)) for lid in level_ids}
    metric = coverage_metric()

    def _section_pct(cov: dict, section: str) -> float:
        return next(
            s for s in cov["by_section"] if s["section"] == section
        )["coverage_pct"]

    def _section_dim(section: str) -> float:
        vals = [_section_pct(cov, section) for cov in coverages.values()]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    depth_mean = (
        round(sum(d["score"] for d in depths.values()) / len(depths), 1)
        if depths
        else 0.0
    )

    dimensions = {
        "coverage": {
            "score": metric["coverage_pct"],
            "label": "Matriz nivel×sección",
        },
        "depth": {"score": depth_mean, "label": "CEFR Depth Score (media)"},
        "listening": {
            "score": _section_dim("listening"),
            "label": "Listening por unidad",
        },
        "speaking": {
            "score": _section_dim("speaking"),
            "label": "Speaking por unidad",
        },
        "interaction": {
            "score": _section_dim("interaction"),
            "label": "Interaction por unidad",
        },
        "assessment": {
            "score": _section_dim("assessment"),
            "label": "Assessment por unidad",
        },
        "review": {"score": _section_dim("review"), "label": "Review por unidad"},
    }
    overall = round(
        sum(d["score"] for d in dimensions.values()) / len(dimensions), 1
    )

    by_level = []
    for lid in level_ids:
        cov = coverages[lid]
        by_level.append(
            {
                "level_id": lid,
                "level": cov["level"],
                "depth": depths[lid]["score"],
                "unit_coverage_mean": cov["overall"]["mean_unit_coverage_pct"],
                "sections": {
                    s["section"]: s["coverage_pct"] for s in cov["by_section"]
                },
            }
        )

    # Unit Learning Loop (V2.6): bloque aditivo, no una dimensión más del
    # dashboard. Mide, por fase y por nivel, cuántas unidades cierran el bucle.
    phase_units: dict[str, int] = {p: 0 for p in LEARNING_LOOP_PHASES}
    phase_covered: dict[str, int] = {p: 0 for p in LEARNING_LOOP_PHASES}
    loop_by_level: list[dict] = []
    for lid in level_ids:
        lp = loops[lid]
        loop_by_level.append(
            {
                "level_id": lid,
                "level": lp["level"],
                "mean_loop_pct": lp["mean_loop_pct"],
            }
        )
        for entry in lp["by_phase"]:
            phase_units[entry["phase"]] += entry["units"]
            phase_covered[entry["phase"]] += entry["covered_units"]
    learning_loop = {
        "phases": list(LEARNING_LOOP_PHASES),
        "mean_loop_pct": round(
            sum(entry["mean_loop_pct"] for entry in loop_by_level)
            / len(loop_by_level),
            1,
        )
        if loop_by_level
        else 0.0,
        "by_phase": [
            {
                "phase": p,
                "units": phase_units[p],
                "covered_units": phase_covered[p],
                "coverage_pct": (
                    round(phase_covered[p] / phase_units[p] * 100, 1)
                    if phase_units[p]
                    else 0.0
                ),
            }
            for p in LEARNING_LOOP_PHASES
        ],
        "by_level": loop_by_level,
    }

    listening = listening_curriculum_report()

    return {
        "version": QUALITY_REPORT_VERSION,
        "overall": overall,
        "dimensions": dimensions,
        "by_level": by_level,
        "learning_loop": learning_loop,
        "listening_curriculum": listening,
    }


def quality_report_delta(before: dict, after: dict) -> dict:
    """Delta before/after del dashboard (V2.6).

    Para dejar de desarrollar "a sensación": cada cambio de contenido debe mover
    una cifra concreta. Devuelve `{overall, dimensions, by_level}` con
    `{before, after, delta}` (delta redondeado a 1 decimal).
    """
    def _delta(a: float, b: float) -> float:
        return round(b - a, 1)

    return {
        "overall": {
            "before": before["overall"],
            "after": after["overall"],
            "delta": _delta(before["overall"], after["overall"]),
        },
        "dimensions": {
            key: {
                "before": before["dimensions"][key]["score"],
                "after": after["dimensions"][key]["score"],
                "delta": _delta(
                    before["dimensions"][key]["score"],
                    after["dimensions"][key]["score"],
                ),
            }
            for key in before["dimensions"]
        },
        "by_level": {
            b["level_id"]: {
                "before": b["depth"],
                "after": a["depth"],
                "delta": _delta(b["depth"], a["depth"]),
            }
            for b, a in zip(before["by_level"], after["by_level"], strict=True)
        },
    }

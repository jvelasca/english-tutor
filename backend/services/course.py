"""Course Engine (V1.38): secuencia Course→Unit→Lesson con gating y posición.

Transforma el contenido estático de `services.curriculum` (módulos/unidades/
lecciones/objetivos con `order`) en la **secuencia del curso**: orden explícito
de lecciones, gating lineal por objetivo y la posición actual del alumno
("¿dónde estoy dentro del curso?").

Puro y determinista: recibe el nivel cargado y el estado del alumno (mastery
por objetivo + contadores de intentos), sin I/O ni base de datos. El dominio
(`domain/academy.py`) es quien lee ese estado y lo inyecta aquí.
"""
from __future__ import annotations

from services.curriculum import Level

# Estados canónicos de un objetivo en la secuencia del curso.
MASTERED = "mastered"
REVIEW = "review"
AVAILABLE = "available"
LOCKED = "locked"

# Estados de una unidad (y una lección) en la barra de progreso.
UNIT_DONE = "done"
UNIT_CURRENT = "current"
UNIT_LOCKED = "locked"

# Plantilla fija de unidad (V2.2): 7 secciones canónicas del curso. Cada unidad
# expone las 7 con su conteo; las vacías se marcan `needs_content` para que el
# hueco pedagógico sea visible (y alimente el Quality Gate en V2.3).
UNIT_SECTIONS: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "listening",
    "speaking",
    "interaction",
    "review",
    "assessment",
)

# Sub-destrezas que cuentan como práctica de interacción (turnos/diálogo).
_INTERACTION_SUBSKILLS: tuple[str, ...] = ("interaction", "turn_taking", "repair")

# Umbrales compuestos de dominio por sección (Mastery Gates V2.2). Solo se exige
# una destreza si la unidad la declara (tiene contenido en esa sección).
UNIT_GATE_THRESHOLDS: dict[str, float] = {
    "vocabulary": 0.80,
    "grammar": 0.80,
    "listening": 0.75,
    "speaking": 0.70,
}

# Mínimo de evidencias transfer/novel para considerar dominio generalizado.
UNIT_GATE_TRANSFER_MIN = 1


def gate_objective_ids(level: Level) -> set[str]:
    """Objetivos que gatean la progresión: tienen checks evaluables.

    Un objetivo sin `checks` solo tiene actividades abiertas (no evaluable de
    forma determinista), así que no debe bloquear a los siguientes."""
    return {o.id for o in level.objectives() if o.assessable_skills()}


def objective_gated_status(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
) -> dict[str, str]:
    """Status por objetivo con gating lineal (premisa 21).

    En el orden de la secuencia del currículum:
    - `mastered`: dominado.
    - `review`: no dominado pero con intentos registrados.
    - `locked`: no dominado, sin intentos, y hay un objetivo *gate* anterior sin
      dominar (bloquea la progresión lineal).
    - `available`: no dominado, sin intentos, y todos los gates anteriores
      dominados (es el siguiente paso del curso).
    """
    attempts = attempts or {}
    gates = gate_objective_ids(level)
    statuses: dict[str, str] = {}
    blocked = False
    for obj in level.objectives():
        if obj.id in mastered_ids:
            statuses[obj.id] = MASTERED
        elif blocked:
            statuses[obj.id] = LOCKED
        else:
            att = attempts.get(obj.id, {})
            tried = int(att.get("correct", 0)) + int(att.get("incorrect", 0)) > 0
            statuses[obj.id] = REVIEW if tried else AVAILABLE
        # Un gate sin dominar bloquea los objetivos siguientes.
        if obj.id in gates and obj.id not in mastered_ids:
            blocked = True
    return statuses


def _first_non_mastered(
    level: Level, mastered_ids: set[str]
) -> tuple[int | None, object | None]:
    """(índice, objetivo) del primer objetivo no dominado, o (None, None)."""
    for i, obj in enumerate(level.objectives()):
        if obj.id not in mastered_ids:
            return i, obj
    return None, None


def _unit_objectives(unit) -> list:
    """Objetivos de una unidad en orden de aparición (aplanando lecciones)."""
    return [o for les in unit.lessons for o in les.objectives]


def _unit_module(level: Level, unit) -> object | None:
    """Módulo que contiene a la unidad, o None."""
    for mod in level.modules:
        if any(u.id == unit.id for u in mod.units):
            return mod
    return None


def unit_objectives(unit) -> list[str]:
    """Learning Objectives de unidad (V2.2).

    Agrega los `can_do` de los objetivos de la unidad para presentar
    "By the end of this unit you will be able to...". Es la misma fuente que
    alimenta el contrato CEFR (sin duplicar contenido).
    """
    return [o.can_do for o in _unit_objectives(unit)]


def unit_sections(level: Level, unit) -> list[dict]:
    """Plantilla fija de 7 secciones (V2.2) con conteo y huecos visibles.

    Agrupa el contenido del JSON en las secciones canónicas:
    - `vocabulary`/`grammar`/`listening`/`speaking` derivan de los objetivos
      (destrezas declaradas + checks deterministas por destreza).
    - `interaction` deriva de las sub-destrezas de turnos/diálogo.
    - `review`/`assessment` derivan del módulo `Final` (repaso y evaluación).

    Cada sección devuelve `count` (ítems) y `needs_content` (count == 0), para
    que el hueco pedagógico sea visible en la UI y alimente el Quality Gate.
    """
    objs = _unit_objectives(unit)
    checks = [c for o in objs for c in o.checks]
    mod = _unit_module(level, unit)
    is_final = bool(mod) and "final" in (mod.title or "").lower()

    def objectives_with(skill: str) -> int:
        return sum(1 for o in objs if skill in o.skills)

    def checks_with(skill: str) -> int:
        return sum(1 for c in checks if c.skill == skill)

    counts: dict[str, int] = {}
    for section in ("vocabulary", "grammar", "listening", "speaking"):
        counts[section] = objectives_with(section) + checks_with(section)
    counts["interaction"] = sum(
        1 for o in objs if any(s in _INTERACTION_SUBSKILLS for s in o.subskills)
    )
    counts["review"] = len(objs) if is_final else 0
    counts["assessment"] = len(checks) if is_final else 0

    return [
        {"section": section, "count": counts[section],
         "needs_content": counts[section] == 0}
        for section in UNIT_SECTIONS
    ]


def unit_gates(level: Level, unit, profile: list[dict]) -> dict:
    """Mastery Gates de una unidad (V2.2): umbrales compuestos → UNIT MASTERED.

    Evalúa las 4 destrezas macro que la unidad entrena (umbral por sección, solo
    si la unidad declara contenido en esa sección) más dos condiciones
    transversales: retención (sin repaso vencido) y transferencia (al menos una
    evidencia transfer/novel). Devuelve `{mastered, gates}` con el desglose
    `met`/`required`/`value` para que la UI muestre "qué falta para UNIT MASTERED".
    """
    sections = {s["section"]: s for s in unit_sections(level, unit)}
    by_skill = {e.get("skill"): e for e in profile}

    gates: list[dict] = []
    for skill, required in UNIT_GATE_THRESHOLDS.items():
        declared = sections.get(skill, {}).get("count", 0) > 0
        entry = by_skill.get(skill)
        value = round(float(entry.get("score", 0.0)), 3) if entry else 0.0
        met = (not declared) or (value >= required)
        gates.append({
            "section": skill,
            "label": f"{skill} >= {int(required * 100)}%",
            "value": value,
            "required": required,
            "met": met,
            "declared": declared,
        })

    # Destrezas efectivamente declaradas por la unidad (para retención/transfer).
    unit_skills = [
        s for s in UNIT_GATE_THRESHOLDS if sections.get(s, {}).get("count", 0) > 0
    ]

    due = [s for s in unit_skills if by_skill.get(s, {}).get("review_due")]
    retention_met = not due
    gates.append({
        "section": "retention",
        "label": "retention PASS",
        "value": 1.0 if retention_met else 0.0,
        "required": 1.0,
        "met": retention_met,
        "declared": bool(unit_skills),
    })

    def _transfer_count(skill: str) -> int:
        entry = by_skill.get(skill)
        if not entry:
            return 0
        kinds = entry.get("evidence_by_kind") or {}
        return int(kinds.get("transfer", 0)) + int(kinds.get("novel", 0))

    transfer_total = sum(_transfer_count(s) for s in unit_skills)
    transfer_met = transfer_total >= UNIT_GATE_TRANSFER_MIN
    gates.append({
        "section": "transfer",
        "label": "transfer PASS",
        "value": transfer_total,
        "required": UNIT_GATE_TRANSFER_MIN,
        "met": transfer_met,
        "declared": bool(unit_skills),
    })

    return {"mastered": all(g["met"] for g in gates), "gates": gates}


def unit_sequence(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
    profile: list[dict] | None = None,
) -> list[dict]:
    """Unidades del nivel con sus lecciones anidadas, progreso y estado.

    Cada unidad expone `status` (`done`/`current`/`locked`), `progress` 0..1,
    sus Learning Objectives (`objectives`), su plantilla de 7 secciones
    (`sections`) y, si se inyecta `profile`, el desglose de Mastery Gates
    (`gates`/`gate_mastered`). Cuando hay `profile`, una unidad solo queda
    `done` si pasa el gate compuesto además de dominar todos sus objetivos.
    """
    attempts = attempts or {}
    statuses = objective_gated_status(level, mastered_ids, attempts)
    current_id = _first_non_mastered(level, mastered_ids)[1]
    current_id = current_id.id if current_id is not None else None

    units: list[dict] = []
    for mod in level.modules:
        for unit in mod.units:
            lessons: list[dict] = []
            unit_obj_ids: list[str] = []
            for lesson in unit.lessons:
                lesson_obj_ids = [o.id for o in lesson.objectives]
                unit_obj_ids.extend(lesson_obj_ids)
                l_mastered = sum(1 for oid in lesson_obj_ids if oid in mastered_ids)
                l_total = len(lesson_obj_ids)
                if l_total and l_mastered == l_total:
                    l_status = UNIT_DONE
                elif current_id in lesson_obj_ids:
                    l_status = UNIT_CURRENT
                else:
                    l_status = UNIT_LOCKED
                lessons.append(
                    {
                        "lesson_id": lesson.id,
                        "lesson_title": lesson.title,
                        "lesson_order": lesson.order,
                        "mastered": l_mastered,
                        "total": l_total,
                        "progress": round(l_mastered / l_total, 3) if l_total else 0.0,
                        "status": l_status,
                        "objectives": [
                            {
                                "objective_id": o.id,
                                "title": o.title,
                                "status": statuses.get(o.id, LOCKED),
                            }
                            for o in lesson.objectives
                        ],
                    }
                )
            u_mastered = sum(1 for oid in unit_obj_ids if oid in mastered_ids)
            u_total = len(unit_obj_ids)
            obj_done = u_total > 0 and u_mastered == u_total
            gates = unit_gates(level, unit, profile) if profile is not None else None
            gate_mastered = gates["mastered"] if gates is not None else obj_done
            if obj_done and gate_mastered:
                u_status = UNIT_DONE
            elif obj_done or current_id in unit_obj_ids:
                u_status = UNIT_CURRENT
            else:
                u_status = UNIT_LOCKED
            units.append(
                {
                    "module_id": mod.id,
                    "module_title": mod.title,
                    "module_order": mod.order,
                    "unit_id": unit.id,
                    "unit_title": unit.title,
                    "unit_order": unit.order,
                    "mastered": u_mastered,
                    "total": u_total,
                    "progress": round(u_mastered / u_total, 3) if u_total else 0.0,
                    "status": u_status,
                    "objectives": unit_objectives(unit),
                    "sections": unit_sections(level, unit),
                    "gates": gates["gates"] if gates is not None else [],
                    "gate_mastered": gate_mastered,
                    "lessons": lessons,
                }
            )
    return units


def current_position(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
    profile: list[dict] | None = None,
) -> dict:
    """Posición actual del alumno dentro del curso ("¿dónde estoy?").

    Devuelve el primer objetivo no dominado (progresión lineal) con su módulo,
    unidad y lección, más los índices y el progreso del nivel. Si el nivel está
    completo, `objective_id` es None y la posición es el final del curso."""
    attempts = attempts or {}
    units = unit_sequence(level, mastered_ids, attempts, profile)
    objs = level.objectives()
    mastered = sum(1 for o in objs if o.id in mastered_ids)
    total = len(objs)
    current_index, current_obj = _first_non_mastered(level, mastered_ids)

    position: dict = {
        "level_id": level.level_id,
        "level": level.level,
        "title": level.title,
        "objective_id": current_obj.id if current_obj is not None else None,
        "objective_title": current_obj.title if current_obj is not None else None,
        "objective_order": (current_index + 1) if current_index is not None else total,
        "module_id": None,
        "module_title": None,
        "unit_id": None,
        "unit_title": None,
        "lesson_id": None,
        "lesson_title": None,
        "unit_index": 0,
        "unit_count": len(units),
        "mastered": mastered,
        "total": total,
        "progress": round(mastered / total, 3) if total else 0.0,
        "complete": total > 0 and mastered == total,
    }

    if current_obj is not None:
        for idx, unit in enumerate(units):
            for lesson in unit["lessons"]:
                ids = [o["objective_id"] for o in lesson["objectives"]]
                if current_obj.id in ids:
                    position["module_id"] = unit["module_id"]
                    position["module_title"] = unit["module_title"]
                    position["unit_id"] = unit["unit_id"]
                    position["unit_title"] = unit["unit_title"]
                    position["lesson_id"] = lesson["lesson_id"]
                    position["lesson_title"] = lesson["lesson_title"]
                    position["unit_index"] = idx
                    break
    return position


def course_map(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
    profile: list[dict] | None = None,
) -> dict:
    """Mapa completo del curso de un nivel: unidades + posición + progreso."""
    attempts = attempts or {}
    objs = level.objectives()
    mastered = sum(1 for o in objs if o.id in mastered_ids)
    total = len(objs)
    return {
        "level_id": level.level_id,
        "level": level.level,
        "title": level.title,
        "description": level.description,
        "units": unit_sequence(level, mastered_ids, attempts, profile),
        "position": current_position(level, mastered_ids, attempts, profile),
        "progress": {
            "mastered": mastered,
            "total": total,
            "progress": round(mastered / total, 3) if total else 0.0,
        },
    }

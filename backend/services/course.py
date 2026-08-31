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


def unit_sequence(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
) -> list[dict]:
    """Unidades del nivel con sus lecciones anidadas, progreso y estado.

    Cada unidad expone `status` (`done`/`current`/`locked`) y `progress` 0..1;
    cada lección expone su progreso y el status de cada objetivo."""
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
            if u_total and u_mastered == u_total:
                u_status = UNIT_DONE
            elif current_id in unit_obj_ids:
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
                    "lessons": lessons,
                }
            )
    return units


def current_position(
    level: Level,
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]] | None = None,
) -> dict:
    """Posición actual del alumno dentro del curso ("¿dónde estoy?").

    Devuelve el primer objetivo no dominado (progresión lineal) con su módulo,
    unidad y lección, más los índices y el progreso del nivel. Si el nivel está
    completo, `objective_id` es None y la posición es el final del curso."""
    attempts = attempts or {}
    units = unit_sequence(level, mastered_ids, attempts)
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
        "units": unit_sequence(level, mastered_ids, attempts),
        "position": current_position(level, mastered_ids, attempts),
        "progress": {
            "mastered": mastered,
            "total": total,
            "progress": round(mastered / total, 3) if total else 0.0,
        },
    }

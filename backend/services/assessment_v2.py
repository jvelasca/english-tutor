"""Assessment 2.0 — escalera de evaluación (V2.10).

Tipos canónicos (auditoría):

    Lesson  → formative (micro-assessment)
    Unit    → unit
    ~3 units → progress
    Level   → level (CEFR exam)
    Later   → retention (reassessment retardada)

También expone:
- `readiness` derivado de la escalera (no es un tipo de sesión).
- `mastery_evidence_gate`: MASTERED exige
  initial + practice + transfer + novel + delayed.

Motor puro y determinista: sin FastAPI ni BD.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.curriculum import Level, Objective, ObjectiveCheck, Unit

ASSESSMENT_VERSION = "2.0.0"

ASSESSMENT_KINDS: tuple[str, ...] = (
    "formative",
    "unit",
    "progress",
    "level",
    "retention",
)

# Umbral overall por tipo (0..1). El examen de nivel también exige min_per_skill
# en el scorer de exams; aquí el overall es la regla uniforme de la escalera.
PASS_THRESHOLDS: dict[str, float] = {
    "formative": 0.70,
    "unit": 0.75,
    "progress": 0.80,
    "level": 0.80,
    "retention": 0.70,
}

# Tope de ítems por tipo (None = sin tope; usa todos los checks disponibles).
ITEM_CAPS: dict[str, int | None] = {
    "formative": None,
    "unit": 12,
    "progress": 18,
    "level": None,
    "retention": None,
}

# Cada progress assessment cubre este número de unidades consecutivas.
PROGRESS_UNIT_SPAN = 3

# Días mínimos entre evaluación formal y retention reassessment.
RETENTION_MIN_DAYS = 7

# Ratio delayed/initial a partir del cual la retención se considera estable.
RETENTION_STABLE_RATIO = 0.9

# Regla MASTERED (auditoría §16): no basta con terminar.
MASTERY_EVIDENCE_REQUIREMENTS: dict[str, int] = {
    "initial": 1,  # familiar ≥ 1
    "practice": 2,  # familiar ≥ 2
    "transfer": 1,
    "novel": 1,
    "delayed": 1,
}


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def ordered_units(level: Level) -> list[Unit]:
    """Unidades del nivel en orden curricular (módulo.order, unit.order)."""
    units: list[Unit] = []
    for module in sorted(level.modules, key=lambda m: m.order):
        for unit in sorted(module.units, key=lambda u: u.order):
            units.append(unit)
    return units


def find_unit(level: Level, unit_id: str) -> Unit | None:
    for unit in ordered_units(level):
        if unit.id == unit_id:
            return unit
    return None


def unit_objectives(unit: Unit) -> list[Objective]:
    return [o for lesson in unit.lessons for o in lesson.objectives]


def checks_from_objectives(objectives: list[Objective]) -> list[ObjectiveCheck]:
    """Concatena checks preservando orden curricular y sin duplicar ids."""
    seen: set[str] = set()
    out: list[ObjectiveCheck] = []
    for obj in objectives:
        for check in obj.checks:
            if check.id in seen:
                continue
            seen.add(check.id)
            out.append(check)
    return out


def _cap_items(
    items: list[ObjectiveCheck], kind: str
) -> list[ObjectiveCheck]:
    cap = ITEM_CAPS.get(kind)
    if cap is None or len(items) <= cap:
        return list(items)
    # Muestreo determinista: reparte por destreza (round-robin) hasta el tope.
    by_skill: dict[str, list[ObjectiveCheck]] = {}
    for it in items:
        by_skill.setdefault(it.skill, []).append(it)
    skills = list(by_skill.keys())
    picked: list[ObjectiveCheck] = []
    index = 0
    while len(picked) < cap and skills:
        skill = skills[index % len(skills)]
        bucket = by_skill[skill]
        if bucket:
            picked.append(bucket.pop(0))
        if not bucket:
            skills = [s for s in skills if by_skill[s]]
            if not skills:
                break
            index = index % len(skills)
            continue
        index += 1
    return picked


def item_payload(check: ObjectiveCheck) -> dict:
    """Ítem seguro para el cliente (sin correct_index)."""
    return {
        "id": check.id,
        "skill": check.skill,
        "prompt": check.prompt,
        "options": list(check.options),
    }


def build_formative(objective: Objective) -> dict:
    """Micro-assessment de una lección/objetivo."""
    items = list(objective.checks)
    return {
        "kind": "formative",
        "title": f"Formative · {objective.title}",
        "objective_id": objective.id,
        "unit_id": "",
        "unit_ids": [],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["formative"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_unit(level: Level, unit_id: str) -> dict | None:
    unit = find_unit(level, unit_id)
    if unit is None:
        return None
    raw = checks_from_objectives(unit_objectives(unit))
    items = _cap_items(raw, "unit")
    return {
        "kind": "unit",
        "title": f"Unit assessment · {unit.title}",
        "objective_id": "",
        "unit_id": unit.id,
        "unit_ids": [unit.id],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["unit"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_progress(level: Level, anchor_unit_id: str) -> dict | None:
    """Progress assessment: la ancla y las (PROGRESS_UNIT_SPAN-1) anteriores."""
    units = ordered_units(level)
    ids = [u.id for u in units]
    if anchor_unit_id not in ids:
        return None
    end = ids.index(anchor_unit_id)
    start = max(0, end - (PROGRESS_UNIT_SPAN - 1))
    span = units[start : end + 1]
    if len(span) < 1:
        return None
    objs = [o for u in span for o in unit_objectives(u)]
    items = _cap_items(checks_from_objectives(objs), "progress")
    titles = " · ".join(u.title for u in span)
    return {
        "kind": "progress",
        "title": f"Progress assessment · {titles}",
        "objective_id": "",
        "unit_id": anchor_unit_id,
        "unit_ids": [u.id for u in span],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["progress"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_level(exam_items: list, *, exam_id: str, title: str) -> dict:
    """Envuelve el examen CEFR existente como peldaño `level`."""
    items = [
        {
            "id": it.id,
            "skill": it.skill,
            "prompt": it.prompt,
            "options": list(it.options),
        }
        for it in exam_items
    ]
    return {
        "kind": "level",
        "title": title or f"Level assessment · {exam_id}",
        "objective_id": "",
        "unit_id": "",
        "unit_ids": [],
        "exam_id": exam_id,
        "items": items,
        "item_ids": [it["id"] for it in items],
        "threshold": PASS_THRESHOLDS["level"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_retention(previous: dict) -> dict:
    """Misma batería que una evaluación previa (reassessment retardada)."""
    return {
        "kind": "retention",
        "title": f"Retention · {previous.get('title') or previous.get('kind')}",
        "objective_id": previous.get("objective_id") or "",
        "unit_id": previous.get("unit_id") or "",
        "unit_ids": list(previous.get("unit_ids") or []),
        "source_kind": previous.get("kind") or "",
        "source_session_id": previous.get("session_id"),
        "items": list(previous.get("items") or []),
        "item_ids": list(previous.get("item_ids") or []),
        "threshold": PASS_THRESHOLDS["retention"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def score_answers(
    checks: list[ObjectiveCheck] | list[dict],
    answers: dict[str, int],
) -> dict:
    """Puntúa respuestas. Acepta ObjectiveCheck o dicts con correct_index."""
    per_skill: dict[str, dict[str, int]] = {}
    correct = 0
    answered = 0
    for it in checks:
        item_id = it.id if hasattr(it, "id") else it["id"]
        skill = it.skill if hasattr(it, "skill") else it["skill"]
        correct_index = (
            it.correct_index if hasattr(it, "correct_index") else it["correct_index"]
        )
        if item_id not in answers:
            continue
        answered += 1
        bucket = per_skill.setdefault(skill, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if answers[item_id] == correct_index:
            bucket["correct"] += 1
            correct += 1
    skills = {
        skill: {
            "correct": b["correct"],
            "total": b["total"],
            "score": round(b["correct"] / b["total"], 3) if b["total"] else 0.0,
        }
        for skill, b in per_skill.items()
    }
    overall = round(correct / answered, 3) if answered else 0.0
    return {
        "skills": skills,
        "correct": correct,
        "total": answered,
        "overall": overall,
    }


def evaluate(
    kind: str,
    scored: dict,
    *,
    min_per_skill: float | None = None,
) -> dict:
    """Decide pass/fail y lista destrezas fallidas."""
    if kind not in ASSESSMENT_KINDS:
        raise ValueError(f"kind desconocido: {kind}")
    threshold = PASS_THRESHOLDS[kind]
    skills = scored.get("skills") or {}
    failed: list[str] = []
    if min_per_skill is not None:
        for skill, block in skills.items():
            if block.get("score", 0.0) < min_per_skill:
                failed.append(skill)
        skill_ok = not failed if skills else False
    else:
        skill_ok = True
    overall = float(scored.get("overall") or 0.0)
    passed = bool(scored.get("total", 0) > 0) and overall >= threshold and skill_ok
    if not skill_ok and min_per_skill is None:
        failed = [
            s for s, b in skills.items() if b.get("score", 0.0) < threshold
        ]
    return {
        "kind": kind,
        "overall": overall,
        "threshold": threshold,
        "passed": passed,
        "correct": scored.get("correct", 0),
        "total": scored.get("total", 0),
        "skills": skills,
        "failed_skills": failed,
        "phase": "evaluation",
    }


def retention_delta(initial: dict, delayed: dict) -> dict:
    """Compara evaluación inicial vs retention reassessment."""
    first = float(initial.get("overall") or 0.0)
    later = float(delayed.get("overall") or 0.0)
    rate = round(later / first, 3) if first > 0 else None
    by_skill: list[dict] = []
    skills = set(initial.get("skills") or {}) | set(delayed.get("skills") or {})
    for skill in sorted(skills):
        a = (initial.get("skills") or {}).get(skill, {}).get("score")
        b = (delayed.get("skills") or {}).get(skill, {}).get("score")
        if a is None or b is None:
            delta = None
        else:
            delta = round(float(b) - float(a), 3)
        by_skill.append({"skill": skill, "initial": a, "delayed": b, "delta": delta})
    return {
        "initial_overall": first,
        "delayed_overall": later,
        "retention_rate": rate,
        "stable": rate is not None and rate >= RETENTION_STABLE_RATIO,
        "by_skill": by_skill,
        "phase": "retention",
    }


def mastery_evidence_gate(by_kind: dict | None) -> dict:
    """¿Se puede considerar MASTERED? (initial+practice+transfer+novel+delayed)."""
    kinds = by_kind or {}
    familiar = int(kinds.get("familiar", 0))
    transfer = int(kinds.get("transfer", 0))
    novel = int(kinds.get("novel", 0))
    delayed = int(kinds.get("delayed", 0))
    checks = {
        "initial": familiar >= MASTERY_EVIDENCE_REQUIREMENTS["initial"],
        "practice": familiar >= MASTERY_EVIDENCE_REQUIREMENTS["practice"],
        "transfer": transfer >= MASTERY_EVIDENCE_REQUIREMENTS["transfer"],
        "novel": novel >= MASTERY_EVIDENCE_REQUIREMENTS["novel"],
        "delayed": delayed >= MASTERY_EVIDENCE_REQUIREMENTS["delayed"],
    }
    missing = [name for name, ok in checks.items() if not ok]
    return {
        "met": not missing,
        "checks": checks,
        "missing": missing,
        "counts": {
            "familiar": familiar,
            "transfer": transfer,
            "novel": novel,
            "delayed": delayed,
        },
    }


def retention_due(
    last_formal_at: str,
    *,
    now: str = "",
    min_days: int = RETENTION_MIN_DAYS,
) -> bool:
    """True si ya pasó la ventana de retención desde la última formal."""
    if not last_formal_at:
        return False
    now_dt = _parse_iso(now) or datetime.now(timezone.utc)
    last_dt = _parse_iso(last_formal_at)
    if last_dt is None:
        return False
    return (now_dt - last_dt).days >= min_days


def ladder_status(
    *,
    completed_kinds: set[str],
    units_done: int,
    has_exam: bool,
    retention_ready: bool,
    mastery_gate: dict | None = None,
) -> dict:
    """Estado de la escalera + siguiente peldaño recomendado."""
    steps = []
    for kind in ASSESSMENT_KINDS:
        available = True
        reason = "available"
        if kind == "unit" and units_done < 1:
            available = False
            reason = "complete-a-unit"
        elif kind == "progress" and units_done < PROGRESS_UNIT_SPAN:
            available = False
            reason = f"need-{PROGRESS_UNIT_SPAN}-units"
        elif kind == "level" and not has_exam:
            available = False
            reason = "no-exam"
        elif (
            kind == "level"
            and "progress" not in completed_kinds
            and units_done < PROGRESS_UNIT_SPAN
        ):
            # Nivel disponible si hay examen; se recomienda tras progress.
            reason = "recommended-after-progress"
        elif kind == "retention" and not retention_ready:
            available = False
            reason = "wait-retention-window"
        done = kind in completed_kinds
        steps.append(
            {
                "kind": kind,
                "available": available,
                "completed": done,
                "reason": "done" if done else reason,
            }
        )

    next_kind = None
    for step in steps:
        if step["available"] and not step["completed"]:
            next_kind = step["kind"]
            break

    gate = mastery_gate or mastery_evidence_gate({})
    non_retention_done = all(
        s["completed"] for s in steps if s["kind"] != "retention"
    )
    readiness = {
        "ladder_complete": non_retention_done
        or (
            "formative" in completed_kinds
            and "unit" in completed_kinds
            and (
                "progress" in completed_kinds or units_done < PROGRESS_UNIT_SPAN
            )
            and ("level" in completed_kinds or not has_exam)
        ),
        "mastery_eligible": gate["met"],
        "mastery_missing": list(gate.get("missing") or []),
        "next_kind": next_kind,
        "retention_due": retention_ready,
    }
    return {
        "steps": steps,
        "readiness": readiness,
        "assessment_version": ASSESSMENT_VERSION,
    }


def evidence_kind_for(kind: str) -> str:
    """Qué evidence_kind registrar al completar un peldaño."""
    if kind == "retention":
        return "delayed"
    if kind in ("unit", "progress", "level"):
        return "transfer"
    return "familiar"

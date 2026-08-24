"""Lógica pura de la Academy (progresión, mastery, adaptación y evaluación).

No hace I/O ni toca la base de datos: recibe el currículum cargado y el estado del
alumno, y devuelve resultados deterministas. Se apoya en `services.curriculum`.
"""

from __future__ import annotations

from collections import defaultdict

from services.curriculum import (
    CEFR_ORDER,
    Exam,
    Level,
    Objective,
    next_level_id,
)

# --- Mastery y progresión -------------------------------------------------


def objective_progress(objective: Objective, skill_scores: dict[str, float]) -> dict:
    """Devuelve el desglose por destreza de un objetivo y si está dominado.

    `skill_scores` mapea destreza → mejor puntuación (0..1). Un objetivo se domina
    cuando TODAS sus destrezas alcanzan su umbral."""
    skills = []
    for skill in objective.skills:
        score = skill_scores.get(skill, 0.0)
        required = objective.threshold(skill)
        skills.append(
            {
                "skill": skill,
                "score": round(score, 3),
                "required": required,
                "met": score >= required,
            }
        )
    mastered = all(s["met"] for s in skills) if skills else False
    return {"objective_id": objective.id, "skills": skills, "mastered": mastered}


def mastered_objective_ids(level: Level, skill_scores: dict[str, float]) -> set[str]:
    """Ids de objetivos dominados del nivel según las puntuaciones actuales."""
    return {
        obj.id
        for obj in level.objectives()
        if objective_progress(obj, skill_scores)["mastered"]
    }


def unlock_state(level: Level, mastered_ids: set[str]) -> dict[str, bool]:
    """Mapa objective_id → desbloqueado. Un objetivo está desbloqueado si es el
    primero de la secuencia o si todos los anteriores están dominados (gating)."""
    ids = [o.id for o in level.objectives()]
    unlocked: dict[str, bool] = {}
    prev_all_mastered = True
    for oid in ids:
        unlocked[oid] = prev_all_mastered
        prev_all_mastered = prev_all_mastered and oid in mastered_ids
    return unlocked


def module_progress(level: Level, skill_scores: dict[str, float]) -> list[dict]:
    """Progreso por módulo: nº de objetivos dominados / total y ratio 0..1."""
    mastered = mastered_objective_ids(level, skill_scores)
    result = []
    for mod in level.modules:
        objs = [o for u in mod.units for les in u.lessons for o in les.objectives]
        done = sum(1 for o in objs if o.id in mastered)
        result.append(
            {
                "module_id": mod.id,
                "title": mod.title,
                "order": mod.order,
                "mastered": done,
                "total": len(objs),
                "progress": round(done / len(objs), 3) if objs else 0.0,
            }
        )
    return result


def level_progress(level: Level, skill_scores: dict[str, float]) -> dict:
    """Progreso agregado del nivel."""
    objs = level.objectives()
    done = sum(1 for o in objs if objective_progress(o, skill_scores)["mastered"])
    return {
        "level": level.level,
        "mastered": done,
        "total": len(objs),
        "progress": round(done / len(objs), 3) if objs else 0.0,
    }


# --- Intentos y contadores (acertado / fallado / a repasar) ---------------


def objective_attempts(
    objective_id: str, attempts: dict[str, dict[str, int]]
) -> dict[str, int]:
    """Resumen de intentos de un objetivo: {attempts, correct, incorrect}."""
    a = attempts.get(objective_id, {"correct": 0, "incorrect": 0})
    return {
        "attempts": a["correct"] + a["incorrect"],
        "correct": a["correct"],
        "incorrect": a["incorrect"],
    }


def classify_objective(
    objective_id: str, mastered_ids: set[str], attempts: dict[str, dict[str, int]]
) -> str:
    """Clasifica un objetivo en una categoría mutuamente excluyente para el rollup:
    'correct' (verde) | 'incorrect' (rojo) | 'review' (ámbar) | None (sin intentar)."""
    if objective_id in mastered_ids:
        return "correct"
    a = attempts.get(objective_id, {"correct": 0, "incorrect": 0})
    if a["incorrect"] > 0:
        return "incorrect"
    if a["correct"] > 0:
        return "review"
    return ""


def rollup_counters(
    objective_ids: list[str],
    mastered_ids: set[str],
    attempts: dict[str, dict[str, int]],
) -> dict[str, int]:
    """Contadores de un conjunto de objetivos: correct / incorrect / to_review."""
    counters = {"correct": 0, "incorrect": 0, "to_review": 0}
    for oid in objective_ids:
        cls = classify_objective(oid, mastered_ids, attempts)
        if cls == "correct":
            counters["correct"] += 1
        elif cls == "incorrect":
            counters["incorrect"] += 1
        elif cls == "review":
            counters["to_review"] += 1
    return counters


def module_progress_with_counters(
    level: Level, mastered_ids: set[str], attempts: dict[str, dict[str, int]]
) -> list[dict]:
    """Progreso por módulo con contadores de estado (para el árbol)."""
    result = []
    for mod in level.modules:
        objs = [o for u in mod.units for les in u.lessons for o in les.objectives]
        ids = [o.id for o in objs]
        counters = rollup_counters(ids, mastered_ids, attempts)
        result.append(
            {
                "module_id": mod.id,
                "title": mod.title,
                "order": mod.order,
                "mastered": counters["correct"],
                "total": len(objs),
                "progress": round(counters["correct"] / len(objs), 3)
                if objs
                else 0.0,
                **counters,
            }
        )
    return result


def level_progress_with_counters(
    level: Level, mastered_ids: set[str], attempts: dict[str, dict[str, int]]
) -> dict:
    """Progreso agregado del nivel con contadores de estado."""
    ids = [o.id for o in level.objectives()]
    counters = rollup_counters(ids, mastered_ids, attempts)
    return {
        "level": level.level,
        "mastered": counters["correct"],
        "total": len(ids),
        "progress": round(counters["correct"] / len(ids), 3) if ids else 0.0,
        **counters,
    }


# --- Selección del siguiente paso ----------------------------------------


def next_objective(level: Level, mastered_ids: set[str]) -> str | None:
    """Primer objetivo desbloqueado y no dominado (progresión lineal)."""
    unlocked = unlock_state(level, mastered_ids)
    for oid in unlocked:
        if oid not in mastered_ids:
            return oid
    return None


def weakest_skill(level: Level, skill_scores: dict[str, float]) -> str | None:
    """Destreza con menor puntuación media entre los objetivos del nivel."""
    totals: dict[str, list[float]] = defaultdict(list)
    for obj in level.objectives():
        for skill in obj.skills:
            totals[skill].append(skill_scores.get(skill, 0.0))
    if not totals:
        return None
    return min(totals, key=lambda s: sum(totals[s]) / len(totals[s]))


def adaptive_next(
    level: Level, mastered_ids: set[str], skill_scores: dict[str, float]
) -> str | None:
    """Siguiente objetivo adaptativo: entre los desbloqueados no dominados, elige
    el que peor puntuación tiene en su destreza más débil (remediation-aware)."""
    unlocked = [
        oid
        for oid, ok in unlock_state(level, mastered_ids).items()
        if ok and oid not in mastered_ids
    ]
    if not unlocked:
        return None
    objs = {o.id: o for o in level.objectives()}

    def key(oid: str) -> float:
        obj = objs[oid]
        return min(skill_scores.get(s, 0.0) for s in obj.skills)

    return min(unlocked, key=key)


# --- Evaluación -----------------------------------------------------------


def score_items(items: list, answers: dict[str, int]) -> dict:
    """Puntúa respuestas de ítems. `answers` mapea item_id → índice elegido."""
    per_skill: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    correct = 0
    answered = 0
    for it in items:
        if it.id not in answers:
            continue
        answered += 1
        per_skill[it.skill]["total"] += 1
        if answers[it.id] == it.correct_index:
            per_skill[it.skill]["correct"] += 1
            correct += 1
    skills = {
        skill: {
            "correct": b["correct"],
            "total": b["total"],
            "score": round(b["correct"] / b["total"], 3) if b["total"] else 0.0,
        }
        for skill, b in per_skill.items()
    }
    return {
        "skills": skills,
        "correct": correct,
        "total": answered,
        "overall": round(correct / answered, 3) if answered else 0.0,
    }


def placement_result(items: list, answers: dict[str, int]) -> dict:
    """Estima el nivel de inicio (A1..C2) y su confianza a partir de los ítems.

    Heurística CAT-lite: se supera una banda de dificultad d (1..6) si se acierta
    al menos la mitad de sus ítems; el nivel estimado es la banda más alta superada.
    No es una certificación: es un punto de partida recomendado."""
    by_diff: dict[int, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    answered = 0
    for it in items:
        if it.id not in answers:
            continue
        answered += 1
        by_diff[it.difficulty]["total"] += 1
        if answers[it.id] == it.correct_index:
            by_diff[it.difficulty]["correct"] += 1

    highest_passed = 0
    for d in range(1, 7):
        band = by_diff[d]
        if band["total"] > 0 and band["correct"] / band["total"] >= 0.5:
            highest_passed = d

    level = CEFR_ORDER[highest_passed - 1] if highest_passed >= 1 else CEFR_ORDER[0]
    confidence = round(min(0.5 + 0.05 * answered, 0.95), 2) if answered else 0.0
    return {
        "level": level,
        "confidence": confidence,
        "answered": answered,
        "correct": sum(1 for it in items if answers.get(it.id) == it.correct_index),
    }


def exam_result(exam: Exam, answers: dict[str, int]) -> dict:
    """Puntúa un examen de nivel. Aprueba si TODAS las destrezas requeridas
    alcanzan el umbral mínimo y todas están cubiertas por ítems respondidos."""
    per_skill: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    for it in exam.items:
        if it.id not in answers:
            continue
        per_skill[it.skill]["total"] += 1
        if answers[it.id] == it.correct_index:
            per_skill[it.skill]["correct"] += 1

    skills = {
        skill: {
            "correct": b["correct"],
            "total": b["total"],
            "score": round(b["correct"] / b["total"], 3) if b["total"] else 0.0,
            "passed": (b["correct"] / b["total"] if b["total"] else 0.0)
            >= exam.min_per_skill,
        }
        for skill, b in per_skill.items()
    }
    covered = set(skills) >= set(exam.skills)
    all_passed = all(s["passed"] for s in skills.values()) if skills else False
    overall = (
        round(sum(s["score"] for s in skills.values()) / len(skills), 3)
        if skills
        else 0.0
    )
    return {
        "skills": skills,
        "overall": overall,
        "passed": covered and all_passed,
        "failed_skills": [s for s, b in skills.items() if not b["passed"]],
    }


# --- Plan de estudio ------------------------------------------------------


def study_plan(start_level: str, target_level: str, weeks: int) -> list[dict]:
    """Reparte las semanas disponibles entre los niveles CEFR entre inicio y meta."""
    if start_level not in CEFR_ORDER or target_level not in CEFR_ORDER:
        return []
    start = CEFR_ORDER.index(start_level)
    target = CEFR_ORDER.index(target_level)
    if target <= start or weeks <= 0:
        return []
    span = target - start
    base = weeks // span
    remainder = weeks % span
    plan = []
    for i in range(start, target):
        level = CEFR_ORDER[i]
        w = base + (1 if (i - start) < remainder else 0)
        plan.append({"level": level, "weeks": w, "next_level_id": next_level_id(level)})
    return plan

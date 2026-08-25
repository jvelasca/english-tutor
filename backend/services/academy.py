"""Lógica pura de la Academy (progresión, mastery, adaptación y evaluación).

No hace I/O ni toca la base de datos: recibe el currículum cargado y el estado del
alumno, y devuelve resultados deterministas. Se apoya en `services.curriculum`.

Modelo de mastery (dirección única, nunca al revés):
    Evidence (por ítem, versionada)
        → Objective mastery  (`academy_objective_mastery`, fuente de verdad)
        → Skill aggregation (`aggregate_skill_mastery`, vista derivada)
        → CEFR profile      (destreza → score/confidence/evidence/review_due)
        → Level completion  (certificación interna, reproducible)
Las destrezas de conocimiento (grammar, vocabulary, reading, listening) se
evalúan con checks deterministas (opción múltiple); las de producción (speaking,
writing, pronunciation) se evalúan con rúbricas deterministas + extracción LLM
y, desde V1.3, integran evidencia de rendimiento versionada en el Student Model.
"""

from __future__ import annotations

import math
from collections import defaultdict

from services.curriculum import (
    CANONICAL_SKILLS,
    CEFR_ORDER,
    PLACEMENT_VERSION,
    Exam,
    Level,
    Objective,
    next_level_id,
)
from services.forgetting import review_due as forgetting_review_due

# --- Modelo de mastery determinista (recencia + racha + confianza) ---------

# Suavizado EMA aplicado a la evidencia (recent_score) y a la consistencia.
MASTERY_ALPHA = 0.5
# Racha de aciertos sobre el umbral que satura el bonus de consistencia.
STREAK_TARGET = 3


def enrollment_unlocked(level_id: str, completed_level_ids: set[str]) -> bool:
    """True si el nivel puede matricularse.

    Progresión CEFR estricta: el primer nivel (A1) siempre está disponible; el
    resto solo si el nivel CEFR inmediatamente anterior está completado. Los ids
    de nivel se normalizan a mayúsculas para compararlos con `CEFR_ORDER`."""
    code = level_id.upper()
    if code not in CEFR_ORDER:
        return False
    idx = CEFR_ORDER.index(code)
    if idx == 0:
        return True
    return CEFR_ORDER[idx - 1].lower() in completed_level_ids


def _default_mastery_state() -> dict:
    """Estado inicial de una destreza sin evidencia registrada."""
    return {
        "score": 0.0,
        "recent_score": 0.0,
        "confidence": 0.0,
        "streak": 0,
        "attempts": 0,
        "last_seen_at": "",
    }


def next_mastery_state(
    current: dict | None, score: float, threshold: float, now: str = ""
) -> dict:
    """Transición determinista del estado de mastery ante una evidencia (0..1).

    Sustituye a ``score = MAX(score, new)``: el dominio puede **bajar** si la
    evidencia empeora (decay), de modo que un objetivo dominado puede volver a
    "a repasar".

    - ``recent_score``: EMA de la evidencia; refleja el rendimiento reciente.
    - ``confidence``: EMA del indicador "supera el umbral" (consistencia), 0..1;
      no depende del número de preguntas.
    - ``streak``: aciertos consecutivos sobre el umbral; se reinicia si falla.
    - ``score`` (mastery): ``0.7·recent + 0.3·min(1, streak/3)``; exige algo de
      consistencia para consolidar el dominio.
    """
    prev = current or _default_mastery_state()
    attempts = int(prev.get("attempts", 0)) + 1
    prev_recent = float(prev.get("recent_score", 0.0))
    if attempts == 1:
        recent = score
    else:
        recent = MASTERY_ALPHA * score + (1 - MASTERY_ALPHA) * prev_recent

    met = 1.0 if score >= threshold else 0.0
    prev_conf = float(prev.get("confidence", 0.0))
    if attempts == 1:
        confidence = met
    else:
        confidence = MASTERY_ALPHA * met + (1 - MASTERY_ALPHA) * prev_conf

    streak = int(prev.get("streak", 0)) + 1 if score >= threshold else 0
    mastery = round(0.7 * recent + 0.3 * min(1.0, streak / STREAK_TARGET), 3)
    return {
        "score": mastery,
        "recent_score": round(recent, 3),
        "confidence": round(confidence, 3),
        "streak": streak,
        "attempts": attempts,
        "last_seen_at": now,
    }


# --- Mastery y progresión -------------------------------------------------


def objective_progress(
    objective: Objective,
    skill_scores: dict[str, float],
    skill_attempts: dict[str, int] | None = None,
) -> dict:
    """Devuelve el desglose por destreza de un objetivo y si está dominado.

    Solo se evalúan las destrezas con evidencia determinista
    (`objective.assessable_skills()`); las destrezas de producción (speaking,
    writing, pronunciation) no gatean el dominio hasta tener evidencia real.

    `skill_scores` mapea destreza → puntuación (0..1); `skill_attempts` mapea
    destreza → nº de evidencias. Una destreza se da por dominada solo si alcanza
    su umbral **y** acumula al menos `objective.minimum_attempts` evidencias (así
    un único acierto no marca el objetivo como dominado)."""
    skill_attempts = skill_attempts or {}
    skills = []
    for skill in objective.assessable_skills():
        score = skill_scores.get(skill, 0.0)
        attempts = skill_attempts.get(skill, 0)
        required = objective.threshold(skill)
        met = score >= required and attempts >= objective.minimum_attempts
        skills.append(
            {
                "skill": skill,
                "score": round(score, 3),
                "required": required,
                "met": met,
            }
        )
    mastered = all(s["met"] for s in skills) if skills else False
    return {"objective_id": objective.id, "skills": skills, "mastered": mastered}


def mastered_objective_ids(
    level: Level,
    objective_scores: dict[str, dict[str, float]],
    objective_attempts: dict[str, dict[str, int]] | None = None,
) -> set[str]:
    """Ids de objetivos dominados del nivel (mastery **por objetivo**).

    `objective_scores` mapea objective_id → {skill: score}; `objective_attempts`
    mapea objective_id → {skill: nº de intentos}. El dominio de una destreza en un
    objetivo no se contagia a otros objetivos que compartan destreza."""
    objective_attempts = objective_attempts or {}
    return {
        obj.id
        for obj in level.objectives()
        if objective_progress(
            obj,
            objective_scores.get(obj.id, {}),
            objective_attempts.get(obj.id, {}),
        )["mastered"]
    }


def module_progress(
    level: Level,
    objective_scores: dict[str, dict[str, float]],
    objective_attempts: dict[str, dict[str, int]] | None = None,
) -> list[dict]:
    """Progreso por módulo: nº de objetivos dominados / total y ratio 0..1."""
    mastered = mastered_objective_ids(level, objective_scores, objective_attempts)
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


def level_progress(
    level: Level,
    objective_scores: dict[str, dict[str, float]],
    objective_attempts: dict[str, dict[str, int]] | None = None,
) -> dict:
    """Progreso agregado del nivel."""
    objs = level.objectives()
    mastered = mastered_objective_ids(level, objective_scores, objective_attempts)
    done = sum(1 for o in objs if o.id in mastered)
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
    """Primer objetivo no dominado en la secuencia del currículum
    (progresión lineal)."""
    for o in level.objectives():
        if o.id not in mastered_ids:
            return o.id
    return None


def weakest_skill(
    level: Level, objective_scores: dict[str, dict[str, float]]
) -> str | None:
    """Destreza con menor puntuación media entre los objetivos del nivel."""
    totals: dict[str, list[float]] = defaultdict(list)
    for obj in level.objectives():
        scores = objective_scores.get(obj.id, {})
        for skill in obj.assessable_skills():
            totals[skill].append(scores.get(skill, 0.0))
    if not totals:
        return None
    return min(totals, key=lambda s: sum(totals[s]) / len(totals[s]))


def recommend_next(
    level: Level,
    mastered_ids: set[str],
    objective_scores: dict[str, dict[str, float]],
) -> tuple[str | None, str]:
    """Recomienda el siguiente objetivo y el motivo (soft gating, remediation-aware).

    Devuelve (objective_id, reason) con reason ∈ {"remediation", "next-in-path",
    "level-complete"}. La remediación solo se propone para objetivos NO dominados
    que ya tienen evidencia y cuya destreza más débil está por debajo de su umbral;
    en ausencia de evidencia se sigue la progresión lineal. No hay gating duro
    dentro del nivel: el gating duro es por nivel (A1→A2→B1)."""
    objs = {o.id: o for o in level.objectives()}
    non_mastered = [o.id for o in level.objectives() if o.id not in mastered_ids]
    if not non_mastered:
        return None, "level-complete"

    weak: list[str] = []
    for oid in non_mastered:
        scores = objective_scores.get(oid)
        if not scores:
            continue
        obj = objs[oid]
        assessable = obj.assessable_skills()
        if any(scores[s] < obj.threshold(s) for s in assessable if s in scores):
            weak.append(oid)

    if weak:
        def key(oid: str) -> float:
            obj = objs[oid]
            scores = objective_scores[oid]
            assessable = obj.assessable_skills()
            return min((scores[s] for s in assessable if s in scores), default=0.0)

        return min(weak, key=key), "remediation"

    return next_objective(level, mastered_ids), "next-in-path"


def adaptive_next(
    level: Level,
    mastered_ids: set[str],
    objective_scores: dict[str, dict[str, float]],
) -> str | None:
    """Siguiente objetivo recomendado (remediación sobre progresión)."""
    return recommend_next(level, mastered_ids, objective_scores)[0]


def aggregate_skill_mastery(
    level: Level, objective_scores: dict[str, dict[str, float]]
) -> dict[str, float]:
    """Vista derivada: mastery por destreza agregado desde el mastery por objetivo.

    ``academy_objective_mastery`` es la fuente de verdad; esta función la agrega
    (media aritmética de cada destreza entre los objetivos que la comparten) para
    producir el perfil de destreza del nivel. Nunca se escribe `academy_skill_mastery`
    como fuente primaria: se deriva de aquí cuando se necesite el CEFR profile."""
    totals: dict[str, list[float]] = defaultdict(list)
    for obj in level.objectives():
        scores = objective_scores.get(obj.id, {})
        if not scores:
            continue
        for skill in obj.assessable_skills():
            totals[skill].append(scores.get(skill, 0.0))
    return {
        skill: round(sum(vals) / len(vals), 3)
        for skill, vals in totals.items()
        if vals
    }


def build_skill_profile(
    level: Level,
    objective_mastery: dict[str, dict[str, dict]],
    evidence_rows: list[dict],
    now: str = "",
) -> list[dict]:
    """Vista derivada del perfil CEFR por destreza de un nivel.

    Agrega el mastery por objetivo (`academy_objective_mastery`, fuente de verdad)
    y la evidencia por ítem (`academy_evidence`) en una entrada por destreza con
    `score` (media), `confidence` (media), `evidence_count`, `last_evidence`
    (ISO más reciente, o ''), y `review_due`, derivado del modelo de olvido
    (`services.forgetting`) a partir del `last_seen_at`/última evidencia y `now`.

    Devuelve una lista ordenada por `CANONICAL_SKILLS` y, tras ellas, cualquier
    destreza extra en orden alfabético.
    """
    skills: set[str] = set()
    for obj in level.objectives():
        skills.update(obj.skills)
    for skills_by_obj in objective_mastery.values():
        skills.update(skills_by_obj)
    for row in evidence_rows:
        skill = row.get("skill")
        if skill:
            skills.add(skill)

    evidence_by_skill: dict[str, list[dict]] = defaultdict(list)
    for row in evidence_rows:
        evidence_by_skill[row["skill"]].append(row)

    canonical_index = {skill: i for i, skill in enumerate(CANONICAL_SKILLS)}

    profile: list[dict] = []
    for skill in skills:
        scores: list[float] = []
        confidences: list[float] = []
        last_seen = ""
        for skills_by_obj in objective_mastery.values():
            state = skills_by_obj.get(skill)
            if state is not None:
                scores.append(float(state["score"]))
                confidences.append(float(state["confidence"]))
                seen = state.get("last_seen_at", "")
                if seen:
                    last_seen = max(last_seen, seen)
        score = round(sum(scores) / len(scores), 3) if scores else 0.0
        confidence = (
            round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        )
        rows = evidence_by_skill.get(skill, [])
        evidence_count = len(rows)
        last_evidence = max(r["created_at"] for r in rows) if rows else ""
        review_ts = last_seen or last_evidence
        profile.append(
            {
                "skill": skill,
                "score": score,
                "confidence": confidence,
                "evidence_count": evidence_count,
                "last_evidence": last_evidence,
                "review_due": (
                    evidence_count > 0 and forgetting_review_due(score, review_ts, now)
                ),
                "subskills": [],
            }
        )

    profile.sort(
        key=lambda x: (
            canonical_index.get(x["skill"], len(CANONICAL_SKILLS)),
            x["skill"],
        )
    )
    return profile


# Pesos pedagógicos por destreza para el overall del perfil CEFR (suman 1).
# Reflejan el peso relativo de cada destreza en la competencia global.
CEFR_SKILL_WEIGHTS: dict[str, float] = {
    "vocabulary": 0.15,
    "grammar": 0.20,
    "pronunciation": 0.10,
    "listening": 0.15,
    "speaking": 0.15,
    "reading": 0.10,
    "writing": 0.15,
}
# Peso por defecto para destrezas no canónicas (no deberían aparecer en el perfil).
CEFR_DEFAULT_WEIGHT = 0.1

# Mínimos críticos: una destreza crítica evaluada por debajo de su mínimo limita
# el overall (no se puede certificar un nivel sin esas bases).
CRITICAL_MINIMUMS: dict[str, float] = {
    "grammar": 0.4,
    "vocabulary": 0.4,
}


def overall_cefr_score(skill_profile: list[dict]) -> float:
    """Overall del perfil CEFR: media ponderada por destreza + mínimos críticos.

    Sustituye a la media aritmética simple: pondera cada destreza por su peso
    pedagógico (renormalizado sobre las destrezas presentes) y limita el resultado
    al mínimo de una destreza crítica evaluada que esté por debajo de su umbral.
    Sin destrezas (o sin peso total) devuelve 0.0.
    """
    if not skill_profile:
        return 0.0
    total_weight = 0.0
    weighted_sum = 0.0
    for entry in skill_profile:
        weight = CEFR_SKILL_WEIGHTS.get(entry["skill"], CEFR_DEFAULT_WEIGHT)
        total_weight += weight
        weighted_sum += weight * entry["score"]
    if total_weight == 0.0:
        return 0.0
    overall = weighted_sum / total_weight

    for skill, minimum in CRITICAL_MINIMUMS.items():
        entry = next((e for e in skill_profile if e["skill"] == skill), None)
        if (
            entry is not None
            and entry.get("evidence_count", 0) > 0
            and entry["score"] < minimum
        ):
            overall = min(overall, minimum)

    return round(overall, 3)


def critical_skills(skill_profile: list[dict]) -> list[str]:
    """Destrezas críticas evaluadas por debajo de su mínimo (lista, vacía = ok).

    Complementa a `overall_cefr_score`: aquella topa el overall al mínimo cuando
    una destreza crítica cae por debajo de su umbral; esta función expone CUÁLES
    son, para que el perfil y la remediación puedan señalarlas. Solo se activa
    con evidencia (una destreza sin evaluar no es "crítica": aún no hay dato)."""
    result: list[str] = []
    for skill, minimum in CRITICAL_MINIMUMS.items():
        entry = next((e for e in skill_profile if e["skill"] == skill), None)
        if (
            entry is not None
            and entry.get("evidence_count", 0) > 0
            and entry["score"] < minimum
        ):
            result.append(skill)
    return result


def remediation_plan(
    level: Level,
    skill_profile: list[dict],
    objective_scores: dict[str, dict[str, float]],
    mastered_ids: set[str],
) -> list[dict]:
    """Plan de remediación: destrezas débiles y objetivos concretos para reforzarlas.

    Para cada destreza débil del perfil (`review_due` True), ordena los objetivos del
    nivel que la declaran y aún no están dominados por su score ascendente (empate por
    orden curricular, que conserva el sort estable), y devuelve
    `{"skill", "score", "objective_ids"}`. La lista final va ordenada por score
    ascendente (más débil primero).
    """
    result = []
    for entry in skill_profile:
        if not entry["review_due"]:
            continue
        skill = entry["skill"]
        candidates = [
            (objective_scores.get(o.id, {}).get(skill, 0.0), o.id)
            for o in level.objectives()
            if skill in o.skills and o.id not in mastered_ids
        ]
        candidates.sort(key=lambda t: t[0])
        objective_ids = [oid for _, oid in candidates]
        if not objective_ids:
            continue
        result.append(
            {"skill": skill, "score": entry["score"], "objective_ids": objective_ids}
        )
    result.sort(key=lambda r: r["score"])
    return result


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


def evidence_from_items(
    items: list,
    answers: dict[str, int],
    *,
    level_id: str,
    objective_id: str = "",
    item_type: str = "mcq",
    source: str = "objective_assessment",
    difficulty: int = 1,
    curriculum_version: str = "",
    assessment_version: str = "",
) -> list[dict]:
    """Convierte respuestas de ítems en registros de evidencia por ítem.

    Devuelve una lista de dicts con las claves exactas que consume
    `repositories.academy.record_evidence` (sin `user_id`)."""
    records = []
    for it in items:
        if it.id not in answers:
            continue
        correct = answers[it.id] == it.correct_index
        records.append(
            {
                "level_id": level_id,
                "objective_id": objective_id,
                "skill": it.skill,
                "item_id": it.id,
                "item_type": item_type,
                "difficulty": getattr(it, "difficulty", difficulty),
                "source": source,
                "result": 1.0 if correct else 0.0,
                "curriculum_version": curriculum_version,
                "assessment_version": assessment_version,
            }
        )
    return records


# Tipos y fuentes de evidencia reconocidos (invariante: un registro de evidencia
# siempre debe pertenecer a uno de estos conjuntos para ser interpretable por el
# Student Model). Se amplían en paralelo a nuevos motores (p. ej. 'listening').
EVIDENCE_ITEM_TYPES: tuple[str, ...] = (
    "mcq",
    "speaking",
    "writing",
    "pronunciation",
)

EVIDENCE_SOURCES: tuple[str, ...] = (
    "objective_assessment",
    "exam",
    "speaking",
    "writing",
    "pronunciation",
)


def evidence_record_errors(
    record: dict,
    *,
    user_id: str,
    level: Level,
    canonical_skills: tuple[str, ...] = CANONICAL_SKILLS,
    item_types: tuple[str, ...] = EVIDENCE_ITEM_TYPES,
    sources: tuple[str, ...] = EVIDENCE_SOURCES,
) -> list[str]:
    """Devuelve las violaciones de invariantes de un registro de evidencia
    (lista vacía = válido).

    Invariantes: `user_id` no vacío; `objective_id` vacío (evidencia de nivel,
    p. ej. un examen) o perteneciente al nivel; `skill` canónica; `item_type` y
    `source` en sus conjuntos conocidos; `curriculum_version` y
    `assessment_version` no vacíos (reproducibilidad); `result` numérico en [0,1].
    """
    errors: list[str] = []
    if not user_id:
        errors.append("user_id vacío")

    objective_ids = {o.id for o in level.objectives()}
    objective_id = record.get("objective_id", "")
    if objective_id and objective_id not in objective_ids:
        errors.append(
            f"objective_id '{objective_id}' no pertenece a {level.level_id}"
        )

    skill = record.get("skill", "")
    if skill not in canonical_skills:
        errors.append(f"skill '{skill}' no canónica")

    item_type = record.get("item_type", "")
    if item_type not in item_types:
        errors.append(f"item_type '{item_type}' desconocido")

    source = record.get("source", "")
    if source not in sources:
        errors.append(f"source '{source}' desconocida")

    if not record.get("curriculum_version"):
        errors.append("curriculum_version vacío")
    if not record.get("assessment_version"):
        errors.append("assessment_version vacío")

    result = record.get("result")
    if isinstance(result, bool) or not isinstance(result, (int, float)):
        errors.append("result no numérico")
    elif not 0.0 <= float(result) <= 1.0:
        errors.append(f"result {result} fuera de [0,1]")

    return errors


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
    confidence = _placement_confidence(by_diff, answered, len(items))
    return {
        "level": level,
        "confidence": confidence,
        "answered": answered,
        "correct": sum(1 for it in items if answers.get(it.id) == it.correct_index),
        "skills": _skill_breakdown(items, answers),
        "placement_version": PLACEMENT_VERSION,
    }


def _placement_confidence(
    by_diff: dict[int, dict[str, int]], answered: int, total: int
) -> float:
    """Confianza del test de nivel basada en cobertura y consistencia.

    No crece linealmente con el nº de respuestas: premia cubrir el test (cobertura)
    y que el rendimiento sea homogéneo entre bandas de dificultad (consistencia).
    Un rendimiento muy dispar (acierto perfecto en lo fácil y cero en lo difícil)
    baja la confianza, lo que corrige el antiguo ``0.5 + 0.05·answered``."""
    if answered == 0 or total == 0:
        return 0.0
    accs = [
        b["correct"] / b["total"] for b in by_diff.values() if b["total"] > 0
    ]
    coverage = answered / total
    consistency = 1.0 - (max(accs) - min(accs)) if accs else 0.0
    confidence = coverage * (0.4 + 0.6 * consistency)
    return round(min(0.95, max(0.0, confidence)), 2)


# --- Placement adaptativo (IRT-lite) -------------------------------------

PLACEMENT_START_THETA = 3.0
PLACEMENT_THETA_MIN = -3.0
PLACEMENT_THETA_MAX = 9.0
MAX_PLACEMENT_ITEMS = 8
# Mínimo de ítems antes de poder detener por criterio estadístico (evita parar
# con muy poca información).
PLACEMENT_MIN_ITEMS = 4
# Error estándar de θ por debajo del cual el placement se da por suficientemente
# preciso y se detiene antes del máximo de ítems.
PLACEMENT_SE_THRESHOLD = 0.5


def _p_correct(theta: float, difficulty: int) -> float:
    """Probabilidad de acierto del modelo logístico de un parámetro (1PL)."""
    return 1.0 / (1.0 + math.exp(difficulty - theta))


def ability_theta(responses: list[tuple[int, bool]]) -> float:
    """Estima la habilidad θ por máxima verosimilitud con prior débil (MAP).

    `responses` es una lista de tuplas `(difficulty, correct)`. Se maximiza la
    log-verosimilitud de la 1PL mediante Newton-Raphson; el prior débil (una
    normal suave centrada en `PLACEMENT_START_THETA`) estabiliza el caso
    todo-acierto/todo-fallo. Devuelve θ redondeado a 3 decimales."""
    if not responses:
        return PLACEMENT_START_THETA
    theta = PLACEMENT_START_THETA
    for _ in range(20):
        grad = 0.0
        hess = 0.0
        for difficulty, correct in responses:
            p = _p_correct(theta, difficulty)
            grad += (1.0 - p) if correct else -p
            hess -= p * (1.0 - p)
        grad += (PLACEMENT_START_THETA - theta) * 0.1
        hess -= 0.1
        if abs(hess) < 1e-12:
            break
        delta = grad / hess
        theta -= delta
        theta = max(PLACEMENT_THETA_MIN, min(PLACEMENT_THETA_MAX, theta))
        if abs(delta) < 1e-6:
            break
    return round(theta, 3)


def theta_to_level(theta: float) -> str:
    """Mapea θ (escala ~dificultad 1..6) a nivel CEFR con fronteras de media banda."""
    if theta < 1.5:
        return "A1"
    if theta < 2.5:
        return "A2"
    if theta < 3.5:
        return "B1"
    if theta < 4.5:
        return "B2"
    if theta < 5.5:
        return "C1"
    return "C2"


def _item_information(theta: float, difficulty: int) -> float:
    """Información de Fisher de un ítem 1PL en θ: p·(1-p), máxima en dificultad≈θ."""
    p = _p_correct(theta, difficulty)
    return p * (1.0 - p)


def select_next_item(
    items: list, answered_ids: set[str], theta: float
) -> object | None:
    """Ítem sin responder con máxima información (Fisher) en θ.

    En el modelo 1PL la información es máxima cuando la dificultad del ítem se
    acerca a θ, de modo que coincide con "dificultad más cercana a θ". Empate:
    menor dificultad y, si persiste, el primero en el orden de `items`. None si
    no quedan."""
    remaining = [it for it in items if it.id not in answered_ids]
    if not remaining:
        return None
    return max(
        remaining,
        key=lambda it: (_item_information(theta, it.difficulty), -it.difficulty),
    )


def placement_standard_error(
    theta: float, responses: list[tuple[int, bool]]
) -> float | None:
    """Error estándar de θ: inverso de la raíz de la información de Fisher.

    Incluye el prior débil (+1) usado en `ability_theta`. Devuelve None si no hay
    respuestas (θ no estimada)."""
    if not responses:
        return None
    info = 1.0 + sum(
        p * (1.0 - p) for p in (_p_correct(theta, b) for b, _ in responses)
    )
    return round(1.0 / math.sqrt(info), 3)


def placement_adaptive_confidence(
    theta: float, responses: list[tuple[int, bool]]
) -> float:
    """Confianza (0..0.95) derivada del error estándar de θ (información de Fisher)."""
    se = placement_standard_error(theta, responses)
    if se is None:
        return 0.0
    return round(min(0.95, max(0.0, 1.0 - se)), 2)


def placement_should_stop(
    answered: int, total_items: int, standard_error: float | None
) -> bool:
    """Criterio de parada del placement adaptativo.

    True si se agotaron los ítems, se alcanzó el máximo, o el error estándar de θ
    cae bajo el umbral tras responder el mínimo de ítems. Con el banco actual de
    8 ítems el umbral rara vez se alcanza, pero el criterio queda explícito y
    aplicará al ampliar el banco."""
    if answered >= total_items or answered >= MAX_PLACEMENT_ITEMS:
        return True
    return (
        standard_error is not None
        and answered >= PLACEMENT_MIN_ITEMS
        and standard_error < PLACEMENT_SE_THRESHOLD
    )


def _skill_breakdown(items: list, answers: dict[str, int]) -> dict[str, dict]:
    """Desglose por destreza de las respuestas: {skill: {correct, total, score}}."""
    per_skill: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    for it in items:
        if it.id not in answers:
            continue
        per_skill[it.skill]["total"] += 1
        if answers[it.id] == it.correct_index:
            per_skill[it.skill]["correct"] += 1
    return {
        skill: {
            "correct": b["correct"],
            "total": b["total"],
            "score": round(b["correct"] / b["total"], 3) if b["total"] else 0.0,
        }
        for skill, b in per_skill.items()
    }


def placement_result_adaptive(items: list, answers: dict[str, int]) -> dict:
    """Resultado del placement adaptativo: θ, nivel CEFR, confianza, contadores,
    desglose por destreza y versión del motor."""
    responses = [
        (it.difficulty, answers[it.id] == it.correct_index)
        for it in items
        if it.id in answers
    ]
    theta = ability_theta(responses) if responses else PLACEMENT_START_THETA
    level = theta_to_level(theta)
    confidence = placement_adaptive_confidence(theta, responses)
    correct = sum(1 for it in items if answers.get(it.id) == it.correct_index)
    answered = len(responses)
    return {
        "level": level,
        "theta": theta,
        "confidence": confidence,
        "answered": answered,
        "correct": correct,
        "skills": _skill_breakdown(items, answers),
        "placement_version": PLACEMENT_VERSION,
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

"""Adaptive Engine (puro, determinista, sin I/O).

Casa del "qué hacer ahora": convierte el perfil CEFR por destreza (derivado por
`services.academy.build_skill_profile`) y la evidencia acumulada en decisiones
pedagógicas reproducibles:

    perfil CEFR → stability → estimated_level → readiness → reevaluación
                → Today's Plan

No decide el progreso el LLM: el LLM genera evidencia; este motor decide. No
importa FastAPI ni toca la base de datos (recibe datos ya agregados).

Relación con el resto del dominio:
- `services.academy` construye el perfil de destreza (score/confidence/evidence/
  review_due) y agrega el overall ponderado.
- `services.forgetting` aporta la curva de olvido (retrieval_probability).
- `services.curriculum` define niveles CEFR y el contenido (Level).
"""

from __future__ import annotations

import math

from services.academy import overall_cefr_score
from services.curriculum import get_objective
from services.forgetting import days_since, retrieval_probability

# --- Nivel continuo -------------------------------------------------------

# Mapa nivel CEFR → valor numérico continuo (A1=1.0 … C2=6.0). Permite expresar
# "A2.7" en lugar de una etiqueta discreta inmutable.
CEFR_NUMERIC: dict[str, float] = {
    "A1": 1.0,
    "A2": 2.0,
    "B1": 3.0,
    "B2": 4.0,
    "C1": 5.0,
    "C2": 6.0,
}


def numeric_to_level(numeric: float) -> str:
    """Etiqueta CEFR de un nivel continuo (fronteras de media banda)."""
    if numeric < 1.5:
        return "A1"
    if numeric < 2.5:
        return "A2"
    if numeric < 3.5:
        return "B1"
    if numeric < 4.5:
        return "B2"
    if numeric < 5.5:
        return "C1"
    return "C2"


def estimated_level(profile: list[dict]) -> dict:
    """Nivel CEFR estimado de forma continua a partir del perfil por destreza.

    Convierte el `overall_cefr_score` ponderado (0..1) a una escala continua
    A1=1.0 … C2=6.0 y devuelve `{level, numeric, confidence}`, donde `confidence`
    es la confianza media de las destrezas con evidencia (0.0 si no hay ninguna).
    """
    overall = overall_cefr_score(profile)
    numeric = round(1.0 + 5.0 * overall, 2)
    confidences = [
        float(e["confidence"]) for e in profile if e.get("evidence_count", 0) > 0
    ]
    confidence = (
        round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    )
    return {
        "level": numeric_to_level(numeric),
        "numeric": numeric,
        "confidence": confidence,
    }


# --- Estabilidad ----------------------------------------------------------

# Umbral de recuperación bajo el cual la destreza se considera inestable.
STABILITY_RETRIEVAL_THRESHOLD = 0.7


def skill_stability(
    score: float, confidence: float, last_seen_at: str, now: str
) -> float:
    """Estabilidad de una destreza (0..1): dominio × retención × consistencia.

    Combina la confianza (EMA de "supera el umbral", es decir, consistencia) con
    la probabilidad de recuperación actual de la curva de olvido. Un dominio alto
    mantenido en el tiempo es estable; un dominio alto sin repaso reciente decae
    (retrieval) y una consistencia baja (muchos aciertos/fallos) también penaliza.
    """
    confidence = max(0.0, min(1.0, confidence))
    retrieval = retrieval_probability(score, last_seen_at, now)
    return round(confidence * retrieval, 3)


# --- Readiness (preparación para el siguiente nivel) -----------------------

# Mínimos de score por destreza para considerarla "preparada" para subir de nivel.
# Generalizables por banda CEFR en el futuro; por ahora un mínimo por destreza.
READINESS_MINIMUMS: dict[str, float] = {
    "grammar": 0.7,
    "vocabulary": 0.7,
    "pronunciation": 0.6,
    "listening": 0.7,
    "speaking": 0.6,
    "reading": 0.7,
    "writing": 0.6,
}
# Confianza mínima (consistencia EMA) para que una destreza cuente como preparada.
READINESS_MIN_CONFIDENCE = 0.6
# Nº mínimo de evidencias para que una destreza sea evaluable como "preparada".
READINESS_MIN_EVIDENCE = 3
# Mínimo por defecto para destrezas fuera del mapa (no deberían aparecer).
READINESS_DEFAULT_MINIMUM = 0.7


def readiness(profile: list[dict], target_level: str) -> dict:
    """Preparación de cada destreza para el `target_level`.

    Una destreza está `ready` solo si supera simultáneamente su mínimo de score,
    la confianza mínima y el mínimo de evidencias. No se "pasa" de nivel por
    promedio: una destreza bloqueante deja `ready` en False aunque el resto estén
    altas. Devuelve per-skill, `overall` (% de destrezas listas), `blocking_skills`
    (destrezas evaluadas pero no listas) y `ready` global.
    """
    skills = []
    ready_count = 0
    evaluated_count = 0
    blocking: list[str] = []
    for entry in profile:
        skill = entry["skill"]
        minimum = READINESS_MINIMUMS.get(skill, READINESS_DEFAULT_MINIMUM)
        evidence_count = entry.get("evidence_count", 0)
        score = float(entry.get("score", 0.0))
        confidence = float(entry.get("confidence", 0.0))
        evaluated = evidence_count > 0
        is_ready = (
            evaluated
            and score >= minimum
            and confidence >= READINESS_MIN_CONFIDENCE
            and evidence_count >= READINESS_MIN_EVIDENCE
        )
        if evaluated:
            evaluated_count += 1
            if is_ready:
                ready_count += 1
            else:
                blocking.append(skill)
        skills.append(
            {
                "skill": skill,
                "score": round(score, 3),
                "confidence": round(confidence, 3),
                "evidence_count": evidence_count,
                "minimum": minimum,
                "ready": is_ready,
            }
        )
    overall = round(ready_count / evaluated_count * 100, 1) if evaluated_count else 0.0
    return {
        "target_level": target_level,
        "skills": skills,
        "overall": overall,
        "blocking_skills": blocking,
        "ready": overall >= 100.0,
    }


# --- Reevaluación continua -------------------------------------------------

# Mínimo total de evidencias antes de considerar una reevaluación.
REASSESS_MIN_EVIDENCE = 6
# Confianza media mínima para proponer reevaluación (evidencia suficiente y
# consistente).
REASSESS_MIN_CONFIDENCE = 0.6
# Días mínimos desde la última evaluación formal para reevaluar por tiempo.
REASSESS_MIN_DAYS = 7.0
# Estabilidad por debajo de la cual se propone reevaluar (conocimiento en riesgo).
REASSESS_STABILITY_THRESHOLD = 0.5


def _weakest_skill(profile: list[dict]) -> dict | None:
    """Destreza evaluada más débil (menor score; empate: menos evidencia)."""
    with_evidence = [e for e in profile if e.get("evidence_count", 0) > 0]
    if not with_evidence:
        return None
    return min(with_evidence, key=lambda e: (e["score"], -e["evidence_count"]))


def reassessment_due(
    profile: list[dict], assessment_history: list[dict], now: str
) -> dict | None:
    """Propone una reevaluación de destreza/nivel, o None si aún no procede.

    Solo con evidencia suficiente y confianza media suficiente. Razones:
    - `first-reassessment`: aún no hay ninguna evaluación formal.
    - `stability-low`: la destreza más débil tiene estabilidad por debajo del
      umbral (conocimiento en riesgo de olvido).
    - `time-elapsed`: pasó el tiempo mínimo desde la última evaluación formal.

    Devuelve `{skill, level, reason}` con la destreza más débil y el nivel
    estimado actual, o None.
    """
    total_evidence = sum(e.get("evidence_count", 0) for e in profile)
    if total_evidence < REASSESS_MIN_EVIDENCE:
        return None
    weakest = _weakest_skill(profile)
    if weakest is None:
        return None
    confidences = [
        float(e["confidence"]) for e in profile if e.get("evidence_count", 0) > 0
    ]
    avg_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
    if avg_conf < REASSESS_MIN_CONFIDENCE:
        return None

    last = max((a.get("created_at", "") for a in assessment_history), default="")
    if not last:
        reason = "first-reassessment"
    else:
        # La estabilidad solo es medible con timestamp de última evidencia; sin él
        # no hay olvido observable y no se puede afirmar "stability-low".
        last_seen = weakest.get("last_evidence", "")
        stability = (
            skill_stability(
                weakest["score"],
                weakest.get("confidence", 0.0),
                last_seen,
                now,
            )
            if last_seen
            else None
        )
        if stability is not None and stability < REASSESS_STABILITY_THRESHOLD:
            reason = "stability-low"
        elif days_since(last, now) >= REASSESS_MIN_DAYS:
            reason = "time-elapsed"
        else:
            return None

    return {
        "skill": weakest["skill"],
        "level": estimated_level(profile)["level"],
        "reason": reason,
    }


# --- Today's Plan ---------------------------------------------------------

# Presupuesto por defecto de la sesión diaria (minutos).
TODAY_BUDGET = 30
# Reparto del presupuesto entre categorías (weakness / review / new / easy_wins).
# Ajustable; la suma ideal es 1. Se renormaliza sobre las categorías presentes.
TODAY_MIX: dict[str, float] = {
    "weakness": 0.40,
    "review": 0.30,
    "new": 0.20,
    "easy_wins": 0.10,
}


def _objective_title(level, objective_id: str | None) -> str:
    """Título legible del objetivo (desde el currículo) o None."""
    if level is None or not objective_id:
        return None
    obj = get_objective(level, objective_id)
    return obj.title if obj is not None else None


def _largest_remainder(minutes_float: list[float], total: int) -> list[int]:
    """Reparte `total` (entero) entre minutos reales con el método del resto mayor,
    de modo que la suma sea exactamente `total` y el reparto sea determinista."""
    if not minutes_float:
        return []
    floors = [int(math.floor(m)) for m in minutes_float]
    leftover = total - sum(floors)
    fracs = sorted(
        (
            (m - f, i)
            for i, (m, f) in enumerate(zip(minutes_float, floors, strict=False))
        ),
        key=lambda x: (-x[0], x[1]),
    )
    for j in range(leftover):
        floors[fracs[j % len(fracs)][1]] += 1
    return floors


def _assign_minutes(
    items: list[dict], budget: int, mix: dict[str, float] | None = None
) -> list[dict]:
    """Asigna minutos a los ítems según el `mix` por kind (compartido a partes
    iguales dentro del mismo kind), sumando exactamente `budget`."""
    mix = mix if mix is not None else TODAY_MIX
    if not items:
        return items
    weights = [mix.get(it["kind"], 0.0) for it in items]
    total_weight = sum(weights)
    if total_weight <= 0.0:
        # Sin pesos conocidos: reparto a partes iguales.
        n = len(items)
        base = budget // n
        remainder = budget % n
        for i, it in enumerate(items):
            it["minutes"] = base + (1 if i < remainder else 0)
        return items
    minutes_float = [budget * w / total_weight for w in weights]
    minutes = _largest_remainder(minutes_float, budget)
    for it, m in zip(items, minutes, strict=False):
        it["minutes"] = m
    return items


def today_plan(
    profile: list[dict],
    level=None,
    remediation: list[dict] | None = None,
    mastered_ids: set[str] | None = None,
    next_objective_id: str | None = None,
    budget_minutes: int = TODAY_BUDGET,
) -> list[dict]:
    """Construye el plan de estudio de hoy, equilibrando weakness/review/new/easy.

    Combina el perfil por destreza, el plan de remediación, las destrezas "a
    repasar" (olvido), el siguiente objetivo del currículo y un "quick win" para
    motivación. Devuelve una lista de ítems `{kind, skill, objective_id, title,
    reason, minutes}` con minutos que suman `budget_minutes`. Es determinista
    dados los mismos inputs.

    Se evita un 100% de debilidades: la mezcla `TODAY_MIX` garantiza material
    nuevo y un refuerzo de confianza.
    """
    remediation = remediation or []
    mastered_ids = mastered_ids or set()
    items: list[dict] = []

    # Weakness: destrezas débiles del plan de remediación (más débil primero).
    for r in remediation:
        oid = r["objective_ids"][0] if r.get("objective_ids") else None
        items.append(
            {
                "kind": "weakness",
                "skill": r["skill"],
                "objective_id": oid,
                "title": _objective_title(level, oid) or f"Practice {r['skill']}",
                "reason": f"weakest skill: {r['skill']}",
            }
        )

    # Review: destrezas con repaso pendiente (curva de olvido).
    for e in profile:
        if e.get("review_due"):
            items.append(
                {
                    "kind": "review",
                    "skill": e["skill"],
                    "objective_id": None,
                    "title": f"Review {e['skill']}",
                    "reason": "due for review",
                }
            )

    # New: siguiente material del currículo (progresión).
    if next_objective_id:
        items.append(
            {
                "kind": "new",
                "skill": None,
                "objective_id": next_objective_id,
                "title": _objective_title(level, next_objective_id)
                or "Next objective",
                "reason": "next in path",
            }
        )

    # Easy wins: refuerzo de confianza con una destreza fuerte reciente.
    strong = [
        e
        for e in profile
        if e.get("evidence_count", 0) > 0 and not e.get("review_due")
    ]
    strong.sort(key=lambda e: -e["score"])
    if strong:
        e = strong[0]
        items.append(
            {
                "kind": "easy_wins",
                "skill": e["skill"],
                "objective_id": None,
                "title": f"Quick win: {e['skill']}",
                "reason": "confidence boost",
            }
        )

    return _assign_minutes(items, budget_minutes)


# --- Session Engine -------------------------------------------------------

# Reparto del presupuesto de la sesión entre categorías. La suma ideal es 1; se
# renormaliza sobre las categorías presentes. `listening` compite con el resto.
SESSION_MIX: dict[str, float] = {
    "review": 0.30,
    "listening": 0.15,
    "weakness": 0.30,
    "new": 0.15,
    "easy_wins": 0.10,
}

# Máximo de pasos por categoría en una sesión: evita saturar la sesión cuando hay
# muchas señales pendientes (p. ej. un usuario nuevo tiene todas las sub-destrezas
# de listening sin practicar). La sesión diaria debe ser corta y accionable.
SESSION_CAPS: dict[str, int] = {
    "review": 3,
    "listening": 2,
    "weakness": 2,
    "new": 1,
    "easy_wins": 1,
}


def steps_of(steps: list[dict], kind: str) -> list[dict]:
    """Pasos de una categoría concreta dentro de una sesión."""
    return [s for s in steps if s["kind"] == kind]


def session_plan(
    profile: list[dict],
    level=None,
    remediation: list[dict] | None = None,
    mastered_ids: set[str] | None = None,
    next_objective_id: str | None = None,
    listening_weak: list[str] | None = None,
    budget_minutes: int = TODAY_BUDGET,
) -> list[dict]:
    """Sesión diaria ordenada por prioridad pedagógica.

    Convierte todas las señales (olvido CEFR, listening pendiente, remediación,
    progresión y refuerzo) en una secuencia única y accionable, en este orden:

        1. review     — repaso vencido (recuperación activa, sin pistas)
        2. listening  — sub-destrezas de listening pendientes/debilitadas
        3. weakness   — objetivos de la destreza más débil (remediación)
        4. new        — siguiente objetivo del currículo (progresión)
        5. easy_wins  — refuerzo de confianza

    Devuelve pasos `{kind, skill, subskill, objective_id, level_id, skills,
    title, reason, minutes}` con minutos que suman `budget_minutes` según
    `SESSION_MIX`. Cada categoría está limitada por `SESSION_CAPS`. Determinista
    dados los mismos inputs.
    """
    remediation = remediation or []
    mastered_ids = mastered_ids or set()
    listening_weak = listening_weak or []
    steps: list[dict] = []

    def _cap(kind: str) -> int:
        return SESSION_CAPS.get(kind, 1)

    # 1. Review: destrezas con repaso pendiente (curva de olvido).
    for e in profile:
        if len(steps_of(steps, "review")) >= _cap("review"):
            break
        if e.get("review_due"):
            steps.append(
                {
                    "kind": "review",
                    "skill": e["skill"],
                    "subskill": None,
                    "objective_id": None,
                    "level_id": None,
                    "skills": [],
                    "title": f"Review {e['skill']}",
                    "reason": "due for review",
                }
            )

    # 2. Listening: sub-destrezas pendientes (ya ordenadas por debilidad).
    for subskill in listening_weak:
        if len(steps_of(steps, "listening")) >= _cap("listening"):
            break
        steps.append(
            {
                "kind": "listening",
                "skill": "listening",
                "subskill": subskill,
                "objective_id": None,
                "level_id": None,
                "skills": [],
                "title": f"Listen: {subskill}",
                "reason": "listening pending",
            }
        )

    # 3. Weakness: destrezas débiles del plan de remediación (más débil primero).
    for r in remediation:
        if len(steps_of(steps, "weakness")) >= _cap("weakness"):
            break
        oid = r["objective_ids"][0] if r.get("objective_ids") else None
        obj = get_objective(level, oid) if (level is not None and oid) else None
        steps.append(
            {
                "kind": "weakness",
                "skill": r["skill"],
                "subskill": None,
                "objective_id": oid,
                "level_id": level.level_id if level is not None else None,
                "skills": list(obj.skills) if obj is not None else [],
                "title": _objective_title(level, oid) or f"Practice {r['skill']}",
                "reason": f"weakest skill: {r['skill']}",
            }
        )

    # 4. New: siguiente material del currículo (progresión).
    if next_objective_id and len(steps_of(steps, "new")) < _cap("new"):
        obj = get_objective(level, next_objective_id) if level is not None else None
        steps.append(
            {
                "kind": "new",
                "skill": None,
                "subskill": None,
                "objective_id": next_objective_id,
                "level_id": level.level_id if level is not None else None,
                "skills": list(obj.skills) if obj is not None else [],
                "title": _objective_title(level, next_objective_id)
                or "Next objective",
                "reason": "next in path",
            }
        )

    # 5. Easy wins: refuerzo de confianza con una destreza fuerte reciente.
    strong = [
        e
        for e in profile
        if e.get("evidence_count", 0) > 0 and not e.get("review_due")
    ]
    strong.sort(key=lambda e: -e["score"])
    if strong and len(steps_of(steps, "easy_wins")) < _cap("easy_wins"):
        e = strong[0]
        steps.append(
            {
                "kind": "easy_wins",
                "skill": e["skill"],
                "subskill": None,
                "objective_id": None,
                "level_id": None,
                "skills": [],
                "title": f"Quick win: {e['skill']}",
                "reason": "confidence boost",
            }
        )

    return _assign_minutes(steps, budget_minutes, mix=SESSION_MIX)


def session_summary(steps: list[dict]) -> dict:
    """Resumen de la sesión para la tarjeta principal: cuánto repasar y cuánto
    practicar (nuevo + debilidad). El refuerzo no se cuenta en ninguna de las dos."""
    review_count = sum(1 for s in steps if s["kind"] in ("review", "listening"))
    practice_count = sum(1 for s in steps if s["kind"] in ("weakness", "new"))
    return {"review_count": review_count, "practice_count": practice_count}

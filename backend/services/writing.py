"""Scorer determinista de writing (rubric CEFR de 6 dimensiones).

Reutiliza el evaluador de gramática determinista (find_errors) para producir un
score por criterio y un overall ponderado. Sigue la premisa del proyecto: la
evidencia la extrae el LLM, pero el score lo calcula SIEMPRE un scorer
determinista (nunca "el LLM te pone B1").
"""
from __future__ import annotations

import re

from services import adaptive
from services.curriculum import RUBRIC_VERSION
from services.forgetting import review_due as forgetting_review_due
from services.grammar import find_errors

# Dimensiones del rubric de writing (alineadas con CEFR).
WRITING_CRITERIA: tuple[str, ...] = (
    "task_completion",
    "grammatical_accuracy",
    "lexical_resource",
    "organization",
    "coherence",
    "register",
)

# Pesos por defecto (suman 1).
CRITERION_WEIGHTS: dict[str, float] = {
    "task_completion": 0.25,
    "grammatical_accuracy": 0.20,
    "lexical_resource": 0.20,
    "organization": 0.15,
    "coherence": 0.10,
    "register": 0.10,
}

# Parámetros del diagnóstico longitudinal de writing (V1.17). Un criterio está
# "débil" si no se ha practicado (attempts == 0) o si su media está por debajo del
# umbral con un mínimo de intentos (evidencia suficiente).
WRITING_WEAK_THRESHOLD = 0.6
WRITING_TREND_WINDOW = 5

# --- Student Model ownership del diagnóstico (V1.17) ------------------------
# El diagnóstico deja de ser un agregador mean/min/max: cada criterio expone las
# mismas señales que el Student Model (EMA de recent_score y confidence, stability
# y review_due por olvido), de modo que el diagnóstico es una VISTA de esas señales
# y no un cálculo estadístico propio.
WRITING_EMA_ALPHA = 0.5
WRITING_CONFIDENCE_THRESHOLD = 0.6

# Referencia léxica: 5 palabras de contenido ≈ vocabulario adecuado.
_LEXICAL_REFERENCE = 5.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    """Tokeniza en minúsculas, sin puntuación, conservando orden y repeticiones."""
    return re.findall(r"[a-z0-9']+", text.lower())


def _sentences(text: str) -> int:
    """Número de frases (grupos de puntuación final). 1 si hay texto sin puntuación."""
    return len(re.findall(r"[.!?]+", text)) or (1 if text.strip() else 0)


def score_writing(text: str, expected: str) -> dict:
    """Puntúa una producción escrita frente a un texto esperado (escritura controlada).

    Devuelve un dict con `text`, `expected`, `criteria` (dict criterion → score
    0..1), y `overall` (media ponderada 0..1, redondeada a 3 decimales).
    """
    text_tokens = _tokens(text)
    expected_tokens = _tokens(expected)

    grammatical_accuracy = round(
        max(0.0, 1.0 - 0.25 * len(find_errors(text))), 3
    )

    if expected_tokens:
        lexical_resource = round(
            _clamp(
                len(set(text_tokens) & set(expected_tokens))
                / len(set(expected_tokens))
            ),
            3,
        )
        task_completion = round(
            _clamp(
                len([t for t in expected_tokens if t in text_tokens])
                / len(expected_tokens)
            ),
            3,
        )
        coherence = round(_clamp(len(text_tokens) / max(1, len(expected_tokens))), 3)
        organization = round(
            _clamp(_sentences(text) / max(1, _sentences(expected))), 3
        )
    else:
        lexical_resource = 1.0
        task_completion = 1.0
        coherence = 1.0
        organization = 1.0

    # Sin contexto de tarea no hay señal determinista de registro: neutro.
    register = 0.5

    criteria = {
        "task_completion": task_completion,
        "grammatical_accuracy": grammatical_accuracy,
        "lexical_resource": lexical_resource,
        "organization": organization,
        "coherence": coherence,
        "register": register,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in WRITING_CRITERIA), 3
    )

    return {
        "text": text,
        "expected": expected,
        "criteria": criteria,
        "overall": overall,
    }


def scores_from_evidence(evidence: dict) -> dict:
    """Convierte evidencia extraída por el LLM en los 6 criterios + overall.

    `evidence` es el dict normalizado de `writing_llm.parse_writing_evidence`.
    Devuelve {"criteria": {...}, "overall": float}."""
    task_completion = 1.0 if evidence["task_completed"] else 0.0
    grammatical_accuracy = round(
        _clamp(1.0 - 0.25 * evidence["grammar_errors"]), 3
    )
    lexical_resource = round(
        _clamp(len(set(evidence["lexical_tokens"])) / _LEXICAL_REFERENCE), 3
    )
    organization = round(_clamp(float(evidence["organization"])), 3)
    coherence = round(_clamp(float(evidence["coherence"])), 3)
    register = round(_clamp(float(evidence["register"])), 3)

    criteria = {
        "task_completion": task_completion,
        "grammatical_accuracy": grammatical_accuracy,
        "lexical_resource": lexical_resource,
        "organization": organization,
        "coherence": coherence,
        "register": register,
    }

    overall = round(
        sum(CRITERION_WEIGHTS[c] * criteria[c] for c in WRITING_CRITERIA), 3
    )

    return {
        "criteria": criteria,
        "overall": overall,
    }


def evidence_from_writing(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
    evidence_kind: str = "familiar",
) -> list[dict]:
    """Convierte el resultado de score_writing en registros de evidencia.

    Una fila por criterio del rubric (item_id = criterio) más una fila 'overall'.
    Todas con source='writing', item_type='writing', difficulty=1. El instrumento
    de medida es la rúbrica, versionada en `assessment_version`."""
    records = [
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "writing",
            "item_id": criterion,
            "item_type": "writing",
            "difficulty": 1,
            "source": "writing",
            "result": float(result["criteria"][criterion]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
            "evidence_kind": evidence_kind,
        }
        for criterion in WRITING_CRITERIA
    ]
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "writing",
            "item_id": "overall",
            "item_type": "writing",
            "difficulty": 1,
            "source": "writing",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
            "evidence_kind": evidence_kind,
        }
    )
    return records


def _mean_trend(rows: list[dict], window: int = WRITING_TREND_WINDOW) -> dict:
    """Tendencia de la media de `result` (0..1) de los últimos `window` vs previos.

    Las filas llegan en orden cronológico (id ASC). Devuelve
    `{recent_mean, prior_mean, delta, direction}` con `direction` en
    `{"up", "down", "flat", "n/a"}`. Adapta `listening.recent_trend` (que trabaja
    sobre `correct`) a medias de scores continuos.
    """
    if not rows:
        return {
            "recent_mean": None,
            "prior_mean": None,
            "delta": None,
            "direction": "n/a",
        }

    def _mean(subset: list[dict]) -> float:
        return round(sum(r["result"] for r in subset) / len(subset), 3)

    if len(rows) <= window:
        return {
            "recent_mean": _mean(rows),
            "prior_mean": None,
            "delta": None,
            "direction": "n/a",
        }
    recent = _mean(rows[-window:])
    prior = _mean(rows[:-window])
    delta = round(recent - prior, 3)
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "recent_mean": recent,
        "prior_mean": prior,
        "delta": delta,
        "direction": direction,
    }


def _ema(values: list[float], alpha: float = WRITING_EMA_ALPHA) -> float:
    """EMA de una secuencia cronológica de valores (0..1); 0.0 si está vacía.

    Refleja el rendimiento *reciente* (más peso a lo último), frente a la media
    aritmética que pondera toda la historia por igual (misma idea que
    `next_mastery_state`).
    """
    if not values:
        return 0.0
    recent = float(values[0])
    for value in values[1:]:
        recent = alpha * float(value) + (1 - alpha) * recent
    return round(recent, 3)


def writing_diagnostic(evidence_rows: list[dict], now: str = "") -> dict:
    """Vista longitudinal de writing por criterio (Student Model ownership, V1.17).

    `evidence_rows` son las filas de `academy_evidence` con `skill="writing"`
    (cada fila tiene `item_id` = criterio del rubric y `result` = score 0..1, más
    una fila `item_id="overall"` por intento). En lugar de un agregador mean/min/max
    propio, cada criterio expone las señales del Student Model:
    - `recent_score`: EMA del rendimiento (estado reciente, no toda la historia).
    - `lifetime_score`/`mean`: media de todo el historial.
    - `confidence`: EMA de "supera el umbral" (consistencia).
    - `stability`: dominio × retención (curva de olvido) vía `adaptive.skill_stability`.
    - `review_due`: olvido vencido, fallo reciente o confianza baja (no solo
      `mean < 0.6` con `attempts >= 3`).

    `now` (ISO) permite testear el olvido sin reloj de pared; vacío = sin decaimiento.
    Devuelve `criteria`, `weak`, `recommendation`, `attempts`, `overall_mean`,
    `overall_recent`, `trend` y `rubric_version`. Determinista, sin LLM ni red.
    """
    groups: dict[str, list[dict]] = {}
    overall_rows: list[dict] = []
    for row in evidence_rows:
        item_id = row.get("item_id") or ""
        if item_id == "overall":
            overall_rows.append(row)
            continue
        groups.setdefault(item_id, []).append(row)

    def _criterion(name: str, rows: list[dict]) -> dict:
        attempts = len(rows)
        results = [float(r["result"]) for r in rows if r.get("result") is not None]
        if not results:
            return {
                "criterion": name,
                "attempts": attempts,
                "mean": None,
                "recent_score": None,
                "lifetime_score": None,
                "confidence": None,
                "stability": None,
                "min": None,
                "max": None,
                "review_due": True,
            }
        mean = round(sum(results) / len(results), 3)
        recent = _ema(results)
        confidence = _ema(
            [1.0 if r >= WRITING_WEAK_THRESHOLD else 0.0 for r in results]
        )
        last_seen = max(
            r.get("created_at", "") for r in rows if r.get("result") is not None
        )
        review_due = (
            forgetting_review_due(recent, last_seen, now)
            or results[-1] < WRITING_WEAK_THRESHOLD
            or confidence < WRITING_CONFIDENCE_THRESHOLD
        )
        stability = adaptive.skill_stability(recent, confidence, last_seen, now)
        return {
            "criterion": name,
            "attempts": attempts,
            "mean": mean,
            "recent_score": recent,
            "lifetime_score": mean,
            "confidence": confidence,
            "stability": stability,
            "min": round(min(results), 3),
            "max": round(max(results), 3),
            "review_due": review_due,
        }

    criteria = [_criterion(c, groups.get(c, [])) for c in WRITING_CRITERIA]
    known = set(WRITING_CRITERIA)
    for name in sorted(set(groups) - known):
        criteria.append(_criterion(name, groups[name]))

    def _weak_key(name: str) -> tuple:
        entry = next(c for c in criteria if c["criterion"] == name)
        recent = entry["recent_score"]
        return (recent is None, recent if recent is not None else 0.0)

    weak = [c["criterion"] for c in criteria if c["review_due"]]
    weak.sort(key=_weak_key)

    recommendation = (
        "All writing criteria look strong."
        if not weak
        else "Focus on: " + ", ".join(weak)
    )

    overall_results = [
        float(r["result"]) for r in overall_rows if r.get("result") is not None
    ]
    overall_mean = (
        round(sum(overall_results) / len(overall_results), 3)
        if overall_results
        else None
    )

    return {
        "criteria": criteria,
        "weak": weak,
        "recommendation": recommendation,
        "attempts": len(overall_rows),
        "overall_mean": overall_mean,
        "overall_recent": _ema(overall_results) if overall_results else None,
        "trend": _mean_trend(overall_rows),
        "rubric_version": RUBRIC_VERSION,
    }


def writing_level(evidence_rows: list[dict], now: str = "") -> dict:
    """Writing Assessment 1.0: nivel CEFR continuo + confianza (determinista).

    Agrega la evidencia de writing (`item_id="overall"`, una fila por intento) en
    un `score` reciente (EMA), una `confidence` (EMA de "supera el umbral") y lo
    proyecta a la escala continua A1=1.0 … C2=6.0 → `{level, numeric}`. Produce la
    afirmación trazable "B1 · confidence 82%" a partir de evidencia versionada, sin
    LLM ni red. Sin evidencia → `level`/`numeric`/`score` None y confidence 0.0.

    `now` se acepta por simetría con `writing_diagnostic`/`writing_journey`
    (el nivel agregado no decae con el tiempo; la estabilidad por criterio ya lo
    refleja en el diagnóstico).
    """
    overall_rows = [r for r in evidence_rows if r.get("item_id") == "overall"]
    results = [
        float(r["result"]) for r in overall_rows if r.get("result") is not None
    ]
    if not results:
        return {
            "level": None,
            "numeric": None,
            "score": None,
            "confidence": 0.0,
            "attempts": 0,
        }
    score = _ema(results)
    confidence = _ema(
        [1.0 if r >= WRITING_WEAK_THRESHOLD else 0.0 for r in results]
    )
    numeric = round(1.0 + 5.0 * score, 2)
    return {
        "level": adaptive.numeric_to_level(numeric),
        "numeric": numeric,
        "score": score,
        "confidence": round(confidence, 3),
        "attempts": len(overall_rows),
    }


def writing_journey(evidence_rows: list[dict], now: str = "") -> dict:
    """Writing Journey (CEFR): trayectoria de nivel y confianza (V1.17).

    Proyecta la evidencia de writing (`item_id="overall"`, en orden cronológico)
    en una secuencia de snapshots acumulados (`numeric`, `level`, `confidence`),
    más el estado actual. Conecta el diagnóstico con el CEFR Journey: "A2.7 →
    B1.1 → B1.3" y "Confidence 72% → 79% → 86%". Determinista y sin LLM ni red.

    Devuelve `{current_level, current_numeric, current_confidence, attempts,
    steps}` con `steps` ordenados cronológicamente.
    """
    overall_rows = [r for r in evidence_rows if r.get("item_id") == "overall"]
    steps: list[dict] = []
    results_so_far: list[float] = []
    for row in overall_rows:
        if row.get("result") is None:
            continue
        results_so_far.append(float(row["result"]))
        score = _ema(results_so_far)
        confidence = _ema(
            [1.0 if r >= WRITING_WEAK_THRESHOLD else 0.0 for r in results_so_far]
        )
        numeric = round(1.0 + 5.0 * score, 2)
        steps.append(
            {
                "at": row.get("created_at", ""),
                "numeric": numeric,
                "level": adaptive.numeric_to_level(numeric),
                "confidence": round(confidence, 3),
            }
        )
    current = writing_level(evidence_rows, now)
    return {
        "current_level": current["level"],
        "current_numeric": current["numeric"],
        "current_confidence": current["confidence"],
        "attempts": len(overall_rows),
        "steps": steps,
    }

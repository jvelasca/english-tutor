"""Scorer determinista de speaking (rubric CEFR de 6 dimensiones).

Reutiliza los evaluadores deterministas existentes (phonetics, fluency, grammar,
vocabulary) para producir un score por criterio y un overall ponderado. Sigue la
premisa del proyecto: la evidencia la extrae el LLM, pero el score lo calcula SIEMPRE
un scorer determinista (nunca "el LLM te pone B1").

Un criterio puede no ser observable (p. ej. `pronunciation` sin audio o `fluency`
sin duración). En ese caso su `score` es `None`, `observed` es `False` y no entra en
el `overall`, que se recalcula solo sobre los criterios observados (renormalizando
los pesos). Así "desconocido" no se confunde con "50%".
"""
from __future__ import annotations

import re

from services.curriculum import RUBRIC_VERSION
from services.fluency import compute_fluency
from services.grammar import find_errors
from services.phonetics import composite_score

# Dimensiones del rubric de speaking (alineadas con CEFR).
SPEAKING_CRITERIA: tuple[str, ...] = (
    "task_achievement",
    "grammatical_control",
    "lexical_resource",
    "fluency",
    "pronunciation",
    "coherence",
)

# Pesos por defecto (suman 1). El overall es la media ponderada de los criterios
# observados (renormalizada sobre los presentes).
CRITERION_WEIGHTS: dict[str, float] = {
    "task_achievement": 0.25,
    "grammatical_control": 0.20,
    "lexical_resource": 0.20,
    "fluency": 0.15,
    "pronunciation": 0.10,
    "coherence": 0.10,
}

# Referencia de fluidez: 120 palabras por minuto ≈ hablante fluido.
_FLUENT_WPM = 120.0

# Penalizaciones de fluidez por señal de discurso extraída por el LLM (por
# autocorrección, titubeo y repetición): una producción fluida no se autocorrige
# ni titubea en exceso.
_FLUENCY_PENALTY_SELF_CORRECTION = 0.05
_FLUENCY_PENALTY_HESITATION = 0.03
_FLUENCY_PENALTY_REPETITION = 0.03

# Parámetros del diagnóstico longitudinal de speaking (V1.15). Un criterio está
# "débil" si no se ha practicado (attempts == 0) o si su media está por debajo del
# umbral con un mínimo de intentos (evidencia suficiente).
SPEAKING_WEAK_THRESHOLD = 0.6
SPEAKING_MIN_ATTEMPTS = 3
SPEAKING_TREND_WINDOW = 5


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    """Tokeniza en minúsculas, sin puntuación, conservando orden y repeticiones.

    No se apoya en vocabulary.extract_words a propósito: aquella devuelve palabras
    únicas ordenadas alfabéticamente y filtra stopwords, lo que anularía la
    semántica "con repetición/orden" de task_achievement. Aquí se conserva el flujo
    completo de tokens para que lexical (set) y task (lista) midan cosas distintas.
    """
    return re.findall(r"[a-z0-9']+", text.lower())


def lexical_diversity(tokens: list[str]) -> float:
    """Diversidad léxica (type-token ratio, TTR): vocabulario distinto / total.

    Sustituye al "conteo de palabras de contenido": mide riqueza léxica real
    (variedad frente a repetición), no solapamiento con un texto esperado. 0.0 si
    no hay tokens.
    """
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 3)


def _sequence_coherence(heard_tokens: list[str], expected_tokens: list[str]) -> float:
    """Coherencia de secuencia (read-aloud): preservación del orden esperado.

    Mide cuánto de la frase esperada se reproduce en el orden correcto usando la
    subsecuencia común más larga (LCS) normalizada por la longitud esperada. Así
    decir las palabras desordenadas o repetir la frase entera no puntúa como
    coherente (a diferencia del ratio de longitud, que podía "engañarse" con
    cualquier producción de la misma extensión). 1.0 si no hay referencia.
    """
    if not expected_tokens:
        return 1.0
    n, m = len(heard_tokens), len(expected_tokens)
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        for j in range(1, m + 1):
            if heard_tokens[i - 1] == expected_tokens[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return round(_clamp(prev[m] / len(expected_tokens)), 3)


def _fluency_score(heard: str, duration_seconds: float | None) -> float | None:
    """Fluidez (0..1) a partir de WPM; `None` cuando no se puede calcular (sin
    audio válido o sin palabras)."""
    info = compute_fluency(heard, duration_seconds)
    wpm = info["wpm"]
    if wpm is None:
        return None
    return round(_clamp(wpm / _FLUENT_WPM), 3)


def _weighted_overall(criteria: dict, observed: dict) -> float:
    """Overall = media ponderada de los criterios observados, con pesos
    renormalizados sobre los presentes. 0.0 si ninguno es observable."""
    total_weight = 0.0
    weighted_sum = 0.0
    for criterion in SPEAKING_CRITERIA:
        score = criteria.get(criterion)
        if observed.get(criterion, False) and score is not None:
            total_weight += CRITERION_WEIGHTS[criterion]
            weighted_sum += CRITERION_WEIGHTS[criterion] * score
    if total_weight == 0.0:
        return 0.0
    return round(weighted_sum / total_weight, 3)


def score_speaking(
    heard: str,
    expected: str,
    duration_seconds: float | None = None,
) -> dict:
    """Puntúa una producción oral frente a una frase/tarea esperada (read-aloud).

    Devuelve un dict con `heard`, `expected`, `criteria` (dict criterion → score
    0..1, o `None` si el criterio no es observable), `observed` (dict criterion →
    bool) y `overall` (media ponderada sobre los criterios observados).
    """
    heard_tokens = _tokens(heard)
    expected_tokens = _tokens(expected)

    # pronunciation: similitud palabra/fonética con lo esperado (0-100 → 0-1).
    pronunciation = round(composite_score(expected, heard)["score"] / 100, 3)

    # fluency: wpm frente a 120 wpm ≈ fluido; None si no se puede calcular.
    fluency = _fluency_score(heard, duration_seconds)

    # grammatical_control: 0 errores = 1.0; cada error resta 0.25; suelo 0.0.
    grammatical_control = round(
        max(0.0, 1.0 - 0.25 * len(find_errors(heard))), 3
    )

    # lexical_resource: cobertura del léxico esperado (tokens únicos, sin orden).
    # En read-aloud el objetivo es reproducir la frase esperada, así que la
    # cobertura es la señal correcta (no la diversidad).
    if expected_tokens:
        lexical_resource = round(
            _clamp(
                len(set(heard_tokens) & set(expected_tokens))
                / len(set(expected_tokens))
            ),
            3,
        )
    else:
        lexical_resource = 1.0

    # task_achievement: cobertura de tokens clave esperados (con repetición/orden).
    if expected_tokens:
        task_achievement = round(
            _clamp(
                len([t for t in expected_tokens if t in heard_tokens])
                / len(expected_tokens)
            ),
            3,
        )
    else:
        task_achievement = 1.0

    # coherence: preservación del orden de la frase esperada (read-aloud: sin
    # señal discursiva del LLM, la coherencia es "reproducir en el orden correcto").
    coherence = _sequence_coherence(heard_tokens, expected_tokens)

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
    }
    observed = {
        "task_achievement": True,
        "grammatical_control": True,
        "lexical_resource": True,
        "fluency": fluency is not None,
        "pronunciation": True,
        "coherence": True,
    }

    overall = _weighted_overall(criteria, observed)

    return {
        "heard": heard,
        "expected": expected,
        "criteria": criteria,
        "observed": observed,
        "overall": overall,
    }


def scores_from_evidence(
    evidence: dict,
    heard: str,
    duration_seconds: float | None = None,
) -> dict:
    """Convierte evidencia extraída por el LLM en los 6 criterios + overall.

    `evidence` es el dict normalizado de `speaking_llm.parse_speaking_evidence`.
    La pronunciación no es evaluable sin referencia de audio en este flujo, así que
    queda `None`/no observada. La fluidez se calcula por WPM si hay duración; si no,
    queda `None`/no observada. El `overall` se calcula solo sobre criterios
    observados. Devuelve {"criteria": {...}, "observed": {...}, "overall": float}.
    """
    task_achievement = 1.0 if evidence["task_achieved"] else 0.0
    grammatical_control = round(
        _clamp(1.0 - 0.25 * evidence["grammar_errors"]), 3
    )

    # lexical_resource: diversidad léxica real (TTR) sobre la producción, no
    # solapamiento con un texto esperado.
    lexical_resource = lexical_diversity(_tokens(heard))

    coherence = round(_clamp(float(evidence["coherence"])), 3)

    fluency = _fluency_score(heard, duration_seconds)
    if fluency is not None:
        # Una producción fluida se autocorrige, titubea y repite poco.
        penalty = (
            _FLUENCY_PENALTY_SELF_CORRECTION * evidence.get("self_corrections", 0)
            + _FLUENCY_PENALTY_HESITATION * evidence.get("hesitations", 0)
            + _FLUENCY_PENALTY_REPETITION * evidence.get("repetitions", 0)
        )
        fluency = round(_clamp(fluency - penalty), 3)

    pronunciation = None  # no observable sin audio de referencia

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
    }
    observed = {
        "task_achievement": True,
        "grammatical_control": True,
        "lexical_resource": True,
        "fluency": fluency is not None,
        "pronunciation": False,
        "coherence": True,
    }

    overall = _weighted_overall(criteria, observed)

    return {
        "criteria": criteria,
        "observed": observed,
        "overall": overall,
    }


def evidence_from_speaking(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
) -> list[dict]:
    """Convierte el resultado de score_speaking en registros de evidencia.

    Una fila por criterio observable del rubric (item_id = criterio) más una fila
    'overall'. Los criterios no observados (score `None`) NO se registran como
    evidencia: "desconocido" no contamina el mastery. Todas con source='speaking',
    item_type='speaking', difficulty=1. El instrumento de medida es la rúbrica,
    versionada en `assessment_version`."""
    observed = result.get("observed", {c: True for c in SPEAKING_CRITERIA})
    records = []
    for criterion in SPEAKING_CRITERIA:
        score = result["criteria"].get(criterion)
        if score is None or not observed.get(criterion, True):
            continue
        records.append(
            {
                "level_id": level_id,
                "objective_id": objective_id,
                "skill": "speaking",
                "item_id": criterion,
                "item_type": "speaking",
                "difficulty": 1,
                "source": "speaking",
                "result": float(score),
                "curriculum_version": curriculum_version,
                "assessment_version": assessment_version,
            }
        )
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "speaking",
            "item_id": "overall",
            "item_type": "speaking",
            "difficulty": 1,
            "source": "speaking",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
    )
    return records


def _mean_trend(rows: list[dict], window: int = SPEAKING_TREND_WINDOW) -> dict:
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


def speaking_diagnostic(evidence_rows: list[dict]) -> dict:
    """Perfil longitudinal de speaking por criterio del rubric (V1.15).

    `evidence_rows` son las filas de `academy_evidence` con `skill="speaking"`
    (cada fila tiene `item_id` = criterio del rubric y `result` = score 0..1, más
    una fila `item_id="overall"` por intento). Agrupa por criterio y calcula
    `attempts`, `mean`, `min`, `max` y `review_due`; deriva `weak` y
    `recommendation`; y expone el `trend` global sobre las filas `overall` (una
    por intento) como señal longitudinal de la calidad oral.

    Devuelve un dict con `criteria`, `weak`, `recommendation`, `attempts` (nº de
    intentos = nº de filas `overall`), `overall_mean`, `trend` y `rubric_version`.
    Es determinista y no depende de LLM ni red.
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
        results = [r["result"] for r in rows if r.get("result") is not None]
        mean = round(sum(results) / len(results), 3) if results else None
        review_due = attempts == 0 or (
            attempts >= SPEAKING_MIN_ATTEMPTS
            and mean is not None
            and mean < SPEAKING_WEAK_THRESHOLD
        )
        return {
            "criterion": name,
            "attempts": attempts,
            "mean": mean,
            "min": round(min(results), 3) if results else None,
            "max": round(max(results), 3) if results else None,
            "review_due": review_due,
        }

    criteria = [_criterion(c, groups.get(c, [])) for c in SPEAKING_CRITERIA]
    known = set(SPEAKING_CRITERIA)
    for name in sorted(set(groups) - known):
        criteria.append(_criterion(name, groups[name]))

    def _weak_key(name: str) -> tuple:
        entry = next(c for c in criteria if c["criterion"] == name)
        mean = entry["mean"]
        return (mean is None, mean if mean is not None else 0.0)

    weak = [c["criterion"] for c in criteria if c["review_due"]]
    weak.sort(key=_weak_key)

    recommendation = (
        "All speaking criteria look strong."
        if not weak
        else "Focus on: " + ", ".join(weak)
    )

    overall_results = [r["result"] for r in overall_rows if r.get("result") is not None]
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
        "trend": _mean_trend(overall_rows),
        "rubric_version": RUBRIC_VERSION,
    }

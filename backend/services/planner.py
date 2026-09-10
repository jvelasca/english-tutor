"""Planner del repaso léxico: la SIGUIENTE TAREA ÓPTIMA (V3.38).

V3.35-V3.37 construyeron la infraestructura adaptativa: evidencia longitudinal
(`learning_evidence`), dimensiones del evento (apoyo, dificultad, contexto,
latencia, tipo de error), cues graduados y la política de consolidación y
regresión de la escalera de recall. Faltaba USAR esa evidencia para planificar:
responder "¿por qué esta tarea, por qué ahora, con qué apoyo?".

Este módulo puro (sin I/O ni FastAPI) aporta dos cosas:

1. `planned_signals` + `priority_score` — una PUNTUACIÓN de la siguiente tarea
   óptima que combina la urgencia del scheduler (`forgetting`) con el hueco
   pedagógico (`gap`), la debilidad observada (`weakness`), la dependencia de
   apoyo (`support`) y la latencia (`latency`). Los pesos son declarados y
   calibrables; el orden de la cola de repaso pasa a ser una decisión explicable
   en lugar de solo "menor retrievability primero".
2. `evidence_reason` — razones ADITIVAS dirigidas por la evidencia fina que
   V3.36 empezó a registrar y V3.38 sabe leer por modalidad:
   `error_prone` (confusión real, no errata), `skill_gap` (consolidado en una
   modalidad pero sin producción en la otra) y `slow_recall` (aciertos que aún
   no son fluidos). Ninguna sustituye a las razones de hueco de V3.35: solo
   entran cuando el ledger las justifica.

La segmentación por modalidad (`services.evidence.automatic_skills`) alimenta
`skill_gaps`: qué modalidades NO tienen ningún éxito. Es lo que permite decir
"puede recuperarla, pero nunca la ha producido por escrito".

Puro y determinista: recibe el resumen de evidencia y la matriz de competencia
ya calculados. Nunca lanza.
"""

from __future__ import annotations

from services.evidence import (
    LEXICAL_SKILLS,
    automatic_skills,
    is_automatic,
)

# Pesos declarados de la prioridad (suman 1.0). El olvido manda — es la razón de
# que la carta esté vencida —, pero un hueco de producción pesa casi tanto como
# la urgencia: es la diferencia entre "repasar" y "cerrar el hueco".
PRIORITY_WEIGHTS: dict[str, float] = {
    "forgetting": 0.35,
    "gap": 0.30,
    "weakness": 0.20,
    "support": 0.10,
    "latency": 0.05,
}

# Latencia (ms) a partir de la cual un acierto de recall NO es fluido: hay
# recuperación, pero no automaticidad en velocidad. Declarado y calibrable.
SLOW_RECALL_MS = 8000.0

# Techo de normalización de la latencia (ms): por encima, `latency` = 1.0.
LATENCY_CEILING_MS = 20000.0

# Fallos "otra palabra" (NO errata) que exigen volver a practicar el ítem: una
# errata dice que el alumno sabe la palabra; `wrong_word` dice que no.
ERROR_PRONE_MIN_WRONG = 2

# Modalidades de PRODUCCIÓN: su ausencia en el ledger es el hueco que cierra la
# actividad `sentence`.
PRODUCTION_SKILLS: tuple[str, ...] = ("written_production", "spoken_production")

# Actividad del drill que cierra cada razón dirigida por la evidencia.
ACTIVITY_FOR_REASON: dict[str, str] = {
    "error_prone": "recall",
    "skill_gap": "sentence",
    "slow_recall": "recall",
}

# Orden de prioridad de las razones dirigidas por la evidencia (el primero que
# se cumpla gana). Declarado para que el desempate no dependa del diccionario.
EVIDENCE_REASON_ORDER: tuple[str, ...] = (
    "error_prone",
    "skill_gap",
    "slow_recall",
)


def _int(value: object) -> int:
    """Entero no negativo (0 si falta o no es numérico)."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _ratio(part: int, total: int) -> float:
    """`part / total` acotado a [0, 1] (0.0 si no hay total)."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, part / total))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def error_prone(evidence: dict | None) -> bool:
    """¿El ítem acumula confusión real (`wrong_word` repetido)? (V3.38, puro)."""
    if not evidence:
        return False
    errors = evidence.get("error_types")
    if not isinstance(errors, dict):
        return False
    return _int(errors.get("wrong_word")) >= ERROR_PRONE_MIN_WRONG


def _successful_skills(evidence: dict | None) -> list[str]:
    """Modalidades con AL MENOS un éxito en el ledger (orden canónico).

    Vacía si el resumen no trae segmentación (evidencia legacy sin modalidad).
    """
    if not evidence:
        return []
    successes = evidence.get("skill_successes")
    if not isinstance(successes, dict):
        return []
    return [skill for skill in LEXICAL_SKILLS if _int(successes.get(skill))]


def skill_gaps(evidence: dict | None) -> list[str]:
    """Modalidades de PRODUCCIÓN sin ningún éxito, si el ítem ya logra algo.

    Es el hueco que cierra la actividad `sentence`: el ítem tiene evidencia de
    logro en alguna modalidad, pero ninguna de producción (ni escrita ni oral).
    Vacía si no hay ningún éxito (nada que transferir todavía) o si no hay
    segmentación por modalidad.
    """
    achieved = _successful_skills(evidence)
    if not achieved:
        return []
    return [skill for skill in PRODUCTION_SKILLS if skill not in achieved]


def has_production_evidence(evidence: dict | None) -> bool:
    """¿Hay algún éxito en una modalidad de PRODUCCIÓN? (V3.38, puro)."""
    achieved = _successful_skills(evidence)
    return any(skill in achieved for skill in PRODUCTION_SKILLS)


def is_slow_recall(evidence: dict | None) -> bool:
    """¿Hay aciertos pero aún no son fluidos? (V3.38, puro).

    Exige latencia medida Y al menos un éxito: la latencia de un fallo no mide
    fluidez, mide dificultad (señal que ya cubre `weakness`).
    """
    if not evidence:
        return False
    latency = evidence.get("mean_response_time_ms")
    if latency is None:
        return False
    try:
        measured = float(latency)
    except (TypeError, ValueError):
        return False
    return measured >= SLOW_RECALL_MS and _int(evidence.get("successes")) > 0


def evidence_reason(matrix: dict | None, evidence: dict | None) -> str:
    """Razón dirigida por la evidencia fina, o "" (V3.38, puro).

    Solo mira señales que registran eventos concretos (errores, modalidades,
    latencia). Un resumen vacío o legacy devuelve "": las razones de hueco de
    V3.35 siguen siendo la decisión por defecto.
    """
    matrix = matrix or {}
    checks = {
        "error_prone": lambda: error_prone(evidence),
        "skill_gap": lambda: bool(
            matrix.get("production")
            and skill_gaps(evidence)
            and len(skill_gaps(evidence)) == len(PRODUCTION_SKILLS)
        ),
        "slow_recall": lambda: is_slow_recall(evidence),
    }
    for reason in EVIDENCE_REASON_ORDER:
        try:
            if checks[reason]():
                return reason
        except Exception:  # noqa: BLE001 — el planner nunca rompe la cola
            continue
    return ""


def planned_signals(
    evidence: dict | None,
    matrix: dict | None,
    *,
    retrievability: float | None = None,
) -> dict:
    """Señales deterministas de la siguiente tarea óptima (V3.38, puro).

    - `forgetting` — 1 - `retrievability` (0.0 si el scheduler no la conoce):
      cuánto se ha olvidado desde el último repaso;
    - `gap` — 1.0 si falta la producción (`production_gap`), 0.5 si falta
      transferencia (`transfer_gap`), 0.0 sin hueco declarado;
    - `weakness` — 1 - `success_rate` (0.0 sin intentos);
    - `support` — proporción de éxitos que NO fueron independientes (0.0 sin
      éxitos): un ítem que solo acierta con apoyo depende de él;
    - `latency` — latencia media normalizada por `LATENCY_CEILING_MS`.
    """
    ev = evidence or {}
    mx = matrix or {}
    try:
        forgetting = (
            1.0 - _clamp(float(retrievability)) if retrievability is not None else 0.0
        )
    except (TypeError, ValueError):
        forgetting = 0.0
    if mx.get("production_gap"):
        gap = 1.0
    elif mx.get("transfer_gap"):
        gap = 0.5
    else:
        gap = 0.0
    attempts = _int(ev.get("attempts"))
    successes = _int(ev.get("successes"))
    independent = _int(ev.get("independent_successes"))
    weakness = 0.0
    if attempts:
        rate = ev.get("success_rate")
        try:
            weakness = 1.0 - _clamp(float(rate))
        except (TypeError, ValueError):
            weakness = 1.0 - _ratio(successes, attempts)
    latency = 0.0
    if ev.get("mean_response_time_ms") is not None:
        try:
            latency = _clamp(float(ev["mean_response_time_ms"]) / LATENCY_CEILING_MS)
        except (TypeError, ValueError):
            latency = 0.0
    # Sin éxitos no hay dependencia de apoyo que medir (0.0, no 1.0).
    support = 1.0 - _ratio(independent, successes) if successes > 0 else 0.0
    return {
        "forgetting": round(_clamp(forgetting), 4),
        "gap": round(gap, 4),
        "weakness": round(_clamp(weakness), 4),
        "support": round(_clamp(support), 4),
        "latency": round(latency, 4),
        "automatic": is_automatic(ev),
        "automatic_skills": automatic_skills(ev),
        "skill_gaps": skill_gaps(ev),
        "error_prone": error_prone(ev),
        "slow_recall": is_slow_recall(ev),
    }


def priority_score(signals: dict) -> float:
    """Prioridad 0..1 de la siguiente tarea (V3.38, puro).

    Suma ponderada de `PRIORITY_WEIGHTS`. Un diccionario incompleto cuenta 0 en
    las señales que falten: nunca lanza.
    """
    total = 0.0
    for key, weight in PRIORITY_WEIGHTS.items():
        try:
            total += weight * _clamp(float(signals.get(key, 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
    return round(_clamp(total), 4)


def explain_priority(signals: dict, reason: str = "") -> str:
    """Explicación legible (inglés) de por qué esta tarea es la siguiente.

    Mismo registro que `services.adaptive.explain_priority`: frases cortas
    separadas por `; `, deterministas y en inglés (el contrato `why` del
    proyecto). Nunca lanza.
    """
    parts: list[str] = []
    if reason == "weak_recognition":
        parts.append("no receptive base yet")
    if reason == "no_recall_evidence":
        parts.append("recognition without recall evidence")
    if reason == "production_gap":
        parts.append("recognized but never produced")
    if reason == "error_prone":
        parts.append("repeated wrong-word errors")
    if reason == "skill_gap":
        gaps = signals.get("skill_gaps") or []
        if gaps:
            parts.append(f"no success yet in {', '.join(gaps)}")
        else:
            parts.append("production modality still missing")
    if reason == "slow_recall":
        parts.append("correct but not yet fluent")
    if reason == "automatic_maintenance":
        parts.append("automatic: spaced independent success")
    try:
        forgetting = float(signals.get("forgetting") or 0.0)
    except (TypeError, ValueError):
        forgetting = 0.0
    if forgetting >= 0.5:
        parts.append("due for review (memory decayed)")
    if signals.get("support"):
        try:
            if float(signals["support"]) >= 0.5:
                parts.append("successes still depend on support")
        except (TypeError, ValueError):
            pass
    if not parts:
        parts.append("scheduled maintenance")
    return "; ".join(parts)

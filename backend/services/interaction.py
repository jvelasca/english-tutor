"""Evidencia objetiva de interacción (InteractionEvidence 2.0, señal objetiva).

Este módulo deriva, de forma determinista y sin I/O, sub-dimensiones de
interacción a partir de la telemetría de turnos de una conversación. La señal es
OBJETIVA (recuento/balance de turnos, latencia de respuesta, duración de turno,
interrupciones), no una estimación semántica del LLM. Una sub-dimensión no
observable (sin datos) devuelve `None`, de modo que el scorer determinista no la
"inventa" (score=None, observed=False) y "desconocido" no se confunde con "50%".

Mantiene la función pura y muy testeable: no lee BD, no llama a red y no usa el
reloj de pared.
"""
from __future__ import annotations

# --- Umbrales (constantes con nombre) --------------------------------------

# Duración media del turno del alumno mapeada a [0,1] (turn_duration). Por debajo
# de `TURN_DURATION_MIN_MS` el turno es demasiado corto (0.0); a partir de
# `TURN_DURATION_FULL_MS` la duración se considera plena (meseta en 1.0). Entre
# medias, rampa lineal. Es DURACIÓN, no completitud (la completitud real del turno
# es semántica y la estima el LLM).
TURN_DURATION_MIN_MS = 500
TURN_DURATION_FULL_MS = 4000

# Latencia de respuesta del alumno por debajo de este umbral se considera una
# posible interrupción (el alumno entra antes de que el tutor termine su turno).
INTERRUPTION_LATENCY_MS = 300

# Rango de proporción de turnos del alumno considerado "equilibrado" (meseta):
# dentro de [0.30, 0.70] la interacción es plena (1.0), no solo en el 50/50.
TURN_BALANCE_IDEAL_LOW = 0.3
TURN_BALANCE_IDEAL_HIGH = 0.7

# Roles tratados como turno del alumno (cualquier otro rol cuenta como assistant).
_STUDENT_ROLES = frozenset({"student", "user"})


def _num(value) -> float | None:
    """Normaliza un valor numérico (rechazando bool) o devuelve None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _is_student(role: str) -> bool:
    return (role or "").lower() in _STUDENT_ROLES


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _turn_balance_score(student_turns: int, assistant_turns: int) -> float:
    """Balance de turnos en [0,1]: 1.0 dentro de la meseta [30%, 70%] del alumno.

    Un intercambio no tiene por qué ser 50/50 para ser equilibrado: con entre el
    30% y el 70% de turnos del alumno la interacción es plena (1.0). Por debajo
    del 30% (el tutor domina) o por encima del 70% (el alumno monopoliza), el
    score baja linealmente hasta 0.0.
    """
    total = student_turns + assistant_turns
    proportion = student_turns / total
    if TURN_BALANCE_IDEAL_LOW <= proportion <= TURN_BALANCE_IDEAL_HIGH:
        return 1.0
    if proportion < TURN_BALANCE_IDEAL_LOW:
        return round(_clamp(proportion / TURN_BALANCE_IDEAL_LOW), 3)
    return round(_clamp((1.0 - proportion) / (1.0 - TURN_BALANCE_IDEAL_HIGH)), 3)


def _turn_duration_score(avg_duration_ms: float) -> float:
    """Duración media del turno del alumno mapeada a [0,1] con umbrales.

    Es una señal de DURACIÓN (no de completitud): 500ms → 0.0, 4000ms → 1.0, rampa
    lineal entre medias. La completitud real del turno es semántica (la da el LLM).
    """
    if avg_duration_ms <= TURN_DURATION_MIN_MS:
        return 0.0
    if avg_duration_ms >= TURN_DURATION_FULL_MS:
        return 1.0
    span = TURN_DURATION_FULL_MS - TURN_DURATION_MIN_MS
    return round((avg_duration_ms - TURN_DURATION_MIN_MS) / span, 3)


def interaction_evidence(turns: list[dict]) -> dict:
    """Sub-dimensiones objetivas de interacción a partir de la telemetría de turnos.

    Cada turno es un dict con `role` ("student"/"assistant"), `duration_ms`
    (int|None), `latency_ms` (int|None, tiempo antes de empezar a responder) y
    opcionalmente `created_at`. Devuelve:
    - `turn_balance`: balance de turnos en [0,1] (None sin intercambio real).
    - `avg_response_latency_ms`: latencia media de respuesta en ms (None sin datos).
    - `turn_duration`: duración media del turno del alumno en [0,1] (None sin datos).
    - `student_turns` / `assistant_turns`: recuento de turnos.
    - `interruptions`: recuento de interrupciones (None sin datos de latencia).
    """
    student_durations: list[float] = []
    all_latencies: list[float] = []
    student_turns = 0
    assistant_turns = 0
    interruptions = 0
    student_latency_observed = False

    for turn in turns or []:
        role = turn.get("role")
        duration = _num(turn.get("duration_ms"))
        latency = _num(turn.get("latency_ms"))
        if latency is not None:
            all_latencies.append(latency)
        if _is_student(role):
            student_turns += 1
            if duration is not None:
                student_durations.append(duration)
            if latency is not None:
                student_latency_observed = True
                if latency < INTERRUPTION_LATENCY_MS:
                    interruptions += 1
        else:
            assistant_turns += 1

    has_exchange = student_turns > 0 and assistant_turns > 0

    turn_balance = (
        _turn_balance_score(student_turns, assistant_turns) if has_exchange else None
    )

    avg_response_latency_ms = (
        int(round(sum(all_latencies) / len(all_latencies))) if all_latencies else None
    )

    turn_duration = None
    if student_durations:
        avg_duration = sum(student_durations) / len(student_durations)
        turn_duration = _turn_duration_score(avg_duration)

    interruptions_result = interruptions if student_latency_observed else None

    return {
        "turn_balance": turn_balance,
        "avg_response_latency_ms": avg_response_latency_ms,
        "turn_duration": turn_duration,
        "student_turns": student_turns,
        "assistant_turns": assistant_turns,
        "interruptions": interruptions_result,
    }

"""Política de repaso de frases de listening falladas (V3.89, Listening robusto).

Módulo **puro** (sin BD y sin FastAPI): decide dos cosas que hasta V3.89 vivían
implícitas en el frontend y que ahora son contrato verificable del backend.

1. **El desenlace pedagógico de un intento** (`outcome_for`). Un `correct: true`
   no distingue acertar a la primera de acertar tras un reintento, y esa
   diferencia es evidencia: la primera es dominio, la segunda es dominio con
   ayuda. Los desenlaces se persisten en `listening_attempts.outcome`.

2. **Cuándo y con qué prioridad se reabre una frase fallada** (`schedule`). Un
   fallo de comprensión auditiva NO es una flashcard: por eso esta cola es
   independiente de FSRS. La frase vuelve más tarde (repetición espaciada
   propia) y la prioridad ordena la cola por dificultad real.

**Principio de diseño (el corazón de V3.89):** el fallo es **evidencia**, no una
barrera de navegación. Nada de aquí puede impedir que la sesión avance; el
tope `IMMEDIATE_RETRY_LIMIT` es lo único que se interpone, y es un tope, no un
bucle: como máximo **una** repetición inmediata por ítem.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Máximo de repeticiones inmediatas de la MISMA frase antes de continuar. Es un
# tope duro: el bucle "hasta acertar" es exactamente lo que esta release elimina.
IMMEDIATE_RETRY_LIMIT = 1

# Desenlaces posibles de un intento (columna `listening_attempts.outcome`).
OUTCOME_CORRECT_FIRST = "correct_first"
OUTCOME_CORRECT_RETRY = "correct_retry"
OUTCOME_WRONG = "wrong"
OUTCOME_HINT_USED = "hint_used"
OUTCOME_SOLUTION_SHOWN = "solution_shown"

OUTCOMES: tuple[str, ...] = (
    OUTCOME_CORRECT_FIRST,
    OUTCOME_CORRECT_RETRY,
    OUTCOME_WRONG,
    OUTCOME_HINT_USED,
    OUTCOME_SOLUTION_SHOWN,
)

# Intervalos de reapertura por número de fallo (horas). Escalonados y acotados:
# el primer fallo vuelve al día siguiente, el cuarto (y siguientes) a las dos
# semanas. Nunca "veinte veces seguidas": eso es lo que se elimina.
_REVIEW_INTERVAL_HOURS: tuple[int, ...] = (24, 72, 168, 336)

# Peso pedagógico por sub-destreza: una frase de inferencia o de discurso
# conectado merece más prioridad de repaso que una de reconocimiento de palabra
# aislada. Es la única señal de contenido que entra en la prioridad; no depende
# de datos de usuario.
_SKILL_WEIGHT: dict[str, float] = {
    "inference": 3.0,
    "connected_speech": 3.0,
    "gist": 2.0,
    "detail": 2.0,
    "recognition": 1.0,
}
_DEFAULT_SKILL_WEIGHT = 1.5

# Ventana de «fallo reciente»: dentro de ella la prioridad recibe un extra. Un
# fallo de hoy debe adelantar a otro de hace un mes con el mismo `fail_count`.
RECENT_WINDOW_HOURS = 24
RECENT_BONUS = 2.0


def now_iso() -> str:
    """Marca temporal ISO-8601 en UTC, con el mismo formato que la BD.

    Se centraliza aquí para que `next_review_at` y las comparaciones de la cola
    hablen el mismo idioma que `repositories.db._now()` (mismo offset `+00:00`,
    de modo que el orden lexicográfico coincide con el cronológico).
    """
    return datetime.now(timezone.utc).isoformat()


def outcome_for(
    correct: bool,
    attempt_number: int = 1,
    *,
    hint_used: bool = False,
    solution_shown: bool = False,
) -> str:
    """Clasifica el desenlace pedagógico de un intento.

    `attempt_number` es 1 para el primer intento y 2 para el que llega tras la
    repetición inmediata (el cliente lo declara desde su micro-flujo; el backend
    lo acota a `>= 1`). Un acierto a la primera es dominio; a la segunda, dominio
    con ayuda. Un fallo con pista o con solución mostrada es un fallo ASISTIDO,
    que es información distinta de un fallo limpio.

    Es puro y total: cualquier combinación devuelve uno de `OUTCOMES`.
    """
    attempt = max(1, int(attempt_number))
    if correct:
        return OUTCOME_CORRECT_RETRY if attempt > 1 else OUTCOME_CORRECT_FIRST
    if solution_shown:
        return OUTCOME_SOLUTION_SHOWN
    if hint_used:
        return OUTCOME_HINT_USED
    return OUTCOME_WRONG


def review_interval_hours(fail_count: int) -> int:
    """Horas hasta la próxima reapertura según el número de fallo acumulado."""
    index = max(1, int(fail_count)) - 1
    if index >= len(_REVIEW_INTERVAL_HOURS):
        return _REVIEW_INTERVAL_HOURS[-1]
    return _REVIEW_INTERVAL_HOURS[index]


def next_review_at(fail_count: int, now: datetime | None = None) -> str:
    """Marca ISO en la que la frase vuelve a la cola (espaciado propio de la cola).

    No es FSRS: es una política simple, determinista y explicable, adecuada a un
    objeto distinto (una frase que no se entendió al oírla).
    """
    base = now or datetime.now(timezone.utc)
    return (base + timedelta(hours=review_interval_hours(fail_count))).isoformat()


def priority(
    fail_count: int,
    last_failed_at: str,
    skill: str = "",
    now: datetime | None = None,
) -> float:
    """Prioridad de repaso (mayor = más urgente). Determinista y explicable.

    Combina lo que pidió el análisis: número de fallos, recencia y peso
    pedagógico de la sub-destreza. No incluye el orden de llegada como término
    aleatorio, así que dos frases con la misma evidencia y el mismo skill
    empatan; el desempate (más antigua primero) lo hace la consulta SQL.
    """
    base = now or datetime.now(timezone.utc)
    peso_skill = _SKILL_WEIGHT.get(skill or "", _DEFAULT_SKILL_WEIGHT)
    score = 3.0 * max(1, int(fail_count)) + peso_skill
    moment = _parse_iso(last_failed_at)
    if moment is not None:
        age_hours = (base - moment).total_seconds() / 3600.0
        if age_hours <= RECENT_WINDOW_HOURS:
            score += RECENT_BONUS
    return round(score, 4)


def _parse_iso(value: str) -> datetime | None:
    """Parsea una marca ISO de la BD; None si está vacía o es ilegible.

    Tolerante a propósito: una fecha corrupta no puede tumbar la prioridad de
    toda la cola. Sin fecha, la entrada simplemente pierde el extra de recencia.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def schedule(
    fail_count: int,
    *,
    skill: str = "",
    now: datetime | None = None,
) -> dict:
    """Plan de reapertura de una frase recién fallada.

    Devuelve `{fail_count, next_review_at, priority}` listo para persistir. Se
    ofrece como una sola función para que el repositorio no componga la política
    a mano y haya un único sitio que la define.
    """
    moment = now or datetime.now(timezone.utc)
    stamp = moment.isoformat()
    return {
        "fail_count": max(1, int(fail_count)),
        "next_review_at": next_review_at(fail_count, moment),
        "priority": priority(fail_count, stamp, skill, moment),
    }


def can_retry_immediately(attempts_so_far: int) -> bool:
    """¿Queda repetición inmediata para este ítem? (`attempts_so_far` >= 1).

    Con `IMMEDIATE_RETRY_LIMIT = 1`, solo el primer fallo habilita una repetición;
    a partir de ahí la frase va a la cola y la sesión continúa.
    """
    return max(1, int(attempts_so_far)) <= IMMEDIATE_RETRY_LIMIT

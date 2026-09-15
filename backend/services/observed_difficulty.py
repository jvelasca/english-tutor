"""Observed Task Difficulty 2.0 — la capa EMPÍRICA de la dificultad (V3.63).

Hasta V3.62 el proyecto declaraba TRES dificultades y ninguna era empírica
(V3.55): `declared` (lo que declara el ítem o la actividad), `served` (lo que la
tarea sirvió) y `observed_task_difficulty` (lo ACREDITADO, que es lo servido
DESCONTADO por el andamiaje). Las tres son HECHOS de la tarea; ninguna mira el
RESULTADO.

V3.63 (P2-20 de la auditoría de V3.62) añade la cuarta pata, la que cierra el
ciclo declarado → servido → experimentado → demostrado:

    served_ceiling(rows)     techo SERVIDO por dimensión (lo que se pidió).
    credited_ceiling(rows)   techo ACREDITADO (lo que se logró); su distancia al
                             servido es la DEPENDENCIA DE ANDAMIAJE.
    experienced_load(row)    carga servida MODULADA por el coste OBSERVADO
                             (latencia, error, repeticiones, apoyo).
    observed_task_difficulty_2(rows)
                             la medida empírica agregada, con la MISMA puerta
                             espaciada de V3.54 (`OBSERVED_MIN_SAMPLES`/
                             `OBSERVED_MIN_DAYS`): sin muestra espaciada NO se
                             declara nada.

Fronteras declaradas (lo que este módulo NO hace):

- **No ajusta parámetros.** Todas las modulaciones son TABLAS DECLARADAS y
  monótonas (`LATENCY_STEP`, `ERROR_TYPE_STEP`, `REPLAY_STEP`, `SUPPORT_STEP`);
  nada se estima a partir de los datos.
- **No inventa hechos.** Un coste desconocido NO modula (la carga experimentada
  es la servida). No hay imputación ni valores por defecto "razonables".
- **No lee el reloj, ni aleatoriedad, ni I/O.** Es una función pura de sus
  argumentos, determinista byte a byte.
- **No acredita por su cuenta.** La puerta espaciada se REUTILIZA de
  `learner_skill`; este módulo no introduce ningún umbral nuevo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from services import difficulty, task_semantics
from services.learner_skill import OBSERVED_MIN_DAYS, OBSERVED_MIN_SAMPLES
from services.planner import LATENCY_CEILING_MS, SLOW_RECALL_MS

# Rango declarado de carga por dimensión (el mismo de `difficulty`).
LOAD_MIN = 1
LOAD_MAX = 5

# Ventana de RECENCIA (V3.67): nº de INTENTOS más recientes que describen la
# tasa `recent_rate`. Es descriptiva (sin ML ni suavizado): solo la tasa cruda de
# la cola reciente, para que el informe de calibración distinga lo reciente de lo
# histórico sin inventar una tendencia.
RECENT_ATTEMPTS = 5

# Separador canónico de la firma de tarea (`task_signature`): detalle de FORMATO,
# no de identidad. Nunca se expone como contrato.
_TASK_SIGNATURE_SEPARATOR = "|"

# Tabla DECLARADA y MONÓTONA: pasos que la latencia observada suma a la carga
# servida. Se reutilizan las constantes declaradas del planner (no se inventan
# números nuevos) y se recorre de mayor a menor, quedándose con el primer tramo.
LATENCY_STEP: tuple[tuple[float, int], ...] = (
    (LATENCY_CEILING_MS, 2),
    (SLOW_RECALL_MS, 1),
)
# Un error declarado en el evento suma un paso: recuperar con error cuesta más.
ERROR_TYPE_STEP = 1
# Repetir el audio por encima de este número de veces declaradas suma un paso.
REPLAY_MIN = 2
REPLAY_STEP = 1
# El APOYO declarado (transcripción visible, audio ralentizado) RESTA un paso: la
# tarea fue más fácil de lo servido, y eso se declara, no se supone.
SUPPORT_STEP = -1
SLOW_SPEED_VALUES: tuple[str, ...] = ("slow", "slower", "x-slow")


def _truthy(value: object) -> bool:
    """Interpretación booleana tolerante (nunca lanza)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def _number(value: object) -> float | None:
    """Número finito o None (rechaza bool y basura; nunca lanza)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _clamp(load: int) -> int:
    return max(LOAD_MIN, min(LOAD_MAX, load))


def _facts(row: Mapping) -> Mapping:
    facts = row.get("facts")
    return facts if isinstance(facts, Mapping) else {}


def _day(row: Mapping) -> str:
    return str(row.get("occurred_on") or "")[:10]


def _served_vector(row: Mapping) -> dict[str, int]:
    """Vector SERVIDO de la fila (hecho declarado; `{}` si no lo declara)."""
    declared = _facts(row).get("served_load")
    if isinstance(declared, Mapping) and declared:
        return difficulty.normalize_vector(declared)
    return {}


def _credited_vector(row: Mapping) -> dict[str, int]:
    """Vector ACREDITADO de la fila (lo que la fila aporta al estado)."""
    return difficulty.normalize_vector(row.get("dimensions"))


def _ceiling(vectors: Sequence[Mapping]) -> dict[str, int]:
    """Máximo por dimensión de varios vectores (orden canónico, nunca lanza)."""
    ceiling: dict[str, int] = {}
    for vector in vectors:
        if not isinstance(vector, Mapping):
            continue
        for dimension, load in vector.items():
            value = _number(load)
            if value is None:
                continue
            current = ceiling.get(str(dimension), 0)
            if int(value) > current:
                ceiling[str(dimension)] = int(value)
    return {
        dimension: ceiling[dimension]
        for dimension in difficulty.DIFFICULTY_DIMENSIONS
        if dimension in ceiling
    }


def served_ceiling(rows: Sequence[Mapping]) -> dict[str, int]:
    """Techo SERVIDO por dimensión: la carga más alta que se pidió (pura).

    Solo mira HECHOS declarados por el evento (`facts.served_load`); una fuente
    que no declare lo servido (academy, listening, pronunciación) no aporta, y eso
    es correcto: no se inventa una carga que nadie declaró. Nunca lanza.
    """
    return _ceiling(
        [_served_vector(row) for row in rows if isinstance(row, Mapping)]
    )


def credited_ceiling(rows: Sequence[Mapping]) -> dict[str, int]:
    """Techo ACREDITADO por dimensión: la carga más alta que se LOGRO (pura).

    Es la MISMA lectura que alimenta el estado (`row.dimensions`), así que la
    distancia entre `served_ceiling` y `credited_ceiling` es exactamente la
    dependencia de ANDAMIAJE de la evidencia. Nunca lanza.
    """
    return _ceiling(
        [_credited_vector(row) for row in rows if isinstance(row, Mapping)]
    )


def scaffolding_gap(rows: Sequence[Mapping]) -> dict[str, int]:
    """Distancia servido − acreditado por dimensión (pura, solo positivos)."""
    served = served_ceiling(rows)
    credited = credited_ceiling(rows)
    return {
        dimension: load - credited.get(dimension, 0)
        for dimension, load in served.items()
        if load - credited.get(dimension, 0) > 0
    }


def experienced_load(row: Mapping) -> dict[str, int]:
    """Carga EXPERIMENTADA por dimensión: la servida modulada por el coste (pura).

    El coste es OBSERVADO y ya declarado por el evento (`response_time_ms`,
    `error_type`, `replay_count`, `speed_used`, `transcript_used`). Cada hecho
    conocido modula con la tabla declarada; los DESCONOCIDOS no modulan (la carga
    experimentada es la servida). El resultado se recorta al rango 1..5. Nunca
    lanza.
    """
    base = _served_vector(row) or _credited_vector(row)
    if not base:
        return {}
    facts = _facts(row)
    steps = 0
    latency = _number(facts.get("response_time_ms"))
    if latency is not None:
        for threshold, step in LATENCY_STEP:
            if latency >= threshold:
                steps += step
                break
    if str(facts.get("error_type") or "").strip():
        steps += ERROR_TYPE_STEP
    replays = _number(facts.get("replay_count"))
    if replays is not None and replays >= REPLAY_MIN:
        steps += REPLAY_STEP
    if _truthy(facts.get("transcript_used")):
        steps += SUPPORT_STEP
    if str(facts.get("speed_used") or "").strip().lower() in SLOW_SPEED_VALUES:
        steps += SUPPORT_STEP
    return {dimension: _clamp(load + steps) for dimension, load in base.items()}


def observed_task_difficulty_2(rows: Sequence[Mapping]) -> dict:
    """Capa EMPÍRICA agregada de la dificultad (pura; nunca lanza).

    Devuelve `{served_ceiling, credited_ceiling, experienced_load, success_rate,
    samples, days}`. Sin la muestra ESPACIADA de V3.54 (2 éxitos en 2 días
    naturales distintos) NO declara ninguna medida: los tres techos quedan vacíos
    y solo se informan `samples`/`days`/`success_rate`. No hay reloj: los días
    son los que declara la fuente.
    """
    clean = [row for row in rows if isinstance(row, Mapping)]
    successes = [row for row in clean if _truthy(row.get("success"))]
    days = {_day(row) for row in successes if _day(row)}
    declared = (
        len(successes) >= OBSERVED_MIN_SAMPLES and len(days) >= OBSERVED_MIN_DAYS
    )
    result = {
        "served_ceiling": {},
        "credited_ceiling": {},
        "experienced_load": {},
        "success_rate": (
            round(len(successes) / len(clean), 3) if clean else 0.0
        ),
        "samples": len(successes),
        "days": len(days),
    }
    if not declared:
        return result
    result["served_ceiling"] = served_ceiling(clean)
    result["credited_ceiling"] = credited_ceiling(successes)
    result["experienced_load"] = _ceiling(
        [experienced_load(row) for row in successes]
    )
    return result


def empirical_success(rows: Sequence[Mapping], *, now: str = "") -> dict[str, dict]:
    """Estimación EMPÍRICA de `P(éxito | alumno, tarea)` por CLAVE DE TAREA (V3.65).

    Agrupa las filas canónicas por clave de tarea
    `(target_id, actividad, dificultad servida declarada)` y devuelve por clave
    `{successes, attempts, p_success, days}`. Reutiliza la MISMA puerta espaciada
    de V3.54 (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`): sin muestra espaciada
    la clave NO aparece (no se declara estimación). El `p_success` es la tasa
    empírica CRUDA acotada a [0, 1]: sin umbrales nuevos.

    Sin reloj: `now` se acepta por contrato pero no se usa — los días son los que
    declaran las filas (`occurred_on`). Pura y determinista, byte a byte; nunca
    lanza.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        target = str(row.get("target_id") or "").strip()
        activity = str(row.get("activity_id") or "").strip()
        served = difficulty.format_vector(_served_vector(row))
        grouped.setdefault(f"{target}|{activity}|{served}", []).append(dict(row))
    result: dict[str, dict] = {}
    for key, group in grouped.items():
        successes = [row for row in group if _truthy(row.get("success"))]
        days = {_day(row) for row in successes if _day(row)}
        if len(successes) < OBSERVED_MIN_SAMPLES or len(days) < OBSERVED_MIN_DAYS:
            continue
        attempts = len(group)
        result[key] = {
            "successes": len(successes),
            "attempts": attempts,
            "p_success": round(len(successes) / attempts, 3),
            "days": len(days),
        }
    return result


def task_signature_parts(
    target_id: object,
    activity: object,
    support_level: object,
    served_difficulty: object,
    context: object = "",
    assessed_skill: object = "",
) -> str:
    """Firma canónica de TAREA (V3.67, pura): identidad completa de la tarea.

    Cierra el P1-01 de la auditoría de V3.66: `target_id` no es una identidad de
    tarea completa (el MISMO ítem con distinta actividad, apoyo o carga servida es
    OTRA tarea). La firma combina los SEIS componentes que distinguen una tarea de
    otra:

        (target_id, activity, support_level, served_difficulty, context,
         assessed_skill)

    Cada componente se normaliza (`""` cuando falta o no se declara): la clave es
    estable, determinista byte a byte y nunca lanza. `served_difficulty` se
    serializa con `difficulty.format_vector` (mismo formato canónico del ledger).
    """
    target = str(target_id or "").strip()
    act = str(activity or "").strip().lower()
    support = str(support_level or "").strip().lower()
    served = difficulty.format_vector(served_difficulty)
    ctx = str(context or "").strip()
    assessed = str(assessed_skill or "").strip().lower()
    return _TASK_SIGNATURE_SEPARATOR.join(
        (target, act, support, served, ctx, assessed)
    )


def task_signature(row: Mapping) -> str:
    """Firma canónica de una FILA del estado (V3.67, pura).

    Lee los hechos YA proyectados por `skill_state._lexicon_rows`
    (`facts.activity`, `facts.support_level`, `facts.served_load` y
    `facts.context_instance`/`facts.context_id`) y la modalidad evaluada.
    La skill evaluada se deriva de la ACTIVIDAD (`task_semantics.assessed_skill_for`),
    NO del `modality` canónico del estado (que habla otro vocabulario:
    `vocabulary`/`writing`/`speaking`): así la firma del ledger y la del candidato
    (`services.lexicon`) usan el MISMO idioma y la búsqueda empírica por firma
    puede CASAR. Nunca lanza; una fila no-Mapping devuelve `""`.
    """
    if not isinstance(row, Mapping):
        return ""
    facts = _facts(row)
    return task_signature_parts(
        target_id=row.get("target_id"),
        activity=facts.get("activity"),
        support_level=facts.get("support_level"),
        served_difficulty=facts.get("served_load"),
        context=facts.get("context_instance") or facts.get("context_id"),
        assessed_skill=task_semantics.assessed_skill_for(facts.get("activity")),
    )


def _empirical_entry(rows: Sequence[Mapping]) -> dict | None:
    """Estimación EMPÍRICA de un grupo de intentos (pura; `None` sin muestra).

    Devuelve `{successes, attempts, p_success, p_success_observed, raw_rate,
    recent_rate, long_term_rate, days}` o `None` si el grupo no cruza la puerta
    espaciada de V3.54 (`OBSERVED_MIN_SAMPLES` éxitos en `OBSERVED_MIN_DAYS` días
    naturales distintos).

    V3.67 (honestidad estadística, P2-06/07):
    - `p_success_observed` es el nombre honesto de la tasa observada;
    - `p_success` se CONSERVA como alias retrocompatible de V3.66 (retirada cuando
      exista una capa calibrada que reclame ese nombre);
    - `raw_rate` = `long_term_rate` = tasa global cruda del grupo;
    - `recent_rate` = tasa de los últimos `RECENT_ATTEMPTS` intentos (descriptiva).

    Sin ML ni suavizado: todas son tasas CRUDAS. Nunca lanza.
    """
    ordered = sorted(
        (row for row in rows if isinstance(row, Mapping)),
        key=lambda r: (
            str(r.get("occurred_at") or ""),
            str(r.get("id") or r.get("evidence_id") or ""),
        ),
    )
    if not ordered:
        return None
    successes = [row for row in ordered if _truthy(row.get("success"))]
    days = {_day(row) for row in successes if _day(row)}
    if len(successes) < OBSERVED_MIN_SAMPLES or len(days) < OBSERVED_MIN_DAYS:
        return None
    attempts = len(ordered)
    rate = round(len(successes) / attempts, 3)
    recent = ordered[-RECENT_ATTEMPTS:]
    recent_successes = [row for row in recent if _truthy(row.get("success"))]
    return {
        "successes": len(successes),
        "attempts": attempts,
        "p_success": rate,
        "p_success_observed": rate,
        "raw_rate": rate,
        "recent_rate": round(len(recent_successes) / len(recent), 3),
        "long_term_rate": rate,
        "days": len(days),
    }


def empirical_success_by_target(
    rows: Sequence[Mapping], *, now: str = ""
) -> dict[str, dict]:
    """Estimación EMPÍRICA por ITEM (`target_id`) (V3.66 → V3.67, Nivel A).

    Agrupa SOLO por `target_id` (el ítem), sin colapsar por actividad ni
    dificultad servida: es la granularidad `P(éxito | alumno, target)` (Nivel A =
    target empirical de la jerarquía V3.67). Reutiliza la MISMA puerta espaciada de
    V3.54 y devuelve por ítem el payload de `_empirical_entry` (con
    `p_success_observed`, `raw_rate`, `recent_rate`, `long_term_rate`). Sin muestra
    espaciada el ítem NO aparece (no se declara estimación). Un ítem sin
    `target_id` (fuente que no declara identidad) no aporta clave: no se inventa.

    Sin reloj: `now` se acepta por contrato pero no se usa — los días son los que
    declaran las filas (`occurred_on`). Pura y determinista, byte a byte; nunca
    lanza.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        target = str(row.get("target_id") or "").strip()
        if not target:
            continue
        grouped.setdefault(target, []).append(dict(row))
    result: dict[str, dict] = {}
    for target, group in grouped.items():
        entry = _empirical_entry(group)
        if entry is not None:
            result[target] = entry
    return result


def empirical_success_by_task(
    rows: Sequence[Mapping], *, now: str = ""
) -> dict[str, dict]:
    """Estimación EMPÍRICA por TAREA (`task_signature`) (V3.67, P1-01).

    La granularidad que V3.66 buscaba y no alcanzó: agrupa por la FIRMA canónica de
    tarea (`task_signature`), de modo que el MISMO `target_id` con distinta
    actividad, apoyo o carga servida produce una estimación DISTINTA. Es el Nivel
    `task_empirical` de la jerarquía de resolución `task → target → skill →
    margin`. Reutiliza la MISMA puerta espaciada de V3.54; sin muestra espaciada la
    firma NO aparece. Una fila sin identidad de tarea (firma vacía) no aporta
    clave.

    Sin reloj: `now` se acepta por contrato pero no se usa. Pura y determinista,
    byte a byte; nunca lanza.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = task_signature(row)
        if not key.strip(_TASK_SIGNATURE_SEPARATOR):
            continue
        grouped.setdefault(key, []).append(dict(row))
    result: dict[str, dict] = {}
    for key, group in grouped.items():
        entry = _empirical_entry(group)
        if entry is not None:
            result[key] = entry
    return result

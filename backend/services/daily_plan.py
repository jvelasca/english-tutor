"""Plan diario (V3.90): presupuesto por tiempo/unidades, política repaso-antes-que-nuevo
y métricas honestas del día.

Módulo **puro**: recibe números y filas ya leídas y devuelve números. No toca la
BD, no lee el reloj y no sabe nada de FastAPI, así que su comportamiento se fija
con tests sin `monkeypatch`.

**Qué declara el objetivo del día.** En modo `time` manda `minutes_per_day` (lo de
siempre); en modo `units` manda `target_units` traducido a minutos con
`MINUTES_PER_UNIT`; en modo `mixed` el objetivo son las dos cosas y se pide el
mayor de los dos presupuestos, porque el día se da por cumplido solo si se cumplen
**ambos**.

**Qué es un "minuto" aquí.** Una estimación del Session Engine (los minutos que el
plan asignaba a la unidad cuando se completó), **no** tiempo de reloj: la app no
tiene cronómetro y este módulo no lo finge.
"""
from __future__ import annotations

# --- Constantes declaradas (las cotas son las del esquema `LearningGoalIn`) ---

PLAN_MODES = ("time", "units", "mixed")  # modos del objetivo del día
DEFAULT_PLAN_MODE = "time"
DEFAULT_TARGET_UNITS = 0
DEFAULT_MAX_NEW = 1

# Coste nominal de UNA unidad de trabajo del plan. Es una convención del motor
# (no una medida observada): sirve para traducir "quiero 3 unidades" a minutos
# cuando el objetivo se declara por unidades.
MINUTES_PER_UNIT = 10

MINUTES_MIN = 5
MINUTES_MAX = 180
TARGET_UNITS_MIN = 0
TARGET_UNITS_MAX = 12
MAX_NEW_MIN = 0
MAX_NEW_MAX = 5

# Categorías de paso del Session Engine que cuentan como REPASO (trabajo sobre
# material ya visto). El resto (`new`) es contenido nuevo. Se declara aquí, en un
# solo sitio, en vez de repetir la tupla en cada agregado.
REVIEW_KINDS = ("review", "listening")
NEW_KINDS = ("new",)


def normalize_plan_mode(value: object) -> str:
    """Modo de plan válido o `time` (tolerante con datos viejos o ajenos)."""
    return value if value in PLAN_MODES else DEFAULT_PLAN_MODE


def clamp_int(value: object, low: int, high: int, default: int) -> int:
    """Entero dentro de `[low, high]`; `default` si no es convertible."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def clamp_minutes_per_day(value: object) -> int:
    return clamp_int(value, MINUTES_MIN, MINUTES_MAX, 15)


def clamp_target_units(value: object) -> int:
    return clamp_int(value, TARGET_UNITS_MIN, TARGET_UNITS_MAX, DEFAULT_TARGET_UNITS)


def clamp_max_new(value: object) -> int:
    return clamp_int(value, MAX_NEW_MIN, MAX_NEW_MAX, DEFAULT_MAX_NEW)


def day_minutes_target(
    minutes_per_day: object, plan_mode: object, target_units: object
) -> int:
    """Minutos que declara el objetivo del día, según el modo.

    `units` sin `target_units` (0) cae a los minutos: un modo sin cifra no puede
    fijar un presupuesto, y caer a `time` es lo único honesto que se puede hacer
    sin inventarse un número.
    """
    minutes = clamp_minutes_per_day(minutes_per_day)
    units = clamp_target_units(target_units)
    mode = normalize_plan_mode(plan_mode)
    if mode == "units":
        return units * MINUTES_PER_UNIT if units > 0 else minutes
    if mode == "mixed":
        return max(minutes, units * MINUTES_PER_UNIT)
    return minutes


def day_units_target(plan_mode: object, target_units: object) -> int:
    """Unidades del objetivo del día (0 = el día no tiene tope de unidades)."""
    if normalize_plan_mode(plan_mode) == "time":
        return 0
    return clamp_target_units(target_units)


def remaining_units(units_target: int, units_done: int) -> int | None:
    """Unidades que aún caben hoy, o None si el día no declara objetivo de unidades.

    Es el tope de UNA lectura del plan: como el plan se recalcula en cada
    petición, sin restar lo ya hecho el objetivo de unidades no se podría cumplir
    nunca (cada lectura volvería a servir el cupo entero).
    """
    if units_target <= 0:
        return None
    return max(0, units_target - max(0, int(units_done)))


def remaining_minutes(minutes_target: int, minutes_done: int) -> int:
    """Minutos que faltan para el objetivo del día (nunca negativo).

    El plan sirve lo que FALTA, no el presupuesto entero otra vez: es lo que hace
    que la barra de progreso de la Home pueda llegar al 100 % en vez de
    rellenarse mientras el alumno sigue trabajando.
    """
    return max(0, int(minutes_target) - max(0, int(minutes_done)))


def cap_units(steps: list[dict], limit: int | None) -> list[dict]:
    """Recorta el plan a `limit` unidades sin romper el orden pedagógico.

    `session_plan` ya entrega los pasos ordenados (repaso vencido → listening →
    debilidad → nuevo → refuerzo), así que truncar por la cola **es** la política
    "repaso antes que nuevo": lo que se cae es siempre lo menos prioritario, y el
    material nuevo es lo primero que desaparece. `limit` None = sin tope.
    """
    if limit is None:
        return steps
    return steps[: max(0, limit)]


def rows_on_day(rows: list[dict], day: str) -> list[dict]:
    """Filas cuyo `created_at` cae en `day` (`YYYY-MM-DD`, ISO UTC como en `_now()`).

    Mismo criterio que `services/trends._day` (los 10 primeros caracteres): no se
    parsea la fecha para no depender de formatos que la app no genera.
    """
    return [r for r in rows if str(r.get("created_at") or "")[:10] == day]


def day_metrics(
    completions: list[dict],
    evidence_rows: list[dict],
    listening_rows: list[dict],
    day: str,
    bridge_rows: list[dict] | None = None,
) -> dict:
    """Métricas del día a partir de filas YA leídas y ya filtradas al día.

    Qué es cada número y qué NO es:

    - `units`: unidades del plan completadas hoy (una fila de `session_completions`).
    - `minutes`: suma de los minutos que el Session Engine había asignado a esas
      unidades. **Estimación del motor, no tiempo de reloj medido** (no hay
      cronómetro en la app).
    - `reviews` / `new` / `listening` / `practice`: las unidades agrupadas por su
      categoría (`kind`). `practice` = debilidad + refuerzo.
    - `speaking`: unidades completadas cuya destreza es `speaking` (por `skill`).
    - `unknown_units`: unidades completadas sin metadata (filas anteriores a
      V3.90). Cuentan como trabajo hecho pero **no** suman minutos: mejor un 0
      declarado que un dato inventado.
    - `listening_attempts` / `listening_accuracy`: intentos de listening del día y
      su acierto medio.
    - `accuracy`: media agregada de los resultados registrados hoy (evidencia de
      academia + intentos de listening), ponderada por número de intentos. **No es
      una nota del alumno**: es el resultado medio observado hoy.

    V3.92 (integración pedagógica) añade la pata del puente Listening → FSRS, con
    los mismos criterios de honestidad que el resto:

    - `difficulty_evidence`: cuántas VECES el día ha subido la dificultad de una
      palabra del léxico por no entender una frase que la contenía (`bridge_rows`,
      ya filtradas al día). Es evidencia REGISTRADA, no una estimación.
    - `words_flagged`: cuántas palabras DISTINTAS han subido. Se publica aparte
      porque una frase que se falla tres veces genera tres evidencias y una sola
      palabra marcada: sumar las dos cifras sería contar dos veces lo mismo.
    - `sense_exposures` (V3.94, ENFORCE): cuántas filas son una exposición a un
      sentido NUEVO (veredicto `mismatch`). NO subieron ninguna carta, así que no
      se cuentan como dificultad: el ledger las guarda y aquí se separan.
    - `occurrence:split` sin cambio de dificultad (V3.94.2, carta fuerte): la fila
      existe para medir el conflicto, pero no es dificultad ni exposición. Una
      carta débil con la misma razón SÍ sube y cuenta como dificultad.
    """
    by_kind: dict[str, int] = {}
    by_skill: dict[str, int] = {}
    minutes = 0
    unknown = 0
    for row in completions:
        kind = str(row.get("kind") or "")
        if kind:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        else:
            unknown += 1
        skill = str(row.get("skill") or "")
        if skill:
            by_skill[skill] = by_skill.get(skill, 0) + 1
        minutes += max(0, int(row.get("minutes") or 0))

    listening = rows_on_day(listening_rows, day)
    evidence = rows_on_day(evidence_rows, day)
    bridge = rows_on_day(list(bridge_rows or []), day)
    # V3.94 (ENFORCE): el ledger guarda también las filas `mismatch`, que registran
    # una acepción DISTINTA y NO subieron la dificultad de ninguna carta. Contarlas
    # como dificultad mentiría.
    # V3.94.2: un `occurrence:split` de carta fuerte también viaja con
    # `difficulty_before == difficulty_after`, pero NO es exposición. Si se contara
    # como el resto de lo que no es `mismatch`, inflaría la dificultad. Queda fuera
    # de los dos contadores. El informe de sombra lo cuenta por la razón.
    exposures = [
        row for row in bridge if str(row.get("sense_match") or "") == "mismatch"
    ]
    applied = [
        row
        for row in bridge
        if str(row.get("sense_match") or "") != "mismatch" and not _is_split_noop(row)
    ]
    correct = [1.0 if r.get("correct") else 0.0 for r in listening]
    results = [float(r.get("result") or 0.0) for r in evidence]
    pooled = correct + results
    attempts = len(pooled)
    listening_accuracy = (
        round(sum(correct) / len(correct), 3) if correct else None
    )
    return {
        "day": day,
        "units": len(completions),
        "unknown_units": unknown,
        "minutes": minutes,
        "reviews": sum(by_kind.get(k, 0) for k in REVIEW_KINDS),
        "new": sum(by_kind.get(k, 0) for k in NEW_KINDS),
        "listening": by_kind.get("listening", 0),
        "practice": by_kind.get("weakness", 0) + by_kind.get("easy_wins", 0),
        "speaking": by_skill.get("speaking", 0),
        "listening_attempts": len(correct),
        "listening_accuracy": listening_accuracy,
        "accuracy": round(sum(pooled) / attempts, 3) if attempts else None,
        "difficulty_evidence": len(applied),
        "words_flagged": len(
            {str(r.get("word") or "") for r in applied if r.get("word")}
        ),
        # V3.94 (ENFORCE): exposiciones a un sentido nuevo. NO son dificultad —no
        # subieron ninguna carta—, así que se publican aparte. Un split sin cambio
        # de dificultad no entra aquí: no es `mismatch`.
        "sense_exposures": len(exposures),
        "by_kind": by_kind,
        "by_skill": by_skill,
    }


def _is_split_noop(row: dict) -> bool:
    """¿Fila de conflicto que no movió la dificultad? (V3.94.2, pura).

    Solo el `occurrence:split` de una carta fuerte: `before == after`. Una carta
    débil con la misma razón sí sube y no es un no-op. Sin las dos cifras no se
    inventa el no-op (las filas antiguas del test no las traen).
    """
    if str(row.get("sense_reason") or "") != "occurrence:split":
        return False
    before = row.get("difficulty_before")
    after = row.get("difficulty_after")
    if before is None or after is None:
        return False
    return float(before) == float(after)


def goal_progress(
    *,
    minutes_target: int,
    minutes_done: int,
    units_target: int,
    units_done: int,
) -> dict:
    """Progreso del objetivo de hoy (0..1 en `percent`, con los números crudos).

    El `percent` es el **mínimo** de los objetivos declarados: en `mixed` el día se
    cumple con las dos cosas, así que la barra no puede ir más rápido que la más
    atrasada. Un objetivo no declarado (`units_target` = 0) no participa.

    Los repasos pendientes **no** se suman aquí: son trabajo disponible, no trabajo
    hecho. Un repaso ya completado sí cuenta como unidad (`units_done`), que es la
    política "repaso antes que nuevo" vista desde las métricas.
    """
    minutes_target = max(0, int(minutes_target))
    units_target = max(0, int(units_target))
    minutes_done = max(0, int(minutes_done))
    units_done = max(0, int(units_done))

    minutes_ratio = (
        min(1.0, minutes_done / minutes_target) if minutes_target > 0 else None
    )
    units_ratio = min(1.0, units_done / units_target) if units_target > 0 else None
    declared = [r for r in (minutes_ratio, units_ratio) if r is not None]
    percent = round(min(declared), 3) if declared else 0.0
    return {
        "units_done": units_done,
        "units_target": units_target,
        "minutes_done": minutes_done,
        "minutes_target": minutes_target,
        "units_ratio": units_ratio,
        "minutes_ratio": minutes_ratio,
        "percent": percent,
        "done": bool(declared) and percent >= 1.0,
    }


def review_pending(fsrs_due: int, listening_due: int) -> dict:
    """Repasos pendientes publicados por separado, con su origen (trazabilidad)."""
    fsrs = max(0, int(fsrs_due))
    listening = max(0, int(listening_due))
    return {"fsrs": fsrs, "listening": listening, "total": fsrs + listening}

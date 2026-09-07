"""Review/SRS por unidad (V3.16) — servicio puro y determinista.

Modela el "repaso por unidad" como un calendario de **ventanas de retención
fijas** (7/30/90 días desde el ancla de la unidad) totalmente separado del
scheduler continuo FSRS (hallazgo E3 de `docs/audit/E-FSRS-RETENTION.md`):
la ventana es un hito temporal, nunca se recalendariza por un grade; el grade
solo la marca como superada/fallida y, en paralelo, reprograma las cartas FSRS
`objective` de la unidad.

Mecanismos separados y etiquetados:
- La ventana vive aquí (`unit_review_attempts` como persistencia).
- El scheduler FSRS (`services/fsrs.py`) sigue siendo el único que decide el
  "cuándo" de las cartas; este módulo solo deriva estados de ventana a partir
  de intentos persistidos y del ancla.

El micro-review es **práctica de recuperación**: puntúa los checks MC oficiales
del currículo (muestreo determinista y balanceado, cero contenido artificial) y
NUNCA declara dominio ni crea evidencia de mastery (decisión D5: la evidencia
del currículo sigue siendo competencia exclusiva del Mastery Engine).

Puro: sin FastAPI ni BD.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from services import fsrs

# Ventanas de retención fijas (días) desde el ancla de la unidad (D3).
UNIT_REVIEW_WINDOWS_DAYS: tuple[int, ...] = (7, 30, 90)

# Umbral de "ventana superada" del micro-review (ratio de aciertos, D6).
MICRO_REVIEW_PASS_RATIO = 0.7

# Tamaño objetivo de un micro-review y máximo de ítems por objetivo (D8:
# muestreo balanceado por objetivo; el contenido son los checks MC oficiales).
MICRO_REVIEW_TARGET_ITEMS = 8
MICRO_REVIEW_MAX_PER_OBJECTIVE = 2

# Origen semántico de los intentos de repaso de unidad (etiqueta D5/E3: este
# mecanismo no es evidencia del currículo).
UNIT_REVIEW_SOURCE = "unit_micro_review"

# Estados posibles de una ventana.
WINDOW_UPCOMING = "upcoming"
WINDOW_DUE_NOW = "due_now"
WINDOW_PASSED = "passed"
WINDOW_FAILED = "failed"


def _parse_iso(value: str) -> datetime | None:
    """Parsea un ISO-8601 a datetime UTC con `tzinfo` (None si es inválido)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt: datetime) -> str:
    """Serializa un datetime a ISO-8601 UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _unit_checks(unit) -> Iterable[tuple[Any, Any]]:
    """Recorre `(objetivo, check)` de todos los objetivos de la unidad.

    La unidad es un modelo `Unit` del currículo (Lesson/Objective/ObjectiveCheck);
    el servicio se mantiene agnóstico de capa y solo consume su estructura."""
    for lesson in unit.lessons:
        for objective in lesson.objectives:
            for check in objective.checks:
                yield objective, check


def _unit_objective_ids(unit) -> set[str]:
    """Ids de todos los objetivos de la unidad."""
    return {o.id for les in unit.lessons for o in les.objectives}


def unit_completed(unit, mastered_ids: set[str]) -> bool:
    """True si todos los objetivos de la unidad están en `mastered_ids` (D4).

    Una unidad sin objetivos no puede estar completada: se devuelve False para
    no fabricar repaso donde no hay contenido evaluable."""
    ids = _unit_objective_ids(unit)
    return bool(ids) and ids.issubset(set(mastered_ids))


def unit_anchor(unit_mastery_rows: list[dict]) -> str | None:
    """Ancla temporal de la unidad: `max(updated_at)` de sus filas de mastery.

    Cada fila es un dict con al menos `updated_at` (ISO-8601). Es el momento en
    que aterrizó la última evidencia de mastery de la unidad (D4). Devuelve
    `None` si no hay filas (unidad sin evidencia → sin ancla → sin ventanas)."""
    best: datetime | None = None
    best_raw = ""
    for row in unit_mastery_rows:
        raw = str(row.get("updated_at") or "")
        parsed = _parse_iso(raw)
        if parsed is None:
            continue
        if best is None or parsed > best:
            best = parsed
            best_raw = raw
    return best_raw or None


def window_due_at(
    anchor_iso: str,
    window_days: int,
    *,
    now: str = "",
    attempts: list[dict] | None = None,
) -> dict:
    """Estado de una ventana de retención fija (D3/D6 + cadena O1, V3.18).

    `due_at = anchor + window_days` días y no cambia jamás: un grade no la
    mueve. `attempts` son los intentos de micro-review de la UNIDAD (todas sus
    ventanas, filas de `unit_review_attempts`); el "intento propio" se filtra
    aquí por `window_days`. Regla de estado (V3.18, cadena 7→30→90):

    - si hay intento propio: `passed` si el último alcanzó
      `accuracy >= MICRO_REVIEW_PASS_RATIO`, si no `failed` (reintentable); el
      intento propio manda SIEMPRE, incluso si otro intento superado posterior
      de la unidad cubriría esta ventana;
    - sin intento propio (cadena): `passed` si existe un intento SUPERADO de la
      unidad (de cualquier ventana) con `created_at >= due_at` de esta ventana —
      resolver tarde una ventana demuestra retención para las anteriores cuyo
      hito ya venció (deuda O1);
    - si no: `due_now` si `now >= due_at`, en otro caso `upcoming`.

    Devuelve `{window_days, due_at, state}`. Si el ancla no es un ISO válido se
    devuelve el estado `upcoming` (sin `due_at` computable) para no bloquear."""
    due_at = ""
    anchor_dt = _parse_iso(anchor_iso)
    due_dt = None
    if anchor_dt is not None:
        due_dt = anchor_dt + timedelta(days=int(window_days))
        due_at = _iso(due_dt)

    unit_attempts = attempts or []
    own = sorted(
        (
            a
            for a in unit_attempts
            if int(a.get("window_days") or -1) == window_days
        ),
        key=lambda a: a.get("created_at") or "",
    )
    if own:
        latest = own[-1]
        accuracy = float(latest.get("accuracy") or 0.0)
        state = WINDOW_PASSED if accuracy >= MICRO_REVIEW_PASS_RATIO else WINDOW_FAILED
        return {"window_days": int(window_days), "due_at": due_at, "state": state}

    # Cadena O1 (V3.18): sin intento propio, un intento superado de la unidad
    # con `created_at >= due_at` cierra esta ventana (resolución tardía).
    if due_dt is not None:
        for a in unit_attempts:
            if not bool(a.get("passed")):
                continue
            created = _parse_iso(a.get("created_at") or "")
            if created is not None and created >= due_dt:
                return {
                    "window_days": int(window_days),
                    "due_at": due_at,
                    "state": WINDOW_PASSED,
                }

    now_dt = _parse_iso(now) or _parse_iso(anchor_iso)
    state = WINDOW_UPCOMING
    if due_dt is not None and now_dt is not None:
        if now_dt >= due_dt:
            state = WINDOW_DUE_NOW
    return {"window_days": int(window_days), "due_at": due_at, "state": state}


def build_unit_review_plan(
    *,
    unit,
    unit_mastery_rows: list[dict],
    mastered_ids: set[str],
    now: str,
    level_id: str = "",
    module_id: str = "",
    module_title: str = "",
    anchor: str | None = None,
    attempts: list[dict] | None = None,
) -> dict:
    """Plan de repaso de una unidad: progreso, ancla y ventanas 7/30/90.

    `unit_mastery_rows` son las filas de mastery de los objetivos de la unidad
    (cada una con `updated_at`); `mastered_ids` los objetivos dominados del
    nivel; `now` fija la referencia temporal; `attempts` son los intentos de
    micro-review de la unidad (todas sus ventanas) para derivar los estados.

    V3.18 (I2): `anchor` permite pasar el ancla CONGELADA persistida en
    `unit_review_anchors`; si se omite (o es `None`) se deriva de las filas con
    `unit_anchor` (backfill). Un ancla persistida no se mueve por refuerzos o
    decay posteriores a la completitud (fijeza D3).

    Devuelve `{level_id, unit_id, module_id, module_title, title,
    objectives_total, objectives_mastered, completed, anchor, windows}` donde
    `windows` es la lista de `window_due_at` ordenada por ventana."""
    objective_ids = _unit_objective_ids(unit)
    total = len(objective_ids)
    mastered_here = len(objective_ids & set(mastered_ids))
    if anchor is None:
        anchor = unit_anchor(unit_mastery_rows)
    windows: list[dict] = []
    if anchor:
        unit_attempts = [a for a in (attempts or []) if a.get("unit_id") == unit.id]
        windows = [
            window_due_at(anchor, wd, now=now, attempts=unit_attempts)
            for wd in UNIT_REVIEW_WINDOWS_DAYS
        ]
    return {
        "level_id": level_id,
        "unit_id": unit.id,
        "module_id": module_id,
        "module_title": module_title,
        "title": unit.title,
        "objectives_total": total,
        "objectives_mastered": mastered_here,
        "completed": unit_completed(unit, mastered_ids),
        "anchor": anchor,
        "windows": windows,
    }


def sample_micro_review(
    *,
    unit,
    user_id: str,
    window_days: int,
    previous_failed_ids: list[str] | None = None,
    now: str = "",
) -> list[dict]:
    """Muestreo determinista y balanceado de checks MC para un micro-review.

    Semilla derivada de `(user_id, unit_id, window_days)`: la misma sesión
    produce el mismo orden (el servidor repuntúa exactamente lo que mostró al
    cliente entre el GET y el POST). En un reintento de la misma ventana se
    priorizan los ítems fallados del último intento (`previous_failed_ids`) y
    después se rellena con el resto de checks en rotación determinista.

    Cada ítem devuelto es `{item_id, objective_id, objective_title, skill,
    prompt, options}` — NUNCA incluye `correct_index` (premisa 21): el servidor
    puntúa con `score_micro_review`. `now` se acepta por compatibilidad de
    firma; no participa de la semilla para que GET y POST coincidan."""
    del now  # la semilla no usa el reloj: GET y POST deben muestrear igual
    refs = list(_unit_checks(unit))
    if not refs:
        return []
    rng = random.Random(f"{user_id}|{unit.id}|{window_days}")
    ordered = list(refs)
    rng.shuffle(ordered)

    failed = {cid for cid in (previous_failed_ids or [])}
    chosen: list[tuple[Any, Any]] = []
    counts: dict[str, int] = {}

    def _add(objective, check) -> bool:
        if len(chosen) >= MICRO_REVIEW_TARGET_ITEMS:
            return False
        if counts.get(objective.id, 0) >= MICRO_REVIEW_MAX_PER_OBJECTIVE:
            return False
        chosen.append((objective, check))
        counts[objective.id] = counts.get(objective.id, 0) + 1
        return True

    # 1) Fallidos del último intento primero (orden estable de rotación).
    for objective, check in ordered:
        if check.id in failed:
            _add(objective, check)
    # 2) Relleno con el resto de checks en rotación determinista.
    for objective, check in ordered:
        if len(chosen) >= MICRO_REVIEW_TARGET_ITEMS:
            break
        _add(objective, check)

    return [
        {
            "item_id": check.id,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "skill": check.skill,
            "prompt": check.prompt,
            "options": list(check.options),
        }
        for objective, check in chosen
    ]


def validate_micro_review_answers(
    *, answers: dict[str, int], sample: list[dict]
) -> None:
    """Valida las respuestas del micro-review contra la muestra servida (M2).

    Endurecimiento de la auditoría v3.16: cada clave de `answers` debe ser un
    `item_id` DE la muestra (nunca un ítem ajeno o stale) y cada índice elegido
    debe estar dentro del rango de opciones del ítem. Un ítem de la muestra SIN
    respuesta sigue contando como fallo (cobertura parcial permitida). Levanta
    `ValueError("unit_review.invalid_answers")` si algo no es coherente; el
    router lo convierte en 400."""
    sample_ids = {item["item_id"] for item in sample}
    unknown = [key for key in answers if key not in sample_ids]
    if unknown:
        raise ValueError("unit_review.invalid_answers")
    for item in sample:
        selected = answers.get(item["item_id"])
        if selected is None:
            continue
        option_count = len(item.get("options") or [])
        if not isinstance(selected, int) or not (0 <= selected < option_count):
            raise ValueError("unit_review.invalid_answers")


def score_micro_review(*, answers: dict[str, int], unit, sample: list[dict]) -> dict:
    """Puntúa un micro-review contra los checks oficiales del currículo.

    El cliente envía SOLO índices (`answers`: item_id → índice elegido); el
    servidor compara con `correct_index` de cada check (premisa 21). Un ítem sin
    respuesta cuenta como fallo. Antes de puntuar valida las respuestas contra
    la muestra (M2: claves ⊆ muestra e índices en rango). Devuelve `{correct,
    total, accuracy, passed, per_objective, items}` donde `per_objective`
    agrega por objetivo (`{objective_id, correct, total}`), `passed` =
    `accuracy >= 0.7` (D6) e `items` audita cada ítem (`{item_id, objective_id,
    selected_index, correct_index, correct}`) para que la UI revele la
    respuesta al terminar."""
    validate_micro_review_answers(answers=answers, sample=sample)
    checks: dict[str, tuple[Any, Any]] = {}
    for objective, check in _unit_checks(unit):
        checks[check.id] = (objective, check)

    per_item: list[dict] = []
    per_objective: dict[str, dict[str, int]] = {}
    order: list[str] = []
    correct = 0
    for item in sample:
        pair = checks.get(item["item_id"])
        if pair is None:
            continue
        objective, check = pair
        selected = answers.get(item["item_id"])
        is_correct = isinstance(selected, int) and selected == check.correct_index
        if is_correct:
            correct += 1
        bucket = per_objective.setdefault(
            objective.id, {"objective_id": objective.id, "correct": 0, "total": 0}
        )
        if objective.id not in order:
            order.append(objective.id)
        bucket["total"] += 1
        if is_correct:
            bucket["correct"] += 1
        per_item.append(
            {
                "item_id": item["item_id"],
                "objective_id": objective.id,
                "selected_index": selected if isinstance(selected, int) else -1,
                "correct_index": int(check.correct_index),
                "correct": bool(is_correct),
            }
        )

    total = len(sample)
    accuracy = round(correct / total, 3) if total else 0.0
    return {
        "per_objective": [per_objective[oid] for oid in order],
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "passed": accuracy >= MICRO_REVIEW_PASS_RATIO,
        "items": per_item,
    }


def grade_for_accuracy(accuracy: float) -> int:
    """Convierte la precisión (0..1) de un objetivo en grade FSRS 1..4.

    Delega en `fsrs.grade_from_score`: los grades de las cartas `objective` del
    micro-review se derivan siempre de la precisión por objetivo puntuada en
    servidor (nunca de una puntuación enviada por el cliente)."""
    return fsrs.grade_from_score(accuracy)

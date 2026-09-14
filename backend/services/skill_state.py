"""Estado del alumno por MODALIDAD × COMPETENCIA (V3.62, puro y determinista).

V3.62 (Student Skill State 4.0) construye **UN** modelo del alumno alimentado por
**toda** la evidencia disponible, para que lo que se mide fuera del drill léxico
(grammar, listening por subdestreza, pronunciation, reading, writing, speaking)
deje de ser INERTE para el propio estado:

    learning_evidence (léxico)  ┐
    academy_evidence            ├→ filas canónicas → puerta espaciada (2/2) → estado
    listening_attempts          │                      {modalidad: {competencia: entry}}
    pronunciation_attempts      ┘

La **puerta** es la MISMA de siempre: `learner_skill.OBSERVED_MIN_SAMPLES` éxitos
en `OBSERVED_MIN_DAYS` días naturales distintos por (modalidad, competencia), el
mismo rigor que el estado léxico de V3.53/V3.54. **Sin umbrales nuevos**: los 4
estados pedagógicos salen de `services.competence.competence_state` (el gate
reutilizado) y la carga por dimensión de `services.difficulty.earned_difficulty`.

Fronteras declaradas (lo que este módulo NO hace):

- **No inventa competencias.** La competencia la declara la FUENTE (subdestrezas
  del objetivo de currículum, subdestreza de `listening_attempts`, criterios de
  rúbrica). El camino léxico aporta entradas de MODALIDAD (con sus `dimensions`)
  y SIN competencia. `syntax`/`discourse`/… son CARGA de dificultad, no
  competencias: mapearlas a `grammar` inventaría evidencia no producida.
- **No traduce carga a competencia ni a nivel.** `dimensions` es la carga
  observada (1..5) y `state` sale del gate; no hay eje CEFR nuevo.
- **No declara éxito donde la fuente no lo declara.** Una fila de
  `academy_evidence` sin objetivo resoluble (el hueco F-K3: speaking assessment y
  misión escriben `objective_id=''`) entra como INTENTO con su `result` pero no
  acredita éxito, así que no cruza la puerta espaciada. Es la MISMA frontera que
  tiene hoy el Student Model (esas filas tampoco mueven el mastery por objetivo),
  no una regla nueva.
- **No usa reloj.** `review_due` solo se calcula si el llamador aporta `now`; sin
  `now` es `False` y la función es determinista con sus argumentos.

Fila canónica: `{modality, competence, occurred_on, occurred_at, success, score,
dimensions, source, kind, production}`. Las tres últimas claves son ADITIVAS
respecto al briefing y existen porque el gate reutilizado de `competence` lee
`evidence_by_kind` (retención `delayed`) y `production_count` (R5: Recognition ≠
Production): sin declararlas por fila, el gate no podría aplicarse sin inventar.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from services import difficulty, forgetting
from services.competence import PRODUCTION_SKILLS, STATE_ORDER, competence_state
from services.curriculum import DEFAULT_THRESHOLD
from services.evidence_depth import PRODUCTION_ITEM_TYPES
from services.learner_skill import OBSERVED_MIN_DAYS, OBSERVED_MIN_SAMPLES
from services.pronunciation import PASS_THRESHOLD as PRONUNCIATION_PASS_SCORE
from services.skill_axis import (
    COMPETENCES_BY_MODALITY,
    LEXICAL_MODALITY,
    MODALITY_OF,
    SKILL_MODALITIES,
    canonical_competence,
)

# Fuentes declaradas del estado (el nombre viaja en cada fila canónica).
SOURCES: tuple[str, ...] = ("lexicon", "academy", "listening", "pronunciation")

# Skills del ledger léxico que DECLARAN producción (los otros dos son
# recuperación y condición de uso espontáneo). Se usan para `production_count`,
# que el gate exige en las destrezas productivas.
_LEXICAL_PRODUCTION_SKILLS: tuple[str, ...] = (
    "written_production",
    "spoken_production",
    "spontaneous_use",
)

# Tipos de evidencia reconocidos por el gate (mismo vocabulario que
# `services.evidence_depth`).
_KINDS: tuple[str, ...] = ("familiar", "transfer", "novel", "delayed")


def _truthy(value: object) -> bool:
    """Interpretación booleana tolerante del ledger (nunca lanza)."""
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


def _stamp(value: object) -> str:
    """Marca temporal ISO declarada por la fuente ("" si no hay)."""
    return str(value or "").strip()


def _row(
    *,
    modality: str,
    competence: str,
    occurred_at: str,
    success: bool,
    score: float | None,
    dimensions: Mapping | None,
    source: str,
    kind: str = "",
    production: bool = False,
) -> dict:
    """Fila canónica del estado (una por HECHO observable; nunca agrega fuentes)."""
    return {
        "modality": modality,
        "competence": competence,
        "occurred_on": _stamp(occurred_at)[:10],
        "occurred_at": _stamp(occurred_at),
        "success": bool(success),
        "score": score,
        "dimensions": dict(dimensions or {}),
        "source": source,
        "kind": kind if kind in _KINDS else "",
        "production": bool(production),
    }


# ---------------------------------------------------------------------------
# Adaptadores: cada fuente → filas canónicas
# ---------------------------------------------------------------------------


def _lexicon_rows(rows: Sequence[Mapping]) -> list[dict]:
    """Ledger léxico (`learning_evidence`) → filas de modalidad, sin competencia.

    Proyección EXACTA de `services.evidence.observed_signals`: misma lectura de la
    carga acreditada (`difficulty.earned_difficulty`) y mismo descarte de fallos y
    de filas sin vector. El lector `list_observed_rows` entrega SOLO éxitos
    (filtro SQL de V3.53), de ahí `success=True`.
    """
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        skill = (
            str(row.get("assessed_skill") or row.get("skill") or "").strip().lower()
        )
        modality = LEXICAL_MODALITY.get(skill)
        if not modality:
            continue
        vector = difficulty.earned_difficulty(row)
        if not vector:
            continue
        result.append(
            _row(
                modality=modality,
                competence="",
                occurred_at=row.get("occurred_at"),
                success=True,
                score=1.0,
                dimensions=vector,
                source="lexicon",
                production=skill in _LEXICAL_PRODUCTION_SKILLS,
            )
        )
    return result


def _academy_rows(
    rows: Sequence[Mapping], objectives: Mapping | None
) -> list[dict]:
    """`academy_evidence` → filas por subdestreza declarada del objetivo.

    `skill` → modalidad; `objective_id` + `level_id` → objetivo del currículum →
    subdestrezas RESTRINGIDAS a las que declara la modalidad de la fila (una fila
    por subdestreza). Sin subdestrezas declaradas la fila va a competencia `""`.

    El ÉXITO lo declara el umbral del propio objetivo (`Objective.threshold`), que
    es el que ya usa el Student Model al actualizar el mastery. Sin objetivo
    resoluble no hay umbral declarado y la fila no acredita éxito (frontera F-K3).
    """
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        skill = str(row.get("skill") or "").strip().lower()
        modality = MODALITY_OF.get(skill)
        if not modality:
            continue
        level_id = str(row.get("level_id") or "").strip().lower()
        objective_id = str(row.get("objective_id") or "").strip()
        entry = None
        if objectives is not None and objective_id:
            entry = objectives.get((level_id, objective_id))
        threshold: float | None = None
        competences: tuple[str, ...] = ("",)
        if entry is not None:
            subskills, thresholds = entry
            threshold = _number((thresholds or {}).get(skill, DEFAULT_THRESHOLD))
            declared = [
                raw
                for raw in subskills
                if canonical_competence(modality, raw)
            ]
            unique = tuple(dict.fromkeys(declared))
            competences = unique or ("",)
        value = _number(row.get("result"))
        success = (
            threshold is not None and value is not None and value >= threshold
        )
        item_type = str(row.get("item_type") or "").strip().lower()
        production = item_type in PRODUCTION_ITEM_TYPES or skill in PRODUCTION_SKILLS
        kind = str(row.get("evidence_kind") or "").strip().lower()
        stamp = row.get("created_at")
        for competence in competences:
            result.append(
                _row(
                    modality=modality,
                    competence=competence,
                    occurred_at=stamp,
                    success=success,
                    score=value,
                    dimensions=None,
                    source="academy",
                    kind=kind,
                    production=production,
                )
            )
    return result


def _listening_rows(rows: Sequence[Mapping]) -> list[dict]:
    """`listening_attempts` → filas de la modalidad listening por subdestreza.

    La competencia es la subdestreza declarada por el intento (`skill`), validada
    contra el vocabulario de listening; una subdestreza no declarada (o ausente)
    deja la competencia `""` en lugar de inventarse. El acierto es el `correct`
    que el motor ya decide (incluye el umbral declarado de dictado/shadowing) y el
    `score` continuo (0..1) se conserva cuando lo hay.
    """
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        success = _truthy(row.get("correct"))
        value = _number(row.get("score"))
        result.append(
            _row(
                modality="listening",
                competence=canonical_competence("listening", row.get("skill")),
                occurred_at=row.get("created_at"),
                success=success,
                score=value if value is not None else (1.0 if success else 0.0),
                dimensions=None,
                source="listening",
            )
        )
    return result


def _pronunciation_rows(rows: Sequence[Mapping]) -> list[dict]:
    """`pronunciation_attempts` → filas de la modalidad pronunciation.

    El esquema de la tabla guarda el score en 0..100 (`services.pronunciation`:
    `score INTEGER`, umbral `PASS_THRESHOLD = 80`), así que se normaliza a 0..1 y
    el éxito lo declara ese mismo umbral ya declarado. La competencia queda `""`:
    la tabla no declara criterio, así que no se inventa ninguno.
    """
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        raw = _number(row.get("score"))
        result.append(
            _row(
                modality="pronunciation",
                competence="",
                occurred_at=row.get("created_at"),
                success=raw is not None and raw >= PRONUNCIATION_PASS_SCORE,
                score=None if raw is None else raw / 100.0,
                dimensions=None,
                source="pronunciation",
            )
        )
    return result


def skill_state_sources(
    *,
    lexicon: Sequence[Mapping] = (),
    academy: Sequence[Mapping] = (),
    listening: Sequence[Mapping] = (),
    pronunciation: Sequence[Mapping] = (),
    objectives: Mapping | None = None,
) -> list[dict]:
    """Filas canónicas de las CUATRO fuentes (pura; nunca lanza).

    `objectives` es el índice del currículum que devuelve
    `skill_axis.objective_competences_index()`; sin él las filas de
    `academy_evidence` se leen igual pero no declaran competencia ni éxito.
    """
    rows: list[dict] = []
    rows.extend(_lexicon_rows(lexicon or ()))
    rows.extend(_academy_rows(academy or (), objectives))
    rows.extend(_listening_rows(listening or ()))
    rows.extend(_pronunciation_rows(pronunciation or ()))
    return rows


# ---------------------------------------------------------------------------
# Agregación: filas → estado
# ---------------------------------------------------------------------------


def _capacity(rows: Sequence[Mapping]) -> dict[str, int]:
    """Carga observada por dimensión con la MISMA puerta que V3.54 (pura).

    Por (modalidad, competencia) ya hay entrada; aquí la carga de CADA dimensión
    exige su propia muestra espaciada, exactamente como
    `learner_skill.observed_skill_capacity`, para que los valores del camino
    léxico sean idénticos a los del estado de V3.54 (test de paridad).
    """
    samples: dict[str, int] = {}
    days: dict[str, set[str]] = {}
    capacity: dict[str, int] = {}
    for row in rows:
        if not row.get("success"):
            continue
        vector = row.get("dimensions") or {}
        if not isinstance(vector, Mapping):
            continue
        day = str(row.get("occurred_on") or "")
        for dimension, load in vector.items():
            if dimension not in difficulty.DIFFICULTY_DIMENSIONS:
                continue
            value = _number(load)
            if value is None:
                continue
            samples[dimension] = samples.get(dimension, 0) + 1
            if day:
                days.setdefault(dimension, set()).add(day)
            if int(value) > capacity.get(dimension, 0):
                capacity[dimension] = int(value)
    return {
        dimension: capacity[dimension]
        for dimension in difficulty.DIFFICULTY_DIMENSIONS
        if dimension in capacity
        and samples.get(dimension, 0) >= OBSERVED_MIN_SAMPLES
        and len(days.get(dimension, set())) >= OBSERVED_MIN_DAYS
    }


def _entry(
    rows: Sequence[Mapping],
    modality: str,
    competence: str,
    *,
    level: str,
    now: str,
) -> dict | None:
    """Entrada de (modalidad, competencia) o None si no cruza la puerta espaciada."""
    successes = [row for row in rows if row.get("success")]
    day_set = {
        str(row.get("occurred_on") or "")
        for row in successes
        if row.get("occurred_on")
    }
    if len(successes) < OBSERVED_MIN_SAMPLES or len(day_set) < OBSERVED_MIN_DAYS:
        return None
    attempts = len(rows)
    values = [
        value
        for value in (_number(row.get("score")) for row in rows)
        if value is not None
    ]
    score = (
        round(sum(values) / len(values), 3)
        if values
        else round(len(successes) / attempts, 3)
    )
    confidence = round(len(successes) / attempts, 3)
    last = max((str(row.get("occurred_at") or "") for row in rows), default="")
    by_kind = {kind: 0 for kind in _KINDS}
    for row in rows:
        kind = str(row.get("kind") or "")
        if kind in by_kind:
            by_kind[kind] += 1
    production_count = sum(1 for row in rows if row.get("production"))
    # `review_due` solo si el llamador aporta reloj; si las marcas de la fuente no
    # son comparables con `now` (naive vs aware) NO se inventa vencimiento.
    try:
        review_due = bool(now) and forgetting.review_due(score, last, now)
    except (TypeError, ValueError):
        review_due = False
    gate_entry = {
        "evidence_count": attempts,
        "score": score,
        "confidence": confidence,
        "evidence_by_kind": by_kind,
        "production_count": production_count,
        "last_evidence": last,
        "review_due": review_due,
    }
    record = competence_state(gate_entry, modality, level)
    return {
        "state": record["state"],
        "samples": len(successes),
        "days": len(day_set),
        "score": score,
        "confidence": confidence,
        "dimensions": _capacity(rows),
        "sources": sorted({str(row.get("source") or "") for row in rows}),
    }


def skill_state(
    rows: Sequence[Mapping] | None,
    *,
    level: str = "",
    now: str = "",
) -> dict[str, dict[str, dict]]:
    """Estado `{modalidad: {competencia: entry}}` (pura; nunca lanza).

    TODAS las modalidades canónicas están presentes (con `{}` si no hay
    evidencia), la misma convención que `learner_level_state.floor_level_by_skill`,
    para que el contrato no cambie de forma. `level` es el nivel del alumno (el
    mismo que usa `/api/profile` para el gate de profundidad) y `now` es opcional:
    sin él `review_due` es `False` y la función no lee el reloj.
    """
    grouped: dict[str, dict[str, list[dict]]] = {
        modality: {} for modality in SKILL_MODALITIES
    }
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        modality = str(row.get("modality") or "")
        if modality not in grouped:
            continue
        competence = str(row.get("competence") or "")
        grouped[modality].setdefault(competence, []).append(dict(row))
    state: dict[str, dict[str, dict]] = {}
    for modality in SKILL_MODALITIES:
        entries: dict[str, dict] = {}
        for competence in sorted(grouped[modality]):
            entry = _entry(
                grouped[modality][competence],
                modality,
                competence,
                level=level,
                now=now,
            )
            if entry is not None:
                entries[competence] = entry
        state[modality] = entries
    return state


def skill_state_summary(state: object) -> dict[str, dict]:
    """Resumen por modalidad del estado (DERIVADO, nunca fuente de verdad).

    Devuelve `{modalidad: {state, competences_with_sample, coverage}}`: el estado
    pedagógico MÁS ALTO alcanzado en la modalidad, las competencias con muestra
    (la entrada de modalidad `""` se incluye: es la que aporta el camino léxico) y
    la cobertura de competencias DECLARADAS por la modalidad
    (`{covered, total}`; `""` no cuenta como competencia porque no lo es).
    """
    data = state if isinstance(state, Mapping) else {}
    summary: dict[str, dict] = {}
    for modality in SKILL_MODALITIES:
        entries = data.get(modality)
        entries = entries if isinstance(entries, Mapping) else {}
        valid = {
            str(competence): entry
            for competence, entry in entries.items()
            if isinstance(entry, Mapping)
        }
        rank = max(
            (
                STATE_ORDER.index(str(entry.get("state")))
                for entry in valid.values()
                if str(entry.get("state")) in STATE_ORDER
            ),
            default=0,
        )
        declared = COMPETENCES_BY_MODALITY.get(modality, ())
        summary[modality] = {
            "state": STATE_ORDER[rank],
            "competences_with_sample": sorted(valid),
            "coverage": {
                "covered": sum(1 for c in declared if c in valid),
                "total": len(declared),
            },
        }
    return summary


def empty_skill_state() -> dict[str, dict[str, dict]]:
    """Estado neutro con la MISMA forma (dict nuevo en cada llamada)."""
    return {modality: {} for modality in SKILL_MODALITIES}


def normalize_skill_state(value: object) -> dict[str, dict[str, dict]]:
    """Estado desde un `Mapping` o su JSON cacheado (pura; nunca lanza).

    Normaliza la FORMA (todas las modalidades presentes, solo entradas que sean
    objetos) y descarta el resto. No reinterpreta valores: la fuente de verdad es
    la que lo escribió, esto solo lo hace legible para un consumidor O(1).
    """
    data = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return empty_skill_state()
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return empty_skill_state()
    state = empty_skill_state()
    if not isinstance(data, Mapping):
        return state
    for modality in SKILL_MODALITIES:
        entries = data.get(modality)
        if not isinstance(entries, Mapping):
            continue
        for competence, entry in entries.items():
            if isinstance(entry, Mapping):
                state[modality][str(competence)] = dict(entry)
    return state

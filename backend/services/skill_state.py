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

V3.63 (honestidad del estado, sin recablear la decisión) añade a esa fila:

- **Identidad y OCASIÓN** (`evidence_id`, `activity_id`, `assessment_id` y
  `occasion_key`): una evaluación que se EXPANDE a N competencias sigue siendo
  **UNA** ocasión. El dedup por ocasión SOLO puede acreditar menos que las
  muestras, nunca más, y si la fuente no declara identidad degrada EXACTAMENTE a
  V3.62 (una muestra = una ocasión).
- **Canal OBSERVADO** (`facts.assessment_mode`): la modalidad del evento léxico se
  resuelve por el CANAL declarado por la actividad (`services.task_semantics`), no
  solo por el mapa skill → modalidad. Sin canal declarado la degradación es exacta.
- **Hechos para la confianza de EVALUACIÓN** (`facts`): latencia, error, apoyo,
  canal, repeticiones, transcripción. `confidence` sigue siendo la estadística
  (éxitos / intentos) y **no cambia de fórmula**; `assessment_confidence` es otra
  cosa y se declara por separado.

La entrada del estado gana claves ADITIVAS: `observations`, `occasions`,
`assessment_confidence` y `observed_task_difficulty_2` (la capa empírica de
`services.observed_difficulty`). Ninguna clave de V3.62 cambia de significado.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from services import difficulty, forgetting, observed_difficulty
from services.competence import (
    PRODUCTION_SKILLS,
    STATE_ORDER,
    competence_state,
    gate_for,
)
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
    layer_for,
    layers_for,
    modalities_by_assessed_channel,
)
from services.task_semantics import (
    ASSESSMENT_MODES,
    activity_from_activity_id,
    assessment_mode_for,
)

# Fuentes declaradas del estado (el nombre viaja en cada fila canónica).
SOURCES: tuple[str, ...] = ("lexicon", "academy", "listening", "pronunciation")

# Canal OBSERVADO que declara cada modalidad (V3.63). Es una DECLARACIÓN, no una
# inferencia: la confianza de EVALUACIÓN baja cuando la modalidad no declara canal
# (no se inventa cobertura) y `interaction`/`mediation` quedan sin canal porque su
# canal real hoy no lo declara ninguna actividad.
MODALITY_CHANNEL: dict[str, str] = {
    "writing": "written",
    "vocabulary": "written",
    "grammar": "written",
    "reading": "receptive",
    "listening": "receptive",
    "speaking": "spoken",
    "pronunciation": "spoken",
}

# Bandas declaradas de confianza de EVALUACIÓN, de menor a mayor (el índice es el
# rango: agregar varias filas usa la banda MÍNIMA, que es la honesta).
ASSESSMENT_CONFIDENCE_BANDS: tuple[str, ...] = ("low", "medium", "high")

# Motivo escrito de la competencia vacía de la ruta de PRÁCTICA de pronunciación
# (P2-11): la tabla no declara criterio y la rúbrica formal no existe todavía, así
# que no se inventa ninguna competencia.
PRONUNCIATION_PRACTICE_REASON = (
    "la ruta de PRÁCTICA libre (`pronunciation_attempts`) no declara criterio de "
    "rúbrica (solo expected/heard/score): la competencia queda vacía a propósito"
)

# Hechos DECLARADOS que bajan la confianza de evaluación (tabla declarada, no
# umbral nuevo): apoyo fuerte → banda mínima; apoyo con pista o ayuda audiovisual
# → un escalón. Los mismos valores que ya lee la evidencia de listening.
_STRONG_SUPPORT_LEVELS: tuple[str, ...] = ("copied", "guided")
_SLOW_SPEED_VALUES: tuple[str, ...] = ("slow", "slower", "x-slow")
_REPLAY_MIN = 2

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
    evidence_id: object = "",
    activity_id: object = "",
    assessment_id: object = "",
    facts: Mapping | None = None,
) -> dict:
    """Fila canónica del estado (una por HECHO observable; nunca agrega fuentes).

    La IDENTIDAD (`evidence_id`/`activity_id`/`assessment_id`) y los `facts` son
    ADITIVOS de V3.63 y los declara la fuente: si no los declara van vacíos (nunca
    se inventa una identidad que permita acreditar de más).
    """
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
        "evidence_id": _stamp(evidence_id),
        "activity_id": _stamp(activity_id),
        "assessment_id": _stamp(assessment_id),
        "facts": dict(facts or {}),
    }


def occasion_key(row: Mapping) -> str:
    """Clave ESTABLE de la OCASIÓN de una fila canónica ("" si no la declara).

    Una OCASIÓN es una medición independiente (V3.62 P2-13: una evaluación que se
    expande a N competencias NO son N ocasiones). La clave se compone de identidad
    YA DECLARADA por la fuente, y su ausencia devuelve "": el llamador trata cada
    muestra sin identidad como su propia ocasión, que es la degradación EXACTA a
    V3.62 (nunca acredita más). Nunca lanza.
    """
    source = _stamp(row.get("source"))
    assessment = _stamp(row.get("assessment_id"))
    if assessment:
        return f"{source}:assessment:{assessment}"
    evidence = _stamp(row.get("evidence_id"))
    if evidence:
        return f"{source}:evidence:{evidence}"
    return ""


def _declared_channel(row: Mapping) -> str:
    """Canal OBSERVADO declarado por la actividad del evento ("" si no declara).

    La actividad sale del `activity_id` que ya escribe el ledger
    (`services.task_semantics.activity_from_activity_id`) y el canal de la
    declaración de esa actividad (`assessment_mode_for`). Nada se infiere del
    texto libre ni del skill.
    """
    activity = activity_from_activity_id(row.get("activity_id"))
    return assessment_mode_for(activity)


def _lexicon_modality(skill: str, channel: str) -> str:
    """Modalidad del evento léxico por CANAL declarado, o por skill (V3.62).

    Sin canal declarado (o con un canal que no declara modalidad para esa skill)
    la lectura es EXACTAMENTE la de V3.62: el mapa duro `LEXICAL_MODALITY`. Nunca
    lanza.
    """
    if channel:
        declared = modalities_by_assessed_channel(skill, channel)
        if declared:
            return declared[0]
    return LEXICAL_MODALITY.get(skill, "")


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
        channel = _declared_channel(row)
        modality = _lexicon_modality(skill, channel)
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
                evidence_id=row.get("id"),
                activity_id=row.get("activity_id"),
                facts={
                    "assessment_mode": channel,
                    "served_load": difficulty.parse_vector(
                        row.get("served_difficulty")
                    ),
                    "support_level": str(row.get("support_level") or "").strip(),
                    "response_time_ms": row.get("response_time_ms"),
                    "error_type": str(row.get("error_type") or "").strip(),
                    "context_instance": str(
                        row.get("context_instance") or ""
                    ).strip(),
                    "activity": activity_from_activity_id(row.get("activity_id")),
                },
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
        activity_id = row.get("activity_id")
        context_id = str(row.get("context_id") or "").strip()
        support_level = str(row.get("support_level") or "").strip()
        # V3.63 (P2-11): si la fila DECLARA un criterio (`item_id`) que la ruta ya
        # puntúa, esa es la competencia. No se expande por las subdestrezas del
        # objetivo (esas son la lectura de V3.62 para filas sin criterio).
        declared_competence = canonical_competence(modality, row.get("item_id"))
        if declared_competence:
            competences = (declared_competence,)
        facts = {
            "assessment_mode": assessment_mode_for(
                activity_from_activity_id(activity_id)
            ),
            "support_level": support_level,
            "activity": activity_from_activity_id(activity_id),
            "context_id": context_id,
        }
        # UNA evaluación (una fila de academy) es UNA ocasión aunque se expanda a
        # N competencias: la identidad de la OCASIÓN es la fila, no la competencia.
        identity = row.get("id")
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
                    evidence_id=identity,
                    activity_id=activity_id,
                    assessment_id=identity,
                    facts=facts,
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
                evidence_id=row.get("id"),
                activity_id=row.get("question_id"),
                facts={
                    "speed_used": str(row.get("speed_used") or "").strip(),
                    "transcript_used": row.get("transcript_used"),
                    "replay_count": row.get("replay_count"),
                    "response_time_ms": row.get("response_time_ms"),
                    "layer": str(row.get("layer") or "").strip(),
                },
            )
        )
    return result


def _pronunciation_rows(rows: Sequence[Mapping]) -> list[dict]:
    """`pronunciation_attempts` → filas de la modalidad pronunciation.

    El esquema de la tabla guarda el score en 0..100 (`services.pronunciation`:
    `score INTEGER`, umbral `PASS_THRESHOLD = 80`), así que se normaliza a 0..1 y
    el éxito lo declara ese mismo umbral ya declarado. La competencia queda `""`
    porque la tabla NO declara criterio (V3.63 P2-11: `PRONUNCIATION_PRACTICE_REASON`
    deja el motivo escrito en lugar de inventar una rúbrica que no existe).
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
                evidence_id=row.get("id"),
                facts={"practice": True},
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


def assessment_confidence(row: Mapping) -> dict:
    """Confianza de EVALUACIÓN de una fila: banda declarada + motivos (V3.63).

    NO es la confianza estadística (`confidence` = éxitos / intentos, que no cambia
    de fórmula). Responde a otra pregunta: *¿cuánto cubre esta medición de lo que
    dice medir?* y se deriva SOLO de hechos YA PERSISTIDOS (canal observado,
    `support_level`, audiovisual de listening, contexto de transfer). Un hecho
    DESCONOCIDO baja la banda (nunca se inventa cobertura). Nunca lanza.
    """
    facts = row.get("facts")
    facts = facts if isinstance(facts, Mapping) else {}
    modality = str(row.get("modality") or "")
    reasons: list[str] = []
    rank = len(ASSESSMENT_CONFIDENCE_BANDS) - 1
    channel = str(
        facts.get("assessment_mode") or MODALITY_CHANNEL.get(modality, "")
    ).strip().lower()
    if channel not in ASSESSMENT_MODES:
        reasons.append("channel_unknown")
        rank = 0
    support = str(facts.get("support_level") or "").strip().lower()
    if support in _STRONG_SUPPORT_LEVELS:
        reasons.append("scaffolded")
        rank = 0
    elif support == "cued":
        reasons.append("cued")
        rank = min(rank, 1)
    if _truthy(facts.get("transcript_used")):
        reasons.append("transcript_visible")
        rank = min(rank, 1)
    if str(facts.get("speed_used") or "").strip().lower() in _SLOW_SPEED_VALUES:
        reasons.append("slowed_audio")
        rank = min(rank, 1)
    replays = _number(facts.get("replay_count"))
    if replays is not None and replays >= _REPLAY_MIN:
        reasons.append("repeated_audio")
        rank = min(rank, 1)
    if str(facts.get("activity") or "").strip().lower() == "transfer" and not (
        str(facts.get("context_instance") or "").strip()
        or str(facts.get("context_id") or "").strip()
    ):
        reasons.append("instance_unknown")
        rank = min(rank, 1)
    if _truthy(facts.get("practice")):
        reasons.append("practice_route")
        rank = min(rank, 1)
    return {
        "band": ASSESSMENT_CONFIDENCE_BANDS[rank],
        "reasons": sorted(set(reasons)),
    }


def _aggregate_assessment_confidence(rows: Sequence[Mapping]) -> dict:
    """Banda MÍNIMA y motivos UNIDOS de varias filas (la honesta al agregar)."""
    confidences = [assessment_confidence(row) for row in rows]
    if not confidences:
        return {"band": ASSESSMENT_CONFIDENCE_BANDS[0], "reasons": []}
    rank = min(
        ASSESSMENT_CONFIDENCE_BANDS.index(str(item.get("band")))
        for item in confidences
        if str(item.get("band")) in ASSESSMENT_CONFIDENCE_BANDS
    )
    reasons = sorted(
        {reason for item in confidences for reason in item.get("reasons", [])}
    )
    return {"band": ASSESSMENT_CONFIDENCE_BANDS[rank], "reasons": reasons}


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
    # V3.63 (P2-14): la puerta se PIDE por política declarada; hoy devuelve siempre
    # el gate de V3.54 (2/2), así que el corte es byte-idéntico.
    sources = sorted({str(row.get("source") or "") for row in rows})
    gate = gate_for(modality, competence, ",".join(sources))
    if len(successes) < gate.min_samples or len(day_set) < gate.min_days:
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
    # V3.63: muestras ≠ OCASIONES. Una evaluación expandida a N competencias son N
    # muestras y UNA ocasión; una fuente sin identidad declarada cuenta cada
    # muestra como su propia ocasión (degradación EXACTA a V3.62). El dedup solo
    # puede acreditar MENOS, nunca más.
    keys = [occasion_key(row) for row in successes]
    occasions = sum(1 for key in keys if not key) + len(
        {key for key in keys if key}
    )
    return {
        "state": record["state"],
        "samples": len(successes),
        "days": len(day_set),
        "score": score,
        "confidence": confidence,
        "dimensions": _capacity(rows),
        "sources": sources,
        "observations": attempts,
        "occasions": occasions,
        "assessment_confidence": _aggregate_assessment_confidence(rows),
        "observed_task_difficulty_2": (
            observed_difficulty.observed_task_difficulty_2(rows)
        ),
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
        # V3.63 (P2-12): capas DECLARADAS de la modalidad (hoy solo listening, con
        # el vocabulario que ya usa el motor: recognition/comprehension/inference).
        # Una competencia fuera del eje (`dictation`/`shadowing`, que son PRODUCCIÓN)
        # no entra en ninguna capa, y eso es lo declarado, no un olvido.
        declared_layers = layers_for(modality)
        if declared_layers:
            layers: dict[str, dict] = {}
            for layer in declared_layers:
                covered = sorted(
                    competence
                    for competence, entry in valid.items()
                    if layer_for(modality, competence) == layer
                )
                layer_rank = max(
                    (
                        STATE_ORDER.index(str(valid[competence].get("state")))
                        for competence in covered
                        if str(valid[competence].get("state")) in STATE_ORDER
                    ),
                    default=0,
                )
                layers[layer] = {
                    "state": STATE_ORDER[layer_rank],
                    "competences_with_sample": covered,
                }
            summary[modality]["layers"] = layers
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

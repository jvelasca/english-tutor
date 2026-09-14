"""Decision Projection — del Student Skill State a la DECISIÓN (V3.64).

V3.62 construyó **UN** modelo del alumno (`{modalidad: {competencia: entry}}`) y
V3.63 lo hizo **honesto** (ocasiones, canal observado, confianza de evaluación,
frescura). Pero el modelo seguía siendo **DESCRIPTIVO**: la decisión de tareas
(ELV, planner) continuaba leyendo el estado de V3.54
(`learning_profile.observed_skill_capacity`) y el estado nuevo **no gobernaba
nada**. Ese es el **P1-01** de la auditoría de V3.62, y esta es su capa de cierre:

    Student Skill State  →  DECISION PROJECTION  →  Planner 3.0

**Nunca** `skill_state → planner` directamente. El planner sigue siendo un módulo
PURO y CIEGO al estado persistido: recibe `capacity_by_skill`, `skill_values` y
`drivers`, que son **proyecciones** calculadas aquí a partir de las **MISMAS
filas canónicas** que alimentan el estado (nunca de la caché como fuente de
verdad; la caché sellada de V3.63 es solo la optimización O(1) y se valida con
`skill_state_is_fresh` antes de usarse).

Qué proyecta cada celda, y por qué está SEPARADO:

- `load` — HECHOS de la tarea: `highest_demonstrated_load` (lo que hoy se llamaba
  "dificultad": es carga MÁXIMA DEMOSTRADA, no dificultad empírica — P2-04 de la
  auditoría de V3.63), `served_ceiling`, `credited_ceiling` y `scaffolding_gap`.
- `effort` — COSTE observado: nivel declarado (apoyo/audiovisual) y la carga
  EXTRA experimentada sobre la servida.
- `retention` — vencimiento declarado (`review_due`, `last_evidence`).
- `transfer` — contextos distintos declarados y reparto por `kind`.
- `confidence` (estadística) y `assessment_confidence` (banda + motivos) siguen
  siendo DOS cosas distintas y aquí **no se fusionan** (V3.63).

Fronteras declaradas (lo que este módulo NO hace):

- **No mezcla dificultad con esfuerzo (P2-02).** Los grupos van separados y solo
  `gap`/`retention`/`transfer`/`effort` entran en el valor, con pesos DECLARADOS.
- **No trata `error_type` como coste homogéneo (P2-03).** Una tabla declarada lo
  reparte en error de TAREA (señal de dificultad) e INCERTIDUMBRE DE MEDIDA
  (baja la confianza de evaluación, **nunca** sube la carga): `semantic_doubt` y
  `empty` no dicen que la tarea fuera más difícil, dicen que la medición cubre
  menos.
- **No inventa dificultad empírica.** `highest_demonstrated_load` se llama como
  lo que es; `P(éxito | alumno, tarea)` es **V3.65** y no se simula aquí.
- **No usa umbrales nuevos de evidencia.** La puerta espaciada (2 éxitos / 2
  días) ya la aplicó el estado; `assessment_confidence` no es un peso, es un
  **filtro de comparabilidad** (una capacidad medida con banda MÍNIMA no compite
  en el argmax: premiar la ignorancia rompería el invariante de V3.57).
- **No lee el reloj, ni aleatoriedad, ni I/O, ni LLM.** Función pura de sus
  argumentos, determinista byte a byte; nunca lanza.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from services.difficulty import DIFFICULTY_DIMENSIONS
from services.evidence import (
    LEXICAL_SKILLS,
    SEMANTIC_DOUBT_ERROR,
    SEMANTIC_MISMATCH_ERROR,
)
from services.skill_axis import LEXICAL_MODALITY
from services.skill_state import MODALITY_CHANNEL

# Pesos DECLARADOS de la proyección (suman 1.0). No son parámetros estimados por
# datos: son la importancia pedagógica declarada de cada componente sobre el eje.
# `assessment_confidence` NO está aquí: es un filtro de comparabilidad, no un peso.
PROJECTION_WEIGHTS: dict[str, float] = {
    "gap": 0.35,
    "retention": 0.30,
    "transfer": 0.20,
    "effort": 0.15,
}

# Progreso declarado del estado pedagógico (tabla, no umbral): 0 = nada
# demostrado, 1 = demostrado. El hueco es su complemento.
STATE_PROGRESS: dict[str, float] = {
    "not_started": 0.0,
    "developing": 0.34,
    "functional": 0.67,
    "demonstrated": 1.0,
}

# Depender del andamiaje es un hueco AÑADIDO al del estado (declarado, acotado).
SCAFFOLDING_PENALTY = 0.2

# Nivel de ESFUERZO declarado → valor 0..1 del componente (tabla declarada).
EFFORT_VALUE: dict[str, float] = {"none": 0.0, "some": 0.5, "high": 1.0}
EFFORT_ORDER: tuple[str, ...] = ("none", "some", "high")

# Motivos de `assessment_confidence` que son COSTE de la tarea (suben el nivel de
# esfuerzo). `channel_unknown`/`instance_unknown` NO están: son incertidumbre de
# MEDIDA y bajan la banda, no suben el esfuerzo (frontera P2-03).
EFFORT_LEVEL_BY_REASON: dict[str, str] = {
    "scaffolded": "high",
    "transcript_visible": "high",
    "slowed_audio": "some",
    "repeated_audio": "some",
    "cued": "some",
    "practice_route": "some",
}

# Clasificación DECLARADA de `error_type` (V3.64, P2-03). NO es un umbral: es el
# reparto de un vocabulario YA DECLARADO (`services.evidence.RECALL_ERROR_TYPES`,
# `WRITE_ERROR_TYPES`, `TRANSFER_ERROR_TYPES` y el `asr_status` del reconocimiento
# de voz) en dos familias con significado distinto.
TASK_ERROR_TYPES: tuple[str, ...] = (
    "wrong_word",  # otra palabra: confusión real, la tarea costó
    "orthographic_error",  # errata sobre la forma esperada
    "partial",  # producción incompleta
    "multiple_word_error",  # varias palabras mal
    "missing_target",  # no usó la unidad objetivo
    "too_short",  # frase demasiado corta para ser producción propia
    SEMANTIC_MISMATCH_ERROR,  # la unidad se usó en una función incompatible
)
MEASUREMENT_UNCERTAINTY_TYPES: tuple[str, ...] = (
    "empty",  # nada que medir: no es dificultad, es ausencia de intento
    SEMANTIC_DOUBT_ERROR,  # veredicto débil: advierte, no destruye la evidencia
    "low_confidence",  # ASR
    "unintelligible",  # ASR
    "no_speech",  # ASR
)

# Contextos distintos exigidos para considerar la transferencia cubierta (espejo
# declarado de `planner.TRANSFER_MIN_SUCCESS_CONTEXTS`; no se importa para no
# acoplar la proyección al planner).
TRANSFER_MIN_CONTEXTS = 2

# Banda de evaluación por debajo de la cual la celda es PROVISIONAL y no aporta
# capacidad comparable (banda mínima declarada de V3.63).
PROVISIONAL_BAND = "low"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


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


def _int(value: object) -> int:
    """Entero no negativo (0 si falta o no es numérico)."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence:
    return value if isinstance(value, (list, tuple)) else ()


def _dimensions(value: object) -> dict[str, int]:
    """Vector por dimensión canónica, solo cargas > 0 y en orden canónico."""
    loads = {
        str(dimension): _int(load)
        for dimension, load in _mapping(value).items()
        if dimension in DIFFICULTY_DIMENSIONS and _int(load) > 0
    }
    return {
        dimension: loads[dimension]
        for dimension in DIFFICULTY_DIMENSIONS
        if dimension in loads
    }


def _positive_difference(left: Mapping, right: Mapping) -> dict[str, int]:
    """Diferencia POSITIVA `left − right` por dimensión canónica (pura).

    Es la distancia entre dos medidas declaradas (servido vs acreditado). Sin
    dimensiones nuevas ni umbrales: solo la resta de dos hechos. Nunca lanza.
    """
    return {
        dimension: load - _int(right.get(dimension))
        for dimension, load in _dimensions(left).items()
        if load - _int(right.get(dimension)) > 0
    }


def _error_families(error_types: object) -> dict[str, list[str]]:
    """Reparte los `error_type` declarados en las dos familias (pura)."""
    declared = [
        str(value).strip().lower()
        for value in _sequence(error_types)
        if str(value).strip()
    ]
    task = [value for value in declared if value in TASK_ERROR_TYPES]
    uncertainty = [
        value for value in declared if value in MEASUREMENT_UNCERTAINTY_TYPES
    ]
    return {"task": sorted(set(task)), "measurement": sorted(set(uncertainty))}


def _effort(entry: Mapping) -> dict:
    """Grupo ESFUERZO declarado de una celda: nivel + motivos de coste."""
    reasons = _sequence(_mapping(entry.get("assessment_confidence")).get("reasons"))
    level = "none"
    declared_reasons: list[str] = []
    for reason in reasons:
        declared = EFFORT_LEVEL_BY_REASON.get(str(reason), "")
        if not declared:
            continue
        declared_reasons.append(str(reason))
        if EFFORT_ORDER.index(declared) > EFFORT_ORDER.index(level):
            level = declared
    return {"level": level, "reasons": sorted(set(declared_reasons))}


def _cell(modality: str, competence: str, entry: Mapping) -> dict:
    """Celda proyectada de (modalidad, competencia) — pura y nunca lanza.

    Todos los hechos salen del propio estado: la capacidad acreditada
    (`dimensions`) y la capa empírica de V3.63 (`observed_task_difficulty_2`,
    que YA agrega los techos servido/acreditado/experimentado). Así la proyección
    es función pura del estado y no necesita volver a leer las filas canónicas:
    la misma celda se obtiene de la caché sellada o de un recálculo.
    """
    capacity = _dimensions(entry.get("dimensions"))
    confidence = _mapping(entry.get("assessment_confidence"))
    reasons = sorted(
        {str(reason) for reason in _sequence(confidence.get("reasons"))}
    )
    band = str(confidence.get("band") or "")
    # PROVISIONAL = banda MÍNIMA declarada (medición que cubre poco). No es un
    # umbral nuevo: es la banda que V3.63 ya declara.
    provisional = band == PROVISIONAL_BAND
    empirical = _mapping(entry.get("observed_task_difficulty_2"))
    served = _dimensions(empirical.get("served_ceiling"))
    credited = _dimensions(empirical.get("credited_ceiling"))
    experienced = _dimensions(empirical.get("experienced_load"))
    kinds = {
        str(kind): _int(count)
        for kind, count in _mapping(entry.get("kinds")).items()
    }
    contexts = [
        str(context).strip()
        for context in _sequence(entry.get("contexts"))
        if str(context).strip()
    ]
    occasions = _int(entry.get("occasions"))
    novel_kinds = kinds.get("novel", 0) + kinds.get("transfer", 0)
    declared_channel = (
        "" if "channel_unknown" in reasons else MODALITY_CHANNEL.get(modality, "")
    )
    return {
        "modality": modality,
        "competence": competence,
        "state": str(entry.get("state") or ""),
        "samples": _int(entry.get("samples")),
        "occasions": occasions,
        "days": _int(entry.get("days")),
        "confidence": _number(entry.get("confidence")) or 0.0,
        "assessment_confidence": {"band": band, "reasons": reasons},
        "declared_channel": declared_channel,
        # CAPACIDAD medida (la misma lectura que el estado acredita). El filtro de
        # comparabilidad se aplica en `capacity_by_skill`, no aquí: la proyección
        # describe, la decisión filtra.
        "capacity": dict(capacity),
        "comparable": not provisional,
        # GRUPO CARGA (hechos de la tarea). `highest_demonstrated_load` se llama
        # como lo que es: carga máxima DEMOSTRADA, no dificultad empírica; la
        # dependencia de andamiaje es la distancia `servido − acreditado` (dos
        # hechos declarados, ninguna tabla de descuento nueva).
        "load": {
            "highest_demonstrated_load": dict(capacity),
            "served_ceiling": served,
            "credited_ceiling": credited,
            "scaffolding_gap": _positive_difference(served, credited),
        },
        # GRUPO ESFUERZO (coste observado), SEPARADO de la carga (P2-02): el
        # nivel declarado por los motivos de `assessment_confidence` y la carga
        # EXTRA que la tarea no había pedido (`experimentado − servido`).
        "effort": {
            **_effort(entry),
            "extra_load": _positive_difference(experienced, served),
        },
        # RETENCIÓN (señal de primera clase para el Planner 3.0).
        "retention": {
            "review_due": bool(entry.get("review_due")),
            "last_evidence": str(entry.get("last_evidence") or ""),
        },
        # TRANSFERENCIA Y NOVEDAD (contextos declarados y reparto por `kind`).
        "transfer": {
            "kinds": kinds,
            "contexts": sorted(set(contexts)),
            "context_count": len(set(contexts)),
        },
        "novelty": (round(_clamp(novel_kinds / occasions), 4) if occasions else 0.0),
        # PRODUCCIÓN y reparto declarado de tipos de error (P2-03).
        "production_count": _int(entry.get("production_count")),
        "error_families": _error_families(entry.get("error_types")),
        "provisional": provisional,
    }


def project(state: object) -> dict[str, dict[str, dict]]:
    """Proyecta el estado `{modalidad: {competencia: entry}}` (pura).

    Devuelve `{modalidad: {competencia: celda}}` con la MISMA forma de modalidades
    que el estado (todas las presentes), para que el contrato no cambie de forma
    entre el camino con estado y el camino degradado. Es una función PURA del
    estado: no lee I/O, ni el reloj, ni las filas canónicas (el estado ya las
    agregó). Nunca lanza.
    """
    projection: dict[str, dict[str, dict]] = {}
    for modality, entries in _mapping(state).items():
        cells: dict[str, dict] = {}
        for competence, entry in _mapping(entries).items():
            if not isinstance(entry, Mapping):
                continue
            cells[str(competence)] = _cell(str(modality), str(competence), entry)
        projection[str(modality)] = cells
    return projection


def _cell_of(projection: object, modality: str, competence: str = "") -> Mapping:
    entries = _mapping(_mapping(projection).get(modality))
    cell = entries.get(competence)
    return cell if isinstance(cell, Mapping) else {}


def capacity_by_skill(projection: object) -> dict[str, dict]:
    """Capacidad por CANAL evaluado desde la proyección (V3.64).

    Es el **reemplazo directo** de `lexicon._capacity_by_skill`: MISMO espacio de
    claves (las cuatro de `LEXICAL_SKILLS`) y mismo contrato de valor (vector de
    dimensiones). La diferencia es la FUENTE (el estado unificado en vez de la
    columna de V3.54) y el FILTRO: una celda PROVISIONAL (banda de evaluación
    mínima) no aporta capacidad comparable, de modo que el argmax de V3.57 no
    premie la ignorancia. Nunca lanza.
    """
    result: dict[str, dict] = {}
    for skill in LEXICAL_SKILLS:
        cell = _cell_of(projection, LEXICAL_MODALITY.get(skill, ""), "")
        result[skill] = (
            _dimensions(cell.get("capacity")) if cell.get("comparable") else {}
        )
    return result


def has_comparable_capacity(capacity: object) -> bool:
    """¿La proyección declara alguna capacidad comparable? (V3.64, pura).

    Condición de DEGRADACIÓN declarada del recableado: el estado unificado solo
    habla con su puerta espaciada (2 muestras / 2 días) y una celda PROVISIONAL no
    compite. Mientras el estado calla, el llamador conserva el estimador anterior
    (`lexicon._capacity_by_skill`, la misma familia de evidencia): el estado manda
    cuando tiene algo que decir y **nunca** se pierde señal por recablear. Nunca
    lanza.
    """
    return any(
        bool(_dimensions(vector)) for vector in _mapping(capacity).values()
    )


def skill_components(projection: object, skill: str) -> dict[str, float]:
    """Componentes DECLARADOS del valor pedagógico de un eje (pura).

    `{gap, retention, transfer, effort}` en 0..1. Un eje SIN celda (sin muestra
    espaciada) tiene hueco máximo: es exactamente el caso que `planner.skill_gaps`
    llama "modalidad sin ningún éxito". Nunca lanza.
    """
    modality = LEXICAL_MODALITY.get(str(skill or "").strip().lower(), "")
    cell = _cell_of(projection, modality, "")
    if not cell:
        return {"gap": 1.0, "retention": 0.0, "transfer": 1.0, "effort": 0.0}
    progress = STATE_PROGRESS.get(str(cell.get("state") or ""), 0.0)
    gap = 1.0 - progress
    if _mapping(_mapping(cell.get("load")).get("scaffolding_gap")):
        gap = gap + SCAFFOLDING_PENALTY
    retention = 1.0 if _mapping(cell.get("retention")).get("review_due") else 0.0
    contexts = _int(_mapping(cell.get("transfer")).get("context_count"))
    transfer = 1.0 - (contexts / TRANSFER_MIN_CONTEXTS)
    effort = EFFORT_VALUE.get(
        str(_mapping(cell.get("effort")).get("level") or ""), 0.0
    )
    return {
        "gap": round(_clamp(gap), 4),
        "retention": round(_clamp(retention), 4),
        "transfer": round(_clamp(transfer), 4),
        "effort": round(_clamp(effort), 4),
    }


def skill_values(projection: object) -> dict[str, float]:
    """Valor pedagógico proyectado por eje (0..1), con pesos declarados.

    Es el `value` del Planner 3.0: sustituye al `skill_priorities` de V3.57 como
    VALOR de la tarea e incorpora como señales de primera clase la retención, la
    transferencia y el esfuerzo observado —no solo la urgencia. Nunca lanza.
    """
    values: dict[str, float] = {}
    for skill in LEXICAL_SKILLS:
        components = skill_components(projection, skill)
        total = sum(
            weight * components.get(component, 0.0)
            for component, weight in PROJECTION_WEIGHTS.items()
        )
        values[skill] = round(_clamp(total), 4)
    return values


def _driver_band(value: float) -> str:
    """Banda declarada de un componente (0..1) para la explicación."""
    if value <= 0.0:
        return "none"
    if value >= 0.67:
        return "high"
    if value >= 0.34:
        return "medium"
    return "low"


def drivers(projection: object, skill: str) -> dict:
    """Drivers EXPLICABLES de la decisión de un eje (V3.64, pura).

    Es el bloque que hace auditable al Planner 3.0: nada de un `priority` sin
    motivo. `difficulty_fit` NO se calcula aquí porque depende de la dificultad
    de la TAREA (lo añade el planner con el `margin` que ya mide). Nunca lanza.
    """
    key = str(skill or "").strip().lower()
    modality = LEXICAL_MODALITY.get(key, "")
    cell = _cell_of(projection, modality, "")
    components = skill_components(projection, key)
    base = {
        "skill": key,
        "modality": modality,
        "value": skill_values(projection).get(key, 0.0),
        "components": components,
        "weights": dict(PROJECTION_WEIGHTS),
    }
    if not cell:
        return {
            **base,
            "measured": False,
            "gap": "high",
            "retention_due": False,
            "transfer_gap": "high",
            "effort": "none",
            "assessment_confidence": "",
            "recent_failure": False,
            "novelty": 0.0,
            "contexts": 0,
        }
    families = _mapping(cell.get("error_families"))
    return {
        **base,
        "measured": True,
        "gap": _driver_band(components["gap"]),
        "retention_due": bool(_mapping(cell.get("retention")).get("review_due")),
        "transfer_gap": _driver_band(components["transfer"]),
        "effort": str(_mapping(cell.get("effort")).get("level") or "none"),
        "assessment_confidence": str(
            _mapping(cell.get("assessment_confidence")).get("band") or ""
        ),
        "recent_failure": bool(list(_sequence(families.get("task")))),
        "novelty": _number(cell.get("novelty")) or 0.0,
        "contexts": _int(_mapping(cell.get("transfer")).get("context_count")),
    }

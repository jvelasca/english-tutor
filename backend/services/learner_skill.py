"""Learner Skill State 3.0: capacidad OBSERVADA por SKILL × DIMENSIÓN (V3.53 → V3.54).

V3.53 convirtió la dificultad OBSERVADA (el vector de la TAREA servida que el
ledger guarda en `learning_evidence.observed_difficulty`) en una capacidad por
dimensión. V3.53.1 cerró el P1-01: una sola dimensión ya no puede producir un
nivel CEFR global. Pero ese estado seguía COLAPSANDO las modalidades: tomaba el
máximo entre todas ellas por dimensión, de modo que una producción escrita B2
podía elevar el reto de una tarea ORAL que el alumno nunca ha producido.

    10|V3.54 (Student Skill State 3.0) conserva la modalidad como eje del estado:

- `observed_skill_capacity` — capacidad por SKILL canónico del ledger
  (`LEXICAL_SKILLS`: recall, written_production, spoken_production,
  spontaneous_use) y por dimensión. Es la FUENTE de verdad; ya no se pierde la
  modalidad que produjo la evidencia.
- `observed_capacity` — PROYECCIÓN legacy por dimensión (máximo entre skills) que
  V3.53 exponía y la caché de `learning_profile` conserva. Es un resumen
  DERIVADO para retrocompatibilidad, nunca la fuente de verdad.
    20|- `level_from_skill_capacity` — nivel CEFR EQUIVALENTE **por skill**: reutiliza
  la regla de V3.53.1 (cobertura dimensional COMPLETA de la envolvente del
  banco), así que sigue siendo imposible fabricar un CEFR global con evidencia
  parcial, ahora también en el eje de la modalidad.
- `skill_coverage` — cobertura dimensional observada por skill
  (`none`/`partial`/`full`): lo que el gate del Difficulty Engine necesita para
  no aplicar una subida parcial a una tarea multidimensional.
- `skill_capacity` — capacidad de reto por dimensión de UN skill, con su
  cobertura y las dimensiones cubiertas explícitas.

Muestra ESPACIADA: `OBSERVED_MIN_SAMPLES` éxitos en `OBSERVED_MIN_DAYS` días
    30|naturales distintos por (skill, dimensión), mismo rigor que
`independent_success_days`/`recall_rung_days`. Un acierto suelto no asciende.

Alternativas rechazadas (documentadas para que no se reintroduzcan):

- colapsar las modalidades en un único vector por dimensión (máximo entre
  skills): es el P1 que cierra V3.54 — una capacidad escrita elevaría el reto de
  una tarea oral;
- declarar un nivel global con cobertura dimensional parcial o con una dimensión
  sin muestra: sigue siendo el error que cerró V3.53.1 (P1-01);
- usar `observed_capacity` (proyección) como fuente de verdad: pierde la
  modalidad y reintroduciría el colapso;
    40|- reescribir `CEFR_CAPACITY`: es la tabla del BANCO (envelope monótono,
  recalibrado en V3.52.2), no una escala del alumno.

Módulo PURO: sin I/O, sin reloj, sin aleatoriedad. Nunca lanza.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from services import difficulty
from services.cefr import CEFR_LEVELS

# Muestra ESPACIADA mínima para que (skill, dimensión) declare capacidad
# observada: nº de éxitos y nº de días naturales distintos con ese éxito.
# Declarado y calibrable; mismo rigor que el resto de evidencias temporales.
OBSERVED_MIN_SAMPLES = 2
OBSERVED_MIN_DAYS = 2

# Cobertura dimensional observada de un skill (V3.54). `none` = sin ninguna
# dimensión con muestra; `partial` = alguna pero no todas; `full` = las cuatro
# dimensiones canónicas. Solo con `full` se declara un nivel CEFR por skill.
COVERAGE_NONE = "none"
COVERAGE_PARTIAL = "partial"
COVERAGE_FULL = "full"


def observed_skill_capacity(signals: object) -> dict[str, dict[str, int]]:
    """Capacidad observada por SKILL y dimensión desde el ledger (pura).

    `signals` es la salida de `services.evidence.observed_signals`
    (`observed_samples`/`observed_days`/`observed_capacity` por modalidad y
    dimensión). Devuelve `{skill: {dimension: carga}}` conservando la MODALIDAD:
    para cada (skill, dimensión) se toma la mayor carga superada si alcanza la
    muestra espaciada mínima; las que no la alcanzan no contribuyen (ni
    bloquean). Devuelve `{}` sin señales válidas. Nunca lanza.
    """
    data = signals if isinstance(signals, dict) else {}
    samples = data.get("observed_samples")
    days = data.get("observed_days")
    capacity = data.get("observed_capacity")
    if not all(isinstance(bucket, dict) for bucket in (samples, days, capacity)):
        return {}
    result: dict[str, dict[str, int]] = {}
    for skill, by_dimension in capacity.items():
        if not isinstance(by_dimension, dict):
            continue
        skill_samples = samples.get(skill)
        skill_days = days.get(skill)
        skill_samples = skill_samples if isinstance(skill_samples, dict) else {}
        skill_days = skill_days if isinstance(skill_days, dict) else {}
        bucket: dict[str, int] = {}
        for dimension, load in by_dimension.items():
            if dimension not in difficulty.DIFFICULTY_DIMENSIONS:
                continue
            try:
                measured = int(skill_samples.get(dimension, 0) or 0)
                distinct_days = int(skill_days.get(dimension, 0) or 0)
                value = int(load)
            except (TypeError, ValueError):
                continue
            if measured < OBSERVED_MIN_SAMPLES or distinct_days < OBSERVED_MIN_DAYS:
                continue
            if value > bucket.get(dimension, 0):
                bucket[dimension] = value
        if bucket:
            result[skill] = bucket
    return result


def normalize_skill_capacity(value: object) -> dict[str, dict[str, int]]:
    """Capacidad por skill × dimensión desde un Mapping o su JSON (pura).

    Acepta el `Mapping` ya construido o el texto JSON con el que `domain.profile`
    lo cachea en `learning_profile.observed_skill_capacity`. Normaliza cada
    vector a las dimensiones canónicas (1..5) y descarta skills sin ninguna
    dimensión válida. Devuelve `{}` con entradas vacías o basura. Nunca lanza.
    """
    data = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return {}
    if not isinstance(data, Mapping):
        return {}
    result: dict[str, dict[str, int]] = {}
    for skill, by_dimension in data.items():
        normalized = difficulty.normalize_vector(by_dimension)
        if normalized:
            result[str(skill)] = normalized
    return result


def _flatten(nested: object) -> dict[str, int]:
    """Proyección legacy {dimensión: carga}: máximo entre skills (pura)."""
    if not isinstance(nested, Mapping):
        return {}
    result: dict[str, int] = {}
    for by_dimension in nested.values():
        normalized = difficulty.normalize_vector(by_dimension)
        for dimension, load in normalized.items():
            if load > result.get(dimension, 0):
                result[dimension] = load
    return result


def observed_capacity(signals: object) -> dict[str, int]:
    """PROYECCIÓN legacy por dimensión de la capacidad observada (pura).

    Resumen DERIVADO (máximo entre modalidades) que V3.53 exponía y la caché
    conserva por retrocompatibilidad: la fuente de verdad de V3.54 es
    `observed_skill_capacity`, que NO colapsa la modalidad. Devuelve `{}` sin
    señales válidas. Nunca lanza.
    """
    return _flatten(observed_skill_capacity(signals))


def _level_from_normalized(capacity: dict[str, int]) -> str:
    """Mayor nivel cuya envolvente queda dominada en TODAS sus dimensiones.

    Recorre las dimensiones que exige el NIVEL candidato (no las observadas), así
    que una dimensión sin muestra cuenta 0 y BLOQUEA la etiqueta (V3.53.1,
    P1-01). `capacity` debe venir ya normalizado. Nunca lanza.
    """
    if not capacity:
        return ""
    best = ""
    for level in CEFR_LEVELS:
        target = difficulty.capacity_for(level)
        if not target:
            continue
        if all(
            capacity.get(dimension, 0) >= load
            for dimension, load in target.items()
        ):
            best = level
    return best


def level_from_capacity(observed: object) -> str:
    """Nivel CEFR EQUIVALENTE de una capacidad observada por dimensión (pura).

    Resumen DERIVADO con COBERTURA DIMENSIONAL COMPLETA: sin muestra, o con
    cobertura parcial, devuelve `""` (no se inventa nivel). Se conserva como
    fachada de la proyección legacy; la versión por skill es
    `level_from_skill_capacity`. Nunca lanza.
    """
    return _level_from_normalized(difficulty.normalize_vector(observed))


def level_from_skill_capacity(observed_skill_capacity: object) -> dict[str, str]:
    """Nivel CEFR EQUIVALENTE por SKILL (pura).

    Aplica la regla de V3.53.1 a cada modalidad por separado: solo declara nivel
    el skill con cobertura dimensional COMPLETA de la envolvente del banco. Una
    modalidad sin muestra (o con cobertura parcial) devuelve `""`, de modo que la
    capacidad escrita no puede fabricar un nivel oral. Devuelve una entrada por
    skill presente (nunca omite claves, para que el consumidor no tenga que
    distinguir «sin nivel» de «skill desconocido»). Nunca lanza.
    """
    nested = (
        observed_skill_capacity
        if isinstance(observed_skill_capacity, Mapping)
        else {}
    )
    return {
        str(skill): _level_from_normalized(difficulty.normalize_vector(by_dimension))
        for skill, by_dimension in nested.items()
    }


def _coverage_of(normalized: Mapping) -> str:
    """Cobertura dimensional de un vector ya normalizado (pura)."""
    measured = len(normalized)
    if measured <= 0:
        return COVERAGE_NONE
    if measured >= len(difficulty.DIFFICULTY_DIMENSIONS):
        return COVERAGE_FULL
    return COVERAGE_PARTIAL


def skill_coverage(observed_skill_capacity: object) -> dict[str, str]:
    """Cobertura dimensional observada por skill (V3.54, pura).

    `none` sin dimensiones con muestra, `full` con las cuatro canónicas y
    `partial` con alguna pero no todas. Es lo que el gate del Difficulty Engine
    lee para no aplicar una subida parcial a una tarea multidimensional. Nunca
    lanza.
    """
    nested = (
        observed_skill_capacity
        if isinstance(observed_skill_capacity, Mapping)
        else {}
    )
    return {
        str(skill): _coverage_of(difficulty.normalize_vector(by_dimension))
        for skill, by_dimension in nested.items()
    }


def learner_capacity(floor_level: object, observed: object) -> dict[str, int]:
    """Suelo de reto efectivo por dimensión: max(nivel, observado) (pura).

    Máximo por dimensión entre la capacidad del nivel de suelo declarado
    (`floor_level`, ver `student_state.floor_level`) y la capacidad observada
    (proyección legacy o vector). Sube el reto SOLO en las dimensiones con
    evidencia y nunca baja el suelo declarado. `{}` si ninguna de las dos fuentes
    aporta dimensiones (el Difficulty Engine entonces no filtra). Nunca lanza.
    """
    base = difficulty.capacity_for(floor_level)
    override = difficulty.normalize_vector(observed)
    if not base and not override:
        return {}
    return {
        dimension: max(base.get(dimension, 0), override.get(dimension, 0))
        for dimension in difficulty.DIFFICULTY_DIMENSIONS
        if dimension in base or dimension in override
    }


def skill_capacity(
    floor_level: object,
    observed_skill_capacity: object,
    skill: object,
) -> dict[str, object]:
    """Capacidad de reto por dimensión de UN skill, con su cobertura (pura).

    Devuelve `{capacity, coverage, covered_dimensions}`:

    - `capacity` — `max(capacity_for(floor_level)[d], observado[skill][d])` por
      dimensión (`{}` si ninguna fuente aporta dimensiones);
    - `coverage` — `none`/`partial`/`full` del skill (ver `skill_coverage`);
    - `covered_dimensions` — dimensiones del skill con muestra ESPACIADA, en
      orden canónico. El gate del Difficulty Engine solo aplica la subida a las
      tareas cuyas dimensiones son SUBCONJUNTO de este conjunto.

    Un skill sin muestra conserva la capacidad del suelo declarado (nunca baja el
    suelo) pero su cobertura es `none`: el gate no eleva nada por él. Nunca lanza.
    """
    nested = (
        observed_skill_capacity
        if isinstance(observed_skill_capacity, Mapping)
        else {}
    )
    key = str(skill or "")
    declared = nested.get(key)
    if declared is None and key:
        # Tolerancia a claves no canónicas (p. ej. mayúsculas) sin inventar datos.
        declared = nested.get(key.strip().lower())
    observed = difficulty.normalize_vector(declared)
    base = difficulty.capacity_for(floor_level)
    capacity = {
        dimension: max(base.get(dimension, 0), observed.get(dimension, 0))
        for dimension in difficulty.DIFFICULTY_DIMENSIONS
        if dimension in base or dimension in observed
    }
    return {
        "capacity": capacity,
        "coverage": _coverage_of(observed),
        "covered_dimensions": [
            dimension
            for dimension in difficulty.DIFFICULTY_DIMENSIONS
            if dimension in observed
        ],
    }


def observed_skill_state(signals: object) -> dict[str, object]:
    """Estado observado por skill × dimensión, cacheable (V3.54, pura).

    Devuelve `{observed_skill_capacity, observed_skill_level, skill_coverage,
    observed_level, observed_capacity}`: la capacidad por modalidad y dimensión
    (fuente de verdad), su nivel CEFR por skill, la cobertura y la proyección
    legacy por dimensión (nivel equivalente incluido). Es lo que `domain.profile`
    persiste en `learning_profile`. Nunca lanza.
    """
    nested = observed_skill_capacity(signals)
    flat = _flatten(nested)
    return {
        "observed_skill_capacity": nested,
        "observed_skill_level": level_from_skill_capacity(nested),
        "skill_coverage": skill_coverage(nested),
        "observed_level": _level_from_normalized(flat),
        "observed_capacity": flat,
    }


def observed_state(signals: object) -> dict[str, object]:
    """Estado observado legacy de V3.53: nivel y capacidad por dimensión (pura).

    Fachada estable que solo expone `{observed_level, observed_capacity}` (la
    proyección por dimensión). Se conserva para los llamadores históricos; el
    estado nuevo por skill es `observed_skill_state`. Nunca lanza.
    """
    state = observed_skill_state(signals)
    return {
        "observed_level": state["observed_level"],
        "observed_capacity": state["observed_capacity"],
    }


def empty_state() -> dict[str, object]:
    """Estado observado neutro (sin muestra). Dict nuevo en cada llamada."""
    return {
        "observed_skill_capacity": {},
        "observed_skill_level": {},
        "skill_coverage": {},
        "observed_level": "",
        "observed_capacity": {},
    }

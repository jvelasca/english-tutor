"""Learner Skill State 2.0: capacidad OBSERVADA por dimensión (V3.53).

V3.52 formalizó el estado del alumno como un NIVEL CEFR con su fuente
(`practice`/`estimated`/`demonstrated`, ver `services.student_state`), pero ese
nivel es una etiqueta GLOBAL: no puede representar a un alumno B1 global con
`lexical` B2 y `syntax` A2, ni reconocer que ha SUPERADO tareas exigentes de una
dimensión concreta. El suelo de dificultad seguía siendo «lo que dice el nivel»,
no «lo que la evidencia demuestra».

Este módulo puro convierte la evidencia de dificultad OBSERVADA (que V3.53
persiste por evento en `learning_evidence.observed_difficulty`, un vector de la
TAREA servida) en una capacidad por dimensión:

- `observed_capacity` — carga máxima superada por dimensión, exigiendo MUESTRA
  ESPACIADA (`OBSERVED_MIN_SAMPLES` éxitos en `OBSERVED_MIN_DAYS` días naturales
  distintos): un acierto suelto no asciende, mismo rigor que
  `independent_success_days`/`recall_rung_days`. Se toma el máximo entre las
  modalidades que cumplen, así que no se inventa capacidad donde no hay muestra.
- `level_from_capacity` — nivel CEFR EQUIVALENTE: el mayor cuya envolvente del
  banco (`services.difficulty.CEFR_CAPACITY`) queda DOMINADA por la capacidad
  observada en las dimensiones CON muestra. Una dimensión sin muestra no bloquea
  (no se sabe nada de ella), pero tampoco asciende: la función es conservadora
  por construcción.
- `learner_capacity` — SUELO efectivo por dimensión para el Difficulty Engine:
  el máximo entre la capacidad del nivel de suelo declarado y la observada. Sube
  el reto solo donde hay evidencia y NUNCA baja el suelo declarado.

Alternativas rechazadas (documentadas para que no se reintroduzcan):

- persistir una media escalar del vector: colapsaría las dimensiones, el P1 que
  cerraron V3.52/V3.52.2;
- ascender con un solo éxito o con dos el mismo día: confunde volumen con
  retención (premisa del ledger longitudinal);
- reescribir `CEFR_CAPACITY`: es la tabla del BANCO (envelope monótono,
  recalibrado en V3.52.2), no una escala del alumno.

Módulo PURO: sin I/O, sin reloj, sin aleatoriedad. Nunca lanza.
"""

from __future__ import annotations

from services import difficulty
from services.cefr import CEFR_LEVELS

# Muestra ESPACIADA mínima para que una dimensión declare capacidad observada:
# nº de éxitos y nº de días naturales distintos con ese éxito. Declarado y
# calibrable; mismo rigor que el resto de evidencias temporales del proyecto.
OBSERVED_MIN_SAMPLES = 2
OBSERVED_MIN_DAYS = 2


def observed_capacity(signals: object) -> dict[str, int]:
    """Capacidad observada por dimensión desde las señales del ledger (pura).

    `signals` es la salida de `services.evidence.observed_signals`
    (`observed_samples`/`observed_days`/`observed_capacity` por modalidad y
    dimensión). Para cada dimensión se toma la MAYOR carga superada entre las
    modalidades que alcanzan la muestra espaciada mínima; las que no la alcanzan
    no contribuyen (ni bloquean). Devuelve `{}` sin señales válidas. Nunca lanza.
    """
    data = signals if isinstance(signals, dict) else {}
    samples = data.get("observed_samples")
    days = data.get("observed_days")
    capacity = data.get("observed_capacity")
    if not all(isinstance(bucket, dict) for bucket in (samples, days, capacity)):
        return {}
    result: dict[str, int] = {}
    for skill, by_dimension in capacity.items():
        if not isinstance(by_dimension, dict):
            continue
        skill_samples = samples.get(skill)
        skill_days = days.get(skill)
        skill_samples = skill_samples if isinstance(skill_samples, dict) else {}
        skill_days = skill_days if isinstance(skill_days, dict) else {}
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
            if value > result.get(dimension, 0):
                result[dimension] = value
    return result


def level_from_capacity(observed: object) -> str:
    """Nivel CEFR EQUIVALENTE de una capacidad observada por dimensión (pura).

    Devuelve el mayor nivel cuya `CEFR_CAPACITY` (envolvente del banco) queda
    dominada por `observed` en las dimensiones CON muestra. Las dimensiones sin
    muestra no bloquean (no hay señal que las contradiga) pero tampoco ascienden:
    sin ninguna muestra devuelve `""` (no se inventa nivel). Nunca lanza.
    """
    capacity = difficulty.normalize_vector(observed)
    if not capacity:
        return ""
    best = ""
    for level in CEFR_LEVELS:
        target = difficulty.capacity_for(level)
        if not target:
            continue
        dominated = all(
            capacity[dimension] >= target[dimension]
            for dimension in capacity
            if dimension in target
        )
        if dominated:
            best = level
    return best


def learner_capacity(floor_level: object, observed: object) -> dict[str, int]:
    """Suelo de reto efectivo por dimensión: max(nivel, observado) (pura).

    Máximo por dimensión entre la capacidad del nivel de suelo declarado
    (`floor_level`, ver `student_state.floor_level`) y la capacidad observada.
    Sube el reto SOLO en las dimensiones con evidencia y nunca baja el suelo
    declarado. `{}` si ninguna de las dos fuentes aporta dimensiones (el
    Difficulty Engine entonces no filtra). Nunca lanza.
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


def observed_state(signals: object) -> dict[str, object]:
    """Estado observado cacheable: nivel equivalente y capacidad (V3.53, pura).

    Devuelve `{observed_level, observed_capacity}` con la capacidad por dimensión
    y su nivel CEFR equivalente. Es lo que `domain.profile` persiste en
    `learning_profile` para que el drill lo lea en O(1). Nunca lanza.
    """
    capacity = observed_capacity(signals)
    return {
        "observed_level": level_from_capacity(capacity),
        "observed_capacity": capacity,
    }


def empty_state() -> dict[str, object]:
    """Estado observado neutro (sin muestra). Dict nuevo en cada llamada."""
    return {"observed_level": "", "observed_capacity": {}}

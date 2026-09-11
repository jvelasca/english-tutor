"""Difficulty Engine 2.0: encaje de dificultad por DIMENSIÓN (V3.52).

V3.50/V3.51 emparejaban la dificultad con un ESCALAR: comparaban el ordinal CEFR
(0..5) y la media del `difficulty_vector` (1..6) en una misma escala y colapsaban
las cuatro dimensiones del vector antes de decidir. La auditoría externa de V3.51
lo señaló como P1: un contexto ``(5,1,5,1)`` y otro ``(3,3,3,3)`` tienen la misma
media y resultaban indistinguibles, de modo que el suelo de dificultad no podía
razonar sobre QUÉ dimensión exigía el contexto.

Este módulo sustituye ese escalar por una comparación VECTOR contra VECTOR:

- `CEFR_CAPACITY` declara la capacidad de reto de cada nivel CEFR por dimensión
  (1..5), calibrada con la distribución real del banco de transferencia (en A1–B1
  la `interaction` va por detrás del resto). Es una tabla DECLARATIVA y
  calibrable, no un modelo aprendido.
- `challenge_vector(item_level, learner_level)` da el reto objetivo como el
  MÁXIMO por dimensión entre la capacidad del ítem (techo lingüístico: hasta
  dónde llega el contenido) y la del alumno (suelo de reto: lo que ya domina).
  Generaliza el `max(item_index, learner_index)` de V3.51 SIN mezclar escalas.
- `fit(context_vector, challenge)` mide la DISTANCIA por dimensión y el mayor
  exceso (`overshoot`) sobre el reto objetivo.
- `select_by_difficulty(pool, challenge, tolerance)` conserva los contextos que
  no se pasan del reto (`within`) y, entre ellos, los de MENOR distancia; si
  ninguno encaja, degrada a los de menor distancia del pool completo. Nunca deja
  el pool vacío y nunca sirve el más difícil «por defecto».

Módulo PURO: sin I/O, sin reloj, sin aleatoriedad. Nunca lanza.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# Dimensiones canónicas de carga del contexto. Es el vocabulario que ya usan
# listening/speaking y el `difficulty_vector` del banco de transferencia; en
# V3.52 pasa a ser la ÚNICA fuente (transfer lo consume como alias).
DIFFICULTY_DIMENSIONS: tuple[str, ...] = (
    "lexical",
    "syntax",
    "discourse",
    "interaction",
)

_MIN_LOAD = 1
_MAX_LOAD = 5

# Capacidad de reto DECLARADA por nivel CEFR y dimensión (1..5). Monótona no
# decreciente por dimensión: un nivel superior nunca tiene menos capacidad. La
# `interaction` crece más despacio en A1–B1 (por detrás de léxico/sintaxis),
# fiel a la distribución del banco: los contextos dialogados sencillos no suben
# la exigencia interactiva al mismo ritmo que la carga léxica. Calibrable.
CEFR_CAPACITY: dict[str, dict[str, int]] = {
    "A1": {"lexical": 1, "syntax": 1, "discourse": 1, "interaction": 1},
    "A2": {"lexical": 2, "syntax": 2, "discourse": 2, "interaction": 1},
    "B1": {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 2},
    "B2": {"lexical": 4, "syntax": 4, "discourse": 4, "interaction": 3},
    "C1": {"lexical": 5, "syntax": 5, "discourse": 5, "interaction": 4},
    "C2": {"lexical": 5, "syntax": 5, "discourse": 5, "interaction": 5},
}

# Tolerancia de EXCESO (`overshoot`) admisible sobre la capacidad de reto.
# `DIFFICULTY_TOLERANCE` se aplica cuando el suelo procede de un nivel
# DEMOSTRADO (certificación: máxima confianza, margen estricto);
# `DIFFICULTY_TOLERANCE_ESTIMATED` cuando procede de un nivel estimado o
# declarado (proxy: menos confianza, más margen). Declaradas y calibrables.
DIFFICULTY_TOLERANCE = 1
DIFFICULTY_TOLERANCE_ESTIMATED = 2

_CAPACITY_BY_LEVEL: dict[str, dict[str, int]] = {
    level.strip().upper(): dict(vector)
    for level, vector in CEFR_CAPACITY.items()
}

_EMPTY_FIT: dict[str, object] = {
    "dimensions": 0,
    "distance": 0,
    "max_overshoot": 0,
    "within": True,
}


def _as_load(value: object) -> int | None:
    """Carga válida 1..5 de una dimensión (None si no es un número útil)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(_MIN_LOAD, min(_MAX_LOAD, int(value)))


def normalize_vector(vector: object) -> dict[str, int]:
    """Vector de carga restringido a las dimensiones canónicas (V3.52, pura).

    Ignora claves desconocidas, valores no numéricos y fuera de rango (los
    recorta a 1..5). Devuelve `{}` si no queda ninguna dimensión válida. Nunca
    lanza.
    """
    if not isinstance(vector, Mapping):
        return {}
    normalized: dict[str, int] = {}
    for dimension in DIFFICULTY_DIMENSIONS:
        load = _as_load(vector.get(dimension))
        if load is not None:
            normalized[dimension] = load
    return normalized


def normalize_level(level: object) -> str:
    """Nivel CEFR canónico en mayúsculas ("" si no está en la tabla) (pura)."""
    text = str(level or "").strip().upper()
    return text if text in _CAPACITY_BY_LEVEL else ""


def capacity_for(level: object) -> dict[str, int]:
    """Capacidad de reto declarada de un nivel CEFR (V3.52, pura).

    Devuelve una copia (el llamador no puede mutar la tabla) o `{}` si el nivel
    no se reconoce: sin nivel no se inventa capacidad. Nunca lanza.
    """
    capacity = _CAPACITY_BY_LEVEL.get(normalize_level(level))
    return dict(capacity) if capacity else {}


def challenge_vector(item_level: object, learner_level: object) -> dict[str, int]:
    """Reto objetivo por dimensión: máximo entre ítem y alumno (V3.52, pura).

    El ítem aporta el TECHO lingüístico (el contenido llega hasta donde llega) y
    el alumno el SUELO de reto (lo que ya domina). Se toma el MÁXIMO por
    dimensión, sin colapsar el vector: un `(5,1,5,1)` y un `(3,3,3,3)` dejan de
    ser indistinguibles. Devuelve `{}` si no se reconoce ningún nivel (el
    llamador entonces no filtra). Nunca lanza.
    """
    item_capacity = capacity_for(item_level)
    learner_capacity = capacity_for(learner_level)
    if not item_capacity and not learner_capacity:
        return {}
    return {
        dimension: max(
            item_capacity.get(dimension, 0),
            learner_capacity.get(dimension, 0),
        )
        for dimension in DIFFICULTY_DIMENSIONS
        if dimension in item_capacity or dimension in learner_capacity
    }


def fit(
    context_vector: object,
    challenge: object,
    *,
    tolerance: int = DIFFICULTY_TOLERANCE,
) -> dict[str, object]:
    """Encaje dimensión a dimensión de un contexto contra el reto (V3.52, pura).

    Devuelve `{dimensions, distance, max_overshoot, within}`:

    - `dimensions` — nº de dimensiones comparadas (las presentes en AMBOS
      vectores);
    - `distance` — suma de las distancias ABSOLUTAS por dimensión (0 = encaje
      perfecto). Es el criterio de «más cercano» del selector;
    - `max_overshoot` — mayor exceso de la carga del contexto sobre la capacidad
      de reto (0 si el contexto no supera el reto en ninguna dimensión);
    - `within` — `max_overshoot <= tolerance` (el contexto no se pasa del reto
      más de lo admitido).

    Con vectores vacíos el encaje es vacuo: `dimensions=0`, `distance=0`,
    `within=True`. Nunca lanza.
    """
    context = normalize_vector(context_vector)
    target = normalize_vector(challenge)
    dimensions = [
        dimension
        for dimension in DIFFICULTY_DIMENSIONS
        if dimension in context and dimension in target
    ]
    if not dimensions:
        return dict(_EMPTY_FIT)
    distance = 0
    max_overshoot = 0
    for dimension in dimensions:
        delta = context[dimension] - target[dimension]
        distance += abs(delta)
        if delta > max_overshoot:
            max_overshoot = delta
    return {
        "dimensions": len(dimensions),
        "distance": distance,
        "max_overshoot": max_overshoot,
        "within": max_overshoot <= max(0, int(tolerance)),
    }


def _context_vector(context: object) -> object:
    """`difficulty_vector` de un contexto del banco (o el propio dict) (pura)."""
    if isinstance(context, Mapping):
        vector = context.get("difficulty_vector")
        return vector if isinstance(vector, Mapping) else context
    return {}


def select_by_difficulty(
    pool: Iterable[dict],
    challenge: object,
    *,
    tolerance: int = DIFFICULTY_TOLERANCE,
) -> list[dict]:
    """Contextos más cercanos al reto sin pasarse de la tolerancia (V3.52, pura).

    Conserva los contextos `within` (no exceden el reto más de `tolerance`) y,
    entre ellos, los de MENOR `distance`; si NINGUNO está `within`, degrada a los
    de menor `distance` de todo el pool (el más cercano posible, nunca el más
    difícil por defecto). Nunca deja el pool vacío: sin reto reconocible o sin
    pool devuelve el pool intacto. Determinista: preserva el orden de entrada.
    Nunca lanza.
    """
    contexts = list(pool)
    target = normalize_vector(challenge)
    if not contexts or not target:
        return contexts
    results = [
        fit(_context_vector(context), target, tolerance=tolerance)
        for context in contexts
    ]
    within = {index for index, result in enumerate(results) if result["within"]}
    best = min(
        results[index]["distance"]
        for index in range(len(contexts))
        if not within or index in within
    )
    return [
        context
        for index, context in enumerate(contexts)
        if results[index]["distance"] == best
        and (not within or index in within)
    ]


def tolerance_for(source: object) -> int:
    """Tolerancia según la FUENTE del suelo de dificultad (V3.52, pura).

    Solo un nivel DEMOSTRADO (certificación formal) usa el margen estricto; un
    nivel estimado, declarado o ausente usa el margen amplio. Es deliberadamente
    conservador: ante la duda, más margen en lugar de más exigencia. Nunca lanza.
    """
    text = str(source or "").strip().lower()
    if text == "demonstrated":
        return DIFFICULTY_TOLERANCE
    return DIFFICULTY_TOLERANCE_ESTIMATED

"""Difficulty Engine 2.0: encaje de dificultad por DIMENSIÓN (V3.52).

V3.50/V3.51 emparejaban la dificultad con un ESCALAR: comparaban el ordinal CEFR
(0..5) y la media del `difficulty_vector` (1..6) en una misma escala y colapsaban
las cuatro dimensiones del vector antes de decidir. La auditoría externa de V3.51
lo señaló como P1: un contexto ``(5,1,5,1)`` y otro ``(3,3,3,3)`` tienen la misma
media y resultaban indistinguibles, de modo que el suelo de dificultad no podía
razonar sobre QUÉ dimensión exigía el contexto.

Este módulo sustituye ese escalar por una comparación VECTOR contra VECTOR:

- `CEFR_CAPACITY` declara la carga máxima que el banco de transferencia usa en
  cada nivel CEFR por dimensión (1..5): es el ENVELOPE monótono de los
  `difficulty_vector` reales del banco, verificado por test
  (`test_capacity_is_the_monotone_envelope_of_the_bank`) para que tabla y banco
  no puedan divergir en silencio. La envolvente (y no el máximo del nivel a
  secas) es lo que la hace monótona no decreciente por dimensión aunque un nivel
  tenga un contexto puntual más plano que el anterior (B1 declara `interaction`
  2 y A2 tiene contextos con 3). Es una calibración del BANCO, no una escala
  CEFR normativa: la tabla describe lo que el contenido exige, no lo que «debería»
  exigir.
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

# Carga máxima que el banco de transferencia usa por nivel y dimensión (1..5).
# Es el ENVELOPE MONÓTONO de los `difficulty_vector` reales del banco: por
# dimensión, `CEFR_CAPACITY[nivel]` = máximo del banco hasta ese nivel inclusive.
# Monótona no decreciente por dimensión POR CONSTRUCCIÓN, aunque un nivel
# concreto sea más plano que el anterior (B1 declara `interaction` 2 y A2 tiene
# contextos con 3: la envolvente sube a 2 y B1 queda en 3). Un test
# (`test_capacity_is_the_monotone_envelope_of_the_bank`) recalcula la envolvente
# desde `TRANSFER_CONTEXTS` y falla si la tabla se desvía: fue el P2-01 de la
# auditoría Q de V3.52.1 (la tabla declarada se quedaba corta en la `interaction`
# de A1/A2 y larga en el léxico/sintaxis de B2/C1, y con la tolerancia estricta
# excluía contextos del propio nivel). Calibración del BANCO, no escala CEFR.
CEFR_CAPACITY: dict[str, dict[str, int]] = {
    "A1": {"lexical": 1, "syntax": 1, "discourse": 2, "interaction": 2},
    "A2": {"lexical": 2, "syntax": 2, "discourse": 2, "interaction": 3},
    "B1": {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3},
    "B2": {"lexical": 3, "syntax": 3, "discourse": 4, "interaction": 3},
    "C1": {"lexical": 4, "syntax": 5, "discourse": 5, "interaction": 5},
    "C2": {"lexical": 5, "syntax": 5, "discourse": 5, "interaction": 5},
}

# Tolerancia de EXCESO (`overshoot`) admisible sobre la capacidad de reto.
# `DIFFICULTY_TOLERANCE` se aplica cuando el suelo procede de un nivel
# DEMOSTRADO (certificación: máxima confianza) y
# `DIFFICULTY_TOLERANCE_ESTIMATED` cuando procede de un nivel estimado o
# declarado (proxy: menos confianza). Ojo con la intuición: un margen MAYOR no
# es «más conservador» en el sentido de exigir menos — admite más `overshoot`, es
# decir deja entrar contextos que EXCEDEN el reto (más exigencia). Ambos son una
# RED DE SEGURIDAD para bancos que declaren cargas por encima de la envolvente:
# sobre el banco actual ningún contexto de un nivel supera `CEFR_CAPACITY` de su
# nivel, así que la tolerancia no cambia hoy ninguna selección (lo fija
# `test_tolerance_bites_only_when_a_context_declares_above_the_envelope`).
DIFFICULTY_TOLERANCE = 1
DIFFICULTY_TOLERANCE_ESTIMATED = 2

_CAPACITY_BY_LEVEL: dict[str, dict[str, int]] = {
    level.strip().upper(): dict(vector)
    for level, vector in CEFR_CAPACITY.items()
}


def _empty_fit(expected: int) -> dict[str, object]:
    """Encaje sin dimensiones comparadas (V3.52.1, pura).

    `within` solo es True si NO había reto que comparar (`expected == 0`): un
    reto vacío no filtra y el encaje es vacuo. Con un reto declarado y NINGUNA
    dimensión común la cobertura es 0 y NO se considera encaje: antes se
    devolvía un `within=True` «perfecto» que premiaba a los contextos que no
    declaran `difficulty_vector`.
    """
    return {
        "dimensions": 0,
        "dimensions_compared": 0,
        "dimensions_expected": expected,
        "coverage": 1.0 if expected == 0 else 0.0,
        "distance": 0,
        "max_overshoot": 0,
        "within": expected == 0,
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

    Devuelve `{dimensions, dimensions_compared, dimensions_expected, coverage,
    distance, max_overshoot, within}`:

    - `dimensions_expected` — nº de dimensiones que declara el RETO;
    - `dimensions_compared` — nº de dimensiones presentes en AMBOS vectores
      (`dimensions` se conserva como alias por compatibilidad);
    - `coverage` — `dimensions_compared / dimensions_expected` (1.0 si no hay
      reto). Una cobertura < 1 significa que el contexto declara MENOS
      dimensiones que el reto y por tanto no es comparable del todo;
    - `distance` — suma de las distancias ABSOLUTAS por dimensión (0 = encaje
      perfecto). Es el criterio de «más cercano» del selector;
    - `max_overshoot` — mayor exceso de la carga del contexto sobre la capacidad
      de reto (0 si el contexto no supera el reto en ninguna dimensión);
    - `within` — cobertura COMPLETA (`compared == expected`) y
      `max_overshoot <= tolerance`.

    V3.52.1 (P1-01 de la auditoría): antes se comparaban solo las dimensiones
    comunes y una intersección vacía devolvía un `within=True` «perfecto», de
    modo que un contexto SIN `difficulty_vector` (o con vector parcial) ganaba
    la selección con `distance=0`. Ahora un reto declarado exige cobertura
    completa para considerarse `within`; solo un reto VACÍO (`expected == 0`)
    deja el encaje vacuo con `within=True`. Nunca lanza.
    """
    context = normalize_vector(context_vector)
    target = normalize_vector(challenge)
    expected = len(target)
    dimensions = [
        dimension
        for dimension in DIFFICULTY_DIMENSIONS
        if dimension in context and dimension in target
    ]
    if not dimensions:
        return _empty_fit(expected)
    distance = 0
    max_overshoot = 0
    for dimension in dimensions:
        delta = context[dimension] - target[dimension]
        distance += abs(delta)
        if delta > max_overshoot:
            max_overshoot = delta
    compared = len(dimensions)
    return {
        "dimensions": compared,
        "dimensions_compared": compared,
        "dimensions_expected": expected,
        "coverage": compared / expected if expected else 1.0,
        "distance": distance,
        "max_overshoot": max_overshoot,
        "within": compared == expected
        and max_overshoot <= max(0, int(tolerance)),
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

    Conserva los contextos `within` (cobertura dimensional completa y sin
    exceder el reto más de `tolerance`) y, entre ellos, los de MENOR `distance`;
    si NINGUNO está `within`, degrada primero por MAYOR cobertura y luego por
    menor `distance` (V3.52.1: antes bastaba la distancia, así que un contexto
    sin `difficulty_vector` ganaba con `distance=0`). Nunca deja el pool vacío:
    sin reto reconocible o sin pool devuelve el pool intacto. Determinista:
    preserva el orden de entrada. Nunca lanza.
    """
    contexts = list(pool)
    target = normalize_vector(challenge)
    if not contexts or not target:
        return contexts
    results = [
        fit(_context_vector(context), target, tolerance=tolerance)
        for context in contexts
    ]
    within = [index for index, result in enumerate(results) if result["within"]]
    if within:
        best = min(results[index]["distance"] for index in within)
        return [
            context
            for index, context in enumerate(contexts)
            if index in within and results[index]["distance"] == best
        ]
    # Nadie encaja: degradar por cobertura completa y, a igualdad, por cercanía.
    best_coverage = max(result["coverage"] for result in results)
    candidates = [
        index
        for index, result in enumerate(results)
        if result["coverage"] == best_coverage
    ]
    best_distance = min(results[index]["distance"] for index in candidates)
    return [
        context
        for index, context in enumerate(contexts)
        if index in candidates and results[index]["distance"] == best_distance
    ]


def tolerance_for(source: object) -> int:
    """Tolerancia según la FUENTE del suelo de dificultad (V3.52, pura).

    Solo un nivel DEMOSTRADO (certificación formal) usa el margen estricto; un
    nivel estimado, declarado o ausente usa el margen amplio. Un margen mayor
    admite más `overshoot` (contextos que exceden el reto), así que la tolerancia
    estricta es la que MENOS exceso deja pasar: al certificar se pide que el
    contexto no se pase del reto objetivo más de `DIFFICULTY_TOLERANCE`. Sobre el
    banco actual (envolvente monótona, ningún contexto supera la capacidad de su
    nivel) la tolerancia no cambia ninguna selección: es una red de seguridad
    para bancos que declaren cargas por encima de la envolvente. Nunca lanza.
    """
    text = str(source or "").strip().lower()
    if text == "demonstrated":
        return DIFFICULTY_TOLERANCE
    return DIFFICULTY_TOLERANCE_ESTIMATED

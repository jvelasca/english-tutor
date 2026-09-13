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
- `challenge_for(context_vector, challenge, covered_dimensions, floor_challenge)`
  (V3.54) resuelve el reto aplicable a UN contexto: la subida observada solo
  vale si las dimensiones que el contexto declara son SUBCONJUNTO de las
  dimensiones observadas; si no, el contexto se evalúa contra el suelo declarado.
- `select_by_difficulty(pool, challenge, tolerance, covered_dimensions,
  floor_challenge)` conserva los contextos que
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
# concreto sea más plano que el anterior (A2 tiene contextos con `interaction`
# 3 y la envolvente sube con el nivel, no con el ordinal: la tabla es la del
# contenido real, no una escala CEFR). Un test
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


# Separador de la serialización canónica de un vector de carga (V3.53). Es un
# detalle de FORMATO del ledger, no del algoritmo: `format_vector`/`parse_vector`
# son inversas y el vocabulario de dimensiones sigue siendo el único canónico.
_VECTOR_SEPARATOR = ","


def format_vector(vector: object) -> str:
    """Serializa un vector de carga a texto canónico (V3.53, pura).

    Formato `dim:load,dim:load` en el ORDEN de `DIFFICULTY_DIMENSIONS` y solo
    con las dimensiones presentes (normalizadas a 1..5). Sirve para persistir la
    dificultad de la TAREA servida en el ledger sin colapsar el vector a una
    media escalar (el P1 que cerraron V3.52/V3.52.2). Un vector vacío o inválido
    se serializa como `""` = dificultad NO declarada. Nunca lanza.
    """
    normalized = normalize_vector(vector)
    return _VECTOR_SEPARATOR.join(
        f"{dimension}:{normalized[dimension]}"
        for dimension in DIFFICULTY_DIMENSIONS
        if dimension in normalized
    )


def parse_vector(text: object) -> dict[str, int]:
    """Vector de carga desde su serialización canónica (V3.53, pura).

    Inversa de `format_vector`. Tolerante a propósito (filas legacy y datos
    externos): ignora pares mal formados, claves fuera del vocabulario y cargas
    fuera de 1..5, y devuelve `{}` con entradas vacías o basura. Acepta también
    un `Mapping` por comodidad (`normalize_vector`). Nunca lanza.
    """
    if isinstance(text, Mapping):
        return normalize_vector(text)
    raw = str(text or "")
    if not raw.strip():
        return {}
    parsed: dict[str, int] = {}
    for part in raw.split(_VECTOR_SEPARATOR):
        key, separator, value = part.partition(":")
        if not separator:
            continue
        dimension = key.strip().lower()
        if dimension not in DIFFICULTY_DIMENSIONS:
            continue
        try:
            numeric = float(value.strip())
        except (TypeError, ValueError):
            continue
        load = _as_load(numeric)
        if load is not None:
            parsed[dimension] = load
    return parsed


# ---------------------------------------------------------------------------
# V3.55 (Task Difficulty 3.0): las TRES dificultades de un evento.
#
# Hasta V3.54 el ledger guardaba UNA: `observed_difficulty` (V3.53), que en
# realidad contenía la dificultad de la tarea SERVIDA — el vector del contexto
# que el alumno tenía delante, no la carga que había SUPERADO — y solo la
# escribía el drill de Transfer. El P2-01 de la auditoría de V3.53.1 pidió
# desdoblar esa señal en tres, con nombres honestos:
#
#   declared  — lo que DECLARA el ítem o la actividad por diseño (el CEFR léxico
#               del ítem; en Transfer el vector del contexto del banco);
#   served    — lo que la actividad SIRVIÓ de verdad (en los drills de ítem
#               coincide con lo declarado: no hay banco que ajuste);
#   observed  — lo que el alumno ACREDITÓ: lo servido DESCONTADO por el
#               andamiaje que la actividad le dio.
#
# El descuento es la pieza del P2-02: un éxito `guided` (repetir tras un modelo)
# no puede acreditar la misma carga que uno `spontaneous`, y hasta V3.54 el
# ledger los sumaba igual. Tabla DECLARADA, monótona con la escalera canónica de
# `services.evidence.EVIDENCE_SUPPORT_LEVELS`
# (`copied → guided → cued → independent → spontaneous`): cada PASO descuenta
# una unidad de carga por dimensión y una dimensión que cae por debajo de
# `_MIN_LOAD` no acredita nada. Los niveles FUERA de la tabla (`copied` y
# cualquier valor legacy/desconocido) no acreditan carga: sin apoyo declarado no
# se inventa capacidad (misma política que el resto del motor).
SUPPORT_DISCOUNT_STEPS: dict[str, int] = {
    "guided": 2,
    "cued": 1,
    "independent": 0,
    "spontaneous": 0,
}


def declared_difficulty(lexical_load: object) -> dict[str, int]:
    """Carga que DECLARA un ítem léxico: solo la dimensión `lexical` (pura).

    Un ítem declara su CEFR (la dificultad léxica del diccionario), no el
    discurso ni la interacción de una tarea: devuelve `{lexical: load}` con la
    carga recortada a 1..5, o `{}` si no hay dificultad declarada. La cobertura
    PARCIAL que produce es justamente la que el gate de V3.54 sabe tratar (una
    capacidad léxica no eleva tareas multidimensionales). Nunca lanza.

    Ojo al 0: `lexicon.cefr_difficulty` devuelve `0.0` cuando la fila no declara
    CEFR, y `_as_load` recortaría ese 0 a la carga mínima 1 — se declara `{}` en
    su lugar (un ítem sin CEFR no declara nada, no «un poco»).

    V3.55: es la mitad `declared` de las tres dificultades; en los drills de ítem
    (recall/word/sentence/write) `served` coincide con ella.
    """
    if isinstance(lexical_load, bool):
        return {}
    try:
        numeric = float(lexical_load)
    except (TypeError, ValueError):
        return {}
    if numeric <= 0:
        return {}
    load = _as_load(numeric)
    return {"lexical": load} if load is not None else {}


def observed_task_difficulty(
    served: object, support_level: object
) -> dict[str, int]:
    """Carga que el alumno ACREDITA tras descontar el andamiaje (V3.55, pura).

    Aplica `SUPPORT_DISCOUNT_STEPS` al vector SERVIDO: resta los pasos del nivel
    de apoyo declarado y descarta las dimensiones que quedan por debajo de la
    carga mínima. `copied` y cualquier apoyo desconocido devuelven `{}` (quien
    repite un modelo no acredita tarea; sin dato no se inventa). Un vector
    servido vacío no acredita nada. Nunca lanza.
    """
    vector = normalize_vector(served)
    if not vector:
        return {}
    steps = SUPPORT_DISCOUNT_STEPS.get(str(support_level or "").strip().lower())
    if steps is None:
        return {}
    return {
        dimension: load - steps
        for dimension, load in vector.items()
        if load - steps >= _MIN_LOAD
    }


def task_difficulty_vectors(
    *,
    declared: object,
    served: object,
    support_level: object,
    success: bool,
) -> dict[str, str]:
    """Serializa las TRES dificultades de un evento del ledger (V3.55, pura).

    Devuelve `{declared_difficulty, served_difficulty, observed_task_difficulty,
    observed_difficulty}` ya en el formato canónico de `format_vector`:

    - `declared`/`served` son HECHOS de la tarea y se guardan siempre (también en
      el fallo: declaran qué se pidió, no qué se logró);
    - `observed_task_difficulty` es lo ACREDITADO y solo se guarda en el ÉXITO
      (`''` en el fallo): un intento no superado no acredita carga;
    - `observed_difficulty` es la PROYECCIÓN LEGACY de lo servido, que V3.53/V3.54
      leían como la propia señal de capacidad. Se emite aquí para que no pueda
      divergir de `served_difficulty` (paridad exacta con el comportamiento
      anterior).

    Centralizar aquí la serialización garantiza que las vías de escritura del
    ledger producen el MISMO contrato. Nunca lanza.
    """
    served_vector = normalize_vector(served)
    served_text = format_vector(served_vector)
    return {
        "declared_difficulty": format_vector(normalize_vector(declared)),
        "served_difficulty": served_text,
        "observed_task_difficulty": (
            format_vector(observed_task_difficulty(served_vector, support_level))
            if success
            else ""
        ),
        # Proyección legacy: hasta V3.55 era la única columna y guardaba lo
        # servido, así que se conserva EXACTAMENTE igual.
        "observed_difficulty": served_text,
    }


def earned_difficulty(row: Mapping[str, object]) -> dict[str, int]:
    """Vector ACREDITADO de una fila del ledger (V3.55, pura).

    `served_difficulty` no vacía marca una fila de V3.55: entonces lo acreditado
    es EXACTAMENTE `observed_task_difficulty` (aunque sea `''`, p. ej. un éxito
    `copied`). Sin esa marca la fila es legacy (V3.53/V3.54) y se cae a
    `observed_difficulty`, que entonces se acreditaba completa (el drill de
    Transfer siempre declara apoyo `spontaneous`, así que la equivalencia es
    exacta). Nunca lanza.
    """
    if str(row.get("served_difficulty") or "").strip():
        return parse_vector(row.get("observed_task_difficulty"))
    return parse_vector(row.get("observed_difficulty"))


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


def _covered_set(dimensions: object) -> frozenset[str] | None:
    """Conjunto de dimensiones cubiertas, o None si no hay gate (V3.54, pura).

    `None` significa «sin gate»: el reto elevado aplica a todos los contextos
    (comportamiento de V3.53.1). Un iterable devuelve el conjunto normalizado a
    minúsculas; un tipo no iterable o una cadena se tratan como «sin gate» para
    no inventar una restricción a partir de datos mal formados. Nunca lanza.
    """
    if dimensions is None or isinstance(dimensions, (str, bytes)):
        return None
    try:
        return frozenset(
            str(dimension).strip().lower()
            for dimension in dimensions
            if str(dimension).strip()
        )
    except TypeError:
        return None


def challenge_for(
    context_vector: object,
    challenge: object,
    *,
    covered_dimensions: object = None,
    floor_challenge: object = None,
) -> dict[str, int]:
    """Reto aplicable a UN contexto según su cobertura observada (V3.54, pura).

    Con `covered_dimensions` (dimensiones con muestra espaciada de la modalidad
    que la tarea mide) la subida observada solo aplica a los contextos cuyas
    dimensiones declaradas son SUBCONJUNTO de las cubiertas: una capacidad
    léxica parcial no debe elevar el reto de una tarea que también exige sintaxis,
    discurso e interacción (P1 de V3.54). Los contextos fuera de la cobertura se
    evalúan contra `floor_challenge` (el reto sin subida observada); si no se
    aporta, contra el propio `challenge`. Sin `covered_dimensions` devuelve el
    reto tal cual (V3.53.1). Nunca lanza.
    """
    target = normalize_vector(challenge)
    covered = _covered_set(covered_dimensions)
    if covered is None:
        return target
    context = normalize_vector(context_vector)
    if set(context) <= covered:
        return target
    return normalize_vector(floor_challenge) or target


def select_by_difficulty(
    pool: Iterable[dict],
    challenge: object,
    *,
    tolerance: int = DIFFICULTY_TOLERANCE,
    covered_dimensions: object = None,
    floor_challenge: object = None,
) -> list[dict]:
    """Contextos más cercanos al reto sin pasarse de la tolerancia (V3.52, pura).

    Conserva los contextos `within` (cobertura dimensional completa y sin
    exceder el reto más de `tolerance`) y, entre ellos, los de MENOR `distance`;
    si NINGUNO está `within`, degrada primero por MAYOR cobertura y luego por
    menor `distance` (V3.52.1: antes bastaba la distancia, así que un contexto
    sin `difficulty_vector` ganaba con `distance=0`). Nunca deja el pool vacío:
    sin reto reconocible o sin pool devuelve el pool intacto. Determinista:
    preserva el orden de entrada.

    V3.54: `covered_dimensions` y `floor_challenge` activan el GATE de cobertura
    (ver `challenge_for`): cada contexto se evalúa contra el reto que le
    corresponde según las dimensiones que declara. Sin ellos el comportamiento
    es exactamente el de V3.52/V3.53. Nunca lanza.
    """
    contexts = list(pool)
    target = normalize_vector(challenge)
    if not contexts or not target:
        return contexts
    results = []
    for context in contexts:
        vector = _context_vector(context)
        results.append(
            fit(
                vector,
                challenge_for(
                    vector,
                    target,
                    covered_dimensions=covered_dimensions,
                    floor_challenge=floor_challenge,
                ),
                tolerance=tolerance,
            )
        )
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

"""Contextos de TRANSFERENCIA auténtica de una unidad léxica (V3.40 → V3.48).

La auditoría de V3.38.1 (P1-03) distingue dos cosas que hasta ahora se
confundían:

- **recuperación contextualizada** (`situation`): completar «The _____ was
  purring.» es reconocer/recuperar la palabra con una guía fuerte;
- **transferencia contextual**: usar la palabra por decisión propia en un
  contexto DISTINTO del de aprendizaje.

Este módulo aporta el contenido determinista de la segunda: un banco curado de
contextos (con cualquier unidad léxica) y la elección **pura y determinista** del
contexto que toca practicar, preferiendo uno que el ítem aún no haya usado con
éxito y que sea lo más DISTANTE posible de los contextos ya dominados.

V3.43 (Transfer 2.0, auditoría de V3.42.0) corrige dos sobreestimaciones:

- **P1-01 — el target deja de ser visible.** La consigna V3.40 mostraba la forma
  esperada («Tell a story using "bank"»), así que el alumno solo tenía que
  insertarla: eso demuestra producción contextualizada, no recuperación léxica
  espontánea. Ahora la consigna da un ESCENARIO y un objetivo comunicativo, y
  **nunca contiene la unidad objetivo**; el servidor sigue sabiendo cuál debe
  comprobar.
- **P1-03 — diversidad contextual real.** No basta con que `context_id A !=
  context_id B`: seis contextos con `topic`/`goal`/`discurso` distintos pueden
  producir la MISMA estructura lingüística (work/future/problem con "take").
  Cada contexto declara ahora sus atributos y `context_diversity` mide cuántas
  dimensiones cambian de verdad.

V3.46 (P1-03 de la auditoría de V3.43.0) añade la **CONDICIÓN DE RECUPERACIÓN**:
hasta ahora todo intento de transferencia era `spontaneous_use` con
`support_level="spontaneous"`, sin distinguir si la unidad se usó porque se pidió
(`prompted`), porque el escenario la insinuaba (`cued_context`), por decisión
propia en un escenario abierto (`open_context`), por elección libre
(`free_choice`) o porque surgió sola (`naturally_emergent`). La condición se
DERIVA de la evidencia (nunca la declara el cliente) y es lo que permite
endurecer `transfer_demonstrated`: un éxito en una tarea andamiada no acredita
transferencia no andamiada.

V3.47 añade el **nivel y la carga del contexto**: cada contexto del banco declara
su `cefr` (`services.cefr.CEFR_LEVELS`) y su `difficulty_vector`
(`lexical`/`syntax`/`discourse`/`interaction`, enteros 1..5, misma convención que
listening/speaking), y `context_for` acepta un `level` opcional para no servir un
contexto por encima del alcance del alumno si hay uno alcanzable (si no, cae al
nivel más cercano). Todo es aditivo: sin `level` el comportamiento es el de
V3.46.

V3.48 (**Context Bank 2.0 + diversidad 2.0**) amplía el banco curado de 6 a 20
contextos con cobertura A1–C2 y añade una capa de VARIEDAD informativa
(`CONTEXT_VARIETY_DIMENSIONS`: `register`/`lexical_environment`/
`syntactic_focus`). La variedad se expone en `context_diversity.variety` y
`context_variety` para explicabilidad, pero **NO entra en el gate de evidencia**:
`CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score` y
`diverse_dimensions` conservan la semántica de V3.47 (cero regresión). Los seis
contextos originales se mantienen congelados (mismos `id` y mismos valores core)
para no alterar la evidencia ya registrada.

V3.50 (**Context→Skill mapping + difficulty matching**) hace que los datos que
V3.47/V3.48 declaraban y nadie consumía al elegir la tarea pasen a decidirla:
cada contexto declara las competencias que ejercita (`skills`, vocabulario
`CONTEXT_SKILLS`) y `context_for` acepta la modalidad LIMITANTE del ítem
(`skill`, derivada por el llamador del planner) y la prefiere. Los filtros son
PREFERENCIAS con degradación con gracia y no tocan la escalera `transfer_state`,
sus umbrales, el scoring ni FSRS. El `skills` del contexto servido se expone de
forma aditiva.

V3.52 (**Difficulty Engine 2.0**) sustituye el ajuste de dificultad ESCALAR de
V3.50/V3.51 (que mezclaba el ordinal CEFR con la media del `difficulty_vector` y
colapsaba las cuatro dimensiones: un `(5,1,5,1)` y un `(3,3,3,3)` eran
indistinguibles) por una comparación VECTOR contra VECTOR por dimensión
(`services.difficulty`). `level` sigue siendo el TECHO lingüístico del ítem
(`_within_level`) y `learner_level` el SUELO de reto del alumno, ahora con su
origen (`learner_level_source`: demostrado/estimado/declarado) para elegir la
tolerancia. El retorno gana `difficulty_fit` (reto objetivo + distancia +
overshoot) y `learner_level_source`, aditivos; `difficulty` y
`difficulty_vector` se conservan por compatibilidad.

V3.59 (**Context Engine 3.0: Context Bank Family/Instance**) separa FAMILIA de
INSTANCIA: la familia (los 20 contextos, `id` incluido) sigue siendo la identidad
pedagógica y la unidad de EVIDENCIA, y cada familia declara ahora superficies
ADICIONALES (`instances`) de la MISMA identidad —otra redacción del mismo
escenario— que se sirven por ROTACIÓN de intentos (`attempts_by_context`: el
intento N recibe la superficie `N % nº_superficies`). El objetivo es que el banco
finito no se memorice (el alumno reciclaba la misma consigna al agotarlo). La
superficie 0 es la consigna histórica de la familia: sin evidencia el payload es
el de V3.58 salvo `context_instance`/`instance_index`/`instance_count` (aditivos),
y la superficie no entra en el pool, la novedad, la distancia ni la dificultad,
así que la familia servida y toda la evidencia/umbrales quedan intactos.

No usa LLM ni aleatoriedad con estado: la rotación se deriva de un hash ESTABLE
(`zlib.crc32`, no el `hash()` de Python, que va sembrado por proceso) y de los
contextos ya registrados en el ledger (`context_id`), así que la misma evidencia
produce siempre la misma consigna.
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping

from services import difficulty, learner_skill, task_semantics
from services.cefr import CEFR_LEVELS

# Prefijo del `context_id` del ledger para esta actividad. Distingue la
# transferencia de los contextos de práctica (`lexicon:<canal>`, `objective:*`).
TRANSFER_CONTEXT_PREFIX = "transfer:"

# Dimensiones pedagógicas de un contexto. `register` se declara como atributo
# (informa) pero NO entra en la diversidad: en el banco actual todos los
# contextos son `neutral`, así que no discrimina y solo inflaría el denominador.
CONTEXT_DIMENSIONS: tuple[str, ...] = (
    "topic",
    "communicative_goal",
    "discourse_type",
    "social_relation",
    "time_reference",
    "interaction_type",
)

# V3.48 (Context Bank 2.0): dimensiones de VARIEDAD del banco. Son INFORMATIVAS
# (explicabilidad y reporte) y NO entran en el gate de evidencia: los umbrales de
# transferencia siguen midiéndose sobre `CONTEXT_DIMENSIONS` (cero regresión).
# `register` ya se declaraba en todos los contextos; aquí se formaliza como
# dimensión de variedad junto a dos ejes nuevos del entorno lingüístico.
CONTEXT_VARIETY_DIMENSIONS: tuple[str, ...] = (
    "register",
    "lexical_environment",
    "syntactic_focus",
)

# V3.43 (P1-03): nº mínimo de dimensiones con valores DISTINTOS que exigen los
# contextos con éxito limpio para declarar diversidad real. Declarado y
# calibrable; dos contextos distintos suelen diferir en >= 2 dimensiones.
CONTEXT_DIVERSITY_MIN = 2

# V3.59 (Context Engine 3.0): claves que puede declarar una INSTANCIA de familia.
# Es una lista BLANCA a propósito: la instancia solo puede aportar su etiqueta y
# su consigna, nunca la identidad pedagógica (que es la unidad de evidencia).
CONTEXT_INSTANCE_KEYS: tuple[str, ...] = ("instance", "prompt")

# V3.59: nº mínimo de superficies ADICIONALES que debe declarar cada familia. Es
# el invariante anti-memorización de la release y está verificado por test: con
# una sola superficie declarada la rotación sería inerte.
CONTEXT_INSTANCES_MIN = 2

# V3.47: dimensiones de CARGA del contexto de transferencia (misma convención que
# el `difficulty_vector` de listening/speaking: enteros 1..5). No entran en la
# diversidad contextual (son dificultad, no atributo de variedad).
# V3.52: pasa a ser un ALIAS del vocabulario canónico del Difficulty Engine 2.0
# (`services.difficulty.DIFFICULTY_DIMENSIONS`), verificado por test de paridad.
TRANSFER_DIFFICULTY_KEYS: tuple[str, ...] = difficulty.DIFFICULTY_DIMENSIONS

# V3.50 (Context→Skill mapping): vocabulario de competencias que un contexto de
# transferencia puede ejercitar. Es un ESPEJO de `services.evidence.LEXICAL_SKILLS`
# declarado aquí (no importado) porque `services.evidence` ya importa este módulo:
# importarlo de vuelta crearía un ciclo. Un test de paridad falla si divergen.
# Orden canónico: es el orden en el que `context_skills` normaliza las listas y el
# que usan los contratos.
CONTEXT_SKILLS: tuple[str, ...] = (
    "recall",
    "written_production",
    "spoken_production",
    "spontaneous_use",
)

# V3.50 (difficulty matching): banda de tolerancia por debajo del contexto más
# exigente ALCANZABLE por el alumno.
# DEPRECADA en V3.52 (P1-02): la sustituye el Difficulty Engine 2.0 por dimensión
# (`services.difficulty.select_by_difficulty`), que ya no mezcla el ordinal CEFR
# con la media del vector. Se conserva declarada por trazabilidad y compatibilidad
# de lectura; ningún camino de selección la consume.
TRANSFER_DIFFICULTY_BAND = 1

# Orden del Marco para comparar niveles (Pre-A1 y valores desconocidos quedan
# fuera: `cefr_index` devuelve -1 y no filtran).
_CEFR_ORDER: dict[str, int] = {
    level: index for index, level in enumerate(CEFR_LEVELS)
}


def cefr_index(value: object) -> int:
    """Índice ordinal de un nivel CEFR (`-1` si no se reconoce) (V3.47, pura).

    Permite comparar niveles sin depender del orden alfabético (`A1`..`C2`).
    """
    return _CEFR_ORDER.get(str(value or "").strip().upper(), -1)


def difficulty_from_vector(vector: object) -> int:
    """Escalar de dificultad (1..6) como la media redondeada del vector (V3.47).

    Misma regla que `services.listening.difficulty_from_vector` y
    `services.speaking.difficulty_from_vector`: `round` de Python y clamp a [1, 6].
    Un vector vacío o inválido se trata como dificultad mínima. Nunca lanza.
    """
    if not isinstance(vector, dict) or not vector:
        return 1
    values = [
        value
        for value in vector.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not values:
        return 1
    mean = round(sum(values) / len(values))
    return max(1, min(6, mean))


def _within_level(pool: list[dict], level: object) -> list[dict]:
    """Contextos alcanzables para un nivel CEFR (V3.47, pura).

    Sin nivel reconocible devuelve el pool tal cual (retrocompatibilidad). Con
    nivel, prefiere los contextos de nivel igual o inferior; si NINGUNO es
    alcanzable (todos por encima del alumno), cae a los del nivel más cercano por
    arriba, de modo que nunca deja al alumno sin tarea. Nunca lanza.
    """
    index = cefr_index(level)
    if index < 0:
        return pool
    reachable = [
        context
        for context in pool
        if 0 <= cefr_index(context.get("cefr")) <= index
    ]
    if reachable:
        return reachable
    known = [
        (cefr_index(context.get("cefr")), context)
        for context in pool
        if cefr_index(context.get("cefr")) >= 0
    ]
    if not known:
        return pool
    nearest = min(rank for rank, _ in known)
    return [context for rank, context in known if rank == nearest]


def _filter_skill(pool: list[dict], skill: object) -> list[dict]:
    """Prefiere los contextos que ejercitan la modalidad pedida (V3.50, pura).

    Filtra el pool a los contextos que declaran `skill` en sus `skills`. Si la
    modalidad no es del vocabulario o NINGÚN contexto la declara, devuelve el
    pool intacto: el filtro es una PREFERENCIA, nunca deja al alumno sin tarea
    (degradación con gracia). Nunca lanza.
    """
    wanted = str(skill or "").strip().lower()
    if wanted not in CONTEXT_SKILLS:
        return pool
    matched = [context for context in pool if wanted in context_skills(context)]
    return matched or pool


def _challenge_and_tolerance(
    level: object,
    learner_level: object,
    learner_level_source: object,
    learner_capacity: object = None,
) -> tuple[dict[str, int], dict[str, int], int]:
    """Reto objetivo, reto de suelo y tolerancia aplicable (V3.52 → V3.54, pura).

    `challenge` es el MÁXIMO por dimensión entre la capacidad del ítem (techo
    lingüístico) y la del alumno (suelo de reto); `{}` si no se reconoce ningún
    nivel (el selector no filtra). La tolerancia es estricta solo con un suelo
    DEMOSTRADO; estimado/declarado/`observed`/ausente usan el margen amplio.

    V3.53: un `learner_capacity` explícito (capacidad OBSERVADA por dimensión,
    `services.learner_skill`) SUSTITUYE al `capacity_for(learner_level)` como
    suelo del alumno, pero conserva el máximo con la capacidad del ítem: sube el
    reto solo en las dimensiones demostradas y nunca inventa nivel. Con `None`
    o `{}` el cálculo es exactamente el de V3.52.2.

    V3.54: devuelve también `floor_challenge`, el reto SIN la subida observada
    (el de V3.52.2 sobre el suelo declarado), que el gate de cobertura usa para
    los contextos cuyas dimensiones quedan fuera de la capacidad observada.
    Nunca lanza.
    """
    floor_challenge = difficulty.challenge_vector(level, learner_level)
    challenge = floor_challenge
    override = difficulty.normalize_vector(learner_capacity)
    if override:
        item_capacity = difficulty.capacity_for(level)
        challenge = {
            dimension: max(
                item_capacity.get(dimension, 0),
                override.get(dimension, 0),
            )
            for dimension in difficulty.DIFFICULTY_DIMENSIONS
            if dimension in item_capacity or dimension in override
        }
    return challenge, floor_challenge, difficulty.tolerance_for(learner_level_source)


def _difficulty_fit_for(
    context: object, challenge: dict[str, int], tolerance: int
) -> dict:
    """`difficulty_fit` del contexto servido contra el reto (V3.52, pura).

    Devuelve `{challenge, dimensions, dimensions_compared, dimensions_expected,
    coverage, distance, max_overshoot, within, tolerance}`. Con reto vacío el
    encaje es vacuo (`within=True`, cobertura 1.0): no había nada que comparar y
    la elección no se filtró. V3.52.1 (P1-01): se expone la COBERTURA dimensional
    para que la UI pueda distinguir «encaja» de «no era comparable». Nunca lanza.
    """
    if not challenge:
        return {
            "challenge": {},
            "dimensions": 0,
            "dimensions_compared": 0,
            "dimensions_expected": 0,
            "coverage": 1.0,
            "distance": 0,
            "max_overshoot": 0,
            "within": True,
            "tolerance": tolerance,
        }
    vector = (
        (context or {}).get("difficulty_vector")
        if isinstance(context, dict)
        else None
    )
    result = difficulty.fit(vector, challenge, tolerance=tolerance)
    return {
        "challenge": dict(challenge),
        "dimensions": result["dimensions"],
        "dimensions_compared": result["dimensions_compared"],
        "dimensions_expected": result["dimensions_expected"],
        "coverage": result["coverage"],
        "distance": result["distance"],
        "max_overshoot": result["max_overshoot"],
        "within": result["within"],
        "tolerance": tolerance,
    }


def _normalize_source(value: object) -> str:
    """Fuente del suelo normalizada a minúsculas ("" si no se aporta) (pura)."""
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# V3.46 (P1-03 de la auditoría de V3.43.0): CONDICIÓN DE RECUPERACIÓN.
#
# `spontaneous_use` era una etiqueta DEMASIADO amplia: no es lo mismo usar la
# unidad porque la tarea la nombra que recuperarla por decisión propia en un
# escenario abierto. La condición es una dimensión ADICIONAL (no sustituye al
# `support_level`, que sigue declarando el andamiaje de la ACTIVIDAD) y se
# DERIVA del estado de evidencia, nunca la declara el cliente (premisa 21).
#
# Orden de andamiaje DECRECIENTE (el primero da más ayuda):
#   prompted → cued_context → open_context → free_choice → naturally_emergent
# ---------------------------------------------------------------------------
TRANSFER_CONDITIONS: tuple[str, ...] = (
    "prompted",
    "cued_context",
    "open_context",
    "free_choice",
    "naturally_emergent",
)

# Condiciones que este drill puede SERVIR. `free_choice`/`naturally_emergent`
# solo se pueden REGISTRAR (llegan de conversación libre/natural, fuera del
# banco de escenarios); se declaran para que el vocabulario sea único.
SERVABLE_CONDITIONS: tuple[str, ...] = (
    "prompted",
    "cued_context",
    "open_context",
)

# Condiciones NO andamiadas: ningún enunciado da la unidad ni la exige. Solo un
# ÉXITO LIMPIO en una de ellas acredita transferencia DEMOSTRADA (V3.46); un
# acierto en `prompted`/`cued_context` demuestra producción con ayuda, no
# recuperación espontánea.
UNSCAFFOLDED_CONDITIONS: tuple[str, ...] = (
    "open_context",
    "free_choice",
    "naturally_emergent",
)

# Condición por defecto: la de V3.43 (escenario sin nombrar la unidad). Mantiene
# el comportamiento previo cuando no se declara condición.
DEFAULT_TRANSFER_CONDITION = "cued_context"

# Condiciones que EXIGEN la unidad objetivo: no usarla es un intento fallido
# (`missing_target`). En las no andamiadas la ausencia NO es un fallo (el alumno
# elige su vocabulario), así que un intento sin la unidad no se registra como
# evidencia: no hay nada que observar sobre el objetivo.
REQUIRED_TARGET_CONDITIONS: tuple[str, ...] = (
    "prompted",
    "cued_context",
)

# Instrucción que se AÑADE al escenario del banco para componer la consigna
# servida. `cued_context` no añade nada: el escenario ES la consigna (V3.43).
# `prompted` nombra la unidad a propósito (es la condición más débil y queda
# registrada como tal); `open_context` deja claro que no hay palabra obligatoria.
CONDITION_INSTRUCTIONS: dict[str, str] = {
    "prompted": "Try to use the word “{word}” in your answer.",
    "cued_context": "",
    "open_context": "Use any vocabulary you need.",
}

# Banco curado de contextos NOVEDOSOS. La consigna NO da la palabra (eso sería
# `sentence`): solo un escenario y un objetivo comunicativo en los que usarla por
# decisión propia (V3.43, P1-01). Declarado y estable; ampliarlo no rompe
# determinismo, porque la elección se deriva del banco.
TRANSFER_CONTEXTS: tuple[dict[str, str], ...] = (
    {
        "id": "story",
        "skills": (
            "written_production",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "personal_experience",
        "communicative_goal": "narrate",
        "discourse_type": "narrative",
        "social_relation": "friend",
        "time_reference": "past",
        "register": "neutral",
        "interaction_type": "monologue",
        # V3.47: nivel y carga declarados (convención listening/speaking).
        "cefr": "A2",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 1,
        },
        # V3.48: ejes de variedad (solo reporte; ver CONTEXT_VARIETY_DIMENSIONS).
        "lexical_environment": "personal_experience",
        "syntactic_focus": "past_narrative",
        "prompt": (
            "Tell a short story about something that happened to you recently."
        ),
        # V3.59: superficies declaradas de la MISMA familia (ver `context_instances`).
        "instances": (
            {
                "instance": "a_journey",
                "prompt": (
                    "Tell a short story about a journey that did not go as "
                    "planned."
                ),
            },
            {
                "instance": "a_surprise",
                "prompt": (
                    "Tell a short story about a surprise you had one day."
                ),
            },
        ),
    },
    {
        "id": "question",
        "skills": (
            "written_production",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "friend_life",
        "communicative_goal": "ask",
        "discourse_type": "dialogue",
        "social_relation": "friend",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "dialogue",
        # V3.47: el contexto más simple del banco (una pregunta a un amigo).
        "cefr": "A1",
        "difficulty_vector": {
            "lexical": 1,
            "syntax": 1,
            "discourse": 1,
            "interaction": 2,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "questions",
        "prompt": "Write a question you would like to ask a friend.",
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "about_the_weekend",
                "prompt": (
                    "Write a question you would like to ask a friend about "
                    "their weekend."
                ),
            },
            {
                "instance": "about_their_family",
                "prompt": (
                    "Write a question you would like to ask a friend about "
                    "their family."
                ),
            },
        ),
    },
    {
        "id": "work",
        "skills": (
            "written_production",
            "spoken_production",
        ),
        "topic": "employment",
        "communicative_goal": "describe",
        "discourse_type": "descriptive",
        "social_relation": "colleague",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "monologue",
        "cefr": "B1",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 3,
            "interaction": 2,
        },
        "lexical_environment": "professional",
        "syntactic_focus": "simple_present",
        "prompt": (
            "You have a new job. Describe something interesting about your "
            "first week to a colleague."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_new_workplace",
                "prompt": (
                    "You have changed offices. Describe your new workplace to "
                    "a colleague."
                ),
            },
            {
                "instance": "a_daily_task",
                "prompt": (
                    "Describe one task you do every day at work to a colleague."
                ),
            },
        ),
    },
    {
        "id": "future",
        "skills": (
            "written_production",
            "spoken_production",
        ),
        "topic": "personal_plans",
        "communicative_goal": "plan",
        "discourse_type": "expository",
        "social_relation": "friend",
        "time_reference": "future",
        "register": "neutral",
        "interaction_type": "monologue",
        "cefr": "A2",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 1,
        },
        "lexical_environment": "personal_experience",
        "syntactic_focus": "future_forms",
        "prompt": "Talk about your plans for next year.",
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "next_summer",
                "prompt": "Talk about your plans for next summer.",
            },
            {
                "instance": "next_month",
                "prompt": "Talk about your plans for next month.",
            },
        ),
    },
    {
        "id": "opinion",
        "skills": (
            "recall",
            "written_production",
            "spoken_production",
        ),
        "topic": "everyday_topics",
        "communicative_goal": "give_opinion",
        "discourse_type": "argumentative",
        "social_relation": "friend",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "monologue",
        "cefr": "B1",
        "difficulty_vector": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 3,
            "interaction": 1,
        },
        "lexical_environment": "abstract",
        "syntactic_focus": "complex_subordination",
        "prompt": (
            "Give your opinion about something you feel strongly about, and "
            "say why."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_school_subject",
                "prompt": (
                    "Give your opinion about a school subject you liked or "
                    "disliked, and say why."
                ),
            },
            {
                "instance": "city_life",
                "prompt": (
                    "Give your opinion about living in a big city, and say why."
                ),
            },
        ),
    },
    {
        "id": "problem",
        "skills": (
            "written_production",
            "spoken_production",
        ),
        "topic": "everyday_problems",
        "communicative_goal": "explain",
        "discourse_type": "explanatory",
        "social_relation": "family",
        "time_reference": "past",
        "register": "neutral",
        "interaction_type": "monologue",
        "cefr": "B1",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 3,
            "discourse": 3,
            "interaction": 1,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "past_narrative",
        "prompt": "Describe a small problem you had and how you solved it.",
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "at_home",
                "prompt": (
                    "Describe a problem you had at home one day and how you "
                    "solved it."
                ),
            },
            {
                "instance": "on_a_trip",
                "prompt": (
                    "Describe something that went wrong on a trip and how you "
                    "dealt with it."
                ),
            },
        ),
    },
    # --- V3.48 (Context Bank 2.0): 14 contextos nuevos, cobertura A1–C2 ---
    {
        "id": "introductions",
        "skills": (
            "written_production",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "social_introductions",
        "communicative_goal": "introduce",
        "discourse_type": "dialogue",
        "social_relation": "stranger",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "dialogue",
        "cefr": "A1",
        "difficulty_vector": {
            "lexical": 1,
            "syntax": 1,
            "discourse": 1,
            "interaction": 2,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "simple_present",
        "prompt": (
            "You meet someone new at a class. Introduce yourself and say where "
            "you are from."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "at_a_club",
                "prompt": (
                    "You meet someone new at a sports club. Introduce yourself "
                    "and say what you like doing."
                ),
            },
            {
                "instance": "at_a_party",
                "prompt": (
                    "You meet someone new at a party. Introduce yourself and "
                    "say what you do."
                ),
            },
        ),
    },
    {
        "id": "routine",
        "skills": (
            "written_production",
            "spoken_production",
        ),
        "topic": "daily_routine",
        "communicative_goal": "describe",
        "discourse_type": "descriptive",
        "social_relation": "family",
        "time_reference": "present",
        "register": "informal",
        "interaction_type": "monologue",
        "cefr": "A1",
        "difficulty_vector": {
            "lexical": 1,
            "syntax": 1,
            "discourse": 2,
            "interaction": 1,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "simple_present",
        "prompt": "Describe what you usually do on a normal morning at home.",
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "an_evening",
                "prompt": "Describe what you usually do on a normal evening at home.",
            },
            {
                "instance": "a_weekend",
                "prompt": "Describe what you usually do at the weekend.",
            },
        ),
    },
    {
        "id": "directions",
        "skills": (
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "city_navigation",
        "communicative_goal": "ask",
        "discourse_type": "dialogue",
        "social_relation": "stranger",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "dialogue",
        "cefr": "A2",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 3,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "questions",
        "prompt": (
            "You are lost in a new city. Ask a passer-by how to get to the "
            "station."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "the_market",
                "prompt": (
                    "You are looking for the market in a city you do not know. "
                    "Ask a passer-by how to get there."
                ),
            },
            {
                "instance": "a_pharmacy",
                "prompt": (
                    "You need a pharmacy in a town you do not know. Ask a "
                    "passer-by where to find one."
                ),
            },
        ),
    },
    {
        "id": "shopping",
        "skills": (
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "shopping",
        "communicative_goal": "request",
        "discourse_type": "dialogue",
        "social_relation": "stranger",
        "time_reference": "present",
        "register": "informal",
        "interaction_type": "dialogue",
        "cefr": "A2",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 3,
        },
        "lexical_environment": "concrete_everyday",
        "syntactic_focus": "modals",
        "prompt": (
            "You are in a shop and cannot find what you need. Ask an assistant "
            "for help."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "the_wrong_size",
                "prompt": (
                    "You like something in a shop but it is the wrong size. "
                    "Ask an assistant for help."
                ),
            },
            {
                "instance": "the_price",
                "prompt": (
                    "You cannot find the price of something in a shop. Ask an "
                    "assistant for help."
                ),
            },
        ),
    },
    {
        "id": "health",
        "skills": (
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "health",
        "communicative_goal": "explain",
        "discourse_type": "explanatory",
        "social_relation": "professional",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "dialogue",
        "cefr": "B1",
        "difficulty_vector": {
            "lexical": 2,
            "syntax": 3,
            "discourse": 3,
            "interaction": 2,
        },
        "lexical_environment": "professional",
        "syntactic_focus": "modals",
        "prompt": (
            "You do not feel well. Explain your symptoms to a doctor and answer "
            "their questions."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_bad_cough",
                "prompt": (
                    "You have a bad cough. Explain it to a pharmacist and "
                    "answer their questions."
                ),
            },
            {
                "instance": "a_check_up",
                "prompt": (
                    "You are at a check-up. Explain how you have been feeling "
                    "lately and answer the doctor's questions."
                ),
            },
        ),
    },
    {
        "id": "travel_plan",
        "skills": (
            "recall",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "trip_planning",
        "communicative_goal": "plan",
        "discourse_type": "expository",
        "social_relation": "friend",
        "time_reference": "future",
        "register": "informal",
        "interaction_type": "dialogue",
        "cefr": "B2",
        "difficulty_vector": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 3,
            "interaction": 3,
        },
        "lexical_environment": "personal_experience",
        "syntactic_focus": "future_forms",
        "prompt": (
            "Plan a weekend away with a friend: suggest where to go and why, "
            "and agree on the details."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_longer_trip",
                "prompt": (
                    "Plan a longer trip with a friend: suggest where to go and "
                    "why, and agree on the details."
                ),
            },
            {
                "instance": "a_family_visit",
                "prompt": (
                    "Plan a visit to family with a friend: suggest when to go "
                    "and why, and agree on the details."
                ),
            },
        ),
    },
    {
        "id": "work_problem",
        "skills": (
            "recall",
            "written_production",
            "spoken_production",
        ),
        "topic": "employment",
        "communicative_goal": "explain",
        "discourse_type": "explanatory",
        "social_relation": "colleague",
        "time_reference": "past",
        "register": "formal",
        "interaction_type": "dialogue",
        "cefr": "B2",
        "difficulty_vector": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 4,
            "interaction": 3,
        },
        "lexical_environment": "professional",
        "syntactic_focus": "past_narrative",
        "prompt": (
            "Something went wrong on a project at work. Explain to a colleague "
            "what happened and how you fixed it."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_late_delivery",
                "prompt": (
                    "A delivery arrived late on a project at work. Explain to a "
                    "colleague what happened and how you fixed it."
                ),
            },
            {
                "instance": "a_missing_file",
                "prompt": (
                    "An important file was missing at work. Explain to a "
                    "colleague what happened and how you fixed it."
                ),
            },
        ),
    },
    {
        "id": "community",
        "skills": (
            "recall",
            "written_production",
            "spoken_production",
        ),
        "topic": "community",
        "communicative_goal": "persuade",
        "discourse_type": "argumentative",
        "social_relation": "neighbour",
        "time_reference": "future",
        "register": "formal",
        "interaction_type": "monologue",
        "cefr": "B2",
        "difficulty_vector": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 4,
            "interaction": 2,
        },
        "lexical_environment": "abstract",
        "syntactic_focus": "conditionals",
        "prompt": (
            "Propose one change to improve your neighbourhood and explain why "
            "your neighbours should support it."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_greener_neighbourhood",
                "prompt": (
                    "Propose one change to make your neighbourhood greener and "
                    "explain why your neighbours should support it."
                ),
            },
            {
                "instance": "a_shared_space",
                "prompt": (
                    "Propose one change to the shared spaces of your building "
                    "and explain why your neighbours should support it."
                ),
            },
        ),
    },
    {
        "id": "debate",
        "skills": (
            "recall",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "society",
        "communicative_goal": "argue",
        "discourse_type": "argumentative",
        "social_relation": "audience",
        "time_reference": "present",
        "register": "formal",
        "interaction_type": "dialogue",
        "cefr": "C1",
        "difficulty_vector": {
            "lexical": 4,
            "syntax": 4,
            "discourse": 5,
            "interaction": 4,
        },
        "lexical_environment": "abstract",
        "syntactic_focus": "complex_subordination",
        "prompt": (
            "Take a position on a social issue and defend it against an "
            "opposing view."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "work_and_private_life",
                "prompt": (
                    "Take a position on the balance between work and private "
                    "life and defend it against an opposing view."
                ),
            },
            {
                "instance": "technology_and_privacy",
                "prompt": (
                    "Take a position on technology and personal privacy and "
                    "defend it against an opposing view."
                ),
            },
        ),
    },
    {
        "id": "review",
        "skills": (
            "recall",
            "written_production",
            "spoken_production",
        ),
        "topic": "culture",
        "communicative_goal": "evaluate",
        "discourse_type": "evaluative",
        "social_relation": "audience",
        "time_reference": "past",
        "register": "formal",
        "interaction_type": "monologue",
        "cefr": "C1",
        "difficulty_vector": {
            "lexical": 4,
            "syntax": 4,
            "discourse": 5,
            "interaction": 2,
        },
        "lexical_environment": "cultural",
        "syntactic_focus": "complex_subordination",
        "prompt": (
            "Review a film or a book you have recently experienced, weighing "
            "its strengths and weaknesses."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_series",
                "prompt": (
                    "Review a series you have recently watched, weighing its "
                    "strengths and weaknesses."
                ),
            },
            {
                "instance": "an_exhibition",
                "prompt": (
                    "Review an exhibition or a concert you have recently "
                    "visited, weighing its strengths and weaknesses."
                ),
            },
        ),
    },
    {
        "id": "mediation",
        "skills": (
            "recall",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "interpersonal_conflict",
        "communicative_goal": "mediate",
        "discourse_type": "explanatory",
        "social_relation": "group",
        "time_reference": "past",
        "register": "formal",
        "interaction_type": "dialogue",
        "cefr": "C1",
        "difficulty_vector": {
            "lexical": 4,
            "syntax": 5,
            "discourse": 5,
            "interaction": 5,
        },
        "lexical_environment": "professional",
        "syntactic_focus": "complex_subordination",
        "prompt": (
            "Two people you know disagree. Explain each side to the other and "
            "help them reach an understanding."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_family_disagreement",
                "prompt": (
                    "Two members of your family disagree about a decision. "
                    "Explain each side to the other and help them reach an "
                    "understanding."
                ),
            },
            {
                "instance": "a_team_disagreement",
                "prompt": (
                    "Two colleagues disagree about how to organise some work. "
                    "Explain each side to the other and help them reach an "
                    "understanding."
                ),
            },
        ),
    },
    {
        "id": "academic",
        "skills": (
            "recall",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "research",
        "communicative_goal": "justify",
        "discourse_type": "academic",
        "social_relation": "expert",
        "time_reference": "present",
        "register": "formal",
        "interaction_type": "dialogue",
        "cefr": "C2",
        "difficulty_vector": {
            "lexical": 5,
            "syntax": 5,
            "discourse": 5,
            "interaction": 4,
        },
        "lexical_environment": "academic",
        "syntactic_focus": "passive",
        "prompt": (
            "Present an argument from a field you know well and respond to a "
            "critical question about your evidence."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_method",
                "prompt": (
                    "Explain and defend a method you use in a field you know "
                    "well, and respond to a critical question about it."
                ),
            },
            {
                "instance": "a_counterexample",
                "prompt": (
                    "Present a claim from a field you know well and respond to "
                    "a counterexample an expert raises."
                ),
            },
        ),
    },
    {
        "id": "negotiation",
        "skills": (
            "recall",
            "spoken_production",
            "spontaneous_use",
        ),
        "topic": "high_stakes",
        "communicative_goal": "negotiate",
        "discourse_type": "negotiation",
        "social_relation": "expert",
        "time_reference": "future",
        "register": "formal",
        "interaction_type": "dialogue",
        "cefr": "C2",
        "difficulty_vector": {
            "lexical": 5,
            "syntax": 5,
            "discourse": 5,
            "interaction": 5,
        },
        "lexical_environment": "professional",
        "syntactic_focus": "conditionals",
        "prompt": (
            "Negotiate the terms of an agreement with a counterpart who wants "
            "something different, and justify the concessions you are willing "
            "to make."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "a_budget",
                "prompt": (
                    "Negotiate a budget with a counterpart who wants to spend "
                    "more, and justify the concessions you are willing to make."
                ),
            },
            {
                "instance": "a_deadline",
                "prompt": (
                    "Negotiate a deadline with a counterpart who wants it "
                    "sooner, and justify the concessions you are willing to "
                    "make."
                ),
            },
        ),
    },
    {
        "id": "keynote",
        "skills": (
            "recall",
            "written_production",
            "spoken_production",
        ),
        "topic": "abstract_ideas",
        "communicative_goal": "present",
        "discourse_type": "academic",
        "social_relation": "audience",
        "time_reference": "present",
        "register": "formal",
        "interaction_type": "monologue",
        "cefr": "C2",
        "difficulty_vector": {
            "lexical": 5,
            "syntax": 5,
            "discourse": 5,
            "interaction": 1,
        },
        "lexical_environment": "abstract",
        "syntactic_focus": "passive",
        "prompt": (
            "Deliver a short keynote on an abstract theme and use concrete "
            "examples to make it persuasive."
        ),
        # V3.59: superficies declaradas de la MISMA familia.
        "instances": (
            {
                "instance": "how_people_learn",
                "prompt": (
                    "Deliver a short keynote on how people learn and use "
                    "concrete examples to make it persuasive."
                ),
            },
            {
                "instance": "how_teams_change",
                "prompt": (
                    "Deliver a short keynote on how teams change over time and "
                    "use concrete examples to make it persuasive."
                ),
            },
        ),
    },
)

# Índice por `id` para resoluciones de atributos en O(1) (derivado del banco).
_CONTEXTS_BY_ID: dict[str, dict] = {
    context["id"]: context for context in TRANSFER_CONTEXTS
}


# ---------------------------------------------------------------------------
# V3.46: vocabulario de la CONDICIÓN DE RECUPERACIÓN (puro y determinista).
# ---------------------------------------------------------------------------

def normalize_condition(value: object) -> str:
    """Condición canónica de un valor libre ("" si no se reconoce) (V3.46, pura).

    Tolerante a propósito: el ledger puede traer filas legacy (sin condición) o
    valores de una taxonomía futura. Lo no reconocido se trata como "sin
    condición" y NUNCA como una condición andamiada inventada.
    """
    text = str(value or "").strip().lower()
    return text if text in TRANSFER_CONDITIONS else ""


def is_unscaffolded(condition: object) -> bool:
    """¿La condición acredita uso NO andamiado? (V3.46, pura)."""
    return normalize_condition(condition) in UNSCAFFOLDED_CONDITIONS


def requires_target(condition: object) -> bool:
    """¿La condición EXIGE la unidad objetivo? (V3.46, pura).

    Sin condición declarada se responde con la condición por defecto (la de
    V3.43), para no cambiar el comportamiento previo.
    """
    canonical = normalize_condition(condition) or DEFAULT_TRANSFER_CONDITION
    return canonical in REQUIRED_TARGET_CONDITIONS


def condition_instruction(condition: object, word: str = "") -> str:
    """Instrucción que se añade al escenario para una condición (V3.46, pura).

    Devuelve "" para las condiciones cuyo escenario ya ES la consigna
    (`cued_context`) y para las no servibles. Nunca lanza.
    """
    canonical = normalize_condition(condition) or DEFAULT_TRANSFER_CONDITION
    template = CONDITION_INSTRUCTIONS.get(canonical, "")
    if not template:
        return ""
    return template.format(word=(word or "").strip())


def condition_for_state(
    state: object,
    *,
    attempted: bool = False,
    clean_successes: int = 0,
) -> str:
    """Condición que toca SERVIR según el estado de transferencia (V3.46, pura).

    Escalera de andamiaje DECRECIENTE, derivada del estado formal (que ya se
    calcula en `services.evidence.transfer_state`):

    - `not_ready` **con intentos y sin ningún éxito limpio** → `prompted`: el
      alumno no recupera la unidad ni con un escenario, así que se le nombra
      explícitamente. Es la única puerta a `prompted` (no se degrada la tarea a
      quien ya acierta ni a quien aún no lo ha intentado).
    - `not_ready` en el resto de casos y `emerging` → `cued_context`: escenario
      sin nombrar la unidad, exactamente el comportamiento de V3.43 (sin
      regresión).
    - `contextualized` o superior → `open_context`: la unidad ya se usa con éxito
      en contextos distintos, así que toca el escenario abierto que NO exige la
      palabra — el único que puede acreditar transferencia demostrada (V3.46).

    Un estado desconocido (resumen parcial/legacy) cae a la condición por
    defecto. Nunca lanza.
    """
    value = str(state or "").strip().lower()
    if value in (
        "contextualized",
        "transfer_demonstrated",
        "transfer_stable",
        "automatic",
    ):
        return "open_context"
    if value == "not_ready" and attempted and clean_successes <= 0:
        return "prompted"
    return DEFAULT_TRANSFER_CONDITION


def context_id_for(context: dict | str) -> str:
    """`context_id` de ledger de un contexto del banco (pura)."""
    ident = context["id"] if isinstance(context, dict) else str(context)
    ident = (ident or "").strip()
    if not ident:
        return ""
    if ident.startswith(TRANSFER_CONTEXT_PREFIX):
        return ident
    return f"{TRANSFER_CONTEXT_PREFIX}{ident}"


def _bare_context_id(context_id: object) -> str:
    """`id` del banco sin el prefijo `transfer:` ("" si no es reconocible)."""
    text = str(context_id or "").strip()
    if not text:
        return ""
    if text.startswith(TRANSFER_CONTEXT_PREFIX):
        text = text[len(TRANSFER_CONTEXT_PREFIX):]
    return text if text in _CONTEXTS_BY_ID else ""


def _as_attributes(context: object) -> dict[str, str]:
    """Atributos de un contexto a partir de su dict, su `id` o su `context_id`."""
    if isinstance(context, dict):
        if "id" not in context:
            return {}
        attributes = dict(context)
    else:
        ident = _bare_context_id(context)
        if not ident:
            return {}
        attributes = dict(_CONTEXTS_BY_ID[ident])
    # V3.47: el `difficulty_vector` es un dict anidado; se copia para no exponer
    # (ni permitir mutar) el del banco.
    vector = attributes.get("difficulty_vector")
    if isinstance(vector, dict):
        attributes["difficulty_vector"] = dict(vector)
    return attributes


def context_attributes(context: object) -> dict[str, str]:
    """Atributos pedagógicos de un contexto ({} si no se reconoce) (V3.43, pura).

    Acepta el dict del banco, un `id` (`"story"`) o un `context_id` de ledger
    (`"transfer:story"`). Devuelve una COPIA: nunca expone el dict del banco.
    """
    return _as_attributes(context)


def context_skills(context: object) -> tuple[str, ...]:
    """Competencias que DECLARA un contexto de transferencia (V3.50, pura).

    Acepta el dict del banco, un `id` (`"story"`) o un `context_id` de ledger
    (`"transfer:story"`). Normaliza: deduplica, ordena por `CONTEXT_SKILLS`
    (orden canónico y estable) e ignora cualquier valor fuera del vocabulario.
    Un contexto sin `skills` declaradas (o no reconocido) devuelve `()`. Nunca
    lanza.
    """
    attributes = _as_attributes(context)
    declared = attributes.get("skills")
    if isinstance(declared, str) or not isinstance(
        declared, (list, tuple, set, frozenset)
    ):
        return ()
    wanted = {str(skill or "").strip().lower() for skill in declared}
    return tuple(skill for skill in CONTEXT_SKILLS if skill in wanted)


def context_difficulty(context: object) -> dict[str, int]:
    """Carga DECLARADA por un contexto del banco, por dimensión (V3.53, pura).

    Acepta el dict del banco, un `id` (`"story"`) o un `context_id` de ledger
    (`"transfer:story"`), igual que `context_skills`. Devuelve el
    `difficulty_vector` normalizado al vocabulario canónico (1..5) o `{}` si el
    contexto no se reconoce o no declara carga. Es la señal que el ledger
    persiste por evento (`observed_difficulty`): la dificultad de la TAREA
    servida, no la del ítem léxico. Nunca lanza.
    """
    attributes = _as_attributes(context)
    return difficulty.normalize_vector(attributes.get("difficulty_vector"))


# ---------------------------------------------------------------------------
# V3.59 (Context Engine 3.0): FAMILIA vs INSTANCIA.
#
# Una familia (los 20 contextos del banco) es la identidad pedagógica y la
# unidad de EVIDENCIA: su `id` es el `context_id` del ledger. Una INSTANCIA es
# una superficie DECLARADA de esa misma familia: otra redacción del MISMO
# escenario, con la misma identidad (nadie puede declararle otra cosa, ver
# `CONTEXT_INSTANCE_KEYS`). El ledger, los umbrales, `context_distance`,
# `context_diversity`, la novedad y el ajuste de dificultad siguen leyendo la
# FAMILIA, así que ampliar las superficies no reinterpreta evidencia pasada.
# ---------------------------------------------------------------------------


def _count(value: object) -> int:
    """Nº de intentos a partir de un valor del ledger, tolerante (V3.59, pura).

    Acepta un entero, su forma textual y el bucket `{"attempts": n}` del resumen
    de evidencia. Cualquier otra cosa (incluidos `bool`, negativos y `None`)
    vale 0: la superficie histórica. Nunca lanza.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, str):
        text = value.strip()
        return int(text) if text.isdigit() else 0
    if isinstance(value, Mapping):
        return _count(value.get("attempts"))
    return 0


def context_instances(context: object) -> tuple[dict[str, str], ...]:
    """Superficies servibles de una familia (V3.59, pura).

    Devuelve `({"instance": "", "prompt": <consigna histórica>}, *declaradas)`:
    la propia `prompt` de la familia es SIEMPRE la superficie 0 (byte a byte la
    histórica, así que sin evidencia el resultado es el de V3.58) y cada
    `instances` declarada añade una superficie nueva de la MISMA identidad.
    Acepta el dict del banco, un `id` o un `context_id`. Normaliza (recorta y
    descarta superficies sin consigna o no-dict) y nunca lanza.
    """
    attributes = _as_attributes(context)
    surfaces: list[dict[str, str]] = []
    family_prompt = str(attributes.get("prompt") or "").strip()
    if family_prompt:
        surfaces.append({"instance": "", "prompt": family_prompt})
    declared = attributes.get("instances")
    if isinstance(declared, (list, tuple)):
        for raw in declared:
            if not isinstance(raw, Mapping):
                continue
            prompt = str(raw.get("prompt") or "").strip()
            if not prompt:
                continue
            surfaces.append(
                {"instance": str(raw.get("instance") or "").strip(), "prompt": prompt}
            )
    return tuple(surfaces)


def context_instance_index(context: object, attempts: object = 0) -> int:
    """Superficie que toca servir, por ROTACIÓN de intentos (V3.59, pura).

    `attempts` son los intentos ya registrados en ESA familia para el ítem (el
    resumen de evidencia los cuenta por `context_id`), de modo que el intento N
    recibe la superficie `N % nº_superficies`: la primera estancia sirve la
    consigna histórica y las siguientes no repiten redacción, que es lo que
    evita que el alumno memorice la estructura en lugar de transferir. Sin
    intentos (o con un valor no reconocible) devuelve 0, es decir, la superficie
    de V3.58 exacta. Una familia sin superficies declaradas devuelve 0 siempre
    (rotación inerte). Nunca lanza.
    """
    count = len(context_instances(context))
    if count <= 1:
        return 0
    return _count(attempts) % count


def _attempts_for(attempts_by_context: object, context_id: str) -> int:
    """Intentos del ítem en una familia (V3.59, pura y tolerante).

    Acepta el mapa `contexts` del resumen de evidencia (`{context_id: {attempts,
    successes}}`), un mapa de enteros o nada. Prueba el `context_id` del ledger
    y, si no, el `id` desnudo. Nunca lanza.
    """
    if not isinstance(attempts_by_context, Mapping):
        return 0
    if context_id in attempts_by_context:
        return _count(attempts_by_context[context_id])
    return _count(attempts_by_context.get(_bare_context_id(context_id)))


def _normalize_dimensions(dimensions: object) -> tuple[str, ...]:
    """Ejes de atributos válidos para medir variedad (V3.48, pura).

    Acepta un iterable de nombres de dimensión; filtra vacíos y cae a
    `CONTEXT_DIMENSIONS` si no queda ninguno (o si el valor no es iterable). Es
    el punto único que permite reutilizar `context_dimensions` tanto para el gate
    (ejes core) como para la variedad informativa. Nunca lanza.
    """
    if isinstance(dimensions, str):
        candidates: tuple = (dimensions,)
    elif isinstance(dimensions, (list, tuple, set, frozenset)):
        candidates = tuple(dimensions)
    else:
        return CONTEXT_DIMENSIONS
    axes = tuple(
        str(dimension).strip()
        for dimension in candidates
        if str(dimension or "").strip()
    )
    return axes or CONTEXT_DIMENSIONS


def context_dimensions(
    context_ids: object,
    *,
    dimensions: object = CONTEXT_DIMENSIONS,
) -> dict[str, list[str]]:
    """Valores DISTINTOS por dimensión de una colección de contextos (V3.43 → V3.48).

    Devuelve `{dimension: [valores ordenados]}`. Los contextos no reconocidos y
    las dimensiones sin valor se ignoran. Determinista: las listas van
    ordenadas alfabéticamente. `dimensions` permite medir otros ejes (V3.48:
    `CONTEXT_VARIETY_DIMENSIONS`) sin duplicar la lógica; sin él se usan los ejes
    core del gate. Nunca lanza.
    """
    axes = _normalize_dimensions(dimensions)
    values: dict[str, set[str]] = {dimension: set() for dimension in axes}
    try:
        iterable = list(context_ids or ())
    except TypeError:
        iterable = []
    for raw in iterable:
        attributes = _as_attributes(raw)
        for dimension in axes:
            value = (attributes.get(dimension) or "").strip()
            if value:
                values[dimension].add(value)
    return {
        dimension: sorted(values[dimension])
        for dimension in axes
        if values[dimension]
    }


def context_variety(context_ids: object) -> dict:
    """Variedad INFORMATIVA de una colección de contextos (V3.48, pura).

    Gemela de `context_diversity` sobre `CONTEXT_VARIETY_DIMENSIONS`
    (`register`/`lexical_environment`/`syntactic_focus`). NO alimenta el gate de
    evidencia, que sigue midiéndose sobre los ejes core: es explicabilidad y
    reporte. Devuelve:

    - `dimensions` — `{dimensión: [valores distintos]}`;
    - `varied_dimensions` — nº de ejes con >= 2 valores distintos;
    - `score` — `varied_dimensions / len(dimensions)` (0.0 sin dimensiones).

    Nunca lanza.
    """
    dimensions = context_dimensions(
        context_ids, dimensions=CONTEXT_VARIETY_DIMENSIONS
    )
    varied_dimensions = sum(
        1 for values in dimensions.values() if len(values) >= 2
    )
    score = (
        round(varied_dimensions / len(dimensions), 4) if dimensions else 0.0
    )
    return {
        "dimensions": dimensions,
        "varied_dimensions": varied_dimensions,
        "score": score,
    }


def context_distance(a: object, b: object) -> int:
    """Nº de dimensiones en las que dos contextos difieren (V3.43, pura).

    Acepta dicts, `id` o `context_id`. Si alguno no se reconoce devuelve 0: sin
    atributos no se puede afirmar distancia (no se inventa).
    """
    first = _as_attributes(a)
    second = _as_attributes(b)
    if not first or not second:
        return 0
    return sum(
        1
        for dimension in CONTEXT_DIMENSIONS
        if (first.get(dimension) or "") != (second.get(dimension) or "")
    )


def context_diversity(context_ids: object) -> dict:
    """Diversidad contextual REAL de una colección de contextos (V3.43, pura).

    No basta con ``context_id A != context_id B``: dos contextos pueden generar
    la misma estructura lingüística. Devuelve:

    - `distinct_contexts` — nº de contextos reconocidos distintos;
    - `dimensions` — `{dimension: [valores distintos]}` (`context_dimensions`);
    - `diverse_dimensions` — nº de dimensiones con >= 2 valores distintos;
    - `score` — `diverse_dimensions / len(dimensions)` (0.0 sin dimensiones);
    - `variety` — V3.48: variedad informativa sobre `CONTEXT_VARIETY_DIMENSIONS`
      (`context_variety`). NO entra en el gate: el umbral sigue siendo
      `diverse_dimensions`.

    Nunca lanza: una entrada no iterable se trata como «sin contextos».
    """
    try:
        iterable = list(context_ids or ())
    except TypeError:
        iterable = []
    recognized: set[str] = set()
    for raw in iterable:
        ident = _bare_context_id(
            raw.get("id", "") if isinstance(raw, dict) else raw
        )
        if ident:
            recognized.add(ident)
    dimensions = context_dimensions(iterable)
    diverse_dimensions = sum(
        1 for values in dimensions.values() if len(values) >= 2
    )
    score = (
        round(diverse_dimensions / len(dimensions), 4) if dimensions else 0.0
    )
    return {
        "distinct_contexts": len(recognized),
        "dimensions": dimensions,
        "diverse_dimensions": diverse_dimensions,
        "score": score,
        # V3.48: variedad informativa (no entra en el gate de evidencia).
        "variety": context_variety(iterable),
    }


def _stable_index(word: str, size: int) -> int:
    """Índice 0..size-1 ESTABLE para una palabra (nunca el `hash()` sembrado)."""
    if size <= 0:
        return 0
    checksum = zlib.crc32((word or "").strip().lower().encode("utf-8"))
    return checksum % size


def _novelty_score(context: dict, success_contexts: list[str]) -> int:
    """Distancia MÍNIMA del contexto a los ya logrados (V3.43, pura).

    Maximizar esta cota inferior es lo que hace que el contexto elegido sea
    realmente NUEVO respecto a lo que el alumno ya domina (no solo distinto en
    `context_id`). Sin contextos logrados devuelve 0 (empate → hash estable).
    """
    distances = [
        context_distance(context, success)
        for success in success_contexts
        if _as_attributes(success)
    ]
    return min(distances) if distances else 0


def context_for(
    word: str,
    used_context_ids: object = (),
    *,
    success_context_ids: object = (),
    condition: object = "",
    level: object = "",
    skill: object = "",
    learner_level: object = "",
    learner_level_source: object = "",
    learner_capacity: object = None,
    learner_skill_capacity: object = None,
    capacity_skill: object = "",
    skill_priorities: object = None,
    attempts_by_context: object = None,
) -> dict:
    """Contexto de transferencia que toca practicar (V3.40 → V3.59, puro).

    Devuelve `{word, context_id, topic, prompt, available, exhausted,
    communicative_goal, discourse_type, condition, required_target,
    unscaffolded, cefr,     difficulty_vector, difficulty, skills, target_skill,
    assessed_skill, assessment_mode, item_level, learner_level,
    learner_level_source, learner_capacity, capacity_skill, difficulty_fit,
    skill_priorities, context_instance, instance_index, instance_count}`.
    La consigna es la del banco; el escenario **no contiene la unidad objetivo**
    salvo en la condición `prompted` (V3.43/P1-01 y V3.46). `condition` (V3.46)
    es la condición de recuperación SERVIDA: la deriva el llamador del estado de
    evidencia (`condition_for_state`) y aquí se compone el enunciado con su
    instrucción (`CONDITION_INSTRUCTIONS`).

    Elección, determinista y estable:

    1. se filtra el banco a los contextos cuyo `context_id` no esté en
       `used_context_ids` (contextos que el ítem ya registró en el ledger);
    1b. V3.47: con un `level` CEFR reconocible se prefieren los contextos de
       nivel igual o inferior (y, si ninguno es alcanzable, los del nivel más
       cercano por arriba). Sin `level` el comportamiento es el de V3.46;
    1c. V3.50: si se aporta una `skill` (la modalidad limitante del ítem), se
       prefieren los contextos que la declaran en `skills`. Es una PREFERENCIA
       con degradación con gracia: si deja el pool vacío, se ignora;
    1d. V3.52 (P1-02): `level` (CEFR del ítem: TECHO lingüístico) y
       `learner_level` (nivel del alumno: SUELO de reto) se comparan VECTOR
       contra VECTOR por dimensión con el Difficulty Engine 2.0
       (`services.difficulty`); `learner_level_source` fija la tolerancia
       (estricta solo si el suelo es DEMOSTRADO). Sin niveles reconocibles el
       comportamiento es el de V3.46/V3.47. V3.53: un `learner_capacity`
       explícito (capacidad OBSERVADA) sustituye al suelo declarado del nivel,
       conservando el máximo con el ítem. `skill_priorities` es informativo
       (se devuelve tal cual para explicar la elección);
    1e. V3.54 (Student Skill State 3.0): `learner_skill_capacity` (capacidad
       observada por SKILL × dimensión, `services.learner_skill`) resuelve la
       capacidad de la modalidad que ESTA tarea puede medir (`capacity_skill`,
       por defecto el `assessed_skill` del transfer): la evidencia de otra
       modalidad ya no eleva su reto. Con cobertura dimensional PARCIAL, el gate
       de `services.difficulty` solo aplica la subida a los contextos cuyas
       dimensiones están cubiertas; el resto se evalúa contra el suelo declarado.
       Sin `learner_skill_capacity` el comportamiento es el de V3.53;
    1f. V3.59 (Context Engine 3.0): elegida la FAMILIA, se resuelve su SUPERFICIE
       con `attempts_by_context` (el mapa `contexts` del resumen de evidencia):
       el intento N del ítem en esa familia sirve la superficie
       `N % nº_superficies` (`context_instance_index`), de modo que la primera
       estancia sirve la consigna histórica y las siguientes no repiten
       redacción. Sin ese dato la superficie es la 0, EXACTA a V3.58. La
       superficie NO entra en el pool, la novedad, la distancia ni la dificultad:
       la familia servida es la misma que en V3.58;
    2. entre los candidatos, si se aportan los contextos ya logrados con éxito
       (`success_context_ids`), se prefiere el de mayor DISTANCIA mínima a ellos
       (el más novedoso pedagógicamente, V3.43/P1-03); los empates los resuelve
       `_stable_index(word)`, de modo que la misma palabra y la misma evidencia
       producen siempre la misma consigna;
    3. si ya se usaron todos, se ROTA igual sobre el banco COMPLETO (nunca deja
       al alumno sin tarea), marcando `exhausted=True`.

    `used_context_ids` acepta un iterable de cadenas o el mapa `contexts` del
    resumen de evidencia. El banco es estático, así que `available` es siempre
    `True` (el campo se mantiene por simetría con los demás GET del drill).
    Nunca lanza.
    """
    unit = (word or "").strip()
    served = normalize_condition(condition) or DEFAULT_TRANSFER_CONDITION
    if isinstance(used_context_ids, dict):
        # Comodidad: se acepta el mapa `contexts` del resumen de evidencia.
        used_context_ids = used_context_ids.keys()
    used: set[str] = set()
    try:
        for raw in used_context_ids or ():
            value = str(raw or "").strip()
            if value:
                used.add(value)
    except TypeError:  # objeto no iterable: se trata como "ninguno usado"
        used = set()
    success: list[str] = []
    try:
        for raw in success_context_ids or ():
            value = str(raw or "").strip()
            if value:
                success.append(value)
    except TypeError:
        success = []
    pool = [c for c in TRANSFER_CONTEXTS if context_id_for(c) not in used]
    exhausted = not pool
    if exhausted:
        pool = list(TRANSFER_CONTEXTS)
    # V3.47: ajusta al nivel del alumno (sin nivel reconocible, pool intacto).
    pool = _within_level(pool, level)
    # V3.50/V3.52: primero se prefiere la modalidad limitante y DESPUÉS se aplica
    # el Difficulty Engine 2.0 sobre ese pool. El reto objetivo solo depende de
    # los niveles (ítem/alumno), así que filtrar por modalidad no lo rebaja.
    pool = _filter_skill(pool, skill)
    # V3.53: capacidad observada del alumno (aditiva). Con {} es V3.52.2 exacto.
    # V3.54: la capacidad por SKILL × dimensión tiene prioridad y resuelve la
    # modalidad que esta tarea mide; el gate de cobertura restringe la subida a
    # los contextos cuyas dimensiones están cubiertas.
    capacity_skill_key = (
        str(capacity_skill or "").strip().lower()
        or task_semantics.assessed_skill_for("transfer")
    )
    covered_dimensions = None
    nested = (
        learner_skill_capacity
        if isinstance(learner_skill_capacity, Mapping)
        else {}
    )
    if nested:
        measured = learner_skill.skill_capacity(
            learner_level, nested, capacity_skill_key
        )
        if measured["coverage"] == learner_skill.COVERAGE_NONE:
            # El skill de la tarea no tiene muestra: no se eleva el reto con la
            # capacidad observada de OTRA modalidad (P1 de V3.54).
            capacity_override: dict[str, int] = {}
        else:
            capacity_override = difficulty.normalize_vector(measured["capacity"])
        if measured["coverage"] == learner_skill.COVERAGE_PARTIAL:
            covered_dimensions = list(measured["covered_dimensions"])
    else:
        capacity_override = difficulty.normalize_vector(learner_capacity)
    challenge, floor_challenge, tolerance = _challenge_and_tolerance(
        level, learner_level, learner_level_source, capacity_override
    )
    pool = difficulty.select_by_difficulty(
        pool,
        challenge,
        tolerance=tolerance,
        covered_dimensions=covered_dimensions,
        floor_challenge=floor_challenge,
    )
    # V3.51: dimensiones semánticas de la tarea (idénticas en todos los retornos).
    # `target_skill` es lo que la tarea quiere provocar: la modalidad limitante
    # que pidió el llamador si la hay, o el eje propio del transfer. Los niveles
    # no reconocidos se devuelven como "" (degradación con gracia: el retorno es
    # idéntico al de V3.50 y la elección no cambia).
    requested = str(skill or "").strip().lower()
    target_skill = requested or task_semantics.target_skill_for("transfer")
    assessed_skill = task_semantics.assessed_skill_for("transfer")
    assessment_mode = task_semantics.assessment_mode_for("transfer")
    item_level = str(level or "").strip().upper() if cefr_index(level) >= 0 else ""
    learner = (
        str(learner_level or "").strip().upper()
        if cefr_index(learner_level) >= 0
        else ""
    )
    level_source = _normalize_source(learner_level_source)
    priorities = (
        {str(k): float(v) for k, v in skill_priorities.items()}
        if isinstance(skill_priorities, dict)
        else {}
    )
    if not pool:  # banco vacío: no se inventa contenido
        return {
            "word": unit,
            "context_id": "",
            "topic": "",
            "prompt": "",
            "available": False,
            "exhausted": True,
            "communicative_goal": "",
            "discourse_type": "",
            "condition": served,
            "required_target": requires_target(served),
            "unscaffolded": is_unscaffolded(served),
            "cefr": "",
            "difficulty_vector": {},
            "difficulty": 0,
            "skills": [],
            "target_skill": target_skill,
            "assessed_skill": assessed_skill,
            "assessment_mode": assessment_mode,
            "item_level": item_level,
            "learner_level": learner,
            # V3.52: origen del suelo y encaje del reto (aditivos).
            # V3.53: capacidad observada que elevó el suelo ({} si no hay).
            "learner_level_source": level_source,
            "learner_capacity": dict(capacity_override),
            # V3.54: modalidad cuya capacidad observada se aplicó ("" sin skill).
            "capacity_skill": capacity_skill_key,
            "difficulty_fit": _difficulty_fit_for(None, challenge, tolerance),
            "skill_priorities": priorities,
            # V3.59: banco vacío → no hay familia ni superficie que servir.
            "context_instance": "",
            "instance_index": 0,
            "instance_count": 0,
        }
    if success:
        best = max(_novelty_score(context, success) for context in pool)
        # Se conserva el orden del banco dentro del empate: `_stable_index` es
        # función del pool, así que un empate no depende del orden del dict.
        pool = [c for c in pool if _novelty_score(c, success) == best]
    context = pool[_stable_index(unit, len(pool))]
    vector = dict(context.get("difficulty_vector") or {})
    # V3.59: la FAMILIA ya está elegida (misma que V3.58); ahora se resuelve su
    # SUPERFICIE por rotación de intentos sobre esa familia.
    instances = context_instances(context)
    instance_index = context_instance_index(
        context, _attempts_for(attempts_by_context, context_id_for(context))
    )
    instance = {"instance": "", "prompt": ""}
    if instances:
        instance = instances[instance_index]
    return {
        "word": unit,
        "context_id": context_id_for(context),
        "topic": context.get("topic", ""),
        "prompt": _compose_prompt(instance["prompt"], served, unit),
        "available": True,
        "exhausted": exhausted,
        "communicative_goal": context.get("communicative_goal", ""),
        "discourse_type": context.get("discourse_type", ""),
        "condition": served,
        "required_target": requires_target(served),
        "unscaffolded": is_unscaffolded(served),
        # V3.47: nivel y carga del contexto servido (aditivos).
        "cefr": context.get("cefr", ""),
        "difficulty_vector": vector,
        "difficulty": difficulty_from_vector(vector),
        # V3.50: competencias que declara el contexto servido (aditivo). Es la
        # INTENCIÓN pedagógica del escenario (`context_skills`), no la modalidad
        # que la tarea puede evaluar (ver `assessed_skill`).
        "skills": list(context_skills(context)),
        # V3.51 (P1-01/P1-02): dimensiones explícitas de la tarea y de la
        # dificultad (todas aditivas).
        "target_skill": target_skill,
        "assessed_skill": assessed_skill,
        "assessment_mode": assessment_mode,
        "item_level": item_level,
        "learner_level": learner,
        # V3.52 (P1-02): origen del suelo y encaje VECTOR a VECTOR del contexto
        # servido contra el reto objetivo (aditivos).
        # V3.53: capacidad observada que elevó el suelo ({} si no hay).
        "learner_level_source": level_source,
        "learner_capacity": dict(capacity_override),
        # V3.54: modalidad cuya capacidad observada se aplicó ("" sin skill).
        "capacity_skill": capacity_skill_key,
        "difficulty_fit": _difficulty_fit_for(
            context,
            difficulty.challenge_for(
                vector,
                challenge,
                covered_dimensions=covered_dimensions,
                floor_challenge=floor_challenge,
            ),
            tolerance,
        ),
        "skill_priorities": priorities,
        # V3.59 (Context Engine 3.0): superficie declarada servida de la familia
        # ("" = la histórica), su índice y cuántas tiene la familia.
        "context_instance": instance["instance"],
        "instance_index": instance_index,
        "instance_count": len(instances),
    }


def _compose_prompt(scenario: str, condition: str, word: str) -> str:
    """Consigna servida = escenario + instrucción de la condición (V3.46, pura).

    `cued_context` devuelve el escenario tal cual (V3.43). Nunca lanza.
    """
    base = (scenario or "").strip()
    instruction = condition_instruction(condition, word)
    if not instruction:
        return base
    return f"{base} {instruction}".strip()

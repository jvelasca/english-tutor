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
(`skill`, derivada por el llamador del planner) y la prefiere; además ajusta a la
banda de dificultad alcanzable (`TRANSFER_DIFFICULTY_BAND`) para no servir el
contexto más plano del banco a un alumno avanzado. Los dos filtros son
PREFERENCIAS con degradación con gracia y no tocan la escalera `transfer_state`,
sus umbrales, el scoring ni FSRS. El `skills` del contexto servido se expone de
forma aditiva.

No usa LLM ni aleatoriedad con estado: la rotación se deriva de un hash ESTABLE
(`zlib.crc32`, no el `hash()` de Python, que va sembrado por proceso) y de los
contextos ya registrados en el ledger (`context_id`), así que la misma evidencia
produce siempre la misma consigna.
"""

from __future__ import annotations

import zlib

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

# V3.47: dimensiones de CARGA del contexto de transferencia (misma convención que
# el `difficulty_vector` de listening/speaking: enteros 1..5). No entran en la
# diversidad contextual (son dificultad, no atributo de variedad).
TRANSFER_DIFFICULTY_KEYS: tuple[str, ...] = (
    "lexical",
    "syntax",
    "discourse",
    "interaction",
)

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
# exigente ALCANZABLE por el alumno. Con banda 1, un ítem B2 recibe contextos de
# dificultad >= (máximo alcanzable - 1): se evita servir el contexto más plano del
# banco cuando hay uno más cercano a su nivel. Declarado y calibrable.
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


def _difficulty_floor(pool: list[dict], level: object) -> int:
    """Dificultad mínima admisible para el nivel del alumno (V3.50, pura).

    El «objetivo» es la MAYOR de dos referencias: el techo de dificultad real de
    los contextos alcanzables y la posición del nivel en la escala 1..6
    (A1≈1 … C2≈6, la misma escala que `difficulty_from_vector`). Anclar al nivel
    evita que un item B1 reciba el contexto A1 más plano cuando el techo
    declarado de su alcance es bajo. Devuelve `1` (sin filtro) si el nivel no se
    reconoce o no hay contextos alcanzables: comportamiento de V3.47. Nunca
    lanza.
    """
    index = cefr_index(level)
    if index < 0:
        return 1
    reachable = [
        context
        for context in pool
        if 0 <= cefr_index(context.get("cefr")) <= index
    ]
    if not reachable:
        return 1
    ceiling = max(
        difficulty_from_vector(context.get("difficulty_vector"))
        for context in reachable
    )
    target = max(ceiling, index + 1)
    return max(1, target - TRANSFER_DIFFICULTY_BAND)


def _within_band(pool: list[dict], floor: int) -> list[dict]:
    """Conserva los contextos dentro de la banda de dificultad (V3.50, pura).

    Si la banda pedida no existe en el pool (p. ej. la modalidad filtrada no
    tiene contextos tan difíciles), degrada con gracia a lo MÁS DIFÍCIL
    disponible: nunca devuelve algo más plano de lo necesario ni deja el pool
    vacío. Con `floor <= 1` devuelve el pool intacto. Nunca lanza.
    """
    if floor <= 1 or not pool:
        return pool
    band = [
        context
        for context in pool
        if difficulty_from_vector(context.get("difficulty_vector")) >= floor
    ]
    if band:
        return band
    best = max(
        difficulty_from_vector(context.get("difficulty_vector"))
        for context in pool
    )
    return [
        context
        for context in pool
        if difficulty_from_vector(context.get("difficulty_vector")) == best
    ]

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
) -> dict:
    """Contexto de transferencia que toca practicar (V3.40 → V3.50, puro).

    Devuelve `{word, context_id, topic, prompt, available, exhausted,
    communicative_goal, discourse_type, condition, required_target,
    unscaffolded, cefr, difficulty_vector, difficulty, skills}`. La consigna es
    la del banco; el escenario **no contiene la unidad objetivo** salvo en la
    condición `prompted` (V3.43/P1-01 y V3.46). `condition` (V3.46) es la
    condición de recuperación SERVIDA: la deriva el llamador del estado de
    evidencia (`condition_for_state`) y aquí se compone el enunciado con su
    instrucción (`CONDITION_INSTRUCTIONS`).

    Elección, determinista y estable:

    1. se filtra el banco a los contextos cuyo `context_id` no esté en
       `used_context_ids` (contextos que el ítem ya registró en el ledger);
    1b. V3.47: con un `level` CEFR reconocible se prefieren los contextos de
       nivel igual o inferior (y, si ninguno es alcanzable, los del nivel más
       cercano por arriba). Sin `level` el comportamiento es el de V3.46;
    1c. V3.50: si se aporta una `skill` (la modalidad LIMITANTE del ítem), se
       prefieren los contextos que la declaran en `skills`; y se prefiere la
       banda de dificultad alcanzable (`_difficulty_band`), para no servir el
       contexto más plano del banco a un alumno avanzado. Ambos filtros son
       PREFERENCIAS con degradación con gracia: si dejan el pool vacío, se
       ignoran;
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
    # V3.50: el mínimo de dificultad se calcula sobre TODO el alcance del nivel
    # (antes de filtrar por modalidad, para no rebajar el objetivo al filtrar) y
    # luego se prioriza la modalidad limitante y la banda. Ambos filtros degradan
    # con gracia: si la modalidad no tiene contextos, se ignora; si la banda no
    # existe, se queda con lo más difícil disponible.
    floor = _difficulty_floor(pool, level)
    pool = _filter_skill(pool, skill)
    pool = _within_band(pool, floor)
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
        }
    if success:
        best = max(_novelty_score(context, success) for context in pool)
        # Se conserva el orden del banco dentro del empate: `_stable_index` es
        # función del pool, así que un empate no depende del orden del dict.
        pool = [c for c in pool if _novelty_score(c, success) == best]
    context = pool[_stable_index(unit, len(pool))]
    vector = dict(context.get("difficulty_vector") or {})
    return {
        "word": unit,
        "context_id": context_id_for(context),
        "topic": context.get("topic", ""),
        "prompt": _compose_prompt(context.get("prompt", ""), served, unit),
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
        # V3.50: competencias que declara el contexto servido (aditivo).
        "skills": list(context_skills(context)),
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

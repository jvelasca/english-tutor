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

V3.60 (**Context Engine 4.0: Instance Specification → Parameterized Instance**)
cierra el P1 que la auditoría de V3.59 dejó abierto: tres redacciones por familia
se agotan en tres intentos y el alumno puede prepararlas de memoria. En lugar de
añadir consignas a mano, cada familia declara un ESPACIO paramétrico
(`instance_space`: una `template` con slots y sus valores) del que se GENERAN
superficies deterministas de la MISMA identidad: la familia sigue siendo la
unidad de EVIDENCIA y el contenido sigue siendo declarado, porque lo que se
genera es la COMBINACIÓN de valores, no el texto. La superficie 0 sigue siendo
la consigna histórica y `space[:3]` reproduce byte a byte las tres superficies
de V3.59, así que la rotación no cambia: se prolonga. Una superficie puede
declarar metadatos NO identitarios (`scenario`/`goal`/`register`), las
competencias que añade (`skill_delta`) y un AJUSTE de carga (`difficulty_delta`)
que hace explícita la dificultad EFECTIVA de la tarea servida —el P2 «las
instancias cambian la dificultad sin poder declararlo»—, sin tocar
`context_difficulty` (la familia), los umbrales ni el ledger: sin delta la
degradación es exacta a V3.59.

V3.61 (**Instance-aware Evidence + Anti-spoiler Guard**) cierra los dos defectos
funcionales que la auditoría `T` de V3.60 reprodujo:

- **T-01, fuga del target.** V3.60 garantizaba el invariante de V3.43 (la
  consigna da ESCENARIO, nunca la unidad objetivo) sobre la PLANTILLA, pero no
  sobre los VALORES de slot: la familia `shopping` servía en su índice 7 «You are
  in a supermarket and cannot find what you need…». `available_instance_details`
  retira de la rotación toda superficie que NOMBRE la unidad (`_reveals_target`,
  léxico y determinista), `context_for` retira del pool las familias sin
  superficie segura y declara `instance_suppressed`/`instance_guarded`.
- **T-02, identidad de instancia.** `serve_instance` resuelve la superficie que el
  alumno **respondió** por su slug inmutable (`context_instance`, derivado del
  contenido), de modo que la carga que el ledger persiste es la de ESA superficie
  y no la de la siguiente rotación.

Además aborda la parte determinista de los P1 de la auditoría `S`: la rotación
deja de ser el orden declarado a partir del tercer intento (semilla
`(familia, unidad)`, biyección del tramo), `_expand_spec` reparte el techo
`CONTEXT_INSTANCE_SPACE_MAX` de forma estratificada en lugar de por prefijo, cada
familia declara un TERCER eje (`constraint`) que sube el banco de **358 a 1020
superficies** (51 por familia) y `services/transfer_audit.py` valida el contenido
del espacio (deltas justificados, `register` coherente con la familia, competencias
canónicas, ausencia de callejones sin salida para una unidad objetivo) con avisos
heurísticos de equivalencia pedagógica.
"""

from __future__ import annotations

import re
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

# V3.59 (Context Engine 3.0) → V3.60 (Context Engine 4.0): claves que puede
# declarar una INSTANCIA de familia. Sigue siendo una lista BLANCA, ampliada con
# METADATOS NO IDENTITARIOS: además de su etiqueta y su consigna, una superficie
# puede describir su `scenario`/`goal`/`register` (qué situación concreta y con
# qué registro sirve) y el AJUSTE de carga que introduce (`difficulty_delta`) o
# las competencias que añade (`skill_delta`). Lo que sigue PROHIBIDO es la
# identidad: `id`, las seis dimensiones core, `cefr`, `difficulty_vector`,
# `skills`, `lexical_environment` y `syntactic_focus` no se pueden declarar en
# una instancia (lo fija un test: la intersección con las claves de familia es
# exactamente `{"prompt"}`, porque la consigna es la única clave compartida).
CONTEXT_INSTANCE_KEYS: tuple[str, ...] = (
    "instance",
    "prompt",
    "scenario",
    "goal",
    "register",
    "difficulty_delta",
    "skill_delta",
)

# V3.59: nº mínimo de superficies ADICIONALES que debe declarar cada familia. Es
# el invariante anti-memorización de la release y está verificado por test: con
# una sola superficie declarada la rotación sería inerte.
CONTEXT_INSTANCES_MIN = 2

# V3.60 (Context Engine 4.0): nº mínimo de superficies TOTALES por familia (la 0
# histórica, las declaradas y las GENERADAS por la especificación paramétrica).
# Es el invariante anti-memorización de Context Engine 4.0: con tres redacciones
# el alumno agotaba la familia en tres intentos; con >=12 la rotación no se
# puede aprender de memoria y sigue siendo determinista y explicable.
CONTEXT_INSTANCE_SPACE_MIN = 12

# V3.60: TECHO del espacio de una familia. La expansión es determinista. V3.61:
# cuando el producto cartesiano excede este techo el recorte es ESTRATIFICADO
# (reparto equiespaciado, `_stratified_indices`), no un prefijo: ningún eje queda
# con un subconjunto fijo de valores. El banco real (4 × 4 × 3 = 48 combinaciones
# por familia) queda muy por debajo del techo.
CONTEXT_INSTANCE_SPACE_MAX = 96

# V3.61 (P1-01): el banco declara un TERCER eje (`constraint`: qué debe hacer la
# respuesta) en cada familia, así que el espacio real pasa de 16 a 48
# combinaciones (51 superficies contando la histórica y las declaradas) por
# familia y el banco de **358 a 1020 superficies** sin escribir ninguna consigna a
# mano: sigue siendo contenido DECLARADO. Reduce la memorizabilidad (el alumno ya
# no puede enumerar el conjunto), aunque no la elimina: el cierre real es el
# `Instance Generator 2.0` (V3.65).

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
        # V3.60 (Context Engine 4.0): ESPACIO paramétrico de superficies de la
        # MISMA familia (ver `context_instance_details`). La plantilla se combina
        # con los slots en el orden de `selection`; las superficies generadas
        # ocupan los índices siguientes a las declaradas arriba.
        "instance_space": {
            "template": (
                "Tell a short story about {what} that happened {when}. "
                "{constraint}"
            ),
            "selection": ("what", "when"),
            # V3.61 (P1-01): tercer eje declarado (`constraint`). Sube el espacio
            # real de 16 a 48 combinaciones por familia sin superar el techo y sin
            # generar texto: sigue siendo contenido DECLARADO.
            "slots": {
                "constraint": (
                    "Keep it short so the listener can follow.",
                    "Make the ending clear.",
                    "Say how the people felt.",
                ),
                "what": (
                    {"value": "a journey", "scenario": "a journey in the past"},
                    {"value": "a surprise", "scenario": "an unexpected event"},
                    {"value": "a mistake", "scenario": "something that went wrong"},
                    {"value": "a coincidence", "scenario": "an unlikely coincidence"},
                ),
                "when": (
                    "last year",
                    "at the weekend",
                    "during a holiday",
                    "when you were younger",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Write a question to ask a friend {moment}. "
                "You want to know about {topic}. {constraint}"
            ),
            "selection": ("topic", "moment"),
            "slots": {
                "constraint": (
                    "Ask only one question.",
                    "Say why you want to know.",
                    "Offer to help in return.",
                ),
                "topic": (
                    {"value": "their weekend", "scenario": "a friend's weekend"},
                    {"value": "their family", "scenario": "a friend's family"},
                    {"value": "their new job", "scenario": "a friend's new job"},
                    {"value": "their holiday plans", "scenario": "a friend's plans"},
                ),
                "moment": (
                    "when you meet them",
                    "on the phone",
                    "in a message",
                    "after a long time",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        # El `change` es la SITUACIÓN y el `focus` lo que se describe: es el
        # P1 de la auditoría de V3.59 (una instancia puede cambiar el escenario
        # real) hecho declarable sin tocar la identidad de la familia.
        "instance_space": {
            "template": (
                "You have {change}. Describe {focus} to a colleague. "
                "{constraint}"
            ),
            "selection": ("change", "focus"),
            "slots": {
                "constraint": (
                    "Say what changed in your routine.",
                    "Mention one benefit and one difficulty.",
                    "Explain how long it took to get used to it.",
                ),
                "change": (
                    {"value": "a new job", "scenario": "a first week in a new job"},
                    {"value": "changed offices", "scenario": "a new workplace"},
                    {"value": "started a new project", "scenario": "a new project"},
                    {"value": "a new manager", "scenario": "a change of manager"},
                ),
                "focus": (
                    "something interesting about your first week",
                    "your new workplace",
                    "one task you do every day",
                    "the people you work with",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": "Talk about your plans for {period} {detail}. {constraint}",
            "selection": ("period", "detail"),
            "slots": {
                "constraint": (
                    "Explain the reason for your choice.",
                    "Say what you need to prepare.",
                    "Mention one possible problem.",
                ),
                "period": (
                    {"value": "next month", "scenario": "short-term plans"},
                    {"value": "next summer", "scenario": "summer plans"},
                    {"value": "next year", "scenario": "the year ahead"},
                    {"value": "the next few weeks", "scenario": "the near future"},
                ),
                "detail": (
                    "and say why",
                    "and who you will be with",
                    "and what you need to do first",
                    "and how you will prepare",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Give your opinion about {topic} to {audience}, and say why. "
                "{constraint}"
            ),
            "selection": ("topic", "audience"),
            "slots": {
                "constraint": (
                    "Give one reason and one example.",
                    "Acknowledge the other side.",
                    "End with a clear recommendation.",
                ),
                "topic": (
                    {
                        "value": "a school subject you liked or disliked",
                        "scenario": "school and learning",
                    },
                    {"value": "living in a big city", "scenario": "city life"},
                    {
                        "value": "learning languages online",
                        "scenario": "online learning",
                    },
                    {
                        "value": "how much homework students get",
                        "scenario": "homework and school work",
                    },
                ),
                "audience": (
                    "a friend",
                    "your classmates",
                    "a teacher",
                    "someone who disagrees with you",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Describe a problem you had {where} {when} "
                "and how you solved it. {constraint}"
            ),
            "selection": ("where", "when"),
            "slots": {
                "constraint": (
                    "Say what you tried first.",
                    "Explain how you felt at the time.",
                    "Mention what you learnt from it.",
                ),
                "where": (
                    {"value": "at home", "scenario": "a problem at home"},
                    {"value": "on a trip", "scenario": "a problem while travelling"},
                    {"value": "at work", "scenario": "a problem at work"},
                    {"value": "at school", "scenario": "a problem at school"},
                ),
                "when": ("last month", "last week", "recently", "a few years ago"),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "You meet someone new at {place}. "
                "Introduce yourself and {info}. {constraint}"
            ),
            "selection": ("place", "info"),
            "slots": {
                "constraint": (
                    "Mention one thing you have in common.",
                    "Ask one question back.",
                    "Say how you would like to keep in touch.",
                ),
                "place": (
                    {"value": "a class", "scenario": "a new class"},
                    {"value": "a party", "scenario": "a social event"},
                    {"value": "a sports club", "scenario": "a sports club"},
                    {"value": "a new job", "scenario": "a first day at work"},
                ),
                "info": (
                    "say where you are from",
                    "say what you do",
                    "say what you like doing",
                    "say why you are there",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": "Describe what you usually do {when} {where}. {constraint}",
            "selection": ("when", "where"),
            "slots": {
                "constraint": (
                    "Say how often you do it.",
                    "Mention one thing you would change.",
                    "Explain why it matters to you.",
                ),
                "when": (
                    {"value": "on a normal morning", "scenario": "a morning routine"},
                    {"value": "on a normal evening", "scenario": "an evening routine"},
                    {"value": "at the weekend", "scenario": "a weekend routine"},
                    {"value": "on a day off", "scenario": "a day off"},
                ),
                "where": (
                    "at home",
                    "before school or work",
                    "with your family",
                    "when you have some free time",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "You need to get to {place} in a city you do not know. "
                "Ask a passer-by {how}. {constraint}"
            ),
            "selection": ("place", "how"),
            "slots": {
                "constraint": (
                    "Repeat the route back to check it.",
                    "Ask the person to speak slowly.",
                    "Thank them and confirm one detail.",
                ),
                "place": (
                    {"value": "the station", "scenario": "finding the station"},
                    {"value": "the market", "scenario": "finding the market"},
                    {"value": "a pharmacy", "scenario": "finding a pharmacy"},
                    {"value": "the nearest bank", "scenario": "finding a bank"},
                ),
                "how": (
                    {"value": "how to get there", "goal": "ask for directions"},
                    {"value": "which way to go", "goal": "ask for directions"},
                    {
                        "value": "where you can find it",
                        "goal": "ask for the location of a place",
                    },
                    {"value": "if it is far from here", "goal": "ask about distance"},
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "You are in {place} and {problem}. Ask an assistant for "
                "help. {constraint}"
            ),
            "selection": ("place", "problem"),
            "slots": {
                "constraint": (
                    "Explain what you have already tried.",
                    "Ask whether there is a cheaper option.",
                    "Say how much time you have.",
                ),
                "place": (
                    {"value": "a clothes shop", "scenario": "buying clothes"},
                    {"value": "a supermarket", "scenario": "doing the shopping"},
                    {"value": "a bookshop", "scenario": "buying a book"},
                    {"value": "a shoe shop", "scenario": "buying shoes"},
                ),
                "problem": (
                    "cannot find what you need",
                    "like something but it is the wrong size",
                    "cannot find the price of something",
                    "want to change something you bought",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        # El `symptom` es la SITUACIÓN concreta (la auditoría de V3.59 observó que
        # las superficies cambian de escenario sin poder declararlo).
        "instance_space": {
            "template": (
                "You {symptom}. Explain it to {who} and answer their questions. "
                "{constraint}"
            ),
            "selection": ("symptom", "who"),
            "slots": {
                "constraint": (
                    "Say how long you have felt like this.",
                    "Mention what you have already taken.",
                    "Ask what you should avoid.",
                ),
                "symptom": (
                    {"value": "do not feel well", "scenario": "feeling unwell"},
                    {"value": "have a bad cough", "scenario": "a bad cough"},
                    {"value": "have a headache", "scenario": "a headache"},
                    {"value": "have trouble sleeping", "scenario": "sleep problems"},
                ),
                "who": (
                    "a doctor",
                    "a pharmacist",
                    "a nurse",
                    "a doctor at a check-up",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "{plan} with a friend: suggest where to go and why, "
                "and {agree}. {constraint}"
            ),
            "selection": ("plan", "agree"),
            "slots": {
                "constraint": (
                    "Mention the budget.",
                    "Agree on one thing and disagree on another.",
                    "Set a date before you finish.",
                ),
                "plan": (
                    {"value": "Plan a weekend away", "scenario": "a short trip"},
                    {"value": "Plan a longer trip", "scenario": "a long trip"},
                    {"value": "Plan a visit to family", "scenario": "visiting family"},
                    {"value": "Plan a day out", "scenario": "a day out"},
                ),
                "agree": (
                    "agree on the details",
                    "agree on the dates",
                    "agree on how much to spend",
                    "agree on who to invite",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "{incident} on a project at work. Explain to a colleague "
                "what happened and {action}. {constraint}"
            ),
            "selection": ("incident", "action"),
            "slots": {
                "constraint": (
                    "Say what you need from your colleague.",
                    "Explain the effect on the deadline.",
                    "Suggest one way to prevent it next time.",
                ),
                "incident": (
                    {"value": "Something went wrong", "scenario": "an unclear problem"},
                    {"value": "A delivery arrived late", "scenario": "a late delivery"},
                    {
                        "value": "An important file was missing",
                        "scenario": "a missing file",
                    },
                    {
                        "value": "A client changed the plan",
                        "scenario": "a change requested by a client",
                    },
                ),
                "action": (
                    "how you fixed it",
                    "what you did next",
                    "how the team reacted",
                    "what you learned from it",
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Propose one change to {change} and explain why {who} "
                "should support it. {constraint}"
            ),
            "selection": ("change", "who"),
            "slots": {
                "constraint": (
                    "Mention what it would cost.",
                    "Answer one likely objection.",
                    "Say who should act first.",
                ),
                "change": (
                    {
                        "value": "improve your neighbourhood",
                        "scenario": "the neighbourhood",
                    },
                    {
                        "value": "make your neighbourhood greener",
                        "scenario": "green spaces",
                    },
                    {
                        "value": "the shared spaces of your building",
                        "scenario": "shared spaces",
                    },
                    {"value": "make your street safer", "scenario": "street safety"},
                ),
                "who": (
                    "your neighbours",
                    "the people in your building",
                    "other families in the area",
                    {
                        "value": "the local council",
                        "goal": "persuade an institution",
                        "difficulty_delta": {"interaction": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        # El `qualifier` es la primera superficie que declara AJUSTE de carga y
        # competencias: la dificultad EFECTIVA pasa a ser explícita.
        "instance_space": {
            "template": (
                "Take a position on {issue} and defend it against an "
                "opposing view {qualifier}. {constraint}"
            ),
            "selection": ("issue", "qualifier"),
            "slots": {
                "constraint": (
                    "Concede one point before you answer.",
                    "Support your view with one example.",
                    "Close with a direct challenge.",
                ),
                "issue": (
                    {"value": "a social issue", "scenario": "an open social issue"},
                    {
                        "value": "the balance between work and private life",
                        "scenario": "work and private life",
                    },
                    {
                        "value": "technology and personal privacy",
                        "scenario": "technology and privacy",
                    },
                    {
                        "value": "the cost of higher education",
                        "scenario": "higher education",
                    },
                ),
                "qualifier": (
                    {"value": "in a discussion", "goal": "argue orally"},
                    {
                        "value": "in front of a critical audience",
                        "scenario": "a critical audience",
                        "goal": "argue orally",
                        "difficulty_delta": {"interaction": 1},
                    },
                    {
                        "value": "in a short written contribution",
                        "goal": "argue in writing",
                        "register": "formal",
                        "skill_delta": ("written_production",),
                    },
                    {
                        "value": "and respond to a counterargument",
                        "goal": "rebut a counterargument",
                        "difficulty_delta": {"discourse": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Review {work} you have recently experienced, weighing its "
                "strengths and weaknesses {angle}. {constraint}"
            ),
            "selection": ("work", "angle"),
            "slots": {
                "constraint": (
                    "Give one example from your own experience.",
                    "Say who would enjoy it most.",
                    "End with a clear verdict.",
                ),
                "work": (
                    {"value": "a film or a book", "scenario": "a film or a book"},
                    {"value": "a series", "scenario": "a series"},
                    {
                        "value": "an exhibition or a concert",
                        "scenario": "an exhibition",
                    },
                    {"value": "a play or a musical", "scenario": "a play or a musical"},
                ),
                "angle": (
                    {
                        "value": "from the point of view of its audience",
                        "goal": "evaluate for an audience",
                    },
                    {
                        "value": "and comparing it with something similar",
                        "goal": "compare two works",
                        "difficulty_delta": {"discourse": 1},
                    },
                    {"value": "focusing on its message", "goal": "interpret"},
                    {
                        "value": "and recommending it to a specific audience",
                        "goal": "recommend",
                        "difficulty_delta": {"interaction": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "{parties} disagree {about}. Explain each side to the other "
                "and help them reach an understanding. {constraint}"
            ),
            "selection": ("parties", "about"),
            "slots": {
                "constraint": (
                    "Stay neutral throughout.",
                    "Summarise one point from each side.",
                    "Propose one first step.",
                ),
                "parties": (
                    {"value": "Two people you know", "scenario": "two acquaintances"},
                    {
                        "value": "Two members of your family",
                        "scenario": "a family conflict",
                    },
                    {"value": "Two colleagues", "scenario": "a conflict at work"},
                    {
                        "value": "Two of your neighbours",
                        "scenario": "a conflict between neighbours",
                    },
                ),
                "about": (
                    {"value": "about a decision", "scenario": "a decision"},
                    {
                        "value": "about how to organise some work",
                        "scenario": "organising work",
                    },
                    {"value": "about money", "scenario": "a disagreement about money"},
                    {
                        "value": "about who should do what",
                        "scenario": "a disagreement about responsibilities",
                        "difficulty_delta": {"interaction": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Present {thing} from a field you know well and respond "
                "to {question}. {constraint}"
            ),
            "selection": ("thing", "question"),
            "slots": {
                "constraint": (
                    "Define one key term.",
                    "Give an example from outside your field.",
                    "Mention one limitation.",
                ),
                "thing": (
                    {"value": "an argument", "scenario": "an argument"},
                    {"value": "a method you use", "scenario": "a method"},
                    {"value": "a claim", "scenario": "a claim"},
                    {"value": "a result from a study", "scenario": "a study result"},
                ),
                "question": (
                    {
                        "value": "a critical question about your evidence",
                        "goal": "justify the evidence",
                    },
                    {
                        "value": "a counterexample an expert raises",
                        "goal": "rebut a counterexample",
                        "difficulty_delta": {"interaction": 1},
                    },
                    {
                        "value": "a question about your method",
                        "goal": "justify the method",
                    },
                    {
                        "value": "a question about how your claim applies elsewhere",
                        "goal": "generalise a claim",
                        "difficulty_delta": {"discourse": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Negotiate {term} with a counterpart who {demand}, and "
                "justify the concessions you are willing to make. {constraint}"
            ),
            "selection": ("term", "demand"),
            "slots": {
                "constraint": (
                    "Make one concession conditional.",
                    "Ask for something in return.",
                    "Summarise the agreement at the end.",
                ),
                "term": (
                    {"value": "the terms of an agreement", "scenario": "an agreement"},
                    {"value": "a budget", "scenario": "a budget"},
                    {"value": "a deadline", "scenario": "a deadline"},
                    {"value": "the scope of a project", "scenario": "a project scope"},
                ),
                "demand": (
                    {
                        "value": "wants something different",
                        "scenario": "different terms",
                    },
                    {"value": "wants to spend more", "scenario": "a bigger budget"},
                    {"value": "wants it sooner", "scenario": "an earlier deadline"},
                    {
                        "value": "wants a longer commitment",
                        "scenario": "a longer commitment",
                        "difficulty_delta": {"discourse": 1},
                    },
                ),
            },
        },
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
        # V3.60: espacio paramétrico de la familia (ver `context_instance_details`).
        "instance_space": {
            "template": (
                "Deliver a short keynote {occasion} on {theme} and use "
                "concrete examples to make it persuasive. {constraint}"
            ),
            "selection": ("theme", "occasion"),
            "slots": {
                "constraint": (
                    "Open with a concrete example.",
                    "Keep the main message in one sentence.",
                    "End with a call to action.",
                ),
                "theme": (
                    {"value": "an abstract theme", "scenario": "an abstract theme"},
                    {"value": "how people learn", "scenario": "how people learn"},
                    {
                        "value": "how teams change over time",
                        "scenario": "how teams change",
                    },
                    {
                        "value": "how technology changes the way we work",
                        "scenario": "technology and work",
                        "difficulty_delta": {"lexical": 1},
                    },
                ),
                "occasion": (
                    {
                        "value": "to a professional audience",
                        "goal": "persuade professionals",
                    },
                    {"value": "to a small expert group", "goal": "persuade experts"},
                    {"value": "to a general audience", "goal": "explain to everyone"},
                    {
                        "value": "at a company event",
                        "goal": "address a mixed company audience",
                        "difficulty_delta": {"interaction": 1},
                    },
                ),
            },
        },
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


# ---------------------------------------------------------------------------
# V3.60 (Context Engine 4.0): ESPECIFICACIÓN → INSTANCIA PARAMETRIZADA.
#
# V3.59 separó FAMILIA de INSTANCIA pero dejó el banco finito: 20 familias × 3
# redacciones escritas a mano, agotables en tres intentos (el P1 de la auditoría
# de V3.59). V3.60 no añade redacciones a mano: añade un ESPACIO paramétrico por
# familia (`instance_space`) del que se GENERAN superficies deterministas de la
# MISMA identidad. La familia sigue siendo la unidad de evidencia y el contenido
# sigue siendo declarado (no generado por LLM): lo que se genera es la
# COMBINACIÓN de valores declarados, no el texto.
#
# Invariantes (probadas por test):
#   (a) la superficie 0 es SIEMPRE la consigna histórica y `space[:3]` reproduce
#       byte a byte las tres superficies de V3.59 (la rotación no cambia, se
#       prolonga);
#   (b) ninguna clave nueva entra en `CONTEXT_DIMENSIONS`, `context_distance`,
#       `context_diversity`, `_novelty_score` ni el `transfer_state`: la familia
#       elegida es EXACTAMENTE la de V3.59 con la misma evidencia;
#   (c) sin intentos la degradación es exacta (superficie 0 y delta nulo);
#   (d) sin LLM ni aleatoriedad con estado: la expansión recorre el producto
#       cartesiano en orden declarado y la rotación es `attempts % len(space)`.
# ---------------------------------------------------------------------------

# Placeholder de una plantilla de consigna: `{nombre_slot}` en minúsculas.
_TEMPLATE_FIELD = re.compile(r"\{([a-z][a-z0-9_]*)\}")

# Claves de una superficie NORMALIZADA (`context_instance_details`): la lista
# blanca de instancia más `generated`, que distingue una superficie declarada de
# una generada por el espacio paramétrico (explicabilidad; no entra en ninguna
# decisión).
CONTEXT_INSTANCE_DETAIL_KEYS: tuple[str, ...] = (*CONTEXT_INSTANCE_KEYS, "generated")


def _slug(value: object) -> str:
    """Etiqueta canónica de una superficie: minúsculas y `_` (V3.60, pura).

    Se deriva del CONTENIDO declarado (el valor del slot), nunca del orden del
    diccionario ni del `hash()` de Python (sembrado por proceso), así que es
    estable entre ejecuciones. Devuelve "" para lo vacío. Nunca lanza.
    """
    text = str(value or "").strip().lower()
    slug = "".join(
        character if character.isalnum() else "_" for character in text
    )
    return "_".join(part for part in slug.split("_") if part)


def _skill_delta(raw: object) -> tuple[str, ...]:
    """Competencias que AÑADE una superficie, en orden canónico (V3.60, pura).

    Solo admite valores del vocabulario `CONTEXT_SKILLS` (deduplicados y
    ordenados por él); cualquier otra cosa (una cadena suelta, basura) devuelve
    `()`: una superficie no puede inventar competencias. Nunca lanza.
    """
    if isinstance(raw, str) or not isinstance(
        raw, (list, tuple, set, frozenset)
    ):
        return ()
    wanted = {str(skill or "").strip().lower() for skill in raw}
    return tuple(skill for skill in CONTEXT_SKILLS if skill in wanted)


# ---------------------------------------------------------------------------
# V3.61 (Instance-aware Evidence): GUARD ANTI-SPOILER de la superficie servida.
#
# V3.60 garantizaba que la PLANTILLA no contiene la unidad objetivo (V3.43/P1-01)
# pero no comprobaba los VALORES de slot, que son texto declarado nuevo: la
# auditoría T de V3.60 reprodujo que la familia `shopping` sirve en el índice 7
# «You are in a supermarket and cannot find what you need…» — si la unidad es
# `supermarket`, la respuesta está a la vista. El guard es determinista y
# léxico (sin LLM ni WSD, premisa 21): una superficie que NOMBRA la unidad
# objetivo no se sirve, y la rotación sigue sobre las que sí dan ESCENARIO.
# ---------------------------------------------------------------------------

# Longitud mínima de una unidad objetivo para aplicar el guard: con menos
# caracteres (o con funcionales) la coincidencia sería ruido, no fuga.
_TARGET_GUARD_MIN_LEN = 3

# Token léxico de una consigna: lo que separa la coincidencia de palabra de una
# coincidencia de subcadena (`supermarket` no debe casar con `supermarketing`).
_TARGET_TOKEN = re.compile(r"[a-z0-9']+")


def _target_forms(target: object) -> tuple[str, ...]:
    """Formas que DELATAN la unidad objetivo en un texto (V3.61, pura).

    Devuelve la forma base y un juego acotado de variantes inflexivas
    deterministas (`-s`/`-es`/`-d`/`-ed`/`-ing`/`-er`/`-ers` y su recorte) para
    no exigir un lematizador. Una unidad de menos de `_TARGET_GUARD_MIN_LEN`
    caracteres devuelve `()`: no se aplica guard (evita suprimir medio banco por
    una palabra funcional). Nunca lanza.
    """
    text = " ".join(str(target or "").strip().lower().split())
    if len(text) < _TARGET_GUARD_MIN_LEN:
        return ()
    forms = [text]
    if " " not in text:
        forms.extend(text + suffix for suffix in ("s", "es", "d", "ed", "ing",
                                                  "er", "ers"))
        for suffix in ("s", "es", "ed", "ing", "d"):
            if text.endswith(suffix) and len(text) > len(suffix) + 2:
                forms.append(text[: -len(suffix)])
    return tuple(dict.fromkeys(forms))


def _reveals_target(text: object, target: object) -> bool:
    """¿El texto NOMBRA la unidad objetivo? (V3.61, pura y conservadora).

    Compara por TOKEN (frontera de palabra) cuando la unidad es una sola
    palabra, y por subcadena normalizada cuando es una expresión de varias: una
    consigna que nombra la unidad es producción guiada, no recuperación
    espontánea (V3.43/P1-01). Nunca lanza.
    """
    haystack = " ".join(str(text or "").strip().lower().split())
    if not haystack:
        return False
    forms = _target_forms(target)
    if not forms:
        return False
    if " " in forms[0]:
        return any(form in haystack for form in forms)
    tokens = set(_TARGET_TOKEN.findall(haystack))
    return bool(tokens.intersection(forms))


def _surface_reveals_target(surface: Mapping, target: object) -> bool:
    """¿Algún campo visible/metadata de la superficie delata la unidad? (V3.61).

    Se comprueban la consigna y los metadatos que el contrato expone
    (`scenario`/`goal`/`register`): todos describen la situación servida y
    ninguno debe nombrar la unidad objetivo. Nunca lanza.
    """
    return any(
        _reveals_target(surface.get(key), target)
        for key in ("prompt", "scenario", "goal", "register")
    )


def reveals_target(text: object, target: object) -> bool:
    """Fachada PÚBLICA del guard anti-spoiler (V3.61, pura).

    La usa el validador de contenido (`services.transfer_audit`) para auditar el
    banco sin depender de un nombre privado. Nunca lanza.
    """
    return _reveals_target(text, target)


def surface_reveals_target(surface: object, target: object) -> bool:
    """Fachada PÚBLICA de la comprobación por superficie (V3.61, pura).

    Acepta cualquier mapping con `prompt`/`scenario`/`goal`/`register` (una
    superficie normalizada de `context_instance_details`). Nunca lanza.
    """
    return _surface_reveals_target(
        surface if isinstance(surface, Mapping) else {}, target
    )


def _instance_value(raw: object) -> dict[str, object]:
    """Valor de un SLOT del espacio de instancias, normalizado (V3.60, pura).

    Un valor se declara como texto (`"a longer trip"`) o como dict
    `{"value": str, "scenario": str, "goal": str, "register": str,
    "difficulty_delta": {...}, "skill_delta": (...)}`. `value` es OBLIGATORIA
    (es lo que se interpola en la consigna): sin texto el valor se DESCARTA, no
    se inventa contenido. Devuelve `{}` para lo inválido. Nunca lanza.
    """
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        return {
            "value": text,
            "slug": _slug(text),
            "scenario": "",
            "goal": "",
            "register": "",
            "difficulty_delta": {},
            "skill_delta": (),
        }
    if not isinstance(raw, Mapping):
        return {}
    text = str(raw.get("value") or "").strip()
    if not text:
        return {}
    return {
        "value": text,
        "slug": _slug(text),
        "scenario": str(raw.get("scenario") or "").strip(),
        "goal": str(raw.get("goal") or "").strip(),
        "register": str(raw.get("register") or "").strip(),
        "difficulty_delta": difficulty.normalize_delta(
            raw.get("difficulty_delta")
        ),
        "skill_delta": _skill_delta(raw.get("skill_delta")),
    }


def _template_fields(template: str) -> tuple[str, ...]:
    """Nombres de slot que interpola una plantilla de consigna (V3.60, pura).

    Los placeholders son `{nombre}` en minúsculas. Una plantilla sin ningún
    placeholder, o con llaves que no forman uno válido (`{`, `}`, `{}`,
    `{Word}`), devuelve `()`: la especificación es INSERVIBLE y la familia se
    queda con sus superficies declaradas. Los nombres repetidos se deduplican
    conservando su orden. Nunca lanza.
    """
    fields = _TEMPLATE_FIELD.findall(template)
    leftover = _TEMPLATE_FIELD.sub("", template)
    if "{" in leftover or "}" in leftover:
        return ()
    return tuple(dict.fromkeys(fields))


def _slot_order(selection: object, fields: tuple[str, ...]) -> tuple[str, ...]:
    """Orden en que se MEZCLAN los slots del espacio (V3.60, pura).

    `selection` es la lista ordenada de slots que la familia considera
    principales: se recorren primero y, por tanto, son los que entran siempre
    que el techo `CONTEXT_INSTANCE_SPACE_MAX` recorte el producto cartesiano.
    Los nombres desconocidos se ignoran y los slots no nombrados se AÑADEN
    detrás en su orden de declaración: nada se cae en silencio. Nunca lanza.
    """
    if isinstance(selection, (list, tuple)) and not isinstance(selection, str):
        wanted = [str(name or "").strip().lower() for name in selection]
    else:
        wanted = []
    ordered = [name for name in wanted if name in fields]
    seen = set(ordered)
    ordered.extend(name for name in fields if name not in seen)
    return tuple(ordered)


def context_instance_spec(context: object) -> dict:
    """Especificación PARAMÉTRICA de instancias de una familia (V3.60, pura).

    Normaliza el `instance_space` que declara la familia:

        {"template": "... {when} ...", "selection": ("when", "who"),
         "slots": {"when": [valores], "who": [valores]},
         "difficulty_delta": {...}}

    donde cada valor es texto o un dict (ver `_instance_value`). Se valida que
    la plantilla tenga placeholders VÁLIDOS y que TODOS ellos tengan un slot con
    al menos un valor utilizable: si algo falta, la especificación se considera
    INSERVIBLE y devuelve `{}` (la familia conserva sus superficies declaradas).
    Los slots que la plantilla NO interpola se ignoran, porque no producirían
    consignas distintas. Acepta el dict del banco, un `id` o un `context_id`;
    una familia sin `instance_space` devuelve `{}`. Nunca lanza.
    """
    attributes = _as_attributes(context)
    raw = attributes.get("instance_space")
    if not isinstance(raw, Mapping):
        return {}
    template = str(raw.get("template") or "").strip()
    if not template:
        return {}
    fields = _template_fields(template)
    if not fields:
        return {}
    declared = raw.get("slots")
    if not isinstance(declared, Mapping):
        return {}
    slots: dict[str, tuple[dict[str, object], ...]] = {}
    for name in fields:
        values = declared.get(name)
        if isinstance(values, str) or not isinstance(values, (list, tuple)):
            return {}
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in values:
            value = _instance_value(item)
            slug = str(value.get("slug") or "")
            if not value or slug in seen:
                continue
            seen.add(slug)
            normalized.append(value)
        if not normalized:
            return {}
        slots[name] = tuple(normalized)
    return {
        "template": template,
        "slots": slots,
        "order": _slot_order(raw.get("selection"), fields),
        "difficulty_delta": difficulty.normalize_delta(
            raw.get("difficulty_delta")
        ),
    }


def _merge_partial(
    name: str, value: Mapping, partial: Mapping
) -> dict:
    """Combina un valor de slot con una combinación parcial (V3.60, pura).

    Acumula la etiqueta del valor, el texto a interpolar, los deltas (se SUMAN
    por dimensión), el `scenario` (se concatenan los declarados) y las
    competencias (unión en orden canónico). `register` y `goal` son singulares:
    gana el último declarado no vacío. Nunca lanza.
    """
    delta = dict(partial.get("delta") or {})
    for dimension, load in (value.get("difficulty_delta") or {}).items():
        delta[dimension] = delta.get(dimension, 0) + load
    wanted = set(partial.get("skills") or ()) | set(value.get("skill_delta") or ())
    scenario = "; ".join(
        part
        for part in (
            str(partial.get("scenario") or ""),
            str(value.get("scenario") or ""),
        )
        if part
    )
    return {
        "labels": (*partial.get("labels", ()), value.get("slug") or ""),
        "values": {
            **dict(partial.get("values") or {}),
            name: value.get("value") or "",
        },
        "delta": delta,
        "scenario": scenario,
        "goal": str(value.get("goal") or "") or str(partial.get("goal") or ""),
        "register": str(value.get("register") or "")
        or str(partial.get("register") or ""),
        "skills": tuple(skill for skill in CONTEXT_SKILLS if skill in wanted),
    }


def _render_template(template: str, values: Mapping) -> str:
    """Plantilla con sus valores interpolados ("" si no se puede) (V3.60, pura)."""
    try:
        return template.format(**values).strip()
    except (KeyError, IndexError, ValueError):
        return ""


def _empty_partial() -> dict:
    """Combinación parcial VACÍA del producto cartesiano (V3.60, pura)."""
    return {
        "labels": (),
        "values": {},
        "delta": {},
        "scenario": "",
        "goal": "",
        "register": "",
        "skills": (),
    }


def _stratified_indices(total: int, limit: int) -> tuple[int, ...]:
    """Posiciones del producto cartesiano repartidas de forma equilibrada.

    V3.61 (P1-01). V3.60 recortaba el producto por PREFIJO, así que con más
    combinaciones que el techo las últimas variables quedaban con un subconjunto
    fijo de valores (sesgo estructural, inerte hoy con 16–19 superficies). Aquí
    se toman `limit` posiciones equiespaciadas sobre el producto COMPLETO: cada
    eje recibe cobertura repartida, el resultado sigue siendo determinista y el
    producto no se materializa (solo se decodifican las posiciones elegidas).
    Nunca lanza.
    """
    if limit <= 0 or total <= 0:
        return ()
    if total <= limit:
        return tuple(range(total))
    return tuple((position * total) // limit for position in range(limit))


def _partial_at(
    axes: list[tuple[str, tuple]], lengths: list[int], index: int
) -> dict:
    """Combinación del producto cartesiano en la posición `index` (V3.61, pura).

    Decodifica `index` en base mixta con el ÚLTIMO eje variando más rápido (el
    mismo orden que recorrían los bucles anidados de V3.60), de modo que la
    posición 0 sigue siendo la combinación de los primeros valores de cada slot y
    el orden de las combinaciones con espacio pequeño no cambia. Nunca lanza.
    """
    digits: list[int] = []
    remainder = index
    for length in reversed(lengths):
        if length <= 0:
            return {}
        digits.append(remainder % length)
        remainder //= length
    digits.reverse()
    partial = _empty_partial()
    for (name, values), digit in zip(axes, digits, strict=False):
        partial = _merge_partial(name, values[digit], partial)
    return partial


def _expand_spec(spec: Mapping) -> tuple[dict[str, object], ...]:
    """Superficies GENERADAS por la especificación, en orden estable (V3.60).

    Producto cartesiano de los slots en el orden de `spec["order"]`, cortado a
    `CONTEXT_INSTANCE_SPACE_MAX`. V3.61 (P1-01): cuando el producto excede el
    techo, el recorte es ESTRATIFICADO (`_stratified_indices`) y no un prefijo,
    así que ningún eje queda con un subconjunto fijo de valores; con el espacio
    por debajo del techo (el banco real) el orden es EXACTAMENTE el de V3.60.
    Cada superficie declara su consigna (el `template` interpolado), su etiqueta
    (slug estable de los valores elegidos) y los metadatos que APORTAN esos
    valores (`scenario`/`goal`/`register`/`difficulty_delta`/`skill_delta`) más
    el delta base declarado por la familia. Una combinación cuya plantilla no se
    puede renderizar se descarta. Nunca lanza.
    """
    slots = spec.get("slots") or {}
    order = spec.get("order") or tuple(slots)
    template = str(spec.get("template") or "")
    if not order or not template:
        return ()
    axes: list[tuple[str, tuple]] = []
    lengths: list[int] = []
    for name in order:
        values = slots.get(name) or ()
        if not values:
            continue
        axes.append((name, values))
        lengths.append(len(values))
    if not axes:
        return ()
    total = 1
    for length in lengths:
        total *= length
    base_delta = difficulty.normalize_delta(spec.get("difficulty_delta"))
    surfaces: list[dict[str, object]] = []
    for index in _stratified_indices(total, CONTEXT_INSTANCE_SPACE_MAX):
        partial = _partial_at(axes, lengths, index)
        if not partial:
            continue
        prompt = _render_template(template, partial["values"])
        if not prompt:
            continue
        delta = dict(base_delta)
        for dimension, load in partial["delta"].items():
            delta[dimension] = delta.get(dimension, 0) + load
        surfaces.append(
            {
                "instance": "_".join(partial["labels"]) or "generated",
                "prompt": prompt,
                "scenario": partial["scenario"],
                "goal": partial["goal"],
                "register": partial["register"],
                "difficulty_delta": difficulty.normalize_delta(delta),
                "skill_delta": partial["skills"],
                "generated": True,
            }
        )
    return tuple(surfaces)


def _surface_details(raw: object) -> dict[str, object]:
    """Superficie normalizada desde su declaración (V3.60, pura).

    Lee SOLO las claves de `CONTEXT_INSTANCE_KEYS`: cualquier otra declaración
    (la identidad de la familia) se IGNORA, que es la garantía de
    no-fragmentación del ledger. Todas las claves de
    `CONTEXT_INSTANCE_DETAIL_KEYS` están siempre presentes, con `""`/`{}`/`()`
    cuando la superficie no aporta nada. Nunca lanza.
    """
    if not isinstance(raw, Mapping):
        raw = {}
    return {
        "instance": str(raw.get("instance") or "").strip(),
        "prompt": str(raw.get("prompt") or "").strip(),
        "scenario": str(raw.get("scenario") or "").strip(),
        "goal": str(raw.get("goal") or "").strip(),
        "register": str(raw.get("register") or "").strip(),
        "difficulty_delta": difficulty.normalize_delta(
            raw.get("difficulty_delta")
        ),
        "skill_delta": _skill_delta(raw.get("skill_delta")),
        "generated": bool(raw.get("generated")),
    }


def context_instance_details(context: object) -> tuple[dict[str, object], ...]:
    """Espacio COMPLETO de superficies de una familia, en orden (V3.59 → V3.60).

    Devuelve, en este orden y sin repetir consigna (deduplicado por texto):

    0. la consigna HISTÓRICA de la familia, byte a byte (sin evidencia la
       degradación es exacta a V3.58);
    1. las superficies DECLARADAS de V3.59 (`instances`, en su orden), que
       ocupan por tanto los mismos índices que antes;
    2. las superficies GENERADAS por la especificación paramétrica
       (`instance_space`), en orden determinista.

    Acepta el dict del banco, un `id` o un `context_id`; una entrada no
    reconocible devuelve `()`. Nunca lanza.
    """
    attributes = _as_attributes(context)
    details: list[dict[str, object]] = []
    seen: set[str] = set()

    def _add(surface: object) -> None:
        normalized = _surface_details(surface)
        prompt = str(normalized.get("prompt") or "")
        if not prompt or prompt in seen:
            return
        seen.add(prompt)
        details.append(normalized)

    if attributes:
        _add({"prompt": attributes.get("prompt")})
        declared = attributes.get("instances")
        if isinstance(declared, (list, tuple)):
            for raw in declared:
                if isinstance(raw, Mapping):
                    _add(raw)
        spec = context_instance_spec(attributes)
        if spec:
            for surface in _expand_spec(spec):
                _add(surface)
    return tuple(details)


def available_instance_details(
    context: object, target: object = ""
) -> tuple[dict[str, object], ...]:
    """Superficies SERVIDAS de una familia, sin delatar la unidad (V3.61, pura).

    Es `context_instance_details` con el guard anti-spoiler aplicado: se
    descartan las superficies que NOMBRAN la unidad objetivo (`target`) en su
    consigna o en sus metadatos. La rotación, la dificultad efectiva y lo que el
    ledger persiste se resuelven sobre ESTA lista cuando hay unidad objetivo, de
    modo que el índice servido y la carga servida hablan siempre de la misma
    superficie.

    Sin `target` (o con uno demasiado corto para ser señal) devuelve el espacio
    completo: es la degradación EXACTA a V3.60 de todos los llamadores que no
    declaran unidad. Nunca lanza.
    """
    details = context_instance_details(context)
    if not _target_forms(target):
        return details
    return tuple(
        detail
        for detail in details
        if not _surface_reveals_target(detail, target)
    )


def context_instances(context: object) -> tuple[dict[str, str], ...]:
    """Superficies servibles de una familia, en orden de rotación (V3.59, pura).

    V3.60: es la VISTA de dos claves (`{"instance", "prompt"}`) del espacio
    completo (`context_instance_details`), que ahora incluye las superficies
    GENERADAS. Se conserva con esta forma porque es el contrato puro que fijó
    V3.59 (rotación, degradación a la superficie histórica y equivalencia entre
    `id` y `context_id`). La superficie 0 es SIEMPRE la consigna histórica.
    Normaliza (recorta y descarta superficies sin consigna) y nunca lanza.
    """
    return tuple(
        {"instance": str(detail["instance"]), "prompt": str(detail["prompt"])}
        for detail in context_instance_details(context)
    )


def context_instance_index(
    context: object,
    attempts: object = 0,
    *,
    target: object = "",
    unit: object = "",
) -> int:
    """Superficie que toca servir, por ROTACIÓN de intentos (V3.59 → V3.61, pura).

    `attempts` son los intentos ya registrados en ESA familia para el ítem (el
    resumen de evidencia los cuenta por `context_id`), de modo que el intento N
    recibe la superficie `N % nº_superficies`: la primera estancia sirve la
    consigna histórica y las siguientes no repiten redacción, que es lo que
    evita que el alumno memorice la estructura en lugar de transferir. Sin
    intentos (o con un valor no reconocible) devuelve 0, es decir, la superficie
    de V3.58 exacta. Una familia sin superficies declaradas devuelve 0 siempre
    (rotación inerte). Nunca lanza.

    V3.61 (P1-01): con `target` declarado la rotación corre sobre las superficies
    SERVIDAS (`available_instance_details`), así que una consigna que nombra la
    unidad objetivo no entra en el ciclo. A partir del TERCER intento la posición
    se permuta de forma determinista con una semilla `(familia, `unit`)`: el
    ciclo deja de ser el orden declarado y difiere entre ítems. Los intentos
    0/1/2 conservan las superficies 0/1/2 (contrato V3.59/V3.60) y con menos de
    cuatro superficies el comportamiento es el de V3.60 exacto. Sin `target` ni
    `unit` la degradación es EXACTA a V3.60.
    """
    count = len(available_instance_details(context, target))
    if count <= 1:
        return 0
    total = _count(attempts)
    if total <= 0:
        return 0
    position = total % count if total > 0 else 0
    if count < 4 or position < 3:
        return position
    return _rotated_index(context_id_for(context), unit, count, position)


def _rotated_index(
    family_id: object, unit: object, count: int, position: int
) -> int:
    """Posición del ciclo, permutada de forma determinista (V3.61, pura).

    Conserva las TRES primeras posiciones (las superficies 0–2 son la histórica y
    las declaradas de V3.59) y reparte el resto del ciclo con un desplazamiento
    derivado de `(familia, unidad)`: el ciclo deja de coincidir con el orden
    declarado y cambia entre ítems, sin `random()` ni `hash()` sembrado por
    proceso. El desplazamiento es una biyección del tramo, así que el ciclo sigue
    visitando TODO el espacio. Nunca lanza.
    """
    tail = count - 3
    if tail <= 1:
        return position
    seed = zlib.crc32(
        f"{str(family_id or '').strip().lower()}:{unit or ''}".encode("utf-8")
    )
    return 3 + ((position - 3 + seed) % tail)


def context_instance_metadata(
    context: object, index: object = 0, *, target: object = ""
) -> dict:
    """Metadatos de la superficie `index` de una familia (V3.60 → V3.61, pura).

    Devuelve las claves de `CONTEXT_INSTANCE_DETAIL_KEYS` más `skills`: la unión
    entre las competencias de la FAMILIA (`context_skills`) y las que la
    superficie AÑADE (`skill_delta`), en el orden canónico de `CONTEXT_SKILLS`.
    Es EXPLICABILIDAD de la superficie: no cambia la modalidad que la tarea
    evalúa (`assessed_skill`, que sigue siendo `written_production`). Un índice
    fuera de rango cae a la superficie 0 y una familia sin espacio devuelve los
    valores por defecto. V3.61: con `target` declarado el índice se interpreta
    sobre las superficies SERVIDAS (guard anti-spoiler). Nunca lanza.
    """
    details = available_instance_details(context, target)
    if not details:
        return {**_surface_details({}), "skills": ()}
    position = _count(index)
    if position >= len(details):
        position = 0
    detail = details[position]
    wanted = set(context_skills(context)) | set(detail["skill_delta"])
    return {
        **detail,
        "skills": tuple(skill for skill in CONTEXT_SKILLS if skill in wanted),
    }


def context_instance_difficulty(
    context: object, index: object = 0, *, target: object = ""
) -> dict[str, int]:
    """Vector de carga EFECTIVO de la superficie `index` (V3.60 → V3.61, pura).

    Es el vector de la FAMILIA (`context_difficulty`, que NO cambia) más el
    `difficulty_delta` que declara la superficie, recortado al envelope 1..5.
    Sin delta declarado devuelve el vector de la familia EXACTO, que es la
    garantía de degradación de la release. V3.61: `target` resuelve el índice
    sobre las superficies servidas. Nunca lanza.
    """
    metadata = context_instance_metadata(context, index, target=target)
    return difficulty.apply_delta(
        context_difficulty(context), metadata["difficulty_delta"]
    )


def served_difficulty(
    context_id: object,
    attempts_by_context: object = None,
    *,
    target: object = "",
    unit: object = "",
) -> dict[str, int]:
    """Carga de la superficie que TOCA SERVIRSE en una familia (V3.60, pura).

    Resuelve la familia (`context_id` del ledger, `id` o dict del banco), cuenta
    sus intentos con `_attempts_for` —el MISMO insumo que la rotación de
    `context_for`— y devuelve la dificultad EFECTIVA de la superficie que ese
    intento sirve. Es lo que el ledger persiste por evento, así que la carga
    guardada corresponde a la tarea realmente servida, incluida su superficie.
    Una familia no reconocible devuelve `{}`: sin banco no se declara carga.

    V3.61: `target` (la unidad objetivo) aplica el guard anti-spoiler y `unit`
    alimenta la semilla de la rotación no secuencial; el llamador que quiere la
    degradación exacta a V3.60 no declara ninguno de los dos. Nunca lanza.
    """
    attributes = _as_attributes(context_id)
    if not attributes:
        return {}
    index = context_instance_index(
        attributes,
        _attempts_for(attempts_by_context, context_id_for(attributes)),
        target=target,
        unit=unit,
    )
    return context_instance_difficulty(attributes, index, target=target)


def serve_instance(
    context_id: object,
    context_instance: object = "",
    attempts_by_context: object = None,
    *,
    target: object = "",
    unit: object = "",
) -> dict[str, object]:
    """Superficie que el alumno RESPONDIÓ y su carga efectiva (V3.61, pura).

    Cierra el defecto T-02 de la auditoría de V3.60: el POST no debe recalcular
    la superficie con el contador actual (que puede haber avanzado por una
    respuesta simultánea o un reintento de red), sino resolver la que el cliente
    **recibió** y **respondió**. La identidad inmutable es el **slug** de la
    superficie (`context_instance`), estable porque se deriva del contenido
    declarado y no del orden (`_slug`).

    Devuelve `{instance, index, count, matched, difficulty, suppressed}`:

    - `matched=True` si el slug existe en la familia (tras el guard anti-spoiler)
      y `difficulty` es la carga de ESA superficie;
    - `matched=False` si el slug falta o ya no existe (familia cambiada, cliente
      legacy, superficie retirada): se cae a la rotación actual —degradación
      exacta a V3.60— y se declara para que el ledger no mienta;
    - `count` es el nº de superficies servidas y `suppressed` cuántas descartó
      el guard anti-spoiler.

    Nunca lanza.
    """
    attributes = _as_attributes(context_id)
    if not attributes:
        return {
            "instance": "",
            "index": 0,
            "count": 0,
            "matched": False,
            "difficulty": {},
            "suppressed": 0,
        }
    declared = context_instance_details(attributes)
    details = available_instance_details(attributes, target)
    suppressed = len(declared) - len(details)
    slug = str(context_instance or "").strip()
    index = -1
    if slug:
        for position, detail in enumerate(details):
            if detail["instance"] == slug:
                index = position
                break
    matched = index >= 0
    if not matched:
        index = context_instance_index(
            attributes,
            _attempts_for(
                attempts_by_context, context_id_for(attributes)
            ),
            target=target,
            unit=unit,
        )
    served = (
        difficulty.apply_delta(
            context_difficulty(attributes), details[index]["difficulty_delta"]
        )
        if details
        else {}
    )
    return {
        "instance": details[index]["instance"] if details else "",
        "index": index,
        "count": len(details),
        "matched": matched,
        "difficulty": served,
        "suppressed": suppressed,
    }


def served_difficulty_for_instance(
    context_id: object,
    context_instance: object = "",
    attempts_by_context: object = None,
    *,
    target: object = "",
    unit: object = "",
) -> dict[str, int]:
    """Carga EFECTIVA de la superficie RESPONDIDA (V3.61, pura).

    Fachada de `serve_instance` para el ledger: devuelve solo el vector servido
    (el de la superficie que el alumno respondió si el slug la identifica; el de
    la rotación actual si no). Con la superficie 0 —o cualquiera sin ajuste—
    escribe bytes idénticos a V3.60. Nunca lanza.
    """
    return serve_instance(
        context_id,
        context_instance,
        attempts_by_context,
        target=target,
        unit=unit,
    )["difficulty"]


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
    """Contexto de transferencia que toca practicar (V3.40 → V3.60, puro).

    Devuelve `{word, context_id, topic, prompt, available, exhausted,
    communicative_goal, discourse_type, condition, required_target,
    unscaffolded, cefr,     difficulty_vector, difficulty, skills, target_skill,
    assessed_skill, assessment_mode, item_level, learner_level,
    learner_level_source, learner_capacity, capacity_skill, difficulty_fit,
    skill_priorities, context_instance, instance_index, instance_count,
    instance_scenario, instance_goal, instance_register,
    instance_difficulty_delta, instance_difficulty_vector, instance_difficulty,
    instance_skills, instance_generated, instance_suppressed,
    instance_guarded}`.
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
    1g. V3.60 (Context Engine 4.0): el espacio de superficies de la familia ya no
       son solo las declaradas a mano, sino las que genera su especificación
       paramétrica (`context_instance_details`), con la MISMA regla de rotación.
       Si la superficie declara un `difficulty_delta`, la carga EFECTIVA
       (`instance_difficulty_vector`) es la de la familia más ese ajuste; sin
       delta (incluida siempre la superficie 0) es idéntica a V3.59;
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
            # V3.60: sin familia no hay superficie, así que los metadatos y la
            # dificultad de la superficie quedan vacíos (siempre presentes).
            "instance_scenario": "",
            "instance_goal": "",
            "instance_register": "",
            "instance_difficulty_delta": {},
            "instance_difficulty_vector": {},
            "instance_difficulty": 0,
            "instance_skills": [],
            "instance_generated": False,
            # V3.61: sin familia no hay superficie que el guard pueda retirar.
            "instance_suppressed": 0,
            "instance_guarded": False,
        }
    # V3.61 (anti-spoiler de la superficie SERVIDA): una familia cuya superficie
    # nombra la unidad objetivo no puede servirla —el alumno leería la respuesta
    # y la evidencia acreditaría producción GUIADA en lugar de recuperación
    # espontánea (V3.43/P1-01)—. Se descarta del pool SOLO si queda alternativa
    # segura; con TODAS las familias delatando la unidad (banco patológico) se
    # degrada a V3.60 y se declara con `instance_guarded=False`.
    safe_pool = [
        context for context in pool if available_instance_details(context, unit)
    ]
    guarded = bool(safe_pool)
    if guarded:
        pool = safe_pool
    # Familia elegida: la MISMA que V3.59 salvo que el guard haya retirado
    # familias que delatan la unidad.
    if success:
        best = max(_novelty_score(context, success) for context in pool)
        # Se conserva el orden del banco dentro del empate: `_stable_index` es
        # función del pool, así que un empate no depende del orden del dict.
        pool = [c for c in pool if _novelty_score(c, success) == best]
    context = pool[_stable_index(unit, len(pool))]
    vector = dict(context.get("difficulty_vector") or {})
    # V3.59: la FAMILIA ya está elegida (misma que V3.58); ahora se resuelve su
    # SUPERFICIE por rotación de intentos sobre esa familia.
    # V3.60: el espacio de superficies incluye las GENERADAS por la
    # especificación paramétrica de la familia, y la superficie puede declarar
    # metadatos (escenario, registro) y un AJUSTE de carga.
    # V3.61: la rotación corre sobre las superficies SERVIDAS (sin las que
    # delatan la unidad) y su semilla incluye la unidad, así que el ciclo no es
    # el orden declarado ni coincide entre ítems.
    guard_target = unit if guarded else ""
    details = available_instance_details(context, guard_target)
    instance_index = context_instance_index(
        context,
        _attempts_for(attempts_by_context, context_id_for(context)),
        target=guard_target,
        unit=unit,
    )
    detail = details[instance_index] if details else _surface_details({})
    # Carga EFECTIVA de la superficie servida (la de la familia si no declara
    # ajuste): es la que explica el reto REAL de esta estancia.
    effective = difficulty.apply_delta(
        context_difficulty(context), detail["difficulty_delta"]
    )
    instance_skills = tuple(
        skill
        for skill in CONTEXT_SKILLS
        if skill in set(context_skills(context)) | set(detail["skill_delta"])
    )
    return {
        "word": unit,
        "context_id": context_id_for(context),
        "topic": context.get("topic", ""),
        "prompt": _compose_prompt(detail["prompt"], served, unit),
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
        # V3.59 (Context Engine 3.0): superficie servida de la familia
        # ("" = la histórica), su índice y cuántas superficies tiene el espacio.
        "context_instance": detail["instance"],
        "instance_index": instance_index,
        "instance_count": len(details),
        # V3.60 (Context Engine 4.0): metadatos NO identitarios de la superficie
        # (escenario, objetivo y registro concretos), su AJUSTE de carga, la
        # carga EFECTIVA que se está sirviendo, las competencias efectivas y si
        # la superficie la generó la especificación paramétrica. Todo aditivo y
        # solo explicativo: la familia servida y la evidencia no cambian.
        "instance_scenario": detail["scenario"],
        "instance_goal": detail["goal"],
        "instance_register": detail["register"],
        "instance_difficulty_delta": dict(detail["difficulty_delta"]),
        "instance_difficulty_vector": dict(effective),
        "instance_difficulty": difficulty_from_vector(effective),
        "instance_skills": list(instance_skills),
        "instance_generated": bool(detail["generated"]),
        # V3.61 (anti-spoiler de la superficie servida): cuántas superficies
        # retiró el guard por nombrar la unidad objetivo y si la familia servida
        # pasó por él (`False` = se degradó a V3.60 porque NINGUNA familia tenía
        # una superficie segura para esa unidad). Aditivo y solo explicativo.
        "instance_suppressed": max(
            len(context_instance_details(context)) - len(details), 0
        ),
        "instance_guarded": guarded,
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

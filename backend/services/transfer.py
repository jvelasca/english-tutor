"""Contextos de TRANSFERENCIA auténtica de una unidad léxica (V3.40 → V3.43).

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

No usa LLM ni aleatoriedad con estado: la rotación se deriva de un hash ESTABLE
(`zlib.crc32`, no el `hash()` de Python, que va sembrado por proceso) y de los
contextos ya registrados en el ledger (`context_id`), así que la misma evidencia
produce siempre la misma consigna.
"""

from __future__ import annotations

import zlib

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

# V3.43 (P1-03): nº mínimo de dimensiones con valores DISTINTOS que exigen los
# contextos con éxito limpio para declarar diversidad real. Declarado y
# calibrable; dos contextos distintos suelen diferir en >= 2 dimensiones.
CONTEXT_DIVERSITY_MIN = 2

# Banco curado de contextos NOVEDOSOS. La consigna NO da la palabra (eso sería
# `sentence`): solo un escenario y un objetivo comunicativo en los que usarla por
# decisión propia (V3.43, P1-01). Declarado y estable; ampliarlo no rompe
# determinismo, porque la elección se deriva del banco.
TRANSFER_CONTEXTS: tuple[dict[str, str], ...] = (
    {
        "id": "story",
        "topic": "personal_experience",
        "communicative_goal": "narrate",
        "discourse_type": "narrative",
        "social_relation": "friend",
        "time_reference": "past",
        "register": "neutral",
        "interaction_type": "monologue",
        "prompt": (
            "Tell a short story about something that happened to you recently."
        ),
    },
    {
        "id": "question",
        "topic": "friend_life",
        "communicative_goal": "ask",
        "discourse_type": "dialogue",
        "social_relation": "friend",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "dialogue",
        "prompt": "Write a question you would like to ask a friend.",
    },
    {
        "id": "work",
        "topic": "employment",
        "communicative_goal": "describe",
        "discourse_type": "descriptive",
        "social_relation": "colleague",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "monologue",
        "prompt": (
            "You have a new job. Describe something interesting about your "
            "first week to a colleague."
        ),
    },
    {
        "id": "future",
        "topic": "personal_plans",
        "communicative_goal": "plan",
        "discourse_type": "expository",
        "social_relation": "friend",
        "time_reference": "future",
        "register": "neutral",
        "interaction_type": "monologue",
        "prompt": "Talk about your plans for next year.",
    },
    {
        "id": "opinion",
        "topic": "everyday_topics",
        "communicative_goal": "give_opinion",
        "discourse_type": "argumentative",
        "social_relation": "friend",
        "time_reference": "present",
        "register": "neutral",
        "interaction_type": "monologue",
        "prompt": (
            "Give your opinion about something you feel strongly about, and "
            "say why."
        ),
    },
    {
        "id": "problem",
        "topic": "everyday_problems",
        "communicative_goal": "explain",
        "discourse_type": "explanatory",
        "social_relation": "family",
        "time_reference": "past",
        "register": "neutral",
        "interaction_type": "monologue",
        "prompt": "Describe a small problem you had and how you solved it.",
    },
)

# Índice por `id` para resoluciones de atributos en O(1) (derivado del banco).
_CONTEXTS_BY_ID: dict[str, dict[str, str]] = {
    context["id"]: context for context in TRANSFER_CONTEXTS
}


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
        if "id" in context:
            return dict(context)
        return {}
    ident = _bare_context_id(context)
    return dict(_CONTEXTS_BY_ID[ident]) if ident else {}


def context_attributes(context: object) -> dict[str, str]:
    """Atributos pedagógicos de un contexto ({} si no se reconoce) (V3.43, pura).

    Acepta el dict del banco, un `id` (`"story"`) o un `context_id` de ledger
    (`"transfer:story"`). Devuelve una COPIA: nunca expone el dict del banco.
    """
    return _as_attributes(context)


def context_dimensions(context_ids: object) -> dict[str, list[str]]:
    """Valores DISTINTOS por dimensión de una colección de contextos (V3.43).

    Devuelve `{dimension: [valores ordenados]}`. Los contextos no reconocidos y
    las dimensiones sin valor se ignoran. Determinista: las listas van
    ordenadas alfabéticamente. Nunca lanza.
    """
    values: dict[str, set[str]] = {dimension: set() for dimension in CONTEXT_DIMENSIONS}
    try:
        iterable = list(context_ids or ())
    except TypeError:
        iterable = []
    for raw in iterable:
        attributes = _as_attributes(raw)
        for dimension in CONTEXT_DIMENSIONS:
            value = (attributes.get(dimension) or "").strip()
            if value:
                values[dimension].add(value)
    return {
        dimension: sorted(values[dimension])
        for dimension in CONTEXT_DIMENSIONS
        if values[dimension]
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
    - `score` — `diverse_dimensions / len(dimensions)` (0.0 sin dimensiones).

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
) -> dict:
    """Contexto de transferencia que toca practicar (V3.40 → V3.43, puro).

    Devuelve `{word, context_id, topic, prompt, available, exhausted,
    communicative_goal, discourse_type}`. La consigna es la del banco y **no
    contiene la unidad objetivo** (V3.43, P1-01): el escenario no da la palabra.

    Elección, determinista y estable:

    1. se filtra el banco a los contextos cuyo `context_id` no esté en
       `used_context_ids` (contextos que el ítem ya registró en el ledger);
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
        }
    if success:
        best = max(_novelty_score(context, success) for context in pool)
        # Se conserva el orden del banco dentro del empate: `_stable_index` es
        # función del pool, así que un empate no depende del orden del dict.
        pool = [c for c in pool if _novelty_score(c, success) == best]
    context = pool[_stable_index(unit, len(pool))]
    return {
        "word": unit,
        "context_id": context_id_for(context),
        "topic": context.get("topic", ""),
        "prompt": context.get("prompt", ""),
        "available": True,
        "exhausted": exhausted,
        "communicative_goal": context.get("communicative_goal", ""),
        "discourse_type": context.get("discourse_type", ""),
    }

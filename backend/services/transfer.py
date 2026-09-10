"""Contextos de TRANSFERENCIA auténtica de una unidad léxica (V3.40, puro).

La auditoría de V3.38.1 (P1-03) distingue dos cosas que hasta ahora se
confundían:

- **recuperación contextualizada** (`situation`): completar «The _____ was
  purring.» es reconocer/recuperar la palabra con una guía fuerte;
- **transferencia contextual**: usar la palabra por decisión propia en un
  contexto DISTINTO del de aprendizaje.

Este módulo aporta el contenido determinista de la segunda: un banco curado de
contextos genéricos (con cualquier unidad léxica) y la elección **pura y
determinista** del contexto que toca practicar, preferiendo uno que el ítem aún
no haya usado con éxito. No usa LLM ni aleatoriedad con estado: la rotación se
deriva de un hash ESTABLE (`zlib.crc32`, no el `hash()` de Python, que va
sembrado por proceso) y de los contextos ya registrados en el ledger
(`context_id`), así que la misma evidencia produce siempre la misma consigna.
"""

from __future__ import annotations

import zlib

# Prefijo del `context_id` del ledger para esta actividad. Distingue la
# transferencia de los contextos de práctica (`lexicon:<canal>`, `objective:*`).
TRANSFER_CONTEXT_PREFIX = "transfer:"

# Banco curado de contextos NOVEDOSOS. La consigna no da la palabra (eso sería
# `sentence`): solo un escenario nuevo en el que usarla. Declarado y estable;
# ampliarlo no rompe determinismo, porque la elección se deriva del banco.
TRANSFER_CONTEXTS: tuple[dict[str, str], ...] = (
    {
        "id": "story",
        "topic": "story",
        "prompt": 'Tell a short story about your day using "{word}".',
    },
    {
        "id": "question",
        "topic": "question",
        "prompt": 'Write a question you could ask a friend using "{word}".',
    },
    {
        "id": "work",
        "topic": "work",
        "prompt": 'Use "{word}" in a sentence about work or school.',
    },
    {
        "id": "future",
        "topic": "future",
        "prompt": 'Use "{word}" in a sentence about your plans for next year.',
    },
    {
        "id": "opinion",
        "topic": "opinion",
        "prompt": 'Give your opinion about something using "{word}".',
    },
    {
        "id": "problem",
        "topic": "problem",
        "prompt": 'Describe a small problem and use "{word}" in your answer.',
    },
)


def context_id_for(context: dict | str) -> str:
    """`context_id` de ledger de un contexto del banco (pura)."""
    ident = context["id"] if isinstance(context, dict) else str(context)
    ident = (ident or "").strip()
    if not ident:
        return ""
    if ident.startswith(TRANSFER_CONTEXT_PREFIX):
        return ident
    return f"{TRANSFER_CONTEXT_PREFIX}{ident}"


def _stable_index(word: str, size: int) -> int:
    """Índice 0..size-1 ESTABLE para una palabra (nunca el `hash()` sembrado)."""
    if size <= 0:
        return 0
    checksum = zlib.crc32((word or "").strip().lower().encode("utf-8"))
    return checksum % size


def context_for(
    word: str, used_context_ids: object = ()
) -> dict:
    """Contexto de transferencia que toca practicar (V3.40, puro).

    Devuelve `{word, context_id, topic, prompt, available}`. La consigna es la
    del banco con `{word}` ya sustituido.

    Elección, determinista y estable:
    1. se filtra el banco a las consignas cuyo `context_id` no esté en
       `used_context_ids` (contextos que el ítem ya registró en el ledger) y se
       elige una por `_stable_index(word)` dentro de ese pool: la misma palabra y
       la misma evidencia producen siempre la misma consigna;
    2. si ya se usaron todos, se ROTA igual sobre el banco COMPLETO (nunca deja
       al alumno sin tarea), marcando `exhausted=True`.

    `used_context_ids` acepta un iterable de cadenas (se ignoran vacías y
    duplicados). El banco es estático, así que `available` es siempre `True`
    (el campo se mantiene por simetría con los demás GET del drill). Nunca
    lanza.
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
        }
    context = pool[_stable_index(unit, len(pool))]
    return {
        "word": unit,
        "context_id": context_id_for(context),
        "topic": context.get("topic", ""),
        "prompt": context.get("prompt", "").replace("{word}", unit),
        "available": True,
        "exhausted": exhausted,
    }

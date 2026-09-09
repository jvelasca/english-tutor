"""Contenido del diccionario de consulta con el modelo local (V3.30, D1, Fase B).

Genera la definición/traducción de UNA palabra cuando la caché global
`dictionary_entries` no la tiene: definición EN en inglés simple, categoría
gramatical (`pos`) y traducción ES neutra. Mismo patrón que `services/translate.py`
(modelo local, `temperature=0`, elección del modelo rápido instalado) con dos
diferencias:

- la salida es ESTRUCTURADA (un objeto JSON con `pos`/`definition`/`translation`);
- el contenido se PERSISTE en BD por el repositorio (`repositories/dictionary.py`),
  así que la primera consulta de una palabra es la única que paga la latencia del
  modelo y las siguientes son deterministas.

El contenido es idioma, NO evidencia (premisa 21): nunca alimenta mastery, la
curva de olvido ni el ledger `vocabulary_events`. Si el modelo no está disponible
o la respuesta no valida se lanza `ContentUnavailableError`; el dominio degrada a
`definition_source="none"` (la marca de uso y el ejemplo se siguen sirviendo).
"""

from __future__ import annotations

import json
import logging
import re

from schemas.chat import ChatMessage
from services import llm, translate

logger = logging.getLogger(__name__)

# Límites de contenido generado (validación del parseo tolerante).
MAX_WORD_CHARS = 80
MAX_DEFINITION_CHARS = 600
MAX_TRANSLATION_CHARS = 200

# Categorías gramaticales aceptadas del `pos` devuelto por el modelo. Cualquier
# otro valor se normaliza a "" (la UI no muestra POS inventado).
_VALID_POS = frozenset(
    {
        "noun",
        "verb",
        "adjective",
        "adverb",
        "pronoun",
        "preposition",
        "conjunction",
        "interjection",
        "determiner",
        "phrase",
    }
)

_SYSTEM_PROMPT = (
    "You are a learner-friendly English dictionary inside a local "
    "language-learning app. For the given English word or phrase, reply with "
    "ONLY one JSON object with exactly these keys: "
    '"pos" (one of: noun, verb, adjective, adverb, pronoun, preposition, '
    "conjunction, interjection, determiner, phrase), "
    '"definition" (a short definition in SIMPLE English, one or two sentences, '
    "without examples inside it), "
    '"translation" (the natural neutral Spanish translation of the headword). '
    "Do not add any text outside the JSON object."
)


class ContentUnavailableError(RuntimeError):
    """Contenido de diccionario no disponible (modelo caído o respuesta inválida).

    El dominio lo captura y degrada a `definition_source="none"`; nunca debe
    propagarse como error 5xx: la consulta sigue sirviendo uso y ejemplo.
    """


async def _fetch_chat(word: str, model: str | None) -> str:
    """Llama al modelo local y devuelve el texto crudo de la respuesta.

    Elige modelo con la misma política de `translate.pick_model` (rápido
    instalado; nunca `config.UNUSABLE_MODELS`) y `temperature=0` para que la
    generación sea lo más reproducible posible. Cualquier fallo de red/modelo o
    respuesta vacía se convierte en `ContentUnavailableError` (degradación).
    """
    try:
        chosen = await translate.pick_model(model)
        reply = await llm.chat_once(
            messages=[ChatMessage(role="user", content=word)],
            model=chosen,
            temperature=0.0,
            system_prompt=_SYSTEM_PROMPT,
        )
    except ContentUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 — frontera con Ollama: degradar
        raise ContentUnavailableError(f"Modelo no disponible: {exc}") from exc
    raw = (reply.content or "").strip()
    if not raw:
        raise ContentUnavailableError("El modelo devolvió una respuesta vacía")
    return raw


# Punto de inyección para tests (sustituible sin tocar Ollama).
_default_fetcher = _fetch_chat


def parse_content(raw: str) -> dict:
    """Parsea y valida la respuesta del modelo → `{pos, definition, translation}`.

    Parseo tolerante: extrae el primer bloque `{…}` aunque el modelo lo envuelva
    en cercas de Markdown, y normaliza `pos` a un valor canónico ("" si no es
    válido). Lanza `ContentUnavailableError` si el JSON es corrupto, no es un
    objeto o la definición está vacía/supera el límite.
    """
    text = (raw or "").strip()
    if not text:
        raise ContentUnavailableError("Respuesta vacía del modelo")
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ContentUnavailableError("La respuesta no contiene un objeto JSON")
    try:
        obj = json.loads(match.group(0))
    except (ValueError, TypeError) as exc:
        raise ContentUnavailableError("JSON de la respuesta inválido") from exc
    if not isinstance(obj, dict):
        raise ContentUnavailableError("El JSON de la respuesta no es un objeto")

    pos = str(obj.get("pos") or "").strip().lower()
    definition = str(obj.get("definition") or "").strip()
    translation = str(obj.get("translation") or "").strip()
    if not definition:
        raise ContentUnavailableError("La respuesta no incluye una definición")
    if len(definition) > MAX_DEFINITION_CHARS:
        raise ContentUnavailableError("La definición supera el límite de longitud")
    return {
        "pos": pos if pos in _VALID_POS else "",
        "definition": definition,
        "translation": translation[:MAX_TRANSLATION_CHARS],
    }


async def generate_content(
    word: str,
    *,
    model: str | None = None,
    fetcher=None,
) -> dict:
    """Genera `{pos, definition, translation}` para `word` con el modelo local.

    `fetcher` es inyectable para tests (default: llamada real `_fetch_chat`).
    La palabra debe venir normalizada (minúsculas, sin puntuación circundante).
    Lanza `ContentUnavailableError` si el modelo falla o la respuesta no valida.
    """
    fetch = fetcher or _default_fetcher
    raw = await fetch(word, model)
    return parse_content(raw)

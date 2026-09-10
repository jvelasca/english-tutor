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

Semántica del contenido (V3.31.1, auditoría V3.31.0): la caché
`dictionary_entries` es GLOBAL y CANÓNICA — una definición/traducción vale para
cualquier usuario y no lleva `model_id`. Por tanto el parámetro `model` de la
consulta NO elige «con qué modelo se sirve mi contenido» (el cacheado se sirve
igual a todos); significa «si hay que generar contenido nuevo, prefiero este
modelo». Se mantiene así a propósito: el contenido es canónico y la generación
solo decide cómo crearlo la primera vez.
"""

from __future__ import annotations

import json
import logging
import re

from schemas.chat import ChatMessage
from services import llm, translate
from services import situation as situation_service

logger = logging.getLogger(__name__)

# Versión del prompt + parseador + política POS. Un cambio de criterio (prompt,
# validación, categorías aceptadas, idioma, longitud) debe SUBIR esta versión:
# las entradas de `dictionary_entries` guardan la versión con la que se
# generaron y el dominio solo sirve caché cuya `generator_version` coincide
# (las anteriores se regeneran y sobrescriben).
#
# V3.31: bump 1.0.0 -> 1.1.0. El contenido cacheado antes de V3.31 —incluido
# el que V3.30.1 etiquetó como "1.0.0" al migrar y que es indistinguible por
# fila del generado por el parser greedy de V3.30— no se sirve como fresco:
# regenera de forma perezosa una sola vez al primer lookup.
# `repositories/db.py` mantiene `DICTIONARY_LEGACY_VERSION = "1.0.0"` como marca
# deliberadamente DISTINTA de esta versión para ese contenido previo.
#
# V3.38: bump 1.1.0 -> 1.2.0. El contrato de contenido gana `situation`, el
# enunciado situacional que sirve el 4.º peldaño de la escalera de recall. El
# contenido cacheado con 1.0.0/1.1.0 no lo tiene, así que se regenera una sola
# vez al primer lookup (misma política de invalidación, sin migración de datos).
#
# V3.38.1: bump 1.2.0 -> 1.2.1. Endurecimiento del validador de `situation`
# (una sola frase + fuga morfológica, P2-01 de la auditoría de V3.38.0): la
# caché 1.2.0 puede contener enunciados que las reglas nuevas descartarían, así
# que se regenera una sola vez bajo el validador estricto.
GENERATOR_VERSION = "1.2.1"

# Límites de contenido generado (validación del parseo tolerante).
MAX_WORD_CHARS = 80
MAX_DEFINITION_CHARS = 600
MAX_TRANSLATION_CHARS = 200
# El enunciado situacional es UNA frase de escenario con un único hueco; se
# acota para que no se convierta en un párrafo.
# V3.38.1 (P2-01): la validación del enunciado situacional vive en la capa pura
# `services.situation` (única fuente de verdad, compartida con la lectura de la
# escalera). Aquí solo se re-exportan los nombres por retrocompatibilidad.
MAX_SITUATION_CHARS = situation_service.MAX_SITUATION_CHARS
SITUATION_BLANK = situation_service.SITUATION_BLANK

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
    '"translation" (the natural neutral Spanish translation of the headword), '
    '"situation" (ONE short English sentence, at most 200 characters, that '
    "sets a concrete everyday scenario and contains EXACTLY one blank "
    '"_____" where the headword fits; do NOT write the headword or any form '
    "of it anywhere else in the sentence). "
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


def parse_content(raw: str, *, word: str = "") -> dict:
    """Parsea y valida la respuesta del modelo → `{pos, definition, translation,
    situation}`.

    Parseo tolerante: extrae el PRIMER objeto `{…}` válido aunque el modelo lo
    envuelva en cercas de Markdown o texto alrededor (V3.30.1: barrido con
    `raw_decode` en cada `{`; la vieja regex greedy `{.*}` podía tragarse
    `{…} texto {…}` hasta el último cierre), y normaliza `pos` a un valor
    canónico ("" si no es válido). Lanza `ContentUnavailableError` si no hay
    ningún objeto JSON válido o la definición está vacía/supera el límite.

    V3.38: `situation` es el enunciado situacional del 4.º peldaño de recall.
    Es contenido OPCIONAL: si falta, supera el límite, no trae un hueco `_____`
    o filtra la palabra diana, se descarta (queda "") sin invalidar la
    definición/traducción. `word` (normalizada) activa la comprobación de
    spoiler: el enunciado no puede contener la diana en ningún otro sitio.
    """
    text = (raw or "").strip()
    if not text:
        raise ContentUnavailableError("Respuesta vacía del modelo")
    decoder = json.JSONDecoder()
    obj = None
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text, match.start())
        except (ValueError, TypeError):
            continue
        if isinstance(candidate, dict):
            obj = candidate
            break
    if obj is None:
        raise ContentUnavailableError("La respuesta no contiene un objeto JSON")

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
        "situation": _situation_from(obj.get("situation"), word),
    }


def _situation_from(raw_situation: object, word: str) -> str:
    """Enunciado situacional validado, o "" si no cumple el contrato (V3.38).

    V3.38.1 (P2-01): delega en el validador puro `services.situation`, que
    exige UN hueco, UNA sola frase, longitud acotada y ausencia de fuga de la
    diana (forma textual o variante morfológica regular). La misma función
    valida la lectura en la escalera de recall, así que generación y servicio no
    pueden divergir.
    """
    return situation_service.validate_situation(raw_situation, word)


async def generate_content(
    word: str,
    *,
    model: str | None = None,
    fetcher=None,
) -> dict:
    """Genera `{pos, definition, translation, situation}` para `word`.

    `fetcher` es inyectable para tests (default: llamada real `_fetch_chat`).
    La palabra debe venir normalizada (minúsculas, sin puntuación circundante).
    Lanza `ContentUnavailableError` si el modelo falla o la respuesta no valida.
    """
    fetch = fetcher or _default_fetcher
    raw = await fetch(word, model)
    return parse_content(raw, word=word)

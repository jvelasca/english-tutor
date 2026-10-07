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
from services import llm, semantics, translate
from services import situation as situation_service

# V3.95.0: el guardarraíl de retrotraducción reutiliza el comparador del matcher
# inverso (`_gloss_segments`, `_segment_score`, `normalize_term`) en vez de
# escribir una segunda semántica de coincidencia. `dictionary_reverse` no
# importa este módulo, así que no hay ciclo.
from services.dictionary_reverse import (
    _gloss_segments,
    _segment_score,
    normalize_term,
)

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
#
# V3.39: bump 1.2.1 -> 1.3.0. El contrato de contenido gana la dirección ES→EN
# (`dictionary_reverse_entries`, prompt propio): el contenido directo se
# regenera una sola vez para incorporar el nuevo `GENERATOR_VERSION` común a
# ambas direcciones (una sola política de frescura para las dos cachés).
#
# V3.44 (P1-01 de la auditoría de V3.43.0): bump 1.3.0 -> 1.4.0. El contrato de
# contenido gana `senses` (los sentidos declarados de la unidad, cada uno con su
# `pos` y su glosa): es lo que permite que el scoring semántico deje de usar la
# `pos` GLOBAL como sustituto de sentido. El contenido cacheado con 1.3.0 no los
# tiene, así que se regenera una sola vez al primer lookup (misma política de
# invalidación lazy, sin migración de datos).
#
# V3.86.0: bump 1.4.0 -> 1.5.0. El contrato de contenido gana `meanings`, los
# significados ELEGIBLES que la UI ofrece para desambiguar una palabra
# polisémica, con marca de nombre propio. Es lo que retira la fila envenenada de
# «lima» (un nombre propio servido como equivalente de un nombre común) y lo que
# permite elegir «file» en lugar de «Lima». El contenido con 1.4.0 se regenera
# una sola vez al primer lookup (misma invalidación lazy).
#
# V3.88.0: bump 1.5.0 -> 1.6.0. El prompt deja de pedir «at most 6» y EXIGE el
# mínimo `MIN_MEANINGS` cuando la palabra tiene más de un sentido común. Era el
# fallo real de V3.86.0: la plomería de significados existía, pero el modelo
# devolvía uno solo para casi todo, así que el selector nacía con una opción. El
# contenido con 1.5.0 se regenera una sola vez al primer lookup.
#
# V3.91: bump 1.6.0 -> 1.7.0. El contrato de ACEPCIÓN crece de `{pos, gloss}` a
# los nueve campos que el motor de sentidos necesita para DESAMBIGUAR y para
# pintar la ficha: `{term, pos, gloss, domain, proper_noun, example, context,
# lemma, source}`. Los sentidos dejan de ser una etiqueta interna del scoring
# semántico y pasan a ser contenido de pantalla (acepción con su equivalente,
# su ejemplo, su contexto y su audio). Los dos prompt piden UNA acepción por
# significado, en el MISMO orden que `meanings`, y el contenido con 1.6.0 se
# regenera una sola vez al primer lookup (misma invalidación perezosa: no hay
# migración de datos ni de esquema, y `pos`/`gloss` siguen siendo la identidad
# frente a los sentidos viejos, así que el scoring NO cambia de forma).
#
# V3.95.0: bump 1.7.0 -> 1.8.0. La dirección ES→EN gana el guardarraíl de
# RETROTRADUCCIÓN (`generate_reverse_content`): un equivalente que no vuelve al
# término español de origen se descarta en vez de servirse y cachearse. Era el
# fallo de la caché de «broca» → «rock» (confusión con «roca»). El contenido
# anterior a 1.8.0 se regenera una sola vez al primer lookup y, al pasar por el
# guardarraíl, una fila envenenada no puede sobrevivir al bump.
GENERATOR_VERSION = "1.8.0"

# Límites de contenido generado (validación del parseo tolerante).
MAX_WORD_CHARS = 80
MAX_DEFINITION_CHARS = 600
MAX_TRANSLATION_CHARS = 200
# La traducción inversa (ES→EN) es una palabra o locución corta; se acota para
# que el modelo no devuelva una explicación en lugar de un equivalente.
MAX_ENGLISH_CHARS = 120
# El enunciado situacional es UNA frase de escenario con un único hueco; se
# acota para que no se convierta en un párrafo.
# V3.38.1 (P2-01): la validación del enunciado situacional vive en la capa pura
# `services.situation` (única fuente de verdad, compartida con la lectura de la
# escalera). Aquí solo se re-exportan los nombres por retrocompatibilidad.
MAX_SITUATION_CHARS = situation_service.MAX_SITUATION_CHARS
SITUATION_BLANK = situation_service.SITUATION_BLANK

# V3.44 (P1-01): sentidos declarados de la unidad. Cada sentido es
# `{"pos": <categoría canónica>, "gloss": <etiqueta corta en inglés simple>}`.
# El tope evita que el modelo convierta la ficha en un listado interminable y la
# glosa se acota para que sea una ETIQUETA de sentido, no una definición.
MAX_SENSES = 4
MAX_GLOSS_CHARS = 120

# V3.91 (diccionario de sentidos): contrato de ACEPCIÓN. Un sentido deja de ser
# una etiqueta para el scoring y pasa a ser la unidad que la ficha pinta:
#
# - `term`   — equivalente en el OTRO idioma de esa acepción (español en EN→ES,
#              inglés en ES→EN): es lo que hace legible la acepción.
# - `pos`    — categoría canónica (la misma taxonomía que `meanings`).
# - `gloss`  — etiqueta corta en inglés simple.
# - `domain` — ámbito («tools», «finance», «geography»).
# - `proper_noun` — nombre propio: nunca el defecto y siempre marcado.
# - `example`— UNA frase de uso en inglés de ESA acepción (lo que se lee con el
#              altavoz por acepción).
# - `context`— etiqueta corta del contexto donde se usa («money and finance»).
# - `lemma`  — forma base declarada, ACEPTADA solo si el motor puro de morfología
#              la reconoce como forma de la cabeza (nunca se inventa: ver
#              `_sense_lemma`); "" si el modelo no la declaró o no es creíble.
# - `source` — procedencia del contenido (`model` en esta fase; `lexicon`
#              reservado al lexicón offline de la fase 2/3). Es lo que permite
#              decir de dónde sale cada acepción sin mentir.
#
# El orden de `SENSE_KEYS` es el ORDEN DE LECTURA de la ficha y también el orden
# de las claves del JSON persistido (estable, para que el diff de la caché sea
# legible).
SENSE_KEYS = (
    "term",
    "pos",
    "gloss",
    "domain",
    "proper_noun",
    "example",
    "context",
    "lemma",
    "source",
)
# El ejemplo de uso es UNA frase corta (no un párrafo); el contexto es una
# ETIQUETA («at a river»), no una explicación.
MAX_SENSE_EXAMPLE_CHARS = 240
MAX_CONTEXT_CHARS = 80
# Procedencia del contenido de una acepción. `lexicon` NO se produce todavía:
# existe para que el lexicón offline de la fase 2/3 marque lo suyo sin tocar el
# contrato ni la UI.
SENSE_SOURCE_MODEL = "model"
SENSE_SOURCE_LEXICON = "lexicon"

# V3.86.0 (diccionario polisémico): significados elegibles. Cada significado es
# `{"term": <equivalente en el otro idioma>, "pos", "gloss", "domain",
# "proper_noun"}`. El tope es más alto que el de `senses` porque una palabra
# polisémica real (banco, lima, hoja) tiene más acepciones que categorías
# gramaticales, pero sigue acotado para no convertir la ficha en un listado.
MAX_MEANINGS = 6
# V3.88.0: mínimo exigido. El prompt decía «at most 6» sin pedir ninguno, así que
# el modelo devolvía un solo significado para casi todo y el selector de la
# tarjeta nacía con una única opción (y `senses`/`alternatives` no lo cubrían).
# El mínimo solo aplica cuando la palabra tiene más de un sentido común: una
# palabra monosémica sigue devolviendo uno, y eso es correcto.
MIN_MEANINGS = 2
# Regla de recuento inyectada en AMBOS prompts. Se construye aquí para que el
# contrato sea verificable por test (el literal aparece en el prompt) y para no
# volver a escribir el número a mano en dos sitios.
_MEANINGS_COUNT_RULE = (
    f"at least {MIN_MEANINGS} and at most {MAX_MEANINGS} when the headword "
    "has more than one common meaning, otherwise just the one"
)
MAX_MEANING_TERM_CHARS = 120
MAX_DOMAIN_CHARS = 40

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
# V3.91: alias PÚBLICO de la taxonomía. El mapeo de POS de un lexicón externo
# (`services.dictionary_batch.map_pos`) tiene que validar contra la MISMA lista
# que usa el modelo: dos taxonomías paralelas acabarían divergiendo, y una POS
# que el scoring no reconoce es una POS que la UI pinta y el motor ignora.
VALID_POS = _VALID_POS

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
    "of it anywhere else in the sentence), "
    '"senses" (a JSON array with ONE object per MEANING of the headword, at '
    f"most {MAX_SENSES}, in the SAME order as the meanings below and "
    "describing the SAME meanings, so its first objects are the senses of the "
    'most common meanings; each object has "term" (the Spanish translation '
    'for THAT meaning), "pos" (same list as above), "gloss" (a very short '
    "sense label in SIMPLE English, at most 60 characters), \"domain\" (same "
    'as the meanings below), "proper_noun" (same rule as the meanings below), '
    '"example" (ONE short English sentence, at most 240 characters, that uses '
    "the headword with THAT meaning and clearly fits THAT meaning, with no "
    'blank in it) and "context" (a very short English label of the situation '
    "where THAT meaning is used, at most 80 characters, for example "
    '"money and finance" or "at a river"), '
    '"meanings" (a JSON array with ONE object per DIFFERENT meaning of the '
    f"headword, {_MEANINGS_COUNT_RULE}, ordered with the most common meaning "
    "first; each "
    'object has "term" (the Spanish translation for THAT meaning), "pos" '
    "(same list as above), \"gloss\" (a very short English label, at most 60 "
    'characters), "domain" (a very short area label in English, for example '
    '"tools", "geography", "botany", "finance", or "" if unclear) and '
    '"proper_noun" (true ONLY if that meaning is a proper noun: a place, a '
    "person or a brand name). RULES: a proper noun must NEVER be the only "
    "translation of a common noun; if the headword also names a place or a "
    "person, put that meaning LAST with \"proper_noun\": true. If the headword "
    "has several common meanings, NEVER return only one: list the most common "
    "ones (most common first) so the learner can choose. Every \"example\" "
    "must contain the headword in some form and must fit the meaning it "
    "belongs to; never repeat the same example in two senses. "
    "Do not add any text outside the JSON object."
)

# V3.39 (diccionario reversible): prompt de la dirección ES→EN. Devuelve el
# equivalente inglés principal (`english`) más su definición simple y un
# enunciado situacional EN INGLÉS con hueco (el peldaño `situation` sirve
# siempre la palabra inglesa, también cuando la búsqueda fue en español).
# V3.86.0: añade `meanings`, los EQUIVALENTES INGLESES elegibles del término
# español (con nombre propio marcado y enviado al final).
_REVERSE_SYSTEM_PROMPT = (
    "You are a learner-friendly bilingual dictionary inside a local "
    "language-learning app. For the given Spanish word or phrase, reply with "
    "ONLY one JSON object with exactly these keys: "
    '"english" (the most common English equivalent, a word or short phrase, '
    "without articles or explanations), "
    '"pos" (one of: noun, verb, adjective, adverb, pronoun, preposition, '
    "conjunction, interjection, determiner, phrase), "
    '"definition" (a short definition in SIMPLE English of that English '
    "equivalent, one or two sentences, without examples inside it), "
    '"situation" (ONE short English sentence, at most 200 characters, that '
    "sets a concrete everyday scenario and contains EXACTLY one blank "
    '"_____" where the English equivalent fits; do NOT write the English '
    "equivalent or any form of it anywhere else in the sentence), "
    '"senses" (a JSON array with ONE object per MEANING of the English '
    f"equivalent, at most {MAX_SENSES}, in the SAME order as the meanings "
    "below and describing the SAME meanings, so its first objects are the "
    'senses of the most common meanings; each object has "term" (the English '
    'equivalent for THAT meaning), "pos" (same list as above), "gloss" (a '
    'very short sense label in SIMPLE English, at most 60 characters), '
    '"domain" (same as the meanings below), "proper_noun" (same rule as the '
    'meanings below), "example" (ONE short English sentence, at most 240 '
    "characters, that uses the English equivalent with THAT meaning and "
    'clearly fits THAT meaning, with no blank in it) and "context" (a very '
    "short English label of the situation where THAT meaning is used, at most "
    '80 characters, for example "money and finance" or "at a river"), '
    '"meanings" (a JSON array with ONE object per DIFFERENT English '
    "equivalent of the Spanish headword, "
    f"{_MEANINGS_COUNT_RULE}, ordered with the most "
    "common meaning first; each object has \"term\" (the English equivalent "
    'for THAT meaning), "pos", "gloss" (a very short English label, at most '
    '60 characters), "domain" (a very short area label in English, for '
    'example "tools", "geography", "botany", "finance", or "" if unclear) '
    'and "proper_noun" (true ONLY if that equivalent is a proper noun: a '
    "place, a person or a brand name). RULES: a proper noun must NEVER be "
    "the only equivalent of a common noun; if the Spanish word also names a "
    "place or a person, put that meaning LAST with \"proper_noun\": true. If "
    "the Spanish word has several common meanings, NEVER return only one: list "
    "the most common English equivalents (most common first) so the learner "
    "can choose. Every \"example\" must contain the English equivalent in some "
    "form and must fit the meaning it belongs to; never repeat the same "
    "example in two senses. "
    "If you do NOT know the English equivalent, or you are not confident it is "
    "correct, reply with exactly {\"english\": null} instead of guessing. "
    "Do not add any text outside the JSON object."
)


class ContentUnavailableError(RuntimeError):
    """Contenido de diccionario no disponible (modelo caído o respuesta inválida).

    El dominio lo captura y degrada a `definition_source="none"`; nunca debe
    propagarse como error 5xx: la consulta sigue sirviendo uso y ejemplo.
    """


async def _fetch_chat(
    word: str, model: str | None, *, system_prompt: str = _SYSTEM_PROMPT
) -> str:
    """Llama al modelo local y devuelve el texto crudo de la respuesta.

    Elige modelo con la misma política de `translate.pick_model` (rápido
    instalado; nunca `config.UNUSABLE_MODELS`) y `temperature=0` para que la
    generación sea lo más reproducible posible. Cualquier fallo de red/modelo o
    respuesta vacía se convierte en `ContentUnavailableError` (degradación).
    `system_prompt` permite reutilizarla en la dirección ES→EN (V3.39).
    """
    try:
        chosen = await translate.pick_model(model)
        reply = await llm.chat_once(
            messages=[ChatMessage(role="user", content=word)],
            model=chosen,
            temperature=0.0,
            system_prompt=system_prompt,
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


def _first_json_object(text: str) -> dict | None:
    """Primer objeto JSON válido del texto (o None).

    Barrido tolerante con `raw_decode` en cada `{` (V3.30.1): la vieja regex
    greedy `{.*}` podía tragarse `{…} texto {…}` hasta el último cierre.
    """
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text, match.start())
        except (ValueError, TypeError):
            continue
        if isinstance(candidate, dict):
            return candidate
    return None


def _sense_text(value: object, limit: int) -> str:
    """Texto de una acepción: espacios colapsados y recortado a `limit` (V3.91).

    Un solo camino para los campos de una acepción (`term`, `gloss`, `domain`,
    `example`, `context`, `lemma`): lo que el modelo devuelva como lista o número
    se trata como TEXTO vacío en vez de romper el parseo, y nunca se deja un
    campo con saltos de línea que romperían la ficha.
    """
    text = " ".join(str(value if value is not None else "").split())
    return text[:limit].strip() if limit > 0 else text.strip()


def _sense_lemma(declared: object, word: str) -> str:
    """Forma base ACEPTADA de una acepción, o "" si no es creíble (V3.91, pura).

    El `lemma` lo declara el modelo, pero no se sirve tal cual: la morfología de
    la app (`services.semantics`, la MISMA que usa el Sense Engine) tiene que
    reconocer la relación con la cabeza. Se acepta si

    - es la propia cabeza (`bank` → `bank`), o
    - es una forma de la cabeza según las variantes declaradas
      (`banks` → `bank`, `making` → `make`), o
    - la cabeza es una forma de ÉL (`run` → `run`, `running` → `run`).

    Cualquier otra cosa se descarta y la acepción queda sin lema: la ficha lo
    omite y NO se muestra una forma base inventada. Se descarta a propósito la
    comprobación morfológica sobre el EJEMPLO (una flexión irregular legítima
    —`go` → `went`— haría perder ejemplos buenos) porque el lema es una
    RELACIÓN declarada y verificable, y el ejemplo es contenido de lectura.
    """
    candidate = _sense_text(declared, MAX_MEANING_TERM_CHARS).lower()
    base = _sense_text(word, MAX_MEANING_TERM_CHARS).lower()
    if not candidate or not base:
        return ""
    if candidate == base:
        return candidate
    if candidate in semantics.lemma_variants(base):
        return candidate
    if base in semantics.lemma_variants(candidate):
        return candidate
    return ""


def normalize_senses(
    raw: object,
    *,
    word: str = "",
    source: str = SENSE_SOURCE_MODEL,
) -> list[dict]:
    """Acepciones declaradas de la unidad, normalizadas (V3.44 → V3.91).

    Acepta la lista cruda del modelo y devuelve una lista NUEVA de objetos con el
    contrato de `SENSE_KEYS` —`{term, pos, gloss, domain, proper_noun, example,
    context, lemma, source}`—, SIEMPRE con las nueve claves (un campo que el
    modelo no dio queda `""`/`False`, nunca ausente: el contrato tiene una forma,
    no varias):

    - descarta los elementos que no son objetos o cuyo `pos` no es canónico
      (nunca se inventa una categoría; es la MISMA regla de V3.44 y lo que
      mantiene al Sense Engine sin cambios: sigue leyendo `pos` y `gloss`);
    - colapsa los espacios y recorta `term`/`gloss`/`domain`/`example`/`context`;
    - acepta `proper_noun` **solo si es boolean** (`True`/`False`), como en
      `normalize_meanings`: el string `"false"` es *truthy* en Python y el
      contenido lo genera un modelo;
    - acepta el `lemma` solo si el motor puro lo reconoce (`_sense_lemma`) y
      sella `source` con la procedencia declarada por quien llama;
    - deduplica por `(pos, gloss)` conservando el primer orden —la identidad de
      V3.44, para que el `sense_index` del intento de transferencia no cambie de
      significado— y limita a `MAX_SENSES`.

    `word` es la cabeza de la entrada (la palabra inglesa en EN→ES, el
    equivalente inglés en ES→EN): sin ella no hay relación de lema que verificar
    y `lemma` queda `""` (el modelo no puede declararlo solo).

    Es contenido OPCIONAL: una entrada inválida se descarta y devuelve `[]` sin
    invalidar definición/traducción. Nunca lanza.
    """
    if not isinstance(raw, list):
        return []
    senses: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        pos = str(item.get("pos") or "").strip().lower()
        if pos not in _VALID_POS:
            continue
        gloss = _sense_text(item.get("gloss"), MAX_GLOSS_CHARS)
        key = (pos, gloss)
        if key in seen:
            continue
        seen.add(key)
        senses.append(
            {
                "term": _sense_text(item.get("term"), MAX_MEANING_TERM_CHARS),
                "pos": pos,
                "gloss": gloss,
                "domain": _sense_text(item.get("domain"), MAX_DOMAIN_CHARS),
                # Estricto a propósito, igual que en `normalize_meanings`.
                "proper_noun": item.get("proper_noun") is True,
                "example": _sense_text(item.get("example"), MAX_SENSE_EXAMPLE_CHARS),
                "context": _sense_text(item.get("context"), MAX_CONTEXT_CHARS),
                "lemma": _sense_lemma(item.get("lemma"), word),
                "source": source,
            }
        )
        if len(senses) >= MAX_SENSES:
            break
    return senses


def normalize_meanings(raw: object) -> list[dict]:
    """Significados elegibles de la unidad, normalizados y deterministas (V3.86.0).

    Acepta la lista cruda del modelo y devuelve una lista NUEVA de
    `{"term", "pos", "gloss", "domain", "proper_noun"}`:

    - descarta los elementos que no son objetos o sin `term`;
    - normaliza `pos` a la taxonomía canónica ("" si no lo es: nunca se inventa);
    - colapsa y recorta `term`/`gloss`/`domain`;
    - deduplica por `term` normalizado —espacios colapsados y `casefold()`, la
      MISMA clave que usa el índice único de las fichas—, conservando el primer
      orden de entrada: en `meanings` el término ES el significado, así que dos
      apariciones del mismo equivalente son la misma acepción aunque declaren
      `pos` distinto (la primera trae la mejor metadata);
    - acepta `proper_noun` **solo si es boolean** (`True`/`False`). Cualquier
      otro valor —incluido el string `"false"`, que en Python es *truthy*— se
      trata como `False`: el contenido lo genera un modelo y el parser no puede
      fiarse de su tipo;
    - **reordena los nombres propios al final** (regla dura: un nombre propio
      nunca puede ser el significado por defecto si hay uno común);
    - limita a `MAX_MEANINGS`.

    Es contenido OPCIONAL: una entrada inválida se descarta sin invalidar el
    resto. Nunca lanza.
    """
    if not isinstance(raw, list):
        return []
    meanings: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        term = " ".join(str(item.get("term") or "").split())
        term = term[:MAX_MEANING_TERM_CHARS].strip()
        if not term:
            continue
        pos = str(item.get("pos") or "").strip().lower()
        if pos not in _VALID_POS:
            pos = ""
        gloss = " ".join(str(item.get("gloss") or "").split())
        gloss = gloss[:MAX_GLOSS_CHARS].strip()
        domain = " ".join(str(item.get("domain") or "").split())
        domain = domain[:MAX_DOMAIN_CHARS].strip()
        # Dedupe por TÉRMINO (sin distinguir mayúsculas): en `meanings` el término
        # ES el significado, así que dos apariciones del mismo equivalente son la
        # misma acepción aunque declaren `pos` distinto. Conserva la primera, que
        # es la que trae la mejor metadata (ámbito/glosa). `casefold()` —la misma
        # clave que el índice único de `flashcard_cards`— cubre mejor que
        # `lower()` los alfabetos no ASCII.
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        meanings.append(
            {
                "term": term,
                "pos": pos,
                "gloss": gloss,
                "domain": domain,
                # Estricto a propósito: `bool("false")` es `True` en Python, y el
                # modelo a veces devuelve el booleano como string. Solo el boolean
                # de verdad marca un nombre propio.
                "proper_noun": item.get("proper_noun") is True,
            }
        )
    # Regla dura (V3.86.0): un nombre propio jamás representa el significado por
    # defecto de una palabra común; va al final conservando su orden relativo.
    # Estable y determinista (no depende del orden de llegada más que para el
    # empate dentro de cada grupo).
    common = [m for m in meanings if not m["proper_noun"]]
    proper = [m for m in meanings if m["proper_noun"]]
    return (common + proper)[:MAX_MEANINGS]


def default_meaning_term(meanings: object, fallback: str = "") -> str:
    """Término del significado por defecto: primer NO nombre propio (V3.86.0).

    `normalize_meanings` ya deja los nombres propios al final, así que basta con
    el primer elemento; se recorre por claridad y por si una lista llega sin
    normalizar. Sin significados válidos devuelve `fallback` (el equivalente que
    el modelo declaró en `translation`/`english`).
    """
    for item in meanings if isinstance(meanings, (list, tuple)) else ():
        if not isinstance(item, dict):
            continue
        if item.get("proper_noun"):
            continue
        term = str(item.get("term") or "").strip()
        if term:
            return term
    for item in meanings if isinstance(meanings, (list, tuple)) else ():
        if isinstance(item, dict):
            term = str(item.get("term") or "").strip()
            if term:
                return term
    return fallback


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

    V3.44: `senses` es el modelo de sentidos con el que el scoring semántico deja
    de depender de una `pos` global. También es contenido OPCIONAL y se normaliza
    con `normalize_senses` (nunca invalida la definición/traducción); el `pos`
    superior se deriva del primer sentido.

    V3.91: `senses` deja de ser una etiqueta y pasa a ser la ACEPCIÓN que la
    ficha pinta (`SENSE_KEYS`). El `lemma` se sella solo si el motor puro de
    morfología lo reconoce frente a la cabeza (`word`) y `source` declara la
    procedencia; los dos campos son DERIVADOS, no se copian del modelo.
    """
    text = (raw or "").strip()
    if not text:
        raise ContentUnavailableError("Respuesta vacía del modelo")
    obj = _first_json_object(text)
    if obj is None:
        raise ContentUnavailableError("La respuesta no contiene un objeto JSON")

    pos = str(obj.get("pos") or "").strip().lower()
    definition = str(obj.get("definition") or "").strip()
    translation = str(obj.get("translation") or "").strip()
    if not definition:
        raise ContentUnavailableError("La respuesta no incluye una definición")
    if len(definition) > MAX_DEFINITION_CHARS:
        raise ContentUnavailableError("La definición supera el límite de longitud")
    senses = normalize_senses(obj.get("senses"), word=word)
    # V3.86.0: significados elegibles. Si el modelo no los dio, se sintetiza uno
    # desde `translation` para que la UI siempre tenga al menos una opción
    # seleccionable (degradación honesta, sin inventar acepciones). En ese caso
    # `translation` conserva su valor declarado (y su límite de longitud); el
    # término del significado por defecto solo manda cuando el modelo SÍ declaró
    # significados, que es donde puede colarse un nombre propio.
    declared = normalize_meanings(obj.get("meanings"))
    fallback_pos = senses[0]["pos"] if senses else (pos if pos in _VALID_POS else "")
    meanings = declared or normalize_meanings(
        [
            {
                "term": translation,
                "pos": fallback_pos,
            }
        ]
    )
    default_term = (
        default_meaning_term(declared, translation) if declared else translation
    )
    return {
        # V3.44: una sola fuente de verdad para el `pos` superior: el primer
        # sentido válido; sin sentidos se conserva el `pos` del modelo si es
        # canónico (retrocompatible con el contrato 1.3.0).
        "pos": senses[0]["pos"] if senses else (pos if pos in _VALID_POS else ""),
        "definition": definition,
        # V3.86.0: `translation` es el término del significado POR DEFECTO (el
        # primer no nombre propio) cuando el modelo declaró significados: es la
        # regla que impide servir «Lima» como traducción de «lima».
        "translation": default_term[:MAX_TRANSLATION_CHARS],
        "situation": _situation_from(obj.get("situation"), word),
        "senses": senses,
        "meanings": meanings,
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
    """Genera `{pos, definition, translation, situation, senses}` para `word`.

    `fetcher` es inyectable para tests (default: llamada real `_fetch_chat`).
    La palabra debe venir normalizada (minúsculas, sin puntuación circundante).
    Lanza `ContentUnavailableError` si el modelo falla o la respuesta no valida.
    """
    fetch = fetcher or _default_fetcher
    raw = await fetch(word, model)
    return parse_content(raw, word=word)


def parse_reverse_content(raw: str, *, word: str = "") -> dict:
    """Parsea y valida la respuesta ES→EN del modelo (V3.39).

    Devuelve `{english, pos, definition, situation}`. `english` es OBLIGATORIO
    (es la razón de ser de la dirección inversa): sin equivalente inglés la
    respuesta se descarta y el dominio degrada a `definition_source="none"`.
    `pos` se normaliza a la taxonomía canónica, `definition` se acota a
    `MAX_DEFINITION_CHARS` y `situation` pasa por el mismo validador puro que la
    dirección directa (una frase, un hueco, sin fuga de la diana inglesa).

    V3.44: `senses` (del equivalente INGLÉS) se normaliza con el mismo
    `normalize_senses`; el `pos` superior se deriva del primer sentido.

    V3.91: la cabeza de la acepción en esta dirección es el EQUIVALENTE INGLÉS
    (el término español solo se usa para buscar), así que el `lemma` se verifica
    contra él y `source` declara la procedencia como en la dirección directa.
    """
    text = (raw or "").strip()
    if not text:
        raise ContentUnavailableError("Respuesta vacía del modelo")
    obj = _first_json_object(text)
    if obj is None:
        raise ContentUnavailableError("La respuesta no contiene un objeto JSON")
    english = str(obj.get("english") or "").strip()
    if not english:
        raise ContentUnavailableError("La respuesta no incluye el equivalente inglés")
    english = english[:MAX_ENGLISH_CHARS].strip()
    definition = str(obj.get("definition") or "").strip()
    if not definition:
        raise ContentUnavailableError("La respuesta no incluye una definición")
    if len(definition) > MAX_DEFINITION_CHARS:
        raise ContentUnavailableError("La definición supera el límite de longitud")
    pos = str(obj.get("pos") or "").strip().lower()
    senses = normalize_senses(obj.get("senses"), word=english)
    # V3.86.0: significados elegibles en la dirección inversa. El `term` de cada
    # significado es un EQUIVALENTE INGLÉS del término español; los nombres
    # propios van al final. Sin lista del modelo se sintetiza uno desde `english`
    # (que entonces conserva su valor y su límite de longitud).
    declared = normalize_meanings(obj.get("meanings"))
    fallback_pos = senses[0]["pos"] if senses else (pos if pos in _VALID_POS else "")
    meanings = declared or normalize_meanings(
        [
            {
                "term": english,
                "pos": fallback_pos,
            }
        ]
    )
    default_term = (
        default_meaning_term(declared, english) if declared else english
    )
    return {
        # V3.86.0: `english` es el equivalente del significado por defecto (el
        # primer no nombre propio). Es la regla que evita servir «Lima» (capital)
        # como equivalente de «lima» (herramienta).
        "english": default_term[:MAX_ENGLISH_CHARS],
        "pos": senses[0]["pos"] if senses else (pos if pos in _VALID_POS else ""),
        "definition": definition,
        "situation": _situation_from(obj.get("situation"), english),
        "senses": senses,
        "meanings": meanings,
    }


async def generate_reverse_content(
    word: str,
    *,
    model: str | None = None,
    fetcher=None,
    verifier=None,
) -> dict:
    """Genera `{english, pos, definition, situation, senses}` para el término ES `word`.

    Mismo `fetcher` inyectable y misma degradación que `generate_content`; el
    término debe venir normalizado (minúsculas, acentos conservados).

    V3.95.0 (guardarraíl de retrotraducción): antes de dar por buena la respuesta,
    el equivalente inglés elegido se RETROTRADUCE con el modelo y se exige que el
    término español de origen aparezca entre sus traducciones. Es lo que impide
    servir (y CACHEAR) un equivalente inventado por confusión léxica —el caso
    reportado «broca» → «rock» (roca)—: como «rock» retrocede a «roca», no a
    «broca», se descarta con `ContentUnavailableError` y el dominio degrada a
    `definition_source="none"` en lugar de envenenar la caché global. La
    verificación es inyectable (`verifier`) para los tests.
    """
    fetch = fetcher or _reverse_fetcher
    raw = await fetch(word, model)
    content = parse_reverse_content(raw, word=word)
    english = (content.get("english") or "").strip()
    check = verifier or _default_reverse_verifier
    if english and not await check(word, english, model):
        raise ContentUnavailableError(
            f"El equivalente '{english}' de '{word}' no supera la retrotraducción"
        )
    return content


async def _reverse_fetcher(word: str, model: str | None) -> str:
    """Llama al modelo local con el prompt ES→EN (misma política y degradación)."""
    return await _fetch_chat(word, model, system_prompt=_REVERSE_SYSTEM_PROMPT)


def _spanish_candidates(direct: dict) -> list[str]:
    """Términos ESPAÑOLES con los que el modelo describe una palabra inglesa.

    De la respuesta EN→ES (`translation` + `meanings`) extrae los segmentos
    comparables de cada glosa con el MISMO comparador plegado del matcher inverso
    (`services.dictionary_reverse`), para no inventar una segunda semántica de
    coincidencia. Puro y tolerante: cualquier campo ausente se ignora.
    """
    candidates: list[str] = []
    candidates.extend(_gloss_segments(direct.get("translation") or ""))
    for meaning in direct.get("meanings") or []:
        if isinstance(meaning, dict):
            term = normalize_term(meaning.get("term") or "")
            if term:
                candidates.append(term)
    return candidates


def _matches_source_term(word: str, candidates: list[str]) -> bool:
    """¿El término español `word` está entre los candidatos de la retrotraducción?

    Usa el scoring de coincidencia del matcher inverso (`_segment_score`):
    exacta, prefijo u ocurrencia como palabra completa. Plegado de acentos
    incluido (la eñe se conserva como letra distinta).
    """
    target = normalize_term(word)
    if not target:
        return False
    return any(_segment_score(candidate, target) >= 0 for candidate in candidates)


async def _default_reverse_verifier(
    word: str, english: str, model: str | None
) -> bool:
    """Retrotraducción de `english` (EN→ES) y comprobación contra `word` (V3.95.0).

    Llama al modelo con el prompt DIRECTO sobre el equivalente inglés y exige que
    el término español buscado aparezca entre los términos devueltos. Cualquier
    fallo del modelo o respuesta inválida se trata como NO verificado (se
    descarta el equivalente): es más honesto degradar a «sin contenido» que
    servir una traducción que no se ha podido comprobar. Puro respecto al
    estado del producto (no persiste nada).
    """
    try:
        raw = await _fetch_chat(english, model)
    except ContentUnavailableError:
        return False
    try:
        direct = parse_content(raw, word=english)
    except ContentUnavailableError:
        return False
    return _matches_source_term(word, _spanish_candidates(direct))


# Punto de inyección para tests (sustituible sin tocar el modelo), igual que
# `_default_fetcher`: el guardarraíl lo consulta en tiempo de llamada.
_default_reverse_verifier = _default_reverse_verifier

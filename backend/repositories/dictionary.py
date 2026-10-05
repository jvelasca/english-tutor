"""Caché persistente del contenido del diccionario de consulta (V3.30, D1).

Tabla global `dictionary_entries` (sin `user_id`): la definición/traducción de
una palabra es contenido de idioma, no evidencia de un alumno, así que una vez
generada (Fase B, modelo local) cualquier usuario la lee sin volver a pagar la
latencia del modelo.

Cada entrada guarda `generator_version` (V3.30.1, P1-03): la versión del
prompt/parseador/política con la que se generó. El dominio solo sirve caché
cuya versión coincide con la actual; si una versión futura cambia el criterio,
la entrada obsoleta se regenera y se SOBRESCRIBE (`save_entry`, ON CONFLICT DO
UPDATE) en lugar de quedar como contenido obsoleto permanente.

Este repositorio nunca registra evidencia del alumno ni toca
`vocabulary`/`vocabulary_events` (decisión D3: la consulta es solo lectura).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import closing

from repositories.db import (
    DICTIONARY_FTS_TABLE,
    _conn,
    _now,
    fts5_available,
)

# El contrato de ACEPCIÓN (`SENSE_KEYS`) vive con el contenido que lo produce
# (`services.dictionary_content`, su prompt y su normalizador) y el repositorio lo
# IMPORTA en vez de reescribirlo: el mismo criterio declarado para la plegadura
# (`fold`) y para `front_key`. Duplicar la lista de claves aquí sería una segunda
# fuente de verdad que se desincronizaría al primer campo nuevo.
from services.dictionary_content import SENSE_KEYS
from services.dictionary_reverse import fold, phrase_query, phrase_tokens


def _decode_senses(raw: object) -> list[dict]:
    """Acepciones desde el JSON persistido (`[]` si vacío o corrupto) (V3.44 → V3.91).

    Tolerante a propósito: un `senses_json` ilegible no debe romper la consulta
    del diccionario ni el scoring (que degrada a `unknown`).

    V3.91: se conservan las claves del contrato de ACEPCIÓN (`SENSE_KEYS`) que la
    fila DECLARE —con su tipo normalizado: texto para las de texto, `bool`
    estricto para `proper_noun`— y se ignoran las desconocidas. Una fila de la
    caché anterior al contrato (1.6.0: `{pos, gloss}`) se sirve TAL CUAL, sin
    rellenar campos que nadie declaró: rellenarlos aquí inventaría contenido, y
    la política del proyecto es que la caché obsoleta se REGENERA (bump de
    `GENERATOR_VERSION`), no se disfraza.
    """
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    senses: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        entry: dict = {}
        for key in SENSE_KEYS:
            if key not in item:
                continue
            if key == "proper_noun":
                entry[key] = item.get(key) is True
            else:
                entry[key] = str(item.get(key) or "").strip()
        senses.append(entry)
    return senses


def _encode_senses(senses: object) -> str:
    """Serializa las acepciones a JSON compacto y orden estable (V3.44 → V3.91).

    `""` cuando no hay acepciones. Acepta una lista de diccionarios (o una
    cadena JSON ya serializada, que se conserva) y escribe SOLO las claves del
    contrato que cada acepción declare, en el orden de `SENSE_KEYS`: una acepción
    de V3.91 viaja con sus nueve campos y una entrada antigua (`{pos, gloss}`) se
    persiste sin campos inventados. Descarta entradas vacías o que no sean
    diccionario; nunca lanza.
    """
    if not senses:
        return ""
    if isinstance(senses, str):
        return senses.strip()
    cleaned = []
    for item in senses if isinstance(senses, (list, tuple)) else ():
        if not isinstance(item, dict):
            continue
        entry: dict = {}
        for key in SENSE_KEYS:
            if key not in item:
                continue
            value = item.get(key)
            if key == "proper_noun":
                entry[key] = value is True
            else:
                entry[key] = str(value or "").strip()
        if not entry:
            continue
        cleaned.append(entry)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))


def _decode_meanings(raw: object) -> list[dict]:
    """Significados elegibles desde el JSON persistido (`[]` si vacío/corrupto).

    V3.86.0. Tolerante por el mismo motivo que `_decode_senses`: una fila
    ilegible no debe romper la consulta; la UI degrada a un único significado
    sintetizado desde `translation`/`english`.
    """
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    meanings: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            continue
        meanings.append(
            {
                "term": term,
                "pos": str(item.get("pos") or "").strip(),
                "gloss": str(item.get("gloss") or "").strip(),
                "domain": str(item.get("domain") or "").strip(),
                "proper_noun": bool(item.get("proper_noun")),
            }
        )
    return meanings


def _encode_meanings(meanings: object) -> str:
    """Serializa los significados elegibles a JSON compacto (V3.86.0).

    `""` cuando no hay. Descarta entradas sin `term`; nunca lanza. Acepta una
    cadena JSON ya serializada y la conserva.
    """
    if not meanings:
        return ""
    if isinstance(meanings, str):
        return meanings.strip()
    cleaned: list[dict] = []
    for item in meanings if isinstance(meanings, (list, tuple)) else ():
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            continue
        cleaned.append(
            {
                "term": term,
                "pos": str(item.get("pos") or "").strip(),
                "gloss": str(item.get("gloss") or "").strip(),
                "domain": str(item.get("domain") or "").strip(),
                "proper_noun": bool(item.get("proper_noun")),
            }
        )
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))


def _entry_dict(row: object) -> dict:
    """Fila de caché con sentidos y significados ya decodificados (V3.44/V3.86)."""
    entry = dict(row)  # type: ignore[arg-type]
    entry["senses"] = _decode_senses(entry.get("senses_json"))
    entry["meanings"] = _decode_meanings(entry.get("meanings_json"))
    return entry


def brief_for_words(words: list[str]) -> dict[str, dict]:
    """Traducción y definición de caché para esas palabras, sin el artículo entero."""
    wanted = [
        str(word or "").strip().lower() for word in words if str(word or "").strip()
    ]
    out: dict[str, dict] = {}
    if not wanted:
        return out
    with closing(_conn()) as conn:
        for start in range(0, len(wanted), 200):
            chunk = wanted[start : start + 200]
            marks = ",".join("?" for _ in chunk)
            rows = conn.execute(
                "SELECT word, translation, definition FROM dictionary_entries "
                f"WHERE word IN ({marks})",
                tuple(chunk),
            ).fetchall()
            for row in rows:
                out[str(row["word"])] = {
                    "translation": str(row["translation"] or ""),
                    "definition": str(row["definition"] or ""),
                }
    return out


def get_entry(word: str) -> dict | None:
    """Devuelve la entrada de diccionario cacheada de `word` (None si no existe).

    `word` debe venir ya normalizada (minúsculas, sin puntuación circundante).
    Incluye `generator_version` para que el dominio decida si la caché es
    válida con la política actual (V3.30.1, P1-03), `situation` (V3.38) y
    `senses` (V3.44, ya decodificados desde `senses_json`).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT word, pos, definition, translation, situation, senses_json, "
            "meanings_json, generator_version, created_at, updated_at "
            "FROM dictionary_entries WHERE word = ?",
            (word,),
        ).fetchone()
    return _entry_dict(row) if row else None


def fresh_entry_words(words: Iterable[str], *, version: str) -> set[str]:
    """Subconjunto de `words` que la caché ya sirve FRESCA (V3.91, fase 2).

    Mismo criterio que `domain.vocabulary._content_is_fresh`: versión de
    generación vigente **y** definición no vacía (una fila sin definición no es
    contenido servible: el dominio la degrada a `definition_source="none"`).
    Es la consulta que hace REANUDABLE al lote de operador: una palabra ya
    preparada deja de estar pendiente, así que relanzar continúa donde quedó sin
    fichero de estado ni marcas de «hecho» que puedan desincronizarse.

    Se consulta por lotes (`_IN_CHUNK`) para no depender del tope de parámetros
    del build de SQLite, y NUNCA se materializa la tabla completa: devuelve solo
    las palabras preguntadas.
    """
    wanted = [str(word).strip().lower() for word in words if str(word).strip()]
    if not wanted:
        return set()
    fresh: set[str] = set()
    with closing(_conn()) as conn:
        for start in range(0, len(wanted), _IN_CHUNK):
            chunk = list(dict.fromkeys(wanted[start : start + _IN_CHUNK]))
            marks = ",".join("?" * len(chunk))
            rows = conn.execute(
                "SELECT word FROM dictionary_entries "
                "WHERE generator_version = ? "
                "AND TRIM(COALESCE(definition, '')) <> '' "
                f"AND word IN ({marks})",
                (version, *chunk),
            ).fetchall()
            fresh.update(str(row[0]) for row in rows)
    return fresh


def save_entry(
    word: str,
    *,
    pos: str = "",
    definition: str = "",
    translation: str = "",
    situation: str = "",
    senses: object = None,
    meanings: object = None,
    generator_version: str = "",
) -> bool:
    """Inserta o sobrescribe la entrada de diccionario de `word` (V3.30.1).

    `INSERT ... ON CONFLICT(word) DO UPDATE`: escribe UNA fila tanto si la
    palabra es nueva (primera generación) como si ya existía con una
    `generator_version` obsoleta (regeneración controlada). `updated_at` se
    actualiza en cada escritura y `created_at` solo en la inserción inicial.
    Devuelve True si hubo operación de escritura (fila insertada o
    actualizada); el contenido es global (sin `user_id`).

    V3.38: `situation` es el enunciado situacional (con hueco `_____`) del
    peldaño `situation`; se persiste junto al resto del contenido para no pagar
    dos veces la latencia del modelo.

    V3.44: `senses` (`[{pos, gloss}]`) se serializa en `senses_json` (JSON
    compacto). Es contenido, no evidencia: permite que el scoring semántico
    deje de depender de la `pos` global.

    V3.86.0: `meanings` (`[{term, pos, gloss, domain, proper_noun}]`) se
    serializa en `meanings_json`: son los significados ELEGIBLES que la UI
    ofrece para desambiguar una palabra polisémica.

    V3.91: `translation` se guarda ADEMÁS plegada en `translation_fold` (misma
    `fold` que usa el matcher inverso), que es la columna por la que busca el
    índice FTS5 y el repliegue `LIKE`. Se calcula aquí y no en una migración
    posterior para que una fila nunca pueda nacer sin su forma plegada: el
    índice se alimenta de ella con un disparador.
    """
    with closing(_conn()) as conn, conn:
        now = _now()
        cursor = conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, situation, senses_json, "
            "meanings_json, generator_version, created_at, updated_at, "
            "translation_fold) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "pos = excluded.pos, "
            "definition = excluded.definition, "
            "translation = excluded.translation, "
            "situation = excluded.situation, "
            "senses_json = excluded.senses_json, "
            "meanings_json = excluded.meanings_json, "
            "generator_version = excluded.generator_version, "
            "updated_at = excluded.updated_at, "
            "translation_fold = excluded.translation_fold",
            (
                word,
                pos,
                definition,
                translation,
                situation,
                _encode_senses(senses),
                _encode_meanings(meanings),
                generator_version,
                now,
                now,
                fold(translation),
            ),
        )
        return cursor.rowcount > 0


_ENTRY_COLUMNS = (
    "word, pos, definition, translation, situation, senses_json, "
    "meanings_json, generator_version, created_at, updated_at"
)


def list_entries() -> list[dict]:
    """Todas las entradas globales de `dictionary_entries` (sin `user_id`).

    V3.33 (eslabón Recognition del puente): la caché global es el único
    contenido de significado del diccionario, así que el helper de MCQ la usa
    como banco de textos de significado candidatos a distractor. Sin filtro de
    `generator_version`: aunque una entrada quede obsoleta por un cambio de
    política del generador, su significado real sigue sirviendo de distractor
    para el reconocimiento. Orden estable por `word` (determinista).

    V3.91: **ya no la usa ningún camino de producción.** Volcar la tabla entera
    (y decodificar su JSON) era el O(N) medido de la inversa ES→EN; el producto
    usa consultas dirigidas (`get_entry`, `find_by_words`, `find_by_translation`,
    `distractor_pool`). Se conserva —con su semántica intacta— porque es la
    referencia con la que los tests comprueban que la búsqueda dirigida devuelve
    EXACTAMENTE lo mismo, y porque un instrumento (informe de caché) puede
    querer el volcado completo.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries ORDER BY word"
        ).fetchall()
    return [_entry_dict(row) for row in rows]


# Cota de filas que materializa una consulta dirigida. No es un límite de
# producto (el resultado visible son unas pocas opciones o el equivalente
# elegido): es la garantía de que ninguna consulta puede volver a leer la tabla
# COMPLETA, que es lo que este incremento retira.
_CANDIDATE_LIMIT = 200

# Cota del banco de distractores del MCQ: la diana más candidatos del mismo
# `pos` y, si hacen falta, del resto. El helper puro solo usa los 3 primeros.
_POOL_LIMIT = 60

# Tope de términos por consulta `IN (...)` (el límite de parámetros de SQLite es
# 999 en las compilaciones antiguas; se trocea para no depender del build).
_IN_CHUNK = 400


def find_by_translation(term: str, *, limit: int = _CANDIDATE_LIMIT) -> list[dict]:
    """Entradas cuya traducción puede contener `term` (V3.91, consulta dirigida).

    Sustituye el volcado completo con el que la inversa ES→EN pagaba 268 ms de
    CPU por consulta (medido a tamaño de diccionario completo en
    `docs/DISENO-V388-DICCIONARIO-OFFLINE.md` §2.3). La comparación fina sigue
    siendo la del matcher PURO (`services.dictionary_reverse.match_translation`),
    pero ahora se ejecuta sobre un conjunto ya reducido en SQL.

    Garantía declarada: el resultado es un **superconjunto** de las filas que el
    matcher puede aceptar, nunca un subconjunto. Con FTS5 se busca la FRASE de
    los tokens del término (secuencia contigua = la condición de palabra completa
    del matcher); sin FTS5 se repliega a un `LIKE` por TOKEN (todos los tokens
    tienen que aparecer en la traducción, en cualquier orden), que es más ANCHO
    que la frase justamente porque no hay índice que la resuelva. En los dos
    casos el matcher descarta lo que no encaje, así que un candidato de más no
    cambia el resultado; uno de menos sí, y por eso las dos vías son anchas.

    Se ordena por relevancia (`bm25`) y se materializan como mucho `limit`
    filas: el orden importa porque recortar candidatos por orden alfabético
    podría tirar la coincidencia EXACTA que el matcher pone primera.

    Los patrones salen de `services.dictionary_reverse.phrase_tokens` (letras y
    dígitos), así que ni el índice ni el repliegue pueden recibir un comodín o un
    operador escritos por el alumno: el término es TEXTO, nunca sintaxis.
    """
    tokens = phrase_tokens(term)
    if not tokens:
        return []
    with closing(_conn()) as conn:
        if fts5_available(conn):
            rows = conn.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries d "
                f"JOIN {DICTIONARY_FTS_TABLE} f ON f.rowid = d.rowid "
                f"WHERE {DICTIONARY_FTS_TABLE} MATCH ? "
                f"ORDER BY bm25({DICTIONARY_FTS_TABLE}) LIMIT ?",
                (phrase_query(term), limit),
            ).fetchall()
            return [_entry_dict(row) for row in rows]
        clauses = " AND ".join("translation_fold LIKE ?" for _ in tokens)
        params: list[object] = [f"%{token}%" for token in tokens]
        params.append(limit)
        rows = conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries "
            f"WHERE {clauses} "
            "ORDER BY length(translation_fold), word LIMIT ?",
            params,
        ).fetchall()
    return [_entry_dict(row) for row in rows]


def find_by_words(words: list[str]) -> list[dict]:
    """Entradas cacheadas de `words`, en UNA consulta por PK (V3.91).

    Es la consulta dirigida de los recorridos que solo necesitan la entrada de
    SU palabra (los peldaños de recall y su disponibilidad por palabra): antes
    leían la caché entera para buscar en Python la fila que ya sabían nombrar.

    `words` llega normalizada por el dominio (minúsculas, sin puntuación en los
    extremos, espacios colapsados: la misma clave con la que `save_entry` guarda
    y `get_entry` lee). Aun así se recorta y se pasa a minúsculas aquí, porque un
    lookup por PK es EXACTO y no puede permitirse fallar por una mayúscula.
    Solo las que existen; orden por `word` (determinista).
    """
    keys = sorted(
        {
            " ".join((word or "").split()).lower()
            for word in words
        }
        - {""}
    )
    if not keys:
        return []
    found: list[dict] = []
    with closing(_conn()) as conn:
        for start in range(0, len(keys), _IN_CHUNK):
            chunk = keys[start : start + _IN_CHUNK]
            placeholders = ", ".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries "
                f"WHERE word IN ({placeholders}) ORDER BY word",
                chunk,
            ).fetchall()
            found.extend(_entry_dict(row) for row in rows)
    return sorted(found, key=lambda entry: entry.get("word", ""))


def distractor_pool(word: str, *, limit: int = _POOL_LIMIT) -> list[dict]:
    """Diana y candidatos a distractor para el MCQ de reconocimiento (V3.91).

    Devuelve la entrada de `word` (si existe) y hasta `limit` entradas MÁS con
    algún texto de significado, en el MISMO orden con el que el helper puro
    (`services.dictionary_mcq._candidate_meanings`) elige distractores: primero
    las del MISMO `pos` que la diana y después el resto, cada franja por orden
    alfabético de `word`.

    La franja del mismo `pos` **solo existe si la diana declara `pos`**: el
    criterio del helper es `target_pos and entry.pos == target_pos`, así que con
    `pos` vacío TODAS las candidatas compiten en la misma franja por orden
    alfabético (una entrada sin `pos` no es «del mismo `pos`» que otra sin `pos`,
    es una candidata más). Reproducirlo mal no perdería candidatas —el `limit` es
    holgado— pero cambiaría el ORDEN de las primeras, y con él los tres
    distractores que el helper recorta: la misma palabra daría otras opciones.

    El recorte a `limit` por franja es una cota DECLARADA, no una garantía de
    suficiencia: si una franja entera se quedara corta de significados distintos,
    el MCQ degrada a «no disponible» (que ya era su contrato). Con el `limit`
    actual (60 frente a los 3 textos que el helper necesita) el caso no se da ni
    con la caché cargada.
    """
    key = " ".join((word or "").split()).lower()
    if not key:
        return []
    with closing(_conn()) as conn:
        target_row = conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries WHERE word = ?",
            (key,),
        ).fetchone()
        if target_row is None:
            return []
        target = _entry_dict(target_row)
        target_pos = (target.get("pos") or "").strip()
        bands: list[tuple[str, tuple[object, ...]]] = []
        if target_pos:
            bands.append(("AND pos = ? ", (target_pos,)))
            bands.append(("AND pos <> ? ", (target_pos,)))
        else:
            bands.append(("", ()))
        pool: list[dict] = [target]
        for condition, params in bands:
            rows = conn.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries "
                "WHERE word <> ? AND (translation <> '' OR definition <> '') "
                f"{condition}ORDER BY word LIMIT ?",
                (key, *params, limit),
            ).fetchall()
            pool.extend(_entry_dict(row) for row in rows)
    return pool


def translations_near(length: int, *, band: int, limit: int = 400) -> list[str]:
    """Traducciones cuya longitud cae cerca de `length`.

    Sirve para armar distractores de «¿Cuál es?» parecidos en tamaño antes de
    medir las sílabas. No devuelve la tabla entera.
    """
    low = max(1, length - band)
    high = max(low, length + band)
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT translation FROM dictionary_entries "
            "WHERE translation <> '' AND length(translation) BETWEEN ? AND ? "
            "ORDER BY word LIMIT ?",
            (low, high, limit),
        ).fetchall()
    return [str(row["translation"]) for row in rows]


def words_near(length: int, *, band: int, limit: int = 400) -> list[str]:
    """Lemas ingleses cuya longitud cae cerca de `length`.

    Distractores de «¿Cuál es?» cuando se pregunta el español y se responde
    la palabra inglesa. No devuelve la tabla entera.
    """
    low = max(1, length - band)
    high = max(low, length + band)
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word FROM dictionary_entries "
            "WHERE word <> '' AND length(word) BETWEEN ? AND ? "
            "ORDER BY word LIMIT ?",
            (low, high, limit),
        ).fetchall()
    return [str(row["word"]) for row in rows]


# ---------------------------------------------------------------------------
# V3.39 (diccionario reversible): caché ES→EN. Tabla propia y aislada de
# `dictionary_entries` para no contaminar el banco de distractores del MCQ
# (ver `repositories/db.py`). Misma política de versionado que la directa: el
# dominio solo sirve caché cuya `generator_version` coincide con la actual.
# ---------------------------------------------------------------------------

_REVERSE_COLUMNS = (
    "word, english, pos, definition, situation, senses_json, "
    "meanings_json, generator_version, created_at, updated_at"
)


def get_reverse_entry(word: str) -> dict | None:
    """Entrada ES→EN cacheada de `word` (None si no existe).

    `word` es el término ESPAÑOL ya normalizado (sin acentos plegados: la
    normalización conserva la eñe). Devuelve `english` (traducción principal) y
    el contenido inglés asociado (`pos`/`definition`/`situation`/`senses`).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_REVERSE_COLUMNS} FROM dictionary_reverse_entries "
            "WHERE word = ?",
            (word,),
        ).fetchone()
    return _entry_dict(row) if row else None


def save_reverse_entry(
    word: str,
    *,
    english: str = "",
    pos: str = "",
    definition: str = "",
    situation: str = "",
    senses: object = None,
    meanings: object = None,
    generator_version: str = "",
) -> bool:
    """Inserta o sobrescribe la entrada ES→EN de `word` (V3.39).

    Mismo `INSERT ... ON CONFLICT(word) DO UPDATE` que `save_entry`: sirve tanto
    para la primera generación como para regenerar contenido obsoleto. Devuelve
    True si hubo escritura. Contenido GLOBAL (sin `user_id`). V3.44: `senses`
    se persiste en `senses_json` (misma política que la dirección directa).
    V3.86.0: `meanings` (equivalentes ingleses elegibles) se persiste en
    `meanings_json`.
    """
    with closing(_conn()) as conn, conn:
        now = _now()
        cursor = conn.execute(
            "INSERT INTO dictionary_reverse_entries "
            "(word, english, pos, definition, situation, senses_json, "
            "meanings_json, generator_version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "english = excluded.english, "
            "pos = excluded.pos, "
            "definition = excluded.definition, "
            "situation = excluded.situation, "
            "senses_json = excluded.senses_json, "
            "meanings_json = excluded.meanings_json, "
            "generator_version = excluded.generator_version, "
            "updated_at = excluded.updated_at",
            (
                word,
                english,
                pos,
                definition,
                situation,
                _encode_senses(senses),
                _encode_meanings(meanings),
                generator_version,
                now,
                now,
            ),
        )
        return cursor.rowcount > 0


def list_reverse_entries() -> list[dict]:
    """Todas las entradas ES→EN (orden estable por término español)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_REVERSE_COLUMNS} FROM dictionary_reverse_entries "
            "ORDER BY word"
        ).fetchall()
    return [_entry_dict(row) for row in rows]


def cefr_words() -> dict[str, str]:
    """`palabra → CEFR` de la caché del diccionario, solo donde el nivel consta.

    Es el punto de extensión del banco de Estudiar: una importación que rellene
    `dictionary_entries.cefr` entra en el mismo recuento sin otra pantalla.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, cefr FROM dictionary_entries "
            "WHERE cefr IS NOT NULL AND cefr != ''"
        ).fetchall()
    return {
        str(row["word"]).strip().lower(): str(row["cefr"]).strip().upper()
        for row in rows
        if str(row["word"] or "").strip()
    }

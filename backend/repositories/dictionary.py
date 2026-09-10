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

from contextlib import closing

from repositories.db import _conn, _now


def get_entry(word: str) -> dict | None:
    """Devuelve la entrada de diccionario cacheada de `word` (None si no existe).

    `word` debe venir ya normalizada (minúsculas, sin puntuación circundante).
    Incluye `generator_version` para que el dominio decida si la caché es
    válida con la política actual (V3.30.1, P1-03) y `situation` (V3.38): el
    enunciado situacional del peldaño `situation` de la escalera de recall.
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT word, pos, definition, translation, situation, "
            "generator_version, created_at, updated_at "
            "FROM dictionary_entries WHERE word = ?",
            (word,),
        ).fetchone()
    return dict(row) if row else None


def save_entry(
    word: str,
    *,
    pos: str = "",
    definition: str = "",
    translation: str = "",
    situation: str = "",
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
    """
    with closing(_conn()) as conn, conn:
        now = _now()
        cursor = conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, situation, generator_version, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "pos = excluded.pos, "
            "definition = excluded.definition, "
            "translation = excluded.translation, "
            "situation = excluded.situation, "
            "generator_version = excluded.generator_version, "
            "updated_at = excluded.updated_at",
            (
                word,
                pos,
                definition,
                translation,
                situation,
                generator_version,
                now,
                now,
            ),
        )
        return cursor.rowcount > 0


_ENTRY_COLUMNS = (
    "word, pos, definition, translation, situation, generator_version, "
    "created_at, updated_at"
)


def list_entries() -> list[dict]:
    """Todas las entradas globales de `dictionary_entries` (sin `user_id`).

    V3.33 (eslabón Recognition del puente): la caché global es el único
    contenido de significado del diccionario, así que el helper de MCQ la usa
    como banco de textos de significado candidatos a distractor. Sin filtro de
    `generator_version`: aunque una entrada quede obsoleta por un cambio de
    política del generador, su significado real sigue sirviendo de distractor
    para el reconocimiento. Orden estable por `word` (determinista).
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM dictionary_entries ORDER BY word"
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# V3.39 (diccionario reversible): caché ES→EN. Tabla propia y aislada de
# `dictionary_entries` para no contaminar el banco de distractores del MCQ
# (ver `repositories/db.py`). Misma política de versionado que la directa: el
# dominio solo sirve caché cuya `generator_version` coincide con la actual.
# ---------------------------------------------------------------------------

_REVERSE_COLUMNS = (
    "word, english, pos, definition, situation, generator_version, "
    "created_at, updated_at"
)


def get_reverse_entry(word: str) -> dict | None:
    """Entrada ES→EN cacheada de `word` (None si no existe).

    `word` es el término ESPAÑOL ya normalizado (sin acentos plegados: la
    normalización conserva la eñe). Devuelve `english` (traducción principal) y
    el contenido inglés asociado (`pos`/`definition`/`situation`).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_REVERSE_COLUMNS} FROM dictionary_reverse_entries "
            "WHERE word = ?",
            (word,),
        ).fetchone()
    return dict(row) if row else None


def save_reverse_entry(
    word: str,
    *,
    english: str = "",
    pos: str = "",
    definition: str = "",
    situation: str = "",
    generator_version: str = "",
) -> bool:
    """Inserta o sobrescribe la entrada ES→EN de `word` (V3.39).

    Mismo `INSERT ... ON CONFLICT(word) DO UPDATE` que `save_entry`: sirve tanto
    para la primera generación como para regenerar contenido obsoleto. Devuelve
    True si hubo escritura. Contenido GLOBAL (sin `user_id`).
    """
    with closing(_conn()) as conn, conn:
        now = _now()
        cursor = conn.execute(
            "INSERT INTO dictionary_reverse_entries "
            "(word, english, pos, definition, situation, generator_version, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "english = excluded.english, "
            "pos = excluded.pos, "
            "definition = excluded.definition, "
            "situation = excluded.situation, "
            "generator_version = excluded.generator_version, "
            "updated_at = excluded.updated_at",
            (
                word,
                english,
                pos,
                definition,
                situation,
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
    return [dict(row) for row in rows]

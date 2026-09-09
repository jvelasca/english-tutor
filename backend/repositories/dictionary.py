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
    válida con la política actual (V3.30.1, P1-03).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT word, pos, definition, translation, generator_version, "
            "created_at, updated_at "
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
    generator_version: str = "",
) -> bool:
    """Inserta o sobrescribe la entrada de diccionario de `word` (V3.30.1).

    `INSERT ... ON CONFLICT(word) DO UPDATE`: escribe UNA fila tanto si la
    palabra es nueva (primera generación) como si ya existía con una
    `generator_version` obsoleta (regeneración controlada). `updated_at` se
    actualiza en cada escritura y `created_at` solo en la inserción inicial.
    Devuelve True si hubo operación de escritura (fila insertada o
    actualizada); el contenido es global (sin `user_id`).
    """
    with closing(_conn()) as conn, conn:
        now = _now()
        cursor = conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, generator_version, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "pos = excluded.pos, "
            "definition = excluded.definition, "
            "translation = excluded.translation, "
            "generator_version = excluded.generator_version, "
            "updated_at = excluded.updated_at",
            (word, pos, definition, translation, generator_version, now, now),
        )
        return cursor.rowcount > 0

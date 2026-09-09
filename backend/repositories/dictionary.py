"""Caché persistente del contenido del diccionario de consulta (V3.30, D1).

Tabla global `dictionary_entries` (sin `user_id`): la definición/traducción de
una palabra es contenido de idioma, no evidencia de un alumno, así que una vez
generada (Fase B, modelo local) cualquier usuario la lee sin volver a pagar la
latencia del modelo.

Fase A solo necesita la LECTURA (`get_entry`) para cablear el flujo del endpoint:
`definition_source="llm"` si hay definición cacheada, `"none"` en otro caso. La
escritura idempotente (`INSERT OR IGNORE`) llega con el generador en Fase B.

Este repositorio nunca registra evidencia del alumno ni toca
`vocabulary`/`vocabulary_events` (decisión D3: la consulta es solo lectura).
"""

from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now


def get_entry(word: str) -> dict | None:
    """Devuelve la entrada de diccionario cacheada de `word` (None si no existe).

    `word` debe venir ya normalizada (minúsculas, sin puntuación circundante).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT word, pos, definition, translation, created_at, updated_at "
            "FROM dictionary_entries WHERE word = ?",
            (word,),
        ).fetchone()
    return dict(row) if row else None


def insert_entry(
    word: str,
    *,
    pos: str = "",
    definition: str = "",
    translation: str = "",
) -> bool:
    """Inserta una entrada de diccionario de forma idempotente (V3.30, Fase B).

    `INSERT OR IGNORE`: si la palabra ya tiene contenido (carrera de dos
    consultas simultáneas o reintento), no la sobreescribe. Devuelve True si se
    insertó una fila nueva y False si ya existía. `created_at` usa el reloj
    local del repositorio (`repositories.db._now`).
    """
    with closing(_conn()) as conn, conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO dictionary_entries "
            "(word, pos, definition, translation, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, '')",
            (word, pos, definition, translation, _now()),
        )
        return cursor.rowcount > 0

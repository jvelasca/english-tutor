"""Repositorio de vocabulario (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def _day(iso: str) -> str:
    """Parte `YYYY-MM-DD` de una marca de tiempo ISO-8601."""
    return iso[:10]


def record_words(user_id: str, words: list[str]) -> bool:
    """Registra producción del alumno (upsert). Incrementa `appearances` y, si la
    producción ocurre en un día distinto al último, `production_days`.

    Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    now = _now()
    today = _day(now)
    with closing(_conn()) as conn, conn:
        for w in words:
            row = conn.execute(
                "SELECT last_seen FROM vocabulary WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            prior = row["last_seen"] if row else ""
            new_day = 1 if not prior or _day(prior) != today else 0
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, appearances, first_seen, last_seen, production_days) "
                "VALUES (?, ?, 1, ?, ?, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "appearances = vocabulary.appearances + 1, "
                "first_seen = CASE WHEN vocabulary.first_seen = '' "
                "THEN excluded.first_seen ELSE vocabulary.first_seen END, "
                "last_seen = excluded.last_seen, "
                "production_days = vocabulary.production_days "
                "+ excluded.production_days",
                (user_id, w, now, now, new_day),
            )
    return True


def record_exposures(user_id: str, words: list[str]) -> bool:
    """Registra exposición (palabras de la respuesta del tutor). Upsert que crea la
    fila con `appearances = 0` si el alumno aún no ha producido la palabra.

    Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO vocabulary "
            "(user_id, word, appearances, first_seen, last_seen, "
            "exposures, last_exposed_at, production_days) "
            "VALUES (?, ?, 0, '', '', 1, ?, 0) "
            "ON CONFLICT(user_id, word) DO UPDATE SET "
            "exposures = vocabulary.exposures + 1, "
            "last_exposed_at = excluded.last_exposed_at",
            [(user_id, w, now) for w in words],
        )
    return True


def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario ordenado por producción (desc) y
    palabra (asc). Incluye métricas de exposición y espaciado, y el contexto
    curricular del ítem léxico (V2.3)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, appearances, first_seen, last_seen, "
            "exposures, last_exposed_at, production_days, "
            "cefr, level_id, objective_id, source, lemma, kind FROM vocabulary "
            "WHERE user_id = ? ORDER BY appearances DESC, word ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def seed_curriculum_items(user_id: str, items: list[dict]) -> bool:
    """Siembra ítems léxicos del currículo sin tocar producción/input (V2.3).

    `items` es una lista de dicts `{word, lemma, cefr, level_id, objective_id,
    kind}`. Crea la fila si no existe (con `appearances=0`/`exposures=0`) o
    rellena el contexto curricular si ya existía. Nunca incrementa `appearances`
    ni `exposures`: solo fija el contexto, para no contaminar las métricas de
    producción/lectura del alumno. Devuelve False si el usuario no existe.
    """
    if get_user(user_id) is None:
        return False
    if not items:
        return True
    with closing(_conn()) as conn, conn:
        for it in items:
            word = it["word"]
            row = conn.execute(
                "SELECT word FROM vocabulary WHERE user_id = ? AND word = ?",
                (user_id, word),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO vocabulary "
                    "(user_id, word, appearances, first_seen, last_seen, "
                    "exposures, last_exposed_at, production_days, "
                    "cefr, level_id, objective_id, source, lemma, kind) "
                    "VALUES (?, ?, 0, '', '', 0, '', 0, ?, ?, ?, 'curriculum', ?, ?)",
                    (
                        user_id,
                        word,
                        it.get("cefr", ""),
                        it.get("level_id", ""),
                        it.get("objective_id", ""),
                        it.get("lemma", word),
                        it.get("kind", "word"),
                    ),
                )
            else:
                conn.execute(
                    "UPDATE vocabulary SET "
                    "cefr = CASE WHEN cefr = '' THEN ? ELSE cefr END, "
                    "level_id = CASE WHEN level_id = '' THEN ? ELSE level_id END, "
                    "objective_id = CASE WHEN objective_id = '' "
                    "THEN ? ELSE objective_id END, "
                    "source = CASE WHEN source = 'user' THEN 'curriculum' "
                    "ELSE source END, "
                    "lemma = CASE WHEN lemma = '' THEN ? ELSE lemma END, "
                    "kind = CASE WHEN kind IN ('word', 'structure') THEN ? "
                    "ELSE kind END "
                    "WHERE user_id = ? AND word = ?",
                    (
                        it.get("cefr", ""),
                        it.get("level_id", ""),
                        it.get("objective_id", ""),
                        it.get("lemma", word),
                        it.get("kind", "word"),
                        user_id,
                        word,
                    ),
                )
    return True

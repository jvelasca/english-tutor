"""Flashcards (V3.78.0): mazos manuales, tarjetas y ledger de revisiones.

Este módulo es **acceso a datos, sin lógica de negocio** (misma convención que
`repositories/collections.py`): valida la existencia del usuario para que la FK
no sea la que falle, pero quien decide qué es un mazo, qué límites aplican y qué
tarjeta toca es `domain/flashcards.py`.

Dos ideas que conviene tener presentes al leerlo:

1. **El mazo automático no tiene fila.** Es virtual (`AUTO_DECK_ID = 0`) y se
   sintetiza desde el léxico del alumno. Si fuera una fila habría que sembrarla,
   protegerla del borrado y migrarla; siendo virtual, no hay nada de eso.
2. **El ledger `flashcard_reviews` es la fuente de los límites y las
   estadísticas.** Se escribe una fila por calificación, incluidas las
   repeticiones de una misma tarjeta el mismo día, porque eso es exactamente lo
   que Anki cuenta como «repaso».
"""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user

#: Id del mazo automático (todo el léxico). No existe como fila.
AUTO_DECK_ID = 0

DEFAULT_NEW_PER_DAY = 10
DEFAULT_REVIEW_PER_DAY = 50

#: Tope defensivo de los límites por mazo (una sesión no es un atracón).
MAX_PER_DAY = 9_999


def _clamp_limit(value: int | None, default: int) -> int:
    if value is None:
        return default
    return max(0, min(int(value), MAX_PER_DAY))


def _deck_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "name": str(row["name"] or ""),
        "new_per_day": int(row["new_per_day"] or 0),
        "review_per_day": int(row["review_per_day"] or 0),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def _card_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "deck_id": int(row["deck_id"]),
        "front": str(row["front"] or ""),
        "back": str(row["back"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


# --- Mazos -----------------------------------------------------------------


def list_decks(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, name, new_per_day, review_per_day, created_at, updated_at "
            "FROM flashcard_decks WHERE user_id = ? ORDER BY name COLLATE NOCASE",
            (user_id,),
        ).fetchall()
    return [_deck_row(r) for r in rows]


def get_deck(user_id: str, deck_id: int) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, name, new_per_day, review_per_day, created_at, updated_at "
            "FROM flashcard_decks WHERE user_id = ? AND id = ?",
            (user_id, int(deck_id)),
        ).fetchone()
    return _deck_row(row) if row is not None else None


def create_deck(
    user_id: str,
    *,
    name: str,
    new_per_day: int | None = None,
    review_per_day: int | None = None,
) -> dict | None:
    """Crea un mazo. `None` si el usuario no existe o el nombre está vacío."""
    if get_user(user_id) is None:
        return None
    clean = " ".join((name or "").split())
    if not clean:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO flashcard_decks "
            "(user_id, name, new_per_day, review_per_day, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                clean,
                _clamp_limit(new_per_day, DEFAULT_NEW_PER_DAY),
                _clamp_limit(review_per_day, DEFAULT_REVIEW_PER_DAY),
                now,
                now,
            ),
        )
        if not cur.rowcount:
            # Nombre repetido: `UNIQUE (user_id, name)` lo rechaza.
            return None
        deck_id = int(cur.lastrowid)
    return get_deck(user_id, deck_id)


def update_deck(
    user_id: str,
    deck_id: int,
    *,
    name: str | None = None,
    new_per_day: int | None = None,
    review_per_day: int | None = None,
) -> dict | None:
    current = get_deck(user_id, deck_id)
    if current is None:
        return None
    clean = current["name"] if name is None else " ".join((name or "").split())
    if not clean:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE flashcard_decks "
            "SET name = ?, new_per_day = ?, review_per_day = ?, updated_at = ? "
            "WHERE user_id = ? AND id = ?",
            (
                clean,
                _clamp_limit(new_per_day, current["new_per_day"]),
                _clamp_limit(review_per_day, current["review_per_day"]),
                _now(),
                user_id,
                int(deck_id),
            ),
        )
    return get_deck(user_id, deck_id)


def delete_deck(user_id: str, deck_id: int) -> bool:
    """Borra el mazo y sus tarjetas. `False` si no era del usuario."""
    if get_deck(user_id, deck_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "DELETE FROM flashcard_cards WHERE user_id = ? AND deck_id = ?",
            (user_id, int(deck_id)),
        )
        conn.execute(
            "DELETE FROM flashcard_decks WHERE user_id = ? AND id = ?",
            (user_id, int(deck_id)),
        )
    return True


def count_cards(user_id: str) -> dict[int, int]:
    """Tarjetas por mazo (`{deck_id: n}`) en una sola consulta."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT deck_id, COUNT(*) AS n FROM flashcard_cards "
            "WHERE user_id = ? GROUP BY deck_id",
            (user_id,),
        ).fetchall()
    return {int(r["deck_id"]): int(r["n"]) for r in rows}


# --- Tarjetas --------------------------------------------------------------


def list_cards(user_id: str, deck_id: int) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, deck_id, front, back, created_at, updated_at "
            "FROM flashcard_cards WHERE user_id = ? AND deck_id = ? "
            "ORDER BY id",
            (user_id, int(deck_id)),
        ).fetchall()
    return [_card_row(r) for r in rows]


def get_card(user_id: str, card_id: int) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, deck_id, front, back, created_at, updated_at "
            "FROM flashcard_cards WHERE user_id = ? AND id = ?",
            (user_id, int(card_id)),
        ).fetchone()
    return _card_row(row) if row is not None else None


def create_card(
    user_id: str, deck_id: int, *, front: str, back: str = ""
) -> dict | None:
    """Añade una tarjeta a un mazo del usuario. `None` si el mazo no es suyo."""
    if get_deck(user_id, deck_id) is None:
        return None
    clean_front = " ".join((front or "").split())
    if not clean_front:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO flashcard_cards "
            "(user_id, deck_id, front, back, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                int(deck_id),
                clean_front,
                (back or "").strip(),
                now,
                now,
            ),
        )
        card_id = int(cur.lastrowid)
    return get_card(user_id, card_id)


def update_card(
    user_id: str, card_id: int, *, front: str, back: str
) -> dict | None:
    current = get_card(user_id, card_id)
    if current is None:
        return None
    clean_front = " ".join((front or "").split())
    if not clean_front:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE flashcard_cards SET front = ?, back = ?, updated_at = ? "
            "WHERE user_id = ? AND id = ?",
            (clean_front, (back or "").strip(), _now(), user_id, int(card_id)),
        )
    return get_card(user_id, card_id)


def delete_card(user_id: str, card_id: int) -> dict | None:
    """Borra una tarjeta y devuelve la fila borrada (para limpiar su carta FSRS)."""
    current = get_card(user_id, card_id)
    if current is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "DELETE FROM flashcard_cards WHERE user_id = ? AND id = ?",
            (user_id, int(card_id)),
        )
    return current


def count_deck_cards(user_id: str, deck_id: int) -> int:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM flashcard_cards "
            "WHERE user_id = ? AND deck_id = ?",
            (user_id, int(deck_id)),
        ).fetchone()
    return int(row["n"] or 0)


# --- Ledger de revisiones --------------------------------------------------


def record_review(
    user_id: str,
    *,
    deck_id: int,
    card_type: str,
    card_id: str,
    grade: int,
    was_new: bool,
) -> None:
    """Una fila por calificación. No lanza si el usuario no existe (best-effort)."""
    if get_user(user_id) is None:
        return
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO flashcard_reviews "
            "(user_id, deck_id, card_type, card_id, grade, was_new, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                int(deck_id),
                str(card_type),
                str(card_id),
                int(grade),
                1 if was_new else 0,
                _now(),
            ),
        )


def day_state(user_id: str, day_prefix: str, deck_id: int) -> dict:
    """Estado del día para un mazo, en UNA consulta.

    Devuelve `{"reviews": n, "new": n, "seen": {(card_type, card_id), …}}`.

    Es lo que aplica los dos límites de Anki:
    - `reviews` → cuántos repasos se han hecho hoy (cada repetición cuenta, que
      es justo lo que un `COUNT(DISTINCT card_id)` no vería);
    - `new` → cuántas tarjetas se han calificado por **primera** vez hoy, leído
      del flag `was_new` y no de `last_review_at`, que se pisa en cada repaso.
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS reviews, "
            "SUM(CASE WHEN was_new = 1 THEN 1 ELSE 0 END) AS fresh "
            "FROM flashcard_reviews "
            "WHERE user_id = ? AND deck_id = ? AND created_at LIKE ?",
            (user_id, int(deck_id), f"{day_prefix}%"),
        ).fetchone()
        rows = conn.execute(
            "SELECT DISTINCT card_type, card_id FROM flashcard_reviews "
            "WHERE user_id = ? AND deck_id = ? AND created_at LIKE ?",
            (user_id, int(deck_id), f"{day_prefix}%"),
        ).fetchall()
    return {
        "reviews": int(row["reviews"] or 0),
        "new": int(row["fresh"] or 0),
        "seen": {(str(r["card_type"]), str(r["card_id"])) for r in rows},
    }


def reviews_by_day(user_id: str, *, since_prefix: str) -> dict[str, dict[str, int]]:
    """`{YYYY-MM-DD: {"total": n, "good": n}}` desde `since_prefix` (inclusive)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN grade >= 3 THEN 1 ELSE 0 END) AS good "
            "FROM flashcard_reviews "
            "WHERE user_id = ? AND created_at >= ? "
            "GROUP BY day ORDER BY day",
            (user_id, since_prefix),
        ).fetchall()
    return {
        str(r["day"]): {"total": int(r["total"] or 0), "good": int(r["good"] or 0)}
        for r in rows
    }


def review_totals(user_id: str, *, since_iso: str) -> dict:
    """Totales y acierto (`good`+`easy`) desde `since_iso`. Sin filas → ceros."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN grade >= 3 THEN 1 ELSE 0 END) AS good, "
            "SUM(CASE WHEN was_new = 1 THEN 1 ELSE 0 END) AS new_cards "
            "FROM flashcard_reviews WHERE user_id = ? AND created_at >= ?",
            (user_id, since_iso),
        ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "good": int(row["good"] or 0),
        "new_cards": int(row["new_cards"] or 0),
    }


def studied_cards(user_id: str) -> set[tuple[str, str]]:
    """Pares `(card_type, card_id)` que el alumno YA ha calificado alguna vez.

    Es la definición de NUEVA que usa el modo Flashcards: «nunca la he
    trabajado aquí», que es exactamente lo que cuenta Anki y lo que el alumno
    entiende por nueva.

    No se usa `reps == 0` del scheduler porque no significa lo mismo: la
    siembra de retención (`sync_fsrs_cards`) marca `reps = 1` en las cartas que
    deriva de la evidencia de las lecciones, así que una palabra que el alumno
    nunca ha repasado puede llegar con `reps = 1` y, si se clasificara por él,
    ni contaría para el tope de nuevas ni aparecería como nueva. El ledger sí lo
    sabe porque solo lo escribe una calificación de verdad.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT card_type, card_id FROM flashcard_reviews "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {(str(r["card_type"]), str(r["card_id"])) for r in rows}

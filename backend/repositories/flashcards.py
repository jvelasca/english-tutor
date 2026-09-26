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

from repositories.db import _conn, _now, front_key
from repositories.users import get_user

#: Id del mazo automático (todo el léxico). No existe como fila.
AUTO_DECK_ID = 0

DEFAULT_NEW_PER_DAY = 10
DEFAULT_REVIEW_PER_DAY = 50

#: Tope defensivo de los límites por mazo (una sesión no es un atracón).
MAX_PER_DAY = 9_999


class CardFrontConflictError(Exception):
    """El anverso nuevo ya es de OTRA ficha del mismo alumno (V3.86.1).

    La identidad fuerte (`UNIQUE (user_id, front_key)`) convierte lo que era una
    duplicación silenciosa en un conflicto declarado: editar el anverso de una
    ficha hasta el de otra no crea una gemela, avisa. El router lo traduce a 409.
    """

    def __init__(self, existing_card_id: int) -> None:
        super().__init__(existing_card_id)
        self.existing_card_id = int(existing_card_id)


class NoValidDecksError(Exception):
    """Ninguno de los mazos declarados existe o es del alumno (V3.86.1).

    En el PATCH atómico esto aborta la transacción ENTERA: si los mazos no son
    válidos no se escribe tampoco el resto de la ficha.
    """


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
        "mnemonic": str(row["mnemonic"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


#: Columnas de una ficha en cualquier SELECT (V3.86.0: incluye `mnemonic`).
_CARD_COLUMNS = "id, deck_id, front, back, mnemonic, created_at, updated_at"


def _find_card_by_front(conn, user_id: str, front: str) -> dict | None:
    """Ficha EXISTENTE del alumno con el mismo anverso, dentro de una transacción.

    V3.86.0: una misma palabra no debe generar una segunda ficha por el hecho de
    entrar en otro mazo —eso es justo lo que la tabla puente existe para
    evitar—, así que el alta REUTILIZA la ficha y solo añade la pertenencia.

    V3.86.1: la búsqueda va por `front_key` (la columna con índice ÚNICO), no por
    un escaneo en Python. `front_key` se importa de `repositories.db` porque es
    la MISMA política que usa la migración para construir el índice.
    """
    needle = front_key(front)
    if not needle:
        return None
    row = conn.execute(
        f"SELECT {_CARD_COLUMNS} FROM flashcard_cards "
        "WHERE user_id = ? AND front_key = ?",
        (user_id, needle),
    ).fetchone()
    return _card_row(row) if row is not None else None


def _card_cols(alias: str = "") -> str:
    """Columnas de ficha con prefijo de tabla (`c.id, c.deck_id, …`)."""
    prefix = f"{alias}." if alias else ""
    return ", ".join(f"{prefix}{column.strip()}" for column in _CARD_COLUMNS.split(","))


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


def delete_deck(user_id: str, deck_id: int) -> dict | None:
    """Borra un mazo manual respetando las fichas COMPARTIDAS (V3.86.0).

    Devuelve `{"deleted_card_ids": [...], "shared": n}` o `None` si el mazo no
    era del usuario. Una ficha que solo vivía en este mazo se borra (y su id sale
    en `deleted_card_ids` para que el dominio limpie su carta FSRS); una ficha
    que también está en otro mazo SOBREVIVE, solo pierde esta pertenencia (y si
    apuntaba aquí por la columna deprecada `deck_id`, se repunta a uno de los
    mazos que le quedan: la FK no admite un mazo que desaparece). Todo en UNA
    transacción: no queda estado a medias.
    """
    if get_deck(user_id, deck_id) is None:
        return None
    with closing(_conn()) as conn, conn:
        rows = conn.execute(
            f"SELECT {_card_cols('c')} "
            "FROM flashcard_cards c "
            "JOIN flashcard_deck_cards dc ON dc.card_id = c.id "
            "WHERE c.user_id = ? AND dc.deck_id = ? "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM flashcard_deck_cards other "
            "  WHERE other.card_id = c.id AND other.deck_id <> ?"
            ")",
            (user_id, int(deck_id), int(deck_id)),
        ).fetchall()
        deleted_ids = [int(r["id"]) for r in rows]
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM flashcard_deck_cards WHERE deck_id = ?",
            (int(deck_id),),
        ).fetchone()["n"]
        conn.execute(
            "DELETE FROM flashcard_deck_cards WHERE deck_id = ?", (int(deck_id),)
        )
        # La columna deprecada `deck_id` (el «mazo principal») NO puede quedarse
        # apuntando a un mazo que desaparece: la FK lo impediría. Las fichas
        # COMPARTIDAS que lo tenían aquí se repuntan a uno de los mazos que les
        # quedan (el menor por id, para que sea determinista).
        conn.execute(
            "UPDATE flashcard_cards SET deck_id = ("
            "  SELECT MIN(dc.deck_id) FROM flashcard_deck_cards dc "
            "  WHERE dc.card_id = flashcard_cards.id"
            ") WHERE user_id = ? AND deck_id = ? "
            "AND EXISTS (SELECT 1 FROM flashcard_deck_cards dc "
            "            WHERE dc.card_id = flashcard_cards.id)",
            (user_id, int(deck_id)),
        )
        if deleted_ids:
            placeholders = ",".join("?" for _ in deleted_ids)
            conn.execute(
                f"DELETE FROM flashcard_cards WHERE id IN ({placeholders})",
                deleted_ids,
            )
        conn.execute(
            "DELETE FROM flashcard_decks WHERE user_id = ? AND id = ?",
            (user_id, int(deck_id)),
        )
    return {
        "deleted_card_ids": deleted_ids,
        "shared": max(0, int(total or 0) - len(deleted_ids)),
    }


def count_cards(user_id: str) -> dict[int, int]:
    """Fichas por mazo (`{deck_id: n}`) leyendo la tabla puente (V3.86.0).

    Una ficha en dos mazos cuenta en LOS DOS: es lo que el alumno ve al mirar el
    mazo. Sin duplicar filas de ficha.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT dc.deck_id, COUNT(*) AS n "
            "FROM flashcard_deck_cards dc "
            "JOIN flashcard_cards c ON c.id = dc.card_id "
            "WHERE c.user_id = ? GROUP BY dc.deck_id",
            (user_id,),
        ).fetchall()
    return {int(r["deck_id"]): int(r["n"]) for r in rows}


# --- Tarjetas --------------------------------------------------------------


def list_cards(user_id: str, deck_id: int) -> list[dict]:
    """Fichas de un mazo por la tabla puente (una ficha compartida aparece en
    cada uno de sus mazos, pero una sola vez por mazo)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_card_cols('c')} "
            "FROM flashcard_cards c "
            "JOIN flashcard_deck_cards dc ON dc.card_id = c.id "
            "WHERE c.user_id = ? AND dc.deck_id = ? "
            "ORDER BY c.id",
            (user_id, int(deck_id)),
        ).fetchall()
    return [_card_row(r) for r in rows]


def list_all_cards(user_id: str) -> list[dict]:
    """Todas las fichas del alumno, sin importar el mazo (V3.86.0)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_CARD_COLUMNS} FROM flashcard_cards "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [_card_row(r) for r in rows]


def get_card(user_id: str, card_id: int) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_CARD_COLUMNS} FROM flashcard_cards "
            "WHERE user_id = ? AND id = ?",
            (user_id, int(card_id)),
        ).fetchone()
    return _card_row(row) if row is not None else None


def decks_for_card(user_id: str, card_id: int) -> list[int]:
    """Ids de los mazos a los que pertenece una ficha (orden ascendente)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT dc.deck_id FROM flashcard_deck_cards dc "
            "JOIN flashcard_cards c ON c.id = dc.card_id "
            "WHERE c.user_id = ? AND dc.card_id = ? ORDER BY dc.deck_id",
            (user_id, int(card_id)),
        ).fetchall()
    return [int(r["deck_id"]) for r in rows]


def deck_ids_for_cards(user_id: str, card_ids: list[int]) -> dict[int, list[int]]:
    """`{card_id: [deck_id, …]}` en UNA consulta (evita N+1 al listar)."""
    ids = [int(cid) for cid in card_ids]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT dc.card_id, dc.deck_id FROM flashcard_deck_cards dc "
            "JOIN flashcard_cards c ON c.id = dc.card_id "
            f"WHERE c.user_id = ? AND dc.card_id IN ({placeholders}) "
            "ORDER BY dc.card_id, dc.deck_id",
            (user_id, *ids),
        ).fetchall()
    out: dict[int, list[int]] = {cid: [] for cid in ids}
    for row in rows:
        out[int(row["card_id"])].append(int(row["deck_id"]))
    return out


def _owned_deck_ids_in(conn, user_id: str, deck_ids: list[int]) -> list[int]:
    """Filtra y ordena ids de mazo del usuario usando una conexión YA abierta.

    Es la pieza que permite validar los mazos DENTRO de la transacción del PATCH
    atómico: abrir otra conexión ahí sería un interbloqueo de escritura y, sobre
    todo, dejaría una ventana entre «validar» y «escribir».
    """
    unique: list[int] = []
    for raw in deck_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value not in unique:
            unique.append(value)
    if not unique:
        return []
    placeholders = ",".join("?" for _ in unique)
    rows = conn.execute(
        f"SELECT id FROM flashcard_decks WHERE user_id = ? "
        f"AND id IN ({placeholders}) ORDER BY id",
        (user_id, *unique),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def _owned_deck_ids(user_id: str, deck_ids: list[int]) -> list[int]:
    """Igual que `_owned_deck_ids_in`, con su propia conexión de solo lectura."""
    with closing(_conn()) as conn:
        return _owned_deck_ids_in(conn, user_id, deck_ids)


def set_card_decks(user_id: str, card_id: int, deck_ids: list[int]) -> list[int] | None:
    """Reemplaza los mazos de una ficha en UNA transacción (V3.86.0).

    Devuelve la lista final de ids o `None` si la ficha no es del usuario o no
    queda ningún mazo válido. Una ficha SIEMPRE pertenece al menos a un mazo: el
    FK `deck_id` (deprecado) exige un mazo real y no hay «ficha sin mazo».
    """
    if get_card(user_id, card_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        owned = _owned_deck_ids_in(conn, user_id, deck_ids)
        if not owned:
            return None
        conn.execute(
            "DELETE FROM flashcard_deck_cards WHERE card_id = ?", (int(card_id),)
        )
        conn.executemany(
            "INSERT OR IGNORE INTO flashcard_deck_cards "
            "(card_id, deck_id, created_at) VALUES (?, ?, ?)",
            [(int(card_id), deck_id, now) for deck_id in owned],
        )
        # El FK deprecado se mantiene como «mazo principal» (el primero del
        # conjunto) para que el esquema viejo siga siendo coherente.
        conn.execute(
            "UPDATE flashcard_cards SET deck_id = ?, updated_at = ? "
            "WHERE user_id = ? AND id = ?",
            (owned[0], now, user_id, int(card_id)),
        )
    return owned


def add_card_to_deck(user_id: str, card_id: int, deck_id: int) -> list[int] | None:
    """Añade una pertenencia sin tocar las demás. `None` si algo no es suyo."""
    if get_card(user_id, card_id) is None:
        return None
    if not _owned_deck_ids(user_id, [deck_id]):
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO flashcard_deck_cards "
            "(card_id, deck_id, created_at) VALUES (?, ?, ?)",
            (int(card_id), int(deck_id), _now()),
        )
    return decks_for_card(user_id, card_id)


def remove_card_from_deck(
    user_id: str, card_id: int, deck_id: int
) -> list[int] | None:
    """Quita una pertenencia. `None` si la ficha no es del usuario.

    Devuelve la lista de mazos que le QUEDAN (posiblemente vacía: el dominio
    decide qué hacer con una ficha sin mazo). Si el mazo no pertenecía a la
    ficha, es un no-op silencioso.
    """
    if get_card(user_id, card_id) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "DELETE FROM flashcard_deck_cards WHERE card_id = ? AND deck_id = ?",
            (int(card_id), int(deck_id)),
        )
        remaining = [
            int(r["deck_id"])
            for r in conn.execute(
                "SELECT deck_id FROM flashcard_deck_cards WHERE card_id = ? "
                "ORDER BY deck_id",
                (int(card_id),),
            ).fetchall()
        ]
        # El «mazo principal» deprecado se mantiene coherente con el conjunto.
        if remaining:
            conn.execute(
                "UPDATE flashcard_cards SET deck_id = ?, updated_at = ? "
                "WHERE user_id = ? AND id = ?",
                (remaining[0], _now(), user_id, int(card_id)),
            )
    return remaining


def create_card(
    user_id: str,
    deck_id: int | None = None,
    *,
    front: str,
    back: str = "",
    mnemonic: str = "",
    deck_ids: list[int] | None = None,
) -> dict | None:
    """Crea una ficha y la asocia a uno o varios mazos (V3.86.0).

    Acepta `deck_ids` (nuevo contrato, 1..N mazos) o `deck_id` (contrato antiguo
    de un solo mazo) por retrocompatibilidad. `None` si no hay ningún mazo
    válido del usuario o el anverso queda vacío.

    Regla de no duplicar: si el alumno YA tiene una ficha con el mismo anverso
    (espacios colapsados, `casefold()`), no se crea otra: se reutiliza, se añaden
    las pertenencias que falten y se actualizan los campos que llegan **no
    vacíos** (un campo vacío no borra lo que ya había; para borrar el recordatorio
    está el `PATCH` explícito).
    """
    if deck_ids:
        requested = list(deck_ids)
    else:
        requested = [deck_id] if deck_id is not None else []
    owned = _owned_deck_ids(user_id, requested)
    if not owned:
        return None
    clean_front = " ".join((front or "").split())
    if not clean_front:
        return None
    key = front_key(clean_front)
    now = _now()
    clean_back = (back or "").strip()
    clean_mnemonic = (mnemonic or "").strip()
    with closing(_conn()) as conn, conn:
        existing = _find_card_by_front(conn, user_id, clean_front)
        inserted = False
        if existing is not None:
            card_id = int(existing["id"])
        else:
            cur = conn.execute(
                "INSERT INTO flashcard_cards "
                "(user_id, deck_id, front, front_key, back, mnemonic, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                # La identidad fuerte la garantiza la BD: si otra petición ganó
                # la carrera entre el SELECT y el INSERT, esta no falla ni
                # duplica; justo debajo se reutiliza la que entró.
                "ON CONFLICT(user_id, front_key) DO NOTHING",
                (
                    user_id,
                    owned[0],
                    clean_front,
                    key,
                    clean_back,
                    clean_mnemonic,
                    now,
                    now,
                ),
            )
            if cur.rowcount:
                card_id = int(cur.lastrowid)
                inserted = True
            else:
                raced = _find_card_by_front(conn, user_id, clean_front)
                if raced is None:  # imposible salvo corrupción de la BD
                    return None
                card_id = int(raced["id"])
                existing = raced
        # Un campo VACÍO no borra lo que ya había (para borrar el recordatorio
        # está el PATCH explícito); una ficha recién insertada ya trae sus valores.
        if not inserted and (clean_back or clean_mnemonic):
            conn.execute(
                "UPDATE flashcard_cards SET back = ?, mnemonic = ?, "
                "updated_at = ? WHERE user_id = ? AND id = ?",
                (
                    clean_back or existing["back"],
                    clean_mnemonic or existing["mnemonic"],
                    now,
                    user_id,
                    card_id,
                ),
            )
        conn.executemany(
            "INSERT OR IGNORE INTO flashcard_deck_cards "
            "(card_id, deck_id, created_at) VALUES (?, ?, ?)",
            [(card_id, deck_id, now) for deck_id in owned],
        )
    return get_card(user_id, card_id)


def create_cards(
    user_id: str, deck_id: int, cards: list[dict]
) -> list[dict]:
    """Alta masiva de tarjetas en un mazo: UNA transacción para todas (V3.80.0).

    Pegar una lista de 40 tarjetas con `create_card` en bucle abriría 40
    conexiones y 40 transacciones —el mismo defecto que V3.77.2 cerró para el
    léxico—, así que el pegado masivo escribe en bloque. Devuelve las filas
    creadas para que la pantalla pueda decir cuántas entraron de verdad y no
    cuántas se intentaron.

    No deduplica: eso es política de producto y vive en el dominio (junto con el
    tope). Aquí solo se escribe lo que llega, y se ignoran las entradas sin
    anverso. V3.86.0: cada ficha entra también en la tabla puente y acepta
    `mnemonic`.
    """
    if get_deck(user_id, deck_id) is None:
        return []
    now = _now()
    created: list[dict] = []
    with closing(_conn()) as conn, conn:
        for raw in cards:
            clean_front = " ".join(str(raw.get("front") or "").split())
            if not clean_front:
                continue
            clean_back = str(raw.get("back") or "").strip()
            clean_mnemonic = str(raw.get("mnemonic") or "").strip()
            # V3.86.1: el pegado respeta la identidad fuerte. Si el anverso ya era
            # una ficha del alumno NO se duplica: se le añade este mazo (y se
            # completan reverso/recordatorio si llegan). `added` sigue contando lo
            # que entró en el mazo, que es lo que la UI promete.
            existing = _find_card_by_front(conn, user_id, clean_front)
            inserted = False
            if existing is not None:
                card_id = int(existing["id"])
            else:
                cur = conn.execute(
                    "INSERT INTO flashcard_cards "
                    "(user_id, deck_id, front, front_key, back, mnemonic, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(user_id, front_key) DO NOTHING",
                    (
                        user_id,
                        int(deck_id),
                        clean_front,
                        front_key(clean_front),
                        clean_back,
                        clean_mnemonic,
                        now,
                        now,
                    ),
                )
                if cur.rowcount:
                    card_id = int(cur.lastrowid)
                    inserted = True
                else:
                    raced = _find_card_by_front(conn, user_id, clean_front)
                    if raced is None:  # imposible salvo corrupción de la BD
                        continue
                    card_id = int(raced["id"])
                    existing = raced
            if not inserted and (clean_back or clean_mnemonic):
                conn.execute(
                    "UPDATE flashcard_cards SET back = ?, mnemonic = ?, "
                    "updated_at = ? WHERE user_id = ? AND id = ?",
                    (
                        clean_back or existing["back"],
                        clean_mnemonic or existing["mnemonic"],
                        now,
                        user_id,
                        card_id,
                    ),
                )
            conn.execute(
                "INSERT OR IGNORE INTO flashcard_deck_cards "
                "(card_id, deck_id, created_at) VALUES (?, ?, ?)",
                (card_id, int(deck_id), now),
            )
            created.append(
                {
                    "id": card_id,
                    "deck_id": int(deck_id),
                    "front": clean_front,
                    "back": clean_back,
                    "mnemonic": clean_mnemonic,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return created


def update_card(
    user_id: str,
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    mnemonic: str | None = None,
) -> dict | None:
    """Actualiza la ficha (parcial): solo los campos no nulos (V3.86.0).

    Editar el RECORDATORIO sin tocar anverso/reverso es una operación legítima y
    frecuente, así que un `None` significa «no lo cambies». `front`, si viene,
    no puede quedar vacío.
    """
    current = get_card(user_id, card_id)
    if current is None:
        return None
    new_front = current["front"] if front is None else " ".join(front.split())
    if not new_front:
        return None
    new_key = front_key(new_front)
    new_back = current["back"] if back is None else (back or "").strip()
    new_mnemonic = (
        current["mnemonic"] if mnemonic is None else (mnemonic or "").strip()
    )
    now = _now()
    with closing(_conn()) as conn, conn:
        # V3.86.1: cambiar el anverso al de OTRA ficha no crea una gemela (lo que
        # el índice único rechazaría con un `IntegrityError` opaco): se declara el
        # conflicto para que la UI pueda decir «ya tienes una ficha con ese
        # anverso» en vez de reventar.
        if new_key != front_key(current["front"]):
            clash = conn.execute(
                "SELECT id FROM flashcard_cards "
                "WHERE user_id = ? AND front_key = ? AND id <> ?",
                (user_id, new_key, int(card_id)),
            ).fetchone()
            if clash is not None:
                raise CardFrontConflictError(int(clash["id"]))
        conn.execute(
            "UPDATE flashcard_cards SET front = ?, front_key = ?, back = ?, "
            "mnemonic = ?, updated_at = ? WHERE user_id = ? AND id = ?",
            (new_front, new_key, new_back, new_mnemonic, now, user_id, int(card_id)),
        )
    return get_card(user_id, card_id)


def update_card_with_decks(
    user_id: str,
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    mnemonic: str | None = None,
    deck_ids: list[int] | None = None,
) -> dict | None:
    """Edita la ficha y/o reemplaza sus mazos en UNA transacción (V3.86.1).

    Es lo que hace atómico el PATCH: antes el router encadenaba `update_card` y
    `set_card_decks`, así que un `deck_ids` inválido dejaba el mnemónico ya
    escrito y devolvía 400 (el cliente veía error, pero parte del PATCH sí se
    había aplicado). Aquí, si algo no es válido no se escribe NADA.

    `deck_ids = None` significa «no toques los mazos»; una lista —aunque venga
    vacía— significa «este es el conjunto nuevo» y exige al menos un mazo válido.
    Devuelve la ficha o `None` si no es del usuario; lanza
    `CardFrontConflictError` / `NoValidDecksError` para los conflictos.
    """
    with closing(_conn()) as conn, conn:
        row = conn.execute(
            f"SELECT {_CARD_COLUMNS} FROM flashcard_cards "
            "WHERE user_id = ? AND id = ?",
            (user_id, int(card_id)),
        ).fetchone()
        if row is None:
            return None
        current = _card_row(row)
        new_front = current["front"] if front is None else " ".join(front.split())
        if not new_front:
            return None
        new_key = front_key(new_front)
        if new_key != front_key(current["front"]):
            clash = conn.execute(
                "SELECT id FROM flashcard_cards "
                "WHERE user_id = ? AND front_key = ? AND id <> ?",
                (user_id, new_key, int(card_id)),
            ).fetchone()
            if clash is not None:
                raise CardFrontConflictError(int(clash["id"]))
        owned: list[int] | None = None
        if deck_ids is not None:
            owned = _owned_deck_ids_in(conn, user_id, deck_ids)
            if not owned:
                # Aborta la transacción ENTERA (rollback del `with`): el PATCH no
                # queda medio aplicado.
                raise NoValidDecksError()
        new_back = current["back"] if back is None else (back or "").strip()
        new_mnemonic = (
            current["mnemonic"] if mnemonic is None else (mnemonic or "").strip()
        )
        now = _now()
        conn.execute(
            "UPDATE flashcard_cards SET front = ?, front_key = ?, back = ?, "
            "mnemonic = ?, updated_at = ? WHERE user_id = ? AND id = ?",
            (new_front, new_key, new_back, new_mnemonic, now, user_id, int(card_id)),
        )
        if owned:
            conn.execute(
                "DELETE FROM flashcard_deck_cards WHERE card_id = ?", (int(card_id),)
            )
            conn.executemany(
                "INSERT OR IGNORE INTO flashcard_deck_cards "
                "(card_id, deck_id, created_at) VALUES (?, ?, ?)",
                [(int(card_id), deck_id, now) for deck_id in owned],
            )
            conn.execute(
                "UPDATE flashcard_cards SET deck_id = ?, updated_at = ? "
                "WHERE user_id = ? AND id = ?",
                (owned[0], now, user_id, int(card_id)),
            )
    return get_card(user_id, card_id)


def delete_card(user_id: str, card_id: int) -> dict | None:
    """Borra una tarjeta y devuelve la fila borrada (para limpiar su carta FSRS)."""
    current = get_card(user_id, card_id)
    if current is None:
        return None
    with closing(_conn()) as conn, conn:
        # Las pertenencias caen por `ON DELETE CASCADE`; se borran explícitamente
        # para no depender del pragma `foreign_keys` de la conexión.
        conn.execute(
            "DELETE FROM flashcard_deck_cards WHERE card_id = ?", (int(card_id),)
        )
        conn.execute(
            "DELETE FROM flashcard_cards WHERE user_id = ? AND id = ?",
            (user_id, int(card_id)),
        )
    return current


def count_deck_cards(user_id: str, deck_id: int) -> int:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM flashcard_deck_cards dc "
            "JOIN flashcard_cards c ON c.id = dc.card_id "
            "WHERE c.user_id = ? AND dc.deck_id = ?",
            (user_id, int(deck_id)),
        ).fetchone()
    return int(row["n"] or 0)


def shared_cards_by_deck(user_id: str) -> dict[int, int]:
    """Fichas de cada mazo que TAMBIÉN están en otro mazo (V3.86.0).

    Es lo que permite avisar antes de borrar: de las `card_count` fichas de un
    mazo, cuántas sobrevivirán por estar compartidas. `{deck_id: n}`.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT dc.deck_id, COUNT(*) AS n "
            "FROM flashcard_deck_cards dc "
            "JOIN flashcard_cards c ON c.id = dc.card_id "
            "JOIN flashcard_deck_cards other "
            "  ON other.card_id = dc.card_id AND other.deck_id <> dc.deck_id "
            "WHERE c.user_id = ? GROUP BY dc.deck_id",
            (user_id,),
        ).fetchall()
    return {int(r["deck_id"]): int(r["n"]) for r in rows}


def cards_without_deck(user_id: str | None = None) -> int:
    """Fichas SIN ninguna fila en la tabla puente (V3.86.1).

    Es el health check de la migración N:M: el dominio no produce este estado —o
    la ficha tiene mazo o se borra—, así que un contador > 0 delata una
    restauración a medias. `init_db()` lo repara al arrancar; `user_id = None`
    cuenta TODAS (lo que publica `/api/system/status`) y con un `user_id` se
    acota a un alumno.
    """
    with closing(_conn()) as conn:
        if user_id is None:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM flashcard_cards c WHERE NOT EXISTS ("
                "  SELECT 1 FROM flashcard_deck_cards dc WHERE dc.card_id = c.id"
                ")"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM flashcard_cards c WHERE c.user_id = ? "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM flashcard_deck_cards dc WHERE dc.card_id = c.id"
                ")",
                (user_id,),
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

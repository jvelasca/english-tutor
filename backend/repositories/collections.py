"""Colecciones léxicas: packs temáticos y listas de usuario (retención Personal).

Catálogo global (`user_id=''`, `kind=theme_pack`) sembrado desde
`backend/curriculum/vocab_packs/*.json` (contenido versionado, no `backend/data/`,
que está ignorado por git). Listas del alumno (`kind=user_list`).
La membresía `vocab_collection_membership` enlaza palabras del alumno con
colecciones; no escribe mastery ni Assessment.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from pathlib import Path

from repositories.db import _conn, _now
from repositories.users import get_user

logger = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).resolve().parent.parent / "curriculum" / "vocab_packs"

BULK_MAX_WORDS = 200


def ensure_theme_packs_seeded() -> int:
    """Idempotente: carga packs JSON globales si el slug aún no existe.

    Devuelve el número de packs recién insertados.
    """
    if not PACKS_DIR.is_dir():
        return 0
    inserted = 0
    with closing(_conn()) as conn, conn:
        for path in sorted(PACKS_DIR.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("vocab pack ilegible: %s", path.name, exc_info=True)
                continue
            slug = str(payload.get("slug") or path.stem).strip().lower()
            if not slug:
                continue
            existing = conn.execute(
                "SELECT id FROM vocab_collections "
                "WHERE user_id = '' AND slug = ?",
                (slug,),
            ).fetchone()
            if existing is not None:
                continue
            now = _now()
            cur = conn.execute(
                "INSERT INTO vocab_collections "
                "(user_id, kind, slug, title, title_es, cefr_hint, created_at) "
                "VALUES ('', ?, ?, ?, ?, ?, ?)",
                (
                    str(payload.get("kind") or "theme_pack"),
                    slug,
                    str(payload.get("title") or slug),
                    str(payload.get("title_es") or ""),
                    str(payload.get("cefr_hint") or ""),
                    now,
                ),
            )
            coll_id = int(cur.lastrowid)
            items = payload.get("items") or []
            for idx, raw in enumerate(items):
                if not isinstance(raw, dict):
                    continue
                word = str(raw.get("word") or "").strip().lower()
                if not word:
                    continue
                lemma = str(raw.get("lemma") or word).strip().lower()
                conn.execute(
                    "INSERT OR IGNORE INTO vocab_collection_items "
                    "(collection_id, word, lemma, translation, pos, order_index) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        coll_id,
                        word,
                        lemma,
                        str(raw.get("translation") or "").strip(),
                        str(raw.get("pos") or "").strip(),
                        idx,
                    ),
                )
            inserted += 1
    return inserted


def list_collections(user_id: str) -> list[dict]:
    """Packs globales + listas del usuario, con conteo de ítems y enrolled."""
    ensure_theme_packs_seeded()
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT c.id, c.user_id, c.kind, c.slug, c.title, c.title_es, "
            "c.cefr_hint, c.created_at, "
            "(SELECT COUNT(*) FROM vocab_collection_items i "
            " WHERE i.collection_id = c.id) AS item_count, "
            "CASE WHEN e.user_id IS NULL THEN 0 ELSE 1 END AS enrolled "
            "FROM vocab_collections c "
            "LEFT JOIN vocab_collection_enrollments e "
            "  ON e.collection_id = c.id AND e.user_id = ? "
            "WHERE c.user_id = '' OR c.user_id = ? "
            "ORDER BY c.kind DESC, c.slug",
            (user_id, user_id),
        ).fetchall()
    return [dict(r) for r in rows]


def get_collection(collection_id: int) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, kind, slug, title, title_es, cefr_hint, created_at "
            "FROM vocab_collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_collection_items(collection_id: int) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, lemma, translation, pos, order_index "
            "FROM vocab_collection_items "
            "WHERE collection_id = ? ORDER BY order_index, word",
            (collection_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_user_list(
    user_id: str,
    *,
    title: str,
    slug: str = "",
    cefr_hint: str = "",
) -> dict | None:
    """Crea una lista vacía del alumno. None si el usuario no existe."""
    if get_user(user_id) is None:
        return None
    base = (slug or title or "list").strip().lower()
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in base)
    safe = "-".join(part for part in safe.split("-") if part) or "list"
    now = _now()
    with closing(_conn()) as conn, conn:
        # Evitar colisión de slug: sufijo numérico.
        candidate = safe
        n = 1
        while conn.execute(
            "SELECT 1 FROM vocab_collections WHERE user_id = ? AND slug = ?",
            (user_id, candidate),
        ).fetchone():
            n += 1
            candidate = f"{safe}-{n}"
        cur = conn.execute(
            "INSERT INTO vocab_collections "
            "(user_id, kind, slug, title, title_es, cefr_hint, created_at) "
            "VALUES (?, 'user_list', ?, ?, '', ?, ?)",
            (user_id, candidate, title.strip() or candidate, cefr_hint, now),
        )
        coll_id = int(cur.lastrowid)
    return get_collection(coll_id)


def add_items_to_collection(
    collection_id: int, items: list[dict]
) -> int:
    """Añade ítems al catálogo de una colección. Devuelve cuántos se insertaron."""
    added = 0
    with closing(_conn()) as conn, conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(order_index), -1) FROM vocab_collection_items "
            "WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()[0]
        order = int(max_order) + 1
        for raw in items:
            word = str(raw.get("word") or "").strip().lower()
            if not word:
                continue
            lemma = str(raw.get("lemma") or word).strip().lower()
            cur = conn.execute(
                "INSERT OR IGNORE INTO vocab_collection_items "
                "(collection_id, word, lemma, translation, pos, order_index) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    collection_id,
                    word,
                    lemma,
                    str(raw.get("translation") or "").strip(),
                    str(raw.get("pos") or "").strip(),
                    order,
                ),
            )
            if cur.rowcount:
                added += 1
                order += 1
    return added


def is_enrolled(user_id: str, collection_id: int) -> bool:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM vocab_collection_enrollments "
            "WHERE user_id = ? AND collection_id = ?",
            (user_id, collection_id),
        ).fetchone()
    return row is not None


def mark_enrolled(user_id: str, collection_id: int) -> bool:
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO vocab_collection_enrollments "
            "(user_id, collection_id, enrolled_at) VALUES (?, ?, ?)",
            (user_id, collection_id, _now()),
        )
    return True


def add_membership(
    user_id: str, collection_id: int, word: str
) -> bool:
    if get_user(user_id) is None:
        return False
    w = word.strip().lower()
    if not w:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO vocab_collection_membership "
            "(user_id, collection_id, word, created_at) VALUES (?, ?, ?, ?)",
            (user_id, collection_id, w, _now()),
        )
    return True


def add_memberships(
    user_id: str, collection_id: int, words: list[str]
) -> int:
    """Alta de membresías en UNA transacción (V3.77.2).

    `add_membership` abría una conexión (más su comprobación de usuario) por
    palabra: enrolar un pack o pegar una lista de N palabras hacía N idas y
    vueltas a la BD, dentro de un `to_thread` cada una. Aquí se agrupa con un
    solo `executemany`, con la MISMA semántica (`INSERT OR IGNORE`, duplicados
    dentro del lote incluidos). Devuelve las filas realmente insertadas.
    """
    if get_user(user_id) is None:
        return 0
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in words:
        w = str(raw).strip().lower()
        if w and w not in seen:
            seen.add(w)
            cleaned.append(w)
    if not cleaned:
        return 0
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO vocab_collection_membership "
            "(user_id, collection_id, word, created_at) VALUES (?, ?, ?, ?)",
            [(user_id, collection_id, w, now) for w in cleaned],
        )
        return int(cur.rowcount or 0)


def words_in_collection(user_id: str, collection_id: int) -> set[str]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word FROM vocab_collection_membership "
            "WHERE user_id = ? AND collection_id = ?",
            (user_id, collection_id),
        ).fetchall()
    return {str(r["word"]) for r in rows}


def translation_for_word(word: str, collection_id: int | None = None) -> str:
    """Traducción del catálogo de colección o cadena vacía."""
    w = word.strip().lower()
    with closing(_conn()) as conn:
        if collection_id is not None:
            row = conn.execute(
                "SELECT translation FROM vocab_collection_items "
                "WHERE collection_id = ? AND word = ?",
                (collection_id, w),
            ).fetchone()
            if row and row["translation"]:
                return str(row["translation"])
        row = conn.execute(
            "SELECT translation FROM vocab_collection_items "
            "WHERE word = ? AND translation != '' "
            "ORDER BY id LIMIT 1",
            (w,),
        ).fetchone()
    return str(row["translation"]) if row else ""

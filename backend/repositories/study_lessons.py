"""Ítems servidos por Estudiar y su cierre, en una sola transacción.

`GET /study/queue` inserta una fila `open` por palabra. `POST /study/complete`
solo cierra ese `item_id`: la identidad (palabra, carta, mazo) sale de la fila,
no del cuerpo. Repetir el mismo id devuelve el resultado ya guardado y no
vuelve a agendar.

Una ficha manual califica `flashcard:<id>` y da de alta la carta `lexicon`
sin nota (`reps=0`). El ámbito léxico califica solo `lexicon:<palabra>`.
"""
from __future__ import annotations

import json
import uuid
from contextlib import closing

from repositories import academy as academy_repo
from repositories import flashcards as flashcards_repo
from repositories.db import _conn, _now
from repositories.vocabulary import lexical_unit_key
from services import fsrs
from services.evidence import classify_event_role

OK = "ok"
INVALID = "invalid"
GONE = "gone"

CARD_FLASHCARD = "flashcard"
CARD_LEXICON = "lexicon"


def _after_writes() -> None:
    """Barrera de prueba. Un fallo aquí aborta el commit y no deja nada a medias."""
    return None


def insert_served_items(
    user_id: str,
    items: list[dict],
    scope: str,
    mode: str,
    level: str,
    collection_id: int | None,
) -> list[dict]:
    """Persiste la cola servida y devuelve los mismos ítems con `item_id`."""
    if not items:
        return []
    now = _now()
    coll = int(collection_id) if collection_id is not None else None
    out: list[dict] = []
    with closing(_conn()) as conn, conn:
        for item in items:
            item_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO study_lesson_items "
                "(item_id, user_id, word, cefr, card_type, card_id, deck_id, "
                "scope, mode, level, collection_id, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    item_id,
                    user_id,
                    str(item.get("word") or ""),
                    str(item.get("cefr") or ""),
                    str(item.get("card_type") or ""),
                    str(item.get("card_id") or ""),
                    int(item.get("deck_id") or 0),
                    scope,
                    mode,
                    level or "",
                    coll,
                    now,
                ),
            )
            out.append({**item, "item_id": item_id})
    return out


def complete_item(
    user_id: str,
    item_id: str,
    grade: int,
    facets: dict,
    translation: str,
    required_facets: list[str],
) -> tuple[str, dict | None]:
    """Cierra el ítem servido. `(ok, resultado)`, `(invalid, None)` o `(gone, None)`.

    `gone`: la ficha manual ya no pertenece a ese mazo. No se escribe nada y
    el ítem sigue `open`. Un reintento del mismo id, si la ficha volviera,
    podría cerrarse; mientras no esté, no agenda otra carta.
    """
    if grade not in fsrs.GRADES or not str(item_id or "").strip():
        return INVALID, None
    conn = _conn()
    try:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            code, body, wrote = _finish(
                conn,
                user_id,
                str(item_id).strip(),
                int(grade),
                facets if isinstance(facets, dict) else {},
                translation,
                list(required_facets or []),
            )
            if wrote:
                _after_writes()
            conn.execute("COMMIT")
            return code, body
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def _finish(
    conn,
    user_id: str,
    item_id: str,
    grade: int,
    facets: dict,
    translation: str,
    required_facets: list[str],
) -> tuple[str, dict | None, bool]:
    if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        return INVALID, None, False
    row = conn.execute(
        "SELECT * FROM study_lesson_items WHERE item_id = ? AND user_id = ?",
        (item_id, user_id),
    ).fetchone()
    if row is None:
        return INVALID, None, False
    if str(row["status"]) == "completed":
        return OK, _stored_result(row["result_json"]), False
    if str(row["status"]) != "open":
        return INVALID, None, False

    word = str(row["word"] or "")
    if not word:
        return INVALID, None, False
    card_type = str(row["card_type"] or "")
    card_id = str(row["card_id"] or "")
    deck_id = int(row["deck_id"] or 0)
    cefr = str(row["cefr"] or "")
    now_iso = _now()

    manual = card_type == CARD_FLASHCARD and deck_id != flashcards_repo.AUTO_DECK_ID
    if manual:
        front = _manual_front(conn, user_id, card_id, deck_id)
        if front is None:
            return GONE, None, False
        graded_type = CARD_FLASHCARD
        graded_id = card_id
        graded_deck = deck_id
        label = front or word
        why = fsrs.why_for_flashcard()
        event_detail = f"flashcard:{card_id}:{grade}"
    elif card_type == CARD_LEXICON:
        graded_type = CARD_LEXICON
        graded_id = word
        graded_deck = flashcards_repo.AUTO_DECK_ID
        label = word
        why = "review"
        event_detail = f"retention:{word}:{grade}"
    else:
        return INVALID, None, False

    _ensure_vocabulary(conn, user_id, word, cefr=cefr, translation=translation)
    if manual:
        _ensure_ungraded_lexicon(conn, user_id, word, now_iso)
    merged = _write_facets(conn, user_id, word, facets)
    updated = _schedule(
        conn,
        user_id,
        graded_type,
        graded_id,
        label,
        why,
        grade,
        now_iso,
    )
    _write_review(
        conn,
        user_id,
        deck_id=graded_deck,
        card_type=graded_type,
        card_id=graded_id,
        grade=grade,
        now_iso=now_iso,
    )
    _write_event(conn, user_id, event_detail, now_iso)

    from domain.study_bank import is_learned

    explained = fsrs.explain(updated, now=now_iso)
    result = {
        "word": word,
        "grade": grade,
        "card_type": graded_type,
        "card_id": graded_id,
        "deck_id": graded_deck,
        "due_at": updated.get("due_at") or "",
        "next_in_days": float(explained.get("when", {}).get("next_in_days") or 0),
        "facets": merged,
        "learned": is_learned(updated, merged, required_facets),
    }
    cur = conn.execute(
        "UPDATE study_lesson_items SET status = 'completed', result_json = ?, "
        "completed_at = ? WHERE item_id = ? AND user_id = ? AND status = 'open'",
        (json.dumps(result, ensure_ascii=False), now_iso, item_id, user_id),
    )
    if cur.rowcount != 1:
        raise RuntimeError("el ítem de la lección cambió dentro de la transacción")
    return OK, result, True


def _stored_result(raw: str) -> dict | None:
    try:
        parsed = json.loads(raw or "")
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _manual_front(conn, user_id: str, card_id: str, deck_id: int) -> str | None:
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return None
    row = conn.execute(
        "SELECT c.front FROM flashcard_cards c "
        "JOIN flashcard_deck_cards dc ON dc.card_id = c.id "
        "WHERE c.user_id = ? AND c.id = ? AND dc.deck_id = ?",
        (user_id, cid, int(deck_id)),
    ).fetchone()
    if row is None:
        return None
    return str(row["front"] or "")


def _ensure_vocabulary(
    conn, user_id: str, word: str, *, cefr: str, translation: str
) -> None:
    """La misma siembra que `seed_study_items` para una sola palabra."""
    lemma = word
    unit = lexical_unit_key(word, lemma)
    text = str(translation or "").strip()[:500]
    code = str(cefr or "").strip()
    existing = conn.execute(
        "SELECT word FROM vocabulary WHERE user_id = ? AND word = ?",
        (user_id, word),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO vocabulary "
            "(user_id, word, production_count, first_seen, last_seen, "
            "exposure_count, last_exposed_at, production_days, "
            "cefr, level_id, objective_id, source, lemma, kind, "
            "lexical_unit, translation, sense_json) "
            "VALUES (?, ?, 0, '', '', 0, '', 0, ?, '', '', 'user', ?, 'word', "
            "?, ?, '')",
            (user_id, word, code, lemma, unit, text),
        )
        return
    conn.execute(
        "UPDATE vocabulary SET "
        "lemma = CASE WHEN lemma = '' THEN ? ELSE lemma END, "
        "cefr = CASE WHEN cefr = '' THEN ? ELSE cefr END, "
        "lexical_unit = CASE WHEN lexical_unit = '' THEN ? ELSE lexical_unit END, "
        "translation = CASE WHEN ? = '' THEN translation ELSE ? END "
        "WHERE user_id = ? AND word = ?",
        (lemma, code, unit, text, text, user_id, word),
    )


def _ensure_ungraded_lexicon(conn, user_id: str, word: str, now_iso: str) -> None:
    """Crea la carta léxico si falta o sigue en cero repasos. No la califica."""
    prev = academy_repo.read_fsrs_card(conn, user_id, CARD_LEXICON, word)
    if prev and int(prev.get("reps") or 0) > 0:
        return
    academy_repo.write_fsrs_card(
        conn,
        user_id,
        fsrs.empty_card(
            target_type=CARD_LEXICON,
            target_id=word,
            label=word,
            why="retention-import",
            now=now_iso,
        ),
    )


def _write_facets(conn, user_id: str, word: str, incoming: dict) -> dict[str, str]:
    from domain.study_bank import merge_facets

    stored: dict = {}
    row = conn.execute(
        "SELECT lesson_facets FROM vocabulary WHERE user_id = ? AND word = ?",
        (user_id, word),
    ).fetchone()
    if row is not None and row["lesson_facets"]:
        try:
            parsed = json.loads(row["lesson_facets"])
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            stored = parsed
    merged = merge_facets(stored, incoming)
    conn.execute(
        "UPDATE vocabulary SET lesson_facets = ? WHERE user_id = ? AND word = ?",
        (json.dumps(merged, ensure_ascii=False, sort_keys=True), user_id, word),
    )
    return merged


def _schedule(
    conn,
    user_id: str,
    target_type: str,
    target_id: str,
    label: str,
    why: str,
    grade: int,
    now_iso: str,
) -> dict:
    prev = academy_repo.read_fsrs_card(conn, user_id, target_type, target_id)
    if prev is None:
        prev = fsrs.empty_card(
            target_type=target_type,
            target_id=target_id,
            label=label,
            why=why,
            now=now_iso,
        )
    updated = fsrs.schedule(prev, grade, now=now_iso, why=why)
    academy_repo.write_fsrs_card(conn, user_id, updated)
    return updated


def _write_review(
    conn,
    user_id: str,
    *,
    deck_id: int,
    card_type: str,
    card_id: str,
    grade: int,
    now_iso: str,
) -> None:
    seen = conn.execute(
        "SELECT 1 FROM flashcard_reviews "
        "WHERE user_id = ? AND card_type = ? AND card_id = ? LIMIT 1",
        (user_id, card_type, card_id),
    ).fetchone()
    conn.execute(
        "INSERT INTO flashcard_reviews "
        "(user_id, deck_id, card_type, card_id, grade, was_new, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            int(deck_id),
            card_type,
            card_id,
            int(grade),
            0 if seen else 1,
            now_iso,
        ),
    )


def _write_event(conn, user_id: str, detail: str, now_iso: str) -> None:
    conn.execute(
        "INSERT INTO learning_events "
        "(user_id, type, detail, created_at, event_role) "
        "VALUES (?, 'exercise', ?, ?, ?)",
        (user_id, detail, now_iso, classify_event_role("exercise", detail)),
    )

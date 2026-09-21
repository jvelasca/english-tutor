"""Retención léxica (Personal): ingestión + sesión de tarjetas sobre FSRS.

Camino etiquetado (D5/E3), paralelo al planner/drill:
- añadir palabra/lista/pack → fila `vocabulary` + carta FSRS `lexicon` due;
- grade Again/Hard/Good/Easy → `services.fsrs.schedule` + evento informativo
  `retention:<word>:<grade>`;
- NO escribe mastery, Assessment delayed ni CEFR.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import partial

from starlette.concurrency import run_in_threadpool

from repositories import academy as academy_repo
from repositories import collections as collections_repo
from repositories import dictionary as dictionary_repo
from repositories import learning as learning_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs

_WORD_RE = re.compile(r"^[a-zA-Z][a-zA-Z'\- ]{0,79}$")
SESSION_LIMIT = 20
BULK_MAX = collections_repo.BULK_MAX_WORDS


def _normalize_word(raw: str) -> str | None:
    text = " ".join((raw or "").strip().lower().split())
    if not text or not _WORD_RE.match(text):
        return None
    return text


def _parse_bulk_lines(text: str) -> list[dict]:
    """Una palabra por línea; opcional `word,translation` o `word\\ttranslation`."""
    items: list[dict] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            left, right = line.split("\t", 1)
        elif "," in line:
            left, right = line.split(",", 1)
        else:
            left, right = line, ""
        word = _normalize_word(left)
        if not word or word in seen:
            continue
        seen.add(word)
        items.append(
            {
                "word": word,
                "lemma": word,
                "translation": right.strip(),
                "kind": "word",
            }
        )
        if len(items) >= BULK_MAX:
            break
    return items


def _ensure_fsrs_lexicon(user_id: str, words: list[str], *, why: str) -> None:
    """Siembra cartas lexicon due ahora si no existen (o reps==0)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    for word in words:
        prev = academy_repo.get_fsrs_card(user_id, "lexicon", word)
        if prev and int(prev.get("reps") or 0) > 0:
            continue
        card = fsrs.empty_card(
            target_type="lexicon",
            target_id=word,
            label=word,
            why=why,
            now=now_iso,
        )
        academy_repo.upsert_fsrs_card(user_id, card)


def _card_face(word: str, collection_id: int | None = None) -> dict:
    """Cara B: traducción de pack o caché de diccionario."""
    translation = collections_repo.translation_for_word(word, collection_id)
    definition = ""
    entry = dictionary_repo.get_entry(word)
    if entry:
        if not translation:
            translation = str(entry.get("translation") or "")
        definition = str(entry.get("definition") or "")
    return {
        "word": word,
        "translation": translation,
        "definition": definition,
    }


async def add_item(
    user_id: str,
    word: str,
    *,
    translation: str = "",
    collection_id: int | None = None,
) -> dict | None:
    """Añade una palabra suelta al léxico personal + FSRS. Sin evidencia de skill."""
    normalized = _normalize_word(word)
    if not normalized:
        return None
    items = [
        {
            "word": normalized,
            "lemma": normalized,
            "translation": (translation or "").strip(),
            "kind": "word",
        }
    ]
    touched = await run_in_threadpool(
        partial(vocabulary_repo.seed_study_items, source="user"),
        user_id,
        items,
    )
    if not touched:
        return None
    if collection_id is not None:
        await run_in_threadpool(
            collections_repo.add_membership, user_id, collection_id, normalized
        )
        if translation:
            await run_in_threadpool(
                collections_repo.add_items_to_collection,
                collection_id,
                items,
            )
    await run_in_threadpool(
        partial(_ensure_fsrs_lexicon, why="retention-import"),
        user_id,
        touched,
    )
    face = await run_in_threadpool(_card_face, normalized, collection_id)
    return {"added": touched, "item": face}


async def add_bulk(
    user_id: str,
    text: str,
    *,
    title: str = "",
    collection_id: int | None = None,
) -> dict | None:
    """Pega una lista de palabras; opcionalmente crea/usa una lista de usuario."""
    items = _parse_bulk_lines(text)
    if not items:
        return {"added": [], "collection_id": collection_id, "count": 0}

    coll_id = collection_id
    if coll_id is None:
        created = await run_in_threadpool(
            partial(
                collections_repo.create_user_list,
                title=title.strip() or "My list",
            ),
            user_id,
        )
        if created is None:
            return None
        coll_id = int(created["id"])

    await run_in_threadpool(
        collections_repo.add_items_to_collection, coll_id, items
    )
    touched = await run_in_threadpool(
        partial(vocabulary_repo.seed_study_items, source="imported"),
        user_id,
        items,
    )
    for w in touched:
        await run_in_threadpool(
            collections_repo.add_membership, user_id, coll_id, w
        )
    await run_in_threadpool(collections_repo.mark_enrolled, user_id, coll_id)
    await run_in_threadpool(
        partial(_ensure_fsrs_lexicon, why="retention-import"),
        user_id,
        touched,
    )
    return {"added": touched, "collection_id": coll_id, "count": len(touched)}


async def list_collections(user_id: str) -> dict:
    rows = await run_in_threadpool(collections_repo.list_collections, user_id)
    return {
        "collections": [
            {
                "id": int(r["id"]),
                "kind": r["kind"],
                "slug": r["slug"],
                "title": r["title"],
                "title_es": r.get("title_es") or "",
                "cefr_hint": r.get("cefr_hint") or "",
                "item_count": int(r.get("item_count") or 0),
                "enrolled": bool(r.get("enrolled")),
                "is_global": not str(r.get("user_id") or ""),
            }
            for r in rows
        ]
    }


async def create_collection(user_id: str, title: str) -> dict | None:
    row = await run_in_threadpool(
        partial(collections_repo.create_user_list, title=title),
        user_id,
    )
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "kind": row["kind"],
        "slug": row["slug"],
        "title": row["title"],
        "title_es": "",
        "cefr_hint": row.get("cefr_hint") or "",
        "item_count": 0,
        "enrolled": False,
        "is_global": False,
    }


async def enroll_collection(user_id: str, collection_id: int) -> dict | None:
    """Activa un pack/lista: materializa ítems en vocabulary + FSRS + membership."""
    coll = await run_in_threadpool(collections_repo.get_collection, collection_id)
    if coll is None:
        return None
    owner = str(coll.get("user_id") or "")
    if owner and owner != user_id:
        return None
    catalog = await run_in_threadpool(
        collections_repo.list_collection_items, collection_id
    )
    if not catalog:
        await run_in_threadpool(
            collections_repo.mark_enrolled, user_id, collection_id
        )
        return {"collection_id": collection_id, "added": [], "count": 0}

    cefr = str(coll.get("cefr_hint") or "")
    items = [
        {
            "word": r["word"],
            "lemma": r.get("lemma") or r["word"],
            "translation": r.get("translation") or "",
            "cefr": cefr,
            "kind": "word",
        }
        for r in catalog
    ]
    source = "imported" if not owner else "user"
    touched = await run_in_threadpool(
        partial(vocabulary_repo.seed_study_items, source=source),
        user_id,
        items,
    )
    for w in touched:
        await run_in_threadpool(
            collections_repo.add_membership, user_id, collection_id, w
        )
    await run_in_threadpool(
        collections_repo.mark_enrolled, user_id, collection_id
    )
    await run_in_threadpool(
        partial(_ensure_fsrs_lexicon, why="retention-import"),
        user_id,
        touched,
    )
    return {
        "collection_id": collection_id,
        "added": touched,
        "count": len(touched),
    }


async def retention_due(
    user_id: str,
    *,
    limit: int = SESSION_LIMIT,
    collection_id: int | None = None,
) -> dict:
    """Cola due solo lexicon, enriquecida para la sesión de tarjetas."""
    now_iso = datetime.now(timezone.utc).isoformat()
    limit = max(1, min(int(limit), SESSION_LIMIT))
    cards = await run_in_threadpool(academy_repo.list_fsrs_cards, user_id)
    lexicon = [c for c in cards if c.get("target_type") == "lexicon"]
    if collection_id is not None:
        allowed = await run_in_threadpool(
            collections_repo.words_in_collection, user_id, collection_id
        )
        lexicon = [c for c in lexicon if c.get("target_id") in allowed]
    due = fsrs.due_queue(lexicon, now=now_iso, limit=limit)
    items = []
    for card in due:
        word = str(card.get("target_id") or "")
        face = await run_in_threadpool(_card_face, word, collection_id)
        explained = fsrs.explain(card, now=now_iso)
        items.append(
            {
                "word": word,
                "translation": face["translation"],
                "definition": face["definition"],
                "due_at": card.get("due_at") or "",
                "stability": float(card.get("stability") or 0),
                "retrievability": float(
                    explained.get("how_strong", {}).get("retrievability") or 0
                ),
                "why": card.get("why") or "",
                "reps": int(card.get("reps") or 0),
            }
        )
    return {
        "due_count": len(items),
        "limit": limit,
        "items": items,
        "fsrs_version": fsrs.FSRS_VERSION,
    }


async def retention_review(
    user_id: str, word: str, grade: int
) -> dict | None:
    """Grade 1–4 sobre carta lexicon + evento informativo. Sin mastery."""
    normalized = _normalize_word(word)
    if not normalized or grade not in fsrs.GRADES:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    card = await run_in_threadpool(
        academy_repo.get_fsrs_card, user_id, "lexicon", normalized
    )
    if card is None:
        card = fsrs.empty_card(
            target_type="lexicon",
            target_id=normalized,
            label=normalized,
            why="retention-import",
            now=now_iso,
        )
    updated = fsrs.schedule(card, grade, now=now_iso)
    saved = await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, updated)
    if saved is None:
        return None
    await run_in_threadpool(
        learning_repo.record_event,
        user_id,
        "exercise",
        f"retention:{normalized}:{grade}",
    )
    explained = fsrs.explain(saved, now=now_iso)
    return {
        "word": normalized,
        "grade": grade,
        "due_at": saved.get("due_at") or "",
        "next_in_days": float(explained.get("when", {}).get("next_in_days") or 0),
        "stability": float(saved.get("stability") or 0),
        "retrievability": float(
            explained.get("how_strong", {}).get("retrievability") or 0
        ),
        "reps": int(saved.get("reps") or 0),
    }

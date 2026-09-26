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


def parse_bulk_fields(text: str, *, max_fields: int = 2) -> list[list[str]]:
    """Parte un pegado en campos por línea, sin opinar sobre ellos (V3.86.0).

    Generaliza `parse_bulk_lines`: una entrada por línea, `#` comenta y las
    líneas vacías se ignoran. El separador es el primer tabulador o, si no hay,
    la primera coma; se parten como mucho `max_fields` campos (el último conserva
    las comas sobrantes, para que un reverso con comas no se destroce). Devuelve
    listas de 1..`max_fields` cadenas ya recortadas. Con `max_fields=2` el
    resultado es idéntico al de `parse_bulk_lines`.
    """
    fields: list[list[str]] = []
    limit = max(1, int(max_fields))
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            parts = line.split("\t", limit - 1) if limit > 1 else [line]
        elif "," in line:
            parts = line.split(",", limit - 1) if limit > 1 else [line]
        else:
            parts = [line]
        fields.append([part.strip() for part in parts])
    return fields


def parse_bulk_lines(text: str) -> list[tuple[str, str]]:
    """Parte un pegado en pares `(izquierda, derecha)`, sin opinar sobre ellos.

    V3.80.0: la sintaxis es **una sola** para lo que el alumno pega, porque el
    alumno pega lo mismo en los dos sitios. La usan el léxico (`add_bulk`) y las
    tarjetas a mano (`flashcards.add_cards_bulk`):

    - una entrada por línea;
    - `,` o tabulador separan «anverso» de «reverso» (`word,translation`,
      `word\\ttranslation`); sin separador, el reverso es vacío;
    - `#` comenta la línea y las líneas vacías se ignoran.

    Lo que **no** se comparte es la validación de cada lado, y a propósito: el
    léxico normaliza palabras (minúsculas, sin dígitos, hasta 80 caracteres) y
    una tarjeta admite una frase entera («break a leg»). Por eso esta función
    solo parte y cada llamante valida y acota lo suyo. Teniendo dos parsers, la
    sintaxis de pegado acabaría divergiendo entre las dos pantallas.

    V3.86.0: se apoya en `parse_bulk_fields` (una sola implementación del corte);
    el alta masiva de FICHAS usa la variante de tres campos para el recordatorio.
    """
    pairs: list[tuple[str, str]] = []
    for parts in parse_bulk_fields(text, max_fields=2):
        left = parts[0] if parts else ""
        right = parts[1] if len(parts) > 1 else ""
        pairs.append((left.strip(), right.strip()))
    return pairs


def _parse_bulk_lines(text: str) -> list[dict]:
    """Una palabra por línea; opcional `word,translation` o `word\\ttranslation`."""
    items: list[dict] = []
    seen: set[str] = set()
    for left, right in parse_bulk_lines(text):
        word = _normalize_word(left)
        if not word or word in seen:
            continue
        seen.add(word)
        items.append(
            {
                "word": word,
                "lemma": word,
                "translation": right,
                "kind": "word",
            }
        )
        if len(items) >= BULK_MAX:
            break
    return items


def _ensure_fsrs_lexicon(user_id: str, words: list[str], *, why: str) -> None:
    """Siembra cartas lexicon due ahora si no existen (o reps==0).

    V3.77.2: en LOTE. Antes hacía `get_fsrs_card` + `upsert_fsrs_card` por
    palabra (dos conexiones cada una, más su `get_user`), así que importar un
    pack de 40 palabras abría ~120 conexiones. Ahora son dos: una consulta con
    `IN (...)` y un `executemany`.
    """
    candidates = [w for w in words if w]
    if not candidates:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    previous = academy_repo.fsrs_cards_by_ids(user_id, "lexicon", candidates)
    pending: list[dict] = []
    for word in candidates:
        prev = previous.get(str(word))
        if prev and int(prev.get("reps") or 0) > 0:
            continue
        pending.append(
            fsrs.empty_card(
                target_type="lexicon",
                target_id=word,
                label=word,
                why=why,
                now=now_iso,
            )
        )
    if pending:
        academy_repo.upsert_fsrs_cards(user_id, pending)


def card_face(
    user_id: str, word: str, collection_id: int | None = None
) -> dict:
    """Cara B: la traducción del alumno, o la del pack, o la caché del diccionario.

    V3.78.0: deja de ser privada porque el modo Flashcards la reutiliza para el
    mazo automático. Es la MISMA cara que ve la sesión de retención: si hubiera
    dos constructores, la misma palabra podría enseñar dos reversos distintos
    según por dónde se entrara.

    V3.80.0: la precedencia pasa a estar **declarada**, porque antes no había
    nada que pudiera mandar —solo existían el pack y la caché— y la cara B vacía
    era el estado normal (139 de 145 cartas del léxico sin reverso, medido en la
    BD del alumno). El orden es, de más a menos autoridad:

    1. **Lo que escribió el alumno** (`vocabulary.translation`). Es un dato
       humano, suyo y explícito: si corrige una traducción, su corrección manda
       sobre cualquier cosa que la app pudiera haber puesto ahí.
    2. **El catálogo del pack** (`vocab_collection_items`), que es contenido
       curado y compartido: una autoría mejor que la generada a máquina.
    3. **La caché del diccionario** (`dictionary_entries`), que es lo que el
       modelo local generó a demanda al consultar la palabra.

    Y si no hay ninguna de las tres, devuelve vacío: **no inventa**. Una tarjeta
    sin reverso es un dato («no consta»), no un error que haya que disimular con
    una traducción de relleno. De ahí que la UI tenga que ofrecer generarla o
    escribirla, en vez de dar por hecho que siempre hay algo que enseñar.

    `user_id` no es opcional a propósito (V3.80.0): la precedencia depende de un
    dato POR ALUMNO, así que una firma que lo omitiera sería una firma que miente
    sobre lo que hace. Los tres llamantes lo tienen a mano.
    """
    translation = str(
        vocabulary_repo.translation_for_word(user_id, word) or ""
    ).strip()
    if not translation:
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


def _collection_writable(coll: dict | None, user_id: str) -> bool:
    """Predicado puro: ¿puede `user_id` escribir en el catálogo de esa colección?

    La misma puerta que ya aplicaba `enroll_collection` (V3.77.1) se extiende a
    la ingestión: un pack global (`user_id=''`) es de todos, pero la lista
    privada de otro perfil no es un destino válido. Sin esto, `collection_id`
    —que es entrada pública del cliente— permitía inyectar palabras y
    traducciones en el catálogo de un pack global o en la lista de otro usuario.
    La colección inexistente tampoco es un destino válido.
    """
    if coll is None:
        return False
    owner = str(coll.get("user_id") or "")
    return not owner or owner == user_id


async def _collection_writable_by(user_id: str, collection_id: int) -> bool:
    coll = await run_in_threadpool(
        collections_repo.get_collection, collection_id
    )
    return _collection_writable(coll, user_id)


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
    if collection_id is not None and not await _collection_writable_by(
        user_id, collection_id
    ):
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
    face = await run_in_threadpool(card_face, user_id, normalized, collection_id)
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
    if collection_id is not None and not await _collection_writable_by(
        user_id, collection_id
    ):
        return None

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
    # V3.77.2: una sola transacción para todas las membresías (antes: una
    # conexión por palabra).
    await run_in_threadpool(
        collections_repo.add_memberships, user_id, coll_id, touched
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
    if not _collection_writable(coll, user_id):
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
    # V3.77.2: una sola transacción para todas las membresías del pack.
    await run_in_threadpool(
        collections_repo.add_memberships, user_id, collection_id, touched
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
        face = await run_in_threadpool(card_face, user_id, word, collection_id)
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

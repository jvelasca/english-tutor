"""Modo Flashcards del diccionario (V3.78.0): mazos, cola y calificación.

Cuatro cosas que este módulo decide y conviene entender antes de tocarlo:

1. **Hay DOS clases de tarjeta y una sola cola.** El mazo automático son las
   cartas `lexicon` —todo lo que la app ha registrado del alumno: currículum,
   chat, speaking, listas y packs— y los mazos manuales son filas de
   `flashcard_cards` con su carta `flashcard`. Ambas clases se sirven con el
   MISMO planificador (`services.fsrs`) y se califican por el mismo endpoint,
   así que el alumno ve una sesión y no dos.

2. **Los límites del día salen del ledger, no del scheduler.** Se cuenta cada
   calificación (`flashcard_reviews`), no cada tarjeta distinta, porque Anki
   mide repasos: una tarjeta fallada y repetida tres veces son tres repasos.
   `was_new` marca la primera vez, que es lo que aplica el tope de nuevas.

3. **Nada de esto acredita mastery.** Igual que la retención léxica (D5/E3): la
   calificación programa el próximo repaso y escribe un evento informativo; no
   toca `learning_evidence`, ni Assessment, ni CEFR.

4. **La pertenencia ficha ↔ mazo la manda la tabla puente (V3.86.1).** La autoridad
   es `flashcard_deck_cards`; `flashcard_cards.deck_id` se conserva **deprecada**
   como proyección legacy del «mazo principal» (`MIN(mazos)`), con un solo
   escritor, solo para que el esquema anterior siga abriendo. No es una segunda
   fuente de verdad y no debe leerse como tal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import partial

from starlette.concurrency import run_in_threadpool

from domain import retention as retention_domain
from domain import study_config as study_config_domain
from repositories import academy as academy_repo
from repositories import collections as collections_repo
from repositories import flashcards as flashcards_repo
from repositories import learning as learning_repo
from services import fsrs
from services import study_config as study_config_service

#: Tope de la cola de una sesión (defensivo: una sesión no es un atracón).
QUEUE_MAX = 100

#: Tarjetas del mazo automático y de un mazo manual.
CARD_TYPE_LEXICON = "lexicon"
CARD_TYPE_FLASHCARD = "flashcard"

#: Tope del pegado masivo de tarjetas, y cotas de cada lado. Son los mismos
#: límites que valida `FlashcardCardIn` en el alta de una en una: el pegado no
#: puede colar lo que la pantalla rechaza de una tarjeta suelta.
CARDS_BULK_MAX = 200
MAX_CARD_FRONT = 400
MAX_CARD_BACK = 2000
#: V3.86.0: tope del recordatorio (mnemónico). Es una frase corta, no un texto.
MAX_CARD_MNEMONIC = 400
#: V3.86.0: tope de mazos a los que se puede asociar una ficha de una vez.
MAX_CARD_DECKS = 30

AUTO_DECK_NAME = "My dictionary"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_prefix() -> str:
    """Día UTC en `YYYY-MM-DD`. Mismo criterio que `_now()`: la app es local,
    pero toda la BD guarda ISO UTC, así que el «hoy» del ledger es el mismo
    «hoy» que el del scheduler y no hay dos calendarios en juego."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


#: V3.87.0: ventana de adelanto del modo `intensive`. Los repasos que vencen
#: dentro de este plazo se sirven ya, SIN tocar su calendario (el `due_at` no se
#: reescribe: solo se presenta antes la oportunidad de repasarlos). V3.87.1:
#: entran en la cola pero NO en `due_count`; se cuentan aparte en
#: `upcoming_count` para no presentar como vencido lo que aún no lo está.
INTENSIVE_HORIZON_HOURS = 24


def _faces(entry: dict, config: dict | None) -> tuple[str, str, str]:
    """`(prompt, answer, hint)` de una entrada según dirección y ayudas (V3.87.0).

    La dirección es PRESENTACIÓN: `front`/`back` siguen siendo la identidad de la
    ficha; lo que cambia es qué cara se pregunta. El `hint` es lo que se puede
    enseñar ANTES de voltear y nunca incluye la respuesta: definición de
    diccionario y/o recordatorio personal, según lo pedido.
    """
    front = str(entry.get("front") or "")
    back = str(entry.get("back") or "")
    if (config or {}).get("direction") == "es-en":
        # ES→EN: se pregunta la traducción y se responde la palabra inglesa. Si
        # el léxico aún no tiene cara B, se cae al inglés para no dejar el prompt
        # vacío (mejor una tarjeta en el sentido contrario que una en blanco).
        prompt, answer = (back or front), front
    else:
        prompt, answer = front, back
    hint_parts: list[str] = []
    if study_config_service.hints_definition(config):
        definition = str(entry.get("definition") or "")
        if definition:
            hint_parts.append(definition)
    if study_config_service.hints_mnemonic(config):
        mnemonic = str(entry.get("mnemonic") or "")
        if mnemonic:
            hint_parts.append(mnemonic)
    return prompt, answer, "\n".join(hint_parts)


def _difficulty_new_cap(new_per_day: int, difficulty: str) -> int:
    """Techo de nuevas según la carga pedida (V3.87.0).

    `gentle` reduce a la mitad (sin bajar de una si el mazo admite nuevas) para
    que «suave» signifique algo; `intensive` no amplía el techo de nuevas (lo que
    amplía es la ventana de repasos, en `deck_queue`), porque el tope de nuevas
    protege del atracón que el propio alumno configuró.
    """
    if difficulty == "gentle" and new_per_day > 0:
        return max(1, new_per_day // 2)
    return new_per_day



def _auto_deck() -> dict:
    """Ficha del mazo automático. Es VIRTUAL: no existe como fila.

    Al no ser una fila no hay que sembrarlo, no se puede borrar y no puede
    quedar desincronizado del léxico. Su `id` es 0 y se reserva a propósito.
    """
    return {
        "id": flashcards_repo.AUTO_DECK_ID,
        "name": AUTO_DECK_NAME,
        "slug": "auto",
        "is_auto": True,
        "new_per_day": flashcards_repo.DEFAULT_NEW_PER_DAY,
        "review_per_day": flashcards_repo.DEFAULT_REVIEW_PER_DAY,
        "card_count": 0,
        "due_count": 0,
        "new_count": 0,
    }


async def _lexicon_cards(user_id: str) -> list[dict]:
    """Cartas `lexicon` del alumno, sembradas antes de leerlas.

    Se llama a `sync_fsrs_cards` (import perezoso: `domain.academy` es enorme y
    no debe acoplarse en tiempo de import) porque las palabras que llegan por
    currículum, chat o producción no tienen carta hasta que alguien sincroniza.
    Depender de que el alumno abra el panel de REVISAR para que su léxico
    aparezca en el mazo automático sería un mazo que no enseña lo que promete.
    """
    from domain import academy as academy_domain

    cards = await academy_domain.sync_fsrs_cards(user_id, now=_now())
    return [c for c in cards if (c.get("target_type") or "") == CARD_TYPE_LEXICON]


async def _manual_cards(user_id: str, deck_id: int) -> list[dict]:
    """Cartas manuales de un mazo, cada una con su carta FSRS (si la tiene)."""
    rows = await run_in_threadpool(flashcards_repo.list_cards, user_id, deck_id)
    if not rows:
        return []
    ids = [str(r["id"]) for r in rows]
    scheduled = await run_in_threadpool(
        academy_repo.fsrs_cards_by_ids, user_id, CARD_TYPE_FLASHCARD, ids
    )
    cards: list[dict] = []
    for row in rows:
        key = str(row["id"])
        card = scheduled.get(key)
        if card is None:
            card = fsrs.empty_card(
                target_type=CARD_TYPE_FLASHCARD,
                target_id=key,
                label=row["front"],
                why=fsrs.why_for_flashcard(),
                now=_now(),
            )
        cards.append(
            {
                "card_type": CARD_TYPE_FLASHCARD,
                "card_id": key,
                "front": row["front"],
                "back": row["back"],
                # V3.86.0: el recordatorio viaja con la ficha hasta el reverso de
                # la sesión; el léxico no lo tiene (vive en la ficha manual).
                "mnemonic": row.get("mnemonic") or "",
                "definition": "",
                "card": card,
            }
        )
    return cards


def _lexicon_entry(word: str, card: dict | None, mnemonic: str) -> dict:
    """Una palabra del diccionario, con SU carta FSRS (nunca una ficha paralela)."""
    key = word.strip().lower()
    scheduled = card
    if scheduled is None:
        scheduled = fsrs.empty_card(
            target_type=CARD_TYPE_LEXICON,
            target_id=key,
            label=key,
            why=fsrs.why_for_flashcard(),
            now=_now(),
        )
    return {
        "card_type": CARD_TYPE_LEXICON,
        "card_id": key,
        "front": key,
        "back": "",
        "mnemonic": mnemonic,
        "definition": "",
        "card": scheduled,
    }


async def _deck_entries(
    user_id: str,
    deck_id: int,
    *,
    lexicon: list[dict] | None = None,
) -> list[dict]:
    """Tarjetas del mazo en la forma común de la cola, SIN la cara B del léxico.

    Forma común: `card_type`, `card_id`, `front`, `back` (y `definition` cuando
    existe). Es lo que permite que `StudySession` no sepa si está enseñando una
    palabra del léxico o una nota escrita a mano.

    La cara B del léxico se resuelve MÁS TARDE, solo para los ítems que entran
    de verdad en la sesión: son dos consultas por palabra y resolverlas para los
    cientos de palabras del léxico solo para descartarlas después era trabajo
    tirado (y el mazo automático tiene el léxico entero).

    Un mazo manual es una pertenencia. Si la palabra ya está en el diccionario
    del alumno, la cola sirve la carta `lexicon` (la misma que «todo el
    diccionario»), no una segunda ficha FSRS. El recordatorio sale de esa
    palabra.
    """
    from repositories import vocabulary as vocabulary_repo

    mnemonics = await run_in_threadpool(vocabulary_repo.mnemonic_by_word, user_id)
    if lexicon is None:
        lexicon = await _lexicon_cards(user_id)
    by_word = {
        str(card.get("target_id") or ""): card
        for card in lexicon
        if card.get("target_id")
    }
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        return [
            _lexicon_entry(word, card, mnemonics.get(word, ""))
            for word, card in by_word.items()
        ]
    known = await run_in_threadpool(vocabulary_repo.words_of, user_id)
    linked = await run_in_threadpool(
        flashcards_repo.lexicon_words_in_deck, user_id, deck_id
    )
    manual = await _manual_cards(user_id, deck_id)
    entries: list[dict] = []
    seen: set[str] = set()
    for entry in manual:
        word = str(entry.get("front") or "").strip().lower()
        if word and word in known:
            phrase = mnemonics.get(word) or str(entry.get("mnemonic") or "")
            entries.append(_lexicon_entry(word, by_word.get(word), phrase))
            seen.add(word)
        else:
            entries.append(entry)
    for word in linked:
        if word in seen or word not in known:
            continue
        entries.append(
            _lexicon_entry(word, by_word.get(word), mnemonics.get(word, ""))
        )
        seen.add(word)
    return entries


async def _with_face(entry: dict, user_id: str) -> dict:
    """Completa la cara B de una tarjeta del léxico (traducción y definición)."""
    if entry["card_type"] != CARD_TYPE_LEXICON or entry["back"]:
        return entry
    face = await run_in_threadpool(
        retention_domain.card_face, user_id, entry["card_id"], None
    )
    return {
        **entry,
        "back": face["translation"],
        "definition": face["definition"],
    }


def _split(
    cards: list[dict], studied: set[tuple[str, str]]
) -> tuple[list[dict], list[dict]]:
    """Separa repasos de tarjetas NUEVAS, en el orden en que se sirven.

    «Nueva» significa **nunca calificada en esta superficie**, leído del ledger
    (`studied_cards`), no del `reps` del scheduler. La diferencia importa: la
    siembra de retención marca `reps = 1` en las cartas que deriva de la
    evidencia de las lecciones, así que una palabra recién añadida por el alumno
    puede llegar con `reps = 1` y una `due_at` de dentro de diez horas —clasificada
    por `reps` desaparecería del mazo en vez de ofrecerse como nueva—. Con el
    ledger, «nueva» es lo que el alumno entiende por nueva, y el tope de nuevas
    del día se aplica a lo que de verdad no ha trabajado.
    """
    reviews: list[dict] = []
    fresh: list[dict] = []
    for entry in cards:
        key = (entry["card_type"], str(entry["card_id"]))
        (reviews if key in studied else fresh).append(entry)
    return reviews, fresh


async def _due_entries(
    user_id: str,
    deck_id: int,
    *,
    collection_id: int | None = None,
    level: str | None = None,
) -> tuple[list[dict], list[dict], list[dict], set[tuple[str, str]]]:
    """Devuelve `(vencidas, próximas 24 h, nuevas, ya estudiadas)`.

    Las «próximas» son repasos YA estudiados que aún no vencen pero vencen dentro
    de `INTENSIVE_HORIZON_HOURS`; solo las consume el modo `intensive`. Se separan
    de las vencidas para que el modo normal (`auto`) siga sirviendo exactamente lo
    mismo que antes de V3.87.0.
    """
    cards = await _deck_entries(user_id, deck_id)
    studied = await run_in_threadpool(flashcards_repo.studied_cards, user_id)
    if collection_id is not None and deck_id == flashcards_repo.AUTO_DECK_ID:
        allowed = await run_in_threadpool(
            collections_repo.words_in_collection, user_id, collection_id
        )
        cards = [c for c in cards if c["card_id"] in allowed]
    code = str(level or "").strip().upper()
    if code and code != "ALL" and deck_id == flashcards_repo.AUTO_DECK_ID:
        from repositories import vocabulary as vocabulary_repo

        cefrs = await run_in_threadpool(vocabulary_repo.cefr_by_word, user_id)
        cards = [
            c
            for c in cards
            if str(cefrs.get(c["card_id"], "")).strip().upper() == code
        ]
    reviews, fresh = _split(cards, studied)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    horizon = (now + timedelta(hours=INTENSIVE_HORIZON_HOURS)).isoformat()
    due: list[dict] = []
    upcoming: list[dict] = []
    for entry in reviews:
        if fsrs.is_due(entry["card"], now=now_iso):
            due.append(entry)
            continue
        due_at = str((entry["card"] or {}).get("due_at") or "")
        if due_at and due_at <= horizon:
            upcoming.append(entry)
    return due, upcoming, fresh, studied


async def list_decks(user_id: str) -> dict:
    """Mazo automático + mazos manuales, con lo que queda por hacer HOY.

    `due_count` y `new_count` van recortados por los límites del día: son lo que
    la sesión va a servir de verdad, no lo que hay en el mazo. Un mazo con 400
    palabras sin estudiar y un tope de 10 nuevas no debe anunciar «400», porque
    el alumno no las va a ver hoy. El total de tarjetas va aparte, en
    `card_count`.
    """
    day = _today_prefix()
    now_iso = _now()
    # Los temas entran en el diccionario antes de contar, para que el primer
    # listado ya traiga sus palabras y sus mazos.
    await retention_domain.ensure_theme_pack_decks(user_id)
    lexicon = await _lexicon_cards(user_id)
    studied = await run_in_threadpool(flashcards_repo.studied_cards, user_id)
    auto_state = await run_in_threadpool(
        flashcards_repo.day_state, user_id, day, flashcards_repo.AUTO_DECK_ID
    )
    auto = _auto_deck()
    auto.update(
        _today_counts(
            [
                {
                    "card_type": CARD_TYPE_LEXICON,
                    "card_id": str(c.get("target_id") or ""),
                    "card": c,
                }
                for c in lexicon
            ],
            studied=studied,
            state=auto_state,
            new_per_day=auto["new_per_day"],
            review_per_day=auto["review_per_day"],
            now_iso=now_iso,
        )
    )
    auto["card_count"] = len(lexicon)
    auto["learned_count"] = sum(
        1 for card in lexicon if str(card.get("state") or "") == "review"
    )

    coll_rows = await run_in_threadpool(collections_repo.list_collections, user_id)
    slug_of = {
        int(item["id"]): str(item.get("slug") or "")
        for item in coll_rows
        if str(item.get("kind") or "") == "theme_pack"
    }
    rows = await run_in_threadpool(flashcards_repo.list_decks, user_id)
    counts = await run_in_threadpool(flashcards_repo.count_cards, user_id)
    shared = await run_in_threadpool(flashcards_repo.shared_cards_by_deck, user_id)
    decks = []
    for row in rows:
        deck_id = int(row["id"])
        state = await run_in_threadpool(
            flashcards_repo.day_state, user_id, day, deck_id
        )
        cards = await _deck_entries(user_id, deck_id, lexicon=lexicon)
        source = row.get("source_collection_id")
        deck = {
            "id": deck_id,
            "name": row["name"],
            "slug": slug_of.get(int(source), "") if source else "",
            "is_auto": False,
            "source_collection_id": row.get("source_collection_id"),
            "new_per_day": int(row["new_per_day"]),
            "review_per_day": int(row["review_per_day"]),
        }
        deck.update(
            _today_counts(
                cards,
                studied=studied,
                state=state,
                new_per_day=int(row["new_per_day"]),
                review_per_day=int(row["review_per_day"]),
                now_iso=now_iso,
            )
        )
        deck["card_count"] = len(cards) or counts.get(deck_id, 0)
        deck["learned_count"] = sum(
            1
            for entry in cards
            if str((entry.get("card") or {}).get("state") or "") == "review"
        )
        # V3.86.0: cuántas de esas fichas sobrevivirán al borrar el mazo por
        # estar también en otro. Es lo que hace honesto el aviso de borrado.
        deck["shared_count"] = shared.get(deck_id, 0)
        decks.append(deck)
    decks.sort(key=lambda d: d["name"].casefold())
    return {
        "decks": [auto, *decks],
        "auto_deck_id": flashcards_repo.AUTO_DECK_ID,
        "fsrs_version": fsrs.FSRS_VERSION,
    }


def _today_counts(
    cards: list[dict],
    *,
    studied: set[tuple[str, str]],
    state: dict,
    new_per_day: int,
    review_per_day: int,
    now_iso: str,
) -> dict:
    """Contadores de hoy de un mazo, ya recortados por sus límites.

    Función pura y compartida por el mazo automático y los manuales: si hubiera
    dos copias, la automática y la manual podrían contestar cosas distintas a la
    misma pregunta («¿cuántas me quedan hoy?»).
    """
    reviews, fresh = _split(cards, studied)
    due = [c for c in reviews if fsrs.is_due(c["card"], now=now_iso)]
    new_remaining = max(0, int(new_per_day) - int(state["new"]))
    review_remaining = max(0, int(review_per_day) - int(state["reviews"]))
    return {
        "due_count": min(len(due), review_remaining),
        "new_count": min(len(fresh), new_remaining),
        "reviewed_today": int(state["reviews"]),
        "limits": {
            "new_remaining": new_remaining,
            "review_remaining": review_remaining,
        },
    }


async def create_deck(
    user_id: str,
    *,
    name: str,
    new_per_day: int | None = None,
    review_per_day: int | None = None,
) -> dict | None:
    row = await run_in_threadpool(
        partial(
            flashcards_repo.create_deck,
            user_id,
            name=name,
            new_per_day=new_per_day,
            review_per_day=review_per_day,
        )
    )
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "is_auto": False,
        "new_per_day": int(row["new_per_day"]),
        "review_per_day": int(row["review_per_day"]),
        "card_count": 0,
        "due_count": 0,
        "new_count": 0,
    }


async def update_deck(
    user_id: str,
    deck_id: int,
    *,
    name: str | None = None,
    new_per_day: int | None = None,
    review_per_day: int | None = None,
) -> dict | None:
    """Edita un mazo manual. El automático no se edita: es una vista del léxico."""
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        return None
    row = await run_in_threadpool(
        partial(
            flashcards_repo.update_deck,
            user_id,
            deck_id,
            name=name,
            new_per_day=new_per_day,
            review_per_day=review_per_day,
        )
    )
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "is_auto": False,
        "new_per_day": int(row["new_per_day"]),
        "review_per_day": int(row["review_per_day"]),
    }


async def delete_deck(user_id: str, deck_id: int) -> dict | None:
    """Borra un mazo manual conservando las fichas COMPARTIDAS (V3.86.0).

    Borra primero las cartas FSRS de las fichas que quedan HUÉRFANAS (las que
    solo vivían en este mazo) y devuelve `{"deleted_count", "shared_count"}`; la
    ficha compartida sobrevive y solo pierde la pertenencia. Antes se borraba
    todo lo que apuntara al mazo, que con la tabla puente destruiría fichas de
    otros mazos.
    """
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        return None
    current = await run_in_threadpool(flashcards_repo.get_deck, user_id, deck_id)
    if current is None:
        return None
    # Un tema sale del diccionario: borrarlo lo volvería a crear al listar.
    if current.get("source_collection_id"):
        return {"refused": True}
    # La lista de huérfanas se recolecta ANTES de borrar (el repo la devuelve en
    # la misma transacción), para no dejar cartas FSRS de fichas ya inexistentes.
    result = await run_in_threadpool(flashcards_repo.delete_deck, user_id, deck_id)
    if result is None:
        return None
    for card_id in result["deleted_card_ids"]:
        await run_in_threadpool(
            academy_repo.delete_fsrs_card, user_id, CARD_TYPE_FLASHCARD, str(card_id)
        )
    return {
        "deleted_count": len(result["deleted_card_ids"]),
        "shared_count": int(result["shared"]),
    }


async def list_cards(user_id: str, deck_id: int) -> list[dict]:
    """Tarjetas de un mazo manual con su estado FSRS y sus mazos (V3.86.0)."""
    rows = await run_in_threadpool(flashcards_repo.list_cards, user_id, deck_id)
    return await _cards_out(user_id, rows)


async def list_all_cards(user_id: str) -> list[dict]:
    """Todas las fichas manuales del alumno, con sus mazos (V3.86.0)."""
    rows = await run_in_threadpool(flashcards_repo.list_all_cards, user_id)
    return await _cards_out(user_id, rows)


async def _cards_out(user_id: str, rows: list[dict]) -> list[dict]:
    """Fichas con estado FSRS y el conjunto de mazos a los que pertenecen."""
    if not rows:
        return []
    ids = [str(r["id"]) for r in rows]
    scheduled = await run_in_threadpool(
        academy_repo.fsrs_cards_by_ids, user_id, CARD_TYPE_FLASHCARD, ids
    )
    memberships = await run_in_threadpool(
        flashcards_repo.deck_ids_for_cards, user_id, [r["id"] for r in rows]
    )
    out = []
    for row in rows:
        card = scheduled.get(str(row["id"])) or {}
        out.append(
            {
                "id": int(row["id"]),
                "deck_id": int(row["deck_id"]),
                "deck_ids": memberships.get(int(row["id"]), []),
                "front": row["front"],
                "back": row["back"],
                "mnemonic": row.get("mnemonic") or "",
                "state": str(card.get("state") or "new"),
                "reps": int(card.get("reps") or 0),
                "due_at": str(card.get("due_at") or ""),
                "created_at": row["created_at"],
            }
        )
    return out


def _clean_deck_ids(deck_ids: list[int] | None, deck_id: int | None) -> list[int]:
    """Unifica el contrato nuevo (`deck_ids`) y el viejo (`deck_id`)."""
    if deck_ids:
        return [int(d) for d in deck_ids][:MAX_CARD_DECKS]
    if deck_id is not None:
        return [int(deck_id)]
    return []


async def create_card(
    user_id: str,
    deck_id: int | None = None,
    *,
    front: str,
    back: str = "",
    mnemonic: str = "",
    deck_ids: list[int] | None = None,
) -> dict | None:
    """Crea una ficha en uno o varios mazos manuales (V3.86.0).

    Acepta el contrato viejo (`deck_id`) y el nuevo (`deck_ids`). Nunca en el
    mazo automático (es el léxico y no admite notas a mano) ni sin mazo: una
    ficha sin mazo no existe.
    """
    targets = _clean_deck_ids(deck_ids, deck_id)
    if not targets or flashcards_repo.AUTO_DECK_ID in targets:
        return None
    row = await run_in_threadpool(
        partial(
            flashcards_repo.create_card,
            user_id,
            front=front,
            back=back[:MAX_CARD_BACK],
            mnemonic=mnemonic[:MAX_CARD_MNEMONIC],
            deck_ids=targets,
        )
    )
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def add_cards_bulk(
    user_id: str, deck_id: int, *, text: str
) -> dict | None:
    """Pega una lista de tarjetas en un mazo manual (V3.80.0).

    Una entrada por línea, `anverso,reverso` (coma o tabulador), con el MISMO
    parser que el pegado de palabras del léxico (`retention.parse_bulk_lines`):
    el alumno pega lo mismo en las dos pantallas, así que la sintaxis tiene que
    ser la misma o la app le obligaría a recordar dos formatos. V3.86.0 admite un
    tercer campo OPCIONAL con el **recordatorio** (`anverso,reverso,recordatorio`).

    `None` si el mazo no es del usuario o es el automático (que no admite
    tarjetas escritas a mano, igual que `create_card`). Devuelve
    `{deck_id, added, count}`; `added` son los anversos que entraron de verdad,
    que es lo que la UI cuenta —no lo que se intentó pegar.
    """
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        return None
    if await run_in_threadpool(flashcards_repo.get_deck, user_id, deck_id) is None:
        return None

    cards: list[dict] = []
    seen: set[str] = set()
    for parts in retention_domain.parse_bulk_fields(text, max_fields=3):
        left = parts[0] if parts else ""
        right = parts[1] if len(parts) > 1 else ""
        mnemonic = parts[2] if len(parts) > 2 else ""
        # El anverso se colapsa como en `create_card` (espacios internos), y el
        # deduplicado es por esa forma: pegar dos veces la misma línea no debe
        # crear dos tarjetas que el alumno no puede distinguir.
        front = " ".join(left.split())[:MAX_CARD_FRONT]
        if not front or front.casefold() in seen:
            continue
        seen.add(front.casefold())
        cards.append(
            {
                "front": front,
                "back": right[:MAX_CARD_BACK],
                "mnemonic": mnemonic[:MAX_CARD_MNEMONIC],
            }
        )
        if len(cards) >= CARDS_BULK_MAX:
            break

    if not cards:
        return {"deck_id": int(deck_id), "added": [], "count": 0}

    created = await run_in_threadpool(
        flashcards_repo.create_cards, user_id, deck_id, cards
    )
    return {
        "deck_id": int(deck_id),
        "added": [row["front"] for row in created],
        "count": len(created),
    }


async def update_card(
    user_id: str,
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    mnemonic: str | None = None,
) -> dict | None:
    """Edita anverso/reverso/recordatorio de una ficha (V3.86.0, parcial).

    Un parámetro `None` significa «no lo cambies»: así editar SOLO el recordatorio
    (o borrarlo con `""`) no obliga a reenviar el anverso. El id de ficha es
    global del usuario (IDOR: se busca por `user_id`), ya no cuelga de un mazo.
    """
    if front is not None:
        front = " ".join(front.split())[:MAX_CARD_FRONT]
        if not front:
            return None
    if back is not None:
        back = back[:MAX_CARD_BACK]
    if mnemonic is not None:
        mnemonic = mnemonic[:MAX_CARD_MNEMONIC]
    row = await run_in_threadpool(
        partial(
            flashcards_repo.update_card,
            user_id,
            card_id,
            front=front,
            back=back,
            mnemonic=mnemonic,
        )
    )
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def update_card_with_decks(
    user_id: str,
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    mnemonic: str | None = None,
    deck_ids: list[int] | None = None,
) -> dict | None:
    """Edita la ficha y/o reemplaza sus mazos en UNA sola operación (V3.86.1).

    Mismos topes y saneado que `update_card`, pero ATÓMICO con los mazos: o se
    aplica el PATCH entero o no se aplica nada. Sustituye a la secuencia
    `update_card` + `set_card_decks` que dejaba el recordatorio escrito aunque los
    mazos fueran inválidos. `deck_ids = None` no toca las pertenencias.
    """
    if front is not None:
        front = " ".join(front.split())[:MAX_CARD_FRONT]
        if not front:
            return None
    if back is not None:
        back = back[:MAX_CARD_BACK]
    if mnemonic is not None:
        mnemonic = mnemonic[:MAX_CARD_MNEMONIC]
    targets: list[int] | None = None
    if deck_ids is not None:
        targets = [int(d) for d in deck_ids][:MAX_CARD_DECKS]
    row = await run_in_threadpool(
        partial(
            flashcards_repo.update_card_with_decks,
            user_id,
            card_id,
            front=front,
            back=back,
            mnemonic=mnemonic,
            deck_ids=targets,
        )
    )
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def set_card_decks(
    user_id: str, card_id: int, deck_ids: list[int]
) -> dict | None:
    """Reemplaza los mazos de una ficha (V3.86.0). `None` si algo no es suyo."""
    if not deck_ids:
        return None
    owned = await run_in_threadpool(
        flashcards_repo.set_card_decks,
        user_id,
        card_id,
        [int(d) for d in deck_ids][:MAX_CARD_DECKS],
    )
    if owned is None:
        return None
    row = await run_in_threadpool(flashcards_repo.get_card, user_id, card_id)
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def add_card_to_deck(
    user_id: str, card_id: int, deck_id: int
) -> dict | None:
    """Añade una pertenencia sin tocar las demás (V3.86.0)."""
    if await run_in_threadpool(
        flashcards_repo.add_card_to_deck, user_id, card_id, deck_id
    ) is None:
        return None
    row = await run_in_threadpool(flashcards_repo.get_card, user_id, card_id)
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def remove_card_from_deck(
    user_id: str, card_id: int, deck_id: int
) -> dict | None:
    """Quita una pertenencia. Si era la ÚLTIMA, la ficha se borra (V3.86.0).

    Una ficha sin mazo no existe en este modelo (el FK `deck_id` exige un mazo
    real), así que quitar la última pertenencia equivale a borrar la ficha; se
    devuelve `{"deleted": True, "card_id": id}` para que la UI lo diga.
    """
    if await run_in_threadpool(
        flashcards_repo.get_card, user_id, card_id
    ) is None:
        return None
    remaining = await run_in_threadpool(
        flashcards_repo.remove_card_from_deck, user_id, card_id, deck_id
    )
    if remaining is None:
        return None
    if not remaining:
        await delete_card(user_id, card_id)
        return {"deleted": True, "card_id": int(card_id), "deck_ids": []}
    row = await run_in_threadpool(flashcards_repo.get_card, user_id, card_id)
    if row is None:
        return None
    out = await _cards_out(user_id, [row])
    return out[0] if out else None


async def card_belongs_to_deck(user_id: str, card_id: int, deck_id: int) -> bool:
    """Membresía de una ficha en un mazo (para los envoltorios legacy)."""
    decks = await run_in_threadpool(flashcards_repo.decks_for_card, user_id, card_id)
    return int(deck_id) in decks


async def delete_card(user_id: str, card_id: int) -> bool:
    """Borra la tarjeta y su carta FSRS, en ese orden y con la carta devuelta."""
    deleted = await run_in_threadpool(flashcards_repo.delete_card, user_id, card_id)
    if deleted is None:
        return False
    await run_in_threadpool(
        academy_repo.delete_fsrs_card, user_id, CARD_TYPE_FLASHCARD, str(deleted["id"])
    )
    return True


async def deck_queue(
    user_id: str,
    deck_id: int,
    *,
    collection_id: int | None = None,
    level: str | None = None,
    limit: int = QUEUE_MAX,
) -> dict | None:
    """Cola de estudio de un mazo, ya recortada por los límites del día.

    Orden: primero los repasos vencidos y después las nuevas. Es el orden clásico
    de Anki y además el que respeta el dinero del alumno —lo que ya se sabe y se
    está olvidando va antes que lo que nunca ha visto—.

    V3.87.1: en `intensive` los repasos que vencen en ≤ 24 h (`upcoming`) se
    SIRVEN (sin reescribir su `due_at`) pero se cuentan APARTE, para que la UI no
    presente como vencido lo que aún no lo está: `due_count` = vencidas reales,
    `upcoming_count` = adelantos voluntarios (0 fuera de `intensive`) y
    `queue_count` = lo que la cola sirve de verdad (vencidas + adelantos).
    """
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        deck = _auto_deck()
        new_per_day = flashcards_repo.DEFAULT_NEW_PER_DAY
        review_per_day = flashcards_repo.DEFAULT_REVIEW_PER_DAY
    else:
        row = await run_in_threadpool(flashcards_repo.get_deck, user_id, deck_id)
        if row is None:
            return None
        deck = {
            "id": int(row["id"]),
            "name": row["name"],
            "is_auto": False,
            "new_per_day": int(row["new_per_day"]),
            "review_per_day": int(row["review_per_day"]),
        }
        new_per_day = int(row["new_per_day"])
        review_per_day = int(row["review_per_day"])

    state = await run_in_threadpool(
        flashcards_repo.day_state, user_id, _today_prefix(), deck_id
    )
    due, upcoming, fresh, _studied = await _due_entries(
        user_id, deck_id, collection_id=collection_id, level=level
    )

    # V3.87.0: la configuración de estudio matiza la sesión. `intensive` ensancha
    # la ventana (repasos que vencen en 24 h) SIN reescribir ningún `due_at`;
    # `gentle` recorta el techo de nuevas. `auto` (el defecto) no toca nada: la
    # cola de un alumno sin configurar es EXACTAMENTE la de V3.86.1.
    #
    # V3.87.1: `due` son SIEMPRE las vencidas y `upcoming` los adelantos de
    # `intensive`; se sirven juntos pero se cuentan por separado (`due_count` /
    # `upcoming_count`) para no mezclar «vencido» con «vence en ≤ 24 h».
    study = await study_config_domain.get_study_config(user_id)
    config = study["config"]
    difficulty = config.get("difficulty") or "auto"
    intensive = difficulty == "intensive"
    served_reviews = due + upcoming if intensive else due
    effective_new_per_day = _difficulty_new_cap(new_per_day, difficulty)

    new_remaining = max(0, effective_new_per_day - state["new"])
    review_remaining = max(0, review_per_day - state["reviews"])
    taken_reviews = [
        {**c, "is_new": False} for c in served_reviews[:review_remaining]
    ]
    taken_new = [
        {**c, "is_new": True}
        for c in fresh[: min(new_remaining, max(0, limit - len(taken_reviews)))]
    ]
    selected = (taken_reviews + taken_new)[: max(1, min(limit, QUEUE_MAX))]

    now_iso = _now()
    items = []
    for entry in selected:
        entry = await _with_face(entry, user_id)
        card = entry["card"] or {}
        explained = fsrs.explain(card, now=now_iso)
        prompt, answer, hint = _faces(entry, config)
        items.append(
            {
                "card_type": entry["card_type"],
                "card_id": entry["card_id"],
                "front": entry["front"],
                "back": entry["back"],
                "definition": entry.get("definition") or "",
                # V3.86.0: recordatorio de la ficha manual ("" en el léxico). La
                # sesión lo pinta en el reverso; no altera el planificador.
                "mnemonic": entry.get("mnemonic") or "",
                # V3.87.0: cara preguntada/respuesta según la dirección y ayuda
                # previa al volteo. Aditivo: `front`/`back` (la identidad) siguen.
                "prompt": prompt,
                "answer": answer,
                "hint": hint,
                # `is_new` sale del ledger (`_split`), no de `reps`: ver el
                # comentario de `_split` para por qué no son lo mismo.
                "is_new": bool(entry["is_new"]),
                "state": str(card.get("state") or "new"),
                "due_at": str(card.get("due_at") or ""),
                "reps": int(card.get("reps") or 0),
                "retrievability": float(
                    explained.get("how_strong", {}).get("retrievability") or 0
                ),
            }
        )
    return {
        "deck": deck,
        "items": items,
        # V3.87.1: `due_count` = vencidas REALES (siempre); `upcoming_count` =
        # adelantos voluntarios de `intensive` (≤ 24 h, sin tocar su calendario),
        # 0 en el resto; `queue_count` = vencidas + adelantos (candidatas de
        # repaso antes del tope diario).
        "due_count": len(due),
        "upcoming_count": len(upcoming) if intensive else 0,
        "queue_count": len(served_reviews),
        "new_count": len(fresh),
        "reviewed_today": state["reviews"],
        "new_today": state["new"],
        "limits": {
            "new_per_day": effective_new_per_day,
            "review_per_day": review_per_day,
            "new_remaining": new_remaining,
            "review_remaining": review_remaining,
        },
        "fsrs_version": fsrs.FSRS_VERSION,
        # La sesión conoce así la dirección/modo/ayudas con los que se construyó
        # la cola, en la misma respuesta y sin una segunda llamada.
        "study_config": {**config, "configured": bool(study["configured"])},
    }


async def _review_manual(
    user_id: str, card_id: int, grade: int
) -> dict | None:
    """Califica una tarjeta manual: su carta FSRS es `flashcard:<id>`."""
    row = await run_in_threadpool(flashcards_repo.get_card, user_id, card_id)
    if row is None:
        return None
    key = str(row["id"])
    card = await run_in_threadpool(
        academy_repo.get_fsrs_card, user_id, CARD_TYPE_FLASHCARD, key
    )
    if card is None:
        card = fsrs.empty_card(
            target_type=CARD_TYPE_FLASHCARD,
            target_id=key,
            label=row["front"],
            why=fsrs.why_for_flashcard(),
            now=_now(),
        )
    updated = fsrs.schedule(card, grade, now=_now())
    saved = await run_in_threadpool(
        academy_repo.upsert_fsrs_card, user_id, updated
    )
    if saved is None:
        return None
    explained = fsrs.explain(saved, now=_now())
    return {
        "card_type": CARD_TYPE_FLASHCARD,
        "card_id": key,
        "deck_id": int(row["deck_id"]),
        "front": row["front"],
        "back": row["back"],
        "grade": grade,
        "due_at": saved.get("due_at") or "",
        "next_in_days": float(explained.get("when", {}).get("next_in_days") or 0),
        "stability": float(saved.get("stability") or 0),
        "retrievability": float(
            explained.get("how_strong", {}).get("retrievability") or 0
        ),
        "reps": int(saved.get("reps") or 0),
    }


async def review_card(
    user_id: str, deck_id: int, card_type: str, card_id: str, grade: int
) -> dict | None:
    """Califica una tarjeta del mazo y anota la revisión en el ledger.

    El léxico NO se reagenda aquí: se delega en `retention_review`, que ya es el
    dueño de esa carta (`lexicon:<word>`) y de su evento. Tener un segundo
    escritor de la misma carta sería exactamente el doble escritor que M4 cerró
    para los objetivos.
    """
    if grade not in fsrs.GRADES:
        return None

    # Se lee ANTES de calificar: `was_new` es «no había ninguna revisión previa
    # de esta tarjeta», que es la definición que usan los límites del día y las
    # estadísticas. Después de insertar la fila ya no se puede saber.
    studied = await run_in_threadpool(flashcards_repo.studied_cards, user_id)

    if card_type == CARD_TYPE_LEXICON:
        out = await retention_domain.retention_review(user_id, card_id, grade)
        if out is None:
            return None
        resolved = {
            "card_type": CARD_TYPE_LEXICON,
            "card_id": out["word"],
            "deck_id": flashcards_repo.AUTO_DECK_ID,
            "front": out["word"],
            "back": "",
            "grade": grade,
            "due_at": out["due_at"],
            "next_in_days": out["next_in_days"],
            "stability": out["stability"],
            "retrievability": out["retrievability"],
            "reps": out["reps"],
        }
    elif card_type == CARD_TYPE_FLASHCARD:
        # IDOR: la tarjeta se busca POR USUARIO. Además se comprueba que la ficha
        # PERTENEZCA al mazo que el cliente dice (con la tabla puente ya no basta
        # con que sea su `deck_id` principal), para que la revisión no contamine
        # el ledger de otro mazo.
        row = await run_in_threadpool(flashcards_repo.get_card, user_id, int(card_id))
        if row is None or not await card_belongs_to_deck(
            user_id, int(card_id), int(deck_id)
        ):
            return None
        resolved = await _review_manual(user_id, int(card_id), grade)
        if resolved is None:
            return None
        # El ledger apunta al mazo DESDE EL QUE se estudió, no al principal: los
        # límites diarios son por mazo y una ficha compartida debe contar donde
        # se repasó.
        resolved["deck_id"] = int(deck_id)
    else:
        return None

    await run_in_threadpool(
        partial(
            flashcards_repo.record_review,
            user_id,
            deck_id=resolved["deck_id"],
            card_type=resolved["card_type"],
            card_id=resolved["card_id"],
            grade=grade,
            was_new=(resolved["card_type"], resolved["card_id"]) not in studied,
        )
    )
    if resolved["card_type"] == CARD_TYPE_FLASHCARD:
        # El léxico ya escribe su evento dentro de `retention_review`; la tarjeta
        # manual escribe el suyo aquí. Mismo rol informativo (evidence.py).
        await run_in_threadpool(
            learning_repo.record_event,
            user_id,
            "exercise",
            f"flashcard:{resolved['card_id']}:{grade}",
        )
    return resolved


async def deck_stats(user_id: str, deck_id: int) -> dict | None:
    """Estadísticas del mazo: hoy, total, acierto, 14 días y previsión a 7."""
    if deck_id == flashcards_repo.AUTO_DECK_ID:
        deck = _auto_deck()
    else:
        row = await run_in_threadpool(flashcards_repo.get_deck, user_id, deck_id)
        if row is None:
            return None
        deck = {
            "id": int(row["id"]),
            "name": row["name"],
            "is_auto": False,
            "new_per_day": int(row["new_per_day"]),
            "review_per_day": int(row["review_per_day"]),
        }
    # La previsión lee `card_type` y `card_id`. El léxico crudo de FSRS no trae
    # esa forma: hay que usar la misma lista que la cola (una carta por palabra).
    cards = await _deck_entries(user_id, deck_id)
    deck["card_count"] = len(cards)
    deck["learned_count"] = sum(
        1
        for entry in cards
        if str((entry.get("card") or {}).get("state") or "") == "review"
    )

    now = datetime.now(timezone.utc)
    day = _today_prefix()
    month_ago = (now - timedelta(days=30)).isoformat()
    fortnight = (now - timedelta(days=13)).strftime("%Y-%m-%d")

    day_state = await run_in_threadpool(
        flashcards_repo.day_state, user_id, day, deck_id
    )
    totals = await run_in_threadpool(
        flashcards_repo.review_totals, user_id, since_iso=month_ago
    )
    by_day = await run_in_threadpool(
        flashcards_repo.reviews_by_day, user_id, since_prefix=fortnight
    )

    # Previsión: cuántas tarjetas YA estudiadas vencen cada uno de los próximos
    # 7 días. Se calcula con `due_at` (el dato que el scheduler ya guarda) y no
    # con una proyección de estabilidad: es lo que el alumno va a ver de verdad.
    # Las nuevas se excluyen porque su `due_at` no anticipa cuándo las estudiará
    # —eso lo decide su plan— y contarlas prometería un día que no depende de
    # ellas.
    studied = await run_in_threadpool(flashcards_repo.studied_cards, user_id)
    forecast: list[dict] = []
    for offset in range(7):
        target = (now + timedelta(days=offset)).strftime("%Y-%m-%d")
        count = sum(
            1
            for entry in cards
            if (entry["card_type"], str(entry["card_id"])) in studied
            and str((entry["card"] or {}).get("due_at") or "").startswith(target)
        )
        forecast.append({"day": target, "count": count})

    accuracy = (
        round(totals["good"] / totals["total"] * 100, 1) if totals["total"] else 0.0
    )
    return {
        "deck": deck,
        "cards_total": len(cards),
        "reviewed_today": day_state["reviews"],
        "new_today": day_state["new"],
        "reviews_30d": totals["total"],
        "new_cards_30d": totals["new_cards"],
        "accuracy_30d": accuracy,
        "by_day": [
            {"day": day_key, **values} for day_key, values in sorted(by_day.items())
        ],
        "forecast": forecast,
    }

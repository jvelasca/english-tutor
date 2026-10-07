"""Banco de Estudiar: de dónde salen las palabras y qué números se ven.

El banco es una vista, no una tabla de artículos. Une el vocabulario declarado
del currículum, los packs temáticos, el léxico del alumno y —cuando una
importación lo rellene— las entradas del diccionario que ya traen nivel CEFR.
El contenido profundo (acepciones, ejemplo, audio) se pide al abrir la palabra.

Los contadores cambian con el ámbito:

- total: tamaño del banco en ese ámbito
- estudiadas: alguna vez calificadas en el libro de repasos
- aprendidas: estado FSRS ``review`` y los pasos obligatorios no están pendientes.
  Es un recuento respecto de ``required_facets`` actual, no un hecho histórico.
- no aprendidas: el resto del ámbito
- a repasar: vencidas según FSRS
- difíciles: la última nota del libro fue Difícil
- bien: la última nota del libro fue Bien
- veces estudiada: filas del libro, sin recorte de 30 días

La cola depende del modo, siempre dentro del ámbito:

- ``pending``: ya estudiadas y vencidas según FSRS
- ``unlearned``: las que aún no cuentan como aprendidas (vencidas primero)
- ``hard``: la última nota fue Difícil (vencidas primero)
- ``good``: la última nota fue Bien (vencidas primero)
- ``failed``: la última nota del libro fue Otra vez
- ``all``: todas las palabras del ámbito (las vencidas primero)

En «Todas» del banco las que no están vencidas se reparten entre niveles. El
tope es ``words_per_day``; en un mazo manual, Pendientes usa además el límite
de repasos del mazo.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from domain import flashcards as flashcards_domain
from domain import retention as retention_domain
from domain import study_config as study_config_domain
from repositories import academy as academy_repo
from repositories import collections as collections_repo
from repositories import dictionary as dictionary_repo
from repositories import flashcards as flashcards_repo
from repositories import study_lessons as study_lessons_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs
from services.cefr import CEFR_LEVELS
from services.curriculum import load_all_levels

_WORD_RE = re.compile(r"^[a-zA-Z][a-zA-Z'\- ]{0,79}$")
_PACKS_DIR = Path(__file__).resolve().parent.parent / "curriculum" / "vocab_packs"
_LEVELS = (*CEFR_LEVELS, "")
FACETS = ("meaning", "pronunciation", "context", "senses", "related")
FACET_STATUSES = ("done", "pending", "na")
SCOPES = ("all", "level", "deck")
MODES = ("pending", "unlearned", "hard", "good", "failed", "all")


def normalize_word(raw: object) -> str | None:
    """Misma superficie que el alta del léxico: minúsculas y sin huecos dobles."""
    text = " ".join(str(raw or "").strip().lower().split())
    if not text or not _WORD_RE.match(text):
        return None
    return text


def parse_scope(raw: object) -> str | None:
    scope = str(raw or "all").strip().lower()
    return scope if scope in SCOPES else None


def parse_mode(raw: object) -> str | None:
    mode = str(raw or "pending").strip().lower()
    return mode if mode in MODES else None


def facet_status_ok(facets: dict, name: str) -> bool:
    """Un paso no bloquea si no consta, está hecho o no aplicaba.

    ``pending`` es lo único que impide contar la palabra cuando ese paso es
    obligatorio. Una palabra aprendida antes de existir la lección no tiene
    JSON: no se le retira el estado por un paso que nadie le pidió.
    """
    status = str((facets or {}).get(name) or "")
    return status in ("", "done", "na")


def is_learned(card: dict | None, facets: dict, required: list[str]) -> bool:
    """Si la carta está en repaso y ningún paso obligatorio sigue pendiente.

    Es un estado derivado de la configuración vigente, no un hecho histórico.
    ``required`` son los ``required_facets`` de ahora: vaciar esa lista puede
    marcar aprendida una palabra sin un repaso nuevo. ``state == review`` no
    basta: faltan el significado y los pasos que el alumno haya exigido.

    Los ``facets`` los afirma el cliente al cerrar la lección. El servidor no
    comprueba que el paso se haya mostrado. Un paso saltado sigue en
    ``pending`` y, si es obligatorio, impide este recuento.
    """
    if not card or str(card.get("state") or "") != "review":
        return False
    if not facet_status_ok(facets, "meaning"):
        return False
    return all(facet_status_ok(facets, name) for name in required)


def merge_facets(stored: dict | None, incoming: dict | None) -> dict[str, str]:
    """Superpone estados válidos. Una clave ausente no borra la que ya había."""
    out: dict[str, str] = {}
    for source in (stored or {}, incoming or {}):
        if not isinstance(source, dict):
            continue
        for name in FACETS:
            status = str(source.get(name) or "")
            if status in FACET_STATUSES:
                out[name] = status
    return out


def interleave_by_level(items: list[dict]) -> list[dict]:
    """Reparte las nuevas entre niveles: una de cada banda, en orden estable.

    Dentro de cada nivel el orden es alfabético, para que la cola no dependa
    del azar del proceso y una sesión «Todas» no se quede en A1.
    """
    buckets: dict[str, list[dict]] = {level: [] for level in _LEVELS}
    for item in items:
        code = str(item.get("cefr") or "").upper()
        buckets[code if code in buckets else ""].append(item)
    for level in buckets:
        buckets[level].sort(key=lambda item: str(item.get("word") or ""))
    out: list[dict] = []
    while any(buckets.values()):
        for level in _LEVELS:
            if buckets[level]:
                out.append(buckets[level].pop(0))
    return out


@lru_cache(maxsize=1)
def course_words() -> dict[str, str]:
    """`palabra → CEFR` del currículum y, si aún no estaba, de los packs."""
    out: dict[str, str] = {}
    for level in load_all_levels():
        code = str(level.level or "").strip().upper()
        if code not in CEFR_LEVELS:
            code = ""
        for objective in level.objectives():
            for raw in objective.vocabulary:
                word = normalize_word(raw)
                if word and word not in out:
                    out[word] = code
    if _PACKS_DIR.is_dir():
        for path in sorted(_PACKS_DIR.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            hint = str(payload.get("cefr_hint") or "").strip().upper()
            if hint not in CEFR_LEVELS:
                hint = ""
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                word = normalize_word(item.get("word"))
                if word and word not in out:
                    out[word] = hint
    return out


def bank_index(user_words: dict[str, str]) -> dict[str, str]:
    """Unión sin duplicar. El CEFR del alumno, si consta, manda sobre el curso."""
    out = dict(course_words())
    for word, cefr in dictionary_repo.cefr_words().items():
        key = normalize_word(word)
        code = str(cefr or "").strip().upper()
        if key and key not in out and code in CEFR_LEVELS:
            out[key] = code
    for word, cefr in user_words.items():
        key = normalize_word(word)
        if not key:
            continue
        code = str(cefr or "").strip().upper()
        if key not in out:
            out[key] = code if code in CEFR_LEVELS else ""
        elif code in CEFR_LEVELS:
            out[key] = code
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cap(words_per_day: int, difficulty: str) -> int:
    if difficulty == "gentle" and words_per_day > 0:
        return max(1, words_per_day // 2)
    return max(1, words_per_day)


def _counts(
    rows: list[dict],
    *,
    cards: dict[str, dict],
    studied: set[tuple[str, str]],
    counts: dict[tuple[str, str], int],
    grades: dict[tuple[str, str], int],
    facets: dict[str, dict],
    required: list[str],
    now_iso: str,
    card_of,
) -> dict[str, int]:
    total = len(rows)
    studied_n = 0
    learned_n = 0
    unlearned_n = 0
    due_n = 0
    hard_n = 0
    good_n = 0
    times = 0
    for row in rows:
        identity = card_of(row)
        word = str(row.get("word") or identity[1])
        if identity in studied:
            studied_n += 1
        times += int(counts.get(identity) or 0)
        if identity[0] == flashcards_domain.CARD_TYPE_LEXICON:
            card = cards.get(word)
        else:
            card = row.get("card")
        if is_learned(card, facets.get(word) or {}, required):
            learned_n += 1
        else:
            unlearned_n += 1
        grade = grades.get(identity)
        if grade == fsrs.GRADE_HARD:
            hard_n += 1
        elif grade == fsrs.GRADE_GOOD:
            good_n += 1
        if identity in studied and card and fsrs.is_due(card, now=now_iso):
            due_n += 1
    return {
        "total": total,
        "studied": studied_n,
        "learned": learned_n,
        "unlearned": unlearned_n,
        "due": due_n,
        "hard": hard_n,
        "good": good_n,
        "times_studied": times,
    }


async def _bank_rows(
    user_id: str, *, level: str, collection_id: int | None
) -> list[dict]:
    user_words = await run_in_threadpool(vocabulary_repo.cefr_by_word, user_id)
    index = bank_index(user_words)
    if collection_id is not None:
        allowed = await run_in_threadpool(
            collections_repo.words_in_collection, user_id, collection_id
        )
        index = {word: cefr for word, cefr in index.items() if word in allowed}
    code = str(level or "").strip().upper()
    if code in CEFR_LEVELS:
        index = {word: cefr for word, cefr in index.items() if cefr == code}
    return [
        {"word": word, "cefr": cefr}
        for word, cefr in sorted(index.items())
    ]


async def _lexicon_cards(user_id: str) -> dict[str, dict]:
    cards = await run_in_threadpool(academy_repo.list_fsrs_cards, user_id)
    return {
        str(card.get("target_id") or ""): card
        for card in cards
        if card.get("target_type") == flashcards_domain.CARD_TYPE_LEXICON
        and card.get("target_id")
    }


def _classify(
    rows: list[dict],
    *,
    key_of,
    card_of,
    studied: set[tuple[str, str]],
    now: datetime,
) -> tuple[list[dict], list[dict], list[dict]]:
    """`(vencidas, próximas 24 h, el resto)`.

    Una palabra nunca calificada no es un repaso vencido: entra en el resto,
    que es lo que sirve el modo «todas».
    """
    horizon = (
        now + timedelta(hours=flashcards_domain.INTENSIVE_HORIZON_HOURS)
    ).isoformat()
    now_iso = now.isoformat()
    due: list[dict] = []
    upcoming: list[dict] = []
    rest: list[dict] = []
    for row in rows:
        card = card_of(row) or {}
        if key_of(row) not in studied:
            rest.append(row)
            continue
        if fsrs.is_due(card, now=now_iso):
            due.append({**row, "due_at": str(card.get("due_at") or "")})
            continue
        rest.append(row)
        due_at = str(card.get("due_at") or "")
        if due_at and due_at <= horizon:
            upcoming.append(row)
    due.sort(key=lambda item: item.get("due_at") or "")
    return due, upcoming, rest


def _session_cap(
    *,
    mode: str,
    words_per_day: int,
    difficulty: str,
    day_reviews: int,
    deck_review_remaining: int | None,
) -> int:
    """Tope de la sesión. Pendientes de un mazo manual usa su límite de repasos."""
    cap = _cap(words_per_day, difficulty)
    if mode != "pending":
        return cap
    if deck_review_remaining is None:
        return max(0, cap - int(day_reviews))
    return max(0, min(cap, int(deck_review_remaining)))


def _due_first(pool: list[dict], due: list[dict]) -> list[dict]:
    """Las vencidas del grupo van delante; el resto se reparte por nivel."""
    keys = {_row_key(row) for row in pool}
    first = [row for row in due if _row_key(row) in keys]
    seen = {_row_key(row) for row in first}
    tail = [row for row in pool if _row_key(row) not in seen]
    return first + interleave_by_level(tail)


def _pick(
    *,
    mode: str,
    due: list[dict],
    upcoming: list[dict],
    rest: list[dict],
    failed: list[dict],
    unlearned: list[dict],
    hard: list[dict],
    good: list[dict],
    intensive: bool,
    cap: int,
) -> list[dict]:
    if mode == "failed":
        pool = failed
    elif mode == "unlearned":
        pool = unlearned
    elif mode == "hard":
        pool = hard
    elif mode == "good":
        pool = good
    elif mode == "all":
        pool = due + interleave_by_level(rest)
    else:
        pool = due + upcoming if intensive else due
    return pool[: max(0, cap)]


async def _snapshot(user_id: str) -> dict:
    study = await study_config_domain.get_study_config(user_id)
    config = study["config"]
    studied = await run_in_threadpool(flashcards_repo.studied_cards, user_id)
    counts = await run_in_threadpool(flashcards_repo.review_counts, user_id)
    facets = await run_in_threadpool(vocabulary_repo.lesson_facets_by_word, user_id)
    cards = await _lexicon_cards(user_id)
    grades = await run_in_threadpool(flashcards_repo.latest_grades, user_id)
    mnemonics = await run_in_threadpool(vocabulary_repo.mnemonic_by_word, user_id)
    day = await run_in_threadpool(
        flashcards_repo.day_state,
        user_id,
        datetime.now(timezone.utc).date().isoformat(),
        flashcards_repo.AUTO_DECK_ID,
    )
    return {
        "study": study,
        "config": config,
        "studied": studied,
        "counts": counts,
        "facets": facets,
        "cards": cards,
        "grades": grades,
        "mnemonics": mnemonics,
        "day": day,
        "required": list(config.get("required_facets") or []),
        "now": _now(),
    }


def _lesson_item(row: dict, snap: dict, *, is_new: bool, deck_id: int) -> dict:
    word = str(row.get("word") or "")
    card = snap["cards"].get(word) or row.get("card") or {}
    reminder = str(row.get("mnemonic") or "").strip()
    if not reminder:
        reminder = str((snap.get("mnemonics") or {}).get(word) or "").strip()
    return {
        "word": word,
        "cefr": str(row.get("cefr") or ""),
        "card_type": str(row.get("card_type") or flashcards_domain.CARD_TYPE_LEXICON),
        "card_id": str(row.get("card_id") or word),
        "deck_id": int(row.get("deck_id") or deck_id),
        "is_new": is_new,
        "translation": "",
        "definition": "",
        "mnemonic": reminder,
        "facets": dict(snap["facets"].get(word) or {}),
        "state": str((card or {}).get("state") or "new"),
    }


async def _with_faces(user_id: str, items: list[dict]) -> list[dict]:
    """Traducción y definición solo de las palabras de la sesión, en un lote."""
    missing = [
        str(item.get("word") or "") for item in items if not item.get("translation")
    ]
    faces = await run_in_threadpool(retention_domain.card_faces, user_id, missing)
    out = []
    for item in items:
        face = faces.get(str(item.get("word") or ""), {})
        out.append(
            {
                **item,
                "translation": item.get("translation") or face.get("translation") or "",
                "definition": item.get("definition") or face.get("definition") or "",
            }
        )
    return out


def _row_key(row: dict) -> tuple[str, str]:
    if row.get("card_type") and row.get("card_id"):
        return (str(row["card_type"]), str(row["card_id"]))
    return (flashcards_domain.CARD_TYPE_LEXICON, str(row.get("word") or ""))


def _row_card(row: dict, snap: dict) -> dict:
    if row.get("card"):
        return row["card"]
    return snap["cards"].get(str(row.get("word") or "")) or {}


async def _scope_rows(
    user_id: str,
    snap: dict,
    *,
    scope: str,
    level: str,
    deck_id: int,
    collection_id: int | None,
) -> tuple[list[dict], int | None, int] | None:
    """Filas del ámbito, el límite de repasos del mazo manual y el id que se publica.

    ``None`` si el mazo manual no existe.
    """
    manual = scope == "deck" and int(deck_id) != flashcards_repo.AUTO_DECK_ID
    if not manual:
        level_code = level if scope == "level" else ""
        rows = await _bank_rows(
            user_id,
            level=level_code,
            collection_id=collection_id,
        )
        return rows, None, flashcards_repo.AUTO_DECK_ID
    deck = await run_in_threadpool(flashcards_repo.get_deck, user_id, int(deck_id))
    if deck is None:
        return None
    entries = await flashcards_domain._deck_entries(user_id, int(deck_id))
    rows = []
    for entry in entries:
        word = normalize_word(entry.get("front") or entry.get("card_id")) or str(
            entry.get("card_id") or ""
        )
        rows.append({**entry, "word": word, "cefr": ""})
    day = await run_in_threadpool(
        flashcards_repo.day_state,
        user_id,
        snap["now"].date().isoformat(),
        int(deck_id),
    )
    remaining = max(0, int(deck["review_per_day"]) - int(day["reviews"]))
    return rows, remaining, int(deck_id)


async def _assemble(
    user_id: str,
    *,
    scope: str,
    mode: str,
    level: str = "",
    deck_id: int = 0,
    collection_id: int | None = None,
    include_items: bool = False,
) -> dict | None:
    """Contadores y, si se pide, la cola. Una sola lectura del alumno."""
    if scope not in SCOPES or mode not in MODES:
        return None
    snap = await _snapshot(user_id)
    scoped = await _scope_rows(
        user_id,
        snap,
        scope=scope,
        level=level,
        deck_id=deck_id,
        collection_id=collection_id,
    )
    if scoped is None:
        return None
    rows, deck_remaining, published_deck = scoped
    now_iso = snap["now"].isoformat()
    numbers = _counts(
        rows,
        cards=snap["cards"],
        studied=snap["studied"],
        counts=snap["counts"],
        grades=snap["grades"],
        facets=snap["facets"],
        required=snap["required"],
        now_iso=now_iso,
        card_of=_row_key,
    )
    due, upcoming, rest = _classify(
        rows,
        key_of=_row_key,
        card_of=lambda row: _row_card(row, snap),
        studied=snap["studied"],
        now=snap["now"],
    )
    grades = snap["grades"]

    def last_grade(row: dict) -> int | None:
        return grades.get(_row_key(row))

    def learned_row(row: dict) -> bool:
        word = str(row.get("word") or "")
        return is_learned(
            _row_card(row, snap),
            snap["facets"].get(word) or {},
            snap["required"],
        )

    failed = [row for row in rows if last_grade(row) == fsrs.GRADE_AGAIN]
    unlearned = _due_first([row for row in rows if not learned_row(row)], due)
    hard = _due_first([row for row in rows if last_grade(row) == fsrs.GRADE_HARD], due)
    good = _due_first([row for row in rows if last_grade(row) == fsrs.GRADE_GOOD], due)
    cap = _session_cap(
        mode=mode,
        words_per_day=int(snap["config"].get("words_per_day") or 20),
        difficulty=str(snap["config"].get("difficulty") or "auto"),
        day_reviews=int(snap["day"]["reviews"]),
        deck_review_remaining=deck_remaining,
    )
    chosen = _pick(
        mode=mode,
        due=due,
        upcoming=upcoming,
        rest=rest,
        failed=failed,
        unlearned=unlearned,
        hard=hard,
        good=good,
        intensive=snap["config"].get("difficulty") == "intensive",
        cap=cap,
    )
    level_code = level if scope == "level" and level in CEFR_LEVELS else ""
    body = {
        **numbers,
        "queued": len(chosen),
        "mode": mode,
        "scope": scope,
        "level": level_code,
        "deck_id": published_deck,
        "collection_id": None if published_deck else collection_id,
    }
    if not include_items:
        return body
    items = [
        _lesson_item(
            row,
            snap,
            is_new=_row_key(row) not in snap["studied"],
            deck_id=published_deck,
        )
        for row in chosen
    ]
    for item, row in zip(items, chosen, strict=True):
        if row.get("back") and not item.get("translation"):
            item["translation"] = str(row.get("back") or "")
    items = await _with_faces(user_id, items)
    items = await run_in_threadpool(
        study_lessons_repo.insert_served_items,
        user_id,
        items,
        scope,
        mode,
        level_code,
        None if published_deck else collection_id,
    )
    config = snap["config"]
    return {
        **body,
        "items": items,
        "study_config": {**config, "configured": bool(snap["study"]["configured"])},
    }


async def study_summary(
    user_id: str,
    *,
    scope: str,
    level: str = "",
    deck_id: int = 0,
    collection_id: int | None = None,
    mode: str = "pending",
) -> dict | None:
    """Cinco contadores del ámbito y cuántas palabras entran en el modo pedido."""
    return await _assemble(
        user_id,
        scope=scope,
        mode=mode,
        level=level,
        deck_id=deck_id,
        collection_id=collection_id,
        include_items=False,
    )


async def study_queue(
    user_id: str,
    *,
    scope: str,
    level: str = "",
    deck_id: int = 0,
    collection_id: int | None = None,
    mode: str = "pending",
) -> dict | None:
    """Cola del modo dentro del ámbito, con los contadores de esa misma lectura."""
    return await _assemble(
        user_id,
        scope=scope,
        mode=mode,
        level=level,
        deck_id=deck_id,
        collection_id=collection_id,
        include_items=True,
    )


class LessonUnavailable:
    """La ficha que sirvió la cola ya no pertenece a ese mazo."""


LESSON_UNAVAILABLE = LessonUnavailable()


async def complete_lesson(
    user_id: str,
    *,
    item_id: str,
    grade: int,
    translation: str = "",
    facets: dict | None = None,
) -> dict | None | LessonUnavailable:
    """Cierra el ítem servido: una nota, una carta FSRS.

    La identidad sale de la fila de la cola. Una ficha manual agenda
    ``flashcard:<id>`` y deja la carta léxico sin calificar. El léxico agenda
    solo ``lexicon:<palabra>``. Repetir el mismo ``item_id`` devuelve el
    resultado ya guardado.

    ``LESSON_UNAVAILABLE`` si la ficha manual ya no está en el mazo: no se
    escribe nada. ``None`` si el id o la nota no valen.
    """
    if grade not in fsrs.GRADES or not str(item_id or "").strip():
        return None
    study = await study_config_domain.get_study_config(user_id)
    required = list(study["config"].get("required_facets") or [])
    code, result = await run_in_threadpool(
        study_lessons_repo.complete_item,
        user_id,
        str(item_id).strip(),
        int(grade),
        dict(facets or {}),
        translation,
        required,
    )
    if code == study_lessons_repo.GONE:
        return LESSON_UNAVAILABLE
    if code != study_lessons_repo.OK or result is None:
        return None
    return result

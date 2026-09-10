"""Repositorio de vocabulario (SQLite).

V3.25 (F-K7/P2-01/P2-02, fase 6): los contadores de producción/input usan los
nombres canónicos `production_count`/`exposure_count` (renombrado idempotente
en `db.init_db` desde el histórico `appearances`/`exposures`), y cada fila
declara su UNIDAD léxica (`lexical_unit`) además de su FORMA SUPERFICIAL
(`word`). La producción/input sigue siendo por superficie; la unidad permite
agregar por lemma y no tratar `go/going/went/gone` como conocimientos
independientes cuando comparten lemma.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime

from repositories.db import _conn, _now
from repositories.users import get_user


def _day(iso: str) -> str:
    """Parte `YYYY-MM-DD` de una marca de tiempo ISO-8601."""
    return iso[:10]


def _date_of(iso: str) -> date | None:
    """Fecha `date` de una marca ISO (datetime o date). None si vacía o inválida."""
    text = (iso or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _merge_context_tag(existing: str, tag: str) -> str:
    """Fusiona `tag` (canónico `channel:activity`) en la lista CSV de
    `context_tags` de forma canónica: única y ordenada (primero por el orden de
    `PRODUCTION_CHANNELS` del canal, luego por la actividad). Orden estable y
    determinista para tests y para la derivación pura."""
    if not tag:
        return existing
    seen = [t for t in existing.split(",") if t]
    if tag not in seen:
        seen.append(tag)
    channel_index = {c: i for i, c in enumerate(PRODUCTION_CHANNELS)}

    def order_key(item: str) -> tuple[int, str]:
        channel, _, activity = item.partition(":")
        return (channel_index.get(channel, len(channel_index)), activity)

    return ",".join(sorted(seen, key=order_key))


def lexical_unit_key(word: str, lemma: str = "") -> str:
    """Clave canónica de unidad léxica (V3.25/P2-02): el lemma en minúsculas
    cuando el currículo lo declara, o la superficie normalizada en minúsculas
    si no hay lemma. Es la dimensión de AGREGADO de dominio (no de trazabilidad
    por superficie, que sigue siendo `word`)."""
    base = (lemma or word or "").strip()
    return base.lower()


# Canales de producción (V3.19): cada columna `<channel>_prod` de `vocabulary`
# cuenta cuántos mensajes producidos por el alumno llegaron por ese canal.
# Invariante de trazabilidad: `sum(chat_prod, speaking_prod, writing_prod,
# conversation_prod) == production_count`.
PRODUCTION_CHANNELS: tuple[str, ...] = (
    "chat",
    "speaking",
    "writing",
    "conversation",
)

_CHANNEL_COLUMN: dict[str, str] = {
    channel: f"{channel}_prod" for channel in PRODUCTION_CHANNELS
}

# Tipos de evento del ledger léxico (V3.26, Eje B/F-B2): la historia detallada
# por forma de superficie. `produced` (mensaje del alumno en que apareció la
# palabra), `exposed` (mensaje del tutor), `retrieval` (recuperación demorada
# correcta) y `recalled` (V3.34: recuperación correcta de la palabra desde su
# significado en el paso Recall del drill, sin acreditar producción). Semántica
# de conteo idéntica a la de los contadores agregados: presencia de la palabra
# en un mensaje/intento (extract_words único), nunca frecuencia de tokens. La
# historia empieza en V3.26; SIN backfill (mejor perder el histórico fino que
# inventarlo; los contadores conservan el agregado).
VOCABULARY_EVENT_TYPES: tuple[str, ...] = (
    "produced",
    "exposed",
    "retrieval",
    "recalled",
)


def _insert_event(
    conn,
    user_id: str,
    word: str,
    unit: str,
    event_type: str,
    channel: str,
    activity: str,
    created_at: str,
) -> None:
    """Inserta una fila del ledger léxico dentro de la MISMA transacción del
    contador que la origina (V3.26, Eje B/F-B2): evita la doble fuente de verdad
    entre `vocabulary` (agregado) y `vocabulary_events` (historia fina)."""
    conn.execute(
        "INSERT INTO vocabulary_events "
        "(user_id, word, lexical_unit, event_type, channel, activity, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, word, unit, event_type, channel, activity, created_at),
    )


def record_production(
    user_id: str, words: list[str], channel: str = "chat", activity: str | None = None
) -> bool:
    """Registra producción del alumno etiquetada por canal (upsert).

    Incrementa `production_count` y, si la producción ocurre en un día distinto
    al último, `production_days` — exactamente igual que `record_words` — y
    además suma 1 a la columna `<channel>_prod` del canal. La semántica
    agregada (`production_count`/`production_days`/`item_status`/coverage) no
    cambia; el desglose por destreza queda derivable de las columnas
    `<channel>_prod`.

    V3.23 (P1-04): si se pasa `activity`, se etiqueta la producción con el
    contexto canónico `channel:activity` en `context_tags` (V3.23): permite
    medir la transferencia por contexto real de actividad (dos actividades del
    mismo canal cuentan como contextos distintos) y no solo por canal.

    V3.25 (P2-02): la fila declara su `lexical_unit` (lemma del currículo si la
    fila ya lo tiene, si no la superficie normalizada).

    Devuelve False si el usuario no existe o el canal no es válido.
    """
    column = _CHANNEL_COLUMN.get(channel)
    if column is None:
        return False
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    tag = f"{channel}:{activity}" if activity else ""
    now = _now()
    today = _day(now)
    with closing(_conn()) as conn, conn:
        for w in words:
            row = conn.execute(
                "SELECT last_seen, context_tags, lemma FROM vocabulary "
                "WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            prior = row["last_seen"] if row else ""
            existing_tags = row["context_tags"] if row else ""
            lemma = row["lemma"] if row else ""
            new_day = 1 if not prior or _day(prior) != today else 0
            tags = (
                _merge_context_tag(existing_tags, tag) if tag else existing_tags
            )
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, production_count, first_seen, last_seen, "
                f"production_days, {column}, context_tags, lexical_unit) "
                "VALUES (?, ?, 1, ?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "production_count = vocabulary.production_count + 1, "
                "first_seen = CASE WHEN vocabulary.first_seen = '' "
                "THEN excluded.first_seen ELSE vocabulary.first_seen END, "
                "last_seen = excluded.last_seen, "
                "production_days = vocabulary.production_days "
                f"+ excluded.production_days, "
                f"{column} = vocabulary.{column} + 1, "
                "context_tags = excluded.context_tags, "
                "lexical_unit = CASE WHEN vocabulary.lexical_unit = '' "
                "THEN excluded.lexical_unit ELSE vocabulary.lexical_unit END",
                (user_id, w, now, now, new_day, tags, lexical_unit_key(w, lemma)),
            )
            # Ledger léxico (V3.26, Eje B/F-B2): un evento por palabra producida
            # en este mensaje, en la misma transacción del contador.
            _insert_event(
                conn, user_id, w, lexical_unit_key(w, lemma),
                "produced", channel, activity or "", now,
            )
    return True


def record_words(user_id: str, words: list[str]) -> bool:
    """Registra producción del alumno (chat libre, canal `chat`).

    Wrapper retrocompatible de `record_production` (V3.19). Devuelve False si
    el usuario no existe."""
    return record_production(user_id, words, channel="chat")


def record_retrievals(user_id: str, words: list[str]) -> bool:
    """Registra una RECUPERACIÓN correcta de las palabras (éxito de micro-drill).

    V3.23 (P1-02): acredita retención por recuperación DEMORADA, no por
    exposición espaciada. Para cada palabra, solo cuenta si el intento ocurre
    `RETENTION_MIN_INTERVAL_DAYS` o más días naturales después del ancla
    (la primera señal: `min(first_exposed_at, first_seen)`). Al cumplirse:

    - `retrieval_successes += 1` (nº de recuperaciones correctas demoradas);
    - si el día de `last_retrieval_at` es distinto del actual,
      `retrieval_days += 1` (días distintos con recuperación demorada);
    - `last_retrieval_at = now`.

    Sin ancla (filas sin exposición ni producción) o antes del intervalo, la
    palabra se ignora en silencio. Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    # Import local: la constante canónica vive en el servicio puro; evita
    # dependencia en tiempo de import entre capas.
    from services.lexicon import RETENTION_MIN_INTERVAL_DAYS

    now = _now()
    today = _day(now)
    today_dt = _date_of(now)
    with closing(_conn()) as conn, conn:
        for w in words:
            row = conn.execute(
                "SELECT first_seen, first_exposed_at, last_retrieval_at, "
                "lexical_unit FROM vocabulary WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            if row is None:
                continue
            anchor = _earliest_day(row["first_seen"], row["first_exposed_at"])
            if anchor is None or today_dt is None:
                continue  # sin ancla no hay retención medible
            if (today_dt - anchor).days < RETENTION_MIN_INTERVAL_DAYS:
                continue  # aún dentro del intervalo: no es recuperación demorada
            new_day = 1 if _day(row["last_retrieval_at"] or "") != today else 0
            conn.execute(
                "UPDATE vocabulary SET "
                "retrieval_successes = retrieval_successes + 1, "
                "retrieval_days = retrieval_days + ?, "
                "last_retrieval_at = ? "
                "WHERE user_id = ? AND word = ?",
                (new_day, now, user_id, w),
            )
            # Ledger léxico (V3.26, Eje B/F-B2): una recuperación demorada OK.
            unit = row["lexical_unit"] or lexical_unit_key(w, "")
            _insert_event(
                conn, user_id, w, unit, "retrieval", "", "", now,
            )
    return True


def record_recalls(user_id: str, words: list[str]) -> bool:
    """Registra una RECUPERACIÓN correcta de la palabra desde su significado.

    V3.34 (Recall 2.0): capa PROPIA del recall por texto (paso Recall del
    drill). A diferencia de `record_production`, NO acredita producción: no
    toca `production_count` ni las columnas `<channel>_prod`, y no ensucia
    `first_seen`/`last_seen` (que miden producción). A diferencia de
    `record_retrievals`, no exige que el intento quede fuera de la ventana: es
    la señal de recuperación en sí misma (la recuperación demorada la sigue
    acreditando `record_retrievals`).

    - `recall_successes += 1` (nº de recuperaciones correctas);
    - si el día de `last_recall_at` es distinto del actual, `recall_days += 1`
      (días distintos con recall);
    - `last_recall_at = now`.

    Crea la fila si no existe (palabra consultada en el diccionario y nunca
    expuesta/producida) con `production_count = 0`/`exposure_count = 0`: el
    recall no inventa producción. Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    now = _now()
    today = _day(now)
    with closing(_conn()) as conn, conn:
        for w in words:
            row = conn.execute(
                "SELECT last_recall_at, lexical_unit, lemma FROM vocabulary "
                "WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            new_day = (
                1
                if row is None or _day(row["last_recall_at"] or "") != today
                else 0
            )
            lemma = row["lemma"] if row else ""
            unit = (row["lexical_unit"] if row else "") or lexical_unit_key(w, lemma)
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, production_count, exposure_count, first_seen, "
                "last_seen, recall_successes, recall_days, last_recall_at, "
                "lexical_unit) "
                "VALUES (?, ?, 0, 0, '', '', 1, ?, ?, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "recall_successes = vocabulary.recall_successes + 1, "
                "recall_days = vocabulary.recall_days + excluded.recall_days, "
                "last_recall_at = excluded.last_recall_at, "
                "lexical_unit = CASE WHEN vocabulary.lexical_unit = '' "
                "THEN excluded.lexical_unit ELSE vocabulary.lexical_unit END",
                (user_id, w, new_day, now, unit),
            )
            # Ledger léxico (V3.26): una recuperación correcta de recall.
            _insert_event(conn, user_id, w, unit, "recalled", "", "", now)
    return True


def _earliest_day(first_seen: str, first_exposed_at: str) -> date | None:
    """Fecha más temprana entre la primera producción y la primera exposición
    (ancla de la ventana de retención). None si no hay ninguna."""
    candidates = [d for d in (_date_of(first_seen), _date_of(first_exposed_at)) if d]
    return min(candidates) if candidates else None


def record_exposures(user_id: str, words: list[str]) -> bool:
    """Registra exposición (palabras de la respuesta del tutor). Upsert que crea
    la fila con `production_count = 0` si el alumno aún no ha producido la
    palabra.

    V3.22: además de `exposure_count`/`last_exposed_at`, incrementa
    `exposure_days` cuando la exposición ocurre en un día distinto al de la
    última exposición y fija `first_exposed_at` en la primera exposición
    (patrón idéntico al de `production_days`/`first_seen` en
    `record_production`). Así la matriz de competencia puede acreditar
    retención RECEPTIVA espaciada sin migrar.

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
                "SELECT last_exposed_at, lemma FROM vocabulary "
                "WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            prior = row["last_exposed_at"] if row else ""
            lemma = row["lemma"] if row else ""
            new_day = 1 if not prior or _day(prior) != today else 0
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, production_count, first_seen, last_seen, "
                "exposure_count, last_exposed_at, production_days, "
                "exposure_days, first_exposed_at, lexical_unit) "
                "VALUES (?, ?, 0, '', '', 1, ?, 0, ?, ?, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "exposure_count = vocabulary.exposure_count + 1, "
                "last_exposed_at = excluded.last_exposed_at, "
                "exposure_days = vocabulary.exposure_days "
                "+ excluded.exposure_days, "
                "first_exposed_at = CASE WHEN vocabulary.first_exposed_at = '' "
                "THEN excluded.first_exposed_at "
                "ELSE vocabulary.first_exposed_at END, "
                "lexical_unit = CASE WHEN vocabulary.lexical_unit = '' "
                "THEN excluded.lexical_unit ELSE vocabulary.lexical_unit END",
                (user_id, w, now, new_day, now, lexical_unit_key(w, lemma)),
            )
            # Ledger léxico (V3.26, Eje B/F-B2): un evento por palabra expuesta
            # en el mensaje del tutor, en la misma transacción del contador.
            _insert_event(
                conn, user_id, w, lexical_unit_key(w, lemma),
                "exposed", "", "", now,
            )
    return True


def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario ordenado por producción (desc) y
    palabra (asc). Incluye métricas de exposición y espaciado (V3.22:
    `exposure_days`/`first_exposed_at`), la unidad léxica canónica
    (V3.25/P2-02: `lexical_unit` junto a la superficie `word` y el `lemma`),
    el contexto curricular del ítem léxico (V2.3) y el desglose de producción
    por destreza (V3.19: `chat_prod`/`speaking_prod`/`writing_prod`/
    `conversation_prod`). V3.23 añade la evidencia de recuperación demorada
    (`retrieval_successes`/`retrieval_days`/`last_retrieval_at`) y el contexto
    de producción por actividad (`context_tags`). V3.34 añade la señal de recall
    por texto (`recall_successes`/`recall_days`/`last_recall_at`)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, production_count, first_seen, last_seen, "
            "exposure_count, last_exposed_at, exposure_days, first_exposed_at, "
            "production_days, "
            "cefr, level_id, objective_id, source, lemma, kind, lexical_unit, "
            "chat_prod, speaking_prod, writing_prod, conversation_prod, "
            "retrieval_successes, retrieval_days, last_retrieval_at, "
            "recall_successes, recall_days, last_recall_at, "
            "context_tags "
            "FROM vocabulary "
            "WHERE user_id = ? ORDER BY production_count DESC, word ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_vocabulary_events(
    user_id: str,
    word: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Historia de eventos léxicos por forma de superficie (V3.26, Eje B/F-B2).

    Devuelve las filas del ledger `vocabulary_events` del usuario ordenadas de
    más reciente a más antigua (append-only). `word` filtra por la superficie
    exacta (p. ej. `going`); la unidad canónica (`lexical_unit`) acompaña a la
    forma para agregar sin perder la superficie. `limit`/`offset` pagan la
    consulta; el ledger es señal (D5/E3), nunca puerta de mastery."""
    clauses = ["user_id = ?"]
    params: list[str] = [user_id]
    if word:
        clauses.append("word = ?")
        params.append(word)
    params.extend([limit, offset])
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, word, lexical_unit, event_type, channel, activity, "
            "created_at "
            "FROM vocabulary_events "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at DESC, id DESC "
            "LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def seed_curriculum_items(
    user_id: str, items: list[dict]
) -> bool:
    """Siembra ítems léxicos del currículo sin tocar producción/input (V2.3).

    `items` es una lista de dicts `{word, lemma, cefr, level_id, objective_id,
    kind}`. Crea la fila si no existe (con `production_count=0`/
    `exposure_count=0`) o rellena el contexto curricular si ya existía. Nunca
    incrementa `production_count` ni `exposure_count`: solo fija el contexto,
    para no contaminar las métricas de producción/lectura del alumno. La
    `lexical_unit` se fija al lemma del currículo cuando se declara (P2-02);
    las filas legacy sin unidad se rellenan con la superficie normalizada.
    Devuelve False si el usuario no existe.
    """
    if get_user(user_id) is None:
        return False
    if not items:
        return True
    with closing(_conn()) as conn, conn:
        for it in items:
            word = it["word"]
            lemma = it.get("lemma", word)
            unit = lexical_unit_key(word, lemma)
            row = conn.execute(
                "SELECT word FROM vocabulary WHERE user_id = ? AND word = ?",
                (user_id, word),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO vocabulary "
                    "(user_id, word, production_count, first_seen, last_seen, "
                    "exposure_count, last_exposed_at, production_days, "
                    "cefr, level_id, objective_id, source, lemma, kind, "
                    "lexical_unit) "
                    "VALUES (?, ?, 0, '', '', 0, '', 0, ?, ?, ?, 'curriculum', "
                    "?, ?, ?)",
                    (
                        user_id,
                        word,
                        it.get("cefr", ""),
                        it.get("level_id", ""),
                        it.get("objective_id", ""),
                        it.get("lemma", word),
                        it.get("kind", "word"),
                        unit,
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
                    "ELSE kind END, "
                    "lexical_unit = CASE WHEN lexical_unit = '' "
                    "THEN ? ELSE lexical_unit END "
                    "WHERE user_id = ? AND word = ?",
                    (
                        it.get("cefr", ""),
                        it.get("level_id", ""),
                        it.get("objective_id", ""),
                        lemma,
                        it.get("kind", "word"),
                        unit,
                        user_id,
                        word,
                    ),
                )
    return True

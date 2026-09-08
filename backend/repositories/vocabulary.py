"""Repositorio de vocabulario (SQLite)."""
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


# Canales de producción (V3.19): cada columna `<channel>_prod` de `vocabulary`
# cuenta cuántos mensajes producidos por el alumno llegaron por ese canal.
# Invariante de trazabilidad: `sum(chat_prod, speaking_prod, writing_prod,
# conversation_prod) == appearances`.
PRODUCTION_CHANNELS: tuple[str, ...] = (
    "chat",
    "speaking",
    "writing",
    "conversation",
)

_CHANNEL_COLUMN: dict[str, str] = {
    channel: f"{channel}_prod" for channel in PRODUCTION_CHANNELS
}


def record_production(
    user_id: str, words: list[str], channel: str = "chat", activity: str | None = None
) -> bool:
    """Registra producción del alumno etiquetada por canal (upsert).

    Incrementa `appearances` y, si la producción ocurre en un día distinto al
    último, `production_days` — exactamente igual que `record_words` — y además
    suma 1 a la columna `<channel>_prod` del canal. La semántica agregada
    (`appearances`/`production_days`/`item_status`/coverage) no cambia; el
    desglose por destreza queda derivable de las columnas `<channel>_prod`.

    V3.23 (P1-04): si se pasa `activity`, se etiqueta la producción con el
    contexto canónico `channel:activity` en `context_tags` (V3.23): permite
    medir la transferencia por contexto real de actividad (dos actividades del
    mismo canal cuentan como contextos distintos) y no solo por canal.

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
                "SELECT last_seen, context_tags FROM vocabulary "
                "WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            prior = row["last_seen"] if row else ""
            existing_tags = row["context_tags"] if row else ""
            new_day = 1 if not prior or _day(prior) != today else 0
            tags = (
                _merge_context_tag(existing_tags, tag) if tag else existing_tags
            )
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, appearances, first_seen, last_seen, "
                f"production_days, {column}, context_tags) "
                "VALUES (?, ?, 1, ?, ?, ?, 1, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "appearances = vocabulary.appearances + 1, "
                "first_seen = CASE WHEN vocabulary.first_seen = '' "
                "THEN excluded.first_seen ELSE vocabulary.first_seen END, "
                "last_seen = excluded.last_seen, "
                "production_days = vocabulary.production_days "
                f"+ excluded.production_days, "
                f"{column} = vocabulary.{column} + 1, "
                "context_tags = excluded.context_tags",
                (user_id, w, now, now, new_day, tags),
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
                "SELECT first_seen, first_exposed_at, last_retrieval_at "
                "FROM vocabulary WHERE user_id = ? AND word = ?",
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
    return True


def _earliest_day(first_seen: str, first_exposed_at: str) -> date | None:
    """Fecha más temprana entre la primera producción y la primera exposición
    (ancla de la ventana de retención). None si no hay ninguna."""
    candidates = [d for d in (_date_of(first_seen), _date_of(first_exposed_at)) if d]
    return min(candidates) if candidates else None


def record_exposures(user_id: str, words: list[str]) -> bool:
    """Registra exposición (palabras de la respuesta del tutor). Upsert que crea la
    fila con `appearances = 0` si el alumno aún no ha producido la palabra.

    V3.22: además de `exposures`/`last_exposed_at`, incrementa `exposure_days`
    cuando la exposición ocurre en un día distinto al de la última exposición y
    fija `first_exposed_at` en la primera exposición (patrón idéntico al de
    `production_days`/`first_seen` en `record_production`). Así la matriz de
    competencia puede acreditar retención RECEPTIVA espaciada sin migrar.

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
                "SELECT last_exposed_at FROM vocabulary "
                "WHERE user_id = ? AND word = ?",
                (user_id, w),
            ).fetchone()
            prior = row["last_exposed_at"] if row else ""
            new_day = 1 if not prior or _day(prior) != today else 0
            conn.execute(
                "INSERT INTO vocabulary "
                "(user_id, word, appearances, first_seen, last_seen, "
                "exposures, last_exposed_at, production_days, "
                "exposure_days, first_exposed_at) "
                "VALUES (?, ?, 0, '', '', 1, ?, 0, ?, ?) "
                "ON CONFLICT(user_id, word) DO UPDATE SET "
                "exposures = vocabulary.exposures + 1, "
                "last_exposed_at = excluded.last_exposed_at, "
                "exposure_days = vocabulary.exposure_days "
                "+ excluded.exposure_days, "
                "first_exposed_at = CASE WHEN vocabulary.first_exposed_at = '' "
                "THEN excluded.first_exposed_at ELSE vocabulary.first_exposed_at END",
                (user_id, w, now, new_day, now),
            )
    return True


def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario ordenado por producción (desc) y
    palabra (asc). Incluye métricas de exposición y espaciado (V3.22:
    `exposure_days`/`first_exposed_at`), el contexto curricular del ítem léxico
    (V2.3) y el desglose de producción por destreza
    (V3.19: `chat_prod`/`speaking_prod`/`writing_prod`/`conversation_prod`).
    V3.23 añade la evidencia de recuperación demorada
    (`retrieval_successes`/`retrieval_days`/`last_retrieval_at`) y el contexto
    de producción por actividad (`context_tags`)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, appearances, first_seen, last_seen, "
            "exposures, last_exposed_at, exposure_days, first_exposed_at, "
            "production_days, "
            "cefr, level_id, objective_id, source, lemma, kind, "
            "chat_prod, speaking_prod, writing_prod, conversation_prod, "
            "retrieval_successes, retrieval_days, last_retrieval_at, "
            "context_tags "
            "FROM vocabulary "
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

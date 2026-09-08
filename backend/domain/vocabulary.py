"""Servicio de dominio de vocabulario."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from domain import learning as learning_service
from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.fluency import compute_fluency
from services.phonetics import unit_produced
from services.pronunciation import score_pronunciation
from services.pronunciation_routes import sentence_context_for
from services.vocabulary import classify, extract_words

logger = logging.getLogger(__name__)


async def analyze_text(user_id: str, text: str) -> list[str]:
    """Registra producción del alumno (chat libre, canal `chat`) y devuelve las
    palabras extraídas."""
    words = extract_words(text)
    await run_in_threadpool(
        vocabulary_repo.record_production,
        user_id,
        words,
        channel="chat",
        activity="free_chat",
    )
    return words


async def record_production_text(
    user_id: str,
    text: str,
    channel: str,
    as_unit: bool = False,
    activity: str | None = None,
) -> list[str]:
    """Registra producción del alumno por canal (V3.19).

    Punto único por el que las superficies de práctica (speaking, writing,
    conversación guiada) vuelcan el texto producido al léxico etiquetado con su
    destreza. `record_production` mantiene la semántica agregada de
    `appearances`/`production_days` y suma la columna `<channel>_prod`.

    - `as_unit=False` (texto libre): tokeniza con `extract_words` (palabras
      sueltas sin stopwords).
    - `as_unit=True` (V3.21, V20-01): acredita `text` como unidad léxica
      atómica (p. ej. "living room" o cualquier palabra del micro-drill), sin
      trocearla en tokens. Necesario para que una unidad multi-palabra incremente
      SU PROPIA fila (`speaking_prod`/`appearances`) y no solo las de sus tokens.
    - `activity` (V3.23, P1-04): etiqueta de la actividad concreta (p. ej.
      `drill`, `free_chat`, `speaking_task`). Permite derivar la transferencia
      por CONTEXTO real de actividad y no solo por canal.

    Nunca lanza: el volcado al léxico es señal pedagógica (no evidencia de
    mastery) y no debe romper la puntuación del flujo que lo llama. Si el canal
    no es válido o falla la escritura, registra el aviso y devuelve la lista
    extraída igualmente."""
    words: list[str]
    if as_unit:
        words = [text.strip().lower()] if text.strip() else []
    else:
        words = extract_words(text)
    try:
        await run_in_threadpool(
            vocabulary_repo.record_production,
            user_id,
            words,
            channel=channel,
            activity=activity,
        )
    except Exception:  # noqa: BLE001 — volcado no bloqueante, nunca rompe
        logger.warning(
            "No se pudo volcar producción al léxico user=%s channel=%s",
            user_id,
            channel,
            exc_info=True,
        )
    return words


async def record_exposure(user_id: str, text: str) -> list[str]:
    """Registra exposición (palabras de la respuesta del tutor)."""
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_exposures, user_id, words)
    return words


async def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario con el estado de dominio calculado."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    for row in rows:
        row["status"] = classify(row["production_count"], row["production_days"])
    return rows


async def get_vocabulary_history(
    user_id: str,
    word: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Historia de eventos léxicos por superficie (V3.26, Eje B/F-B2).

    Puente de dominio al ledger `vocabulary_events` (más reciente primero). La
    historia empieza en V3.26 y es señal (no evidencia de mastery); el agregado
    de `vocabulary` conserva la verdad de los contadores."""
    return await run_in_threadpool(
        vocabulary_repo.list_vocabulary_events,
        user_id,
        word=word,
        limit=limit,
        offset=offset,
    )


async def seed_objective_vocabulary(user_id: str, level, objective) -> bool:
    """Siembra el léxico declarado por un objetivo (V2.3).

    Convierte `objective.vocabulary` + `objective.concepts` en ítems léxicos de
    la tabla `vocabulary` (solo contexto curricular: no toca producción/input).
    """
    items = lexicon.items_from_objective(level, objective)
    return await run_in_threadpool(
        vocabulary_repo.seed_curriculum_items, user_id, items
    )


async def get_lexicon(user_id: str) -> dict:
    """Léxico personal del alumno: `{summary, items, units}` por ítem léxico.

    Enriquece cada fila con `status`, `recall` y `next_review_days` reutilizando
    la curva de olvido y el scheduler de repaso existentes. V3.25.1 (P1-02):
    expone además el agregado por `lexical_unit` (`units`, con las superficies
    y su competencia propia) y el resumen por unidad (`summary.units`), sin
    cambiar el contrato por superficie."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    items = [
        {
            "word": row["word"],
            "lemma": row.get("lemma", ""),
            "cefr": row.get("cefr", ""),
            "kind": row.get("kind", "word"),
            "source": row.get("source", "user"),
            "status": lexicon.item_status(row),
            "recall": lexicon.item_recall(row),
            "next_review_days": lexicon.next_review_days(row),
            "production_count": row["production_count"],
            "exposure_count": row["exposure_count"],
            # V3.25 (P2-02): unidad léxica canónica (lemma cuando el currículo lo
            # declara; `word` conserva la FORMA SUPERFICIAL del ítem).
            "lexical_unit": row.get("lexical_unit", ""),
            # V3.21 (V20-16): matriz de competencia Recognition/Production/
            # Transfer/Retention con el transfer gap por ítem (puro, derivado).
            "competence": lexicon.item_competence_matrix(row),
            # V3.19: desglose de producción por destreza.
            "chat_prod": row.get("chat_prod", 0),
            "speaking_prod": row.get("speaking_prod", 0),
            "writing_prod": row.get("writing_prod", 0),
            "conversation_prod": row.get("conversation_prod", 0),
        }
        for row in rows
    ]
    summary = lexicon.summary(rows)
    # V3.25.1 (P1-02): agregado real por unidad léxica (aditivo).
    summary["units"] = lexicon.summary_units(rows)
    return {
        "summary": summary,
        "items": items,
        # V3.25.1 (P1-02): conocimiento por lexical_unit + superficies.
        "units": lexicon.units_from_rows(rows),
        # P1 (§3.1): Vocabulary Coverage Indicator receptivo/productivo por
        # nivel. Es un indicador interno (no una puerta): informa, no certifica.
        "coverage": lexicon.coverage_indicator(rows),
    }


async def get_drill_candidates(user_id: str, limit: int = 8) -> list[str]:
    """Candidatos al speaking micro-drill escalera (V3.21, F6/V20-06).

    Señal determinista en servidor: ítems con `exposures > 0` que aún no han
    consolidado la producción oral espaciada (`drill_ok_days` desde los eventos
    `learning_events` de éxito de drill; V3.21/F6.2), ordenados por recuerdo
    ascendente y acotados a `limit`. Reemplaza el recálculo cliente de
    `recognized_not_produced` (SIGNAL-01/A2-07) y el criterio antiguo de salir
    tras UNA producción del día (V20-06)."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    events = await learning_service.list_events(user_id, event_type="exercise")
    ok_days = lexicon.drill_ok_days(events)
    today = datetime.now(timezone.utc).date().isoformat()
    return lexicon.drill_candidates(
        rows, limit=limit, ok_days=ok_days, today=today
    )


async def _record_retrieval(user_id: str, word: str) -> None:
    """Registra una recuperación correcta del micro-drill (V3.23, P1-02).

    Solo el éxito de micro-drill cuenta como recuperación para la retención:
    el repositorio decide si el intento quedó FUERA del intervalo de retención
    (`record_retrievals` exige una separación >= RETENTION_MIN_INTERVAL_DAYS
    desde el ancla de la primera exposición/producción). Nunca lanza: es señal
    pedagógica y no debe romper la puntuación."""
    try:
        await run_in_threadpool(vocabulary_repo.record_retrievals, user_id, [word])
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar retrieval user=%s word=%s",
            user_id,
            word,
            exc_info=True,
        )


async def submit_drill_attempt(
    user_id: str,
    word: str,
    heard: str,
    duration_seconds: float | None = None,
    asr_status: str = "ok",
    asr_confidence: float | None = None,
) -> dict:
    """Puntúa un intento de speaking micro-drill y marca la palabra producida.

    Reutiliza el scorer determinista de pronunciación (`score_pronunciation` con
    la palabra esperada) y `compute_fluency`. La producción se decide por
    ALINEACIÓN SECUENCIAL (`unit_produced`, V3.21/V20-01), no por pertenencia de
    tokens: una palabra debe quedar alineada como `equal`; una frase multi-palabra
    debe aparecer contigua en la transcripción. Si se produjo, se registra la
    unidad léxica completa como `speaking_prod += 1` (`as_unit=True`, para que una
    frase acredite SU fila y no solo sus tokens), lo que la saca de la lista de
    candidatas.

    V3.21 (V20-14/V20-15): si el ASR no reconoció el audio con fiabilidad
    (`asr_status != "ok"`), `produced` va forzado a False (no se acredita
    producción) y NO se registra fallo: no podemos distinguir "no lo dijo" de
    "no te he oído". El drill NO declara dominio ni crea evidencia curricular
    (D5/E3, igual que el micro-review de V3.16). Devuelve el scoring + `produced`."""
    result = score_pronunciation(word, heard)
    # La palabra/frase "se produjo" si quedó alineada secuencialmente en la
    # transcripción (orden + cobertura + contigüidad, misma normalización).
    # Con ASR no fiable se fuerza False para no acreditar en falso.
    produced = unit_produced(word, heard) and asr_status == "ok"
    if produced:
        # Volcado al léxico por destreza; nunca lanza (señal, no evidencia).
        # `as_unit=True`: acredita la unidad atómica (V3.21, V20-01).
        await record_production_text(
            user_id, word, "speaking", as_unit=True, activity="drill"
        )
        # V3.23 (P1-02): recuperación correcta del micro-drill (retención si el
        # éxito queda fuera del intervalo respecto al ancla).
        await _record_retrieval(user_id, word)
    return {
        "word": word,
        "produced": produced,
        "expected": result["expected"],
        "heard": result["heard"],
        "score": result["score"],
        "level": result["level"],
        "ok": result["ok"],
        "word_accuracy": result["word_accuracy"],
        "phonetic_score": result["phonetic_score"],
        "phoneme_accuracy_proxy": result["phoneme_accuracy_proxy"],
        "prosody_proxy": result["prosody_proxy"],
        "pronunciation_source": result["pronunciation_source"],
        "breakdown": result["breakdown"],
        "phoneme_breakdown": result["phoneme_breakdown"],
        "fluency": (
            compute_fluency(heard, duration_seconds)
            if duration_seconds is not None
            else None
        ),
        "asr_status": asr_status,
        "asr_confidence": asr_confidence,
    }


def _row_for_word(rows: list[dict], word: str) -> dict | None:
    """Fila del léxico del usuario para una palabra (None si no existe)."""
    return next((row for row in rows if row.get("word") == word), None)


async def get_sentence_context(user_id: str, word: str) -> dict:
    """Frase de contexto determinista para el paso Sentence del drill (V3.21/F6.1).

    Busca en el banco oficial de frases de pronunciación del nivel CEFR del ítem
    la primera frase que CONTIENE la unidad léxica (alineación `unit_produced`);
    si ninguna la contiene (el banco es pequeño), usa una plantilla simple que
    no inventa significado ("Say the word …"). Sin LLM y determinista: el mismo
    servidor la vuelve a derivar al puntuar el intento."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    row = _row_for_word(rows, word)
    cefr = (row or {}).get("cefr", "")
    return sentence_context_for(word, level=cefr or None)


async def submit_sentence_attempt(
    user_id: str,
    word: str,
    heard: str,
    duration_seconds: float | None = None,
    asr_status: str = "ok",
    asr_confidence: float | None = None,
) -> dict:
    """Puntúa el paso "Sentence" del speaking micro-drill (V3.21/F6.1).

    El alumno repite en voz alta una FRASE de contexto que contiene la palabra
    objetivo. Scoring determinista reutilizando `score_pronunciation` sobre la
    frase esperada (derivada con `sentence_context_for`).

    - `produced`: la palabra objetivo quedó alineada en la transcripción
      (`unit_produced`, V3.21/V20-01).
    - `phrase_ok`: la frase completa superó el umbral del scorer (>= 80).
    - `passed` = produced AND phrase_ok: la evidencia del paso frase es decir la
      palabra DENTRO de la frase, no la palabra suelta (si solo dice la palabra,
      `produced=True` pero `phrase_ok=False` y no se acredita por este paso).

    Al `passed`, se acredita la unidad atómica como `speaking_prod += 1`
    (`as_unit=True`), igual que el paso palabra. Con ASR no fiable
    (`asr_status != "ok"`) `passed` va forzado a False y no se registra fallo
    (V20-14/15). El drill no declara dominio ni crea evidencia curricular (D5/E3)."""
    ctx = await get_sentence_context(user_id, word)
    phrase = ctx["phrase"]
    scored = score_pronunciation(phrase, heard)
    produced = unit_produced(word, heard) and asr_status == "ok"
    phrase_ok = scored["ok"] and asr_status == "ok"
    passed = produced and phrase_ok
    if passed:
        # Volcado al léxico por destreza; nunca lanza (señal, no evidencia).
        await record_production_text(
            user_id, word, "speaking", as_unit=True, activity="drill"
        )
        # V3.23 (P1-02): recuperación correcta del micro-drill (paso frase).
        await _record_retrieval(user_id, word)
    return {
        "word": word,
        "phrase": phrase,
        "source": ctx["source"],
        "produced": produced,
        "phrase_ok": phrase_ok,
        "passed": passed,
        "heard": scored["heard"],
        "score": scored["score"],
        "level": scored["level"],
        "fluency": (
            compute_fluency(heard, duration_seconds)
            if duration_seconds is not None
            else None
        ),
        "asr_status": asr_status,
        "asr_confidence": asr_confidence,
    }

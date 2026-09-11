"""Servicio de dominio de vocabulario."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

import config
from domain import learning as learning_service
from repositories import academy as academy_repo
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import vocabulary as vocabulary_repo
from services import (
    dictionary_content,
    dictionary_mcq,
    dictionary_reverse,
    example_sentences,
    fsrs,
    lexicon,
    planner,
    recall,
    transfer,
)
from services.evidence import (
    DRILL_SKILL,
    RECALL_SKILL,
    classify_recall_error,
    production_skill,
    recall_rung_activity,
)
from services.evidence import empty_summary as empty_evidence
from services.evidence import (
    transfer_state as evidence_transfer_state,
)
from services.fluency import compute_fluency
from services.phonetics import unit_produced
from services.pronunciation import score_pronunciation
from services.pronunciation_routes import sentence_context_for
from services.vocabulary import classify, extract_words

logger = logging.getLogger(__name__)

# V3.36 (Learning Evidence 2.0): APOYO declarado por canal de producción. `chat`
# es conversación libre (espontánea); `conversation` es conversación GUIADA (con
# andamiaje); `speaking`/`writing` son tareas sin apoyo declarado. El apoyo es
# del CANAL, no del resultado: no cambia con el acierto. Valores canónicos de
# `services.evidence.EVIDENCE_SUPPORT_LEVELS` (eje copied→spontaneous).
_PRODUCTION_SUPPORT: dict[str, str] = {
    "chat": "spontaneous",
    "conversation": "guided",
    "speaking": "independent",
    "writing": "independent",
}

# V3.39 (diccionario reversible): direcciones de búsqueda del diccionario de
# consulta. `en-es` es la histórica (V3.30, caché `dictionary_entries`);
# `es-en` es la inversa, que primero busca en las traducciones cacheadas y, si
# no hay coincidencia, genera y cachea en `dictionary_reverse_entries`.
DIRECTION_EN_ES = "en-es"
DIRECTION_ES_EN = "es-en"
DIRECTIONS: tuple[str, ...] = (DIRECTION_EN_ES, DIRECTION_ES_EN)


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
    await _record_production_evidence(
        user_id, words, channel="chat", activity="free_chat"
    )
    return words


async def _record_production_evidence(
    user_id: str, words: list[str], *, channel: str, activity: str | None = None
) -> None:
    """Escribe la evidencia longitudinal de una producción (V3.35).

    Cada palabra producida es un EVENTO (`task="production"`, rol `evidence`).
    Best-effort: nunca lanza (el volcado al léxico no debe romper la
    puntuación).

    V3.36 (Learning Evidence 2.0): el evento declara su CONTEXTO
    (`context_id="lexicon:<canal>"`), su actividad concreta (`activity_id`) y el
    APOYO del canal (`_PRODUCTION_SUPPORT`: chat libre → `spontaneous`,
    conversación guiada → `guided`, speaking/writing → `independent`). El apoyo
    es del canal, no del resultado: no cambia con el acierto.

    V3.38 (P1-03): la MODALIDAD (`skill`) deja de ser el canal crudo y pasa a
    ser el vocabulario declarado de `LEXICAL_SKILLS` (`production_skill`): el
    canal concreto no se pierde (sigue en `context_id`/`activity_id`), pero la
    automaticidad ya puede segmentarse por modalidad en lugar de mezclar
    producción escrita y oral."""
    if not words:
        return
    support_level = _PRODUCTION_SUPPORT.get(channel, "independent")
    try:
        await run_in_threadpool(
            evidence_repo.record_evidence_bulk,
            user_id,
            [
                {
                    "target_type": "lexicon",
                    "target_id": word,
                    "surface_form": word,
                    "skill": production_skill(channel),
                    "task": "production",
                    "activity": activity or "",
                    "activity_id": activity or channel,
                    "context_id": f"lexicon:{channel}",
                    "support_level": support_level,
                    "success": True,
                    "event_role": "evidence",
                }
                for word in words
            ],
        )
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar evidencia de producción user=%s channel=%s",
            user_id,
            channel,
            exc_info=True,
        )


async def record_production_text(
    user_id: str,
    text: str,
    channel: str,
    as_unit: bool = False,
    activity: str | None = None,
    write_evidence: bool = True,
) -> list[str]:
    """Registra producción del alumno por canal (V3.19).

    Punto único por el que las superficies de práctica (speaking, writing,
    conversación guiada) vuelcan el texto producido al léxico etiquetado con su
    destreza. `record_production` mantiene la semántica agregada de
    `appearances`/`production_days` y suma la columna `<channel>_prod`.
    V3.39: `write_evidence=False` para los pasos que escriben SU PROPIO evento
    de evidencia (con latencia y tipo de error, p. ej. la actividad `write`),
    evitando así DOS filas por intento.

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
        if write_evidence:
            await _record_production_evidence(
                user_id, words, channel=channel, activity=activity
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
    # V3.35 (Longitudinal Learning Evidence): evidencia fina del ledger por ítem
    # (`attempts`/`successes`/`days`/`intervals`), aditiva a los contadores
    # rápidos de `vocabulary`. Una sola consulta agregada, sin N+1.
    evidence_by_word = await run_in_threadpool(
        evidence_repo.summarize_by_target, user_id, target_type="lexicon"
    )
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
            # V3.35: historia longitudinal del ítem (sin filas → resumen vacío).
            "evidence": evidence_by_word.get(row["word"]) or empty_evidence(),
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
    tras UNA producción del día (V20-06).

    V3.35 (P1-2): esta cola deja de mezclar el repaso espaciado con el
    micro-drill. Las cartas FSRS `lexicon` vencidas ya NO se inyectan aquí: el
    "qué repasar ahora" vive en `GET /api/learning/review`, que propone la
    actividad óptima por hueco de competencia. Aquí solo quedan los huecos de
    producción ORAL pendiente."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    events = await learning_service.list_events(user_id, event_type="exercise")
    ok_days = lexicon.drill_ok_days(events)
    now_iso = datetime.now(timezone.utc).isoformat()
    today = now_iso[:10]
    return lexicon.drill_candidates(
        rows,
        limit=limit,
        ok_days=ok_days,
        today=today,
    )


async def _retrieval_decision(
    user_id: str, word: str, *, now_iso: str
) -> tuple[dict, dict, str]:
    """Fila del léxico + decisión de recuperación demorada + `due_at` FSRS.

    V3.35 (P1-1): la decisión la toma la función pura
    `services.lexicon.delayed_retrieval_decision`, con el ancla ENCADENADA
    (última recuperación `last_retrieval_at`/`last_recall_at` o, en la primera,
    la primera señal del ítem) y el intervalo de la carta FSRS `lexicon`
    vigente cuando existe. Devuelve `(row, decision, due_at)`.
    """
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    row = _row_for_word(rows, word) or {}
    card = await run_in_threadpool(
        academy_repo.get_fsrs_card, user_id, "lexicon", word
    )
    due_at = (card or {}).get("due_at") or ""
    decision = lexicon.delayed_retrieval_decision(
        row, now=now_iso, due_at=due_at
    )
    return row, decision, due_at


def _duration_ms(duration_seconds: float | None) -> int | None:
    """Latencia en ms a partir de una duración en segundos del cliente (V3.36).

    `None` si no se midió; nunca negativa. El cliente del drill manda SEGUNDOS
    (contrato existente) y el ledger guarda MILISEGUNDOS, la misma unidad que
    `listening.response_time_ms`, para que las latencias sean comparables entre
    superficies.
    """
    if duration_seconds is None:
        return None
    try:
        return max(0, int(round(float(duration_seconds) * 1000)))
    except (TypeError, ValueError):
        return None


async def _record_retrieval(
    user_id: str,
    word: str,
    *,
    task: str = "retrieval",
    activity_id: str = "drill:word",
    response_time_ms: int | None = None,
    write_evidence: bool = True,
) -> dict:
    """Registra una recuperación correcta del micro-drill (V3.23, P1-02).

    Solo el éxito de micro-drill cuenta como recuperación para la retención: la
    decisión (ancla encadenada + intervalo FSRS) la toma la capa pura y el
    repositorio solo persiste el resultado.

    V3.35 (Longitudinal Learning Evidence): escribe además la fila de evidencia
    longitudinal del intento, salvo que el llamador la escriba por su cuenta
    (`write_evidence=False`, p. ej. el recall, que registra su propio evento).
    V3.35.1 (P1-01): el intervalo NO se pasa: `record_evidence` lo deriva SIEMPRE
    de la evidencia anterior del ledger (`learning_evidence → learning_evidence`),
    que es el contrato de `interval_since_last_evidence`. El `interval_days` de
    la decisión es el hueco desde el ANCLA de retención (FSRS): otro concepto,
    que se queda en la decisión y no se persiste como intervalo de evidencia.
    V3.36 (Learning Evidence 2.0): el evento declara su contexto
    (`lexicon:drill`), su actividad concreta (`activity_id`, para distinguir el
    paso palabra del paso frase), el APOYO `guided` (el alumno repite tras oír
    un modelo: producción con andamiaje), la dificultad del ÍTEM y la latencia
    de la respuesta cuando el cliente la mide.
    V3.38 (P1-03): la MODALIDAD del evento es `spoken_production` (el alumno
    dice la palabra o la frase en voz alta), no el canal crudo.
    Nunca lanza: es señal pedagógica y no debe romper la puntuación. Devuelve la
    decisión tomada (para saber si acreditó y con qué intervalo de retención).
    """
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        row, decision, due_at = await _retrieval_decision(
            user_id, word, now_iso=now_iso
        )
        if decision["credited"]:
            await run_in_threadpool(
                vocabulary_repo.record_retrievals, user_id, [word], due_at=due_at
            )
        if write_evidence:
            await run_in_threadpool(
                evidence_repo.record_evidence,
                user_id,
                target_type="lexicon",
                target_id=word,
                surface_form=word,
                lexical_unit=row.get("lexical_unit") or word,
                skill=DRILL_SKILL,
                task=task,
                activity="drill",
                activity_id=activity_id,
                context_id="lexicon:drill",
                success=True,
                support_level="guided",
                difficulty=lexicon.cefr_difficulty(row),
                response_time_ms=response_time_ms,
                error_type="correct",
                event_role="evidence",
            )
        return decision
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar retrieval user=%s word=%s",
            user_id,
            word,
            exc_info=True,
        )
        return {}


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
        # éxito queda fuera del intervalo respecto al ancla). V3.36: la
        # evidencia declara el paso palabra y la latencia medida por el cliente.
        await _record_retrieval(
            user_id,
            word,
            activity_id="drill:word",
            response_time_ms=_duration_ms(duration_seconds),
        )
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
        # V3.36: evidencia del paso frase + latencia medida por el cliente.
        await _record_retrieval(
            user_id,
            word,
            activity_id="drill:sentence",
            response_time_ms=_duration_ms(duration_seconds),
        )
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


# ---------------------------------------------------------------------------
# Actividad de ESCRITURA del drill (V3.39, Fase 3, motor de tarea óptima).
# Cierra la modalidad `written_production` (el hueco `spoken ✓ / written ✗` que
# hasta V3.38 solo se exponía). El alumno escribe una frase PROPIA con la
# palabra objetivo: producción con el mínimo andamiaje (`independent`), pero el
# drill no declara dominio ni crea evidencia curricular (D5/E3): una producción
# del día no consolida.
# ---------------------------------------------------------------------------


async def _record_write_evidence(
    user_id: str,
    word: str,
    row: dict,
    scored: dict,
    *,
    response_time_ms: int | None = None,
) -> None:
    """Evento de evidencia del paso Write (V3.39), éxito Y fallo.

    A diferencia del paso Sentence (que solo deja señal cuando acredita), la
    escritura registra también el FALLO clasificado (taxonomía
    `services.evidence.WRITE_ERROR_TYPES`): eso es lo que permite al planner ver
    que la modalidad escrita se intenta y no sale, en lugar de solo que no
    existe. La modalidad es `written_production` y el apoyo `independent` (la
    frase es del alumno, sin modelo que repetir). Nunca lanza: es señal.
    """
    try:
        await run_in_threadpool(
            evidence_repo.record_evidence,
            user_id,
            target_type="lexicon",
            target_id=word,
            surface_form=word,
            lexical_unit=row.get("lexical_unit") or word,
            skill="written_production",
            task="write",
            activity="drill",
            activity_id="drill:write",
            context_id="lexicon:writing",
            success=bool(scored["passed"]),
            support_level="independent",
            difficulty=lexicon.cefr_difficulty(row),
            response_time_ms=response_time_ms,
            error_type=scored["error_type"] or "partial",
            event_role="evidence",
        )
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar evidencia de escritura user=%s word=%s",
            user_id,
            word,
            exc_info=True,
        )


async def submit_write_attempt(
    user_id: str,
    word: str,
    text: str,
    response_time_ms: int | None = None,
) -> dict:
    """Puntúa la actividad `write` del micro-drill (V3.39).

    El alumno escribe una frase PROPIA que use la palabra objetivo. Scoring
    determinista y sin LLM (`services.lexicon.score_write_attempt`): la unidad
    alineada + longitud mínima.

    Al `passed` se acredita la modalidad escrita (`writing_prod += 1` por el
    volcado al léxico) con evidencia `written_production`; en fallo se registra
    igualmente el intento clasificado (gap real de producción escrita). El paso
    NO graba recuperación ni FSRS: escribir con la palabra visible no es
    recuperación demorada (eso lo acredita el paso Recall)."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    row = _row_for_word(rows, word) or {}
    scored = lexicon.score_write_attempt(word, text)
    written = (text or "").strip()
    if scored["passed"]:
        # El volcado NO escribe evidencia: este paso escribe SU evento (con
        # latencia y tipo) para no duplicar filas por intento.
        await record_production_text(
            user_id,
            word,
            "writing",
            as_unit=True,
            activity="drill:write",
            write_evidence=False,
        )
    await _record_write_evidence(
        user_id, word, row, scored, response_time_ms=response_time_ms
    )
    return {
        "word": word,
        "text": written,
        **scored,
    }


# ---------------------------------------------------------------------------
# Actividad de TRANSFERENCIA a un contexto nuevo (V3.40, Fase 4).
# Cierra la modalidad `spontaneous_use`: usar la unidad por decisión propia en un
# contexto DISTINTO del de aprendizaje. La consigna la sirve `services.transfer`
# (banco curado, elección determinista) y el `context_id` que se registra en el
# ledger es el del contexto NUEVO, de modo que el éxito en >= 2 contextos
# demuestra —con evidencia— la transferencia contextual real (P1-03 de la
# auditoría de V3.38.1). El drill no declara dominio (D5/E3).
# ---------------------------------------------------------------------------


async def _record_transfer_evidence(
    user_id: str,
    word: str,
    row: dict,
    scored: dict,
    context_id: str,
    *,
    condition: str = "",
    response_time_ms: int | None = None,
) -> None:
    """Evento de evidencia del paso Transfer (V3.40 → V3.46), éxito Y fallo.

    Modalidad `spontaneous_use` y apoyo `spontaneous` (la consigna da un
    escenario nuevo, no ayuda con la unidad); el `context_id` es el del contexto
    NUEVO, que es lo que permite a `services.evidence.context_signals` contar la
    transferencia. Como en `write`, el fallo también se registra clasificado.
    Nunca lanza: es señal.

    V3.43: al ocultarse el target (P1-01), `spontaneous` pasa a ser literal —el
    alumno decide si usa la unidad—. `success` sigue siendo el TRANSFER LÉXICO
    (`scored["passed"]`); un uso léxicamente correcto pero `suspect` guarda
    `error_type="semantic_mismatch"` y NO contará como ÉXITO LIMPIO en
    `context_signals` (V3.43/P1-02).

    V3.46 (P1-03): `condition` persiste la CONDICIÓN DE RECUPERACIÓN
    (`services.transfer`) derivada por el servidor del estado de evidencia. El
    `support_level` sigue declarando el andamiaje de la ACTIVIDAD
    (`spontaneous`); la condición es la dimensión fina que permite ponderar el
    acierto (un éxito en `cued_context` no acredita transferencia no andamiada).
    """
    try:
        await run_in_threadpool(
            evidence_repo.record_evidence,
            user_id,
            target_type="lexicon",
            target_id=word,
            surface_form=word,
            lexical_unit=row.get("lexical_unit") or word,
            skill="spontaneous_use",
            task="transfer",
            activity="drill",
            activity_id="drill:transfer",
            context_id=context_id,
            success=bool(scored["passed"]),
            support_level="spontaneous",
            difficulty=lexicon.cefr_difficulty(row),
            response_time_ms=response_time_ms,
            error_type=scored["error_type"] or "partial",
            transfer_condition=condition,
            event_role="evidence",
        )
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar evidencia de transferencia user=%s word=%s",
            user_id,
            word,
            exc_info=True,
        )


def _transfer_condition_for(summary: dict) -> str:
    """Condición de recuperación que toca SERVIR/registrar (V3.46, pura).

    La deriva el SERVIDOR del resumen de evidencia (nunca la declara el cliente,
    premisa 21): `services.evidence.transfer_state` fija el andamiaje y
    `attempted` distingue si el alumno ya intentó transferir alguna vez.
    """
    state = evidence_transfer_state(summary or {})
    attempted = int((summary or {}).get("context_attempts") or 0) > 0
    clean = int((summary or {}).get("clean_successes") or 0)
    return transfer.condition_for_state(
        state, attempted=attempted, clean_successes=clean
    )


def _transfer_target_skill(row: dict, summary: dict) -> str:
    """Modalidad LIMITANTE del ítem para orientar el contexto nuevo (V3.50, pura).

    Devuelve la skill que el planner considera limitante (`planner.limiting_skill`
    sobre las señales que produce `planned_signals`) o "" si no hay segmentación
    por modalidad en el ledger: sin evidencia fina no se inventa una preferencia
    y `context_for` sirve el contexto como en V3.49. Es una PREFERENCIA (no una
    obligación): la decisión sigue siendo del servidor, sin LLM (premisa 21).
    Nunca lanza.
    """
    attempts = (summary or {}).get("skill_attempts")
    if not isinstance(attempts, dict):
        return ""
    try:
        if not any(int(value or 0) > 0 for value in attempts.values()):
            return ""
        matrix = lexicon.item_competence_matrix(row or {})
        signals = planner.planned_signals(summary, matrix)
        return planner.limiting_skill(signals)
    except Exception:  # noqa: BLE001 — preferencia no bloqueante
        return ""


async def get_transfer_context(user_id: str, word: str) -> dict:
    """Consigna de transferencia que toca practicar (V3.40 → V3.46, solo lectura).

    Elige el contexto NUEVO con `services.transfer.context_for` sobre los
    contextos que el ítem ya registró en su evidencia (así no repite el que ya
    usó) y, V3.43 (P1-03), prioriza el contexto más DISTANTE de los que ya
    logró con éxito: máxima novedad pedagógica, no solo otro `context_id`. No
    escribe nada: es el GET del peldaño.

    V3.46 (P1-03): además sirve la CONDICIÓN DE RECUPERACIÓN derivada del estado
    (`_transfer_condition_for`): `prompted` tras fallar sin éxito limpio,
    `cued_context` por defecto (comportamiento de V3.43) y `open_context` cuando
    la unidad ya se usa en contextos distintos — el escenario abierto que no
    exige la palabra y única condición que acredita transferencia demostrada.

    V3.47: pasa el nivel CEFR declarado del ítem (`row["cefr"]`) a
    `context_for`, de modo que no se sirve un contexto por encima del alcance del
    alumno si hay uno alcanzable.
    """
    summaries = await run_in_threadpool(
        evidence_repo.summarize_by_target, user_id, target_type="lexicon"
    )
    summary = summaries.get(word) or {}
    used = (summary.get("contexts") or {}).keys()
    success = summary.get("success_contexts") or []
    condition = _transfer_condition_for(summary)
    # V3.47: el nivel declarado del ítem ajusta el contexto servido (sin nivel se
    # mantiene el comportamiento de V3.46).
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    row = _row_for_word(rows, word) or {}
    # V3.50: la modalidad limitante del ítem orienta el contexto servido ("" si
    # el ledger no tiene segmentación por modalidad: comportamiento de V3.49).
    skill = _transfer_target_skill(row, summary)
    return transfer.context_for(
        word,
        used,
        success_context_ids=success,
        condition=condition,
        level=row.get("cefr") or "",
        skill=skill,
    )


async def submit_transfer_attempt(
    user_id: str,
    word: str,
    text: str,
    context_id: str = "",
    response_time_ms: int | None = None,
) -> dict:
    """Puntúa la actividad `transfer` del micro-drill (V3.40 → V3.46).

    El alumno usa la unidad en un contexto NUEVO (consigna abierta, sin la
    palabra: V3.43/P1-01). Scoring determinista y sin LLM
    (`services.lexicon.score_transfer_attempt`): unidad alineada + longitud
    mínima (TRANSFER LÉXICO), más un proxy determinista de ADECUACIÓN SEMÁNTICA
    (V3.43/P1-02) que exige la categoría declarada del ítem
    (`dictionary_entries.pos`). La evidencia va como `spontaneous_use` y con el
    `context_id` del contexto nuevo.

    Al `passed` se acredita la producción con el volcado al léxico
    (`writing_prod += 1`; `as_unit=True`) y se registra la evidencia; en fallo se
    registra igualmente el intento clasificado. Un uso léxicamente correcto pero
    semánticamente `suspect` mantiene `passed=True` y añade
    `error_type="semantic_doubt"`, que NO bloquea los ÉXITOS LIMPIOS (V3.44).

    V3.46 (P1-03): la CONDICIÓN la deriva el servidor (`_transfer_condition_for`)
    y se persiste con el intento. En condiciones que NO exigen la unidad
    (`open_context`), un intento que no la usa NO se registra como evidencia: no
    hay nada que observar sobre el objetivo y no debe penalizar al alumno (el
    contrato lo declara con `required_target=false`). No graba recuperación ni
    FSRS.
    """
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    row = _row_for_word(rows, word) or {}
    # POS y SENTIDOS declarados del ítem para el proxy semántico (vacíos si no
    # hay caché: el proxy queda `unknown` y no inventa). V3.44: se prefieren los
    # sentidos de la UNIDAD léxica (go/went/gone comparten sentido) y se cae a
    # la superficie buscada cuando la unidad no tiene entrada propia.
    entry = await run_in_threadpool(dictionary_repo.get_entry, word)
    pos = (entry or {}).get("pos") or ""
    senses = list((entry or {}).get("senses") or [])
    unit = (row.get("lexical_unit") or "").strip().lower()
    if unit and unit != (word or "").strip().lower():
        unit_entry = await run_in_threadpool(dictionary_repo.get_entry, unit)
        if unit_entry and unit_entry.get("senses"):
            senses = list(unit_entry.get("senses") or [])
            pos = unit_entry.get("pos") or pos
    # Sin `context_id` del cliente se DERIVA del banco (determinista) con la
    # MISMA función que el GET (incluidos los contextos ya logrados), para que el
    # evento nunca quede sin contexto y no discrepe del peldaño servido. La
    # CONDICIÓN se deriva del mismo resumen: el cliente no la declara (premisa 21).
    summaries = await run_in_threadpool(
        evidence_repo.summarize_by_target, user_id, target_type="lexicon"
    )
    summary = summaries.get(word) or {}
    condition = _transfer_condition_for(summary)
    if not context_id:
        # V3.50: mismo criterio que el GET (modalidad limitante) para que ambos
        # caminos deriven el MISMO `context_id`.
        context_id = transfer.context_for(
            word,
            (summary.get("contexts") or {}).keys(),
            success_context_ids=summary.get("success_contexts") or [],
            condition=condition,
            level=row.get("cefr") or "",
            skill=_transfer_target_skill(row, summary),
        ).get("context_id", "")
    scored = lexicon.score_transfer_attempt(word, text, pos=pos, senses=senses)
    written = (text or "").strip()
    required = transfer.requires_target(condition)
    if scored["passed"]:
        await record_production_text(
            user_id,
            word,
            "writing",
            as_unit=True,
            activity="drill:transfer",
            write_evidence=False,
        )
    # Sin la unidad en una condición que no la exige no hay evidencia que
    # registrar: no es un fallo, es una elección legítima del alumno (V3.46).
    if scored["passed"] or required:
        await _record_transfer_evidence(
            user_id,
            word,
            row,
            scored,
            context_id,
            condition=condition,
            response_time_ms=response_time_ms,
        )
    return {
        "word": word,
        "text": written,
        "context_id": context_id,
        "condition": condition,
        "required_target": required,
        **scored,
    }


# ---------------------------------------------------------------------------
# Paso Recognition del drill (V3.33, eslabón 2 del Dictionary → Learning
# Bridge). MCQ definición ↔ palabra servido y puntuado por el backend (premisa
# 21, sin estado servidor): la pregunta es una función pura y determinista por
# (palabra, question_id) sobre la caché global `dictionary_entries`
# (`services/dictionary_mcq`); el `question_id` es un nonce por intento (V3.33.1)
# que rebaraja la posición de la correcta sin guardar sesión.
# Evidencia SOLO informativa (V3.13: el MC de reconocimiento no demuestra
# destrezas productivas): el acierto/fallo registra únicamente el evento
# `learning_events` `drill:<word>:recognition:ok|ko`; NUNCA escribe en
# `vocabulary`/`vocabulary_events` ni mueve FSRS/mastery/usage (D3 + sin
# "mastery de clic"), y no saca la palabra de la lista de candidatas.
# ---------------------------------------------------------------------------


async def get_recognition_question(user_id: str, word: str) -> dict:
    """Pregunta del paso Recognition del drill (V3.33).

    La pregunta NO depende del alumno (contenido global); `user_id` se conserva
    por simetría con el resto de funciones de drill. Si no hay contenido
    suficiente (palabra sin entrada o sin distractores), devuelve
    `available=false` con `options=[]`: degradación controlada sin evento (el
    peldaño muestra aviso y no rompe Recall/Sentence). La respuesta NUNCA
    incluye el índice correcto: lo puntúa el POST recomputando la pregunta.

    V3.33.1: el GET entrega un `question_id` (nonce por intento) que actúa como
    seed del barajado. El POST lo devuelve y el servidor reconstruye la MISMA
    permutación, de modo que la posición de la correcta cambia entre intentos
    sin guardar estado servidor (no se puede aprender la posición).
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    question_id = secrets.token_urlsafe(8)
    built = dictionary_mcq.recognition_options_for(
        normalized, entries, seed=question_id
    )
    if built is None:
        return {
            "word": normalized,
            "available": False,
            "options": [],
            "question_id": "",
        }
    options, _correct_index = built
    return {
        "word": normalized,
        "available": True,
        "options": options,
        "question_id": question_id,
    }


async def submit_recognition_attempt(
    user_id: str, word: str, selected_index: int, question_id: str = ""
) -> dict | None:
    """Puntúa un intento del paso Recognition (V3.33) sin efectos colaterales.

    El servidor recomputa la pregunta con la MISMA función pura (premisa 21) y
    el `question_id` recibido como seed (V3.33.1): misma permutación que sirvió
    el GET. Compara `selected_index` con la correcta. Devuelve `None` si la
    palabra ya no tiene pregunta (el router responde un 4xx controlado sin
    evento).
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    built = dictionary_mcq.recognition_options_for(
        normalized, entries, seed=question_id
    )
    if built is None:
        return None
    options, correct_index = built
    if selected_index < 0 or selected_index >= len(options):
        raise ValueError("selected_index fuera de rango")
    return {
        "word": normalized,
        "correct": selected_index == correct_index,
        "correct_index": correct_index,
        "selected_index": selected_index,
    }


# ---------------------------------------------------------------------------
# Paso Recall del drill (V3.34, Recall 2.0). Camino INVERSO a Recognition: el
# alumno ve el SIGNIFICADO (cue) y recupera/teclea la palabra. Recuperación
# productiva por texto, sin micrófono. A diferencia de Recognition (SOLO
# informativo, V3.13), el acierto de Recall SÍ deja señal en la capa léxica:
# `recall_successes`/`recall_days` + evento `vocabulary_events` `recalled`
# (NUNCA cuenta como producción: no toca `production_count` ni `<channel>_prod`,
# ni saca la palabra de candidatas) y, si el intento supera el intervalo de
# retención, acredita la recuperación demorada existente (`retrieval_*`).
# Además reprograma la carta FSRS `lexicon` de la palabra con intervalos reales
# (acierto inmediato = Good, recuperación demorada = Easy, fallo = Again).
# La pregunta es pura y determinista sobre la caché global `dictionary_entries`
# (`services.recall`); el servidor la re-deriva al puntuar y solo revela la
# palabra esperada tras el intento (premisa 21).
# ---------------------------------------------------------------------------


async def get_recall_prompt(
    user_id: str, word: str, cue: str | None = None
) -> dict:
    """Cue del paso Recall del drill (V3.34 → V3.37, cues graduados).

    La pregunta NO depende del alumno (contenido global); `user_id` se conserva
    por simetría con el resto de funciones de drill.

    - `cue=None` conserva EXACTAMENTE el comportamiento V3.34 (traducción y, si
      no, definición sin spoiler) para no romper clientes antiguos.
    - `cue="translation"|"definition"|"cloze"|"situation"` sirve ESE peldaño. El
      dominio re-deriva el peldaño de forma pura (premisa 21) y, para `cloze`,
      obtiene la frase real del banco de pronunciación (`example_for`); para
      `situation` sirve el enunciado situacional de la caché (V3.38).
    - Si no hay contenido para el peldaño pedido (o no hay cue utilizable sin
      `cue`), devuelve `available=false` con `cue=""`: degradación controlada
      sin evento (el peldaño muestra aviso y no rompe Sentence).
    - Un `cue` no soportado responde 422 (ValueError).

    El payload incluye `support_level` (apoyo que declara el peldaño servido,
    aditivo) y NUNCA la forma esperada: la revela el POST tras puntuar.
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    if cue is not None and cue not in recall.RECALL_CUES:
        raise ValueError("Peldaño de recall no válido")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    if cue is None:
        built = recall.recall_prompt_for(normalized, entries)
        support_level = (
            recall.RECALL_CUE_SUPPORT.get(built["cue_kind"], "") if built else ""
        )
    else:
        example = (
            await run_in_threadpool(example_sentences.example_for, normalized)
            if cue == "cloze"
            else None
        )
        built = recall.recall_prompt_for(
            normalized, entries, cue=cue, example=example
        )
        support_level = recall.RECALL_CUE_SUPPORT[cue]
    if built is None:
        return {
            "word": normalized,
            "available": False,
            "cue": "",
            "cue_kind": "",
            "support_level": support_level,
        }
    return {
        "word": normalized,
        "available": True,
        "cue": built["cue"],
        "cue_kind": built["cue_kind"],
        "support_level": recall.RECALL_CUE_SUPPORT.get(built["cue_kind"], ""),
    }


async def submit_recall_attempt(
    user_id: str,
    word: str,
    answer: str,
    *,
    cue: str | None = None,
    response_time_ms: int | None = None,
) -> dict | None:
    """Puntúa un intento del paso Recall (V3.34) y deja su señal.

    El servidor re-deriva el cue con la misma función pura (premisa 21) y
    compara la respuesta normalizada con la palabra (igualdad estricta de
    superficie, sin tolerar variantes: recuperar la forma es el objetivo).
    Devuelve `None` si la palabra ya no tiene pregunta (el router responde un
    4xx controlado sin evento).

    V3.35 (Longitudinal Learning Evidence): el INTENTO se registra siempre
    (`recall_attempts`, acierto o fallo), la recuperación demorada se decide con
    la cadena encadenada (ancla = recuperación anterior) y CADA intento deja una
    fila en `learning_evidence`. V3.35.1 (P1-01): el intervalo de esa fila lo
    deriva `record_evidence` de la evidencia ANTERIOR del ledger (contrato de
    `interval_since_last_evidence`); el `interval_days` de la decisión es el
    hueco desde el ancla de RETENCIÓN (FSRS) y no se persiste como intervalo de
    evidencia. Orden importante: la recuperación demorada se evalúa ANTES de
    fijar el nuevo ancla de recall, de modo que el intervalo se mide desde la
    recuperación anterior y no desde este mismo intento.

    En el acierto: `record_recalls` (señal de recall + ledger `recalled`),
    `record_retrievals` (recuperación demorada, si el intento supera el
    intervalo) y la reprogramación de la carta FSRS de la palabra. En el fallo:
    solo la carta FSRS (`Again`), y únicamente si ya existía, para no inventar
    deuda de repaso de una palabra no rastreada.

    V3.36 (Learning Evidence 2.0): el evento declara el APOYO, su contexto
    (`lexicon:drill`), la dificultad del ÍTEM, la latencia del cliente y la
    CLASIFICACIÓN del intento (`classify_recall_error`: vacío / errata /
    parcial / otra palabra). La clasificación es OBSERVACIONAL: `correct` sigue
    siendo igualdad estricta de superficie, así que una errata no acredita
    recall ni cambia la evidencia ni FSRS; solo informa al tutor.

    V3.37 (cues graduados): el cliente declara QUÉ peldaño le sirvieron (`cue`,
    premisa 21) y el servidor lo RE-DERIVA con la misma función pura: un `cue`
    no soportado o sin contenido para esa palabra se rechaza con 422, sin
    evento. El evento pasa a declarar el `support_level` del peldaño real
    (`cued`/`cued`/`guided`/`guided`) y el `activity_id`
    `drill:recall:<peldaño>`, de modo que el ledger distinga apoyos y la
    escalera pueda leer sus éxitos. El
    scoring NO cambia: un acierto con cloze vale lo mismo que con traducción
    para el contador de recall; lo que cambia es lo que el ledger sabe.

    V3.38 (P1-03): el evento declara su MODALIDAD (`skill="recall"`), para que
    la automaticidad pueda segmentarse por modalidad y no se mezcle con la
    producción oral/escrita del mismo ítem.
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    if cue is not None and cue not in recall.RECALL_CUES:
        raise ValueError("Peldaño de recall no válido")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    if cue is None:
        built = recall.recall_prompt_for(normalized, entries)
    else:
        example = (
            await run_in_threadpool(example_sentences.example_for, normalized)
            if cue == "cloze"
            else None
        )
        built = recall.recall_prompt_for(
            normalized, entries, cue=cue, example=example
        )
    if built is None:
        if cue is not None:
            # El peldaño PEDIDO no tiene contenido: 422, sin evento (V3.37).
            raise ValueError("El peldaño no tiene contenido para esta palabra")
        return None
    served_cue = built["cue_kind"]
    support_level = recall.RECALL_CUE_SUPPORT[served_cue]
    activity_id = recall_rung_activity(served_cue)
    given = _normalize_lookup_word(answer)
    correct = bool(given) and given == normalized
    error_type = classify_recall_error(normalized, given)
    now_iso = datetime.now(timezone.utc).isoformat()
    row_before, decision, due_at = await _retrieval_decision(
        user_id, normalized, now_iso=now_iso
    )
    delayed = False
    recall_days = 0
    if correct:
        # La recuperación demorada se decide con el estado ANTERIOR al intento
        # (ancla = recuperación previa, no este mismo recall).
        delayed = bool(decision["credited"])
        if delayed:
            await run_in_threadpool(
                vocabulary_repo.record_retrievals,
                user_id,
                [normalized],
                due_at=due_at,
            )
        await run_in_threadpool(
            vocabulary_repo.record_recalls, user_id, [normalized]
        )
        rows_after = await run_in_threadpool(
            vocabulary_repo.get_vocabulary, user_id
        )
        row = _row_for_word(rows_after, normalized) or {}
        recall_days = int(row.get("recall_days") or 0)
    else:
        # Un fallo también es evidencia: suma intento sin tocar el ancla.
        await run_in_threadpool(
            vocabulary_repo.record_recall_attempt,
            user_id,
            [normalized],
            success=False,
        )
    await run_in_threadpool(
        evidence_repo.record_evidence,
        user_id,
        target_type="lexicon",
        target_id=normalized,
        surface_form=normalized,
        lexical_unit=row_before.get("lexical_unit") or normalized,
        skill=RECALL_SKILL,
        task="recall",
        activity="drill",
        activity_id=activity_id,
        context_id="lexicon:drill",
        success=correct,
        support_level=support_level,
        difficulty=lexicon.cefr_difficulty(row_before),
        response_time_ms=response_time_ms,
        error_type=error_type,
        event_role="evidence",
    )
    await _reschedule_lexicon_card(
        user_id, normalized, correct=correct, delayed=delayed
    )
    return {
        "word": normalized,
        "correct": correct,
        "expected": normalized,
        "delayed": delayed,
        "recall_days": recall_days,
        "error_type": error_type,
    }


async def _reschedule_lexicon_card(
    user_id: str, word: str, *, correct: bool, delayed: bool
) -> None:
    """Reprograma la carta FSRS de la palabra tras un intento de Recall (V3.34).

    Acierto inmediato → `Good`; recuperación demorada → `Easy`; fallo → `Again`
    (lapse). No crea carta por un FALLO de una palabra no rastreada (no se
    inventa deuda de repaso); en acierto sí la siembra si no existía. Nunca
    lanza: el scheduling es señal pedagógica y no debe romper la puntuación.
    `sync_fsrs_cards` respeta las cartas con `reps > 0`, así que este intervalo
    no se pisa en la siguiente sincronización.
    """
    try:
        existing = await run_in_threadpool(
            academy_repo.get_fsrs_card, user_id, "lexicon", word
        )
        if existing is None:
            if not correct:
                return
            card = fsrs.empty_card(
                target_type="lexicon",
                target_id=word,
                label=word,
                why="recall",
            )
        else:
            card = existing
        if not correct:
            grade, why = fsrs.GRADE_AGAIN, "recall-miss"
        elif delayed:
            grade, why = fsrs.GRADE_EASY, "recall-delayed"
        else:
            grade, why = fsrs.GRADE_GOOD, "recall"
        updated = fsrs.schedule(card, grade, why=why)
        await run_in_threadpool(academy_repo.upsert_fsrs_card, user_id, updated)
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo reprogramar la carta FSRS user=%s word=%s",
            user_id,
            word,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Diccionario de consulta (V3.30). D3: la consulta es SOLO LECTURA — no crea
# filas en `vocabulary` ni eventos en `vocabulary_events`. La marca de uso se
# deriva en servidor con los cómputos puros de `services/lexicon.py` (premisa
# 21); la definición/traducción viene de la caché global `dictionary_entries`
# (Fase B rellena la caché con el modelo local; hasta entonces "none").
# ---------------------------------------------------------------------------


def _normalize_lookup_word(word: str) -> str:
    """Normaliza una palabra buscada en el diccionario de consulta.

    Minúsculas, recorte de puntuación en los extremos y colapso de espacios
    (conserva apóstrofos y guiones interiores: "don't", "well-being"). Devuelve
    "" si la búsqueda queda vacía (solo puntuación/espacios).
    """
    text = (word or "").strip().lower()
    text = re.sub(r"^[^a-z0-9]+", "", text)
    text = re.sub(r"[^a-z0-9]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


# Letras válidas de un término español: ASCII más vocales acentuadas y la eñe.
# La normalización inversa NO pliega acentos (el término se usa como clave de
# caché y como `word` de la entrada: "camión" y "camion" no son la misma clave),
# pero sí acepta ambos y el matcher inverso compara plegado.
_SPANISH_EDGE_STRIP = re.compile(r"^[^0-9a-záéíóúüñ]+|[^0-9a-záéíóúüñ]+$")


def _normalize_lookup_spanish(word: str) -> str:
    """Normaliza un término buscado en dirección ES→EN (V3.39).

    Minúsculas, recorte de puntuación en los extremos, colapso de espacios y
    conservación de acentos y eñe ("camión", "mañana", "casa"). Devuelve "" si
    queda vacío (solo puntuación/espacios).
    """
    text = (word or "").strip().lower()
    text = _SPANISH_EDGE_STRIP.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _latest_activity(row: dict) -> str:
    """Marca temporal ISO (original) de la actividad léxica más reciente.

    Mismo criterio que `lexicon._last_activity_at` (V3.23, P1-01): compara los
    timestamps reales de `last_seen` (producción) y `last_exposed_at`
    (exposición) y devuelve el ORIGINAL del más reciente, normalizando
    naive/aware a UTC solo para comparar.
    """
    best = ""
    best_dt: datetime | None = None
    for candidate in (row.get("last_seen"), row.get("last_exposed_at")):
        text = (candidate or "").strip()
        if not text:
            continue
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if best_dt is None or dt > best_dt:
            best, best_dt = text, dt
    return best


def _surface_usage_from_row(row: dict) -> dict:
    """Marca de uso de la forma superficial exacta (cómputos puros de lexicon)."""
    return {
        "status": lexicon.item_status(row),
        "mastery": lexicon.item_mastery(row),
        "recall": lexicon.item_recall(row),
        "next_review_days": lexicon.next_review_days(row),
        "production_count": row.get("production_count", 0),
        "exposure_count": row.get("exposure_count", 0),
        "production_channels": lexicon.production_channels(row),
        "competence": lexicon.item_competence_matrix(row),
        "last_activity_at": _latest_activity(row),
    }


def _unit_usage_from_rows(rows: list[dict]) -> dict | None:
    """Marca de uso agregada por `lexical_unit` (derivado informativo).

    Reutiliza `lexicon.units_from_rows`: dado que `rows` es el subconjunto de
    filas de UNA unidad, el agregado devuelve una única entrada con las
    superficies y el estado derivado (máximo entre superficies).
    """
    units = lexicon.units_from_rows(rows)
    if not units:
        return None
    u = units[0]
    return {
        "lexical_unit": u["lexical_unit"],
        "status": u["status"],
        "mastery": u["mastery"],
        "recall": u["recall"],
        "surface_count": u["surface_count"],
        "mastered_surfaces": u["mastered_surfaces"],
        "recognized": u["recognized"],
        "produced": u["produced"],
        "transfer": u["transfer"],
        "production_count": u["production_count"],
        "exposure_count": u["exposure_count"],
    }


def _build_dictionary_entry(
    normalized: str, rows: list[dict], cached: dict | None
) -> dict:
    """Compone la entrada del diccionario (forma + unidad + contenido cacheado).

    Pura y determinista sobre las filas del usuario y la caché global:
    - `usage.surface`: estado de la FORMA exacta buscada, si existe;
    - `usage.unit`: agregado por `lexical_unit` solo cuando la unidad canónica
      difiere de la forma buscada (p. ej. buscar "going" agrega por "go");
    - `kind`/`cefr`: de la fila del usuario si existe; para palabra nueva, kind
      inferido con `classify_kind` (taxonomía LEXICAL_KINDS) y cefr "".
    """
    surface_rows = [r for r in rows if (r.get("word") or "").lower() == normalized]
    unit_key = lexicon.lexical_unit(surface_rows[0]) if surface_rows else normalized
    unit_rows = [r for r in rows if lexicon.lexical_unit(r) == unit_key]
    surface_row = surface_rows[0] if surface_rows else None
    tracked = bool(surface_rows or unit_rows)
    rep = surface_row or (unit_rows[0] if unit_rows else None)

    cache = cached or {}
    has_definition = bool((cache.get("definition") or "").strip())
    definition = (cache.get("definition") or "").strip() or None
    translation = (cache.get("translation") or "").strip() or None

    return {
        "word": normalized,
        "kind": ((rep.get("kind") or "") if rep is not None else "")
        or lexicon.classify_kind(normalized, source="vocabulary"),
        "cefr": (rep or {}).get("cefr", "") or "",
        "definition_source": "llm" if has_definition else "none",
        "pos": cache.get("pos", ""),
        "definition": definition,
        "translation": translation,
        # V3.38: enunciado situacional (4.º peldaño de recall). Se expone en la
        # consulta como contenido, igual que definición/traducción (no es
        # evidencia ni sirve la respuesta esperada).
        "situation": (cache.get("situation") or "").strip() or None,
        # V3.44: sentidos declarados de la unidad (`[{pos, gloss}]`). Contenido
        # aditivo que explica por qué el scoring semántico no depende de una
        # `pos` global; [] si el modelo no los dio.
        "senses": list(cache.get("senses") or []),
        "example": example_sentences.example_for(normalized),
        # V3.39 (diccionario reversible): dirección servida y alternativas de la
        # búsqueda inversa (siempre [] en EN→ES). Campos ADITIVOS.
        "direction": "en-es",
        "alternatives": [],
        "usage": {
            "tracked": tracked,
            "surface": (_surface_usage_from_row(surface_row) if surface_row else None),
            # La unidad se muestra cuando aporta información: sin forma exacta
            # (buscar la unidad canónica con filas bajo ella) o cuando la
            # unidad canónica difiere de la forma buscada (p. ej. "going" con
            # unidad "go"). Con forma exacta y unidad == forma no hay dato extra.
            "unit": (
                _unit_usage_from_rows(unit_rows)
                if unit_rows and (surface_row is None or unit_key != normalized)
                else None
            ),
        },
    }


def _build_reverse_entry(
    normalized_es: str,
    english: str,
    alternatives: list[str],
    rows: list[dict],
    content: dict | None,
) -> dict:
    """Compone la entrada ES→EN reutilizando el constructor directo (V3.39).

    La entrada describe el EQUIVALENTE INGLÉS (su definición, ejemplo, uso y
    estado de aprendizaje) pero con `word` = término español buscado y
    `translation` = equivalente inglés, de modo que la UI solo tenga que
    reetiquetar. `content` es la fila cacheada del inglés (directa o inversa).

    Pura y determinista; `alternatives` son las otras traducciones inglesas
    encontradas en la inversa instantánea (sin la principal).
    """
    base = _build_dictionary_entry(english, rows, content)
    return {
        **base,
        "word": normalized_es,
        "direction": "es-en",
        "translation": english or None,
        "alternatives": [
            word for word in alternatives if word and word.lower() != english.lower()
        ],
    }


# Vuelos en curso de generación de contenido por palabra (V3.30.1, P1-01):
# clave → Future que resuelve con la entrada cacheada (dict) o None si la
# generación falló. Evita que dos consultas simultáneas de la misma palabra
# llamen al LLM dos veces (el `INSERT OR IGNORE` protegía la fila, no la
# llamada al modelo). Best-effort por proceso (la app es de un solo proceso en
# LAN); la persistencia `ON CONFLICT DO UPDATE` mantiene la BD consistente aun
# con varias réplicas.
_inflight_content: dict[str, asyncio.Future] = {}

# Tope defensivo de espera de los waiters de un vuelo (V3.31): si el ganador
# colgara (p. ej. Ollama sin responder), los waiters degradan a None en lugar
# de quedarse esperando para siempre. La generación legítima de una palabra no
# debería acercarse a este límite.
_INFLIGHT_WAIT_SECONDS = 60.0

# Endurecimiento V3.31.1 (auditoría V3.31.0, P2), best-effort por proceso como
# `_inflight_content`:
# - Negative cache: palabra → marca de tiempo (monotónica) hasta la que NO se
#   vuelve a llamar al modelo tras un fallo reciente de generación. Evita la
#   tormenta de reintentos cuando Ollama está caído o devuelve contenido
#   inválido (cat → retry → cat → retry).
# - Rate limit de generación: ventanas deslizantes por usuario y global. Solo
#   el DUEÑO de un vuelo genera, así que cada palabra nueva consume cupo una
#   vez (los waiters que esperan un vuelo ajeno no generan ni consumen). El
#   caché evita repeticiones de la misma palabra, no la cardinalidad de
#   palabras nuevas; esto limita el abuso local (N palabras nuevas seguidas).
_negative_until: dict[str, float] = {}
_user_gen_times: dict[str, deque[float]] = defaultdict(deque)
_global_gen_times: deque[float] = deque()


def _clear_generation_state() -> None:
    """Limpia el estado global de generación del diccionario (tests).

    Vuelos en curso, negative cache y ventanas de rate limit son estado global
    por proceso; los tests que ejercitan la generación deben limpiarlo entre
    pruebas para no acoplarse por palabra/usuario."""
    _inflight_content.clear()
    _negative_until.clear()
    _user_gen_times.clear()
    _global_gen_times.clear()


def _negative_cache_hit(key: str) -> bool:
    """¿La clave `(direction, word)` está en negative cache aún vigente?

    Si el plazo ya venció, la entrada se limpia perezosamente (el siguiente
    lookup podrá reintentar la generación)."""
    until = _negative_until.get(key)
    if until is None:
        return False
    if time.monotonic() < until:
        return True
    _negative_until.pop(key, None)
    return False


def _mark_generation_failed(key: str) -> None:
    """Marca la clave `(direction, word)` como no generable durante el TTL."""
    _negative_until[key] = (
        time.monotonic() + config.DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS
    )


def _cache_key(direction: str, word: str) -> str:
    """Clave de los mapas efímeros de generación: vuelos y negative cache.

    V3.39: el contenido EN→ES y ES→EN de un mismo término son generaciones
    distintas (prompts distintos), así que no pueden compartir vuelo ni
    negative cache; se prefija la dirección.
    """
    return f"{direction}:{word}"


def _generation_quota_allowed(user_id: str) -> bool:
    """¿Hay cupo de generación nueva para `user_id` ahora?

    Consume cupo de usuario y global SOLO si ambos tienen hueco (un intento
    descartado por cupo no carga cupo). Ventanas deslizantes de 60 s, mismo
    patrón que el rate limiting de `security.py`."""
    now = time.monotonic()
    window = 60.0
    user_queue = _user_gen_times[user_id]
    while user_queue and now - user_queue[0] > window:
        user_queue.popleft()
    if len(user_queue) >= config.DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE:
        return False
    while _global_gen_times and now - _global_gen_times[0] > window:
        _global_gen_times.popleft()
    if len(_global_gen_times) >= config.DICTIONARY_MAX_GENERATIONS_PER_MINUTE_GLOBAL:
        return False
    user_queue.append(now)
    _global_gen_times.append(now)
    return True


def _content_is_fresh(entry: dict | None) -> bool:
    """Caché válida: tiene definición y fue generada con la versión actual.

    V3.30.1 (P1-03): si el contenido se generó con un prompt/política anterior
    (`generator_version` distinta de la actual, o `""` legacy previo a la
    migración) no se sirve: se regenera y sobrescribe. Evita que un cambio
    futuro de prompt deje la caché como contenido obsoleto permanente.
    """
    return bool(
        entry
        and (entry.get("definition") or "").strip()
        and entry.get("generator_version") == dictionary_content.GENERATOR_VERSION
    )


async def _generate_and_persist(
    word: str,
    *,
    model: str | None = None,
    user_id: str | None = None,
    direction: str = DIRECTION_EN_ES,
) -> dict | None:
    """Genera contenido de diccionario para `word` si la caché no es fresca.

    Relee la BD dentro del vuelo (entre el chequeo y la generación otra
    consulta pudo persistir), genera con el modelo local si sigue faltando,
    persiste con `save_entry` (inserta o sobrescribe una versión obsoleta) y
    devuelve la fila persistida. Si la generación falla o la persistencia es
    de solo lectura, devuelve el contenido en memoria o None sin lanzar: la
    consulta nunca se rompe por el generador (la definición es contenido, no
    evidencia).

    V3.31.1 (auditoría V3.31.0, P2):
    - negative cache: si la palabra falló hace menos de
      `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS`, no se vuelve a llamar al modelo
      (se degrada a None sin reintento en cascada);
    - rate limit: una generación NUEVA consume cupo de usuario/global
      (`_generation_quota_allowed`); sin cupo se degrada, nunca es un error;
    - tope del dueño: la llamada al modelo se envuelve en
      `DICTIONARY_GENERATION_TIMEOUT_SECONDS` para que un Ollama colgado no
      deje el vuelo de la palabra clavado indefinidamente (los waiters ya
      tenían su tope de 60 s; el dueño ahora también).

    V3.39: `direction` decide la tabla, el lector/escritor del repositorio y el
    generador (prompt EN→ES o ES→EN). Las cachés están SEPARADAS: el mismo
    término puede tener contenido directo e inverso distinto.
    """
    reverse = direction == DIRECTION_ES_EN
    key = _cache_key(direction, word)
    read_cached = (
        dictionary_repo.get_reverse_entry if reverse else dictionary_repo.get_entry
    )
    cached = await run_in_threadpool(read_cached, word)
    if _content_is_fresh(cached):
        return cached
    if _negative_cache_hit(key):
        logger.info(
            "Diccionario: '%s' (%s) en negative cache, se degrada", word, direction
        )
        return None
    if not _generation_quota_allowed(user_id or "?"):
        logger.warning("Diccionario: cupo de generación agotado para '%s'", word)
        return None
    generate = (
        dictionary_content.generate_reverse_content
        if reverse
        else dictionary_content.generate_content
    )
    try:
        content = await asyncio.wait_for(
            generate(word, model=model),
            timeout=config.DICTIONARY_GENERATION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Diccionario: timeout generando '%s' (%s)", word, direction)
        _mark_generation_failed(key)
        return None
    except dictionary_content.ContentUnavailableError:
        logger.warning(
            "Diccionario: contenido no disponible para '%s' (%s)", word, direction
        )
        _mark_generation_failed(key)
        return None
    except Exception:  # noqa: BLE001 — señal no bloqueante, nunca rompe la consulta
        logger.exception(
            "Diccionario: error generando contenido para '%s' (%s)", word, direction
        )
        _mark_generation_failed(key)
        return None
    _negative_until.pop(key, None)
    try:
        if reverse:
            await run_in_threadpool(
                dictionary_repo.save_reverse_entry,
                word,
                english=content.get("english", ""),
                pos=content.get("pos", ""),
                definition=content.get("definition", ""),
                situation=content.get("situation", ""),
                senses=content.get("senses") or [],
                generator_version=dictionary_content.GENERATOR_VERSION,
            )
        else:
            await run_in_threadpool(
                dictionary_repo.save_entry,
                word,
                pos=content.get("pos", ""),
                definition=content.get("definition", ""),
                translation=content.get("translation", ""),
                situation=content.get("situation", ""),
                senses=content.get("senses") or [],
                generator_version=dictionary_content.GENERATOR_VERSION,
            )
        persisted = await run_in_threadpool(read_cached, word)
    except Exception:  # noqa: BLE001 — persistir es opcional
        logger.warning("Diccionario: no se pudo persistir la caché de '%s'", word)
        persisted = None
    if persisted:
        return persisted
    fallback = {
        "pos": content.get("pos", ""),
        "definition": content.get("definition", ""),
        "situation": content.get("situation", ""),
        "senses": content.get("senses") or [],
        "generator_version": dictionary_content.GENERATOR_VERSION,
    }
    if reverse:
        fallback["english"] = content.get("english", "")
    else:
        fallback["translation"] = content.get("translation", "")
    return fallback


async def _ensure_cached_content(
    word: str,
    *,
    model: str | None = None,
    user_id: str | None = None,
    direction: str = DIRECTION_EN_ES,
) -> dict | None:
    """Devuelve el contenido cacheado disponible para `word` y `direction`.

    Single-flight (V3.30.1, P1-01): si otra consulta ya está generando la
    misma palabra, esta espera su resultado en lugar de llamar al modelo otra
    vez (exactamente UNA generación por palabra en concurrencia). Con la caché
    fresca la reutiliza (determinista); si la versión es obsoleta o no existe,
    genera, persiste y devuelve la entrada. Un fallo de generación devuelve
    None para todos (incluidos los que esperaban), sin reintentos en cascada.

    V3.31 (robustez del vuelo): si el primer cliente (dueño del vuelo) se
    cancela a mitad de generación (desconexión), su `CancelledError` no puede
    dejar a los waiters esperando un Future que nunca se resuelve: se resuelve
    con None antes de propagar la cancelación. Además los waiters esperan con
    un tope defensivo (`_INFLIGHT_WAIT_SECONDS`): si el ganador colgara por
    cualquier causa, degradan a None en vez de colgarse indefinidamente.

    V3.31.1: `user_id` identifica al DUEÑO del vuelo para el rate limit de
    generación (los waiters nunca generan ni consumen cupo); con None (uso
    interno de tests) se imputa al cubo "?".

    V3.39: el vuelo y la negative cache se indexan por `(direction, word)`:
    EN→ES y ES→EN de un mismo término son generaciones distintas.
    """
    key = _cache_key(direction, word)
    fut = _inflight_content.get(key)
    if fut is None:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        _inflight_content[key] = fut
        try:
            result = await _generate_and_persist(
                word, model=model, user_id=user_id, direction=direction
            )
            if not fut.done():
                fut.set_result(result)
        except asyncio.CancelledError:
            # El dueño del vuelo fue cancelado (cliente desconectado). La
            # generación queda truncada: se resuelve el Future para que los
            # waiters no queden colgados y se propaga la cancelación.
            if not fut.done():
                fut.set_result(None)
            raise
        except Exception:  # noqa: BLE001 — nunca romper el vuelo ni a los waiters
            logger.exception("Diccionario: fallo interno generando '%s'", word)
            if not fut.done():
                fut.set_result(None)
        finally:
            _inflight_content.pop(key, None)
    try:
        return await asyncio.wait_for(
            asyncio.shield(fut), timeout=_INFLIGHT_WAIT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Diccionario: el vuelo de '%s' agotó el tope de espera", word
        )
        return None


async def lookup_dictionary(
    user_id: str,
    word: str,
    model: str | None = None,
    direction: str = DIRECTION_EN_ES,
) -> dict:
    """Entrada del diccionario de consulta para `word` (V3.30, D3).

    Devuelve `DictionaryEntryOut`: frase de ejemplo determinista del banco y
    marca de uso/aprendizaje (solo lectura del léxico del usuario), más la
    definición/traducción generada por el modelo local y cacheada en
    `dictionary_entries` (Fase B). La primera consulta de una palabra genera y
    persiste el contenido; las siguientes son deterministas. V3.30.1 (P1-01):
    en concurrencia, N consultas simultáneas comparten UNA generación
    (single-flight); si la caché quedó obsoleta por un cambio de prompt
    (`generator_version`), se regenera y sobrescribe (P1-03). Si el modelo no
    está disponible, degrada a `definition_source="none"`.

    Sin evidencia nueva: no crea filas en `vocabulary`, no registra eventos ni
    mueve mastery. Lanza `ValueError` si la palabra queda vacía tras normalizar
    (el endpoint lo traduce a 422). `model` usa el mismo contrato que
    `/api/translate` (preferencia opcional del usuario). El contenido cacheado
    es GLOBAL y CANÓNICO: `model` solo influye en la generación de contenido
    nuevo, nunca en qué contenido se sirve (V3.31.1, semántica documentada en
    `services/dictionary_content.py`).

    V3.39 (diccionario reversible): con `direction="es-en"` la búsqueda es
    inversa — primero intenta la inversa INSTANTÁNEA sobre las traducciones ya
    cacheadas (`services.dictionary_reverse`, sin latencia del modelo) y, solo
    si no hay coincidencia, genera y cachea contenido ES→EN.
    """
    if direction == DIRECTION_ES_EN:
        return await _lookup_dictionary_reverse(user_id, word, model=model)
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada queda vacía tras normalizar")
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    cached = await _ensure_cached_content(
        normalized, model=model, user_id=user_id
    )
    return await run_in_threadpool(_build_dictionary_entry, normalized, rows, cached)


async def _lookup_dictionary_reverse(
    user_id: str, word: str, *, model: str | None = None
) -> dict:
    """Entrada del diccionario ES→EN para el término `word` (V3.39, D3).

    Dos caminos, en este orden:
    1. **Inversa instantánea** — `dictionary_reverse.match_translation` sobre
       las traducciones ya cacheadas en `dictionary_entries`. Devuelve el
       equivalente inglés y sus alternativas sin pagar latencia del modelo.
    2. **Generación** — si no hay ninguna coincidencia, genera y cachea el
       contenido ES→EN en `dictionary_reverse_entries`.
    """
    normalized = _normalize_lookup_spanish(word)
    if not normalized:
        raise ValueError("La palabra buscada queda vacía tras normalizar")
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    matches = dictionary_reverse.match_translation(normalized, entries)
    if matches:
        english = matches[0]
        content = await _ensure_cached_content(
            english, model=model, user_id=user_id
        )
        return await run_in_threadpool(
            _build_reverse_entry, normalized, english, matches[1:], rows, content
        )
    content = await _ensure_cached_content(
        normalized, model=model, user_id=user_id, direction=DIRECTION_ES_EN
    )
    english = (content or {}).get("english", "")
    return await run_in_threadpool(
        _build_reverse_entry, normalized, english, [], rows, content
    )

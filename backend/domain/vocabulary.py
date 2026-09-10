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
    example_sentences,
    fsrs,
    lexicon,
    recall,
)
from services.evidence import empty_summary as empty_evidence
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
    puntuación)."""
    if not words:
        return
    try:
        await run_in_threadpool(
            evidence_repo.record_evidence_bulk,
            user_id,
            [
                {
                    "target_type": "lexicon",
                    "target_id": word,
                    "surface_form": word,
                    "skill": channel,
                    "task": "production",
                    "activity": activity or "",
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


async def _record_retrieval(
    user_id: str,
    word: str,
    *,
    task: str = "retrieval",
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
                task=task,
                activity="drill",
                success=True,
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


async def get_recall_prompt(user_id: str, word: str) -> dict:
    """Cue del paso Recall del drill (V3.34).

    La pregunta NO depende del alumno (contenido global); `user_id` se conserva
    por simetría con el resto de funciones de drill. Si no hay cue utilizable
    (palabra sin entrada, o sin traducción ni definición que no filtre la
    respuesta), devuelve `available=false` con `cue=""`: degradación controlada
    sin evento (el peldaño muestra aviso y no rompe Sentence). La respuesta
    NUNCA incluye la forma esperada: la revela el POST tras puntuar.
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    built = recall.recall_prompt_for(normalized, entries)
    if built is None:
        return {
            "word": normalized,
            "available": False,
            "cue": "",
            "cue_kind": "",
        }
    return {
        "word": normalized,
        "available": True,
        "cue": built["cue"],
        "cue_kind": built["cue_kind"],
    }


async def submit_recall_attempt(user_id: str, word: str, answer: str) -> dict | None:
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
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada no es válida")
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    built = recall.recall_prompt_for(normalized, entries)
    if built is None:
        return None
    given = _normalize_lookup_word(answer)
    correct = bool(given) and given == normalized
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
        task="recall",
        activity="drill",
        success=correct,
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
        "example": example_sentences.example_for(normalized),
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


def _negative_cache_hit(word: str) -> bool:
    """¿La palabra está en negative cache aún vigente?

    Si el plazo ya venció, la entrada se limpia perezosamente (el siguiente
    lookup podrá reintentar la generación)."""
    until = _negative_until.get(word)
    if until is None:
        return False
    if time.monotonic() < until:
        return True
    _negative_until.pop(word, None)
    return False


def _mark_generation_failed(word: str) -> None:
    """Marca `word` como no generable durante el TTL de la negative cache."""
    _negative_until[word] = (
        time.monotonic() + config.DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS
    )


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
    word: str, *, model: str | None = None, user_id: str | None = None
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
    """
    cached = await run_in_threadpool(dictionary_repo.get_entry, word)
    if _content_is_fresh(cached):
        return cached
    if _negative_cache_hit(word):
        logger.info("Diccionario: '%s' en negative cache, se degrada", word)
        return None
    if not _generation_quota_allowed(user_id or "?"):
        logger.warning("Diccionario: cupo de generación agotado para '%s'", word)
        return None
    try:
        content = await asyncio.wait_for(
            dictionary_content.generate_content(word, model=model),
            timeout=config.DICTIONARY_GENERATION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Diccionario: timeout generando '%s'", word)
        _mark_generation_failed(word)
        return None
    except dictionary_content.ContentUnavailableError:
        logger.warning("Diccionario: contenido no disponible para '%s'", word)
        _mark_generation_failed(word)
        return None
    except Exception:  # noqa: BLE001 — señal no bloqueante, nunca rompe la consulta
        logger.exception("Diccionario: error generando contenido para '%s'", word)
        _mark_generation_failed(word)
        return None
    _negative_until.pop(word, None)
    try:
        await run_in_threadpool(
            dictionary_repo.save_entry,
            word,
            pos=content.get("pos", ""),
            definition=content.get("definition", ""),
            translation=content.get("translation", ""),
            generator_version=dictionary_content.GENERATOR_VERSION,
        )
        persisted = await run_in_threadpool(dictionary_repo.get_entry, word)
    except Exception:  # noqa: BLE001 — persistir es opcional
        logger.warning("Diccionario: no se pudo persistir la caché de '%s'", word)
        persisted = None
    if persisted:
        return persisted
    return {
        "pos": content.get("pos", ""),
        "definition": content.get("definition", ""),
        "translation": content.get("translation", ""),
        "generator_version": dictionary_content.GENERATOR_VERSION,
    }


async def _ensure_cached_content(
    word: str, *, model: str | None = None, user_id: str | None = None
) -> dict | None:
    """Devuelve contenido (`pos`/`definition`/`translation`) para `word`.

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
    """
    fut = _inflight_content.get(word)
    if fut is None:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        _inflight_content[word] = fut
        try:
            result = await _generate_and_persist(
                word, model=model, user_id=user_id
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
            _inflight_content.pop(word, None)
    try:
        return await asyncio.wait_for(
            asyncio.shield(fut), timeout=_INFLIGHT_WAIT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Diccionario: el vuelo de '%s' agotó el tope de espera", word
        )
        return None


async def lookup_dictionary(user_id: str, word: str, model: str | None = None) -> dict:
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
    en `dictionary_entries` es GLOBAL y CANÓNICO: `model` solo influye en la
    generación de contenido nuevo, nunca en qué contenido se sirve (V3.31.1,
    semántica documentada en `services/dictionary_content.py`).
    """
    normalized = _normalize_lookup_word(word)
    if not normalized:
        raise ValueError("La palabra buscada queda vacía tras normalizar")
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    cached = await _ensure_cached_content(
        normalized, model=model, user_id=user_id
    )
    return await run_in_threadpool(_build_dictionary_entry, normalized, rows, cached)

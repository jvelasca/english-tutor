"""Servicio de dominio de vocabulario."""
from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.fluency import compute_fluency
from services.pronunciation import score_pronunciation
from services.vocabulary import classify, extract_words

logger = logging.getLogger(__name__)


async def analyze_text(user_id: str, text: str) -> list[str]:
    """Registra producción del alumno (chat libre, canal `chat`) y devuelve las
    palabras extraídas."""
    words = extract_words(text)
    await run_in_threadpool(
        vocabulary_repo.record_production, user_id, words, channel="chat"
    )
    return words


async def record_production_text(
    user_id: str, text: str, channel: str
) -> list[str]:
    """Registra producción del alumno por canal (V3.19).

    Punto único por el que las superficies de práctica (speaking, writing,
    conversación guiada) vuelcan el texto producido al léxico etiquetado con su
    destreza. `record_production` mantiene la semántica agregada de
    `appearances`/`production_days` y suma la columna `<channel>_prod`.

    Nunca lanza: el volcado al léxico es señal pedagógica (no evidencia de
    mastery) y no debe romper la puntuación del flujo que lo llama. Si el canal
    no es válido o falla la escritura, registra el aviso y devuelve la lista
    extraída igualmente."""
    words = extract_words(text)
    try:
        await run_in_threadpool(
            vocabulary_repo.record_production, user_id, words, channel=channel
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
        row["status"] = classify(row["appearances"], row["production_days"])
    return rows


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
    """Léxico personal del alumno: `{summary, items}` por ítem léxico (V2.3).

    Enriquece cada fila con `status`, `recall` y `next_review_days` reutilizando
    la curva de olvido y el scheduler de repaso existentes.
    """
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
            "exposures": row["exposures"],
            "appearances": row["appearances"],
            # V3.19: desglose de producción por destreza.
            "chat_prod": row.get("chat_prod", 0),
            "speaking_prod": row.get("speaking_prod", 0),
            "writing_prod": row.get("writing_prod", 0),
            "conversation_prod": row.get("conversation_prod", 0),
        }
        for row in rows
    ]
    return {
        "summary": lexicon.summary(rows),
        "items": items,
        # P1 (§3.1): Vocabulary Coverage Indicator receptivo/productivo por
        # nivel. Es un indicador interno (no una puerta): informa, no certifica.
        "coverage": lexicon.coverage_indicator(rows),
    }


async def get_drill_candidates(user_id: str, limit: int = 8) -> list[str]:
    """Candidatos al speaking micro-drill (V3.19, premisa 21).

    Señal determinista en servidor: ítems con `exposures > 0` y
    `speaking_prod == 0`, ordenados por recuerdo ascendente y acotados a
    `limit`. Reemplaza el recálculo cliente de `recognized_not_produced`
    (SIGNAL-01/A2-07)."""
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    return lexicon.drill_candidates(rows, limit=limit)


async def submit_drill_attempt(
    user_id: str,
    word: str,
    heard: str,
    duration_seconds: float | None = None,
) -> dict:
    """Puntúa un intento de speaking micro-drill y marca la palabra producida.

    Reutiliza el scorer determinista de pronunciación (`score_pronunciation` con
    la palabra esperada) y `compute_fluency`. Si la palabra esperada aparece en
    el `breakdown.correct` (el alumno la dijo), la registra como producción de
    speaking (    `speaking_prod += 1`), lo que la saca de la lista de candidatas.
    El drill NO declara dominio ni crea evidencia curricular (D5/E3, igual que
    el micro-review de V3.16). Devuelve el scoring + `produced`."""
    result = score_pronunciation(word, heard)
    correct = result["breakdown"]["correct"]
    # La palabra "se produjo" si la dijo tal cual (alineada como correcta).
    # `word` puede ser una frase (p. ej. "living room"): se exige la frase
    # completa alineada, no solo un token.
    expected_tokens = [t for t in result["expected"].split() if t]
    produced = bool(expected_tokens) and all(
        token in correct for token in expected_tokens
    )
    if produced:
        # Volcado al léxico por destreza; nunca lanza (señal, no evidencia).
        await record_production_text(user_id, word, "speaking")
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
    }

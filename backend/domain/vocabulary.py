"""Servicio de dominio de vocabulario."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.vocabulary import classify, extract_words


async def analyze_text(user_id: str, text: str) -> list[str]:
    """Registra producción del alumno y devuelve las palabras extraídas."""
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_words, user_id, words)
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

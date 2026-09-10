"""Cola de repaso del léxico (V3.35, Longitudinal Learning Evidence 1.0).

Separa el "¿qué repaso ahora?" del speaking micro-drill (P1-2 de la auditoría
de V3.34.0). Antes, las cartas FSRS `lexicon` vencidas se inyectaban como
prioridad dentro de `GET /api/vocabulary/drill/candidates`, mezclando dos
conceptos distintos:

- REPASO ESPACIADO del léxico (cuándo volver a comprobar una palabra);
- PRODUCCIÓN ORAL pendiente (qué palabra falta decir en voz alta).

Aquí vive el primero, con una decisión pedagógica explícita:

    FSRS due → hueco de competencia → actividad óptima

`services.lexicon.review_queue_item` (puro) elige la actividad por hueco
(reconocer sin base receptiva, recuperar por texto, producir en contexto) y el
scheduler aporta la urgencia (`due_queue`: menor retrievability primero).
"""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from domain import academy as academy_service
from repositories import evidence as evidence_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon
from services.evidence import empty_summary as empty_evidence

# Tope de ítems por defecto/ máximo de la cola de repaso.
REVIEW_QUEUE_DEFAULT_LIMIT = 20
REVIEW_QUEUE_MAX_LIMIT = 50


async def get_review_queue(
    user_id: str, limit: int = REVIEW_QUEUE_DEFAULT_LIMIT
) -> dict:
    """Cola de repaso léxico: cartas FSRS `lexicon` vencidas + actividad óptima.

    Sincroniza primero el scheduling desde la evidencia (el léxico es single
    writer de sus cartas: las ya revisadas conservan `reps > 0`) y devuelve las
    cartas vencidas ordenadas por urgencia (`fsrs.due_queue`), enriquecidas con
    la competencia del ítem y la actividad recomendada.

    Nunca es una puerta (D5/E3): informa de lo que toca repasar; la actividad y
    su contenido los sirve el peldaño correspondiente (y el GET de ese peldaño
    sigue sin exponer la forma esperada).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    cards = await academy_service.sync_fsrs_cards(user_id, now=now_iso)
    lexicon_cards = [
        card
        for card in cards
        if (card.get("target_type") or "") == "lexicon"
    ]
    due = fsrs.due_queue(
        lexicon_cards, now=now_iso, limit=max(1, min(limit, REVIEW_QUEUE_MAX_LIMIT))
    )
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    by_word = {row["word"]: row for row in rows}
    # V3.35: historia longitudinal del ítem (una consulta agregada, sin N+1).
    evidence_by_word = await run_in_threadpool(
        evidence_repo.summarize_by_target, user_id, target_type="lexicon"
    )
    items: list[dict] = []
    for card in due:
        row = by_word.get(card.get("target_id") or "")
        if row is None:
            # Carta huérfana (la palabra ya no está en el léxico): se omite.
            continue
        items.append(
            lexicon.review_queue_item(
                row,
                card,
                now=now_iso,
                evidence=evidence_by_word.get(row["word"]) or empty_evidence(),
            )
        )
    return {
        "due_count": len(items),
        "items": items,
        "fsrs_version": fsrs.FSRS_VERSION,
    }

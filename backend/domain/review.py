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
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, recall
from services.evidence import empty_summary as empty_evidence
from services.example_sentences import example_for

# Tope de ítems por defecto/ máximo de la cola de repaso.
REVIEW_QUEUE_DEFAULT_LIMIT = 20
REVIEW_QUEUE_MAX_LIMIT = 50


async def get_review_queue(
    user_id: str, limit: int = REVIEW_QUEUE_DEFAULT_LIMIT
) -> dict:
    """Cola de repaso léxico: cartas FSRS `lexicon` vencidas + actividad óptima.

    Sincroniza primero el scheduling desde la evidencia (el léxico es single
    writer de sus cartas: las ya revisadas conservan `reps > 0`) y devuelve las
    cartas vencidas enriquecidas con la competencia del ítem, la actividad
    recomendada y la PRIORIDAD de la siguiente tarea óptima.

    V3.38 (planner): el orden deja de ser solo la urgencia del scheduler
    (`fsrs.due_queue`: menor retrievability primero) y pasa a ser la prioridad
    combinada de `services.planner` (olvido + hueco + debilidad + apoyo +
    latencia), con el olvido como primer componente. El scheduler sigue
    aportando `retrievability`/`stability` como señal explicable.

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
    # V3.37: la decisión pedagógica (`next_recall_rung`) se resuelve contra la
    # disponibilidad REAL de contenido (`resolve_recall_cue`), para que la cola
    # nunca recomiende un peldaño que el GET no podría servir.
    available_by_word = await _available_recall_cues(
        [card.get("target_id") or "" for card in due]
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
                available_cues=available_by_word.get(row["word"] or "", set()),
            )
        )
    # V3.38 (planner): la "siguiente tarea óptima" primero. Desempate por
    # urgencia del scheduler (menor retrievability) y, por último, palabra
    # (orden estable y determinista).
    items.sort(
        key=lambda item: (
            -float(item.get("priority") or 0.0),
            item["retrievability"] if item["retrievability"] is not None else 1.0,
            item["word"],
        )
    )
    return {
        "due_count": len(items),
        "items": items,
        "fsrs_version": fsrs.FSRS_VERSION,
    }


async def _available_recall_cues(words: list[str]) -> dict[str, set[str]]:
    """Peldaños de recall con contenido real por palabra (V3.37).

    Calcula, sobre la caché global del diccionario y el banco de pronunciación,
    qué peldaños puede servir el GET de recall para cada palabra. Es lo que
    `services.recall.resolve_recall_cue` necesita para no recomendar un peldaño
    sin contenido. Una sola lectura de la caché para todas las palabras.
    """
    unique = sorted({word for word in words if word})
    if not unique:
        return {}
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    available: dict[str, set[str]] = {}
    for word in unique:
        cues: set[str] = set()
        for cue in recall.RECALL_CUES:
            example = (
                await run_in_threadpool(example_for, word)
                if cue == "cloze"
                else None
            )
            if recall.recall_prompt_for(word, entries, cue=cue, example=example):
                cues.add(cue)
        available[word] = cues
    return available

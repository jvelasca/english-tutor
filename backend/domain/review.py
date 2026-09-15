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

import logging
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from domain import academy as academy_service
from domain import decision as decision_domain
from domain import learner_state as learner_state_domain
from repositories import decision_records as decision_records_repo
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, recall
from services.evidence import empty_summary as empty_evidence
from services.example_sentences import example_for_many

logger = logging.getLogger(__name__)

# Tope de ítems por defecto/ máximo de la cola de repaso (límite de PRESENTACIÓN).
REVIEW_QUEUE_DEFAULT_LIMIT = 20
REVIEW_QUEUE_MAX_LIMIT = 50

# V3.38.1 (P1-01): cota de CANDIDATOS que entran al planner. El planner debe
# comparar TODAS las cartas vencidas para elegir la siguiente tarea óptima; el
# recorte de presentación (`REVIEW_QUEUE_*_LIMIT`) se aplica DESPUÉS del ranking.
# Antes, el límite de presentación se pasaba a `fsrs.due_queue`, así que el
# planner solo veía el subconjunto que el scheduler ya había recortado: una
# tarea muy prioritaria podía quedar fuera. La cota es una salvaguarda de
# memoria, no una decisión pedagógica (volumen doméstico, SQLite).
REVIEW_QUEUE_CANDIDATE_LIMIT = 500

# V3.67 (P3-10): contador LOCAL de pérdida silenciosa del provenance. Cuando el
# upsert de `record_decision` falla (excepción capturada) la cola no rompe, pero
# la decisión queda SIN registrar; este contador monotónico lo hace visible (se
# expone en el informe de analítica del Bloque D) sin persistir nada.
_PROVENANCE_RECORD_FAILURES = 0

# V3.68 (P1-02): antigüedad a partir de la cual una decisión SERVIDA y nunca
# completada ni abandonada se cierra como `abandoned` por el barrido de higiene.
# Sin ventana declarada, esas filas quedarían en `served` para siempre y
# ensuciarían la lectura del provenance (no se sabría si el alumno sigue en el
# peldaño o lo dejó). 24 h es un múltiplo holgado de una sesión de estudio.
DECISION_ABANDON_AFTER_HOURS = 24


def provenance_health() -> dict:
    """Señal de salud del registro de decisiones (V3.67 → V3.68; puro).

    Devuelve la pérdida silenciosa del registro (decisiones que NO se pudieron
    escribir desde que el proceso arrancó) y la salud de la FSM del ciclo de vida
    (`decision_records.transition_health`: transiciones aplicadas, reaperturas,
    re-servicios de decisiones ya medidas y rechazos por motivo). `0` es lo sano
    en `record_failures`; un valor creciente en `transition_health.rejections`
    alerta de un `decision_id` ajeno, de un target que no cuadra o de una
    transición imposible.
    """
    return {
        "record_failures": _PROVENANCE_RECORD_FAILURES,
        "transition_health": decision_records_repo.transition_health(),
    }


def _stale_before() -> str:
    """Instante (ISO) de corte del barrido de decisiones abandonadas (V3.68).

    Puro respecto al llamador: lee el reloj UNA vez con la misma utilidad del
    repositorio y resta la ventana declarada.
    """
    return (
        datetime.now(timezone.utc)
        - timedelta(hours=DECISION_ABANDON_AFTER_HOURS)
    ).isoformat()


async def close_stale_decisions(user_id: str) -> int:
    """Barrido best-effort de decisiones servidas y nunca cerradas (V3.68, P1-02).

    Cierra como `abandoned` las decisiones del alumno que quedaron en
    `served`/`started` más allá de la ventana declarada. Es higiene del
    provenance: un fallo NUNCA rompe la cola (devuelve 0).
    """
    try:
        return await run_in_threadpool(
            decision_records_repo.close_stale,
            user_id,
            before_iso=_stale_before(),
        )
    except Exception:  # noqa: BLE001 — el barrido es higiene, no camino crítico
        logger.debug("close_stale falló para %s", user_id, exc_info=True)
        return 0


def _queue_sort_key(item: dict) -> tuple:
    """Orden de la cola: ELV, prioridad, urgencia del scheduler, palabra.

    V3.56 (Planner 2.0): manda el valor ESPERADO de aprendizaje
    (`expected_learning_value`), que combina la urgencia con la probabilidad de
    éxito de la tarea. `priority` se conserva como primer desempate (misma
    decisión de urgencia de V3.55) y el scheduler (menor retrievability) y la
    palabra cierran. Un ítem legacy sin `expected_learning_value` cae a su
    `priority`: con la degradación neutra de V3.56 ambos coinciden, así que el
    orden de V3.55.0 se reproduce exactamente.
    """
    retrievability = item.get("retrievability")
    priority = float(item.get("priority") or 0.0)
    learning_value = item.get("expected_learning_value")
    if learning_value is None:
        learning_value = priority
    return (
        -float(learning_value or 0.0),
        -priority,
        retrievability if retrievability is not None else 1.0,
        item.get("word") or "",
    )


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

    V3.38.1 (P1-01): el planner decide sobre TODAS las vencidas. `fsrs.due_queue`
    solo acota por `REVIEW_QUEUE_CANDIDATE_LIMIT`; el recorte de presentación
    (`limit`) se aplica DESPUÉS del ranking global por prioridad, de modo que la
    "siguiente tarea óptima" ya no es "la mejor del subconjunto de FSRS".

    V3.56 (Planner 2.0): el ranking pasa a ser el valor ESPERADO de aprendizaje
    (`expected_learning_value`), que combina la urgencia con la probabilidad de
    éxito de la tarea para el estado del alumno; `priority` queda como primer
    desempate. El estado del alumno se lee UNA vez (O(1), caché del Student
    Model) y sin perfil el ELV degrada EXACTAMENTE a la prioridad, así que el
    orden de V3.55.0 se conserva.

    Nunca es una puerta (D5/E3): informa de lo que toca repasar; la actividad y
    su contenido los sirve el peldaño correspondiente (y el GET de ese peldaño
    sigue sin exponer la forma esperada).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    # V3.68 (P1-02): barrido de higiene del ciclo de vida ANTES de servir. Cierra
    # como `abandoned` las decisiones que quedaron `served`/`started` más allá de
    # la ventana declarada, para que la lectura del provenance no arrastre filas
    # cuyo destino ya no puede cambiar. Best-effort: nunca rompe la cola.
    await close_stale_decisions(user_id)
    cards = await academy_service.sync_fsrs_cards(user_id, now=now_iso)
    lexicon_cards = [
        card
        for card in cards
        if (card.get("target_type") or "") == "lexicon"
    ]
    # V3.38.1: candidatos = TODAS las vencidas (acotadas por la salvaguarda),
    # no el top del scheduler.
    due = fsrs.due_queue(
        lexicon_cards, now=now_iso, limit=REVIEW_QUEUE_CANDIDATE_LIMIT
    )
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    by_word = {row["word"]: row for row in rows}
    # V3.40 (Fase 4): formas superficiales por unidad léxica, para exponer en
    # cada ítem las hermanas de su unidad (go/went/gone/going). Se calcula de las
    # filas ya leídas: coste cero de IO.
    surfaces_by_unit: dict[str, list[str]] = {}
    for row in rows:
        unit = lexicon.lexical_unit(row)
        if not unit:
            continue
        forms = surfaces_by_unit.setdefault(unit, [])
        if row["word"] not in forms:
            forms.append(row["word"])
    # V3.35: historia longitudinal del ítem (una consulta agregada, sin N+1).
    evidence_by_word = await run_in_threadpool(
        evidence_repo.summarize_by_target, user_id, target_type="lexicon"
    )
    # V3.56 (Planner 2.0): el estado del alumno se lee UNA vez por cola (O(1),
    # caché del Student Model) y se pasa a las DOS pasadas de `review_queue_item`
    # (ranking y servido), para que orden y payload no puedan divergir.
    learner_state = await learner_state_domain.learner_level_state(user_id)
    # V3.64 (cierre de P1-01): la Decision Projection se construye UNA vez por
    # cola desde las MISMAS filas canónicas que el estado (caché sellada validada
    # por frescura; si está vieja se recomputa UNA vez y se re-sella) y se pasa a
    # las DOS pasadas. Es el único punto por el que el Student Skill State
    # gobierna la decisión: el planner sigue sin leerlo.
    projection = await decision_domain.decision_projection(
        user_id,
        level=learner_state.get("practice_level") or "",
        now=now_iso,
    )
    # V3.38.1: primera pasada SIN disponibilidad de contenido. La PRIORIDAD no
    # depende del cue recomendado, así que basta para el ranking global; así el
    # coste de resolver el cue (que consulta el corpus por palabra, P2 de V3.38)
    # se paga solo por lo que se sirve.
    candidates: list[tuple[dict, dict]] = []
    for card in due:
        row = by_word.get(card.get("target_id") or "")
        if row is None:
            # Carta huérfana (la palabra ya no está en el léxico): se omite.
            continue
        candidates.append((row, card))
    items = [
        lexicon.review_queue_item(
            row,
            card,
            now=now_iso,
            evidence=evidence_by_word.get(row["word"]) or empty_evidence(),
            unit_surfaces=surfaces_by_unit.get(
                lexicon.lexical_unit(row) or "", None
            ),
            learner_state=learner_state,
            projection=projection,
        )
        for row, card in candidates
    ]
    # V3.38: la "siguiente tarea óptima" primero (ranking GLOBAL). Desempate por
    # urgencia del scheduler (menor retrievability) y, por último, palabra.
    items.sort(key=_queue_sort_key)
    # Recorte de presentación DESPUÉS del ranking.
    display_limit = max(1, min(limit, REVIEW_QUEUE_MAX_LIMIT))
    served = items[:display_limit]
    # V3.37/V3.38.1: segunda pasada (solo lo servido): resolver la decisión
    # pedagógica (`next_recall_rung`) contra la disponibilidad REAL de contenido
    # (`resolve_recall_cue`), para que la cola nunca recomiende un peldaño que el
    # GET no podría servir, sin pagar `example_for` por todas las vencidas.
    available_by_word = await _available_recall_cues(
        [item["word"] for item in served]
    )
    by_candidate_word = {row["word"]: (row, card) for row, card in candidates}
    served_items: list[dict] = []
    for item in served:
        row, card = by_candidate_word[item["word"]]
        served_items.append(
            lexicon.review_queue_item(
                row,
                card,
                now=now_iso,
                evidence=evidence_by_word.get(row["word"]) or empty_evidence(),
                available_cues=available_by_word.get(row["word"] or "", set()),
                unit_surfaces=surfaces_by_unit.get(
                    lexicon.lexical_unit(row) or "", None
                ),
                learner_state=learner_state,
                projection=projection,
            )
        )
    # V3.66 (Decision Provenance): registro append-only de CADA decisión servida.
    # Best-effort: un fallo de escritura nunca rompe la cola.
    if isinstance(projection, dict):
        await _record_decision_provenance(
            user_id, projection, served_items, by_candidate_word
        )
    return {
        "due_count": len(served_items),
        "items": served_items,
        "fsrs_version": fsrs.FSRS_VERSION,
        # V3.40 (Fase 4): roll-up por unidad léxica (aditivo). Es el estado
        # pedagógico que gobierna irregulares, phrasal verbs y chunks sin tocar
        # la evidencia por forma (cada intento sigue siendo de su `surface_form`).
        "units": lexicon.unit_evidence(rows, evidence_by_word),
    }


async def _record_decision_provenance(
    user_id: str,
    projection: dict,
    served_items: list[dict],
    by_candidate_word: dict[str, tuple[dict, dict]],
) -> None:
    """Registra una fila de PROVENANCE por decisión servida (V3.66 → V3.68).

    Solo para los ítems que traen el bloque `decision` del Planner 3.0 (es decir,
    cuando la Decision Projection gobernó el argmax). Cada fila captura la tarea
    elegida, el `p_success` y su FUENTE, el ELV, las alternativas puntuadas y los
    drivers, junto con la metadata de la TAREA (la DEFINICIÓN `task_key` y la
    INSTANCIA `task_instance_key`, la carga servida, el apoyo y el canal
    observado) y las DOS huellas de fingerprint de la decisión.

    V3.68 (P1-01): la DEFINICIÓN viaja en `task_key` y la INSTANCIA (definición +
    contexto) en `task_instance_key`. En la cola el contexto aún no existe, así
    que la instancia sale con el contexto vacío y la completa `mark_served`
    cuando el GET del peldaño declara el contexto servido.

    V3.67 (P1-02): el `decision_id` devuelto por el upsert idempotente se EXPONE
    en cada ítem servido (`item["decision_id"]`), para que el cliente lo conserve
    y haga round-trip en los GET/POST del drill. Best-effort: un fallo de
    escritura nunca rompe la cola (el ítem sale sin `decision_id`).
    """
    decision_start_fingerprint = str(
        projection.get("decision_start_fingerprint") or ""
    )
    state_fingerprint = str(projection.get("state_fingerprint") or "")
    for item in served_items:
        decision = item.get("decision")
        if not isinstance(decision, dict):
            continue
        word = item.get("word") or ""
        _, card = by_candidate_word.get(word, ({}, {}))
        target_id = str((card or {}).get("target_id") or "") or word
        task = item.get("task") or {}
        try:
            record = await run_in_threadpool(
                decision_records_repo.record_decision,
                user_id,
                target_id=target_id,
                task_key=str(item.get("task_key") or ""),
                task_signature=str(item.get("task_instance_key") or ""),
                served_load=item.get("served_load"),
                support_level=str(task.get("support_level") or ""),
                assessment_mode=str(item.get("assessment_mode") or ""),
                decision_start_fingerprint=decision_start_fingerprint,
                state_fingerprint=state_fingerprint,
                selected_skill=str(task.get("skill") or ""),
                selected_activity=str(task.get("activity") or ""),
                selected_reason=str(task.get("reason") or ""),
                p_success=decision.get("p_success"),
                p_success_source=str(decision.get("p_success_source") or ""),
                expected_learning_value=decision.get(
                    "expected_learning_value"
                ),
                candidates=decision.get("alternatives"),
                drivers=decision.get("drivers"),
            )
        except Exception:  # noqa: BLE001 — el provenance nunca rompe la cola
            global _PROVENANCE_RECORD_FAILURES
            _PROVENANCE_RECORD_FAILURES += 1
            continue
        if isinstance(record, dict) and record.get("decision_id"):
            item["decision_id"] = record["decision_id"]


async def _available_recall_cues(words: list[str]) -> dict[str, set[str]]:
    """Peldaños de recall con contenido real por palabra (V3.37).

    Calcula, sobre la caché global del diccionario y el banco de pronunciación,
    qué peldaños puede servir el GET de recall para cada palabra. Es lo que
    `services.recall.resolve_recall_cue` necesita para no recomendar un peldaño
    sin contenido. Una sola lectura de la caché para todas las palabras.

    V3.39 (Fase 3C): los ejemplos del peldaño `cloze` se resuelven con UNA sola
    pasada al banco (`example_for_many`) en lugar de un lookup por palabra
    (P2 de la auditoría).
    """
    unique = sorted({word for word in words if word})
    if not unique:
        return {}
    entries = await run_in_threadpool(dictionary_repo.list_entries)
    examples = await run_in_threadpool(example_for_many, unique)
    available: dict[str, set[str]] = {}
    for word in unique:
        example_all = examples.get(word)
        cues: set[str] = set()
        for cue in recall.RECALL_CUES:
            example = example_all if cue == "cloze" else None
            if recall.recall_prompt_for(word, entries, cue=cue, example=example):
                cues.add(cue)
        available[word] = cues
    return available

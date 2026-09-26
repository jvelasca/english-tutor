"""Endpoints de vocabulario."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

import config
from dependencies import current_user, read_audio_limited
from domain import flashcards as flashcards_service
from domain import learning as learning_service
from domain import retention as retention_service
from domain import vocabulary as vocabulary_service
from repositories import decision_records as decision_records_repo
from repositories import flashcards as flashcards_repo
from schemas.vocabulary import (
    DecisionLifecycleIn,
    DecisionLifecycleOut,
    DictionaryEntryOut,
    DictionaryLookupRequest,
    DrillAttemptOut,
    DrillCandidatesOut,
    FlashcardCardIn,
    FlashcardCardOut,
    FlashcardCardPatchIn,
    FlashcardCardsBulkIn,
    FlashcardCardsBulkOut,
    FlashcardCardsOut,
    FlashcardDeckDeleteOut,
    FlashcardDeckIn,
    FlashcardDeckMembershipIn,
    FlashcardDeckOut,
    FlashcardDecksOut,
    FlashcardQueueOut,
    FlashcardReviewIn,
    FlashcardReviewOut,
    FlashcardStatsOut,
    LexiconOut,
    RecallAttemptIn,
    RecallAttemptOut,
    RecallPromptOut,
    RecognitionAttemptIn,
    RecognitionAttemptOut,
    RecognitionQuestionOut,
    RetentionDueOut,
    RetentionReviewIn,
    RetentionReviewOut,
    SentenceAttemptOut,
    SentenceContextOut,
    TransferAttemptIn,
    TransferAttemptOut,
    TransferContextOut,
    VocabBulkAddIn,
    VocabBulkAddOut,
    VocabCollectionCreateIn,
    VocabCollectionOut,
    VocabCollectionsOut,
    VocabEnrollOut,
    VocabItemAddIn,
    VocabItemAddOut,
    VocabItemTranslationIn,
    VocabItemTranslationOut,
    VocabularyAnalyzeRequest,
    VocabularyAnalyzeResponse,
    VocabularyEventOut,
    VocabularyItem,
    WriteAttemptIn,
    WriteAttemptOut,
)
from services.stt import exceeds_max_duration, transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()


async def _mark_served(
    user_id: str,
    decision_id: str,
    *,
    target_id: str = "",
    activity: str = "",
    context_id: str = "",
    context_instance: str = "",
) -> None:
    """Round-trip V3.67 → V3.68 (P1-02/P1-03): marca la decisión como SERVIDA.

    El `decision_id` llega del ítem de la cola y el cliente lo devuelve en el GET
    del peldaño. V3.68 exige además el `user_id` (propiedad de la fila) y el
    `target_id` + la actividad EJECUTADA, y permite declarar la INSTANCIA servida
    (`context_id`/`context_instance`) cuando el peldaño la conoce. Un fallo de
    escritura nunca rompe el GET: la FSM rechaza y lo contabiliza.
    """
    if not decision_id:
        return
    try:
        await run_in_threadpool(
            decision_records_repo.mark_served,
            user_id,
            decision_id,
            target_id=target_id,
            activity=activity,
            context_id=context_id,
            context_instance=context_instance,
        )
    except Exception:  # noqa: BLE001 — el ciclo de vida es best-effort
        logger.debug("mark_served falló para %s", decision_id, exc_info=True)


async def _mark_started(
    user_id: str, decision_id: str, *, target_id: str = "", activity: str = ""
) -> None:
    """Round-trip V3.68 (P1-02): marca la decisión como INICIADA (best-effort)."""
    if not decision_id:
        return
    try:
        await run_in_threadpool(
            decision_records_repo.mark_started,
            user_id,
            decision_id,
            target_id=target_id,
            activity=activity,
        )
    except Exception:  # noqa: BLE001 — el ciclo de vida es best-effort
        logger.debug("mark_started falló para %s", decision_id, exc_info=True)


async def _mark_abandoned(
    user_id: str, decision_id: str, *, target_id: str = "", activity: str = ""
) -> None:
    """Round-trip V3.68 (P1-02): marca la decisión como ABANDONADA (best-effort)."""
    if not decision_id:
        return
    try:
        await run_in_threadpool(
            decision_records_repo.mark_abandoned,
            user_id,
            decision_id,
            target_id=target_id,
            activity=activity,
        )
    except Exception:  # noqa: BLE001 — el ciclo de vida es best-effort
        logger.debug("mark_abandoned falló para %s", decision_id, exc_info=True)


async def _mark_completed(
    user_id: str,
    decision_id: str,
    outcome: str,
    *,
    target_id: str = "",
    activity: str = "",
) -> None:
    """Round-trip V3.67 → V3.68 (P1-02/P1-03): cierra la decisión con el resultado.

    El `outcome` es el veredicto del intento (`ok`/`ko`/`unclear`), la pieza que
    habilita la calibración "¿el Planner acertó?" del Bloque D. V3.68 exige el
    `user_id` (propiedad) y el `target_id` ejecutado, y solo `ok`/`ko` puntúan en
    la calibración (`unclear` es incertidumbre de MEDICIÓN, no fallo de dominio).
    """
    if not decision_id:
        return
    try:
        await run_in_threadpool(
            decision_records_repo.mark_completed,
            user_id,
            decision_id,
            outcome,
            target_id=target_id,
            activity=activity,
        )
    except Exception:  # noqa: BLE001 — el ciclo de vida es best-effort
        logger.debug("mark_completed falló para %s", decision_id, exc_info=True)


@router.post("/api/vocabulary/analyze", response_model=VocabularyAnalyzeResponse)
async def analyze(
    body: VocabularyAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    words = await vocabulary_service.analyze_text(user["id"], body.text)
    return {"words": words}


@router.get("/api/vocabulary", response_model=list[VocabularyItem])
async def get_vocabulary(user: dict = Depends(current_user)) -> list[dict]:
    return await vocabulary_service.get_vocabulary(user["id"])


@router.get("/api/vocabulary/history", response_model=list[VocabularyEventOut])
async def vocabulary_history(
    word: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(current_user),
) -> list[dict]:
    """Historia de eventos léxicos por forma de superficie (V3.26, Eje B/F-B2).

    Ledger append-only de producciones/exposiciones/recuperaciones demoradas de
    la palabra (más reciente primero). La historia empieza en V3.26 (sin
    backfill); el agregado de `vocabulary` sigue siendo la verdad de los
    contadores."""
    return await vocabulary_service.get_vocabulary_history(
        user["id"], word=word, limit=limit, offset=offset
    )


@router.get("/api/vocabulary/lexicon", response_model=LexiconOut)
async def get_lexicon(user: dict = Depends(current_user)) -> dict:
    return await vocabulary_service.get_lexicon(user["id"])


@router.post(
    "/api/vocabulary/dictionary", response_model=DictionaryEntryOut
)
async def dictionary_lookup(
    body: DictionaryLookupRequest,
    user: dict = Depends(current_user),
) -> dict:
    """Entrada del diccionario de consulta (V3.30).

    Busca cualquier palabra (esté o no en la evidencia del alumno) y devuelve
    la frase de ejemplo determinista del banco, la marca de uso/aprendizaje
    (solo lectura del léxico del usuario) y, si existe en la caché global, la
    definición/traducción generada por el modelo local (Fase B). La consulta NO
    registra evidencia (D3): no crea filas en `vocabulary` ni eventos."""
    try:
        return await vocabulary_service.lookup_dictionary(
            user["id"], body.word, model=body.model, direction=body.direction
        )
    except ValueError:
        raise HTTPException(
            status_code=422, detail="La palabra buscada no es válida"
        ) from None


@router.get("/api/vocabulary/drill/candidates", response_model=DrillCandidatesOut)
async def drill_candidates(
    limit: int = 8, user: dict = Depends(current_user)
) -> dict:
    """Candidatos al speaking micro-drill (V3.19): expuestas (exposures > 0) y
    nunca producidas en práctica de speaking (`speaking_prod == 0`), por recuerdo
    ascendente. Señal determinista en servidor (premisa 21)."""
    words = await vocabulary_service.get_drill_candidates(user["id"], limit=limit)
    return {"words": words}


@router.post("/api/vocabulary/drill/attempt", response_model=DrillAttemptOut)
async def drill_attempt(
    word: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    """Intento de speaking micro-drill: transcribe el audio (Whisper) y puntúa la
    palabra/frase con `score_pronunciation`. Si el alumno la produjo (alineación
    secuencial `unit_produced`, V3.21/V20-01) se registra la unidad atómica
    (`speaking_prod += 1`) y sale de la lista de candidatas. No crea evidencia
    curricular ni FSRS (D5/E3)."""
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, "en")
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio del drill")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    # V3.21 (V20-13): red de seguridad de duración (audio demasiado largo).
    if exceeds_max_duration(timed.get("duration")):
        raise HTTPException(
            status_code=400,
            detail=f"El audio dura {timed['duration']:.1f}s y supera el máximo de "
            f"{config.MAX_AUDIO_DURATION_SECONDS:.0f}s permitido. Grábalo de nuevo.",
        )
    heard = timed["text"]
    asr_status = timed.get("asr_status", "ok")
    asr_confidence = timed.get("confidence")
    result = await vocabulary_service.submit_drill_attempt(
        user["id"],
        word,
        heard,
        duration_seconds=timed.get("duration"),
        asr_status=asr_status,
        asr_confidence=asr_confidence,
    )
    # V3.21 (V20-14/15): si el ASR no reconoció el audio, el intento es "unclear"
    # (ni ok ni ko): no se penaliza un fallo que pudo ser del reconocimiento.
    outcome = (
        "unclear"
        if asr_status != "ok"
        else ("ok" if result["produced"] else "ko")
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{word}:{outcome}"
    )
    return result


@router.get("/api/vocabulary/drill/sentence-context", response_model=SentenceContextOut)
async def drill_sentence_context(
    word: str = Query(..., min_length=1, max_length=120),
    decision_id: str = Query("", max_length=64),
    user: dict = Depends(current_user),
) -> dict:
    """Frase de contexto del paso Sentence del drill (V3.21/F6.1): determinista,
    sin LLM (banco de frases de pronunciación del nivel o plantilla simple)."""
    await _mark_served(
        user["id"], decision_id, target_id=word, activity="sentence"
    )
    return await vocabulary_service.get_sentence_context(user["id"], word)


@router.post(
    "/api/vocabulary/drill/sentence-attempt",
    response_model=SentenceAttemptOut,
)
async def drill_sentence_attempt(
    word: str = Form(..., max_length=120),
    file: UploadFile = File(...),
    decision_id: str = Form(""),
    user: dict = Depends(current_user),
) -> dict:
    """Intento del paso Sentence del drill (V3.21/F6.1): repite la frase de
    contexto que contiene la palabra objetivo. Acredita producción de la unidad
    solo si la palabra quedó alineada DENTRO de una frase que supera el umbral
    (`passed`). El servidor vuelve a derivar la frase (misma fuente determinista
    que el contexto) para no fiarse del cliente."""
    audio = await read_audio_limited(file)
    try:
        timed = await run_in_threadpool(transcribe_with_timing, audio, "en")
    except Exception:  # noqa: BLE001
        logger.exception("Error transcribiendo el audio del drill de frase")
        raise HTTPException(
            status_code=500, detail="No se pudo transcribir el audio"
        ) from None
    # V3.21 (V20-13): red de seguridad de duración.
    if exceeds_max_duration(timed.get("duration")):
        raise HTTPException(
            status_code=400,
            detail=f"El audio dura {timed['duration']:.1f}s y supera el máximo de "
            f"{config.MAX_AUDIO_DURATION_SECONDS:.0f}s permitido. Grábalo de nuevo.",
        )
    heard = timed["text"]
    asr_status = timed.get("asr_status", "ok")
    asr_confidence = timed.get("confidence")
    result = await vocabulary_service.submit_sentence_attempt(
        user["id"],
        word,
        heard,
        duration_seconds=timed.get("duration"),
        asr_status=asr_status,
        asr_confidence=asr_confidence,
    )
    # V3.21 (V20-14/15): intento "unclear" si el ASR no reconoció el audio.
    outcome = (
        "unclear"
        if asr_status != "ok"
        else ("ok" if result["passed"] else "ko")
    )
    await _mark_completed(
        user["id"],
        decision_id,
        outcome,
        target_id=word,
        activity="sentence",
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{word}:sentence:{outcome}"
    )
    return result


@router.post(
    "/api/vocabulary/drill/write-attempt",
    response_model=WriteAttemptOut,
)
async def drill_write_attempt(
    body: WriteAttemptIn,
    user: dict = Depends(current_user),
) -> dict:
    """Actividad de escritura del drill (V3.39, Fase 3).

    El alumno escribe una frase PROPIA que use la palabra objetivo. Puntúa el
    servidor (premisa 21) de forma determinista y sin LLM: la unidad alineada
    (`unit_produced`) y una longitud mínima. Al superarla se acredita la
    modalidad `written_production` (volcado `writing_prod`) y se registra la
    evidencia `activity_id="drill:write"` — es lo que cierra el hueco
    `spoken ✓ / written ✗` que el motor de tarea óptima detecta. En fallo
    también se registra el intento clasificado. El paso no graba recuperación
    ni FSRS y no declara dominio (D5/E3).

    V3.68 (P1-02): este es el ÚNICO peldaño sin GET propio (su consigna es la
    propia palabra objetivo), así que el POST declara el `served` antes de
    cerrar: la llegada del intento con `decision_id` es la prueba de que el
    peldaño se sirvió. Sin esa declaración la FSM rechazaría
    `computed → completed` y la medición se perdería. Es idempotente cuando el
    peldaño ya venía `served`."""
    await _mark_served(
        user["id"], body.decision_id, target_id=body.word, activity="write"
    )
    result = await vocabulary_service.submit_write_attempt(
        user["id"],
        body.word,
        body.text,
        response_time_ms=body.response_time_ms,
    )
    outcome = "ok" if result["passed"] else "ko"
    await _mark_completed(
        user["id"], body.decision_id, outcome, target_id=body.word, activity="write"
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{body.word}:write:{outcome}"
    )
    return result


@router.get(
    "/api/vocabulary/drill/transfer-context",
    response_model=TransferContextOut,
)
async def drill_transfer_context(
    word: str = Query(..., min_length=1, max_length=120),
    decision_id: str = Query("", max_length=64),
    user: dict = Depends(current_user),
) -> dict:
    """Consigna de TRANSFERENCIA del drill (V3.40 → V3.43).

    Servicio de solo lectura: elige un contexto NUEVO (banco curado) que el ítem
    aún no haya usado, priorizando el más DISTANTE de los ya logrados con éxito
    (V3.43/P1-03). La consigna da un ESCENARIO y un objetivo comunicativo y
    **nunca contiene la unidad objetivo** (V3.43/P1-01): la producción es del
    alumno (modalidad `spontaneous_use`). El `context_id` que devuelve es el que
    el intento registra en el ledger.
    """
    normalized = (word or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=422, detail="La palabra buscada no es válida"
        )
    # V3.68 (P1-01/P1-02): la consigna se sirve ANTES de marcar el peldaño para
    # poder declarar la INSTANCIA realmente servida (`context_id` y su slug, que
    # es lo que completa la clave de instancia de la decisión). Marcar el peldaño
    # nunca rompe el GET (best-effort).
    context = await vocabulary_service.get_transfer_context(user["id"], normalized)
    await _mark_served(
        user["id"],
        decision_id,
        target_id=normalized,
        activity="transfer",
        context_id=str(context.get("context_id") or ""),
        context_instance=str(context.get("context_instance") or ""),
    )
    return context


@router.post(
    "/api/vocabulary/drill/transfer-attempt",
    response_model=TransferAttemptOut,
)
async def drill_transfer_attempt(
    body: TransferAttemptIn,
    user: dict = Depends(current_user),
) -> dict:
    """Intento del paso Transfer del drill (V3.40 → V3.43).

    El alumno usa la unidad en un contexto NUEVO. Puntúa el servidor (premisa
    21) de forma determinista y sin LLM: unidad alineada + longitud mínima
    (`services.lexicon.score_transfer_attempt`), más un proxy de ADECUACIÓN
    semántica (V3.43/P1-02) que separa el uso correcto del sospechoso sin
    bloquear el éxito léxico. Al superarlo se acredita la modalidad
    `spontaneous_use` con evidencia `activity_id="drill:transfer"` y el
    `context_id` del contexto nuevo; un uso sospechoso añade
    `error_type="semantic_mismatch"` y no cuenta como ÉXITO LIMPIO del estado de
    transferencia. En fallo también se registra el intento clasificado. No graba
    recuperación ni FSRS y no declara dominio.
    """
    result = await vocabulary_service.submit_transfer_attempt(
        user["id"],
        body.word,
        body.text,
        context_id=body.context_id,
        response_time_ms=body.response_time_ms,
        context_instance=body.context_instance,
    )
    outcome = "ok" if result["passed"] else "ko"
    await _mark_completed(
        user["id"],
        body.decision_id,
        outcome,
        target_id=body.word,
        activity="transfer",
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{body.word}:transfer:{outcome}"
    )
    return result


@router.get(
    "/api/vocabulary/drill/recognition", response_model=RecognitionQuestionOut
)
async def drill_recognition_question(
    word: str = Query(..., min_length=1, max_length=120),
    decision_id: str = Query("", max_length=64),
    user: dict = Depends(current_user),
) -> dict:
    """Pregunta del paso Recognition del drill (V3.33, eslabón 2 del puente).

    MCQ definición ↔ palabra determinista por (palabra, question_id) (sin estado
    servidor, premisa 21): el servidor la recomputa al puntuar. La pregunta solo
    depende de la caché global `dictionary_entries`, nunca de la evidencia del
    alumno. V3.33.1: entrega un `question_id` (nonce por intento) que el POST
    reenvía para reconstruir la misma permutación; así la posición de la
    correcta cambia entre intentos. Si no hay contenido suficiente devuelve
    `available=false` con `options=[]` (degradación controlada, sin evento). La
    respuesta NUNCA incluye la opción correcta: el POST es quien puntúa."""
    try:
        await _mark_served(
            user["id"], decision_id, target_id=word, activity="recognition"
        )
        return await vocabulary_service.get_recognition_question(
            user["id"], word
        )
    except ValueError:
        raise HTTPException(
            status_code=422, detail="La palabra buscada no es válida"
        ) from None


@router.post(
    "/api/vocabulary/drill/recognition-attempt",
    response_model=RecognitionAttemptOut,
)
async def drill_recognition_attempt(
    body: RecognitionAttemptIn,
    user: dict = Depends(current_user),
) -> dict:
    """Intento del paso Recognition del drill (V3.33).

    El servidor recomputa la pregunta con la misma función pura (premisa 21) y
    el `question_id` recibido como seed (V3.33.1), puntuando `selected_index`.
    Evidencia SOLO informativa (V3.13: el MC de reconocimiento no demuestra
    destrezas productivas): registra el evento `learning_events`
    `drill:<word>:recognition:ok|ko` y NO escribe en
    `vocabulary`/`vocabulary_events` ni mueve FSRS/mastery/usage. Si la palabra
    ya no tiene pregunta (contenido desaparecido), responde 409 sin evento."""
    try:
        result = await vocabulary_service.submit_recognition_attempt(
            user["id"], body.word, body.selected_index, body.question_id
        )
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Intento de reconocimiento no válido"
        ) from None
    if result is None:
        raise HTTPException(
            status_code=409,
            detail="La palabra ya no tiene pregunta de reconocimiento",
        ) from None
    outcome = "ok" if result["correct"] else "ko"
    await _mark_completed(
        user["id"],
        body.decision_id,
        outcome,
        target_id=str(result["word"]),
        activity="recognition",
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{result['word']}:recognition:{outcome}"
    )
    return result


@router.get("/api/vocabulary/drill/recall", response_model=RecallPromptOut)
async def drill_recall_prompt(
    word: str = Query(..., min_length=1, max_length=120),
    cue: str = Query("", max_length=32),
    decision_id: str = Query("", max_length=64),
    user: dict = Depends(current_user),
) -> dict:
    """Cue del paso Recall del drill (V3.34; peldaños graduados en V3.37).

    Camino inverso a Recognition: el alumno ve el SIGNIFICADO (cue) y debe
    recuperar/teclear la palabra. Puro y determinista sobre la caché global
    `dictionary_entries` (sin estado servidor, premisa 21): el servidor
    re-deriva el cue al puntuar. Si no hay cue utilizable devuelve
    `available=false` con `cue=""` (degradación controlada, sin evento). La
    respuesta NUNCA incluye la palabra esperada.

    V3.37: el parámetro opcional `cue` pide un peldaño concreto
    (`translation`/`definition`/`cloze`); sin él se conserva la escalera por
    defecto de V3.34 (traducción y, si no, definición). Un `cue` no soportado
    responde 422 sin evento."""
    try:
        await _mark_served(
            user["id"], decision_id, target_id=word, activity="recall"
        )
        return await vocabulary_service.get_recall_prompt(
            user["id"], word, cue or None
        )
    except ValueError:
        raise HTTPException(
            status_code=422, detail="La palabra buscada no es válida"
        ) from None


@router.post(
    "/api/vocabulary/drill/recall-attempt",
    response_model=RecallAttemptOut,
)
async def drill_recall_attempt(
    body: RecallAttemptIn,
    user: dict = Depends(current_user),
) -> dict:
    """Intento del paso Recall del drill (V3.34).

    El servidor re-deriva el cue con la misma función pura (premisa 21) y
    compara la respuesta con la palabra (forma de superficie normalizada). En
    acierto deja señal léxica PROPIA (recall + evento `recalled`; nunca
    producción), acredita la recuperación demorada si el intento supera el
    intervalo de retención y reprograma la carta FSRS `lexicon` de la palabra.
    En fallo solo aplica el lapse FSRS si la palabra ya estaba rastreada. Si la
    palabra ya no tiene pregunta, responde 409 sin evento.
    V3.36: la latencia del cliente (`response_time_ms`) se persiste como
    dimensión observacional del evento; no interviene en la puntuación.
    V3.37: `cue` declara el peldaño servido y el servidor lo re-deriva; un
    peldaño no soportado o sin contenido responde 422 sin evento."""
    try:
        result = await vocabulary_service.submit_recall_attempt(
            user["id"],
            body.word,
            body.answer,
            cue=body.cue or None,
            response_time_ms=body.response_time_ms,
        )
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Intento de recall no válido"
        ) from None
    if result is None:
        raise HTTPException(
            status_code=409,
            detail="La palabra ya no tiene pregunta de recall",
        ) from None
    outcome = "ok" if result["correct"] else "ko"
    await _mark_completed(
        user["id"],
        body.decision_id,
        outcome,
        target_id=str(result["word"]),
        activity="recall",
    )
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{result['word']}:recall:{outcome}"
    )
    return result


@router.post(
    "/api/vocabulary/drill/decision-lifecycle",
    response_model=DecisionLifecycleOut,
)
async def drill_decision_lifecycle(
    body: DecisionLifecycleIn,
    user: dict = Depends(current_user),
) -> dict:
    """Evento del ciclo de vida de una decisión servida (V3.68, P1-02).

    Cierra los dos estados que NINGÚN POST de intento puede observar:

    - `started`   — el alumno abrió el peldaño (el intento empezó de verdad);
    - `abandoned` — el alumno salió sin completarlo.

    La FSM del provenance decide si la transición es válida: si llega tarde (la
    decisión ya está `completed`), si es de otro usuario o si el `target_id` no
    cuadra, la rechaza y lo CONTABILIZA, pero responde `applied=false` sin error.
    El drill nunca puede romperse por esto: es telemetría del ciclo de vida.

    `applied` es el acuse honesto: `True` solo si el estado cambió de verdad.
    """
    if not body.decision_id:
        return {"applied": False, "decision_id": "", "event": body.event}
    applied = False
    if body.event == "started":
        applied = await run_in_threadpool(
            decision_records_repo.mark_started,
            user["id"],
            body.decision_id,
            target_id=body.target_id,
            activity=body.activity,
        )
    else:
        applied = await run_in_threadpool(
            decision_records_repo.mark_abandoned,
            user["id"],
            body.decision_id,
            target_id=body.target_id,
            activity=body.activity,
        )
    return {
        "applied": bool(applied),
        "decision_id": body.decision_id,
        "event": body.event,
    }


# --- Retención Personal (ingestión + sesión tarjetas) ---------------------


@router.post("/api/vocabulary/items", response_model=VocabItemAddOut)
async def add_vocabulary_item(
    body: VocabItemAddIn, user: dict = Depends(current_user)
) -> dict:
    """Añade una palabra suelta al léxico personal + carta FSRS (sin mastery)."""
    result = await retention_service.add_item(
        user["id"],
        body.word,
        translation=body.translation,
        collection_id=body.collection_id,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Palabra no válida")
    return result


@router.patch(
    "/api/vocabulary/items", response_model=VocabItemTranslationOut
)
async def set_vocabulary_item_translation(
    body: VocabItemTranslationIn, user: dict = Depends(current_user)
) -> dict:
    """Corrige la traducción propia de una palabra del léxico (V3.80.0).

    Es la pieza que hace que la cara B de una tarjeta deje de ser un callejón sin
    salida: el alumno escribe o corrige el reverso y su texto **manda** sobre el
    pack y sobre la caché del diccionario. Solo escribe la fila del usuario de la
    sesión y **no crea vocabulario**: si la palabra no está en su léxico, es un
    404, no un alta encubierta (invariante D3)."""
    result = await vocabulary_service.set_item_translation(
        user["id"], body.word, body.translation
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail="Palabra no encontrada en tu léxico"
        )
    return result


@router.post("/api/vocabulary/items/bulk", response_model=VocabBulkAddOut)
async def add_vocabulary_bulk(
    body: VocabBulkAddIn, user: dict = Depends(current_user)
) -> dict:
    """Pega una lista de palabras (una por línea; opcional word,translation)."""
    result = await retention_service.add_bulk(
        user["id"],
        body.text,
        title=body.title,
        collection_id=body.collection_id,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Lista no válida")
    return result


@router.get("/api/vocabulary/collections", response_model=VocabCollectionsOut)
async def list_vocab_collections(user: dict = Depends(current_user)) -> dict:
    return await retention_service.list_collections(user["id"])


@router.post(
    "/api/vocabulary/collections", response_model=VocabCollectionOut
)
async def create_vocab_collection(
    body: VocabCollectionCreateIn, user: dict = Depends(current_user)
) -> dict:
    result = await retention_service.create_collection(user["id"], body.title)
    if result is None:
        raise HTTPException(status_code=400, detail="No se pudo crear la lista")
    return result


@router.post(
    "/api/vocabulary/collections/{collection_id}/enroll",
    response_model=VocabEnrollOut,
)
async def enroll_vocab_collection(
    collection_id: int, user: dict = Depends(current_user)
) -> dict:
    result = await retention_service.enroll_collection(user["id"], collection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    return result


@router.get("/api/vocabulary/retention/due", response_model=RetentionDueOut)
async def retention_due(
    limit: int = Query(20, ge=1, le=20),
    collection_id: int | None = None,
    user: dict = Depends(current_user),
) -> dict:
    """Cola due de cartas lexicon para la sesión de retención (estilo Anki)."""
    return await retention_service.retention_due(
        user["id"], limit=limit, collection_id=collection_id
    )


@router.post(
    "/api/vocabulary/retention/review", response_model=RetentionReviewOut
)
async def retention_review(
    body: RetentionReviewIn, user: dict = Depends(current_user)
) -> dict:
    """Grade 1–4 (Again/Hard/Good/Easy) → reprograma FSRS; evento informativo.

    V3.78.0: delega en el servicio de Flashcards para que TODA calificación de
    una carta `lexicon` pase por el mismo escritor y deje su fila en
    `flashcard_reviews`. El ledger es lo que definen «tarjeta nueva» y los
    límites del día: si este endpoint siguiera agendando por su cuenta, una
    palabra calificada aquí contaría como nueva para siempre.
    """
    result = await flashcards_service.review_card(
        user["id"],
        flashcards_repo.AUTO_DECK_ID,
        flashcards_service.CARD_TYPE_LEXICON,
        body.word,
        body.grade,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Review de retención no válido")
    return {
        "word": result["card_id"],
        "grade": result["grade"],
        "due_at": result["due_at"],
        "next_in_days": result["next_in_days"],
        "stability": result["stability"],
        "retrievability": result["retrievability"],
        "reps": result["reps"],
    }


# --- V3.78.0: modo Flashcards (mazos manuales + mazo automático virtual) -----
#
# El mazo automático (`id = 0`) es una VISTA del léxico, no una fila: por eso
# rechaza la escritura en vez de aceptarla y guardarla en algún sitio raro.


@router.get("/api/vocabulary/decks", response_model=FlashcardDecksOut)
async def list_flashcard_decks(user: dict = Depends(current_user)) -> dict:
    """Mazos del alumno: el automático (todo el léxico) + los manuales."""
    return await flashcards_service.list_decks(user["id"])


@router.post("/api/vocabulary/decks", response_model=FlashcardDeckOut)
async def create_flashcard_deck(
    body: FlashcardDeckIn, user: dict = Depends(current_user)
) -> dict:
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Nombre de mazo requerido")
    result = await flashcards_service.create_deck(
        user["id"],
        name=body.name or "",
        new_per_day=body.new_per_day,
        review_per_day=body.review_per_day,
    )
    if result is None:
        # Con el nombre ya validado y el usuario tomado de la sesión, el único
        # desenlace posible aquí es la colisión `UNIQUE (user_id, name)`: se
        # declara con un código para que la UI lo diga («ya tienes un mazo con
        # ese nombre») en vez de un genérico que oculta el selector. Es un
        # código máquina, como `SESSION_REQUIRED`, no un texto para el alumno.
        raise HTTPException(status_code=400, detail="DECK_NAME_TAKEN")
    return result


@router.patch(
    "/api/vocabulary/decks/{deck_id}", response_model=FlashcardDeckOut
)
async def update_flashcard_deck(
    deck_id: int, body: FlashcardDeckIn, user: dict = Depends(current_user)
) -> dict:
    result = await flashcards_service.update_deck(
        user["id"],
        deck_id,
        name=body.name,
        new_per_day=body.new_per_day,
        review_per_day=body.review_per_day,
    )
    if result is None:
        # Incluye el mazo automático: es del sistema y no se edita.
        raise HTTPException(status_code=400, detail="Mazo no editable")
    return result


@router.delete(
    "/api/vocabulary/decks/{deck_id}", response_model=FlashcardDeckDeleteOut
)
async def delete_flashcard_deck(
    deck_id: int, user: dict = Depends(current_user)
) -> dict:
    """Borra un mazo manual (V3.86.0).

    Devuelve cuántas fichas se borraron (`deleted_count`) y cuántas se
    conservaron por estar también en otro mazo (`shared_count`), para que la UI
    pueda avisar antes/después con datos reales. El mazo automático no se borra.
    """
    result = await flashcards_service.delete_deck(user["id"], deck_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Mazo no encontrado")
    return result


@router.get(
    "/api/vocabulary/decks/{deck_id}/queue", response_model=FlashcardQueueOut
)
async def flashcard_queue(
    deck_id: int,
    limit: int = Query(100, ge=1, le=100),
    collection_id: int | None = None,
    user: dict = Depends(current_user),
) -> dict:
    """Cola de estudio: repasos vencidos primero, después las nuevas, recortada
    por los límites del día del mazo."""
    result = await flashcards_service.deck_queue(
        user["id"], deck_id, collection_id=collection_id, limit=limit
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Mazo no encontrado")
    return result


@router.post(
    "/api/vocabulary/decks/{deck_id}/review", response_model=FlashcardReviewOut
)
async def flashcard_review(
    deck_id: int, body: FlashcardReviewIn, user: dict = Depends(current_user)
) -> dict:
    """Grade 1–4 → reprograma la carta y anota la revisión en el ledger."""
    result = await flashcards_service.review_card(
        user["id"], deck_id, body.card_type, body.card_id, body.grade
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Review de tarjeta no válido")
    return result


@router.post(
    "/api/vocabulary/decks/{deck_id}/cards/bulk",
    response_model=FlashcardCardsBulkOut,
)
async def add_flashcard_cards_bulk(
    deck_id: int, body: FlashcardCardsBulkIn, user: dict = Depends(current_user)
) -> dict:
    """Pega una lista de tarjetas: una por línea, `anverso,reverso[,recordatorio]`.

    Mismo parser que el pegado de palabras del léxico, para que el alumno solo
    tenga que aprenderse una sintaxis. Sin efectos FSRS: las tarjetas nacen
    «nuevas» y se programan al calificarlas, como las creadas de una en una.
    """
    result = await flashcards_service.add_cards_bulk(
        user["id"], deck_id, text=body.text
    )
    if result is None:
        raise HTTPException(
            status_code=400, detail="Mazo no válido para añadir tarjetas"
        )
    return result


# --- V3.86.0: endpoints FICHA-PRIMERO (el id de ficha es global del usuario) ---
#
# El contrato nuevo desacopla la ficha de su mazo: una ficha se identifica por
# `card_id` y su pertenencia a mazos (1..N) se lee/escribe aparte. Los endpoints
# `.../decks/{deck_id}/cards...` de V3.78–V3.85.1 quedan como ENVOLTORIOS finos
# (deprecados) para no romper clientes, pero ya no son la fuente de verdad.


@router.get("/api/vocabulary/cards", response_model=FlashcardCardsOut)
async def list_vocabulary_cards(
    deck_id: int | None = Query(None),
    user: dict = Depends(current_user),
) -> dict:
    """Todas las fichas del alumno (o las de un mazo, si se filtra).

    Card-first: sin `deck_id` devuelve el conjunto completo, cada ficha con sus
    mazos (`deck_ids`) y su recordatorio. Es lo que necesita la pestaña Fichas,
    que ya no obliga a elegir un mazo.
    """
    if deck_id is None:
        cards = await flashcards_service.list_all_cards(user["id"])
    else:
        cards = await flashcards_service.list_cards(user["id"], deck_id)
    return {"cards": cards}


@router.post("/api/vocabulary/cards", response_model=FlashcardCardOut)
async def create_vocabulary_card(
    body: FlashcardCardIn, user: dict = Depends(current_user)
) -> dict:
    """Crea una ficha en uno o varios mazos (`deck_ids`; `deck_id` legacy)."""
    result = await flashcards_service.create_card(
        user["id"],
        front=body.front,
        back=body.back,
        mnemonic=body.mnemonic,
        deck_ids=body.deck_ids or None,
        deck_id=body.deck_id,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Elige al menos un mazo válido (el automático no admite fichas)",
        )
    return result


@router.patch(
    "/api/vocabulary/cards/{card_id}", response_model=FlashcardCardOut
)
async def update_vocabulary_card(
    card_id: int,
    body: FlashcardCardPatchIn,
    user: dict = Depends(current_user),
) -> dict:
    """Edita anverso/reverso/recordatorio y/o reemplaza los mazos de la ficha.

    Parcial: un campo ausente no se toca (editar solo el recordatorio no obliga a
    reenviar el anverso). Si llega `deck_ids`, el conjunto no puede quedar vacío.
    """
    result = await flashcards_service.update_card(
        user["id"],
        card_id,
        front=body.front,
        back=body.back,
        mnemonic=body.mnemonic,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    if body.deck_ids is not None:
        updated = await flashcards_service.set_card_decks(
            user["id"], card_id, body.deck_ids
        )
        if updated is None:
            raise HTTPException(
                status_code=400, detail="La ficha debe pertenecer a algún mazo"
            )
        result = updated
    return result


@router.delete("/api/vocabulary/cards/{card_id}", status_code=204)
async def delete_vocabulary_card(
    card_id: int, user: dict = Depends(current_user)
) -> None:
    if not await flashcards_service.delete_card(user["id"], card_id):
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")


@router.post(
    "/api/vocabulary/cards/{card_id}/decks", response_model=FlashcardCardOut
)
async def add_vocabulary_card_to_deck(
    card_id: int,
    body: FlashcardDeckMembershipIn,
    user: dict = Depends(current_user),
) -> dict:
    """Añade la ficha a un mazo sin tocar sus otras pertenencias."""
    result = await flashcards_service.add_card_to_deck(
        user["id"], card_id, body.deck_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Ficha o mazo no encontrado")
    return result


@router.delete(
    "/api/vocabulary/cards/{card_id}/decks/{deck_id}", status_code=204
)
async def remove_vocabulary_card_from_deck(
    card_id: int, deck_id: int, user: dict = Depends(current_user)
) -> None:
    """Quita la ficha de un mazo. Si era su última pertenencia, la ficha se borra.

    204 siempre que la operación se aplicara: la UI refresca la lista y ve si la
    ficha sigue (seguía en otro mazo) o desaparece (era la última).
    """
    result = await flashcards_service.remove_card_from_deck(
        user["id"], card_id, deck_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Ficha o mazo no encontrado")


# --- Envoltorios LEGACY de V3.78–V3.85.1 (deprecados) ------------------------


@router.get(
    "/api/vocabulary/decks/{deck_id}/cards", response_model=FlashcardCardsOut
)
async def list_flashcard_cards(
    deck_id: int, user: dict = Depends(current_user)
) -> dict:
    """DEPRECADO (V3.86.0): usa `GET /api/vocabulary/cards?deck_id=`."""
    cards = await flashcards_service.list_cards(user["id"], deck_id)
    return {"cards": cards}


@router.post(
    "/api/vocabulary/decks/{deck_id}/cards", response_model=FlashcardCardOut
)
async def create_flashcard_card(
    deck_id: int, body: FlashcardCardIn, user: dict = Depends(current_user)
) -> dict:
    """DEPRECADO (V3.86.0): usa `POST /api/vocabulary/cards` con `deck_ids`."""
    result = await flashcards_service.create_card(
        user["id"],
        deck_id,
        front=body.front,
        back=body.back,
        mnemonic=body.mnemonic,
        deck_ids=body.deck_ids or None,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="No se pudo crear la tarjeta")
    return result


@router.patch(
    "/api/vocabulary/decks/{deck_id}/cards/{card_id}",
    response_model=FlashcardCardOut,
)
async def update_flashcard_card(
    deck_id: int,
    card_id: int,
    body: FlashcardCardPatchIn,
    user: dict = Depends(current_user),
) -> dict:
    """DEPRECADO (V3.86.0): usa `PATCH /api/vocabulary/cards/{card_id}`.

    Conserva la comprobación de que la ficha PERTENEZCA al mazo declarado, para
    no cambiar la semántica de los clientes antiguos.
    """
    if not await flashcards_service.card_belongs_to_deck(
        user["id"], card_id, deck_id
    ):
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    result = await flashcards_service.update_card(
        user["id"],
        card_id,
        front=body.front,
        back=body.back,
        mnemonic=body.mnemonic,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    if body.deck_ids is not None:
        updated = await flashcards_service.set_card_decks(
            user["id"], card_id, body.deck_ids
        )
        if updated is None:
            raise HTTPException(
                status_code=400, detail="La ficha debe pertenecer a algún mazo"
            )
        result = updated
    return result


@router.delete(
    "/api/vocabulary/decks/{deck_id}/cards/{card_id}", status_code=204
)
async def delete_flashcard_card(
    deck_id: int, card_id: int, user: dict = Depends(current_user)
) -> None:
    """DEPRECADO (V3.86.0): usa `DELETE /api/vocabulary/cards/{card_id}`."""
    if not await flashcards_service.card_belongs_to_deck(
        user["id"], card_id, deck_id
    ):
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    if not await flashcards_service.delete_card(user["id"], card_id):
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")


@router.get(
    "/api/vocabulary/decks/{deck_id}/stats", response_model=FlashcardStatsOut
)
async def flashcard_stats(
    deck_id: int, user: dict = Depends(current_user)
) -> dict:
    result = await flashcards_service.deck_stats(user["id"], deck_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Mazo no encontrado")
    return result


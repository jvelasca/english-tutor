"""Endpoints de vocabulario."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

import config
from dependencies import current_user, read_audio_limited
from domain import learning as learning_service
from domain import vocabulary as vocabulary_service
from schemas.vocabulary import (
    DictionaryEntryOut,
    DictionaryLookupRequest,
    DrillAttemptOut,
    DrillCandidatesOut,
    LexiconOut,
    RecognitionAttemptIn,
    RecognitionAttemptOut,
    RecognitionQuestionOut,
    SentenceAttemptOut,
    SentenceContextOut,
    VocabularyAnalyzeRequest,
    VocabularyAnalyzeResponse,
    VocabularyEventOut,
    VocabularyItem,
)
from services.stt import exceeds_max_duration, transcribe_with_timing

logger = logging.getLogger(__name__)

router = APIRouter()


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
            user["id"], body.word, model=body.model
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
    user: dict = Depends(current_user),
) -> dict:
    """Frase de contexto del paso Sentence del drill (V3.21/F6.1): determinista,
    sin LLM (banco de frases de pronunciación del nivel o plantilla simple)."""
    return await vocabulary_service.get_sentence_context(user["id"], word)


@router.post(
    "/api/vocabulary/drill/sentence-attempt",
    response_model=SentenceAttemptOut,
)
async def drill_sentence_attempt(
    word: str = Form(..., max_length=120),
    file: UploadFile = File(...),
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
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{word}:sentence:{outcome}"
    )
    return result


@router.get(
    "/api/vocabulary/drill/recognition", response_model=RecognitionQuestionOut
)
async def drill_recognition_question(
    word: str = Query(..., min_length=1, max_length=120),
    user: dict = Depends(current_user),
) -> dict:
    """Pregunta del paso Recognition del drill (V3.33, eslabón 2 del puente).

    MCQ definición ↔ palabra determinista por palabra (sin estado servidor,
    premisa 21): el servidor la recomputa al puntuar. La pregunta solo depende
    de la caché global `dictionary_entries`, nunca de la evidencia del alumno.
    Si no hay contenido suficiente devuelve `available=false` con `options=[]`
    (degradación controlada, sin evento). La respuesta NUNCA incluye la opción
    correcta: el POST es quien puntúa."""
    try:
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
    puntúa `selected_index`. Evidencia SOLO informativa (V3.13: el MC de
    reconocimiento no demuestra destrezas productivas): registra el evento
    `learning_events` `drill:<word>:recognition:ok|ko` y NO escribe en
    `vocabulary`/`vocabulary_events` ni mueve FSRS/mastery/usage. Si la palabra
    ya no tiene pregunta (contenido desaparecido), responde 409 sin evento."""
    try:
        result = await vocabulary_service.submit_recognition_attempt(
            user["id"], body.word, body.selected_index
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
    await learning_service.record_event(
        user["id"], "exercise", f"drill:{result['word']}:recognition:{outcome}"
    )
    return result

"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import listening as listening_repo
from repositories import settings as settings_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, listening_bridge, listening_review, sense_context, tts
from services.audio_library import is_recorded, recorded_audio_path
from services.auditory_profile import auditory_profile
from services.curriculum import LISTENING_BANK_VERSION
from services.listening import (
    AUDIO_VARIANTS,
    DERIVED_BY_ID,
    DERIVED_PRODUCTION_POOL,
    DERIVED_RECOGNITION_POOL,
    GENERATED_ID_PREFIX,
    LEVEL_ORDER,
    PRODUCTION_PASS_SCORE,
    audio_digest,
    audio_text,
    audio_variants,
    coarse_sentence_timings,
    dictation_score,
    difficulty_from_vector,
    get_question,
    level_status,
    listening_diagnostic,
    pick_next_question,
    production_reference,
    production_score,
    realization_status,
    realized_difficulty,
    review_next_question,
    route_competence,
    route_gate,
    score_answer,
    skill_layer,
    spoken_text,
    variant_length_scale,
    word_timings_for,
)
from services.listening import (
    level_items as motor_level_items,
)
from services.listening_bottom_up import DERIVED_ID_PREFIX
from services.listening_flow import flow_for_question
from services.word_alignment_proxy import ensure_word_alignment


def _generated_payload(row: dict) -> dict | None:
    """Payload completo del ítem generado desde una fila del catálogo global.

    El `payload_json` guarda el contenido sin `id` (para deduplicar por texto);
    aquí se reconstruye el dict con el id de la fila, con las mismas claves que
    el banco curado para que el motor lo trate igual.
    """
    if not row:
        return None
    try:
        payload = json.loads(row.get("payload_json") or "")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload["id"] = row.get("id", "")
    return payload


async def _extra_questions(user_id: str, level: str) -> list[dict]:
    """Ítems extra activados por el usuario en una ruta (dicts completos).

    Los ítems viven en el catálogo global `listening_generated`; solo se sirven
    en el pool de la ruta si el usuario los ha activado en `listening_route_extras`.
    """
    rows = await run_in_threadpool(
        listening_repo.list_route_extras, user_id, level
    )
    if not rows:
        return []
    ids = [r["question_id"] for r in rows]
    catalog = await run_in_threadpool(listening_repo.list_generated_by_ids, ids)
    by_id = {row["id"]: row for row in catalog}
    questions: list[dict] = []
    for qid in ids:
        payload = _generated_payload(by_id.get(qid))
        if payload:
            questions.append(payload)
    return questions


async def _resolve_question(question_id: str) -> dict | None:
    """Resuelve un ítem del banco curado, de práctica extra (id `g-`) o derivado
    bottom-up (id `d-`, V3.28). Los derivados se recomputan desde el catálogo
    determinista (mismo payload siempre para el mismo id)."""
    question = get_question(question_id)
    if question is not None:
        return question
    if question_id.startswith(GENERATED_ID_PREFIX):
        row = await run_in_threadpool(listening_repo.get_generated, question_id)
        return _generated_payload(row)
    if question_id.startswith(DERIVED_ID_PREFIX):
        return DERIVED_BY_ID.get(question_id)
    return None


def _audio_cache_dir(voice: str) -> Path:
    """Carpeta de audio pre-renderizado, versionada por banco y voz.

    El versionado (`LISTENING_BANK_VERSION` + la voz elegida por el usuario) y el
    digest del contenido garantizan que un cambio de script/velocidad/voz/modelo
    invalide el WAV antiguo en lugar de seguir sirviéndolo (P1.1). Cada voz usa su
    propia carpeta: cambiar de voz no rompe la caché de la voz anterior, solo
    regenera bajo demanda la nueva (Configuración → Voces).
    """
    return db.DATA_DIR / "listening" / LISTENING_BANK_VERSION / voice


def _audio_path(question: dict, variant: str, voice: str) -> Path:
    digest = audio_digest(question, variant)
    # Los ítems derivados bottom-up (V3.28) reutilizan el audio del ítem padre:
    # el WAV se cachea bajo el id del padre (`derived_from`) para no duplicar
    # ficheros con el mismo contenido audible.
    cache_id = question.get("derived_from") or question["id"]
    return _audio_cache_dir(voice) / f"{cache_id}-{digest}.wav"


def audio_ready(question: dict) -> bool:
    """True si el ítem puede servir audio de referencia reproducible.

    Para audio humano grabado (`audio_type="recorded"`), basta con que el WAV del
    manifest exista en disco (no depende de Piper). Para el resto, requiere texto a
    sintetizar y Piper disponible.
    """
    if is_recorded(question):
        path = recorded_audio_path(question)
        return path is not None and path.exists()
    return bool(audio_text(question)) and tts.is_ready()


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index/partial_reference) y expone dificultad
    derivada + realización.

    `partial_reference` es la solución de un dictado parcial derivado (V3.28): no
    debe viajar en el payload público igual que no viaja `answer_index`.
    """
    out = {
        k: v
        for k, v in question.items()
        if k not in ("answer_index", "partial_reference")
    }
    out["difficulty"] = difficulty_from_vector(question.get("difficulty_vector", {}))
    out["realized_difficulty"] = realized_difficulty(question)
    out["realization"] = realization_status(question)
    out["layer"] = skill_layer(question.get("skill", ""))
    out["audio_type"] = (
        "recorded"
        if is_recorded(question)
        else (question.get("audio_type") or "tts")
    )
    out["context"] = question.get("context", "")
    out["audio_ready"] = audio_ready(question)
    out["variants"] = audio_variants(question)
    out["default_variant"] = "normal"
    return out


def _public_with_flow(question: dict, attempts: list[dict] | None) -> dict:
    """Payload público de un ítem + micro-flujo (V3.28, unificación del flow).

    Adjunta `flow` y `transcript_policy` calculados por el backend a partir del
    perfil auditivo del alumno (igual que la rama adaptativa). Con `attempts=None`
    (sin evidencia) se calcula igualmente el flow con política por nivel/capa, sin
    overrides de perfil.
    """
    perfil = (
        auditory_profile(listening_diagnostic(attempts or [])) if attempts else None
    )
    out = _public(question)
    out.update(flow_for_question(question, perfil))
    out["sentence_timings"] = coarse_sentence_timings(question)
    # V3.29 (Fase 3): karaoke palabra a palabra solo para audio TTS con sidecar
    # `word_alignment_proxy` de la voz default (audio_ready garantiza el WAV
    # pre-renderizado). Sin sidecar, `word_timings_for` devuelve `[]` y el
    # frontend degrada al sync de frase. El repaso `mastered` (modo compacto) no
    # expone timings, igual que hoy con `sentence_timings`.
    if out.get("audio_type") == "tts" and out.get("audio_ready"):
        out["word_timings"] = word_timings_for(question)
    return out


async def next_question(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente pregunta consumiendo el Student Model (sub-destrezas débiles).

    El selector prioriza, dentro del nivel de trabajo del alumno, las sub-destrezas
    que el diagnóstico marca como débiles, con selección consciente de la
    realización auditiva (no entrena una sub-destreza con audio que no la respalda).

    Con `level` (repaso de un nivel o de su ruta) se ignora el Student Model y se
    rota por las frases de esa ruta (banco curado + práctica extra activada por el
    alumno) sin repetirlas hasta completar una vuelta. `mode="failed"` (drill)
    restringe la rotación a las frases intentadas pero nunca acertadas; `mode=
    "mastered"` (repasar lo aprendido) a las acertadas alguna vez. Si no quedan,
    `review_next_question` lanza `ValueError`.

    Micro-flujo (V3.27/V3.28): las rutas adaptativa, por nivel (`level`) y drill
    (`failed`) sirven el flow pre/while1/while2/post/shadowing + `transcript_policy`
    en el payload; solo el repaso `mastered` conserva el modo compacto sin flow
    (P1-01 de la auditoría V3.27, resuelto en V3.28).
    """
    if level is not None:
        attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
        extra = await _extra_questions(user_id, level)
        question = review_next_question(
            level,
            attempts,
            only_failed=mode == "failed",
            only_mastered=mode == "mastered",
            extra_questions=extra,
        )
        if mode == "mastered":
            # Repaso de lo ya superado: modo compacto sin micro-flujo.
            return _public(question)
        return _public_with_flow(question, attempts)
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    diagnostic = listening_diagnostic(attempts)
    weak = diagnostic["weak"]
    profile = auditory_profile(diagnostic)
    # Bottom-up (V3.28): con perfil Caso A (recognition débil) el selector puede
    # servir ítems derivados (cloze/segmentación) del nivel de trabajo como
    # volumen extra de decodificación. Nunca entran en la puerta/certificación.
    recognition_layer = profile.get("layer") == "recognition"
    bottom_up = DERIVED_RECOGNITION_POOL if recognition_layer else None
    # Bottom-up de producción (V3.28.1, P1-01): los dictados parciales derivados
    # solo se sirven en sesión Caso A cuando además el diagnóstico marca la
    # producción escrita (`dictation`) como débil o sin muestra suficiente
    # (review_due). Se intercalan tras cloze/segmentación, sin nueva taxonomía.
    bottom_up_production = (
        DERIVED_PRODUCTION_POOL
        if recognition_layer and "dictation" in weak
        else None
    )
    question = pick_next_question(
        seen,
        correct,
        weak_subskills=weak,
        layer=profile.get("layer"),
        bottom_up_questions=bottom_up,
        bottom_up_production_questions=bottom_up_production,
    )
    out = _public(question)
    # Micro-flujo por ítem (V3.27): política y pasos viajan en el payload; el
    # frontend solo los ejecuta. En el modo adaptativo ("all") el perfil auditivo
    # puede hacer el shadowing obligatorio (overrides dentro de flow_for_question).
    out.update(flow_for_question(question, profile))
    # Sync grueso del transcript (V3.28, Bloque D): timings heurísticos de frase
    # para el resaltado coarse; vacío si el ítem no declara `duration`.
    out["sentence_timings"] = coarse_sentence_timings(question)
    # V3.29 (Fase 3): karaoke palabra a palabra (sidecar word_alignment_proxy de
    # la voz default); `[]` si no hay sidecar → el frontend degrada a frase.
    if out.get("audio_type") == "tts" and out.get("audio_ready"):
        out["word_timings"] = word_timings_for(question)
    return out

async def level_items(user_id: str, level: str) -> dict:
    """Estado por frase del pool de una ruta (panel del alumno) + resumen.

    `mastered`/`failed`/`unseen` reflejan la práctica por frase sobre el pool de
    la ruta (banco curado + práctica extra activada); `completed` ya no es "todo
    dominado": es la puerta de ruta del nivel (`route_gate`, calculada solo sobre
    el banco curado), de modo que el panel distingue dominar frases de superar la
    ruta. Cada ítem expone `source` ("base"/"generated")."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    extra = await _extra_questions(user_id, level)
    items = motor_level_items(level, attempts, extra_questions=extra)
    mastered = sum(1 for i in items if i["state"] == "mastered")
    failed = sum(1 for i in items if i["state"] == "failed")
    unseen = sum(1 for i in items if i["state"] == "unseen")
    total = len(items)
    gate = route_gate(level, attempts)
    return {
        "level": level,
        "total": total,
        "mastered": mastered,
        "failed": failed,
        "unseen": unseen,
        "completed": gate["passed"],
        "items": items,
        "gate": gate,
    }


async def submit_answer(
    user_id: str,
    question_id: str,
    answer_index: int,
    response_time_ms: int | None = None,
    replay_count: int = 0,
    speed_used: str = "normal",
    stage: str = "",
    transcript_used: str = "",
    segments_replayed: int = 0,
    attempt_number: int = 1,
    hint_used: bool = False,
    solution_shown: bool = False,
    attempt_id: str = "",
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe.

    `layer` no llega por parámetro: es la fuente de verdad del backend y se deriva
    del skill del ítem (la capa del esquema de clientes es solo informativa).

    V3.89 (Listening robusto): el fallo deja de ser un callejón. El intento se
    clasifica con un `outcome` (acierto a la primera, acierto tras reintento,
    fallo, fallo con pista o con solución mostrada) y, si es un fallo, la frase
    **entra en la cola de repaso** (`listening_review_queue`). La respuesta
    declara `outcome`, `queued_for_review` y `immediate_retry_available` para que
    el cliente muestre las tres acciones (continuar / repasar ahora / repasar
    después) sin improvisar política. Un acierto resuelve la entrada de la cola.
    """
    question = await _resolve_question(question_id)
    if question is None:
        return None
    correct = score_answer(answer_index, question["answer_index"])
    difficulty = difficulty_from_vector(question.get("difficulty_vector", {}))
    realized = realized_difficulty(question)
    # V3.28 (Bloque C): los ítems derivados persisten su `task_type`
    # (cloze/segmentation); el resto conserva el default `mcq`.
    task_type = question.get("task_type", "mcq")
    # V3.29 (Fase 3): en un acierto incorrecto de cloze/segmentation se persiste
    # la palabra diana del hueco (la respuesta correcta que el alumno no eligió)
    # como evidencia de palabra fallada; el resto de intentos guarda NULL.
    word_breakdown = (
        {"target": question["options"][question["answer_index"]]}
        if not correct and task_type in ("cloze", "segmentation")
        else None
    )
    outcome = listening_review.outcome_for(
        correct,
        attempt_number,
        hint_used=hint_used,
        solution_shown=solution_shown,
    )
    skill = question.get("skill", "")
    # V3.93.1: intento + cola de repaso en UNA transacción, idempotente por
    # `attempt_id`. Repetir el mismo intento (reintento de red, doble toque) no
    # inserta otra fila ni vuelve a incrementar `fail_count`; la evidencia se
    # reclama después (idempotente por la misma clave).
    event = await run_in_threadpool(
        listening_repo.record_answer_event,
        user_id,
        question_id,
        answer_index,
        correct,
        skill=skill,
        difficulty=difficulty,
        response_time_ms=response_time_ms,
        replay_count=replay_count,
        topic=question.get("topic", ""),
        realized_difficulty=realized,
        task_type=task_type,
        layer=skill_layer(skill) or "",
        speed_used=speed_used,
        stage=stage,
        transcript_used=transcript_used,
        segments_replayed=segments_replayed,
        word_breakdown=word_breakdown,
        outcome=outcome,
        attempt_id=attempt_id,
        level=question.get("level", ""),
    )
    if event is None:
        return None
    fail_count = int(event["fail_count"])
    evidence = (
        _empty_evidence()
        if fail_count == 0
        else await _apply_difficulty_evidence(
            user_id,
            question_id,
            question,
            fail_count=fail_count,
            attempt_number=attempt_number,
            attempt_id=attempt_id,
        )
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
        "skill": skill,
        "difficulty": difficulty,
        "realized_difficulty": realized,
        # V3.89: contrato del fallo como evidencia (nunca como bloqueo).
        "outcome": outcome,
        "queued_for_review": fail_count > 0,
        # V3.92 (integración pedagógica): palabras del léxico del alumno que
        # aparecían en la frase fallada y han recibido evidencia de dificultad.
        # Es INFORMATIVO: ninguna acción del cliente depende de esto y el fallo
        # sigue sin bloquear nada.
        "difficulty_evidence": {
            "words": evidence["words"],
            "count": evidence["count"],
        },
        # V3.94 (ENFORCE): palabras que aparecían en la frase en una acepción
        # DISTINTA a la aprendida. Su carta NO se penalizó (sería señalar la carta
        # equivocada) y el suceso queda registrado. Aditivo e informativo.
        "new_sense_exposure": evidence["new_sense_exposure"],
        "immediate_retry_available": (
            not correct
            and listening_review.can_retry_immediately(attempt_number)
        ),
    }


async def _apply_difficulty_evidence(
    user_id: str,
    question_id: str,
    question: dict,
    *,
    fail_count: int = 1,
    attempt_number: int = 1,
    attempt_id: str = "",
) -> dict:
    """Puente Listening → FSRS: el fallo sube la dificultad de las palabras suyas.

    V3.92. La frase NO entra en FSRS (eso lo resolvió V3.89 con su propia cola);
    lo que entra es la EVIDENCIA de que las palabras que el alumno ya tiene y que
    aparecían en la frase son más difíciles de lo que su carta decía.

    Reglas duras, todas comprobables en `services/listening_bridge.py`:

    - Solo palabras que el alumno YA tiene en `vocabulary`: el puente nunca crea
      vocabulario (invariante D3 del proyecto).
    - Solo cartas débiles: un dominio demostrado no se castiga por no entender
      una frase. Una palabra sin carta la recibe aquí (es suya desde el alta) con
      la dificultad ya subida.
    - Ni un solo fallo más que una escritura por palabra y fallo.

    V3.94 (ENFORCE sense-aware): el Sense Resolver **decide**. Un `mismatch`
    PROBADO —el contexto usa una acepción DISTINTA a la aprendida— **no** sube la
    dificultad de la carta: el fallo no penaliza la acepción aprendida y se
    registra como `new_sense_exposure`. Todo lo demás (`matched`, `ambiguous`, sin
    veredicto) conserva la evidencia de V3.92 (ver `allows_difficulty_evidence`: la
    duda no resta evidencia). Las ALTERNATIVAS del diccionario se cablean
    (`alternatives_index`) para que `mismatch` sea ALCANZABLE: sin ellas la política
    no podría actuar.

    V3.94.1 (resolver SIEMPRE): el sentido se resuelve para **todas** las palabras
    emparejadas, no solo para las cartas débiles (`select_targets()` filtraba antes
    de resolver y hacía invisible una acepción nueva en una palabra fuerte). Una
    carta fuerte: (a) si el veredicto es `mismatch` PROBADO, registra la exposición
    sin tocar FSRS; (b) si no, conserva su dominio y no recibe evidencia de
    dificultad. Es decir, se separa «resolver el sentido» de «escribir la carta».

    V3.94.2 (ocurrencias en conflicto): si la misma palabra aparece con un
    `mismatch` probado y con otro veredicto, el agregado es `occurrence:split`.
    No es exposición. Una carta débil sigue recibiendo la subida (la duda no
    resta). Una carta fuerte deja fila en el ledger con la dificultad intacta,
    para que el conflicto sea medible, y no toca FSRS.

    V3.93 (robustez): el ledger reclama la clave del intento ANTES de tocar la
    carta (una repetición del mismo intento no vuelve a sumar) y la carta se
    escribe con control de concurrencia optimista (dos evidencias simultáneas
    suman las DOS en vez de pisarse).

    V3.93.1 (atomicidad): el claim y el CAS de la carta van en la MISMA
    transacción (`claim_evidence_and_write_card`): nunca queda una evidencia
    registrada sin su subida de FSRS. Si el CAS no escribe, la transacción se
    revierte (no queda fila y la clave se libera) y se reintenta con la carta
    fresca.

    Devuelve `{"words": [...], "count": n, "new_sense_exposure": {"words", "count"}}`;
    `count` es el número de cartas tocadas (no el de coincidencias léxicas) y
    `new_sense_exposure` las palabras que aparecían en una acepción distinta. Nunca
    lanza hacia el cliente: si algo del puente falla, el intento ya está persistido
    y la sesión puede continuar.
    """
    text = audio_text(question)
    if not text:
        return _empty_evidence()
    known = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    matches = listening_bridge.match_units(text, known)
    if not matches:
        return _empty_evidence()
    matched_words = [m["word"] for m in matches]
    cards = await run_in_threadpool(
        academy_repo.fsrs_cards_by_ids,
        user_id,
        "lexicon",
        matched_words,
    )
    senses = listening_bridge.sense_index(known)
    # V3.94: las ALTERNATIVAS del diccionario (todas las acepciones que la caché
    # conoce de la palabra) son lo que hace ALCANZABLE un `mismatch`. Sin ellas el
    # resolver solo puede decir `matched`/`ambiguous` y la política no tendría nada
    # que suprimir: ENFORCE sería un no-op.
    dictionary_entries = await run_in_threadpool(
        dictionary_repo.find_by_words, matched_words
    )
    alternatives = listening_bridge.alternatives_index(dictionary_entries)
    now = datetime.now(timezone.utc).isoformat()
    words: list[str] = []
    exposures: list[str] = []
    for target in matches:
        word = target["word"]
        card = cards.get(word)
        verdict = sense_context.classify_sense_evidence(
            word, text, senses.get(word), senses=alternatives.get(word, ())
        )
        if not sense_context.allows_difficulty_evidence(verdict):
            # ENFORCE (V3.94): la frase usa una acepción DISTINTA a la aprendida. La
            # carta de la acepción aprendida NO se toca —subirla sería señalar la
            # carta equivocada— y el suceso se registra como exposición a un sentido
            # nuevo, con la dificultad SIN cambiar (`before == after`). El registro es
            # idempotente por la clave del intento (una repetición no reexpone).
            base = float((card or {}).get("difficulty") or 5.0)
            inserted = await run_in_threadpool(
                listening_repo.record_difficulty_evidence,
                user_id,
                question_id,
                word,
                fail_count=fail_count,
                difficulty_before=base,
                difficulty_after=base,
                attempt_number=attempt_number,
                attempt_id=attempt_id,
                sense_key=verdict["declared_key"],
                sense_match=verdict["match"],
                sense_reason=verdict["reason"],
            )
            if inserted:
                exposures.append(word)
            continue
        if sense_context.is_occurrence_split(verdict) and not (
            listening_bridge.is_weak_card(card)
        ):
            # V3.94.2: conflicto de ocurrencias en una carta FUERTE. No es una
            # exposición (no se fabrica la acepción nueva) ni un castigo del
            # dominio. La fila queda, con la dificultad intacta, para contarla.
            base = float((card or {}).get("difficulty") or 5.0)
            await run_in_threadpool(
                listening_repo.record_difficulty_evidence,
                user_id,
                question_id,
                word,
                fail_count=fail_count,
                difficulty_before=base,
                difficulty_after=base,
                attempt_number=attempt_number,
                attempt_id=attempt_id,
                sense_key=verdict["declared_key"],
                sense_match=verdict["match"],
                sense_reason=verdict["reason"],
            )
            continue
        if not listening_bridge.is_weak_card(card):
            # V3.94.1: el sentido se resuelve SIEMPRE (arriba), pero una carta fuerte
            # (review, dificultad baja) NO recibe evidencia de dificultad por no
            # entender una frase: sería castigar un dominio ya demostrado. Antes esto
            # lo decidía `select_targets()` y la carta fuerte nunca llegaba al
            # resolver, así que una acepción NUEVA en una palabra fuerte era
            # invisible. Ahora se resuelve el sentido y solo se omite la escritura.
            continue
        if card is None:
            card = fsrs.empty_card(
                target_type="lexicon",
                target_id=word,
                label=word,
                why=listening_bridge.SOURCE,
                now=now,
            )
        # V3.93.1: el claim de la evidencia y el CAS de la carta van en UNA sola
        # transacción (`claim_evidence_and_write_card`): o ambas cosas, o ninguna.
        # `duplicate` = el intento ya estaba aplicado (no-op). `conflict` = otro
        # escritor cambió la carta: se RELEE y se recalcula la subida sobre el
        # valor fresco (hasta `_CARD_WRITE_ATTEMPTS`) conservando el CAS de V3.93.
        for _ in range(_CARD_WRITE_ATTEMPTS):
            before = float(card.get("difficulty") or 5.0)
            expected_version = int(card.get("version") or 0)
            updated = fsrs.apply_difficulty_evidence(
                card, source=listening_bridge.SOURCE, now=now
            )
            if updated is None:
                break
            after = float(updated.get("difficulty") or before)
            result = await run_in_threadpool(
                listening_repo.claim_evidence_and_write_card,
                user_id,
                question_id,
                word,
                updated,
                expected_version=expected_version,
                fail_count=fail_count,
                difficulty_before=before,
                difficulty_after=after,
                due_at=updated.get("due_at") or "",
                attempt_number=attempt_number,
                attempt_id=attempt_id,
                sense_key=verdict["declared_key"],
                sense_match=verdict["match"],
                sense_reason=verdict["reason"],
            )
            if result == "ok":
                words.append(word)
                break
            if result in ("duplicate", "no_user"):
                # El intento ya estaba aplicado (o no hay usuario): no se reintenta.
                break
            # "conflict": relevo la carta y recalculó sobre el valor fresco.
            fresh = await run_in_threadpool(
                academy_repo.get_fsrs_card, user_id, "lexicon", word
            )
            if fresh is None:
                break
            card = fresh
    return {
        "words": words,
        "count": len(words),
        "new_sense_exposure": {"words": exposures, "count": len(exposures)},
    }


def _empty_evidence() -> dict:
    """Evidencia vacía del puente, con la forma COMPLETA del contrato (V3.94).

    Se construye nueva en cada llamada (no es una constante mutable compartida): el
    contrato de la respuesta lleva `words`/`count` y, desde V3.94, `new_sense_exposure`.
    """
    return {
        "words": [],
        "count": 0,
        "new_sense_exposure": {"words": [], "count": 0},
    }


# Reintentos del CAS antes de rendirse. La contención real es de dos escritores
# (el mismo alumno fallando la misma frase desde dos pestañas); tres intentos
# sobran y acotan el peor caso sin bucle infinito.
_CARD_WRITE_ATTEMPTS = 3


async def submit_production(
    user_id: str,
    question_id: str,
    transcript: str,
    task_type: str,
    stage: str = "",
    transcript_used: str = "",
    speed_used: str = "normal",
    shadowing_duration_ms: int | None = None,
    shadowing_speech_rate: float | None = None,
    attempt_id: str = "",
) -> dict | None:
    """Evalúa y persiste una tarea de producción (dictado/shadowing), sin LLM.

    Puntúa de forma determinista y persiste la evidencia con `answer_index=-1`,
    `task_type` y `score` continuo (0..1). Devuelve `None` si la pregunta no
    existe o su `skill` no coincide con `task_type` (el router lo traduce a 404).
    En producción la capa cognitiva no aplica (`layer=""`): los ítems
    dictation/shadowing no pertenecen a la taxonomía receptiva.

    V3.28.1 (P1-02): el scoring es distinto según la tarea. El dictado escrito
    (banco `dictation` o parcial derivado `d-`, ambos `task_type=dictation`)
    puntúa **exacto por token** (`dictation_score`): sin Soundex, phoneme proxy
    ni prosodia — "escribe lo que oíste" no admite tolerancia fonética. El
    shadowing oral conserva el score compuesto de producción.

    Desde V3.28 (Bloque C) la pregunta puede ser también un dictado parcial
    derivado (`d-`, `task_type=partial_dictation` con skill `dictation`): se
    resuelve igual que el banco y puntúa contra `partial_reference`.

    Desde V3.28 (Bloque E) `shadowing_duration_ms`/`shadowing_speech_rate` son
    señales auxiliares informativas que el cliente calcula desde el audio grabado
    (duración y velocidad proxy). Solo se persisten en intentos `shadowing` y sin
    peso de mastery: el scoring determinista sigue siendo el texto oído.

    V3.93.2: la persistencia pasa por `record_answer_event` con
    `sync_queue=False`, de modo que el intento se **deduplica por `attempt_id`**
    (UUID del cliente reutilizado en el reintento HTTP) sin alterar en nada el
    comportamiento histórico: una tarea de producción nunca ha tocado
    `listening_review_queue` (esa cola es de frases receptivas falladas, V3.89).
    Un `attempt_id` vacío mantiene la semántica anterior (inserta siempre).
    """
    question = await _resolve_question(question_id)
    if question is None:
        return None
    if question.get("skill") != task_type:
        return None
    reference = production_reference(question)
    heard = (transcript or "").strip()
    scorer = dictation_score if task_type == "dictation" else production_score
    result = scorer(reference, heard)
    correct = result["score"] >= PRODUCTION_PASS_SCORE
    difficulty = difficulty_from_vector(question.get("difficulty_vector", {}))
    realized = realized_difficulty(question)
    await run_in_threadpool(
        listening_repo.record_answer_event,
        user_id,
        question_id,
        -1,
        correct,
        skill=task_type,
        difficulty=difficulty,
        response_time_ms=None,
        replay_count=0,
        topic=question.get("topic", ""),
        realized_difficulty=realized,
        task_type=task_type,
        score=result["score"] / 100.0,
        stage=stage,
        transcript_used=transcript_used,
        speed_used=speed_used,
        shadowing_duration_ms=(
            shadowing_duration_ms if task_type == "shadowing" else None
        ),
        shadowing_speech_rate=(
            shadowing_speech_rate if task_type == "shadowing" else None
        ),
        # V3.29 (Fase 3): evidencia de palabra fallada. En un intento de
        # producción el breakdown de `word_alignment` (missing/substituted)
        # indica exactamente qué palabras el alumno no oyó bien; se persiste
        # para el futuro salto a palabra fallada y agregados (V3.30).
        word_breakdown=result["breakdown"],
        attempt_id=attempt_id,
        # La cola de repaso es de frases RECEPTIVAS falladas (V3.89): una tarea
        # de producción nunca la ha tocado y este cambio (V3.93.2) NO lo altera;
        # solo añade la deduplicación por `attempt_id`.
        sync_queue=False,
    )
    return {
        "question_id": question_id,
        "task_type": task_type,
        "correct": correct,
        "score": result["score"],
        "word_accuracy": result["word_accuracy"],
        "phonetic_score": result["phonetic_score"],
        "phoneme_accuracy_proxy": result["phoneme_accuracy_proxy"],
        "breakdown": result["breakdown"],
        "reference": reference,
        "level": question["level"],
        "skill": question.get("skill", ""),
    }


async def get_stats(user_id: str) -> dict:
    stats = await run_in_threadpool(listening_repo.get_stats, user_id)
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    levels = level_status(attempts)
    # La ruta actual es la primera aún no superada por la puerta (certificación
    # honesta), no la primera con ítems sin acertar: cubrir el banco no basta.
    stats["level"] = next(
        (s["level"] for s in levels if not s["completed"]), LEVEL_ORDER[-1]
    )
    stats["completed"] = all(s["completed"] for s in levels)
    # Estado pedagógico por ruta (Constitución §2.1): la puerta de ruta decide
    # FUNCTIONAL y la retención retardada estable DEMONSTRATED (H3/H5).
    by_route = {c["level"]: c for c in route_competence(attempts)}
    for row in levels:
        route = by_route.get(row["level"])
        if route:
            row["state"] = route["state"]
            row["retention"] = route["retention"]
    # Práctica extra generada (V3.6): `total`/`mastered` del anillo crecen con
    # los ítems extra activados, pero la puerta, `completed` y `state` siguen
    # anclados al banco curado (certificación honesta). El desglose se expone en
    # `base_total`/`base_mastered`/`extras`/`extras_mastered`.
    extra_rows = await run_in_threadpool(listening_repo.list_route_extras, user_id)
    extras_by_level: dict[str, list[str]] = {}
    for r in extra_rows:
        extras_by_level.setdefault(r["level"], []).append(r["question_id"])
    all_ids = [qid for ids in extras_by_level.values() for qid in ids]
    catalog = await run_in_threadpool(listening_repo.list_generated_by_ids, all_ids)
    catalog_ids = {row["id"] for row in catalog}
    correct_ids = {row["question_id"] for row in attempts if row.get("correct")}
    for row in levels:
        extra_ids = [
            qid for qid in extras_by_level.get(row["level"], []) if qid in catalog_ids
        ]
        extras_mastered = sum(1 for qid in extra_ids if qid in correct_ids)
        row["base_total"] = row["total"]
        row["base_mastered"] = row["mastered"]
        row["extras"] = len(extra_ids)
        row["extras_mastered"] = extras_mastered
        row["total"] = row["base_total"] + len(extra_ids)
        row["mastered"] = row["base_mastered"] + extras_mastered
    stats["levels"] = levels
    return stats


async def get_diagnostic(user_id: str) -> dict:
    """Diagnóstico de sub-destrezas derivado de los intentos registrados.

    Adjunta el perfil auditivo (V3.27): capa objetivo e intervención recomendada
    (casos A-D de la especificación Listening Engine 4.0 §5)."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    diagnostic = listening_diagnostic(attempts, now=db._now())
    diagnostic["profile"] = auditory_profile(diagnostic)
    return diagnostic


async def get_audio(
    user_id: str,
    question_id: str,
    variant: str = "normal",
    voice: str | None = None,
) -> tuple[bytes | None, int | None, str]:
    """Devuelve el audio WAV del ítem (grabado o sintetizado), o un código de error.

    Si el ítem es `recorded` (biblioteca de audio humano), sirve el WAV referenciado
    en el manifest; si está referenciado pero ausente, devuelve 404 (no cae a TTS).
    Si es `tts`, `variant` selecciona la variante de velocidad de la escalera
    (`AUDIO_VARIANTS`) y la voz es la preferida del usuario (Configuración → Voces;
    default si no ha elegido o su voz no está instalada). Retorna `(bytes, None,
    voz)` con el audio en caso de éxito, o `(None, status, "")` donde `status` es 400
    (variante no válida), 404 (ítem inexistente o audio grabado ausente) o 503
    (Piper no disponible). El audio TTS se sintetiza en la primera petición de cada
    variante y voz, y se cachea en un path versionado
    (`DATA_DIR/listening/{bank_version}/{voice}/{id}-{digest}.wav`), con digest
    distinto por variante (la variante `normal` preserva el digest/cache actual).

    V3.75.5 (dos acentos): `voice` permite pedir una voz concreta (la B del
    comparador A/B) sin cambiar la preferencia del perfil. Solo se acepta si está
    instalada y es inglesa (`pick_requested_voice`); si no, se ignora y manda la
    voz del perfil — nunca un 400 por esto, porque una preferencia vieja no debe
    romper la reproducción. La caché ya está separada por voz.

    V3.75.7: la tercera pieza del retorno es la voz que se sirvió **de verdad**
    (vacía en audio grabado). El router la publica en `X-TTS-Voice` porque la
    pedida y la servida pueden no coincidir: sin esa señal, el comparador A/B podía
    sonar dos veces con la misma voz y el cliente creer que oyó dos acentos.
    """
    question = await _resolve_question(question_id)
    if question is None:
        return None, 404, ""
    if is_recorded(question):
        recorded = recorded_audio_path(question)
        if recorded is not None and recorded.exists():
            return recorded.read_bytes(), None, ""
        return None, 404, ""
    if variant not in AUDIO_VARIANTS:
        return None, 400, ""
    requested = tts.pick_requested_voice(voice, "en")
    if requested is not None:
        voice = requested
    else:
        prefs = await run_in_threadpool(settings_repo.get_settings, user_id)
        voice = tts.resolve_voice(prefs)
    if not tts.is_ready(voice):
        return None, 503, ""
    path = _audio_path(question, variant, voice)
    if path.exists():
        return path.read_bytes(), None, voice
    length_scale = variant_length_scale(question, variant)
    data = await run_in_threadpool(
        tts.synthesize, spoken_text(question), length_scale, voice
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    # V3.29 (Fase 3): sidecar word_alignment_proxy para WAV generados bajo
    # demanda (voz no-default o variante no pre-renderizada). Solo se ejecuta en
    # la primera síntesis (cache miss); nunca rompe el flujo si el ASR no está.
    await run_in_threadpool(ensure_word_alignment, path, spoken_text(question))
    return data, None, voice


# --- Cola de repaso de frases (V3.89, Listening robusto) ----------------------


async def get_review_queue(user_id: str, only_due: bool = False) -> dict:
    """Cola de repaso de frases falladas del usuario.

    Devuelve `{pending, total, due, entries}`. `entries` viene ordenada por
    prioridad (mayor primero) y declara, por frase, cuántas veces se falló y
    cuándo toca repasarla. Con `only_due=True` solo se sirven las vencidas.
    """
    rows = await run_in_threadpool(listening_repo.list_queue, user_id)
    now = listening_review.now_iso()
    entries = [
        {
            "question_id": row["question_id"],
            "level": row["level"],
            "skill": row["skill"],
            "task_type": row["task_type"],
            "fail_count": int(row["fail_count"]),
            "priority": float(row["priority"]),
            "state": row["state"],
            "next_review_at": row["next_review_at"],
            "due": row["state"] == "pending" and row["next_review_at"] <= now,
        }
        for row in rows
    ]
    due = [e for e in entries if e["due"]]
    served = due if only_due else entries
    return {
        "pending": len(entries),
        "due": len(due),
        "total": len(served),
        "entries": served,
    }


async def defer_review(
    user_id: str, question_id: str, hours: int = 24
) -> dict | None:
    """«Repasar después»: pospone la entrada en vez de ignorarla.

    Devuelve la entrada actualizada, o None si la frase no estaba en la cola
    (el router lo traduce a 404: no se puede posponer lo que no existe).
    """
    entry = await run_in_threadpool(
        listening_repo.get_queue_entry, user_id, question_id
    )
    if entry is None:
        return None
    later = datetime.now(timezone.utc) + timedelta(hours=max(1, int(hours)))
    await run_in_threadpool(
        listening_repo.defer_queue_entry, user_id, question_id, later.isoformat()
    )
    updated = await run_in_threadpool(
        listening_repo.get_queue_entry, user_id, question_id
    )
    if updated is None:  # pragma: no cover - la fila existe (se acaba de leer)
        return None
    return {
        "question_id": updated["question_id"],
        "level": updated["level"],
        "skill": updated["skill"],
        "task_type": updated["task_type"],
        "fail_count": int(updated["fail_count"]),
        "priority": float(updated["priority"]),
        "state": updated["state"],
        "next_review_at": updated["next_review_at"],
        "due": False,
    }


async def mark_reviewed(user_id: str, question_id: str) -> bool:
    """Saca una frase de la cola porque el alumno la repasó y la acertó."""
    return await run_in_threadpool(
        listening_repo.mark_queue_reviewed, user_id, question_id
    )

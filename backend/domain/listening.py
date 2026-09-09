"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

import json
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from repositories import db
from repositories import listening as listening_repo
from repositories import settings as settings_repo
from services import tts
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
)
from services.listening import (
    level_items as motor_level_items,
)
from services.listening_bottom_up import DERIVED_ID_PREFIX
from services.listening_flow import flow_for_question


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
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe.

    `layer` no llega por parámetro: es la fuente de verdad del backend y se deriva
    del skill del ítem (la capa del esquema de clientes es solo informativa).
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
    await run_in_threadpool(
        listening_repo.record_attempt,
        user_id,
        question_id,
        answer_index,
        correct,
        question.get("skill", ""),
        difficulty,
        response_time_ms,
        replay_count,
        question.get("topic", ""),
        realized,
        task_type=task_type,
        layer=skill_layer(question.get("skill", "")) or "",
        speed_used=speed_used,
        stage=stage,
        transcript_used=transcript_used,
        segments_replayed=segments_replayed,
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
        "skill": question.get("skill", ""),
        "difficulty": difficulty,
        "realized_difficulty": realized,
    }


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
        listening_repo.record_attempt,
        user_id,
        question_id,
        -1,
        correct,
        task_type,
        difficulty,
        None,
        0,
        question.get("topic", ""),
        realized,
        task_type,
        result["score"] / 100.0,
        stage=stage,
        transcript_used=transcript_used,
        speed_used=speed_used,
        shadowing_duration_ms=(
            shadowing_duration_ms if task_type == "shadowing" else None
        ),
        shadowing_speech_rate=(
            shadowing_speech_rate if task_type == "shadowing" else None
        ),
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
    user_id: str, question_id: str, variant: str = "normal"
) -> tuple[bytes | None, int | None]:
    """Devuelve el audio WAV del ítem (grabado o sintetizado), o un código de error.

    Si el ítem es `recorded` (biblioteca de audio humano), sirve el WAV referenciado
    en el manifest; si está referenciado pero ausente, devuelve 404 (no cae a TTS).
    Si es `tts`, `variant` selecciona la variante de velocidad de la escalera
    (`AUDIO_VARIANTS`) y la voz es la preferida del usuario (Configuración → Voces;
    default si no ha elegido o su voz no está instalada). Retorna `(bytes, None)`
    con el audio en caso de éxito, o `(None, status)` donde `status` es 400
    (variante no válida), 404 (ítem inexistente o audio grabado ausente) o 503
    (Piper no disponible). El audio TTS se sintetiza en la primera petición de cada
    variante y voz, y se cachea en un path versionado
    (`DATA_DIR/listening/{bank_version}/{voice}/{id}-{digest}.wav`), con digest
    distinto por variante (la variante `normal` preserva el digest/cache actual).
    """
    question = await _resolve_question(question_id)
    if question is None:
        return None, 404
    if is_recorded(question):
        recorded = recorded_audio_path(question)
        if recorded is not None and recorded.exists():
            return recorded.read_bytes(), None
        return None, 404
    if variant not in AUDIO_VARIANTS:
        return None, 400
    prefs = await run_in_threadpool(settings_repo.get_settings, user_id)
    voice = tts.resolve_voice(prefs)
    if not tts.is_ready(voice):
        return None, 503
    path = _audio_path(question, variant, voice)
    if path.exists():
        return path.read_bytes(), None
    length_scale = variant_length_scale(question, variant)
    data = await run_in_threadpool(
        tts.synthesize, spoken_text(question), length_scale, voice
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data, None

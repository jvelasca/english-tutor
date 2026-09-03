"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from pathlib import Path

from starlette.concurrency import run_in_threadpool

from config import PIPER_VOICE
from repositories import db
from repositories import listening as listening_repo
from services import tts
from services.audio_library import is_recorded, recorded_audio_path
from services.curriculum import LISTENING_BANK_VERSION
from services.listening import (
    AUDIO_VARIANTS,
    LEVEL_ORDER,
    PRODUCTION_PASS_SCORE,
    audio_digest,
    audio_text,
    audio_variants,
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
    spoken_text,
    variant_length_scale,
)
from services.listening import (
    level_items as motor_level_items,
)


def _audio_cache_dir() -> Path:
    """Carpeta de audio pre-renderizado, versionada por banco y voz.

    El versionado (`LISTENING_BANK_VERSION` + `PIPER_VOICE`) y el digest del
    contenido garantizan que un cambio de script/velocidad/voz/modelo invalide el
    WAV antiguo en lugar de seguir sirviéndolo (P1.1).
    """
    return db.DATA_DIR / "listening" / LISTENING_BANK_VERSION / PIPER_VOICE


def _audio_path(question: dict, variant: str = "normal") -> Path:
    digest = audio_digest(question, variant)
    return _audio_cache_dir() / f"{question['id']}-{digest}.wav"


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
    """Quita la respuesta (answer_index) y expone dificultad derivada + realización."""
    out = {k: v for k, v in question.items() if k != "answer_index"}
    out["difficulty"] = difficulty_from_vector(question.get("difficulty_vector", {}))
    out["realized_difficulty"] = realized_difficulty(question)
    out["realization"] = realization_status(question)
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


async def next_question(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente pregunta consumiendo el Student Model (sub-destrezas débiles).

    El selector prioriza, dentro del nivel de trabajo del alumno, las sub-destrezas
    que el diagnóstico marca como débiles, con selección consciente de la
    realización auditiva (no entrena una sub-destreza con audio que no la respalda).

    Con `level` (repaso de un nivel) se ignora el Student Model y se rota por las
    frases de ese nivel sin repetirlas hasta completar una vuelta. `mode="failed"`
    (drill) restringe la rotación a las frases del nivel intentadas pero nunca
    acertadas; si no quedan, `review_next_question` lanza `ValueError`.
    """
    if level is not None:
        attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
        return _public(
            review_next_question(level, attempts, only_failed=mode == "failed")
        )
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    weak = listening_diagnostic(attempts)["weak"]
    question = pick_next_question(seen, correct, weak_subskills=weak)
    return _public(question)


async def level_items(user_id: str, level: str) -> dict:
    """Estado por frase de un nivel (panel del alumno) + contadores resumen.

    `mastered`/`failed`/`unseen` reflejan la práctica por frase; `completed` ya no
    es "todo dominado": es la puerta de ruta del nivel (`route_gate`), de modo que
    el panel distingue dominar frases de superar la ruta."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    items = motor_level_items(level, attempts)
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
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe."""
    question = get_question(question_id)
    if question is None:
        return None
    correct = score_answer(answer_index, question["answer_index"])
    difficulty = difficulty_from_vector(question.get("difficulty_vector", {}))
    realized = realized_difficulty(question)
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
) -> dict | None:
    """Evalúa y persiste una tarea de producción (dictado/shadowing), sin LLM.

    Puntúa de forma determinista (`production_score` sobre `composite_score`) y
    persiste la evidencia con `answer_index=-1`, `task_type` y `score` continuo
    (0..1). Devuelve `None` si la pregunta no existe o su `skill` no coincide con
    `task_type` (el router lo traduce a 404).
    """
    question = get_question(question_id)
    if question is None:
        return None
    if question.get("skill") != task_type:
        return None
    reference = production_reference(question)
    heard = (transcript or "").strip()
    result = production_score(reference, heard)
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
    stats["levels"] = levels
    return stats


async def get_diagnostic(user_id: str) -> dict:
    """Diagnóstico de sub-destrezas derivado de los intentos registrados."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    return listening_diagnostic(attempts, now=db._now())


async def get_audio(
    question_id: str, variant: str = "normal"
) -> tuple[bytes | None, int | None]:
    """Devuelve el audio WAV del ítem (grabado o sintetizado), o un código de error.

    Si el ítem es `recorded` (biblioteca de audio humano), sirve el WAV referenciado
    en el manifest; si está referenciado pero ausente, devuelve 404 (no cae a TTS).
    Si es `tts`, `variant` selecciona la variante de velocidad de la escalera
    (`AUDIO_VARIANTS`). Retorna `(bytes, None)` con el audio en caso de éxito, o
    `(None, status)` donde `status` es 400 (variante no válida), 404 (ítem
    inexistente o audio grabado ausente) o 503 (Piper no disponible). El audio TTS
    se sintetiza en la primera petición de cada variante y se cachea en un path
    versionado
    (`DATA_DIR/listening/{bank_version}/{voice}/{id}-{digest}.wav`), con digest
    distinto por variante (la variante `normal` preserva el digest/cache actual).
    """
    question = get_question(question_id)
    if question is None:
        return None, 404
    if is_recorded(question):
        recorded = recorded_audio_path(question)
        if recorded is not None and recorded.exists():
            return recorded.read_bytes(), None
        return None, 404
    if variant not in AUDIO_VARIANTS:
        return None, 400
    if not tts.is_ready():
        return None, 503
    path = _audio_path(question, variant)
    if path.exists():
        return path.read_bytes(), None
    length_scale = variant_length_scale(question, variant)
    data = await run_in_threadpool(tts.synthesize, spoken_text(question), length_scale)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data, None

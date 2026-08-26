"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from pathlib import Path

from starlette.concurrency import run_in_threadpool

from config import PIPER_VOICE
from repositories import db
from repositories import listening as listening_repo
from services import tts
from services.curriculum import LISTENING_BANK_VERSION
from services.listening import (
    PRODUCTION_PASS_SCORE,
    audio_digest,
    audio_text,
    current_level,
    difficulty_from_vector,
    get_question,
    length_scale_for_rate,
    level_status,
    listening_diagnostic,
    pick_next_question,
    production_reference,
    production_score,
    realization_status,
    realized_difficulty,
    score_answer,
    spoken_text,
)


def _audio_cache_dir() -> Path:
    """Carpeta de audio pre-renderizado, versionada por banco y voz.

    El versionado (`LISTENING_BANK_VERSION` + `PIPER_VOICE`) y el digest del
    contenido garantizan que un cambio de script/velocidad/voz/modelo invalide el
    WAV antiguo en lugar de seguir sirviéndolo (P1.1).
    """
    return db.DATA_DIR / "listening" / LISTENING_BANK_VERSION / PIPER_VOICE


def _audio_path(question: dict) -> Path:
    return _audio_cache_dir() / f"{question['id']}-{audio_digest(question)}.wav"


def audio_ready(question: dict) -> bool:
    """True si el ítem puede servir audio de referencia reproducible."""
    return bool(audio_text(question)) and tts.is_ready()


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index) y expone dificultad derivada + realización."""
    out = {k: v for k, v in question.items() if k != "answer_index"}
    out["difficulty"] = difficulty_from_vector(question.get("difficulty_vector", {}))
    out["realized_difficulty"] = realized_difficulty(question)
    out["realization"] = realization_status(question)
    out["audio_type"] = question.get("audio_type") or "tts"
    out["audio_ready"] = audio_ready(question)
    return out


async def next_question(user_id: str) -> dict:
    """Siguiente pregunta consumiendo el Student Model (sub-destrezas débiles).

    El selector prioriza, dentro del nivel de trabajo del alumno, las sub-destrezas
    que el diagnóstico marca como débiles, con selección consciente de la
    realización auditiva (no entrena una sub-destreza con audio que no la respalda).
    """
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    weak = listening_diagnostic(attempts)["weak"]
    question = pick_next_question(seen, correct, weak_subskills=weak)
    return _public(question)


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
        "phoneme_accuracy": result["phoneme_accuracy"],
        "breakdown": result["breakdown"],
        "reference": reference,
        "level": question["level"],
        "skill": question.get("skill", ""),
    }


async def get_stats(user_id: str) -> dict:
    stats = await run_in_threadpool(listening_repo.get_stats, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    levels = level_status(correct)
    stats["level"] = current_level(correct)
    stats["completed"] = all(s["completed"] for s in levels)
    stats["levels"] = levels
    return stats


async def get_diagnostic(user_id: str) -> dict:
    """Diagnóstico de sub-destrezas derivado de los intentos registrados."""
    attempts = await run_in_threadpool(listening_repo.list_attempts, user_id)
    return listening_diagnostic(attempts, now=db._now())


async def get_audio(question_id: str) -> tuple[bytes | None, int | None]:
    """Devuelve el audio WAV del ítem (cacheado en disco), o un código de error.

    Retorna `(bytes, None)` con el audio en caso de éxito, o `(None, status)` donde
    `status` es 404 (ítem inexistente) o 503 (sintetizador Piper no disponible). El
    audio se sintetiza en la primera petición y se cachea en un path versionado
    (`DATA_DIR/listening/{bank_version}/{voice}/{id}-{digest}.wav`).
    """
    question = get_question(question_id)
    if question is None:
        return None, 404
    if not tts.is_ready():
        return None, 503
    path = _audio_path(question)
    if path.exists():
        return path.read_bytes(), None
    length_scale = length_scale_for_rate(question.get("speech_rate") or 0.0)
    data = await run_in_threadpool(tts.synthesize, spoken_text(question), length_scale)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data, None

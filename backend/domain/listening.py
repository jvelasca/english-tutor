"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from pathlib import Path

from starlette.concurrency import run_in_threadpool

from repositories import db
from repositories import listening as listening_repo
from services import tts
from services.listening import (
    audio_text,
    current_level,
    difficulty_from_vector,
    get_question,
    length_scale_for_rate,
    level_status,
    listening_diagnostic,
    pick_next_question,
    score_answer,
)


def _audio_cache_dir() -> Path:
    """Carpeta de audio pre-renderizado (cache en disco, local)."""
    return db.DATA_DIR / "listening"


def _audio_path(question_id: str) -> Path:
    return _audio_cache_dir() / f"{question_id}.wav"


def audio_ready(question: dict) -> bool:
    """True si el ítem puede servir audio de referencia reproducible."""
    return bool(audio_text(question)) and tts.is_ready()


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index) y añade la dificultad derivada del vector."""
    out = {k: v for k, v in question.items() if k != "answer_index"}
    out["difficulty"] = difficulty_from_vector(question.get("difficulty_vector", {}))
    out["audio_ready"] = audio_ready(question)
    return out


async def next_question(user_id: str) -> dict:
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    correct = await run_in_threadpool(listening_repo.correct_question_ids, user_id)
    return _public(pick_next_question(seen, correct))


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
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
        "skill": question.get("skill", ""),
        "difficulty": difficulty,
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
    return listening_diagnostic(attempts)


def _spoken_text(question: dict) -> str:
    """Texto a sintetizar, respetando `repetition_policy` (duplicar para 'twice')."""
    text = audio_text(question)
    if question.get("repetition_policy") == "twice":
        text = f"{text}. {text}"
    return text


async def get_audio(question_id: str) -> tuple[bytes | None, int | None]:
    """Devuelve el audio WAV del ítem (cacheado en disco), o un código de error.

    Retorna `(bytes, None)` con el audio en caso de éxito, o `(None, status)` donde
    `status` es 404 (ítem inexistente) o 503 (sintetizador Piper no disponible). El
    audio se sintetiza en la primera petición y se cachea en `DATA_DIR/listening/`.
    """
    question = get_question(question_id)
    if question is None:
        return None, 404
    if not tts.is_ready():
        return None, 503
    path = _audio_path(question_id)
    if path.exists():
        return path.read_bytes(), None
    length_scale = length_scale_for_rate(question.get("speech_rate") or 0.0)
    data = await run_in_threadpool(tts.synthesize, _spoken_text(question), length_scale)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data, None

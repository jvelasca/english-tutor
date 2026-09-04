"""Dominio de las rutas de speaking (V3.8).

Orquesta las APIs de práctica oral por nivel CEFR basada en tarjetas de
micro-conversación guiada: siguiente tarjeta por bucket (all/failed/mastered),
estado del nivel, intentos de respuesta abierta (transcripción + extracción de
evidencia con LLM local + `scores_from_evidence` + persistencia), audio modelo
TTS con caché por tipo de audio (línea del interlocutor o respuesta modelo),
estadísticas con puerta de ruta honesta y la práctica extra generada con IA
local en segundo plano (el mismo patrón de `domain.listening_extras`).

La ruta mide práctica: el estado por nivel es `not_started` / `developing` /
`functional`. Demostrar el nivel es del Speaking Assessment y la evidencia formal
(vía `services.speaking.speaking_level`); este dominio nunca emite `demonstrated`.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from repositories import db
from repositories import settings as settings_repo
from repositories import speaking_routes as speaking_repo
from schemas.chat import ChatMessage
from services import speaking_generate as gen
from services import speaking_llm
from services import tts
from services.curriculum import SPEAKING_CORPUS_VERSION
from services.llm import chat_once
from services.speaking import scores_from_evidence
from services.speaking_routes import (
    GENERATED_ID_PREFIX,
    LEVEL_ORDER,
    SPEAKING_PASS_THRESHOLD,
    SPEAKING_TOPICS,
    current_level,
    difficulty_from_vector,
    get_phrase,
    level_items as motor_level_items,
    phrases_for_level,
    review_next_phrase,
    route_competence,
    route_gate,
    topics_for_level,
)
from services.translate import pick_model

# Nº de tarjetas pedidas al modelo por llamada y techo de llamadas por trabajo
# (permite reintentar tandas vacías sin dejar el trabajo colgado para siempre).
BATCH = 6
_MAX_CALLS_FACTOR = 2


class EvidenceExtractionError(Exception):
    """El LLM local no produjo evidencia válida para un intento de conversación.

    Es un fallo transitorio del extractor (Ollama ocupado o salida no JSON): el
    router lo traduce a un 503 para que el alumno reintente. Nunca se puntúa un
    intento en falso ni se marca como fallido.
    """


# Tipos de audio sintetizables de una tarjeta de intercambio.
AUDIO_KINDS = ("opening", "model")


def _kind_text(phrase: dict, kind: str) -> str:
    """Texto de una tarjeta según el tipo de audio pedido."""
    if kind == "model":
        return phrase.get("model_response", "")
    return phrase.get("app_line", "")


def _card_task(phrase: dict) -> str:
    """Instrucción de evaluación de una tarjeta (sin la respuesta modelo).

    El extractor de evidencia recibe la tarea que el alumno debía cumplir: la
    situación, su rol y la línea del interlocutor a la que respondió. La respuesta
    modelo se omite aquí (no debe sesgar la evidencia).
    """
    setup = (phrase.get("setup") or "").strip()
    role = (phrase.get("you") or "").strip()
    line = (phrase.get("app_line") or "").strip()
    parts = []
    if setup:
        parts.append(f"Scenario: {setup}")
    if role:
        parts.append(f"Your role: {role}")
    if line:
        parts.append(f'The other person says: "{line}"')
    parts.append("Respond to them naturally in English.")
    return "\n".join(parts)


def _generated_payload(row: dict | None) -> dict | None:
    """Payload completo de una tarjeta extra desde una fila del catálogo global."""
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


def _next_item_id(level: str) -> str:
    return f"{GENERATED_ID_PREFIX}{level}-{uuid.uuid4().hex[:8]}"


async def _extra_phrases(user_id: str, level: str) -> list[dict]:
    """Tarjetas extra activadas por el usuario en una ruta (dicts completos)."""
    rows = await run_in_threadpool(
        speaking_repo.list_route_extras, user_id, level
    )
    if not rows:
        return []
    ids = [r["phrase_id"] for r in rows]
    catalog = await run_in_threadpool(speaking_repo.list_generated_by_ids, ids)
    by_id = {row["id"]: row for row in catalog}
    phrases: list[dict] = []
    for pid in ids:
        payload = _generated_payload(by_id.get(pid))
        if payload:
            phrases.append(payload)
    return phrases


async def _resolve_phrase(phrase_id: str) -> dict | None:
    """Resuelve una tarjeta del banco curado o, si es extra (id `sp-`), del catálogo."""
    phrase = get_phrase(phrase_id)
    if phrase is not None:
        return phrase
    if phrase_id.startswith(GENERATED_ID_PREFIX):
        row = await run_in_threadpool(speaking_repo.get_generated, phrase_id)
        return _generated_payload(row)
    return None


# --- Audio modelo (TTS) ------------------------------------------------------


def _audio_cache_dir(voice: str) -> Path:
    """Carpeta de audio modelo pre-renderizado, versionada por voz.

    El versionado (`SPEAKING_CORPUS_VERSION` + la voz elegida) y el digest del
    contenido garantizan que un cambio de tarjeta/voz invalide el WAV antiguo.
    """
    return db.DATA_DIR / "speaking" / SPEAKING_CORPUS_VERSION / voice


def _audio_path(phrase: dict, voice: str, kind: str) -> Path:
    text = _kind_text(phrase, kind)
    digest = hashlib.sha1(f"{text}|{voice}".encode()).hexdigest()[:12]
    return _audio_cache_dir(voice) / f"{phrase['id']}-{kind}-{digest}.wav"


def audio_ready(phrase: dict) -> bool:
    """True si la tarjeta puede servir voz modelo reproducible (Piper disponible)."""
    return bool(phrase.get("app_line")) and bool(phrase.get("model_response")) and tts.is_ready()


def _phrase_public(phrase: dict) -> dict:
    """Forma pública de una tarjeta: contexto + línea del interlocutor + audio.

    NO incluye `model_response`: la respuesta modelo se revela en la respuesta
    del intento, después de que el alumno haya hablado.
    """
    return {
        "id": phrase["id"],
        "level": phrase.get("level", ""),
        "setup": phrase.get("setup", ""),
        "you": phrase.get("you", ""),
        "app_line": phrase.get("app_line", ""),
        "topic": phrase.get("topic", ""),
        "difficulty": difficulty_from_vector(phrase.get("difficulty_vector", {})),
        "difficulty_vector": phrase.get("difficulty_vector", {}),
        "audio_ready": audio_ready(phrase),
    }


async def get_audio(
    user_id: str, phrase_id: str, kind: str = "opening"
) -> tuple[bytes | None, int | None]:
    """Audio WAV modelo (línea del interlocutor o respuesta modelo) con caché.

    Devuelve `(bytes, None)` en éxito, o `(None, status)`: 404 tarjeta inexistente
    o `kind` no válido, 503 Piper no disponible. Se sintetiza a la primera petición
    y se cachea en `DATA_DIR/speaking/{corpus_version}/{voice}/{id}-{kind}-{digest}.wav`.
    """
    if kind not in AUDIO_KINDS:
        return None, 404
    phrase = await _resolve_phrase(phrase_id)
    if phrase is None:
        return None, 404
    text = _kind_text(phrase, kind)
    if not text:
        return None, 404
    prefs = await run_in_threadpool(settings_repo.get_settings, user_id)
    voice = tts.resolve_voice(prefs)
    if not tts.is_ready(voice):
        return None, 503
    path = _audio_path(phrase, voice, kind)
    if path.exists():
        return path.read_bytes(), None
    data = await run_in_threadpool(tts.synthesize, text, 1.0, voice)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data, None


# --- Progreso y sesión de práctica -------------------------------------------


async def next_phrase(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente tarjeta del pool de una ruta (nueva/failed/mastered).

    Sin `level`, elige el nivel por cobertura del banco oficial. Lanza
    `ValueError("speaking.no_failed")` si no queda nada en el bucket pedido.
    """
    attempts_rows = await run_in_threadpool(speaking_repo.list_attempts, user_id)
    if level is None:
        passed = await run_in_threadpool(speaking_repo.passed_phrase_ids, user_id)
        level = current_level(passed)
    extra = await _extra_phrases(user_id, level)
    only_failed = mode == "failed"
    only_mastered = mode == "mastered"
    phrase = review_next_phrase(
        level,
        attempts_rows,
        only_failed=only_failed,
        only_mastered=only_mastered,
        extra_phrases=extra,
    )
    return _phrase_public(phrase)


async def phrases_for_level_out(user_id: str, level: str) -> dict:
    """Estado por tarjeta de un nivel + contadores (para el panel del nivel)."""
    attempts_rows = await run_in_threadpool(speaking_repo.list_attempts, user_id)
    extra = await _extra_phrases(user_id, level)
    items = motor_level_items(
        level, attempts_rows, extra_phrases=extra
    )
    gate = route_gate(level, attempts_rows)
    counts = {"mastered": 0, "failed": 0, "unseen": 0}
    for item in items:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {
        "level": level,
        "total": len(items),
        "mastered": counts.get("mastered", 0),
        "failed": counts.get("failed", 0),
        "unseen": counts.get("unseen", 0),
        "completed": gate["passed"],
        "items": items,
        "gate": gate,
    }


async def submit_attempt(
    user_id: str,
    phrase_id: str,
    heard: str,
    duration_seconds: float | None = None,
) -> dict | None:
    """Puntúa un turno abierto de micro-conversación y persiste el intento.

    El turno del alumno se evalúa como respuesta abierta (el mismo pipeline de
    misiones/assessment): el LLM local extrae la evidencia sobre la tarea de la
    tarjeta y el scorer determinista calcula criterios y overall. Si el extractor
    no produce evidencia válida se lanza `EvidenceExtractionError` (transitorio)
    para que el frontend ofrezca reintentar. None si la tarjeta no existe.
    """
    phrase = await _resolve_phrase(phrase_id)
    if phrase is None:
        return None
    model = await pick_model(None)
    task = _card_task(phrase)
    evidence = await speaking_llm.extract_speaking_evidence(task, heard, model)
    if evidence is None:
        raise EvidenceExtractionError(
            "el extractor de evidencia no devolvió una salida válida"
        )
    scored = scores_from_evidence(
        evidence, heard, duration_seconds, task_type="conversation"
    )
    overall = float(scored["overall"])
    passed = overall >= SPEAKING_PASS_THRESHOLD
    topic = phrase.get("topic", "")
    difficulty = difficulty_from_vector(phrase.get("difficulty_vector", {}))
    await run_in_threadpool(
        speaking_repo.record_attempt,
        user_id,
        phrase_id,
        phrase.get("level", ""),
        overall,
        passed,
        difficulty,
        topic,
    )
    return {
        "phrase_id": phrase_id,
        "level": phrase.get("level", ""),
        "app_line": phrase.get("app_line", ""),
        "heard": heard,
        "model_response": phrase.get("model_response", ""),
        "overall": overall,
        "passed": passed,
        "criteria": scored["criteria"],
        "observed": scored["observed"],
        "topic": topic,
        "difficulty": difficulty,
    }


async def get_stats(user_id: str) -> dict:
    """Progreso del mapa de rutas de speaking (niveles + puertas honestas)."""
    attempts_rows = await run_in_threadpool(speaking_repo.list_attempts, user_id)
    passed_rows = [r for r in attempts_rows if r.get("passed")]
    accuracy = (
        round(len(passed_rows) / len(attempts_rows) * 100, 1)
        if attempts_rows
        else None
    )
    levels: list[dict] = []
    for level in LEVEL_ORDER:
        extra = await _extra_phrases(user_id, level)
        gate = route_gate(level, attempts_rows)
        items = motor_level_items(level, attempts_rows, extra_phrases=extra)
        mastered = sum(1 for i in items if i["state"] == "mastered")
        extras = sum(1 for i in items if i["source"] == "generated")
        extras_mastered = sum(
            1 for i in items if i["source"] == "generated" and i["state"] == "mastered"
        )
        levels.append(
            {
                "level": level,
                "total": len(items),
                "mastered": mastered,
                "completed": gate["passed"],
                "coverage_pct": gate["coverage_pct"],
                "accuracy": gate["accuracy"],
                "gate": gate,
                "state": next(
                    (c["state"] for c in route_competence(attempts_rows) if c["level"] == level),
                    "not_started",
                ),
                "base_total": gate["total"],
                "base_mastered": gate["mastered"],
                "extras": extras,
                "extras_mastered": extras_mastered,
            }
        )
    # Nivel actual: primer nivel oficial sin dominar; si todos, el último.
    passed_official: set[str] = set()
    for row in attempts_rows:
        pid = row.get("phrase_id")
        base = get_phrase(pid) if pid else None
        if base is not None and row.get("passed"):
            passed_official.add(pid)
    level = current_level(passed_official)
    completed = all(g["gate"]["passed"] for g in levels if g["base_total"] > 0)
    return {
        "attempts": len(attempts_rows),
        "passed": len(passed_rows),
        "accuracy": accuracy,
        "level": level,
        "completed": completed,
        "levels": levels,
    }


# --- Práctica extra generada (V3.7/V3.8) -------------------------------------


async def start_extras_job(
    user_id: str, level: str, requested: int
) -> tuple[dict, bool]:
    """Crea (o reutiliza) el trabajo de generación de extras de una ruta."""
    running = await run_in_threadpool(
        speaking_repo.running_generation_job, user_id, level
    )
    if running:
        return running, False
    job = await run_in_threadpool(
        speaking_repo.create_generation_job, user_id, level, requested
    )
    return job, True


async def extras_job(job_id: str) -> dict | None:
    """Estado de un trabajo de generación para el polling del frontend."""
    return await run_in_threadpool(speaking_repo.get_generation_job, job_id)


async def route_extras(user_id: str, level: str) -> dict:
    """Tarjetas extra activadas en la ruta de un usuario (ids)."""
    rows = await run_in_threadpool(
        speaking_repo.list_route_extras, user_id, level
    )
    ids = [r["phrase_id"] for r in rows]
    return {"level": level, "total": len(ids), "phrase_ids": ids}


async def remove_route_extra(
    user_id: str, level: str, phrase_id: str
) -> bool:
    """Desactiva una tarjeta extra de la ruta. False si no estaba activada."""
    return await run_in_threadpool(
        speaking_repo.remove_route_extra, user_id, level, phrase_id
    )


def _rotate(items: list[str], offset: int, index: int) -> list[str]:
    """Selecciona `index` elementos de `items` rotando desde `offset`."""
    n = len(items)
    if n == 0:
        return []
    return [items[(offset + i * 3) % n] for i in range(index)]


async def _catalog_phrase_keys(level: str) -> set[str]:
    """Claves canónicas de las tarjetas ya presentes (banco curado + catálogo).

    La clave canónica identifica la tarjeta por su intercambio (línea del
    interlocutor + respuesta modelo normalizadas), de modo que un contenido ya
    generado o del banco no se vuelve a insertar.
    """
    keys = {gen.canonical_card(p, level) for p in phrases_for_level(level)}
    rows = await run_in_threadpool(speaking_repo.list_generated, level)
    for row in rows:
        try:
            payload = json.loads(row.get("payload_json") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            keys.add(gen.canonical_card(payload, level))
    return keys


async def run_extras_job(job_id: str) -> None:
    """Ejecuta un trabajo de generación de tarjetas extra en segundo plano.

    Genera en tandas de `BATCH`, valida/persiste cada tarjeta en el catálogo global
    (deduplicando por intercambio) y al terminar las activa en la ruta del usuario.
    Nunca lanza: los errores quedan en el trabajo para que el frontend los muestre.
    """
    job = await run_in_threadpool(speaking_repo.get_generation_job, job_id)
    if job is None or job["status"] != "running":
        return
    user_id = job["user_id"]
    level = job["level"]
    requested = int(job["requested"])
    added_ids: list[str] = []
    try:
        existing = await _catalog_phrase_keys(level)
        level_topics = list(topics_for_level(level)) or list(SPEAKING_TOPICS)
        model = await pick_model(None)
        remaining = requested
        max_calls = max(2, math.ceil(requested / BATCH) * _MAX_CALLS_FACTOR)
        calls = 0
        while remaining > 0 and calls < max_calls:
            calls += 1
            ask = min(remaining, BATCH)
            topics = _rotate(level_topics, calls * 2, ask)
            prompt = gen.build_user_prompt(level, topics, allowed=level_topics)
            reply = await chat_once(
                messages=[ChatMessage(role="user", content=prompt)],
                model=model,
                temperature=0.7,
                system_prompt=gen.SYSTEM_PROMPT,
            )
            try:
                raws = gen.parse_content(reply.content)
            except ValueError:
                raws = []
            for raw in raws:
                if remaining <= 0:
                    break
                item_id = _next_item_id(level)
                payload = gen.compose_item(level, raw, item_id=item_id)
                if payload is None:
                    continue
                key = gen.canonical_card(payload, level)
                if key in existing:
                    continue  # contenido ya generado o del banco: no se duplica
                if not gen.validate_payload_shape(payload):
                    continue
                inserted = await run_in_threadpool(
                    speaking_repo.insert_generated,
                    payload,
                    gen.GENERATOR_VERSION,
                )
                if not inserted:
                    continue
                existing.add(key)
                added_ids.append(payload["id"])
                remaining = requested - len(added_ids)
            if not raws:
                # El modelo no devolvió JSON en esta tanda: probar de nuevo es
                # caro; se corta con lo que haya (puede ser vacío).
                break
        await run_in_threadpool(
            speaking_repo.add_route_extras, user_id, level, added_ids
        )
        await run_in_threadpool(
            speaking_repo.finish_generation_job, job_id, added_ids
        )
    except Exception as exc:  # noqa: BLE001 - el error se informa en el trabajo
        message = f"{type(exc).__name__}: {exc}"[:500]
        await run_in_threadpool(
            speaking_repo.finish_generation_job, job_id, added_ids, error=message
        )


def is_valid_level(level: str) -> bool:
    return level in LEVEL_ORDER

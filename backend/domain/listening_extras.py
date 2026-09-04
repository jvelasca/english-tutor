"""Dominio de la práctica extra generada de listening (V3.6).

Orquesta la generación de ítems extra con IA local en un trabajo en segundo
plazo: el POST de extras crea un trabajo (tabla `listening_generation_jobs`), el
frontend hace polling de su estado y, al terminar, los ítems generados quedan
activados en la ruta del usuario (`listening_route_extras`). El contenido
generado vive en el catálogo global `listening_generated` y es compartido entre
perfiles (la caché de audio y la deduplicación se reutilizan).

La puerta de ruta y la certificación siguen calculándose solo sobre el banco
curado (ver `domain.listening.get_stats`): este módulo solo aporta práctica
adicional voluntaria.
"""
from __future__ import annotations

import json
import math
import uuid

from starlette.concurrency import run_in_threadpool

from repositories import listening as listening_repo
from schemas.chat import ChatMessage
from services import listening_generate as gen
from services.listening import (
    GENERATED_ID_PREFIX,
    LEVEL_ORDER,
    LISTENING_TOPICS,
    questions_for_level,
)
from services.llm import chat_once
from services.translate import pick_model

# Ítems pedidos al modelo en cada llamada. Pedir de uno en uno es lo más fiable
# (JSON corto, menos inválidos), pero muy lento; 5 equilibra fiabilidad y
# latencia en un modelo local.
BATCH = 5
# Nº máximo de llamadas al modelo por trabajo (permite reintentar tandas vacías
# sin dejar el trabajo colgado para siempre).
_MAX_CALLS_FACTOR = 2


def _next_item_id(level: str) -> str:
    return f"{GENERATED_ID_PREFIX}{level}-{uuid.uuid4().hex[:8]}"


async def start_extras_job(
    user_id: str, level: str, requested: int
) -> tuple[dict, bool]:
    """Crea (o reutiliza) el trabajo de generación de extras de una ruta.

    Devuelve `(job, is_new)`: si ya hay un trabajo `running` del mismo usuario y
    nivel, devuelve ese trabajo con `is_new=False` (el router no lanza una
    segunda ejecución en paralelo); si no, crea uno nuevo con `is_new=True`.
    """
    running = await run_in_threadpool(
        listening_repo.running_generation_job, user_id, level
    )
    if running:
        return running, False
    job = await run_in_threadpool(
        listening_repo.create_generation_job, user_id, level, requested
    )
    return job, True


async def extras_job(job_id: str) -> dict | None:
    """Estado de un trabajo de generación para el polling del frontend."""
    return await run_in_threadpool(listening_repo.get_generation_job, job_id)


async def route_extras(user_id: str, level: str) -> dict:
    """Ítems extra activados en la ruta de un usuario (ids)."""
    rows = await run_in_threadpool(
        listening_repo.list_route_extras, user_id, level
    )
    ids = [r["question_id"] for r in rows]
    return {"level": level, "total": len(ids), "question_ids": ids}


async def remove_route_extra(
    user_id: str, level: str, question_id: str
) -> bool:
    """Desactiva un ítem extra de la ruta. False si no estaba activado."""
    return await run_in_threadpool(
        listening_repo.remove_route_extra, user_id, level, question_id
    )


def _rotate(items: list[str], offset: int, index: int) -> list[str]:
    """Selecciona `index+1` elementos de `items` rotando desde `offset`.

    Da variedad determinista de skill/topic entre tandas sin repetir en exceso.
    """
    n = len(items)
    return [items[(offset + i * 3) % n] for i in range(index)]


async def _catalog_script_keys(level: str) -> set[str]:
    """Formas canónicas de los scripts ya presentes (banco curado + catálogo)."""
    keys = {gen.canonical_script(q["script"]) for q in questions_for_level(level)}
    rows = await run_in_threadpool(listening_repo.list_generated, level)
    for row in rows:
        try:
            payload = json.loads(row.get("payload_json") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get("script"):
            keys.add(gen.canonical_script(payload["script"]))
    return keys


async def run_extras_job(job_id: str) -> None:
    """Ejecuta un trabajo de generación en segundo plano.

    Genera los ítems en tandas de `BATCH`, valida y persiste cada uno en el
    catálogo global (deduplicando por script), y al terminar los activa en la
    ruta del usuario. Actualiza el estado del trabajo a `done` (con los ids
    activados) o `error` (con el mensaje). Nunca lanza: los errores quedan en el
    trabajo para que el frontend los muestre.
    """
    job = await run_in_threadpool(listening_repo.get_generation_job, job_id)
    if job is None or job["status"] != "running":
        return
    user_id = job["user_id"]
    level = job["level"]
    requested = int(job["requested"])
    added_ids: list[str] = []
    try:
        existing = await _catalog_script_keys(level)
        model = await pick_model(None)
        remaining = requested
        max_calls = max(2, math.ceil(requested / BATCH) * _MAX_CALLS_FACTOR)
        calls = 0
        while remaining > 0 and calls < max_calls:
            calls += 1
            ask = min(remaining, BATCH)
            skills = _rotate(list(gen.GENERATED_SUBSKILLS), calls, ask)
            topics = _rotate(list(LISTENING_TOPICS), calls * 2, ask)
            prompt = gen.build_user_prompt(level, skills, topics)
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
                key = gen.canonical_script(payload["script"])
                if key in existing:
                    continue  # contenido ya generado o del banco: no se duplica
                if not gen.validate_payload_shape(payload):
                    continue
                inserted = await run_in_threadpool(
                    listening_repo.insert_generated,
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
        # Activa los ítems generados en la ruta del usuario.
        await run_in_threadpool(
            listening_repo.add_route_extras, user_id, level, added_ids
        )
        await run_in_threadpool(
            listening_repo.finish_generation_job, job_id, added_ids
        )
    except Exception as exc:  # noqa: BLE001 - el error se informa en el trabajo
        message = f"{type(exc).__name__}: {exc}"[:500]
        await run_in_threadpool(
            listening_repo.finish_generation_job, job_id, added_ids, error=message
        )


async def resolve_generated_question(question_id: str) -> dict | None:
    """Carga el payload de un ítem generado del catálogo (para audio/respuesta)."""
    if not question_id.startswith(GENERATED_ID_PREFIX):
        return None
    row = await run_in_threadpool(listening_repo.get_generated, question_id)
    if row is None:
        return None
    try:
        payload = json.loads(row.get("payload_json") or "")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload["id"] = row.get("id", "")
    return payload


def is_valid_level(level: str) -> bool:
    return level in LEVEL_ORDER

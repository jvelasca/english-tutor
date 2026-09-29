"""Precalentado del diccionario del alumno (V3.88.0).

La PRIMERA consulta de una palabra sin caché paga una generación con el modelo
local (hasta `config.DICTIONARY_GENERATION_TIMEOUT_SECONDS`). En CPU eso se nota:
el alumno espera sin saber cuánto. Este módulo convierte ese coste en un trabajo
de fondo: el alumno pide «precargar mis palabras», el backend responde 202 y va
generando las que falten; el frontend hace polling del progreso.

Decisiones deliberadas:

- **En proceso, no en tabla.** El RESULTADO del trabajo es la caché global
  `dictionary_entries`, que sí es persistente; perder el registro del trabajo
  (reinicio del backend) no pierde contenido, solo la barra de progreso. La app
  es un único proceso local, así que un registro en memoria basta y evita una
  migración de esquema. Es la diferencia con los trabajos de listening
  (`listening_generation_jobs`), cuyo resultado SÍ son filas propias.
- **Reutiliza el camino de la consulta.** Cada palabra pasa por
  `vocabulary.warm_dictionary_word`, que ES el single-flight de la consulta: si
  el alumno busca esa palabra mientras se precalienta, comparten la misma
  generación, y las cuotas (`_generation_quota_allowed`) y la negative cache se
  respetan igual. Precalentar no es una puerta trasera.
- **Un trabajo por usuario.** Pedir dos veces no lanza dos barridos en paralelo
  sobre el mismo léxico: se devuelve el que ya está corriendo.
- **Best-effort por palabra.** Una palabra que no se puede preparar (sin cupo,
  modelo caído, timeout) cuenta como `skipped`, no como error: se puede
  reintentar más tarde y no invalida el resto de la pasada.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from starlette.concurrency import run_in_threadpool

import config
from domain import vocabulary as vocabulary_domain
from repositories import vocabulary as vocabulary_repo

logger = logging.getLogger(__name__)

# Registro en memoria de trabajos (ver docstring). `_JOB_ORDER` solo existe para
# descartar el más antiguo cuando se supera el tope retenido.
_JOBS: dict[str, dict[str, Any]] = {}
_JOB_ORDER: list[str] = []


def _trim_jobs() -> None:
    """Descarta los trabajos más antiguos por encima del tope retenido."""
    while len(_JOB_ORDER) > config.DICTIONARY_WARMUP_JOBS_KEPT:
        oldest = _JOB_ORDER.pop(0)
        _JOBS.pop(oldest, None)


def _running_job_for(user_id: str) -> dict[str, Any] | None:
    """Trabajo en curso del usuario, si lo hay (evita barridos duplicados)."""
    for job_id in reversed(_JOB_ORDER):
        job = _JOBS.get(job_id)
        if job and job.get("user_id") == user_id and job.get("status") == "running":
            return job
    return None


async def lexicon_words(user_id: str, limit: int) -> list[str]:
    """Palabras del léxico del alumno, sin duplicados y en su orden.

    El orden de `get_vocabulary` (más producidas primero) se respeta: es el
    mejor indicador disponible de qué palabras el alumno trata de verdad. El
    tope evita recorrer un léxico enorme en una sola pasada.
    """
    rows = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    words: list[str] = []
    seen: set[str] = set()
    for row in rows:
        word = str((row or {}).get("word") or "").strip().lower()
        if not word or word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) >= limit:
            break
    return words


async def start_warmup_job(
    user_id: str, limit: int | None = None
) -> tuple[dict[str, Any], bool]:
    """Crea (o reutiliza) el trabajo de precalentado del léxico del alumno.

    Devuelve `(job, is_new)`. Con un trabajo del mismo usuario ya corriendo
    devuelve ese (`is_new=False`) y el router no lanza una segunda ejecución.
    """
    requested = limit if limit is not None else config.DICTIONARY_WARMUP_MAX_WORDS
    requested = max(1, min(int(requested), config.DICTIONARY_WARMUP_MAX_WORDS))
    running = _running_job_for(user_id)
    if running is not None:
        return running, False
    words = await lexicon_words(user_id, requested)
    job: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "status": "running",
        "total": len(words),
        "prepared": 0,
        "skipped": 0,
        "pending": len(words),
        "error": None,
        # Lista de trabajo interna: no sale en la respuesta (el esquema no la
        # declara). Se retira al terminar para no retener memoria.
        "words": words,
    }
    if not words:
        # Nada que preparar: no tiene sentido dejar un trabajo corriendo ni
        # ocupar un hueco del registro. El 202 puede declararlo ya terminado.
        job["status"] = "done"
        job.pop("words", None)
    _JOBS[job["id"]] = job
    _JOB_ORDER.append(job["id"])
    _trim_jobs()
    return job, True


async def warmup_job(job_id: str) -> dict[str, Any] | None:
    """Estado de un trabajo de precalentado, para el polling del frontend."""
    return _JOBS.get(job_id)


async def run_warmup_job(job_id: str) -> None:
    """Recorre el léxico preparando lo que falte. Corre tras responder 202.

    Actualiza el progreso tras CADA palabra: el polling ve avanzar la barra en
    lugar de un salto final. Nunca propaga excepciones al servidor (el trabajo
    las declara como `error` y termina): el precalentado no puede tumbar la app.
    """
    job = _JOBS.get(job_id)
    if job is None or job.get("status") != "running":
        return
    user_id = str(job["user_id"])
    try:
        for word in list(job.get("words") or []):
            result = await vocabulary_domain.warm_dictionary_word(
                word, user_id=user_id
            )
            if result is None:
                job["skipped"] += 1
            else:
                job["prepared"] += 1
            job["pending"] = max(
                0, int(job["total"]) - int(job["prepared"]) - int(job["skipped"])
            )
        job["status"] = "done"
    except Exception as exc:  # noqa: BLE001 — el trabajo nunca rompe el proceso
        logger.exception("Diccionario: fallo en el precalentado %s", job_id)
        job["status"] = "error"
        job["error"] = type(exc).__name__
    finally:
        job.pop("words", None)
        job["pending"] = max(
            0, int(job["total"]) - int(job["prepared"]) - int(job["skipped"])
        )

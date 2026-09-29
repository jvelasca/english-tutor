"""Repositorio de listening (SQLite)."""
from __future__ import annotations

import json
import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str,
    question_id: str,
    answer_index: int,
    correct: bool,
    skill: str = "",
    difficulty: int = 1,
    response_time_ms: int | None = None,
    replay_count: int = 0,
    topic: str = "",
    realized_difficulty: int = 0,
    task_type: str = "mcq",
    score: float | None = None,
    layer: str = "",
    speed_used: str = "normal",
    stage: str = "",
    transcript_used: str = "",
    segments_replayed: int = 0,
    shadowing_duration_ms: int | None = None,
    shadowing_speech_rate: float | None = None,
    word_breakdown: dict | None = None,
    outcome: str = "",
) -> bool:
    """Persiste un intento de listening para un usuario existente.

    Los kwargs `task_type` y `score` son opcionales y compatibles hacia atrás: el
    flujo MCQ no los pasa (queda `task_type="mcq"` y `score=None`); las tareas de
    producción (dictado/shadowing) sí, dejando `score` como evidencia continua 0..1.

    Los kwargs `layer`/`speed_used`/`stage`/`transcript_used`/`segments_replayed`
    (V3.27, Listening Engine 4.0) registran el apoyo con el que se respondió para
    medir "precisión con apoyo decreciente"; tienen defaults que preservan el
    comportamiento de los llamadores existentes.

    Los kwargs `shadowing_duration_ms`/`shadowing_speech_rate` (V3.28, Bloque E)
    son señales auxiliares informativas del Shadowing 2.0, nullables: el cliente
    las calcula desde el audio grabado y jamás participan en mastery/gate.

    `word_breakdown` (V3.29, Fase 3) es la evidencia de palabra fallada del
    intento (dictado erróneo → breakdown de `word_alignment`; cloze/segmentation
    fallado → `{"target": <palabra diana>}`); se serializa a JSON en
    `word_breakdown_json`. Default `None` retrocompatible: los intentos sin
    breakdown (MCQ correcto, dictado acertado…) guardan `NULL`.

    `outcome` (V3.89, Listening robusto) clasifica el DESENLACE pedagógico del
    intento (`correct_first`/`correct_retry`/`wrong`/`hint_used`/`solution_shown`;
    ver `services/listening_review.py`). Default `""` retrocompatible: los
    llamadores que no lo declaran conservan el comportamiento anterior.
    """
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, topic, realized_difficulty, "
            "task_type, score, layer, speed_used, stage, transcript_used, "
            "segments_replayed, shadowing_duration_ms, shadowing_speech_rate, "
            "word_breakdown_json, outcome, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?)",
            (
                user_id,
                question_id,
                answer_index,
                int(correct),
                skill,
                difficulty,
                response_time_ms,
                replay_count,
                topic,
                realized_difficulty,
                task_type,
                score,
                layer,
                speed_used,
                stage,
                transcript_used,
                segments_replayed,
                shadowing_duration_ms,
                shadowing_speech_rate,
                json.dumps(word_breakdown) if word_breakdown is not None else None,
                outcome,
                _now(),
            ),
        )
    return True


def list_attempts(user_id: str) -> list[dict]:
    """Todas las filas de intentos de listening del usuario, en orden de creación."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, topic, realized_difficulty, "
            "task_type, score, layer, speed_used, stage, transcript_used, "
            "segments_replayed, shadowing_duration_ms, shadowing_speech_rate, "
            "word_breakdown_json, outcome, created_at "
            "FROM listening_attempts WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def seen_question_ids(user_id: str) -> set[str]:
    """Ids de preguntas ya respondidas por el usuario."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM listening_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {r["question_id"] for r in rows}


def correct_question_ids(user_id: str) -> set[str]:
    """Ids de preguntas respondidas correctamente al menos una vez."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM listening_attempts "
            "WHERE user_id = ? AND correct = 1",
            (user_id,),
        ).fetchall()
    return {r["question_id"] for r in rows}


def get_stats(user_id: str) -> dict:
    """Intentos, aciertos y precisión del usuario."""
    with closing(_conn()) as conn:
        attempts = conn.execute(
            "SELECT COUNT(*) FROM listening_attempts WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        correct = conn.execute(
            "SELECT COUNT(*) FROM listening_attempts "
            "WHERE user_id = ? AND correct = 1",
            (user_id,),
        ).fetchone()[0]
    accuracy = round(correct / attempts * 100, 1) if attempts else None
    return {"attempts": attempts, "correct": correct, "accuracy": accuracy}


# --- Listening extra generado (V3.6) ------------------------------------------
# Ítems de práctica extra generados con IA local: catálogo global en
# `listening_generated`, activación por usuario en `listening_route_extras` y
# trabajos de generación en segundo plano en `listening_generation_jobs`.
# El contenido extra nunca participa en la puerta de ruta ni en la certificación
# (siempre se calculan sobre el banco curado).


def insert_generated(item: dict, generator_version: str) -> bool:
    """Persiste un ítem generado en el catálogo global.

    Devuelve True si se insertó (nuevo contenido); False si ya existía un ítem
    con el mismo `level` y contenido (se ignora). El `id` vive en su propia
    columna y se guarda FUERA del `payload_json` para que la restricción
    `UNIQUE(level, payload_json)` deduplique por contenido aunque dos ids
    distintos tengan el mismo texto (una segunda generación no crea copias).
    """
    payload = {k: v for k, v in item.items() if k != "id"}
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO listening_generated "
            "(id, level, payload_json, generator_version, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (item["id"], item.get("level", ""), json.dumps(payload),
             generator_version, _now()),
        )
        return cur.rowcount > 0


def list_generated_by_ids(ids: list[str]) -> list[dict]:
    """Devuelve las filas del catálogo global para los ids indicados."""
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT id, level, payload_json, generator_version, created_at "
            f"FROM listening_generated WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    return [dict(r) for r in rows]


def get_generated(item_id: str) -> dict | None:
    """Devuelve una fila del catálogo global por id, o None si no existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM listening_generated WHERE id = ?",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None


def list_generated(level: str) -> list[dict]:
    """Todas las filas del catálogo global de un nivel (orden de creación)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, level, payload_json, generator_version, created_at "
            "FROM listening_generated WHERE level = ? ORDER BY id ASC",
            (level,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_route_extras(user_id: str, level: str | None = None) -> list[dict]:
    """Extras activados por un usuario, opcionalmente de un nivel concreto."""
    with closing(_conn()) as conn:
        if level is None:
            rows = conn.execute(
                "SELECT user_id, level, question_id, added_at "
                "FROM listening_route_extras WHERE user_id = ? ORDER BY added_at ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT user_id, level, question_id, added_at "
                "FROM listening_route_extras "
                "WHERE user_id = ? AND level = ? ORDER BY added_at ASC",
                (user_id, level),
            ).fetchall()
    return [dict(r) for r in rows]


def add_route_extras(user_id: str, level: str, question_ids: list[str]) -> int:
    """Activa ítems extra en la ruta de un usuario. Devuelve cuántos eran nuevos.

    INSERT OR IGNORE: activar un ítem ya activado no cuenta como nuevo.
    """
    if not question_ids:
        return 0
    added = 0
    with closing(_conn()) as conn, conn:
        for qid in question_ids:
            cur = conn.execute(
                "INSERT OR IGNORE INTO listening_route_extras "
                "(user_id, level, question_id, added_at) VALUES (?, ?, ?, ?)",
                (user_id, level, qid, _now()),
            )
            if cur.rowcount > 0:
                added += 1
    return added


def remove_route_extra(user_id: str, level: str, question_id: str) -> bool:
    """Desactiva un ítem extra de la ruta de un usuario. True si existía."""
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM listening_route_extras "
            "WHERE user_id = ? AND level = ? AND question_id = ?",
            (user_id, level, question_id),
        )
        return cur.rowcount > 0


def create_generation_job(user_id: str, level: str, requested: int) -> dict:
    """Crea un trabajo de generación en segundo plano y devuelve su fila."""
    job_id = "gj-" + uuid.uuid4().hex[:12]
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_generation_jobs "
            "(id, user_id, level, requested, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (job_id, user_id, level, requested, now, now),
        )
    return get_generation_job(job_id)  # type: ignore[return-value]


def running_generation_job(user_id: str, level: str) -> dict | None:
    """Trabajo en curso (running) del usuario para un nivel, si existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM listening_generation_jobs "
            "WHERE user_id = ? AND level = ? AND status = 'running' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, level),
        ).fetchone()
    return dict(row) if row else None


def get_generation_job(job_id: str) -> dict | None:
    """Devuelve una fila de trabajo por id."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM listening_generation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def list_running_generation_jobs() -> list[dict]:
    """Todos los trabajos de generación en curso (status='running').

    Se usa en `/api/system/status` para que el launcher indique cuándo el
    servidor está generando práctica extra (el backend puede tener varios
    trabajos vivos si se lanzaron desde perfiles/niveles distintos).
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, level, requested, status, added_ids_json, error, "
            "created_at, updated_at FROM listening_generation_jobs "
            "WHERE status = 'running' ORDER BY created_at ASC",
        ).fetchall()
    return [dict(r) for r in rows]



def finish_generation_job(job_id: str, added_ids: list[str], error: str = "") -> None:
    """Cierra un trabajo: `done` con los ids activados o `error` con el mensaje."""
    status = "error" if error else "done"
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE listening_generation_jobs "
            "SET status = ?, added_ids_json = ?, error = ?, updated_at = ? "
            "WHERE id = ?",
            (status, json.dumps(added_ids), error, _now(), job_id),
        )


# --- Cola de repaso de frases falladas (V3.89, Listening robusto) -------------
# Objeto pedagógico separado de FSRS: aquí viven EJERCICIOS/FRASES que el alumno
# no entendió al escucharlas, no vocabulario. La cola es persistente y por
# usuario; `fail_count` es la evidencia de dificultad que ordena la prioridad.
# El cálculo de `next_review_at`/`priority` vive en `services/listening_review.py`
# (puro y testeable); aquí solo se persiste y se lee.

_QUEUE_COLUMNS = (
    "user_id, question_id, level, skill, task_type, fail_count, last_failed_at, "
    "next_review_at, priority, state, created_at, updated_at"
)


def enqueue_failure(
    user_id: str,
    question_id: str,
    *,
    level: str = "",
    skill: str = "",
    task_type: str = "mcq",
    fail_count: int = 1,
    next_review_at: str,
    priority: float,
) -> bool:
    """Inserta o actualiza la entrada de repaso de una frase fallada.

    Upsert por `(user_id, question_id)`: la misma frase que vuelve a fallar
    incrementa `fail_count` y recalcula `next_review_at`/`priority` (el
    llamador los calcula con el módulo puro). Devuelve True si hubo escritura.

    `state` se fuerza a `pending`: un fallo nuevo reabre la entrada aunque
    estuviera `deferred` (el alumno volvió a fallarla, luego toca repasarla).
    """
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_review_queue "
            "(user_id, question_id, level, skill, task_type, fail_count, "
            "last_failed_at, next_review_at, priority, state, created_at, "
            "updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?) "
            "ON CONFLICT(user_id, question_id) DO UPDATE SET "
            "level = excluded.level, "
            "skill = excluded.skill, "
            "task_type = excluded.task_type, "
            "fail_count = excluded.fail_count, "
            "last_failed_at = excluded.last_failed_at, "
            "next_review_at = excluded.next_review_at, "
            "priority = excluded.priority, "
            "state = 'pending', "
            "updated_at = excluded.updated_at",
            (
                user_id,
                question_id,
                level,
                skill,
                task_type,
                max(1, int(fail_count)),
                now,
                next_review_at,
                float(priority),
                now,
                now,
            ),
        )
    return True


def get_queue_entry(user_id: str, question_id: str) -> dict | None:
    """Entrada de la cola para una frase, o None si no está encolada."""
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_QUEUE_COLUMNS} FROM listening_review_queue "
            "WHERE user_id = ? AND question_id = ?",
            (user_id, question_id),
        ).fetchone()
    return dict(row) if row else None


def list_queue(user_id: str, state: str | None = "pending") -> list[dict]:
    """Entradas de la cola del usuario, ordenadas por prioridad DESC.

    `state=None` devuelve todas (auditoría); por defecto solo las `pending`.
    Orden determinista: prioridad DESC y, a igualdad, la más antigua primero.
    """
    with closing(_conn()) as conn:
        if state is None:
            rows = conn.execute(
                f"SELECT {_QUEUE_COLUMNS} FROM listening_review_queue "
                "WHERE user_id = ? ORDER BY priority DESC, last_failed_at ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_QUEUE_COLUMNS} FROM listening_review_queue "
                "WHERE user_id = ? AND state = ? "
                "ORDER BY priority DESC, last_failed_at ASC",
                (user_id, state),
            ).fetchall()
    return [dict(r) for r in rows]


def due_queue(user_id: str, now: str) -> list[dict]:
    """Entradas `pending` cuya `next_review_at` ya venció, por prioridad DESC.

    `now` es una marca ISO-8601 comparable lexicográficamente (mismo formato que
    `_now()`), de modo que la comparación es de cadenas y no necesita SQLite
    que entienda fechas.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_QUEUE_COLUMNS} FROM listening_review_queue "
            "WHERE user_id = ? AND state = 'pending' AND next_review_at <= ? "
            "ORDER BY priority DESC, last_failed_at ASC",
            (user_id, now),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_queue_reviewed(user_id: str, question_id: str) -> bool:
    """Marca una entrada como repasada (la resuelve y la saca de la cola)."""
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM listening_review_queue "
            "WHERE user_id = ? AND question_id = ?",
            (user_id, question_id),
        )
        return cur.rowcount > 0


def defer_queue_entry(user_id: str, question_id: str, next_review_at: str) -> bool:
    """Pospone una entrada (`state='deferred'`) hasta `next_review_at`.

    «Repasar después» no es ignorar: la entrada sigue viva y con nueva fecha.
    """
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE listening_review_queue "
            "SET state = 'deferred', next_review_at = ?, updated_at = ? "
            "WHERE user_id = ? AND question_id = ?",
            (next_review_at, _now(), user_id, question_id),
        )
        return cur.rowcount > 0


def queue_fail_counts(user_id: str) -> dict[str, int]:
    """Mapa `question_id → fail_count` de las entradas en cola del usuario.

    Sirve para no volver a fallar «desde cero»: la cola ya guarda cuántas veces
    se falló la frase, así que un nuevo fallo incrementa sobre ese número.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT question_id, fail_count FROM listening_review_queue "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {r["question_id"]: int(r["fail_count"]) for r in rows}


# --- Puente Listening → FSRS (V3.92, integración pedagógica) ------------------
# Rastro append-only de la evidencia de dificultad que un fallo de comprensión
# deja en una palabra del léxico del alumno. La carta FSRS guarda el ESTADO
# (`difficulty`, `due_at`, `why`); aquí queda el SUCESO, que es lo que permite
# contarlo por día y explicar de qué frase vino (`question_id`).

_EVIDENCE_COLUMNS = (
    "id, user_id, question_id, word, fail_count, difficulty_before, "
    "difficulty_after, due_at, created_at"
)


def record_difficulty_evidence(
    user_id: str,
    question_id: str,
    word: str,
    *,
    fail_count: int = 1,
    difficulty_before: float = 0.0,
    difficulty_after: float = 0.0,
    due_at: str = "",
) -> bool:
    """Registra una subida de dificultad de `word` causada por `question_id`.

    Devuelve False si el usuario no existe. No deduplica: dos fallos distintos de
    la misma palabra en la misma frase son DOS evidencias, y contarlas es la
    lectura honesta (la carta, en cambio, se acota sola: su dificultad está
    topada en 10).
    """
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_difficulty_evidence "
            "(user_id, question_id, word, fail_count, difficulty_before, "
            "difficulty_after, due_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                question_id,
                str(word or "").strip().lower(),
                max(1, int(fail_count)),
                float(difficulty_before),
                float(difficulty_after),
                due_at,
                _now(),
            ),
        )
    return True


def list_difficulty_evidence(user_id: str, day: str = "") -> list[dict]:
    """Evidencia del puente del usuario, opcionalmente de un día (`YYYY-MM-DD`).

    Mismo criterio de día que `services.daily_plan.rows_on_day` (los 10 primeros
    caracteres de la marca ISO): no se parsea la fecha ni se depende de SQLite
    para entenderla.
    """
    with closing(_conn()) as conn:
        if day:
            rows = conn.execute(
                f"SELECT {_EVIDENCE_COLUMNS} FROM listening_difficulty_evidence "
                "WHERE user_id = ? AND substr(created_at, 1, 10) = ? "
                "ORDER BY id ASC",
                (user_id, day),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_EVIDENCE_COLUMNS} FROM listening_difficulty_evidence "
                "WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


# Subagente F6.2 — Progreso histórico real (tendencias, racha, dominio, hitos)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Añadir un **único endpoint nuevo** `GET /api/progress/history` que transforme el progreso de
"counts estáticos" a "evolución en el tiempo". Devuelve cuatro bloques, todos **deterministas y
sin LLM** (premisa 12):

1. **series** — actividad agregada por `day|week|month` (mensajes, ejercicios, correcciones,
   pronunciaciones).
2. **streak** — racha actual, mejor racha y último día activo.
3. **mastery** — errores gramaticales **activos** (recurrentes recientemente) vs **resueltos**.
4. **milestones** — catálogo de hitos con su estado `achieved`.

No se rompen `/api/progress` ni `/api/profile` (se mantienen intactos).

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/repositories/db.py`: `_conn()`, `_now()` (ISO UTC con microsegundos y `+00:00`),
  `init_db()`. Las tablas relevantes ya existen: `messages` (con `mode` y `created_at`, FK a
  `conversations`), `pronunciation_attempts` (`created_at`, FK a `users`), `grammar_errors`
  (`rule, message, count, last_example, last_seen`), `vocabulary`.
- `backend/repositories/grammar.py`: `get_recurring_errors(user_id) -> list[dict]` ya existe y
  devuelve `[{rule, message, count, last_example, last_seen}]` ordenado por count desc.
- `backend/repositories/pronunciation.py`: `get_progress(user_id) -> dict` ya existe y devuelve
  `{user_id, conversations, messages, exercises, corrections, pronunciation:{attempts,...}}`.
- `backend/repositories/vocabulary.py`: `get_vocabulary(user_id) -> list[dict]` ya existe.
- `backend/routers/progress.py` (LEERLO): usa `Depends(current_user)` (dependencia que resuelve
  `user_id` por query param y devuelve 404 si no existe). `backend/dependencies.py` define
  `current_user`.
- `backend/schemas/profile.py` importa `GrammarRecurringError` desde `schemas.grammar` (patrón a
  imitar para el mastery). `schemas/grammar.py` define `GrammarRecurringError` con campos
  `rule, message, count, last_example, last_seen`.
- Tests: patrón `monkeypatch.setattr(db, "DATA_DIR", tmp_path)` +
  `monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")` + `db.init_db()`. `TestClient(app)`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/schemas/progress.py` — ampliar
Mantén lo existente (`PronunciationStats`, `ProgressSummary`) y añade al final:

```python
from typing import Literal

from schemas.grammar import GrammarRecurringError

Bucket = Literal["day", "week", "month"]


class SeriesPoint(BaseModel):
    bucket: str
    messages: int
    exercises: int
    corrections: int
    pronunciation: int


class Streak(BaseModel):
    current_days: int
    best_days: int
    last_active_date: str | None = None


class ErrorMastery(BaseModel):
    active: list[GrammarRecurringError]
    resolved: list[GrammarRecurringError]


class Milestone(BaseModel):
    id: str
    label: str
    achieved: bool


class ProgressHistory(BaseModel):
    user_id: str
    bucket: Bucket
    series: list[SeriesPoint]
    streak: Streak
    mastery: ErrorMastery
    milestones: list[Milestone]
```

> Ajusta los imports al estilo isort/ruff (el `from typing import Literal` y
> `from schemas.grammar import ...` van al principio, en sus bloques correctos).

### 2. `backend/services/trends.py` (nuevo, puro)
```python
"""Agregación temporal de la actividad del alumno (puro, determinista)."""
from __future__ import annotations

from datetime import datetime

_KEYS = ("messages", "exercises", "corrections", "pronunciation")


def _day(iso_ts: str) -> str:
    # _now() genera ISO UTC; los 10 primeros caracteres son YYYY-MM-DD.
    return iso_ts[:10]


def active_days(events: list[dict]) -> list[str]:
    """Días con actividad (YYYY-MM-DD), sin duplicados, orden asc."""
    return sorted({_day(e["created_at"]) for e in events})


def daily_activity(events: list[dict]) -> list[dict]:
    """Agrega eventos en una fila por día. Un evento es {created_at, kind, mode}
    con kind en {"message","pronunciation"}."""
    agg: dict[str, dict] = {}
    for e in events:
        day = _day(e["created_at"])
        row = agg.setdefault(
            day,
            {
                "day": day,
                "messages": 0,
                "exercises": 0,
                "corrections": 0,
                "pronunciation": 0,
            },
        )
        if e["kind"] == "pronunciation":
            row["pronunciation"] += 1
        else:
            row["messages"] += 1
            if e.get("mode") == "exercises":
                row["exercises"] += 1
            elif e.get("mode") == "grammar":
                row["corrections"] += 1
    return [agg[d] for d in sorted(agg)]


def _week_key(day: str) -> str:
    iso = datetime.fromisoformat(day).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _month_key(day: str) -> str:
    return day[:7]


def aggregate_series(daily: list[dict], bucket: str) -> list[dict]:
    """Reagrupa filas diarias en buckets day|week|month (orden ascendente)."""
    if bucket == "day":
        return [{"bucket": r["day"], **{k: r[k] for k in _KEYS}} for r in daily]
    key_fn = _week_key if bucket == "week" else _month_key
    agg: dict[str, dict] = {}
    order: list[str] = []
    for r in daily:
        key = key_fn(r["day"])
        if key not in agg:
            agg[key] = {"bucket": key, "messages": 0, "exercises": 0,
                        "corrections": 0, "pronunciation": 0}
            order.append(key)
        for k in _KEYS:
            agg[key][k] += r[k]
    return [agg[k] for k in order]


def compute_streak(active_days: list[str]) -> dict:
    """Racha: días consecutivos con actividad. current = racha que termina en el
    último día activo; best = racha más larga del histórico."""
    days = sorted(set(active_days))
    if not days:
        return {"current_days": 0, "best_days": 0, "last_active_date": None}

    def consecutive(a: str, b: str) -> bool:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days == 1

    best = 1
    run = 1
    for i in range(1, len(days)):
        if consecutive(days[i - 1], days[i]):
            run += 1
        else:
            run = 1
        best = max(best, run)

    current = 1
    i = len(days) - 1
    while i > 0 and consecutive(days[i - 1], days[i]):
        current += 1
        i -= 1

    return {"current_days": current, "best_days": best, "last_active_date": days[-1]}
```

### 3. `backend/services/mastery.py` (nuevo, puro)
```python
"""Dominio de errores recurrentes e hitos (puro, determinista)."""
from __future__ import annotations

from datetime import datetime

RESOLVED_AFTER_DAYS = 14

_MILESTONES = [
    ("first_conversation", "Primera conversación"),
    ("first_message", "Primer mensaje"),
    ("message_10", "10 mensajes"),
    ("message_50", "50 mensajes"),
    ("pronunciation_1", "Primera pronunciación"),
    ("pronunciation_10", "10 pronunciaciones"),
    ("vocab_50", "50 palabras de vocabulario"),
    ("vocab_200", "200 palabras de vocabulario"),
    ("streak_3", "Racha de 3 días"),
    ("streak_7", "Racha de 7 días"),
]


def classify_errors(
    errors: list[dict], now_iso: str, resolved_after_days: int = RESOLVED_AFTER_DAYS
) -> dict:
    """Separa errores recurrentes en activos (last_seen reciente) y resueltos
    (sin recurrencia reciente). Heurística v1, determinista."""
    now = datetime.fromisoformat(now_iso)
    active: list[dict] = []
    resolved: list[dict] = []
    for e in errors:
        try:
            last = datetime.fromisoformat(e["last_seen"])
        except (KeyError, ValueError):
            active.append(e)
            continue
        if (now - last).days <= resolved_after_days:
            active.append(e)
        else:
            resolved.append(e)
    return {"active": active, "resolved": resolved}


def compute_milestones(signals: dict) -> list[dict]:
    """Devuelve el catálogo completo de hitos con su estado achieved según
    señales: messages, conversations, pronunciation, vocab_size, streak_best."""
    checks = {
        "first_conversation": signals.get("conversations", 0) >= 1,
        "first_message": signals.get("messages", 0) >= 1,
        "message_10": signals.get("messages", 0) >= 10,
        "message_50": signals.get("messages", 0) >= 50,
        "pronunciation_1": signals.get("pronunciation", 0) >= 1,
        "pronunciation_10": signals.get("pronunciation", 0) >= 10,
        "vocab_50": signals.get("vocab_size", 0) >= 50,
        "vocab_200": signals.get("vocab_size", 0) >= 200,
        "streak_3": signals.get("streak_best", 0) >= 3,
        "streak_7": signals.get("streak_best", 0) >= 7,
    }
    return [
        {"id": mid, "label": label, "achieved": checks[mid]}
        for mid, label in _MILESTONES
    ]
```

### 4. `backend/repositories/progress.py` (nuevo)
```python
"""Repositorio de progreso histórico (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn


def activity_events(user_id: str) -> list[dict]:
    """Devuelve los eventos de actividad crudos del usuario (mensajes con su modo
    y pronunciaciones), con su timestamp ISO."""
    with closing(_conn()) as conn:
        msgs = conn.execute(
            "SELECT m.created_at, m.mode FROM messages m "
            "JOIN conversations c ON m.conversation_id = c.id "
            "WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()
        pron = conn.execute(
            "SELECT created_at FROM pronunciation_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    events = [
        {"created_at": r["created_at"], "kind": "message", "mode": r["mode"]}
        for r in msgs
    ]
    events += [
        {"created_at": r["created_at"], "kind": "pronunciation", "mode": None}
        for r in pron
    ]
    return events
```

### 5. `backend/domain/progress.py` (nuevo)
```python
"""Servicio de dominio del progreso histórico."""
from __future__ import annotations

from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from repositories import pronunciation as pronunciation_repo
from repositories import progress as progress_repo
from repositories import vocabulary as vocabulary_repo
from services.mastery import classify_errors, compute_milestones
from services.trends import active_days, aggregate_series, compute_streak, daily_activity


async def get_progress_history(user_id: str, bucket: str) -> dict:
    events = await run_in_threadpool(progress_repo.activity_events, user_id)
    daily = daily_activity(events)
    series = aggregate_series(daily, bucket)
    streak = compute_streak(active_days(events))

    errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    mastery = classify_errors(errors, now_iso)

    progress = await run_in_threadpool(pronunciation_repo.get_progress, user_id)
    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    milestones = compute_milestones(
        {
            "messages": progress["messages"],
            "conversations": progress["conversations"],
            "pronunciation": progress["pronunciation"]["attempts"],
            "vocab_size": len(vocab),
            "streak_best": streak["best_days"],
        }
    )

    return {
        "user_id": user_id,
        "bucket": bucket,
        "series": series,
        "streak": streak,
        "mastery": mastery,
        "milestones": milestones,
    }
```

### 6. `backend/routers/progress.py` — añadir endpoint
Añade el import `Query` y `from domain import progress as progress_service`, y los schemas
`Bucket`, `ProgressHistory`. Añade al final del archivo:

```python
@router.get("/api/progress/history", response_model=ProgressHistory)
async def progress_history(
    user: dict = Depends(current_user),
    bucket: Bucket = Query("week"),
) -> dict:
    return await progress_service.get_progress_history(user["id"], bucket)
```

> NO toques el endpoint `/api/progress` existente.

### 7. Tests nuevos (3 archivos)

**`backend/tests/test_trends.py`** (servicios puros de `services/trends.py`). Usa timestamps
ISO de ejemplo como `"2026-08-10T10:00:00+00:00"`. Cubre al menos:
- `test_daily_activity_counts_modes`: eventos con `mode` `exercises`/`grammar`/`conversation` y
  pronunciación → contadores correctos por día.
- `test_aggregate_series_day`: bucket `day` devuelve las mismas filas con clave `bucket=day`.
- `test_aggregate_series_week`: días de la misma semana ISO se agrupan y suman.
- `test_aggregate_series_month`: días de meses distintos se separan; mismos meses se suman.
- `test_compute_streak_empty`: lista vacía → `current_days=0, best_days=0, last_active_date=None`.
- `test_compute_streak_best_and_current`: varios días consecutivos → best y current correctos.
- `test_compute_streak_gap_resets_run`: un hueco rompe la racha.

**`backend/tests/test_mastery.py`** (servicios puros de `services/mastery.py`):
- `test_classify_errors_active_vs_resolved`: `last_seen` reciente → active; antiguo → resolved.
- `test_classify_errors_empty`: lista vacía → `{"active": [], "resolved": []}`.
- `test_compute_milestones_flags`: señales por debajo/encima de umbrales → `achieved` correcto.

**`backend/tests/test_progress_history.py`** (repo + domain + endpoint). `_setup` crea la DB
temporal y un usuario; usa `conversations_repo`/`pronunciation_repo`/`grammar_repo` para sembrar
datos y `TestClient(app)`. Cubre al menos:
- `test_activity_events_isolated_per_user`: la actividad de A no aparece para B.
- `test_get_progress_history_shape`: domain devuelve `user_id`, `bucket`, `series`, `streak`,
  `mastery` (con `active`/`resolved`) y `milestones`.
- `test_progress_history_endpoint_200`: `GET /api/progress/history?user_id=<uid>&bucket=week`
  → 200 con forma correcta.
- `test_progress_history_endpoint_404`: `user_id` inexistente → 404.
- `test_progress_history_invalid_bucket_422`: `bucket=year` → 422.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 151 tests** (136 previos + 15 nuevos).
- `python -m ruff check .` **sin errores**.
- Los 136 tests existentes siguen verdes. No se modifica ningún test ni módulo existente salvo
  `schemas/progress.py` y `routers/progress.py` (solo añadiendo).

## Restricciones
- NO tocar el frontend.
- NO tocar `main.py` (no se registran routers nuevos), `repositories/` existentes,
  `services/` existentes, `domain/` existentes, ni `dependencies.py`.
- NO cambiar `/api/progress`, `/api/profile` ni ningún endpoint existente.
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  `run_in_threadpool`, imports ordenados (ruff/isort).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.

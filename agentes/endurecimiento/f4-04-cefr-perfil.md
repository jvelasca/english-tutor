# Subagente F4.4 — CEFR + recomendaciones (perfil agregado)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Cuarta y última pieza backend del Learning Profile: **estimar el nivel CEFR** del alumno con una
heurística determinista a partir de las señales ya persistidas (vocabulario, pronunciación,
ejercicios), guardar ese nivel en una tabla `learning_profile`, y generar **recomendaciones**
personalizadas. Expone todo en un único `GET /api/profile`. Sin LLM, sin red (premisa 12).

> **Desviación respecto al plan aprobado:** el plan mencionaba `GET /api/profile` +
> `POST /api/profile/assess`. Se simplifica a un único `GET /api/profile` que recalcula la
> estimación en cada consulta (es barata y determinista) y persiste el nivel como caché. Evita
> duplicar lógica en dos endpoints.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- Piezas ya existentes de Fase 4 (LEERLAS para reutilizar):
  - `backend/repositories/vocabulary.py`: `get_vocabulary(user_id) -> list[dict]` (con `word`,
    `occurrences`, … ordenado por apariciones desc).
  - `backend/repositories/grammar.py`: `get_recurring_errors(user_id) -> list[dict]` (con `rule`,
    `message`, `count`, `last_example`, `last_seen`).
  - `backend/repositories/pronunciation.py`: `get_progress(user_id) -> dict` (con
    `pronunciation.average` y `exercises`).
  - `backend/repositories/users.py`: `get_user(uid) -> dict | None`.
- `backend/repositories/db.py` (LEERLO): `_conn()`, `_now()`, `init_db()`. Tablas existentes:
  `conversations`, `messages`, `users`, `pronunciation_attempts`, `learning_events`, `vocabulary`,
  `grammar_errors` (todas las de F4 con FK inline).
- `backend/domain/*.py`: servicios async que delegan en repos con `run_in_threadpool`.
- `backend/routers/learning.py` etc.: usan `Depends(current_user)`.
- `backend/schemas/grammar.py`: exporta `GrammarRecurringError`.
- `backend/main.py`: registra routers.
- Tests: `monkeypatch.setattr(db, "DATA_DIR", tmp_path)` y `db.DB_PATH` antes de `db.init_db()`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/cefr.py` (nuevo) — funciones puras
```python
"""Estimación heurística de nivel CEFR y recomendaciones (puro, determinista)."""
from __future__ import annotations

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def estimate_cefr(signals: dict) -> str:
    """Estima el nivel CEFR a partir de señales: vocab_size, pronunciation_avg
    (float|None) y exercises. Heurística v1 (la evaluación CEFR real es la Fase 8)."""
    vocab = signals.get("vocab_size", 0)
    pron = signals.get("pronunciation_avg")
    exercises = signals.get("exercises", 0)

    points = 0
    if vocab >= 900:
        points += 4
    elif vocab >= 400:
        points += 3
    elif vocab >= 150:
        points += 2
    elif vocab >= 50:
        points += 1

    if pron is not None:
        if pron >= 85:
            points += 3
        elif pron >= 70:
            points += 2
        elif pron >= 50:
            points += 1

    if exercises >= 50:
        points += 3
    elif exercises >= 20:
        points += 2
    elif exercises >= 5:
        points += 1

    if points >= 9:
        return "C2"
    if points >= 7:
        return "C1"
    if points >= 5:
        return "B2"
    if points >= 3:
        return "B1"
    if points >= 1:
        return "A2"
    return "A1"


def recommendations(profile: dict) -> list[str]:
    """Genera recomendaciones en español a partir del perfil agregado."""
    recs: list[str] = []
    errors = profile.get("recurring_errors", [])
    if errors:
        recs.append(f"Refuerza: {errors[0]['message']} (error recurrente).")
    pron = profile.get("pronunciation_avg")
    if pron is not None and pron < 70:
        recs.append("Practica pronunciación con la tarjeta de pronunciación.")
    if profile.get("vocab_size", 0) < 50:
        recs.append("Amplía vocabulario: lee y describe imágenes o rutinas.")
    if not recs:
        recs.append("¡Buen trabajo! Sigue practicando conversación.")
    return recs
```

### 2. `backend/repositories/db.py` — tabla
Tras `CREATE TABLE IF NOT EXISTS grammar_errors`, añade:
```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_profile (
                user_id TEXT PRIMARY KEY,
                cefr_level TEXT NOT NULL DEFAULT 'A1',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
```
> No hace falta índice (la PK ya indexa por user_id).

### 3. `backend/repositories/profile.py` (nuevo)
```python
"""Repositorio del perfil de aprendizaje (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def get_profile(user_id: str) -> dict | None:
    """Devuelve el perfil almacenado o None si no existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, cefr_level, updated_at FROM learning_profile "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_cefr(user_id: str, level: str) -> dict | None:
    """Persiste (upsert) el nivel CEFR del usuario. Devuelve None si el usuario
    no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile (user_id, cefr_level, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "cefr_level = excluded.cefr_level, updated_at = excluded.updated_at",
            (user_id, level, now),
        )
    return {"user_id": user_id, "cefr_level": level, "updated_at": now}
```

### 4. `backend/schemas/profile.py` (nuevo)
```python
"""Esquemas Pydantic del perfil de aprendizaje."""
from __future__ import annotations

from pydantic import BaseModel

from schemas.grammar import GrammarRecurringError


class LearningProfile(BaseModel):
    user_id: str
    cefr_level: str
    vocabulary_size: int
    top_words: list[str]
    recurring_errors: list[GrammarRecurringError]
    pronunciation_average: float | None
    recommendations: list[str]
```

### 5. `backend/domain/profile.py` (nuevo)
```python
"""Servicio de dominio del perfil de aprendizaje."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from repositories import pronunciation as pronunciation_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import estimate_cefr, recommendations


async def get_profile_summary(user_id: str) -> dict | None:
    """Compone el perfil del alumno: vocabulario, errores, pronunciación, CEFR
    estimado y recomendaciones. Devuelve None si el usuario no existe."""
    if await run_in_threadpool(users_repo.get_user, user_id) is None:
        return None

    vocab = await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
    errors = await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
    progress = await run_in_threadpool(pronunciation_repo.get_progress, user_id)

    pron_avg = progress["pronunciation"]["average"]
    level = estimate_cefr(
        {
            "vocab_size": len(vocab),
            "pronunciation_avg": pron_avg,
            "exercises": progress["exercises"],
        }
    )
    await run_in_threadpool(profile_repo.set_cefr, user_id, level)

    recs = recommendations(
        {
            "recurring_errors": errors,
            "pronunciation_avg": pron_avg,
            "vocab_size": len(vocab),
        }
    )
    return {
        "user_id": user_id,
        "cefr_level": level,
        "vocabulary_size": len(vocab),
        "top_words": [v["word"] for v in vocab[:5]],
        "recurring_errors": errors,
        "pronunciation_average": pron_avg,
        "recommendations": recs,
    }
```

### 6. `backend/routers/profile.py` (nuevo)
```python
"""Endpoint del perfil de aprendizaje."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import profile as profile_service
from schemas.profile import LearningProfile

router = APIRouter()


@router.get("/api/profile", response_model=LearningProfile)
async def get_profile(user: dict = Depends(current_user)) -> dict:
    return await profile_service.get_profile_summary(user["id"])
```

### 7. `backend/main.py`
Añade `from routers.profile import router as profile_router` y `app.include_router(profile_router)`.

### 8. Test nuevo `backend/tests/test_profile.py`
Cubre: FK presente; `estimate_cefr` (bajo → A1, medio → B2, alto → C2); `recommendations`
(por error recurrente, por pronunciación baja, por vocabulario bajo, por defecto);
`set_cefr` roundtrip + usuario inexistente; endpoint 200 con forma completa; endpoint 404.

```python
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import estimate_cefr, recommendations
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}
```
Añade al menos:
- `test_learning_profile_table_has_user_fk`
- `test_estimate_cefr_low_is_a1`
- `test_estimate_cefr_medium_is_b2`
- `test_estimate_cefr_high_is_c2`
- `test_recommendations_grammar_error`
- `test_recommendations_pronunciation`
- `test_recommendations_vocabulary`
- `test_recommendations_default`
- `test_set_cefr_roundtrip`
- `test_set_cefr_unknown_user_none`
- `test_profile_endpoint_shape`
- `test_profile_endpoint_404`

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 114 tests** (102 previos + 12 nuevos).
- `python -m ruff check .` **sin errores**.

## Restricciones
- NO tocar el frontend.
- NO tocar `schemas/` existentes, `services/` existentes, ni `domain/`/`repositories/`
  existentes salvo `db.py` y `main.py`.
- NO cambiar tablas/migraciones existentes.
- Estilo: docstrings en español, `from __future__ import annotations`, `run_in_threadpool`,
  isort/ruff limpios.

## Salida
Lista de archivos creados/modificados, salida de `python -m pytest tests/ -q`, de
`python -m ruff check .`, y cualquier desviación.

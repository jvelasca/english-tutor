# Subagente F4.3 — Errores gramaticales recurrentes (detección + persistencia + lectura)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Tercera pieza del Learning Profile: **errores gramaticales recurrentes**. Detectar errores
comunes en el texto del alumno con un **conjunto fijo de reglas deterministas** (regex), persistir
su recuento por regla, y exponer los errores recurrentes por usuario. Sin LLM, sin red (premisa
12). Es una heurística v1; la corrección gramatical fina es de la Fase 5/8.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/repositories/db.py` (LEERLO): `_conn()`, `_now()`, `init_db()`. Tablas existentes:
  `conversations`, `messages`, `users`, `pronunciation_attempts`, `learning_events` (F4.1),
  `vocabulary` (F4.2) — las dos últimas con FK inline y `UNIQUE`/índice por usuario.
- `backend/repositories/pronunciation.py`: patrón `record_pronunciation` (valida usuario con
  `get_user`).
- `backend/services/vocabulary.py` (F4.2): patrón de **función pura determinista**.
- `backend/domain/*.py`: servicios async que delegan en repos con `run_in_threadpool`.
- `backend/routers/learning.py` y `routers/vocabulary.py` (F4.1/F4.2): usan `Depends(current_user)`.
- `backend/config.py`: `MAX_CONTENT_CHARS = 8000`.
- `backend/main.py`: registra routers.
- Tests: `monkeypatch.setattr(db, "DATA_DIR", tmp_path)` y `db.DB_PATH` antes de `db.init_db()`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/grammar.py` (nuevo) — reglas puras deterministas
Define una lista `RULES` de reglas `{rule, message, pattern}` y la función `find_errors`.

```python
"""Detección de errores gramaticales comunes (puro, determinista, heurística v1)."""
from __future__ import annotations

import re

RULES: list[dict] = [
    {
        "rule": "he_she_it_s",
        "message": "Falta la -s en la 3ª persona singular (he/she/it).",
        "pattern": re.compile(
            r"\b(he|she|it)\s+(go|do|have|like|want|need|know|work|play|say|"
            r"think|make|come|look|use|take|run|walk|eat|drink)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "a_an",
        "message": "Usa 'an' antes de sonido vocálico.",
        "pattern": re.compile(
            r"\ba\s+(?!(?:uni|use|one|eu))([aeiou][a-z]+)\b", re.IGNORECASE
        ),
    },
    {
        "rule": "double_negative",
        "message": "Doble negación: usa una sola negación.",
        "pattern": re.compile(
            r"\b(?:don'?t|do\s+not|can'?t|cannot|doesn'?t|does\s+not|won'?t|"
            r"isn'?t|aren'?t|ain'?t)\b[^.!?]*?\b(no|nothing|nobody|none|nowhere)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "there_their_theyre",
        "message": "Confusión entre there, their y they're.",
        "pattern": re.compile(
            r"\btheir\s+(?:going|coming|are|is|was|were|nice|good|happy|here|"
            r"right|wrong)\b|\bthere\s+(?:car|house|friend|book|name|job|"
            r"family|dog|cat|mother|father)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "your_youre",
        "message": "Confusión entre your y you're.",
        "pattern": re.compile(
            r"\byour\s+(?:going|welcome|nice|right|wrong|doing|awesome|amazing|"
            r"great|kind|correct)\b|\byoure\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "capitalization_i",
        "message": "El pronombre 'I' va en mayúscula.",
        "pattern": re.compile(r"\bi\b"),
    },
    {
        "rule": "to_too",
        "message": "Usa 'too' para 'demasiado/también'.",
        "pattern": re.compile(
            r"\bto\s+(?:much|many|late|early|far|big|small|easy|hard|slow|fast)\b",
            re.IGNORECASE,
        ),
    },
]


def find_errors(text: str) -> list[dict]:
    """Devuelve los errores detectados, como máximo uno por regla. Cada dict:
    `{"rule", "message", "example"}` (example = fragmento coincidente)."""
    findings: list[dict] = []
    seen: set[str] = set()
    for rule in RULES:
        m = rule["pattern"].search(text)
        if m and rule["rule"] not in seen:
            seen.add(rule["rule"])
            findings.append(
                {
                    "rule": rule["rule"],
                    "message": rule["message"],
                    "example": m.group(0).strip(),
                }
            )
    return findings
```

### 2. `backend/repositories/db.py` — tabla + índice
Tras `CREATE TABLE IF NOT EXISTS vocabulary`, añade:
```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS grammar_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                rule TEXT NOT NULL,
                message TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                last_example TEXT NOT NULL DEFAULT '',
                last_seen TEXT NOT NULL,
                UNIQUE (user_id, rule),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
```
Y un índice (junto a los demás):
```python
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_grammar_errors_user_id "
            "ON grammar_errors(user_id)"
        )
```

### 3. `backend/repositories/grammar.py` (nuevo)
```python
"""Repositorio de errores gramaticales recurrentes (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_errors(user_id: str, errors: list[dict]) -> bool:
    """Incrementa el recuento de cada error detectado (upsert por regla).
    Devuelve False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not errors:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO grammar_errors "
            "(user_id, rule, message, count, last_example, last_seen) "
            "VALUES (?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(user_id, rule) DO UPDATE SET "
            "count = count + 1, last_example = excluded.last_example, "
            "last_seen = excluded.last_seen",
            [
                (user_id, e["rule"], e["message"], e.get("example", ""), now)
                for e in errors
            ],
        )
    return True


def get_recurring_errors(user_id: str) -> list[dict]:
    """Devuelve los errores recurrentes del usuario ordenados por recuento (desc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT rule, message, count, last_example, last_seen "
            "FROM grammar_errors WHERE user_id = ? ORDER BY count DESC, rule ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

### 4. `backend/schemas/grammar.py` (nuevo)
```python
"""Esquemas Pydantic de errores gramaticales."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS


class GrammarAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class GrammarFinding(BaseModel):
    rule: str
    message: str
    example: str


class GrammarAnalyzeResponse(BaseModel):
    errors: list[GrammarFinding]


class GrammarRecurringError(BaseModel):
    rule: str
    message: str
    count: int
    last_example: str
    last_seen: str
```

### 5. `backend/domain/grammar.py` (nuevo)
```python
"""Servicio de dominio de errores gramaticales."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import grammar as grammar_repo
from services.grammar import find_errors


async def analyze_text(user_id: str, text: str) -> list[dict]:
    errors = find_errors(text)
    await run_in_threadpool(grammar_repo.record_errors, user_id, errors)
    return errors


async def get_recurring_errors(user_id: str) -> list[dict]:
    return await run_in_threadpool(grammar_repo.get_recurring_errors, user_id)
```

### 6. `backend/routers/grammar.py` (nuevo)
```python
"""Endpoints de errores gramaticales."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import grammar as grammar_service
from schemas.grammar import (
    GrammarAnalyzeRequest,
    GrammarAnalyzeResponse,
    GrammarRecurringError,
)

router = APIRouter()


@router.post("/api/grammar/analyze", response_model=GrammarAnalyzeResponse)
async def analyze(
    body: GrammarAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    errors = await grammar_service.analyze_text(user["id"], body.text)
    return {"errors": errors}


@router.get("/api/grammar/errors", response_model=list[GrammarRecurringError])
async def get_errors(user: dict = Depends(current_user)) -> list[dict]:
    return await grammar_service.get_recurring_errors(user["id"])
```

### 7. `backend/main.py`
Añade `from routers.grammar import router as grammar_router` y `app.include_router(grammar_router)`.

### 8. Test nuevo `backend/tests/test_grammar.py`
Cubre: FK presente; cada regla detecta su caso (y un negativo); `record_errors` incrementa
`count`; usuario inexistente → `False`; aislamiento; orden por recuento; endpoints con forma
correcta; endpoint 404.

```python
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import users as users_repo
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
- `test_grammar_errors_table_has_user_fk`
- `test_find_errors_third_person_s` ("He go to school" → `he_she_it_s`; "He goes" → sin error)
- `test_find_errors_a_an` ("a apple" → `a_an`; "an apple" → sin error)
- `test_find_errors_double_negative` ("I don't have no money" → `double_negative`)
- `test_find_errors_there_their` ("their going home" → `there_their_theyre`)
- `test_find_errors_your_youre` ("your nice" → `your_youre`)
- `test_find_errors_capitalization_i` ("i like it" → `capitalization_i`; "I like it" → sin error)
- `test_record_errors_increments_count`
- `test_record_errors_unknown_user_false`
- `test_grammar_isolation`
- `test_get_recurring_errors_ordered`
- `test_grammar_endpoint_shape`
- `test_grammar_endpoint_404`

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 102 tests** (89 previos + 13 nuevos).
- `python -m ruff check .` **sin errores**.

## Restricciones
- NO tocar el frontend.
- NO tocar `schemas/` existentes, `services/vocabulary.py`, `services/pronunciation.py`,
  `services/llm.py`, ni `domain/`/`repositories/` existentes salvo `db.py`.
- NO cambiar tablas/migraciones existentes.
- Estilo: docstrings en español, `from __future__ import annotations`, `run_in_threadpool`,
  isort/ruff limpios.

## Salida
Lista de archivos creados/modificados, salida de `python -m pytest tests/ -q`, de
`python -m ruff check .`, y cualquier desviación.

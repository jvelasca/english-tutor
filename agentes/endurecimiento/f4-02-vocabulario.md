# Subagente F4.2 — Vocabulario (extracción + persistencia + lectura)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Segunda pieza del Learning Profile: **vocabulario del alumno**. Extraer palabras del texto que
escribe el alumno (función pura y determinista), persistirlas con recuento de apariciones, y
exponer el vocabulario acumulado por usuario. Sin LLM, sin red (premisa 12: tests rápidos y
deterministas).

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/repositories/db.py` (LEERLO): `_conn()`, `_now()`, `init_db()`. En `init_db()` las
  tablas se crean en el primer bloque `with closing(_conn()) as conn, conn:` y los índices van
  justo después de los `CREATE INDEX IF NOT EXISTS` existentes. Ya existen: `conversations`,
  `messages`, `users`, `pronunciation_attempts`, y (F4.1) `learning_events` con FK inline.
- `backend/repositories/pronunciation.py`: patrón `record_pronunciation` (valida usuario con
  `get_user`, devuelve `bool`).
- `backend/services/pronunciation.py`: patrón de **función pura** (`score_pronunciation`) sin
  imports de FastAPI ni SQLite.
- `backend/domain/*.py`: servicios async que delegan en repos con `run_in_threadpool`.
- `backend/routers/progress.py` y `routers/learning.py`: usan `Depends(current_user)`.
- `backend/config.py`: `MAX_CONTENT_CHARS = 8000`.
- `backend/main.py`: registra routers con `app.include_router(...)`.
- Tests: `monkeypatch.setattr(db, "DATA_DIR", tmp_path)` y `db.DB_PATH` antes de `db.init_db()`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/vocabulary.py` (nuevo) — función pura
```python
"""Extracción de vocabulario del texto del alumno (puro, determinista)."""
from __future__ import annotations

import re

# Palabras funcionales inglesas que no aportan valor como "vocabulario".
EN_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "so", "for", "nor", "yet",
        "of", "in", "on", "at", "to", "by", "with", "from", "into", "over",
        "under", "about", "between", "through", "during", "without",
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "can",
        "could", "shall", "should", "may", "might", "must",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their", "mine",
        "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
        "what", "which", "who", "whom", "whose", "when", "where", "why",
        "how", "not", "no", "yes", "if", "then", "than", "as", "there",
        "here", "just", "very", "too", "also", "only",
    }
)


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


def extract_words(text: str) -> list[str]:
    """Devuelve las palabras únicas (normalizadas, sin stopwords ni tokens de 1
    carácter) ordenadas alfabéticamente."""
    tokens = _normalize(text).split()
    words = {t for t in tokens if len(t) > 1 and t not in EN_STOPWORDS}
    return sorted(words)
```

### 2. `backend/repositories/db.py` — tabla + índice
Tras `CREATE TABLE IF NOT EXISTS learning_events` (o después de `pronunciation_attempts`),
añade:
```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                word TEXT NOT NULL,
                occurrences INTEGER NOT NULL DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE (user_id, word),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
```
Y un índice por usuario (junto a los demás índices):
```python
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id)"
        )
```
> No toques tablas ni migraciones existentes.

### 3. `backend/repositories/vocabulary.py` (nuevo)
```python
"""Repositorio de vocabulario (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_words(user_id: str, words: list[str]) -> bool:
    """Incrementa el recuento de cada palabra para el usuario (upsert). Devuelve
    False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    if not words:
        return True
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO vocabulary "
            "(user_id, word, occurrences, first_seen, last_seen) "
            "VALUES (?, ?, 1, ?, ?) "
            "ON CONFLICT(user_id, word) DO UPDATE SET "
            "occurrences = occurrences + 1, last_seen = excluded.last_seen",
            [(user_id, w, now, now) for w in words],
        )
    return True


def get_vocabulary(user_id: str) -> list[dict]:
    """Devuelve el vocabulario del usuario ordenado por apariciones (desc) y
    palabra (asc)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT word, occurrences, first_seen, last_seen FROM vocabulary "
            "WHERE user_id = ? ORDER BY occurrences DESC, word ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

### 4. `backend/schemas/vocabulary.py` (nuevo)
```python
"""Esquemas Pydantic de vocabulario."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS


class VocabularyAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class VocabularyAnalyzeResponse(BaseModel):
    words: list[str]


class VocabularyItem(BaseModel):
    word: str
    occurrences: int
    first_seen: str
    last_seen: str
```

### 5. `backend/domain/vocabulary.py` (nuevo)
```python
"""Servicio de dominio de vocabulario."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary as vocabulary_repo
from services.vocabulary import extract_words


async def analyze_text(user_id: str, text: str) -> list[str]:
    words = extract_words(text)
    await run_in_threadpool(vocabulary_repo.record_words, user_id, words)
    return words


async def get_vocabulary(user_id: str) -> list[dict]:
    return await run_in_threadpool(vocabulary_repo.get_vocabulary, user_id)
```

### 6. `backend/routers/vocabulary.py` (nuevo)
```python
"""Endpoints de vocabulario."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import current_user
from domain import vocabulary as vocabulary_service
from schemas.vocabulary import (
    VocabularyAnalyzeRequest,
    VocabularyAnalyzeResponse,
    VocabularyItem,
)

router = APIRouter()


@router.post("/api/vocabulary/analyze", response_model=VocabularyAnalyzeResponse)
async def analyze(
    body: VocabularyAnalyzeRequest, user: dict = Depends(current_user)
) -> dict:
    words = await vocabulary_service.analyze_text(user["id"], body.text)
    return {"words": words}


@router.get("/api/vocabulary", response_model=list[VocabularyItem])
async def get_vocabulary(user: dict = Depends(current_user)) -> list[dict]:
    return await vocabulary_service.get_vocabulary(user["id"])
```

### 7. `backend/main.py`
Añade `from routers.vocabulary import router as vocabulary_router` y
`app.include_router(vocabulary_router)`.

### 8. Test nuevo `backend/tests/test_vocabulary.py`
Cubre: `extract_words` (puntuación/mayúsculas/stopwords, dedup, tokens de 1 carácter);
`record_words` incrementa `occurrences`; usuario inexistente → `False`; aislamiento; orden por
apariciones; endpoint POST+GET con forma correcta; endpoint 404.

```python
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import vocabulary as vocabulary_repo
from repositories import users as users_repo
from services.vocabulary import extract_words


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
- `test_vocabulary_table_has_user_fk`
- `test_extract_words_filters_and_sorts`
- `test_extract_words_deduplicates`
- `test_extract_words_removes_short_tokens`
- `test_record_words_increments_occurrences`
- `test_record_words_unknown_user_false`
- `test_vocabulary_isolation`
- `test_get_vocabulary_ordered_by_occurrences`
- `test_vocabulary_endpoint_shape`
- `test_vocabulary_endpoint_404`

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 89 tests** (79 previos + 10 nuevos).
- `python -m ruff check .` **sin errores**.

## Restricciones
- NO tocar el frontend.
- NO tocar `schemas/` existentes, `services/pronunciation.py`, `services/llm.py`,
  `services/stt.py`, `services/tts.py`, ni `domain/`/`repositories/` existentes salvo `db.py`.
- NO cambiar tablas/migraciones existentes.
- Estilo: docstrings en español, `from __future__ import annotations`, `run_in_threadpool`,
  isort/ruff limpios.

## Salida
Lista de archivos creados/modificados, salida de `python -m pytest tests/ -q`, de
`python -m ruff check .`, y cualquier desviación.

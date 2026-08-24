# Subagente F8.3 — Listening: banco de preguntas + evaluación (backend)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Añadir **listening (comprensión auditiva)** como nuevo módulo completo:
- Un **banco** estático y determinista de preguntas (sin LLM, premisa 12).
- Endpoints para obtener la siguiente pregunta y para responder (evaluación determinista).
- Persistencia de intentos en SQLite y registro de eventos de aprendizaje (`exercise`).

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- Patrón a imitar: vocabulario y pronunciación. `routers/pronunciation.py` usa
  `Depends(current_user)` (query `user_id`), `run_in_threadpool`, y al final registra el
  evento: `await learning_service.record_event(user_id, "pronunciation", ...)`.
- `repositories/db.py`: `init_db()` crea tablas e índices con `CREATE TABLE IF NOT EXISTS`
  e `CREATE INDEX IF NOT EXISTS`. Hay tablas `pronunciation_attempts`, `learning_events`,
  `vocabulary`, `grammar_errors`. Los índices se crean al final del primer bloque.
- `main.py`: importa routers y hace `app.include_router(...)`.
- `services/tts.py` ya existe (`synthesize(text) -> bytes`) y `POST /api/tts` ya sintetiza;
  el frontend usará `/api/tts` para leer el `script` en voz alta (NO es parte de este
  subagente).
- Estilo: `from __future__ import annotations`, docstrings en español, imports ordenados
  (ruff/isort). Línea ≤ 88 chars (ruff E501).

## Tarea detallada

### 1. `backend/services/listening.py` (nuevo, puro)
Banco de 8 preguntas + funciones puras:

```python
"""Banco de preguntas de listening y puntuación determinista (puro)."""
from __future__ import annotations

QUESTION_BANK: list[dict] = [
    {
        "id": "l1",
        "level": "A1",
        "script": "Tom gets up at seven o'clock and has toast for breakfast.",
        "question": "What time does Tom get up?",
        "options": ["At six", "At seven", "At eight", "At nine"],
        "answer_index": 1,
    },
    {
        "id": "l2",
        "level": "A1",
        "script": "Maria goes to the supermarket every Saturday morning.",
        "question": "When does Maria go to the supermarket?",
        "options": ["On Sunday", "On Saturday", "On Friday", "On Monday"],
        "answer_index": 1,
    },
    {
        "id": "l3",
        "level": "A1",
        "script": "The children are playing football in the park.",
        "question": "What are the children doing?",
        "options": ["Reading", "Swimming", "Playing football", "Sleeping"],
        "answer_index": 2,
    },
    {
        "id": "l4",
        "level": "A2",
        "script": "John bought a blue shirt and a pair of black shoes.",
        "question": "What did John buy?",
        "options": [
            "A blue shirt and black shoes",
            "A red jacket",
            "A white hat",
            "A green bag",
        ],
        "answer_index": 0,
    },
    {
        "id": "l5",
        "level": "A2",
        "script": "Anna prefers to travel by train because it is cheaper than flying.",
        "question": "Why does Anna prefer the train?",
        "options": ["It is faster", "It is cheaper", "It is more comfortable", "It is safer"],
        "answer_index": 1,
    },
    {
        "id": "l6",
        "level": "A2",
        "script": "The meeting will start at half past nine and finish at noon.",
        "question": "How long does the meeting last?",
        "options": ["One hour", "Two hours and a half", "Three hours", "Half an hour"],
        "answer_index": 1,
    },
    {
        "id": "l7",
        "level": "B1",
        "script": "Despite the heavy rain, the team decided to continue the match.",
        "question": "What did the team decide?",
        "options": ["To stop", "To continue", "To postpone", "To go home"],
        "answer_index": 1,
    },
    {
        "id": "l8",
        "level": "B1",
        "script": "If you arrive early, you will have time to review your notes.",
        "question": "What happens if you arrive early?",
        "options": [
            "You miss the review",
            "You have time to review",
            "You must wait",
            "Nothing",
        ],
        "answer_index": 1,
    },
]


def get_question(question_id: str) -> dict | None:
    """Devuelve la pregunta por id o None si no existe."""
    for q in QUESTION_BANK:
        if q["id"] == question_id:
            return q
    return None


def pick_next_question(seen_ids: set[str]) -> dict:
    """Primera pregunta no vista; si todas están vistas, reinicia por la primera."""
    for q in QUESTION_BANK:
        if q["id"] not in seen_ids:
            return q
    return QUESTION_BANK[0]


def score_answer(answer_index: int, correct_index: int) -> bool:
    """True si el índice elegido coincide con el correcto."""
    return answer_index == correct_index
```

### 2. `backend/schemas/listening.py` (nuevo)

```python
"""Esquemas Pydantic de listening."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ListeningQuestion(BaseModel):
    id: str
    level: str
    script: str
    question: str
    options: list[str]


class ListeningAnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(ge=0)


class ListeningAnswerResponse(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    level: str


class ListeningStats(BaseModel):
    attempts: int
    correct: int
    accuracy: float | None = None
```

### 3. `backend/repositories/listening.py` (nuevo)

```python
"""Repositorio de listening (SQLite)."""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def record_attempt(
    user_id: str, question_id: str, answer_index: int, correct: bool
) -> bool:
    """Persiste un intento de listening para un usuario existente."""
    if get_user(user_id) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, question_id, answer_index, int(correct), _now()),
        )
    return True


def seen_question_ids(user_id: str) -> set[str]:
    """Ids de preguntas ya respondidas por el usuario."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM listening_attempts WHERE user_id = ?",
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
```

### 4. `backend/domain/listening.py` (nuevo)

```python
"""Servicio de dominio de listening (comprensión auditiva)."""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import listening as listening_repo
from services.listening import get_question, pick_next_question, score_answer


def _public(question: dict) -> dict:
    """Quita la respuesta (answer_index) antes de exponerla al cliente."""
    return {k: v for k, v in question.items() if k != "answer_index"}


async def next_question(user_id: str) -> dict:
    seen = await run_in_threadpool(listening_repo.seen_question_ids, user_id)
    return _public(pick_next_question(seen))


async def submit_answer(
    user_id: str, question_id: str, answer_index: int
) -> dict | None:
    """Evalúa y persiste la respuesta. Devuelve None si la pregunta no existe."""
    question = get_question(question_id)
    if question is None:
        return None
    correct = score_answer(answer_index, question["answer_index"])
    await run_in_threadpool(
        listening_repo.record_attempt, user_id, question_id, answer_index, correct
    )
    return {
        "question_id": question_id,
        "correct": correct,
        "correct_index": question["answer_index"],
        "level": question["level"],
    }


async def get_stats(user_id: str) -> dict:
    return await run_in_threadpool(listening_repo.get_stats, user_id)
```

### 5. `backend/routers/listening.py` (nuevo)

```python
"""Endpoints de listening (comprensión auditiva)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import learning as learning_service
from domain import listening as listening_service
from schemas.listening import (
    ListeningAnswerRequest,
    ListeningAnswerResponse,
    ListeningQuestion,
    ListeningStats,
)

router = APIRouter()


@router.get("/api/listening/question", response_model=ListeningQuestion)
async def question(user: dict = Depends(current_user)) -> dict:
    return await listening_service.next_question(user["id"])


@router.post("/api/listening/answer", response_model=ListeningAnswerResponse)
async def answer(
    body: ListeningAnswerRequest, user: dict = Depends(current_user)
) -> dict:
    result = await listening_service.submit_answer(
        user["id"], body.question_id, body.answer_index
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"listening:{body.question_id}:{'ok' if result['correct'] else 'ko'}",
    )
    return result


@router.get("/api/listening/stats", response_model=ListeningStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await listening_service.get_stats(user["id"])
```

### 6. `backend/repositories/db.py` — añadir tabla + índice (solo aditivo)
En `init_db()`, dentro del primer bloque `with closing(_conn()) as conn, conn:`, añade la
tabla después de la de `grammar_errors`:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                answer_index INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
```

Y junto a los demás índices (después de `idx_grammar_errors_user_id`), añade:

```python
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_attempts_user_id "
            "ON listening_attempts(user_id)"
        )
```

No toques nada más de `db.py`.

### 7. `backend/main.py` — registrar el router (solo aditivo)
Añade el import (respetando el orden alfabético de `routers`):
```python
from routers.listening import router as listening_router
```
y el include (junto a los demás):
```python
app.include_router(listening_router)
```
No toques nada más de `main.py`.

### 8. Test nuevo `backend/tests/test_listening.py` (13 tests)

```python
"""Tests de listening: banco, puntuación, dominio, repositorio y endpoints."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    QUESTION_BANK,
    get_question,
    pick_next_question,
    score_answer,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_score_answer_correct():
    assert score_answer(1, 1) is True


def test_score_answer_incorrect():
    assert score_answer(0, 1) is False


def test_get_question_found():
    q = get_question(QUESTION_BANK[0]["id"])
    assert q is not None
    assert q["script"]


def test_get_question_missing():
    assert get_question("nope") is None


def test_pick_next_unseen():
    assert pick_next_question(set())["id"] == QUESTION_BANK[0]["id"]
    assert pick_next_question({QUESTION_BANK[0]["id"]})["id"] == QUESTION_BANK[1]["id"]


def test_pick_next_wraps_around():
    seen = {q["id"] for q in QUESTION_BANK}
    assert pick_next_question(seen)["id"] == QUESTION_BANK[0]["id"]


def test_bank_shape_valid():
    assert len(QUESTION_BANK) >= 3
    for q in QUESTION_BANK:
        assert q["id"]
        assert q["script"]
        assert q["question"]
        assert len(q["options"]) >= 2
        assert 0 <= q["answer_index"] < len(q["options"])


def test_next_question_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["script"]
    assert body["question"]
    assert isinstance(body["options"], list) and len(body["options"]) >= 2
    assert "answer_index" not in body


def test_answer_correct(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["correct_index"] == q["answer_index"]


def test_answer_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    wrong = (q["answer_index"] + 1) % len(q["options"])
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": wrong},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_answer_unknown_question_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": "nope", "answer_index": 0},
        )
    assert r.status_code == 404


def test_answer_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": "no-existe"},
            json={"question_id": q["id"], "answer_index": 0},
        )
    assert r.status_code == 404


def test_stats_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/stats", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
```

## Verificación (desde `backend/`)
```powershell
python -c "import main"
python -m pytest tests/ -q
python -m ruff check .
```
Si `python` no funciona, prueba `.venv\Scripts\python.exe` (Python 3.13.7).

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 191 tests** (178 previos + 13 nuevos).
- `python -m ruff check .` **sin errores**.
- Ningún test existente se rompe.

## Restricciones
- NO tocar el frontend.
- En `db.py` y `main.py` solo cambios **aditivos** (tabla+índice / import+include_router).
- NO tocar `routers/*` existentes, `domain/*` existentes, `services/*` existentes,
  `dependencies.py`, ni `config.py`.
- Mantener estilo: docstrings en español, `from __future__ import annotations`,
  imports ordenados (ruff/isort), línea ≤ 88.

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.

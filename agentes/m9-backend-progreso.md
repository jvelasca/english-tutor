# Subagente M9 (backend) — Seguimiento de progreso del alumno

## Rol
Desarrollador backend (Python + FastAPI + Pydantic, tipado fuerte). Sin acceso a Git.
No necesitas red: la persistencia es SQLite (stdlib) y los tests no dependen de modelos externos.

## Objetivo
Implementar el **registro y consulta del progreso del alumno por usuario**: número de
ejercicios, correcciones y puntuaciones de pronunciación. Corresponde al issue de GitHub #2
("Seguimiento de progreso del alumno", pendiente diferido de M4).

## Contexto (autocontenido)
- Proyecto 100% local (premisa 2). Estructura modular en `docs/ARQUITECTURA.md`:
  `routers/` (HTTP), `services/` (lógica), `schemas/` (contratos Pydantic).
- Persistencia en `backend/services/store.py` (SQLite stdlib, `init_db()` idempotente y
  no destructivo; ya tiene migración idempotente para `user_id` como patrón a copiar).
- El chat acepta `mode` ∈ {`conversation`, `grammar`, `exercises`, `pronunciation`}
  (ver `backend/config.py` → `MODE_PROMPTS`).
- La pronunciación se evalúa en `backend/services/pronunciation.py` (`score_pronunciation`,
  devuelve `{expected, heard, score, level, ok}`) y se expone en
  `backend/routers/pronunciation.py` (`POST /api/pronunciation`, multipart: `file`,
  `expected`, `language`). **Hoy el resultado NO se persiste.**
- Los mensajes se guardan en `backend/services/store.py` → `save_conversation(cid, title,
  messages)` con `messages = [{role, content}]` (ver `backend/schemas/chat.py` `ChatMessage`).
- Tests con pytest en `backend/tests/` (ver `test_store.py`: monkeypatching de
  `store.DATA_DIR` y `store.DB_PATH`).

## Contrato (API) — respétalo exactamente

### `GET /api/progress?user_id=<id>` → `ProgressSummary`
```json
{
  "user_id": "<id>",
  "conversations": 3,
  "messages": 42,
  "exercises": 5,
  "corrections": 7,
  "pronunciation": {
    "attempts": 10,
    "best": 95,
    "average": 82.5,
    "last_score": 88,
    "last_level": "good"
  }
}
```
- `conversations`: nº de conversaciones del usuario.
- `messages`: nº total de mensajes (user + assistant) del usuario.
- `exercises`: nº de mensajes de rol `user` cuyo `mode` es `exercises`.
- `corrections`: nº de mensajes de rol `user` cuyo `mode` es `grammar`.
- `pronunciation`: agregados de la tabla `pronunciation_attempts` del usuario
  (`best`/`last_score`/`last_level` = `None` si no hay intentos; `average` = media de
  `score` redondeada a 1 decimal, o `None` si no hay intentos).

### `POST /api/pronunciation` (extendido, sin romper lo actual)
- Acepta un campo opcional `user_id: str = Form(None)`.
- Si `user_id` viene, tras calcular el score persiste el intento (expected, heard, score,
  level) asociado a ese usuario. La respuesta sigue siendo la misma
  (`PronunciationResponse`), sin cambios.

## Tarea
1. `backend/schemas/chat.py`: añadir a `ChatMessage` un campo opcional
   `mode: str | None = None`.
2. `backend/schemas/progress.py` (nuevo): modelos Pydantic `PronunciationStats` y
   `ProgressSummary` (campos exactos del contrato).
3. `backend/services/store.py`:
   - `init_db()`: crear tabla `pronunciation_attempts`
     (`id INTEGER PK AUTOINCREMENT`, `user_id TEXT NOT NULL`, `expected TEXT NOT NULL`,
     `heard TEXT NOT NULL`, `score INTEGER NOT NULL`, `level TEXT NOT NULL`,
     `created_at TEXT NOT NULL`).
   - Migración idempotente para añadir columna `mode TEXT` a `messages` (mismo patrón que
     el `ALTER TABLE ... ADD COLUMN user_id` ya existente).
   - `save_conversation`: guardar el `mode` de cada mensaje (si no viene, `None`).
   - `get_conversation`: devolver `mode` en cada mensaje (para round-trip; no romper).
   - `record_pronunciation(user_id, expected, heard, score, level) -> None`.
   - `get_progress(user_id) -> dict` con la forma del contrato.
4. `backend/routers/progress.py` (nuevo): `GET /api/progress?user_id=<id>`. Si el usuario
   no existe, devolver 404 (patrón de `routers/conversations.py`).
5. `backend/routers/pronunciation.py`: aceptar `user_id: str = Form(None)` y, si viene,
   llamar a `record_pronunciation` tras el score.
6. `backend/main.py`: registrar `progress_router` (junto a los demás routers).
7. Tests: `backend/tests/test_progress.py` (nuevo) + ajustar `test_store.py` si el shape de
   los mensajes cambia (debe seguir aceptando `{role, content}` sin `mode`).

## Criterios de aceptación
- `pytest tests/ -q` verde, rápido y sin red.
- `python -c "import main"` sin errores.
- `GET /api/progress?user_id=<id>` devuelve exactamente el contrato anterior.
- Grabar 2 intentos de pronunciación y ver `attempts=2`, `best`/`average`/`last_score`
  correctos.
- Guardar una conversación con mensajes en modo `grammar` y `exercises` y ver esos
  contadores incrementados en `get_progress`.

## Restricciones
- No tocar `services/llm.py`, `services/stt.py`, `services/tts.py`, `services/pronunciation.py`.
- No cambiar el contrato existente de `/api/conversations`, `/api/users`, `/api/chat`.
- No actualizar `docs/`, `PLAN.md`, `README.md`, `RELEVO.md` ni `agentes/` (lo hace el gerente).
- Tests deterministas y rápidos (monkeypatch de `store.DATA_DIR`/`DB_PATH` como en `test_store.py`).

## Salida
- Lista de archivos creados/modificados.
- Resumen de decisiones (p. ej. cómo cuentas `exercises`/`corrections`).
- Confirmación de `pytest tests/ -q` verde.

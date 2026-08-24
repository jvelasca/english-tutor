# Subagente E1.1 — Backend: aislamiento real de conversaciones y pronunciación (ownership)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Cerrar el **bug crítico de aislamiento multiusuario (P0)**: hoy `GET/PUT/DELETE
/api/conversations/{cid}` y `POST /api/pronunciation` no comprueban el propietario/usuario,
así que conociendo un `cid` se puede leer, modificar o borrar una conversación ajena, y
registrar pronunciación a nombre de otro usuario. Debe quedar **enforcement de ownership a
nivel de datos (store) y de HTTP (routers)**.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (leer premisas 2, 5, 8, 12, 13 — "aislamiento total").
- Estructura: `docs/ARQUITECTURA.md`. Regla de oro: `routers/` = HTTP sin lógica; `services/`
  = lógica sin HTTP; `schemas/` = contratos.
- Persistencia en `backend/services/store.py` (SQLite stdlib). Estado actual:
  - `init_db()` crea `conversations`, `messages`, `users`, `pronunciation_attempts` y migra
    `conversations.user_id` y `messages.mode` con `ALTER TABLE` (idempotente).
  - `get_conversation(cid)`, `save_conversation(cid, title, messages)`,
    `delete_conversation(cid)` **NO filtran por usuario** (ahí está el bug).
  - `create_conversation(user_id)` y `list_conversations(user_id)` ya filtran por usuario.
  - `record_pronunciation(user_id, expected, heard, score, level)` **no valida** que el
    usuario exista.
  - `get_user(uid) -> dict | None` ya existe.
- `backend/routers/conversations.py`: `create`/`list_all` reciben `user_id` (query param);
  `get_one`/`save`/`delete` reciben **solo `cid`**.
- `backend/routers/pronunciation.py`: `user_id: str = Form(None)` (opcional).
- Tests existentes que **usan las funciones que van a cambiar de firma** y que DEBES
  actualizar: `backend/tests/test_store.py::test_store_crud`,
  `backend/tests/test_users.py::test_migration_assigns_orphans_to_default_user`,
  `backend/tests/test_progress.py` (varios `save_conversation` y `get_conversation`).
- Cómo ejecutar los tests (desde `backend/`, con la línea base ya verde):
  ```powershell
  python -m pytest tests/ -q
  python -c "import main"
  ```

## Tarea detallada

### 1. `services/store.py` — ownership en datos
Cambia las firmas y añade la condición `AND user_id = ?` en TODAS las consultas de estas
funciones. Si la conversación no existe **o no pertenece** a `user_id`, devuelven
`None`/`False` (indistinguible de "no encontrado", para no filtrar existencia):

- `get_conversation(cid: str, user_id: str) -> dict | None`:
  ```sql
  SELECT id, title, created_at, updated_at, user_id
  FROM conversations WHERE id = ? AND user_id = ?
  ```
  (la consulta de `messages` se mantiene `WHERE conversation_id = ?`, porque la
  conversación ya está validada como propia).
- `save_conversation(cid: str, user_id: str, title: str, messages: list[dict]) -> dict | None`:
  comprobar primero `SELECT created_at, user_id FROM conversations WHERE id = ? AND user_id = ?`;
  si no hay fila, devolver `None` (no tocar nada). El `UPDATE` también con `AND user_id = ?`.
- `delete_conversation(cid: str, user_id: str) -> bool`:
  `DELETE FROM conversations WHERE id = ? AND user_id = ?`; devolver `rowcount > 0`.
- `record_pronunciation(user_id, expected, heard, score, level) -> bool`:
  si `get_user(user_id) is None` devolver `False`; si existe, insertar y devolver `True`.
- En `init_db()`, añadir índices (no FK por ahora; la FK real requiere rebuild y se difiere):
  ```sql
  CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
  CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id ON pronunciation_attempts(user_id);
  ```
  Colócalos tras la migración de columnas, dentro del mismo `init_db`.

### 2. `routers/conversations.py` — exigir user_id
- `get_one(cid: str, user_id: str)` → `store.get_conversation(cid, user_id)`.
- `save(cid: str, user_id: str, body)` → `store.save_conversation(cid, user_id, body.title, [...])`.
- `delete(cid: str, user_id: str)` → `store.delete_conversation(cid, user_id)`.
- `user_id` es **query param requerido** (igual que `create`/`list_all`): si falta, FastAPI
  devuelve 422. Si el store devuelve `None`/`False`, mantener el `404` actual.

### 3. `routers/pronunciation.py` — validar usuario
- Cambiar a `user_id: str = Form(...)` (obligatorio).
- Al inicio del endpoint, si `store.get_user(user_id) is None` → `404 "Usuario no encontrado"`
  (antes de transcribir, para no gastar CPU en un usuario inválido).
- Tras puntuar, llamar a `store.record_pronunciation(...)` (ahora devuelve bool; con la
  validación previa siempre será `True`; ignora el retorno).

### 4. Actualizar tests existentes (firmas nuevas)
- `test_store.py::test_store_crud`: `save_conversation(cid, uid, "Mi clase", [...])`,
  `get_conversation(cid, uid)`, `delete_conversation(cid, uid)`.
- `test_users.py::test_migration_assigns_orphans_to_default_user`: `get_conversation("old1", users[0]["id"])`.
- `test_progress.py`: todas las llamadas `save_conversation(cid, uid, "Clase", [...])` y
  `get_conversation(cid, uid)`.

### 5. Test nuevo: `backend/tests/test_store_isolation.py`
Crea un archivo con estos tests (pytest, deterministas, sin red, usando `monkeypatch` sobre
`store.DATA_DIR` y `store.DB_PATH` igual que `test_store.py`):

- `test_get_conversation_other_user_returns_none`: crear usuarios A y B, conversación de A;
  `get_conversation(cid, A) is not None` y `get_conversation(cid, B) is None`.
- `test_save_conversation_other_user_returns_none`: `save_conversation(cid, B, ...) is None`
  y la conversación de A queda intacta.
- `test_delete_conversation_other_user_returns_false`: `delete_conversation(cid, B) is False`,
  la conversación sigue existiendo para A, y `delete_conversation(cid, A) is True`.
- `test_record_pronunciation_unknown_user_returns_false`.
- `test_record_pronunciation_known_user_returns_true`.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (los 27 previos actualizados + los 5 nuevos de
  aislamiento ≈ 32 tests).
- El aislamiento se verifica a nivel store: con el `cid` de A, desde B no se puede leer,
  modificar ni borrar; y no se puede registrar pronunciación para un usuario inexistente.

## Restricciones
- NO tocar `services/llm.py`, `services/stt.py`, `services/tts.py`,
  `services/pronunciation.py`, `config.py`, `main.py`, `schemas/` ni el frontend.
- NO añadir dependencias (solo stdlib + lo ya instalado).
- NO introducir autenticación/JWT/cuentas: el "contexto de usuario" se resuelve del
  `user_id` explícito que ahora es obligatorio en cada operación sensible.
- Mantener estilo del repo: funciones puras y testables, sin lógica en routers, comentarios
  solo donde aporten. Migración no destructiva.

## Salida
Lista de archivos creados/modificados (con un resumen de cada cambio) y la salida de
`python -m pytest tests/ -q`.

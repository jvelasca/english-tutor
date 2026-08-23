# Subagente M7 — Backend: multi-usuario (perfiles + aislamiento de conversaciones)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Añadir **perfiles de usuario locales** con **aislamiento total** de conversaciones entre
usuarios (premisa 13). Sin cuentas en la nube: perfiles locales simples (id + nombre),
seleccionados al abrir la app. Todo 100% local, persistencia en SQLite.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (leer premisas 2, 5, 8, 12, 13).
- Estructura y responsabilidades: `docs/ARQUITECTURA.md`. Regla de oro:
  - `routers/` = capa HTTP (sin lógica de negocio).
  - `services/` = lógica (sin HTTP).
  - `schemas/` = contratos Pydantic.
- Persistencia actual en `backend/services/store.py` (SQLite stdlib):
  - `init_db()` crea `conversations` y `messages` (idempotente).
  - Funciones: `create_conversation()`, `list_conversations()`,
    `get_conversation(cid)`, `save_conversation(cid, title, messages)`,
    `delete_conversation(cid)`.
  - `DB_PATH = DATA_DIR / "tutor.db"`. Las pruebas usan `monkeypatch` sobre `store.DATA_DIR`
    y `store.DB_PATH` (ver `backend/tests/test_store.py`).
- `backend/routers/conversations.py` expone el CRUD de conversaciones
  (`POST/GET /api/conversations`, `GET/PUT/DELETE /api/conversations/{cid}`).
- `backend/schemas/conversations.py` define `ConversationMeta`, `Conversation`,
  `ConversationUpsert`.
- `backend/main.py` monta los routers y llama a `init_db()` en el lifespan.
- `backend/schemas/__init__.py` reexporta los esquemas.

## Tarea
1. **Migración del esquema (idempotente)** en `services/store.py`:
   - Nueva tabla `users`:
     ```sql
     CREATE TABLE IF NOT EXISTS users (
         id TEXT PRIMARY KEY,
         name TEXT NOT NULL,
         created_at TEXT NOT NULL
     )
     ```
   - Añadir columna `user_id TEXT` a `conversations`. Como SQLite no soporta
     `ADD COLUMN IF NOT EXISTS`, usar una migración segura: comprobar con
     `PRAGMA table_info(conversations)` si la columna `user_id` existe; si no,
     `ALTER TABLE conversations ADD COLUMN user_id TEXT`. Para bases existentes,
     dejar `user_id` como `NULL` para las filas antiguas (o asignarlas a un usuario
     por defecto, ver punto siguiente).
   - Crear un **usuario por defecto** (p. ej. `name="Usuario"`) si la tabla `users`
     está vacía, y asignar sus conversaciones huérfanas (`user_id IS NULL`) a ese
     usuario, para no perder datos previos.
2. **Nuevas funciones de store** (todas devuelven `dict`, sin HTTP):
   - `create_user(name: str) -> dict` (id uuid hex, `created_at`).
   - `list_users() -> list[dict]`.
   - `get_user(uid: str) -> dict | None`.
   - `create_conversation(user_id: str) -> dict` (valida que el usuario existe;
     devuelve el meta incluyendo `user_id`).
   - `list_conversations(user_id: str) -> list[dict]` (solo del usuario).
   - `get_conversation(cid: str)`, `save_conversation(cid, title, messages)`,
     `delete_conversation(cid)` se mantienen por `cid`, sin cambios de firma.
   - **Aislamiento:** todas las consultas de listado filtran por `user_id`.
3. **Esquemas**:
   - `backend/schemas/users.py`: `User` (id, name, created_at) y `UserCreate`
     (name, con validación no vacío).
   - Actualizar `ConversationMeta` para incluir `user_id: str` (campo obligatorio en
     el contrato; en el store, las conversaciones siempre pertenecen a un usuario).
4. **Routers**:
   - `backend/routers/users.py`: `GET /api/users` (listar) y `POST /api/users`
     (crear con `UserCreate`).
   - Actualizar `backend/routers/conversations.py`:
     - `POST /api/conversations` recibe `user_id` (query param o body; elegir una y
       documentarla) y crea la conversación para ese usuario.
     - `GET /api/conversations` filtra por `user_id` (query param).
     - Si no se pasa `user_id`, devolver 422 (Pydantic/FastAPI).
5. **Cableado**: montar `users_router` en `backend/main.py` y reexportar los nuevos
   esquemas en `backend/schemas/__init__.py`.

## Criterios de aceptación
- `python -c "import main"` no falla.
- Tests nuevos en `backend/tests/test_users.py` (pytest, deterministas, sin red):
  - Crear usuario devuelve id y nombre.
  - Listar usuarios.
  - `create_conversation(uid)` asocia `user_id`.
  - **Aislamiento:** las conversaciones del usuario A no aparecen en la lista del
    usuario B (crear A y B, crear conversación de A, listar B → vacío).
  - `create_conversation` con usuario inexistente falla o devuelve error controlado.
- Actualizar `backend/tests/test_store.py` si las firmas cambiaron; debe seguir verde.
- `pytest tests/ -q` verde.

## Restricciones
- No tocar `services/llm.py`, `services/stt.py`, `services/tts.py`,
  `services/pronunciation.py` ni los routers de chat/voz/pronunciación.
- No añadir dependencias nuevas (solo stdlib + lo ya instalado).
- Mantener el estilo: sin lógica de negocio en routers, funciones de store puras y
  testables, comentarios solo donde aporten.
- Preservar la compatibilidad con bases existentes (migración no destructiva).

## Salida
Lista de archivos creados/modificados y resultado de `pytest tests/ -q`.

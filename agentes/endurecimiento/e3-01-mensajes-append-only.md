# Subagente E3.1 — Backend: mensajes append-only (con id de mensaje)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Hoy `save_conversation` hace `DELETE FROM messages WHERE conversation_id=?` y reinserta todos
los mensajes con el mismo `now`: pierde los IDs y timestamps originales y multiplica escrituras
(auditoría #7). Cambiar a **append-only**: los mensajes traen un `id` estable y solo se insertan
los nuevos; los ya existentes se conservan con su timestamp. Mantener compatibilidad con
clientes legacy (sin `id`).

## Contexto (autocontenido)
- `backend/services/store.py` (LEERLO): `init_db`, `get_conversation`, `save_conversation`.
  Tabla `messages`: `id INTEGER PK AUTOINCREMENT, conversation_id, role, content, created_at`
  + columna `mode` (migración idempotente). `get_conversation` hace
  `SELECT role, content, mode FROM messages WHERE conversation_id=? ORDER BY id ASC`.
  `save_conversation` borra e inserta todo con `_now()`.
- `backend/schemas/chat.py`: `ChatMessage` (role, content, mode). Lo usan tanto `ChatRequest`
  (chat) como `ConversationUpsert` (guardado). Por eso el `id` debe ser **opcional**
  (`id: str | None = None`), para no romper `/api/chat` (que no envía ids).
- `routers/conversations.py` llama `store.save_conversation(cid, user["id"], title,
  [m.model_dump() for m in body.messages])` — `model_dump()` ya incluirá la clave `id`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/schemas/chat.py`
Añadir `id` opcional a `ChatMessage`:
```python
class ChatMessage(BaseModel):
    """Un mensaje dentro de la conversación."""

    role: Role
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    mode: str | None = None
    id: str | None = None
```

### 2. `backend/services/store.py` — migración idempotente
En `init_db`, justo después del bloque que añade `mode` (junto a las otras migraciones), añadir
la columna `message_id` y un índice único. Insertar:
```python
        if "message_id" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_message_id "
            "ON messages(conversation_id, message_id)"
        )
```
> El índice único permite múltiples `message_id` NULL (SQLite trata NULL como distinto), así
> que las filas legacy (message_id NULL) no entran en conflicto.

### 3. `backend/services/store.py` — `get_conversation`
Cambiar el SELECT y la construcción de mensajes para devolver `id` (= `message_id`):
```python
        msgs = conn.execute(
            "SELECT role, content, mode, message_id FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (cid,),
        ).fetchall()
    result = dict(conv)
    result["messages"] = [
        {
            "id": m["message_id"],
            "role": m["role"],
            "content": m["content"],
            "mode": m["mode"],
        }
        for m in msgs
    ]
    return result
```

### 4. `backend/services/store.py` — `save_conversation` append-only
Sustituir el cuerpo de `save_conversation` por:
```python
def save_conversation(
    cid: str, user_id: str, title: str, messages: list[dict]
) -> dict | None:
    """Guarda título y mensajes de una conversación (solo del propietario).

    Si todos los mensajes traen `id`, el guardado es append-only: se insertan solo los
    mensajes cuyo `id` no existe aún en la conversación (los ya existentes conservan su
    timestamp original). Si algún mensaje no trae `id` (cliente legacy), se mantiene el
    comportamiento anterior de reemplazar todos los mensajes.
    """
    now = _now()
    append_only = all(m.get("id") for m in messages)
    with closing(_conn()) as conn, conn:
        conv = conn.execute(
            "SELECT created_at, user_id FROM conversations WHERE id = ? AND user_id = ?",
            (cid, user_id),
        ).fetchone()
        if conv is None:
            return None
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ?",
            (title, now, cid, user_id),
        )
        if append_only:
            conn.executemany(
                "INSERT OR IGNORE INTO messages "
                "(conversation_id, role, content, mode, created_at, message_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (cid, m["role"], m["content"], m.get("mode"), now, m.get("id"))
                    for m in messages
                ],
            )
        else:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.executemany(
                "INSERT INTO messages (conversation_id, role, content, mode, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [(cid, m["role"], m["content"], m.get("mode"), now) for m in messages],
            )
    return {
        "id": cid,
        "title": title,
        "created_at": conv["created_at"],
        "updated_at": now,
        "user_id": conv["user_id"],
    }
```

### 5. Test nuevo `backend/tests/test_store_append_only.py`
```python
from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()
    uid = store.list_users()[0]["id"]
    cid = store.create_conversation(uid)["id"]
    return uid, cid


def test_append_only_does_not_duplicate(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    store.save_conversation(
        cid,
        uid,
        "T",
        [
            {"id": "m1", "role": "user", "content": "Hi"},
            {"id": "m2", "role": "assistant", "content": "Hello"},
        ],
    )
    store.save_conversation(
        cid,
        uid,
        "T",
        [
            {"id": "m1", "role": "user", "content": "Hi"},
            {"id": "m2", "role": "assistant", "content": "Hello"},
            {"id": "m3", "role": "user", "content": "Bye"},
        ],
    )
    conv = store.get_conversation(cid, uid)
    assert [m["id"] for m in conv["messages"]] == ["m1", "m2", "m3"]
    assert len(conv["messages"]) == 3


def test_legacy_save_without_ids_replaces(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    store.save_conversation(
        cid,
        uid,
        "T",
        [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}],
    )
    store.save_conversation(cid, uid, "T", [{"role": "user", "content": "only"}])
    conv = store.get_conversation(cid, uid)
    assert [m["content"] for m in conv["messages"]] == ["only"]


def test_get_conversation_returns_message_id(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    store.save_conversation(
        cid, uid, "T", [{"id": "abc", "role": "user", "content": "Hi"}]
    )
    conv = store.get_conversation(cid, uid)
    assert conv["messages"][0]["id"] == "abc"
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (62 previos + 3 nuevos = 65 tests).
- `python -m ruff check .` **sin errores**.
- Los tests existentes (`test_store.py`, `test_api_security.py`, etc.) siguen verdes (el path
  legacy sin ids mantiene el comportamiento anterior).

## Restricciones
- NO tocar el frontend ni `routers/` ni `schemas/conversations.py`.
- NO tocar `llm.py`, `stt.py`, `tts.py`, `pronunciation.py`.
- NO cambiar el contrato de `/api/chat` (los mensajes de chat siguen sin `id`).
- Mantener el estilo y las firmas de `get_conversation`/`save_conversation` (solo cambia su
  comportamiento interno y el contenido devuelto).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q` y de `python -m ruff check .`, y cualquier desviación.

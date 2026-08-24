# Subagente E1.4 — Backend: contratos (quitar `system` y límites de payload)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Cerrar dos brechas P0 en los contratos de la API:
1. El cliente no debe poder enviar mensajes con `role="system"` (solo `user` y `assistant`);
   el único `system` lo construye el servidor internamente.
2. Acotar el tamaño de los payloads (mensajes, contenido y texto TTS) para evitar abusos de
   RAM/CPU/contexto.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (premisas 5, 8, 12) y `docs/ARQUITECTURA.md`.
- Archivos a tocar (LEERLOS antes de editar):
  - `backend/config.py` — constantes de configuración (sin lógica). Ya define `DEFAULT_MODEL`,
    `DEFAULT_MODE`, `MODE_PROMPTS`, etc.
  - `backend/schemas/chat.py` — `Role = Literal["system", "user", "assistant"]`,
    `ChatMessage`, `ChatRequest`. Importa `DEFAULT_MODE`, `DEFAULT_MODEL` desde `config`.
  - `backend/schemas/voz.py` — `TTSRequest.text: str = Field(min_length=1)`.
  - `backend/services/llm.py` — construye `[{"role":"system", ...}, *[m.model_dump() ...]]`.
    **NO necesita cambios**: al quitar `system` del `Role`, el único system será el interno.
  - `backend/tests/test_schemas.py` — tests actuales de `ChatRequest`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. `backend/config.py` — constantes de límites
Añadir:
```python
MAX_CHAT_MESSAGES = 100
MAX_CONTENT_CHARS = 8000
MAX_TTS_CHARS = 4000
```

### 2. `backend/schemas/chat.py`
- Cambiar `Role = Literal["system", "user", "assistant"]` → `Role = Literal["user", "assistant"]`.
- `ChatMessage.content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)`.
- `ChatRequest.messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_CHAT_MESSAGES)`.
- Importar `MAX_CONTENT_CHARS` y `MAX_CHAT_MESSAGES` desde `config` (junto a los ya importados).

### 3. `backend/schemas/voz.py`
- `TTSRequest.text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)`.
- Importar `MAX_TTS_CHARS` desde `config`.

### 4. Tests (añadir a `backend/tests/test_schemas.py`)
Añadir estos tests (mantener los 3 existentes):
```python
from config import MAX_CHAT_MESSAGES, MAX_CONTENT_CHARS, MAX_TTS_CHARS
from schemas.voz import TTSRequest

def test_system_role_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "system", "content": "you are a tutor"}])

def test_content_too_long_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "x" * (MAX_CONTENT_CHARS + 1)}])

def test_too_many_messages_rejected():
    msgs = [{"role": "user", "content": "x"}] * (MAX_CHAT_MESSAGES + 1)
    with pytest.raises(ValidationError):
        ChatRequest(messages=msgs)

def test_empty_messages_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[])

def test_tts_text_too_long_rejected():
    with pytest.raises(ValidationError):
        TTSRequest(text="x" * (MAX_TTS_CHARS + 1))
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (38 previos + 5 nuevos ≈ 43 tests).
- `ChatRequest` con `role="system"` lanza `ValidationError`; el frontend (que solo manda
  `user`/`assistant`) sigue funcionando.

## Restricciones
- NO tocar `services/llm.py` (ya está bien), `routers/`, `services/store.py`, `dependencies.py`,
  `main.py` ni el frontend.
- NO añadir dependencias.
- Mantener el estilo del repo (constantes en `config.py`, schemas con `Field`).

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.

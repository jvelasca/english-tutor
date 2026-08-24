# Subagente E1.5 — Backend: límites de subida de audio + sanitización de errores

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Cerrar dos brechas de robustez P0/P1:
1. **Subida de audio sin límites**: `POST /api/transcribe` y `POST /api/pronunciation` hacen
   `await file.read()` sin tope de tamaño ni comprobación de tipo. Añadir límite de tamaño
   (413) y comprobación de content-type (415).
2. **Filtración de errores internos**: varios routers devuelven `detail=f"... {exc}"`,
   exponiendo el error interno al cliente. Sustituir por mensajes genéricos y registrar el
   detalle en el log del servidor.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (premisas 5, 8, 12) y `docs/ARQUITECTURA.md`.
- `backend/dependencies.py` ya existe (creado en E1.3) con `current_user`. Tiene
  `from fastapi import HTTPException, Query` y `from services import store`.
- Archivos a tocar (LEERLOS antes de editar):
  - `backend/config.py` — añadir `MAX_AUDIO_BYTES`.
  - `backend/dependencies.py` — añadir helper de lectura limitada.
  - `backend/routers/voz.py` — `/api/transcribe` (usa `await file.read()` y filtra `exc`)
    y `/api/tts` (filtra `exc`).
  - `backend/routers/pronunciation.py` — usa `await file.read()` y filtra `exc`.
  - `backend/routers/chat.py` — filtra `exc` en `/api/chat` y en `/api/chat/stream`.
  - `backend/routers/models.py` — filtra `exc` en `/api/models`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. `backend/config.py`
Añadir:
```python
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB
```

### 2. `backend/dependencies.py` — helper de lectura limitada
Añadir:
```python
import config
from fastapi import HTTPException, Query, UploadFile  # ampliar el import existente

_ALLOWED_AUDIO_TYPES = {
    "application/octet-stream",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-wav",
}


def _content_type_ok(content_type: str | None) -> bool:
    if not content_type:
        return True
    base = content_type.split(";")[0].strip().lower()
    return base.startswith("audio/") or base in _ALLOWED_AUDIO_TYPES


async def read_audio_limited(file: UploadFile) -> bytes:
    """Lee un audio con límite de tamaño y tipo. 415 si el tipo no es audio, 413 si excede."""
    if not _content_type_ok(file.content_type):
        raise HTTPException(status_code=415, detail="Formato de audio no soportado")
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > config.MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio demasiado grande")
    return bytes(data)
```

> Referenciar `config.MAX_AUDIO_BYTES` como atributo del módulo (no `from config import ...`)
> para que los tests puedan monkeypatchearlo.

### 3. `routers/voz.py`
- `/api/transcribe`: sustituir `audio = await file.read()` por
  `audio = await read_audio_limited(file)` (importar `read_audio_limited` de `dependencies`).
- Sustituir el `except` que devuelve `detail=f"Error transcribiendo el audio: {exc}"` por:
  ```python
  except Exception:  # noqa: BLE001
      logger.exception("Error transcribiendo el audio")
      raise HTTPException(status_code=500, detail="No se pudo transcribir el audio")
  ```
- `/api/tts`: igual, mensaje genérico `"No se pudo sintetizar la voz"` y `logger.exception`.
- Añadir al inicio del archivo: `import logging` y `logger = logging.getLogger(__name__)`.

### 4. `routers/pronunciation.py`
- Sustituir `audio = await file.read()` por `audio = await read_audio_limited(file)`.
- En el `except` de transcripción: mensaje genérico `"No se pudo transcribir el audio"` +
  `logger.exception(...)`. Añadir `import logging` y `logger`.

### 5. `routers/chat.py`
- Añadir `import logging` y `logger = logging.getLogger(__name__)`.
- `/api/chat`: en el `except`, `logger.exception("Error en /api/chat")` y devolver
  `HTTPException(502, detail="No se pudo completar la respuesta")`.
- `/api/chat/stream` (en `generate`): en el `except`, `logger.exception(...)` y emitir
  `yield 'data: {"error": "No se pudo completar la respuesta"}\n\n'` (sin `str(exc)`).

### 6. `routers/models.py`
- Añadir `import logging` y `logger`.
- `/api/models`: en el `except`, `logger.exception(...)` y devolver
  `HTTPException(502, detail="No se pudo contactar con Ollama")`.

### 7. Test nuevo `backend/tests/test_robustness.py`
Usar `TestClient` + `monkeypatch`. Helper de setup igual que `test_api_security.py` (NO hace
falta para los tests de transcribe/models, pero sí para que `main.app` arranque).

```python
import config
import pytest
from fastapi.testclient import TestClient

from main import app
from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()
```

Tests:
- `test_transcribe_audio_too_large_413`: `monkeypatch.setattr(config, "MAX_AUDIO_BYTES", 8)`;
  POST `/api/transcribe` con `files={"file": ("a.webm", b"0123456789ABCDEF", "audio/webm")}`
  → 413.
- `test_transcribe_bad_content_type_415`: POST `/api/transcribe` con
  `files={"file": ("a.pdf", b"data", "application/pdf")}` → 415.
- `test_models_error_not_leaked`: `monkeypatch.setattr("services.llm.list_models",
  _raise)` con `_raise` que lance `RuntimeError("SECRET-INTERNAL")`; GET `/api/models` → 502
  y `"SECRET-INTERNAL" not in r.text`.
- `test_chat_error_not_leaked`: `monkeypatch.setattr("services.llm.chat_once", _raise)`;
  POST `/api/chat` con `json={"messages": [{"role": "user", "content": "Hi"}]}` → 502 y
  `"SECRET-INTERNAL" not in r.text`.

> Para `_raise`, define `async def _raise(*args, **kwargs): raise RuntimeError("SECRET-INTERNAL")`
> (las funciones son `async`, por eso el stub debe ser corrutina).

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (43 previos + 4 nuevos ≈ 47 tests).
- Ningún detalle de excepción interna se devuelve al cliente (mensajes genéricos).

## Restricciones
- NO tocar `services/llm.py`, `services/stt.py`, `services/tts.py`, `services/store.py`,
  `schemas/`, `main.py` ni el frontend.
- NO cambiar el contrato de respuesta exitosa (200/404/etc. se mantienen).
- NO añadir dependencias.
- Mantener el estilo del repo (log interno + mensaje genérico al cliente).

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.

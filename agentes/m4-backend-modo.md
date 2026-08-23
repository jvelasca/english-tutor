# Subagente M4 — Backend: modo profesor + corrección de pronunciación

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
Añadir al backend dos capacidades del "modo profesor":
1. **Modos de tutor** (system prompt por modo) en el chat.
2. **Corrección de pronunciación** (audio + texto esperado → puntuación).

## Contexto (autocontenido)
- Proyecto 100% local. Stack fijado en `docs/PREMISAS.md`.
- Estructura y responsabilidades en `docs/ARQUITECTURA.md`:
  - `routers/` = capa HTTP (sin lógica). `services/` = lógica (sin HTTP). `schemas/` = Pydantic.
- `config.py` tiene `DEFAULT_MODEL` y `SYSTEM_PROMPT`. `services/llm.py` tiene `_messages()`,
  `chat_once()`, `chat_stream()`. `routers/chat.py` tiene `POST /api/chat` y `/api/chat/stream`.
- STT ya existe en `services/stt.py` como `transcribe(audio: bytes, language: str) -> str`
  (bloqueante; se ejecuta en thread con `run_in_threadpool`).
- `main.py` monta los routers. `schemas/__init__.py` reexporta los modelos.

## Tarea
1. `config.py`: añadir `DEFAULT_MODE = "conversation"` y `MODE_PROMPTS: dict[str, str]` con 4 modos:
   `conversation`, `grammar`, `exercises`, `pronunciation` (cada uno con su system prompt en inglés,
   permitiendo explicaciones en español cuando ayude).
2. `schemas/chat.py`: añadir `mode: str = Field(default=DEFAULT_MODE)` a `ChatRequest`.
3. `services/llm.py`: función pura `system_prompt_for(mode) -> str` (fallback al modo por defecto
   si el modo no existe); `_messages()` y `chat_once()`/`chat_stream()` aceptan y usan `mode`.
4. `routers/chat.py`: pasar `req.mode` a `chat_once` y `chat_stream`.
5. `services/pronunciation.py`: función pura `score_pronunciation(expected, heard) -> dict` con
   `score` (0-100, usando `difflib.SequenceMatcher` sobre texto normalizado), `level`
   (`good`/`fair`/`needs_practice` con umbral 80/50) y `ok`.
6. `schemas/pronunciation.py`: `PronunciationResponse` (expected, heard, score, level, ok).
7. `routers/pronunciation.py`: `POST /api/pronunciation` (multipart: `file`, `expected`, `language`="en")
   → transcribe y puntúa.
8. `main.py`: montar `pronunciation_router`. `schemas/__init__.py`: reexportar `PronunciationResponse`.

## Criterios de aceptación
- `python -c "import main"` no falla.
- Tests nuevos (pytest, deterministas, sin red ni modelos):
  - `test_pronunciation.py`: coincidencia exacta=100, ignora mayúsculas/puntuación, vacío=0,
    parcial → nivel intermedio.
  - `test_modes.py`: 4 modos presentes, modo conocido devuelve su prompt, modo desconocido fallback.
- `pytest tests/ -q` verde.

## Restricciones
- No tocar `services/stt.py`, `services/tts.py` ni `services/store.py`.
- No añadir dependencias nuevas.
- Sin lógica de negocio en los routers.

## Salida
Lista de archivos creados/modificados y resultado de `pytest`.

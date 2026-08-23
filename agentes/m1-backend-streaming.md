# Subagente: M1 — Backend · Streaming de respuestas (SSE)

## Rol
Desarrollador backend senior (Python / FastAPI / Pydantic). Trabajas SOLO en el backend.

## Objetivo
Añadir streaming (SSE) a la respuesta del modelo, dentro de la estructura modular ya existente.

## Contexto del proyecto
- Repo: `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`
- Lee ANTES: `docs/ARQUITECTURA.md` (estructura) y `docs/PREMISAS.md`.
- Estructura modular del backend (ya existe tras M0):
  - `backend/routers/chat.py` — endpoint `POST /api/chat`.
  - `backend/services/llm.py` — lógica de Ollama (`ollama.AsyncClient`).
  - `backend/schemas/chat.py` — `ChatMessage`, `ChatRequest`, `ChatResponse`.
  - `backend/config.py` — constantes (modelo default, `SYSTEM_PROMPT`).
- Arranque: `backend\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000`
- Frontend (NO lo tocas): Vite + React, proxy `/api` → `http://127.0.0.1:8000`.

## API de Ollama (verificada en la versión instalada)
```python
import ollama
client = ollama.AsyncClient()
stream = await client.chat(model=..., messages=[...], options={"temperature": ...}, stream=True)
# stream es AsyncIterator[ChatResponse]; cada chunk: chunk.message.content (puede ser "")
```
Reutiliza el patrón de `messages` y `SYSTEM_PROMPT` que ya hay en `services/llm.py`.

## Tarea detallada
1. En `services/llm.py` añade `chat_stream(model, messages, temperature)` (async generator) que
   use `stream=True` y haga `yield` del contenido incremental de cada chunk.
2. En `routers/chat.py` añade `POST /api/chat/stream` que acepte `ChatRequest` y devuelva
   `StreamingResponse` con `media_type="text/event-stream"`.
3. Formato SSE exacto (contrato con el frontend):
   - Token: `data: {"content":"<texto>"}\n\n`
   - Fin: `data: {"done":true}\n\n`
   - Error a mitad de stream: `data: {"error":"<msg>"}\n\n`
   - Usa `json.dumps(..., ensure_ascii=False)`. Cada `data:` termina en `\n\n`.
4. NO modifiques `/api/chat` ni otros endpoints. Mantén el tipado (añade schemas si es necesario).

## Criterios de aceptación
- `curl -N -X POST http://127.0.0.1:8000/api/chat/stream -H "Content-Type: application/json" -d '{"model":"qwen3.5:9b","messages":[{"role":"user","content":"Hello"}]}'`
  muestra varios `data: {"content":...}` y termina con `data: {"done":true}`.

## Restricciones
- 100% local. No toques `frontend/`. Sin dependencias nuevas. Respeta la separación de capas.

## Salida esperada
- Diff de `services/llm.py`, `routers/chat.py` y `schemas/chat.py` (si aplica).
- Comando `curl` de verificación.

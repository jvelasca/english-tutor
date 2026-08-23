# Subagente: M0 — Esqueleto modular (refactor sin cambios de comportamiento)

## Rol
Desarrollador full-stack senior. Refactoriza backend (Python/FastAPI) y frontend (React/TS)
para dejar el proyecto **modular**, SIN cambiar ninguna funcionalidad.

## Objetivo
Reorganizar el código actual en la estructura definida en `docs/ARQUITECTURA.md`, manteniendo
exactamente el mismo comportamiento. Al terminar, la app debe seguir funcionando igual.

## Contexto
- Repo: `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`
- Lee ANTES de tocar nada: `docs/ARQUITECTURA.md`, `docs/PREMISAS.md`, `docs/DESARROLLO.md`.
- Estado actual (plano):
  - Backend: `backend/main.py` (endpoints + lógica) y `backend/schemas.py`.
  - Frontend: `frontend/src/App.tsx` (todo el chat) y `frontend/src/index.css`.

## Tarea detallada — Backend
Reorganiza en:
```
backend/
├── main.py          # solo crea la app y monta routers
├── config.py        # constantes (modelo default, SYSTEM_PROMPT, URL Ollama)
├── routers/
│   ├── __init__.py
│   ├── chat.py      # POST /api/chat
│   └── models.py    # GET /api/health, GET /api/models
├── schemas/
│   ├── __init__.py  # re-exporta ChatMessage, ChatRequest, ChatResponse
│   └── chat.py      # los 3 modelos Pydantic actuales
└── services/
    ├── __init__.py
    └── llm.py       # función chat_once(model, messages, temperature) que usa ollama.AsyncClient
```
Reglas:
- La lógica de Ollama vive en `services/llm.py`; los routers solo validan y llaman.
- `SYSTEM_PROMPT` va en `config.py` (o en `services/llm.py` si lo prefieres); no en el router.
- Mantén el tipado Pydantic idéntico.
- NO añadas endpoints nuevos. NO cambies el formato de respuesta.

## Tarea detallada — Frontend
Reorganiza en:
```
frontend/src/
├── main.tsx
├── App.tsx           # orquesta; mínimo estado
├── api/
│   ├── client.ts     # fetch JSON base
│   └── chat.ts       # getModels(), sendChat(messages, model)
├── components/
│   ├── ChatMessage.tsx
│   └── Composer.tsx
├── hooks/
│   └── useChat.ts    # estado: messages, input, loading, model, models + send()
├── types/
│   └── api.ts        # Role, Message, ChatResponse
└── index.css
```
Reglas:
- `useChat` concentra TODO el estado y la lógica de envío; `App.tsx` solo compone.
- `api/chat.ts` es el único sitio con `fetch("/api/...")`.
- Extrae el estado y lógica de `App.tsx` actual sin cambiar el comportamiento visual.
- Mantén los estilos iguales.

## Criterios de aceptación
- Backend arranca (`uvicorn main:app`) y `GET /api/health` y `POST /api/chat` responden igual.
- Frontend compila (`npx tsc --noEmit`) y `npm run dev` muestra el chat idéntico a antes.
- El diálogo con `qwen3.5:9b` sigue funcionando de punta a punta.

## Restricciones
- 100% local. Sin dependencias nuevas. Sin cambios de comportamiento ni de UI.
- No toques `agentes/`, `docs/`, `PLAN.md` ni `README.md` (salvo que detectes una ruta errónea).
- Si un archivo no encaja en la estructura, pregunta/decide documentándolo en la salida.

## Salida esperada
- Lista de archivos movidos/creados (antes → después).
- Diff completo de los archivos nuevos.
- Cómo verificaste que todo sigue funcionando.

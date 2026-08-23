# Subagente: M1 — Frontend · Consumir streaming (SSE)

## Rol
Desarrollador frontend senior (React + TypeScript). Trabajas SOLO en el frontend.

## Objetivo
Mostrar la respuesta del modelo **incrementalmente**, consumiendo `POST /api/chat/stream` (SSE).

## Contexto del proyecto
- Frontend en `frontend/`. Lee ANTES: `docs/ARQUITECTURA.md`.
- Estructura modular (ya existe tras M0):
  - `src/hooks/useChat.ts` — estado y lógica (`messages`, `input`, `loading`, `model`, `models`, `send()`).
  - `src/api/chat.ts` — único lugar con `fetch` (`getModels()`, `sendChat()`).
  - `src/components/` — `ChatMessage.tsx`, `Composer.tsx`.
  - `src/types/api.ts` — `Role`, `Message`, `ChatResponse`.
- Arranque: `npm run dev` (Vite `http://localhost:5173`, proxy `/api` ya configurado).

## Contrato de API (SSE)
`POST /api/chat/stream` con JSON `{ model, messages }` responde `text/event-stream`:
```
data: {"content":"texto incremental"}

data: {"done":true}
```
Puede venir `{"error":"..."}` en lugar de `done`. Es POST: usa `fetch` + `ReadableStream`
(NO `EventSource`, que solo soporta GET).

## Tarea detallada
1. En `src/api/chat.ts` añade `streamChat(messages, model, onDelta, onDone, onError)` que haga
   `fetch("/api/chat/stream")`, lea `res.body.getReader()` + `TextDecoder`, divida por líneas,
   detecte `data: ` y haga `JSON.parse`; llame `onDelta(content)` por token y `onDone()`/`onError(msg)`.
2. En `src/hooks/useChat.ts` modifica `send()` para usar `streamChat`: crea una burbuja `assistant`
   vacía y la va rellenando con cada `onDelta` (estado incremental).
3. El indicador "typing" se muestra solo hasta que llegue el primer token.
4. Mantén intacta la UI (selector de modelo, sugerencias, estilos) y el manejo de errores.

## Criterios de aceptación
- El texto aparece fragmento a fragmento, sin esperar la generación completa.
- El historial y el auto-scroll siguen funcionando.

## Restricciones
- TypeScript estricto (`noUnusedLocals`, `noUnusedParameters`), sin `any`. Sin dependencias nuevas.
- No toques `backend/`. Respeta la separación `api/` vs `hooks/` vs `components/`.

## Salida esperada
- Diff de `src/api/chat.ts`, `src/hooks/useChat.ts` (y `src/types/api.ts` si cambia).
- Nota de cómo lo probaste.

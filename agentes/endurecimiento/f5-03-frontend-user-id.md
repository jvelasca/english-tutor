# Subagente F5.3 — Frontend: propagar user_id al chat

## Rol
Programador frontend (React + TypeScript + Vitest). Sin acceso a Git ni al backend.

## Objetivo
Activar la personalización del tutor: que `streamChat`/`sendChat` envíen `user_id` al backend
para que `/api/chat` y `/api/chat/stream` inyecten el perfil del alumno al system prompt
(F5.2). El backend ya acepta `user_id` opcional (`null` = prompt base), así que este cambio es
aditivo y no rompe nada.

## Contexto (autocontenido)
- `frontend/src/api/chat.ts` (LEERLO): `sendChat(messages, model, mode)` y
  `streamChat(messages, model, mode, callbacks)`; el body actual NO lleva `user_id`.
- `frontend/src/hooks/useChat.ts` (LEERLO): `currentUserId` (string|null) y en `sendText` llama
  `await streamChat(history, model, mode, { onDelta, onDone, onError })`.
- `frontend/src/api/client.ts`: `postJson` y `fetch` global (mockeable con `vi.stubGlobal`).
- `frontend/src/types/api.ts`: `Message`, `TutorMode`, `ChatResponse`.
- `frontend/src/utils/sse.ts`: `parseSseLine` para líneas `data: {...}`.
- Patrón de test: `frontend/src/api/learning.test.ts` (mockea `fetch` y revisa `body`).
- Verificación (desde `frontend/`):
  ```powershell
  npm run build
  npx tsc --noEmit
  npx vitest run
  ```

## Tarea detallada

### 1. `frontend/src/api/chat.ts`
Añade `userId?: string | null` a ambas funciones y envía `user_id: userId ?? null` en el body:
```ts
export function sendChat(
  messages: Message[],
  model: string,
  mode: TutorMode,
  userId?: string | null,
): Promise<ChatResponse> {
  return postJson<ChatResponse>("/api/chat", {
    model,
    messages,
    mode,
    user_id: userId ?? null,
  });
}
```
Y en `streamChat(..., callbacks, userId?)` añade `user_id: userId ?? null` al `JSON.stringify`.

### 2. `frontend/src/hooks/useChat.ts`
En `sendText`, pasa `currentUserId` como 5º argumento de `streamChat`:
`await streamChat(history, model, mode, { ...callbacks }, currentUserId);`

### 3. Test nuevo `frontend/src/api/chat.test.ts`
- `sendChat incluye user_id en el body` (mock fetch, aserta `body.user_id === "u1"`).
- `sendChat manda user_id null cuando no hay usuario`.
- `streamChat incluye user_id en el body` (mock fetch con `res.body.getReader()` y chunk SSE;
  aserta `body.user_id === "u1"`, `onDelta("Hi")` y `onDone()`).

## Criterios de aceptación
- `npm run build` OK.
- `npx tsc --noEmit` OK.
- `npx vitest run` **verde: 51 tests** (48 previos + 3 nuevos).

## Restricciones
- NO tocar el backend.
- NO cambiar la lógica de `sendText` salvo pasar `currentUserId`.
- Mantener estilo TypeScript existente.

## Salida
Lista de archivos creados/modificados, salida de `npx tsc --noEmit`, de `npx vitest run`, de
`npm run build`, y cualquier desviación.

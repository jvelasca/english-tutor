# Subagente E3.2 — Frontend: mensajes con id estable (append-only)

## Rol
Programador frontend React + TypeScript. Sin acceso a Git ni al backend.

## Objetivo
El backend ya guarda mensajes en modo **append-only**: si un mensaje trae `id`, se inserta
solo si no existe; si no trae `id`, reemplaza todo (legacy). El frontend todavía **no genera
`id`**, así que cada guardado sigue usando el path legacy (borrar y reinsertar). Hay que hacer
que `useChat` genere un `id` estable (`crypto.randomUUID()`) para cada mensaje de usuario y de
asistente, añadir `id` al tipo `Message`, y propagarlo en la persistencia.

## Contexto (autocontenido)
- `frontend/src/types/api.ts`: define `interface Message { role: Role; content: string; mode?: TutorMode; }`.
  El backend (`backend/schemas/chat.py`) ya devuelve un campo `id` opcional por mensaje
  (`id: str | None = None`). El tipo `Message` debe ganar `id?: string`.
- `frontend/src/hooks/useChat.ts` (LEERLO): `sendText` construye el mensaje de usuario como
  `{ role: "user", content: trimmed, mode }`, lo acumula en `history`, y al final persiste con
  `persist(cid, [...history, { role: "assistant", content: assistantReply, mode }])`. También hay
  dos ramas de error (`onError` y `catch`) que añaden mensajes de asistente.
- `frontend/src/api/conversations.ts`: `saveConversation(id, userId, title, messages)` ya envía
  `messages` tal cual en el body; no hay que tocarlo.
- `frontend/src/components/ChatMessage.tsx` y `App.tsx`: renderizan `message.content`. En
  `App.tsx` los mensajes usan `key={i}` (índice). Añadir `id` no rompe nada.

## Tarea detallada

### 1. `frontend/src/types/api.ts`
Añadir `id` opcional a `Message`:
```typescript
export interface Message {
  id?: string;
  role: Role;
  content: string;
  mode?: TutorMode;
}
```

### 2. `frontend/src/hooks/useChat.ts` — generar ids estables
Usa `crypto.randomUUID()` (disponible en navegadores modernos y Node 16.7+). Cambios concretos:

**(a) Mensaje de usuario** — en `sendText`, donde hoy se hace:
```typescript
      const history: Message[] = [
        ...messages,
        { role: "user", content: trimmed, mode },
      ];
```
pasa a:
```typescript
      const history: Message[] = [
        ...messages,
        { id: crypto.randomUUID(), role: "user", content: trimmed, mode },
      ];
```

**(b) Mensaje de asistente (streaming)** — justo antes de `let assistantReply = "";`
(después de `setLoading(true)`), genera **un único** id para el mensaje del asistente:
```typescript
      const assistantId = crypto.randomUUID();
      let assistantReply = "";
      let errored = false;
```
Y en el callback `onDelta`, el bloque que actualiza el último mensaje de asistente debe
preservar ese id. Sustituye las dos ramas por versiones que incluyan `id: assistantId`:
```typescript
          onDelta: (content) => {
            assistantReply += content;
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === "assistant") {
                next[next.length - 1] = {
                  id: assistantId,
                  role: "assistant",
                  content: last.content + content,
                  mode,
                };
              } else {
                next.push({ id: assistantId, role: "assistant", content, mode });
              }
              return next;
            });
          },
```

**(c) Persistencia final** — en el bloque que guarda tras el streaming:
```typescript
      if (assistantReply && !errored) {
        void persist(cid, [
          ...history,
          { id: assistantId, role: "assistant", content: assistantReply, mode },
        ]);
      }
```

**(d) Mensajes de error** — las dos ramas de error añaden un mensaje de asistente; dales un
`id` propio (no reutilices `assistantId`, porque puede haber errores tanto en `onError` como en
`catch`, y cada mensaje debe ser único):
- En `onError`:
```typescript
            setMessages((prev) => [
              ...prev,
              { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
            ]);
```
- En `catch`:
```typescript
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
        ]);
```

> Nota: los mensajes de error no se persisten (la persistencia solo corre si `!errored`), pero
> deben llevar `id` para que el tipo sea coherente y no se reutilice el índice como clave.

**(e) Opcional pero recomendado** — en `App.tsx`, cambia la clave de renderizado de mensajes de
índice a id para que React no reordene mal al hacer append:
```tsx
          {messages.map((m) => (
            <ChatMessage key={m.id ?? `${m.role}-${m.content}`} message={m} />
          ))}
```
Si prefieres no tocar `App.tsx`, no es obligatorio; el append-only del backend ya es correcto
con solo los cambios de `useChat.ts` y `types/api.ts`.

## Verificación obligatoria (desde `frontend/`)
```powershell
npm run build     # tsc && vite build: sin errores de tipos
npm test          # vitest run: los 40 tests siguen verdes
```
Los tests existentes de `api/conversations.test.ts` usan mensajes literales sin `id` y **no
deben cambiar** (siguen pasando porque `id` es opcional).

## Criterios de aceptación
- `npm run build` sin errores de TypeScript.
- `npm test` verde (40 tests).
- `useChat` genera un `id` estable para el mensaje de usuario y uno para el de asistente, y los
  propaga en `persist`. Al recargar una conversación y enviar un mensaje nuevo, el backend
  recibe todos los mensajes con `id` (append-only), no el path legacy.

## Restricciones
- NO tocar el backend ni `api/conversations.ts` (ya envía `messages` correctamente).
- NO cambiar la firma pública de `useChat` (sigue devolviendo `sendText`, `persist`, etc.).
- NO introducir dependencias nuevas. `crypto.randomUUID()` es nativo.
- Mantener el estilo (comillas, `type` imports) del proyecto.

## Salida
Lista de archivos modificados (resumen por archivo), la salida de `npm run build` y de
`npm test`, y cualquier desviación.

# Subagente E1.2 — Frontend: propagar user_id en conversaciones y pronunciación

## Rol
Programador frontend (Vite + React + TypeScript, modo estricto). Sin acceso a Git ni al backend.

## Objetivo
Cerrar el "par de contrato" del aislamiento multiusuario. El backend (E1.1, ya hecho) ahora
**exige** `user_id` en `GET/PUT/DELETE /api/conversations/{cid}` y en `POST /api/pronunciation`.
Este subagente actualiza el cliente HTTP y el hook para **enviar siempre `user_id`**, de modo
que cargar/guardar/borrar conversaciones y registrar pronunciación sigan funcionando y queden
aislados por perfil.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (premisas 5, 8, 12, 13) y `docs/ARQUITECTURA.md`.
- Estructura frontend (`frontend/src/`): `api/` = único lugar con `fetch`; `components/` =
  presentación (reciben props); `hooks/` = estado y llamadas a `api/`; `types/` = tipos.
- Archivos a tocar (LEERLOS antes de editar, no asumas su contenido):
  - `frontend/src/api/conversations.ts` — `createConversation`/`listConversations` ya envían
    `user_id` vía `URLSearchParams`; `getConversation`/`saveConversation`/`deleteConversation`
    **no** lo envían.
  - `frontend/src/api/pronunciation.ts` — `checkPronunciation(blob, expected, userId?)` con
    `userId` opcional (solo lo añade al FormData si existe).
  - `frontend/src/hooks/useChat.ts` — `loadConversation(id)`, `removeConversation(id)`,
    `persist(id, history)` llaman a las funciones anteriores sin `user_id`. Existe
    `currentUserId` en el scope del hook.
  - `frontend/src/components/PronunciationPractice.tsx` — recibe `userId: string | null`.
- Tests: vitest con `environment: "node"` (`frontend/vitest.config.ts`), `include: src/**/*.test.ts`.
  Estilo de import: `import { describe, expect, it, vi } from "vitest"`.
- Verificación (desde `frontend/`):
  ```powershell
  npx tsc --noEmit
  npm test
  npm run build
  ```

## Tarea detallada

### 1. `api/conversations.ts`
Añadir `userId: string` a las tres funciones y construir la URL con `URLSearchParams`
(mismo estilo que `createConversation`/`listConversations`):
- `getConversation(id: string, userId: string)` →
  `getJson(`/api/conversations/${id}?${new URLSearchParams({ user_id: userId })}`)`.
- `saveConversation(id: string, userId: string, title: string, messages: Message[])` →
  `putJson(`/api/conversations/${id}?${query}`, { title, messages })`.
- `deleteConversation(id: string, userId: string)` →
  `deleteJson(`/api/conversations/${id}?${query}`)`.

### 2. `api/pronunciation.ts`
- `checkPronunciation(blob: Blob, expected: string, userId: string)` — `userId` **obligatorio**.
- Añadir siempre `form.append("user_id", userId)` (quitar el `if (userId)`).

### 3. `hooks/useChat.ts`
- `loadConversation(id)`: llamar `getConversation(id, currentUserId)`; añadir guard
  `if (!currentUserId) return;` al inicio; añadir `currentUserId` al array de deps.
- `removeConversation(id)`: `deleteConversation(id, currentUserId)`; añadir `currentUserId` a deps.
- `persist(id, history)`: `saveConversation(id, currentUserId, deriveTitle(history), history)`;
  añadir `currentUserId` a deps.

### 4. `components/PronunciationPractice.tsx`
- Mantener prop `userId: string | null`.
- En el handler que evalúa (dentro de `recorder.onstop`), antes de llamar a
  `checkPronunciation`, añadir `if (!userId) return;` (y no llamar si es null).
- Cambiar la llamada a `checkPronunciation(blob, sentence, userId)`.
- (Opcional, recomendado) `disabled={processing || !userId}` en el botón de grabar.

### 5. Test nuevo: `frontend/src/api/conversations.test.ts`
Mockea `fetch` global y verifica las URLs y métodos. Usa este patrón (robusto, sin depender
de la aridad exacta de los argumentos):

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteConversation, getConversation, saveConversation } from "./conversations";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("conversations api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getConversation llama con user_id en la query", async () => {
    const fn = mockFetch(true, { id: "c1", messages: [] });
    await getConversation("c1", "u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
  });

  it("saveConversation usa PUT con el body correcto", async () => {
    const fn = mockFetch(true, { id: "c1", title: "T", messages: [] });
    await saveConversation("c1", "u1", "T", [{ role: "user", content: "hi" }]);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({
      title: "T",
      messages: [{ role: "user", content: "hi" }],
    });
  });

  it("deleteConversation usa DELETE con user_id", async () => {
    const fn = mockFetch(true, { ok: true });
    await deleteConversation("c1", "u1");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
    expect(init.method).toBe("DELETE");
  });
});
```

(Ajusta solo si el `fetch` real se llama con argumentos distintos; inspecciona
`fn.mock.calls` en vez de asumir aridad.)

## Criterios de aceptación
- `npx tsc --noEmit` sin errores.
- `npm test` verde (incluye los nuevos tests de `api/conversations`).
- `npm run build` OK.

## Restricciones
- NO tocar el backend ni `frontend/src/types/api.ts` salvo si `tsc` lo exige.
- NO tocar otros componentes/hooks no listados.
- NO añadir dependencias.
- Mantener estilo del repo: `api/` es la única capa que hace `fetch`; los componentes no hacen fetch.
- `checkPronunciation` ahora exige `userId`; NO dejar llamadas con `userId` opcional/undefined.

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`npx tsc --noEmit`, `npm test` y `npm run build`.

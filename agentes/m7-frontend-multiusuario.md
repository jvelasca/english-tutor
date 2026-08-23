# Subagente M7 — Frontend: multi-usuario (selector de perfil + conversaciones por usuario)

## Rol
Programador frontend React + TypeScript (Vite). Sin acceso a Git ni al backend.

## Objetivo
Añadir **selección simple de perfil de usuario** al abrir la app y aislar las
conversaciones por usuario (premisa 13). Todo local, sin cuentas en la nube.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (leer premisas 2, 8, 12, 13).
- Estructura y responsabilidades: `docs/ARQUITECTURA.md`.
  - `src/api/` = única capa que habla con el backend (fetch).
  - `src/hooks/` = estado y lógica de UI.
  - `src/components/` = presentación pura (reciben props, no hacen fetch).
  - `src/types/` = tipos espejo de los schemas del backend.
- Archivos actuales (leer antes de tocar):
  - `src/types/api.ts`: define `ConversationMeta` (id, title, created_at, updated_at),
    `Conversation`, `Message`, `TutorMode`, etc.
  - `src/api/client.ts`: `getJson`, `postJson`, `putJson`, `deleteJson`.
  - `src/api/conversations.ts`: `createConversation`, `listConversations`,
    `getConversation`, `saveConversation`, `deleteConversation` (hoy sin usuario).
  - `src/hooks/useChat.ts`: estado `conversations`, `conversationId`, y funciones
    `newConversation`, `loadConversation`, `removeConversation`, `refreshConversations`,
    `persist`.
  - `src/components/Sidebar.tsx`: lista de conversaciones + botón "Nuevo chat".
  - `src/App.tsx`: orquesta todo; cabecera con `ModeSelect` y selector de modelo.

## API del backend (contrato fijado por el subagente backend; usar estas rutas)
- `GET /api/users` → `User[]` (cada `User`: `id`, `name`, `created_at`).
- `POST /api/users` con `{ name }` → `User`.
- `GET /api/conversations?user_id=<id>` → `ConversationMeta[]`.
- `POST /api/conversations?user_id=<id>` → `ConversationMeta`.
- `GET/PUT/DELETE /api/conversations/{cid}` → sin cambios.
- `ConversationMeta` ahora incluye `user_id`.

## Tarea
1. **Tipos** en `src/types/api.ts`:
   - `export interface User { id: string; name: string; created_at: string; }`.
   - Añadir `user_id: string` a `ConversationMeta`.
2. **Cliente** nuevo `src/api/users.ts`:
   - `listUsers(): Promise<User[]>` → `GET /api/users`.
   - `createUser(name: string): Promise<User>` → `POST /api/users`.
3. **Cliente de conversaciones** `src/api/conversations.ts`:
   - `createConversation(userId: string)` → `POST /api/conversations?user_id=${userId}`.
   - `listConversations(userId: string)` → `GET /api/conversations?user_id=${userId}`.
   - El resto (`getConversation`, `saveConversation`, `deleteConversation`) sin cambios.
   - Usar `URLSearchParams` o template string limpio para el query param.
4. **Hook** `src/hooks/useChat.ts`:
   - Añadir estado `users: User[]` y `currentUserId: string | null`.
   - Al montar: `listUsers()`; si hay usuarios, seleccionar el primero; si no, crear
     uno por defecto (`createUser("Usuario")`) y seleccionarlo.
   - `refreshConversations` ahora usa `currentUserId`.
   - `newConversation`, `persist` y `removeConversation` usan `currentUserId`.
   - Al cambiar de usuario: recargar conversaciones y resetear `conversationId` y
     `messages` (nada de un usuario debe verse desde otro).
   - Exponer `users`, `currentUserId` y una función `selectUser(uid)` (y opcionalmente
     `addUser(name)`).
5. **Componente** nuevo `src/components/UserSelect.tsx` (presentación pura):
   - Recibe `users`, `currentUserId`, `onSelect(uid)`.
   - Selector de perfil (dropdown) + opción de añadir usuario (input + botón).
   - Recibe también `onAdd(name)` si implementas la creación inline.
6. **Integración** en `src/App.tsx`: colocar `UserSelect` en la cabecera (o junto al
   `ModeSelect`) y cablear props desde el hook.

## Criterios de aceptación
- `npm test` (vitest) verde y `npx tsc --noEmit` sin errores.
- Añadir un test de utilidad pura si introduces lógica (p. ej. filtro/derivación de
  lista de usuarios); si no, al menos mantener los tests existentes verdes.
- `npm run build` (o `tsc -b`) no debe romper.

## Restricciones
- No tocar la capa de streaming/chat (`src/api/chat.ts`), voz ni pronunciación.
- Mantener los componentes como presentación pura (sin `fetch` dentro).
- Tipado fuerte: nada de `any`. Usar los tipos de `src/types/api.ts`.
- No añadir dependencias nuevas de npm.

## Salida
Lista de archivos creados/modificados y resultado de `npm test` y `npx tsc --noEmit`.

# Subagente M9 (frontend) — Seguimiento de progreso del alumno

## Rol
Desarrollador frontend (Vite + React + TypeScript, modo estricto). Sin acceso a Git.
No necesitas red: consumes la API local (contrato fijo más abajo) y los tests son vitest.

## Objetivo
Mostrar un **resumen del progreso del alumno** (nº de ejercicios, correcciones y
puntuaciones de pronunciación) en el frontend, por usuario. Issue de GitHub #2.

## Contexto (autocontenido)
- Frontend en `frontend/src/` (ver `docs/ARQUITECTURA.md`): `api/` (única capa con `fetch`),
  `components/` (presentación pura), `hooks/` (estado), `types/` (espejo del backend).
- Cliente HTTP base en `frontend/src/api/client.ts` (`getJson`, `postJson`, `putJson`,
  `deleteJson`).
- El estado de usuario vive en `frontend/src/hooks/useChat.ts` (`currentUserId`, `users`,
  `selectUser`). Al cambiar de usuario se resetea conversación y mensajes.
- `frontend/src/components/PronunciationPractice.tsx` graba audio y llama a
  `checkPronunciation(blob, sentence)` desde `frontend/src/api/pronunciation.ts`.
  **Hoy no conoce el usuario y no refresca progreso.**
- `frontend/src/App.tsx` orquesta: cabecera con `UserSelect`/`ModeSelect`/selector de modelo/
  `ThemeToggle`, área de chat, `Composer` y `PronunciationPractice` cuando `mode ===
  "pronunciation"`.
- Sistema de diseño (M8) con tokens en `index.css` (`--color-*`, `--space-*`, `--radius-*`,
  `--shadow-*`) y tema claro/oscuro. Respeta las clases y tokens existentes.

## Contrato (API del backend, ya fijado) — código contra esto
### `GET /api/progress?user_id=<id>` → `ProgressSummary`
```json
{
  "user_id": "<id>",
  "conversations": 3,
  "messages": 42,
  "exercises": 5,
  "corrections": 7,
  "pronunciation": {
    "attempts": 10,
    "best": 95,
    "average": 82.5,
    "last_score": 88,
    "last_level": "good"
  }
}
```
### `POST /api/pronunciation` (multipart: `file`, `expected`, `language`, y `user_id` opcional)
Sigue devolviendo `PronunciationResponse` (`{expected, heard, score, level, ok}`).

## Tarea
1. `frontend/src/types/api.ts`:
   - Añadir `mode?: TutorMode` a `Message`.
   - Añadir `PronunciationStats` y `ProgressSummary` (espejo del contrato).
2. `frontend/src/api/progress.ts` (nuevo): `getProgress(userId: string): Promise<ProgressSummary>`
   usando `getJson` con query `user_id`.
3. `frontend/src/api/pronunciation.ts`: `checkPronunciation(blob, expected, userId?)` → añade
   `user_id` al `FormData` solo si viene `userId`.
4. `frontend/src/components/ProgressSummary.tsx` (nuevo): componente de presentación pura que
   recibe `progress: ProgressSummary | null` por props y muestra:
   - Conversaciones y mensajes totales.
   - Ejercicios y correcciones.
   - Pronunciación: intentos, mejor puntuación, media (y última puntuación/nivel si existe).
   - Estado vacío elegante si `progress` es `null` (sin datos aún).
   - Usa los tokens de diseño y tema existentes; no hagas `fetch` aquí.
5. `frontend/src/hooks/useChat.ts`:
   - Estado `progress: ProgressSummary | null` + `refreshProgress`.
   - Cargar progreso cuando hay `currentUserId` (y refrescar al cambiar de usuario).
   - En `send`/`persist`, adjuntar `mode` a los mensajes que se guardan (para que el backend
     cuente ejercicios/correcciones). El `mode` actual ya está en el hook.
6. `frontend/src/components/PronunciationPractice.tsx`:
   - Recibir `userId: string | null` por props y pasarlo a `checkPronunciation`.
   - Tras evaluar, llamar a una callback `onAttempt` (o `refreshProgress`) para refrescar.
7. `frontend/src/App.tsx`:
   - Obtener `progress` y `refreshProgress` de `useChat`.
   - Renderizar `ProgressSummary` (sugerencia: dentro del sidebar o como panel colapsable;
     mantén la estética M8).
   - Pasar `currentUserId` a `PronunciationPractice` y `onAttempt={refreshProgress}`.
8. Tests (vitest): tests de `utils`/`api` que sean puros y deterministas (p. ej. un helper de
   formato de `ProgressSummary`, o mock de `getProgress`). No dependen de red.

## Criterios de aceptación
- `npx tsc --noEmit` sin errores.
- `npm test` verde.
- `npm run build` OK.
- Al cambiar de usuario, el panel de progreso se refresca y muestra los datos correctos.
- Grabar una pronunciación actualiza el panel (vía `refreshProgress`).

## Restricciones
- No hacer `fetch` fuera de `api/`.
- No tocar `api/chat.ts`, `api/conversations.ts`, `api/users.ts` salvo lo estrictamente
  necesario (solo `api/pronunciation.ts` cambia para `user_id`).
- No actualizar `docs/`, `PLAN.md`, `README.md`, `RELEVO.md` ni `agentes/` (lo hace el gerente).
- Mantener tipado fuerte y modo estricto; no usar `any`.

## Salida
- Lista de archivos creados/modificados.
- Resumen de decisiones de UI (dónde va el panel, estados vacíos).
- Confirmación de `tsc --noEmit` + `npm test` verdes.

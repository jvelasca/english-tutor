# Subagente M4 — Frontend: selector de modo + práctica de pronunciación

## Rol
Programador frontend React + TypeScript (Vite). Sin acceso a Git ni al backend.

## Objetivo
Añadir al frontend la interfaz del "modo profesor":
1. **Selector de modo** de tutor en la cabecera.
2. **Tarjeta de práctica de pronunciación** (grabar → evaluar contra el backend).

## Contexto (autocontenido)
- Estructura y responsabilidades en `docs/ARQUITECTURA.md`:
  - `api/` = única capa que habla con el backend. `components/` = presentación pura.
  - `hooks/` = estado/lógica de UI. `utils/` = funciones puras testables. `types/` = tipos.
- `types/api.ts` define `Message`, `ChatResponse`, etc.
- `api/chat.ts` tiene `streamChat(messages, model, callbacks)`. `hooks/useChat.ts` guarda
  `model` y `messages`. `App.tsx` renderiza cabecera + `Composer` + `ChatMessage`.
- Backend expone: `POST /api/chat/stream` acepta `{model, messages, mode}`; y
  `POST /api/pronunciation` (multipart: `file`, `expected`, `language`) → `PronunciationResponse`.

## Tarea
1. `types/api.ts`: añadir `TutorMode` (`conversation`|`grammar`|`exercises`|`pronunciation`)
   y `PronunciationResponse` (expected, heard, score, level, ok).
2. `utils/modes.ts`: `MODES` (lista de los 4 modos con etiqueta) e `isTutorMode(value)`.
3. `api/chat.ts`: `streamChat` y `sendChat` aceptan y envían `mode`.
4. `api/pronunciation.ts`: `checkPronunciation(blob, expected)` → POST multipart → `PronunciationResponse`.
5. `hooks/useChat.ts`: estado `mode` (default `conversation`) y `setMode`; pasar `mode` a `streamChat`.
6. `components/ModeSelect.tsx`: `<select>` con los 4 modos (props `value`/`onChange`).
7. `components/PronunciationPractice.tsx`: 3 frases de ejemplo, botón grabar/detener
   (`MediaRecorder` + `getUserMedia`), muestra resultado (score/nivel) al terminar.
8. `App.tsx`: mostrar `ModeSelect` en la cabecera; mostrar `PronunciationPractice` cuando
   `mode === "pronunciation"`.
9. `index.css`: estilos para `.header-controls`, `.mode-select` y los de pronunciación.

## Criterios de aceptación
- `npx tsc --noEmit` sin errores.
- Test nuevo (vitest, determinista): `utils/modes.test.ts` (4 modos + `isTutorMode`).
- `npm test` verde.

## Restricciones
- No hacer `fetch` en componentes: toda llamada a red va en `api/`.
- No tocar `utils/sse.ts`, `utils/title.ts` ni sus tests.

## Salida
Lista de archivos creados/modificados y resultado de `tsc` + `npm test`.

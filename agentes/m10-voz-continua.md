# Subagente M10 (frontend) — Conversación por voz continua (manos libres)

## Rol
Desarrollador frontend (Vite + React + TypeScript, modo estricto). Sin acceso a Git.
No tocas el backend: los endpoints que necesitas ya existen y funcionan.

## Objetivo
Añadir un **modo de conversación por voz continua**: el usuario activa el modo, habla, el
sistema detecta el final del habla (silencio), transcribe automáticamente, genera la
respuesta y la lee en voz alta, y vuelve a escuchar. Sin pulsar botones en el flujo normal.
Issue de GitHub #3.

## Contexto (autocontenido)
- Frontend en `frontend/src/` (ver `docs/ARQUITECTURA.md`): `api/` (única capa con `fetch`),
  `components/` (presentación pura), `hooks/` (estado), `utils/` (puro y testable),
  `types/` (espejo del backend).
- **Endpoints backend YA DISPONIBLES (no los toques):**
  - `POST /api/transcribe` (multipart `file`, `language`) → `{ text }`. Cliente:
    `frontend/src/api/voz.ts` → `transcribe(blob)`.
  - `POST /api/tts` (`{ text }`) → audio/wav. Cliente: `frontend/src/api/voz.ts` → `speak(text)`
    (reproduce y resuelve al terminar).
  - `POST /api/chat/stream` (SSE). Cliente: `frontend/src/api/chat.ts` → `streamChat(...)`.
- Estado de chat en `frontend/src/hooks/useChat.ts` (`send`, `mode`, `model`, `loading`,
  `currentUserId`, `messages`, `conversationId`, `persist`).
- `frontend/src/components/Composer.tsx` usa `MicButton` (push-to-talk) + textarea + botón
  enviar. `App.tsx` orquesta cabecera (`header-controls`: UserSelect, ModeSelect, model-select,
  ThemeToggle), `ProgressSummary`, chat y `Composer`.
- Sistema de diseño M8 con tokens en `index.css` (tema claro/oscuro, `--color-*`,
  `--space-*`, `--radius-*`, `--duration-*`, `--ease-out`). Respétalos y respeta
  `prefers-reduced-motion` y a11y (`aria-*`, `:focus-visible`).

## Contrato interno (cómo integrar con el chat)
Debes **refactorizar `useChat`** para exponer una función reutilizable:

```ts
// hooks/useChat.ts
const sendText = useCallback(async (text: string): Promise<string> => {
  // guard: si !text.trim() || loading || !currentUserId → return "";
  // crea conversación si no hay conversationId (igual que hoy)
  // construye history, setMessages, setLoading(true)
  // await streamChat(...) acumulando assistantReply y actualizando mensajes
  // persiste si assistantReply && !errored
  // devuelve assistantReply (o "" si hubo error)
}, [deps]);
```

- El `send` actual (usado por `Composer`) pasa a ser:
  `send = () => { const t = input.trim(); if (!t) return; setInput(""); void sendText(t); }`.
- Devuelve `sendText` en el objeto retornado por `useChat` (además de `send`).
- **No rompas** el comportamiento actual de `send` ni los tests existentes.

## Tarea
1. **Refactor `hooks/useChat.ts`**: añadir `sendText(text): Promise<string>` como arriba;
   `send` se apoya en él; exportar `sendText`. Asegurar que el mensaje del usuario lleva
   `mode` (como ya hace hoy) y que persiste igual que ahora.

2. **`utils/vad.ts` (nuevo, puro y testable)**: helpers sin dependencias del DOM:
   - `rms(samples: Float32Array | Uint8Array): number` → raíz cuadrática media (0..1 para
     Float32; para Uint8 (0..255) normaliza restando 128 y dividiendo entre 128).
   - Constantes exportadas: `SILENCE_THRESHOLD = 0.02`, `SILENCE_MS = 1200`,
     `MIN_SPEECH_MS = 300`, `MAX_CHUNK_MS = 15000`.
   - `shouldEndUtterance(speechDetected: boolean, silenceStartMs: number | null, nowMs: number): boolean`
     → true si `speechDetected` y el silencio lleva ≥ `SILENCE_MS`.
   - (Puedes añadir más helpers puros si simplifican el hook, p. ej. un reductor de estado.)

3. **`hooks/useHandsFree.ts` (nuevo)**: el bucle manos libres.
   - Firma sugerida: `useHandsFree(sendText: (t: string) => Promise<string>)` y devuelve
     `{ enabled, status, toggle, stop }`.
   - Estado: `enabled: boolean` y `status: "idle" | "listening" | "transcribing" |
     "thinking" | "speaking"`.
   - Al activar (`toggle`): pide `navigator.mediaDevices.getUserMedia({ audio: true })` **una
     sola vez** y mantiene el `MediaStream` vivo (no pares tracks por chunk, para no pedir
     permiso en cada turno ni producir eco). Crea `AudioContext` + `AnalyserNode`
     (`createMediaStreamSource(stream)`) para medir energía, y usa `MediaRecorder` por chunk.
   - **VAD:** con `requestAnimationFrame` (o `setInterval` ~50ms) lee `analyser.getByteTimeDomainData`
     y calcula `rms`. Marca `speechDetected` si `rms > SILENCE_THRESHOLD`. Cuando hay habla
     detectada y después silencio ≥ `SILENCE_MS` (usa `shouldEndUtterance`), paras el
     `MediaRecorder` del chunk y lo procesas.
   - **Procesado del chunk** (`status` transiciones):
     `listening` → (silencio) → `transcribing` (`transcribe(blob)`) → si texto no vacío →
     `thinking` (`await sendText(text)`) → si reply no vacío → `speaking` (`await speak(reply)`)
     → volver a `listening` (si `enabled` sigue true). Si el texto está vacío, volver a
     `listening` sin enviar.
   - **Cap de seguridad:** si un chunk supera `MAX_CHUNK_MS`, forzar stop y procesar.
   - **Limpieza:** al desactivar (`stop`), parar recorder, cerrar `AudioContext`, parar tracks
     del stream y resetear estado. El `speak` en curso termina de forma natural (no hace falta
     interrumpirlo en esta iteración).
   - **Barge-in / interrupción:** FUERA de alcance en esta iteración. No lo implementes.
   - Gestiona errores con `try/catch` y, en caso de error, vuelve a `idle`/`enabled=false` sin
     dejar el micrófono colgado (libera recursos).
   - **a11y:** el `AudioContext` debe crearse/`resume()` dentro de un gesto de usuario (el
     clic del toggle) para evitar problemas de autoplay.

4. **`components/HandsFreeToggle.tsx` (nuevo)**: presentación pura.
   - Props: `enabled: boolean`, `status: HandsFreeStatus`, `onToggle: () => void`.
   - Botón accesible (`aria-pressed={enabled}`, `aria-label`), con etiqueta "Manos libres"
     y un indicador de estado textual (Escuchando… / Transcribiendo… / Pensando… / Hablando…)
     visible cuando `enabled`. Usa tokens de `index.css` (colores de estado `--color-success`/
     `--color-accent`/`--color-warning`).
   - Sin `fetch`, sin lógica de audio (esa vive en el hook).

5. **`App.tsx`**: obtener `sendText` de `useChat`; instanciar `useHandsFree(sendText)`; añadir
   `HandsFreeToggle` en `header-controls` (junto a `ModeSelect`). Mantener el resto igual.

6. **`index.css`**: estilos del toggle y del indicador de estado (coherentes con el resto,
   responsive, tema claro/oscuro, `prefers-reduced-motion`).

7. **`utils/vad.test.ts` (nuevo)**: tests de `rms`, `shouldEndUtterance` y constantes. Rápidos
   y deterministas (sin DOM, sin red, sin audio real).

## Criterios de aceptación
- `npx tsc --noEmit` sin errores.
- `npm test` verde (los 6 tests existentes + los nuevos de `vad`).
- `npm run build` OK.
- El backend no se toca: `cd backend && .venv\Scripts\python.exe -c "import main"` sigue
  funcionando (no debes modificar `backend/`).
- El modo continuo hace el bucle completo en local: hablar → silencio → transcripción →
  respuesta → voz → vuelve a escuchar, sin pulsar botones (verifica manualmente si puedes).
- Hay botón visible para activar/parar y feedback de estado claro y accesible.

## Restricciones
- **No tocar el backend** (`backend/`), ni `api/chat.ts`, `api/conversations.ts`,
  `api/users.ts`, `api/progress.ts`. Solo `api/voz.ts` si es estrictamente necesario (y sin
  cambiar las firmas existentes `transcribe`/`speak`).
- No usar librerías externas (VAD 100% con Web Audio API nativa). Si necesitaras algo, debe
  ser local y documentado, pero para esta iteración NO añadas dependencias npm.
- No actualizar `docs/`, `PLAN.md`, `README.md`, `RELEVO.md` ni `agentes/` (lo hace el gerente).
- Tipado fuerte, modo estricto, sin `any`. Sin APIs en la nube (premisa 2).

## Salida
- Lista de archivos creados/modificados.
- Explicación del VAD (umbral, constantes, heurística) y del bucle de estados.
- Confirmación de `tsc --noEmit`, `npm test` y `npm run build` verdes.
- Nota de cualquier limitación conocida (p. ej. autoplay, calibración del umbral).

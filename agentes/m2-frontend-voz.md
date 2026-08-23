# Subagente: M2 — Frontend · Voz local (micro + reproducción)

## Rol
Desarrollador frontend senior (React + TypeScript). Trabajas SOLO en el frontend.

## Objetivo
Añadir control de voz:
- Botón **micrófono** que graba, transcribe y deja el texto en el input.
- Botón **altavoz** en cada respuesta para escucharla (TTS).

## Contexto del proyecto
- Frontend en `frontend/`. Lee ANTES: `docs/ARQUITECTURA.md`.
- Estructura modular (ya existe tras M0): `src/api/`, `src/components/`, `src/hooks/useChat.ts`, `src/types/`.
- Arranque: `npm run dev`. Backend expondrá:
  - `POST /api/transcribe` — `multipart/form-data` campo `file` → `{"text": "..."}`.
  - `POST /api/tts` — JSON `{"text": "..."}` → audio `audio/wav`.

## Tarea detallada
1. **`src/api/voz.ts`** (nuevo):
   - `transcribe(blob: Blob): Promise<string>` — `FormData` con campo `file` → POST `/api/transcribe`.
   - `speak(text: string): Promise<void>` — POST `/api/tts`, blob → `URL.createObjectURL` → `new Audio(url).play()`.
2. **`src/components/MicButton.tsx`** (nuevo): usa `MediaRecorder` + `getUserMedia({audio:true})`.
   - Al mantener pulsado graba (`audio/webm`), al soltar llama a `transcribe(blob)` y pasa el texto por prop `onTranscribed(text)`.
   - Estado visual: grabando (rojo/animación) y transcribiendo.
3. **`src/components/SpeakButton.tsx`** (nuevo): botón altavoz que llama a `speak(text)`. Desactivado mientras carga.
4. **Integración:** en `Composer.tsx` coloca `MicButton` a la izquierda del `textarea`; `onTranscribed` mete el
   texto en el input. En `ChatMessage.tsx` añade `SpeakButton` solo en mensajes del `assistant`.
5. Iconos SVG sencillos inline (micrófono/altavoz), sin librerías. Mantén el tema oscuro.

## Criterios de aceptación
- En Chrome/Edge: grabas, sueltas y el texto transcrito aparece en el input (sin enviarse solo).
- El altavoz de una respuesta la reproduce.
- El flujo de texto y streaming siguen igual.

## Restricciones
- TypeScript estricto, sin `any`. Sin dependencias nuevas.
- No toques `backend/`. Si el backend de voz no está listo, falla con gracia (mensaje claro, sin romper el resto).

## Salida esperada
- Diff de `src/api/voz.ts`, `src/components/*`, `src/hooks/useChat.ts`, `src/index.css`.
- Nota de cómo lo probaste en el navegador.

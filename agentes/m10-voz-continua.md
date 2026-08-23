# Subagente M10 — Conversación por voz continua (manos libres)

> Estado: **borrador de briefing** (no lanzar todavía; se lanza tras cerrar M5 y M9).

## Rol
Desarrollador full-stack de voz (frontend React + backend FastAPI). Sin acceso a Git.
Puede necesitar red SOLO para Ollama/Whisper/Piper locales, nunca APIs en la nube.

## Objetivo
Añadir un **modo de conversación por voz continua**: el usuario habla, el sistema detecta
el silencio (VAD), transcribe automáticamente, genera la respuesta y la lee en voz alta,
sin pulsar botones. Issue de GitHub #3.

## Contexto (autocontenido)
- Voz local ya implementada (M2):
  - STT: `backend/services/stt.py` (`faster-whisper`, `small`, CPU) expuesto en
    `POST /api/transcribe`.
  - TTS: `backend/services/tts.py` (`piper-tts`, `en_US-lessac-medium`, CPU) expuesto en
    `POST /api/tts`.
  - Frontend: `MicButton`/`Composer` graban con `MediaRecorder` y llaman a
    `api/voz.ts` (`transcribe`, `tts`). Push-to-talk actual: se pulsa para grabar/parar.
- Chat con streaming: `POST /api/chat/stream` (SSE) consumido por `api/chat.ts` (`streamChat`).
- Estado en `hooks/useChat.ts` (`send`, `mode`, `loading`, `currentUserId`).
- El sistema de diseño M8 usa tokens en `index.css`; respeta tema claro/oscuro y a11y
  (`prefers-reduced-motion`, `aria-*`).

## Alcance (primera iteración, minimal y robusta)
1. **VAD en el cliente (navegador)**: umbral de energía/amplitud vía Web Audio API para
   detectar el final del habla (silencio sostenido ~1.0–1.5 s) y el inicio (opcional).
   Sin librerías de nube; si se usa una librería local (p. ej. `@ricky0123/vad-web`) debe
   ser 100% local y compatible con el bundle de Vite.
2. **Bucle manos libres**: al activar el modo, el frontend graba → detecta silencio → corta
   el chunk → `transcribe` → alimenta `streamChat` → `tts` de la respuesta → reproduce audio
   → vuelve a escuchar. Con indicador visual de estado (escuchando / transcribiendo /
   hablando) y botón para pausar/detener el modo.
3. **Sin pulsar botones** para el flujo normal; el push-to-talk actual se mantiene como
   alternativa.
4. Opcional (si es simple): permitir **interrumpir** la locución si el usuario empieza a
   hablar (barge-in), cortando el audio en reproducción.

## Criterios de aceptación
- El modo continuo funciona de punta a punta en local: hablar → transcripción → respuesta →
  voz → vuelve a escuchar, sin tocar botones.
- `npx tsc --noEmit` y `npm test` verdes; `npm run build` OK.
- El backend no se rompe (`python -c "import main"`, `pytest tests/ -q` verdes).
- Hay botón visible para activar/pausar el modo y feedback de estado claro y accesible.
- Nada depende de APIs en la nube (premisa 2).

## Restricciones
- No tocar la lógica de scoring de pronunciación ni el CRUD de conversaciones.
- Si se añade una dependencia npm, debe ser local/offline y documentarse en `package.json`.
- No actualizar `docs/`, `PLAN.md`, `README.md`, `RELEVO.md` (lo hace el gerente).

## Salida
- Lista de archivos creados/modificados.
- Explicación del VAD elegido (umbral, parámetros) y del bucle de estados.
- Confirmación de tests y build verdes, y de prueba manual de punta a punta.

## Nota del gerente
Este hito es más grande que M9 y toca UX de voz en tiempo real. Se recomienda atacarlo en
subagentes separados (backend VAD/endpoints si procede + frontend bucle) una vez M5 y M9
estén integrados. Decisión final pendiente de la evaluación de M5.

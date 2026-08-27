# 37.3 (código) — Listening: ocultar escalera de velocidad en ítems `recorded`

## Rol
Subagente **frontend**: ajuste puntual en `ListeningPractice.tsx`.

## Contexto
- La **infraestructura** de audio humano ya está completa (manifest + resolución + servido +
  validación + CLI `backend/scripts/import_audio.py`). El **contenido** (WAV reales) lo aporta el
  usuario; este subagente **no** toca contenido ni inventa entradas en el manifest.
- `frontend/src/features/listening/ListeningPractice.tsx` muestra una escalera de velocidad
  slow/normal/fast cuando `question.audio_ready && question.variants.length > 1` (≈línea 352). Para
  ítems `recorded` (audio humano real) esa escalera es engañosa: su velocidad es la real, no
  sintetizable (Piper es lo único que puede variar velocidad).

## Objetivo
Ocultar la escalera de velocidad para ítems cuyo `audio_type` no es `"tts"` (en concreto `recorded`).

## Tarea
1. En `ListeningPractice.tsx`, condiciona el bloque de variantes de velocidad para que **solo** se
   muestre en ítems TTS (`question.audio_type === "tts"`). Mantén intacto el resto (botón play, meta
   de acento/wpm/duración, etiqueta de tipo de audio, opciones, resultado, stats, diagnóstico).
2. No cambies la lógica de reproducción ni ningún contrato/prop.

## Criterios de aceptación
- `npx tsc --noEmit` OK; `npm test` (vitest) OK; `npm run build` OK.
- La escalera slow/normal/fast no se muestra en ítems `recorded`.

## Restricciones
- Solo frontend. No `git commit`/`push`. No bump de versión ni edición de `CHANGELOG`/`RELEVO`
  (lo integra el gerente). Sin dependencias nuevas.

## Salida
- Diff del cambio y salida de `tsc` / `vitest` / `build` en verde.

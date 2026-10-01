# v3.28.0 — Listening Engine 4.0 (Fase 2): micro-flujo unificado, AudioController 4.0, bottom-up derivado, transcript con sync grueso y Shadowing 2.0

**V3.28 implementa los Bloques A–F de la Fase 2 de la especificación
`docs/LISTENING_ENGINE_4.0.md` (§14) a través del plan
`v3.28_listening_engine_fase_2_f74493a3.plan.md`: resuelve el **P1-01** de la
auditoría V3.27 (las rutas por nivel y drill no servían el micro-flujo) y
aborda P1-02/P1-03/P1-05. El candidato V3.28 anotado en `PLAN.md`/RELEVO
(diccionario de consulta) se reprioriza a **V3.29**.
Verificación íntegra local: backend pytest **1683 passed** + `ruff check .`
limpio; frontend vitest **505 passed** (61 archivos) + `tsc --noEmit` OK;
`check_release_consistency` 3.28.0 exit 0.**

## Qué cambia

### Bloque A — Micro-flujo unificado en rutas por nivel y drill (P1-01)

En V3.27 el micro-flujo solo se adjuntaba en la rama adaptativa de
`next_question()`; las rutas por nivel (`level=X`) y el drill (`mode=failed`)
devolvían el payload compacto sin `flow`. En V3.28 un helper interno
`_public_with_flow(question, attempts)` encapsula `_public()` +
`flow_for_question()` y se usa también en la rama por nivel cuando
`mode != "mastered"` (calculando el perfil auditivo del alumno con la misma
evidencia que la rama adaptativa). `mastered` conserva `_public(...)` como
repaso compacto sin flow (contrato fijado por E2E-04). El router no cambia de
contrato: `flow`/`transcript_policy` siguen siendo campos opcionales del
payload, así que los consumidores antiguos no se rompen.

### Bloque B — AudioController 4.0 (frontend)

Nuevo módulo puro `frontend/src/features/listening/audioController.ts` que
envuelve `HTMLAudioElement` en una API rica y testable:

- `play()`/`pause()`/`seek(t)`/`replayCurrent()`/`loopSegment(start, end)`/
  `markSegment()`.
- `setRate(r)`: selecciona la variante de URL existente (slow/normal/fast) más
  cercana al rate pedido y usa `playbackRate` fino con `preservesPitch` cuando
  el navegador lo soporta (chequeo en `utils/browserCapabilities`).
- Suscripción de `currentTime`/`ended`/`ratechange` para la UI.

El hook `useAudioController` expone el estado (incluido `audioTime`) y
`ListeningPractice.tsx` consume el controller para while1/while2/replay en
lugar de llamadas sueltas a `new Audio()`.

### Bloque C — Bottom-up derivado del corpus (P1-02/P1-03 parcial)

Nuevo módulo puro `backend/services/listening_bottom_up.py` que **deriva
determinísticamente** ítems de práctica de cada ítem del corpus (por `id` de
ítem + nivel), sin re-etiquetar ni re-autorar los 490 ítems:

- **Cloze auditivo** (`task_type="cloze"`, MCQ): toma la primera frase audible
  de un solo hablante del ítem padre y elige el hueco con heurística
  **determinista** — token de contenido que aparece una sola vez en la frase,
  de 3+ letras, sin apóstrofo, sin stop word ni reducción escrita; selección
  estable por id de ítem + slot; opciones = palabra oída + 2 distractores de
  contenido del banco del mismo nivel que nunca aparecen en la frase. Sin
  frase, sin token único o sin 2 distractores → el ítem no se emite.
- **Dictado parcial** (`task_type="partial_dictation"`, producción): hueco de
  1-N tokens y scoring determinista exacto por token (patrón de `dictation`,
  sin LLM).
- **Segmentación** (`task_type="segmentation"`, MCQ): pares contraídos/
  reducidos (`going to` vs `gonna`) solo donde el corpus los realiza; si no hay
  candidato fiable, el ítem **no se emite** (nunca se inventa audio).

Regla de integración: los ítems derivados (`derived=True`) se sirven como
volumen extra de decodificación (selector con perfil Caso A) pero **no entran
en el pool de ruta ni en la certificación** — `route_questions`/`level_items`
los filtran de forma defensiva (mismo diseño que `listening_generated`). El
backend persiste `task_type` y deriva la capa del skill (nunca del cliente);
el audio reutiliza el del ítem padre (sin WAV duplicados ni cambios en la
caché versionada).

### Bloque D — Transcript dinámico con sync grueso

- Backend: `coarse_sentence_timings` calcula timings de frase **heurísticos**
  a partir de `clean_transcript` y `duration` (distribución proporcional por
  tokens), expuestos con `sync: "coarse_heuristic"` — nunca como alineación
  acústica. Se sirven en el payload cuando el ítem tiene flow (`sentence_timings`).
- Frontend: `microFlow.ts` gana `timingsOf`/`activeSentenceIndex`/
  `revealSentenceIndexes` y el nuevo componente `CoarseTranscript` pinta el
  transcript según el estado (`hidden` → nada, `partial` → frase permitida por
  el paso, `full` → todo) y resalta la frase activa según `currentTime` del
  AudioController. La transcripción parcial revela solo la frase/segmento que
  permite `transcript_state_inicial` de cada step.
- Sin karaoke palabra a palabra en V3.28 (Fase 3 / V3.29).

### Bloque E — Shadowing 2.0 (sin llamarlo pronunciación)

- **Playback de la grabación del alumno** en el paso shadowing de listening:
  se reutiliza `RecordingPlayButton` (de Pronunciation/Speaking) sobre el blob
  en memoria; el frontend lo revoca al cambiar de ítem/desmontar.
- **Evidencia auxiliar no bloqueante**: el cliente calcula de forma
  determinista desde el audio grabado `shadowing_duration_ms` (duración) y
  `shadowing_speech_rate` (velocidad de habla) y las envía en
  `POST /listening/shadowing`; el backend las persiste en `listening_attempts`
  con **migración aditiva idempotente** (columnas nullable, patrón V3.27).
- Estas señales son **informativas**: no tienen peso de mastery ni de gate
  (tests negativos lo fijan). El límite honesto se mantiene: la prueba de que
  "se produjo el texto esperado" sigue siendo un proxy de texto
  (`pronunciation_source=transcript`), no evaluación acústica real.

### Bloque F — E2E adaptativos y negativos del contrato pedagógico

`backend/tests/test_listening_e2e_v328.py` recorre con `TestClient` el ciclo
completo (diagnóstico → perfil → pregunta → flujo → evidencia → diagnóstico):

- **E2E-01** A1 débil en recognition → `profile=recognition`,
  `intervention=bottom_up_path`, siguiente pregunta de capa recognition con
  flow de 5 etapas (shadowing obligatorio).
- **E2E-02** B2 con connected speech débil → `connected_speech_path` y
  `shadowing_optional=False` en la ruta por nivel (`allow_skip=False` en el
  paso shadowing).
- **E2E-03** fuerte en comprehension y débil en inference → `top_down_path`
  con pregunta de capa inference.
- **E2E-04** sesión `mastered` → modo compacto sin flow (contrato del Bloque A).
- Negativos: un ítem derivado nunca aparece en la certificación; responder un
  derivado no mueve la puerta del nivel; `transcript_used` refleja lo realmente
  visto (persistencia fiable); B2 no permite reveal manual antes de Post.

Las siembras de perfil eligen ítems por **realización auditiva real**
(`resilience_dimensions`, nunca por skill declarada), de modo que un intento
solo aporta evidencia a una dimensión si el audio del ítem la ejercita.

Frontend: `microFlow.test.ts` cubre las transiciones de las etapas nuevas
(dictado parcial / cloze / segmentación dentro del flow, sin confundirse con
las tareas de producción).

## Técnica

- Backend (versión de app `3.27.0 → 3.28.0`, fuente única `backend/config.py`):
  - `services/listening.py`: `coarse_sentence_timings` y helpers de frases
    (Bloque D); filtrado defensivo de derivados en `route_questions` (Bloque C).
  - `services/listening_bottom_up.py` (nuevo, puro): cloze / partial_dictation /
    segmentation derivados + `DERIVED_RECOGNITION_POOL`.
  - `services/listening_flow.py`: sin cambios de contrato (los derivados
    receptivos reciben el flow receptivo).
  - `domain/listening.py`: `_public_with_flow` (Bloque A); `next_question`
    unifica nivel/failed; `submit_production` acepta
    `shadowing_duration_ms`/`shadowing_speech_rate` (Bloque E).
  - `repositories/db.py` (migración aditiva idempotente de las 2 columnas de
    shadowing) y `repositories/listening.py` (`record_attempt`/`list_attempts`).
  - `schemas/listening.py` (`sentence_timings` en la pregunta;
    `shadowing_duration_ms`/`shadowing_speech_rate` en producción).
  - `routers/listening.py`: paso de las señales auxiliares en `/shadowing`.
  - Tests nuevos: `test_listening_flow_unified_v328.py` (Bloque A),
    `test_listening_bottom_up_v328.py` (Bloque C, barrido del banco),
    `test_listening_timings_v328.py` (Bloque D),
    `test_listening_shadowing2_v328.py` (Bloque E) y
    `test_listening_e2e_v328.py` (Bloque F).
- Frontend:
  - `features/listening/audioController.ts` (+ `useAudioController`) y
    `utils/browserCapabilities` (Bloque B).
  - `features/listening/CoarseTranscript.tsx` y helpers en `microFlow.ts`
    (Bloque D).
  - `ListeningPractice.tsx`: consumo del AudioController, `CoarseTranscript`,
    playback de la grabación en shadowing y cálculo/envío de señales auxiliares.
  - `types/api.ts` y `api/listening.ts`: `sentenceTimings`/`SentenceTiming` y
    `ListeningShadowingAux`.
  - i18n es/en (`listening.coarseTranscript.*`, `listening.flow.recordShadowing`/
    `playRecording`/`shadowingSignals`).
- Docs: `PLAN.md` (V3.28 cerrado; diccionario → V3.29 candidato),
  `CHANGELOG.md` (`[3.28.0]`), `README.md`, `docs/RELEVO.md`,
  especificación `docs/LISTENING_ENGINE_4.0.md` (Fase 2 cerrada).

## Tests

- Backend: **1683 pytest en verde** (backend + launcher) — incluye los 5
  archivos V3.28 nuevos (A–F) + `ruff check .` limpio.
- Frontend: vitest **505 passed** (61 archivos); `tsc --noEmit` OK.
- `scripts/check_release_consistency.py` exit 0 (3.28.0).

## Fuera de alcance (deuda documentada)

- Karaoke palabra a palabra / `word_alignment_proxy` offline y salto a la
  palabra fallada → **Fase 3 (V3.29+)**.
- Calibración de los umbrales del perfil auditivo (70/85/60), del PRE rico,
  del WHILE1 activo, del dosage de shadowing, del soporte a nivel de Listening
  y la descomposición de `ListeningPractice.tsx` (P2 de la auditoría V3.27).
- P1-04 (corpus B1→C2 dependiente de TTS) → Fase 4 de contenido.
- Dossier de auditoría del candidato v3.28.0 (letra P) → sesión posterior.

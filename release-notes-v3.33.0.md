# v3.33.0 — Dictionary → Learning Bridge, eslabón 2: Recognition (MCQ definición ↔ palabra)

**La escalera compartida de drill gana su primer peldaño de reconocimiento:
al practicar una palabra (desde el lookup «Practicar esta palabra» o desde el
hub de Vocabulario) el alumno puede elegir el significado de la palabra entre
opciones servidas por el backend. La pregunta es determinista por palabra
(sin estado servidor, premisa 21) y su evidencia es SOLO informativa: un
evento `learning_events` `drill:<word>:recognition:ok|ko`. Un MC de
reconocimiento no demuestra destrezas productivas (V3.13), así que el peldaño
no escribe en `vocabulary`, no mueve FSRS/mastery/usage y no saca la palabra
de la lista de candidatas (eso sigue exigiéndolo la producción espaciada).**
Versión de app `3.32.0 → 3.33.0`. Backend (contenido + dominio + endpoints +
schemas) + frontend (UI del peldaño + API + tests); sin cambios de esquema de
BD ni de contrato HTTP previo.

## Qué cambia

### 1. Pregunta Recognition determinista en el backend (`dictionary_mcq.py`)

Nuevo helper puro `backend/services/dictionary_mcq.py`:
`recognition_options_for(word, entries)` devuelve `(options, correct_index)` o
`None`. La opción correcta es el significado real de la diana en un **modo
consistente** —`translation` si existe y hay distractores con traducción;
si no, `definition`— y los distractores son significados (mismo modo) de OTRAS
entradas globales de `dictionary_entries`, preferentemente del mismo `pos`,
deduplicados entre sí y frente a la correcta (nunca dos opciones
indistinguibles). El barajado reutiliza el patrón de
`services/listening_bottom_up.py` (`_stable_int` + `_place_options`): mismo
texto y mismo banco ⇒ misma pregunta y mismo orden en cualquier proceso. Si no
hay suficientes distractores (≥ 2 distintos) devuelve `None`: el peldaño
degrade con aviso en vez de forzar una pregunta mala.

`repositories/dictionary.py` gana `list_entries()` (todas las filas de la
caché global, orden estable por `word`): la caché es el único contenido de
significado del diccionario y no depende de la evidencia de ningún alumno.

### 2. Dominio, endpoints y schemas (premisa 21)

`domain/vocabulary.py`:
- `get_recognition_question(user_id, word)` → `{word, available, options}`.
  NUNCA incluye la opción correcta (lo puntúa el POST recomputando la pregunta
  con la misma función pura).
- `submit_recognition_attempt(user_id, word, selected_index)` → `{word,
  correct, correct_index, selected_index}`. Sin `record_production_text`, sin
  retrieval, sin tocar `vocabulary`: solo devuelve el veredicto para que el
  router registre el evento informativo.

`routers/vocabulary.py` (junto a los endpoints de drill):
- `GET /api/vocabulary/drill/recognition?user_id&word` →
  `RecognitionQuestionOut {word, available, options}`. Sin contenido →
  `available=false` con `options=[]` (200, degradación controlada sin evento).
- `POST /api/vocabulary/drill/recognition-attempt` (body `{word,
  selected_index}`) → `RecognitionAttemptOut`. Registra `learning_events`
  `exercise` con detalle `drill:<word>:recognition:ok|ko`. Si la palabra ya no
  tiene pregunta (contenido desaparecido) responde **409** sin evento; índice
  fuera de rango o palabra inválida → 422 sin evento.

`schemas/vocabulary.py`: `RecognitionQuestionOut`, `RecognitionAttemptIn`,
`RecognitionAttemptOut`.

### 3. Peldaño «1 · Recognize» en la escalera compartida (`wordDrill.tsx`)

La escalera compartida pasa de dos a tres pasos — `1 · Recognize`,
`2 · Word` (era `1`), `3 · Sentence` (era `2`) — visible tanto desde el lookup
(`DictionaryLookup`) como desde el hub (`PersonalDictionary`). El paso
Recognition NO usa micrófono: muestra la pregunta con sus opciones como
botones accesibles, envía `selected_index`, y muestra el feedback correcto o
incorrecto con la opción correcta revelada (`correct_index` llega solo tras
responder). Si `available=false` muestra un aviso y no rompe los pasos orales.
El acierto NO dispara `onProduced` ni `refreshEntry`: es informativo.

Cliente: `types/api.ts` (`DrillRecognitionQuestion`,
`DrillRecognitionAttempt`), `api/vocabulary.ts`
(`getDrillRecognitionQuestion`, `submitDrillRecognitionAttempt`). i18n:
renumeración de `dictionary.drill.stepRecall`/`stepSentence` y nuevas claves es/
en del paso (`stepRecognition`, `recognitionPrompt`, `recognitionCheck`,
`recognitionCorrect`, `recognitionIncorrect`, `recognitionUnavailable`).

## Verificación

- Backend: `pytest` → **1722 passed** (+11 sobre v3.32.0, el nuevo
  `test_dictionary_recognition_v333.py`) + `ruff check .` limpio. El dossier
  siembra la caché `dictionary_entries` con el repositorio (el MCQ nunca invoca
  al generador) y usa el patrón de aceptación HTTP de v332 (TestClient único):
  - determinismo: dos GET consecutivos devuelven las mismas `options` y el GET
    nunca expone `correct_index`;
  - acierto → evento `drill:<word>:recognition:ok` y CERO cambios en filas /
    eventos de `vocabulary` (ni retrievals ni producción: D3 + V3.13);
  - fallo → evento `:ko` con la misma ausencia de efectos y `correct_index`
    revelado solo tras responder;
  - modo `definition` cuando no hay traducciones suficientes (un solo idioma
    entre opciones) y textos duplicados que nunca llegan a opciones;
  - los eventos `drill:<word>:recognition:ok` NO alteran la salida de
    candidatas del drill (`drill_ok_days`/`drill_candidates`, con contrafactual
    que detectaría la regresión);
  - aislamiento A/B (la pregunta es global, el evento solo del autor) y
    palabra sin entrada o sin distractores → `available=false` / POST 409 sin
    evento; normalización de la palabra e índice fuera de rango → 422.
- Frontend: `vitest` → **63 ficheros / 546 tests passed** (+4: `describe`
  Recognition en `DictionaryLookup.test.tsx` — acierto informativo sin
  re-lookup `/dictionary` y fallo con la correcta revelada — y en
  `PersonalDictionary.test.tsx` — acierto que no saca la candidata y
  degradación por falta de significado —, además de las aserciones renumeradas
  de los pasos `2 · Word`/`3 · Sentence`) + `tsc --noEmit` limpio.
- `python scripts/check_release_consistency.py` → **3.33.0** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.33.0 al frente de «Estado actual» (segundo eslabón
  del puente) y cierre en «Siguiente incremento»; quedan pendientes hacia
  **V3.34**: recall demorado con FSRS, transferencia por contexto de actividad
  V3.23 y los diferidos de V3.30 (consumo de `word_breakdown_json`, palabras
  tocables).
- `CHANGELOG.md` con la entrada `[3.33.0]`; nota de cierre en `docs/RELEVO.md`.
- `agentes/v333-dictionary-recognition-mcq.md` (briefing del eslabón,
  decisiones, contrato y acceptance) y `agentes/v332-dictionary-learning-bridge.md`
  actualizado: el eslabón Recognition queda cerrado en v3.33.0.

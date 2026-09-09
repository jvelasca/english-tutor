# Candidato V3.33 — Dictionary → Learning Bridge, eslabón 2: Recognition (MCQ definición ↔ palabra)

> Rol: documento de diseño e instrucciones del candidato **V3.33**. Implementa el
> segundo eslabón del puente que abrió V3.32: un peldaño **Recognition** en la
> escalera compartida de drill (`wordDrill.tsx`) que pide elegir el significado de
> la palabra entre opciones (MCQ definición ↔ palabra), servido y puntuado por el
> backend (premisa 21). Se publicará como **v3.33.0**.
>
> Normas que este candidato DEBE respetar:
> - **D3** (V3.30): «consultar ≠ aprender». El paso Recognition es una acción de
>   práctica explícita, pero su acierto NO demuestra destreza productiva (V3.13),
>   así que su evidencia es SOLO informativa: un evento `learning_events`
>   `drill:<word>:recognition:ok|ko`. NO escribe en `vocabulary`,
>   `vocabulary_events`, ni mueve mastery/FSRS/usage ni saca la palabra de la
>   lista de candidatas (eso sigue exigiéndolo la producción espaciada del
>   drill).
> - **Premisa 21**: la UI nunca declara acierto; envía `selected_index` y el
>   servidor puntúa recomponiendo la pregunta de forma determinista.
> - **Sin estado servidor**: pregunta y barajado deterministas por palabra
>   (mismo patrón que `services/listening_bottom_up.py`: `_distractors` /
>   `_place_options` / `_stable_int`). GET y POST comparten la MISMA función
>   pura; el servidor vuelve a derivar la pregunta al puntuar (como ya hace
>   `submit_sentence_attempt` con la frase).
> - **Evidencia idéntica, sin etiquetas de origen**: si el eslabón acabara
>   escribiendo algo en el Student Model (no es el caso en V3.33) no llevaría
>   «vino del diccionario» como campo; en V3.33 solo existe el evento
>   informativo arriba.
>
> Borrador: 2026-09-09.

## Contexto del puente (leer antes)

`agentes/v332-dictionary-learning-bridge.md` describe el puente completo
(objetivo, invariante D3, arquitectura). V3.32.0 cerró el **primer eslabón**:
«Practicar esta palabra» en la tarjeta del lookup monta in-line la escalera de
drill existente Recall → Sentence (`wordDrill.tsx`, componente compartido con el
hub `PersonalDictionary.tsx`). Ese drill solo depende de `userId` + `word` y no
conoce el origen.

## Qué implementa V3.33

1. **Backend — pregunta Recognition determinista** (sin estado servidor):
   - `repositories/dictionary.py`: nueva consulta `list_entries()` (todas las
     filas de `dictionary_entries`, global y sin `user_id`) para disponer de
     candidatas a distractor (la caché es el único contenido de significado del
     diccionario).
   - Nuevo helper puro `services/dictionary_mcq.py` (o equivalente en
     `domain/vocabulary.py`): `recognition_options_for(word, entries)` →
     devuelve `(options, correct_index)` o `None`.
     - Opción correcta = la definición/traducción de la diana (elegir modo:
       `translation` si existe y hay distractores con traducción; si no,
       `definition`). NO mezclar idiomas entre opciones: un modo consistente.
     - Distractores = textos de significado (mismo modo) de OTRAS entradas
       globales, preferir mismo `pos` que la diana; excluir textos idénticos
       entre sí y a la correcta; si el pool es pequeño pero hay ≥ 2 candidatas
       distintas, emitir con menos opciones (3); si no hay suficientes → `None`
       (la pregunta no está disponible y el peldaño degrada con aviso).
     - Barajado estable ocultando la correcta (reutilizar `_place_options` /
       `_stable_int`).
   - `domain/vocabulary.py`: `get_recognition_question(user_id, word)` →
     `{word, available, options}` (NUNCA incluye `correct_index`) y
     `submit_recognition_attempt(user_id, word, selected_index)` →
     recomputa con la misma función pura, puntúa y devuelve
     `{word, correct, correct_index, selected_index}`. NO registra producción,
     NO retrieval, NO `record_production_text` (es solo informativo).
   - `routers/vocabulary.py` (junto a los endpoints de drill):
     - `GET /api/vocabulary/drill/recognition?user_id&word` →
       `RecognitionQuestionOut {word, available, options}`. Si no disponible:
       `available=false`, `options=[]` (200, degradación controlada, sin evento).
     - `POST /api/vocabulary/drill/recognition-attempt` (body
       `{word, selected_index}`) → `RecognitionAttemptOut`. Registra el evento
       informativo `learning_events` `exercise` con detalle
       `drill:<word>:recognition:ok|ko`. Si la palabra ya no tiene pregunta
       (contenido desaparecido), error controlado 4xx sin evento.
   - `schemas/vocabulary.py`: `RecognitionQuestionOut`, `RecognitionAttemptIn`,
     `RecognitionAttemptOut`.
2. **Frontend — peldaño Recognition en la escalera compartida**:
   - `types/api.ts`: `DrillRecognitionQuestion`, `DrillRecognitionAttempt`.
   - `api/vocabulary.ts`: `getDrillRecognitionQuestion` / `submitDrillRecognitionAttempt`.
   - `wordDrill.tsx`: extender el union `DrillStep` con `"recognition"`,
     número `1 · Recognize`, renumerar `2 · Word` (recall) y `3 · Sentence`.
     Estado/render del bloque: prompt «¿Qué significa esta palabra?», botones de
     opción accesibles, submit con `selected_index`, feedback correcto/incorrecto
     revelando la opción correcta (usa `correct_index` devuelto). El paso NO usa
     micrófono. Degrada con aviso (clave i18n propia) cuando `available=false`.
     El acierto NO dispara `onProduced` ni `refreshEntry`.
   - `i18n.ts`: renumerar `dictionary.drill.stepRecall`/`stepSentence` y añadir
     claves del paso Recognition en es/en (etiqueta, prompt, feedback ok/ko,
     aviso de no disponible). Mantener paridad de claves (test i18n parity).
   - Tests vitest: actualizar los nombres de paso asertados en
     `DictionaryLookup.test.tsx` y `PersonalDictionary.test.tsx` y añadir
     `describe` del paso Recognition (mock de los dos endpoints, verificar
     feedback ok/ko y que tras el acierto NO hay re-lookup `/dictionary`).
3. **Tests backend** (`backend/tests/test_dictionary_recognition_v333.py`,
   patrón del archivo v332: TestClient único por test, repos/sqlite directos):
   - determinismo: dos GET consecutivos devuelven las mismas `options` y el GET
     nunca filtra `correct_index`;
   - acierto → evento `drill:<word>:recognition:ok` y CERO cambios en filas /
     eventos de `vocabulary` ni retrievals (D3 + informativo);
   - fallo → evento `:ko` (misma ausencia de efectos);
   - aislamiento usuario A/B (evento solo en el autor);
   - palabra sin entrada cacheada o sin distractores → `available=false` sin
     evento, y POST controlado sin evento;
   - los eventos `drill:<word>:recognition:ok` NO alteran la salida de
     candidatas (`drill_ok_days` / candidates) de la palabra.
4. **Docs y cierre V3.33.0**: briefing en `agentes/`, ajustar pendientes del
   borrador v332, bump de versión a `3.33.0`, release notes, CHANGELOG `[3.33.0]`,
   PLAN (hito + siguiente incremento), README, Nota superior en `docs/RELEVO.md`,
   gates completos + `check_release_consistency` 3.33.0 + commit + push + CI.

## Contracto de red

GET `/api/vocabulary/drill/recognition?user_id&word` → 200:

```json
{ "word": "quokka", "available": true, "options": ["…", "…", "…", "…"] }
```

Sin contenido suficiente:

```json
{ "word": "quokka", "available": false, "options": [] }
```

POST `/api/vocabulary/drill/recognition-attempt`:

```json
{ "word": "quokka", "selected_index": 2 }
```

→ 200:

```json
{ "word": "quokka", "correct": true, "correct_index": 2, "selected_index": 2 }
```

## Criterios de aceptación

- ✅ La escalera compartida (lookup Y hub) ofrece el paso `1 · Recognize`
  cuando la pregunta está disponible; si no, degrada con aviso y no rompe
  Recall/Sentence.
- ✅ Servidor puntúa; el GET nunca expone la correcta; la pregunta es
  determinista por palabra (misma opción correcta y orden entre llamadas).
- ✅ Acierto y fallo registran únicamente el evento informativo
  `drill:<word>:recognition:ok|ko`; cero efectos en vocabulary/FSRS/mastery/
  usage/candidatas (D3 + V3.13).
- ✅ Suite completa verde: pytest (+nuevos tests) + ruff + vitest + tsc +
  build + `check_release_consistency` 3.33.0 exit 0 + CI GitHub.

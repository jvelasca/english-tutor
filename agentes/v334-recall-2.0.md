# V3.34 — Dictionary → Learning Bridge, eslabón 3: Recall 2.0 (texto)

> Rol: documento de diseño e implementación del candidato **V3.34**. Cierra el
> tercer eslabón del puente que abrió V3.32 y que continuó V3.33 (Recognition):
> el peldaño intermedio del drill deja de ser una repetición oral de la palabra
> y pasa a ser una **recuperación REAL por texto** — el alumno ve el
> SIGNIFICADO (cue) y teclea la palabra. Se publica como **v3.34.0**.
>
> Normas que este eslabón respeta:
>
> - **Premisa 21**: la UI nunca declara acierto; envía la palabra tecleada y el
>   servidor puntúa re-derivando la pregunta de forma pura y determinista. El
>   GET NUNCA expone la forma esperada (`expected` solo aparece en la respuesta
>   del POST).
> - **D3** (V3.30): «consultar ≠ aprender». La consulta del diccionario sigue
>   siendo SOLO lectura; el recall es una acción de práctica explícita.
> - **V3.13**: un MC de reconocimiento no demuestra destrezas productivas.
>   Recognition sigue siendo SOLO informativo (`drill:<word>:recognition:ok|ko`,
>   sin tocar `vocabulary`/FSRS/mastery/candidatas). El recall, en cambio,
>   acredita recuperación real y por eso SÍ deja señal léxica propia.
> - **D5/E3**: el drill NO crea `academy_evidence` curricular; el recall vive en
>   la capa léxica (contadores + ledger + FSRS `lexicon`).
>
> Borrador: 2026-09-10.

## Contexto del puente (leer antes)

`agentes/v332-dictionary-learning-bridge.md` describe el puente completo. V3.32
cerró el primer eslabón («Practicar esta palabra» monta in-line la escalera de
drill compartida `wordDrill.tsx`, que solo depende de `userId` + `word`). V3.33
añadió el peldaño `1 · Recognize` (MCQ definición ↔ palabra, SOLO informativo).
La escalera quedó `1 · Recognize` · `2 · Word` (oral) · `3 · Sentence`.

## Decisiones cerradas de V3.34

- **Escalera de 3 peldaños sin paso oral de palabra suelta**: se retira el
  antiguo `2 · Word`; el nuevo `2 · Recall` es por TEXTO. El micrófono queda
  reservado a `3 · Sentence` (la producción oral real).
- **El acierto de Recall deja señal propia**: `recall_successes` /
  `recall_days` + evento `vocabulary_events` `recalled`. NUNCA cuenta como
  producción (`production_count` y `<channel>_prod` intactos) ni saca la palabra
  de candidatas (`onProduced` solo lo dispara Sentence).
- **El acierto acredita recuperación demorada** si el intento supera el
  intervalo de retención existente (`record_retrievals`, contadores
  `retrieval_*`), reutilizando la semántica de V3.23.
- **FSRS con intervalos reales**: cada intento de Recall reprograma la carta
  `lexicon` de la palabra — Good si acierta de inmediato, Easy si fue
  recuperación demorada, Again si falla. `sync_fsrs_cards` respeta `reps > 0`,
  así que el intervalo no se pisa.

## Qué implementa V3.34

1. **Backend — señal de recall en el léxico**:
   - `repositories/db.py`: migración idempotente en `vocabulary`
     (`recall_successes`, `recall_days`, `last_recall_at`), sin backfill.
   - `repositories/vocabulary.py`: `VOCABULARY_EVENT_TYPES` añade `recalled`;
     nueva `record_recalls(user_id, words)` que hace upsert del contador y del
     día (una vez por día natural) e inserta el evento `recalled` en la MISMA
     transacción, sin tocar producción ni `first_seen`/`last_seen`; crea la fila
     si no existía (palabra solo consultada) con producción/exposición a 0.
     `get_vocabulary` incluye las columnas nuevas.
   - `services/lexicon.py`: `item_competence_matrix` añade `cued_recall`
     (`recall_successes > 0`), `recall_successes` y `recall_days` como señal
     propia (sin renombrar `retrieval_*`/`retention`); `summary` cuenta
     `recalled`; `drill_candidates(..., due_words=…)` antepone las palabras con
     carta FSRS `lexicon` vencida.
2. **Backend — pregunta de Recall pura**: nuevo `services/recall.py`
   (`recall_prompt_for(word, entries)` → `{word, cue, cue_kind}` o `None`). Cue =
   `translation` si existe; si no, `definition` SOLO si no contiene la palabra
   diana (definición circular descartada); sin cue válido → `available=false`
   sin evento. Nunca devuelve la forma esperada.
3. **Backend — dominio, scoring y FSRS** (`domain/vocabulary.py`):
   - `get_recall_prompt(user_id, word)` → `{word, available, cue, cue_kind}`.
   - `submit_recall_attempt(user_id, word, answer)` → `{word, correct,
     expected, delayed, recall_days}`; normaliza palabra y respuesta e iguala
     superficie (case-insensitive); `expected` solo tras responder. En acierto:
     `record_recalls` + `_record_retrieval` (demorada si toca) +
     `_reschedule_lexicon_card`. En fallo: solo el lapse FSRS si la carta ya
     existía.
   - `_reschedule_lexicon_card`: siembra la carta en acierto, aplica
     Good/Easy/Again y persiste; nunca lanza.
   - `get_drill_candidates` prioriza las palabras con carta FSRS `lexicon`
     vencida (`fsrs.is_due`).
4. **Backend — contrato HTTP y esquemas** (`routers/vocabulary.py`,
   `schemas/vocabulary.py`):
   - `GET /api/vocabulary/drill/recall?user_id&word` → `RecallPromptOut`.
   - `POST /api/vocabulary/drill/recall-attempt` (body `{word, answer}`) →
     `RecallAttemptOut`; evento `learning_events` `drill:<word>:recall:ok|ko`;
     409 si la palabra ya no tiene pregunta y 422 en entrada inválida (sin
     evento).
   - `LexicalCompetence` gana `cued_recall`/`recall_successes`/`recall_days`;
     `LexiconSummary` gana `recalled`; `VocabularyEventOut.event_type` admite
     `recalled`.
5. **Frontend — peldaño «2 · Recall» por texto** (`wordDrill.tsx`,
   `api/vocabulary.ts`, `types/api.ts`, `i18n.ts`):
   - `types/api.ts`: `DrillRecallPrompt`, `DrillRecallAttempt`; ampliar
     `LexicalCompetence`/`LexiconSummary`.
   - `api/vocabulary.ts`: `getDrillRecallPrompt`, `submitDrillRecallAttempt`.
   - `wordDrill.tsx`: `RecallStep` presentacional (input + botón Check, sin
     micrófono); oculta la palabra diana durante el intento (el header muestra
     el cue) y la revela en el feedback; `available=false` degrada a Sentence
     sin romper la escalera; se retira el paso oral de palabra y `onProduced`
     queda solo en Sentence.
   - `i18n.ts`: `stepRecall` → «2 · Recall» y claves del paso (prompt, input,
     placeholder, Check, ok/ko, no disponible).
6. **Tests**:
   - Nuevo `backend/tests/test_recall_v334.py` (cue puro con/ sin spoiler,
     scoring, señal propia sin producción, recuperación demorada
     dentro/fuera de intervalo, FSRS Good/Again sin crear deuda, aislamiento
     A/B). `test_lexicon.py`: `cued_recall`/`recalled` y priorización por
     `due_words`.
   - Frontend vitest: peldaño Recall por texto (cue visible, palabra oculta,
     feedback ok/ko, sin producción) y mocks de `DictionaryLookup`/
     `PersonalDictionary` actualizados al degrade Recognize → Recall → Sentence.
7. **Docs y cierre V3.34.0**: este briefing, `release-notes-v3.34.0.md`, bump a
   `3.34.0`, `CHANGELOG.md` `[3.34.0]`, hito en `PLAN.md`, nota en
   `docs/RELEVO.md`, versión en `README.md` y `check_release_consistency`
   **3.34.0** exit 0.

## Contrato de red

GET `/api/vocabulary/drill/recall?user_id&word` → 200:

```json
{ "word": "quokka", "available": true, "cue": "marsupial australiano", "cue_kind": "translation" }
```

Sin cue utilizable:

```json
{ "word": "ghost", "available": false, "cue": "", "cue_kind": "" }
```

POST `/api/vocabulary/drill/recall-attempt`:

```json
{ "word": "quokka", "answer": "Quokka" }
```

→ 200:

```json
{ "word": "quokka", "correct": true, "expected": "quokka", "delayed": false, "recall_days": 1 }
```

## Criterios de aceptación

- ✅ El GET NUNCA expone la forma esperada; el servidor puntúa (premisa 21).
- ✅ El cue prefiere la traducción y descarta definiciones que filtren la
  respuesta; sin cue válido → `available=false` y POST 409 sin evento.
- ✅ El acierto deja señal de recall propia (`recall_successes`/`recall_days` +
  ledger `recalled`), acredita recuperación demorada si supera el intervalo y
  reprograma la carta FSRS `lexicon`; NUNCA acredita producción ni saca la
  palabra de candidatas.
- ✅ El fallo solo aplica lapse FSRS si la palabra ya estaba rastreada.
- ✅ La escalera queda `1 · Recognize` · `2 · Recall` · `3 · Sentence`, con el
  micrófono solo en Sentence y degradación sin rotura cuando falta el cue.
- ✅ Suite completa verde: pytest + ruff + vitest + tsc + build +
  `check_release_consistency` 3.34.0 exit 0 + CI GitHub.

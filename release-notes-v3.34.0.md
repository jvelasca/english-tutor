# v3.34.0 — Dictionary → Learning Bridge, eslabón 3: Recall 2.0 (texto)

**El peldaño intermedio del drill deja de ser una repetición oral de la palabra
y pasa a ser una recuperación REAL por texto: el alumno ve el SIGNIFICADO
(traducción o definición sin spoiler) y teclea la palabra. A diferencia de
Recognition (informativo), el acierto de Recall deja señal léxica PROPIA
(`recall_successes`/`recall_days` + ledger `recalled`), acredita la
recuperación demorada existente si supera el intervalo y reprograma la carta
FSRS `lexicon` con intervalos reales (Good/Easy/Again). NUNCA acredita
producción ni saca la palabra de candidatas. La escalera queda en tres peldaños
(`1 · Recognize` · `2 · Recall` · `3 · Sentence`) con el micrófono reservado a
Sentence.**
Versión de app `3.33.1 → 3.34.0`. Backend (migración léxica + servicio puro +
dominio + endpoints + schemas) + frontend (UI del peldaño + API + i18n +
tests); contrato HTTP aditivo (dos endpoints nuevos) y migración de BD
idempotente y sin backfill.

## Qué cambia

### 1. Señal de recall en el léxico (`repositories/`)

Migración idempotente en la tabla `vocabulary` (`repositories/db.py`):
`recall_successes INTEGER NOT NULL DEFAULT 0`,
`recall_days INTEGER NOT NULL DEFAULT 0`,
`last_recall_at TEXT NOT NULL DEFAULT ''` (sin backfill: mejor perder el
histórico que inventarlo).

`repositories/vocabulary.py`:
- `VOCABULARY_EVENT_TYPES` añade `recalled`.
- Nueva `record_recalls(user_id, words)`: upsert del contador (una vez por
  intento) y del día (una vez por día natural), `last_recall_at = now` y evento
  `recalled` en la MISMA transacción. NO toca `production_count` ni
  `<channel>_prod` ni `first_seen`/`last_seen`; crea la fila si no existía
  (palabra solo consultada) con producción y exposición a 0.
- `get_vocabulary` incluye las columnas nuevas.

### 2. Pregunta de Recall pura y sin spoiler (`services/recall.py`)

Nuevo helper puro `recall_prompt_for(word, entries)` → `{word, cue, cue_kind}` o
`None`. Cue = `translation` si existe; si no, `definition` SOLO si no contiene la
palabra diana (una definición circular se descarta: regalaría la respuesta). Sin
cue válido → `None` (degradación `available=false`, sin evento). Nunca devuelve
la forma esperada.

### 3. Dominio, scoring y FSRS (`domain/vocabulary.py`)

- `get_recall_prompt(user_id, word)` → `{word, available, cue, cue_kind}`; el
  GET nunca expone la respuesta.
- `submit_recall_attempt(user_id, word, answer)` → `{word, correct, expected,
  delayed, recall_days}`: normaliza palabra y respuesta con
  `_normalize_lookup_word` e iguala superficie (case-insensitive); `expected`
  solo se revela tras responder (premisa 21). En acierto: `record_recalls` +
  `_record_retrieval` (recuperación demorada si supera el intervalo) +
  `_reschedule_lexicon_card`. En fallo: solo el lapse FSRS si la carta ya
  existía (no se inventa deuda de repaso de una palabra no rastreada).
- `_reschedule_lexicon_card`: siembra la carta `lexicon` en acierto y aplica
  `GRADE_GOOD` (acierto inmediato), `GRADE_EASY` (recuperación demorada) o
  `GRADE_AGAIN` (fallo); nunca lanza. `sync_fsrs_cards` respeta `reps > 0`, así
  que el intervalo no se pisa.
- `get_drill_candidates` prioriza las palabras con carta FSRS `lexicon` vencida
  (`fsrs.is_due`), conservando el orden por recuerdo dentro de cada grupo.

### 4. Competencia léxica (`services/lexicon.py`)

`item_competence_matrix` añade `cued_recall` (`recall_successes > 0`),
`recall_successes` y `recall_days` como señal propia (sin renombrar
`retrieval_*`/`retention`, que siguen siendo la recuperación demorada);
`summary` añade el contador `recalled`; `drill_candidates` acepta
`due_words: set[str] | None` para anteponer las palabras vencidas.

### 5. Contrato HTTP y esquemas (premisa 21)

`routers/vocabulary.py`, junto a los endpoints de drill:
- `GET /api/vocabulary/drill/recall?user_id&word` →
  `RecallPromptOut {word, available, cue, cue_kind}`. Sin cue → `available=false`
  con `cue=""` (200, degradación controlada sin evento).
- `POST /api/vocabulary/drill/recall-attempt` (body `{word, answer}`) →
  `RecallAttemptOut {word, correct, expected, delayed, recall_days}`. Registra
  `learning_events` `exercise` con detalle `drill:<word>:recall:ok|ko`. Si la
  palabra ya no tiene pregunta → **409** sin evento; entrada inválida → 422 sin
  evento.

`schemas/vocabulary.py`: `RecallPromptOut`, `RecallAttemptIn`, `RecallAttemptOut`;
`LexicalCompetence` gana `cued_recall`/`recall_successes`/`recall_days`;
`LexiconSummary` gana `recalled`; `VocabularyEventOut.event_type` admite
`recalled`.

### 6. Peldaño «2 · Recall» por texto (`wordDrill.tsx`)

La escalera compartida (lookup Y hub) queda en `1 · Recognize` · `2 · Recall` ·
`3 · Sentence`: se retira el paso oral de palabra suelta y el micrófono queda
reservado a Sentence. Se extrae un `RecallStep` presentacional: input de texto +
botón Check, sin micrófono; la palabra diana se OCULTA durante el intento (el
header muestra el cue) y se revela en el feedback; `available=false` degrada a
Sentence sin romper la escalera. `onProduced` solo lo dispara Sentence (un
recall correcto no saca la palabra de candidatas).

Cliente: `types/api.ts` (`DrillRecallPrompt`, `DrillRecallAttempt`),
`api/vocabulary.ts` (`getDrillRecallPrompt`, `submitDrillRecallAttempt`) e i18n
(`stepRecall` renombrado a «2 · Recall» y claves nuevas: prompt, input,
placeholder, Check, ok/ko, no disponible).

## Verificación

- Backend: `pytest` → **1743 passed** (+20 sobre v3.33.1) + `ruff check .`
  limpio. El dossier `test_recall_v334.py` siembra la caché `dictionary_entries`
  con el repositorio (el recall nunca invoca al generador) y usa el patrón de
  aceptación HTTP de V3.33 (TestClient único):
  - cue puro: traducción preferida, fallback a definición sin spoiler,
    definición circular descartada, palabra desconocida → `None`;
  - el GET nunca expone `expected`; acierto/fallo lo revelan solo tras
    responder; normalización de mayúsculas/espacios y respuesta vacía = fallo;
  - acierto → `recall_successes`/`recall_days` + ledger `recalled`, con CERO
    `production_count`/`<channel>_prod` y sin sacar la candidata; dos aciertos
    el mismo día cuentan un solo `recall_days`;
  - recuperación demorada: fuera del intervalo acredita `retrieval_*`
    (`delayed=true`), dentro no;
  - FSRS: acierto siembra la carta `lexicon` (due futuro), fallo sin carta no
    crea nada y fallo con carta aplica lapse (`lapses=1`, `last_grade=Again`);
  - aislamiento A/B y `summary.recalled` con `test_lexicon.py`
    (`cued_recall`, priorización por `due_words`).
- Frontend: `vitest` → **63 ficheros / 549 tests passed** (+2: peldaño Recall
  por texto con cue visible, palabra oculta, feedback correcto/incorrecto y sin
  producción; además de los mocks y aserciones de pasos actualizados al degrade
  Recognize → Recall → Sentence en `DictionaryLookup.test.tsx` y
  `PersonalDictionary.test.tsx`) + `tsc --noEmit` limpio.
- `python scripts/check_release_consistency.py` → **3.34.0** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.34.0 al frente de «Estado actual» (tercer eslabón
  del puente) y cierre en «Siguiente incremento»; quedan pendientes hacia
  **V3.35**: los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat), la transferencia por contexto de actividad V3.23 y el
  Lexical Evidence Engine / Evidence Graph como fuente longitudinal.
- `CHANGELOG.md` con la entrada `[3.34.0]`; nota de cierre en `docs/RELEVO.md`.
- `agentes/v334-recall-2.0.md` (briefing del eslabón, decisiones, contrato y
  acceptance).

## Fuera de alcance (diferido)

- Banco de distractores semánticos/CEFR (V3.36, Recognition 2.0).
- `event_role` en `learning_events`, latencia/automaticidad y recalibrado de
  pesos de `support_level` (señales de calidad).
- Transferencia contextual conectada al Evidence Graph y Evidence Graph como
  fuente longitudinal (V3.35, Lexical Evidence Engine).
- Troceado completo de `wordDrill.tsx` (solo se extrajo `RecallStep`).
- Retirada definitiva del endpoint `submit_drill_attempt` (se conserva por
  compatibilidad; deja de usarse en la escalera).

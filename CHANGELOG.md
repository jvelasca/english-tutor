# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

## [3.36.0] — 2026-09-10

**Learning Evidence 2.0: el ledger longitudinal aprende el CÓMO de cada evento. Hasta ahora `learning_evidence` sabía qué se recuperó y cuándo; desde V3.36 sabe con cuánto APOYO (`support_level`: eje `copied → guided → cued → independent → spontaneous`, el mismo de `academy_evidence`), con qué DIFICULTAD de ítem (CEFR 1-6, escala compartida con listening), en qué CONTEXTO y ACTIVIDAD (`context_id`/`activity_id`), con qué LATENCIA (`response_time_ms`, medido en cliente) y —si falló— con qué TIPO de fallo (`error_type`: taxonomía determinista sobre la errata, lo parcial y la confusión). Migración aditiva e idempotente, contrato HTTP aditivo. `error_type` es OBSERVACIONAL: clasificar no cambia scoring, ni evidencia, ni FSRS — una errata sigue siendo `correct=false`, pero el tutor ya puede distinguir "no lo sabe" de "lo sabe y lo escribió mal". Sin cues graduados ni planner: eso es V3.37.**

Versión de app `3.35.1 → 3.36.0`. Backend (migración aditiva + servicio puro + repositorio + dominio + schemas/routers) + frontend (latencia en el peldaño Recall + tipos + tests); contrato HTTP aditivo y migración de BD idempotente y sin backfill.

- **Dimensiones del evento en el ledger (`repositories/db.py`, `repositories/evidence.py`).** Migración aditiva e idempotente en `learning_evidence`: `activity_id`/`context_id`/`support_level`/`error_type` (`TEXT NOT NULL DEFAULT ''`), `difficulty` (`REAL NOT NULL DEFAULT 0`) y `response_time_ms` (`INTEGER`, NULL = no medida) + índice `(user_id, target_type, context_id, activity_id)` para los conteos de contexto. `record_evidence` y `record_evidence_bulk` persisten y devuelven las dimensiones; `list_evidence` las expone. El default NO inventa semántica: `''`/`0`/`NULL` significan "no declarado", y el dedupe de V3.35.1 sigue midiéndose por el EVENTO (target + tarea + actividad + instante), no por las dimensiones.
- **Taxonomía de error y apoyo declarado (`services/evidence.py`).** Nuevo `EVIDENCE_SUPPORT_LEVELS` (espejo de `services.academy.SUPPORT_LEVELS`, con test de paridad para que no diverjan), `INDEPENDENT_SUPPORT_LEVELS` y `RECALL_ERROR_TYPES` (`correct`/`empty`/`wrong_word`/`orthographic_error`/`partial`/`multiple_word_error`) con el clasificador puro `classify_recall_error(expected, given)`: errata = misma inicial + longitud ≥ 4 + distancia de Levenshtein acotada (1-2 según longitud); recuperación parcial = prefijo de la palabra o comienzo de la unidad multi-palabra; `wrong_word` = otra palabra. Deliberadamente conservador en palabras cortas (`cat`/`cut` es otra palabra, no una errata) para no excusar de más. `summarize_evidence` añade `success_rate`, `independent_successes` (aciertos sin apoyo: lo único que podrá pesar en automaticidad), `support_levels`, `error_types` y `mean_response_time_ms` (ignora los eventos sin medida).
- **Captura en dominio (`domain/vocabulary.py`, `services/lexicon.py`).** `submit_recall_attempt` acepta `response_time_ms` y declara `support_level="cued"` (la recuperación va guiada por cue), `context_id="lexicon:drill"`, `activity_id="drill:recall"`, la dificultad del ítem (`lexicon.cefr_difficulty`: posición CEFR en la escala 1-6 compartida con listening; `0.0` si no está declarada) y la clasificación del intento. `_record_retrieval` distingue `drill:word`/`drill:sentence` con apoyo `guided` (el alumno repite tras un modelo) y convierte la duración del cliente en ms (`_duration_ms`). La producción por canal declara su apoyo real (`_PRODUCTION_SUPPORT`: chat libre → `spontaneous`, conversación guiada → `guided`, speaking/writing → `independent`) y su contexto `lexicon:<canal>`.
- **Contrato HTTP y exposición (`schemas/vocabulary.py`, `routers/vocabulary.py`).** `RecallAttemptIn` gana `response_time_ms` (opcional, `ge=0`, `le=600000`; un valor negativo se rechaza con 422) y `RecallAttemptOut` expone `error_type` para el feedback del tutor. `LexicalEvidence` amplía `success_rate`, `independent_successes`, `support_levels`, `error_types` y `mean_response_time_ms`, con paridad exacta entre el agregado SQL (`summarize_by_target`) y la versión pura (fijada por test).
- **Frontend (`wordDrill.tsx`, `api/vocabulary.ts`, `types/api.ts`).** El peldaño Recall mide la latencia cue → envío con un `ref` que arranca cuando el cue queda visible (sin cue no hay intento, así que no hay medida) y la envía como `response_time_ms`; sin medición el campo va a `null` y el evento se registra igual. Tipos y cliente actualizados (aditivo). Test nuevo: la latencia viaja en el cuerpo del intento.
- **Tests.** Backend pytest **1791 passed** (+22: nuevo `test_learning_evidence_v336.py` con paridad del eje de apoyo, taxonomía de error —incluidas unidades multi-palabra y el sesgo conservador en palabras cortas—, migración idempotente, persistencia en `record_evidence`/`bulk`, agregados y paridad pura↔SQL, captura e2e del recall con latencia y errata, producción por canal y exposición en el léxico). Frontend vitest **65 ficheros/559 tests** (+1). `ruff check backend/` y `tsc --noEmit` limpios; `check_release_consistency` **3.36.0** exit 0.
- **CI verificable.** Commit `d91a637a74678e080478656ed02d7c1e6cd4ba07` con el run [34473218199](https://github.com/jvelasca/english-tutor/actions/runs/34473218199) en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## [3.35.1] — 2026-09-10

**Cierre de la auditoría de V3.35.0: patch quirúrgico de integridad del modelo de evidencia longitudinal. (1) `interval_since_last_evidence` deja de almacenar el intervalo de retención (ancla FSRS) y pasa a derivarse siempre de la evidencia anterior del ledger. (2) Los `intervals` del resumen conservan el orden cronológico (no se reordenan por valor). (3) La cola «Repaso de hoy» oculta la palabra en Recall/Sentence. (4) `record_evidence_bulk` deduplica eventos idénticos y encadena los distintos del mismo target. Sin cambios de esquema, contrato HTTP ni arquitectura.**

Versión de app `3.35.0 → 3.35.1`. Backend (dominio + repositorio + servicio puro) + frontend (cola de repaso + i18n + tests).

- **P1-01 — El intervalo de evidencia es el hueco del ledger, no el del ancla de retención (`domain/vocabulary.py`).** `_record_retrieval` y `submit_recall_attempt` dejaban de pasar `interval_since_last_evidence`; ahora `record_evidence` lo deriva SIEMPRE de la evidencia anterior del mismo ítem (`learning_evidence → learning_evidence`). El `interval_days`/`required_days` de `delayed_retrieval_decision` es el hueco desde el ANCLA de retención (FSRS) y se queda en la decisión (gate `credited` + reprogramación de carta), sin persistirse como intervalo de evidencia. Antes, una producción intercalada entre el ancla y el intento podía guardar un intervalo semánticamente mezclado.
- **P1-02 — Cronología de los intervalos (`services/evidence.py`, `repositories/evidence.py`).** Se retira `intervals.sort()` de `summarize_evidence` y `summarize_by_target` ordena por `occurred_at ASC, id ASC` en lugar de por el valor del intervalo: `[1, 7, 3, 14]` deja de convertirse en `[1, 3, 7, 14]`. La secuencia real es la que el scheduler podrá leer como cadena de repasos.
- **P1-03 — La cola no spoilea la recuperación (`ReviewQueueSection.tsx`, `i18n.ts`).** La forma esperada solo se muestra cuando la actividad es `recognition`; en `recall` y `sentence` se muestra una etiqueta neutra y el botón usa un `aria-label` sin la palabra. El `WordDrill` ya ocultaba la diana en Recall (`hideTarget`), así que la cola era la única fuga.
- **P2-02 — `record_evidence_bulk` blindado (`repositories/evidence.py`).** Deduplica eventos idénticos por `(target_type, target_id, task, activity, occurred_at)` y mantiene el `previous` en memoria actualizándolo tras cada fila (procesando el lote en orden cronológico), de modo que dos eventos distintos del mismo target encadenan su intervalo real en vez de compartir el de la BD. Admite `occurred_at` por entrada.
- **Tests.** Backend pytest **1769 passed** (+5: intervalo de evidencia ≠ ancla de retención e2e, cronología de `summarize_evidence` y `summarize_by_target`, dedupe y encadenado de `record_evidence_bulk`). Frontend vitest **65 ficheros/558 tests** (+1: Recall/Sentence ocultan la palabra, Recognition la muestra). `ruff check backend/` y `tsc --noEmit` limpios; `check_release_consistency` **3.35.1** exit 0.
- **CI verificable.** Commit `df78307432dddf9fe535860b2e3028258454faff` con el run [34470067665](https://github.com/jvelasca/english-tutor/actions/runs/34470067665) en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## [3.35.0] — 2026-09-10

**Longitudinal Learning Evidence 1.0: cierra los dos P1 de la auditoría de V3.34.0. (1) La recuperación demorada deja de estar anclada a la primera exposición y pasa a encadenarse (`evento_1 → intervalo_1 → evento_2 → …`) con el ancla en la última recuperación válida y el intervalo exigido por FSRS. (2) El repaso espaciado del léxico deja de inyectarse en el speaking micro-drill y estrena cola propia (`GET /api/learning/review`) con la actividad óptima por hueco de competencia. Sobre esa base nace el modelo de evidencia longitudinal: ledger append-only `learning_evidence` (attempts ≠ successes ≠ días ≠ intervalos), `event_role` (evidence/telemetry/informative) en `learning_events` y `interval_since_last_evidence`. Sin rehacer arquitectura y sin migración destructiva.**

Versión de app `3.34.0 → 3.35.0`. Backend (migración aditiva + servicio puro de evidencia + ancla encadenada + endpoint de repaso + schemas) + frontend (cola «Repaso de hoy» + `initialStep` del drill + API + i18n + tests); contrato HTTP aditivo y migración idempotente y sin backfill.

- **P1-1 — Ancla longitudinal de la retención (`services/lexicon.py`, `repositories/vocabulary.py`, `domain/vocabulary.py`).** El ancla deja de ser `min(first_seen, first_exposed_at)` para toda la vida del ítem. Nueva función pura `delayed_retrieval_decision(row, now, due_at)` → `{anchor_at, interval_days, required_days, credited}`: el ancla es la ÚLTIMA recuperación válida (`max(last_retrieval_at, last_recall_at)`) y solo la primera recuperación se mide desde la primera señal (`retrieval_anchor_at`); el intervalo exigido lo calcula FSRS cuando existe carta `lexicon` (`due_at`), y sin carta se conserva el suelo `RETENTION_MIN_INTERVAL_DAYS` (nunca por debajo: un lapse no es recuperación demorada). `record_retrievals(..., due_at=…)` persiste el resultado y encadena `last_retrieval_at`. Efecto: `D0 → D+3` acredita, pero `D+3 → D+4` ya no acredita si FSRS no ha vencido.
- **P1-2 — Cola de repaso propia, separada del speaking drill (`domain/review.py`, `routers/learning.py`, `schemas/learning.py`).** Nuevo `GET /api/learning/review` con esquema `ReviewQueueOut`/`ReviewQueueItem`: cartas FSRS `lexicon` vencidas ordenadas por urgencia (`fsrs.due_queue`, retrievability ascendente) y la actividad óptima por hueco (`services/lexicon.py::recommend_review_activity`) — sin base receptiva → `recognition`, sin `cued_recall` → `recall`, `production_gap` → `sentence`, resto → `recall` de mantenimiento. Se elimina `due_words` de `lexicon.drill_candidates` y la lectura de cartas FSRS de `get_drill_candidates`: la cola de speaking vuelve a ser solo huecos de producción oral. Payload con `due_at`/`state`/`stability`/`retrievability`/`elapsed_days`/`competence`/`evidence`; nunca el cue ni la forma esperada.
- **Modelo de evidencia longitudinal (`repositories/db.py`, `repositories/evidence.py`, `services/evidence.py`).** Tabla append-only `learning_evidence` (`occurred_at`, `skill`, `target_type`, `target_id`, `surface_form`, `lexical_unit`, `task`, `activity`, `success`, `interval_since_last_evidence`, `event_role`) + dos índices `(user_id, target_id)` y `(user_id, occurred_at)`; migración idempotente. Repositorio con `record_evidence` (deriva el intervalo desde la evidencia anterior del mismo ítem), `record_evidence_bulk` (volcado de producción en una transacción) y `summarize_by_target` (agregado SQL por ítem). Servicio puro con `EVIDENCE_ROLES`, `classify_event_role` (Recognition → `informative`; recall/retrieval/producción → `evidence`; `unclear` y el resto → `telemetry`), `interval_days` y `summarize_evidence` (`attempts`, `successes`, `distinct_success_days`, `intervals`).
- **`event_role` en el ledger de eventos (`repositories/learning.py`, `schemas/learning.py`).** Columna aditiva con default `''` para filas legacy, derivada en servidor por `classify_event_role` al registrar cada evento: la tabla deja de mezclar señales heterogéneas (una pregunta informativa de Recognition no es la misma señal que la recuperación de una palabra).
- **Escrituras y exposición de evidencia (`domain/vocabulary.py`, `services/lexicon.py`, `schemas/vocabulary.py`).** Cada intento de recall (acierto y fallo) escribe evidencia con su intervalo; `_record_retrieval` escribe la evidencia de recuperación del micro-drill; `record_production_text`/`analyze_text` vuelcan la evidencia de producción en bloque. Nuevo contador aditivo `recall_attempts` (intento ≠ éxito: sin él no se distingue "no lo intentó" de "falló") y `LexicalCompetence` gana `recall_attempts`; `LexicalItemOut` gana `evidence: LexicalEvidence` (`attempts`/`successes`/`distinct_success_days`/`intervals`) derivado del ledger por `summarize_by_target`.
- **UI de la cola de repaso (`ReviewQueueSection.tsx`, `api/learning.ts`, `wordDrill.tsx`, `i18n.ts`).** Nueva sección «Repaso de hoy» montada en el diccionario personal, junto al speaking drill: muestra cada ítem vencido con su actividad y razón y abre el `WordDrill` directamente en el peldaño recomendado (`initialStep`, también expuesto en `SpeakingDrillSection`). `WordDrill` arranca por defecto en Recognition y carga el peldaño pedido sin romper las degradaciones existentes. Claves i18n es/en nuevas (`i18n.parity.test.ts` en verde).
- **Tests.** Backend pytest **1764 passed** (+21: nuevo `test_longitudinal_evidence_v335.py` con la decisión pura del ancla, el encadenado + gate FSRS en repositorio, `event_role`, `summarize_evidence`, derivación del intervalo, evidencia negativa del fallo y exposición en el léxico; nuevo `test_review_queue_v335.py` con el mapeo de actividad, el orden por urgencia FSRS, el aislamiento y la retirada de la priorización FSRS del speaking drill; `test_lexicon.py`/`test_vocabulary.py`/`test_recall_v334.py` actualizados a la semántica V3.35). Frontend vitest **65 ficheros/557 tests** (+2 ficheros/+8 tests: API de la cola — restaura además los 3 casos preexistentes de `getProfile`/`analyzeText`/`getEvents` —, `WordDrill` con `initialStep` y `ReviewQueueSection`). `ruff check backend/` y `tsc --noEmit` limpios; `check_release_consistency` **3.35.0** exit 0.
- **CI verificable.** Commit `b304c257da1cffb408e127c80af1b43e12aa9955` con el run [34467763326](https://github.com/jvelasca/english-tutor/actions/runs/34467763326) en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## [3.34.0] — 2026-09-10

**Tercer eslabón del Dictionary → Learning Bridge: Recall 2.0. El peldaño intermedio del drill deja de ser una repetición oral de la palabra y pasa a ser una recuperación REAL por texto — el alumno ve el SIGNIFICADO (cue: traducción o definición sin spoiler) y teclea la palabra. A diferencia de Recognition (informativo), el acierto deja señal léxica PROPIA (`recall_successes`/`recall_days` + ledger `recalled`), acredita la recuperación demorada existente si supera el intervalo y reprograma la carta FSRS `lexicon` con intervalos reales (Good/Easy/Again); NUNCA acredita producción ni saca la palabra de candidatas. La escalera queda en 3 peldaños (`1 · Recognize` · `2 · Recall` · `3 · Sentence`), con el micrófono reservado a Sentence.**

Versión de app `3.33.1 → 3.34.0`. Backend (migración léxica + servicio puro + dominio + endpoints + schemas) + frontend (peldaño Recall por texto + API + i18n + tests); contrato HTTP aditivo (dos endpoints nuevos) y migración de BD idempotente y sin backfill.

- **Señal de recall en el léxico (`repositories/db.py`, `repositories/vocabulary.py`).** Migración idempotente en `vocabulary`: `recall_successes INTEGER NOT NULL DEFAULT 0`, `recall_days INTEGER NOT NULL DEFAULT 0`, `last_recall_at TEXT NOT NULL DEFAULT ''` (sin backfill). `VOCABULARY_EVENT_TYPES` añade `recalled` y `record_recalls(user_id, words)` hace upsert del contador y del día (una vez por día natural) e inserta el evento `recalled` en la MISMA transacción, **sin tocar `production_count` ni `<channel>_prod`** ni `first_seen`/`last_seen`; crea la fila si no existía (palabra solo consultada) con producción y exposición a 0. `get_vocabulary` incluye las columnas nuevas.
- **Cue puro y sin spoiler (`services/recall.py`).** `recall_prompt_for(word, entries)` → `{word, cue, cue_kind}` o `None`: prefiere `translation`; cae a `definition` SOLO si no contiene la palabra diana (una definición circular se descarta); sin cue válido → `None` (degradación `available=false`, sin evento). Nunca devuelve la forma esperada.
- **Dominio, scoring y FSRS (`domain/vocabulary.py`).** `get_recall_prompt` (el GET nunca expone la respuesta) y `submit_recall_attempt` (normaliza palabra y respuesta, igualdad estricta de superficie; `expected` solo tras responder; `delayed` = si el intento acreditó `retrieval_*` por superar el intervalo). `_reschedule_lexicon_card` siembra la carta `lexicon` en acierto (`reps+1`, Good/Easy) o aplica lapse (`Again`) solo si ya existía; nunca lanza. `get_drill_candidates` prioriza las palabras con carta FSRS `lexicon` vencida (`fsrs.is_due`).
- **Contrato HTTP (`routers/vocabulary.py`, `schemas/vocabulary.py`).** `GET /api/vocabulary/drill/recall` (`RecallPromptOut {word, available, cue, cue_kind}`) y `POST /api/vocabulary/drill/recall-attempt` (`RecallAttemptIn {word, answer}` → `RecallAttemptOut {word, correct, expected, delayed, recall_days}`); evento `learning_events` `drill:<word>:recall:ok|ko`; 409 si la palabra ya no tiene pregunta y 422 en entrada inválida (sin evento). `LexicalCompetence` gana `cued_recall`/`recall_successes`/`recall_days`, `LexiconSummary` gana `recalled` y `VocabularyEventOut.event_type` admite `recalled`.
- **Competencia léxica (`services/lexicon.py`).** `item_competence_matrix` expone `cued_recall` (recall_successes > 0), `recall_successes` y `recall_days` como señal propia (sin renombrar `retrieval_*`/`retention`, que siguen siendo recuperación demorada); `summary` cuenta `recalled`; `drill_candidates(..., due_words=…)` antepone las palabras vencidas conservando el orden por recuerdo dentro de cada grupo.
- **Peldaño «2 · Recall» por texto (`wordDrill.tsx`, `api/vocabulary.ts`, `types/api.ts`, `i18n.ts`).** Se retira el paso oral de palabra suelta: la escalera queda `1 · Recognize` · `2 · Recall` · `3 · Sentence` y el micrófono vive solo en Sentence. El Recall extrae un `RecallStep` presentacional: input de texto + botón Check, oculta la palabra diana durante el intento (el header muestra el cue) y la revela en el feedback; `available=false` degrada a Sentence sin romper la escalera. `onProduced` solo lo dispara Sentence (un recall correcto no saca la palabra de candidatas). Cliente: `DrillRecallPrompt`/`DrillRecallAttempt`, `getDrillRecallPrompt`/`submitDrillRecallAttempt`, claves i18n es/en nuevas y `stepRecall` renombrado a «2 · Recall».
- **Tests.** Backend pytest **1743 passed** (+20: nuevo `test_recall_v334.py` con 17 casos de cue/scoring/señal propia/recuperación demorada/FSRS/aislamiento, más 3 casos de `cued_recall`/`recalled`/priorización FSRS en `test_lexicon.py`). Frontend vitest **63 ficheros/549 tests** (+2: peldaño Recall por texto con cue visible y feedback correcto/incorrecto, y mocks de `DictionaryLookup`/`PersonalDictionary` actualizados al degrade Recognize → Recall → Sentence). `ruff check backend/` y `tsc --noEmit` limpios; `check_release_consistency` **3.34.0** exit 0.
- **CI verificable.** Commit `f9880f15fd7e19f17587c3cd25fa9362604af1d4` con el run [34451370871](https://github.com/jvelasca/english-tutor/actions/runs/34451370871) en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## [3.33.1] — 2026-09-10

**Endurecimiento del peldaño Recognition (auditoría V3.33.0): la posición de la respuesta correcta deja de ser fija por palabra (seed de intento stateless `question_id`) y el drill arranca de verdad en `1 · Recognize`, degradando a Recall solo si no hay pregunta. Evidencia y contrato de seguridad intactos: sigue siendo SOLO informativa y el GET nunca expone la correcta.**

Versión de app `3.33.0 → 3.33.1`. Backend (hash + seed + schemas) + frontend (arranque del drill + tests); cambio de contrato HTTP aditivo (campo opcional `question_id`); sin cambios de esquema de BD.

- **P1-01 — La correcta ya no está siempre en la misma posición (`services/dictionary_mcq.py`).** `recognition_options_for(word, entries, seed="")` deriva la permutación de `palabra + seed`; el seed es un nonce por intento que el `GET drill/recognition` entrega como `question_id` y el `POST drill/recognition-attempt` reenvía para reconstruir la MISMA permutación (premisa 21: sigue sin estado servidor). Reintentar la misma palabra rebaraja las opciones, así que no se puede memorizar «para `cat`, la primera es la correcta». Sin firmar: el seed solo ordena y la correcta nunca viaja, así que manipularlo no revela ni acredita nada.
- **P2 — `_stable_int` con SHA-256.** La suma ponderada por posición (colisionaba entre palabras distintas) se sustituye por `SHA-256(text)` (primeros 8 bytes), estable entre procesos/máquinas y con mucha mejor dispersión del índice. Se aplica SOLO al MCQ de diccionario: `listening_bottom_up` conserva su hash porque sus ids derivados son content-stable y cambiarlo re-barajaría ítems publicados.
- **P1-02 — El drill arranca en Recognition (`wordDrill.tsx`).** `WordDrill` abre en `step="recognition"` y carga la pregunta sola (antes abría en Recall y exigía un clic manual); al montar o cambiar de palabra reinicia el intento. Si el backend responde `available=false`, degrada a Recall de forma elegante (`Practicar → Recognize → Recall → Sentence`, o `Practicar → Recall` sin pregunta). La degradación no pisa una elección manual de otro paso (guarda con `setStep(current => …)`). Cada entrada en Recognize pide un `question_id` nuevo.
- **Contrato (`schemas/vocabulary.py`, `api/vocabulary.ts`, `types/api.ts`).** `RecognitionQuestionOut.question_id: str = ""` y `RecognitionAttemptIn.question_id: str = Field(default="", max_length=64)` (aditivo y retrocompatible); `DrillRecognitionQuestion.question_id` y `submitDrillRecognitionAttempt(..., questionId)`.
- **Tests.** Backend pytest **1723 passed** (+1 neto): nuevo test puro de permutación por seed (mismo seed ⇒ mismo orden; seeds distintos ⇒ la correcta cambia de posición) y determinismo/aislamiento reescritos sobre `question_id`. Frontend vitest **63 ficheros/547** (+1): nuevo test «reentrar en Recognize pide una pregunta nueva», arranque directo en Recognize y degradación automática a Recall. `ruff check .` y `tsc --noEmit` limpios; `check_release_consistency` **3.33.1** exit 0.
- **CI verificable.** Commit `dcaa74cacf4912c3f747a104e491d6a0723c5ca7` con el run [34447562780](https://github.com/jvelasca/english-tutor/actions/runs/34447562780) en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency, Beta V3.0 gate, content validation, Playwright E2E). Aclaración de la auditoría anterior: V3.33.0 también tenía CI verde (run [34383922526](https://github.com/jvelasca/english-tutor/actions/runs/34383922526), sha `5207729`); el «no verificable» venía de mirar *commit statuses* (`/status`, en `pending`) en vez de los *check runs*.

## [3.33.0] — 2026-09-09

**Segundo eslabón del Dictionary → Learning Bridge: el peldaño Recognition (MCQ definición ↔ palabra) en la escalera compartida de drill — la pregunta la sirve y puntúa el backend (determinista por palabra, premisa 21, sin estado servidor) y su evidencia es SOLO informativa: un `learning_events` `drill:<word>:recognition:ok|ko`, sin escribir en `vocabulary`, FSRS, mastery ni usage (V3.13: el MC de reconocimiento no demuestra destrezas productivas).**
Versión de app `3.32.0 → 3.33.0`. Backend (contenido + dominio + endpoints + schemas) + frontend (UI del peldaño + API + tests); sin cambios de esquema de BD ni de contrato HTTP previo.

- **Pregunta determinista en el backend (`services/dictionary_mcq.py`).** `recognition_options_for(word, entries)` → `(options, correct_index)` o `None`, puro y determinista sobre la caché global `dictionary_entries` (`repositories/dictionary.py` gana `list_entries()`). Opción correcta = significado real de la diana en un modo consistente (`translation` si existe y hay distractores; si no, `definition`, sin mezclar idiomas entre opciones); distractores de otras entradas globales, preferir mismo `pos`, deduplicados entre sí y frente a la correcta; barajado estable ocultando la correcta (patrón de `listening_bottom_up`: `_stable_int`/`_place_options`). Sin distractores suficientes → `None`: el peldaño degrada con aviso.
- **Dominio y endpoints (premisa 21).** `domain/vocabulary.py`: `get_recognition_question` → `{word, available, options}` (el GET NUNCA expone la correcta) y `submit_recognition_attempt` → `{word, correct, correct_index, selected_index}` recomputando con la misma función pura, sin producción ni retrieval. `routers/vocabulary.py`: `GET /api/vocabulary/drill/recognition` (degradación 200 `available=false` sin evento) y `POST /api/vocabulary/drill/recognition-attempt` (evento `drill:<word>:recognition:ok|ko`; 409 si la palabra ya no tiene pregunta y 422 en índice/palabra inválidos, ambos sin evento). Schemas `RecognitionQuestionOut`/`RecognitionAttemptIn`/`RecognitionAttemptOut`.
- **Peldaño «1 · Recognize» en la escalera compartida (`wordDrill.tsx`).** Pasos `1 · Recognize`, `2 · Word`, `3 · Sentence` (renumeración de las claves i18n) visibles desde el lookup Y el hub. El paso NO usa micrófono: opciones como botones accesibles, submit con `selected_index`, feedback con la correcta revelada solo tras responder y aviso de no disponible; el acierto NO dispara `onProduced` ni `refreshEntry`. Cliente: tipos `DrillRecognitionQuestion`/`DrillRecognitionAttempt`, `getDrillRecognitionQuestion`/`submitDrillRecognitionAttempt` y claves i18n es/en nuevas.
- **Tests backend (`test_dictionary_recognition_v333.py`, +11).** Determinismo y ausencia de `correct_index` en el GET · acierto → `drill:quokka:recognition:ok` con CERO cambios en `vocabulary`/`vocabulary_events` · fallo → `:ko` con la correcta revelada solo al responder · modo `definition` sin traducciones y textos duplicados que nunca llegan a opciones · los eventos `recognition:ok` no alteran la salida de candidatas (`drill_ok_days`/`drill_candidates`, con contrafactual) · aislamiento A/B · sin entrada/sin distractores → `available=false`/409 sin evento · normalización e índice fuera de rango → 422.
- **Tests frontend (+4 vitest).** `describe` Recognition en `DictionaryLookup.test.tsx` (acierto informativo sin re-lookup `/dictionary`; fallo con la opción correcta revelada) y en `PersonalDictionary.test.tsx` (el acierto no saca la candidata; degradación sin significado disponible), más la renumeración de pasos en las aserciones existentes.
- **Verificación.** Backend pytest **1722 passed** (+11 sobre v3.32.0) + `ruff check .` limpio; frontend vitest (63 ficheros/546) + `tsc --noEmit` limpios; `check_release_consistency` **3.33.0** exit 0 (detalle con conteos en `release-notes-v3.33.0.md`).

## [3.32.0] — 2026-09-09

**Primer eslabón del Dictionary → Learning Bridge: la consulta del diccionario (V3.30, D3) se convierte en puerta a la práctica real con «Practicar esta palabra», que reutiliza la escalera oral existente (Recall → Sentence) sin un solo endpoint nuevo, y produce evidencia idéntica a la de cualquier otra práctica (sin etiquetas de origen).**

Versión de app `3.31.1 → 3.32.0`. Frontend (UI + refactor de extracción) + backend de tests de aceptación; sin cambios de esquema de BD ni de contrato HTTP.

- **«Practicar esta palabra» en la tarjeta del lookup (`DictionaryLookup.tsx`).** La tarjeta de resultado del diccionario gana una acción secundaria junto al `ListenButton` que monta, in-line bajo la tarjeta, la escalera de drill de esa palabra (userId + word). Gating idéntico al resto de la práctica: oculta sin `userId`. Al producir la palabra en el drill, la entrada del diccionario se re-consulta en silencio para actualizar las marcas de uso (`usage.tracked`, producción) sin interrumpir el drill.
- **Refactor de extracción neutro (`wordDrill.tsx`).** `WordDrill`, `SpeakingDrillSection`, el tipo `DrillStep` y el helper `isSentenceAttempt` se extraen de `PersonalDictionary.tsx` a un módulo compartido `frontend/src/features/vocabulary/wordDrill.tsx` y se reimportan: misma UI, mismo comportamiento, cero cambio de contrato (regresión cubierta por `PersonalDictionary.test.tsx`).
- **Cierre del puente: nada de evidencia de origen.** Practicar desde el diccionario usa los mismos endpoints de drill (`drill/attempt`, `drill/sentence-context|attempt`), que ya aceptan palabras arbitrarias: un éxito llama `record_production_text(speaking, as_unit=True, activity="drill")` + los `learning_events` `drill:<word>:ok` habituales. El Student Model no distingue el origen (D3 intacto: el lookup en sí sigue sin escribir nada; solo la acción explícita «Practicar» y su resultado escriben).
- **Tests de aceptación backend (`test_dictionary_bridge_v332.py`, +3).** `test_lookup_new_word_read_only_and_practice_writes_identical_evidence`: A consulta una palabra nueva → sin filas ni eventos (`usage.tracked=false`), practica tras consultar → `speaking_prod=1`, `production_count=1`, `exposure_count=0`, un evento `produced` (channel=speaking, activity=drill) y un `learning_events` `drill:quokka:ok`, con la fila IDÉNTICA a la de B que practica la misma palabra directamente (aislamiento A/B) · `test_sentence_step_after_lookup_equivalent_evidence_and_d3_closure`: el paso frase acredita la misma evidencia con detalle `drill:<word>:sentence:ok`, y una segunda consulta ve la palabra ya trackeada sin crear filas ni eventos adicionales (cierre D3) · `test_lookup_and_practice_isolated_between_users`: lo que hace A no toca el léxico de B hasta que B practica por su cuenta.
- **Verificación.** Backend pytest **1711 passed** (+3 sobre v3.31.1) + `ruff check .` limpio; frontend vitest (63 ficheros) + `tsc --noEmit` limpios; `check_release_consistency` 3.32.0 exit 0 (detalle con conteos en `release-notes-v3.32.0.md`).

## [3.31.1] — 2026-09-09

**Cierre de la auditoría V3.31.0 sobre el diccionario de consulta: el modelo explícito debe estar instalado (no solo ser utilizable), los fallos de generación dejan de reintentar en bucle (negative cache con TTL), la generación de contenido nuevo queda limitada por usuario y global, y el dueño de un vuelo ya no puede dejar la palabra clavada si Ollama se cuelga (tope servidor de 90 s).**

Patch de endurecimiento de la auditoría V3.31.0 (P1-01 residual y P2 de robustez del diccionario). Versión de app `3.31.0 → 3.31.1`. Solo backend + docs; sin cambios de UI ni de esquema de BD.

- **P1-01 — `pick_model` exige modelo explícito INSTALADO (`services/translate.py`).** Antes, un modelo explícito solo tenía que ser utilizable (no estar en `UNUSABLE_MODELS`) para llegar a Ollama aunque no estuviera instalado: la comprobación de instalados solo ocurría en el fallback. Ahora `pick_model` consulta `installed_models()` (con su caché de 300 s) y solo devuelve el explícito si está instalado y es utilizable; si no, cae al mismo fallback automático. Un modelo no instalado ya no puede provocar un error de Ollama ni una degradación evitable.
- **P2 — Negative cache del generador (`domain/vocabulary.py`).** Un fallo de generación (Ollama caído, respuesta inválida o timeout) marca la palabra en memoria durante `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS` (30 s): las consultas siguientes degradan a `definition_source="none"` sin volver a llamar al modelo, y la entrada se limpia perezosamente al vencer (o al conseguir una generación). Evita la tormenta `cat → retry → cat → retry`.
- **P2 — Rate limit de generación nueva (por usuario y global).** `DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE` (10) y `DICTIONARY_MAX_GENERATIONS_PER_MINUTE_GLOBAL` (40) limitan las palabras NUEVAS por minuto; solo el dueño de un vuelo genera, así que cada palabra consume cupo una vez y lo cacheado no consume. Sin cupo → degradación normal (200 con `definition_source="none"`), nunca 5xx.
- **Tope servidor del dueño del vuelo.** La generación se envuelve en `asyncio.wait_for` con `DICTIONARY_GENERATION_TIMEOUT_SECONDS` (90 s): si Ollama se cuelga, el vuelo degrada, se libera y se marca la negative cache (los waiters ya tenían su tope defensivo de 60 s; el dueño ahora también).
- **Semántica documentada del contenido.** La caché `dictionary_entries` es global y canónica (sin `model_id`): el parámetro `model` solo influye en la generación de contenido nuevo, nunca en qué contenido se sirve (docstrings de `dictionary_content.py`, `domain/vocabulary.py` y `schemas/vocabulary.py`).
- **Tests.** `test_translate.py` (+3: explícito utilizable no instalado → fallback; sin preferidos → primer usable; sin modelos → default; el resto con parque inyectado por defecto para hermetismo) y nuevo `test_dictionary_hardening_v3311.py` (+8: negative cache suprime el reintento inmediato y expira, el éxito limpia la marca, cupo por usuario bloquea palabras nuevas pero no cacheadas, cupo global compartido entre usuarios, sin cupo nunca lanza, timeout del dueño degrada y libera el vuelo, D3 intacto en todas las rutas).
- **Verificación.** Backend pytest **1708 passed** (+11 sobre v3.31.0) + `ruff check .` limpio; frontend vitest + `tsc --noEmit` limpios; `check_release_consistency` 3.31.1 exit 0 (detalle con conteos en `release-notes-v3.31.1.md`).

## [3.31.0] — 2026-09-09

**Cierre de los hallazgos residuales de la auditoría profunda de V3.30.1 sobre el diccionario de consulta: el single-flight ya no puede colgar a los waiters si el dueño del vuelo se cancela (ni colgarse el propio cliente si Ollama se queda mudo), la caché de contenido previa a V3.31 se invalida y regenera una sola vez, y el contrato del diccionario queda blindado en ambos lados (tests del path real y de la migración de upgrade + tipo y timeout en el cliente).**

Release de estabilización del diccionario de consulta (auditoría V3.30.1 sobre v3.30.1). Versión de app `3.30.1 → 3.31.0`. Backend + frontend de contrato (tipos y API); sin cambios de UI.

- **Single-flight robusto a cancelación (`domain/vocabulary.py`).** `_ensure_cached_content` captura el `CancelledError` del dueño del vuelo y resuelve el Future con `None` antes de propagar la cancelación (antes el `finally` retiraba la clave sin resolver el Future y los waiters se quedaban esperando para siempre); además los waiters esperan con un tope defensivo de 60 s (`asyncio.wait_for` + `shield`) y degradan a `definition_source="none"` si el ganador colgara.
- **Invalidación del contenido de caché previo a V3.31 (`services/dictionary_content.py` + `repositories/db.py`).** `GENERATOR_VERSION` sube a `1.1.0`: el contenido cacheado antes de V3.31 —incluido el que V3.30.1 etiquetó como `1.0.0` al migrar y que es indistinguible por fila del generado con el parser greedy de V3.30— deja de servirse como fresco y regenera de forma perezosa una sola vez al primer lookup. La migración define `DICTIONARY_LEGACY_VERSION = "1.0.0"` como marca deliberadamente distinta de la versión actual y la aplica a las filas sin versión.
- **Tests de la migración de upgrade y del path real del diccionario.** `test_migration_upgrade_from_v330_adds_version_and_keeps_content` simula una BD creada por V3.30.0 (tabla sin `generator_version`) y verifica el `ALTER` aditivo + backfill + conservación del contenido + idempotencia + que no se sirve como fresca; `test_dictionary_path_never_uses_unusable_explicit_model` ejercita la cadena real `lookup_dictionary → _fetch_chat → pick_model` con un modelo explícito en `UNUSABLE_MODELS` y verifica que nunca llega a Ollama; `test_legacy_content_regenerates_lazily_once` y `test_inflight_leader_cancel_resolves_waiters_without_hanging` completan la cobertura negativa.
- **Contrato del cliente anclado y timeout (`frontend`).** Tipo `DictionaryLookupRequest` en `types/api.ts` y cuerpo tipado en `lookupDictionaryWord`; test en `vocabulary.test.ts` que verifica `POST /api/vocabulary/dictionary?user_id=` + `Content-Type: application/json` + body `{word}`; la llamada se envuelve en `withTimeout` (120 s) para que la tarjeta no se quede en «cargando» si Ollama cuelga.
- **Verificación.** Backend pytest **1697 passed** (+4 sobre v3.30.1) + `ruff check .` limpio; frontend vitest + `tsc --noEmit` limpios; `check_release_consistency` 3.31.0 exit 0 (detalle con conteos en `release-notes-v3.31.0.md`).

## [3.30.1] — 2026-09-09

**Endurecimiento del diccionario de consulta tras la auditoría V3.30.0: una sola generación LLM por palabra en concurrencia (single-flight), la política `UNUSABLE_MODELS` ya no se puede saltar pidiendo un modelo explícito, y la caché global `dictionary_entries` versiona su contenido para poder regenerarse cuando cambie el prompt/política.**

Patch de la auditoría V3.30.0 (los tres P1: concurrencia del generador, modelo explícito frente a `UNUSABLE_MODELS`, caché sin versión/proveniencia). Versión de app `3.30.0 → 3.30.1`. Solo backend + docs; la UI no cambia.

- **P1-01 — Single-flight de generación (`domain/vocabulary.py`).** `_ensure_cached_content` mantiene un registro en vuelo por palabra (Future por proceso): N consultas simultáneas de la misma palabra comparten exactamente UNA llamada al LLM y UNA escritura en BD; los waiters reciben el mismo resultado y un fallo no provoca reintentos en cascada. El `INSERT OR IGNORE` anterior protegía la fila pero no la generación.
- **P1-02 — La política de modelo ya no se salta con un explícito (`services/translate.py`).** `pick_model` descarta cualquier modelo declarado en `config.UNUSABLE_MODELS` aunque el cliente lo solicite y cae al mismo fallback automático (modelo rápido instalado utilizable o el por defecto). Corrige diccionario y traducción a la vez (un único punto de política).
- **P1-03 — Caché versionada (`dictionary_entries.generator_version`).** Columna aditiva + migración idempotente con backfill `'1.0.0'` del contenido V3.30 (mismo prompt/política) en `repositories/db.py`; `save_entry` (upsert `ON CONFLICT DO UPDATE`) sustituye a `insert_entry` y da semántica real a `updated_at` (última regeneración); el dominio solo sirve caché cuya `generator_version` coincide con la actual (`GENERATOR_VERSION` en `services/dictionary_content.py`) — una entrada obsoleta por un cambio futuro de prompt se regenera y sobrescribe en lugar de quedar como contenido obsoleto permanente.
- **P2 — Parser JSON robusto (`services/dictionary_content.py`).** `parse_content` extrae el PRIMER objeto `{…}` válido con barrido `raw_decode` en cada `{` (la regex greedy `{.*}` podía tragarse `{…} texto {…}` hasta el último cierre).
- **Verificación.** Backend pytest **1693 passed** (+9 tests: single-flight misma palabra y dos usuarios, fallo concurrente degradado sin reintentos, regeneración por versión obsoleta, reuso de versión fresca, parser con varios objetos y llaves en prosa; `pick_model` con explícito no utilizable) + `ruff check .` limpio; sin cambios de frontend; `check_release_consistency` 3.30.1 exit 0 (detalle con conteos en `release-notes-v3.30.1.md`).

## [3.30.0] — 2026-09-09

**Diccionario de consulta con marca de uso y aprendizaje: busca cualquier palabra y recibe su definición/traducción generadas por el modelo local y cacheadas en BD, una frase de ejemplo determinista del banco y el estado de esa palabra en tu aprendizaje (vista/producida/dominada), en la nueva vista «Consultar» del hub Vocabulario.**

Cierra el candidato V3.30 (diseño en `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`; decisiones D1/D2/D3). Versión de app `3.29.0 → 3.30.0`.

- **Endpoint `POST /api/vocabulary/dictionary` (backend).** Consulta una palabra arbitraria (esté o no en el léxico del alumno) y devuelve: la marca de uso/aprendizaje derivada en servidor con los cómputos puros de `services/lexicon.py` (estado, mastery/recall, contadores, matriz de competencia y agregado por `lexical_unit` cuando la forma canónica difiere de la buscada), la frase de ejemplo determinista del banco (`services/example_sentences.py`, nunca la plantilla del drill) y la definición/traducción de la caché global `dictionary_entries`. **D3 — solo lectura**: la consulta no crea filas en `vocabulary` ni eventos en `vocabulary_events`, no mueve mastery (tests negativos).
- **Generador de contenido con el modelo local (D1, Fase B).** `services/dictionary_content.py` pide al modelo un objeto JSON `{pos, definition, translation}` (`temperature=0`, prompt estructurado) con parseo tolerante (cercas de Markdown, texto circundante, POS canónico) y límites; el dominio persiste con `INSERT OR IGNORE` en la tabla global `dictionary_entries` (la primera consulta de cada palabra es la única que paga el modelo; las siguientes son deterministas). Degradación controlada: modelo caído o respuesta inválida → 200 con `definition_source="none"` y el resto de la entrada intacto; si persistir falla se sirve el contenido en memoria.
- **UI «Consultar» (Fase C).** Nueva vista alterna en APRENDER → Vocabulario junto al diccionario personal (`DictionaryLookup.tsx`, conmutador en la vista de diccionario de `QuizRoutePage`, solo Vocabulario la declara): caja de búsqueda accesible, tarjeta con palabra + POS/CEFR/kind y audio TTS, definición EN, traducción ES, ejemplo del banco con audio, y sección de uso (badge de estado, recall, contadores, chips de competencia o agregado por unidad). Estados vacío/carga/error de red con retry/error de entrada; el modelo caído muestra la tarjeta de uso igualmente. i18n `dictionary.lookup.*` es/en.
- **Verificación.** Backend pytest **1684 passed** (39 tests del diccionario en `test_dictionary_lookup.py` y `test_dictionary_content_v330.py`) + `ruff check .` limpio; frontend vitest **538 passed** (63 archivos) + `tsc --noEmit` limpio; `check_release_consistency` 3.30.0 exit 0 (detalle con conteos en `release-notes-v3.30.0.md`).

## [3.29.0] — 2026-09-09

**Listening Engine 4.0 — Fase 3 (núcleo): alineación por palabra offline (`word_alignment_proxy` con faster-whisper `word_timestamps=True`), karaoke palabra a palabra, controles de audio precisos (seek slider + bucle A/B con scheduler rAF), salto a la palabra fallada (normal/slow) y evidencia `word_breakdown_json`.**

Implementa el núcleo de la Fase 3 de `docs/LISTENING_ENGINE_4.0.md` (§14) con el plan `v3.29_nucleo_fase_3…plan.md` (P1–P6). El candidato diccionario de consulta se reprioriza a V3.30. Versión de app `3.28.1 → 3.29.0`.

- **P1 — Motor de alineación por palabra (backend).** `stt.transcribe_words` ejecuta faster-whisper con `word_timestamps=True`; el nuevo módulo puro `services/word_alignment_proxy.py` cachea la alineación en un sidecar `{wav}.words.json` (formato con `source_text`, `engine`, `sync: "asr_word_proxy"`, `coverage`; escritura atómica). `align_words` alinea el ASR contra el texto audible con `SequenceMatcher`, interpola de forma monótona las palabras no reconocidas y descarta la señal si la cobertura cae por debajo de ~80 % (degradación controlada al sync de frase). Hooks en `generate_listening_audio.py`, `domain.get_audio` (primeras síntesis bajo demanda) e `import_audio.py` (biblioteca humana) + script de backfill `generate_word_alignments.py` (idempotente, `--force`).
- **P2 — `word_timings` en el payload.** `word_timings_for` resuelve el WAV canónico (voz default/variante `normal`; los ítems derivados `d-` reutilizan el sidecar del padre), lee el sidecar y asigna a cada palabra su `sentence` **por tiempo** contra `coarse_sentence_timings` (funciona con `repetition_policy="twice"` y sin `duration`). Se sirve en `_public_with_flow`/`next_question` solo para TTS `audio_ready`; el campo `word_timings` de `ListeningQuestion` es opcional (`[]` = degradación).
- **P3 — Evidencia de palabra fallada.** Columna aditiva nullable `word_breakdown_json TEXT` en `listening_attempts` (migración idempotente inline, patrón V3.27/V3.28). `record_attempt` la serializa con `json.dumps`; `submit_production` persiste el breakdown del dictado fallado y `submit_answer` el target (palabra diana) en un acierto incorrecto de cloze/segmentation (`NULL` en el resto). Sin consumo en agregados todavía (V3.30).
- **P4 — Karaoke palabra a palabra (frontend).** `ListeningWordTiming` en tipos; helpers puros en `microFlow.ts` (`wordTimingsOf`, `activeWordIndex`, `wordsForSentence`, `scaleWordTimings`, `variantTimeScale`); nuevo `KaraokeTranscript.tsx` (Card, `lang="en"`, chips por palabra clickeables → seek, revelado por frase de `revealSentenceIndexes`, palabra activa `bg-primary/15`); `ListeningPractice` lo renderiza en lugar de `CoarseTranscript` cuando hay `wordTimings` y transcript visible (incluida la revelación completa tras un resultado de dictado/shadowing); slow/fast escalan los tiempos por el ratio de `speech_rate`.
- **P5 — Controles de audio precisos.** `AudioController` notifica `duration` en `loadedmetadata` (`onDuration`) y sustituye el chequeo de bucle en `timeupdate` por un scheduler `requestAnimationFrame` inyectable (`AudioFrameScheduler`; rebobinado en cuanto `currentTime >= segment.end`; `timeupdate` queda como respaldo sin rAF). La tarjeta de audio gana un **seek slider** continuo (visible cuando `audio_ready` y duración real > 0) y el control de **bucle A/B** («marcar inicio» → «bucle A–B» → «quitar bucle»).
- **P6 — Salto a la palabra fallada.** `failedWordTiming` (helper puro en `microFlow.ts`): para dictado, primera palabra de `breakdown.missing`/`substituted[].expected`; para MCQ cloze incorrecto, la opción correcta (diana); localiza la palabra en `wordTimings` (tokens normalizados) y, si no aparece (reducción/expansión), cae al intervalo de la frase contenedora (`null` sin respaldo → botón oculto). Botones «repetir palabra fallada» en **normal** y **slow** en el resultado de dictado y en la tarjeta de reintento del MCQ incorrecto (`seek(start−0.05s)` + `loop(start,end)` + `play(variante)`).
- **Documentación.** Spec `docs/LISTENING_ENGINE_4.0.md` a v1.2: §6.4/§6.5 documentan el contrato `word_timings` + sidecar + escalado y el estado real de la Fase 3; roadmap §14 marca el **núcleo de Fase 3 implementado** (V3.29); checklist §15 cierra los puntos 8-9; nota de cierre en `docs/RELEVO.md`; docstrings/comentarios de karaoke en el frontend.
- **Verificación.** Backend pytest + ruff, frontend vitest + `tsc --noEmit` y `check_release_consistency` 3.29.0 exit 0 (detalle con conteos en `release-notes-v3.29.0.md`).

## [3.28.1] — 2026-09-09

**Patch de la auditoría V3.28.0 (Listening Engine 4.0, Fase 2 en consolidación): dictado parcial derivado servible, scoring exacto por token del dictado escrito, Gonnago/reducciones detectadas por token y frontera de palabra, y verificación del AudioController con `seek` notificando en pausa.**

Aplica los P1 de la auditoría del candidato v3.28.0 (plan `v3.28.1_patch_auditado_e76303f2.plan.md`). Versión de app `3.28.0 → 3.28.1`.

- **P1-01 — Dictado parcial derivado servible.** `derived_catalog` devuelve ahora `(by_id, recognition_pool, production_pool)` con `PRODUCTION_SERVED_TASKS = ("partial_dictation",)`; `services/listening.py` expone `DERIVED_PRODUCTION_POOL` y `pick_next_question` acepta `bottom_up_production_questions` para servir los dictados parciales del nivel de trabajo **tras** agotar cloze/segmentación. El dominio (`next_question`) solo pasa ese pool en sesión Caso A (capa `recognition`) **y** cuando el diagnóstico marca `dictation` débil/sin muestra — el dictado parcial nunca entra en la puerta/certificación (tests negativos de pools, selector y gate).
- **P1-02 — Scoring exacto por token del dictado escrito.** Nueva función pura `dictation_score(reference, heard)` junto a `production_score`: coincidencia exacta de tokens normalizados vía `word_alignment`, sin Soundex/phoneme proxy/prosodia (`new system` ≠ `new sistem`, score 50/100). `submit_production` la aplica a todo `task_type == "dictation"` (banco y parcial derivado); el shadowing oral conserva el composite. La UI oculta la fila fonética en el resultado de dictado.
- **P1-03 — Gonnago y reducciones por token/boundary.** Helper compartido `contains_word_token` (regex de frontera, sin distinguir mayúsculas) en `services/listening_bottom_up.py`, usado por `_reductions_in` (un token concatenado tipo `Gonnago` no es la reducción `gonna`), `_is_eligible_token` (excluye solo el token exacto) y `_connected_speech_realized` de `services/listening.py` (con `STRONG_REDUCTIONS`/`MILD_CONTRACTIONS`). El ítem `l16` corrige su contenido a `"Gonna go …"` (audio digest regenerado) y el dictado parcial de frase completa se mantiene coherente.
- **P1-04/P2-01 — AudioController: integración verificada y `seek` arreglado.** `ListeningPractice.tsx` usa de forma real `play(url)` (variante de la escalera) + `pause()` y alimenta el resaltado de frase activa con `playing`/`currentTime`; `seek`, `setRate` fino, `loop`, `replaySegment` y `markSegmentStart` quedan sin UI y se documenta su mapeo para V3.29 (Fase 3). `audioController.ts::seek(time)` notifica ahora `onCurrentTime(target)` además de fijar `currentTime`, para que el estado React se actualice aunque el audio esté pausado.
- **Documentación.** `release-notes-v3.28.0.md` corrige el bullet del cloze (heurística determinista real: primera frase de un solo hablante, token de contenido único de 3+ letras, sin stop words ni reducciones, selección estable por id+slot y distractores del banco del nivel que nunca aparecen en la frase); docstrings/comentarios con `Gonnago` actualizados al contrato token/boundary; nota V3.28.1 en `docs/RELEVO.md`.
- **Verificación.** Backend pytest **1693 passed** (backend 1619 + launcher 74) + `ruff check .` limpio; frontend vitest **506 passed** (61 archivos) + `tsc --noEmit` OK; `check_release_consistency` 3.28.1 exit 0.

## [3.28.0] — 2026-09-09

**Listening Engine 4.0 — Fase 2 (Bloques A–F): micro-flujo unificado en rutas por nivel y drill, AudioController 4.0 en frontend, tareas bottom-up derivadas del corpus (cloze auditivo/dictado parcial/segmentación), transcript dinámico con sync grueso de frase, Shadowing 2.0 con playback de la grabación, y E2E adaptativos + negativos del contrato pedagógico.**

Cierra los Bloques A-F de la Fase 2 de la especificación `docs/LISTENING_ENGINE_4.0.md` (§14) con el plan `v3.28_listening_engine_fase_2_f74493a3.plan.md` (resuelve el P1-01 de la auditoría V3.27 y aborda P1-02/P1-03/P1-05). El candidato diccionario de consulta se reprioriza a V3.29. Versión de app `3.27.0 → 3.28.0`.

- **Bloque A — Micro-flujo unificado en nivel y drill (P1-01).** `next_question` sirve `flow` + `transcript_policy` también en rutas por nivel (`level=X`) y drill (`mode=failed`) a través del helper `_public_with_flow` (encapsula `_public` + `flow_for_question` con el perfil auditivo del alumno); el modo `mastered` conserva el repaso compacto sin flow (contrato fijado por E2E-04). El router no cambia de contrato: `flow`/`transcript_policy` siguen siendo campos opcionales para consumidores antiguos.
- **Bloque B — AudioController 4.0 (frontend).** Nuevo módulo puro `features/listening/audioController.ts` sobre `HTMLAudioElement`: `play`/`pause`/`seek(t)`/`setRate(r)` con `preservesPitch` y selección de la variante de URL (slow/normal/fast) más cercana al rate pedido, `loopSegment(start,end)`, `replayCurrent`, `markSegment` y suscripción de `currentTime`/`ended`/`ratechange`; hook React `useAudioController` que expone el estado y `ListeningPractice.tsx` consume el controller para while1/while2/replay en lugar de `new Audio()` sueltos.
- **Bloque C — Bottom-up derivado del corpus (P1-02/P1-03 parcial).** Nuevo `services/listening_bottom_up.py` que deriva ítems deterministas de cada ítem del corpus por `id` + nivel: **cloze auditivo** (MCQ con token diana por heurística + distractores de un banco por nivel), **dictado parcial** (producción con hueco de 1-N tokens y scoring determinista por token) y **segmentación** (pares contraídos/reducidos solo donde el corpus los realiza; si no hay candidato fiable el ítem no se emite — nunca se inventa audio). Los derivados (`derived=True`, `task_type` cloze/partial_dictation/segmentation) se sirven como volumen extra de decodificación (selector con perfil Caso A) y **nunca entran en el pool de ruta ni en la certificación** (filtrado defensivo en `route_questions`/`level_items`, replicando `listening_generated`); el audio reutiliza el del ítem padre (sin WAV duplicados).
- **Bloque D — Transcript dinámico con sync grueso.** Backend: `coarse_sentence_timings` calcula timings de frase heurísticos y proporcionales (por tokens sobre `clean_transcript` + `duration`), etiquetados `sync: "coarse_heuristic"` (nunca alineación acústica) y servidos en el payload cuando el ítem tiene flow. Frontend: `microFlow.ts` gana `timingsOf`/`activeSentenceIndex`/`revealSentenceIndexes` y el nuevo componente `CoarseTranscript` pinta hidden/partial/full y resalta la frase activa según `currentTime` del AudioController; la transcripción parcial revela solo la frase/segmento permitido por `transcript_state_inicial`.
- **Bloque E — Shadowing 2.0 (sin llamarlo pronunciación).** El paso shadowing de Listening reproduce la grabación real del alumno (`RecordingPlayButton` reutilizado de Speaking, blob en memoria) y envía señales auxiliares no bloqueantes calculadas en cliente —`shadowing_duration_ms` y `shadowing_speech_rate` (duración y velocidad de habla)— que el backend persiste con migración aditiva idempotente (columnas nullable, patrón V3.27). Son informativas: **no tienen peso de mastery ni de gate** (tests negativos lo fijan); el proxy de texto se mantiene honesto (`pronunciation_source=transcript`).
- **Bloque F — E2E adaptativos y negativos del contrato pedagógico.** `test_listening_e2e_v328.py` recorre con `TestClient` el ciclo diagnóstico → perfil → pregunta → flow → evidencia: **E2E-01** A1 recognition débil → `profile=recognition`/`bottom_up_path` y pregunta adaptativa de capa recognition con flow de 5 etapas · **E2E-02** B2 connected speech débil → `connected_speech_path` y el shadowing deja de ser opcional (`allow_skip=False`) · **E2E-03** comprehension fuerte + inference débil → `top_down_path` · **E2E-04** sesión `mastered` → modo compacto sin flow. Negativos: ítem derivado nunca aparece en la certificación; responder un derivado no mueve la puerta; `transcript_used` se persiste de forma fiable; B2 no permite reveal manual antes de Post.
- **Verificación.** Backend pytest **1683 passed** + `ruff check .` limpio; frontend vitest **505 passed** (61 archivos) + `tsc --noEmit` OK; `check_release_consistency` 3.28.0 exit 0; release notes `release-notes-v3.28.0.md`.

## [3.27.0] — 2026-09-09

**Listening Engine 4.0 — Fase 1 (micro-flujo por ítem): el backend se vuelve la fuente única de la política pedagógica y sirve `flow` + `transcript_policy` por pregunta; el Listening práctico gana perfil auditivo visible en la UI (casos A-D), evidencia ampliada por intento (5 columnas nuevas) y revelado de transcripción progresivo por CEFR.**

Implementa el plan V3.27 (`docs/PLAN-V327-LISTENING-ENGINE-4.md`, especificación `docs/LISTENING_ENGINE_4.0.md`). Versión de app `3.26.0 → 3.27.0`.

- **Política de fases en el backend (decisión de arquitectura §3.1).** Nuevo módulo puro `services/listening_flow.py`: `flow` (pasos pre/while1/while2/post/shadowing con `task`, `transcript_state_inicial`, `allow_skip`, `requires_audio`) y `transcript_policy` (`revelation` `hidden_until_post`/`on_first_fail`/`never_before_post`, `max_attempts_per_stage`, `allow_manual_reveal`, `shadowing_optional`) viajan en el payload de cada pregunta (`next_question`); el frontend ejecuta una máquina de estados de **presentación** sin reglas pedagógicas propias (`features/listening/microFlow.ts`). Backward compatible: sin `flow` la pantalla conserva el comportamiento anterior.
- **Perfil auditivo visible en la UI (objetivo 5).** `services/auditory_profile.py` deriva del diagnóstico la capa de trabajo y la intervención (casos A-D: bottom-up / comprensión / top-down / cadena hablada) con muestra mínima (`PROFILE_MIN_ATTEMPTS=3`, respuesta `needs_min_attempts` sin intervención); el diagnóstico lo expone como `profile` y la nueva tarjeta `AuditoryProfileCard` lo muestra de forma persistente y no bloqueante en el panel de Listening (estados: sin datos → `needsMore` → intervención activa). La capa recomendada se usa además para priorizar el siguiente ítem (`pick_next_question(layer=...)`).
- **Evidencia ampliada por intento (5 columnas en `listening_attempts`).** Migración idempotente que añade `layer`, `speed_used`, `stage`, `transcript_used`, `segments_replayed`; `submit_answer`/`submit_production` las persisten con la capa derivada del ítem en backend (fuente de verdad); la API y los tipos del frontend propagan el metadato de apoyo en cada envío sin romper llamadores antiguos (campos opcionales con default).
- **Verificación.** Backend pytest **1647 passed** + `ruff check .` limpio (incluye 35 tests nuevos de migración/flow/perfil/selector); frontend vitest **472 passed** (59 archivos) + `tsc --noEmit` OK; `check_release_consistency` 3.27.0 exit 0; release notes `release-notes-v3.27.0.md`.

## [3.26.0] — 2026-09-08

**Hoja de ruta completa (Ejes A+B+C): la retención del nivel pasa a longitudinal multi-punto y el gate MASTERED separa encuentro inicial de práctica espaciada, `novel` deja de ser reservado con emisor real en misiones B2+ jamás practicadas, el léxico gana historia detallada por superficie, el Listening se ordena por capas recognition/comprehension/inference, la matriz CEFR unifica los extremos con escalera monótona, la UI explica el motivo de bloqueo por destreza y el perfil marca la evidencia legacy sin `context_id`.**

Cierra el plan V3.26 de las auditorías externas V3.24/V3.25 (dossiers `docs/audit/L-AUDITORIA-TOTAL-V324.md`/`M-AUDITORIA-TOTAL-V325.md`, resolución en `docs/audit/O-AUDITORIA-TOTAL-V326.md`). Versión de app `3.25.1 → 3.26.0`.

- **Eje A — Gate MASTERED y retención longitudinal (F-A1/F-A2/F-A3).** `initial` = primer encuentro por contexto y `practice` = re-encuentros del mismo contexto separados ≥ `SPACED_PRACTICE_MIN_DAYS` (`familiar_spaced_counts`, sin inflar por varias filas del mismo día; legacy sin contexto no demuestra espaciado). Cada `delayed` se ancla a su sesión formal origen (`delayed_origin_anchors`), separando `event_age_days` de `retention_interval_days`. La certificación exige **≥2 reassessment points estables por destreza** (`CERTIFICATION_REQUIRED_DELAYED = 2`, cada uno ≥ `RETENTION_MIN_DAYS` desde su origen con ratio ≥ `RETENTION_STABLE_RATIO`) y espacia cada nuevo reassessment ≥ `RETENTION_MIN_DAYS` del último del mismo origen (409). Fix del escritor: el retention que re-evalúa un examen `kind=level` resuelve `correct_index` vía el examen (antes devolvía `None` y nunca escribía `delayed`, haciendo la certificación inalcanzable por la escalera).
- **Eje B — Emisor real de `novel` + historia léxica por superficie (F-B1/F-B2).** `novel` deja de ser reservado: la **primera misión por escenario B2+ jamás practicada** emite `novel` (detección evidence-only, `mission_context_practiced` sobre `mission:{escenario}`); retries/repeticiones emiten `familiar` (anti-bombeo). `novel_required = 0` intacto (decisión de negocio). Nueva tabla `vocabulary_events` append-only (`word`/`lexical_unit`/`event_type` produced/exposed/retrieval/`channel`/`activity`/`created_at`) escrita en la misma transacción de los 4 writers + `GET /api/vocabulary/history` paginado. SIN backfill: la historia empieza en V3.26; los contadores conservan el histórico. Ledger = señal, no puerta.
- **Eje C — Listening real, calibración CEFR y UX de progreso (F-C1/F-C2/F-C3/F-C4).** Taxonomía determinista `skill → capa` (recognition/comprehension/inference) expuesta en ítems y reporte `by_layer` (dictation/shadowing/producción aparte). Matriz CEFR `2.1.0`: las 4 destrezas planas (vocabulary/grammar/interaction/mediation) pasan a escalera monótona desde B1 siguiendo a reading, conservando suelo A1/A2; extremos unificados por familia. `readiness.blocked_by` con motivo por skill (`score`/`confidence`/`evidence`/`transfer`/`novel`) traducido en `TodayPlan`. Marcas de legacy sin `context_id`: `legacy_context_rows`/`legacy_context_used` por destreza, `legacy_context_evidence`/`legacy_context_rows` en el Student Model y `legacy_fallback` en el gate, con notas i18n en ladder/Progreso/SkillDetail.
- **Verificación.** Backend pytest **1538 passed** + `ruff check .` limpio; goldens en verde (`evidence_depth_cases.json` recalibrado); frontend vitest **450 passed** (57 archivos) + `tsc --noEmit` OK; `check_release_consistency` 3.26.0 exit 0; release notes `release-notes-v3.26.0.md`.

## [3.25.1] — 2026-09-08

**Cierre de los P1 de la auditoría externa V3.25: la certificación exige retención real (ventana ≥7 días + ratio ≥0.90 verificados desde la fila de examen), el modelo léxico agrega de verdad por `lexical_unit`, y el nivel de apoyo pondera la evidencia de dominio. V3.25.0 no se considera cerrada sin estas correcciones.**

Patch correctivo sobre v3.25.0 (candidato auditado en `docs/audit/M-AUDITORIA-TOTAL-V325.md`, P1 en `docs/audit/N-AUDITORIA-TOTAL-V3251.md`). Versión de app `3.25.0 → 3.25.1`.

- **P1-01 — Certification gate real (ventana ≥7 días + ratio ≥0.90).** `certification_gate` (Assessment 2.0) ya no confía en la mera presencia de evidencia `delayed` ni en que el emisor haya codificado la ventana: reconstruye desde las filas de `academy_evidence` el baseline formal (`task_type="exam"`, cubre la escalera `kind=level` y el examen legacy) y los eventos `delayed` agrupados por `context_id`, y certifica cada destreza solo cuando existe un reassessment verificable con `interval_days >= RETENTION_MIN_DAYS` desde el examen y `rate = delayed/initial >= RETENTION_STABLE_RATIO`. Sin examen formal no se certifica. `retention_report` pasa a informar `interval_days`, `initial_score`, `rate` y `baseline_date` por destreza. Los 6 tests negativos de la auditoría (D+6; D+7 ratio 0.89; D+7 ratio 0.90; D+21 ratio 0.50; `created_at` inválido; dos eventos sin ratio válido) quedan en `tests/test_assessment_v2.py`; `test_evidence_context.py` y `test_academy.py` se adaptan al baseline formal.
- **P1-02 — Agregación real por `lexical_unit` (aditiva).** El modelo léxico agrupa de verdad por unidad: `units_from_rows`/`summary_units` en `services/lexicon.py`, expuestos de forma aditiva (`LexiconOut.units` + `LexiconSummary.units`) en schemas, domain y tipos del frontend. Cada superficie conserva su propio estado (`go` dominada no domina `going`); la unidad expone derivados informativos (`mastery`/`recall` máximos, gaps) y `summary_units` cuenta cada unidad una sola vez. Tests de la parábola go/going/went/gone en `tests/test_lexicon.py` y wiring del endpoint en `test_vocabulary.py`.
- **P1-03 — Support level como peso de la evidencia de dominio.** `SUPPORT_LEVEL_WEIGHTS` (`copied 0.5 / guided 0.7 / cued 0.9 / independent 1.0 / spontaneous 1.0`; heurística a calibrar en V3.26) pondera cada `result` dentro de `generalized_mastery_score`. Las filas legacy sin `support_level` (o con valor no declarado) usan peso neutral 1.0: los datos previos a V3.25 no cambian de valor. Tests en `test_academy.py`.
- **Verificación.** Backend pytest **1495 passed** + `ruff check .` limpio; frontend vitest **450 passed** (57 archivos) + `tsc --noEmit` OK; `check_release_consistency` 3.25.1 exit 0. Los P2 de la auditoría quedan para V3.26 (Listening + `novel` + retención longitudinal).

## [3.25.0] — 2026-09-08

**Calibración del Student Model (plan V3.25 del dossier L): la evidencia se escribe como evento con contexto (`support_level` + experiencias/tareas) y el transfer del gate MASTERED pasa a exigir contextos distintos, la certificación verifica la retención demorada desde las filas, y la UI separa nivel demostrado de nivel estimado.**

Cierra el plan V3.25 derivado de la auditoría TOTAL verificada de V3.24.0 (dossier `docs/audit/L-AUDITORIA-TOTAL-V324.md`), absorbiendo los pendientes oficialmente diferidos en V3.24 (F-K3…F-K7). Versión de app `3.24.0 → 3.25.0`.

- **Fase 1 — Modelo de eventos con contexto (P1-05 + F-K6, base).** `academy_evidence` gana `context_id`/`activity_id`/`task_type`/`support_level` con migración idempotente e índice `idx_evidence_context` (`repositories/db.py`); `record_evidence`/`evidence_from_items` enriquecen cada evento (los 10 emisores pasan contexto) sin romper los agregados (`evidence_count`/`evidence_by_kind`/`generalized_mastery_score` siguen derivándose igual). Tests en `tests/test_evidence_context.py`.
- **Fase 2 — Support level canónico (P1-01).** Enumerados `copied/guided/cued/independent/spontaneous` (`SUPPORT_LEVELS` en `services/academy.py`) y declarados por emisor en el evento: formative → `guided`/`cued`, objective assessment → `cued`, speaking assessment/misión y chat libre → `independent`, read-aloud → `guided`, comprensión → `cued`. `build_skill_profile` agrega `support_levels` por destreza y `independent_count`; el gate MASTERED y la UI podrán filtrar por evidencia independiente. Tests: persistencia por emisor (objective assessment `cued`, misión `independent`) y exposición en perfil.
- **Fase 3 — Transfer por contextos/tareas distintos + resolución F-K5 (P1-02).** Los checks `familiar`/`transfer` de `mastery_evidence_gate`, `adaptive.readiness`, el unit gate de `course._transfer_count` y los pesos de evidence_graph dejan de contar filas y cuentan **experiencias distintas** (`effective_evidence_context_count`, con fallback a nº de filas para datos legacy sin contexto). Dos transfers del mismo contexto/tarea ya no satisfacen el gate. Desambiguación semántica documentada: `transfer`/`delayed` académicos (evidencia Assessment 2.0) vs `transfer`/`retention` léxicos (`LexicalCompetence`) en schemas.
- **Fase 4 — Retention longitudinal y robustez (P1-03).** `certification_gate` no confía en la mera existencia de evidencia `delayed`: verifica `created_at` por fila (la rechaza sin fecha) y emite `retention_report` con los intervalos alcanzados (`RETENTION_INTERVALS` D+1/D+3/D+7/D+21) desde los timestamps. Tests de robustez multi-intervalo.
- **Fase 5 — Semántica UI demostrado vs estimado (P1-04/F-K4).** El Student Model separa `demonstrated_level` (máximo nivel certificable: examen aprobado + `delayed` verificable, vía `_demonstrated_level`) de `estimated_level` y añade `level_progress` del tramo actual (`domain/academy.py` + schemas). El header de Progreso etiqueta ambos sin ambigüedad (claves i18n `progress.certified*`/`progress.inLevel*`); `estimated_band` por destreza ya se consumía en la UI.
- **Fase 6 — Renombrado canónico + unidad léxica (F-K7/P2-01/P2-02).** Migración idempotente `occurrences → appearances → production_count` y `exposures → exposure_count` en `vocabulary` (toda la pila: repo/schema/servicios/domain/frontend; accesores con retrocompatibilidad de lectura en `services/lexicon.py`) y columna `lexical_unit` (lema o superficie normalizada) para no tratar `go/going/went/gone` como conocimientos independientes (poblada en `record_production`/`record_exposures`/`seed_curriculum_items`). Decisión `novel` confirmada: el kind sigue **reservado** (sin emisor real) y permanece fuera de los requisitos del gate.
- **Fase 7 — Doble vía speaking con `cefr_target` persistido (F-K3).** `speaking_mission_sessions` gana la columna `cefr_target` (migración idempotente + backfill desde `mission_json`); la vía **assessment** y la vía **misión** siguen declarando su evidencia con `support_level = independent` (contextos `speaking_assessment:<session>` y `mission:<scenario>`). Tests de persistencia y migración de sesiones legacy.
- **Verificación.** Backend pytest **1481 passed** + `ruff check .` limpio; frontend vitest **450 passed** (57 archivos) + `tsc`/`vite build` OK; golden `thresholds.json` y E2E A1→A2 en verde; `check_release_consistency` 3.25.0 exit 0.

## [3.24.0] — 2026-09-08

**Calibración de salida del Student Model (dossier K, Eje 1): el gate MASTERED de Assessment 2.0 exige solo evidencia emisible (familiar×2 + transfer×2 + delayed) y el nivel estimado se ancla a niveles completados + progreso del tramo actual.**

Cierra el plan V3.24 del dossier K (auditoría profunda del Eje 1 sobre v3.23.0), con los dos P1 resueltos por decisión del gerente y sus tests e2e previos (F-K8). Versión de app `3.23.0 → 3.24.0`.

- **F-K1 — MASTERED relajado a lo emisible (`novel` reservado).** El evidence_kind `novel` no tiene emisor real (solo se emiten `familiar`/`transfer`/`delayed`), así que `mastery_evidence_gate` exigía `novel` permanentemente y bloqueaba la escalera Assessment 2.0. `MASTERY_EVIDENCE_REQUIREMENTS` pasa a `initial 1 + practice 2 + transfer 2 + delayed 1` (`assessment_v2.py`) y `novel_required = 0` en las 12 celdas macro de `cefr_matrix.json` (B2/C1/C2, listening/speaking/reading/writing); el kind `novel` queda **reservado** (requisito 0, sin emisor) hasta que exista una modalidad que lo emita de verdad. Frontera documentada en `docs/ASSESSMENT_2.md` y CONSTITUCIÓN §2.1/§6.1/§6.2/§6.4.
- **F-K2 — Nivel estimado anclado (sin rebase al matricular).** `estimated_level` ya no proyecta la escala lineal `numeric = 1 + 5·overall` desde un único nivel: recibe `current_level` + `completed_levels` y ancla el suelo en el nivel completado más alto (o `current_level − 1` sin completados), con `numeric = floor + progreso` en la escala 0.5–6.0. `build_student_model` deriva ambos de las matrículas (`status == "completed"`). Corrección del escenario G4 del dossier: dominar A1 completo ya **no** estima B2, y aprobar el examen A1 (matrícula A2) ya **no** devuelve el estimado a Pre-A1 (sigue A1/numeric 1.0 hasta acreditar el tramo).
- **F-K8 — Tests e2e del salto de nivel (prerequisito del fix).** `_dominate_a1` + `test_endpoint_estimated_level_anchored_across_a1_exam` en `test_academy.py` (escritos primero, red, hoy verdes): dominar A1 → estima A1 (nunca ≥ B2); aprobar examen A1 → matrícula A2, estimado A1 con numeric 1.0 (nunca Pre-A1).
- **Verificación.** Backend pytest **1457 passed** + `ruff check .` limpio; baterías del Eje 1 del dossier K **G1 311 + G2 329** (640, +2 tests e2e); frontend sin cambios (vitest **450**/57 archivos + `tsc`/`vite build` como en v3.23.0); `check_release_consistency` 3.24.0 exit 0; CONSTITUCIÓN documentada (sin cambio de regla pedagógica: `novel` pasa a reservado).

## [3.23.0] — 2026-09-08

**Calibración V3.23 (Student Model, parte 2): la retención deja de ser exposición/producción espaciada y exige recuperación correcta demorada (éxito de micro-drill fuera del intervalo desde el ancla), y la transferencia se mide por contexto real de actividad (`channel:activity`), no solo por canal. Base de calibración de la auditoría externa V3.22 incluida (P1-01/P1-03).**

Cierra el plan V3.23 del dossier de la auditoría externa V3.22.0 (P1-02 Retention por recuperación y P1-04 Transfer por contexto) sobre la base de los quick fixes de esa auditoría. Versión de app `3.22.0 → 3.23.0`.

- **P1-02 — Retention = recuperación demorada.** Migración idempotente en `vocabulary`: `retrieval_successes`/`retrieval_days`/`last_retrieval_at` (sin backfill: el histórico backfilleó `first_exposed_at = last_exposed_at`, una ancla retrospectiva sería injusta — mejor perder evidencia que inventarla). `record_retrievals` cuenta solo los éxitos que ocurren ≥ `RETENTION_MIN_INTERVAL_DAYS` después del ancla (`min(first_exposed_at, first_seen)`), suma `retrieval_successes`, `retrieval_days` una vez por día distinto y actualiza `last_retrieval_at`. Hook de recuperación solo en el micro-drill: `submit_drill_attempt` (si `produced`) y `submit_sentence_attempt` (si `passed`). En `item_competence_matrix`, `retention = retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS`; `_spaced_exposure`/`_spaced_production` pasan a señales independientes (`spaced_exposure`/`spaced_production`, informativas, no certifican retención).
- **P1-04 — Transfer por contexto de actividad.** Migración `context_tags` (CSV canónico `channel:activity`, único y ordenado). `record_production(user, words, channel, activity=None)` fusiona el tag al escribir; `activity` se propaga por `record_production_text` y `_capture_production_text` con el mapeo por superficie: chat libre→`free_chat`, assessment→`speaking_assessment`, misión→`speaking_mission`, checks controlados→`speaking_controlled`/`writing_controlled`, tareas LLM→`speaking_task`/`writing_task`, read-aloud→`read_aloud`, drill→`drill`, rutas speaking→`speaking_route`, conversación guiada→`guided_conversation`. `production_contexts(row)` deriva los contextos (tags explícitos + fallback `channel:other` para canales legacy sin tag) y `transfer_contexts`/`transfer` se basan en contextos (dos actividades del mismo canal cuentan; `chat`+`conversation` dejan de colapsar). `summary` añade `spaced_exposure` (informativo).
- **Quick fixes base (auditoría externa V3.22).** P1-01: `item_recall` usa la actividad más reciente (`_last_activity_at`, max de `last_seen`/`last_exposed_at`). P1-03: `item_mastery` pondera el reconocimiento con `RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6 sobre `exposure_days` (el volumen no satura) y `classify_asr_status` comprueba `no_speech` (alucinación de silencio) ANTES de `low_confidence`.
- **Contratos y UI.** `LexicalCompetence` gana `spaced_exposure`/`spaced_production`/`retrieval_successes`/`retrieval_days` y `LexiconSummary` gana `spaced_exposure` (schemas + `types/api.ts`). Sin renombrar chips; tooltip del diccionario actualizado a la semántica nueva (en/es).
- **Verificación.** Backend pytest **1455 passed** + `ruff check .` limpio; frontend vitest **450 passed** (57 archivos) + `tsc --noEmit`/`vite build` OK; `check_release_consistency` 3.23.0 exit 0; curriculum `--strict --quality` y content validation OK; i18n parity exit 0 (1232 definidas); CONSTITUCIÓN sin cambios.

## [3.22.0] — 2026-09-08

**Calibración V3.22: el ASR agrega métricas por segmentos de faster-whisper (no de TranscriptionInfo) con clasificación explícita, y el Student Model separa Retention de Transfer en la matriz léxica con exposure_days y gaps independientes.**

Cierra el plan V3.22 (dossier de la auditoría externa V3.21.0; P1-01/02/03 ASR + P1-04/05 y P2-01 parcial del léxico). Versión de app `3.21.0 → 3.22.0`.

- **ASR-01 — Calibración ASR por segmentos (P1-01/02/03).** faster-whisper expone `avg_logprob`/`no_speech_prob`/`compression_ratio` en cada `Segment`, no en `TranscriptionInfo` (que solo reporta `language_probability`/`duration`). `transcribe_with_timing` materializa `list(segments_gen)` y agrega con `aggregate_asr_segments` (duck-typed y determinista): `mean_logprob`/`min_logprob` (media ponderada por duración de segmento), `max_no_speech_prob`, `no_speech_ratio`, `speech_ratio`, `compression_ratio`, `segment_count`, `language_probability`, `duration`. En V3.21 `no_speech` era inalcanzable (todo audio vacío caía en `unintelligible`) y `low_confidence` inalcanzable (todo texto caía en `ok`). Nueva firma `classify_asr_status(*, text, metrics)` con política explícita y constantes `MIN_SPEECH_ATTEMPT_SECONDS` (0.5 s) y umbral de alucinación de no-habla: sin texto con 0 segmentos y audio corto/sin medir → `unintelligible` (captura fallida), con audio ≥ 0.5 s → `no_speech`; texto alucinado sobre silencio (`no_speech_ratio` ≥ 0.5 y `max_no_speech_prob` alto, medido sobre silencio digital real) → `no_speech`, nunca penalizable; `mean_logprob` < -1.0 → `low_confidence`. El dict de salida mantiene el contrato (`text/duration/asr_status/confidence` + aliases `avg_logprob`/`no_speech_prob`) y emite telemetría (`segment_count/mean_logprob/min_logprob/no_speech_ratio/compression_ratio/language_probability`) como señal para el Student Model; `LANGUAGE_MISMATCH` queda documentado como frontera futura. El gating `asr_status != "ok"` no cambia en ningún router.
- **P1-04 — Retention ≠ Transfer en la matriz léxica.** Migración idempotente `exposure_days`/`first_exposed_at` en `vocabulary` (backfill: 1 día y `first_exposed_at = last_exposed_at` donde `exposures > 0`); `record_exposures` pasa a bucle por fila, suma `exposure_days` solo cuando la exposición ocurre en un día distinto al de `last_exposed_at` y fija `first_exposed_at` en el alta (mismo patrón que `production_days`/`first_seen`). La matriz `item_competence_matrix` deja de igualar `retention = transfer`: `transfer` = producción en ≥ 2 canales (`transfer_contexts`, sin el "or spaced"), `retention` = `_spaced_exposure(row) or _spaced_production(row)` (recuerdo tras intervalo receptivo o productivo).
- **P1-05 — Gaps independientes (production_gap / transfer_gap).** La clave `gap` (reconocida-nunca-producida) se renombra a `production_gap` — el gap que cierra el speaking micro-drill — y se añade `transfer_gap` (producida en ejercicios pero nunca usada en otro contexto: `production && !transfer`). `summary` desglosa los 6 contadores (`recognized/produced/transfer/retention/production_gap/transfer_gap`). La lista de candidatas del drill no cambia (depende de `exposures`/`speaking_prod`/`ok_days`, no de la matriz). El renombre `appearances → production_count` sigue como deuda documentada (sin migración destructiva).
- **Contratos y UI.** `LexicalCompetence` y `LexiconSummary` (schemas) y `types/api.ts` reflejan las claves nuevas (`transfer_contexts`, `production_gap`, `transfer_gap`; fuera `gap`). El diccionario personal (`PersonalDictionary.tsx`) pasa a 6 contadores (Recognized · Produced · Transfer · Retention · Production gap · Transfer gap) con rejilla `lg:grid-cols-6` y copia de competencia actualizada (transfer = 2+ contextos; retention = espaciada) + clave i18n `dictionary.competenceProductionGap` (en/es). Se mantienen intactas las claves `asr.message.*`.
- **Verificación.** Backend pytest **1440 passed** (26 de la batería ASR con la nueva firma + 2 de integración opt-in `test_stt_asr_integration.py` contra Whisper y piper reales) + `ruff check .` limpio; frontend vitest **450 passed** (57 archivos) + `tsc --noEmit` y `vite build` OK; `check_release_consistency` 3.22.0 exit 0; CONSTITUCIÓN sin cambios.

## [3.21.0] — 2026-09-07

**Calibración V3.21: verdad del micro-drill (alineación secuencial), feedback ASR honesto con gating de no-penalización, matriz de competencia léxica con Transfer Gap para FSRS y drill en escalera con paso Sentence determinista + graduación espaciada.**

Cierra el plan V3.21 (dossier de la auditoría externa V3.20.0; F1-F6). Versión de app `3.20.0 → 3.21.0`.

- **F1 P0 — verdad del micro-drill (V20-01).** La producción en el drill deja de decidirse por pertenencia de tokens: `unit_produced` en `services/phonetics.py` usa la **alineación secuencial** con la misma normalización que el alineador (`tokenize`, nunca `.split()`). Palabra de 1 token → debe quedar `equal`; unidad multi-palabra → sus tokens deben aparecer **contiguos** en la transcripción ("get it up" NO produce "get up"; "my living room is nice" sí produce "living room"). Fix del bug real asociado: las unidades multi-palabra ahora se acreditan **a sí mismas** (`record_production_text(as_unit=True)` hace upsert de la cadena exacta, sin tokenizarla), manteniendo el invariante `sum(channel_prod) == appearances` por fila (tests de frases e invariante multi-palabra).
- **F2 P1 — feedback honesto y taxonomía ASR (V20-02/V20-14/V20-15).** `transcribe_with_timing` captura `no_speech_prob`, `avg_logprob` y `language_probability` de faster-whisper y clasifica `asr_status ∈ {ok, no_speech, unintelligible, low_confidence}` (determinista). **Gating pedagógico**: si `asr_status != ok` los intentos puntuados (drill, read-aloud, speaking abierto y pronunciación legacy) NO registran el KO como fallo lingüístico, devuelven `evaluation` no penalizante y emiten evento `unclear`; la UI muestra el bloque guía correspondiente en vez de marcar en rojo. Los chips palabra a palabra se re-etiquetan con la verdad ASR ("Reconocida correctamente" / "No reconocida" / "Sustituida en la transcripción") con la nota permanente de que el feedback por palabra viene de la transcripción; el término "pronunciación" queda reservado para las señales fonéticas explícitas.
- **F3 quick wins.** `DEFAULT_MODEL` con fuente única: `GET /api/models` devuelve `default_model` (de `config.DEFAULT_MODEL`) y el frontend resuelve el modelo por defecto con `resolveDefaultChatModel()` (`utils/models.ts`), sustituyendo las 3 constantes duplicadas (`useChat`, `ConversationGuidedChat`, `SpeakingRolePlay`). Comentario de `ADMIN_PIN` corregido (fail-closed, 401). Grabaciones manuales con **cronómetro visible y auto-stop** vía hook `useRecordingSession` (120 s) en las escenas de drill/read-aloud/speaking assessment/voz de conversación, más red de seguridad backend que rechaza con 400 el audio que exceda `MAX_AUDIO_DURATION_SECONDS`. Mensaje "No se ha reconocido audio" en los flujos que antes descartaban el texto vacío en silencio (`MicButton`, `ConversationVoiceButton`, manos-libres con estado `unclear`).
- **F4 — semántica de superficie Speaking (V20-03/04).** Sin tocar la arquitectura (tres motores y stats separadas), el modo real se expresa en la UI: títulos por modo (Micro-práctica / Acento / Diálogo guiado) y los pies de stats etiquetan la competencia real (Pronunciación / Conversación / Producción oral) con claves i18n por modo.
- **F5 — matriz de competencia léxica y Transfer Gap (V20-16/17).** `item_competence_matrix` (pura, en `services/lexicon.py`) deriva Recognition/Production/Transfer/Retention/gap por ítem **sin migrar columnas**; el léxico (`GET /api/vocabulary/lexicon`) y la fila de stats del diccionario la exponen (`recognized/produced/transfer/retention/transfer_gap`). Para FSRS, el "why" de las cartas lexicon distingue **`transfer-gap`** (palabras conocidas de un objetivo que ya produce otras) de `recognition-only` (objetivo sin producción). Deuda de modelo documentada: `appearances`/`exposure_days` se renombrarán conceptualmente en una migración futura.
- **F6 — drill en escalera (MVP + graduación espaciada, V20-06).** Paso **Sentence determinista sin LLM**: `sentence_context_for` toma del banco de read-aloud del nivel la primera frase que contiene la unidad (plantilla neutra `Say the word "…".` si ninguna la contiene); endpoints `GET /api/vocabulary/drill/sentence-context` y `POST /api/vocabulary/drill/sentence-attempt` (`passed = produced AND phrase_ok`, servidor re-deriva la frase). La tarjeta `WordDrill` del diccionario ofrece los pasos **Recall → Sentence** en una sola tarjeta. La lista "pendiente" del drill ya **no elimina tras una producción del día**: exige éxito **espaciado** (2 días de éxito — eventos `drill:<word>:ok`/`drill:<word>:sentence:ok` — u otra señal de speaking espaciada) como criterio de salida, sin declarar dominio (D5/E3). F6.3 (Contexto/Transfer libre) queda aplazado a la auditoría pedagógica de Speaking/Listening.
- **Verificación** — backend `pytest` **1424 passed** + `ruff` limpio; frontend `vitest` **450 passed** (57 archivos) + `tsc --noEmit` limpio; `check_release_consistency` 3.21.0 exit 0; CONSTITUCIÓN sin cambios (se mantiene señal ≠ evidencia).

## [3.20.0] — 2026-09-07

**Speaking único: la práctica oral se consolida en una sola superficie (hub de 4 tarjetas), el alumno ya oye su propia grabación, el diálogo guiado admite turnos hablados reales y el modo Acento gana feedback palabra a palabra.**

El candidato V3.20 (definido 2026-09-07 como frontend-only; F1 de `docs/DISENO-SPEAKING-UNICO.md` + feedback oral) se cierra: Pronunciation y Conversation dejan de ser actividades propias y pasan a ser **modos internos de Speaking** (Micro-conversación / Acento / Diálogo guiado) sin cambiar sus motores. Backend sin cambios de lógica; versión de app `3.19.0 → 3.20.0`.

- **Consolidación de la práctica oral (F1)** — el hub de APRENDER pasa a **4 tarjetas** (listening · speaking · vocabulario · gramática) y las URLs `/aprender/pronunciacion` y `/aprender/conversar` degradan al hub. `SpeakingRoutesPractice` reutiliza `PRONUNCIATION_ROUTE_CONFIG`/`CONVERSATION_ROUTE_CONFIG` (exportadas) bajo un selector de modos en `QuizRoutePage` (`modeTabs`); NextBest de destreza `pronunciation` y el CTA post-assessment navegan a Speaking. El chat libre sigue en `/chat`.
- **Cabecera despejada** — el texto «Cada nivel es una ruta…» deja de ocupar siempre el espacio superior: vive plegado tras el botón **(i) «Cómo funcionan las rutas»** en `QuizRoutePage` (`learn.routesInfoToggle`).
- **El alumno oye su grabación real** — el backend solo transcribe (descartaba el audio), así que las escenas de Micro-conversación y Acento conservan el blob en memoria (`URL.createObjectURL`, revocado al cambiar/desmontar) y muestran **«Oír mi grabación»** (`components/RecordingPlayButton.tsx`) junto a la respuesta/frase modelo; en Acento se añade además el altavoz de la frase modelo dentro del resultado.
- **Diálogo guiado con turnos hablados de verdad (F3, parte frontend)** — `ConversationVoiceButton` graba el turno, mide su duración real (metadata de audio con fallback de reloj), transcribe y lo persiste con `mode="voice"` + telemetría (`Message.mode` admite `"voice"`); el backend (CONV-01 de V3.19, sin cambios) distingue el tecleo de los turnos que computan como habla.
- **Feedback palabra a palabra en Acento (mockup §6.3)** — nueva tarjeta «Frase palabra a palabra» en el resultado: la frase modelo se colorea por palabra (verde bien dicha, ámbar sustituida `→ lo dicho`, roja no dicha, «+extra» palabras de más). Clasificación vía `utils/pronunciationAlignment.ts`, puerto TS del `SequenceMatcher` de difflib con paridad exacta con la alineación del backend (`services/phonetics.py::word_alignment`) y tests de paridad.
- **Modos por URL + redirección de URLs heredadas (F4)** — el modo de Speaking vive en la URL (`speakingModePath`/`speakingModeFromPath`), con navegación atrás/adelante y deep links; `/aprender/pronunciacion` y `/aprender/conversar` se canonizan al modo correspondiente de Speaking.
- **Fix UI** — el botón de **traducir la frase del interlocutor** (y el de la respuesta modelo) en Micro-conversación alternaban el estado interno pero la burbuja seguía mostrando el inglés crudo: ahora pinta `display` (traducción ES ⇄ EN) como en el resto de escenas.
- **Verificación** — frontend `tsc`/`vite build` OK, vitest 434 tests OK; backend `pytest` sin cambios con `ruff` limpio; `check_release_consistency` 3.20.0 exit 0; CONSTITUCIÓN sin cambios.

## [3.19.0] — 2026-09-07

**Léxico por destreza + Speaking micro-drill: la producción del alumno se vuelca al léxico etiquetada por destreza y los chips del diccionario dejan de ser inertes, con los fixes P1 del dossier (R6/GATE/CLAIM/SIGNAL/ERR/LIST/CONV) y la deuda ADMIN-01/BOOL-01.**

El candidato V3.19 (definido 2026-09-07, pendiente heredado de v3.18 + auditoría profunda V3.18) se cierra: la tabla `vocabulary` gana contadores por destreza, cada superficie de producción (speaking/pronunciación/writing/conversación guiada/chat) vuelca el texto del alumno por un único punto de captura, y `recognized_not_produced` pasa a ser la señal real "expuestas y nunca dichas" servida por un micro-drill de 1 nivel honesto sobre el scorer de pronunciación. Backend `3.18.0 → 3.19.0`.

- **Refactor previo (CAP-01/REFAC-01)**: `record_words` se generaliza a `record_production(user, words, channel)` en `repositories/vocabulary.py` (semántica intacta de `appearances`/`production_days`/`item_status`/coverage + suma de la columna del canal); helpers compartidos de captura `_capture_production_text`/`record_production_text` (fire-and-forget, no bloqueante) que sustituyen los ≥7 bloques duplicados de `domain/academy.py` y cablean los `submit_*`.
- **Modelo de datos (LEX-01)**: 4 columnas contadoras `INTEGER NOT NULL DEFAULT 0` — `chat_prod`, `speaking_prod`, `writing_prod`, `conversation_prod` — con backfill idempotente `chat_prod = appearances` (toda la producción histórica vino del chat libre). Invariante trazable `sum(columnas) == appearances` con test puro.
- **Volcado por destreza**: `speaking` ← speaking assessment/misión/routes/task + pronunciación libre y rutas + drill; `writing` ← `submit_writing(_task)`/`objective/writing`; `conversation` ← conversación guiada (texto reconstruido de los turnos); `chat` ← chat libre (vía existente). Schemas `LexicalItemOut` ampliados.
- **Speaking micro-drill (1 nivel honesto, sin claims D5/E3)**: `drill_candidates` = `exposures > 0 AND speaking_prod == 0` ordenadas por recuerdo (señal en servidor, premisa 21); `GET /api/vocabulary/drill/candidates` + `POST /api/vocabulary/drill/attempt` (reusa el scorer de pronunciación; éxito = `ok` y palabra en `breakdown.correct` → `record_production(channel="speaking")`, sin evidencia curricular ni FSRS). En `PersonalDictionary` los chips inertes ganan acción de práctica con error+reintento (A6-03) y la palabra sale de la lista al producirla.
- **Fix P1 del dossier**:
  - **R6-01**: la retención (R6, §6.3) se impone en servidor — ventana ≥ `RETENTION_MIN_DAYS` (7) desde la sesión formal origen y ratio estable ≥ 0.9 en `start/submit_assessment_v2`; `RetentionNotDueError` → HTTP 409 (CONSTITUCIÓN §6.3 deja de ser letra muerta).
  - **GATE-01**: ningún endpoint de intento/evaluación/completar lección evalúa un objetivo `locked` (`_ensure_objective_evaluable`); `ObjectiveLockedError` → HTTP 409.
  - **CLAIM-01/SIGNAL-01**: los paneles Speaking/Pronunciation/Conversation re-etiquetan "nivel oral actual (examen)" con calificador estimado (sin claim "demostrado" sin gate real) y la pista del diccionario pasa a "aún no producida en práctica de speaking".
  - **ERR-01**: los fallos transitorios del extractor LLM en misiones/assessment/task dejan de responder 404 (indistinguible de sesión inválida) y responden 503 reintentable.
  - **LIST-01/02/03**: tokens de foco perceptivo (`word_recognition`/`sound_recognition`/`phrase_recognition`) ya servibles en el corpus con ≥1 ítem por nivel; muestra A1/B1 re-etiquetada y pares cuasi-duplicados re-autorados; unicidad de `script` normalizado validada (`validate_listening_bank` + tests).
  - **CONV-01**: la conversación guiada (mini-chat tecleado, `mode="conversation"`) reconstruye por `mode` — el tiempo de redacción no se computa como habla: `turn_duration`/latencia/segundos de habla quedan no observados (el balance de turnos y el volcado al léxico se conservan); `get_turns` expone `mode` e `interaction_evidence` acepta `typed_modes`.
- **Deuda de auditoría externa**: **ADMIN-01** fail-closed (`ADMIN_PIN=""` ⇒ endpoints admin deshabilitados 401, nunca abiertos) y **BOOL-01** (`type(selected) is int` en `unit_review.py`; `True`/`False` ya no valen como índice).
- **Tests**: backend **1371 passed** + ruff limpio (migraciones/backfill, `record_production` canales mixtos, `drill_candidates`, integración HTTP "exponer → drill → producir → sale", rechazos 409 R6/GATE, 503 ERR-01, fail-closed ADMIN-01, bool-as-int, unicidad de scripts, CONV-01 por `mode`); frontend **417 passed** (53 archivos) + `tsc`/`vite build` OK (micro-drill en `PersonalDictionary`, copy CLAIM/SIGNAL, labels listening); `check_release_consistency` exit 0. CONSTITUCIÓN sin cambios (R8/R9 siguen como propuesta abierta); fuera de alcance documentado: micro-drill 3 niveles + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo, WR-UI-01.

## [3.18.0] — 2026-09-07

**Knowledge Graph remainder + deuda del grafo: el ancla de repaso se congela, las ventanas 7/30/90 encadenan, las cartas `objective` dejan de ser autograduables, el plan agrega niveles anteriores y el grafo habla en etiquetas humanas con coste lazy.**

El candidato P3 auditado ABIERTO en 2026-09-06 se cierra: la deuda del grafo que v3.17 dejó diferida (I2/M4/O1/O3/H5/H6 + observaciones de la auditoría v3.17) queda implementada con las decisiones del gerente (2026-09-07). Backend `3.17.0 → 3.18.0`.

- **Ancla congelada (I2)**: nueva tabla `unit_review_anchors` (escritura única `INSERT OR IGNORE`, nunca sobrescribe) + repos `get_unit_anchor`/`set_unit_anchor_if_absent` + `build_unit_review_plan(anchor=)`. El ancla se persiste la primera vez que la unidad se detecta completa (backfill lazy de despliegue en `get_unit_review_plan`/`_unit_review_context`/`sync_fsrs_cards`); un refuerzo o decay posterior ya no desplaza las ventanas 7/30/90 (test de dominio: segunda lectura tras tocar `updated_at` → mismas `due_at`).
- **Cadena de ventanas 7→30→90 (O1)**: `window_due_at` recibe los intentos de la unidad (todas las ventanas) y aplica cascade — una ventana sin intento propio queda `passed` si existe un intento superado de la unidad con `created_at >= due_at` de esa ventana; el intento propio manda siempre. Resolver la 7 tarde cierra la 30 ya vencida (test puro dedicado).
- **Cartas FSRS `objective` fuera del panel autograduable (M4, single writer)**: `sync_fsrs_cards` crea cartas `objective` solo cuando la primera ventana no superada está `due_now`/`failed` o la carta ya existe con `reps > 0` (continuidad de scheduling); `get_fsrs_due` excluye `objective` de la cola y del `due_count` (`get_fsrs_summary` conserva el total por tipo en `by_type`); `review_fsrs_card` rechaza `objective` (`None` → 400). El `FsrsReviewPanel` solo repasa skill/lexicon; los objetivos se repasan en `UnitReviewPanel`.
- **Plan de repaso agregado por niveles (O3)**: `UnitReviewPlanOut` evoluciona a `{levels: [{level_id, level, units, due_count}], due_count}` (nivel actual + anteriores matriculados con unidades completadas/activas); `get_unit_micro_review`/`submit_unit_micro_review` aceptan `level_id` y validan la unidad en el nivel donde vive; routers GET/POST con `level_id` opcional. Frontend: tipos espejo, `UnitReviewPanel` agrupa por nivel con cabecera y contador por nivel, micro-review recuerda el `level_id` de la unidad, i18n es/en con parity.
- **Etiquetas humanas de dimensiones del grafo (H5)**: `GRAPH_DIMENSION_LABELS` (7 dimensiones, inglés de inmersión, convención V3.6.1) + helper `dimensionLabel` en `learningLabels.ts`; aplicadas en el chip del factor limitante de `TodayPlan`, `NextBestCard`, `ObjectiveNodeCard` y `EvidenceGraphPanel` — `transfer`/`discourse`/`interaction` ya no caen al id en crudo.
- **Coste lazy de `/session` y `/next-best` (H6)**: `_session_steps` rankea/construye nodos solo para los grupos de remediación que pueden convertirse en paso (≤ `SESSION_CAPS["weakness"]`) y llama a `list_evidence` una sola vez y solo si hay nodos que construir o enriquecer; payloads idénticos (sin cambio de API) y `/next-best` nunca diverge.
- **Observaciones de la auditoría v3.17**: `ObjectiveNodeCard` distingue error real (copia `evidenceGraph.error` + botón reintento, vía `getJsonNullable` 404 → `null` en el cliente) de 404/sin-datos (copia vacía actual); `float()` defensivo (`_as_float`) en `rank_weakness_objectives` tolera `mastery` no numérico sin lanzar (ordena como 0.0); nueva spec Playwright `homeGraphChip` (mock de red determinista: el chip pinta "Transfer") ejecutada en desktop junto al smoke de la región.
- **Tests**: backend **1345 passed** + ruff limpio (`test_unit_review.py` cascade + ancla, `test_unit_review_endpoints.py` plan multi-nivel/ancla congelada/siembra gated/aislamiento, `test_session_graph.py` coste H6, `test_graph_plan.py` `_as_float`); frontend **414 passed** (52 archivos) + `tsc`/`vite build` OK (`learningLabels.test.ts`, `TodayPlan.test.tsx`, `academy.test.ts`, `client.test.ts`, `ObjectiveNodeCard.test.tsx`, `UnitReviewPanel.test.tsx`, `FsrsReviewPanel.test.tsx`, `unitReviewLogic.test.ts`); `check_release_consistency` exit 0. `GRAPH_VERSION` permanece `2.12.0` (cambio aditivo + helper).

## [3.17.0] — 2026-09-06

**Knowledge Graph + Daily Adaptive Plan: el plan diario deriva del grafo de evidencia y la vista de grafo llega al curso y al perfil.**

El candidato P2 se cierra: la infraestructura (`evidence_graph.py` v2.12 + `adaptive.py`) existía pero el plan diario no derivaba del grafo, `/api/academy/today` era un motor muerto y no había vista de grafo real. Esta iteración conecta el Can-Do ↔ destrezas ↔ dominio en el plan y en la UI. Backend `3.16.0 → 3.17.0`.

- **El plan diario deriva del Evidence Graph (D1b)**: funciones puras nuevas en `services/evidence_graph.py` — `rank_weakness_objectives` (practica primero el objetivo cuyo nodo declara la destreza débil como factor limitante, después por mastery ascendente, empates estables, ids sin nodo al final) y `enrich_item` (aditivo; solo con nodo). En `domain/academy.py::_session_steps` los candidatos de remediación se reordenan con el nodo antes de `session_plan`, y los pasos con objetivo ganan `can_do`/`limiting_factor`/`graph_mastery`/`because[]` — con una única lectura de evidencia, de modo que `/session` y `/next-best` nunca divergen (test dedicado).
- **Vista de grafo real (D2)**: nuevo componente reutilizable `ObjectiveNodeCard` que consume `getEvidenceGraphNode` (con `levelId` opcional) y pinta can-do/nivel/dimensiones con el factor limitante resaltado y el foco recomendado. Montado en el **curso** (`Milestone` expansible bajo demanda) y en el **perfil** (Habilidades: el detalle del `EvidenceGraphPanel` pasa por la tarjeta). Sin endpoint nuevo; la UI refleja la puntuación del servidor, sin declarar dominio.
- **`/api/academy/today` eliminado (D3)**: endpoint, `get_today_plan`, `TodayPlanOut`/`TodayItemOut`, `adaptive.today_plan` + `TODAY_MIX`, cliente `getTodayPlan` y tipos `TodayPlan`/`TodayItem` desaparecen; la Home consume solo `/session`. Los tests se migran con rationale honesto (los 4 puros a `session_plan`; el del presupuesto del objetivo lo cubre ya el test de `/session`).
- **Deuda de la auditoría v3.16 (D4b)**: M2 ✅ (`validate_micro_review_answers`: claves ⊆ muestra e índices en rango → 400 sin persistir), M3 ✅ (prefijos dinámicos `unitReview.window.`/`unitReview.state.`/`skill.`/`fsrs.whyReason.` en `DYNAMIC_KEY_PREFIXES`), O2 ✅ (test GET==POST con reintento parcial: muestra idéntica entre llamadas y fallidos primero). M1 ✅ en el cierre: infraestructura DOM (devDeps `jsdom` + `@testing-library/react`, vitest ampliado a `*.test.tsx` con alias `@` y jsdom por archivo) y 6 vitest de componente nuevos de `UnitReviewPanel` (vacío, ventana due, submit+refresh con plan mutable, error de red) y de la fila enriquecida de `TodayPlan` (D6 y D7).
- **UI del plan y fallback (D6/D7)**: micro-líneas informativas del can-do (itálica) y del factor limitante (chip con `%`/`missing`) en las filas de sesión; sin nodo o sin objetivo el paso se queda igual (silencio, nunca bloquea la práctica). `GRAPH_VERSION` permanece `2.12.0` (cambio aditivo).
- **Tests**: `test_graph_plan.py` (9 puros del ranking/enriquecimiento), `test_session_graph.py` (3 endpoint: campos del grafo coherentes con el currículo, silencio D7, paridad `/next-best`==`/session`), migraciones y M2/O2. Backend **1333 passed** + ruff limpio; frontend **398 passed** (392 + 6 DOM) + `tsc`/`vite build` OK; `scripts/check_release_consistency.py` exit 0.

## [3.16.0] — 2026-09-06

**Review/SRS por unidad: micro-review + ventanas de retención fijas 7/30/90 días sobre la base FSRS.**

El candidato P1 "Review/SRS por unidad" auditado como ABIERTO en 2026-09-05 se cierra: el motor FSRS ya soportaba `target_type="objective"` pero nada lo sembraba, no existía plan de repaso por unidad ni ventanas fijas de retención. Esta iteración convierte el cierre de una unidad en un calendario de repaso de recuperación (práctica, nunca declaración de dominio). Backend `3.15.0 → 3.16.0`.

- **Servicio puro `services/unit_review.py`** (V3.16, determinista, sin BD): ventanas fijas `(7, 30, 90)` días desde el ancla de la unidad (unidad completada = todos sus objetivos `mastered`; ancla = `max(updated_at)` de sus filas de mastery); estados de ventana `upcoming / due_now / passed / failed` con `now` inyectable; muestreo de micro-review **balanceado por objetivo** de los checks MC **oficiales** del currículo (cero contenido artificial; reintento prioriza los ítems fallados del último intento con semilla determinista `user+unit+window`); puntuación en servidor contra `correct_index` (el cliente solo envía respuestas, premisa 21).
- **Siembra FSRS `objective`**: `sync_fsrs_cards` siembra/refresca cartas `target_type="objective"` para los objetivos de las **unidades completadas del nivel actual** (D1/D2), sin pisar cartas con `reps > 0` (solo refresca `why`/`label`) y sin tocar `fsrs.TARGET_TYPES`. Nueva razón pedagógica `why_for_objective` en `fsrs.py` (`unit-window-7/30/90` / `unit-maintenance`).
- **Persistencia e intentos**: tabla idempotente `unit_review_attempts` (con `per_objective` y `failed_items` en JSON, índice de lookup por `user/level/unit/window`) + repos `insert/list/latest_unit_review_attempt`. El micro-review **no crea evidencia de mastery/currículo ni declara dominio** (D5): es práctica de retención separada del scheduler y del Mastery Engine (coherente con el hallazgo E3 de `docs/audit/E-FSRS-RETENTION.md`).
- **API**: `GET /api/academy/review/unit-plan` (plan del nivel actual: unidades completadas o con plan activo + `due_count`), `GET/POST /api/academy/review/unit/{unit_id}/micro-review` (sesión sin `correct_index` / puntúa, persiste y reprograma las cartas FSRS `objective` con el grade derivado de la precisión por objetivo). Gating: 400 si la ventana no está `due_now`/`failed` o el `window_days` es inválido; 404 si la unidad no pertenece al nivel.
- **UI (INICIO)**: `UnitReviewPanel` junto a `FsrsReviewPanel` en HomeScreen: lista de unidades con sus ventanas 7/30/90 (chips de estado con color), contador de unidades por repasar, micro-review por tarjetas (un check a la vez con feedback inmediato y respuesta correcta revelada al terminar) y nota honesta "Repaso de retención · no cuenta como demostración de dominio". Lógica pura extraída a `unitReviewLogic.ts` (testeable sin DOM). i18n `en`/`es` completa con parity.
- **Tests**: `test_unit_review.py` (servicio puro), `test_unit_review_endpoints.py` (siembra solo en unidades completadas, idempotencia, sin `correct_index`, D5 sin evidencia nueva, gating de ventanas, aislamiento entre usuarios); `unitReviewLogic.test.ts` y tests del cliente API. Backend **1318 passed** + ruff limpio; frontend **392 passed** + `tsc`/`vite build` OK.

## [3.15.0] — 2026-09-06

**Profundidad avanzada C1/C2: densidad, taxonomía avanzada y banco de grammar C2 normalizado.**

El candidato P0 "C1/C2 depth" auditado como abierto en 2026-09-05 (banco grammar C2 = 8 <12, volumen 14/20, taxonomía avanzada invisible a `subskill_breadth`) se cierra con contenido y motor honestos. Backend `3.14.0 → 3.15.0`.

- **Volumen: C1 y C2 a 20 objetivos** (desde 14). +6 objetivos por nivel con evidencia completa (checks MC + 5 activities con fases, wiring conservado): C1 en `c1-m02-u01-l01` (+2), `c1-m02-u01-l02` (+1) y `c1-m03-u01-l01` (+3); C2 en `c2-m02-u01-l01` (+2, "Register shifts") y en la lección nueva `c2-m02-u01-l03` (+4, elipsis/gramática formal y cohesion discursiva). Módulos Final intactos (`c1-m04`, `c2-m03`). +30 activities por nivel (68→98) y +18/+19 checks (C1 45→63, C2 38→57).
- **Taxonomía avanzada visible**: `SUBSKILLS` (`backend/services/curriculum.py`) incorpora la capa C1/C2 —`register`, `pragmatics`, `discourse`, `nuance`, `argumentation`— en speaking, listening, writing, grammar, reading y vocabulary (pronunciation intacta). Objetivos C1/C2 re-etiquetados solo donde su contenido lo justifica (C1: 3→16 objetivos con subskill avanzada; C2: 7→20), sin inflado y sin tocar niveles A1–B2.
- **Banco grammar C2 normalizado a 15 ítems** (11 MC + 4 CP en 3 temas, desde 4 MC + 4 CP): C2 deja de ser el único banco corto real y `practice_depth` real deja de leer `"low"`. La regla R7 ("muestra pequeña ≠ competencia") se conserva verificada con un **banco corto sintético** construido en los tests (`_synthetic_short_bank`), no con contenido artificial.
- **Tests e higiene**: `test_curriculum_quality.py` reformula el snapshot V2.6 (`test_depth_c1_c2_reach_deep_target_after_v315`); `test_pedagogical_invariants.py` y `test_grammar_routes.py` re-apuntan la mecánica de banco corto a datos sintéticos y fijan el nuevo conteo C2 (8 → 15); textos "C2 = 4" eliminados de `quiz_routes.py`/`schemas/grammar_routes.py`. Sin cambios de norma pedagógica (la CONSTITUCIÓN no se modifica).
- **Métricas de cierre** (CLI `scripts/curriculum_coverage.py --strict --quality`, exit 0): `depth(C1) = 93.1` y `depth(C2) = 92.5` (≥ 90 y por encima del resto; A1 89.4), unit coverage 100 % (31/31) y Unit Learning Loop 100 % en las 9 fases; `validate_level` vacío en los 6 niveles.

## [3.14.0] — 2026-09-05

**Registro cross-skill de B1 a los 6 niveles (A1–C2): el canal de producción se ofrece en todos los niveles y el panel deja de ser prototipo.**

La iteración escala el registro cross-skill por estructura (V3.13 P1.2) del prototipo B1 a los seis niveles A1–C2: cada nivel declara qué instrumentos ofrece su currículo por destreza y qué evidencia real tiene el usuario, con producción controlada enlazada (normativa, sin CP huérfanos). Backend `3.13.0 → 3.14.0`.

- **Contenido: ítems `controlled_production` en A1 y C2**: 6 ítems nuevos en A1 (`a1-cp-01..06`: verb `to be`, present simple 3.ª persona, adverbios de frecuencia, `have/has got`, preposiciones de lugar, past simple) y 4 en C2 (`c2-cp-01..04`: inversión enfática, cleft sentence, mixed conditional y pasiva formal de registro). Siguen la convención V3.13 (prompt con hueco + `accepted_answers` deterministas). El banco de la ruta Grammar crece (A1 38→44, C2 4→8); C2 sigue en banco corto (≤12), así que su etiqueta "practice coverage · evidence depth LOW" se conserva sin claims falsos.
- **Registro cross-skill generalizado (A1–C2)**: `backend/services/cross_skill.py` deja de ser prototipo B1. `CROSS_SKILL_LEVELS = (a1..c2)`; `structure_registry(level)` devuelve las estructuras de cualquier nivel (objetivos con checks MC de grammar); `PRODUCTION_BINDINGS_BY_LEVEL` declara el binding normativo CP → estructura en los seis niveles (A2/B2/C1 validados contra `can_do`/topic; A1 y C2 nuevos). Un mismo objetivo puede agrupar varios CP y `production.evidence` cuenta CP superados, no filas.
- **Esquema y endpoint sin marca de prototipo**: se elimina `proto` de `CrossSkillMatrixOut` (backend y `frontend/src/types/api.ts`); `/api/cross-skill` acepta `a1..c2`, valida el nivel (400 `cross_skill.level_unknown` para ids desconocidos) y mantiene `"b1"` como default inofensivo.
- **Panel cross-skill en todos los niveles**: `CrossSkillMatrix` se monta en el panel del nivel Grammar para cualquier nivel (no solo B1); se retira el pie "prototipo B1", el título/nota se generalizan y la clave `crossSkill.protoNote` desaparece de i18n (`en`/`es`).
- **Tests e invariantes**: `backend/tests/test_cross_skill.py` reescrito con invariantes por nivel (registro == objetivos con MC de grammar, bindings normativos sin CP huérfanos, semántica de matriz y endpoint para los 6 niveles); nuevo invariante de contenido que protege la producción enlazada de A1/C2. Test `test_grammar_routes.py` actualizado (todos los niveles aportan CP al banco) y docstrings de los invariantes pedagógicos de C2 (4 MC → 4 MC + 4 CP) sincronizados. Playwright `grammarRoutesReview` mockea `/api/cross-skill` (determinista sin backend).

## [3.13.0] — 2026-09-05

**Calibración de evidencia pedagógica: del "¿está implementada la actividad?" al "¿la evidencia demuestra competencia?".**

La iteración V3.13 no añade actividades nuevas: **recalibra el modelo pedagógico** que cerró la auditoría de V3.8 y lo convierte en un único documento normativo con reglas inmutables R1–R7 (`docs/CONSTITUCION-PEDAGOGICA.md`: Practice≠Mastery, Mastery≠Certificación, Vocabulary≠nivel, One skill≠Overall, Recognition≠Production, Éxito≠Retención, Muestra pequeña≠Competencia). Backend `3.12.0 → 3.13.0`.

- **Evidence depth por destreza/nivel** (nuevo `backend/services/evidence_depth.py`): cada competencia clasifica su evidencia formal en bandas **LOW/MEDIUM/HIGH** contra los mínimos de `backend/curriculum/cefr_matrix.json` (`minimum_evidence`, transfer/novel, retardada) y lo expone en `/api/profile` junto a `competence_states`. La evidencia de `academy_evidence` se atribuye a nivel desde ahora (retrocompatible).
- **Claims honestos para bancos cortos**: `stats` por nivel incluyen `bank_size` y `evidence_depth`; los bancos ≤ 12 checks (Grammar B2 y C2) muestran la etiqueta **"practice coverage · evidence depth LOW"** en lugar de invitar a leer competencia, y el techo `functional` de la ruta se mantiene.
- **Suelo de "demostrado" por destreza**: `demonstrated` exige ahora gate funcional **y** `minimum_evidence` de la matriz **y** retención retardada estable ≥ 7 días; en destrezas productivas (grammar/speaking/writing) exige además **muestras de producción** (solo MC de reconocimiento jamás demuestra). Vocabulary es condición de apoyo y queda techado en `functional`.
- **`current_level` como sugerencia de material**: deja de ser "primer nivel no dominado"; con todo dominado elige por repaso pendiente (`review_due`), y la UI no lo lee como banda CEFR del alumno.
- **Grammar en 3 niveles (R5)**: nuevos ítems **`controlled_production`** en el currículo (A2–C1, ~6-10 por nivel) — prompt con hueco + respuestas aceptadas, corrección determinista por normalización, sin LLM — sobre el motor compartido de rutas quiz. La UI los sirve como "type the answer" con feedback y revelación de lo esperado.
- **Cross-skill evidence (prototipo B1)**: registro de estructuras que cruza recognition/production/listening/speaking/transfer por objetivo; nueva matriz por estructura con endpoint `/api/cross-skill` y panel en Grammar B1 (`CrossSkillMatrix`).
- **Golden pedagogical dataset**: `backend/tests/golden/pedagogy/evidence_depth_cases.json` + `test_golden_pedagogy.py` congelan la calibración auditada (LOW/MEDIUM/HIGH, minimum evidence, producción) para que los invariantes pedagógicos no regresionen.
- **LearnRoutePage compartido (V3.13 P2.1)**: `frontend/src/features/routes/QuizRoutePage.tsx` unifica las páginas de ruta de Grammar, Vocabulary, Pronunciation, Conversation y Speaking (mapa A1–C2, panel de nivel, máquina de sesión, gate, assessment formal) en un shell config-driven: cada skill aporta config (API, i18n, panel, escena personalizada y bloques contextuales). Se consolidan las máquinas de sesión espejo (`routeSession.ts`) y se eliminan ~1.600 líneas duplicadas. Listening no migra por diseño: es la única práctica del hub servida dentro del runner `PracticeView` del workspace.
- **Parity i18n automática**: `frontend/src/utils/i18n.parity.test.ts` garantiza claves `en`/`es` no vacías, sin duplicados y sin claves usadas sin resolver.

## [3.12.0] — 2026-09-05

**Grammar por rutas CEFR: página única de checks MC del currículo.**

APRENDER → Grammar deja el chat del tutor (que sigue en `/chat`) y pasa a una
**página única con scroll** (espejo de Speaking/Listening/Pronunciation/
Conversation/Vocabulary): arriba vive el escenario de práctica —un **check MC de
grammar del currículo** del nivel recomendado, con feedback inmediato y
respuesta correcta revelada al fallar— y debajo el mapa de rutas A1–C2 con
anillos y, al abrir un nivel, sus modos (Practicar el nivel / Repetir fallidas /
Repasar aprendidas) y el bloque «Demostrar el nivel» que abre los instrumentos
formales del curso (exámenes y escalera de evaluaciones) como vía honesta para
demostrar el nivel.

El banco **no se inventa**: cada nivel reutiliza los **checks MC de la destreza
grammar del currículo oficial** (`backend/curriculum/a1.json`…`c2.json`, 97
checks en total), sin contenido nuevo. Grammar monta sobre el **motor compartido
de rutas quiz** (`backend/services/quiz_routes.py`, estrenado por Vocabulary)
con su propia tabla (`grammar_route_attempts`), endpoints
`/api/grammar/routes/*` y namespace de errores; los **bancos cortos** (B2 = 8 y
C2 = 4) adaptan la puerta automáticamente. Cada intento es determinista y se
persiste. La ruta es un hito de práctica (`functional`, nunca certifica);
demostrar el nivel exige los exámenes y evaluaciones del curso. Con Grammar,
**las 6 actividades de APRENDER comparten la misma página única de rutas CEFR**
(Listening, Speaking, Pronunciation, Conversation, Vocabulary y Grammar).

## [3.11.0] — 2026-09-05

**Vocabulary por rutas CEFR: página única de checks MC del currículo + diccionario a mano.**

APRENDER → Vocabulary pasa de ser solo el diccionario personal a una **página
única con scroll** (espejo de Speaking/Listening/Pronunciation/Conversation):
arriba vive el escenario de práctica —un **check MC de vocabulary del
currículo** del nivel recomendado, con feedback inmediato y respuesta correcta
revelada al fallar— y debajo el mapa de rutas A1–C2 con anillos y, al abrir un
nivel, sus modos (Practicar el nivel / Repetir fallidas / Repasar aprendidas) y
el bloque «Demostrar el nivel» que abre los instrumentos formales del curso
(exámenes y escalera de evaluaciones) como vía honesta para demostrar el nivel.

El banco **no se inventa**: cada nivel reutiliza los **checks MC de la destreza
vocabulary del currículo oficial** (`backend/curriculum/a1.json`…`c2.json`), sin
contenido nuevo. La lógica de rutas sobre checks MC vive en un **motor
compartido** (`backend/services/quiz_routes.py`) que Grammar (v3.12) reutilizará:
puerta de cobertura/precisión/checkpoint adaptada a bancos cortos. Cada intento
es determinista y se persiste en `vocabulary_route_attempts`. La ruta es un
hito de práctica (`functional`, nunca certifica); demostrar el nivel exige los
exámenes y evaluaciones del curso. El **diccionario personal** se integra en la
propia página (botón «Mi diccionario»), conservando su función completa.

## [3.10.0] — 2026-09-04

**Conversation por rutas CEFR: página única de mini-diálogos guiados multi-turno.**

APRENDER → Conversation deja de ser el chat libre (que ahora vive en su propia
raíz `/chat`, siempre accesible desde la página) y pasa a una **página única con
scroll** (espejo de Speaking/Listening/Pronunciation): arriba vive el escenario
de práctica —un **mini-diálogo guiado multi-turno** con el tutor: situación,
roles y metas comunicativas, línea de apertura, y se conversa por texto o con el
micrófono hasta cumplir las metas— y debajo el mapa de rutas A1–C2 con anillos
y, al abrir un nivel, sus modos (Practicar el nivel / Repetir fallidos / Repasar
aprendidos) y el bloque «Demostrar el nivel» que abre el Speaking Assessment.

El contenido es un banco oficial versionado y auditable
`curriculum/conversation_corpus.json` (v1.0.0: **11 mini-diálogos por nivel**,
A1–C2, con contexto, roles, apertura y metas comunicativas alineadas con el
currículo). Al terminar una conversación (mínimo de turnos y palabras), se
**evalúa el transcripto completo** con el pipeline de evidencia LLM existente
(`extract_speaking_evidence`, task_type conversation) fusionado con la señal
objetiva de interacción, y se persiste el intento por diálogo. La ruta mide
práctica sobre el banco oficial (puerta de cobertura/precisión/checkpoint) con
techo `functional`. Honestidad pedagógica intacta: la ruta **nunca certifica** —
demostrar el nivel solo puede venir del Speaking Assessment + evidencia +
retención—, con nota honesta del nivel oral demostrado.

## [3.9.0] — 2026-09-04

**Pronunciation por rutas CEFR: página única read-aloud con operativa tipo Listening/Speaking.**

APRENDER → Pronunciation deja la práctica libre de 3 frases fijas y pasa a una
**página única con scroll** (espejo de Speaking/Listening): arriba vive el
escenario de práctica —una **frase modelo** que escuchas (TTS local) y lees en
voz alta grabándote— y debajo el mapa de rutas A1–C2 con anillos y, al abrir un
nivel, sus modos (Practicar el nivel / Repetir fallidas / Repasar aprendidas) y
el bloque «Demostrar el nivel» que abre el Speaking Assessment (instrumento
formal oral que ya cubre la banda). Todo en la misma página, con control total
del alumno.

El contenido y la evaluación son nuevos: banco oficial versionado y auditable
`curriculum/pronunciation_corpus.json` (v1.0.0: **20 frases por nivel**, A1–C2,
progresivas) y cada lectura se puntúa de forma **determinista y barata**:
Whisper transcribe la grabación y `score_pronunciation` calcula el composite
fonético (score ≥80 = superada; desglose de palabras, fonética, fonemas, prosodia
y fluidez), sin LLM por intento. La ruta mide práctica sobre el banco oficial
(puerta de cobertura/precisión/checkpoint) con techo `functional`.

Honestidad pedagógica intacta: la ruta **nunca certifica** — «demostrar el
nivel» solo puede venir del Speaking Assessment + evidencia + retención, y la
app lo refleja con la nota honesta del nivel oral demostrado. El read-aloud
clásico sigue disponible como sección de las lecciones del curso; el hub abre la
nueva página de rutas.

## [3.8.0] — 2026-09-04

**Speaking por micro-conversaciones guiadas, con operativa tipo Listening.**

APRENDER → Speaking deja la sesión a pantalla completa y pasa a una **página
única con scroll** (espejo de Listening): arriba vive el escenario de práctica
—una tarjeta de micro-conversación guiada: situación + tu rol + la línea del
interlocutor (con voz modelo), a la que respondes **hablando con tus
palabras**— y debajo el mapa de rutas A1–C2 con anillos y, al abrir un nivel,
sus modos (Practicar el nivel / Repetir fallidas / Repasar aprendidas / Añadir
práctica extra) y el bloque «Demostrar el nivel» que abre el Speaking
Assessment. Todo en la misma página, con control total del alumno en cualquier
momento (cambiar de ruta o modo sin encerrarse en una pantalla).

El contenido y la evaluación cambian a fondo: el banco oficial
`curriculum/speaking_corpus.json` se regenera como **tarjetas de intercambio**
(v2.0.0: A1 36 · A2 32 · B1 28 · B2 22 · C1 16 · C2 14) con
`{id, level, topic, setup, you, app_line, model_response, difficulty_vector}`,
y cada intento se puntúa como **respuesta abierta** con el pipeline LLM +
evidencia que ya usan misiones/assessment (`extract_speaking_evidence` +
`scores_from_evidence`, overall ≥0.6 = superada); la respuesta modelo se revela
tras hablar. Si el extractor local falla se responde 503 transitorio para
reintentar — nunca se puntúa en falso. La práctica extra generada produce
tarjetas del mismo tipo (prompt, validación determinista y dedupe por
intercambio). El TTS modelo se sirve con caché por tipo de audio
(`GET /api/speaking/audio/{id}?kind=opening|model`).

Honestidad pedagógica intacta: la ruta sigue siendo un **hito de práctica**
(estado techo `functional`, puerta de cobertura/precisión/checkpoint sobre el
banco oficial); «demostrar el nivel» solo puede venir del Speaking Assessment +
escenarios/misiones + retención, nunca de la ruta. El read-aloud de V3.7 queda
cubierto por Pronunciation; Speaking pasa a producción guiada, coherente con
Listening (comprensión por rutas) y Conversation (libre).

### Añadido
- `backend/curriculum/speaking_corpus.json` v2.0.0: banco curado de tarjetas de
  micro-conversación guiada por nivel y tema (auditado: campos, niveles,
  longitudes producibles).
- `GET /api/speaking/audio/{phrase_id}?kind=opening|model`: voz TTS cacheada de
  la línea del interlocutor (`opening`, por defecto) y de la respuesta modelo
  (`model`); `kind` inválido o tarjeta inexistente → 404.
- Frontend: escenario superior con tarjeta de intercambio (situación/rol/línea
  del interlocutor con traducción y altavoz, botón «Oír al interlocutor»,
  grabación, evaluación «Evaluando…», `ActivityResult` con barras por criterios
  y revelado de la **respuesta modelo** con voz y traducción), barra de sesión
  compacta, mapa de rutas con anillos y panel del nivel bajo el escenario, y
  sesión sin pantalla separada (practicar/repetir fallidas/repasar aprendidas/
  práctica extra). Escenarios y misiones quedan como secciones plegables.

### Cambiado
- El intento de speaking evalúa la respuesta abierta (LLM local extrae evidencia
  desde la tarjeta + `scores_from_evidence`), no la lectura contra una frase.
- Schemas y tipos (`SpeakingPhrase`, `SpeakingAttemptResponse`, `SpeakingItemOut`
  y espejo en `types/api.ts`) con `setup/you/app_line/model_response`.
- `speaking_generate.py` v2.0.0: prompt, bandas de longitud, validación y
  dedupe por intercambio (`canonical_card`) para tarjetas extra.
- i18n EN/ES de la operativa nueva; textos honestos (ruta = hito de práctica;
  demostrar = examen + evidencia + retención).
- Tests adaptados: backend (corpus, motor, intento con extractor mock, 503 al
  fallar el extractor, audio por kind), frontend (`tsc`, `vitest`) y spec visual
  Playwright de la página única con mocks deterministas.

## [3.7.0] — 2026-09-04

**Speaking por rutas CEFR (A1→C2) + fuente compacta en los logs del lanzador.**

APRENDER → Speaking deja de ser una sola tarjeta de práctica libre y pasa a ser
un mapa de **rutas CEFR**, replicando las mecánicas que ya tenía Listening: cada
nivel es una ruta de frases modelo del nivel (banco curado oficial nuevo,
`curriculum/speaking_corpus.json`) que se practican en voz alta (read-aloud): se
ve la frase escrita, se puede oír la voz modelo (TTS) y se graba. La puntuación
es determinista y local (`score_speaking`, sin LLM por intento). Por ruta se
puede practicar el nivel completo, repetir las falladas hasta dominarlas, repasar
las aprendidas y añadir práctica extra generada por IA local cuando el banco
oficial se domina.

Honestidad pedagógica: la ruta es un **hito de práctica** (estado techo
`functional` con puerta de cobertura/precisión/checkpoint); el nivel
«demostrado» solo puede venir del Speaking Assessment + escenarios/misiones +
retención, nunca de superar la ruta. El examen, escenarios y misiones siguen
accesibles desde el mapa/panel de nivel.

### Añadido (backend)
- `curriculum/speaking_corpus.json`: banco oficial curado de frases modelo por
  nivel (A1 65, A2 60, B1 50, B2 40, C1 32, C2 30) con `{id, level, phrase,
  topic, difficulty_vector}`.
- Tablas SQLite `speaking_attempts`, `speaking_generated`,
  `speaking_route_extras` y `speaking_generation_jobs` (+ repositorio
  `repositories/speaking_routes.py`).
- Motor `services/speaking_routes.py` (pool por ruta, estados por frase, puerta
  de ruta anclada al banco oficial, `route_competence` que nunca emite
  `demonstrated`).
- `services/speaking_generate.py` (frases extra con IA local) y orquestación en
  `domain/speaking_routes.py` (trabajos en segundo plano, audio modelo TTS con
  caché versionada por voz).
- Endpoints `/api/speaking/{question,items,stats,audio/{id},attempt}` y
  `/api/speaking/routes/{level}/extras` (+jobs y DELETE).
- `GET /api/system/status`: agrega los trabajos de generación de speaking en
  curso al estado que consume el lanzador.

### Añadido (frontend)
- APRENDER → Speaking es ahora `SpeakingRoutesPractice`: mapa A1–C2 con anillos,
  cabecera de precisión y nivel oral demostrado, panel por nivel
  (`SpeakingLevelPanel`) con historial de frases falladas/dominadas/sin ver,
  Repetir fallidas, Repasar aprendidas, añadir práctica extra (+10/+25/+50) y el
  bloque «Demostrar el nivel» que abre el Speaking Assessment.
- Sesión de práctica read-aloud con voz modelo, grabación de micrófono y
  resultado con barras de criterios honestas (la puntuación es retroalimentación
  de la ruta, no certificado).
- `api/speakingRoutes.ts` + tipos `Speaking*`; i18n EN/ES de toda la zona.

### Cambiado (launcher)
- Los logs (`backend.log`/`frontend.log`) se muestran en fuente compacta
  monospace (Consolas 8, sin espaciado, wrap por carácter), como una terminal
  pequeña y densa.

### Corregido
- `domain/speaking_routes.get_stats`: el cálculo de `completed` leía `passed`
  fuera del `gate` (KeyError al consultar `/api/speaking/stats`); ahora usa
  `g["gate"]["passed"]`.

## [3.6.2] — 2026-09-04

**Estado del servidor en el lanzador + corrección del 429 espurio.**
El 429 «Demasiadas peticiones» que aparecía en la app cuando el servidor local
estaba saturado lo devolvía el rate limiter propio (`SecurityMiddleware`), no
Ollama: cuenta peticiones por IP en ventanas de 60 s y, al saturarse el
servidor (generación de práctica extra con IA local, TTS Piper), las ráfagas
de pollers, reintentos del usuario y sondas del lanzador superaban los topes y
se rechazaban en cascada. Además, el launcher solo mostraba «Activo/Detenido» y
no permitía ver cuándo el backend estaba trabajando. En esta versión se
endurece el rate limiter para uso local (topes holgados, `/api/health` exento
de cupo y de 429), se telemetrifican los rechazos y el launcher muestra la
«Actividad del servidor».

### Cambiado (backend)
- `security.py`: las peticiones GET/HEAD a `/api/health` quedan exentas del rate
  limit (nunca consumen cupo ni pueden recibir 429, así el health-check y el
  launcher siguen vivos aunque el servidor esté saturado); topes subidos para
  uso local razonable (`_DEFAULT_LIMIT` 600 → 1200; `/api/chat` 120 → 240,
  `/api/voz/transcribe` 60 → 180, `upload`/`backup` 30 → 60, `restore`
  10 → 20); el 429 ahora responde con `{"detail", "code": "RATE_LIMITED"}` y
  `Retry-After: 5`, con mensaje accionable y `logger.warning` al rechazar.
- `security.py`: nuevo `rate_limit_snapshot(window_seconds)` que cuenta los
  rechazos del último minuto, y `is_exempt(path)` (V3.6.2).

### Añadido (backend)
- `GET /api/system/status` (sin candado admin, como `/api/health`): devuelve
  `generation.running/jobs` (trabajos de práctica extra en curso, por nivel) y
  `rate_limited.rejected_last_minute` desde `security.rate_limit_snapshot()`.
- `repositories/listening.py`: `list_running_generation_jobs()`.

### Cambiado (launcher)
- Nueva sección desplegable **«Actividad del servidor»**: línea de trabajo
  («En reposo» / «Generando práctica extra (A1)…») y rechazos por saturación
  del último minuto; verde en reposo y ámbar al trabajar o rechazar. Cuando el
  backend está generando o rechazando, la píldora de cabecera pasa a
  «En marcha · generando…» / «En marcha · saturado» en ámbar.
- `status.py`: `fetch_server_status()`; `ui.py`: helper puro `server_activity`.

### Cambiado (frontend)
- `api/client.ts`: ante un 429 con `code: RATE_LIMITED`, el mensaje de error se
  traduce a la lengua activa (`errors.rateLimited`) en vez de mostrar el texto
  interno del backend. `utils/i18n.ts`: clave `errors.rateLimited` (EN/ES).

### Verificación
- Backend: `pytest tests/test_security.py tests/test_system_status.py` en verde
  (exención de `/api/health`, payload `code`/`Retry-After`, `rate_limit_snapshot`,
  endpoint `/api/system/status` con/sin trabajos y rechazos).
- Launcher: `pytest tests` (74 tests) en verde (helpers puros de la nueva
  sección y `fetch_server_status` con mock).
- Frontend: `npx tsc --noEmit` y `npx vitest run src/api/client.test.ts` en verde
  (429 localizado en ES/EN y `detail` conservado para otros errores).

## [3.6.1] — 2026-09-04

**Atajos de APRENDER + coherencia de idioma.**
La franja superior de cada práctica de APRENDER (Listening, Speaking,
Pronunciation, Conversation, Vocabulary, Grammar) deja de ser solo una flecha de
vuelta al hub: ahora muestra un **selector con las 6 actividades** (icono +
nombre; solo iconos en pantallas estrechas, con `title`/aria) que navega por
hash y resalta la activa. Los **nombres de actividad se unifican en inglés en
ambos idiomas** (Grammar/Pronunciation/Vocabulary/Conversation, igual que ya
estaban Listening/Speaking/Reading/Writing) y se barre el chrome que se pintaba
en inglés fijo aunque la UI estuviera en español.

### Añadido (frontend)
- `components/LearnActivitySwitcher.tsx` (nuevo): atajo entre actividades,
  reutiliza los iconos del hub y `learnActivityPath`; integrado en la franja de
  `PracticeView` (práctica libre de Listening/Pronunciación/Gramática y de
  Conversar, oculto durante una lección del curso), en `SpeakingFreePractice` y
  en el `SubpageHeader` de Vocabulario.

### Cambiado
- `utils/i18n.ts`: `skill.grammar/pronunciation/vocabulary` y
  `learn.conversation` con el mismo valor en `en` y `es` (nombres en inglés).
- Chrome localizado con la UI en español: tipo de audio y buckets de retención
  de listening (`listening.audioType.*`, `listening.retentionBucket.*`,
  `utils/listeningLabels.ts`), resumen del dictado y fila de sub-destrezas del
  diagnóstico (`auto/mean/audio not backed`), fluidez/palabras por minuto y
  avisos por palabra de pronunciación (`pron.*`), píldoras y estabilidad del
  plan del día (`today.kind.*`, `today.stability`), foco y botón de Writing
  (`writing.nextFocus/practiceNow`), marcador del recorrido (`writing.you`),
  título del Speaking Assessment y delta en puntos (`assessment.titleScore`,
  `speaking.deltaPts`), marcadores de puerta del curso (`course.gatePass/Due`)
  y skip-link (`common.skipToContent`).

### Sin traducir (a propósito)
Se mantienen intencionalmente en inglés y se anotan aquí para no reabrirlos:
nombres de *topic* del banco y sub-destrezas de listening (datos), frases de
ejemplo conversacionales y nombres de criterios de rúbrica de speaking/writing
("Task achievement", "Grammatical control", … — jerga de assessment).

### Verificación
- Frontend: `npx tsc --noEmit` y `npx vitest run` (320 tests) en verde;
  Playwright en verde (smoke ampliado: el atajo de actividades es visible en
  APRENDER/LISTENING y pulsar Vocabulario navega a su hoja).
- Comprobación manual con la UI en español: nombres de actividad en inglés y
  resto de la interfaz en español en el hub de APRENDER y sus 6 prácticas.

## [3.6.0] — 2026-09-04

**Listening: práctica ilimitada con ítems generados + repaso de lo aprendido.**
Cada ruta (A1..C2) era un banco curado finito: al dominarlo no quedaban frases
nuevas que practicar en ese nivel. Ahora el alumno puede pedir más práctica
dentro de la ruta y el backend genera ítems completos
(`{script, question, options, …}`) con el modelo local *utilizable* (nunca los
`UNUSABLE_MODELS`), validados de forma determinista antes de publicarse —la
opción correcta debe ser un fragmento literal del guion normalizado, así la
respuesta siempre es verificable por audio— y con el audio sintetizado por Piper
bajo demanda con la caché existente.

La práctica generada es **contenido complementario, no oficial**: la puerta de
ruta, `completed`, el estado `functional`/`demonstrated` y el routing adaptativo
se calculan siempre solo sobre el banco curado, así que añadir extras nunca
revoca una ruta superada ni encarece certificarla. El anillo de la ruta muestra
el desglose «205 oficiales · +55 extra» y el denominador crece («Dominadas 205
de 260»), y desde cada ruta se puede **repasar lo aprendido** (rotación solo
sobre las frases ya dominadas, además del drill de falladas y de la ruta
completa).

### Añadido (backend)
- `repositories/db.py`: tablas `listening_generated` (catálogo global de ítems
  generados), `listening_route_extras` (activación por usuario, reversible) y
  `listening_generation_jobs` (trabajos de generación en segundo plano).
- `services/listening_generate.py` (nuevo): generador con prompt CEFR por nivel
  (tema/sub-destreza), parseo estricto del JSON, validación determinista
  (opción correcta literal en el guion, distractores sin colisión) y
  `GENERATOR_VERSION`.
- `services/listening.py`: `route_questions`/`resolve_question` con extras
  (dedupe por id), selector de repaso `only_mastered`; `route_gate`,
  `level_status` y `current_level` siguen sobre el banco curado sin recibir
  extras.
- `domain/listening_extras.py` (nuevo): orquestación del trabajo de generación
  (lotes, dedupe por script contra banco curado y catálogo, activación en la
  ruta al terminar).
- `domain/listening.py` + `schemas/listening.py` + `routers/listening.py`:
  `POST/GET/DELETE /api/listening/routes/{level}/extras[…]`; stats por ruta con
  `base_total`/`extras`/`extras_mastered`; ítems con `source` `"base"`/`"generated"`;
  ids `g-*` resueltos en `submit_answer`/`get_audio`; modo de sesión `mastered`.

### Añadido (frontend)
- `api/listening.ts` + `types/api.ts`: clientes y tipos de extras (trabajo,
  activación por ruta) y de los nuevos campos de stats/ítems.
- `features/listening/ListeningPractice.tsx`: anillo base+extras con desglose
  «oficiales + extra», estado del trabajo de generación (en marcha / hecho /
  error) y aviso honesto de que los ítems generados no alteran la certificación.
- `features/listening/ListeningLevelPanel.tsx`: botón **«Repasar lo aprendido
  (N)»**, etiqueta «práctica generada» en las filas generadas y bloque **«Añadir
  más práctica a {level}»** (cantidades 10/25/50), visible al dominar el banco
  oficial.
- `features/listening/listeningSession.ts`: nueva variante de sesión
  `mode: "mastered"` (misma vuelta LRU que `level` pero solo dominadas).
- `utils/i18n.ts`: claves `listening.reviewLearned*`, `listening.extra*`,
  `listening.generatedTag` y el aviso honesto, en ES y EN.

### Verificación
- Backend: tests del generador con cliente Ollama simulado, no-regresión de la
  puerta al añadir extras, repaso solo-dominadas y endpoints.
- Frontend: `npx tsc --noEmit` y `npx vitest run` (319 tests) en verde; smoke
  visual de Playwright ampliado con la captura `listening-route` (panel de ruta
  desplegado), en verde.

## [3.5.8] — 2026-09-04

**Auditoría de UI (contraste claro/oscuro + QR).** El código QR de
"Conectar un dispositivo" (Ajustes → Sistema y popover "Ready" del footer) se
pintaba con módulos negros sobre el fondo de tarjeta, que en modo oscuro es casi
negro: el QR quedaba invisible. Ahora el QR vive siempre sobre una tarjeta
blanca independiente del tema, así que se escanea igual en claro y en oscuro.

Además se hizo una pasada de auditoría por contraste (ratio WCAG calculado por
elemento con texto en todas las pantallas, en ambos temas) que corrigió los
puntos de legibilidad más claros.

### Cambiado (frontend)
- `components/ConnectDeviceCard.tsx`: el QR se muestra sobre tarjeta blanca fija
  (`bg-white`, módulos `#000`), sin depender de `bg-background`.
- `styles/legacy.css`: nuevos tokens de acento para texto (`--color-accent-soft`;
  índigo claro en oscuro, índigo oscuro en claro) usados por
  `.cefr-badge.intermediate` (la insignia "B1" era ilegible en oscuro, ratio 2.65);
  `--color-warning` en claro más oscuro (`#b45309`) para el texto ámbar sobre
  blanco (A1/A2, etiquetas de estado); `--color-text-faint` más legible en ambos
  temas (fechas, ejes y subtítulos de la línea de tiempo).
- `components/UserMenu.tsx` + `.user-avatar--placeholder`: el avatar provisional
  "?" sin perfil tenía texto blanco sobre fondo blanco en modo claro; ahora lleva
  fondo neutro y borde visibles.
- Tests visuales estables (`tests/visual/`): con la ProfileGate (V3.5.7), un
  navegador con varios perfiles y sin cookie mostraba la puerta y bloqueaba la
  interacción. Nuevo helper `gateHelper.ts` que crea/recupera el perfil de test
  "Visual Tester" vía API y mockea `GET /api/users` con un único perfil para que
  la app lo auto-seleccione; aplicado a `smoke`, `mobile` y `resize`.

### Verificación
- Sonda de contraste en 9 pantallas × 2 temas: insignia B1 oscuro 2.65 → ≥4.5;
  ámbar claro 3.19 → 4.43–4.98; faint oscuro 3.76 → ≥4.9, claro 2.70 → 3.74.
- Suite visual Playwright completa (desktop/tablet/mobile): 24 tests en verde
  (14 ejecutados, 10 skips de breakpoint previstos).
- `npx tsc --noEmit` y `npx vitest run` (318 tests) en verde.

## [3.5.7] — 2026-09-04

**Selector de perfil al arrancar.** Si la app se abre en un navegador nuevo y
no hay ningún usuario definido (sin cookie recordada y con varios perfiles, o
todavía sin perfiles creados), en lugar de quedarse con un usuario sin
seleccionar o crear uno en silencio, ahora muestra la puerta **"Selecciona un
usuario o crea uno nuevo"** con la lista de perfiles y el campo para crear uno.
Hasta que no se elige un perfil la app no se puede usar (todo cuelga de
`userId`), así que la puerta no se puede cerrar sin elegir.

### Cambiado (frontend)
- `hooks/useChat.ts`: ya **no se crea un perfil por defecto en silencio** cuando
  no hay ninguno; nuevo estado `usersLoaded` para distinguir "cargando" de "sin
  perfil seleccionado". `addUser` ahora devuelve si el backend respondió.
- `components/ProfileGate.tsx` (nuevo): diálogo no cerrable con la lista de
  perfiles existentes (avatar + nombre) y el formulario "Nuevo perfil"; si el
  backend no responde al crear, muestra un aviso en vez de fallar en silencio.
- `App.tsx`: muestra `ProfileGate` cuando `usersLoaded && !currentUserId`.
- Claves i18n `user.choose*`, `user.noProfilesYet`, `user.createProfile` y
  `user.createError`.

Nota: el comportamiento de un solo perfil se conserva (al ser único se
auto-selecciona al abrir cualquier navegador, sin preguntar).

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests) en verde.

## [3.5.6] — 2026-09-04

**Modelos no utilizables fuera de la app.** `qwen3.5:9b` quedó diagnosticado como
inutilizable en este equipo (en CPU tarda 10–64 s por turno y se descarga/recarga
entre llamadas). Ya no aparece en las opciones de configuración (Ajustes → IA) ni
se usa como modelo por defecto en ningún flujo; la app trabaja con `llama3.1:8b`
(instalado y rápido). La lista de excluidos es configurable en
`config.UNUSABLE_MODELS`.

### Cambiado (backend)
- `config.py`: nuevo `UNUSABLE_MODELS = {"qwen3.5:9b"}` (instalados en Ollama
  pero no utilizables) y `DEFAULT_MODEL = "llama3.1:8b"` (el defecto ya no puede
  estar bloqueado).
- `GET /api/models` (`routers/models.py`): excluye los modelos de
  `UNUSABLE_MODELS`. El selector de Ajustes → IA deja de ofrecerlos.
- `services/translate.py`: la traducción a demanda nunca elige un modelo no
  utilizable; si no hay ninguno preferido, usa el primer modelo utilizable
  instalado y solo en último caso el defecto.
- Tests: `tests/test_models.py` (el endpoint filtra y el default no está
  bloqueado) y `tests/test_translate.py` ampliado (no elige no utilizables,
  primero utilizable, sin modelos → default).

### Cambiado (frontend)
- `hooks/useChat.ts`: modelo por defecto `llama3.1:8b`; al restaurar
  preferencias guardadas solo aplica un modelo si sigue ofertándose; nuevo efecto
  de saneo: si el modelo activo o el favorito persistido quedan excluidos por el
  backend, cae al primer modelo disponible y olvida el favorito inalcanzable
  (así una preferencia vieja con `qwen3.5:9b` no vuelve a ralentizar el chat).
- `features/speaking/SpeakingRolePlay.tsx`: el role-play conversacional usa el
  modelo utilizable por defecto.

### Verificación
- `pytest` (subset 30 tests, incluidos `test_models.py` y `test_translate.py`)
  en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` en verde.

## [3.5.5] — 2026-09-04

**Fix: la traducción de apoyo no respondía y ampliación al resto de pantallas.**
La traducción de la v3.5.4 usaba el modelo por defecto del chat (`qwen3.5:9b`),
que en CPU tarda **10–64 s por frase** (se descarga y recarga entre llamadas) y
superaba el timeout del cliente: el botón se quedaba dando vueltas y acababa en
"Traducción no disponible". Ahora el servidor **elige automáticamente el modelo
rápido instalado** para traducir y el botón cubre también Speaking y
Pronunciación.

### Cambiado (backend)
- `services/translate.py`: selección de modelo por latencia. Orden de
  preferencia `llama3.1:8b` → `qwen2.5-coder:1.5b` (con caché de la lista de
  modelos instalados de 5 min); si ninguno está instalado, se cae al modelo por
  defecto. Medido en este equipo: llama3.1 traduce en **~0,3–5 s** frente a
  10–64 s del modelo por defecto. La petición puede forzar un modelo concreto
  (`model`), ahora opcional en `schemas/translate.py`.
- Tests ampliados en `tests/test_translate.py` (13): preferencia de modelo,
  fallback, Ollama caído y endpoint herméticos (sin consultar a Ollama real).

### Cambiado (frontend)
- `api/translate.ts`: timeout de 45 → **60 s** (la primera frase de una sesión
  puede cargar el modelo ligero en CPU; después es instantánea gracias a la
  caché por frase del cliente y del servidor).
- El botón de traducción ya no está solo en listening: ahora también en
  **Speaking Assessment** (junto al prompt de la parte) y en
  **Pronunciación** (junto a la frase elegida y a la frase esperada del
  resultado). Cada uno se reinicia en inglés al cambiar de frase/intento.

### Verificación
- `pytest` (subset 41 tests, incluidos 13 de `test_translate.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests) en verde.
- Prueba real end-to-end contra Ollama: traducción automática con `llama3.1:8b`
  en 0,6 s y 0,3 s para dos frases.

## [3.5.4] — 2026-09-04

**Traducción de apoyo EN→ES en listening.** Un botón nuevo junto al altavoz de
los textos de práctica traduce al español la frase que el alumno no entiende y,
al pulsarlo de nuevo, vuelve al inglés. Es una *ayuda a demanda*: nunca aparece
automáticamente, se reinicia en inglés en cada pregunta y **no cuenta como
intento ni afecta a evidencia, puertas o métricas** (coherente con la
Constitución: la comprensión en inglés sigue siendo la vía principal).

### Añadido (backend)
- `POST /api/translate` (`{text, model?}`) → `{translation}`: traduce con el
  modelo local (Ollama) y mantiene una caché en memoria por frase
  (`services/translate.py`): la primera vez paga la latencia del modelo y las
  siguientes son instantáneas. 422 si el texto está vacío; 502 con mensaje
  legible si el modelo local no está disponible. No registra ninguna actividad.
- Tests en `tests/test_translate.py` (servicio con caché + endpoint).

### Añadido (frontend)
- `api/translate.ts`: cliente con caché por frase y timeout de 45 s (el modelo
  local en CPU tarda en la primera traducción).
- `components/PhraseTranslate.tsx`: hook `usePhraseTranslation(text, resetKey)`
  (estado por frase, se reinicia al cambiar de pregunta) y botón circular "ES"
  junto al altavoz: activo (relleno) mientras muestra español, spinner durante
  la llamada y aviso transitorio si el modelo local no responde.
- **`ListeningPractice`**: botón de traducción en (1) el enunciado de la
  pregunta, (2) el texto oído del resultado MCQ y (3) la referencia de
  dictado/shadowing. Las opciones de respuesta **no** se traducen: hacerlo
  trivializaría el MCQ (emparejar traducciones en vez de escuchar).
- **`ListeningLevelPanel`**: botón en cada frase del historial/repaso por nivel.
- Claves i18n `translate.*` en `utils/i18n.ts`.

### Verificación
- `pytest tests/test_translate.py tests/test_voices.py tests/test_health.py
  tests/test_cors.py` en `backend/` (35 tests) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests, incl.
  `api/translate.test.ts` para la caché por frase) en verde.

## [3.5.3] — 2026-09-04

**Fix: el botón "Continuar" de listening ya no desaparece.** En iPad (por WiFi
hacia el backend del PC, sobre todo con otra sesión abierta en el PC) una
petición que no terminaba dejaba la pantalla sin salida tras responder: el CTA
dependía de una respuesta de red que podía quedarse colgada y solo se arreglaba
refrescando. Ahora el bucle de práctica nunca se queda sin salida.

### Cambiado (frontend)
- **Timeouts de red en el bucle de listening** (`api/client.ts::withTimeout`,
  aplicado en `api/listening.ts` a pregunta, respuesta, dictado, shadowing,
  stats y diagnóstico): si una llamada no responde en 10–20 s, falla con un
  error legible en vez de esperar para siempre.
- **`ListeningPractice`**: al pulsar una opción MCQ se muestra "Evaluando…"
  (estado `submitting`, opciones deshabilitadas para evitar dobles envíos); si el
  envío falla o expira, la alerta de error ofrece **"Saltar a la siguiente
  pregunta"** para avanzar sin refrescar.
- **`NextStep`**: mientras el Adaptive Engine calcula la recomendación se muestra
  un placeholder visible (antes devolvía `null`, parecía un fallo) y, si el
  endpoint no responde en 8 s, aparece igualmente el CTA de salida (fallback).
  Con esto el resultado siempre tiene un botón "Continuar"/"Siguiente".

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (312 tests, incl.
  `client.test.ts` para `withTimeout`) en verde. Sin cambios en backend.

## [3.5.2] — 2026-09-04

**Descarga de voces desde la propia UI.** La pestaña "Voces" de Ajustes ahora
ofrece un catálogo curado de voces Piper de inglés (calidad `medium`, ~63 MB)
con botón "Descargar": la voz se baja del repositorio oficial a
`backend/models/piper/` y aparece al momento en la lista de instaladas. También
se instaló el set inicial de acentos (británico Alan, escocés Cori, norteño
Alba y americano Amy) además del default.

### Añadido (backend)
- `services/voice_downloads.py`: catálogo curado de voces Piper de inglés
  (id/etiqueta/ruta en HF), `available_to_download(installed)` y
  `download_voice(voice_id)` con descarga atómica (`.part` → `rename`, nunca se
  sirve un modelo a medio bajar) y bloqueo por voz.
- `POST /api/voices/download` (`{voice_id}`): descarga en threadpool; 400 para
  ids fuera del catálogo, 502 con mensaje legible si falla la red/escritura.
- `GET /api/voices` ahora expone también `downloadable` (catálogo no instalado,
  con `size_mb`).

### Añadido (frontend)
- `VoicesPanel` con sección "Añadir una voz": cada voz del catálogo con su
  tamaño y botón Descargar (estado de descarga en curso y error legible); al
  terminar refresca el catálogo. `api/voices.ts::downloadVoice` y tipo
  `DownloadableVoice`.

### Verificación
- `pytest` en `backend/` (tests de catálogo/descarga añadidos en
  `tests/test_voices.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.5.1] — 2026-09-04

**Voces TTS configurables por perfil.** Nuevo selector "Voces" en Ajustes
(Configuración → Voces) que ofrece las voces Piper instaladas en
`backend/models/piper/`, guarda la preferencia por usuario (`tts_voice`) y la
aplica al TTS en vivo y a la síntesis de los ítems de listening sin audio
humano. Además, la etiqueta del "modelo vocal" del ejercicio de listening deja de
mostrar el acento *declarado* del corpus ("… : AUSTRALIAN") en los ítems
sintetizados y muestra la voz real del perfil.

### Añadido (backend)
- `services/tts.py` con soporte multi-voz: `list_voices()` (scan de
  `models/piper/*.onnx.json` + `.onnx`, default primero), `resolve_voice(prefs)`
  (función pura: preferencia del usuario si está instalada; si no, default o
  primera voz disponible), `synthesize(..., voice=None)` e `is_ready(voice=None)`
  con instancias `PiperVoice` cacheadas por id (thread-safe). Catálogo amigable
  `VOICE_LABELS` para las voces oficiales de inglés (fallback: nombre derivado
  del id).
- `GET /api/voices?user_id=` (`routers/voices.py` + `schemas/voices.py`) que
  devuelve `{voices, default, selected}` resolviendo la preferencia del perfil
  contra lo instalado (`user_id` opcional → sin perfil, `selected` es el
  default).

### Cambiado (backend)
- La síntesis de listening es por voz y por usuario: `get_audio(user_id, …)`
  resuelve la voz preferida y cachea en
  `DATA_DIR/listening/{bank}/{voice}/{id}-{digest}.wav` (cada voz en su propia
  carpeta: cambiar de voz no invalida la caché anterior; la nueva se regenera
  bajo demanda en la primera reproducción y queda cacheada).
- `/api/tts` acepta `user_id` opcional (voz del perfil; sin perfil, la default).

### Añadido (frontend)
- Pestaña **Voces** en Ajustes (`VoicesPanel`): lista de voces instaladas con
  etiqueta amigable + id, insignia "por defecto", estado de guardado, y texto de
  ayuda para instalar más voces (colocar `<voz>.onnx` + `<voz>.onnx.json` en
  `backend/models/piper/`) y aviso de regeneración del audio de listening.
- `api/voices.ts` (`getVoices`) y tipos `VoiceInfo`/`VoicesResponse`.

### Cambiado (frontend)
- `speak(text, userId?)` pasa `user_id` a `/api/tts` para usar la voz del perfil.
- `ListeningPractice`: la tarjeta de audio de ítems sintéticos muestra la **voz
  real** del perfil (Ajustes → Voces) en vez del acento declarado del corpus; los
  ítems con audio humano conservan su acento declarado. La voz se refresca al
  abrir la tarjeta de audio (así refleja cambios hechos en Ajustes sin recargar).

### Verificación
- `pytest` en `backend/` (1108 tests, incl. `tests/test_voices.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.5.0] — 2026-09-03

**Tercera iteración de la Constitución pedagógica (P2, en la UI).** Cierra los
P2 8–10 del roadmap (§9): pantallas honestas de entrenamiento (la práctica de
listening se lee por estado de ruta, `functional` ≠ `demonstrated`), todo badge
de nivel estimado lleva el calificador "estimado · no certificado", y se elimina
el código muerto `modeCefrLevel`/`modeCefrBand`.

### Cambiado (frontend)
- **Pantallas honestas de entrenamiento (H7, P2-8)**: la UI tipa el estado
  pedagógico por ruta que ya expone el backend (`ListeningLevelProgress.state`:
  `not_started`/`developing`/`functional`/`demonstrated` + `retention`). La ruta
  se lee sin engaño en `ListeningPractice`, `ListeningLevelPanel` y
  `ListeningRecorridoPanel`:
  - `functional` (puerta de ruta superada) se muestra como *hito de práctica*:
    "A1 Listening — not yet demonstrated", con el requisito de demostración
    (retención retardada estable: ≥90 % de la precisión inmediata en
    re-exposiciones tras ≥7 días) y el estado de retención actual.
  - `demonstrated` (puerta + retención estable ≥7 días) muestra la pantalla
    "A1 Listening — demonstrated" con el desglose (gate y retención).
  - Nueva sección "Competencia por ruta" en el Recorrido Listening con los 4
    estados por nivel CEFR y la nota de que "Demostrado" es el único estado que
    certifica.
- **Etiquetado del estimado (H7, P2-9)**: nuevo `EstimatedLevelBadge`
  (`LevelBadge` + calificador localizado "estimado · no certificado",
  `profile.estimatedQualifier`) en los dos sitios que muestran el nivel estimado
  global (Home y cabecera de Progreso) y en ResumenTab; el perfil
  (`LearningProfile`) muestra la distribución por destreza con la nota de que las
  bandas son estimaciones alineadas con el CEFR, no certificaciones
  (`profile.bandNote`).
- **Código muerto eliminado (H7, P2-10)**: retirados `frontend/src/utils/modes.ts`
  y `modes.test.ts` (`modeCefrLevel`/`modeCefrBand` no tenían uso en componentes;
  los modos de chat viven en `TUTOR_MODES` de `hooks/useChat.ts`).

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.4.0] — 2026-09-03

**Segunda iteración de código de la Constitución pedagógica (P1).** Completa los
P1 5–7 del roadmap (§9): la matriz CEFR deja de tener huecos (C1/C2 y las 8
destrezas), la certificación de nivel incorpora la retención retardada como
requisito (completado ≠ certificado) y el Personal Dictionary evoluciona a
Lexical Units con el Vocabulary Coverage Indicator receptivo/productivo.

### Cambiado (backend)
- **Matriz CEFR completa (H4, P1-5)**: `backend/curriculum/cefr_matrix.json` 2.0.0
  cubre A1–C2 × las 8 destrezas de la Constitución §7. Las 4 macro-destrezas
  conservan su calibración A1–B2 y se extrapolan a C1/C2; vocabulary/grammar/
  interaction/mediation declaran en la matriz el mismo suelo que su fallback
  plano histórico (sin inventar escalados no calibrados) y `pronunciation` queda
  por diseño como componente de Speaking. `services/cefr_matrix.py` documenta el
  nuevo alcance y `services/adaptive.readiness` usa la matriz como fuente única
  de requisitos por destreza (retrocompatible con perfiles legacy).
- **Certificación con retención (H5, P1-6)**: nueva semántica *completado ≠
  certificado*. Aprobar el examen sigue completando el nivel y desbloqueando el
  siguiente, pero la certificación plena exige evidencia `delayed` por destreza
  del examen (solo se escribe tras el retention reassessment ≥ 7 días con ratio
  estable). Nuevo `certification_gate` en `services/assessment_v2.py`, expuesto
  como `certification` en el resultado del examen y en el listado de completados
  (`/api/academy/level-completions`). En la escalera, `readiness.level_certified`
  exige el peldaño `level` + el retention reassessment: la retención entra como
  requisito del nivel, no como evaluación aparte.
- **Lexical Units + cobertura (P1-7)**: `services/lexicon.py` amplía `kind` a la
  taxonomía `LEXICAL_KINDS` (§3.2) y tipa las semillas curriculares con
  `classify_kind` (solo patrones inequívocos; lo ambiguo queda `structure`). El
  repo refresca kinds heredados al resembrar. `/api/vocabulary/lexicon` expone el
  **Vocabulary Coverage Indicator** receptivo/productivo por nivel
  (`coverage`, §3.1, bandas de `LEXICAL_COVERAGE_TARGETS`): indicador interno,
  no puerta.

### Cambiado (frontend)
- `PersonalDictionary` etiqueta toda la taxonomía de Lexical Unit con fallback
  genérico (nunca "word" por defecto); i18n en `utils/i18n.ts` y tipos en
  `src/types/api.ts` (`Certification`, `level_certified`, `LexiconCoverage`).

### Tests
- Nuevos: `certification_gate` y `level_certified` (`test_assessment_v2.py`),
  clasificador `classify_kind` y `coverage_indicator` (`test_lexicon.py`),
  "aprobado pero certificación pendiente" y "certificado con evidencia delayed"
  (`test_academy.py`).
- Actualizados: `test_lexicon.py` a la taxonomía ampliada; el resto de la suite
  sin cambios de expectativa.

### Documentación
- `docs/CONSTITUCION-PEDAGOGICA.md` (§8 mapeo y §9 roadmap) y
  `docs/audit/H-NIVELACION-PEDAGOGICA.md`: estado de los hallazgos tras la
  ejecución de los P1 5–7 (H1–H5 cerrados; H6–H7 parciales, pendientes de P2).

## [3.3.0] — 2026-09-03

**Primera iteración de código de la Constitución pedagógica (P0).** Separa el nivel
estimado del demostrado y elimina la lectura "palabras → nivel CEFR" que la auditoría
(`docs/audit/H-NIVELACION-PEDAGOGICA.md`, H1) marcó como pedagógicamente inválida. Introduce
los 4 estados por competencia (Constitución §2.1) en el perfil y convierte la práctica de
listening en evidencia del Student Model con retención retardada (H3/H5).

### Cambiado (backend)
- **`services/cefr.py` sin interpretación palabras→nivel (H1)**: retirado el evaluador legacy
  (`VOCABULARY_BAND_EDGES`, `vocabulary_band`, `evaluate_cefr`, `estimate_cefr`) y sus tests.
  Queda como módulo de constantes compartidas, descriptores, `heuristic_band` (score de
  destreza del Student Model) y recomendaciones; el volumen léxico es un indicador de cobertura
  (`VOCAB_EXPANSION_HINT_WORDS`), nunca una banda CEFR.
- **Registro por competencia Estimado/Demostrado (H2/H7)**: nuevo `services/competence.py` con
  los 4 estados (`not_started`/`developing`/`functional`/`demonstrated`), gate y retención;
  `/api/profile` lo expone como `competence_states`. Una destreza sin evidencia se muestra "—",
  nunca "A1" por defecto.
- **Fuente única de mastery (H6)**: retirado el endpoint `/api/academy/mastery` y su cadena
  domain/schema/repo; la fuente expuesta es `student-model.mastery`.
- **Listening al Student Model (H3/H5)**: nuevo `route_competence` en `services/listening.py`
  que lee `listening_attempts` como estado por ruta (los 4 estados): `route_gate` superado →
  FUNCTIONAL, y retención retardada estable (re-exposiciones ≥ 7 días con ratio ≥ 0.9) →
  DEMONSTRATED. El Student Model expone las rutas de la destreza listening y
  `/api/listening/stats` su estado y retención por ruta.

### Tests
- Nuevos: `backend/tests/test_competence.py` (estados por competencia y combinación
  evidencia formal + ruta de práctica).
- Eliminados: `backend/tests/test_cefr_evaluation.py` (fijaba el evaluador legacy retirado).
- Actualizados: `test_profile.py`, `test_academy.py`, `test_listening.py`, `test_policy.py`.

### Documentación
- `docs/CONSTITUCION-PEDAGOGICA.md` (§8 mapeo y §9 roadmap) y
  `docs/audit/H-NIVELACION-PEDAGOGICA.md`: estado de los hallazgos tras la ejecución de los P0
  (H1–H3 cerrados; H5–H7 parciales; H4 abierto) con la foto V3.2.1 conservada como referencia.

## [3.2.1] — 2026-09-03

**Auditoría pedagógica del modelo de nivelación (solo documentación).** Sin cambios de código.
Corrige el concepto antes de seguir con la UI: se audita cómo decide la app el nivel de un alumno
(`docs/audit/H-NIVELACION-PEDAGOGICA.md`) y se publica la especificación normativa
**`docs/CONSTITUCION-PEDAGOGICA.md`** que separa *Practice Level / Mastery / Estimated CEFR /
Demonstrated CEFR* y prohíbe leer "cantidad de palabras → nivel CEFR".

### Añadido (documentación)
- **Dossier `docs/audit/H-NIVELACION-PEDAGOGICA.md`** (desk, plantilla TEMPLATE): inventario de las
  dos fuentes de nivel (heurístico legacy `services/cefr.py` vs Student Model), hallazgos H1–H7 y
  veredicto: el modelo es honesto en la superficie pero no responde "qué ha demostrado el alumno".
- **`docs/CONSTITUCION-PEDAGOGICA.md`**: principios, 4 conceptos + 4 estados por competencia
  (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), cobertura léxica receptiva/productiva
  como indicador (no puerta), taxonomía de **Lexical Units**, progresión de listening por fases y
  **Mastery Gate** general (coverage + accuracy + subskills + retención ≥ 7 días + checkpoint) con
  mapeo de los bloques que ya existen (`route_gate`, evidence kinds, `mastery_evidence_gate`,
  `cefr_matrix.json`).
- **Roadmap de implementación derivado** (P0/P1/P2, sección 9 de la constitución): eliminar la
  interpretación palabras→nivel, estados Estimado/Demostrado por competencia, listening conectado
  al Student Model, matriz CEFR a C1/C2 y 8 destrezas, retención en la certificación, Lexical
  Units, y UI "Entrenamiento A1" vs "A1 — demonstrated".

## [3.2.0] — 2026-09-03

**Calibración pedagógica de niveles.** Nadie "alcanza A1" con 30 audios o 30
palabras: se recalibra el nivel estimado global, los donuts de Listening pasan a
ser rutas de práctica con puerta de evidencia y el corpus A1/A2 se expande a
cientos de ítems por nivel con un pipeline reproducible (ver `PLAN.md`).

### Cambiado
- **Nivel estimado global honesto (Fase 1)**: tramo `Pre-A1` (sin evidencia suficiente
  ya no es "A1") y recalibración logarítmica de los umbrales de vocabulario
  (`services/cefr.py` 2.1.0: A1 ≈ 150–399 palabras). Soportado en frontend
  (`cefrLabel`/`cefrTone`/badges) y en el tutor (`policy`, escalera de la Academy).
- **Listening como rutas de práctica (Fase 2)**: la UI relee los donuts como
  "Ruta A1…" con nota de qué significa un nivel CEFR real; `level_status` informa
  `{mastered, total, gate}` y la **puerta de ruta** exige cobertura ≥ 80 %,
  precisión ≥ 70 %, variedad de temas/sub-destrezas y un checkpoint de aciertos a
  la primera sin replays (`services/listening.py`, `ROUTE_*`).

### Añadido
- **Pipeline de expansión del corpus (Fase 3)**: `scripts/generate_listening_corpus.py`
  reproducible, idempotente y validado (frames autorados en
  `scripts/_corpus_frames_a1a2.py`). Tranche A1/A2 aplicado: corpus de **140 → 490
  ítems** (A1 200, A2 200; B1→C2 pendientes de siguiente tranche), respetando las
  bandas auditadas y `validate_listening_bank`.
- **Cierre del sesgo posicional (auditoría B, mc-bias)**: rotación determinista de
  opciones por id (`crc32 % n`); la posición de la respuesta queda ~uniforme
  (123/122/122/123 en 490) en vez de 90,7 % en la opción 0.
- **Objetivos de contenido** `LISTENING_CORPUS_TARGETS` en `services/curriculum.py`
  (A1 200, A2 200, B1 180, B2 160, C1 120, C2 100) y bump `LISTENING_BANK_VERSION`
  a 7.0.0 (audio TTS cacheados por versión de banco).

## [3.1.0] — 2026-09-02

**UI V3.1 — Reorganización en 3 mundos.** Rediseño de la interfaz y la navegación
(ver `docs/UI_V3.1.md`). Sin cambios en el stack pedagógico (sigue congelado en 3.0.0).

### Añadido / Cambiado
- Navegación raíz reducida a 3 mundos (INICIO · FORMACIÓN · APRENDER) con URLs reales mediante hash-router propio, deep links y botón atrás.
- INICIO: dashboard de acción con objetivo de hoy, recomendación, repaso FSRS y acceso a MI PROGRESO.
- FORMACIÓN: escalera CEFR A1–C2, listado de unidades con gating, hero "Continuar curso" y bloque de evaluaciones.
- APRENDER: hub de 6 tarjetas (Listening, Speaking, Pronunciación, Conversar, Vocabulario, Gramática) con sub-rutas propias y pantalla de Speaking libre.
- MI PROGRESO: pantalla consolidada por pestañas (Resumen · Curso · Habilidades · Trayectoria · Recorridos); el antiguo panel Analysis queda como contexto ligero.
- Workspace único con barra de contexto lección vs. práctica libre.
- AYUDA real en la ruta de ayuda (enlaza a la documentación) y "Conectar dispositivo" movido a Ajustes → Sistema.
- Limpieza de claves i18n huérfanas y navegación EN/ES coherente.

## [3.0.0] — 2026-09-02

**Beta V3.0 — feature freeze pedagógico.** Cierra el ciclo V2.7–V2.12 y congela
funcionalidad nueva. La fase abierta es contenido + calibración + UX + pruebas
reales (ver `docs/BETA_V3.md`).

### Añadido (stack pedagógico V2.7–V2.12, consolidado en 3.0.0)
- **Curriculum Depth (V2.7)**: Unit Architecture + profundidad A1–C2 (depth media ≥ 80,
  loop 100%).
- **Listening Curriculum (V2.8)**: foco CEFR por nivel + alineación 100%.
- **Speaking Mission (V2.9)**: Mission → Attempt → Drill → Retry → Improvement.
- **Assessment 2.0 (V2.10)**: formative → unit → progress → level → retention + mastery gate.
- **FSRS-lite (V2.11)**: cola due auditable (What/Why/When/How strong/Last/Next).
- **Evidence Graph (V2.12)**: can-do → limiting factor → `because[]` en next-best.
- **Gate Beta V3**: `scripts/check_beta_v3.py` (módulos, rutas, docs, umbrales de calidad).

### Congelado
- No se abren features de producto nuevas hasta completar la checklist de
  `docs/BETA_V3.md` (§4 contenido/calibración/UX/dispositivos).

### Verificado
- Backend pytest + ruff; frontend `tsc`; Curriculum Quality Overall **95,7**;
  loop **100%**; listening alignment **100%**.
- `python scripts/check_beta_v3.py` + `check_release_consistency.py` OK (3.0.0).

## [2.5.0] — 2026-09-01

**Release de consolidación para auditoría externa.** Eleva a versión estable el trabajo
acumulado tras `2.4.0`: finalización del currículo (V2.5), capa de medición de calidad del
currículo (V2.6) y auditoría visual de UI (2.1).

### Añadido
- **Currículo A1→C2 completado (V2.5)**: listening C1/C2 (corpus 100 → 140 ítems), speaking C2
  (26 escenarios), subskills de interacción en A1/A2/B2/C1/C2 y wiring curso↔bancos
  (`Objective.listening_items`/`scenario_ids`). Cobertura total 42/49 celdas (85,7%).
- **Curriculum Quality Dashboard (V2.6)**: métricas de grano fino `unit_coverage`,
  `depth_score`, `unit_learning_loop`/`loop_coverage` y `curriculum_quality_report` con delta
  antes/después.
- **Unit Learning Loop etiquetado (V2.6-C5)**: las 31 unidades etiquetan las fases de cierre
  (`retrieve`/`transfer`/`review`/`assess`); loop por unidad 50,6% → 84,7%.
- **UI 2.1**: banner de lección activa estilizado, "Modelo IA" i18n, estados vacíos con icono.

### Corregido
- **Navegación responsive**: la barra inferior (móvil) y la del header (tablet) desbordaban con
  7 pestañas y tapaban otros controles; ahora desplazan horizontalmente sin desbordar.
- **Sistema de diseño unificado**: eliminado CSS duplicado y muerto legacy y unificados radios,
  espaciado y ancho de lectura entre `index.css` y `legacy.css` (una sola fuente de verdad).

### Verificado
- Backend `pytest` + `ruff` limpios (fases V2.5/V2.6 ya verificadas; 1005 passed).
- Frontend `vitest` (245 tests) y `tsc && vite build` OK.
- Visual (Playwright sobre Chrome del sistema): 14 passed / 10 skipped / 0 failed en
  desktop/tablet/móvil.
- `python scripts/check_release_consistency.py` OK (2.5.0).

## [2.4.0] — 2026-08-31

**Auditoría de cobertura curricular**: responde con datos a "¿el alumno puede recorrer
completo A1→C2?". Recorre el curso completo (Pre-A1 → C2) por las 7 secciones canónicas
(vocabulary/grammar/listening/speaking/interaction/review/assessment), cruza el contenido del
curso con los bancos de destrezas (listening corpus + speaking scenarios) y genera
`curriculum_coverage_report.json`. No añade contenido ni funcionalidad de alumno; es la
instrumentación que permitirá localizar y completar los huecos reales.

### Añadido
- **Servicio puro `services/curriculum_coverage.py`**: `coverage_sections` (conteo por sección a
  nivel de curso), `bank_intersection` (cruce del banco de listening por `level` y de los
  escenarios de speaking por `cefr_target` contra cada nivel), tri-estado
  `complete`/`partial`/`empty` por sección, `level_coverage` y `curriculum_coverage_report`.
- **Métrica "TOTAL CURRICULUM COVERAGE"** (`coverage_metric`): ratio de celdas pobladas sobre la
  matriz completa 7 niveles × 7 secciones (49 celdas), con desglose `by_level`/`by_section`.
  Distinta y complementaria de "TOTAL VALIDATED LEARNING ITEMS" (contenido validado vs. cobertura).
- **Integración en `content_stats()`** (`services/content_validation.py`): `total_curriculum_coverage`
  convive junto a `total_validated_learning_items` como fuente única (anti-drift).
- **CLI `scripts/curriculum_coverage.py`**: emite el JSON completo + resumen legible por nivel y
  sale con código 1 (`--strict`) si hay algún hueco `empty` en una sección con curso (guard de CI).
- **Mapa de cobertura en `docs/CURRICULUM_COVERAGE.md`**: tabla Pre-A1→C2 × 7 secciones con estado
  y la lista priorizada de huecos detectados.

### Verificado
- Backend `pytest` (971 passed) + `ruff` limpio; tests de invariantes `test_curriculum_coverage.py`
  (7 niveles × 7 secciones, Pre-A1 como banda sin curso, cruce con bancos, determinismo y
  coexistencia de las dos métricas).
- `python -m scripts.curriculum_coverage` OK (37/49 celdas, 75.5% de cobertura).

### V2.5-C1 — listening C1/C2 (sin bump de versión, sigue 2.4.0)
- **Corpus de listening 100 → 140** (`curriculum/listening_corpus.json` v1.1.0): 20 ítems C1
  (`c101`–`c120`) y 20 C2 (`c121`–`c140`) con registro y temática avanzados (inferencia, intención
  del hablante, actitud, ironía, hablantes múltiples, connected speech, habla rápida).
- **`LEVEL_ORDER` ampliado** a A1..C2 (`services/listening.py`); `LISTENING_BANK_VERSION` 5.0.0 →
  6.0.0; `QUALITY_THRESHOLDS["min_items_per_level"]` añade C1/C2 (20 cada uno).
- **TOTAL VALIDATED LEARNING ITEMS 143 → 183** (163 listening: 140 corpus + 23 legacy TTS; 20 speaking).

#### Verificado
- `python -m scripts.content_validation` OK (183 ítems validados; 14/14 checks PASS).
- `python -m scripts.curriculum_coverage` OK (`bank_count` listening C1/C2 > 0).
- Backend `pytest` (972 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C2 — speaking C2 (sin bump de versión, sigue 2.4.0)
- **Escenarios de speaking 20 → 26** (`curriculum/speaking_scenarios.json` v1.0.0 → v2.0.0): 6
  escenarios C2 (`persuasion`, `conflict_mediation`, `academic_defence`, `abstract_conversation`,
  `stakes_negotiation`, `diplomatic_talk`) con objetivo comunicativo de nivel C2 (persuasión sutil,
  mediación de conflicto, defensa con evidencia, temas abstractos, negociación delicada y tacto
  diplomático).
- **`SPEAKING_SCENARIOS_VERSION` 2.0.0 → 3.0.0** (`services/curriculum.py`), alineando la discrepancia
  JSON↔constante (el JSON quedó en 1.0.0 y la constante en 2.0.0; sube uno cada uno).
- **TOTAL VALIDATED LEARNING ITEMS 183 → 189** (163 listening: 140 corpus + 23 legacy TTS; 26 speaking).

#### Verificado
- `python -m scripts.curriculum_coverage` OK (`bank_count` speaking C2 > 0).
- Backend `pytest` (973 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C3 — interaction A1/A2/B2/C1/C2 (sin bump de versión, sigue 2.4.0)
- **Subskills de interacción en 5 niveles** (`curriculum/a1.json`, `a2.json`, `b2.json`, `c1.json`,
  `c2.json`): 39 objetivos que declaran `speaking` con actividad `dialogue` añaden
  `subskills: ["interaction", "turn_taking"]`. La sección `interaction` deja de estar `empty` en
  A1/A2/B2/C1/C2 (queda poblada en 6/7 niveles; solo Pre-A1, banda sin curso, sigue vacía).
- **Cobertura TOTAL CURRICULUM COVERAGE 37/49 → 42/49 (75,5% → 85,7%)**.
- **Test invariante nuevo** (`test_curriculum_coverage.py`): `interaction` con `count > 0` en
  A1/A2/B2/C1/C2.

#### Verificado
- `python -m scripts.curriculum_coverage` OK (interaction 6/7; 42/49 celdas).
- Backend `pytest` (974 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C4 — wiring curso↔bancos (sin bump de versión, sigue 2.4.0)
- **Modelo `Objective`** (`services/curriculum.py`): dos campos retrocompatibles
  `listening_items: list[str]` y `scenario_ids: list[str]` (default `[]`) que referencian por ID
  los ítems del banco de listening y los escenarios de speaking.
- **Conteo** (`services/course.py::unit_sections`): `listening`/`speaking` suman
  `len(listening_items)`/`len(scenario_ids)`, de modo que la sección refleja las referencias
  reales al banco y no solo el `skill` declarado.
- **Wiring de contenido** en los 6 niveles (`curriculum/a1.json`–`c2.json`): cada objetivo con
  `listening` referencia 4 ítems del banco de su nivel (`c001`–`c140` + legacy `l1`–`l23`); cada
  objetivo con `speaking` referencia 1 escenario de su `cefr_target` (26 escenarios). Total
  cableado: 18 objetivos de listening y 50 de speaking.
- **Validación** (`services/curriculum.py::validate_level`): comprueba que cada ID referenciado
  existe y que su `level`/`cefr_target` coincide con el nivel del curso (imports diferidos
  anti-ciclo).

#### Verificado
- `python -m scripts.curriculum_coverage --strict` OK (exit 0; listening/speaking cableados por
  unidad, `count` crecido y sin huecos `empty`).
- Backend `pytest` (981 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.6-C1 — capa de medición: Unit Coverage + CEFR Depth + Unit Learning Loop + Dashboard (sin bump, sigue 2.4.0)
- **Hallazgo conceptual**: "cobertura" ≠ "profundidad". `42/49 celdas` no es "curso al 85,7%": una
  celda cuenta como poblada si *alguna* unidad tiene contenido en esa sección. Se añaden métricas de
  grano fino en `services/curriculum_coverage.py`:
  - `unit_coverage(level)` — **UNIT COVERAGE**: por unidad, las 7 secciones pobladas (`coverage_pct`,
    `missing`, `by_section`). Media A1..C2 = **61,7%**.
  - `depth_score(level)` — **CEFR DEPTH SCORE** (0..100): 4 componentes ponderados y auditables
    (`objective_density` 0.20 · `objective_volume` 0.35 · `section_coverage` 0.35 ·
    `subskill_breadth` 0.10). Media **55,7**; A1 74,2 · A2 52,3 · B1 55,7 · B2 61,7 · C1 48,0 ·
    C2 42,5. Ajuste C1b: volumen pesa más que densidad (la densidad sola premiaba a B2 por ser denso
    con solo 9 objetivos).
  - `unit_learning_loop(level, unit)` + `loop_coverage(level)` — **UNIT LEARNING LOOP** (9 fases).
    Media **50,6%**; introduce/practice 100%, listen 45,2%, speak 90,3%, interact 83,9%,
    retrieve/transfer 0%, assess/review 19,4% (solo módulos "Final").
  - `unit_detail(level_id, unit_id)`: drill-down LEVEL → UNIT → LESSON → OBJECTIVE.
  - `curriculum_quality_report()` — **Curriculum Quality Dashboard**: 7 dimensiones + `overall` +
    `by_level` + bloque `learning_loop`. Overall **56,8**; review/assessment 23,5 · listening 47,8 ·
    depth 55,7 · coverage 85,7.
  - `quality_report_delta(before, after)`: delta antes/después por dimensión y nivel.
- **CLI** (`scripts/curriculum_coverage.py`): dashboard + loop legibles + `--quality` (JSON completo).
- **Dato corregido**: objetivos reales por nivel A1 23 → A2 11 → B1 10 → B2 9 → C1 7 → C2 5; la caída
  es más abrupta de lo que sugería la auditoría previa (A2 y B1/B2 también son finos, no solo C1/C2).

#### Verificado
- Backend `pytest` (999 passed) + `ruff` limpio; tests `test_curriculum_quality.py` (18 invariantes).
- `python -m scripts.curriculum_coverage` OK (dashboard + loop) y `--strict` exit 0.
- `python -m scripts.content_validation` OK; `check_release_consistency` OK (2.4.0).

### V2.6-C2 — marcador de fase del Unit Learning Loop (`Activity.phase` + validación) (sin bump, sigue 2.4.0)
- **Modelo** (`services/curriculum.py`): `LEARNING_PHASES` (9 fases canónicas del loop) como fuente de
  verdad y `Activity.phase: str = ""` (default vacío = `practice`, retrocompatible). `validate_level()`
  rechaza `phase` no canónico.
- **Medición** (`services/curriculum_coverage.py`): re-exporta `LEARNING_LOOP_PHASES` desde
  `LEARNING_PHASES` (anti-drift) y `unit_learning_loop()` lee `retrieve`/`transfer`/`review`/`assess`
  desde el `phase` de las actividades. El hueco deja de ser un 0 hardcodeado: ahora es contenido
  etiquetable (hoy sigue 0/19,4% porque ningún JSON usa aún el marcador).
- **Briefing de contenido** `agentes/curriculum/c5-loop-phases.md`: etiquetar fases de cierre por
  unidad (piloto A1 → escalar), subir el loop de 50,6% → ≥ 77%.

#### Verificado
- Backend `pytest` (1005 passed) + `ruff` limpio; `validate_level` vacío para los 6 niveles.
- `python -m scripts.curriculum_coverage --strict` exit 0; `check_release_consistency` OK (2.4.0).

### V2.6-C5 — etiquetado de fases del Unit Learning Loop en el contenido (sin bump, sigue 2.4.0)
- **Contenido** (`backend/curriculum/*.json`): las 25 unidades normales (no módulo "Final") etiquetan
  las 4 fases de cierre del loop con el marcador `phase`:
  - `retrieve` (recuperación espaciada desde memoria) y `transfer` (can-do aplicado a un contexto nuevo
    no ensayado): 25/31 unidades cada una (80,6%).
  - `review` (micro-repaso del can-do en 1 frase) y `assess` (auto-evaluación abierta de cierre):
    31/31 unidades (100%), ya no solo en los módulos "Final".
- **Loop por unidad**: media **50,6% → 84,7%** (objetivo ≥ 77%). introduce/practice 100%, listen 45,2%,
  speak 90,3%, interact 83,9%, retrieve/transfer 80,6%, assess/review 100%.
- **Invariantes de snapshot** (`tests/test_curriculum_quality.py`): los dos tests frágiles que codificaban
  el hueco se actualizan: `test_loop_retrieve_and_transfer_are_still_ungapped` →
  `test_loop_retrieve_and_transfer_are_tagged` (covered_units > 0) y
  `test_loop_assess_and_review_only_in_final_module` → `test_loop_assess_and_review_cover_every_unit`
  (covered_units == total_units).

#### Verificado
- `python -m scripts.curriculum_coverage --strict` exit 0; `validate_level` vacío para los 6 niveles.
- Backend `pytest` (1005 passed) + `ruff` limpio.

## [2.3.0] — 2026-08-31

**Personal Dictionary + evidencia por ítem léxico**: se baja el modelo de evidencia de
"destreza" a "palabra/estructura". Cada entrada de `vocabulary` se convierte en un ítem léxico
de primer nivel sembrado desde el currículo, con estado y `recall` por ítem, expuesto en una
pantalla **Personal Dictionary**.

### Añadido
- **Ítem léxico con contexto curricular** (migración idempotente en `repositories/db.py`): columnas
  `cefr`/`level_id`/`objective_id`/`source`/`lemma`/`kind` en `vocabulary` (solo contexto; no tocan
  `appearances`/`exposures`).
- **Siembra desde el currículo** (`repositories/vocabulary.seed_curriculum_items` +
  `services/lexicon.items_from_objective`): `objective.vocabulary` + `objective.concepts`
  (estructuras como "I am") pueblan el diccionario al avanzar, cableado en
  `submit_objective_assessment` y `record_lesson_completed`.
- **Servicio puro `services/lexicon.py`**: `item_mastery`, `item_recall` (reutiliza la curva de
  olvido de `forgetting`), `item_status` (`mastered`/`known`/`learning`/`weak`), `next_review_days`
  (reutiliza el scheduler de `mastery`), `cefr_distribution`, `summary` y `recognized_not_produced`
  (señal de *speaking micro-drill*).
- **Endpoint `GET /api/vocabulary/lexicon`** → `LexiconOut { summary, items }` con estado, `recall`
  y `next_review_days` por ítem.
- **Pantalla Personal Dictionary** (`features/vocabulary/PersonalDictionary.tsx`): totales
  Known/Learning/Weak/Mastered, barra "Vocabulary by CEFR" (A1→C2), lista de ítems con `recall %` y
  "next review", y sección "Recognized but not produced". Ruta y entrada en la navegación + i18n ES/EN.

### Verificado
- Backend `pytest` (962 passed) + `ruff` limpio; tests de invariantes `test_lexicon.py` (seed sin
  incrementar producción, estado determinista, recall monótono, distribución CEFR, señal micro-drill).
- Frontend `tsc` + `vitest` (245 passed) + `build` en verde.

## [2.2.0] — 2026-08-31

**Academy / Course Engine (profundizar lo existente)**: el foco pasa de "tener contenido"
a "construir un curso completo y medible". Sin reescribir el Course Engine (V1.38),
Mastery 2.0 (V1.39) ni Adaptive 2.0 (V1.31): se les añade estructura y medición pedagógica.

### Añadido
- **Métrica única "TOTAL VALIDATED LEARNING ITEMS"** (`services/content_validation.py`:
  `content_stats()`): cifra canónica derivada de las dos fuentes (banco de listening +
  escenarios de speaking) = **143** (123 listening: 100 corpus + 23 legacy TTS; 20 speaking).
  `run_content_validation()` la reporta y README/CHANGELOG/UI derivan de ella (anti-drift,
  con test que falla si validador y métrica no coinciden).
- **Plantilla fija de unidad (7 secciones)** (`services/course.py`: `UNIT_SECTIONS` +
  `unit_sections`): cada unidad expone vocabulary/grammar/listening/speaking/interaction/
  review/assessment con conteo y huecos visibles (`needs_content`) que alimentan el Quality
  Gate en V2.3.
- **Learning Objectives de unidad** (`unit_objectives`): "By the end of this unit you will
  be able to…" agregando los `can_do` de los objetivos, renderizado en `CourseScreen`.
- **Contrato CEFR conectado al dominio** (`cefr-ladder`): cada dimensión "WHAT CAN I DO?"
  emite su estado real ✓/●/○ (`mastered`/`in_progress`/`not_started`) desde el Student Model
  (`adaptive.dimension_state`), sustituyendo el `Check` estático en `CourseScreen`.
- **Mastery Gates por unidad** (`services/course.py`: `unit_gates`): umbrales compuestos por
  sección (vocabulary/grammar ≥ 0.80, listening ≥ 0.75, speaking ≥ 0.70) + retención PASS +
  transferencia PASS. Una unidad solo se marca `mastered` con el gate compuesto; la UI
  muestra "qué falta para UNIT MASTERED" (`CourseUnit.sections/gates/gate_mastered`).
- **Tríada Progress / Mastery / Readiness** (`adaptive.student_dashboard` + endpoint
  `GET /api/academy/dashboard`): tres métricas explícitas y consistentes, reutilizadas por
  Home/Progress/Course (`TriadCard`).
- **Pantalla Learning Journey** (`features/journey/JourneyScreen.tsx`): escalera Pre-A1→C2
  con marcador "YOU", `units mastered`, `skills ready`, `retention %` y `next milestone`,
  enrutada desde la navegación principal.
- **Tests de regresión pedagógica** (`backend/tests/test_pedagogy.py`): invariantes de la
  métrica única, plantilla de 7 secciones, objetivos de unidad, Mastery Gates (sección
  bloqueante → no `mastered`), recomendación por sub-destreza débil (connected speech),
  contrato CEFR y tríada; `test_course.py` ampliado para secciones/objetivos/gates.

### Verificado
- `python -m scripts.content_validation` OK (143 ítems de aprendizaje validados; 12/12 checks PASS).
- Backend `pytest` (948 passed) + `ruff` limpio; `check_release_consistency` OK.
- Frontend `tsc` + `vitest` (240 passed) + `build` en verde.

## [2.1.0] — 2026-08-31

**Contenido y calidad pedagógica**: primera iteración centrada en volumen y diversidad
de contenido (recomendación inmediata de la auditoría externa), no en arquitectura.

### Añadido
- **Content Quality Gate** (`services/content_validation.py`): umbrales de calidad del banco
  de listening (mínimo de ítems por nivel CEFR, hablantes, acentos, contextos, connected
  speech, ruido, multihablante y habla rápida) con reporte `quality_pass`/`quality_warnings`.
  `scripts/content_validation.py` falla (exit 1) si no se cumplen los umbrales (guard de CI).
- **Corpus de listening 40 → 100** (`curriculum/listening_corpus.json`, c041–c100): 60 ítems
  TTS nuevos con perfil diversificado por nivel (A1 habla clara, A2 conversación natural,
  B1 connected speech/multihablante, B2 habla rápida/acentos/inferencia) y 15 destrezas.
  `LISTENING_BANK_VERSION` 4.0.0 → 5.0.0.
- **Escenarios de speaking 8 → 20** (`curriculum/speaking_scenarios.json`): banco, aeropuerto,
  vivienda, queja, negociación, presentación de equipo, small talk avanzado, soporte técnico,
  debate, narración, etc., cubriendo A1→C1. `SPEAKING_SCENARIOS_VERSION` 1.0.0 → 2.0.0.
- **Niveles de curso C1 y C2** (`curriculum/c1.json`, `curriculum/c2.json`): curso secuencial
  C1 (gramática avanzada, idioms, discurso académico) y C2 (retórica, registro, matiz cultural).
  `CURRICULUM_VERSION` 1.2.5 → 1.3.0.
- **Assessments finales por nivel**: módulos de repaso final añadidos a A2, B1 y B2 (A1 ya los
  tenía), cerrando cada nivel con una evaluación de cierre.

### Verificado
- `python -m scripts.content_validation` OK (integridad + umbrales de calidad; 123 ítems, 12/12 checks PASS).
- Backend `pytest` (936 passed) + `ruff` limpio; `check_release_consistency` OK.
- Frontend `tsc` + `vitest` (240 passed) + `build` + `playwright` (14 passed, 10 skipped) en verde.

## [2.0.0] — 2026-08-31

**Beta 1.0**: cierre del roadmap V1.36 → Beta. Los 5 gates de salida alcanzan 10/10
(Infra / Curriculum / Listening+Speaking / Adaptive+Mastery / UX+Reliability); ver
`docs/BETA_GATES.md`.

### Cambiado
- **Versión mayor** `1.41.0` → `2.0.0` para marcar el producto completo (feature-complete)
  y la entrada en Beta.

### Corregido
- **Seguridad (path traversal)** en `GET /api/system/backup/export`: `read_backup` ahora
  exige un `name` que sea basename `.zip` y lo resuelve confinado a `backups_dir()` (anti
  CWE-22). Hallazgo de la pre-auditoría interna.
- **Restore como reemplazo real** (`services/backup.py`): `restore_backup` ahora elimina los
  archivos que no están en el backup (en `data/` y `audio_library/`, conservando `backups/`
  y `_backups/`), alineando el comportamiento con el docstring "reemplaza el estado actual".

### Verificado
- Gates de salida 10/10 en `docs/BETA_GATES.md`.
- Backend `pytest` (929 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) +
  `build` OK; `check_release_consistency` OK; CI con `content-validation` y `playwright`.

## [1.41.0] — 2026-08-31

**Beta Hardening**: sin features nuevas, solo fiabilidad y seguridad para cerrar el producto.
Backup/restore/export local, seguridad LAN, a11y y performance.

### Añadido
- **Backup / restore / export local** (`services/backup.py` + `routers/system.py`): copias de
  seguridad ZIP deterministas del estado local (SQLite `tutor.db` — perfiles, progreso, vocabulario,
  evidencia, settings, mastery — + biblioteca de audio `manifest.json` + WAV). Endpoints admin:
  `GET /api/system/backup/status`, `POST /api/system/backup`, `GET /api/system/backups`,
  `GET /api/system/backup/export` y `POST /api/system/restore`.
- **Auto-backup diario** (keep 7): hilo `_auto_backup_daemon` en el lifespan de FastAPI que crea una
  copia si no existe ninguna del día UTC, y poda a `KEEP_BACKUPS = 7`.
- **Seguridad LAN** (`security.py::SecurityMiddleware`): middleware ASGI con (a) origin-check para
  métodos no seguros (protección tipo CSRF para la app accesible por LAN) y (b) rate limiting en
  memoria por IP cliente con límites más estrictos para endpoints sensibles.
- **Panel de backup en la UI** (`components/BackupPanel.tsx` + `api/system.ts`): en Ajustes →
  Sistema, permite crear copia, listar, descargar y restaurar desde un ZIP, reutilizando el PIN de
  administración.
- **A11y**: skip-link al contenido principal (`AppShell`) y sincronización de
  `document.documentElement.lang` con el idioma de la interfaz.

### Cambiado
- **Matriz de dispositivos** (`docs/DEVICE_MATRIX.md`): ampliada a PC/Android/iPhone/iPad con
  columnas explícitas HTTPS, mDNS, Mic, Audio, Listening, Speaking y Recuperación de permisos.
- **Performance**: `manualChunks` en `vite.config.ts` separa React, `motion` y `lucide-react` en
  chunks propios (el bundle principal baja de ~505 kB a ~393 kB, gzip de ~160 kB a ~124 kB).

### Verificado
- Backend `pytest` (926 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.

## [1.40.0] — 2026-08-31

**Speaking 3.0**: escenarios comunicativos reales con objetivo comunicativo y métricas declaradas,
más honestidad del proxy de pronunciación en la UI.

### Añadido
- **Catálogo de escenarios comunicativos** (`backend/curriculum/speaking_scenarios.json` + nuevo
  `services/speaking_scenarios.py`): 8 escenarios (Restaurant, Doctor, Travel, Telephone,
  Work meeting, Small talk, Problem solving, Interview) versionados como contenido fuera del código.
  Cada escenario declara un `communicative_objective` (qué debe conseguir el alumno) y las métricas
  que observa (`task_completion`, `interaction`, `fluency`, `repair`, `turn_taking`), mapeadas a los
  criterios del rubric ya existentes (`services/speaking` + `services/interaction`).
- **Endpoint** `GET /api/academy/speaking/scenarios` (schemas `SpeakingScenarioOut`/
  `SpeakingScenariosOut`) que expone el catálogo estático.
- **UI de escenarios** (`frontend/features/speaking/SpeakingScenarios.tsx`): pestaña "Speaking
  scenarios" en el panel de análisis; cada tarjeta muestra título, nivel, categoría, objetivo
  comunicativo y las métricas; al practicar reutiliza `SpeakingRolePlay`, que registra la telemetría
  de turnos (`duration_ms`/`latency_ms`) para la señal objetiva de interacción.

### Cambiado
- **Honestidad del proxy de pronunciación** (`SpeakingDiagnostic.tsx`): el criterio `pronunciation`
  (marcado `proxy` desde V1.34) ahora muestra "Confidence: alta/media/baja · automated proxy" y una
  nota que distingue fonética real de la alineación speech/transcript (proxy), en lugar de un simple
  badge.

### Verificado
- Backend `pytest` (912 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.

## [1.39.0] — 2026-08-31

**Mastery 2.0**: el dominio se abstrae como evidencia + preparación (readiness), no como una media
simple. `MasteryRecord` transversal para las 9 destrezas y CEFR readiness con banda cualitativa.

### Añadido
- **`MasteryRecord` transversal** (`services/mastery.py`): una sola abstracción de dominio para las 9
  destrezas (vocabulary/grammar/pronunciation/listening/speaking/reading/writing/interaction/
  mediation), de modo que el Adaptive Engine observa un conjunto homogéneo. Cada registro porta
  `score`, `confidence`, `evidence_count`, `retention`, `stability`, `review_due`, `review_in_days`,
  `transfer_count`, `novel_count` y la etapa del timeline
  acquire→practice→retrieve→transfer→novel→retention.
- **Curva de olvido conectada a todo el currículo** (`review_interval_days` + `mastery_stage`):
  cada destreza obtiene un "review in N days" determinista derivado de la estabilidad de
  `services.forgetting`, y `mastery_records()` devuelve siempre las 9 destrezas.
- **CEFR readiness sin media simple** (`services/adaptive.py::readiness_band`): combina mastery +
  evidencia + transfer + retención + confianza + gates mínimos y emite una banda cualitativa
  (`developing`/`approaching`/`ready`) en lugar de un "%" crudo. `adaptive.readiness` ahora incluye
  `band`.
- **Exposición en el Student Model** (`StudentModelOut.mastery` + `MasteryRecordOut`): el endpoint
  `/api/academy/student-model` devuelve la vista transversal y la banda de readiness; `/api/profile`
  hereda la banda por `ReadinessOut`.

### Cambiado
- UI de progreso (`ProgressScreen`, `HomeScreen`, `TodayPlan`, `LearningProfile`, `CourseScreen`):
  la preparación se muestra como "B1 developing" (banda) con el % como dato secundario; el detalle de
  destreza muestra "Repasar en N días" desde el `MasteryRecord`.

### Verificado
- Backend `pytest` (906 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) OK.

## [1.38.0] — 2026-08-31

**Course Engine**: el mapa CEFR se convierte en un curso secuencial (Course→Unit→Lesson→Practice→
Assessment→Review→Mastery) con gating de progreso por objetivo y una posición visible "¿dónde estoy?"
en pantalla.

### Añadido
- **Course Engine** (`services/course.py`): secuenciación explícita de módulos/unidades/lecciones a
  partir de `curriculum/a1.json` (y a2/b1/b2), con orden de lección y gate de progreso por objetivo
  (`gate_objective_ids`, `objective_gated_status` → `mastered`/`review`/`available`/`locked`).
- **Posición en el curso** (`unit_sequence` + `current_position` + `course_map`): calcula la unidad
  y lección actuales, el progreso `mastered/total` y el estado (`done`/`current`/`locked`) de cada
  unidad.
- **Endpoint** `GET /api/academy/course/{level_id}` → `CourseMapOut` (protegido por el bloqueo de
  inscripción), expone unidades, lecciones, posición actual y progreso.
- **Progreso visible en frontend** (`CourseScreen.tsx`): barra de unidades (✓/●/🔒) y lección actual
  "¿dónde estoy?" con el porcentaje de avance del nivel.

### Cambiado
- `domain/academy.py::_objective_state` consume el estado gated calculado por `course_svc` (fuente
  única de gating) en lugar de determinarlo internamente; el segundo objetivo de un nivel aparece
  `locked` hasta dominar el anterior.

### Verificado
- Backend `pytest` (900 tests, incl. `test_course.py`) + `ruff` limpio; frontend `tsc` + `vitest`
  (240 tests) OK.

## [1.37.0] — 2026-08-31

**Audio QA + Content Audit**: la subida de audio se convierte en un estudio de QA acústica y la
integridad del contenido se audita de extremo a extremo, con separación admin/estudiante por PIN.

### Añadido
- **QA acústica** (`services/audio_library.py`): análisis determinista de cada WAV (solo stdlib) —
  `peak`, `RMS`, `clipping %`, `DC offset` y `silence ratio` — con clasificación `PASS`/`WARNING`/
  `REJECT`. La subida devuelve un panel "AUDIO QUALITY" (formato, sample rate, canales, duración,
  clipping, silencio, peak dBFS) antes de aceptar la grabación.
- **Content integrity check** (`services/content_validation.py` + `scripts/content_validation.py`):
  recorre `question → audio_id → manifest → WAV → metadata → CEFR → difficulty → subskills` y emite
  el "CONTENT INTEGRITY CHECK" (ítems, grabados vs TTS, referencias rotas, ids duplicados,
  transcripciones ausentes, desfase CEFR y desfase de duración).
- **Content Audit Dashboard** (frontend): pestaña "Content audit" en Ajustes → Audio con el resumen
  de integridad y los issues por severidad.
- **Candado admin (PIN local)** (`dependencies.require_admin` + `ADMIN_PIN`): protege subida, borrado,
  previsualización y auditoría. Separación `student` (aprender) / `admin` (gestionar) sin OAuth/cloud.
- **Backup + auditoría de borrado**: `DELETE` copia el WAV y su entrada a `_backups` y registra la
  operación en `audit.log` (JSONL) antes de borrar, para recuperación.
- **Límites de subida**: MIME WAV estricto, `MAX_AUDIO_DURATION_SECONDS` y `MAX_AUDIO_BYTES`.

### Cambiado
- `POST /api/audio-library/upload` ahora devuelve el panel de QA y aplica límites de MIME/duración.
- Nuevos endpoints `GET /api/audio-library/status` y `GET /api/audio-library/audit` (admin).

### Verificado
- Backend `pytest` (889 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.
- CI ampliado con jobs `content-validation` y `playwright` (E2E visual).

## [1.36.0] — 2026-08-31

**Audio Corpus 1.0**: corpus de audio humano versionado en `curriculum/listening_corpus.json`
(40 ítems A1–B2 con diversidad real de hablantes, acentos, contextos, connected speech, ruido y
velocidad), pipeline de producción de grabación e importación masiva.

### Añadido
- **Corpus de audio humano** (`backend/curriculum/listening_corpus.json`): 40 ítems grabables
  (`c001`–`c040`) con la matriz multidimensional del auditor (nivel × hablante × contexto ×
  condiciones de escucha) y metadatos ampliados (`gender`, `age_band`, `region`, `accent`,
  `speaker_count`, `spontaneity`, `recording_environment`, `overlap`, `connected_speech`,
  `prosody`, `task_type`, `cefr`, `context`).
- **Loader del corpus** (`services/listening.py`): `QUESTION_BANK` ahora fusiona el banco heredado
  TTS (`l1`–`l23`) con el corpus; los ítems del corpus son `tts` hasta que el manifest respalda su
  `audio_id` (el manifest sigue siendo la fuente de verdad). `LISTENING_BANK_VERSION` → `4.0.0`.
- **Pack de grabación** (`backend/scripts/generate_recording_pack.py`): genera el CSV de guiones por
  hablante (transcripción, wpm objetivo, notas de connected speech, entorno, ruido) y un resumen de
  progreso frente al objetivo A1 30–40 / A2 40–50 / B1 60–80 / B2 60–80.
- **Importación masiva** (`backend/scripts/import_audio.py --batch`): incorpora los WAV grabados por
  convención `{cefr}/{speaker_id}/{audio_id}.wav`, mide su duración real y rellena el manifest.
- **Higiene de release** (`scripts/check_release_consistency.py`): comprueba que backend, frontend,
  README, CHANGELOG y PLAN declaran la misma versión; añadido a CI.

### Cambiado
- `PLAN.md` sincronizado a la versión de la app (eliminada la inconsistencia `1.34.0`).

### Verificado
- Backend `pytest` + `ruff` limpio; frontend `tsc` + `vitest` OK.

## [1.35.0] — 2026-08-31

**Gestión en-app de la biblioteca de audio humano**: subir, reemplazar y quitar las
grabaciones WAV de los ejercicios de listening desde la propia app (Ajustes → Audio),
sin tocar la terminal.

### Añadido
- **Switch runtime por manifest** (`services/audio_library.py`): `is_recorded` considera grabado un
  ítem también cuando su `audio_id` está presente en el manifest. Así, subir un WAV convierte el ítem
  de TTS a grabado (y borrarlo lo revierte) sin tocar el banco de preguntas.
- **Helpers de escritura/borrado**: `wav_probe_bytes` (lee el WAV en memoria), `write_entry` (upsert
  atómico + validación del manifest) y `remove_entry` (borra entrada + WAV).
- **Router `/api/audio-library`** (`routers/audio_library.py`): `GET /slots` (los 9 slots grabables
  con su estado), `POST /upload` (subir/reemplazar WAV con metadatos), `GET /{audio_id}/audio`
  (previsualizar) y `DELETE /{audio_id}` (quitar grabación).
- **Frontend**: pestaña **Audio** en Ajustes (`components/AudioLibrary.tsx`) con preview del WAV,
  edición de metadatos (transcripción, hablante, acento, CEFR, velocidad, ruido, género, región,
  contexto), subida y borrado. `domain/listening.py` expone `audio_type="recorded"` cuando el manifest
  respalda el ítem (la UI muestra "Real recording" y oculta la escalera de velocidad).

### Cambiado
- `postForm` en `api/client.ts` para subidas multipart.

### Verificado
- Backend **858 tests** + `ruff` limpio; frontend **237 tests** + `tsc` OK.

## [1.34.0] — 2026-08-28

**Speaking 2.0**: pronunciación marcada como proxy, desglose de Interaction Quality y
Conversation Endurance.

### Añadido
- **Pronunciation proxy** (`services/speaking.py`): `PROXY_CRITERIA` + `criterion_is_proxy()` marcan
  `pronunciation` como *proxy* porque deriva de similitud fonética de texto (no de análisis acústico
  real). El diagnóstico (`/api/academy/speaking/diagnostic`) emite `proxy: true` en ese criterio y la
  UI lo muestra con una insignia "proxy" para ser transparente con la limitación.
- **Interaction Quality** (`services/speaking.py`): `INTERACTION_QUALITY_DIMENSIONS`
  (initiation, response, follow_up, repair, turn_taking) con `interaction_quality_scores()`. Cada
  sub-dimensión se registra como evidencia propia (`interaction:<dim>`) y se agrega en
  `_interaction_quality_breakdown`, expuesta en el diagnóstico como `interaction_quality`.
- **Conversation Endurance** (`services/speaking.py` + `repositories/conversations.py`):
  `conversation_endurance()` mide cuánto puede sostener una conversación el alumno a partir de la
  telemetría de turnos hablados (hitos 30s/60s/90s/120s/180s). Nuevo repositorio
  `student_speaking_sessions()` y endpoint `GET /api/academy/speaking/endurance`.
- **LLM evidence**: `speaking_llm` solicita y parsea el nuevo campo `initiation` para alimentar la
  sub-dimensión de inicio de interacción.

### Cambiado
- **Frontend**: `SpeakingDiagnostic` renderiza la insignia "proxy", el desglose de Interaction
  Quality y los hitos de Conversation Endurance (con traducciones ES/EN).

## [1.33.0] — 2026-08-28

**Listening 2.0**: indicador de resiliencia auditiva y clasificación del corpus por
contexto comunicativo.

### Añadido
- **Listening Resilience** (`services/listening.py`): `resilience_dimensions()` clasifica cada ítem
  según la condición de escucha que su audio *realiza* (habla clara → natural → conectada → rápida →
  ruido → acentos) y `listening_resilience()` agrega la precisión por dimensión. El diagnóstico
  (`/api/listening/diagnostic`) ahora emite `resilience` con `main_weakness` ("Your main weakness is
  understanding connected speech") y `recommendation`, además de `dimensions`.
- **Honestidad de evidencia**: la resiliencia se calcula sobre el vector *realizado* (no el declarado),
  de modo que una voz TTS neutra no aporta evidencia a `noise`/`accents`; esas dimensiones se poblarán
  cuando exista el corpus real.
- **Contexto comunicativo** (`context`): nueva dimensión de clasificación del corpus en
  `ListeningAsset`/`ListeningQuestion` (`LISTENING_CONTEXTS`: conversation, announcement, message,
  instructions, news, interview, narrative, presentation) y en el manifest de audio humano
  (`AudioLibraryEntry.context`, con `by_context` en `library_summary`).

### Cambiado
- **`AUDIO_LIBRARY_VERSION` → `1.2.0`**: el manifest de la biblioteca de audio humano incorpora el
  campo `context` (comunicativo). El manifest vacío del repositorio se actualiza en consecuencia.

## [1.32.0] — 2026-08-28

**Curriculum 2.0**: escalera CEFR completa (Pre-A1 → C2, con bandas "plus") y descriptores
Can-Do por dimensión, visibles en el Course.

### Añadido
- **Marco de descriptores CEFR** (`curriculum/cefr_descriptors.json` + `services/cefr_descriptors.py`):
  la escalera completa `Pre-A1, A1, A2, A2+, B1, B1+, B2, B2+, C1, C2` con descriptores "Can-Do"
  para 9 dimensiones (listening, speaking, reading, writing, grammar, vocabulary, pronunciation,
  **interaction** y **mediation** — las dos nuevas del Companion Volume).
- **Banda continua** (`band_for_numeric`): la estimación puede expresar matices (p. ej. "B1+") sin
  alterar la progresión de matrícula (`CEFR_ORDER` sigue con los 6 cursos principales).
- **`/api/academy/cefr-ladder`**: devuelve dimensiones + bandas con `is_current` y sitúa al alumno
  (`estimated_band`/`estimated_numeric`) desde el Student Model.
- **Course**: escalera CEFR completa con "You are here" y una tarjeta "What you can do" con los
  descriptores Can-Do del nivel estimado, agrupados por dimensión.

### Nota
- Los niveles "plus" (A2+/B1+/B2+) y Pre-A1 son **bandas de competencia**, no cursos con contenido
  propio: el contenido de los cursos (A1..B2) no cambia. La progresión de matrícula permanece intacta.

## [1.31.0] — 2026-08-28

**Adaptive Engine 2.0**: motor de prioridad explicable y "Why this activity?" en la tarjeta de
siguiente mejor actividad.

### Añadido
- **Priority Engine** (`services/adaptive.py`): `priority_signals()` expone las señales observables
  de cada candidato (recencia, retención, confianza, estabilidad, volumen de evidencia,
  transferencia/novedad y dificultad) y `priority_score()` las combina con el orden pedagógico por
  categoría en una prioridad compuesta determinista (0..1).
- **"Why this activity?"**: `explain_priority()` genera una explicación pedagógica en inglés por
  categoría (repaso, listening, debilidad, nuevo, refuerzo); `next_best_activity()` emite `signals`
  y `why` junto a `priority`.
- **Transparencia en la API**: `/api/academy/next-best` incluye `signals` y `why`
  (`NextBestActivityOut`); la tarjeta `NextBestCard` muestra la explicación bajo el CTA.

### Cambiado
- **`priority` semántico**: deja de ser la proyección ordinal fija (`NEXT_BEST_PRIORITY`) y pasa a
  ser un score compuesto explicable (base por categoría + olvido + debilidad + evidencia).
- **`get_next_best_activity`** pasa el perfil CEFR anotado y el instante de referencia al motor
  para calcular las señales.

## [1.30.0] — 2026-08-28

**LAN + Mobile 100%**: verificación real de mDNS, recuperación de permisos de micrófono,
test de micrófono con medidor de nivel, tarjeta de conexión con QR pulido y página de ayuda
`/help/connect` para confiar el certificado por plataforma.

### Añadido
- **mDNS real**: `/api/network` añade `local_url_available` (comprueba si `<host>.local`
  resuelve vía mDNS); el launcher marca la fila "Nombre local (mDNS)" como `resuelve`/`no resuelve`.
- **Recuperación de permiso**: `watchMicrophoneAvailability()` observa `visibilitychange`,
  `focus`, `devicechange` y la Permissions API; `useAudioCapabilities` ahora es reactivo (estado +
  `refresh`) en lugar de `useMemo(..., [])`, resolviendo el caso denegado → ajustes → conceder → volver.
- **Test de micrófono** (`components/MicrophoneTest.tsx`): botón "Test microphone" con medidor de
  nivel de entrada en vivo (`utils/microphoneLevel.ts`) y "Test playback"; integrado en el estado
  del sistema.
- **Tarjeta "Connect a device"** (`components/ConnectDeviceCard.tsx`): QR pulido, URL por IP
  (siempre) y `.local` (solo si resuelve), con enlace a la ayuda.
- **Página `/help/connect`** (`features/help/ConnectHelp.tsx`): instrucciones para confiar el
  certificado autofirmado en Windows, Android e iPhone/iPad; accesible desde el header (botón Help)
  y desde la tarjeta de conexión.
- **E2E móvil** (`tests/visual/mobile.spec.ts`): renderizado de la página de conexión y del test de
  micrófono, y aviso `MicUnavailableNotice` ante permiso denegado, en viewport móvil.
- **`docs/DEVICE_MATRIX.md`**: matriz de validación física (Android/iPhone/Tablet × Mic/Audio/
  Speaking/Listening).

### Cambiado
- **StatusBar**: la barra de estado y su popover ya no se recortan (`overflow: hidden` eliminado) y
  el popover queda acotado al viewport (`max-height` + scroll) con `z-index` correcto.

## [1.29.0] — 2026-08-28

**Fiabilidad LAN + audio móvil (P0) y lanzador de escritorio**: corrección del micrófono en móvil,
acceso por HTTPS autofirmado en la red local, y lanzador con estado en color, reinicio y reloj de
arranque.

### Añadido
- **Detección de capacidades de audio** (`utils/browserCapabilities.ts` + `hooks/useAudioCapabilities.ts`):
  capa que protege el acceso a `navigator.mediaDevices`/`getUserMedia`/secure context y muestra un
  aviso pedagógico (`MicUnavailableNotice`) en lugar del error "Cannot read properties of undefined".
- **`/api/network`**: expone `hostname` y `local_url` (`https://<host>.local`), con `url` ahora en HTTPS.
- **`/api/health/dependencies`**: nuevo estado `audio_library` (infraestructura de la biblioteca de audio).
- **Launcher**: botón "Reiniciar servidor", enlaces de acceso clicables (equipo, LAN y mDNS) y detalle
  del archivo de base de datos (tamaño, nº de tablas, fecha de modificación).
- **`components/ui/tooltip.tsx`**: tooltip accesible para el aviso de diferencia de dificultad del audio
  en Listening.

### Cambiado
- **HTTPS en la LAN**: el frontend se sirve con `@vitejs/plugin-basic-ssl`; Playwright y el launcher
  verifican el estado por HTTPS aceptando el certificado autofirmado.
- **Launcher**: estado con colores reales (verde/rojo/ámbar) en cabecera y servicios, reloj animado
  durante arranque/parada/reinicio, y resumen/diagnóstico de cookies más legible.
- **Analysis panel**: ancho máximo ampliado, pestañas que se envuelven (responsive) y topes de
  redimensionado conscientes del viewport.
- **Footer**: la barra de estado queda anclada al fondo en todas las vistas.
- **Listening**: el aviso de diferencia de dificultad del audio pasa de texto fijo a tooltip sobre un
  icono de aviso (clave `listening.audioGap` con placeholders).

## [1.28.0] — 2026-08-27

**Biblioteca de audio humano — código (P1.5–P1.8)**: ajuste puntual de Listening para ítems
grabados. El contenido real (WAV de varios hablantes) sigue pendiente de grabaciones del usuario;
la infraestructura (manifest + resolución + servido + validación) y el importador
(`backend/scripts/import_audio.py`) ya existían.

### Cambiado
- `features/listening/ListeningPractice.tsx`: la escalera de velocidad slow/normal/fast solo se
  muestra en ítems TTS; en ítems `recorded` la velocidad es la real y no sintetizable.

## [1.27.0] — 2026-08-27

**Code-splitting por rutas**: división del bundle con `React.lazy`/`Suspense`. Cambio solo-frontend.

### Cambiado
- **`app/Workspace.tsx`**: `HomeScreen`, `CourseScreen`, `ProgressScreen` y `PracticeView` pasan a
  `React.lazy` (patrón named→default), envueltos en `Suspense` con fallback (`Loader2` animado,
  `role="status"`/`aria-busy`).
- **`app/PracticeView.tsx`**: `AnalysisPanel` también se carga diferido (panel de insights).
- **`utils/i18n.ts`**: nueva clave `common.loading`.

### Resultado
- Chunk inicial: **537 kB → 425 kB** (gzip 134 kB), con chunks por ruta (`HomeScreen`, `CourseScreen`,
  `ProgressScreen`, `PracticeView`, `AnalysisPanel`) y ya sin aviso de bundle >500 kB.

## [1.26.0] — 2026-08-27

**Rediseño UI 2.0 — fases 3–6**: migración de las pantallas de práctica (Listening, Speaking,
Pronunciation y Progress) del CSS legacy a Tailwind v4 + shadcn/ui + Motion, con retirada de las
reglas huérfanas de `legacy.css`. Cambio solo-frontend.

### Cambiado
- **Listening** (`features/listening/ListeningPractice.tsx`): reproductor destacado con onda animada
  (Motion), variantes de velocidad 0.8x/1.0x/1.2x y estadísticas/diagnóstico presentados con
  `Card`/`Badge`. Lógica intacta (dictado, shadowing, retención, precisión por tema/dificultad).
- **Speaking** (`features/speaking/*` + `PronunciationPractice.tsx`): "estudio de conversación" con
  micrófono que pulsa (Motion) al grabar/escuchar y feedback de fluidez/coherencia con
  `SkillBar`/`Badge`. Props y lógica intactas.
- **Progress** (`features/progress/ProgressScreen.tsx`): dashboard pedagógico limpio con `LevelBadge`,
  barra `SkillBar`, lista de destrezas expandible y `SkillDetail`.
- **`styles/legacy.css`**: poda de ~1.400 líneas de reglas cuyas clases ya no se usan en ningún
  `.tsx` (verificado con `rg`). Se conservan los bloques aún en uso (chat/shell/header/composer y
  `.journey-*`).
- **Móvil**: tap targets ≥40px y sin overflow horizontal en las pantallas migradas (premisa 20).

### Añadido
- Claves i18n nuevas: `roleplay.hint`, `progress.score/confidence/evidence/stability`.

## [1.25.0] — 2026-08-27

**Paneles del chat redimensionables y persistentes**: los tres paneles del CHAT
(conversaciones, zona central y Análisis) son redimensionables por el usuario, con asas
visibles y accesibles, y el ancho elegido se persiste por usuario. Cambio solo-frontend.

### Cambiado
- **`ResizeHandle`** reestilizado con Tailwind: asa de 8px con *grip* central visible
  (`bg-border` → `bg-primary` al hover/foco), cursor de redimensionado y `touch-action: none`.
  Se oculta en móvil/tablet (`hidden lg:flex`) donde los paneles son drawers.
- **Accesibilidad**: el asa expone `role="separator"`, `aria-orientation="vertical"`,
  `aria-valuenow/min/max` y es operativa por teclado (flechas ←/→, ±24px).
- **Persistencia eficiente**: `setLayout` (hook `useChat`) persiste el ancho una sola vez al
  terminar de arrastrar (debounce 400ms) en lugar de un `PUT` por cada `pointermove`.
- **`styles/legacy.css`**: eliminadas las reglas huérfanas de `.resize-handle` (la clase ya no
  se usa); se conserva `body.is-resizing`.

### Añadido
- **Test visual Playwright** (`tests/visual/resize.spec.ts`): redimensiona el panel Análisis por
  teclado, comprueba el cambio de ancho y verifica que el ancho persiste tras recargar.

### Próximos incrementos (fases 3–6)
- **Fase 3** — `features/listening/ListeningPractice.tsx`: entorno auditivo inmersivo.
- **Fase 4** — `features/speaking/*`: "estudio de conversación" (mic que respira, feedback).
- **Fase 5** — `features/progress/ProgressScreen.tsx`: dashboard pedagógico limpio.
- **Fase 6** — Móvil específico y consolidación; **retirar `legacy.css`** una vez migradas todas
  las pantallas.

## [1.24.0] — 2026-08-27

**Analysis redesign + responsive 100%**: el panel ANALYSIS del chat pasa de 10 acordeones colapsables
a **navegación por pestañas** (una sección a la vez, sin truncado de texto), se hace una **pasada
responsive completa** de toda la app y se añaden **tests visuales Playwright** en 3 breakpoints como
parte de la Definition of Done. Cambio solo-frontend.

### Añadido
- **`AnalysisPanel`** (`src/components/AnalysisPanel.tsx`): 7 pestañas (Overview, Today, Profile,
  Speaking, Writing, Assessment, Tutor) con iconos, indicador activo animado (`layoutId` de Motion),
  transición de contenido (`AnimatePresence`) y scroll vertical propio por pestaña. Speaking agrupa
  Diagnostic + Panel + Journey; Writing agrupa Panel + Journey (se elimina el título duplicado).
- **Tests visuales Playwright**: `@playwright/test` + `playwright.config.ts` (3 proyectos: desktop
  1280×800, tablet 768×1024, móvil 390×844), spec `tests/visual/smoke.spec.ts`, script npm
  `test:visual` y helper `scripts/visual.ps1`. Captura screenshots reproducibles de las rutas
  principales en `tests/visual/screenshots/<proyecto>/`.

### Cambiado
- **`PracticeView`**: sustituye las 10 `InsightCard` por `<AnalysisPanel />`.
- **Pasada responsive completa**: `ProgressScreen`, `ListeningPractice`, `ReadingPractice`,
  `PronunciationPractice`, `SpeakingAssessment`, `SpeakingRolePlay`, `SettingsDialog`,
  `ProfileDialog`, `HelpDialog`, `Composer` y `HandsFreeToggle` corrigen overflow horizontal,
  `flex-wrap`, `min-w-0`, tap targets ≥40px y pestañas con scroll horizontal en móvil.
- **`docs/PREMISAS.md`**: añadidas premisas 19–21 (panel de análisis por pestañas sin truncado,
  responsive 100% verificado en 3 breakpoints y tests visuales Playwright obligatorios).

### Eliminado
- **`InsightCard`**: quedó sin uso tras la migración al panel por pestañas.

### Próximos incrementos (fases 3–6)
- **Fase 3** — `features/listening/ListeningPractice.tsx`: entorno auditivo inmersivo (reproductor,
  onda, variantes 0.8x/1.0x/1.2x).
- **Fase 4** — `features/speaking/*`: "estudio de conversación" (mic que respira, fluidez/coherencia,
  feedback).
- **Fase 5** — `features/progress/ProgressScreen.tsx`: dashboard pedagógico limpio.
- **Fase 6** — Móvil específico y consolidación; **retirar `legacy.css`** una vez migradas todas las
  pantallas.

## [1.23.0] — 2026-08-27

**UI 2.0 (incremento 1)**: adopción de un *design system* real — Tailwind CSS v4 + shadcn/ui + Motion —
para sustituir el CSS custom (~6.450 líneas) por primitivas y microinteracciones. Cambio solo-frontend:
no se toca backend, Student Model ni pedagogía.

### Añadido
- **Stack de diseño**: `tailwindcss` + `@tailwindcss/vite`, `motion`, `lucide-react` y dependencias de
  shadcn (`class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `@radix-ui/*`); alias
  `@/*` → `src/*` en `vite.config.ts` y `tsconfig.json`; `components.json` y `lib/utils.ts` (`cn`).
- **Tokens de identidad**: `index.css` con tokens semánticos shadcn (`--background`, `--foreground`,
  `--card`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`,
  `--ring`, `--radius`, `--success`, `--warning`) mapeados al sistema de apariencia existente
  (`data-theme`/`data-accent`/`data-font`/`data-density`), preservando claro/oscuro y los 7 acentos.
- **Aislamiento del CSS legacy**: `src/index.css` → `src/styles/legacy.css` envuelto en `@layer base`
  e importado al final, para no romper las pantallas aún no migradas.
- **Primitivas shadcn**: `Button`, `Card`, `Badge`, `Progress` (`src/components/ui/`).
- **Primitivas de dominio**: `SkillBar` (barra animada al entrar), `LevelBadge` (insignia CEFR por tramo),
  `JourneyNode` (nodo del recorrido con pulso suave en el actual) y `Milestone` (hito de objetivo con icono por estado).

### Cambiado
- **AppShell/Header/Navigation**: reestilizados con Tailwind; navegación activa con píldora animada
  (`layoutId` de Motion) y nav inferior en móvil.
- **Home**: rediseñada con saludo personalizado (nombre), hero protagonista (insignia CEFR + preparación
  animada + tendencia), *Next Best Activity* como protagonista, skills con `SkillBar` y racha; entrada
  escalonada de secciones con Motion.
- **Course**: recorrido A1→B2 rediseñado con `JourneyNode`, línea de progreso, panel de nivel
  (insignia + barra de progreso + readiness) e hitos `Milestone`; entrada escalonada Motion.
- Versión → `1.23.0`.

## [1.22.0] — 2026-08-27

**Learning UX 2.0**: simplificación radical de la interfaz sin añadir pedagogía nueva. El objetivo es que
en 3 segundos se responda a *¿dónde estoy? ¿cómo voy? ¿qué hago ahora? ¿y después?* — y nada más compita
con esas cuatro respuestas.

### Añadido
- **Idioma de interfaz configurable (Español/English)**: sistema i18n completo (`utils/i18n.ts` +
  `hooks/useI18n.tsx`), persistido por usuario (localStorage + `interface_language` en backend). El
  contenido pedagógico permanece en inglés; solo el *chrome* se traduce. Por defecto **English**.
- **Next Best Activity**: el frontend ya no decide pedagogía; una única acción priorizada derivada del
  Adaptive Engine (`/api/academy/next-best`) con un único CTA `Continuar` (`NextBestCard`/`NextStep`).
- **Flujo Activity → Result → Feedback → Next**: componentes compartidos `ActivityResult` y `NextStep`
  para un bucle de práctica uniforme.
- **Course (antes Academy)**: renombrado a *Course* y presentado como recorrido CEFR con hitos
  (`CourseScreen`), no como panel administrativo.
- **Barra de estado colapsable**: indicador mínimo `● Ready` que expande el estado detallado del sistema
  (API/BD/Ollama/STT/TTS + URL LAN) al pulsar.

### Cambiado
- **Inicio (HOME) como "¿qué hago ahora?"**: el dashboard se centra en la siguiente mejor actividad y
  en el estado del alumno, reduciendo la carga cognitiva.
- **Navegación por destrezas**: distinción entre *PRIMARY SKILLS* (Listening, Speaking, Reading, Writing)
  y *SUPPORT* (Grammar, Pronunciation); sin niveles CEFR en los botones.
- **Controles técnicos reubicados**: `Modelo` y `Herramientas` se mueven al menú de usuario / ajustes
  (`SettingsDialog`), dejando la cabecera limpia.
- **Eliminado el botón "Marcar como hecho"**: las actividades se marcan automáticamente al generarse
  evidencia (elimina una acción pedagógicamente peligrosa).
- **App.tsx dividido**: `AppShell`, `Header`, `Navigation`, `Workspace`, `PracticeView` y `routes/`,
  más organización por features (`features/home`, `features/course`, `features/progress`, etc.).
- **Progreso simplificado**: indicadores cualitativos (B1, barras, "Improving") combinados con el % en
  lugar de porcentajes crudos por todas partes.
- **Limpieza y reorganización de `index.css`**.
- **i18n completo del chrome**: cierre de todos los strings en castellano restantes en componentes y
  helpers de dominio (`cefr`, `progress`, `speaking`, `fluency`, `pronunciationFeedback`).
- Versión → `1.22.0`.

## [1.21.0] — 2026-08-26

Cierra la **auditoría pedagógica A1→B2** de V1.21 (los seis P0/P1 del diagnóstico externo) y añade
una **nueva UI de 3 paneles** con barra de estado y navegación por destrezas. Filosofía intacta: el
LLM solo extrae evidencia; todo el scoring es determinista, local y honesto (lo no verificable se
declara como tal, no se inventa).

### Añadido
- **Corpus de audio humano 1.0 (P0-1)**: `AudioLibraryEntry` ampliado con 11 metadatos auditivos
  (`gender`, `age_band`, `region`, `speech_rate`, `spontaneity`, `recording_environment`, `overlap`,
  `connected_speech`, `prosody`, `task_type`, `cefr`) usando `Literal`; `AUDIO_LIBRARY_VERSION` →
  `1.1.0`; `library_summary` con desgloses `by_cefr`/`by_speaker_id`/`by_accent`/`by_region`; CLI
  `backend/scripts/import_audio.py` (`wav_metadata` con solo `wave`).
- **Validación determinista audio↔metadata (P0-2)**: `wav_probe`, modelo `AudioValidationIssue`,
  `validate_audio_entry`/`validate_audio_entries` (duración verificable; `speaker_count` como proxy
  por canales; `speech_rate`/`noise_level`/`accent`/`recording_environment`/`prosody` como `info` "no
  verificable" sin inventar SNR) y flag `--validate-all` en el CLI de importación.
- **Separación del proxy de pronunciación del audio real (P0-3)**: `phoneme_accuracy` →
  `phoneme_accuracy_proxy` y `prosody_score` → `prosody_proxy`; `pronunciation_source:
  "transcript"` y rótulos honestos "proxy de texto / sin audio" en el frontend. Sin cambios de pesos.
- **Evidencia familiar/transfer/novel (P1-4)**: dimensión `evidence_kind` en el Student Model
  (columna `evidence_kind` con migración idempotente), `generalized_mastery_score` ponderado por
  tipo de evidencia y `evidence_by_kind` en `build_skill_profile`.
- **Interaction 3.0 (P1-5)**: `turn_balance` con meseta `[0.3, 0.7]`, renombrado del objetivo
  `turn_completion` → `turn_duration` (desambiguado del semántico del LLM), señal `repair` añadida y
  reponderación objetivo (0.3) / subdimensiones (`turn_balance` 0.3 + `turn_duration` 0.7).
- **Matriz de assessment CEFR A1–B2 (P1-6)**: `backend/curriculum/cefr_matrix.json` + cargador
  `services/cefr_matrix.py`; `adaptive.readiness` consume umbrales de `minimum_mastery`/
  `minimum_confidence`/`minimum_evidence` y gates `transfer_required`/`novel_required`
  (retrocompatible), con campos nuevos en `ReadinessSkillOut`.
- **UI de 3 paneles**: barra superior (logo + avatar de usuario + navegación de 6 destrezas +
  Academy + manos libres/modelo/herramientas/ayuda), panel central de desarrollo, panel derecho de
  análisis y **barra de estado inferior** (API/BD/Ollama/STT/TTS + URL LAN); sistema de iconos SVG
  coherente (`Icons.tsx`), `SectionNav`, `ReadingPractice`, `StatusBar` y persistencia de la sección
  por usuario. Script `launcher/allow-firewall.ps1` para exponer 5173/8000 en la red local.
- **Learning Home (HOME como centro)**: pantalla de inicio que responde a "¿qué debo hacer ahora y
  cómo voy?", con saludo, hero de nivel (banda CEFR + preparación para el siguiente nivel +
  tendencia), **plan de hoy como tarjetas de acción** (`LearnToday`, una acción por tarjeta), barras
  de destrezas, racha/actividad y un único CTA "Practice now" hacia la destreza a reforzar. Reutiliza
  `profile`/`history`/`getSession` existentes (sin backend nuevo); la marca del header vuelve a
  Inicio. Etiquetas compartidas extraídas a `utils/learningLabels.ts`.

### Cambiado
- Versión → `1.21.0`.
- La app abre ahora en **Inicio** (antes abría directamente en el chat).

## [1.20.0] — 2026-08-26

Cierra los tres incrementos naturales pendientes de V1.19: la **pronunciación fonémica (P6)**, la
**integración del turn-taking real** en la parte "Interaction" del Speaking Assessment, y la
**infraestructura de biblioteca de audio humano** (P1.5–P1.8). Filosofía intacta: el LLM solo
extrae evidencia; todo el scoring determinista y local.

### Añadido
- **Pronunciación fonémica (P6)**: `phoneme_alignment`/`syllables`/`prosody_score` en
  `services/phonemes.py` (alineación de fonemas con `SequenceMatcher` + prosodia proxy por nº de
  sílabas). `composite_score` rebalanceado a `word 0.35 / phoneme 0.35 / phonetic 0.15 / prosody
  0.15` (se elimina la similitud por caracteres) y expone `prosody_score` + `phoneme_breakdown`.
  El rubric de pronunciación pasa de 3 a 4 criterios (añade `prosody`); `PronunciationResponse`
  y `PronunciationPractice.tsx` muestran "Precisión de fonemas" y "Prosodia (ritmo)".
- **Turn-taking real → Interaction**: `components/SpeakingRolePlay.tsx` (role-play en vivo dentro
  del Speaking Assessment) con telemetría de turnos (`duration_ms`/`latency_ms`) y persistencia de
  la conversación; `SpeakingAssessment.tsx` bifurca por `task_type` conversacional
  (`isConversationalTaskType` en `utils/speaking.ts`) y `submitSpeakingAssessmentPart` envía
  `conversation_id` para inyectar `interaction_objective` (señal objetiva) en el scorer.
- **Biblioteca de audio humano (P1.5–P1.8)**: `services/audio_library.py` con manifest versionado
  (`backend/audio_library/manifest.json`, vacío hoy — límite de contenido), resolución segura del
  WAV grabado (rechaza rutas fuera de la biblioteca) y servido sin Piper: `get_audio` sirve audio
  `recorded` desde el manifest y devuelve 404 (no TTS) si falta; `audio_ready` ya no depende solo
  de Piper.

### Cambiado
- Versión → `1.20.0`.

## [1.19.0] — 2026-08-26

Refresco visual y de consistencia del frontend (sin cambios de backend ni de lógica de negocio).
Unifica los ~11 paneles del panel de análisis en tarjetas colapsables (`InsightCard`) para eliminar
la "pared de paneles" y dar jerarquía visual, pule el header (sticky con blur + menú secundario en
móvil), enriquece el estado vacío del chat y las burbujas del tutor, y consolida primitivas CSS
(`.card`, `.badge`, `.pill`, `.section-divider`) respetando el sistema de apariencia existente
(`data-theme` / `data-accent` / `data-font` / `data-density`). Se refuerza el diseño responsivo con
un breakpoint nuevo a ≤480px y accesibilidad (`aria-expanded`/`aria-controls`).

### Añadido
- **Primitivas CSS** `.card`/`.card__header`/`.card__toggle`/`.card__body`/`.badge`/`.pill`/
  `.section-divider` y tokens `--color-surface-3`/`--shadow-card`; escala tipográfica por defecto
  afinada (`--text-sm` 14px, `--text-xs` 12.5px).
- **`InsightCard`** (tarjeta colapsable accesible) y envoltura de los 11 paneles del análisis;
  `ProgressDashboard`, `TodayPlan` y `ListeningPractice` expandidos por defecto.
- **Header** sticky con `backdrop-filter: blur()` y fondo translúcido; menú desplegable de
  acciones secundarias (apariencia/ayuda) a ≤768px.
- **Chat**: avatar circular del tutor en las respuestas y estado vacío más rico (kicker + badge).
- **Responsive ≤480px**: header compacto, `composer` sin desbordamiento y drawer de análisis a
  100% de ancho.

### Cambiado
- Controles del header con altura uniforme (36px).
- Versión → `1.19.0`.

## [1.18.0] — 2026-08-26

Retoma los **P1 de listening** de la auditoría V1.14 (§27.8). Añade la medición de **delayed
retention** (precisión inmediata vs. retardada), convierte **dictado** y **shadowing** en tareas
de producción reales (no opción múltiple) con scoring determinista, y añade una **escalera de
variantes de velocidad** (slow/normal/fast) al audio servido. El LLM sigue sin puntuar; todo el
scoring es determinista y local (Whisper + Piper).

### Añadido
- **Delayed retention (P1.2)**: `delayed_retention(attempt_rows, now="")` en
  `services/listening.py` — `immediate_accuracy` (primera exposición por pregunta) vs.
  `delayed_accuracy` (re-exposición a ≥2 días) con buckets `0-2`/`2-7`/`7-30`/`30+` y
  `retention_rate`; expuesto en `listening_diagnostic` (clave `retention`) y en el frontend.
- **Dictado real (P1.4) y shadowing real (P1.3)**: sub-destrezas `dictation`/`shadowing` servidas
  como tareas de producción (escribir lo oído / grabar la repetición), con scoring determinista
  vía `services/phonetics.composite_score`. Columnas `task_type`/`score` en `listening_attempts`
  (migración idempotente), `mean_score` por sub-destreza en el diagnóstico, endpoints
  `POST /api/listening/dictation` y `POST /api/listening/shadowing`, y UI de producción en
  `ListeningPractice.tsx`.
- **Escalera de variantes de audio (P1.9)**: `slow`/`normal`/`fast` sobre el mismo contenido
  (`variant_speech_rate`/`variant_length_scale`/`audio_variants`), con cache por variante
  (`audio_digest(..., variant=...)` preserva el digest de `normal`), query param `variant` en
  `GET /api/listening/audio/{id}` y botones de variante en el frontend.

### Cambiado
- Versión → `1.18.0`.

## [1.17.0] — 2026-08-26

Cierre de tres incrementos naturales sobre V1.16 (Speaking Assessment & Evidence 2.0). Añade la
**pantalla del Speaking Assessment**, cierra el **puente conversación→speaking** (la telemetría
objetiva de interacción pasa a capturarse de extremo a extremo y a consumirse en el scorer) y
convierte el **writing** en una señal longitudinal sobre el Student Model (espejo de speaking).
El LLM sigue siendo solo extractor de evidencia; todo el scoring es determinista.

### Añadido
- **UI del flujo de Speaking Assessment** (`components/SpeakingAssessment.tsx`): start → 4 partes →
  resultado, con micrófono (grabar → transcribir → medir duración) y entrada manual (sin
  micrófono). Tipos + API (`start`/`submit part`/`finish`/`get`) sobre los endpoints ya existentes.
- **Puente conversación→speaking**: `duration_ms`/`latency_ms` en el `ChatMessage` persistido;
  captura de la telemetría del turno del alumno en el chat (`utils/telemetry.ts`) y envío de
  `conversation_id`/`message_id` en `/api/chat/stream`. El scorer de speaking fusiona
  `evidence["interaction_objective"]` (señal objetiva de turnos vía `conversation_id` opcional en
  `submit_speaking_assessment_part` y `submit_speaking_task`).
- **Writing 3.0**: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de speaking) con
  señales del Student Model (EMA, lifetime, confidence, stability, review_due) por criterio;
  endpoints `GET /api/academy/writing/diagnostic|level|journey`; frontend `WritingPanel` +
  `WritingJourney`.

### Cambiado
- Versión → `1.17.0`.

## [1.16.0] — 2026-08-26

Speaking Assessment & Evidence 2.0. Convierte el scoring de speaking de un agregador
`mean/min/max` en un modelo de competencia determinista por criterio, añade un **Speaking
Assessment** estructurado (4 partes) con sesión trazable y la **evidencia objetiva de
interacción** (telemetría de turnos). El LLM sigue siendo solo extractor de evidencia; todo el
scoring es determinista y un criterio no observado no se inventa (`score=None`).

### Añadido
- **task_achievement continuo** (4 sub-dimensiones de tarea) y **GrammarEvidence 2.0** (penalización
  por severidad en lugar de `1 - 0.25·errores`).
- **SpeakingTaskProfile**: `task_type`, dificultad `declared/realized/verified` y pesos de rúbrica por
  tipo de tarea (`weights_for_task_type`, `realized_difficulty`).
- **LexicalEvidence 2.0** (MSTTR por segmentos + sophistication/precision/collocations del LLM) y
  **FluencyEvidence 2.0** (bandas CEFR de WPM + smoothness/rhythm; `fluency ≠ speed`).
- **InteractionEvidence 2.0**: 5 sub-dimensiones semánticas del LLM fusionadas con la señal objetiva
  de interacción (`services/interaction.py`): turn_balance, latencia, completitud de turno e
  interrupciones. Telemetría de turnos (`duration_ms`/`latency_ms` en `messages`) y
  `GET /api/conversations/{id}/interaction`.
- **Diagnóstico por criterio como vista del Student Model**: `recent_score` (EMA), `lifetime_score`,
  `confidence` y `stability` por criterio (adiós al `mean/min/max`).
- **Speaking level continuo** (`speaking_level`: `numeric = 1.0 + 5.0·score`) y **Speaking Journey**
  (trayectoria CEFR): `GET /api/academy/speaking/level` y `GET /api/academy/speaking/journey`.
- **Speaking Assessment 1.0**: instrumento versionado (`curriculum/speaking_assessment.json`, 4
  partes: interview → individual task → interaction → follow-up), sesión trazable
  (`speaking_assessment_sessions`) y endpoints `start`/`part`/`finish`/`{session_id}`.
- **Frontend**: `SpeakingPanel` (NEXT FOCUS + PRACTICE NOW) y `SpeakingJourney` (barra A2→B1→B2 con
  marcador "YOU").

### Cambiado
- `speaking_diagnostic` pasa a ser una vista de las señales del Student Model (`recent_score`/EMA),
  ampliando `SpeakingCriterionOut` y `SpeakingDiagnostic.overall_recent`.
- Versión → `1.16.0`.

## [1.15.0] — 2026-08-26

Speaking 3.0. Convierte la destreza `speaking` de un *scorer por intento* en una señal de
**competencia longitudinal**, sobre el mismo Student Model unificado: mide los criterios del rubric
(fluency/grammar/lexical/pronunciation/coherence/interaction) en el tiempo, añade `interaction`
como séptimo criterio y lo expone con tendencia y criterios débiles.

### Añadido
- **Diagnóstico longitudinal de speaking** (`services/speaking.py::speaking_diagnostic`): agrupa la
  evidencia de speaking por criterio de rúbrica (`attempts`/`mean`/`min`/`max`/`review_due`), deriva
  `weak` + `recommendation` y expone `trend` global (media reciente vs previa sobre las filas
  `overall`) y `overall_mean`. Determinista, sin LLM ni red.
- **`interaction` como séptimo criterio** del rubric (`SPEAKING_CRITERIA` + `CRITERION_WEIGHTS`):
  extraída del LLM en el flujo libre (`speaking_llm.py`), no observable en read-aloud.
- **Endpoint** `GET /api/academy/speaking/diagnostic` (`SpeakingDiagnostic` + schemas
  `SpeakingCriterionOut`/`SpeakingTrend`).
- **Puente de sub-destrezas de speaking** en el Student Model (`_annotated_profile`): la entrada
  `speaking` del perfil recibe sus criterios como `subskills` (mismo patrón que listening).
- **Frontend**: tipos + `getSpeakingDiagnostic`, y panel `SpeakingDiagnostic.tsx` (desglose por
  criterio, tendencia y criterios a revisar), con estilos de tokens.

### Cambiado
- `SpeakingResultOut`/`SpeakingTaskResultOut` pasan de 6 a 7 criterios (`interaction`).
- Versión → `1.15.0`.

## [1.14.0] — 2026-08-26

Listening Evidence & Adaptive Selection. Convierte el listening de "arquitectura muy buena" a
"evidencia auditiva pedagógicamente válida": separa lo que el ítem **declara** de lo que el audio
**realiza**, evita que la metadata falsa contamine el Student Model y hace que el selector consuma
de verdad las sub-destrezas débiles del alumno. Corrige además la terminología "audio real" →
**audio TTS pre-renderizado local** (Piper).

### Añadido
- **Modelo de realización del audio** (`services/listening.py`): `AUDIO_TYPES`
  (`tts`/`recorded`/`mixed`/`synthetic_multispeaker`/`real_world`), `realized_vector`,
  `realization_status` (`declared`/`realized`/`verified`), `realized_difficulty`,
  `realization_gap_factors` y `subskill_realization_gap`. Una voz Piper única no "realiza"
  `accent`, `speaker_count` ni `noise` (quedan en 1); `connected_speech` se realiza solo si el
  texto escribe la reducción; `speed` solo si el ítem fija `speech_rate`.
- **`audio_type`** en `ListeningAsset`/`ListeningQuestion` para distinguir el tipo de audio servido.
- **Integridad de evidencia** en `listening_diagnostic`: `realization_gap` por sub-destreza y
  resumen `realization` (`verified` vs `gap`), para no contar como dominio real una sub-destreza
  entrenada con audio que no la respalda.
- **Selector adaptativo**: `pick_next_question(..., weak_subskills=...)` prioriza, dentro del nivel
  de trabajo del alumno, las sub-destrezas débiles (con realización válida); `domain.next_question`
  lo alimenta con el diagnóstico del Student Model.
- **Cache de audio versionado** (`P1.1`): path `DATA_DIR/listening/{bank}/{voice}/{id}-{digest}.wav`
  (`audio_digest` = texto + velocidad + repetición). Un cambio de script/voz/velocidad/modelo
  invalida el WAV antiguo. `scripts/generate_listening_audio.py` usa el mismo path.
- **`realized_difficulty`** persistido en `listening_attempts` (migración idempotente) y expuesto
  en `ListeningQuestion`/`ListeningAnswerResponse`.

### Cambiado
- **Terminología honesta**: "audio real" → "audio TTS pre-renderizado local" en CHANGELOG, README,
  PLAN, RELEVO y comentarios de código.
- Frontend `ListeningPractice` muestra la **etiqueta honesta del tipo de audio** (voz sintética
  local vs. grabación real), avisa cuando la dificultad realizada es menor que la declarada y
  marca las sub-destrezas con evidencia no respaldada.

## [1.13.0] — 2026-08-26

Listening 3.0. Convierte el listening de "scripts de texto + TTS genérico en vivo" a **audio TTS
pre-renderizado por ítem** (sintetizado y cacheado con Piper), cierra el currículo **A1→B2** y
garantiza evidencia independiente por sub-destreza. Todo local y determinista en el score; sin
LLM ni red.

### Añadido
- **Audio TTS pre-renderizado por ítem**: `GET /api/listening/audio/{question_id}` sirve
  `audio/wav` reproducible, pre-renderizado y cacheado en disco (`DATA_DIR/listening/`). Respeta
  `speech_rate` (mapeado a `length_scale` de Piper) y `repetition_policy="twice"`. 404 si el ítem
  no existe, 503 honesto si Piper no está disponible.
- **`audio_ready`** en `ListeningQuestion` para que el frontend reproduzca el audio TTS
  pre-renderizado o degrade al TTS en vivo con aviso.
- **Cierre A1→B2**: `curriculum/b2.json` (8 objetivos, checks de opción múltiple) y
  `LEVEL_ORDER = ["A1", "A2", "B1", "B2"]` en el banco de listening.
- **Herramienta reproducible**: `scripts/generate_listening_audio.py` pre-renderiza todo el banco
  (idempotente, `--force`).
- **Evidencia por sub-destreza**: test que garantiza que cada sub-destreza canónica
  (`fast_speech`, `connected_speech`, `multiple_speakers`, `dictation`, `shadowing`,
  `speaker_intention`) produce su fila independiente en `listening_diagnostic`.

### Cambiado
- `LISTENING_BANK_VERSION` → `3.0.0`.
- Frontend `ListeningPractice` reproduce el audio TTS pre-renderizado cuando `audio_ready` y muestra
  metadatos; `api/listening.ts` expone `getListeningAudioUrl`.

## [1.12.0] — 2026-08-26

Student Model unificado + Assessment Loop. Reconciliar los dos estimadores CEFR divergentes en
una única fuente de verdad (el Student Model de la Academy), corregir los P0 de Speaking y añadir
snapshots de evaluación históricos reproducibles.

### Añadido
- **Student Model como fuente única**: `build_student_model()` en `domain/academy.py` centraliza el
  modelo del alumno (nivel, `overall_ability`, confianza, `readiness`, `reassessment`);
  `/api/profile` pasa a ser una proyección de este modelo (mismo nivel, misma confianza).
- **Snapshots de evaluación**: tabla `cefr_assessment_snapshots` (reproducible con
  `instrument_version`/`curriculum_version`) y `cefr_history` expuesto en `/api/profile`.
- **Speaking scoring 2.0**: `task_achievement` por `task_achieved` del LLM, `lexical_resource` por
  diversidad léxica (TTR), `coherence` por marcadores discursivos y `pronunciation` con
  `observed=false` sin audio (el `overall` se recalcula solo sobre criterios observados).
- **Evidencia de discurso ampliada**: `cohesion`, `discourse_markers`, `self_corrections`,
  `hesitations`, `repetitions` en la extracción del LLM (`speaking_llm.py`).
- **Naming CEFR**: `heuristic_band` + `CEFR_MODEL_VERSION`; las bandas se documentan como
  "heuristic CEFR-aligned band" (no certificación oficial) y se exponen `overall_ability` y
  `readiness`.

### Cambiado
- `EstimatedBands` pasa de 5 a 7 destrezas (`speaking`, `reading`, `writing`).
- `LearningProfile` expone `skills` (con `samples`/`confidence`/`stability`/`trend`/`subskills`),
  `readiness` y `cefr_history`.
- Frontend `LearningProfile` muestra la barra de `overall_ability`, la `readiness` (con
  `blocking_skills`) y el desglose por destreza.

### Corregido
- Versión de release desactualizada (`config.py`, `README.md`, `package.json`) → `1.12.0`.

## [1.11.0] — 2026-08-25

CEFR basado en evidencia: sustituye el "punto-sum" por muestras por destreza + confianza. Cada
destreza exige un mínimo de muestras (`MIN_SAMPLES`) y aporta banda + confianza; el perfil expone
`estimated_confidence` y `estimated_evidence` (incluye listening).

## [1.10.0] — 2026-08-25

Listening como competencia: `topic` en el banco y métricas de precisión por dificultad/tema,
tendencia reciente y reincidencia (`listening_diagnostic`).

## [1.9.0] — 2026-08-25

Vocabulario exposure/production/mastery (P3): separa exposición (leer), producción (escribir) y
dominio (producción repetida y espaciada), con `classify` determinista.

## [1.8.1] — 2026-08-25

Marcar pasos de la sesión como hechos: `session_completions` + `POST /api/academy/session/complete`
con reseteo diario, para que los pasos completados desaparezcan del plan de hoy.

## [1.8.0] — 2026-08-25

Sesión diaria (Session Engine): plan de hoy (`/api/academy/session`) con objetivo editable y
placement adaptativo en la UI.

## [1.7.0] — 2026-08-25

Placement 2.0: convierte el placement adaptativo (IRT-lite/1PL) en un motor con
calibración observacional de ítems y perfil de resultado multiskill.

### Añadido
- **Calibración observacional de ítems**: nueva tabla `placement_item_calibration`
  (contadores poblacionales `responses`/`correct` + `correct_rate`/`sample_size` y columnas
  `estimated_difficulty`/`standard_error`/`discrimination` para estimaciones futuras).
  Cada respuesta de placement queda registrada (`record_placement_response`, vía
  `next_placement`/`submit_placement`), computando el delta contra la sesión para no
  duplicar contadores.
- **Perfil multiskill**: nueva `placement_profile(items, answers)` estima θ/nivel/confianza
  **por destreza** reutilizando `ability_theta`/`theta_to_level`/`placement_adaptive_confidence`.
  `placement_result_adaptive` ahora incluye `profile` y `PlacementResultOut` lo expone.
- **Endpoint** `POST /api/academy/placement/profile` que devuelve `PlacementProfileOut`.
- **Banco de placement ampliado** a las 7 destrezas: 12 ítems nuevos de listening, speaking,
  writing y pronunciation (meta-lenguaje/reconocimiento, sin voz ni audio real — ver nota).

### Cambiado
- `PLACEMENT_VERSION` → `2.0.0`.
- Docstrings de `ability_theta`, `placement_result_adaptive` y `next_placement` reflejan
  "IRT-lite/1PL" y el perfil multiskill.

### Nota
- Los ítems de placement de producción/listening son de opción múltiple de meta-lenguaje o
  reconocimiento (documentado en `PlacementTest`), no evaluación de voz/texto/audio real.
- La estimación IRT de dificultad/discriminación (Joint MLE/EM) queda como siguiente paso;
  hoy solo se persisten contadores observados.

## [1.6.0] — 2026-08-25

Listening 2.0: convierte el listening en un motor con audio como entidad de primer nivel,
vector de dificultad de 8 dimensiones y métrica de automaticidad.

### Añadido
- **Audio como entidad de primer nivel**: `ListeningAsset` ahora modela `audio_id`, `duration`,
  `speaker_id`, `accent`, `speech_rate`, `transcript`, `clean_transcript`, `noise_level` y
  `repetition_policy`, separando el contenido lingüístico del recurso multimedia.
- **Vector de dificultad de 8 dimensiones**: `DIFFICULTY_FACTORS` pasa a
  `speed`/`vocabulary`/`accent`/`syntactic`/`length`/`speaker_count`/`noise`/`connected_speech`.
- **Dificultad derivada por construcción**: `difficulty_from_vector` es la única fuente de verdad
  del escalar `difficulty` (media redondeada clampada a 1..6); `ListeningAsset.difficulty` es
  un campo computado, eliminando la posible incoherencia media↔dificultad.
- **Sub-destrezas ampliadas** (9 nuevas): `speaker_intention`, `fast_speech`, `connected_speech`,
  `dictation`, `shadowing`, `multiple_speakers`, `note_taking`, `prediction`, `sequencing`, con
  ítems nuevos en B1/B2 (`l15`–`l23`).
- **Métrica `automaticity`** (0..1) por sub-destreza y global, derivada de `replay_count` y
  `response_time_ms` como señal de fluidez procesal (no es un score CEFR directo).
- `LISTENING_BANK_VERSION` → `2.0.0`.

### Añadido (cierre de P1 de la auditoría de V1.5.2)
- **`critical_skills` en el perfil CEFR**: nueva `critical_skills(skill_profile)` expone las
  destrezas críticas (grammar/vocabulary) evaluadas por debajo de su mínimo; `CefrProfileOut`
  devuelve ahora `critical_skills` y `get_skill_profile` lo rellena, completando la regla de
  mínimo crítico que antes solo topaba el `overall` sin señalar qué destreza lo provocaba.

### Cambiado
- Frontend (`ListeningPractice`) muestra `automaticity` y metadatos de audio (accent/wpm/duración).

### Nota
- `LEVEL_ORDER` de listening sigue en A1/A2/B1; los ítems B2 existen y se sirven en rotación tras
  dominar A1–B1, pero aún no gatean la progresión por nivel (pendiente de la expansión A1..C2).

## [1.5.3] — 2026-08-25

Release de hardening: cierra los hallazgos de la auditoría externa de V1.5.2 (validez y
trazabilidad). Sin funcionalidad nueva para el alumno.

### Corregido
- **Evidencia inválida ya no se omite en silencio**: `validate_evidence_record` se renombra a
  `evidence_record_errors` (lista de violaciones, vacía = válido) y `_record_evidence_validated`
  ahora registra en logs y lanza `EvidenceInvariantError` (HTTP 500 estructurado) en vez de
  saltarse el registro. Un intento nunca termina "sin evidencia" de forma silenciosa.
- **Docstrings obsoletos**: `services/academy.py` y `services/curriculum.py` ya no afirman que las
  destrezas de producción "aún no integran evidencia"; se distingue auto-scorable (check MC) de
  performance-scorable (rúbrica/LLM), ambas evaluables.
- **Regresión del vector de dificultad de listening**: se fija con tests el invariante de que el
  `difficulty_vector` de cada ítem debe coincidir exactamente con `DIFFICULTY_FACTORS`
  (factor faltante y factor sobrante).

### Añadido
- **Trazabilidad de la sesión de placement**: nueva tabla `placement_sessions` y endpoints
  `POST /api/academy/placement/start` + `session_id` en `/placement/next`. Persiste ítems,
  respuestas, historial de θ y resultado final para reconstruir un resultado CEFR (qué versión,
  qué ítems, qué respuestas, qué θ/SE).
- **Tests de reproducibilidad**: determinismo de placement/evidencia/listening/perfil CEFR y
  monotonicidad de θ (acierto no reduce θ, fallo no lo aumenta).

## [1.5.2] — 2026-08-25

Release de Quality & Validity: sin funcionalidad nueva, endurece la reproducibilidad y la
validez pedagógica de los motores de evaluación (evidencia, CEFR, placement y listening).

### Añadido
- **Versionado de instrumentos de evaluación**: `ASSESSMENT_VERSION`, `PLACEMENT_VERSION`,
  `RUBRIC_VERSION` y `LISTENING_BANK_VERSION` (`services/curriculum.py`). Toda evidencia persiste
  `assessment_version` y `curriculum_version`, de modo que cada resultado es reproducible aunque
  el contenido evolucione.
- **Invariantes de evidencia**: `validate_evidence_record` (`services/academy.py`) valida
  `user_id`/`objective_id`/`skill`/`item_type`/`source`/versiones/`result` antes de persistir;
  todo el dominio pasa por el helper único `_record_evidence_validated`.
- **Semántica CEFR ponderada**: `overall_cefr_score` sustituye la media aritmética por una media
  ponderada por destreza con mínimos críticos (grammar/vocabulary), y el perfil expone las
  sub-destrezas de listening dentro de `listening`.
- **Placement con validez estadística**: selección del ítem por máxima información (Fisher),
  parada por error estándar con mínimo de ítems, desglose multi-destreza del resultado y
  `placement_version` reportado.
- **Listening: first-pass accuracy**: distingue comprensión (acierto a la primera) de aprendizaje
  por repetición, por sub-destreza y global.
- **Listening: banco versionado con vector de dificultad**: `ListeningAsset` + factores
  (`speed`/`vocabulary`/`accent`/`syntactic`/`length`), sub-destreza `attitude` y `bank_version`
  expuesto en el diagnóstico.
- **Tests**: invariantes de evidencia, E2E de regresión (placement/remediación/listening),
  semántica CEFR, validez del placement y arquitectura de listening (450 tests).

### Cambiado
- La revisión de listening (`review_due`) integra la dependencia de repeticiones y el tiempo de
  respuesta, además de la precisión.

## [1.5.0] — 2026-08-25

Evidence & Performance Engine, Listening Engine y Placement adaptativo. Cierra el ciclo
`Evidence → Mastery → CEFR Skill Profile → Remediación → Olvido` para las destrezas de
producción (speaking/writing/pronunciation) y convierte el listening y el test de nivel en
motores adaptativos.

### Añadido
- **Speaking Evidence Engine (V1.3.0)**: scorer determinista CEFR de 6 dimensiones
  (`services/speaking.py`), extracción de evidencia con LLM (`services/speaking_llm.py`,
  el LLM extrae, el scorer puntúa), puente a mastery y endpoints read-aloud/tarea (JSON y
  audio → Whisper).
- **Writing Evidence Engine**: mismo patrón que speaking (rubric de 6 criterios +
  `services/writing_llm.py`), con `writing` declarado en el currículum.
- **Pronunciación fonémica (P6)**: `services/phonemes.py` (grapheme→phoneme ARPAbet +
  precisión de fonemas por Levenshtein), `phoneme_accuracy` expuesto en el evaluador, y
  puente pronunciation → mastery. Declarado `pronunciation` en el currículum.
- **CEFR Skill Profile (V1.3.1)**: `GET /api/academy/profile` devuelve, por destreza,
  `score`/`confidence`/`evidence_count`/`last_evidence`/`review_due`.
- **Remediación adaptativa (V1.3.2)**: `GET /api/academy/remediation` devuelve las destrezas
  débiles y sus objetivos; el AI Teacher lee el perfil CEFR en su system prompt.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (curva de olvido exponencial,
  `retrieval_probability` y `review_due` real en función del tiempo, sustituyendo la
  heurística por umbral).
- **Listening Engine**: sub-destrezas (`gist`/`detail`/`inference`/`vocabulary`/`numbers`) y
  dificultad en el banco, métricas (`response_time_ms`, `replay_count`), diagnóstico
  adaptativo (`GET /api/listening/diagnostic`) y panel en el frontend.
- **Placement Engine adaptativo (V1.5)**: IRT-lite (estimación de habilidad θ, selección de
  ítem por dificultad más cercana a θ) con `POST /api/academy/placement/next` (flujo stateless).
- **UI**: favicon de la app y selector de modelo IA con favorito integrado en el desplegable.

### Cambiado
- Currículum: `writing` y `pronunciation` declarados en los objetivos de A1/A2;
  `CURRICULUM_VERSION` → `1.2.5`.
- Listening pasa de banco plano a motor con sub-destrezas y diagnóstico.
- Placement pasa de scoring por bandas a estimación adaptativa de habilidad (θ).

## [1.2.2] — 2026-08-25

Hardening de la Academy antes del Evidence & Performance Engine (V1.3). Sin funcionalidad nueva:
refuerza la seguridad del gating curricular, elimina deuda de hardcodes y consolida la
documentación/versionado.

### Añadido
- **Gating de lectura del detalle de nivel**: `GET /api/academy/levels/{level_id}` devuelve
  `403` para niveles bloqueados (prerequisito no completado) y `404` solo para niveles
  inexistentes, alineado con `enroll`/`submit_exam`.
- **Invariante curricular ampliada a todos los niveles** (`load_all_levels`): cada objetivo
  valida `can_do`, destrezas canónicas, umbrales válidos y `minimum_attempts ≥ 1`, y sus checks
  cubren exactamente sus destrezas evaluables.
- **Test de migración** `academy_certificates → academy_level_completions` (copia filas y elimina
  la tabla antigua).

### Cambiado
- **UI de Academy sin hardcodes `"a1"`**: el examen usa el nivel seleccionado
  (`getExam(selectedLevel.level_id)` / `submitExam(...)`), con textos dinámicos
  ("Examen final A2", "Evaluación A2 superada") y cabecera "Currículum CEFR · A1 → C2".
- **Documentación y versionado consistentes**: `README`, `PLAN`, `docs/RELEVO`,
  `docs/ARQUITECTURA` y `package-lock.json` actualizados a `1.2.2`; arquitectura reescrita con
  la estructura real de la Academy.

## [1.2.1] — 2026-08-25

Integridad curricular de la Academy y apariencia configurable. Refuerza el modelo de mastery
determinista (evidencia repetida + decay + gating) y corrige la semántica de "certificado".

### Añadido
- **Gating CEFR estricto**: `enroll()` y `submit_exam()` exigen el nivel anterior completado
  (A1 → A2 → B1 → ...); el examen no puede saltarse la progresión.
- **Mastery por objetivo**: clave `(user, level, objective, skill)`; el dominio de una destreza
  en un objetivo no se contagia a otros objetivos que compartan destreza.
- **Mínimo de evidencias**: `minimum_attempts = 3`; un único acierto ya no marca un objetivo
  como dominado (evidencia + consistencia antes que mastery).
- **Decay del mastery**: sustituye `MAX(score, new)` por EMA (`recent_score`) + `confidence` +
  `streak`; el dominio puede bajar si el rendimiento reciente empeora.
- **Separación knowledge/performance**: `ASSESSABLE_SKILLS` (grammar/vocabulary/reading/listening)
  gatean el dominio; `PERFORMANCE_SKILLS` (speaking/writing/pronunciation) quedan a la espera de
  evidencia de rendimiento real.
- **Listening con progresión**: `current_level()`/`level_status()`/`pick_next_question()` avanzan
  A1→A2→B1 por dominio de preguntas (fix del bug de "se queda en 12 aciertos").
- **Apariencia configurable (M16)**: tema claro/oscuro, acento (7 colores), tamaño de letra y
  densidad; persistido por usuario (`settings` + `localStorage`). Botón de ayuda (`HelpDialog`).

### Cambiado
- **`certificates` → `level_completions`** (tabla + endpoint + esquemas + UI), con migración
  idempotente `academy_certificates → academy_level_completions`.
- **Semántica honesta del examen**: "Evaluación A1 superada" (y explícita que no mide producción
  oral/escrita), en lugar de un "certificado" que el sistema aún no puede emitir.

### Corregido
- Bloqueo de progresión: `objective_progress` solo exige las destrezas con evidencia determinista
  (`assessable_skills`), desbloqueando la cadena de gating.

## [1.2.0] — 2026-08-25

Academy curricular: A1/A2 funcional de extremo a extremo con mastery por objetivo y desbloqueo
secuencial. Corrige el bloqueo pedagógico detectado en la auditoría: las destrezas de producción
(speaking/writing/pronunciation) ya no impiden dominar un objetivo hasta que exista evidencia real
de rendimiento.

### Añadido
- **Academy (curriculum CEFR)**: módulos/unidades/lecciones/objetivos `can_do` para A1 y A2, motor
  de mastery determinista por `(user, level, objective, skill)`, `minimum_attempts` (evidencia
  repetida), gating curricular secuencial y selección adaptativa del siguiente objetivo
  (`adaptive_next`).
- **Evaluación determinista**: checks de opción múltiple (`ObjectiveCheck`) para todos los objetivos
  de A1/A2, cubriendo sus destrezas evaluables (grammar/vocabulary/reading/listening).
- **Placement, examen final y certificados**: test de nivel CAT-lite, examen de nivel por destreza y
  certificado de nivel con desbloqueo en cascada del siguiente nivel.
- **Invariante de currículum** en tests: todo objetivo debe tener checks que cubran exactamente sus
  destrezas evaluables (impide regresiones futuras).

### Corregido
- **Bloqueo de progresión**: `objective_progress` exigía dominio de *todas* las skills (incluido
  speaking, sin vía de evidencia), por lo que ningún objetivo podía dominarse y el gating bloqueaba
  toda la Academy. Ahora solo gatean las destrezas con evidencia determinista (`assessable_skills`),
  dejando speaking/listening/writing como metas de rendimiento pendientes de un pipeline real.
- **Semántica del examen**: el resultado pasa de "¡A1 superado!" a "Evaluación A1 superada",
  explicitando que no mide producción oral/escrita.

## [1.1.1] — 2026-08-24

Release Audit 1.1: corrección de los 6 puntos señalados por la auditoría externa antes de
congelar la arquitectura. Sin funcionalidad nueva; se endurece la coherencia del API, la
semántica pedagógica y la cobertura de aislamiento multiusuario. (Nota: la fluidez ya estaba
expuesta como `FluencyStats` desde F8; se verificó y no requirió cambios de código.)

### Cambiado
- **Identidad unificada (`current_user`)**: `chat`, `chat/stream`, `conversations` (create/list),
  `pronunciation`, `vocabulary`, `grammar` y `learning` resuelven el perfil vía
  `Depends(current_user)` en lugar de confiar en un `user_id` enviado por el cliente. Se añade
  `current_user_optional` para el chat sin perfil. Coherencia total del API en endpoints sensibles.
- **Renombrado "CEFR estimate"**: los campos `cefr_level`/`cefr_bands`/`cefr_descriptor` pasan a
  `estimated_level`/`estimated_bands`/`estimated_descriptor` (backend + frontend), dejando claro
  que es un nivel estimado heurístico y no una certificación CEFR.
- **Semántica de vocabulario**: `occurrences` → `appearances` (número de mensajes en que aparece
  la palabra, no de veces), con migración idempotente de la base de datos existente.
- **Gramática con confianza**: cada hallazgo incorpora `confidence`, `source` y `confirmed`; el
  prompt del tutor solo usa errores `confirmed`, evitando que falsos positivos contaminen el
  Learning Profile.
- **Selector de perfil**: al iniciar con varios usuarios ya no se auto-selecciona el primero; se
  muestra "Selecciona perfil" (`resolveInitialUserId`).

### Añadido
- **Tests de aislamiento cross-user**: batería explícita que verifica que un usuario nunca ve ni
  modifica los datos de otro (conversaciones, vocabulario, gramática, pronunciación, listening,
  eventos y perfil).
- **Tests del prompt/contexto**: verifica que el prompt personalizado incluye solo los errores del
  propio usuario y no filtra datos de otros perfiles.

## [1.1.0] — 2026-08-24

Primera release estable tras el plan de endurecimiento (Fases 1–10). Añade seguimiento
pedagógico real, pronunciación fonética, listening/CEFR, evaluación objetiva del tutor y un
lanzador de escritorio.

### Añadido
- **Lanzador de escritorio** (`launcher/`, GUI `tkinter` sin dependencias nuevas): arranca y
  detiene la app (backend + frontend) y muestra el estado de los servicios, la base de datos
  y los usuarios. Acceso directo del escritorio con icono (`install_shortcut.ps1`).
- **Versión unificada** `1.1.0` expuesta en `/api/health` y en `/`.
- **Progreso pedagógico real (F6)**: eventos de aprendizaje, historial con tendencias, racha,
  dominio de errores e hitos (`GET /api/progress/history`).
- **Pronunciación fonética (F7)**: evaluador compuesto (palabras + Soundex + caracteres) y
  feedback fonético en el frontend.
- **Listening / Speaking / CEFR (F8)**: banco de preguntas de comprensión auditiva, fluidez
  oral (WPM) y evaluación CEFR multi-señal con bandas por destreza.
- **Evaluación objetiva del tutor (F9)**: evaluador determinista sin LLM-juez (backend, puro),
  informe agregado + script por lotes (`scripts/eval_tutor.py`) y panel de calidad en el frontend.

### Cambiado
- El resumen de progreso (`ProgressSummary`) se sustituye por el dashboard de progreso real.
- El CEFR deja de ser una heurística plana: ahora es multi-señal con descriptor.

## [1.0.0] — 2026-08 (release inicial)

Primera versión pública: tutor de inglés 100% local con chat por texto y voz (Ollama +
faster-whisper + piper-tts), modos de tutor, multi-usuario y diseño responsive.

# v3.19.0 — Léxico por destreza + Speaking micro-drill

**El candidato V3.19 (definido 2026-09-07 sobre el pendiente heredado de v3.18 y la auditoría profunda V3.18) se cierra: la producción del alumno se vuelca al léxico etiquetada por destreza (contadores por columna, invariante `sum == appearances`), `recognized_not_produced` pasa a ser la señal real "expuestas y nunca dichas" con un micro-drill de 1 nivel honesto sobre el scorer de pronunciación, y entran los fixes P1 del dossier (R6-01, GATE-01, CLAIM-01, SIGNAL-01, ERR-01, LIST-01/02/03, CONV-01) más la deuda externa ADMIN-01 y BOOL-01.**

## Qué cambia

- **La producción llega al léxico por destreza (P0).** `record_words` se generaliza a `record_production(user, words, channel)` y cada superficie de producción vuelca el texto del alumno por un único helper compartido (`_capture_production_text`/`record_production_text`, fire-and-forget): speaking assessment/misión/routes/task, pronunciación libre y rutas, conversación guiada (texto reconstruido de los turnos) y el micro-drill. La tabla `vocabulary` gana 4 contadores (`chat_prod`/`speaking_prod`/`writing_prod`/`conversation_prod`) con backfill idempotente `chat_prod = appearances`. La semántica de `appearances`/`production_days`/`item_status`/`coverage_indicator` no cambia.
- **Speaking micro-drill honesto (P1, sin claims D5/E3).** Los candidatos son las palabras expuestas (`exposures > 0`) que el alumno nunca ha producido en práctica de speaking (`speaking_prod == 0`), ordenadas por recuerdo y servidas por endpoint determinista (`GET /api/vocabulary/drill/candidates`). `POST /api/vocabulary/drill/attempt` reusa el scorer de pronunciación: al producir la palabra (`ok` y en `breakdown.correct`) se marca como producida por speaking y sale de la lista; no crea evidencia curricular ni cartas FSRS. En `PersonalDictionary` los chips inertes ganan la acción de practicar (con estado de error + reintento, A6-03).
- **Retención R6 impuesta en servidor (R6-01).** `start_assessment_v2(kind="retention")` y el submit exigen ventana ≥ `RETENTION_MIN_DAYS` (7) desde la sesión formal origen y ratio estable ≥ `RETENTION_STABLE_RATIO` (0.9) antes de escribir evidencia `delayed`; si no, `RetentionNotDueError` → HTTP 409. La CONSTITUCIÓN §6.3 deja de ser letra muerta.
- **Objetivos `locked` no evaluables (GATE-01).** `_ensure_objective_evaluable` valida en dominio (punto único) que el objetivo no esté `locked` antes de evaluar/completar en los 8 writers; `ObjectiveLockedError` → HTTP 409 (premisa 21).
- **Copy honesta del nivel oral (CLAIM-01 + SIGNAL-01).** Speaking/Pronunciation/Conversation re-etiquetan sus paneles al esquema de Listening — "nivel oral actual (examen)" con calificador estimado, nunca "demostrado" sin un gate real — y la pista del diccionario pasa a "aún no producida en práctica de speaking".
- **Fallo transitorio del extractor = 503 (ERR-01).** Misiones/assessment/task propagan `EvidenceExtractionError` como las rutas: 503 reintentable, reservando el 404 a estados reales.
- **Listening: tokens de foco servibles + corpus honesto (LIST-01/02/03).** `word_recognition`/`sound_recognition`/`phrase_recognition` entran en `LISTENING_SUBSKILLS` (test ≥1 ítem servible por nivel), la muestra A1/B1 se re-etiqueta donde el guion no respaldaba la etiqueta, los pares cuasi-duplicados c031/c086 y c027/c079 se resuelven re-autorando un miembro y la unicidad de `script` normalizado queda validada.
- **Conversación guiada sin tiempo de redacción fingido (CONV-01).** La conversación guiada es un mini-chat tecleado (`mode="conversation"`): `_student_speech_seconds` y la señal objetiva de interacción reconstruyen por `mode` y ya no computan `duration_ms`/`latency_ms` de redacción como turno oral (`turn_duration`/latencia no observadas; el balance de turnos y el volcado al léxico se conservan). `get_turns` expone `mode`; `interaction_evidence` acepta `typed_modes`.
- **Deuda de auditoría externa.** **ADMIN-01**: `ADMIN_PIN=""` ⇒ los endpoints admin quedan deshabilitados (401) — secure-by-default, nunca fail-open. **BOOL-01**: `unit_review.py` endurece a `type(selected) is int` (`True`/`False` ya no puntúan como índice).

## Técnica

- Backend (`3.18.0 → 3.19.0`, fuente única `backend/config.py`):
  - `repositories/db.py`: migración idempotente de 4 columnas de producción + backfill `chat_prod = appearances`.
  - `repositories/vocabulary.py`: `record_production(user, words, channel)` (generaliza `record_words`); `get_vocabulary` con las nuevas columnas.
  - `domain/vocabulary.py`: `analyze_text(channel="chat")` + `record_production_text`; `get_lexicon` ampliado; `drill_candidates`/`submit_drill_attempt` de dominio.
  - `domain/academy.py`: helpers `_capture_production_text` (punto único), `_ensure_objective_evaluable` (GATE-01), enforcement R6-01 en `start/submit_assessment_v2`, propagación `EvidenceExtractionError` (ERR-01) y volcado en los 7 writers.
  - `domain/speaking_routes.py`/`pronunciation_routes.py`/`conversation_routes.py` (+`routers/pronunciation.py` legacy): volcado `channel="speaking"/"conversation"`.
  - `services/lexicon.py`: `drill_candidates` (semántica oral) sobre `speaking_prod == 0`.
  - `services/listening.py`: `LISTENING_SUBSKILLS` + `normalized_script_key` + unicidad en `validate_listening_bank`.
  - `services/interaction.py`: `interaction_evidence(..., typed_modes=...)` (CONV-01); `repositories/conversations.py::get_turns` con `mode`.
  - `services/unit_review.py`: `type(selected) is int` (BOOL-01); `dependencies.py::require_admin` fail-closed (ADMIN-01).
  - `domain/errors.py`/`main.py`: `RetentionNotDueError`/`ObjectiveLockedError` → 409.
  - `schemas/vocabulary.py`/`routers/vocabulary.py`: `LexicalItemOut` +4 campos, `DrillCandidatesOut`, endpoints drill GET/POST.
  - Tests: migración/backfill, `record_production` canales mixtos (invariante `sum == appearances`), `drill_candidates`, HTTP "exponer → drill → producir → sale de la lista", rechazos R6-01/GATE-01 (409), ERR-01 (503), ADMIN-01 fail-closed, BOOL-01 bool-as-int, LIST unicidad/servibles, CONV-01 por `mode`.
- Frontend:
  - `api/vocabulary.ts`: `getDrillCandidates`/`submitDrillAttempt`; `types/api.ts` espejo (+4 `_prod` y tipos drill).
  - `features/vocabulary/PersonalDictionary.tsx`: chips con acción de micro-drill (micrófono + feedback de pronunciación), estado de error + reintento, refresco al producir.
  - `features/vocabulary/dictionary.ts`: se elimina el recálculo cliente de la señal (ahora es endpoint determinista).
  - `utils/i18n.ts`: claves es/en del drill y copy corregida de SIGNAL-01/CLAIM-01 (`speaking.*`, `pronRoutes.*`, `convRoutes.*`, `dictionary.recognizedNotProduced*`); parity automática.
  - `utils/learningLabels.ts`: etiquetas de `word_recognition`/`sound_recognition`/`phrase_recognition`.
  - Tests: `PersonalDictionary.test.tsx` (candidatas, error+reintento, flujo completo drill), `dictionary.test.ts`, `vocabulary.test.ts`.
- Sin cambios de CONSTITUCIÓN pedagógica (R8/R9 siguen como propuesta abierta). Fuera de alcance documentado como decisión (b)/futura: micro-drill de 3 niveles + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo, WR-UI-01, siembra FSRS sin señal (LEX-03).

## Tests

- Backend: **1371 pytest en verde**; `ruff check .` limpio.
- Frontend: **417 vitest en verde** (53 archivos) y build de producción (`tsc` + `vite build`) OK.
- `scripts/check_release_consistency.py` exit 0 (3.19.0); CLI curriculum `--strict --quality` exit 0; i18n parity verde.

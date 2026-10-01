# v3.23.0 — Student Model Calibration (parte 2): Retention real y Transfer por contexto

**El plan V3.23 (dossier de la auditoría externa V3.22.0) cierra los dos P1 pedagógicos restantes del Student Model léxico sobre la base de los quick fixes de esa misma auditoría: la retención deja de acreditarse por exposición/producción espaciada y exige **recuperación correcta demorada** (éxito de micro-drill ≥ `RETENTION_MIN_INTERVAL_DAYS` después del ancla), y la transferencia se mide por **contexto real de actividad** (`channel:activity`) en lugar de solo por canal. Se mantiene señal ≠ evidencia (D5/E3).**

## Qué cambia

- **P1-02 — Retention = recuperación demorada (no exposición espaciada).** Migración idempotente en `vocabulary`: columnas `retrieval_successes` (INTEGER NOT NULL DEFAULT 0), `retrieval_days` (INTEGER NOT NULL DEFAULT 0) y `last_retrieval_at` (TEXT NOT NULL DEFAULT ''). **Sin backfill** (documentado en el código): el histórico V3.22 backfilleó `first_exposed_at = last_exposed_at`, por lo que una ancla retrospectiva sería injusta — los contadores empiezan en V3.23 (mejor perder evidencia que inventarla).
  - `record_retrievals(user_id, words)`: para cada palabra, si `(hoy - ancla) >= RETENTION_MIN_INTERVAL_DAYS` — ancla = `min(first_exposed_at, first_seen)` (parte fecha) — suma `retrieval_successes += 1`; si el día de `last_retrieval_at` es distinto de hoy suma `retrieval_days += 1`; y fija `last_retrieval_at = now`. Ignora en silencio si falta ancla o no cumple el intervalo. Import local de la constante desde `services.lexicon` (sin dependencia de import entre capas).
  - Hook de recuperación **solo en el micro-drill** (decisión del gerente): `submit_drill_attempt` si `produced` y `submit_sentence_attempt` si `passed`, tras el volcado `speaking`; `_record_retrieval` nunca lanza. No toca `learning_events` del router.
  - En `item_competence_matrix`: `retention = retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS`. `_spaced_exposure`/`_spaced_production` pasan a señales **independientes** (`spaced_exposure`/`spaced_production`): informan (exposición/producción en días distintos) pero ya no certifican retención. `summary` añade el contador informativo `spaced_exposure`; el contador `retention` pasa a la nueva semántica. La UI no renombra chips; la tooltip del diccionario se actualiza a "retention = recuperación demorada (recordada en un drill tras un intervalo)" (en/es).
- **P1-04 — Transfer por contexto de actividad (no solo canal).** Migración `context_tags` (TEXT NOT NULL DEFAULT ''): CSV canónico `channel:activity`, único y ordenado.
  - `record_production(user_id, words, channel, activity=None)`: al escribir, si `activity` dado, fusiona el tag `f"{channel}:{activity}"` en `context_tags` (merge canónico ordenado y único; `record_words` y los callers sin `activity` no cambian).
  - Propagación de `activity` por la capa de dominio: `record_production_text(..., activity=None)` y `_capture_production_text(..., activity=None)`. Mapeo por superficie en los 7 puntos de `academy.py` (assessment→`speaking_assessment`, misión→`speaking_mission`, checks controlados→`speaking_controlled`/`writing_controlled`, tareas LLM→`speaking_task`/`writing_task`, pronunciación de objetivo→`read_aloud`), chat libre→`free_chat`, drill palabra/frase→`drill` (canal `speaking`), rutas speaking→`speaking_route`, read-aloud rutas→`read_aloud`, pronunciación suelta (`routers/pronunciation.py`)→`drill`, conversación guiada→`guided_conversation`.
  - `production_contexts(row)` (pura): tags explícitos de `context_tags` + fallback `channel:other` por canal con `<channel>_prod > 0` sin tag explícito (histórico legacy; un canal con tag explícito NO recibe `other`). Orden canónico (`ACTIVITY_CHANNEL_ORDER`: chat → speaking → writing → conversation) + actividad alfabética, determinista. `transfer_contexts = len(production_contexts(row))`, `transfer = transfer_contexts >= 2`. Dos actividades distintas del mismo canal (p. ej. `speaking:drill` + `speaking:speaking_route`) cuentan como 2 contextos; `chat` y `conversation` guiada dejan de colapsar en un mismo canal.
- **Quick fixes base (auditoría externa V3.22).** P1-01: `item_recall` usa la actividad más reciente (`_last_activity_at`, max de `last_seen`/`last_exposed_at`), no solo `last_seen`. P1-03: `item_mastery` pondera el reconocimiento con `RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6 sobre `exposure_days` (el volumen por sí solo no satura el reconocimiento) y `classify_asr_status` comprueba el silencio alucinado (`no_speech`) ANTES de `low_confidence`, de modo que una alucinación de silencio con logprob bajo nunca se penaliza como confianza baja.
- **Contratos.** `LexicalCompetence` gana `spaced_exposure`/`spaced_production` (bool) y `retrieval_successes`/`retrieval_days` (int); `LexiconSummary` gana `spaced_exposure` (int). Espejo en `frontend/src/types/api.ts` y `frontend/src/utils/i18n.ts` (tooltip). `LexicalCompetence` conserva `production_channels` (canales) y añade la semántica de contextos solo en `transfer_contexts`/`transfer`.

## Técnica

- Backend (versión de app `3.22.0 → 3.23.0`, fuente única `backend/config.py`):
  - `repositories/db.py`: migración idempotente `retrieval_successes`/`retrieval_days`/`last_retrieval_at`/`context_tags`.
  - `repositories/vocabulary.py`: `record_production(..., activity)` con `_merge_context_tag`, nueva `record_retrievals`, `get_vocabulary` con el `SELECT` ampliado.
  - `domain/vocabulary.py`: `analyze_text` (`free_chat`), `record_production_text(..., activity)`, hook `_record_retrieval` en `submit_drill_attempt`/`submit_sentence_attempt`. `domain/academy.py` + `speaking_routes.py`/`pronunciation_routes.py`/`conversation_routes.py` + `routers/pronunciation.py`: mapeo de `activity` por superficie.
  - `services/lexicon.py`: constantes `RETENTION_MIN_INTERVAL_DAYS`/`RETENTION_MIN_RETRIEVAL_DAYS`, `_retrieval_days`/`_retrieval_successes`, `production_contexts`, matriz con retención por recuperación y señales espaciadas independientes, `summary` con `spaced_exposure`.
  - `schemas/vocabulary.py`: contratos nuevos.
- Frontend: `types/api.ts` y `utils/i18n.ts` (tooltip) + mock del test del diccionario.

## Tests

- Backend: **1455 pytest en verde** (nuevos casos de `record_retrievals` con/sin intervalo, dedupe por día, sin ancla ignorado, migración V3.23 sin backfill; `production_contexts` con tags + fallback; retención con contadores; transfer por dos actividades del mismo canal; `summary` con `spaced_exposure`); `ruff check .` limpio.
- Frontend: **450 vitest en verde** (57 archivos); `tsc --noEmit` y `vite build` OK.
- `scripts/check_release_consistency.py` exit 0 (3.23.0); curriculum `--strict --quality` y content validation OK; paridad i18n en verde (1232 definidas); CONSTITUCIÓN sin cambios.

## Fuera de alcance (fronteras documentadas)

- `support_level` por evento (copied/guided/cued/independent/spontaneous): inferible tras el mapeo de actividades, se deja para V3.24.
- Backfill de contadores de retrieval desde `learning_events` históricos (anclas no fiables en pre-V3.22).
- Superficie nueva de "recuerdo de significado" (MC ligado a unidad léxica): requiere campo de palabra en los checks del currículo.
- Renombre `appearances → production_count` (deuda V3.22, sin migración destructiva).

# v3.22.0 — ASR Calibration + Student Model (léxico)

**El plan V3.22 (dossier de la auditoría externa V3.21.0) se cierra en dos frentes: el ASR deja de leer métricas de `TranscriptionInfo` (donde faster-whisper no las expone) y las agrega desde los `Segment`, con una política de clasificación explícita que hace alcanzables `no_speech` y `low_confidence` y que además reconoce el texto alucinado sobre silencio como no-habla (nunca penalizable); y el Student Model separa Retention de Transfer en la matriz de competencia léxica — `exposure_days`/`first_exposed_at` para retención receptiva, transferencia = producción en 2+ contextos — con `production_gap` y `transfer_gap` independientes. Se mantiene señal ≠ evidencia (D5/E3).**

## Qué cambia

- **ASR-01 — Calibración ASR por segmentos (P1-01/02/03).** En faster-whisper 1.2.1 las métricas de confianza viven en cada `Segment` (`avg_logprob`, `no_speech_prob`, `compression_ratio`), no en `TranscriptionInfo` (solo `language_probability`/`duration`). V3.21 las leía con `getattr(info, ...)`: el estado `no_speech` era inalcanzable (todo audio vacío caía en `unintelligible`) y `low_confidence` inalcanzable (todo texto caía en `ok`).
  - `aggregate_asr_segments(segments, info)` (puro, determinista, duck-typed para tests con fakes ligeros) materializa los segmentos y agrega `mean_logprob`/`min_logprob` (media ponderada por duración de segmento), `max_no_speech_prob`, `no_speech_ratio` (fracción de la señal decodificada con `no_speech_prob ≥ 0.6`), `speech_ratio`, `compression_ratio` medio, `segment_count`, `language_probability` y `duration`. Sin segmentos → `segment_count = 0` y el resto en `None`.
  - Nueva firma `classify_asr_status(*, text, metrics)` con política explícita: sin texto y `segment_count == 0` → `unintelligible` si el audio es < `MIN_SPEECH_ATTEMPT_SECONDS` (0.5 s) o no se midió (captura fallida), y `no_speech` si hay audio medible (Whisper descartó todo); `segment_count > 0` sin texto → `unintelligible` (defensivo). Con texto: `mean_logprob < -1.0` → `low_confidence`; **alucinación de silencio** (medida real: silencio digital decodifica "You" con `no_speech_prob` 0.85 y logprob −0.91) → si `max_no_speech_prob` alto y `no_speech_ratio ≥ 0.5` el texto es no-habla → `no_speech` (no se penaliza); el resto → `ok`.
  - `transcribe_with_timing` materializa `list(segments_gen)` (sin `list()` no hay métricas por segmento) y emite el contrato intacto (`text/duration/asr_status/confidence`, aliases `avg_logprob`/`no_speech_prob` = agregados) más telemetría nueva: `segment_count`, `mean_logprob`, `min_logprob`, `max_no_speech_prob`, `no_speech_ratio`, `speech_ratio`, `compression_ratio`. Los routers solo consumen `text/duration/asr_status/confidence`: el gating `asr_status != "ok"` es transparente y no cambia. `compression_ratio`/`language_probability` se emiten como señal para el Student Model; `LANGUAGE_MISMATCH` queda como frontera documentada (no clasifica aún).
- **P1-04 — Retention ≠ Transfer en la matriz léxica.** Migración idempotente en `vocabulary`: columnas `exposure_days` (INTEGER NOT NULL DEFAULT 0) y `first_exposed_at` (TEXT NOT NULL DEFAULT '') con backfill (`exposure_days = 1` y `first_exposed_at = last_exposed_at` donde `exposures > 0`). `record_exposures` pasa de `executemany` a bucle por fila (como `record_production`): suma `exposure_days` solo cuando la exposición cae en un día distinto al de `last_exposed_at` y fija `first_exposed_at` en el alta. En `services/lexicon.py`: `_spaced_exposure(row)` (≥ 2 días de exposición y hueco ≥ 1 día entre `first_exposed_at`/`last_exposed_at`), y la matriz deja de igualar `retention = transfer`:
  - `transfer` = `transfer_contexts >= 2` (producción en 2+ canales/contextos). Se elimina el `or spaced`: el espaciado pasa a ser señal de retención.
  - `retention` = `_spaced_exposure(row) or _spaced_production(row)` (recuerdo tras intervalo, receptivo o productivo).
- **P1-05 — Gaps independientes.** La clave `gap` (reconocida-nunca-producida) pasa a llamarse `production_gap` (es el gap que cierra el speaking micro-drill) y se añade `transfer_gap` = `recognition and production and not transfer` (producida en ejercicios pero nunca usada en otro contexto). `summary` desglosa los 6 contadores (`recognized/produced/transfer/retention/production_gap/transfer_gap`). La lista de candidatas del drill no cambia: depende de `exposures`/`speaking_prod`/`ok_days`, no de la matriz. El renombre `appearances → production_count` sigue como deuda documentada (sin migración destructiva); `test_fsrs_transfer_gap.py` y `services/fsrs.py` (razón `transfer-gap` a nivel de objetivo FSRS) NO se tocan: es semántica distinta de la matriz por ítem.
- **Contratos y UI.** `LexicalCompetence` (claves `transfer_contexts`, `production_gap`, `transfer_gap`; fuera `gap`) y `LexiconSummary` (`production_gap` + `transfer_gap`) en schemas y `types/api.ts`. El diccionario personal (`PersonalDictionary.tsx`) muestra **6 contadores** — Recognized · Produced · Transfer · Retention · Production gap · Transfer gap — con rejilla `sm:grid-cols-3 lg:grid-cols-6`; la copia de `dictionary.competenceHint` explica transfer (2+ contextos) y retention (espaciada) y se añade la clave `dictionary.competenceProductionGap` (en/es). Claves `asr.message.*` intactas.

## Técnica

- Backend (versión de app `3.21.0 → 3.22.0`, fuente única `backend/config.py`):
  - `services/stt.py`: `aggregate_asr_segments` + `classify_asr_status(*, text, metrics)` + `transcribe_with_timing` materializando segmentos y emitiendo telemetría; constantes `MIN_SPEECH_ATTEMPT_SECONDS`/`NO_SPEECH_RATIO_HALLUCINATION_THRESHOLD`.
  - `repositories/db.py`: migración idempotente `exposure_days`/`first_exposed_at` con backfill. `repositories/vocabulary.py`: `record_exposures` con días distintos de exposición y `SELECT` ampliado.
  - `services/lexicon.py`: `_spaced_exposure`, `transfer_contexts`, transfer/retention independientes, `production_gap`/`transfer_gap`, `summary` desglosado. `schemas/vocabulary.py`: contratos nuevos.
- Frontend: `features/vocabulary/PersonalDictionary.tsx` (6 chips de competencia), `types/api.ts`, `utils/i18n.ts` (copia + `competenceProductionGap`).

## Tests

- Backend: **1440 pytest en verde** (nueva `test_stt_asr_integration.py` opt-in — Whisper real: silencio nunca `ok`, voz piper `ok` —, batería ASR reescrita con la firma `metrics` y casos de independencia transfer/retention en `test_lexicon.py`/`test_vocabulary.py`); `ruff check .` limpio.
- Frontend: **450 vitest en verde** (57 archivos); `tsc --noEmit` y `vite build` OK.
- `scripts/check_release_consistency.py` exit 0 (3.22.0); paridad i18n en verde; CONSTITUCIÓN sin cambios.

## Fuera de alcance (fronteras documentadas)

- Telemetría persistente de calidad ASR en el Student Model (necesita tabla/columnas por intento): se emiten ya las señales para una fase posterior.
- `LANGUAGE_MISMATCH` como estado ASR (no penalizador).
- Renombre `appearances → production_count` y preparación Recall → Sentence → Context → Free Transfer.
- El paso Sentence duplicando `speaking_prod` (semántica "acto de producción", documentada en V3.21).

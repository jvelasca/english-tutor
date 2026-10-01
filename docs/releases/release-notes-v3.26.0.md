# v3.26.0 — Hoja de ruta completa: retención longitudinal, emisor real de `novel`, historia léxica, Listening real y calibración CEFR

**V3.26 cierra la hoja de ruta derivada de las auditorías externas V3.24 y
V3.25 (dossiers `docs/audit/L-AUDITORIA-TOTAL-V324.md` y
`docs/audit/M-AUDITORIA-TOTAL-V325.md`): los P2 de los tres ejes pendientes —
retención longitudinal y semántica initial/practice del gate (P2-01/P2-02),
emisor real del kind `novel` + historia léxica por superficie (F-L11/P2, M-F5),
Listening real recognition/comprehension/inference (P2-04) y calibración CEFR
unificada de extremos (P2-03) — más la mejora de UI que muestra el motivo de
bloqueo por destreza (M-F4) y la marca de evidencia legacy sin `context_id`
(M-F2). Verificación íntegra local: pytest backend **1538 passed** + ruff;
vitest frontend **450 passed** (57 archivos) + tsc; CI GitHub Actions success;
`check_release_consistency` 3.26.0 exit 0.**

## Qué cambia

### Eje A — Gate MASTERED y retención longitudinal (F-A1/F-A2/F-A3)

- **F-A1 — `initial` vs `practice` espaciado en el gate MASTERED.** El gate
  deja de tratar todo `familiar` como "práctica": `initial` = un primer
  encuentro por contexto, `practice` = re-encuentros del **mismo** contexto
  separados ≥ `SPACED_PRACTICE_MIN_DAYS` desde su primer encuentro (una sesión
  que emite varias filas el mismo día no infla el contador). Solo cuentan filas
  con `context_id` y `created_at` parseables; las filas legacy no demuestran
  espaciado y quedan fuera (el llamador decide el fallback).
- **F-A2 — Anclaje de cada `delayed` a su origen formal.** El reporte separa
  `event_age_days` (edad del evento respecto a `now`) de
  `retention_interval_days` (intervalo pedagógico formal→delayed). Cada evento
  `delayed` se ancla a la sesión formal que lo originó (`source_session_id` vía
  `delayed_origin_anchors`), de modo que los re-intentos del examen no acortan
  artificialmente las ventanas.
- **F-A3 — Retención longitudinal multi-punto (certificación).** El nivel ya
  no certifica con un único reassessment: exige **≥2 eventos `delayed`
  estables por destreza**, cada uno ≥ `RETENTION_MIN_DAYS` desde su origen y
  con ratio ≥ `RETENTION_STABLE_RATIO`
  (`CERTIFICATION_REQUIRED_DELAYED = 2`). Además se arregla la retención
  **sobre exámenes `kind=level`**: sus ítems no viven en el índice curricular
  de checks, así que el escritor resolvía `correct_index` a `None` y nunca se
  escribía evidencia `delayed` por esa vía (la certificación por la escalera era
  inalcanzable end-to-end). Ahora el retention que re-evalúa un `kind=level`
  resuelve la clave correcta vía el examen, y cada nuevo reassessment se espacia
  ≥ `RETENTION_MIN_DAYS` desde el último del mismo origen (409 si no se cumple).

### Eje B — Emisor real de `novel` + historia léxica por superficie (F-B1/F-B2)

- **F-B1 — Emisor real del kind `novel`.** `novel` deja de ser un kind
  reservado y gana un emisor: la **primera misión por escenario B2+ jamás
  practicada** por el alumno (detección evidence-only sobre `academy_evidence`
  con el contexto canónico `mission:{escenario}`, vía `mission_context_practiced`)
  escribe evidencia `novel` (`mission_evidence_kind`, `services/speaking.py`).
  Retries y repeticiones del mismo escenario escriben `familiar`
  (anti-bombeo: cada escenario produce `novel` una sola vez). Decisión de
  negocio: **no se reactiva el requisito** — `novel_required = 0` en la matriz y
  el gate MASTERED intactos; la activación calibrada de B2+ queda documentada
  como deuda abierta para la siguiente fase.
- **F-B2 — Historia detallada de eventos léxicos.** Nueva tabla `vocabulary_events`
  append-only (`word`, `lexical_unit`, `event_type` `produced|exposed|retrieval`,
  `channel`, `activity`, `created_at`), escrita en la **misma transacción** de
  los 4 writers de `repositories/vocabulary.py` (sin doble fuente de verdad;
  invariantes de contadores intactos). SIN backfill: la historia empieza en
  V3.26 y los contadores conservan el histórico agregado. Endpoint paginado
  `GET /api/vocabulary/history` por palabra. El ledger es señal, nunca puerta
  de mastery. Sin cambios de UI.

### Eje C — Listening real, calibración CEFR y UX de progreso (F-C1/F-C2/F-C3/F-C4)

- **F-C1 — Taxonomía de capas recognition/comprehension/inference.** Mapa
  determinista `skill → capa` en `services/listening.py`: recognition =
  word/sound/phrase_recognition + numbers; comprehension = gist/detail/
  vocabulary/sequencing/note_taking/prediction; inference = inference/attitude/
  speaker_intention/fast_speech/connected_speech/multiple_speakers
  (dictation/shadowing y skills de producción tratados aparte, capa `null`).
  La capa se expone en ítems servidos y en el reporte `by_layer` del
  diagnóstico. Sin migración de datos ni re-etiquetado del corpus (la autoría
  recognition escasa queda como deuda de contenido documentada).
- **F-C2 — Calibración CEFR unificada de extremos.** Las 4 destrezas planas
  (vocabulary/grammar/interaction/mediation) pasan a una **escalera monótona**
  desde B1 siguiendo la progresión de `reading` (minimum_mastery/confidence/
  evidence/transfer_required), conservando su suelo histórico A1/A2. Extremos
  unificados por familia: las 4 destrezas de apoyo convergen al mismo techo que
  reading/writing en C2, mientras las macro-destrezas calibradas (speaking/
  writing) conservan sus techos específicos. Matriz a `version 2.1.0`.
- **F-C3 — Skills bloqueantes con motivo en la UI.** `readiness` expone
  `blocked_by` por destreza evaluada y no lista (`score`/`confidence`/`evidence`/
  `transfer`/`novel`); la UI (`TodayPlan`) traduce el motivo junto al nombre de
  la destreza con claves i18n es/en. Resuelve M-F4: el usuario ve por qué una
  destreza capa su overall.
- **F-C4 — Marca de evidencia legacy sin `context_id`.** `build_skill_profile`
  cuenta `legacy_context_rows` y marca `legacy_context_used` por destreza (el
  fallback del gate a filas ocurre solo cuando un kind con filas no tiene
  NINGÚN contexto conocido — con contextos, las filas legacy no cuentan ni
  inflan experiencias). Agregado en `StudentModelOut`
  (`legacy_context_evidence`/`legacy_context_rows`) y `mastery_gate` expone
  `legacy_fallback`; el ladder (`AssessmentLadder`) y las vistas de Progreso
  (`ProgressScreen`, `SkillDetail`) muestran notas i18n cuando el gate o el
  perfil cae a evidencia no verificada.

## Técnica

- Backend (versión de app `3.25.1 → 3.26.0`, fuente única `backend/config.py`):
  - `services/assessment_v2.py`: `SPACED_PRACTICE_MIN_DAYS`,
    `familiar_spaced_counts`, `delayed_origin_anchors`, `retention_spacing_due`,
    `certification_gate` con `CERTIFICATION_REQUIRED_DELAYED = 2` y
    `delayed_origins`, `mastery_evidence_gate` con initial/practice y
    `legacy_fallback`.
  - `domain/academy.py`: `_mission_evidence_kind`/`submit_speaking_mission_*`,
    resolución de `correct_index` vía examen en retention `kind=level`,
    `legacy_context_evidence/rows` en `get_student_model`.
  - `services/speaking.py`: `mission_evidence_kind` + `NOVEL_MIN_CEFR`;
    `repositories/academy.py`: `mission_context_practiced`.
  - `repositories/vocabulary.py` + `repositories/db.py` + `schemas/vocabulary.py`
    + `domain/vocabulary.py` + `routers/vocabulary.py`: ledger
    `vocabulary_events` + `VocabularyEventOut` + `GET /api/vocabulary/history`.
  - `services/listening.py` + `schemas/listening.py` + `domain/listening.py`:
    taxonomía `skill_layer`, `accuracy_by_layer`, capa en ítems y reporte.
  - `curriculum/cefr_matrix.json` (2.1.0) + `services/cefr_matrix.py`:
    escalera monótona de las 4 destrezas de apoyo.
  - `services/adaptive.py`/`services/academy.py`/`schemas/academy.py`:
    `blocked_by`, `legacy_context_rows`/`legacy_context_used`,
    `legacy_context_evidence`.
- Frontend: tipos espejo opcionales en `types/api.ts`; `TodayPlan` (motivo de
  bloqueo), `AssessmentLadder` (nota `legacy_fallback`), `ProgressScreen`/
  `HabilidadesTab` (notas legacy); i18n es/en.
- Docs: `PLAN.md`, `CHANGELOG.md` (`[3.26.0]`), `README.md`, `docs/RELEVO.md`,
  dossier O (`docs/audit/O-AUDITORIA-TOTAL-V326.md`).

## Tests

- Backend: **1538 pytest en verde** (Eje A: `familiar_spaced_counts`, gate
  initial/practice, anclaje `delayed` por origen, ≥2 reassessment points
  estables, retention sobre `kind=level` con espaciado 409; Eje B: misión
  B2+ primera vez → `novel` y retry → `familiar`, ledger `vocabulary_events`
  con paridad de contadores, historia paginada; Eje C: taxonomía de capas
  `test_listening_taxonomy.py`, matriz 2.1.0 con monotonicidad de las 8
  destrezas y extremos unificados, `blocked_by`, marcas legacy por
  skill/gate/endpoint) + `ruff check .` limpio.
- Golden: `tests/test_golden_*.py` en verde (incl. `evidence_depth_cases.json`
  recalibrado para C1 grammar con `minimum_evidence: 5` y `meets_matrix: false`
  sin transfer).
- Frontend: vitest **450 passed** (57 archivos); `tsc --noEmit` OK.
- `scripts/check_release_consistency.py` exit 0 (3.26.0).

## Fuera de alcance (deuda abierta documentada)

- Reactivación progresiva de `novel_required` en B2+ (emisor real listo desde
  F-B1; decisión de negocio de cuándo activar la exigencia en la matriz).
- Re-etiquetado del corpus de listening para cubrir la capa recognition
  (la taxonomía está viva y expuesta; la autoría de ítems recognition es
  deuda de contenido).
- Heurística de `SUPPORT_LEVEL_WEIGHTS` declarada a calibrar.

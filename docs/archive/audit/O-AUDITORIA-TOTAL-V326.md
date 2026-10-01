# O — Resolución del alcance V3.26 (release v3.26.0): retención longitudinal, `novel` real, historia léxica, Listening por capas, calibración CEFR y UX de progreso

> Fecha: 2026-09-08 · Rol: **resolución de auditoría (cierre del alcance V3.26
> sobre `main`)**.
> Posición auditada: **release v3.26.0 en `main`** (commits del Eje A: F-A1
> `c5cb2b8`, F-A2 `16bbb50`, F-A3 `cd69088`; Eje B: F-B1 `b057e4b`, F-B2
> `5d0a19d`; Eje C: F-C1 `f8e0c64`, F-C2 `b62fc65`, F-C3/F-C4 `eee806a`;
> notas de relevo `e89e97c`/`5408ba7`). `VERSION = "3.26.0"` confirmado en
> `backend/config.py`. Los dossieres de las auditorías externas previas
> declararon para V3.26 los P2 y mejoras que este dossier resuelve (L
> `docs/audit/L-AUDITORIA-TOTAL-V324.md`: P2-04 Listening real; M
> `docs/audit/M-AUDITORIA-TOTAL-V325.md`: P2-01/P2-02 initial·practice y
> `event_age` vs `retention_interval`, P2-03 calibración CEFR, M-F2 legacy sin
> `context_id`, M-F3 ventana de retención en el gate, M-F4 destreza crítica que
> capa el overall, M-F5 emisor real de `novel`). Método: cada incremento con
> tests-first (rojo/verde), batería **íntegra** reproducida al cierre.

## Alcance

- **Se audita**: el gate MASTERED con initial/practice espaciado (F-A1); el
  anclaje de cada `delayed` a su origen formal y la separación
  `event_age_days`/`retention_interval_days` (F-A2); la certificación con ≥2
  reassessment points estables por destreza, el fix del escritor de retención
  sobre exámenes `kind=level` y el espaciado 409 (F-A3); el emisor real del
  kind `novel` en misiones B2+ jamás practicadas (F-B1); el ledger
  `vocabulary_events` por superficie con endpoint paginado (F-B2); la taxonomía
  determinista de capas de Listening expuesta en ítems y diagnóstico (F-C1); la
  calibración CEFR unificada de extremos, matriz 2.1.0 (F-C2); el motivo de
  bloqueo `blocked_by` por destreza en readiness y su traducción en la UI
  (F-C3); las marcas de evidencia legacy sin `context_id` por destreza, global
  y en el gate (F-C4).
- **NO se audita** (deuda abierta documentada): la reactivación calibrada de
  `novel_required` en B2+ (emisor listo, requisito sigue 0 por decisión de
  negocio), el re-etiquetado del corpus de listening para cubrir la capa
  recognition y la calibración de `SUPPORT_LEVEL_WEIGHTS`.

## Resolución por hallazgo

### F-A1 — El gate MASTERED no distinguía encuentro inicial de práctica espaciada (P2-01)

**Problema (auditoría M):** los contadores del gate trataban todo `familiar`
como práctica; dos filas del mismo contexto el mismo día podían satisfacer
`practice` sin demostrar espaciado.

**Resolución** ([backend/services/assessment_v2.py](backend/services/assessment_v2.py)):

- `MASTERY_EVIDENCE_REQUIREMENTS = {initial: 1, practice: 2, transfer: 2,
  delayed: 1}` con la semántica aprobada por el gerente: **practice = re-encuentro
  espaciado**.
- `SPACED_PRACTICE_MIN_DAYS = 1` y `familiar_spaced_counts`: por contexto
  (`context_id` no vacío + `created_at` parseable), `initial_xp` = nº de
  contextos con ≥1 encuentro; `practice_xp` = nº de días posteriores distintos
  del primer encuentro con gap ≥ `SPACED_PRACTICE_MIN_DAYS` (varias filas del
  mismo día no inflan). Las filas legacy (sin contexto/fecha) quedan fuera y el
  llamador decide el fallback.

**Evidencia de cierre**: `tests/test_assessment_v2.py`
(`test_familiar_spaced_counts...`), `test_evidence_context.py`
(`test_mastery_gate_requires_distinct_familiar_contexts`).

### F-A2 — `event_age` vs `retention_interval` en el reporte (P2-02)

**Problema (auditoría M):** el reporte mezclaba la edad del evento desde `now`
con el intervalo pedagógico formal→delayed; re-intentos podían acortar las
ventanas.

**Resolución** ([backend/services/assessment_v2.py](backend/services/assessment_v2.py)
+ [backend/domain/academy.py](backend/domain/academy.py)): cada evento
`delayed` se ancla a su sesión formal origen (`source_session_id` vía
`delayed_origin_anchors`) y el reporte separa `event_age_days` de
`retention_interval_days`, derivado este del ancla formal.

**Evidencia de cierre**: `tests/test_assessment_v2.py` (tests F-A2 de anclaje).

### F-A3 — Retención longitudinal multi-punto + fix del escritor `kind=level` (F-L8/M-F3)

**Problema (auditoría M, F-L8/M-F3):** la certificación era binaria (1
`delayed` verificable por destreza) y, verificado en caliente, la retención
**sobre el examen de nivel (`kind=level`)** no se podía puntuar: los ítems del
examen no viven en el índice de checks del currículo, `submit` devolvía `None`
y nunca se escribía `delayed` por esa vía (la certificación end-to-end era
inalcanzable por la escalera).

**Resolución** ([backend/services/assessment_v2.py](backend/services/assessment_v2.py)
+ [backend/domain/academy.py](backend/domain/academy.py)):

- `CERTIFICATION_REQUIRED_DELAYED = 2`: el gate certifica solo con **≥2
  reassessment points estables por destreza**, cada uno ≥ `RETENTION_MIN_DAYS`
  desde su origen (anclado) y ratio ≥ `RETENTION_STABLE_RATIO`. Un perfil con 1
  único `delayed` deja de certificar.
- Fix del escritor: el retention que re-evalúa un `source_kind == "level"`
  resuelve `correct_index` **vía el examen** (sesión origen), no contra el
  índice curricular.
- `retention_spacing_due`: cada nuevo reassessment se espacia ≥
  `RETENTION_MIN_DAYS` desde el último del mismo origen (409 si no).

**Evidencia de cierre**: tests negativos y de frontera del gate actualizados a
los 2 puntos, tests de `retention_spacing_due`, HTTP de retención sobre
`kind=level` y del espaciado 409 (`tests/test_assessment_v2.py`,
`tests/test_evidence_context.py`, `tests/test_academy.py`).

### F-B1 — El kind `novel` seguía sin emisor real (M-F5/P2, frontera V3.25)

**Problema:** `novel` era un kind reservado sin emisor; la frontera se declaró
hasta que existiera una modalidad real (speaking libre en contexto nunca
practicado).

**Resolución** ([backend/services/speaking.py](backend/services/speaking.py) +
[backend/domain/academy.py](backend/domain/academy.py) +
[backend/repositories/academy.py](backend/repositories/academy.py)):

- Emisor real: la **primera misión por escenario B2+ jamás practicada** emite
  `novel` (`mission_evidence_kind` + `NOVEL_MIN_CEFR`); retries y repeticiones
  del mismo escenario emiten `familiar` (anti-bombeo).
- Detección evidence-only: contexto canónico `mission:{escenario}` sin ninguna
  fila en `academy_evidence` del usuario = nunca practicado
  (`mission_context_practiced` sobre `list_evidence` existente).
- Decisión del gerente: **no se reactiva el requisito** — `novel_required = 0`
  en las celdas de la matriz y el gate MASTERED intactos; la activación
  calibrada B2+ queda como deuda del Eje C (documentada).

**Evidencia de cierre**: `tests/test_speaking_mission.py`
(`test_mission_first_attempt_b2_writes_novel_then_retry_familiar`,
`test_mission_b1_scenario_never_emits_novel`,
`test_mission_repeat_b2_scenario_does_not_inflate_novel`,
`test_mission_evidence_kind_only_novel_for_first_ever_b2_plus`).

### F-B2 — Historia léxica fina por superficie (F-L11/M-C13, sin backfill)

**Problema:** el modelo agregaba por palabra y el histórico fino vivía solo en
`learning_events`; V3.26 debía registrar la historia de eventos léxicos por
forma de superficie.

**Resolución** ([backend/repositories/db.py](backend/repositories/db.py) +
[backend/repositories/vocabulary.py](backend/repositories/vocabulary.py) +
[backend/schemas/vocabulary.py](backend/schemas/vocabulary.py) +
[backend/domain/vocabulary.py](backend/domain/vocabulary.py) +
[backend/routers/vocabulary.py](backend/routers/vocabulary.py)):

- Tabla `vocabulary_events` **append-only** (`word`, `lexical_unit`,
  `event_type` `produced|exposed|retrieval`, `channel`, `activity`,
  `created_at`) con índice por usuario/palabra.
- Escrita en la **misma transacción** de los 4 writers (sin doble fuente de
  verdad; invariantes de contadores y `sum(channel_prod) == production_count`
  intactos).
- SIN backfill: la historia empieza en V3.26; los contadores conservan el
  histórico agregado. Endpoint `GET /api/vocabulary/history` paginado por
  palabra + `VocabularyEventOut`. Ledger = señal (D5/E3), nunca puerta de
  mastery. Sin cambios de UI.

**Evidencia de cierre**: `tests/test_vocabulary_events.py` (creación/índice,
paridad de eventos con contadores en producción/exposures/retrievals,
`seed_curriculum_items` no genera eventos, filtrado/paginación vía API).

### F-C1 — Listening sin capas recognition/comprehension/inference (P2-04, dossier L)

**Problema (auditoría L):** el corpus no tenía capa cognitiva; los intentos
guardan `skill` (snapshot) sin orden por capa.

**Resolución** ([backend/services/listening.py](backend/services/listening.py) +
[backend/schemas/listening.py](backend/schemas/listening.py) +
[backend/domain/listening.py](backend/domain/listening.py)):

- Mapa **determinista** `skill → capa`: recognition = word/sound/
  phrase_recognition + numbers; comprehension = gist/detail/vocabulary/
  sequencing/note_taking/prediction; inference = inference/attitude/
  speaker_intention/fast_speech/connected_speech/multiple_speakers
  (dictation/shadowing y skills de producción aparte: capa `null`).
- Capa expuesta en ítems servidos (`layer`) y reporte agregado `by_layer`
  (`accuracy_by_layer`) del diagnóstico. Sin migración de datos ni
  re-etiquetado del corpus (autoría recognition escasa = deuda de contenido).

**Evidencia de cierre**: `tests/test_listening_taxonomy.py` (11 tests nuevos:
cobertura de todos los subskills, mapa exacto, una sola capa por skill,
producción/desconocidos → `null`, agrupación/orden de `by_layer`, todas las
capas reportadas incluso vacías, exclusión de producción, exposición en
diagnóstico/ítems).

### F-C2 — Matriz CEFR plana en las 4 destrezas de apoyo (P2-03, M-F5)

**Problema (auditoría M):** vocabulary/grammar/interaction/mediation exigían lo
mismo en A1 que en C2; sin validador de coherencia.

**Resolución** ([backend/curriculum/cefr_matrix.json](backend/curriculum/cefr_matrix.json) +
[backend/services/cefr_matrix.py](backend/services/cefr_matrix.py)):
matriz **2.1.0** con escalera monótona para las 4 destrezas de apoyo siguiendo
la fila de `reading` desde B1 (minimum_mastery/confidence/evidence/
transfer_required progresivos), conservando su suelo histórico A1/A2; extremos
**unificados por familia** (las 4 de apoyo convergen al techo de reading/writing
en C2; las macro-destrezas calibradas conservan sus techos específicos).

**Evidencia de cierre**: `tests/test_cefr_matrix.py`
(`test_matrix_scales_with_level_for_all_skills` — monotonicidad de las 8
destrezas —, `test_support_skills_follow_reading_from_b1`,
`test_extremes_unified_across_all_skills` por familia);
`tests/test_adaptive.py` ajustado (B1 grammar ahora exige transfer);
golden `tests/golden/pedagogy/evidence_depth_cases.json` recalibrado
(ed-06-c1-grammar-recognition-only: `meets_matrix false`, `minimum_evidence 5`)
+ `tests/test_golden_pedagogy.py`.

### F-C3 — La UI no explicaba la destreza que capa el overall (M-F4)

**Problema (auditoría M):** `level_progress`/readiness mostraban el % sin decir
por qué una destreza crítica bloquea.

**Resolución** ([backend/services/adaptive.py](backend/services/adaptive.py) +
[backend/schemas/academy.py](backend/schemas/academy.py) +
frontend): `readiness` expone `blocked_by` por destreza evaluada y no lista
(`score`/`confidence`/`evidence`/`transfer`/`novel`; vacío si lista o sin
evaluar). La UI (`TodayPlan`) traduce el motivo junto al nombre con claves i18n
es/en. Tipos espejo en `frontend/src/types/api.ts`.

**Evidencia de cierre**: `tests/test_adaptive.py`
(`test_readiness_reports_blocked_by_reasons`,
`test_readiness_ready_skills_report_no_blocked_by`, asserts de `blocked_by`
añadidos a los tests existentes de bloqueo) + `tsc --noEmit` + vitest.

### F-C4 — Evidencia legacy sin `context_id` no marcada (M-F2)

**Problema (auditoría M, M-F2):** el fallback a filas mantenía la debilidad
para datos previos a V3.25 sin forma de distinguirlos; `SkillProfileOut`
descartaba claves no declaradas.

**Resolución** ([backend/services/academy.py](backend/services/academy.py) +
[backend/services/assessment_v2.py](backend/services/assessment_v2.py) +
[backend/schemas/academy.py](backend/schemas/academy.py) +
[backend/domain/academy.py](backend/domain/academy.py) + frontend):

- `build_skill_profile` cuenta `legacy_context_rows` y marca
  `legacy_context_used` por destreza: el fallback a filas ocurre solo cuando un
  kind con filas no tiene **ningún** contexto conocido (con contextos, las filas
  legacy no cuentan ni inflan experiencias).
- Declarados en `SkillProfileOut`; agregado en `StudentModelOut`
  (`legacy_context_evidence`/`legacy_context_rows`); `mastery_evidence_gate`
  expone `legacy_fallback`.
- UI: nota en `AssessmentLadder` (gate retrocedió a filas), `ProgressScreen`
  (global) y `HabilidadesTab`/SkillDetail (por destreza), con i18n es/en.

**Evidencia de cierre**: `tests/test_evidence_context.py`
(`test_profile_entry_reports_legacy_context_rows` — solo legacy / todos con
contexto / mezcla por kind —, asserts de `legacy_fallback` en el gate,
`test_student_model_endpoint_reports_legacy_context` e2e).

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Veredicto |
|---|---|---|---|
| O-G1 | `cd backend; python -m pytest -q` | **1538 passed** (vs 1495 de v3.25.1; +43 netos V3.26) — exit 0 | ✔ reproducido |
| O-G2 | `cd backend; python -m ruff check .` | `All checks passed!` — exit 0 | ✔ reproducido |
| O-G3 | golden `tests/test_golden_*.py` (incl. `evidence_depth_cases.json`) | en verde dentro de O-G1 | ✔ reproducido |
| O-G4 | `cd frontend; npx tsc --noEmit` | sin errores — exit 0 | ✔ reproducido |
| O-G5 | `cd frontend; npx vitest run` | **450 passed** (57 archivos) — exit 0 | ✔ reproducido |
| O-G6 | `python scripts/check_release_consistency.py` | `OK: Release consistency (3.26.0) en todos los orígenes` — exit 0 | ✔ reproducido |
| O-G7 | CI GitHub Actions (push a `main`) | Backend ruff+pytest · Frontend tsc+vitest+build · Release consistency · Beta V3.0 · Content · Playwright — success | ✔ reproducido |

**1538 tests en verde, 0 fallos, golden incluido, frontend intacto (450).** El
resto de contratos (examen, completions, Student Model, léxico, matrices,
contadores de vocabulario) no cambia salvo en el comportamiento correcto del
gate y la calibración 2.1.0 (monótona, ver F-C2).

## Veredicto de cierre

- **Eje A resuelto**: gate MASTERED separa initial/practice espaciado (F-A1),
  cada `delayed` anclado a su origen con `event_age`/`retention_interval`
  separados (F-A2) y la certificación exige ≥2 reassessment points estables por
  destreza con el escritor `kind=level` arreglado (F-A3).
- **Eje B resuelto**: `novel` tiene emisor real (misión B2+ jamás practicada,
  anti-bombeo) con requisito intacto por decisión de negocio (F-B1); historia
  léxica por superficie en ledger append-only sin backfill (F-B2).
- **Eje C resuelto**: taxonomía de capas de Listening expuesta (F-C1), matriz
  2.1.0 con las 8 destrezas monótonas y extremos unificados (F-C2), `blocked_by`
  con motivo traducido en UI (F-C3) y marcas de legacy sin `context_id`
  (F-C4).

**Deuda abierta (documentada, no bloquea el release):** reactivación calibrada
de `novel_required` en B2+; corpus recognition de listening; calibración de
`SUPPORT_LEVEL_WEIGHTS`.

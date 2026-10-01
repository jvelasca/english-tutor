# M — Auditoría TOTAL externa V3.25.0: calibración del Student Model con contexto (verificada sobre el árbol de trabajo)

> Fecha: 2026-09-08 · Rol: **auditor externo (verificación read-only + cierre)**.
> Posición auditada: **árbol de trabajo sobre `main` = `016f8b7`** (candidato
> release **v3.25.0**, sin commit). `VERSION = "3.25.0"` confirmado en
> `backend/config.py`. El release v3.24.0 (`8970634`) es el padre inmediato; el
> delta auditado es el diff funcional `git diff 016f8b7` (37 ficheros, +1073/−192,
> implementado y verificado en el árbol, pendiente de cierre).
> Método: plantilla `docs/audit/TEMPLATE.md`, dossier L (v3.24.0) como línea base
> de los pendientes que V3.25 declara cerrar (F-L3…F-L8/F-L11 = F-K3…F-K7 y
> P1-01…P1-04), más verificación claim → `archivo:línea` y reproducción **íntegra**
> de la batería de tests (no solo núcleo).

Cadena auditada: **Evidence (eventos con contexto) → Support Level → Mastery
(contextos distintos) → Assessment 2.0 (certificación robusta) → Student Model
(demostrado/estimado/progreso) → UI de Progreso**, más el renombrado léxico
canónico con `lexical_unit` (dominio léxico, D5/E3), la doble vía speaking con
`cefr_target` persistido y las fronteras declaradas de V3.25.

## Alcance

- **Se audita**: el modelo de eventos con contexto (`academy_evidence` +
  `context_id`/`activity_id`/`task_type`/`support_level`), el `support_level`
  canónico por emisor (F-L7), el transfer por experiencias **distintas** en
  gates/readiness/unit (F-L6), la robustez de `certification_gate` con
  `retention_report` (F-L4/F-L8), la semántica demostrado/estimado en el
  Student Model y la UI (F-L3/F-K4), el renombrado léxico
  `production_count`/`exposure_count` + `lexical_unit` (F-L11/F-K7/P2-01/P2-02),
  la desambiguación F-K5 y la doble vía speaking con `cefr_target` (F-K3).
- **NO se audita** (fronteras declaradas V3.25): el emisor real del kind
  `novel` (sigue reservado, requisito 0), la calibración progresiva de la CEFR
  matrix para vocabulary/grammar/interaction/mediation (P2-03) y el listening
  real recognition/comprehension/inference (P2-04) — candidatos V3.26+.
  Sí se comprueba si alguno de esos elementos aplazados provoca incoherencia
  observable en V3.25 (resultado en cada hallazgo).
- **Verificación de claims externos**: la auditoría del dossier L declaró
  cerrables F-K1/F-K2 y abiertos F-L3…F-L8/F-L11 para V3.25. Este dossier
  reproduce **cada** afirmación de `release-notes-v3.25.0.md` contra el código y
  clasifica el resultado (BUG REAL / RIESGO / DEUDA ARQUITECTÓNICA / MEJORA
  PEDAGÓGICA / MEJORA UX / NO PROBLEMA).

## Método

1. **Lectura previa**: `release-notes-v3.25.0.md`, `docs/RELEVO.md` (nota de
   2026-09-08 14:40), dossier L (v3.24.0), `PLAN.md`, `CHANGELOG.md`.
2. **Punto de partida**: `git rev-parse HEAD` → `016f8b7` (punta main);
   `git status --short` → implementación V3.25 **sin commit** (37 ficheros);
   `git diff --stat HEAD` delimita el cambio funcional V3.25 (37 ficheros,
   +1073/−192).
3. **Verificación por trazado**: para cada claim se localizó el
   escritor/lector `archivo:línea`, se confirmó el test que fija el
   comportamiento y se reprodujo **toda** la batería de verificación (sección
   "Evidencia — Gates"), no solo el núcleo.
4. **Clasificación**: cada hallazgo se etiqueta con su naturaleza y severidad
   (P0–P3 / informativo).
5. Sin ejecución de Ollama/Whisper/Piper ni cambios de código en esta fase de
   verificación; la batería se ejecuta tal cual (comandos citados). Los tests
   que requieren LLM/ASR reales quedan fuera o se marcan como *declarado*.

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Veredicto |
|---|---|---|---|
| M1 | `cd backend; .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider` | **1481 passed, 1 warning (deprecación upstream httpx/starlette)** en 138.96s — exit 0 | ✔ reproducido |
| M2 | `cd backend; .venv\Scripts\python.exe -m ruff check .` | `All checks passed!` — exit 0 | ✔ reproducido |
| M3 | golden: pytest `tests/test_golden_{assessment,evidence_graph,fsrs,listening,pedagogy,speaking}.py` | **25 passed** — exit 0 | ✔ reproducido |
| M4 | `cd frontend; npm test` (vitest run) | **450 passed** (57 archivos) — exit 0 | ✔ reproducido |
| M5 | `cd frontend; npm run build` (`tsc && vite build`) | tsc sin errores; vite `✓ built in 2.52s` — exit 0 | ✔ reproducido |
| M6 | `python scripts/check_release_consistency.py` | `OK: Release consistency (3.25.0) en todos los orígenes` — exit 0 | ✔ reproducido |
| M7 | conteo estático `rg "^(\s*)(async )?def test_" backend/tests -g "test_*.py"` | **1481** funciones `test_` (coincide con M1); `test_evidence_context.py` aporta 18 | ✔ reproducido (declarado) |

**1481 tests en verde, 0 fallos, golden incluido** (M1/M3). El claim de las
release notes "1481 pytest en verde" se corresponde con el conteo estático (M7)
y con la suite completa reproducida (M1) — a diferencia del dossier L (que solo
pudo reproducir el núcleo), aquí la batería se ejecutó **íntegra**. El frontend
se reproduce exacto (M4/M5). Los claims de CI (workflows asociados al SHA) no
son verificables desde el repositorio local (no hay commit/release aún) y se
marcan como *declarado, no reproducido*.

## Claims verificados contra el código (con test que los fija)

| Claim | Evidencia de código | Test que lo fija | Resultado |
|---|---|---|---|
| **M-C1** F-L7/Fase 1: `academy_evidence` gana `context_id`/`activity_id`/`task_type`/`support_level` + índice `idx_evidence_context`, migración idempotente | `repositories/db.py:283-339` (CREATE + ALTER columna a columna + `CREATE INDEX IF NOT EXISTS idx_evidence_context ON academy_evidence(user_id, level_id, skill, evidence_kind, context_id, activity_id)`); `repositories/academy.py:361-425` (`record_evidence` con los 4 campos y `list_evidence` leyéndolos) | `test_evidence_context.py::test_migration_adds_context_columns` (38-48), `::test_record_evidence_persists_context_fields` (75-103), `::test_legacy_row_writes_default_empty_context` (52-72) | ✔ NO PROBLEMA |
| **M-C2** Fase 1: los 10 emisores pasan contexto; `evidence_from_items`/`_record_evidence_validated` enriquecen cada evento | 10 call-sites `context={...}` en `domain/academy.py` (1055, 1260, 1765, 3103, 3179, 3274, 3335, 3395, 3462, 3752); `evidence_from_items` con `context_id`/`activity_id`/`task_type`/`support_level` (`services/academy.py:687-736`); `_record_evidence_validated` rellena claves ausentes desde `context` (`domain/academy.py:429-436`) | `test_evidence_context.py::test_evidence_from_items_embeds_context` (107-129), `::test_objective_assessment_writes_context_columns` (183-204) | ✔ NO PROBLEMA |
| **M-C3** Fase 2: `SUPPORT_LEVELS` canónico + mapa por emisor | `services/academy.py:767-788` (`SUPPORT_LEVELS` copied/guided/cued/independent/spontaneous, `TASK_TYPES`); call-sites: objective assessment/assessment_v2/examen → `cued`; speaking assessment (1055-1059) y misión (1260-1265) y speaking/writing task → `independent`; speaking controlled/writing controlled/read-aloud → `guided`; `evidence_record_errors` valida el enumerado (`services/academy.py:872`) | `test_evidence_context.py::test_support_level_unknown_is_invalid` (133-146), `::test_support_level_canonical_is_valid` (149-163), `::test_objective_assessment_writes_context_columns` (183-204, aserción `cued`), `::test_mission_evidence_declares_independent` (209-223) | ✔ NO PROBLEMA |
| **M-C4** Fase 2: `build_skill_profile` expone `support_levels` + `independent_count` por destreza | `services/academy.py:494-531` (agrega `support_levels` por evento y `independent_count = independent + spontaneous`; legacy con '' no cuenta); `schemas/academy.py::SkillProfileOut` (+`support_levels`, `independent_count`, `production_count`, `evidence_by_kind`, `generalized_score`) | `test_evidence_context.py::test_profile_entry_exposes_support_levels` (226-275) | ✔ NO PROBLEMA |
| **M-C5** Fase 3: transfer por contextos **distintos**; dos transfers del mismo contexto ya no satisfacen `transfer≥2` | `services/academy.py:398-431` (`evidence_context_count` cuenta combinaciones distintas `(context_id, activity_id, task_type)`; `effective_evidence_context_count` con fallback a nº de filas si no hay contextos); `services/assessment_v2.py::mastery_evidence_gate(..., context_counts=...)` (463-515) exige experiencias distintas por kind | `test_evidence_context.py::test_mastery_gate_requires_distinct_transfer_contexts` (352-369), `::test_mastery_gate_requires_distinct_familiar_contexts` (372-382), `::test_evidence_context_count_distinct_only` (282-315), `::test_profile_entry_distinct_contexts_by_kind` (319-347) | ✔ NO PROBLEMA (ver M-F2) |
| **M-C6** Fase 3: readiness/unit gate/evidence_graph consumen contextos efectivos | `services/adaptive.py:234-237` (`effective_evidence_context_count` en `readiness`); `services/course.py:228-239` (`_transfer_count` con `distinct_contexts_by_kind`); `services/evidence_graph.py:174-192` (cobertura transfer con `context_id` distintos); retrocompatibilidad explícita con fallback a filas | `test_evidence_context.py::test_readiness_uses_distinct_transfer_contexts_when_known` (386-412); `test_adaptive.py::test_readiness_b2_ready_with_transfer_without_novel` (165-188) | ✔ NO PROBLEMA (ver M-F2) |
| **M-C7** Fase 3: colisión semántica `transfer`/`retention` documentada (F-K5) | `schemas/vocabulary.py::LexicalCompetence` (F-K5: `transfer`/`retention` léxicos ≠ `transfer`/`delayed` académicos); `services/lexicon.py::item_competence_matrix` (494-518: si se renombra → `contextual_transfer`/`delayed_recall`) | — (documentación) | ✔ NO PROBLEMA — frontera documentada correctamente |
| **M-C8** Fase 4: `certification_gate` verifica `created_at` por fila y emite `retention_report` con intervalos D+1/D+3/D+7/D+21 | `services/assessment_v2.py:381-458` (`_parse_iso(created_at)` → `verified`; si una fila `delayed` no es verificable, la certificación no se concede; `retention_report` con `ages_days`/`longest_interval_days`/`intervals_reached`); `RETENTION_INTERVALS = (1,3,7,21)` (77) | `test_evidence_context.py::test_certification_gate_verifies_delayed_rows` (433-449), `::test_retention_report_multi_interval` (463-479); `test_assessment_v2.py::test_certification_gate_rejects_delayed_without_created_at` (133-144) | ✔ NO PROBLEMA (ver M-F3) |
| **M-C9** Fase 4: `delayed` binario → robustez sin cambiar la semántica H5 (completar≠certificar) | `certification_gate` (381-458) mantiene `CERTIFICATION_REQUIRED_DELAYED = 1` por destreza y suma la verificación por fila; los tests previos H5 (`delayed` por destreza) se actualizan con `created_at` válido | `test_assessment_v2.py::test_certification_gate_requires_delayed_per_skill` (97-130), `::test_ladder_level_certified_requires_retention_step` (133-153) | ✔ NO PROBLEMA |
| **M-C10** Fase 5: Student Model separa `demonstrated_level`/`estimated_level`/`level_progress` | `domain/academy.py::_demonstrated_level` (622-654: solo niveles completados con `certification_gate` OK por cada destreza del examen), `build_student_model` (656-713: expone `demonstrated_level`, `level_progress` = overall del tramo, `estimated_level`/`estimated_numeric`); `schemas/academy.py::StudentModelOut` | `test_academy.py::test_endpoint_student_model_separates_demonstrated_level` (1483-1530, E2E: dominar A1 + examen → `demonstrated_level` None; + `delayed` por destreza → `demonstrated_level == "A1"` con `estimated_level` intacto) | ✔ NO PROBLEMA (ver M-F4) |
| **M-C11** Fase 5: la UI etiqueta sin ambigüedad "demostrado"/"en nivel X" | `ProgressScreen.tsx` (140-163: badge `✓ CEFR certificado {demonstrated_level}` y `{level_progress}% en {current_level}`); `i18n.ts` (`progress.certified*`/`progress.inLevel*`); `types/api.ts` (`demonstrated_level: string \| null`, `level_progress: number`) | `TodayPlan.test.tsx` (fixture con `demonstrated_level`/`level_progress`) | ✔ NO PROBLEMA |
| **M-C12** Fase 6: renombrado canónico `production_count`/`exposure_count` (F-K7/P2-01) | `repositories/db.py:601-634` (migración idempotente `occurrences → appearances → production_count`, `exposures → exposure_count` + ADD por si no existieran); toda la pila (repo/schema/servicios/domain/frontend) usa los nombres canónicos; accesores con retrocompatibilidad en `services/lexicon.py:129-139` (`production_count`/`exposure_count` aceptan claves legacy) | `test_vocabulary.py::test_vocabulary_renames_occurrences_and_exposures_idempotent` (75-119: fuerza el estado legacy y re-ejecuta `init_db`); resto de tests re-apuntados (`test_lexicon.py`, `test_chat_profile.py`, `test_drill_*.py`, `test_stt_asr.py`) | ✔ NO PROBLEMA |
| **M-C13** Fase 6: `lexical_unit` (lema o superficie normalizada) poblada en `record_production`/`record_exposures`/`seed_curriculum_items` | `repositories/db.py:744-761` (backfill idempotente: lemma si existe, `lower(word)` si no); `repositories/vocabulary.py` (`lexical_unit_key(word, lemma)` en INSERT/UPDATE de `record_production` 88-145, `record_exposures` 219-262, `seed_curriculum_items` 271-351); `services/lexicon.py::lexical_unit` (142-146) | `test_vocabulary.py::test_lexical_unit_declared_from_lemma_and_surface_fallback` (122-146: `Go`→`go`, `Traveling`→`traveling`); `domain/vocabulary.py` expone `lexical_unit` en `get_lexicon` | ✔ NO PROBLEMA |
| **M-C14** Fase 6: decisión `novel` confirmada (reservado, sin emisor) | Ningún call-site escribe `evidence_kind="novel"`: grep del árbol (backends + tests) muestra `novel` solo como kind válido en `EVIDENCE_KINDS` (`services/academy.py:761`), pesos (`793`), `counts` del gate (`assessment_v2.py:485,513`) y tests; `evidence_kind_for` (`assessment_v2.py:622-627`) solo devuelve `delayed`/`transfer`/`familiar` | `test_assessment_v2.py` (180-188: `novel` no está en `missing`, `counts["novel"]==0`); invariantes existentes | ✔ NO PROBLEMA — frontera correcta (ver M-F5) |
| **M-C15** Fase 7: doble vía speaking con `cefr_target` persistido (F-K3) | `repositories/db.py:400-442` (columna `cefr_target` en `speaking_mission_sessions` + backfill desde `mission_json`); `repositories/academy.py` (INSERT con `cefr_target` 610-616, SELECT 680); call-sites de misión (`domain/academy.py:1170`, `911`/`1091` en `_speaking_part_info`) | `test_speaking_mission.py::test_mission_session_persists_cefr_target` (200-216), `::test_mission_cefr_target_migration_backfills_legacy` (219-243: DROP COLUMN + `init_db` + verifica backfill) | ✔ NO PROBLEMA |
| **M-C16** Fase 7: vías assessment y misión declaran evidencia `independent` (contextos `speaking_assessment:<session>` y `mission:<scenario>`) | `domain/academy.py:1055-1060` (assessment: `context_id=f"speaking_assessment:{session['id']}"`, `support_level="independent"`); `domain/academy.py:1260-1265` (misión: `context_id=f"mission:{scenario_id}"`, `support_level="independent"`) | `test_speaking_mission.py` / `test_evidence_context.py::test_mission_evidence_declares_independent` (209-223) | ✔ NO PROBLEMA |
| **M-C17** El contrato expone el contexto y el nivel por destreza; `estimated_band` ya se consumía | `schemas/academy.py::SkillProfileOut` (+`evidence_by_kind`/`support_levels`/`independent_count`/`production_count`/`generalized_score`, retrocompatible con defaults) | tests de schemas/endpoints | ✔ NO PROBLEMA |

## Las 4 preguntas del auditor (para V3.25)

### P1 — ¿Qué eventos se PIERDEN?

1. **El kind `novel` sigue sin emisor real** (frontera declarada, V3.26+): la
   infraestructura de contexto + `support_level` de V3.25 ya existe, y la doble
   vía speaking es capaz de declarar `independent`, pero ninguna modalidad
   emite `novel`. Correcto mientras no haya modalidad que lo justifique.
2. **Los checks sin contestar de un assessment no generan evento** (diseño
   previo, sin cambio en V3.25): `evidence_from_items` salta ítems sin
   respuesta; no hay evento de "omisión". No es nuevo en V3.25.
3. **El chat libre** como emisor de vocabulario sigue sin `support_level` de
   evento académico (no entra en la cadena de mastery; correcto por D5/E3).
   La producción léxica por chat se sigue capturando por su vía propia
   (`/api/vocabulary/analyze`), no como evento `academy_evidence`.

### P2 — ¿Qué se DUPLICA?

1. **Los contadores derivados del perfil** (`evidence_by_kind` y
   `distinct_contexts_by_kind` en cada entrada de `build_skill_profile`)
   derivan de las mismas `evidence_rows`; no hay doble escritura porque el
   agregado es derivado y el escritor de eventos es único
   (`_record_evidence_validated` + `repositories.academy.record_evidence`).
2. **`familiar` sigue satisfaciendo a la vez `initial` y `practice`** cuando el
   perfil es legacy (sin contextos): el fallback a nº de filas hace que una
   fila de familiar pueda contar para ambos checks. Sigue siendo la frontera
   documentada del dossier L (F-L6 mitigado para datos nuevos, no para legacy).
3. **La vía speaking assessment y la misión** pueden registrar evidencia del
   mismo objetivo/contexto desde dos emisores distintos (assessment vía
   sesión, misión vía escenario): son contextos distintos por diseño
   (`speaking_assessment:<id>` vs `mission:<scenario>`), de modo que la
   combinación es justamente lo que V3.25 quiere contar como experiencias
   distintas. No hay doble conteo involuntario.

### P3 — ¿Qué se MAL AGREGA?

1. **`level_progress` = `overall_cefr_score` del tramo actual está acotado por
   los mínimos críticos** (CRITICAL_MINIMUMS grammar/vocabulary 0.4). Un alumno
   con una destreza crítica baja no puede subir el overall → progreso capado.
   Correcto para no certificar, pero conviene que la UI lo explique como
   "progreso en el tramo", no como nota (mismo matiz que F-L3 en V3.24; la UI
   de V3.25 añade el tooltip "No es una certificación", mitigación parcial).
2. **El conteo de "experiencias distintas" depende de que el emisor declare
   `context_id` distinto por instancia**: dos sessions distintas del mismo
   assessment_v2 type cuentan como contextos distintos aunque los ítems sean
   idénticos (contexto = `assessment_v2:unit:<session_id>`). Es una
   aproximación razonable de experiencia (cada intento de assessment es una
   tarea distinta), no una garantía de ítems distintos.

### P4 — ¿Qué alimenta REALMENTE mastery?

Sin cambios en V3.25: mastery se mueve solo por `apply_objective_evidence` /
`apply_skill_evidence` (K dossier P4). Lo que cambia es **qué cuenta como
experiencia** para los gates que consumen `evidence_by_kind`:
`mastery_evidence_gate`, `adaptive.readiness`, `course._transfer_count` y
`evidence_graph` ahora consumen contextos efectivos
(`distinct_contexts_by_kind`) cuando el perfil los conoce, y retroceden al
conteo de filas en perfiles legacy. La certificación (`certification_gate`)
sigue exigiéndose por destreza del examen con evidencia `delayed` verificable.

## Hallazgos

| # | Naturaleza | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|---|
| **M-F1** | NO PROBLEMA | — | **F-L7 cerrado: `support_level` canónico por evento, con enumerado completo y expuesto por destreza.** La infraestructura de contexto permite distinguir producción guiada de libre y separa `independent_count` en el perfil. Los emisores mapean de forma pedagógicamente coherente (objective/examen cued, speaking libre y misión independent, read-aloud y controlados guided). | M-C3/M-C4; `test_evidence_context.py:226-275` | Mantener el mapa por emisor como fuente única y documentarlo en la Constitución Pedagógica si un emisor nuevo se incorpora. | cerrado en V3.25 ✔ |
| **M-F2** | MEJORA PEDAGÓGICA | **P2** | **F-L6 mitigado para datos nuevos, no para legacy.** Dos transfer del mismo contexto ya no satisfacen el gate cuando el perfil conoce los contextos, pero el fallback a nº de filas (legacy sin `context_id`) mantiene la debilidad para datos previos a V3.25: `familiar×2` con una sola fila sigue siendo posible en perfiles legacy. | M-C5/M-C6; `services/academy.py:418-431` (`effective_evidence_context_count` retrocede a filas si `ctx==0`); `test_evidence_context.py:352-369` | Para V3.26+, considerar marcar la evidencia legacy como "contexto desconocido" (excluirla de `familiar_contexts` sin fallback) o exigir una migración que la recontextualice. No bloquea V3.25 porque los datos legacy son previos al contexto. | abierto (V3.26+, bajo) |
| **M-F3** | RIESGO (robustez) | P2 | **La ventana de retención formal (≥7 días) no la verifica el gate, la codifica el escritor.** `certification_gate` verifica ahora `created_at` parseable por fila (robustez F-L4) pero la edad mínima de 7 días sigue viviendo en el escritor único de `delayed` (`submit_assessment_v2`, validación `retention_due`). `retention_report` calcula intervalos, pero el gate no exige `longest_interval_days >= RETENTION_MIN_DAYS` en sí mismo. | `assessment_v2.py:381-458`; `domain/academy.py` (enforcement R6-01); M-C8 | Correcto estructuralmente (escritor único validado con 409). Si en V3.26 se abren más escritores de `delayed` (p. ej. retención multi-intervalo real), mover la ventana mínima al gate como verificación directa desde las filas. | abierto (V3.26, robustez) |
| **M-F4** | MEJORA DE UX | P3 | **`level_progress` no distingue cuál es la destreza crítica que capa el overall.** La UI muestra "X% en {nivel}" y el tooltip aclara que no es certificación, pero si una destreza crítica (grammar/vocabulary 0.4) bloquea el overall, el progreso mostrado puede quedarse bajo sin explicar por qué. | `ProgressScreen.tsx:140-163`; `services/academy.py:558-574` (CRITICAL_MINIMUMS) | Mostrar junto al % la destreza bloqueante crítica cuando `critical_skills` no esté vacío (el Student Model ya expone `critical_skills`). | abierto (V3.26, UX) |
| **M-F5** | NO PROBLEMA (frontera correcta) | — | **`novel` sigue reservado y `cefr_matrix` no incorpora la calibración P2-03/P2-04.** La infraestructura de contexto + `support_level` de V3.25 es la base para emitirlo cuando exista una modalidad que lo justifique (candidato V3.26+, con la doble vía speaking ya capaz de declarar `independent`). No hay incoherencia nueva observable. | M-C14; release notes (fuera de alcance) | V3.26+: valorar un emisor real de `novel` vía speaking libre en contexto nunca practicado + calibración progresiva de la matriz (P2-03/P2-04). | informativo |
| **M-F6** | NO PROBLEMA (declarado, no reproducido) | — | **Claims de CI no verificables localmente.** No hay commit/release del SHA V3.25 aún (implementación en el árbol). La batería completa (backend/frontend/consistency) sí se reproduce localmente (M1-M7). | `git status` (37 ficheros modificados); M1-M7 | Verificación en CI real tras el cierre del release. | informativo |

### Estado de los hallazgos del dossier L en V3.25

| Ítem dossier L | Estado en V3.25 | Evidencia |
|---|---|---|
| F-L3 (semántica UI de `estimated_level` ambigua; P1) | **cerrado** ✔ (P1-04/Fase 5): separa `demonstrated_level`/`estimated_level`/`level_progress` en el modelo y la UI, con claves i18n y tooltips que desambiguan | M-C10/M-C11; `test_academy.py:1483-1530`; `ProgressScreen.tsx` |
| F-L4 (certification_gate confía en existencia de `delayed`, no en su edad; P2) | **cerrado (robustez)** ✔ (P1-03/Fase 4): verifica `created_at` por fila y emite `retention_report`; matiz M-F3 (ventana mínima vive en el escritor) | M-C8/M-C9 |
| F-L6 (familiar×2/transfer×2 no demuestran experiencias independientes; P1) | **mitigado para datos nuevos** (P1-02/Fase 3): transfer/familiar exigen contextos distintos cuando el perfil los conoce; fallback legacy mantiene la debilidad solo para datos previos (M-F2) | M-C5/M-C6 |
| F-L7 (falta `support_level` en el evento; P1) | **cerrado** ✔ (P1-01/Fase 2): enumerado canónico + mapa por emisor + exposición en perfil | M-C3/M-C4/M-F1 |
| F-L8 (retención longitudinal: `delayed` binario; P2) | **parcial** (P1-03/Fase 4): infraestructura de intervalos + `retention_report`; la certificación sigue siendo binaria (1 delayed por destreza verificable), los intervalos son informativos, no gate | M-C8/M-F3 |
| F-L11 (deuda léxica naming/modelo agregado; P2) | **cerrado (renombrado)** ✔ (F-K7/P2-01/P2-02/Fase 6): `production_count`/`exposure_count` + `lexical_unit`; F-K5 documentado. El modelo sigue agregado por palabra (historia fina en `learning_events`), sin cambio en V3.25 | M-C12/M-C13 |
| F-L9 (E2E domina objetivos artificialmente; P3) | **parcial**: el E2E de Student Model V3.25 (M-C10) sigue usando `_dominate_a1` + `record_evidence` directo para `delayed`; no hay recorrido completo por la escalera real hasta certificación | `test_academy.py:1483-1530` | 
| F-L5 (novel sin emisor + documentación) | **cerrado (documental)** ✔: decisión confirmada y documentada en schemas/UI; `novel` reservado | M-C14/M-F5 |

## Veredicto

**APROBADO PARA CIERRE DEL CANDIDATO v3.25.0 — la batería de verificación se
reproduce íntegra y sin discrepancias (M1-M7), y los pendientes P1 del dossier L
quedan cerrados o mitigados en el código.**

La auditoría sobre el árbol de trabajo (candidato v3.25.0) confirma los cuatro
cierres centrales del plan V3.25: **(F-L7)** `support_level` canónico por evento
con mapa por emisor (M-C3/M-C4), **(F-L6)** el transfer del gate MASTERED ya no
se satisface con dos filas del mismo contexto cuando el perfil conoce los
contextos (M-C5/M-C6), **(F-L4)** `certification_gate` verifica la retención
desde las filas (`created_at` + `retention_report`, M-C8) y **(F-L3)** el
Student Model y la UI separan `demonstrated_level`/`estimated_level`/
`level_progress` con semántica no ambigua (M-C10/M-C11). El renombrado léxico
canónico (F-K7/P2-01) con `lexical_unit` (P2-02) y la desambiguación F-K5
quedan implementados y documentados en toda la pila, y la doble vía speaking
con `cefr_target` persistido (F-K3) cierra la frontera del dossier L.

No hay ningún BUG REAL demostrado en V3.25. Los pendientes son de calibración
pedagógica y robustez de baja severidad: **(M-F2)** el fallback a nº de filas
mantiene la debilidad de F-L6 solo para datos legacy previos a V3.25 (P2),
**(M-F3)** la ventana mínima de retención sigue codificada en el escritor único
y no como verificación del gate (P2, robustez), y **(M-F4)** `level_progress`
no explica qué destreza crítica capa el overall (P3, UX). Las fronteras
declaradas (emisor real de `novel`, calibración P2-03/P2-04 de la matriz CEFR)
no provocan incoherencia observable y se mantienen para V3.26+.

**Recomendación**: cierre del release v3.25.0 (commit + bump + CI) con la
batería M1-M7 como evidencia de verificación. La suite completa (1481 pytest +
golden + 450 vitest + tsc/build + consistency) se reproduce en verde en el
árbol, lo que constituye una verificación más fuerte que la del dossier L
(que solo pudo reproducir el núcleo).

## Regenerar / Verificar

```powershell
git rev-parse HEAD                  # 016f8b7 (main, sin commit del candidato)
git status --short                  # 37 ficheros (implementación V3.25 en el árbol)
git diff --stat HEAD                # delta funcional V3.25
cd backend
# Batería completa V3.25 (M1)
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# Ruff (M2)
.venv\Scripts\python.exe -m ruff check .
# Golden (M3)
.venv\Scripts\python.exe -m pytest tests/test_golden_assessment.py tests/test_golden_evidence_graph.py tests/test_golden_fsrs.py tests/test_golden_listening.py tests/test_golden_pedagogy.py tests/test_golden_speaking.py -q -p no:cacheprovider
# Conteo estático de tests backend (M7)
rg "^(\s*)(async )?def test_" tests -g "test_*.py" | Measure-Object | Select-Object -ExpandProperty Count
cd ..\frontend
npm test                            # M4 (450 passed, 57 files)
npm run build                       # M5 (tsc + vite build)
cd ..
python scripts/check_release_consistency.py   # M6 (OK: Release consistency (3.25.0))
```

Resultados reproducidos: M1 **1481 passed** (138.96s) · M2 ruff `All checks
passed!` · M3 **25 passed** · M4 **450 passed** (57 files) · M5 build OK ·
M6 **3.25.0** exit 0 · M7 **1481** funciones `test_` (18 en
`test_evidence_context.py`). Release notes v3.25.0 reproducidas contra el
código en los claims M-C1..M-C17.

## Tests que respaldan

- `test_evidence_context.py` (nuevo, 18 tests) — contexto del evento,
  `support_level`, contextos distintos, gate MASTERED, retention report.
- `test_assessment_v2.py` — gate MASTERED sin novel + contextos, certificación
  por delayed verificable por destreza, ladder complete≠certified.
- `test_academy.py` — E2E Student Model demostrado/estimado (1483-1530),
  E2E A1→A2 (1413-1530), estudiante vacío.
- `test_vocabulary.py` — migraciones `production_count`/`exposure_count`/
  `lexical_unit` idempotentes y su lectura.
- `test_speaking_mission.py` — `cefr_target` persistido y backfill de sesiones
  legacy.
- `test_golden_*.py` — `thresholds.json` y pesos del gate sin novel.

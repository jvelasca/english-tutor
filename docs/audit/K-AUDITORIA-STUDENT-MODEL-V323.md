# K — Auditoría profunda Eje 1: Student Model → Evidence → Mastery → Academy → CEFR (v3.23.0)

> Fecha: 2026-09-08 · Rol: **auditor externo read-only**. Posición auditada:
> **main = `bb3f253`** (release v3.23.0 en `f3739a9` + fix documental H1 en
> `bb3f253`; versión declarada 3.23.0 intacta). Método y formato: plantilla
> `docs/audit/TEMPLATE.md`, dossier J (v3.23.0) como línea base y dossier I
> (v3.18) para los ítems abiertos que cruzan el eje. Veredicto al final.
>
> Cadena auditada: **actividad → `_record_evidence_validated` →
> `academy_evidence` → mastery por objetivo/destreza → perfil por destreza →
> CEFR estimado (`estimated_*`) / CEFR demostrado (`competence_states`,
> certificación Assessment 2.0)**, más el Student Model léxico (tabla
> `vocabulary`, matriz de competencia, siembra FSRS) en su relación con la capa
> académica.

## Alcance

- **Se audita**: el inventario de eventos que generan evidencia y lo que de
  verdad mueve mastery; la semántica exacta del Student Model léxico
  (`appearances`/`production_days`/`exposures`/`exposure_days`/
  `retrieval_successes`/`retrieval_days`/`context_tags`); el Evidence Graph
  (`services/evidence_graph.py`) y el FSRS-lite (`services/fsrs.py`,
  `sync_fsrs_cards`) en su relación con el eje; los gates de mastery académico
  (`next_mastery_state`, `objective_progress`, `mastered_objective_ids`,
  Assessment 2.0, certificación con `delayed`); y el tramo final **CEFR
  estimado vs demostrado** (etiquetado `estimated_*`, `competence_states`,
  y los puntos donde una agregación se proyecta a etiqueta CEFR).
- **NO se audita** (fronteras): Eje 2 (física ASR/speaking), Eje 3
  (listening), Eje 4 (calibración de contenido/CEFR, dossieres A/D), Eje 5
  (UI/UX, dossier F), `support_level` por evento (frontera explícita V3.24),
  telemetría ASR persistente, backfill de anclas de retención. El estado de los
  ítems del dossier I se comprueba **solo como presencia/ausencia** en v3.23.
- **Relación con `docs/BETA_V3.md` y `docs/PREMISAS.md`**: se verifica premisa
  21 (la IA produce evidencia; el Mastery Engine determinista decide) y premisa
  12 (todo hallazgo exige test que lo fije); máximas "señal ≠ evidencia
  (D5/E3)" y "mejor perder evidencia que inventarla"; Constitución §6.2/§6.3
  (retención ≥7 días y ratio ≥0.9), §6.4 (evidence depth), §7 (modalidades).

## Método

1. **Lectura previa**: `PREMISAS.md`, `CONSTITUCION-PEDAGOGICA.md`, `RELEVO.md`
   (notas y ítems abiertos), dossieres `docs/audit/I-*.md`, `J-*.md` y
   `TEMPLATE.md`, `CHANGELOG.md`, `release-notes-v3.23.0.md`.
2. **Punto de partida**: `git log --oneline -3` → HEAD `bb3f253` (fix
   documental de etiquetas P1) sobre release `f3739a9` (v3.23.0);
   `git status --short` → **limpio**; la única escritura del auditor al terminar
   es este dossier (`?? docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md`);
   `backend/data/tutor.db-*` y `launcher/logs/*.log` quedan ignorados por
   `.gitignore`. Sin cambios de código.
3. **Verificación por trazado**: para cada tramo de la cadena se localizó el
   escritor/lector `archivo:línea`, se confirmó el test que fija el
   comportamiento y se comprobó que pasa dentro de las baterías reproducidas
   (sección "Evidencia — Gates").
4. **Preguntas del auditor** (Fase 1 del runbook): qué eventos se **pierden**,
   cuáles se **duplican**, cuáles se **mal agregan** y qué **realmente**
   alimenta mastery. Respuestas en sección "Las 4 preguntas".
5. Sin instalación de dependencias, sin ejecución de Ollama/Whisper/Piper, sin
   tocar código/BD. Los gates se reprodujeron tal cual (comandos citados).

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Veredicto |
|---|---|---|---|
| G1 | `cd backend; .venv\Scripts\python.exe -m pytest tests/test_vocabulary.py tests/test_lexicon.py tests/test_academy.py tests/test_academy_goal.py tests/test_assessment_v2.py tests/test_cefr_matrix.py tests/test_competence.py tests/test_cross_skill.py tests/test_evidence_graph.py tests/test_evidence_invariants.py tests/test_session_graph.py tests/test_graph_plan.py tests/test_fsrs_transfer_gap.py tests/test_learning_events.py tests/test_pedagogical_invariants.py tests/test_curriculum_quality.py -q -p no:cacheprovider` | `310 passed, 1 warning in 21.50s` — exit 0 | ✔ reproducido |
| G2 | `.venv\Scripts\python.exe -m pytest tests/test_profile.py tests/test_placement.py tests/test_placement_2_0.py tests/test_placement_session.py tests/test_placement_validity.py tests/test_fsrs.py tests/test_golden_fsrs.py tests/test_adaptive.py tests/test_mastery.py tests/test_forgetting.py tests/test_cefr_semantics.py tests/test_reproducibility.py tests/test_user_profile.py tests/test_speaking.py tests/test_speaking_assessment.py tests/test_speaking_mission.py tests/test_speaking_routes.py tests/test_writing.py tests/test_pronunciation.py tests/test_pronunciation_academy.py tests/test_unit_review.py tests/test_drill_ladder.py tests/test_cross_user_isolation.py tests/test_store_append_only.py -q -p no:cacheprovider` | `328 passed, 1 warning in 16.59s` — exit 0 | ✔ reproducido |
| G3 | `git log --oneline -3; git status --short` | HEAD `bb3f253` sobre `f3739a9`; árbol sin cambios del auditor salvo este dossier | ✔ reproducido |
| G4 | reproducción dirigida (script efímero en BD temporal, sin tocar BD real ni repo): dominar todo el currículo A1 (3 assessments correctos por objetivo) → `submit_exam(a1)` correcto | **Fase 1**: `current_level=A1 · estimated_level=B2 · numeric=3.78` · **Fase 2**: `exam passed=True · overall=1.0` → A2 matriculado → `current_level=A2 · estimated_level=Pre-A1 · numeric=1.0` (0 evidencia en A2). Caída B2→Pre-A1 en dos pasos por el mero hecho de aprobar | reproducido (ver F-K2) |

**638 tests del eje en verde, 0 fallos** (G1+G2). Solo se ejecutan tests; no se
modifica ni instala nada.

## La cadena auditada — mapa de escritores y lectores (verificado)

### 1) Escritores de evidencia académica (`academy_evidence`) — escritor único

Todo insert en `academy_evidence` pasa por
`backend/domain/academy.py::_record_evidence_validated` (411-437), que valida
cada fila con `backend/services/academy.py::evidence_record_errors` (739-794)
antes de persistir. Las superficies que llegan a escribir evidencia son:

| Superficie (domain) | Ruta/uso | Evidencia que escribe | ¿Mueve mastery? |
|---|---|---|---|
| `submit_objective_assessment` (2965) | Assessment MC del objetivo (formative/objective) | filas del objetivo vía `evidence_from_items` (2991-3007), `source="objective_assessment"` | Sí: `apply_objective_evidence` (3007) para las destrezas evaluadas |
| `submit_assessment_v2` (1569) | Escalera Assessment 2.0 (formative→retention) | `evidence_from_items` con `evidence_kind = evidence_kind_for(kind)` (1651-1663): `familiar`/`transfer`/`delayed` | Sí: si el peldaño lleva `objective_id` (formative) aplica a los estados del objetivo (1680); si no (unit/progress/level/retention) aplica a las filas de destreza del instrumento con el umbral del peldaño (1693) |
| `submit_speaking_assessment_part` (917) | Speaking Assessment (parte por parte) | filas `skill=speaking`, `objective_id=""`, con `difficulty` de la parte (968-973) | No (solo evidencia; el nivel de speaking se agrega aparte en `finish_speaking_assessment`) |
| `_score_mission_utterance` → misión (1179/1232) | Speaking Mission (intento y retry) | filas `skill=speaking`, `objective_id=""` (1167-1174) | No |
| `submit_speaking` (3028) | Speaking controlado de objetivo | `evidence_from_speaking` con `objective_id` (3061-3068) | Sí: `apply_objective_evidence` (3075) |
| `submit_speaking_task` (3094) | Tarea oral libre de objetivo (LLM extrae, scorer decide) | `evidence_from_speaking` con `objective_id` (3148-3158) | Sí: `apply_objective_evidence` (3164) |
| `submit_writing` (3182) / `submit_writing_task` (3287) | Writing controlado/tarea de objetivo | `evidence_from_writing` con `objective_id` | Sí: `apply_objective_evidence` (3219/3334) |
| `submit_pronunciation` (3237) | Read-aloud / pronunciación de objetivo | `evidence_from_pronunciation` con `objective_id` | Sí: `apply_objective_evidence` (3273) |
| `submit_exam` (3579) | Examen de nivel legacy | `evidence_from_items(exam.items, …, source="exam")` sin `evidence_kind` → **`familiar`** (3599-3610) | Sí, en caso de aprobar: `apply_skill_evidence` por destreza (3628) + `record_level_completion` |
| `submit_placement` (3392) | Placement | **ninguna** (solo `record_assessment_result`, 3398-3404) | No |
| `sync_fsrs_cards` / review FSRS | Tarjetas skill/lexicon/objective | no escribe `academy_evidence` | — |

**Conclusiones verificadas**:

- El **único** camino a mastery pasa por `apply_objective_evidence` /
  `apply_skill_evidence` (`backend/repositories/academy.py:138/72`), que
  transicionan con `services/academy.py::next_mastery_state` (70-112).
- `academy_skill_mastery` (filas por destreza, escritas por la escalera
  Assessment 2.0 sin objetivo y por `submit_exam`) es un **eco write-only**: el
  Student Model (perfil/estimado) se construye desde `academy_objective_mastery`
  + filas de `academy_evidence` (`services/academy.py:398-490`); `get_skill_mastery`
  no tiene consumidores de dominio (grep: solo tests).
- `record_attempts` (`domain/academy.py:2897`, binario) **nunca** toca
  mastery: solo contadores de la vista de actividad — fijado por
  `test_academy.py::test_endpoint_attempts_do_not_grant_mastery` (700).
- Speaking Assessment y Speaking Mission producen **evidencia pero no mastery
  por objetivo**: sus filas van con `objective_id=""` y solo cuentan en
  `evidence_count`/`evidence_by_kind`/`production_count` del perfil y en los
  agregados propios de speaking (`finish_speaking_assessment`,
  `/speaking/diagnostic`, `/speaking/journey`, `/speaking/level`). El score de
  la destreza en el Student Model **no** se mueve por ellas (ver F-K3).
- La propagación de `activity` (contextos `channel:activity`) está completa en
  las superficies académicas: assessment (964), misión (1162), speaking
  controlado (3056), speaking task (3144), writing controlado (3200), read
  aloud (3254), writing task (3315); helper `_capture_production_text`
  (441-…) con destrezas y `activity` canónicas (456-457). Sin fugas a
  `channel:other` en los volcados v3.23 (el fallback `other` queda para filas
  legacy): confirmado por `test_lexicon.py::test_production_contexts_explicit_tags_and_fallback`
  (599) y `test_matrix_transfer_by_two_activities_same_channel` (616).

### 2) Lectores (lo que de verdad alimenta el CEFR)

| Lector | Fuente | Qué produce |
|---|---|---|
| `build_skill_profile` (`services/academy.py:398-490`) | mastery por objetivo (`academy_objective_mastery`) **+** filas de evidencia del nivel | Entrada por destreza: `score`/`confidence` = media de los estados por objetivo que declaran la destreza; `evidence_count`/`evidence_by_kind`/`production_count`/`generalized_score` desde las filas de evidencia |
| `aggregate_skill_mastery` (`services/academy.py:375-395`) | solo mastery por objetivo | Vista derivada por destreza (fuente `academy_objective_mastery`; nunca se lee `academy_skill_mastery` como fuente primaria) |
| `overall_cefr_score` (515-545) | perfil por destreza | media ponderada `CEFR_SKILL_WEIGHTS` + mínimos críticos `CRITICAL_MINIMUMS` (grammar/vocabulary 0.4, 509-514) |
| `adaptive.estimated_level` (`services/adaptive.py:59-88`) | `overall_cefr_score` | `{level, numeric, confidence}`; sin evidencia → `Pre-A1`, `numeric` 1.0 |
| `domain/academy.py::build_student_model` (609-648) | `_annotated_profile` **de un único nivel** (`_current_level_id`, 580-591) | Student Model único: `estimated_level`, `readiness`, `mastery`, `reassessment` |
| `domain/profile.py::_compute_profile` (133-191) | el Student Model + estadísticas de actividad | `/api/profile` con `estimated_*`, bandas y `competence_states` |
| `services/competence.py::competence_state` (73-170) | entrada por destreza del Student Model (+ ruta listening) | estados NOT_STARTED/DEVELOPING/FUNCTIONAL/DEMONSTRATED |
| Evidence Graph (`services/evidence_graph.py`) | mastery por objetivo + perfil + filas de evidencia | nodos por objetivo con `mastery` = **media aritmética** de dimensiones (259-265) |
| FSRS-lite (`domain/academy.py::sync_fsrs_cards`, 1751-1874) | perfil anotado + filas `vocabulary` | tarjetas `skill`/`lexicon`/`objective` (se excluyen de la cola las `objective`, 1976-1989) |

## Las 4 preguntas del auditor

### P1 — ¿Qué eventos se PIERDEN?

1. **Exposición receptiva de la práctica académica (LEX-02)**: `record_exposure`
   se llama solo en `backend/routers/chat.py:66` y `:100` (chat libre y
   stream). El MC de objetivos, reading/listening y la práctica guiada **no
   generan `exposures`** aunque sus ítems estén en la tabla. Un alumno que
   responde bien un check de comprensión no deja señal léxica de esa
   exposición. Estado dossier I: **sigue abierta** (parcialmente mitigada por
   los volcados de producción V3.19-20 y los retrievals de drill).
2. **Chat libre**: la exposición/producción en chat libre depende de que el
   frontend llame a `/api/vocabulary/analyze` (y a los volcados de las rutas de
   conversación); si el flujo UI no lo invoca, no hay evento. No hay un
   sustituto en backend.
3. **Placement**: por diseño no escribe `academy_evidence`
   (`submit_placement`, 3392-3408) — solo `academy_assessment_results`. El
   nivel que arroja `theta_to_level` es puramente estimativo y **no** entra en
   la cadena evidencia→mastery. Coherente con D5/E3, pero conviene que quede
   explícito en la UI (ver F-K2).
4. **`lexical_tokens` (TOK-01/USE-01)**: el LLM de speaking extrae los tokens
   léxicos usados y el pipeline los descarta (no alimentan scorer ni fila).
   Estado dossier I: **sigue abierta** (persistir tokens validados es trabajo
   de V3.24+).

### P2 — ¿Qué eventos se DUPLICAN?

1. **Conversación guiada re-volcada por intento** (`backend/domain/conversation_routes.py:236-240`):
   cada `submit_attempt` vuelca el transcripto acumulado de la conversación al
   léxico; si el alumno reintenta la misma ruta, las mismas producciones se
   acreditan de nuevo (misma palabra, mismo día → `appearances` sube, y si es
   otro día `production_days` también). No es evidencia académica (no toca
   mastery), pero infla la señal de producción léxica del ítem. Severidad P2.
2. **Sin duplicación en `academy_evidence`**: `_record_evidence_validated` +
   validación impiden filas inválidas; la idempotencia de la escalera
   Assessment 2.0 y de `finish_speaking_assessment`/misión está fijada por
   tests (sesión `finished` no re-agrega).

### P3 — ¿Qué se MAL AGREGA?

1. **`retrieval_successes` acumula éxitos del mismo día**
   (`backend/repositories/vocabulary.py::record_retrievals`, 133-183):
   cumple el intervalo ≥ `RETENTION_MIN_INTERVAL_DAYS` desde el ancla, pero un
   segundo éxito el mismo día suma `retrieval_successes` (solo `retrieval_days`
   deduplica por día). El consumo es informativo (`item_competence_matrix`
   usa `retrieval_days`, `services/lexicon.py:442-495`); impacto bajo, pero la
   columna no es "días" ni "intentos independientes".
2. **`appearances`/`exposures` como volumen bruto**: `item_mastery`
   (`services/lexicon.py:222-251`) satura `min(appearances,3)/3` y
   `min(production_days,2)/2` en la parte productiva, y el reconocimiento se
   separó en volumen (0.4) y días (0.6). La "exposición voluminosa ≠
   oportunidades independientes" se corrigió solo en el lado receptivo; la
   producción sigue mezclando volumen con días sin exigir espaciado. Ver
   hallazgos preliminares 5/6.
3. **Perfil por destreza agrega en un mismo `evidence_count` filas de distinta
   naturaleza** (SKILL-01): MC (`item_type=mcq`) y producción (speaking/
   writing/pronunciation/controlled) conviven en `evidence_count` y
   `evidence_by_kind`; `production_count` los separa solo para R5
   (`PRODUCTION_ITEM_TYPES`, `services/academy.py:458-466`). El score de la
   destreza, sin embargo, no sale de ahí sino de los estados por objetivo:
   ver F-K3.

### P4 — ¿Qué alimenta REALMENTE mastery?

Nada léxico. Las filas `vocabulary`, la matriz de competencia y los contadores
`retrieval_*`/`context_tags`/`spaced_*` son **señal** (D5/E3): no entran en
`academy_evidence` ni en `sync_fsrs_cards` más que como razón `why` y score de
siembra. Mastery se mueve **solo** por `apply_objective_evidence`/
`apply_skill_evidence` invocados desde los `submit_*` con objetivo y desde
Assessment 2.0/examen de nivel. Fijado por: `test_academy.py` (objective
assessment actualiza mastery, 726; attempts no conceden mastery, 700),
`test_evidence_invariants.py` (191) y el grep de consumidores (retrieval no
alimenta FSRS ni mastery — comprobado también por dossier J, "Reglas del
juego", línea 99).

## Claims verificados contra el código (con test que los fija)

| Claim | Evidencia de código | Test que lo fija (pasa en G1/G2) | Resultado |
|---|---|---|---|
| **K-C1** `next_mastery_state` = EMA + `0.7·recent + 0.3·min(1,streak/3)`; decay con evidencia peor | `services/academy.py:70-112` (constantes `MASTERY_ALPHA`, `STREAK_TARGET`); `repositories/academy.py::apply_*_evidence` (72/138) | `test_academy.py::test_next_mastery_state_decays_with_bad_evidence` (266), `::test_next_mastery_state_streak_and_confidence` (276), `::test_apply_skill_evidence_persists_and_decays` (285) | ✔ |
| **K-C2** Dominio de objetivo exige umbral por destreza **y** `minimum_attempts` evidencias | `services/academy.py::objective_progress` (117-148) y `mastered_objective_ids` (150-170) | `test_academy.py::test_objective_progress_requires_minimum_attempts` (119), `::test_objective_progress_mastered_when_all_skills_met` (103) | ✔ |
| **K-C3** No contagio entre objetivos | `apply_objective_evidence` es por (objetivo, destreza); el perfil solo promedia los estados del objetivo | `test_academy.py::test_mastery_is_per_objective_not_contagious` (129), `::test_aggregate_skill_mastery_derives_from_objectives` (1110) | ✔ |
| **K-C4** Escritor único y validación de evidencia (kinds canónicos) | `domain/academy.py::_record_evidence_validated` (411-437); `services/academy.py::evidence_record_errors` (739-794) y `EVIDENCE_KINDS` (698) | `test_evidence_invariants.py` (55-148: pases y rechazos, kind ausente → familiar, kind desconocido → inválido; 191: solo evidencia válida al assessment) | ✔ |
| **K-C5** `objective_progress` no evalúa destrezas productivas sin evidencia real | `services/academy.py:117-148` (solo `assessable_skills()`) | cobertura en `test_academy.py` (70-101 invariantes por objetivo) + gates de endpoints 814-920 | ✔ |
| **K-C6** Examen de nivel: aprobar completa y desbloquea; **completado ≠ certificado** | `domain/academy.py::submit_exam` (3579-3657): `record_level_completion` (3632), `certification_gate` (3647-3651) | `test_academy.py::test_exam_pass_unlocks_next_level` (515), `::test_exam_pass_completed_but_certification_pending` (552), `::test_level_becomes_certified_with_delayed_evidence` (583) | ✔ |
| **K-C7** Certificación exige `delayed` por cada destreza del examen (ventana ≥7 días, ratio estable) | `services/assessment_v2.py::certification_gate` (370-410), `RETENTION_MIN_DAYS=7` (58), `RETENTION_STABLE_RATIO=0.9` (61), `CERTIFICATION_REQUIRED_DELAYED=1` (69); `delayed` solo lo escribe el retention reassessment (`evidence_kind_for`, 543-548) | `test_assessment_v2.py::test_certification_gate...` (118-131), `::test_ladder_level_certified_requires_retention_step` (134); `test_academy.py::test_level_becomes_certified_with_delayed_evidence` (583) | ✔ |
| **K-C8** `record_retrievals`: intervalo ≥1 día desde el ancla `min(first_seen, first_exposed_at)`; dedupe por día en `retrieval_days` (no en `successes`) | `repositories/vocabulary.py::record_retrievals` (133-183) y `_earliest_day` (185-188); umbrales `services/lexicon.py:62-63` | `test_vocabulary.py::test_record_retrievals_requires_interval_since_anchor` (461), `::test_record_retrievals_dedupe_by_day_and_counts` (485), `::test_record_retrievals_without_anchor_ignored` (507) | ✔ |
| **K-C9** `item_recall` usa la actividad más reciente | `services/lexicon.py::_last_activity_at` (260-285) y `item_recall` (287-295) | `test_lexicon.py::test_item_recall_uses_most_recent_activity` (208), `::test_item_recall_decays_over_time` (195) | ✔ |
| **K-C10** La matriz léxica es derivada pura e informativa; espaciado ≠ retención; retención por recuperación demorada | `services/lexicon.py::item_competence_matrix` (442-495); deuda de renombre comentada (470-471) | `test_lexicon.py` (460-650: matriz all-false, gaps, transfer por 2 contextos mismo canal, espaciado ≠ retención 523/546, retención por días de retrieval 567/589) | ✔ |
| **K-C11** El grafo usa dimensiones canónicas y `mastery` = media aritmética de dimensiones; `limiting_factor` señala pero no limita la cifra | `services/evidence_graph.py`: `GRAPH_VERSION` 30, `_declared_dimensions` 132, `dimension_scores` 159-240 (novel como cobertura 0.5 si no hay transfer, 174-181), `limiting_factor` 242, `mastery_from_dimensions` 259, `objective_node` 278 | `test_evidence_graph.py`, `test_session_graph.py`, `test_graph_plan.py` (G1) | ✔ |
| **K-C12** FSRS-lite: cartas skill/lexicon/objective; seed desde evidencia; retrieval V3.23 **no** entra en el scheduler | `domain/academy.py::sync_fsrs_cards` (1751-1874): skill solo con `evidence_count>0` (1770-1778), lexicon solo desde filas existentes de `vocabulary` (no siembra ítems ausentes) con `why` por objetivo (1806-1860), objective en micro-review (1865-1892); `services/fsrs.py` (seed_card_from_evidence 161, why_for_lexicon 383, due_queue 351); cola sin `objective` (1976-1989) | `test_fsrs_transfer_gap.py` (G1), `test_fsrs.py::test_fsrs_due_and_review_http` (143), `test_unit_review_endpoints.py::test_fsrs_due_and_summary_exclude_objective_cards` (739) | ✔ (matiz: filas sembradas por lección/objetivo aún entran como tarjeta sin señal — LEX-03) |
| **K-C13** Estimado etiquetado `estimated_*`; sin evidencia → Pre-A1, no A1 | `services/adaptive.py::estimated_level` (59-88); `domain/academy.py::build_student_model` (609-648); `domain/profile.py` (146-170) | `test_academy.py::test_endpoint_student_model_empty` (1389-1408), `::test_endpoint_cefr_ladder_empty_user` (1410-1445) | ✔ |
| **K-C14** DEMONSTRATED exige retención + mínimo de la matriz CEFR + producción (destrezas productivas); vocabulary se capa en FUNCTIONAL | `services/competence.py::competence_state` (73-170): `retention_ok` con `delayed>0` o ruta demostrada (104-106), `matrix_min_ok` vía `evidence_depth_report` (109-113), `production_ok` para `PRODUCTION_SKILLS` (114), `SUPPORT_SKILLS` cap (145-149) | `test_competence.py`, `test_cefr_matrix.py` (G1) | ✔ |
| **K-C15** MASTERED (Assessment 2.0) exige familiar×2 + transfer + **novel** + delayed | `services/assessment_v2.py::mastery_evidence_gate` (412-438) con `MASTERY_EVIDENCE_REQUIREMENTS` (72-78) | `test_assessment_v2.py::test_mastery_evidence_gate_requires_full_ladder` (156-164) | ✔ (ver F-K1) |

## Puntos donde una agregación se proyecta a etiqueta CEFR (Fase 5)

| Punto | Código | ¿Es "estimado"? | Riesgo |
|---|---|---|---|
| `/api/profile` `estimated_level`/`estimated_bands` | `domain/profile.py:146-174` | sí (prefijo `estimated_`) | **alto** — escala no calibrada por nivel y rebase al matricular nivel nuevo (F-K2, reproducido en G4) |
| `/api/profile` `skills[].band` (SkillState) | `domain/profile.py::_skill_band`/`_bands_from_skills` (65-91) y `_skill_states` (93-110) | NO lleva prefijo; banda heurística de `score` continuo | la UI del perfil la presenta como banda de la destreza; es un **estimado** heurístico de un score de progreso en el nivel (ver F-K3/F-K4) |
| Placement → `level` | `services/academy.py::theta_to_level` (900-914), `placement_result` (797), `submit_placement` (3392) | NO (es un nivel del instrumento de placement, sin evidencia previa del modelo) | el nivel de placement es estimación pura y no entra en la cadena; si la UI lo mezcla con "nivel CEFR" puede confundir (ver F-K2) |
| `speaking/level`, `writing/level`, journey/diagnostic | `routers/academy.py:437-458`; agregados propios de speaking/writing sobre sus filas de evidencia | parcial (cada endpoint expone su propio nivel continuo + score de criterios) | niveles de superficie separados del Student Model; el perfil y estos endpoints pueden divergir |
| `competence_states[].state` | `services/competence.py::competence_state` (73) | no (es el estado demostrado con gates) | correcto: solo DEMONSTRATED con retención y mínimos |
| `readiness.overall/ready` | `services/adaptive.py::readiness` (149-…) | estimado hacia `target_level` | correcto si se lee como "preparación", no como certificación |
| `AssessmentLadder` `mastery_gate.met/missing` | `services/assessment_v2.py::ladder_status` (456-540) + `frontend/src/features/assessment/AssessmentLadder.tsx:155-157` | no | **F-K1**: `novel` sin emisor → siempre `met=false` |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| **F-K1** | **P1** | El evidence_kind **`novel` no tiene emisor** en v3.23, pero tres gates lo exigen: `mastery_evidence_gate` (novel ≥1, `assessment_v2.py:72-78,412-438`), readiness B2+ (`services/adaptive.py:177-206`, `novel_required` de `cefr_matrix.json`; B2 listening exige 1, C2 3 — tests `test_adaptive.py:150-164`, `test_cefr_matrix.py:44`), y la cobertura del grafo/evidence depth. Los únicos kinds emitidos son `familiar` (builders por defecto y formative), `transfer` (`evidence_kind_for` de unit/progress/level) y `delayed` (retention). **Consecuencia observable**: la escalera Assessment 2.0 muestra permanentemente "mastery_missing: novel" (`AssessmentLadder.tsx:155-157`), MASTERED nunca es alcanzable y la readiness a B2+ nunca concluye `ready` por vía de evidencia (no rompe certificación ni DEMONSTRATED, que no exigen novel). | `services/assessment_v2.py:543-548` (solo familiar/transfer/delayed); grep de escritores de evidencia (ningún call site con `novel`); `frontend/src/features/assessment/AssessmentLadder.tsx:155-157`; `test_assessment_v2.py:156-164` (el gate "complete" solo pasa con `novel` inyectado a mano) | O bien crear un emisor real de `novel` (una modalidad de la escalera o tarea que exija uso en contexto nunca practicado), o bien relajar/renombrar el gate y la matriz CEFR a lo emisible y documentarlo como frontera. Premisa 12: fijar el emisor con test de extremo a extremo. | abierto |
| **F-K2** | **P1** | **El estimado vive en un único nivel y su escala no está calibrada por nivel**: `_current_level_id` toma el nivel de mayor matrícula (`domain/academy.py:580-591`) y `build_student_model` (619-627) estima **solo** con ese nivel (sin niveles completados ni su evidencia). La escala continua `numeric = 1 + 5·overall` (`services/adaptive.py:66-78`) proyecta el porcentaje de dominio del currículo actual al eje CEFR absoluto. **Reproducido (G4)**: dominar todo A1 → `estimated_level=B2` (numeric 3.78); aprobar el examen A1 (passed, overall 1.0) y quedar matriculado en A2 → `estimated_level=Pre-A1` (numeric 1.0, cero evidencia en A2). El mismo alumno pasa de "B2" a "Pre-A1" en dos pasos seguidos solo por aprobar, y cualquier nivel recién matriculado arranca en Pre-A1 aunque el alumno tenga niveles completados. No rompe gates de progresión ni certificación, pero degrada la etiqueta central de la cadena ("tu nivel estimado") y mezcla dos conceptos: progreso en el nivel actual y competencia CEFR. | G4 (salidas reales); `domain/academy.py:619-627`; `services/adaptive.py:59-88`; no hay test que fije el salto de nivel (solo usuario vacío, `test_academy.py:1389-1408`) | Calibrar la escala por nivel (anclar la etiqueta a los niveles completados/certificados y al tramo del currículo actual, no a una proyección lineal absoluta del mastery de un solo nivel) y fijar con tests de extremo a extremo: (a) dominar A1 completo no debe estimar ≥ B2; (b) aprobar A1 no debe bajar el estimado por debajo de A1. | abierto |
| **F-K3** | P2 | **Speaking Assessment/Mission escriben evidencia que no mueve el score de la destreza** (doble vía, herencia CP-01/SKILL-01): sus filas van con `objective_id=""`, y el `score` de speaking en el Student Model sale solo de los estados por objetivo (`services/academy.py:398-445`). Un alumno con buen speaking en assessment/misión pero sin estados de objetivo mostrará speaking en `developing` (evidencia alta, score 0). El nivel "speaking" agregado de esas superficies vive en endpoints separados (`/speaking/level`, journey). La separación es intencional pero **no está documentada en la UI ni contrastada**, y la evidencia de misión se mezcla con la de assessment en el mismo pool `skill=speaking` sin `cefr_target` de la tarea (solo `difficulty`). | `domain/academy.py:968-973` (assessment part) y 1167-1174 (misión); `submit_assessment_v2` como único camino de nivel; `services/academy.py:398-445` (score solo desde objetivos); `routers/academy.py:437-458` | Separar por `source` en la agregación del perfil, persistir `cefr_target` de la tarea, y documentar/alinear la UI para que "nivel de speaking" (superficie) y "score de speaking" (objetivos) no se lean como lo mismo. | abierto |
| **F-K4** | P2 | **La etiqueta CEFR sin prefijo por destreza** (`SkillState.band`, `skills[].band`) es un estimado heurístico de un score de progreso del nivel, no competencia demostrada, y puede leerse como nivel certificable. El código la deriva de `heuristic_band(score)` con score = media de mastery por objetivo del nivel actual (K-C1/K-C3) → es una proyección de agregación con semántica de "estimado" sin la marca. | `domain/profile.py:65-110` (`_skill_band`/`_bands_from_skills`/`_skill_states`); `services/cefr.py::heuristic_band`; esquema `SkillState` (`schemas/profile.py`) | Renombrar el campo a `estimated_band` en el schema de perfil (o añadir campo explícito de demostrado) para que la UI distinga "estimado" de "demostrado" por destreza, coherente con R2/R4/R5/R7. | abierto |
| **F-K5** | P2 | **Colisión de nomenclatura "transfer"/"retention"** entre la capa léxica y la académica: `item_competence_matrix.transfer` = producción en ≥2 contextos `channel:activity` (`lexicon.py:442-495`) NO es el `evidence_kind="transfer"` académico (superar peldaño unit/progress/level, `assessment_v2.py:543-548`); la `retention` léxica (1 día, 1 recuperación) NO es la retención certificable §6.3 (≥7 días, ratio estable). Ambas parejas comparten etiqueta en schemas y UI. | `lexicon.py:442-495` vs `assessment_v2.py:370-410,543-548`; dossier J H2 (umbrales 1 día) | Documentar la distinción en schemas/tooltips (R2): la señal por ítem es informativa (D5/E3) y no comparte semántica con los gates de la capa académica. | abierto |
| **F-K6** | P2 | **Deuda de modelo agregado (hallazgo preliminar 8)**: la tabla `vocabulary` es agregada por palabra (una fila por ítem con contadores y últimos timestamps); los eventos finos (cuándo/cómo se produjo cada aparición) solo viven en `learning_events` y en las sesiones. El modelo léxico no puede reconstruir una historia de recuperaciones ni ventanas de práctica por ítem más allá de los contadores. No afecta a la cadena académica (D5/E3 respetado), pero limita el Student Model definitivo (scheduling, soporte por evento = V3.24). | `repositories/vocabulary.py` (record_production 65-123, record_exposures 192-233, record_retrievals 133-183); deuda comentada `lexicon.py:468-472` | Mantener la frontera V3.24 (support_level por evento); si se persigue precisión de retención léxica, considerar un log de eventos por ítem como fuente (append-only) y derivar la fila agregada. | abierto |
| **F-K7** | P3 | **Nomenclatura heredada `appearances`/`exposures`** (hallazgo preliminar 6): la columna que en realidad es `production_count` se llama `appearances`, y la deuda de renombre está comentada en `lexicon.py:470-471` sin migración. Semántica correcta en código, nombre confuso en schemas/UI. | `lexicon.py:470-471`; `schemas/vocabulary.py` (LexicalCompetence/LexiconSummary); dossier J (frontera: renombre no realizado) | Renombrado conceptual en schemas/UI sin migración destructiva, o documentación del mapeo. | abierto |
| **F-K8** | P3 | **Sin cobertura de test para el salto de nivel**: el único caso fijado del estimado es el usuario vacío en `a1` (K-C13, `test_academy.py:1389-1408`); no hay ningún test de extremo a extremo que fije la semántica del estimado al pasar de nivel (A1 completo → A2 matriculado). Cualquier fix de F-K2 deberá ir acompañado de estos tests (premisa 12). | `test_academy.py:1389-1408` (solo usuario vacío); G4 (el escenario de salto no está cubierto por la suite) | Añadir tests de extremo a extremo: dominar A1 → estimar; aprobar examen A1 → A2 → estimar. | abierto |

### Estado de los hallazgos preliminares del auditor (los que caen dentro del eje)

| # preliminar | Juicio del auditor | Resultado de la verificación | Severidad final |
|---|---|---|---|
| 1 — Retención léxica con umbrales de 1 día | demasiado débil | **confirmado**: `RETENTION_MIN_INTERVAL_DAYS=1` y `RETENTION_MIN_RETRIEVAL_DAYS=1` (`lexicon.py:62-63`) acreditan "retention" por ítem al día siguiente del ancla; es señal informativa (no alimenta evidencia/mastery), pero la UI la muestra como chip "Retention" con semántica mucho más débil que §6.3 | P2 (abierto; dossier J H2) |
| 2 — Ancla de retención demasiado antigua (`min(first_exposed_at, first_seen)`) | P2 hoy | **confirmado**: `_earliest_day` (`vocabulary.py:185-188`) toma la primera señal (p. ej. una exposición pasiva antigua en chat) como ancla; no afecta a la certificación académica (que ancla en la evaluación formal) | P2 (abierto) |
| 3 — Transfer aún no es "verdadera transferencia" | P1 | **parcial**: v3.23 mejora (contextos `channel:activity`; dos actividades del mismo canal cuentan, mismo día también). Sigue sin exigir espaciado ni consolidación: `transfer_contexts>=2` puede darse en una misma sesión (test `test_matrix_transfer_by_two_channels_same_day_no_retention`, 507). Además no cruza hacia la capa académica (F-K5) | P2 (reclasificado en v3.23) |
| 4 — `support_level` | frontera V3.24 | sin apariciones en v3.23 (frontera explícita respetada) | — |
| 5 — `item_mastery` mezcla señales | P1 futura | **parcialmente corregido**: el reconocimiento separa volumen (0.4) y días (0.6); la producción sigue mezclando volumen+días (`lexicon.py:222-251`). No afecta a evidencia (solo orden/FSRS seed) | P2 (futura) |
| 6 — `appearances` ambiguo | P2 | **confirmado**, deuda comentada sin migración (F-K7) | P3 |
| 7 — `retrieval_successes` acumula el mismo día | P2 | **confirmado** (P3 de las 4 preguntas); impacto bajo: `retrieval_days` deduplica y la matriz usa días | P2 |
| 8 — modelo sin historial de eventos rico | P1 arquitectónico | **confirmado** como deuda del modelo léxico agregado (F-K6); sin impacto académico hoy | P2 (P1 si el léxico pasa a alimentar scheduling fino) |
| 10 — propagación de `activity` | P3 | **confirmado**: call sites completos en superficies académicas y volcados; sin fugas a `other` en v3.23 (ver K-§1 y dossier J P1-04.3) | cerrado ✔ |

### Estado de los ítems abiertos del dossier I que tocan el eje

| Ítem dossier I | Estado en v3.23 | Evidencia |
|---|---|---|
| GRAPH-01 (grafo no distingue reconocimiento de producción) | **sigue abierta**: `dimension_scores` mezcla MC y producción; `transfer` = evidence_kind, no modalidad; discourse/interaction son proxies del speaking con `missing: False` siempre | `services/evidence_graph.py:159-240` |
| CP-01 (doble vía de "producción") | **sigue abierta** (relacionada con F-K3): `production_count` del Student Model y la matriz léxica por canal son dos vías sin unificar | `services/academy.py:458-466` vs `lexicon.py:442-495` |
| LEX-02 (práctica académica no alimenta léxico) | **sigue abierta** (parcial): no hay `record_exposure` fuera del chat; sí hay volcados de producción y retrievals de drill | `routers/chat.py:66,100`; grep de `record_exposures` |
| LEX-03 (siembra FSRS sin señal) | **parcialmente mitigada**: skill solo con `evidence_count>0`; lexicon solo desde filas con evento; pero la siembra curricular se produce al completar la lección (`domain/academy.py:2959`) y tras el assessment del objetivo (`3016`) vía `domain/vocabulary.py::seed_objective_vocabulary` (101-109), y esas filas `learning` sin exposures ni productions generan tarjeta `lexicon` con `item_mastery=0` que entra en la cola de repaso | `domain/academy.py:1806-1860` (filtro `status in weak/learning/known`); `test_lexicon.py:106` (seed no incrementa) |
| TOK-01/USE-01 (tokens léxicos descartados) | **siguen abiertas** (frontera V3.24) | `services/speaking_llm.py`, `services/writing_llm.py` |
| SKILL-01 (misión+assessment mezcladas en el pool speaking) | **sigue abierta** (ver F-K3) | `domain/academy.py:968-973,1167-1174` |
| CONV-02 (conversación guiada sin evidencia formal de interaction) | **sigue abierta** (decisión pendiente: emitir evidencia o documentar como práctica sin acceso al modelo) | `domain/conversation_routes.py` (volcado léxico 236-240) |

## Veredicto

**NO APROBADO PARA CIERRE DEL EJE 1 (v3.23.0) — con la cadena académica sólida
y dos P1 que deben decidirse antes de cerrar el Student Model.**

La cadena central actividad → `academy_evidence` → mastery por objetivo →
perfil → CEFR es determinista, está bien validada (escritor único, kinds
canónicos, gates de intentos, no contagio, certificación con `delayed` ≥7 días)
y queda fijada por **638 tests del eje reproducidos en verde**. Las premisas 21
y D5/E3 se respetan: nada léxico entra en la evidencia académica.

Pero el tramo de **salida** (CEFR estimado/demostrado) y la **coherencia del
modelo de evidencia** dejan dos P1 abiertos: **(F-K1)** el evidence_kind
`novel` no tiene emisor mientras tres gates (MASTERED, readiness B2+, grafo/
depth) lo exigen — con efecto visible permanente en la escalera Assessment 2.0 —
y **(F-K2)** el estimado se calcula con la escala de un único nivel sin calibrar
y re-basa al matricular un nivel nuevo — reproducido: dominar A1 estima **B2**
y aprobar el examen A1 devuelve el estimado a **Pre-A1** (G4). Les siguen P2
relevantes: F-K3 (doble vía de la evidencia de speaking assessment/misión),
F-K4 (etiqueta CEFR por destreza sin marca de estimado), F-K5 (colisión
semántica transfer/retention entre capas) y F-K6 (deuda del modelo léxico
agregado), más F-K7/F-K8 de higiene y cobertura. Los hallazgos preliminares del
auditor se confirman con matices (severidades ajustadas); los ítems del dossier
I siguen abiertos en el eje salvo mitigaciones parciales. Sin cambios de código
en esta auditoría (read-only); recomendación: decidir F-K1 y F-K2 en V3.24 con
tests de extremo a extremo.

## Regenerar / Verificar

```powershell
git log --oneline -3                  # HEAD bb3f253 · release v3.23.0 = f3739a9
git status --short                    # limpio; única escritura = dossier K (nuevo)

# Batería dirigida del Eje 1 (cd backend) — G1
.venv\Scripts\python.exe -m pytest tests/test_vocabulary.py tests/test_lexicon.py tests/test_academy.py tests/test_academy_goal.py tests/test_assessment_v2.py tests/test_cefr_matrix.py tests/test_competence.py tests/test_cross_skill.py tests/test_evidence_graph.py tests/test_evidence_invariants.py tests/test_session_graph.py tests/test_graph_plan.py tests/test_fsrs_transfer_gap.py tests/test_learning_events.py tests/test_pedagogical_invariants.py tests/test_curriculum_quality.py -q -p no:cacheprovider

# Batería complementaria — G2
.venv\Scripts\python.exe -m pytest tests/test_profile.py tests/test_placement.py tests/test_placement_2_0.py tests/test_placement_session.py tests/test_placement_validity.py tests/test_fsrs.py tests/test_golden_fsrs.py tests/test_adaptive.py tests/test_mastery.py tests/test_forgetting.py tests/test_cefr_semantics.py tests/test_reproducibility.py tests/test_user_profile.py tests/test_speaking.py tests/test_speaking_assessment.py tests/test_speaking_mission.py tests/test_speaking_routes.py tests/test_writing.py tests/test_pronunciation.py tests/test_pronunciation_academy.py tests/test_unit_review.py tests/test_drill_ladder.py tests/test_cross_user_isolation.py tests/test_store_append_only.py -q -p no:cacheprovider
```

Resultados reproducidos: G1 **310 passed** · G2 **328 passed** (638 total del
eje, 0 fallos, 1 warning de deprecación upstream de httpx/starlette).

## Tests que respaldan

- `test_academy.py` — `next_mastery_state`/decay (266-306), mínimos de
  intentos (119), no contagio (129), attempts sin mastery (700), objective
  assessment → mastery (726), examen completa/desbloquea/certifica (515-583),
  perfil por destreza desde objetivos (1064-1132), evidencia por kind (1002-
  1018), skill profile refleja evidence (1475), estudiante vacío → Pre-A1
  (1389-1408).
- `test_evidence_invariants.py` — validación de filas y kinds canónicos
  (55-191), `novel` válido como kind pero sin emisor (126-128).
- `test_lexicon.py` / `test_vocabulary.py` — semántica léxica completa:
  retrieval con intervalo/ancla (461-524), merges de `context_tags` (415/450),
  matriz y gaps (460-650), recall (195/208), seed sin incrementar (106).
- `test_assessment_v2.py` — gates MASTERED (156-164), certificación con
  `delayed` (118-154), `retention_due`.
- `test_adaptive.py` — readiness y `novel_required` B2+ (150-206).
- `test_cefr_matrix.py` — `novel_required` por nivel (44).
- `test_fsrs*.py`, `test_unit_review_endpoints.py` — cola FSRS sin cartas
  objective (739), due/review (143), transfer gap.
- `test_competence.py`, `test_cross_skill.py`, `test_evidence_graph.py`,
  `test_session_graph.py`, `test_graph_plan.py`, `test_profile.py`,
  `test_placement*.py`, `test_mastery.py` — estados de competencia, perfil,
  placement y grafo (G1/G2).

# Documento de relevo (handoff)

> **Propósito:** permitir que un agente/contexto **nuevo** retome el proyecto desde cero
> sin perder el hilo (premisa 8 y 12). Si el chat del gerente se satura o hay riesgo de
> alucinación, este documento es el ancla para reanudar.
> Actualizado por última vez: 2026-09-11 (UTC+2).
>
> **Nota (2026-09-11):** **V3.52.0 (Student Skill State + Difficulty Engine
> 2.0)** — release **v3.52.0**, ADITIVA con **dos columnas de BD** que NO cambia
> la escalera `transfer_state`, sus umbrales, `context_signals`,
> `context_diversity`, el scoring ni FSRS: cierra los DOS P1 de la auditoría
> externa de V3.51. **P1-01 (el `learner_level` no era el demostrado):** nuevo
> módulo PURO `services/student_state.py` (`LEVEL_SOURCES`, `floor_level`,
> `level_state`, `is_certified`, `empty_state`) que separa `practice_level` /
> `estimated_cefr` / `demonstrated_cefr` y deriva el SUELO de dificultad con la
> política conservadora **demostrado > estimado > declarado > ninguno** (el
> demostrado gana aunque su banda sea inferior: acredita retención; solo él exige
> `certification_gate` y usa tolerancia estricta). Migración aditiva:
> `learning_profile.estimated_level`/`demonstrated_level` (CREATE TABLE + bucle
> idempotente `ALTER TABLE`, filas legacy `''` que siguen alimentando el suelo
> como nivel DECLARADO `practice`), conservando `cefr_level`;
> `repositories.profile.get_profile` devuelve las dos columnas y nueva
> `set_level_state` (`set_cefr` queda de wrapper que no pisa el demostrado);
> `domain.profile.get_profile_summary` escribe AMBOS niveles y expone
> `demonstrated_level` (aditivo en `schemas/profile.py`); nuevo
> `domain.vocabulary._learner_level_state` lee la caché en O(1) (sin recalcular
> el Student Model) y pasa `learner_level` + `learner_level_source` a
> `context_for` con paridad GET↔POST. **P1-02 (el floor mezclaba escalas):**
> nuevo módulo PURO `services/difficulty.py` (`DIFFICULTY_DIMENSIONS`,
> `CEFR_CAPACITY` monótona con la `interaction` retrasada en A1–B1, `capacity_for`,
> `challenge_vector` = máximo por dimensión entre ítem (techo) y alumno (suelo),
> `fit` con distancia/`max_overshoot`/`within`, `select_by_difficulty` que
> conserva los `within` y, entre ellos, los de menor distancia, degradando al más
> cercano si ninguno encaja — nunca al más difícil; tolerancias
> `DIFFICULTY_TOLERANCE = 1` demostrado / `DIFFICULTY_TOLERANCE_ESTIMATED = 2`).
> `services/transfer.py` sustituye `_difficulty_floor`/`_within_band` escalares
> por el motor (el TECHO lingüístico del ítem sigue en `_within_level: una
> unidad A1 con alumno C2 NO recibe contextos > A1`; `TRANSFER_DIFFICULTY_BAND`
> queda DEPRECADA y `TRANSFER_DIFFICULTY_KEYS` pasa a alias del vocabulario
> canónico) y su retorno gana `difficulty_fit` + `learner_level_source`
> (aditivos; `difficulty`/`difficulty_vector` se conservan). Contratos aditivos
> `TransferContextOut.learner_level_source`/`difficulty_fit`,
> `LearningProfile.demonstrated_level` y espejo opcional en `types/api.ts`
> (`DrillTransferContext`/`DrillDifficultyFit`). **Deuda confirmada y diferida
> (V3.55):** `assessed_skill` → decisión del planner y `skill_priorities` →
> `select_task` (evitar el doble conteo de `written_production` con el drill
> `write`). Tests: pytest **2158 passed** (+39: `test_student_state_v352.py` 15 y
> `test_difficulty_engine_v352.py` 24; ajuste de
> `test_learner_level_raises_the_difficulty_floor` a `difficulty_fit`), `ruff`
> limpio, `check_release_consistency` **3.52.0** exit 0. Fuera de alcance:
> Sense Engine 2.0, `observed_difficulty` persistido, entrega oral real del
> transfer, `expected_learning_value`/Adaptive Planner 2.0, Context Bank
> Family/Instance, offline TTS y code splitting del frontend.
>
> **Nota (2026-09-11):** **V3.51.0 (Task/Skill semantics + learner-level
> difficulty matching)** — release **v3.51.0**, ADITIVA con **una columna de BD**
> que NO cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS:
> cierra los tres P1 de la auditoría externa de V3.50. **P1-01 (qué se EVALÚA):**
> nuevo módulo PURO `services/task_semantics.py` con `ASSESSMENT_MODES`
> (`written`/`spoken`/`receptive`), la tabla `TASK_SEMANTICS` por actividad
> (`target_skill` = lo que la tarea QUIERE provocar, `assessed_skill` = lo que
> puede MEDIR, `assessment_mode` = canal, `evidence_skill` = el `skill=` histórico
> del ledger) y helpers que nunca lanzan (`semantics_for`, `assessed_skill_for`,
> `assessment_mode_for`, `target_skill_for`, `evidence_skill_for`,
> `assessable_skills`, `is_assessable`, `activity_for_target`,
> `activity_from_activity_id`). El drill **Transfer**, que se entrega por TEXTO,
> declara `target_skill="spontaneous_use"`, **`assessed_skill="written_production"`**,
> **`assessment_mode="written"`** y conserva `evidence_skill="spontaneous_use"`:
> antes se podía afirmar que el contexto «servía para hablar» sin que la
> actividad midiera oral. **Ledger honesto (migración aditiva):**
> `learning_evidence.assessed_skill` (CREATE TABLE + bucle idempotente
> `ALTER TABLE`, filas legacy `''`), persistido en
> `record_evidence`/`record_evidence_bulk`/`list_evidence`; `summarize_evidence`,
> `empty_summary` y `summarize_by_target` añaden
> `assessed_skill_attempts`/`assessed_skill_successes` (intentos = todos los
> eventos; éxito = clave creada en el éxito) con paridad exacta pura↔SQL; las
> cinco vías de `domain/vocabulary.py` registran las dos dimensiones sin cambiar
> `skill`. **P1-03 (el argmax descarta información):**
> `planner.skill_priorities(signals)` expone el vector COMPLETO en orden canónico
> y `limiting_skill` pasa a ser su argmax; `_transfer_target_skill` elige solo
> entre `task_semantics.assessable_skills("transfer")` (`written_production`,
> `spontaneous_use`) y `context_for`/`ReviewQueueItem` exponen `skill_priorities`
> (aditivo). **P1-02 (de quién es la dificultad):**
> `context_for(..., learner_level="")`; `level` = CEFR del ÍTEM (techo,
> `_within_level`) y `learner_level` = nivel DEMOSTRADO del alumno (suelo de reto
> en `_difficulty_floor`, que usa `max(item_index, learner_index)`);
> `domain.vocabulary._learner_level` lee la caché del Student Model
> (`learning_profile.cefr_level`, O(1)) sin recalcular el modelo en el camino
> caliente; sin nivel conocido el resultado es IDÉNTICO a V3.50 (test de
> regresión). Contratos aditivos `TransferContextOut` (target/assessed/mode/
> item_level/learner_level/skill_priorities), `TransferAttemptOut`
> (target/assessed/mode) y `ReviewQueueItem.skill_priorities`, con espejo
> opcional en `types/api.ts`. Tests: pytest **2119 passed** (+20: nuevo
> `test_task_semantics_v351.py`; ajuste del contrato exacto de `empty_summary` en
> `test_learning_evidence_v336.py`), vitest **75 ficheros/641 tests**, `ruff`/
> `tsc` limpios, `npm run build`, `check_beta_v3.py`, `content_validation.py` y
> `check_release_consistency` **3.51.0** exit 0. **CI 6/6 en verde** (run
> [34599637351](https://github.com/jvelasca/english-tutor/actions/runs/34599637351)
> sobre `c056546`): Release consistency, Backend (ruff + pytest), Frontend
> (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content
> validation. **P3-01:** corregida la cifra de
> V3.50 (2099 → **2097 passed**, la verificada en CI). Fuera de alcance (V3.52+):
> entrega oral real del transfer (audio+STT), Sense Engine 2.0,
> `observed_difficulty` por evento, `expected_learning_value`/Adaptive Planner
> 2.0, Context Bank Family/Instance y offline TTS.
>
> **Nota (2026-09-11):** **V3.50.0 (Context→Skill mapping + difficulty
> matching)** — release **v3.50.0**, ADITIVA y **SIN migración de BD** que NO
> cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS: cierra
> el candidato diferido por V3.49.0. Hasta V3.49 el banco declaraba `cefr` y
> `difficulty_vector` (V3.47/V3.48) y el planner calculaba la modalidad limitante,
> pero `context_for` solo miraba usados/nivel/novedad: un ítem B1 podía recibir el
> contexto A1 más plano y dos ítems con modalidades débiles distintas recibían el
> mismo escenario. **Parte A — Context→Skill mapping:** nuevo vocabulario
> declarado `CONTEXT_SKILLS` (`recall`/`written_production`/`spoken_production`/
> `spontaneous_use`), espejo verificado por test de
> `services.evidence.LEXICAL_SKILLS` y declarado en `services/transfer.py` para no
> crear el ciclo `evidence → transfer → evidence`; los 20 contextos del banco
> ganan `skills` curado (subconjunto no vacío, con al menos una modalidad de
> producción y `spontaneous_use` donde el escenario admite uso libre) y los 6
> originales conservan `id` y valores core congelados (solo se les AÑADE
> `skills`); helper puro `context_skills(context)` (acepta dict/`id`/`context_id`,
> deduplica, ordena por `CONTEXT_SKILLS`, ignora valores fuera del vocabulario,
> nunca lanza). **Parte B — Difficulty matching:** `TRANSFER_DIFFICULTY_BAND = 1`,
> `_difficulty_floor(pool, level)` fija el objetivo como la MAYOR del techo real
> de dificultad alcanzable y la posición del nivel en la escala 1..6 (A1≈1 … C2≈6;
> anclar al nivel era necesario con los datos reales del banco, porque sin él un
> ítem B1 seguía recibiendo contextos A1) y `_within_band(pool, floor)` degrada
> con gracia a lo más difícil disponible si la banda no existe en el pool
> filtrado. `context_for` gana la firma aditiva `skill=""` y un pipeline
> determinista (usados → `_within_level` → mínimo sobre todo el alcance →
> preferencia por modalidad limitante → banda → novedad V3.43 → `_stable_index`);
> el retorno añade `skills`. Consumo en `domain/vocabulary.py` con
> `_transfer_target_skill` (`planner.limiting_skill(planned_signals(summary,
> item_competence_matrix(row)))`, `""` si no hay segmentación por modalidad) en el
> GET y en el fallback del POST, con paridad de `context_id` GET↔POST. Contratos
> aditivos `TransferContextOut.skills` (`schemas/vocabulary.py`) y
> `DrillTransferContext.skills?` (`types/api.ts`); sin cambio de UI. Tests: pytest
> **2097 passed** (+15: nuevo `test_context_skill_v350.py`; ajuste de
> `test_transfer_cefr_v347.py`, cuya semántica «con C2 la elección es la de sin
> nivel» queda superada por el difficulty matching), vitest **75 ficheros/641
> tests** (sin cambios), `ruff` limpio, `tsc --noEmit` limpio, `npm run build`,
> `check_beta_v3.py`, `content_validation.py` y `check_release_consistency`
> **3.50.0** exit 0. **CI 6/6 en verde** (run
> [34594042697](https://github.com/jvelasca/english-tutor/actions/runs/34594042697)
> sobre `1c8d6e0`). Fuera de alcance (V3.51+):
> Sense Engine 2.0, semantic appropriateness, `expected_learning_value`/Adaptive
> Planner 2.0 y la persistencia de la dificultad del contexto servido por evento.
>
> **Nota (2026-09-11):** **V3.49.0 (Transfer Evidence 3.0 — confianza del eje de
> transferencia)** — release **v3.49.0**, ADITIVA y **SIN migración de BD** que NO
> cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS: cierra el
> punto 8 de la auditoría de V3.43.0 («los nombres de los estados pueden sugerir
> más evidencia de la disponible»). Nueva función PURA
> `services.evidence.transfer_confidence(evidence, *, now="")` →
> `{score, level, sample, drivers, recency_days}`: `score` es la suma ponderada
> (`TRANSFER_CONFIDENCE_WEIGHTS`, suman 1.0) de seis `drivers` 0..1 derivados de
> evidencia YA registrada por `context_signals` (`contexts` = contextos con éxito
> limpio / `TRANSFER_STABLE_MIN_CONTEXTS`; `successes` = `clean_successes` con
> techo `2 * TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED`; `diversity` =
> `diverse_dimensions` / nº de ejes core; `independence` =
> `unscaffolded_clean_successes` / `clean_successes`; `variety` = objetivos
> comunicativos distintos / `TRANSFER_STABLE_MIN_GOALS`; `spacing` =
> `clean_success_days` / `TRANSFER_STABLE_MIN_DAYS`). `level` ∈
> `none`/`low`/`medium`/`high` (`TRANSFER_CONFIDENCE_LEVELS`, umbrales
> `TRANSFER_CONFIDENCE_HIGH = 0.80` / `TRANSFER_CONFIDENCE_MEDIUM = 0.45`)
> calibrados para que `transfer_stable` caiga en `high` y `transfer_demonstrated`
> quede por debajo. Es **monótona no decreciente** al añadir evidencia NO
> andamiada (cada driver lo es) y **conservadora** en resúmenes legacy/parciales
> (`none`, sin inflar y sin lanzar); `recency_days` es INFORMATIVO (`now`
> opcional) y NO entra en el `score` (la decisión no usa reloj, igual que
> `transfer_state`). Se deriva en la MISMA frontera pura↔SQL
> (`with_transfer_state`), así que resumen puro y SQL exponen el mismo valor, y
> `empty_summary()` gana el default neutro. Explicabilidad en
> `planner.planned_signals` (aditivo; `transfer_gap`/`has_contextual_transfer` NO
> cambian) y en `lexicon.review_item`, con contrato aditivo
> `ReviewQueueItem.transfer_confidence` (`schemas/learning.py`) y
> `TransferConfidence` (`types/api.ts`). UI honesta en `ReviewQueueSection`
> (etiqueta solo con evidencia, `title`/`aria-label` que aclaran «transferencia
> contextual demostrada bajo el protocolo interno», no generalizada) con claves
> `dictionary.review.transfer.level.*`/`scope` en paridad es/en. Tests: pytest
> **2084 passed** (+9: nuevo `test_transfer_confidence_v349.py`; ajuste del
> contrato exacto de `empty_summary` en `test_learning_evidence_v336.py`), vitest
> **75 ficheros/641 tests** (+2 en `ReviewQueueSection.test.tsx`), `ruff` limpio,
> `tsc --noEmit` limpio, `npm run build` y `check_release_consistency` **3.49.0**
> exit 0. **CI 6/6 en verde** (run
> [34591158824](https://github.com/jvelasca/english-tutor/actions/runs/34591158824)
> sobre `034da5c`). Fuera de alcance (V3.50+): Context→Skill mapping y difficulty matching
> por `difficulty_vector` (datos de V3.47/V3.48 aún no consumidos por el
> planner), Sense Engine 2.0 (surface→lemma→sense), semantic appropriateness
> (punto 7) y `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.48.1 (APRENDER más limpio + ruta CEFR seleccionada)**
> — patch **v3.48.1**, **SOLO-FRONTEND** (más un script de mantenimiento), **sin
> cambios de contrato ni migración de BD**. **(A) Listening sin «Antes de
> escuchar»:** `microFlow` salta los pasos `stage === "pre"` (`firstRenderableIndex`)
> y el flujo arranca en `while1`; se eliminan la tarjeta y las claves
> `listening.flow.preTitle`/`preHint`/`begin`, y el contexto del ítem pasa a
> caption compacta bajo el botón de audio (el backend sigue sirviendo `pre` por
> contrato, sin alterar `transcript_policy`). **(B) Notas CEFR plegables:** nuevo
> `components/InfoDisclosure.tsx` (`button` + `aria-expanded` + `MoreHorizontal`,
> montado solo al abrir; variantes `inline`/`corner`) que pliega
> `routeNote`/`routeCertNote`/`routeRingHelp`/`routesMapHint` en Listening y en el
> mapa de rutas de las cinco destrezas (`QuizRoutesSection`), y la prosa
> explicativa (`demonstrateNote`/`demonstrateFormal`/`extraHonestNote`) en los seis
> paneles de nivel, dejando visibles los estados accionables (gate/`demoNotYet`).
> **(C) Ruta CEFR seleccionada persistente:** `utils/selectedRoute.ts` (validación
> `A1..C2`, parseo tolerante, `resolveRouteLevel`) y `hooks/useSelectedRoute.ts`
> (persistencia doble `localStorage` + `selected_route_level` en `GET/PUT
> /api/settings`, sin cambios de backend); prioridad **sesión > ruta seleccionada
> > nivel recomendado**, pulsar un anillo A1–C2 selecciona y abre su panel (anillo
> resaltado + «Ruta seleccionada»), chip «Auto» para volver al motor y
> `exitSession` que conserva la selección. **(D) Limpieza:**
> `scripts/purge_virtual_testers.py` (dry-run por defecto; `--apply` con copia
> `tutor.db.bak-<ts>` y borrado transaccional enumerando tablas con `user_id`) y
> eliminación de los 6 perfiles `Visual Tester` (quedan los 2 reales). Tests:
> vitest **75 ficheros/639 tests** (+3/+16: `InfoDisclosure`, `selectedRoute`,
> `useSelectedRoute`), `check_i18n_coverage` 0 indefinidas/0 duplicadas,
> `tsc`/`build`/`check_release_consistency` **3.48.1** en verde. **CI 6/6 en verde** (run [34588975928](https://github.com/jvelasca/english-tutor/actions/runs/34588975928) sobre `6a0a757`). Fuera de alcance
> (V3.49): Sense Engine 2.0, Context→Skill mapping, difficulty matching y
> Transfer evidence 3.0; no se tocan FSRS, Evidence Ledger ni el gate.
>
> **Nota (2026-09-11):** **V3.48.0 (Context Bank 2.0 + diversidad 2.0)** —
> release **v3.48.0**, ADITIVA, **sin migración de BD** y sin tocar la escalera
> `transfer_state`, el scoring ni FSRS, que cierra los dos P2 abiertos por la
> auditoría externa de V3.43.0 sobre la transferencia. **(A) Context Bank 2.0:**
> `services/transfer.py` amplía `TRANSFER_CONTEXTS` de **6 a 20 contextos** —14
> nuevos (`introductions`, `routine`, `directions`, `shopping`, `health`,
> `travel_plan`, `work_problem`, `community`, `debate`, `review`, `mediation`,
> `academic`, `negotiation`, `keynote`)— con cobertura **A1:3 / A2:4 / B1:4 /
> B2:3 / C1:3 / C2:3**; cada contexto declara los 6 atributos core, `cefr`,
> `difficulty_vector` (`lexical`/`syntax`/`discourse`/`interaction`, 1..5) y los
> ejes de variedad, y ningún `prompt` contiene `{word}` (la consigna da un
> escenario, nunca el target). Los **6 contextos originales quedan congelados**
> (mismos `id` y valores core; guardia por test) para no reinterpretar la
> evidencia histórica que referencia sus `context_id`. **(B) Diversidad 2.0
> informativa:** nuevos `CONTEXT_VARIETY_DIMENSIONS` (`register`/
> `lexical_environment`/`syntactic_focus`), función pura `context_variety`
> (`{dimensions, varied_dimensions, score}`) y `context_dimensions(...,
> dimensions=...)` generalizada vía `_normalize_dimensions`; `context_diversity`
> conserva sus cuatro claves históricas y añade `variety`. **El gate NO cambia:**
> `CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score` y
> `diverse_dimensions` mantienen la semántica de V3.47 y `CONTEXT_DIVERSITY_MIN
> = 2` se conserva (la distancia mínima entre pares del banco ampliado es `>= 2`);
> `empty_summary()["context_diversity"]` gana el default `variety` por paridad
> pura↔SQL. Contrato aditivo (`ContextDiversity.variety` en `types/api.ts`).
> **Sin cambio de UI.** Tests: pytest **2075 passed** (+12: nuevo
> `test_context_bank_v348.py`; ajustes en `test_transfer_v343.py` y
> `test_learning_evidence_v336.py`), vitest **72 ficheros/623 tests** (sin
> cambios), `ruff` limpio, `tsc --noEmit` limpio, `npm run build` y
> `check_release_consistency` **3.48.0** exit 0. **CI 6/6 en verde** (run
> [34583804612](https://github.com/jvelasca/english-tutor/actions/runs/34583804612)
> sobre `3438e55`); mismo commit de release `3438e55` que cierra V3.48.0. Fuera
> de alcance (V3.49+): TTS/offline (auto-descarga implícita de voces), Sense
> Engine 2.0, `transfer_state` enriquecido (`confidence`/`recency`) y
> `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.47.0 (Transfer Evidence 2.0 + CEFR/`difficulty_vector`
> del contexto)** — release **v3.47.0**, doble y ADITIVA, **sin migración de BD**
> y sin tocar el scoring ni FSRS, que cierra los dos P1 abiertos por la auditoría
> de V3.46.0 sobre la transferencia. **(A) Transfer Evidence 2.0:** la escalera
> `transfer_state` deja de acreditar transferencia con un único éxito no
> andamiado. `services/evidence.py` define `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED
> = 2` (2 éxitos limpios en condiciones NO andamiadas para
> `transfer_demonstrated`), `TRANSFER_STABLE_MIN_DAYS` `2 → 3` y
> `TRANSFER_STABLE_MIN_GOALS = 2` (objetivos comunicativos distintos);
> `TRANSFER_STABLE_MIN_CONTEXTS = 3` se mantiene. `context_signals` expone la
> evidencia fina (`unscaffolded_clean_success_contexts`/`_days`,
> `clean_success_goals` derivados de `communicative_goal`,
> `last_clean_success_at`/`last_unscaffolded_clean_success_at`; la decisión NO usa
> reloj) y `empty_summary` los defaults neutros. Fallback legacy intacto (sin
> datos de condición se conserva la regla anterior) y paridad pura↔SQL por
> construcción. **(B) CEFR/`difficulty_vector`:** los 6 contextos de
> `services/transfer.py` declaran `cefr` (`services.cefr.CEFR_LEVELS`) y
> `difficulty_vector` (`lexical`/`syntax`/`discourse`/`interaction`, 1..5,
> convención listening/speaking); nuevos helpers puros `difficulty_from_vector`
> (media redondeada, clamp 1..6) y `cefr_index`; `context_for(..., level="")`
> (retrocompatible) prefiere contextos de nivel ≤ al del alumno y, si ninguno es
> alcanzable, cae al nivel más cercano por arriba; el contrato devuelve
> `cefr`/`difficulty_vector`/`difficulty` (`TransferContextOut` y
> `DrillTransferContext`). `domain/vocabulary.py` pasa `level=row.get("cefr")`.
> **Sin cambio de UI.** Tests: pytest **2063 passed** (+16; nuevos
> `test_transfer_evidence_v347.py` y `test_transfer_cefr_v347.py`; ajustes en
> `test_transfer_v340.py`/`v343.py`/`test_transfer_condition_v346.py` y
> `test_learning_evidence_v336.py`), vitest **72 ficheros/623 tests** (sin
> cambios), `ruff` limpio, `tsc --noEmit` limpio, `npm run build` y
> `check_release_consistency` **3.47.0** exit 0. **CI 6/6 en verde** (run
> [34582697000](https://github.com/jvelasca/english-tutor/actions/runs/34582697000)
> sobre `1aa16af`). Fuera de alcance
> (V3.47.1/V3.48): TTS/offline (auto-descarga implícita de voces), Sense Engine
> 2.0, Context Bank 2.0, `transfer_state` enriquecido (`confidence`/`recency`) y
> `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.46.0 (Condición de recuperación en la
> transferencia — `transfer_condition`)** — release **v3.46.0** que cierra el P1
> `transfer_condition` de la auditoría de V3.43.0, **aditiva y sin migración
> destructiva**. Hasta ahora TODO intento de transferencia era `spontaneous_use`
> con `support_level="spontaneous"`, sin distinguir si la unidad se usó porque se
> pidió (`prompted`), porque el escenario la insinuaba (`cued_context`), por
> decisión propia en un escenario abierto (`open_context`), por elección libre
> (`free_choice`) o porque surgió sola (`naturally_emergent`); sin esa dimensión
> `transfer_demonstrated` podía declararse con tareas ANDAMIADAS.
> `services/transfer.py` define `TRANSFER_CONDITIONS` (andamiaje decreciente),
> `SERVABLE_CONDITIONS` (`prompted`/`cued_context`/`open_context`),
> `UNSCAFFOLDED_CONDITIONS` (`open_context`/`free_choice`/`naturally_emergent`),
> `REQUIRED_TARGET_CONDITIONS`, `CONDITION_INSTRUCTIONS`, `normalize_condition`
> (valores desconocidos → `""`) y la escalera PURA `condition_for_state`
> (`not_ready` con intentos → `prompted`; `not_ready` sin intentos y `emerging` →
> `cued_context`, comportamiento de V3.43; `contextualized`+ → `open_context`,
> unidad NO obligatoria). La condición la DERIVA el servidor del resumen del
> ledger (premisa 21: el cliente nunca la declara). Persistencia aditiva
> `transfer_condition TEXT NOT NULL DEFAULT ''` en `learning_evidence` (ALTER
> idempotente) con plumbing en `record_evidence`/lote/`list_evidence`/SELECT de
> detalle (paridad pura↔SQL por construcción: el resumen SQL reutiliza la MISMA
> `context_signals`). `services/evidence.py` agrega `transfer_conditions`
> (`{condición: {attempts, clean_successes}}`), `success_conditions` y
> `unscaffolded_clean_successes`, y **endurece `transfer_demonstrated`**: además
> de 2 contextos limpios con diversidad real (`diverse_dimensions >= 2`), exige
> ≥1 éxito limpio NO andamiado; sin datos de condición (legacy/parcial) se
> conserva la regla anterior (cero regresión). `domain/vocabulary.py` sirve,
> re-deriva y persiste la condición, y un intento de `open_context` que NO usa la
> unidad no se registra (`required_target=false`). Contratos aditivos
> (`condition`/`required_target`/`unscaffolded`) y UI del drill con la condición
> visible y aviso neutro `transferNotRequired`. Tests: pytest **2047 passed**
> (+17; nuevo `test_transfer_condition_v346.py`; ajustes en
> `test_learning_evidence_v336.py` y `test_transfer_v340.py`), vitest **72
> ficheros/623 tests** (+2 en `wordDrill.test.tsx`), `ruff` limpio, `tsc
> --noEmit` limpio, `npm run build` y `check_release_consistency` **3.46.0**
> exit 0. **CI 6/6 en verde** (run
> [34578101387](https://github.com/jvelasca/english-tutor/actions/runs/34578101387)
> sobre `107d8ec`); el commit de release agrupa V3.44 + V3.45 + V3.46 porque
> ninguno se había commiteado desde v3.43.0 (mismo caso que v3.42.0). Fuera de
> alcance (V3.47+): CEFR/`difficulty_vector` del contexto (P1
> restante), Context Bank 2.0, diversidad 2.0, semantic appropriateness,
> transfer_state enriquecido y `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.45.0 (Traductor de viaje práctico + voz española
> real)** — release **v3.45.0** que cierra la experiencia del Traductor de viaje.
> **(A) Voz española real:** la salida en español sonaba a «un inglés hablando
> español» porque `language="es"` degradaba a la voz inglesa (no había voces
> `es_*` instaladas, `download_models.py` solo bajaba la inglesa y
> `resolve_voice` caía al fallback global). Ahora
> `SPANISH_VOICE = "es_ES-davefx-medium"` y
> `DEFAULT_VOICES = {"en": PIPER_VOICE, "es": SPANISH_VOICE}`; la pura
> `default_voice_for(language)` y `resolve_voice` priorizan el default del
> idioma (preferencia del usuario del idioma → default del idioma instalado →
> primera instalada del idioma → fallback global; con `en` idéntico al
> histórico). `ensure_voice_for_language(language)` (no-op si ya hay voz del
> idioma; descarga el default del catálogo curado vía
> `services.voice_downloads`; `False` sin red/disco, NUNCA lanza) se ejecuta en
> `/api/tts` antes de resolver la voz, así que la primera petición en español
> instala la voz y sintetiza con ella sin 500 si no hay red;
> `download_models.py` instala también la española reutilizando el catálogo.
> Contrato aditivo: `VoicesResponse.defaults` (idioma → voz por defecto).
> **(B) Modo Conversación:** `TranslatorScreen` gana dos pestañas
> (**Conversación** por defecto, **Escribir** intacto). Nuevos
> `useVoiceTurn.ts` (MediaRecorder + AnalyserNode + VAD + transcripción; helper
> PURO `nextTurnVadState` que cierra por silencio ≥ `SILENCE_MS` tras voz ≥
> `MIN_SPEECH_MS` y descarta picos de ruido; auto-stop 120 s),
> `BigMicButton.tsx` (botón `size-24` con anillo según nivel),
> `ConversationPanel.tsx` (por idioma, con repetir audio, avisos de micro/
> transcripción y rotación) y `ConversationTranslator.tsx` (dos paneles; cada
> turno se transcribe, traduce y —si el auto-play está activo— se reproduce en el
> idioma del interlocutor; historial en
> `english-tutor.translator-conversation`; toggles «Reproducir automáticamente»
> y «Cara a cara»; tamaño de texto; aviso y descarga en segundo plano de la voz
> española). i18n `translator.mode.*`/`translator.conversation.*` con paridad
> es/en. El Traductor sigue siendo **AUXILIAR**: no registra evidencia ni toca
> FSRS. Tests: pytest **2030 passed** (+10; `test_voices.py`), vitest **72
> ficheros/621 tests** (+13; `useVoiceTurn.test.ts`,
> `ConversationPanel.test.tsx` y `TranslatorScreen.test.tsx` con pestañas),
> `ruff` limpio, `tsc --noEmit` limpio, `npm run build` y
> `check_release_consistency` **3.45.0** exit 0. Fuera de alcance (V3.46+):
> `transfer_condition` + CEFR/`difficulty_vector` del contexto (P1), Context Bank
> 2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y
> `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.44.0 (Lexicón sense-aware + scoring semántico
> 2.0)** — release **v3.44.0** que cierra los dos P1 conceptuales que la
> auditoría externa de V3.43.0 (9,6/10) deja abiertos, **sin migración de datos
> y con contratos aditivos**. **P1-01 (sense-aware):** el proxy semántico deja
> de usar la `pos` GLOBAL como sustituto de sentido. El contrato de contenido
> gana `senses` (`GENERATOR_VERSION` `1.3.0 → 1.4.0`, regeneración lazy una sola
> vez) con el helper puro `normalize_senses` (pos canónico, dedupe por
> `(pos, gloss)`, tope `MAX_SENSES = 4`, orden estable; nunca invalida
> definición/traducción). Persistencia aditiva `senses_json TEXT NOT NULL DEFAULT
> ''` en `dictionary_entries` **y** `dictionary_reverse_entries` (migración
> idempotente con `PRAGMA table_info` + `ALTER TABLE`, también en la tabla
> inversa ya creada; JSON ilegible → `[]`). Nuevo módulo **PURO**
> `services/semantics.py`: `pos_family` (por palabras, no subcadenas),
> `families_from_senses` (con fallback a la `pos` global), `unit_positions`,
> `occurrence_role` (cues FUERTES: pronombre sujeto, auxiliar/`to`, flexión
> `-ed`/`-ing`; DÉBILES: determinante, `-s`/`-ies`; las unidades multi-palabra se
> abstienen) y `semantic_adequacy`. `domain/vocabulary.py` prefiere los sentidos
> de la `lexical_unit` y cae a la superficie; `_build_dictionary_entry` expone
> `senses`. Así `I plan my trip.` deja de ser falso positivo si `plan` declara
> sentido verbal. **P1-02 (scoring robusto):** `score_transfer_attempt(word,
> text, *, pos="", senses=())` mantiene `passed`/`lexical_transfer` y devuelve
> `adequacy` ∈ `fit`/`suspect`/`incorrect`/`unknown`: `incorrect` (contradicción
> fuerte con TODAS las familias) → `semantic_mismatch` es el **ÚNICO** valor que
> bloquea el clean success; `suspect` → `semantic_doubt` (nueva const en
> `TRANSFER_ERROR_TYPES`) es **advisory** y NO destruye la evidencia léxica; sin
> sentidos/POS → `unknown` (nunca bloquea). `semantic_fit: bool | None` se
> conserva y `score_write_attempt` mantiene su contrato exacto (4 claves).
> `context_signals` excluye SOLO `semantic_mismatch`, así que `semantic_doubt`
> cuenta como éxito limpio y `transfer`/`transfer_state` avanzan con él (paridad
> pura↔SQL por construcción). Contratos aditivos: `DictionaryEntryOut.senses`
> (+ `DictionarySenseOut`), `adequacy` admite `incorrect`, y `wordDrill.tsx`
> avisa de `incorrect` con `dictionary.drill.transferSemanticWrong` (warning, sin
> bloquear `onProduced`). Tests: pytest **2020 passed** (+31; nuevos
> `test_senses_v344.py` y `test_transfer_v344.py`; ajustes en
> `test_transfer_v343.py`, `test_dictionary_content_v330.py` y
> `test_situational_cue_v338.py`), vitest **70 ficheros/608 tests** (+1), `ruff`
> limpio, `tsc --noEmit` limpio, `npm run build` y `check_release_consistency`
> **3.44.0** exit 0. Dossier de la auditoría externa:
> `docs/audit/P-AUDITORIA-TOTAL-V343.md`. Fuera de alcance (V3.45+):
> `transfer_condition`, CEFR/`difficulty_vector` del contexto, Context Bank 2.0
> y `expected_learning_value` / Adaptive Planner 2.0.
>
> **Nota (2026-09-11):** **V3.43.0 (Transfer 2.0)** — release **v3.43.0** que
> cierra los 4 P1 de la auditoría de V3.42.0 sobre la evidencia de transferencia.
> **P1-01 (target oculto):** `services/transfer.py` reescribe
> `TRANSFER_CONTEXTS` con atributos (`topic`, `communicative_goal`,
> `discourse_type`, `social_relation`, `time_reference`, `register`,
> `interaction_type`) y consignas que **nunca contienen `{word}`**;
> `context_for(word, used_context_ids, *, success_context_ids)` ya no sustituye
> el target, prioriza el contexto de mayor DISTANCIA mínima a los ya logrados y
> expone `communicative_goal`/`discourse_type`. El drill oculta la palabra
> también en `transfer` (cabecera con `transferHiddenTarget`, revelada tras el
> intento) y la cola deja de mostrarla (`showsWord` sin `transfer`).
> **P1-02 (semanticidad):** `score_transfer_attempt(word, text, *, pos="")`
> separa `lexical_transfer` (alias de `passed`) de la adecuación
> (`semantic_fit`/`adequacy` = `fit`/`suspect`/`unknown`) con un proxy
> DETERMINISTA y advisory (`_semantic_fit`: POS `noun` usada como verbo o POS
> `verb` tras determinante → `suspect`); el uso léxicamente correcto pero
> sospechoso conserva `passed=True` y guarda `error_type="semantic_mismatch"`
> (nueva `TRANSFER_ERROR_TYPES`), sin bloquear la evidencia léxica.
> `domain/vocabulary.py` lee la `pos` de `dictionary_entries` y la pasa al
> scorer; el drill muestra `dictionary.drill.transferSemanticWarning` sin dejar
> de llamar a `onProduced`. Se documenta (P2-04) que `score_write_attempt`
> acredita producción LÉXICA, no corrección gramatical ni ortográfica.
> **P1-03 (diversidad real):** `context_signals` añade
> `clean_contexts`/`clean_successes`/`clean_success_contexts`/`clean_success_days`
> y `context_diversity` (ÉXITO LIMPIO = éxito sin `semantic_mismatch`); `transfer`
> exige `>= CONTEXT_TRANSFER_MIN` contextos limpios **y**
> `diverse_dimensions >= CONTEXT_DIVERSITY_MIN = 2`. **P1-04 (estado):** nueva
> `transfer_state` + `TRANSFER_STATES` (`not_ready` → `emerging` →
> `contextualized` → `transfer_demonstrated` → `transfer_stable` → `automatic`)
> y `with_transfer_state`; `has_contextual_transfer`/`transfer_gap` leen el
> estado (`transfer_state` respeta el booleano `transfer` de un resumen
> legacy/parcial: lo lee como DEMOSTRADA, nunca estable) y `planned_signals`
> expone `transfer_state`/`context_diversity`. Contratos HTTP aditivos
> (`TransferContextOut`/`TransferAttemptOut`/`ReviewQueueItem`), sin migración.
> Tests: pytest **1989 passed** (+14, `test_transfer_v343.py`; ajustes en
> `test_transfer_v340.py` y `test_learning_evidence_v336.py`), vitest **70
> ficheros/607 tests** (+1), `ruff` limpio, `tsc --noEmit` limpio, `npm run
> build` y `check_release_consistency` **3.43.0** exit 0. **Publicada y
> auditable:** commit `04d8db92df8ea12c247c460ee263bf46a189a406` (tag
> `v3.43.0`) con el run
> [34571938704](https://github.com/jvelasca/english-tutor/actions/runs/34571938704)
> **6/6 jobs en success**. La auditoría pre-release del árbol de trabajo
> corrigió P2-02 (`transfer_state` respeta el booleano `transfer` de un resumen
> legacy/parcial) y dejó abierto P2-01 (falsos positivos del proxy semántico en
> palabras noun/verb). Fuera de alcance
> (V3.44): modelo *sense-aware*, Context Bank a escala y
> `expected_learning_value`.
>
> **Nota (2026-09-10):** **V3.42.0 publicada (Fase 4 y CIERRE del plan maestro
> V3.39+)** — release **v3.42.0** (**transferencia contextual real + actividad
> `spontaneous_use` + gobierno por unidad léxica**). Cuarta y última de las
> cuatro fases acordadas (diccionario reversible → Traductor → motor de tarea
> óptima → transferencia real). **Transferencia ≠ recuperación contextualizada:**
> `services/transfer.py` (puro) define el banco curado de contextos nuevos
> (`TRANSFER_CONTEXTS`) y la elección determinista del que toca
> (`context_for(word, used_context_ids)`: filtra los `context_id` ya usados y
> elige por hash ESTABLE `zlib.crc32` —no el `hash()` sembrado—, rotando sobre el
> banco completo con `exhausted=True` al agotarse). `services/evidence.
> context_signals` (pura, reutilizada por el resumen SQL) agrupa el ledger por
> `context_id` y expone `contexts`/`context_attempts`/`success_contexts`/
> `home_context`/`transfer` (éxito en ≥ `CONTEXT_TRANSFER_MIN = 2` contextos
> distintos). `planner.transfer_gap` decide cuándo pedirla: exige contexto
> registrado, ≥ `TRANSFER_MIN_SUCCESSES = 2` éxitos y <
> `TRANSFER_MIN_SUCCESS_CONTEXTS = 2` contextos con éxito (sin ventana devuelve
> `False`); `transfer_gap` entra como último motivo de `EVIDENCE_REASON_ORDER`.
> **La modalidad `spontaneous_use` deja de medirse sin tarea:** actividad
> `transfer` con `lexicon.score_transfer_attempt`, `GET /api/vocabulary/drill/
> transfer-context` (solo lectura; sin `context_id` del cliente el servidor lo
> deriva del banco) y `POST /api/vocabulary/drill/transfer-attempt` (evidencia
> `spontaneous_use`, `activity_id="drill:transfer"`, apoyo `spontaneous` y el
> `context_id` del contexto NUEVO). **Gobierno por `lexical_unit`:** `lexicon.
> unit_evidence(rows, evidence_by_word)` suma contadores y mapas de las formas
> hermanas, **recalcula** `success_rate` del total, une `automatic`/
> `automatic_skills`/`success_contexts` y deriva `transfer`; `ReviewQueueOut.units`
> (aditivo) y `ReviewQueueItem.unit_surfaces`/`transfer`/`success_contexts`
> exponen el roll-up sin cambiar la evidencia por forma. **Descomposición de
> `wordDrill.tsx`:** peldaños presentacionales extraídos a
> `features/vocabulary/wordDrillSteps.tsx` (`RecognitionStep`/`RecallStep`/
> `ProductionTextarea`/`TransferStep`) sin cambiar el contrato; la escalera pasa
> a 5 peldaños y la cola abre `transfer` con `initialStep`. Tests: pytest
> **1975 passed** (+15, `test_transfer_v340.py`; `test_learning_evidence_v336.py`
> ajustado al contrato de `empty_summary`), vitest **70 ficheros/606 tests**
> (+4), `ruff` limpio, `tsc --noEmit` limpio y `check_release_consistency`
> **3.42.0** exit 0. **Plan maestro V3.39+ completo: sin fases pendientes.**
> **Publicada y auditable:** commit
> `3522bac4592beffe92df9fae5fbd3cae817fdc28` (tag `v3.42.0`) con el run
> [34540962417](https://github.com/jvelasca/english-tutor/actions/runs/34540962417)
> **6/6 jobs en success**. Ese commit **agrupa las cuatro fases** (v3.39.0 →
> v3.42.0) porque el trabajo vivió en el árbol de trabajo y las releases
> intermedias no llegaron a commitearse: **no hay estados intermedios
> auditables**, y la auditoría fase a fase se hace sobre las notas versionadas
> (`release-notes-v3.39.0.md` … `release-notes-v3.42.0.md`), no sobre commits
> intermedios.
>
> **Nota (2026-09-10):** **V3.41.0 publicada (Fase 3 del plan maestro V3.39+)** —
> release **v3.41.0** (**motor de tarea óptima por skill + actividad de escritura
> + robustez de señales**). Tercera de las cuatro fases acordadas (diccionario
> reversible → Traductor → motor de tarea óptima → transferencia real). El
> planner deja de responder "¿qué palabra repaso?" y responde **"¿qué modalidad
> limita, qué actividad la cierra y con qué apoyo?"**: `planner.skill_priority`
> aplica `PRIORITY_WEIGHTS` a las señales por modalidad, `planner.limiting_skill`
> devuelve el argmax con desempate por `LEXICAL_SKILLS` (sin segmentación cae en
> `recall`) y `planner.select_task(matrix, evidence, signals)` devuelve
> `{skill, activity, reason, support_level}` con orden declarado `error_prone` →
> `skill_gap` → `slow_recall`. `ACTIVITY_FOR_SKILL` mapea la modalidad a la
> actividad (`recall`, `sentence`, **`write`**) y `ACTIVITY_SUPPORT_LEVEL`
> declara el andamiaje; `evidence_reason` queda como fachada estable y
> `priority`/`signals`/`why` conservan su semántica. **El hueco simétrico
> `spoken ✓ / written ✗` ya es accionable:** nueva actividad `write` con
> `services/lexicon.score_write_attempt` (puro, sin LLM: `unit_produced` sobre la
> frase propia + `WRITE_MIN_WORDS = 4`, taxonomía `WRITE_ERROR_TYPES`),
> `domain/vocabulary.submit_write_attempt`, endpoint nuevo
> `POST /api/vocabulary/drill/write-attempt` y paso `write` en `wordDrill.tsx`
> (la cola lo abre con `initialStep`). **Señales robustas:** `services/evidence.
> recency_signals` (ventana de `RECENT_WINDOW_EVENTS = 10`, `recent_error_rate`,
> `recent_wrong_word`, `median`/`p75`/`p90_response_time_ms` por rango más
> cercano, `recent_response_time_ms`, `latency_trend`), reutilizada por
> `repositories/evidence.summarize_by_target` (paridad por construcción);
> `_has_grave_error` y `error_prone` miran la VENTANA; `is_automatic` se
> **unifica** con `automatic_skills` cuando el resumen trae segmentación (el
> criterio global de V3.38.1 queda como fallback de resúmenes parciales/legacy);
> el ledger encadena el intervalo al evento **cronológicamente anterior**
> (`last_evidence_at(..., before=now)`) y `example_for_many` batchea los ejemplos
> del `cloze` en una sola pasada al banco. **Contratos HTTP aditivos:**
> `ReviewQueueItem.limiting_skill`/`ReviewQueueItem.task` y los campos nuevos del
> resumen (sección `LexicalEvidence`). Tests: pytest **1960 passed** (+36),
> vitest **70 ficheros/602 tests** (+5), `ruff` limpio, `tsc --noEmit` limpio y
> `check_release_consistency` **3.41.0** exit 0. Diferido a la **Fase 4**:
> transferencia contextual real (contextos A/B/nuevos con evidencia por
> `context_id`), actividad propia de `spontaneous_use`, agregación del estado
> pedagógico por `lexical_unit` y descomposición de `wordDrill.tsx`.
>
> **Nota (2026-09-10):** **V3.40.0 publicada (Fase 2 del plan maestro V3.39+)** —
> release **v3.40.0** (**Traductor de viaje bidireccional ES↔EN, 5.º destino**).
> Segunda de las cuatro fases acordadas (diccionario reversible → Traductor →
> motor de tarea óptima → transferencia real). **Nuevo destino AUXILIAR**
> `translator` con ruta propia `/traductor` (`TRANSLATOR_PATH`, `routeMap`
> reversible de 10 valores y `pathToRoute` de `#/traductor`), registrado en
> `ROUTES` justo tras el diccionario —mismo bloque auxiliar tras el separador—,
> icono `Languages` y bottom-nav `grid-cols-4 → grid-cols-5`; el corte de las
> píldoras de cabecera se mantiene en `xl` (con `overflow-x-auto` como red de
> seguridad). **`TranslatorScreen`** (`features/translator/`): conmutador de
> dirección ES→EN / EN→ES con **ES→EN por defecto** (el caso del viajero),
> botón ⇄ que intercambia sentido y textos, entrada por voz (`MicButton`, que
> ahora acepta `language` y auto-detiene a los 120 s) o de texto, panel de
> resultado con `ListenButton` por idioma para escuchar origen y destino,
> historial reciente (8 frases) en `localStorage`
> (`english-tutor.translator-history`) con reutilización y borrado, y aviso de
> utilidad de apoyo. Es **solo lectura pedagógica**: no crea evidencia, no toca
> `vocabulary` y es válida sin perfil. **Backend:** `services/translate.py` pasa
> a BIDIRECCIONAL (`_SYSTEM_PROMPT_ES_EN` nuevo, caché por `(direction, text)`,
> dirección desconocida → `"en-es"`), `TranslateRequest.direction`
> (`Literal["en-es","es-en"]`, defecto `"en-es"` → 422 si no), `TTSRequest.language`
> (defecto `"en"`), `resolve_voice(prefs, language="en")` puro con
> `voice_language(id)` (preferida del idioma → default del idioma → primera voz
> del idioma → fallback global documentado) y tres voces `es_*` **medium** en el
> catálogo curado de Piper (`es_ES-davefx-medium`, `es_ES-sharvard-medium`,
> `es_MX-ald-medium`, descargables desde Ajustes → Voces). Todo aditivo y
> retrocompatible: sin `direction`/`language` el comportamiento es el histórico
> de las pantallas de práctica. Tests: pytest **1924 passed** (+14),
> vitest **70 ficheros/597 tests** (+2 ficheros/+19), `ruff` limpio,
> `tsc --noEmit` limpio y `check_release_consistency` **3.40.0** exit 0.
> Diferido a las fases siguientes: **Fase 3** motor de tarea óptima por skill
> (`skill_priority`/`limiting_skill`/`select_task`) + ruta de escritura
> `written_production` + robustez de señales; **Fase 4** transferencia
> contextual real, actividad `spontaneous_use`, agregación por `lexical_unit` y
> refactor de `wordDrill.tsx`.
>
> **Nota (2026-09-10):** **V3.39.0 publicada (Fase 1 del plan maestro V3.39+)** —
> release **v3.39.0** (**Diccionario reversible EN↔ES + persistencia de la
> pestaña Personal/Consultar**). Primera de las cuatro fases acordadas
> (diccionario reversible → Traductor → motor de tarea óptima → transferencia
> real). **Diccionario ES→EN:** doble escalón — (1) inversa INSTANTÁNEA sobre las
> traducciones ya cacheadas, nuevo servicio PURO `services/dictionary_reverse.py`
> (`match_translation`: segmenta glosas `, ; / |`, quita paréntesis y artículos
> iniciales, pliega acentos conservando la eñe, puntúa exacto > parcial y
> deduplica en orden determinista); (2) generación con el modelo local solo si no
> hay coincidencia, en la tabla PROPIA `dictionary_reverse_entries` (aislada de
> `dictionary_entries` para no contaminar el banco de distractores del MCQ;
> `word` ES como PK + `english`/`pos`/`definition`/`situation`/`generator_version`).
> `GENERATOR_VERSION` 1.2.1 → **1.3.0** (una sola política de frescura para las
> dos direcciones; la caché directa se regenera una vez) con
> `parse_reverse_content`/`generate_reverse_content` (reutiliza el validador puro
> `services/situation.py` sobre el equivalente inglés). La fontanería de
> generación (single-flight, negative cache, rate limit) se indexa por
> `(direction, word)`. Contrato HTTP **aditivo**: `DictionaryLookupRequest.direction`
> (defecto `"en-es"`) y `DictionaryEntryOut.direction`/`alternatives`. La consulta
> inversa sigue siendo SOLO LECTURA (D3) y su marca de uso es la del EQUIVALENTE
> INGLÉS. **Frontend:** conmutador EN↔ES en `DictionaryLookup` (con `lang`/
> placeholder por dirección), tarjeta reetiquetada (término ES de cabecera,
> inglés como «In English», definición EN y `alternatives`) y puente de práctica
> que practica SIEMPRE el término inglés; `lookupDictionaryWord(userId, word,
> direction)` + tipos TS. **Persistencia de pestaña:** hook `useDictionaryView`
> con patrón doble (`localStorage` `english-tutor.dictionary-view` +
> `settings.dictionary_view`, hidratación al cambiar de usuario), integrado en
> `DictionaryScreen` y en el conmutador incrustado de `QuizRoutePage`. Tests:
> pytest **1910 passed** (+20, nuevo `test_dictionary_reverse_v339.py`), vitest
> **68 ficheros/578 tests** (nuevos ES→EN + `DictionaryScreen.test.tsx`), `ruff`
> limpio, `tsc --noEmit` limpio y `check_release_consistency` **3.39.0** exit 0.
> Diferido a las fases siguientes: **Fase 2** Traductor bidireccional por voz
> (5.º destino, voces Piper `es_*`); **Fase 3** motor de tarea óptima por skill
> (`skill_priority`/`limiting_skill`/`select_task`) + ruta de escritura
> `written_production` + robustez de señales; **Fase 4** transferencia contextual
> real, actividad `spontaneous_use`, agregación por `lexical_unit` y refactor de
> `wordDrill.tsx`.
>
> **Nota (2026-09-10):** **V3.38.1 publicada** — release **v3.38.1** (**Cierre
> quirúrgico de los P1 del Planner + UI de diccionario y estado**). Release
> ADITIVA que NO añade funcionalidad: cierra los 4 P1 de la auditoría de V3.38.0
> y endurece `situation`, sin migración de BD y sin tocar scoring, FSRS ni la
> semántica del intervalo de evidencia. **(P1-01) Planner globalmente óptimo:**
> `domain/review.py` separa la cota de CANDIDATOS
> (`REVIEW_QUEUE_CANDIDATE_LIMIT = 500`) del límite de PRESENTACIÓN: el planner
> compara TODAS las vencidas y el recorte se aplica DESPUÉS del ranking por
> `priority`; las cues se resuelven solo para los ítems servidos (de paso, deja
> de pagarse `example_for` por todas las vencidas). **(P1-02) Señales por
> modalidad:** `summarize_evidence`/`summarize_by_target` (paridad exacta
> pura↔SQL) añaden `skill_attempts` y `skill_mean_response_time_ms`;
> `planned_signals` gana el bloque `skills` (attempts/successes/success_rate/
> weakness/support/latency por modalidad, aún sin entrar en `priority_score`) e
> `is_slow_recall` mide la latencia DE `recall` exigiendo un éxito de recall (ya
> no la media global, que mezclaba modalidades). **(P1-03) `skill_gap` parcial
> accionable:** basta con que falte `spoken_production` (caso `written ✓ / spoken
> ✗`) para dirigir la siguiente tarea a `sentence`; el hueco simétrico se expone
> pero no emite razón hasta que exista un drill de escritura (V3.39). **(P1-04)
> Automaticidad robusta:** `AUTOMATIC_MIN_INDEPENDENT` 2 → **3** + nueva ratio
> `AUTOMATIC_MIN_SUCCESS_RATIO = 0.80` + ausencia de fallo grave (`wrong_word` >
> `AUTOMATIC_MAX_WRONG_WORD_ERRORS = 1`), aplicado a `is_automatic` y a
> `automatic_skills`. **(P2-01) `situation` endurecida:** nuevo módulo puro
> `services/situation.py` como única fuente de verdad (UN hueco, UNA sola frase,
> sin fuga morfológica REGULAR de la diana), usado por la generación
> (`GENERATOR_VERSION` 1.2.0 → **1.2.1**, regeneración lazy de la caché) y por la
> lectura de la escalera (una situación cacheada inválida no se sirve ni cuenta
> como peldaño disponible). **UI:** ruta dedicada `/diccionario` (`DICTIONARY_PATH`
> + `routeMap` + cuarto destino tras un separador + `DictionaryScreen` con
> Personal/Consultar; las píldoras de la cabecera pasan a montarse desde `xl`
> porque con 4 destinos con etiqueta no caben por debajo de 1280px sin invadir
> las acciones, y la bottom-nav cubre hasta entonces) y estado de conexión en la
> cabecera (`ConnectionIndicator` con punto verde/rojo y popover `SystemStatus`),
> retirando la barra inferior (`StatusBar.tsx` y reglas CSS huérfanas). Contrato aditivo (`LexicalEvidence`
> gana dos histogramas; `planned_signals` gana `skills`). Tests: pytest **1890
> passed** + `ruff` limpio + vitest (**67 ficheros/568 tests**) + `tsc`/build
> limpios + `check_release_consistency` **3.38.1** exit 0 + **CI 6/6 en verde**
> (run [34500794657](https://github.com/jvelasca/english-tutor/actions/runs/34500794657)
> sobre el commit `856e115`, que corrige el corte de la navegación `md` → `xl`
> tras el fallo de Playwright E2E en tablet del commit de release `217ebfe`).
> Diferidos a V3.39:
> prioridad completa por skill, routing de escritura de `written_production`,
> `sense`/CEFR/contexto y transferencia real (V3.23), pesos del planner y
> recencia ponderada, `example_for_many` y refactor de `wordDrill.tsx`.
>
> **Nota (2026-09-10):** **V3.38 publicada** — release **v3.38.0** (**La
> siguiente tarea óptima: `situación`, planner y automaticidad por skill**).
> Cierra el incremento que V3.37 dejó abierto, en tres frentes. **(1) P1-03
> (automaticidad por modalidad).** El `skill` del ledger léxico deja de ser
> `""`: `services/evidence.py` declara el vocabulario canónico
> `LEXICAL_SKILLS` (`recall`, `written_production`, `spoken_production`,
> `spontaneous_use`) y el mapeo canal→skill (`production_skill`); los caminos de
> escritura (`domain/vocabulary.py`) declaran la modalidad. `summarize_evidence`/
> `empty_summary` y `summarize_by_target` añaden `skill_successes`/
> `skill_success_days`/`skill_independent_successes`/`skill_independent_days`
> (**paridad exacta pura↔SQL** fijada por test) y `automatic_skills` segmenta la
> automaticidad por modalidad: un ítem ya no es "automático" por mezclar
> reconocimiento con producción. **Sin migración** (la columna `skill` ya existía
> desde V3.36.0). **(2) Planner (Optimal Next Task).** Nuevo servicio puro
> `services/planner.py`: `planned_signals` (olvido, hueco, debilidad, dependencia
> de apoyo y latencia), `priority_score` con `PRIORITY_WEIGHTS` declarados y
> `evidence_reason` (`error_prone`, `skill_gap`, `slow_recall`), integrados en
> `recommend_review_activity`. La cola (`domain/review.py`) se ordena por
> `priority` (desempate por `retrievability` y palabra) y cada ítem expone
> `priority`/`signals`/`why`/`automatic_skills` — aditivos y sin spoiler.
> **(3) `situación`.** `GENERATOR_VERSION` 1.1.0 → **1.2.0** y nueva columna
> `dictionary_entries.situation` (**migración aditiva e idempotente**, con
> backfill `''`): un enunciado situacional con un único hueco `_____`, validado
> de forma determinista (un solo hueco, sin spoiler, ≤ `MAX_SITUATION_CHARS`) y
> descartado —sin invalidar definición/traducción— si no cumple.
> `RECALL_CUES` gana `situation` como TECHO de la escalera con apoyo `guided`;
> `next_recall_rung` solo llega a él con `cloze` consolidado y
> `resolve_recall_cue` sigue degradando solo hacia más apoyo; el GET/POST del
> drill lo sirven y lo declaran (`drill:recall:situation`) y la cola lo
> recomienda cuando hay contenido. Contrato aditivo (`LexicalEvidence`,
> `ReviewQueueItem`, `DictionaryEntry`); sin tocar scoring, FSRS ni la semántica
> del intervalo de evidencia (V3.35.1 P1-01). Tests: pytest **1880 passed**
> (+56: nuevos `test_skill_segmentation_v338.py`, `test_planner_v338.py` y
> `test_situational_cue_v338.py`) + ruff limpio + vitest (65 ficheros/**560**) +
> `tsc --noEmit` limpio + `check_release_consistency` **3.38.0** exit 0.
> Se actualizan las expectativas de V3.37/V3.37.1 (el techo pasa de `cloze` a
> `situation`). Diferidos a V3.39: deudas de V3.30 + transferencia por contexto
> V3.23 + `cloze_coverage` de corpus + `example_for_many` de la Review Queue +
> refactor de `wordDrill.tsx`.
> **CI verificable:** commit `002af70d3f480068f8a04d2449a635c196475721`
> con el run [34493744848](https://github.com/jvelasca/english-tutor/actions/runs/34493744848)
> en `success` (6/6 jobs).
>
> **Nota (2026-09-10):** **V3.37.1 publicada** — release **v3.37.1**
> (**Política de consolidación y regresión de la escalera de recall**). Patch
> quirúrgico que cierra los dos P1 pedagógicos de la auditoría de V3.37.0, sin
> migración de BD (el peldaño ya se declaraba en `activity_id` desde V3.37.0) y
> sin tocar scoring ni FSRS. **P1-01:** `services/recall.py` añade
> `RECALL_RUNG_PASS_MIN_SUCCESSES = 2` / `RECALL_RUNG_PASS_MIN_DAYS = 2` y
> `_rung_passed`: un peldaño (`translation`/`definition`/`cloze`) solo se da por
> SUPERADO con varios éxitos en DÍAS NATURALES distintos (un acierto suelto o el
> volumen del mismo día no ascienden; la progresión pasa a EVIDENCIA →
> CONSOLIDACIÓN → MÁS EXIGENCIA). El umbral se mide sobre los ÉXITOS DEL PROPIO
> PELDAÑO, no sobre `independent_successes`, porque `cued`/`guided` nunca son
> `independent` y exigir automaticidad bloquearía la escalera. **P1-02:**
> `RECALL_REGRESSION_FAILURES = 2` y una política determinista:
> `next_recall_rung` BAJA al peldaño inmediatamente inferior (más apoyo) si el
> peldaño ideal acumula ≥2 fallos SIN ningún éxito; nunca baja de `translation`,
> fallar jamás hace subir y la recomendación no oscila (el peldaño inferior ya
> está consolidado). `resolve_recall_cue` no cambia: sigue degradando SOLO hacia
> más apoyo. El resumen de evidencia añade `recall_rung_days` y
> `recall_rung_failures` (`services/evidence.py` + `summarize_by_target` con
> **paridad pura↔SQL**), consumiendo el `activity_id`
> `drill:recall:<peldaño>` que V3.37 ya escribía: **sin migración**. La evidencia
> legacy `drill:recall` (sin peldaño) no alimenta ninguna de las dos políticas
> (no es evidencia negativa ni acredita peldaños que no declaraba). Contrato
> aditivo: `LexicalEvidence` amplía esos dos histogramas (schema Pydantic y tipo
> TS); el resto del contrato HTTP no cambia y la cola sigue sin spoilear (P1-03
> de V3.35.1 intacto). Tests: pytest **1824 passed** (+11, nuevo
> `test_recall_policy_v3371.py` con la matriz éxito/fallo/regresión/legacy/
> paridad) + ruff limpio + vitest (65 ficheros/**560**) + `tsc --noEmit` limpio +
> `check_release_consistency` **3.37.1** exit 0.
> **CI verificable:** commit `654c12f98728bf3f61648014aa9c9bb87755168a`
> con el run [34480419514](https://github.com/jvelasca/english-tutor/actions/runs/34480419514)
> en `success` (6/6 jobs).
> Diferidos a V3.38/V3.39: P1-03 (automaticidad segmentada por skill),
> `cloze_coverage` del corpus y el refactor de `wordDrill.tsx`.
>
> **Nota (2026-09-10):** **V3.37.0 publicada** — release **v3.37.0**
> (**Learning Evidence 3.0: cues graduados y automaticidad**). La escalera del
> peldaño `2 · Recall` deja de ser un *fallback* (traducción y, si no,
> definición) y pasa a ser una **PROGRESIÓN** `translation (cued) < definition
> (cued) < cloze (guided)`. `services/recall.py` añade `RECALL_CUES`,
> `RECALL_CUE_SUPPORT` (el mapeo peldaño → apoyo vive en la capa pura: dominio,
> repositorio y tests no pueden divergir), `blank_out` (blanqueo puro del cloze
> desde el banco de pronunciación, con la misma alineación que acredita la
> producción del drill; descarta el cue si tras blanquear queda cualquier
> aparición de la palabra o si no hay frase real — **nunca se inventa
> contenido**), `next_recall_rung` (peldaño recomendado por ÉXITOS ya
> registrados por peldaño, leídos de `recall_rungs`; techo en `cloze`) y
> `resolve_recall_cue` (ideal sin contenido → baja hacia más apoyo, **nunca
> hacia arriba**). Cada peldaño declara su `support_level` y su `activity_id`
> (`drill:recall:translation|definition|cloze`), así que `independent_successes`
> (V3.36) por fin tiene de dónde salir. `services/evidence.py` añade
> `AUTOMATIC_MIN_INDEPENDENT = 2`, `is_automatic` (éxito independiente **y**
> espaciado: ≥2 días naturales distintos; `cued`/`guided` no cuentan — D5/E3),
> `RECALL_RUNG_EVIDENCE` + `recall_rung_activity`/`recall_rung_from_activity` y
> los agregados `independent_success_days`/`recall_rungs` con **paridad
> pura↔SQL** en `summarize_by_target`. `recommend_review_activity` incorpora el
> ítem `automatic` sin hueco de producción → `recall` de mantenimiento
> (`automatic_maintenance`) y `review_queue_item` expone `recommended_cue` y
> `automatic` (aditivos) resolviendo el ideal contra la disponibilidad real, sin
> spoilear la palabra (P1-03 de V3.35.1 intacto). Contrato HTTP aditivo:
> `cue` opcional en GET/POST (422 **sin evento** si no está soportado o el
> peldaño no tiene contenido; el servidor **re-deriva** el peldaño, premisa 21),
> `support_level` en `RecallPromptOut` y `independent_success_days`/
> `recall_rungs` en `LexicalEvidence`. **Sin migración de BD**
> (`support_level`/`activity_id` ya existían) y **sin tocar** scoring, FSRS,
> `error_type` (observacional) ni la semántica del intervalo de evidencia.
> Frontend: el peldaño Recall pinta el cloze (monoespaciado) y envía su
> `cue_kind`. Tests: pytest **1813 passed** (+22) + ruff limpio + vitest (65
> ficheros/**560**, +1) + `tsc --noEmit` limpio + build OK +
> `check_release_consistency` **3.37.0** exit 0.
> **CI verificable:** commit `bdc77cd5e467cea4b027178e6235da8e57b36f9e` con el
> run [34476875230](https://github.com/jvelasca/english-tutor/actions/runs/34476875230)
> en `success` (6/6 jobs).
> Pendientes hacia **V3.38**: `situación` (exige extender el contrato de
> contenido de la caché, `generator_version`) y el planner (Optimal Next Task),
> más los diferidos de V3.30 y la transferencia por contexto V3.23.
>
> **Nota (2026-09-10):** **V3.36.0 publicada** — release **v3.36.0**
> (**Learning Evidence 2.0**: el ledger longitudinal aprende el CÓMO de cada
> evento). Migración **aditiva e idempotente** de `learning_evidence` con seis
> columnas — `support_level` (eje `copied → guided → cued → independent →
> spontaneous`, espejo de `academy_evidence` con test de paridad),
> `difficulty` (CEFR 1-6, escala compartida con listening; `0.0` = no
> declarada), `context_id`/`activity_id`, `response_time_ms` (`NULL` = no
> medida) y `error_type` (`''` = no clasificado) — más índice
> `(user_id, target_type, context_id, activity_id)`. `services/evidence.py`
> añade `EVIDENCE_SUPPORT_LEVELS`, `INDEPENDENT_SUPPORT_LEVELS`,
> `RECALL_ERROR_TYPES` y el clasificador puro `classify_recall_error`
> (errata = misma inicial + longitud ≥ 4 + Levenshtein acotado; parcial =
> prefijo o comienzo de unidad multi-palabra; conservador en palabras cortas:
> `cat`/`cut` es otra palabra). **Decisión de alcance: `error_type` es
> OBSERVACIONAL** — no toca scoring, ni evidencia, ni FSRS; una errata sigue
> siendo `correct=false`, pero el tutor ya distingue "no lo sabe" de "lo sabe y
> lo escribió mal". Captura end-to-end: recall → `cued`/`drill:recall`;
> retrieval → `guided`/`drill:word`|`drill:sentence` (duración del cliente
> convertida a ms); producción → apoyo real del canal (`chat` → `spontaneous`,
> conversación guiada → `guided`, `speaking`/`writing` → `independent`) y
> contexto `lexicon:<canal>`. `summarize_evidence`/`summarize_by_target` ganan
> `success_rate`, `independent_successes`, `support_levels`, `error_types` y
> `mean_response_time_ms` con paridad pura↔SQL fijada por test. Contrato HTTP
> aditivo: `RecallAttemptIn.response_time_ms` (opcional, `ge=0`, 422 si es
> negativa), `RecallAttemptOut.error_type` y `LexicalEvidence` ampliado.
> Frontend: el peldaño Recall mide la latencia cue → envío. Tests: pytest
> **1791 passed** (+22) + ruff limpio + vitest (65 ficheros/**559**, +1) +
> `tsc --noEmit` limpio + `check_release_consistency` **3.36.0** exit 0.
> **CI verificable:** commit `d91a637a74678e080478656ed02d7c1e6cd4ba07` con el
> run [34473218199](https://github.com/jvelasca/english-tutor/actions/runs/34473218199)
> en `success` (6/6 jobs).
> Pendientes hacia **V3.37**: cues graduados (translation → definition → cloze →
> situación → free recall), gradiente de apoyo como señal de automaticidad y el
> planner (grafo evidencia → conocimiento → retención → transferencia →
> Optimal Next Task), más los diferidos de V3.30 y la transferencia por contexto
> V3.23 (que ya tiene `context_id`/`activity_id` en el ledger léxico).
>
> **Nota (2026-09-10):** **V3.35.1 publicada** — release **v3.35.1** (cierre de
> la auditoría de V3.35.0). Patch quirúrgico de integridad del modelo de
> evidencia longitudinal, sin cambios de esquema ni de arquitectura.
> **P1-01 (intervalo de evidencia):** `interval_since_last_evidence` deja de
> recibir el `interval_days` de `delayed_retrieval_decision` (hueco desde el
> ANCLA de retención FSRS) y lo deriva SIEMPRE `record_evidence` de la evidencia
> anterior del ledger (`learning_evidence → learning_evidence`); el intervalo de
> retención se queda en la decisión (`credited` + reprogramación de carta) y no
> se persiste como intervalo de evidencia. **P1-02 (cronología):** se retira
> `intervals.sort()` de `summarize_evidence` y `summarize_by_target` ordena por
> `occurred_at, id` — la secuencia real del scheduler ya no se reordena por
> valor. **P1-03 (pedagógico):** «Repaso de hoy» solo muestra la palabra en
> `recognition`; en `recall`/`sentence` la oculta (el `WordDrill` ya la ocultaba
> en Recall). **P2-02:** `record_evidence_bulk` deduplica eventos idénticos
> (`target_type`+`target_id`+`task`+`activity`+`occurred_at`) y encadena en
> memoria los eventos distintos del mismo target del lote. Tests: pytest
> **1769 passed** (+5) + ruff limpio + vitest (65 ficheros/**558**, +1) +
> `tsc --noEmit` limpio + `check_release_consistency` **3.35.1** exit 0.
> **CI verificable:** commit `df78307432dddf9fe535860b2e3028258454faff` con el
> run [34470067665](https://github.com/jvelasca/english-tutor/actions/runs/34470067665)
> en `success` (6/6 jobs).
> Pendientes hacia **V3.36 (Learning Evidence 2.0)**: `support_level`,
> `difficulty`, `response_time_ms`, `error_type`, `context_id`/`activity_id`,
> cues graduados y estadísticas derivadas del ledger.
>
> **Nota (2026-09-10):** **V3.35.0 publicada** — release **v3.35.0**
> (**Longitudinal Learning Evidence 1.0**: cierra los dos P1 de la auditoría de
> V3.34.0 y convierte el Evidence Graph en historia longitudinal real, sin
> rehacer arquitectura ni migración destructiva). **P1-1 (ancla encadenada):** la
> recuperación demorada deja de medirse desde la primera exposición. Nueva
> función pura `services/lexicon.py::delayed_retrieval_decision(row, now,
> due_at)` → `{anchor_at, interval_days, required_days, credited}`: el ancla es
> la ÚLTIMA recuperación válida (`max(last_retrieval_at, last_recall_at)`; solo
> la primera recuperación retrocede a `min(first_seen, first_exposed_at)`) y el
> intervalo exigido lo calcula FSRS (`due_at` de la carta `lexicon`) o, sin
> carta, el suelo `RETENTION_MIN_INTERVAL_DAYS`. El dominio carga la carta y el
> repositorio solo persiste (`record_retrievals(..., due_at=…)` encadena
> `last_retrieval_at`). Efecto: `D0 → D+3` acredita; `D+3 → D+4` ya no si FSRS no
> ha vencido. **P1-2 (cola propia):** el repaso espaciado sale del speaking
> micro-drill — nuevo `GET /api/learning/review` (`routers/learning.py`) con las
> cartas FSRS `lexicon` vencidas ordenadas por urgencia (`fsrs.due_queue`) y la
> actividad óptima por hueco (`services/lexicon.py::recommend_review_activity`:
> sin base receptiva → `recognition`, sin `cued_recall` → `recall`,
> `production_gap` → `sentence`, resto → `recall`); se retira `due_words` de
> `lexicon.drill_candidates` y la lectura de cartas FSRS de
> `get_drill_candidates`, así que el speaking drill vuelve a ser solo huecos de
> producción oral. **Evidencia:** tabla append-only `learning_evidence` (+
> `event_role` en `learning_events`, default `''` legacy) con repositorio
> `repositories/evidence.py` y servicio puro `services/evidence.py`
> (`EVIDENCE_ROLES`, `classify_event_role`, `summarize_evidence` = attempts /
> successes / distinct_success_days / intervals); contador aditivo
> `recall_attempts` (intento ≠ éxito) y bloque `evidence` (`LexicalEvidence`)
> expuesto en el léxico y en la cola de repaso; escrituras de evidencia en el
> intento de recall (acierto y FALLO), la recuperación del micro-drill y la
> producción. **UI:** nueva sección «Repaso de hoy»
> (`features/vocabulary/ReviewQueueSection.tsx`) montada en el diccionario
> personal, `api/learning.ts::getReviewQueue`, `initialStep` en `WordDrill` (abre
> el peldaño recomendado) e i18n es/en. Tests: pytest backend **1764 passed**
> (+21: `test_longitudinal_evidence_v335.py` + `test_review_queue_v335.py`, con
> `test_lexicon.py`/`test_vocabulary.py`/`test_recall_v334.py` actualizados al
> ancla encadenada) + ruff limpio + vitest (65 ficheros/**557**, +2
> ficheros/+8 tests: API de la cola — restaura los 3 casos preexistentes de
> `getProfile`/`analyzeText`/`getEvents` —, `WordDrill` con `initialStep` y
> `ReviewQueueSection`) + `tsc --noEmit` limpio + `check_release_consistency`
> **3.35.0** exit 0. **CI verificable:** commit
> `b304c257da1cffb408e127c80af1b43e12aa9955` con el run
> [34467763326](https://github.com/jvelasca/english-tutor/actions/runs/34467763326)
> en `success` (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build,
> release consistency, Beta V3.0 gate, content validation, Playwright E2E).
> Detalle: `release-notes-v3.35.0.md` y `CHANGELOG.md` `[3.35.0]`. Pendientes
> hacia **V3.36**: los P2 de la auditoría de V3.34.0
> (`response_time_ms`, clasificación de errores ortográficos, cues graduados,
> `support_level`, `difficulty` en evidencia, refactor completo de
> `wordDrill.tsx`), los diferidos de V3.30 (consumo de `word_breakdown_json`,
> palabras tocables) y la transferencia por contexto de actividad V3.23.
>
> **Nota (2026-09-10):** **V3.34.0 publicada** — release **v3.34.0**
> (Dictionary → Learning Bridge, eslabón 3: **Recall 2.0 por texto**). El
> peldaño intermedio del drill deja de ser una repetición oral de la palabra y
> pasa a ser recuperación REAL por texto: el alumno ve el SIGNIFICADO (cue =
> traducción o definición sin spoiler, `services/recall.py`) y **teclea la
> palabra**. La escalera queda **`1 · Recognize` · `2 · Recall` · `3 · Sentence`**
> (se retira el paso oral de palabra suelta; el micrófono vive solo en
> Sentence). A diferencia de Recognition (informativo), el acierto de Recall SÍ
> deja señal léxica PROPIA — `recall_successes`/`recall_days` + ledger
> `recalled`, migración idempotente y sin backfill en `vocabulary` —, acredita
> la recuperación demorada existente si supera el intervalo (`retrieval_*`) y
> **reprograma la carta FSRS `lexicon` con intervalos reales** (Good immediate,
> Easy si demorado, Again si falla) sin crear deuda por fallar una palabra no
> rastreada. NUNCA acredita producción (`production_count`/`<channel>_prod`
> intactos) ni saca la palabra de candidatas: `onProduced` solo lo dispara
> Sentence (D5/E3: el recall vive en la capa léxica, no en `academy_evidence`).
> Contrato aditivo: `GET /api/vocabulary/drill/recall` (`available=false` sin
> cue) y `POST /api/vocabulary/drill/recall-attempt` (409 sin pregunta, 422
> inválido); el GET nunca expone `expected` (premisa 21). `LexicalCompetence`
> gana `cued_recall`/`recall_successes`/`recall_days`, `LexiconSummary` gana
> `recalled` y `get_drill_candidates` antepone las palabras con carta FSRS
> vencida. Tests: pytest backend **1743 passed** (+20: `test_recall_v334.py`
> con cue/scoring/señal propia/demorada/FSRS/aislamiento + casos de
> `cued_recall`/`recalled`/priorización en `test_lexicon.py`) + ruff limpio +
> vitest (63 ficheros/**549**, +2: peldaño Recall por texto y mocks al degrade
> Recognize → Recall → Sentence) + `tsc --noEmit` limpio + `check_release_consistency`
> **3.34.0** exit 0. **CI verificable:** commit
> `f9880f15fd7e19f17587c3cd25fa9362604af1d4` con el run 34451370871 en
> `success` (6/6 jobs). Detalle: `release-notes-v3.34.0.md` y
> `agentes/v334-recall-2.0.md`. Pendientes hacia **V3.35**: los diferidos de
> V3.30 (consumo de `word_breakdown_json`, palabras tocables), transferencia por
> contexto de actividad V3.23 y Lexical Evidence Engine / Evidence Graph como
> fuente longitudinal.
>
> **Nota (2026-09-10):** **V3.33.1 publicada** — release **v3.33.1**
> (hardening de Recognition tras la auditoría externa de V3.33.0). Dos
> correcciones P1, sin tocar la evidencia informativa ni la seguridad del
> scoring (el GET sigue sin exponer la correcta):
> **P1-01 (posición fija de la correcta):** `recognition_options_for(word,
> entries, seed="")` deriva ahora la permutación de `palabra + seed`; el
> `GET /api/vocabulary/drill/recognition` entrega un nonce por intento
> (`question_id: ""`) y el `POST .../recognition-attempt` lo reenvía para
> reconstruir la MISMA permutación (premisa 21: sin estado servidor). Reintentar
> la misma palabra rebaraja las opciones, así que no se puede memorizar la
> posición. Sin firmar: el seed solo ordena y la correcta nunca viaja.
> **P2:** `_stable_int` pasa a `SHA-256` (mejor dispersión);
> `listening_bottom_up` conserva su hash (sus ids son content-stable y no deben
> re-barajarse).
> **P1-02 (arranque real en Recognize):** `WordDrill` abre en
> `step="recognition"` y carga la pregunta sola; si `available=false` degrada a
> Recall (`Practicar → Recognize → Recall → Sentence`, o `Practicar → Recall`),
> sin pisar una elección manual de otro paso. Cada entrada en Recognize pide un
> `question_id` nuevo.
> Contrato aditivo y retrocompatible: `RecognitionQuestionOut.question_id` y
> `RecognitionAttemptIn.question_id` (opcional). Tests: pytest backend
> **1723 passed** (+1: test puro de permutación por seed; determinismo y
> aislamiento reescritos sobre `question_id`) + ruff limpio + vitest (63
> ficheros/**547**, +1: reentrar en Recognize pide pregunta nueva / arranque y
> degradación) + `tsc --noEmit` limpios + `check_release_consistency` **3.33.1**
> exit 0. **CI verificable:** commit
> `dcaa74cacf4912c3f747a104e491d6a0723c5ca7` con el run 34447562780 en
> `success` (6/6 jobs). Aclaración para la auditoría: el informe anterior marcó
> la CI de V3.33.0 como «no verificable», pero **sí** tenía CI verde (run
> 34383922526, sha `5207729`, 6/6 jobs); la confusión viene de consultar
> *commit statuses* (`/status`, que queda en `pending`) en lugar de los
> *check runs* que publica `.github/workflows/ci.yml`.
> Detalle: `release-notes-v3.33.1.md`; `CHANGELOG.md` con entrada
> `[3.33.1]`; `PLAN.md` con hito estable V3.33.1. Pendientes hacia **V3.34**:
> recall demorado con FSRS, transferencia por contexto de actividad V3.23 y los
> diferidos de V3.30.
>
> **Nota (2026-09-09):** **V3.33.0 publicada** — release **v3.33.0**
> (Dictionary → Learning Bridge, eslabón 2: peldaño **Recognition — MCQ
> definición ↔ palabra** en la escalera compartida de drill). La escalera
> `wordDrill.tsx` (lookup Y hub) pasa a **`1 · Recognize` · `2 · Word` ·
> `3 · Sentence`**: el primer peldaño muestra la palabra y pide su significado
> entre opciones. La pregunta es **pura y determinista por palabra** (premisa
> 21, sin estado servidor): `backend/services/dictionary_mcq.py` la construye
> desde la caché global `dictionary_entries` (`list_entries()` nuevo en
> `repositories/dictionary.py`) — correcta = `translation` de la diana con
> distractores de otras entradas (mismo `pos` preferido, dedupe, banco de
> reserva `definition` cuando el pool de traducciones no alcanza) y barajado
> estable (`_stable_int`/`_place_options`) ocultando la correcta — y el
> servidor la RECOMPUTA al puntuar: `GET /api/vocabulary/drill/recognition`
> nunca expone la correcta y `POST /api/vocabulary/drill/recognition-attempt`
> devuelve `{correct, correct_index, selected_index}`. Sin distractores o sin
> entrada → `available=false` / 409 (degradación con aviso). **Evidencia SOLO
> informativa** (V3.13: el MC de reconocimiento no demuestra destrezas
> productivas; evita el «mastery de clic»): un `learning_events`
> `drill:<word>:recognition:ok|ko`; cero escrituras en `vocabulary`/
> `vocabulary_events`, FSRS, mastery, `usage` ni candidatas (el acierto NO
> dispara `onProduced`/`refreshEntry`; D3 intacto). Sin etiquetas de origen,
> sin cambios de esquema de BD. Tests: pytest backend **1722 passed** (+11 del
> nuevo `backend/tests/test_dictionary_recognition_v333.py`: determinismo y GET
> sin la correcta · acierto/fallo solo informativos con cero efectos ·
> modo definition y dedupe · eventos recognition que no alteran
> `drill_ok_days`/candidatas · aislamiento A/B · sin entrada/sin distractores →
> 409/`available=false` · normalización) + ruff limpio + vitest (63
> ficheros/546) + `tsc --noEmit` limpios + `check_release_consistency`
> **3.33.0** exit 0. Detalle y conteos: `release-notes-v3.33.0.md`;
> `CHANGELOG.md` con entrada `[3.33.0]`; `PLAN.md` con hito estable V3.33.0.
> Pendientes hacia **V3.34**: los diferidos de V3.30 — consumo de
> `word_breakdown_json` en agregados/práctica dirigida de las falladas y
> palabras tocables en transcripts/chat — y los eslabones restantes del puente
> (recall demorado FSRS, transferencia por contexto de actividad V3.23;
> borrador `agentes/v332-dictionary-learning-bridge.md`).
>
> **Nota (2026-09-09):** **V3.32.0 publicada** — release **v3.32.0**
> (Dictionary → Learning Bridge, primer eslabón: la consulta del diccionario
> V3.30 se convierte en puerta a la práctica real sin romper D3). El botón
> **«Practicar esta palabra»** en la tarjeta del lookup
> (`DictionaryLookup.tsx`) monta in-line la escalera de drill existente
> **Recall → Sentence** (`wordDrill.tsx`, extraída SIN cambio funcional de
> `PersonalDictionary.tsx`) para la palabra consultada — también si
> `usage.tracked=false`: el éxito crea producción pura igual que fuera del
> diccionario — y refresca en silencio las marcas de uso de la entrada al
> producir. Cero backend nuevo (los endpoints de drill ya aceptan palabras
> arbitrarias) y **evidencia idéntica, sin etiquetas de origen**:
> `record_production_text(speaking, as_unit=True, activity="drill")` +
> `learning_events` `drill:<word>:ok` (:sentence: en el paso frase); el lookup
> sigue sin escribir (D3 intacto, cerrado por acceptance). Tests: pytest
> backend **1711 passed** (+3 del nuevo `test_dictionary_bridge_v332.py`:
> lookup read-only + práctica con evidencia idéntica entre usuarios A/B ·
> paso frase equivalente con cierre D3 · aislamiento entre usuarios) + ruff
> limpio + vitest (63 ficheros/542) + `tsc --noEmit` limpios +
> `check_release_consistency` **3.32.0** exit 0. Detalle y conteos:
> `release-notes-v3.32.0.md`; `CHANGELOG.md` con entrada `[3.32.0]`; `PLAN.md`
> con hito estable V3.32.0. Pendientes hacia **V3.33**: los diferidos de V3.30
> — consumo de `word_breakdown_json` en agregados/práctica dirigida de las
> falladas y palabras tocables en transcripts/chat — y los siguientes
> eslabones del puente (reconocimiento MCQ, recall demorado FSRS,
> transferencia por contexto; borrador `agentes/v332-dictionary-learning-bridge.md`).
>
> **Nota (2026-09-09):** **V3.31.1 publicada** — release **v3.31.1**
> (hardening del diccionario de consulta tras la auditoría profunda de
> V3.31.0; solo backend + docs, sin cambios de UI ni de esquema de BD). Cierra:
> **P1-01 residual — `pick_model` exige modelo explícito INSTALADO**
> (`services/translate.py`: antes bastaba con que no estuviera en
> `UNUSABLE_MODELS` para llegar a Ollama aunque no estuviera instalado; ahora
> consulta `installed_models()` — caché de 300 s — y solo devuelve el explícito
> si está instalado y es utilizable, si no cae al fallback automático) ·
> **negative cache del generador** (`domain/vocabulary.py`: un fallo de
> generación — Ollama caído, respuesta inválida o timeout — marca la palabra
> en memoria durante `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS` = 30 s; las
> consultas siguientes degradan a `definition_source="none"` sin reintentar en
> bucle; la marca expira de forma perezosa o se limpia al conseguir una
> generación) · **rate limit de generación nueva** por usuario (10/min) y
> global (40/min) en `config.py`, aplicado solo al dueño de un vuelo (lo
> cacheado no consume cupo; sin cupo → 200 con `definition_source="none"`,
> nunca 5xx) · **tope servidor del dueño del vuelo**
> (`DICTIONARY_GENERATION_TIMEOUT_SECONDS` = 90 s con `asyncio.wait_for`: un
> Ollama colgado ya no deja el vuelo de la palabra clavado — los waiters tenían
> su tope de 60 s; el dueño ahora también) · **semántica documentada del
> contenido canónico** (la caché `dictionary_entries` es global y sin
> `model_id`; `model` solo influye en la generación de contenido nuevo).
> Tests: pytest backend **1708 passed** (+11: +3 en `test_translate.py` para
> explícito utilizable no instalado → fallback y +8 en el nuevo
> `backend/tests/test_dictionary_hardening_v3311.py`: negative cache suprime el
> reintento inmediato y expira, el éxito limpia la marca, cupo por usuario
> bloquea palabras nuevas pero no las cacheadas, cupo global compartido entre
> usuarios, sin cupo nunca lanza, timeout del dueño degrada y libera el vuelo,
> D3 intacto) + ruff limpio + vitest + `tsc --noEmit` limpios +
> `check_release_consistency` **3.31.1** exit 0. Detalle y conteos:
> `release-notes-v3.31.1.md`; `CHANGELOG.md` con entrada `[3.31.1]`; `PLAN.md`
> con hito estable V3.31.1. Pendientes hacia **V3.32**: Dictionary → Learning
> Bridge (borrador movido a `agentes/v332-dictionary-learning-bridge.md`),
> consumo de `word_breakdown_json` en agregados/práctica dirigida de las
> falladas y palabras tocables en transcripts/chat.
>
> **Nota (2026-09-09):** **V3.31 publicada** — release **v3.31.0** (cierre de
> los hallazgos residuales de la auditoría profunda de V3.30.1 sobre el
> diccionario de consulta; backend + frontend de contrato, sin cambios de UI).
> Cierra: **single-flight robusto a cancelación** (`domain/vocabulary.py`: el
> `CancelledError` del dueño del vuelo resuelve el Future con None antes de
> propagar — los waiters ya no se cuelgan — y tope defensivo de espera de 60 s
> en los waiters) · **invalidación del contenido de caché previo a V3.31**
> (`GENERATOR_VERSION` `1.0.0 → 1.1.0` en `services/dictionary_content.py`;
> `DICTIONARY_LEGACY_VERSION = "1.0.0"` en `repositories/db.py`, marca
> deliberadamente distinta de la actual que la migración aplica a las filas sin
> versión: el contenido del parser greedy de V3.30 regenera una vez) · **tests**
> de la migración de upgrade desde una BD V3.30.0 (aditiva + backfill +
> conservación + idempotencia) y del path real del diccionario con modelo
> explícito no utilizable (`qwen3.5:9b` nunca llega a Ollama) · **contrato
> frontend**: tipo `DictionaryLookupRequest`, body tipado, test del
> `POST /api/vocabulary/dictionary` (método/query/header/body) y timeout de
> cliente de 120 s. Verificación: pytest backend **1697 passed** (+4) + ruff
> limpio + vitest + `tsc --noEmit` limpios + `check_release_consistency`
> **3.31.0** exit 0. Detalle y conteos: `release-notes-v3.31.0.md`;
> `CHANGELOG.md` con entrada `[3.31.0]`; `PLAN.md` con hito estable V3.31.
> Pendientes hacia **V3.32**: Dictionary → Learning Bridge (borrador movido a
> `agentes/v332-dictionary-learning-bridge.md`), consumo de `word_breakdown_json`
> en agregados/práctica dirigida de las falladas y palabras tocables en
> transcripts/chat.
>
> **Nota (2026-09-09):** **V3.30.1 publicada** — release **v3.30.1** (patch de
> endurecimiento de la auditoría V3.30.0, sobre el commit `a3857f2` de v3.30.0;
> solo backend + docs, sin cambios de UI). Cierra los tres P1 del dictamen:
> **P1-01** single-flight de generación en `domain/vocabulary.py`
> (`_inflight_content`: N consultas simultáneas de la misma palabra → UNA
> llamada LLM y UNA fila; el `INSERT OR IGNORE` protegía la fila pero no la
> generación; los waiters reciben el mismo resultado y un fallo no reintenta en
> cascada) · **P1-02** la política `UNUSABLE_MODELS` ya no se puede saltar con
> un modelo explícito (`services/translate.py` `pick_model`: el explícito no
> utilizable, p. ej. `qwen3.5:9b`, cae al fallback automático — único punto de
> política para diccionario y traducción) · **P1-03** caché versionada:
> `dictionary_entries.generator_version` (columna aditiva + migración
> idempotente con backfill `'1.0.0'` del contenido V3.30 en `repositories/db.py`;
> `save_entry` upsert `ON CONFLICT DO UPDATE` sustituye a `insert_entry` y da
> semántica real a `updated_at`; `GENERATOR_VERSION = "1.0.0"` en
> `services/dictionary_content.py`; el dominio solo sirve caché cuya
> `generator_version` coincide y regenera/sobrescribe la obsoleta). P2: parser
> JSON robusto (`parse_content` toma el PRIMER objeto válido con `raw_decode`;
> la regex greedy `{.*}` se tragaba `{…} texto {…}`). Verificación: pytest
> backend **1693 passed** (+9 tests: concurrencia misma palabra y dos usuarios,
> fallo concurrente sin reintentos, regeneración por versión obsoleta, reuso de
> versión fresca, parser multi-objeto/llaves en prosa, `pick_model` con
> explícito no utilizable) + ruff limpio + `check_release_consistency` **3.30.1**
> exit 0. Detalle y conteos: `release-notes-v3.30.1.md`; `CHANGELOG.md` con
> entrada `[3.30.1]`; `PLAN.md` con hito estable V3.30.1. Pendientes hacia
> **V3.31**: Dictionary → Learning Bridge (Consultar → Practicar → Transferir →
> Retener sin contaminar evidencia), consumo de `word_breakdown_json` en
> agregados/práctica dirigida de las falladas y palabras tocables en
> transcripts/chat.
>
> **Nota (2026-09-09):** **V3.30 publicada** — release **v3.30.0** = commit
> **`a3857f2`** en `main` con **CI verde 6/6 jobs** (diccionario
> de consulta con marca de uso y aprendizaje; feature cerrada con las Fases
> A/B/C del dossier `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`). Resumen:
> endpoint `POST /api/vocabulary/dictionary` con `usage` por forma y por
> `lexical_unit` (estado, recall, contadores, matriz de competencia; solo
> lectura D3, sin eventos ni impacto en mastery), ejemplo determinista del
> banco (`services/example_sentences.py`) y definición/traducción generadas por
> el modelo local (`services/dictionary_content.py`, `temperature=0`, prompt
> JSON, parseo tolerante) cacheadas con `INSERT OR IGNORE` en la tabla global
> `dictionary_entries` (1.ª consulta paga el modelo; siguientes deterministas;
> degradación a `definition_source="none"` con fallback en memoria si la BD
> falla) · UI «Consultar» (`DictionaryLookup.tsx`, conmutador con el diccionario
> personal en `QuizRoutePage`, solo Vocabulario la declara), cliente
> `lookupDictionaryWord` + tipo `DictionaryEntry`, claves `dictionary.lookup.*`
> es/en. Verificación: pytest backend **1684 passed** (39 tests del diccionario)
> + ruff limpio; vitest **538 passed** (63 archivos) + `tsc --noEmit` limpio;
> `check_release_consistency` **3.30.0** exit 0. Detalle y conteos:
> `release-notes-v3.30.0.md`; `CHANGELOG.md` con entrada `[3.30.0]`; `PLAN.md`
> con hito estable V3.30 y candidato cerrado. Pendientes hacia **V3.31**:
> consumo de `word_breakdown_json` en agregados/práctica dirigida de las
> falladas, palabras tocables en transcripts/chat, afinado de la Fase 3
> (lección orquestada multi-ítem, evaluación acústica real) y el dossier de
> auditoría del candidato v3.28.0 (letra P).
>
> **Nota (2026-09-09, 14:00):** **V3.29 publicada** — release **v3.29.0**
> (Listening Engine 4.0, **Fase 3, núcleo**). Plan
> `v3.29_nucleo_fase_3…plan.md` (P1–P6); especificación
> `docs/LISTENING_ENGINE_4.0.md` a v1.2 con el núcleo de la Fase 3 marcada
> **implementada** (§14/§15). Resumen: **P1** motor `word_alignment_proxy`
> offline — `stt.transcribe_words` (`word_timestamps=True`) + módulo puro con
> sidecar `{wav}.words.json` (`sync: asr_word_proxy`, `coverage`, escritura
> atómica), `align_words` con interpolación monótona y `MIN_COVERAGE ≈ 0.8`
> (degradación controlada al sync de frase); hooks en
> `generate_listening_audio.py`, `get_audio` e `import_audio.py` + backfill
> `generate_word_alignments.py` · **P2** `word_timings` en el payload
> (`word_timings_for`, asignación palabra→frase **por tiempo**, `twice`/derivados
> `d-`, escalado slow/fast por `speech_rate` en cliente) · **P3** evidencia
> `word_breakdown_json` (columna aditiva nullable idempotente; dictado fallido +
> target de cloze/segmentation incorrecto; sin consumo en agregados → V3.30) ·
> **P4** karaoke `KaraokeTranscript` (revelado por frase + palabra activa +
> toque→seek) · **P5** controles precisos (`onDuration` en `loadedmetadata`,
> bucle con scheduler rAF inyectable, seek slider + bucle A/B) · **P6** salto a
> la palabra fallada (`failedWordTiming`, botones normal/slow en dictado/cloze).
> Verificación íntegra local: pytest + ruff, vitest + `tsc --noEmit`,
> `check_release_consistency` **3.29.0** exit 0 (conteos finales en
> `release-notes-v3.29.0.md`). Pendiente para V3.30: diccionario de consulta
> (candidato), consumo de `word_breakdown_json` en agregados/práctica dirigida,
> afinado de la Fase 3 (lección orquestada multi-ítem, evaluación acústica real)
> y el dossier de auditoría del candidato v3.28.0 (letra P).
>
> **Nota (2026-09-09, 12:35):** **V3.28.1 publicada** — patch de la auditoría
> V3.28.0 (release **v3.28.1**, P1 auditados): 1) `partial_dictation` derivado
> **servible** — `derived_catalog` expone `DERIVED_PRODUCTION_POOL` y
> `pick_next_question` lo sirve en sesiones bottom-up (Caso A) con señal de
> `dictation` débil, tras agotar cloze/segmentación del nivel · 2) **scoring
> exacto por token del dictado escrito** (`dictation_score`, sin Soundex/
> phoneme/prosodia; `submit_production` lo aplica a todo `task_type=dictation`;
> fila fonética oculta en la UI) · 3) **Gonnago/reducciones por token y
> frontera** (`contains_word_token` compartido en
> `_reductions_in`/`_is_eligible_token`/`_connected_speech_realized`, contenido
> de `l16` corregido → digest de audio regenerado) · 4) **AudioController
> integrado** (play/pausa/variantes operativas; seek/setRate fino/loop/replay/
> markSegment sin UI → V3.29 Fase 3) y `seek()` notifica `onCurrentTime` en
> pausa (P2-01). Tests negativos añadidos (pools, selector, dictado exacto,
> frontera de reducción, seek). P2 restantes y Fase 3 → V3.29.
>
> **Nota (2026-09-09, 10:30):** **V3.28 publicada** — release **v3.28.0** =
> commit **`74fb1b3`** en `main` con **CI verde 6/6 jobs** (Listening Engine 4.0,
> **Fase 2**, Bloques A–F). Plan
> `v3.28_listening_engine_fase_2_f74493a3.plan.md`; especificación
> `docs/LISTENING_ENGINE_4.0.md` con la Fase 2 marcada **cerrada**. Resumen:
> **Bloque A** micro-flujo unificado — `next_question` sirve `flow`/
> `transcript_policy` también en `level=X` y `mode=failed` (helper
> `_public_with_flow`); `mastered` conserva el modo compacto sin flow (P1-01) ·
> **Bloque B** AudioController 4.0 (`audioController.ts` + `useAudioController`
> con play/seek/setRate+preservesPitch/loopSegment/replayCurrent, variante de
> URL más cercana al rate) integrado en `ListeningPractice.tsx` · **Bloque C**
> bottom-up derivado del corpus (`services/listening_bottom_up.py`: cloze
> auditivo, dictado parcial y segmentación; `derived=True`, filtrados siempre de
> `route_questions`/`level_items` → nunca certifican) · **Bloque D** timings
> gruesos de frase (`coarse_sentence_timings`, etiqueta `coarse_heuristic`, no
> alineación acústica) + `CoarseTranscript` en frontend (hidden/partial/full +
> frase activa por `currentTime`) · **Bloque E** Shadowing 2.0 — playback de la
> grabación (`RecordingPlayButton`) + señales auxiliares no bloqueantes
> (`shadowing_duration_ms`, `shadowing_speech_rate`, migración aditiva
> idempotente, sin peso de mastery/gate) · **Bloque F** E2E adaptativos y
> negativos (`test_listening_e2e_v328.py`: E2E-01..04 + contrato pedagógico;
> ampliación de `microFlow.test.ts` con tareas derivadas en el flujo).
> Verificación íntegra local: pytest **1683 passed** + `ruff check .` limpio;
> vitest **505 passed** (61 archivos) + `tsc --noEmit` OK;
> `check_release_consistency` **3.28.0** exit 0. Pendiente: dossier de
> auditoría del candidato v3.28.0 (letra P, sesión posterior); Fase 3 del
> engine (karaoke palabra a palabra / `word_alignment_proxy`) para V3.29.
> **Candidato V3.29 anotado** (sin diseño): diccionario de consulta con marcas
> de uso/aprendizaje (ver PLAN.md → «Siguiente incremento»).
>
> **Nota (2026-09-09, 09:45):** **V3.27 publicada** — release **v3.27.0**
> (Listening Engine 4.0, Fase 1) en `main`. **Backend = fuente única de la
> política pedagógica**: nuevo módulo puro `services/listening_flow.py` sirve
> `flow` (pre/while1/while2/post/shadowing) y `transcript_policy`
> (`revelation`/`max_attempts_per_stage`/`allow_manual_reveal`/
> `shadowing_optional`) en cada pregunta; el frontend ejecuta una máquina de
> presentación (`features/listening/microFlow.ts`) sin reglas propias.
> **Perfil auditivo visible en UI** (`services/auditory_profile.py` casos A-D +
> `AuditoryProfileCard`, no bloqueante, estados sin datos → needsMore →
> intervención; la capa recomendada prioriza el siguiente ítem vía
> `pick_next_question(layer=...)`). **Evidencia ampliada**: migración
> idempotente con 5 columnas en `listening_attempts` (`layer`, `speed_used`,
> `stage`, `transcript_used`, `segments_replayed`) persistidas en
> `submit_answer`/`submit_production` con metadatos opcionales de la API.
> Plan `docs/PLAN-V327-LISTENING-ENGINE-4.md`; release notes
> `release-notes-v3.27.0.md`; CHANGELOG/PLAN/README actualizados; backend
> pytest **1647 passed** + ruff limpio; frontend vitest **472 passed** (59
> archivos) + `tsc --noEmit` OK; `check_release_consistency` **3.27.0** exit 0.
> Pendiente: auditoría externa del candidato v3.27.0; Fase 2 del engine
> (reproductor rico, karaoke/segmentos) y calibración de umbrales del perfil.
> **Candidato V3.28 anotado** (sin diseño): diccionario de consulta con marcas
> de uso/aprendizaje de las palabras ya usadas en la app (ver PLAN.md →
> «Siguiente incremento»).
>
> **Nota (2026-09-08, 22:10):** **V3.26 publicada** — release **v3.26.0** en
> `main` (hoja de ruta completa: **Eje A** retención longitudinal multi-punto y
> gate MASTERED con initial/practice espaciado — F-A1/F-A2/F-A3, **Eje B**
> emisor real de `novel` en misiones B2+ jamás practicadas + ledger
> `vocabulary_events` por superficie, **Eje C** taxonomía de capas de Listening
> + calibración CEFR 2.1.0 unificada + `blocked_by` con motivo en UI + marcas
> de legacy sin `context_id`). CI GitHub Actions **success**; dossier O
> `docs/audit/O-AUDITORIA-TOTAL-V326.md`; release notes
> `release-notes-v3.26.0.md`; CHANGELOG/PLAN/README actualizados;
> `check_release_consistency` **3.26.0** exit 0. Pendiente: auditoría externa
> del candidato v3.26.0 (deuda abierta documentada: reactivación calibrada de
> `novel_required` en B2+, corpus recognition de listening, pesos de support).
>
> **Nota (2026-09-08, 21:25):** **V3.26 · Eje C CERRADO — Listening real
> (taxonomía por capas) + calibración CEFR unificada + skills bloqueantes en UI
> + marca de legacy sin `context_id` en `main`**. **F-C1** (`f8e0c64`):
> taxonomía determinista `skill → recognition/comprehension/inference` en
> `services/listening.py` (reconocimiento = word/sound/phrase_recognition/
> numbers; comprensión = gist/detail/vocabulary/sequencing/note_taking/
> prediction; inferencia = inference/attitude/speaker_intention/fast_speech/
> connected_speech/multiple_speakers; dictation/shadowing y producción aparte,
> capa `null`), capa expuesta en ítems y reporte `by_layer` del diagnóstico;
> sin migración de datos ni re-etiquetado del corpus (la deuda de autoría
> recognition queda documentada). **F-C2** (`b62fc65`): las 4 destrezas planas
> (vocabulary/grammar/interaction/mediation) pasan a escalera monótona desde
> B1 siguiendo la fila de `reading`, conservando su suelo histórico A1/A2;
> extremos unificados por familia (techo de reading/writing); matriz a
> `version 2.1.0` y monotonicidad de las 8 destrezas fijada por tests y
> goldens de `evidence_depth` actualizados. **F-C3** (`eee806a`): `readiness`
> expone `blocked_by` por destreza evaluada y no lista (score/confidence/
> evidence/transfer/novel) y la UI traduce el motivo en `TodayPlan` (i18n
> es/en). **F-C4** (`eee806a`): `build_skill_profile` cuenta
> `legacy_context_rows` y marca `legacy_context_used` por destreza — el
> fallback del gate a filas ocurre solo cuando un kind con filas no tiene
> NINGÚN contexto conocido (con contextos, las filas legacy no cuentan ni
> inflan experiencias) — agregado en `StudentModelOut`
> (`legacy_context_evidence`/`legacy_context_rows`) y `mastery_gate` expone
> `legacy_fallback`; el ladder y ProgressScreen/SkillDetail muestran notas i18n
> cuando el gate o el perfil cae a legacy. Verificación íntegra: pytest backend
> **1538 passed** + `ruff check .` limpio; vitest frontend **450 passed** +
> `tsc --noEmit` limpio. **Pendiente hacia V3.26:** cierre de release (bump +
> dossier + commit final); el Eje C completa el alcance V3.26 del dossier
> (P2-01/P2-02/P2-03/P2-04 y P2-06) — ver nota del Eje B: la reactivación
> calibrada de `novel_required` en B2+ queda como decisión de negocio abierta.
>
> **Nota (2026-09-08, 19:55):** **V3.26 · Eje B CERRADO — emisor real de
> `novel` + historia léxica por superficie en `main`**. **F-B1** (`b057e4b`):
> `novel` deja de ser un kind reservado y gana emisor real — el primer intento
> de una **misión por escenario B2+ jamás practicado** por el alumno
> (detección evidence-only: `mission_context_practiced` consulta
> `academy_evidence` por el contexto canónico `mission:{escenario}`, decisión
> del gerente) escribe evidencia `novel` (`mission_evidence_kind`,
> `services/speaking.py`); retries y repeticiones del mismo escenario escriben
> `familiar` (anti-bombeo: cada escenario produce novel una sola vez, verificada
> por test e2e de repetición). Decisión del gerente: **no se reactiva el
> requisito** — `novel_required = 0` en las 48 celdas de la matriz y el gate
> MASTERED intactos; la activación calibrada de B2+ queda para el Eje C.
> **F-B2** (`5d0a19d`): historia detallada de eventos léxicos por forma de
> superficie — tabla `vocabulary_events` append-only (`word`,
> `lexical_unit`, `event_type` `produced|exposed|retrieval`, `channel`,
> `activity`, `created_at`) escrita en la MISMA transacción de los 4 writers de
> `repositories/vocabulary.py` (sin doble fuente de verdad; invariantes de
> contadores y `sum(channel_prod) == production_count` intactos), endpoint
> `GET /api/vocabulary/history` paginado por palabra y schema
> `VocabularyEventOut`. SIN backfill: la historia empieza en V3.26 (mismo
> criterio que el retrieval); el ledger es señal (D5/E3), nunca puerta de
> mastery. Verificación íntegra: pytest backend **1520 passed** (+14 tests
> nuevos: 4 de misión novel + 10 del ledger) + `ruff check .` limpio; frontend
> sin cambios. **Pendiente hacia V3.26: Eje C** (Listening real + calibración
> CEFR unificada + skills bloqueantes en UI + marca de legacy sin
> `context_id`).
>
> **Nota (2026-09-08, 19:40):** **V3.26 · Eje A CERRADO — retención
> longitudinal multi-punto en `main`** (decisión del gerente: Eje A primero).
> El gate MASTERED y la certificación ya no se satisfacen con un único
> encuentro/`delayed` puntual. Tres incrementos con su tests-first y su commit:
> **F-A1** (`c5cb2b8`) — `initial` = primer encuentro de cada contexto y
> `practice` = re-encuentros ESPACIADOS (≥ `SPACED_PRACTICE_MIN_DAYS` 1 día) del
> mismo contexto (`familiar_spaced_counts` en `mastery_evidence_gate`); legacy
> sin contexto conserva el fallback filas/contextos (F-C4 lo marcará en el
> perfil). **F-A2** (`16bbb50`) — cada evento `delayed` se ancla a su sesión
> formal origen (`delayed_origin_anchors` desde `source_session_id` → parámetro
> `delayed_origins` del gate) y el reporte separa `retention_interval_days`
> (formal→delayed) de `event_age_days` (edad real del evento), conceptos
> distintos, con alias retrocompatible `interval_days`. **F-A3** (`cd69088`) —
> la certificación exige **≥ 2 reassessment points estables por destreza**
> (`CERTIFICATION_REQUIRED_DELAYED = 2`; `stable_points` en el informe), cada
> uno ≥ `RETENTION_MIN_DAYS` desde su origen y con ratio ≥ 0.9 (un único
> delayed ya no certifica); fix del escritor: la retención que reevalúa un
> examen de nivel (`kind=level`) puntúa contra la clave del examen — sus ítems
> no viven en el índice de checks del currículo y `submit` devolvía None sin
> escribir `delayed` — y cada reassessment nuevo se espacia ≥ 7 días del último
> cerrado del mismo origen (`retention_spacing_due`, 409 si no), haciendo que
> >1 punto sea real y la certificación sea alcanzable end-to-end por la
> escalera. Los tests previos del gate (los 6 negativos + boundaries) se
> actualizaron a la semántica multi-punto; docs: `docs/ASSESSMENT_2.md`
> (sección «Certificación del nivel»), `docs/CONSTITUCION-PEDAGOGICA.md` (H5,
> item 6) y docstrings de `CertificationOut`. Verificación íntegra: pytest
> backend **1506 passed** (4 tests nuevos) + `ruff check .` limpio; frontend
> sin cambios. **Pendiente hacia V3.26: Eje B** (emisor real de `novel` +
> historia léxica por superficie) y **Eje C** (Listening real + calibración
> CEFR + `context_id` legacy en el perfil).
>
> **Nota (2026-09-08, 19:25):** **V3.25.1 publicada** — release **v3.25.1**
> `4fd54a5` en `main` (cierre de los 3 P1 de la auditoría externa V3.25:
> `certification_gate` verifica la retención real desde las filas — baseline
> formal `task_type="exam"` + eventos `delayed` por `context_id`, enforce
> `interval >= 7 días` y `ratio >= 0.90`, sin examen no certifica —,
> agregación real por `lexical_unit` aditiva con superficies independientes
> (`units_from_rows`/`summary_units`) y `SUPPORT_LEVEL_WEIGHTS` ponderando
> `generalized_mastery_score` con legacy neutral 1.0). Verificación local
> reproducida (dossier N `docs/audit/N-AUDITORIA-TOTAL-V3251.md`, los 6 tests
> negativos del gate como evidencia de cierre): pytest backend **1495 passed**
> + ruff limpio; vitest **450 passed** (57 archivos) + `tsc` OK;
> `check_release_consistency` **3.25.1** exit 0. Siguiente paso: V3.26
> (Listening + `novel` + retención longitudinal) — planificar juntos antes de
> tocar código.
>
> **Nota (2026-09-08, 16:50):** **V3.25.1 en curso — cierre de P1 de la
> auditoría externa V3.25** sobre `main` (la auditoría del candidato v3.25.0
> detectó 3 P1 reales que la batería de V3.25 no cubría: `certification_gate`
> no enforceaba la ventana ≥7 días ni el ratio ≥0.90; `lexical_unit` no
> agregaba conocimiento por unidad; `support_level` no ponderaba el dominio).
> Trabajo completo en el árbol: **P1-01** `certification_gate` reconstruye
> baseline formal (`task_type="exam"`) + eventos `delayed` por `context_id`
> desde las filas, enforce `interval >= RETENTION_MIN_DAYS` y `rate >= 0.90`, y
> sin examen no certifica; `retention_report` informa `interval_days`/
> `initial_score`/`rate`/`baseline_date`. Los 6 tests negativos de la auditoría
> quedan en `tests/test_assessment_v2.py` (D+6 → False; D+7 ratio 0.89 →
> False; D+7 ratio 0.90 → True; D+21 ratio 0.50 → False; `created_at` inválido
> → False; dos eventos sin ratio válido → False). **P1-02** agregación real por
> `lexical_unit` (aditiva): `units_from_rows`/`summary_units` en
> `services/lexicon.py`, `LexiconOut.units` + `LexiconSummary.units` en
> schemas/domain y tipos frontend; superficies independientes (go/going/went/
> gone). **P1-03** `SUPPORT_LEVEL_WEIGHTS` pondera `generalized_mastery_score`
> (legacy neutral 1.0). Verificación: backend pytest **1495 passed** + ruff
> limpio; frontend vitest **450 passed** (57 archivos) + `tsc` OK;
> `check_release_consistency` 3.25.1 exit 0. Dossier N
> `docs/audit/N-AUDITORIA-TOTAL-V3251.md`; release notes
> `release-notes-v3.25.1.md`; CHANGELOG/PLAN/README actualizados. Siguiente
> paso: cierre del release (commit + bump + CI). Los P2 de la auditoría quedan
> para V3.26 (Listening + `novel` + retención longitudinal).
>
> **Nota (2026-09-08, 14:45):** **V3.25 publicada** — release **v3.25.0**
> `bb31a1b` en `main` (calibración del Student Model del dossier L — auditoría
> TOTAL verificada de V3.24.0 — que absorbe los pendientes F-K3…F-K7: evidencia
> con contexto + `support_level` canónico, transfer por experiencias distintas,
> certificación robusta con `created_at` + `retention_report` de intervalos,
> semántica demostrado/estimado/progreso en Student Model y UI, renombrado
> léxico canónico `production_count`/`exposure_count` con `lexical_unit` y
> doble vía speaking con `cefr_target` persistido). CI GitHub Actions
> **success** (Backend ruff+pytest · Frontend tsc+vitest+build · Playwright E2E
> visual · Content validation · Beta V3.0 gate · Release consistency 3.25.0).
> Verificación local reproducida íntegra (dossier M
> `docs/audit/M-AUDITORIA-TOTAL-V325.md`, APROBADO para cierre, sin BUG REAL):
> pytest backend **1481 passed** + ruff limpio; golden **25 passed**; vitest
> **450 passed** (57 archivos) + tsc/vite build OK;
> `check_release_consistency` **3.25.0** exit 0.
>
> **Nota (2026-09-08, 14:40):** **V3.25 implementada y verificada en el árbol de
> trabajo (sin commit ni release aún)** — candidato release **v3.25.0**
> (calibración del Student Model del dossier L — auditoría TOTAL verificada de
> V3.24.0 — que absorbe los pendientes F-K3…F-K7: evidencia con contexto +
> `support_level` canónico, transfer por experiencias distintas en
> gates/readiness/unit, certificación con `delayed` verificado por `created_at`
> + `retention_report` de intervalos, Student Model y UI con
> `demonstrated_level`/`estimated_level`/`level_progress` separados, renombrado
> canónico `appearances→production_count`/`exposures→exposure_count` con
> `lexical_unit`, y doble vía speaking con `cefr_target` persistido y emisor
> `independent`). Verificación local en el árbol: backend pytest **1481 passed**
> + `ruff check .` limpio; frontend vitest **450 passed** (57 archivos) + `tsc`/
> `vite build` OK; golden (`thresholds.json`) y E2E A1→A2 en verde;
> `check_release_consistency` **3.25.0** exit 0. Dossier L
> `docs/audit/L-AUDITORIA-TOTAL-V324.md`; release notes
> `release-notes-v3.25.0.md`; CHANGELOG/PLAN/README actualizados. Siguiente
> paso: cierre del release (commit + bump + CI).
>
> **Nota (2026-09-08, 13:35):** **V3.24 publicada** — release **v3.24.0**
> `8970634` en `main` (calibración de salida del Student Model: **F-K1**
> MASTERED a lo emisible + **F-K2** estimado anclado + **F-K8** e2e del salto
> A1→A2; `release-notes-v3.24.0.md`). CI GitHub Actions **success** (Content
> validation · Backend ruff+pytest · Frontend tsc+vitest+build · Playwright E2E
> visual · Beta V3.0 gate · Release consistency 3.24.0). Verificación local:
> suite backend **1457 passed** + ruff limpio; Eje 1 del dossier K **G1 311 +
> G2 329**. La sección 38 y su backlog quedan cerrados como histórico (V3.24);
> los P2/P3 del dossier K (F-K3…F-K7) son candidatos del siguiente incremento.
>
> **Nota (2026-09-08, 13:20):** alcance de V3.24 cerrado por el gerente (solo
> **F-K1 + F-K2 + F-K8**) e implementado en el árbol de trabajo (sin commit ni
> release aún). Decisiones cerradas: **F-K1 (b)** relajar a lo emisible —
> MASTERED = familiar×2 + transfer×2 + delayed (`assessment_v2.py`) y
> `novel_required = 0` en las 12 celdas macro de `cefr_matrix.json`; el kind
> `novel` queda **reservado** (sin emisor real) y la frontera se documenta en
> `ASSESSMENT_2.md` y la CONSTITUCIÓN §2.1/§6. **F-K2 (a)** anclaje del estimado
> a niveles completados + progreso del tramo actual (`adaptive.estimated_level`
> recibe `current_level` + `completed_levels`; `build_student_model` las deriva
> de las matrículas `completed`). **F-K8**: test e2e del salto A1→A2 (dominar A1
> → estima A1, no ≥ B2; aprobar el examen A1 → matrícula A2, estimado A1 con
> numeric 1.0, nunca Pre-A1). Verificación completa en el árbol: suite backend
> **1457 passed** + ruff limpio; Eje 1 del dossier K **G1 311 + G2 329** (640,
> +2 tests e2e); frontend sin cambios. Briefing:
> `agentes/v324-calibracion-salida.md`. Se procede al cierre del release
> (commit + bump `3.23.0 → 3.24.0` + higiene de la sección 38.5).
>
> **Nota (2026-09-08, 12:30):** auditar el **Eje 1 (Student Model → Evidence →
> Mastery → Academy → CEFR)** deja dossier nuevo `docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md`
> sobre main `bb3f253` (release v3.23.0 `f3739a9` + fix documental H1; versión
> declarada 3.23.0 intacta). 638 tests del eje reproducidos en verde (G1+G2 del
> dossier K). La cadena actividad → evidencia → mastery → CEFR es determinista y
> sólida (escritor único, no contagio, certificación con `delayed` ≥7 días), pero
> K **no aprueba el cierre del Eje 1** y deja 2 hallazgos **P1** que deciden el
> alcance de V3.24: **F-K1** (el evidence_kind `novel` no tiene emisor mientras
> `mastery_evidence_gate` MASTERED, la readiness B2+ de `cefr_matrix` y el grafo
> lo exigen → `mastery_missing: novel` permanente en la escalera Assessment 2.0)
> y **F-K2** (el nivel estimado se calcula sobre un único nivel sin calibrar y
> rebasa al matricular nivel nuevo — reproducido: dominar A1 estima **B2**;
> aprobar el examen A1 devuelve el estimado a **Pre-A1**). **Todo lo pendiente
> para llegar a V3.24 queda consolidado en la sección 38 de este documento**:
> candidato recomendado, backlog completo y siguientes pasos.
>
> **Nota (2026-09-08, 11:15):** posición vigente **v3.23.0** — **Student Model
> Calibration (parte 2): Retention real y Transfer por contexto** (versión de
> app `3.22.0 → 3.23.0`). Cierra el plan V3.23 del dossier de la auditoría
> externa V3.22.0 (P1-02/P1-04) sobre la base de los quick fixes de esa misma
> auditoría (P1-01/P1-03): **(P1-02) la retención deja de ser exposición/
> producción espaciada y exige recuperación correcta DEMORADA** — migración
> idempotente en `vocabulary` con `retrieval_successes`/`retrieval_days`/
> `last_retrieval_at` (sin backfill: el histórico V3.22 backfilleó
> `first_exposed_at = last_exposed_at`, una ancla retrospectiva sería injusta —
> mejor perder evidencia que inventarla); `record_retrievals` cuenta solo éxitos
> ≥ `RETENTION_MIN_INTERVAL_DAYS` después del ancla
> `min(first_exposed_at, first_seen)` (días distintos → `retrieval_days`); hook
> solo en el micro-drill (`submit_drill_attempt` si `produced`,
> `submit_sentence_attempt` si `passed`); en `item_competence_matrix`,
> `retention = retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS` y
> `_spaced_exposure`/`_spaced_production` pasan a señales independientes
> (`spaced_exposure`/`spaced_production`) · **(P1-04) la transferencia se mide
> por contexto de actividad `channel:activity`, no solo por canal** — migración
> `context_tags` (CSV único y ordenado), `record_production(..., activity)` con
> merge canónico, `activity` propagada por todas las superficies (mapeo
> assessment/misión/checks controlados/tareas LLM/read-aloud/drill/rutas
> speaking/conversación guiada/chat libre), `production_contexts(row)` con
> fallback `channel:other` para legacy; `transfer`/`transfer_contexts` por
> contextos (dos actividades del mismo canal cuentan; `chat`+`conversation`
> dejan de colapsar) · **quick fixes base (auditoría externa V3.22)**: P1-01
> `item_recall` con `_last_activity_at` (max de `last_seen`/`last_exposed_at`);
> P1-03 `item_mastery` con pesos de reconocimiento 0.4 volumen / 0.6
> `exposure_days` y orden ASR `no_speech` (alucinación de silencio) antes que
> `low_confidence` · `summary` añade `spaced_exposure` (informativo) ·
> `LexicalCompetence`/`LexiconSummary` (schemas + TS) con los campos nuevos;
> tooltip del diccionario actualizado (sin renombrar chips). Fuera de alcance:
> `support_level` por evento (V3.24), backfill de retrieval histórico, superficie
> de recuerdo de significado. Verificación: backend **pytest 1455** + ruff
> limpio; frontend **vitest 450** (57 archivos) + `tsc`/`vite build` OK;
> curriculum `--strict --quality` y content validation OK;
> `check_release_consistency` **3.23.0** exit 0; i18n parity exit 0 (1232
> definidas); CONSTITUCIÓN sin cambios (se mantiene señal ≠ evidencia).
>
> **Nota (2026-09-08, 10:30):** posición vigente **v3.22.0** — **ASR
> Calibration + Student Model (léxico)** (versión de app `3.21.0 → 3.22.0`).
> Cierra el plan V3.22 del dossier de la auditoría externa V3.21.0
> (P1-01/02/03 + P1-04/05 + P2-01 parcial): **(ASR-01) calibración ASR por
> segmentos** — en faster-whisper 1.2.1 `avg_logprob`/`no_speech_prob`/
> `compression_ratio` viven en cada `Segment`, no en `TranscriptionInfo`;
> `services/stt.py` agrega ahora con `aggregate_asr_segments` (media ponderada
> por duración de segmento, ratios y `segment_count`) y clasifica con
> `classify_asr_status(*, text, metrics)` — política explícita con
> `MIN_SPEECH_ATTEMPT_SECONDS` 0.5 s: sin texto y 0 segmentos → `unintelligible`
> (audio corto) o `no_speech` (audio ≥ 0.5 s); texto alucinado sobre no-habla
> (`no_speech_ratio` alto, medido real: silencio decodifica "You" con
> `no_speech_prob` 0.85) → `no_speech`; `mean_logprob` < -1.0 →
> `low_confidence`. Estados antes inalcanzables. El gating `asr_status != "ok"`
> es transparente en todos los routers; la telemetría de segmentos se emite sin
> clasificar (frontera `LANGUAGE_MISMATCH` documentada) · **(léxico) Retention ≠
> Transfer** — migración idempotente `exposure_days`/`first_exposed_at` en
> `vocabulary` (backfill 1 día + `first_exposed_at = last_exposed_at`),
> `record_exposures` por fila contando días distintos de exposición (patrón
> `production_days`/`first_seen`), matriz `item_competence_matrix` con
> `transfer_contexts`, `transfer` = 2+ canales (sin "or spaced"), `retention` =
> `_spaced_exposure or _spaced_production`, `production_gap` (antes `gap`) y
> `transfer_gap` (producida-sin-transferir) independientes; `summary` con 6
> contadores; UI del diccionario a 6 chips + claves i18n. Fuera de alcance:
> telemetría ASR persistente, `LANGUAGE_MISMATCH`, renombre
> `appearances → production_count`, preparación Recall → Sentence → Context →
> Free Transfer. Verificación: backend **pytest 1440** (incluye integración ASR
> opt-in con Whisper/piper reales) + ruff limpio; frontend **vitest 450** (57
> archivos) + `tsc`/`vite build` OK; `check_release_consistency` **3.22.0** exit
> 0; CONSTITUCIÓN sin cambios (se mantiene señal ≠ evidencia).
>
> **Nota (2026-09-07, 20:55):** posición vigente **v3.21.0** — **Speaking &
> Evidence Calibration** (versión de app `3.20.0 → 3.21.0`). Cierra el plan
> V3.21 del dossier de la auditoría externa V3.20.0 (F1–F6): (F1 P0) la
> producción del micro-drill se decide por **alineación secuencial**
> (`unit_produced`, normalización compartida `tokenize`) y las unidades
> multi-palabra se acreditan a sí mismas (`as_unit=True`, invariante por fila
> `sum(channel_prod)==appearances`); (F2 P1) **feedback ASR honesto** —
> metadata de Whisper (`no_speech_prob`/`avg_logprob`/`language_probability`),
> `asr_status ∈ {ok, no_speech, unintelligible, low_confidence}` y **gating de
> no-penalización** (un audio no reconocido nunca se puntúa como fallo
> lingüístico), chips re-etiquetados y mensajes por `asr_status`; (F3)
> `DEFAULT_MODEL` fuente única (`/api/models` + `resolveDefaultChatModel`),
> comentario `ADMIN_PIN` fail-closed, hook `useRecordingSession` (cronómetro +
> auto-stop 120 s) con red de seguridad backend de duración (400) y aviso de
> audio vacío; (F4) semántica de superficie Speaking (títulos por modo y pies
> de stats con la competencia real); (F5) **matriz de competencia léxica**
> (Recognition/Production/Transfer/Retention/gap por ítem, pura sin migrar
> columnas) expuesta en léxico/diccionario y **Transfer Gap para FSRS**
> (razón `transfer-gap` por objetivo); (F6) **drill escalera MVP** — paso
> Sentence determinista sin LLM (`sentence_context_for` + endpoints
> sentence-context/sentence-attempt) con UI Recall → Sentence en la misma
> tarjeta, y **graduación espaciada** (2 días de éxito de drill u otra señal
> espaciada para salir de la lista "pendiente"; sin dominio D5/E3). F6.3
> (Contexto/Transfer libre) APLAZADO a la auditoría pedagógica de
> Speaking/Listening. Verificación: backend **pytest 1424** + ruff limpio;
> frontend **vitest 450** (57 archivos) + `tsc`/`vite build` OK;
> `check_release_consistency` **3.21.0** exit 0; CONSTITUCIÓN sin cambios
> (se mantiene señal ≠ evidencia).
>
> **Nota (2026-09-07, 15:05):** posición vigente **v3.20.0** — **Speaking único +
> feedback oral** (frontend-only; versión de app `3.19.0 → 3.20.0`; la
> implementación de V3.19 que quedó sin release previo viaja en el mismo commit
> v3.20.0). Cierra el candidato V3.20 de la nota siguiente tras la prueba del
> gerente, incluido el fix de esa prueba: el botón de **traducir la frase del
> interlocutor** (y el de la respuesta modelo) en Micro-conversación alternaban
> el estado de traducción pero la burbuja seguía pintando el inglés crudo —
> ahora pinta `display` (ES ⇄ EN) como el resto de escenas. Alcance (a)–(f):
> consolidación F1 (hub 4 tarjetas, modos Micro-conversación/Acento/Diálogo
> guiado, legadas que degradan al hub), texto «Cada nivel es una ruta…» plegado
> tras el botón (i), **grabación real reproducible** del alumno, F3 turnos
> hablados (`mode="voice"`), chips palabra a palabra en Acento y F4 URL por modo
> + redirección de legadas. Verificación: **vitest 434** (54 archivos), `tsc` y
> `vite build` OK; `check_release_consistency` **3.20.0** exit 0; backend sin
> cambios de lógica, CONSTITUCIÓN sin cambios. Fuera del cierre (siguiente
> candidato): F2 (pulido de claims del modo, opcional), la evidencia formal de
> interaction (CONV-02, backend) y los pendientes anotados de V3.19.
>
> **Nota (2026-09-07, 14:26):** candidato **V3.20 (working tree, frontend-only)** —
> **F1 de `docs/DISENO-SPEAKING-UNICO.md` + feedback oral en el working tree**:
> (a) la práctica oral se unifica en una sola superficie **Speaking** — el hub de
> APRENDER pasa a **4 tarjetas** (listening · speaking · vocabulario · gramatica)
> y las antiguas tarjetas/URLs de Pronunciación y Conversación dejan de ser
> actividades propias. Sus motores no cambian: se reutilizan como **modos
> internos** de la página Speaking (`features/speaking/SpeakingRoutesPractice.tsx`),
> que ganó un selector de modos **Micro-conversación / Acento / Diálogo guiado**
> en `QuizRoutePage` (prop `modeTabs`, título de superficie unificado "Speaking";
> Acento = `PRONUNCIATION_ROUTE_CONFIG`, Diálogo guiado = `CONVERSATION_ROUTE_CONFIG`,
> exportadas). Consecuencias de navegación: `/aprender/pronunciacion` y
> `/aprender/conversar` degradan al hub (`LEARN_ACTIVITY_IDS` de 6 a 4); NextBest
> de destreza `pronunciation` y el CTA post-assessment de Recorridos navegan a
> Speaking; el chat libre sigue en su raíz `/chat` (marca Speaking en el atajo).
> (b) El texto «Cada nivel es una ruta…» (`*Routes.routesSubtitle`) dejó de ocupar
> el header: en `QuizRoutePage` vive ahora tras un botón **(i) «Cómo funcionan las
> rutas»** plegado por defecto (clave `learn.routesInfoToggle`). (c) **Se reproduce
> la grabación real del alumno** — el backend solo transcribe y descarta el audio,
> así que las escenas de micro-conversación y Acento conservan el blob en memoria
> (`URL.createObjectURL`, revocada al cambiar/desmontar) y muestran el botón
> **«Oír mi grabación»** (`components/RecordingPlayButton.tsx`) junto a la
> respuesta/frase modelo en el resultado; en Acento se añade también el altavoz de
> la frase modelo dentro del resultado. (d) **F3 — Diálogo guiado con turnos
> hablados reales** (`features/conversation/ConversationVoiceButton.tsx` +
> `ConversationGuidedChat.tsx`): el micro del mini-chat ya no es dictado plano —
> graba el turno, mide su duración real (metadata del audio, fallback al reloj),
> transcribe y lo persiste con `mode="voice"` + telemetría (`Message.mode` admite
> `"voice"`). El backend (sin cambios) ya distingue el tecleo `mode="conversation"`
> de los turnos que computan como habla (CONV-01 V3.19): los turnos por voz
> alimentan `_student_speech_seconds`, `turn_duration`/latencia de
> `interaction_evidence` y la resistencia de conversación. (e) **Chips palabra a
> palabra en el modo Acento** (mockup §6.3): nueva tarjeta «Frase palabra a
> palabra» en el resultado del read-aloud con la frase modelo coloreada por
> palabra — verde (bien dicha), ámbar (sustituida, muestra `→ lo dicho`), roja
> (no dicha) y «+extra» punteado (palabras de más). La clasificación la calcula
> `utils/pronunciationAlignment.ts`, un puerto TS del `SequenceMatcher` de
> difflib (Ratcliff-Obershelp sin junk) que reproduce exactamente la alineación
> del backend `services/phonetics.py::word_alignment` (tests de paridad con los
> casos de `test_phonetics.py`), de modo que los chips siempre cuadran con
> `word_accuracy` y el breakdown mostrado. (f) **F4 — URL por modo + redirección
> de legadas** (`router/learnHub.ts`): el modo activo de Speaking vive en la URL
> (`/aprender/speaking` = micro, `/aprender/speaking/acento` = Acento,
> `/aprender/speaking/dialogo` = Diálogo guiado; alias en inglés aceptados).
> `SpeakingRoutesPractice` arranca desde la ruta, la URL manda en back/forward y
> cambiar de pestaña navega a la ruta canónica (`speakingModePath`). Las
> sub-rutas legadas de las antiguas tarjetas resuelven SÍNCRONO como Speaking con
> su modo (`/aprender/pronunciacion` → Acento, `/aprender/conversar` → Diálogo;
> `SPEAKING_ROOT_LEAF`/`speakingModeFromPath`/`learnActivityFromPath`) y App
> canonicaliza la URL al destino (`legacySpeakingRedirect`, sin parpadeo de hub).
> Tests: router/paridad actualizados + **vitest 434 passed** (54 archivos), `tsc`
> y `vite build` OK;
> backend **sin cambios** (versiones NO subidas; cierre de candidato V3.20 y
> CHANGELOG pendientes). Pendiente del doc (no iniciado): F2 (pulido de claims
> del modo, opcional), la decisión abierta de emitir evidencia formal de
> interaction (CONV-02, backend) y el cierre del candidato V3.20 (versión +
> CHANGELOG) tras la prueba del gerente.
>
> **Nota (2026-09-07, 10:05):** posición vigente **v3.19.0** — **Léxico por
> destreza + Speaking micro-drill** (backend `3.18.0 → 3.19.0`). Cierra el
> candidato V3.19 con las decisiones del gerente y el dossier de la auditoría
> profunda V3.18: **P0** — `record_words` → `record_production(user, words,
> channel)`; la tabla `vocabulary` gana `chat_prod`/`speaking_prod`/
> `writing_prod`/`conversation_prod` (migración idempotente + backfill
> `chat_prod = appearances`; invariante `sum(columnas) == appearances`) y las 7
> superficies de producción vuelcan el texto del alumno por un único helper
> compartido (CAP-01/REFAC-01) · **P1** — speaking micro-drill de 1 nivel
> honesto: señal determinista en servidor `exposures > 0 AND speaking_prod == 0`
> (`drill_candidates` + `GET /api/vocabulary/drill/candidates`), práctica sobre
> el scorer de pronunciación (`POST /api/vocabulary/drill/attempt`; éxito →
> `speaking_prod`, sin evidence/FSRS — D5/E3) y chips con acción real en
> `PersonalDictionary` (con error + reintento) · **Fixes P1 del dossier**: R6-01
> retención impuesta en servidor (409), GATE-01 objetivo `locked` no evaluable
> (409), CLAIM-01 copy "nivel oral actual (examen)" en Speaking/Pron/
> Conversation, SIGNAL-01 semántica oral + copy, ERR-01 404→503 en misiones/
> assessment/task, LIST-01/02/03 tokens de foco servibles + corpus re-etiquetado/
> re-autorado + unicidad de `script` normalizado, CONV-01 reconstrucción por
> `mode` (el tecleo no cuenta como tiempo oral) · **Deuda externa**: ADMIN-01
> fail-closed (`ADMIN_PIN=""` → 401) y BOOL-01 (`type(selected) is int`). Tests:
> **pytest 1371**, **vitest 417**, ruff limpio, `tsc`/`vite build` OK,
> curriculum `--strict --quality` exit 0 y `check_release_consistency` **3.19.0**
> exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta abierta; fuera de alcance
> V3.19: GRAPH-01, modalidad oral/tecleo, WR-UI-01, LEX-03 — ver entrada 37.37).
>
> **Nota (2026-09-07):** posición vigente **v3.18.0** — **Knowledge Graph
> remainder + deuda del grafo** (backend `3.17.0 → 3.18.0`). Cierra el candidato
> P3: **I2** — ancla de unidad congelada al completar (tabla `unit_review_anchors`
> de escritura única `INSERT OR IGNORE` + backfill lazy; los refuerzos/decay ya
> no desplazan las ventanas 7/30/90) · **O1** — cascade de ventanas (una ventana
> sin intento propio se cierra con un intento superado de la unidad posterior a su
> `due_at`; el intento propio manda) · **M4** — cartas FSRS `objective` fuera del
> `FsrsReviewPanel` autograduable (single writer con el micro-review: siembra solo
> en ventana `due_now`/`failed` o con `reps > 0`; `get_fsrs_due`/`due_count` las
> excluyen y `/fsrs/review` responde 400) · **O3** — `/unit-plan` agregado por
> niveles (`{levels, due_count}`, actual + anteriores matriculados) y micro-review
> con `level_id` que valida la unidad en el nivel donde vive (UI agrupada por
> nivel) · **H5** — etiquetas humanas de las 7 dimensiones del grafo
> (`GRAPH_DIMENSION_LABELS` + `dimensionLabel`) en chip/`NextBestCard`/
> `ObjectiveNodeCard`/`EvidenceGraphPanel` · **H6** — `/session` y `/next-best`
> lazy (una sola `list_evidence` y solo si hay nodos que construir; payloads
> idénticos) · **auditoría v3.17** — `ObjectiveNodeCard` distingue error real
> (copia + reintento) de 404/sin-datos, `_as_float` defensivo en
> `rank_weakness_objectives`, spec Playwright `homeGraphChip` nueva (chip
> "Transfer" con mock determinista). Tests: **pytest 1345**, **vitest 414**, ruff
> limpio, `tsc`/`vite build` OK, Playwright de la región Home/grafo en desktop OK
> y `check_release_consistency` exit 0; CONSTITUCIÓN sin cambios.
>
> **Nota (2026-09-07, 09:10):** verificación de cierre de v3.18 reproducida en
> vivo sin cambios de código — pytest **1345** ✅, ruff limpio ✅, vitest **414**
> ✅, `tsc`/`vite build` OK ✅ y `check_release_consistency` **3.18.0** exit 0 ✅
> (versión en `config.py`/`package.json`/`package-lock.json` y resto de fuentes).
> Con los candidatos P0–P3 cerrados, solo queda abierto el **pendiente heredado
> de léxico** (producción volcada por destreza speaking/writing + speaking
> micro-drill de `recognized_not_produced`); queda definido como candidato
> **V3.19** en la sección final (bloques P0/P1). CONSTITUCIÓN sin cambios.
>
> **Nota (2026-09-07, 09:25):** **auditoría profunda V3.18 (read-only, pre-V3.19)**
> completada en 6 áreas — dossier `docs/audit/I-AUDITORIA-PROFUNDA-V318.md`
> (runbook `agentes/auditoria-profunda-v318.md`). Sin P0 confirmado; lista
> P0/P1/P2 mapeada a decisiones V3.19. V3.18 sigue **APROBADO CON MATICES**:
> núcleo mastery/repaso I2-O1-M4-O3-H6/FSRS/evidence depth correctos y fijados.
> P1 clave previos a implementar V3.19: **R6-01** (retención R6 sin enforcement
> en servidor: `assessment_v2` escribe `delayed` sin ventana ni ratio — candidata
> a P0), **GATE-01** (objetivo `locked` evaluable por API directa; premisa 21),
> **CLAIM-01** (UI "Speaking demostrado" desde EMA sin gate), **SIGNAL-01**
> (`recognized_not_produced` con semántica de teclado y chips inertes),
> **PROD-01/WR-UI-01** (confirmado en código: ningún flujo oral/escrito vuelca al
> léxico — base del P0 V3.19). Deuda de la auditoría externa diferida a V3.19:
> **ADMIN-01** (`ADMIN_PIN=""` → fail-closed) y **BOOL-01** (bool-as-int en
> `unit_review.py`). Sin cambios de código ni de CONSTITUCIÓN (R8/R9 propuesta
> abierta); `backend/config.py` sigue `3.18.0`.
>
> **Nota (2026-09-06):** posición vigente **v3.17.0** — **Knowledge Graph +
> Daily Adaptive Plan** (backend `3.16.0 → 3.17.0`). Cierra el candidato P2:
> el plan diario ahora **deriva del Evidence Graph** — la destreza débil se
> practica sobre el objetivo que su nodo señala (D1b) y los pasos de la sesión
> traen `can_do`/`limiting_factor`/`graph_mastery`/`because[]` (enriquecidos
> por dominio con una única lectura de evidencia; `/session` y `/next-best`
> nunca divergen). **D2**: vista de grafo real — nuevo componente
> `ObjectiveNodeCard` (consume `getEvidenceGraphNode`) montado en el curso
> (hitos de unidad expansibles bajo demanda) y en el perfil (Habilidades);
> sin claims de dominio: solo refleja lo que el servidor puntúa. **D3**:
> `/api/academy/today` eliminado de extremo a extremo (endpoint,
> `get_today_plan`, `TodayPlanOut`/`TodayItemOut`, `adaptive.today_plan` +
> `TODAY_MIX`, cliente y tipos frontend); la Home consume solo `/session`
> (Session Engine); tests migrados con rationale honesto. **Deuda v3.16
> (D4b)**: M2 ✅ (`validate_micro_review_answers`: claves ⊆ muestra e índices
> en rango → 400), M3 ✅ (prefijos dinámicos en `DYNAMIC_KEY_PREFIXES`) y O2 ✅
> (test GET==POST con reintento parcial); M1 ✅ en el cierre (devDeps DOM
> `jsdom` + `@testing-library/react` + `*.test.tsx` en vitest + 6 vitest de
> componente de `UnitReviewPanel`/`TodayPlan`). **D5**: `GRAPH_VERSION` sigue
> `2.12.0` (cambio aditivo). **D6**: micro-líneas del can-do/factor limitante
> en las filas de la sesión. **D7**: fallback silencioso sin nodo (la práctica
> nunca se bloquea). Tests: **pytest 1333**, **vitest 398**, ruff limpio,
> `tsc`/`vite build` OK y `check_release_consistency` exit 0; CONSTITUCIÓN sin
> cambios.
>
> Auditoría externa v3.17 (2026-09-06, read-only): **APROBADO CON
> OBSERVACIONES** — D1b/D2c/D3a/D4b/D5a/D6a/D7a ✅ reproducidos en vivo.
> Hotfix aplicado (commit en `main` tras `989658e`): **H1** — 2 tests de
> integración del camino REAL de remediación D1b (paso `weakness` de examen
> suspendido enriquecido con el can-do real + paridad `/next-best`==`/session`
> con primer paso CON nodo) → **pytest 1335**; **H2** — panel de Habilidades
> sin recorte a 12 nodos (criterio 5 de D2); **H3** — `Milestone` no expande
> objetivos `locked`; **H4** — typo docs («10 puros» → «9»). Deuda menor
> **H5**/**H6** + observaciones del informe → candidato v3.18 (37.35).
>
> **Nota (2026-09-03):** este documento quedó congelado en la posición v2.4.0.
> La posición vigente es **v3.2.0** (Calibración pedagógica de niveles) y el
> roadmap actual vive en `PLAN.md` (+ `README.md`, `CHANGELOG.md`,
> `docs/UI_V3.1.md`, `docs/AUDITORIA-V3.md`). La auditoría pedagógica del modelo
> de nivelación (2026-09-03) está en `docs/audit/H-NIVELACION-PEDAGOGICA.md` y su
> especificación normativa en `docs/CONSTITUCION-PEDAGOGICA.md` (ver 37.29 abajo).
>
> **Nota (2026-09-06):** posición vigente **v3.16.0** — **Review/SRS por
> unidad: micro-review + ventanas de retención fijas 7/30/90 días**
> (backend `3.15.0 → 3.16.0`). Cierra el candidato P1 "Review/SRS por unidad"
> (auditado abierto 2026-09-05): el motor FSRS ya soportaba
> `target_type="objective"` pero no se sembraba; no había plan de repaso por
> unidad ni ventanas fijas. **Motor**: nuevo `backend/services/unit_review.py`
> puro y determinista — ventanas `(7, 30, 90)` desde el ancla de la unidad
> (completada = todos sus objetivos `mastered`; ancla = `max(updated_at)`),
> estados `upcoming/due_now/passed/failed`, micro-review con muestreo
> balanceado de los checks MC **oficiales** del currículo (cero contenido
> artificial; reintento prioriza fallidos) y puntuación en servidor (premisa
> 21). **Siembra**: `sync_fsrs_cards` siembra/refresca cartas `objective` solo
> para objetivos de unidades completadas del nivel actual, sin pisar `reps > 0`
> y sin tocar `fsrs.TARGET_TYPES`; `why_for_objective` en `fsrs.py`
> (`unit-window-N` / `unit-maintenance`). **Datos**: tabla idempotente
> `unit_review_attempts` (`per_objective` + `failed_items` JSON) + repos; el
> micro-review **no** crea evidencia de mastery/currículo ni declara dominio
> (D5; mecanismos separados, E3). **API**: `GET /api/academy/review/unit-plan`
> y `GET/POST /api/academy/review/unit/{unit_id}/micro-review` con gating
> (400 ventana no repasable / 404 unidad ajena). **UI**: `UnitReviewPanel` en
> INICIO (junto a `FsrsReviewPanel`) con chips de ventana 7/30/90, micro-review
> por tarjetas y nota honesta "no cuenta como demostración de dominio"; lógica
> pura `unitReviewLogic.ts`; i18n es/en con parity. **Tests**: `pytest 1318`,
> `vitest 392` y build frontend OK; CONSTITUCIÓN sin cambios (mecanismo, no
> norma). **Auditoría externa (read-only)**: APROBADO CON OBSERVACIONES; fix
> aplicado del hallazgo I1 (bug `selected_index` con opción A) + test de
> regresión; deuda I2/M1–M4/O1–O3 registrada en el candidato v3.17 (37.34).
>
> **Nota (2026-09-06):** posición vigente **v3.15.0** — **Profundidad avanzada
> C1/C2: densidad, taxonomía avanzada y banco grammar C2 normalizado**
> (backend `3.14.0 → 3.15.0`). Cierra el candidato P0 "C1/C2 depth" (auditado
> abierto 2026-09-05). **Contenido**: C1 y C2 pasan de 14 a 20 objetivos con
> evidencia completa (checks MC + activities con fases; +30 activities y
> +18/+19 checks por nivel) en `c1-m02-u01`/`c1-m03-u01` y `c2-m02-u01` (+2 en
> `c2-m02-u01-l01` "Register shifts" + lección nueva `c2-m02-u01-l03` con
> elipsis/gramática formal y cohesion discursiva); módulos Final intactos
> (`c1-m04`, `c2-m03`). **Taxonomía**: `SUBSKILLS` (`services/curriculum.py`)
> gana la capa avanzada `register`/`pragmatics`/`discourse`/`nuance`/
> `argumentation` en speaking/listening/writing/grammar/reading/vocabulary y los
> objetivos C1/C2 se re-etiquetan donde su contenido lo justifica (C1 3→16 y C2
> 7→20 con subskill avanzada; A1–B2 intactos). **Banco grammar C2**:
> normalizado 8 → 15 ítems (11 MC + 4 CP en 3 temas); C2 deja de ser el único
> banco corto real y su práctica deja de leer `low`; la regla R7 sigue
> verificada con un **banco corto sintético** construido en los tests.
> **Tests**: snapshot depth V2.6 reformulado
> (`test_depth_c1_c2_reach_deep_target_after_v315`), R7 re-apuntada y conteos
> C2 actualizados (8 → 15); textos "C2 = 4" retirados de
> `quiz_routes.py`/`grammar_routes.py`. Métricas de cierre: `depth(C1) 93.1`,
> `depth(C2) 92.5` (≥ 90, por encima del resto), unit coverage 100 % (31/31) y
> Unit Learning Loop 100 % en 9 fases, `validate_level` vacío en 6 niveles y
> CLI `--strict --quality` exit 0. Tests: **pytest 1293**, **vitest 382** y
> build frontend OK (sin cambios de frontend/launcher; CONSTITUCIÓN sin cambios:
> iteración de contenido, no normativa).
>
> **Nota (2026-09-05):** posición vigente **v3.14.0** — **Registro cross-skill
> de B1 a los 6 niveles (A1–C2)** (backend `3.13.0 → 3.14.0`). Escala el registro
> por estructura (V3.13 P1.2) del prototipo B1 a `a1..c2` con datos reales por
> nivel y sin marca de prototipo. **Contenido**: ítems `controlled_production`
> nuevos en A1 (`a1-cp-01..06`: `to be`, present simple 3.ª, adverbios de
> frecuencia, `have/has got`, preposiciones, past simple) y C2 (`c2-cp-01..04`:
> inversión enfática, cleft, mixed conditional, pasiva formal); el banco Grammar
> crece (A1 38→44, C2 4→8) y C2 conserva "evidence depth LOW" (banco ≤12) sin
> claims falsos. **Motor**: `backend/services/cross_skill.py` generalizado
> (`CROSS_SKILL_LEVELS = a1..c2`), `PRODUCTION_BINDINGS_BY_LEVEL` normativo en
> los seis niveles (test: sin CP huérfanos y toda estructura con binding ofrece
> producción); se elimina `proto` del esquema (`schemas/cross_skill.py`) y de los
> tipos frontend; `/api/cross-skill` valida `a1..c2` (400
> `cross_skill.level_unknown`). **UI**: `CrossSkillMatrix` en el panel Grammar de
> cualquier nivel, copia generalizada y clave `crossSkill.protoNote` retirada de
> i18n. Tests: **pytest 1293**, **vitest 382**, Playwright desktop verde
> (grammarRoutesReview mockea `/api/cross-skill`).
>
> **Nota (2026-09-05):** posición vigente **v3.13.0** — **Calibración de
> evidencia pedagógica** (backend `3.12.0 → 3.13.0`). La iteración recalibra el
> modelo pedagógico sin añadir actividades: `docs/CONSTITUCION-PEDAGOGICA.md`
> pasa a ser el documento normativo único con **Reglas inmutables R1–R7**, §6.4
> **evidence depth** (LOW/MEDIUM/HIGH contra `cefr_matrix.json`) y §7 por
> modalidades. **P0 (motor)**: nuevo `backend/services/evidence_depth.py`
> (expuesto en `/api/profile`), claims honestos —`stats` por nivel con
> `bank_size` + `evidence_depth`; bancos cortos (Grammar B2/C2 ≤12 checks)
> muestran "practice coverage · evidence depth LOW" y nunca invitan a competencia
> fuerte—, suelo de "demostrado" = gate funcional + mínimo de muestras +
> retención ≥7d + **producción** en destrezas productivas (solo MC no demuestra;
> vocabulary techado en `functional`), `current_level` redefinido como sugerencia
> de material con fallback `review_due`, e invariantes pedagógicas en
> `test_pedagogical_invariants.py`. **P1 (producción/cross-skill)**: ítems
> `controlled_production` de grammar en el currículo (typed answers
> deterministas, A2–C1) sobre el motor compartido de rutas; cross-skill evidence
> B1 (registro de estructuras, `/api/cross-skill`, panel `CrossSkillMatrix`);
> golden pedagogical dataset (`tests/golden/pedagogy/`). **P2 (UI)**: shell
> compartido `frontend/src/features/routes/QuizRoutePage.tsx` + máquina de sesión
> consolidada `routeSession.ts`; migradas Grammar, Vocabulary, Pronunciation,
> Conversation y Speaking (~1.600 líneas eliminadas; Listening no migra: es la
> única práctica servida dentro del runner `PracticeView` del workspace);
> parity i18n automática (`i18n.parity.test.ts`). Tests en verde: **pytest 1290**,
> **vitest 382**, Playwright desktop con las 5 review specs de rutas.
>
> **Nota (2026-09-05):** posición vigente **v3.12.0** — **Grammar por rutas CEFR
> (página única de checks MC del currículo)**. APRENDER → Grammar deja el chat
> del tutor (que sigue en `/chat`) y pasa a página única como el resto: arriba
> el escenario de práctica —un check MC de grammar del currículo del nivel
> recomendado, con feedback inmediato y la respuesta correcta revelada al
> fallar— y debajo el mapa de rutas A1–C2 con anillos y el panel del nivel
> (Practicar el nivel / Repetir fallidas / Repasar aprendidas + bloque
> «Demostrar el nivel» que abre los instrumentos formales del curso: exámenes y
> escalera de evaluaciones). El banco **no se inventa**: reutiliza los checks MC
> de la destreza grammar del currículo oficial
> (`backend/curriculum/a1.json`…`c2.json`, 97 checks; B2 = 8 y C2 = 4 como
> bancos cortos con puerta adaptada) sobre el **motor compartido**
> `backend/services/quiz_routes.py`. Intento determinista
> `domain/grammar_routes.py::submit_attempt`, persistido en
> `grammar_route_attempts` (repo `repositories/grammar_routes.py`); endpoints
> `/api/grammar/routes/stats|question|items` y `POST /attempt`. Frontend:
> página única `GrammarRoutesPractice` + `GrammarLevelPanel` + `grammarSession`
> en `/#/aprender/gramatica` (Workspace: rama propia, fuera de PracticeView).
> Ruta = práctica (`functional`, nunca certifica); demostrar exige exámenes +
> evaluaciones formales del curso. Con Grammar, las 6 actividades de APRENDER
> comparten la misma página única de rutas CEFR.
>
> **Nota (2026-09-05):** posición vigente **v3.11.0** — **Vocabulary por rutas
> CEFR (página única de checks MC del currículo)**. APRENDER → Vocabulary deja de
> ser solo el diccionario personal y pasa a página única como el resto: arriba
> el escenario de práctica —un check MC de vocabulary del currículo del nivel
> recomendado, con feedback inmediato y la respuesta correcta revelada al
> fallar— y debajo el mapa de rutas A1–C2 con anillos y el panel del nivel
> (Practicar el nivel / Repetir fallidas / Repasar aprendidas + bloque
> «Demostrar el nivel» que abre los instrumentos formales del curso: exámenes y
> escalera de evaluaciones). El banco **no se inventa**: cada nivel reutiliza los
> checks MC de la destreza vocabulary del currículo oficial
> (`backend/curriculum/a1.json`…`c2.json`) sobre el **motor compartido de rutas
> quiz** `backend/services/quiz_routes.py` (cobertura/precisión/checkpoint
> adaptada a bancos cortos; lo reutilizará Grammar v3.12). Intento determinista
> `domain/vocabulary_routes.py::submit_attempt` → `services/quiz_routes.py`,
> persistido en `vocabulary_route_attempts` (repo
> `repositories/vocabulary_routes.py`); endpoints
> `/api/vocabulary/routes/stats|question|items` y `POST /attempt`. Frontend:
> página única `VocabularyRoutesPractice` (con el diccionario personal integrado
> bajo el botón «Mi diccionario») + `VocabularyLevelPanel` + `vocabularySession`.
> Ruta = práctica (`functional`, nunca certifica); demostrar exige exámenes +
> evaluaciones formales del curso. Siguiente: Grammar (v3.12) con la misma
> filosofía.
>
> **Nota (2026-09-04):** posición vigente **v3.10.0** — **Conversation por rutas
> CEFR (página única de mini-diálogos guiados multi-turno)**. APRENDER →
> Conversation deja el chat libre (que vive en su propia raíz `/chat` desde esta
> versión, siempre accesible) y pasa a página única como Speaking: arriba el
> mini-diálogo guiado con el tutor (contexto, roles, metas comunicativas y línea
> de apertura; se conversa por texto o micrófono) y debajo el mapa de rutas
> A1–C2 con anillos y el panel del nivel (Repetir fallidos / Repasar aprendidos
> + bloque «Demostrar el nivel» → Speaking Assessment). Banco oficial
> `backend/curriculum/conversation_corpus.json` (v1.0.0: 11 mini-diálogos por
> nivel). El intento se evalúa sobre el transcripto completo de la conversación
> (`domain/conversation_routes.py::submit_attempt` →
> `speaking_llm.extract_speaking_evidence` con task_type conversation + señal
> objetiva de interacción) y se persiste por diálogo. Ruta = práctica
> (`functional`, nunca certifica); demostrar exige Speaking Assessment +
> evidencia + retención. Siguiente: Vocabulary (v3.11) y Grammar (v3.12) con la
> misma filosofía.
>
> **Nota (2026-09-04):** posición vigente **v3.9.0** — **Pronunciation por rutas
> CEFR (página única read-aloud)**. APRENDER → Pronunciation es ahora una página
> única como Speaking/Listening: arriba la frase modelo (escucha con TTS local +
> grabación) y debajo el mapa de rutas A1–C2 con anillos y el panel del nivel
> (Repetir fallidas / Repasar aprendidas / Practicar o repasar el nivel + bloque
> «Demostrar el nivel» que abre el Speaking Assessment). Banco oficial
> `backend/curriculum/pronunciation_corpus.json` (v1.0.0: 20 frases por nivel);
> intento determinista `domain/pronunciation_routes.py::submit_attempt` →
> `services/pronunciation.py::score_pronunciation` (Whisper, sin LLM). Ruta =
> práctica (`functional`, nunca certifica); demostrar exige Speaking Assessment +
> evidencia + retención. Siguiente: Conversation (v3.10), Vocabulary (v3.11) y
> Grammar (v3.12) con la misma filosofía.
>
> **Nota (2026-09-04):** posición vigente **v3.8.0** — **Speaking por
> micro-conversaciones guiadas con operativa tipo Listening**. El roadmap y los
> cambios viven en `PLAN.md`, `CHANGELOG.md` y `README.md`. Para retomar Speaking:
> APRENDER → Speaking es una página única con scroll (escenario de práctica con
> tarjetas de intercambio `{setup, you, app_line, model_response}` arriba y mapa
> de rutas A1–C2 con anillos bajo él); el banco curado es
> `backend/curriculum/speaking_corpus.json` (v2.0.0, 148 tarjetas) y cada intento
> se evalúa como respuesta abierta (`domain/speaking_routes.py::submit_attempt`
> → `speaking_llm.extract_speaking_evidence` + `speaking.scores_from_evidence`),
> con audio TTS cacheado por tipo (`?kind=opening|model`). La ruta sigue siendo un
> hito de práctica (`functional`, nunca certifica); demostrar el nivel exige el
> Speaking Assessment + escenarios/misiones + retención.

## 0. START HERE — para el gerente que retoma ahora

**Posición actual (2026-09-10):** `v3.38.1` **Cierre quirúrgico de los P1 del
Planner + UI de diccionario y estado** — patch ADITIVO sobre V3.38.0 que cierra
sus 4 P1 (planner globalmente óptimo, señales por modalidad, `skill_gap` parcial
accionable y automaticidad robusta), endurece `situation` (nuevo módulo puro
`services/situation.py`; `GENERATOR_VERSION` 1.2.1) y reubica en la UI el
diccionario (ruta dedicada `/diccionario`) y el estado de conexión (cabecera,
sin barra inferior). Sin migración de BD y sin tocar scoring, FSRS ni la
semántica del intervalo de evidencia.

**Base inmediata — V3.38.0, «La siguiente tarea óptima: `situación`, planner y
automaticidad por skill».** V3.38.0 dejó la evidencia fina (modalidad, latencia,
tipo de error, apoyo, contexto) USÁNDOSE para planificar y para hablar por
modalidad: **(1)** El `skill` del ledger léxico deja de ser `""`
(vocabulario canónico `LEXICAL_SKILLS` + mapeo canal→skill), el resumen segmenta
los éxitos por skill (puro + SQL con paridad exacta) y `automatic_skills` mide
automaticidad POR modalidad: un ítem no es "automático" por mezclar
reconocimiento con producción. **(2)** Nuevo `services/planner.py` (Optimal Next
Task): `planned_signals` (olvido, hueco, debilidad, dependencia de apoyo,
latencia) + `priority_score` con pesos declarados + `evidence_reason`
(`error_prone`, `skill_gap`, `slow_recall`); la cola de repaso se ordena por
`priority` (desempate por `retrievability` y palabra) y expone
`priority`/`signals`/`why`/`automatic_skills` sin spoiler. **(3)** `situación`:
`GENERATOR_VERSION` 1.2.0 y columna `dictionary_entries.situation` (migración
aditiva e idempotente) — un enunciado situacional con un único hueco `_____`,
validado de forma determinista y descartado (sin invalidar definición/traducción)
si no cumple; es el TECHO de la escalera de recall (`situation`, apoyo `guided`),
servido por el drill y recomendado por la cola, degradando siempre hacia más
apoyo. Contrato aditivo; sin tocar scoring, FSRS ni la semántica del intervalo de
evidencia. Cerradas antes la **V3.37.1** (política de consolidación y regresión
de la escalera: solo asciende con ≥2 éxitos en ≥2 días naturales distintos y
RETROCEDE hacia más apoyo ante ≥2 fallos sin ningún éxito) y la **V3.37.0**
(Learning Evidence 3.0: cues graduados `translation (cued) < definition (cued) <
cloze (guided)` + automaticidad por evidencia espaciada), la **V3.36.0**
(Learning Evidence 2.0: el ledger captura el CÓMO de cada evento) y la
**V3.35.x** (Longitudinal Learning Evidence 1.0 + patch de integridad). La
V3.38.1 tiene **CI 6/6 en verde** (run
[34500794657](https://github.com/jvelasca/english-tutor/actions/runs/34500794657)
sobre `856e115`). Versión en
`config.py`/`package.json`/`package-lock.json`/`CHANGELOG`/`README`/`PLAN`.
**Las notas de la cabecera de este documento son la fuente de verdad más
reciente**; si contradicen a esta sección, mandan las notas.

**Siguiente incremento (V3.39) — arquitectura por skill del planner (definida,
no implementada).** V3.38.1 dejó la SEGMENTACIÓN montada y consumida en parte: el
planner ya recibe `planned_signals.skills[skill] = {attempts, successes,
success_rate, weakness, support, latency}` (calculado por `planner.skill_signals`
a partir de `skill_attempts`/`skill_successes`/`skill_independent_successes`/
`skill_mean_response_time_ms`, con paridad pura↔SQL), y de ahí ya se derivan
`automatic_skills`, el `skill_gap` PARCIAL (solo oral) y el `slow_recall` por
latencia de `recall`. Lo que queda para V3.39 es la DECISIÓN, no la señal:

- **Elegir skill + actividad óptima, no solo la razón.** Hoy `priority_score` es
  GLOBAL y la actividad sale de `ACTIVITY_FOR_REASON` (razones cualitativas). El
  paso siguiente es puntuar por (skill, actividad) —argmax sobre
  `planned_signals.skills` con los mismos pesos declarados— para que el planner
  pueda decir "la modalidad limitante es `spoken_production`, la tarea es
  `sentence`" y no solo "hay un hueco oral".
- **Routing de ESCRITURA para `written_production`.** Hoy el hueco simétrico
  (`spoken ✓ / written ✗`) se expone en `signals.skill_gaps` pero NO emite razón
  accionable: no hay un drill de escritura en la cola (el `sentence` del drill
  actual es oral). V3.39 debe añadir esa ruta para que el hueco de escritura sea
  accionable igual que el oral (P1-03 quedó cerrado solo para el oral, a
  propósito).
- **`spontaneous_use` sin actividad.** La cuarta modalidad se mide pero no tiene
  tarea asociada (el canal legacy `chat` mapea a ella); decidir su actividad es
  parte de la decisión por skill.
- **Recencia ponderada de fallos y calibración de pesos.** `AUTOMATIC_MAX_WRONG_
  WORD_ERRORS` es una aproximación determinista SIN recencia (documentada en
  `services/evidence.py`) y `PRIORITY_WEIGHTS` no se ha optimizado: V3.39 los
  convierte en señales ponderadas por tiempo/skill.
- **`sense`/CEFR/contexto + transferencia real (V3.23).** La transferencia por
  contexto sigue diferida (el `gap` de transferencia existe como señal, 0.5).
- **Deudas menores:** `cloze_coverage` de corpus, `example_for_many` de la Review
  Queue y refactor de `wordDrill.tsx`.

Sin cambio de modelo de evidencia previsto: V3.38.0 ya dejó el ledger segmentado
por modalidad y V3.38.1 dejó el planner leyendo la evidencia fina por modalidad,
así que V3.39 puede atacar la decisión sin migración.

**Histórico (hasta V2.4, 2026-08-31):** `v2.4.0` **CURRICULUM COVERAGE verificada en verde**
(la versión está elevada a `2.4.0` en `config.py`/`package.json`/`package-lock.json`/`CHANGELOG`/`README`/`PLAN`).
Cerrada la **V2.4 AUDITORÍA DE COBERTURA CURRICULAR** (instrumentación que responde con datos a
"¿el alumno puede recorrer completo A1→C2?": servicio puro `services/curriculum_coverage.py` con
`coverage_sections`/`bank_intersection`/tri-estado `complete`/`partial`/`empty`/`level_coverage`/
`curriculum_coverage_report`, métrica **TOTAL CURRICULUM COVERAGE = 42/49 celdas (85,7%)** distinta de
TOTAL VALIDATED LEARNING ITEMS = 189, integrada en `content_stats()` (anti-drift), CLI
`scripts/curriculum_coverage.py` (`--strict` = exit 1 si hay huecos `empty`), tests
`test_curriculum_coverage.py` (9 invariantes, backend 971 tests) y mapa `docs/CURRICULUM_COVERAGE.md`
con los huecos priorizados; Pre-A1 solo marcado como hueco, sin contenido), y antes la
**V2.3 PERSONAL DICTIONARY** (bajar el modelo de evidencia de "destreza" a "palabra/estructura":
columnas `cefr`/`level_id`/`objective_id`/`source`/`lemma`/`kind` en `vocabulary` vía migración idempotente,
siembra de `objective.vocabulary` + `objective.concepts` cableada en `submit_objective_assessment` y
`record_lesson_completed`, servicio puro `services/lexicon.py` con `item_mastery`/`item_recall`/`item_status`
(`mastered`/`known`/`learning`/`weak`)/`next_review_days`/`cefr_distribution`/`summary`/`recognized_not_produced`,
endpoint `GET /api/vocabulary/lexicon`, pantalla `PersonalDictionary.tsx` con totales + barra CEFR + recall por
ítem + señal micro-drill "reconoce pero no produce", y tests `test_lexicon.py` + `test_vocabulary.py` ampliado),
y antes la **V2.2 ACADEMY/COURSE ENGINE** (métrica única "TOTAL VALIDATED LEARNING ITEMS" = 143,
plantilla fija de 7 secciones por unidad, Learning Objectives "By the end of this unit…", contrato
CEFR conectado al dominio ✓/●/○ por dimensión, Mastery Gates por unidad con umbrales compuestos,
tríada Progress/Mastery/Readiness con endpoint `/api/academy/dashboard`, pantalla Learning Journey
con marcador "YOU" + next milestone, y tests de regresión pedagógica `test_pedagogy.py`), y antes la
**V2.1 CONTENT** (Content Quality Gate con umbrales de calidad + reporte + guard de CI, corpus de
listening 40→100 ítems c041–c100, escenarios de speaking 8→20 A1–C1, niveles de curso C1/C2 y
assessments finales por nivel) y, anteriormente, la **Beta 1.0** `v2.0.0` (gates de salida 10/10 en
`docs/BETA_GATES.md`), la **gestión en-app de la biblioteca de audio humano** (V1.35), el **Audio Corpus 1.0** (V1.36),
el **Audio QA + Content Audit** (V1.37), el **Course Engine** (V1.38), el **Mastery 2.0** (V1.39),
el **Speaking 3.0** (V1.40), el **Beta Hardening** (V1.41) y la **Beta 1.0** (5 gates), además de
las **FASE 1–5** de la auditoría externa a V1.29 (LAN/HTTPS/audio móvil):
**V1.30** (LAN + Mobile 100%: mDNS real `local_url_available`, test de micrófono con medidor,
tarjeta de conexión QR, `/help/connect`), **V1.31** (Adaptive Engine 2.0: Priority Engine con
`priority_signals`/`priority_score`/`explain_priority` y "Why this activity?"), **V1.32**
(Curriculum 2.0: escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones y
`/api/academy/cefr-ladder`), **V1.33** (Listening 2.0: `listening_resilience` por condición de
escucha + `context` del corpus), **V1.34** (Speaking 2.0: `pronunciation` marcado como `proxy`,
`interaction_quality` por sub-dimensión y `conversation_endurance` con
`/api/academy/speaking/endurance`), **V1.35** (gestión en-app de la biblioteca de audio humano:
subir/reemplazar/quitar WAV desde Ajustes → Audio), **V1.36** (Audio Corpus 1.0: corpus de audio
humano versionado en `curriculum/listening_corpus.json` con 40 ítems A1–B2 + pipeline de grabación
`generate_recording_pack.py` + importación masiva `import_audio.py --batch` + higiene de release),
**V1.37** (Audio QA + Content Audit: QA acústica `PASS`/`WARNING`/`REJECT`, content integrity check
end-to-end, Content Audit Dashboard, candado admin/PIN local, backup/auditoría de borrado y límites
de tamaño/duración/MIME en la subida), **V1.38** (Course Engine: secuenciación
Course→Unit→Lesson→Practice→Assessment→Review→Mastery con gating por objetivo + progreso visible
"¿dónde estoy?" en `CourseScreen`), **V1.39** (Mastery 2.0: `MasteryRecord` transversal para las
9 destrezas + CEFR readiness con banda cualitativa "B1 developing" + curva de olvido/review_due
conectada a todo el currículo), **V1.40** (Speaking 3.0: catálogo de 8 escenarios comunicativos
con objetivo comunicativo y métricas declaradas + honestidad del proxy de pronunciación en la UI)
y **V1.41** (Beta Hardening: backup/restore/export local con auto-backup diario "keep 7", endpoints
admin con PIN, seguridad LAN origin-check + rate limiting, panel de backup en Ajustes → Sistema,
matriz de dispositivos ampliada, a11y skip-link + lang y code-splitting de vendors)
y **Beta 1.0** (5 gates de salida 10/10 en `docs/BETA_GATES.md`: Infra / Curriculum /
Listening+Speaking / Adaptive+Mastery / UX+Reliability).
Ver CHANGELOG.
Cerradas hasta ahora (histórico): Release Audit 1.1 (M12), M14–M16, Academy v2 + integridad
curricular, hardening, Evidence & Performance Engine, Listening 1.0/2.0/3.0, Placement 1.0/2.0,
Etapa 2 (pedagogía) **P1–P5**; **V1.12** → **V1.20**; **V1.21** (auditoría pedagógica A1→B2 + UI de
3 paneles), **V1.22** (Learning UX 2.0), **V1.23** (UI 2.0: Tailwind v4 + shadcn/ui + Motion),
**V1.24** (Analysis redesign + responsive 100% + tests visuales Playwright), **V1.25** (paneles del
chat redimensionables + persistentes), **V1.26** (UI 2.0 fases 3–6), **V1.27** (code-splitting),
**V1.28** (audio humano — código), **V1.29** (fiabilidad LAN/HTTPS + audio móvil P0 + launcher).
**Todo lo pendiente está consolidado en la sección 37** (próximos incrementos). Lee esa sección antes
de empezar el siguiente incremento.

**Últimos commits:**
- `feat: V1.30-V1.34 - FASE 1-5 auditoria externa (LAN/movil -> Speaking 2.0)` (`f876496`, HEAD)
- `feat: V1.29 - fiabilidad LAN/HTTPS + audio movil (P0) + launcher` (`cb4eec5`)
- `feat: V1.28 - listening: ocultar escalera de velocidad en items recorded`
- `feat: V1.27 - code-splitting por rutas (React.lazy/Suspense + AnalysisPanel diferido)`
- `feat: V1.26 - UI 2.0 fases 3-6 (listening/speaking/progress migrados + legacy.css podado)`
- `feat: UI 2.0 (V1.22-V1.25) — Learning UX, design system, Analysis por pestañas y paneles redimensionables`
- `feat: Learning Home (HOME como centro) con plan de hoy accionable`
- `docs: V1.21 higiene de release + documentacion (1.21.0)`
- `docs: briefings de agentes de la auditoria pedagogica A1-B2`
- `feat: UI de 3 paneles (destrezas + desarrollo + analisis + barra de estado)`
- `feat: validación determinista audio↔metadata`

> **V2.4 implementada y verificada** (auditoría de cobertura curricular; aún sin commitear). Árbol de
> trabajo limpio salvo los archivos de la V2.4. Ver sección 37.21 y `docs/CURRICULUM_COVERAGE.md`.

> **V1.35 implementada y verificada** (gestión en-app de audio humano; aún sin commitear). Árbol de
> trabajo limpio; solo queda pendiente 37.3 (incorporar WAV reales, ya desde la app) y 37.4 (Vercel,
> diferido).

**V1.15 commiteada** (S1 `2a182a8`, S2 `42602ca`, S3 `9be0f7f`) — Speaking 3.0. Ver sección 28.
Resumen:
- **Diagnóstico longitudinal** (`services/speaking.py::speaking_diagnostic`): agrupa la evidencia
  de speaking por criterio (attempts/mean/min/max/review_due), deriva `weak` + `recommendation` y
  expone `trend` global sobre las filas `overall` + `overall_mean`.
- **`interaction` como séptimo criterio** del rubric: extraído del LLM en el flujo libre, no
  observable en read-aloud.
- **Endpoint** `GET /api/academy/speaking/diagnostic` + puente de sub-destrezas de speaking en el
  Student Model (`_annotated_profile`).
- **Frontend**: `SpeakingDiagnostic.tsx` (desglose por criterio + tendencia + a revisar).
- **Higiene de release**: `config.py`/`package.json` → `1.15.0`; CHANGELOG con entrada 1.15.0.

**V1.16 commiteada** (`c9021e3` backend S1-S6 + assessment, `399ce52` interaction, `fbd91fc`
frontend, + `docs:` higiene 1.16.0) — Speaking Assessment & Evidence 2.0. Ver sección 29.
Resumen:
- **Scoring determinista S1–S6**: task_achievement continuo, GrammarEvidence 2.0, SpeakingTaskProfile
  (dificultad declared/realized/verified + pesos por task_type), LexicalEvidence 2.0 (MSTTR),
  FluencyEvidence 2.0 (WPM + smoothness/rhythm), InteractionEvidence 2.0 y diagnóstico por criterio
  como vista del Student Model (EMA/confidence/stability).
- **Speaking Assessment 1.0**: instrumento versionado (4 partes) + sesión trazable + endpoints
  `/api/academy/speaking/assessment/*`.
- **Interaction Evidence objetiva**: `services/interaction.py` + telemetría de turnos
  (`duration_ms`/`latency_ms`) + `GET /api/conversations/{id}/interaction`.
- **Speaking level + journey**: `GET /api/academy/speaking/level` y `/journey`.
- **Frontend**: `SpeakingPanel` (NEXT FOCUS + PRACTICE NOW) + `SpeakingJourney` (barra A2→B1→B2).
- **Higiene de release**: `config.py`/`package.json` → `1.16.0`; CHANGELOG con entrada 1.16.0.

**V1.17 commiteada** (`012ec01` UI, `e679300` puente, `34e32e6` Writing 3.0) — cierre de tres
incrementos naturales. Ver sección 30. Resumen:
- **UI del Speaking Assessment** (`components/SpeakingAssessment.tsx`): start → 4 partes →
  resultado, con micrófono y entrada manual (sin micrófono), sobre los endpoints ya existentes.
- **Puente conversación→speaking**: `duration_ms`/`latency_ms` en `ChatMessage`; captura de la
  telemetría del turno del alumno (`utils/telemetry.ts` + `useChat`) y envío de
  `conversation_id`/`message_id` en `/api/chat/stream`; `conversation_id` opcional en
  `submit_speaking_assessment_part`/`submit_speaking_task` inyecta
  `evidence["interaction_objective"]` (señal objetiva de turnos) en el scorer.
- **Writing 3.0**: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de speaking)
  + endpoints `/api/academy/writing/diagnostic|level|journey` + frontend `WritingPanel`/
  `WritingJourney`.
- **Higiene de release**: `config.py`/`package.json` → `1.17.0`; CHANGELOG con entrada 1.17.0.

**V1.18 commiteada** (`6071bca` retention, `2183849` dictado/shadowing, `26ae6c4` variantes) —
P1 de listening de la auditoría V1.14. Ver sección 31. Resumen:
- **Delayed retention (P1.2)**: `delayed_retention` (inmediata vs. retardada, buckets
  0-2/2-7/7-30/30+ días) integrado en `listening_diagnostic` (clave `retention`) + frontend.
- **Dictado y shadowing reales (P1.3/P1.4)**: sub-destrezas `dictation`/`shadowing` servidas como
  tareas de producción (escribir/grablar) con scoring determinista vía `phonetics.composite_score`;
  columnas `task_type`/`score`, `mean_score` en el diagnóstico y endpoints
  `/api/listening/dictation|shadowing`.
- **Escalera de variantes (P1.9)**: `slow`/`normal`/`fast` con cache por variante y botones en el
  frontend (solo velocidad; acento/ruido quedan como límite de contenido).
- **Higiene de release**: `config.py`/`package.json` → `1.18.0`; CHANGELOG con entrada 1.18.0.

**V1.19 commiteada** (`feat:` UI + `docs:` higiene 1.19.0) — Refresco UI profesional (frontend).
Ver sección 32. Resumen:
- **Primitivas CSS** (`.card`, `.badge`, `.pill`, `.section-divider`) y tokens `--color-surface-3`/
  `--shadow-card`; escala tipográfica por defecto afinada.
- **`InsightCard`** colapsable (aria-expanded/aria-controls) envolviendo los 11 paneles del
  análisis; expandidos por defecto `ProgressDashboard`, `TodayPlan` y `ListeningPractice`.
- **Header** sticky con `backdrop-filter: blur()` + fondo translúcido y menú secundario a ≤768px.
- **Chat** con avatar circular del tutor y estado vacío más rico.
- **Responsive ≤480px** (header compacto, composer y drawer de análisis) sin romper 768/1024.
- **Higiene de release**: `config.py`/`package.json` → `1.19.0`; CHANGELOG con entrada 1.19.0.

**V1.20 commiteada** (P6 fonémica, turn-taking real y audio humano) — cierre de los tres pendientes
de V1.19. Ver sección 33. Resumen:
- **Pronunciación fonémica (P6)**: `phoneme_alignment`/`syllables`/`prosody_score` en
  `services/phonemes.py`; `composite_score` rebalanceado (`word 0.35 / phoneme 0.35 / phonetic
  0.15 / prosody 0.15`) y expone `prosody_score` + `phoneme_breakdown`; rubric de pronunciación
  con 4 criterios (añade `prosody`) y UI con "Precisión de fonemas"/"Prosodia (ritmo)".
- **Turn-taking real → Interaction**: `components/SpeakingRolePlay.tsx` (role-play en vivo con
  telemetría de turnos) + bifurcación por `task_type` conversacional y envío de `conversation_id`
  en `submitSpeakingAssessmentPart` para inyectar `interaction_objective`.
- **Biblioteca de audio humano (P1.5–P1.8)**: `services/audio_library.py` + manifest versionado
  (`backend/audio_library/manifest.json`) + servido de grabaciones sin Piper (`get_audio` 404 si
  falta el WAV; `audio_ready` ya no depende solo de Piper).
- **Higiene de release**: `config.py`/`package.json` → `1.20.0`; CHANGELOG con entrada 1.20.0.

**Estado verde:** backend `843 tests` + `ruff` limpio; frontend `234 tests` + `tsc` OK + `build`
OK; launcher `64 tests` + `ruff` limpio; Playwright `14 passed + 10 skipped`.

**Acciones del nuevo gerente (en orden):**
1. Leer `docs/PREMISAS.md` (fuente de verdad de reglas).
2. Leer la **sección 37** de este documento (consolidado de próximos incrementos).
3. Elegir el siguiente incremento y ejecutarlo con subagentes autocontenidos (`agentes/*.md`).
   Quedan pendientes: **37.3 contenido** (WAV reales, del usuario; código listo), **37.4 Vercel**
   (diferido por decisión) y el **commit `feat:` de cierre de V1.30–V1.34** (FASE 1–5, en árbol).
   Si la auditoría define **FASE 6 (Beta)**, añadirla aquí como 37.6 antes de empezar.
4. Verificar en verde antes de cada commit `feat:` (backend `pytest` + `ruff`, frontend
   `tsc` + `vitest` + `build`, launcher `pytest` + `ruff`, Playwright `npm run test:visual`).

## 1. Qué es el proyecto

Profesor de inglés **100% local** (sin Internet, sin cuentas, sin costes). Conversa por
texto y voz con un LLM local (Ollama), con modos de tutor y corrección de pronunciación.

- **Fuente de verdad de reglas:** `docs/PREMISAS.md` (14 premisas). Léelas primero.
- **Arquitectura:** `docs/ARQUITECTURA.md` (estructura modular y responsabilidades).
- **Guía de desarrollo:** `docs/DESARROLLO.md` (arranque, flujo con subagentes, Git/GitHub).
- **Roadmap y estado:** `PLAN.md`.

## 2. Stack (fijado, premisa 3-4)

- Backend: Python + FastAPI + Pydantic (tipado fuerte).
- Frontend: Vite + React + TypeScript (modo estricto).
- LLM: Ollama (local). Modelo inicial `qwen3.5:9b`.
- Voz: `faster-whisper` (STT, CPU) y `piper-tts` (TTS, CPU).
- Persistencia: SQLite (`backend/data/tutor.db`).

## 3. Estado actual (qué funciona)

Hecho y verificado (tests verdes):

- **M0** esqueleto modular · **M1** streaming (SSE) · **M2** voz local · **M3** memoria/historial.
- **M4** modo profesor: 4 modos de tutor (`conversation`, `grammar`, `exercises`, `pronunciation`)
  + corrección de pronunciación (`POST /api/pronunciation`).
- **M5** modelo conversacional: evaluado `llama3.1:8b` vs `qwen3.5:9b`; se mantiene
  `qwen3.5:9b` (mejor calidad de tutor). `llama3.1:8b` queda instalado como alternativa.
- **M6** release a GitHub.
- **M7** multi-usuario: tabla `users` + columna `user_id` en `conversations` (migración
  idempotente, usuario por defecto `Usuario`), `GET/POST /api/users`, CRUD de conversaciones
  filtrado por `user_id`, selector de perfil en frontend con aislamiento al cambiar.
- **M8** diseño y UX: tokens en `index.css`, tema claro/oscuro (`useTheme`, `ThemeToggle`,
  anti-FOUC), responsive (drawer + hamburguesa ≤768px), a11y y micro-interacciones.
- **M9** seguimiento de progreso: `GET /api/progress?user_id=<id>` (`ProgressSummary`:
  conversaciones, mensajes, ejercicios, correcciones, pronunciación) + `POST /api/pronunciation`
  con `user_id` opcional para persistir intentos (`pronunciation_attempts` + columna `mode`).
  Frontend: panel colapsable `ProgressSummary` + `api/progress.ts`.
- **M10** voz continua / manos libres: modo conversación por voz sin pulsar botones. VAD en
  cliente (RMS + silencio ≥1.2s vía Web Audio API), bucle escuchar → transcribir → responder →
  leer en voz alta → volver a escuchar. Frontend: `useChat.sendText`, `utils/vad.ts`,
  `hooks/useHandsFree.ts`, `components/HandsFreeToggle.tsx`. Sin cambios de backend.
- Tests: backend `pytest tests/ -q` (27 tests), frontend `npm test` (vitest, 37 tests) + `tsc --noEmit`.

## 4. GitHub

- Repo **público**: https://github.com/jvelasca/english-tutor
- Rama por defecto: `main`. Última versión estable: tag `v1.5.2` (release publicado).
- Issues de seguimiento:
  - #1 M5 modelo conversacional
  - #2 Seguimiento de progreso del alumno
  - #3 Conversación por voz continua
  - #4 M7 multi-usuario
  - #5 M8 diseño y UX nivel top

## 5. HECHO — M5: modelo conversacional (se mantiene qwen3.5:9b)

**Tarea:** evaluar `llama3.1:8b` como reemplazo de `qwen3.5:9b` para el rol de tutor.

- Script: `backend/scripts/eval_model.py` (`--model <m>` envía 4 prompts de tutor).
- Briefing: `agentes/m5-modelo-conversacional.md`.
- **Descarga:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min. Al
  **quitar la VPN** (2026-08-24) la descarga terminó en ~1 min a 52 MB/s y sin error de
  certificado (el MITM de DigiMobil ya no afectaba a esa conexión). `llama3.1:8b` instalado.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. `qwen3.5:9b` gana en
  calidad como tutor (correcciones estructuradas, ejercicios con contexto, guía IPA de
  pronunciación detallada y correcta). `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde /θ/ con /ð/), así que **no es claramente
  mejor**. Queda instalado como alternativa selectable en el frontend.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

## 6. HECHO — M7: multi-usuario

**Implementado y verificado** (backend 20 tests, frontend 14 tests, `tsc` sin errores).

- Backend: `services/store.py` ahora gestiona `users` y `conversations` con `user_id`
  (migración idempotente; usuario por defecto `Usuario` y reasignación de huérfanas).
  `routers/users.py` (`GET/POST /api/users`), `routers/conversations.py` filtra por `user_id`
  (query param). `schemas/users.py` (`User`, `UserCreate`).
- Frontend: `api/users.ts`, `components/UserSelect.tsx`, `utils/users.ts` (`nextDefaultUserName`),
  hook `useChat.ts` con estado de usuario y aislamiento al cambiar de perfil.
- Briefings: `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

## 7. HECHO — M8: diseño y UX nivel top

**Implementado y verificado** (frontend 19 tests, `tsc` sin errores, `npm run build` OK).

- Tokens de diseño en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion), tema claro en `:root[data-theme="light"]`.
- Tema claro/oscuro: `hooks/useTheme.ts` + `utils/theme.ts` (`resolveInitialTheme`) +
  `components/ThemeToggle.tsx`; persistencia en `localStorage` y anti-FOUC en `index.html`.
- Responsive ≤768px: sidebar drawer + hamburguesa + backdrop. a11y: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Briefing: `agentes/m8-diseno-ux.md`.

## 7b. HECHO — M9: seguimiento de progreso del alumno

**Implementado y verificado** (backend 27 tests, frontend 26 tests, `tsc` sin errores,
`npm run build` OK).

- Backend: `schemas/progress.py` (`PronunciationStats`, `ProgressSummary`),
  `routers/progress.py` (`GET /api/progress?user_id=<id>` con 404 si no existe el usuario),
  `services/store.py` (tabla `pronunciation_attempts`, columna `mode` en `messages` con
  migración idempotente, `record_pronunciation`, `get_progress`), `routers/pronunciation.py`
  (`user_id: str = Form(None)` persistente), `ChatMessage.mode: str | None = None`.
- Frontend: `api/progress.ts`, `components/ProgressSummary.tsx` (panel colapsable con 4
  stats + sección de pronunciación y estados vacíos), `utils/progress.ts`
  (`formatScore`/`formatAverage`/`pronunciationLevelLabel`, tolerantes a `null`),
  `types/api.ts` (`PronunciationStats`/`ProgressSummary` con campos anulables),
  `hooks/useChat.ts` (estado `progress` + `refreshProgress`, `mode` adjuntado a los mensajes),
  `PronunciationPractice.tsx` (pasa `user_id` y refresca), `App.tsx` (renderiza el panel).
- Nota de tipado: los campos `best`/`average`/`last_score`/`last_level` son `null` si no hay
  intentos (reflejado en frontend como anulables).
- Briefings: `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

## 7c. HECHO — M10: conversación por voz continua (manos libres)

**Implementado y verificado** (frontend 37 tests, `tsc` sin errores, `npm run build` OK;
backend intacto, `import main` OK).

- **Sin cambios de backend:** reutiliza `POST /api/transcribe`, `POST /api/tts` y
  `POST /api/chat/stream` ya existentes.
- Frontend: `hooks/useChat.ts` extrae y exporta `sendText(text): Promise<string>` (el `send`
  actual se apoya en él). `utils/vad.ts` (`rms`, `shouldEndUtterance`, constantes
  `SILENCE_THRESHOLD=0.02`, `SILENCE_MS=1200`, `MIN_SPEECH_MS=300`, `MAX_CHUNK_MS=15000`).
  `hooks/useHandsFree.ts` (un `MediaStream` persistente, `AnalyserNode` para energía,
  `MediaRecorder` por chunk; estados `idle/listening/transcribing/thinking/speaking`).
  `components/HandsFreeToggle.tsx` (toggle accesible + indicador de estado con `role="status"`).
  `App.tsx` lo conecta en `header-controls`. Estilos en `index.css` (tokens, tema claro/oscuro).
- **VAD:** muestreo cada 50 ms con `getByteTimeDomainData`; si `rms > 0.02` marca habla; al
  llegar silencio ≥1.2 s tras habla (y duración ≥0.3 s para descartar clics) cierra el chunk;
  tope de seguridad 15 s. Sin barge-in (fuera de alcance en esta iteración).
- **Limitaciones conocidas:** autoplay (el `AudioContext`/mic se lanzan dentro del clic),
  umbral fijo (podría calibrarse), sin interrupción de la voz del asistente.
- Briefing: `agentes/m10-voz-continua.md`.

## 8. Notas de diseño de M7 (para no romper en M8)

- Contrato de la API (no cambiar sin coordinar frontend):
  - `GET /api/users` → `User[]`; `POST /api/users` con `{ name }` → `User`.
  - `GET /api/conversations?user_id=<id>` y `POST /api/conversations?user_id=<id>`.
  - `ConversationMeta` incluye `user_id`.
- El usuario por defecto se llama `Usuario`; el frontend genera nombres sin colisión con
  `nextDefaultUserName` (`Usuario`, `Usuario 2`, ...).

## 8. Cómo arrancar y verificar desde cero

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests/ -q

# Frontend
cd frontend
npm install
npm test            # vitest
npx tsc --noEmit    # tipos

# Arranque integrado: F5 en Cursor (configuración "English Tutor (F5)")
#   backend :8000 + frontend :5173
```

## 9. Reglas de oro para continuar (premisas clave)

- **Todo se descompone en subagentes autocontenidos** en `agentes/<nombre>.md` (premisa 5).
- **Antes de alucinar, reiniciar el contexto** apoyándose en `docs/` (premisa 12).
- **Documentación VITAL:** todo cambio actualiza `docs/`, `PLAN.md`, `README.md` (premisa 8).
- **Tests obligatorios:** ninguna feature se da por acabada sin sus tests (premisa 12).
- **Ritmo:** hito a hito, un cambio a la vez (premisa 6).

## 10. Fase de endurecimiento (FASES 1, 2 Y 3 CERRADAS — post v1.0.0)

**Motivo:** auditoría interna + externa. La app es un MVP/RC arquitectónico; NO rehacer, pero
sí endurecer antes de seguir con features. Hallazgo crítico: **el aislamiento multiusuario
(M7) no está realmente garantizado** — el CRUD de conversaciones por `cid` no comprueba el
propietario, y `/api/pronunciation` no valida el usuario. M7 no debe considerarse "terminado".

- Plan completo y secuencia de subagentes: `docs/PLAN-ENDURECIMIENTO.md`.
- Prioridades: P0 aislamiento · P1 robustez · P2 Learning Profile · P3 pronunciación real.
- Briefings en `agentes/endurecimiento/` (uno por subagente, autocontenidos).

### Estado de subagentes (FASE 1 · P0) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E1.1 Store ownership + routers | `agentes/endurecimiento/e1-01-store-ownership.md` | ✔ hecho |
| E1.2 Frontend propagar user_id | `agentes/endurecimiento/e1-02-frontend-userid.md` | ✔ hecho |
| E1.3 LocalUserContext + tests seguridad API | `agentes/endurecimiento/e1-03-context-security-tests.md` | ✔ hecho |
| E1.4 Contratos y límites | `agentes/endurecimiento/e1-04-contratos-limites.md` | ✔ hecho |
| E1.5 Límites de audio + sanitización de errores | `agentes/endurecimiento/e1-05-audio-errores.md` | ✔ hecho |

> **Fase 1 (P0) cerrada.** Aislamiento multiusuario extremo a extremo, `system` fuera del
> input externo, límites de payload (chat/messages/TTS/audio) y sanitización de errores.
> **Fase 2 (P1) cerrada** (store no bloqueante, health real, chat integrable, CI + deps + CORS).
> **Fase 3 (persistencia y dominio) cerrada** (mensajes append-only, capa de dominio, FKs reales).
> **Fase 4 (Learning Profile) cerrada** (ver sección 11).
> **Fase 5 (Tutor Policy + Context Builder) cerrada** (ver sección 12).
> Siguiente bloque: **FASE 6 (Progreso pedagógico real)** — ver
> `docs/PLAN-ENDURECIMIENTO.md`.

### HECHO — E1.1: aislamiento real en store y routers

- `services/store.py`: `get_conversation(cid, user_id)`, `save_conversation(cid, user_id, …)`,
  `delete_conversation(cid, user_id)` con `AND user_id = ?`; `record_pronunciation(...) -> bool`
  (valida usuario); índices `idx_conversations_user_id` y `idx_pronunciation_user_id`.
- `routers/conversations.py` y `routers/pronunciation.py`: exigen/validan `user_id`.
- Tests: `test_store_isolation.py` (5 tests nuevos); total backend **32 tests verdes**.
- **ATENCIÓN:** el contrato de la API cambió (GET/PUT/DELETE y pronunciación ahora exigen
  `user_id`). El frontend queda temporalmente roto para cargar/guardar/borrar conversaciones
  hasta cerrar E1.2 (siguiente subagente).

### HECHO — E1.2: frontend propaga user_id (cierra el par de contrato)

- `api/conversations.ts`: `getConversation(id, userId)`, `saveConversation(id, userId, …)`,
  `deleteConversation(id, userId)` con `user_id` en la query vía `URLSearchParams`.
- `api/pronunciation.ts`: `checkPronunciation(blob, expected, userId)` con `userId` obligatorio.
- `hooks/useChat.ts`: `loadConversation`/`removeConversation`/`persist` pasan `currentUserId`
  con guard `if (!currentUserId) return;` y deps actualizadas.
- `components/PronunciationPractice.tsx`: guard `!userId` + `disabled={processing || !userId}`.
- Test nuevo `api/conversations.test.ts` (3 tests, mock de fetch). Frontend: **40 tests verdes**,
  `tsc` sin errores, `npm run build` OK.
- **Contrato cerrado:** la app queda funcional de nuevo y con aislamiento extremo a extremo
  (backend exige `user_id`, frontend lo envía).

### HECHO — E1.3: LocalUserContext + tests canónicos de seguridad API

- `dependencies.py`: dependencia `current_user(user_id: str = Query(...))` que resuelve y
  valida el perfil activo (`store.get_user`), `404` si no existe.
- `routers/conversations.py` y `routers/progress.py`: `get_one`/`save`/`delete`/`progress`
  usan `Depends(current_user)` (DRY) en lugar de recibir `user_id` crudo.
- Tests: `tests/test_api_security.py` (aislamiento por API: no leer/actualizar/borrar la
  conversación de otro usuario, pronunciación con usuario desconocido → 404). Total backend
  **38 tests verdes**.

### HECHO — E1.4: contratos (quitar `system`) y límites de payload

- `schemas/chat.py`: `Role = Literal["user", "assistant"]` (fuera `system`); `content`
  con `max_length=MAX_CONTENT_CHARS`; `messages` con `max_length=MAX_CHAT_MESSAGES`.
- `schemas/voz.py`: `TTSRequest.text` con `max_length=MAX_TTS_CHARS`.
- `config.py`: constantes `MAX_CHAT_MESSAGES=100`, `MAX_CONTENT_CHARS=8000`, `MAX_TTS_CHARS=4000`.
- Tests: `tests/test_schemas.py` (rechaza `system`, rechaza content/messages/TTS fuera de
  límite). Total backend **43 tests verdes**.

### HECHO — E1.5: límites de subida de audio + sanitización de errores

- `config.py`: `MAX_AUDIO_BYTES = 25 * 1024 * 1024` (25 MB).
- `dependencies.py`: `read_audio_limited(file) -> bytes` (415 si el content-type no es audio,
  413 si excede `MAX_AUDIO_BYTES`, lectura por chunks de 1 MB).
- `routers/voz.py`: `/api/transcribe` usa `read_audio_limited`; errores de transcribir/TTS
  sanitizados (`logger.exception` + `500` genérico).
- `routers/pronunciation.py`: usa `read_audio_limited`; error de transcripción sanitizado.
- `routers/chat.py`: `/api/chat` → `502` "No se pudo completar la respuesta"; `/api/chat/stream`
  emite `{"error": "..."}` sin filtrar `exc`.
- `routers/models.py`: `/api/models` → `502` "No se pudo contactar con Ollama".
- Tests: `tests/test_robustness.py` (413, 415, models/chat no filtran `exc`). Total backend
  **47 tests verdes**.

### Estado de subagentes (FASE 2 · P1) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E2.1 Store no bloqueante (threadpool) | `agentes/endurecimiento/e2-01-store-no-bloqueante.md` | ✔ hecho |
| E2.2 Health real (live/ready/dependencies) | `agentes/endurecimiento/e2-02-health-real.md` | ✔ hecho |
| E2.3 Chat integrable + tests Ollama mockeado | `agentes/endurecimiento/e2-03-chat-integrable.md` | ✔ hecho |
| E2.4 CI + deps + CORS | `agentes/endurecimiento/e2-04-ci-deps-cors.md` | ✔ hecho |

### HECHO — E2.4: CI + dependencias reproducibles + CORS

- CORS: `config.py` `ALLOWED_ORIGINS` (solo `localhost:5173`/`127.0.0.1:5173`); `main.py` la usa
  (antes `["*"]`). Test `tests/test_cors.py` (3 tests).
- Deps: `requirements.in` (intención) + `requirements.txt` y `requirements-dev.txt` pineados
  (versiones exactas verificadas) + `ruff` en dev.
- Ruff determinista: `pyproject.toml` (`select E,F,W,I,B`, `ignore B008`, `line-length 88`).
  Se arreglaron issues preexistentes (F401/I001/E501/B904) con cambios mecánicos sin alterar
  comportamiento (reenvuelto de líneas y `raise ... from None`).
- CI: `.github/workflows/ci.yml` (backend: ruff + pytest; frontend: tsc + vitest + build).
- Total backend **62 tests verdes**; frontend **40 tests** + tsc + build OK; `ruff` limpio.

### HECHO — E2.3: chat integrable (DI del cliente Ollama) + tests

- `services/llm.py`: cliente Ollama inyectable (`_client`, `get_client()`, `set_client()`);
  `chat_once`, `chat_stream`, `list_models`, `ping` usan `get_client()` en vez de instanciar
  `ollama.AsyncClient()`. Firmas y comportamiento público sin cambios.
- Tests: `tests/test_chat_integration.py` (7 tests con `FakeOllamaClient`): system prompt +
  modo correcto, fallback a conversación con modo desconocido, stream OK, role inválido 422,
  mensajes vacíos 422, Ollama caído 502 sin fuga, error en stream → evento `error` sin fuga.
  Total backend **59 tests verdes**.

### HECHO — E2.2: health real (live / ready / dependencies)

- `services/store.py` (`ping()`), `services/llm.py` (`ping()` async), `services/stt.py`
  (`is_ready()`), `services/tts.py` (`is_ready()`): checks de cada dependencia.
- `routers/health.py` (nuevo): `/api/health` (compat), `/api/health/live`,
  `/api/health/dependencies` (estado por dependencia), `/api/health/ready` (200/503).
- `routers/models.py`: eliminado el `/api/health` estático. `main.py`: registra `health_router`.
- Tests: `tests/test_health.py` +4 (live, dependencies ok, ready 200, ready 503 con Ollama
  caído, todo con monkeypatch). Total backend **52 tests verdes**.

### HECHO — E2.1: store no bloqueante (threadpool)

- `services/store_async.py` (nuevo): 11 envolturas `async` que delegan en `store` vía
  `starlette.concurrency.run_in_threadpool` (referencias resueltas en runtime → compatible con
  `monkeypatch`). `store.py` síncrono queda **intacto**.
- `dependencies.py`: `current_user` pasa a corrutina (`await store_async.get_user`).
- `routers/users.py`, `conversations.py`, `progress.py`, `pronunciation.py`: usan `store_async`
  (`await`). Firmas y contratos (200/404) sin cambios; `create`/`list_all` conservan `user_id: str`.
- Tests: `tests/test_store_async.py` (delega igual que el store síncrono). Total backend
  **48 tests verdes**.

**Línea base (pre-fase):** backend `27 tests` verdes, `import main` OK. Entorno de este
workspace: Python 3.13.7 (global), dependencias de runtime ya instaladas
(`ollama`, `faster-whisper`, `piper-tts`, `python-multipart`).

### Estado de subagentes (FASE 3 · persistencia y dominio) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E3.1 Mensajes append-only (backend) | `agentes/endurecimiento/e3-01-mensajes-append-only.md` | ✔ hecho |
| E3.2 Mensajes con id (frontend) | `agentes/endurecimiento/e3-02-mensajes-id-frontend.md` | ✔ hecho |
| E3.3 Capa de dominio (Service → Repository) | `agentes/endurecimiento/e3-03-capa-dominio.md` | ✔ hecho |
| E3.4 FK reales | `agentes/endurecimiento/e3-04-fk-reales.md` | ✔ hecho |

### HECHO — E3.1: mensajes append-only (backend)

- `schemas/chat.py`: `ChatMessage.id: str | None = None` (opcional, no rompe `/api/chat`).
- `repositories/db.py` (antes `services/store.py`): columna `message_id` + índice único
  `(conversation_id, message_id)`; `get_conversation` devuelve `id` (= `message_id`);
  `save_conversation` append-only (`INSERT OR IGNORE`) cuando todos los mensajes traen `id`,
  y fallback legacy (replace-all) si no.
- Test `tests/test_store_append_only.py` (3 tests). Total backend **65 tests verdes**.

### HECHO — E3.2: mensajes con id estable (frontend)

- `types/api.ts`: `Message.id?: string`.
- `hooks/useChat.ts`: `id` (`crypto.randomUUID()`) en mensaje de usuario y en el de asistente
  (un único `assistantId` por envío, reutilizado en `onDelta` y `persist`); las ramas de error
  usan su propio id. `App.tsx`: `key={m.id ?? ...}`.
- Frontend: **40 tests verdes**, `npm run build` OK. El backend ya recibe todos los mensajes
  con `id` → persistencia append-only activa.

### HECHO — E3.3: capa de dominio (Router → Service → Repository)

- **Refactor puro, sin cambio de comportamiento** (65 tests verdes).
- Nuevo `repositories/` (acceso a datos puro): `db.py` (conexión/esquema/migraciones/ping),
  `users.py`, `conversations.py`, `pronunciation.py`.
- Nuevo `domain/` (servicios async vía `run_in_threadpool`): `users.py`, `conversations.py`,
  `pronunciation.py`.
- Recableados `routers/{users,conversations,progress,pronunciation,health}.py`, `dependencies.py`
  y `main.py` para depender de `domain/` y `repositories.db`.
- Eliminados `services/store.py` y `services/store_async.py` (sustituidos).
- Tests re-apuntados (cambio mecánico de imports); `test_store_async.py` → `test_domain_async.py`.

### HECHO — E3.4: FKs reales (user_id → users.id)

- `repositories/db.py`: `_conn(foreign_keys=True)`; en `init_db` se añade una **fase 2** que
  reconstruye `conversations` y `pronunciation_attempts` (idempotente, con `foreign_keys OFF`)
  para añadir `FOREIGN KEY user_id → users(id)`. Sentencias `CREATE TABLE IF NOT EXISTS`
  intactas.
- Test `tests/test_foreign_keys.py` (6 tests: presencia de FK, enforcement con `IntegrityError`,
  idempotencia, migración desde esquema legacy). Total backend **71 tests verdes**.

**Estado global al cierre de Fase 3:** backend `71 tests` + `ruff` limpio + `import main` OK;
frontend `40 tests` + `tsc`/`build` OK. Arquitectura ahora `Router → Service (domain) →
Repository (repositories) → SQLite`, con mensajes append-only y FKs reales. Siguiente bloque:
**FASE 4 — Learning Profile** (CEFR, gramática, vocabulario, errores recurrentes, eventos).

## 11. FASE 4 — Learning Profile (CERRADA ✔)

Backend primero (F4.1–F4.4), frontend al final (F4.5). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear.

| Subagente | Briefing | Estado |
|---|---|---|
| F4.1 Eventos de aprendizaje | `agentes/endurecimiento/f4-01-eventos-aprendizaje.md` | ✔ hecho |
| F4.2 Vocabulario | `agentes/endurecimiento/f4-02-vocabulario.md` | ✔ hecho |
| F4.3 Errores gramaticales recurrentes | `agentes/endurecimiento/f4-03-gramatica.md` | ✔ hecho |
| F4.4 CEFR + recomendaciones | `agentes/endurecimiento/f4-04-cefr-perfil.md` | ✔ hecho |
| F4.5 Frontend Learning Profile | `agentes/endurecimiento/f4-05-frontend-perfil.md` | ✔ hecho |

### HECHO — F4.1: eventos de aprendizaje
- `schemas/learning.py` (`LearningEventType`, `LearningEvent`, `LearningEventCreate`),
  `repositories/learning.py` (`record_event`, `list_events`), `domain/learning.py`,
  `routers/learning.py` (`POST/GET /api/learning/events`).
- `repositories/db.py`: tabla `learning_events` con FK inline + índice. Total backend **79 tests**.

### HECHO — F4.2: vocabulario
- `services/vocabulary.py` (`EN_STOPWORDS`, `extract_words` puro), `repositories/vocabulary.py`
  (`record_words` upsert, `get_vocabulary`), `domain/vocabulary.py`, `schemas/vocabulary.py`,
  `routers/vocabulary.py` (`POST /api/vocabulary/analyze`, `GET /api/vocabulary`).
- `repositories/db.py`: tabla `vocabulary` (`UNIQUE(user_id, word)` + FK). Total **89 tests**.

### HECHO — F4.3: errores gramaticales recurrentes
- `services/grammar.py` (7 reglas regex deterministas + `find_errors`), `repositories/grammar.py`
  (`record_errors` upsert, `get_recurring_errors`), `domain/grammar.py`, `schemas/grammar.py`,
  `routers/grammar.py` (`POST /api/grammar/analyze`, `GET /api/grammar/errors`).
- `repositories/db.py`: tabla `grammar_errors` (`UNIQUE(user_id, rule)` + FK). Total **102 tests**.

### HECHO — F4.4: CEFR + recomendaciones
- `services/cefr.py` (`CEFR_LEVELS`, `estimate_cefr`, `recommendations` puras),
  `repositories/profile.py` (`get_profile`, `set_cefr`), `domain/profile.py` (compone
  vocabulario + errores + pronunciación + CEFR), `schemas/profile.py`, `routers/profile.py`
  (`GET /api/profile`).
- `repositories/db.py`: tabla `learning_profile` (PK `user_id` + FK). Total **114 tests**.
- Nota: se simplificó el plan (`GET /api/profile` recalcula la estimación en cada consulta;
  no se creó `POST /api/profile/assess` por ser redundante).

### HECHO — F4.5: frontend Learning Profile
- `types/api.ts` (`CefrLevel`, `GrammarRecurringError`, `LearningProfile`),
  `api/learning.ts` (`getProfile`, `analyzeText`), `utils/cefr.ts` (`cefrTone`, `cefrLabel`),
  `components/LearningProfile.tsx` (badge CEFR + vocabulario + errores + recomendaciones).
- `hooks/useChat.ts`: estado `profile` + `refreshProfile` (aislamiento al cambiar de usuario) y
  `analyzeText(trimmed, currentUserId)` tras cada envío del alumno. `App.tsx` renderiza el panel.
- `index.css`: sección `.learning-profile` con tokens + responsive. Total frontend **48 tests**.

**Estado global al cierre de Fase 4:** backend `114 tests` + `ruff` limpio + `import main` OK;
frontend `48 tests` + `tsc`/`build` OK. La tabla `learning_events` queda lista pero aún sin
consumidor de UI (se cableará en Fase 5/6). Siguiente bloque: **FASE 5 — Tutor Policy +
Context Builder** (el perfil del alumno entra al prompt del tutor).

## 12. FASE 5 — Tutor Policy + Context Builder (CERRADA ✔)

Backend primero (F5.1–F5.2), frontend al final (F5.3). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear.

| Subagente | Briefing | Estado |
|---|---|---|
| F5.1 Tutor Policy (correctness policy) | `agentes/endurecimiento/f5-01-politica-correccion.md` | ✔ hecho |
| F5.2 Context Builder + perfil al prompt | `agentes/endurecimiento/f5-02-context-builder.md` | ✔ hecho |
| F5.3 Frontend propagar user_id al chat | `agentes/endurecimiento/f5-03-frontend-user-id.md` | ✔ hecho |

### HECHO — F5.1: política de corrección (correctness policy)
- `services/policy.py` (`CORRECTNESS_GUIDANCE` por nivel CEFR + `correctness_guidance(cefr_level)`,
  pura y determinista, sin LLM). Tests `test_policy.py` (4). Total backend **118 tests**.

### HECHO — F5.2: Context Builder + perfil al prompt
- `services/context.py` (`build_system_prompt(mode, profile)`: prompt base + política por CEFR +
  errores recurrentes + áreas de enfoque).
- `schemas/chat.py`: `ChatRequest.user_id: str | None = None` (opcional → sin ventana rota).
- `services/llm.py`: `_messages`/`chat_once`/`chat_stream` aceptan `system_prompt` inyectable.
- `domain/profile.py`: extrae `_compute_profile` y añade `get_profile_context` (lectura sin
  persistir CEFR; `get_profile_summary` intacto y con mismo comportamiento).
- `routers/chat.py`: `_system_prompt(req)` resuelve el perfil vía `get_profile_context` y pasa el
  prompt a `chat_once`/`chat_stream`. Sin `user_id` (o usuario inexistente) → prompt base.
- Tests `test_context.py` (6) + `test_chat_profile.py` (4). Total backend **128 tests**.

### HECHO — F5.3: frontend propaga user_id al chat
- `api/chat.ts`: `sendChat`/`streamChat` envían `user_id` (`null` si no hay usuario).
- `hooks/useChat.ts`: `sendText` pasa `currentUserId` a `streamChat`.
- Test `api/chat.test.ts` (3). Total frontend **51 tests**.

**Estado global al cierre de Fase 5:** backend `128 tests` + `ruff` limpio + `import main` OK;
frontend `51 tests` + `tsc`/`build` OK. El perfil del alumno (CEFR + errores recurrentes +
recomendaciones) ya entra al system prompt del tutor; sin `user_id` el chat queda como antes.
Siguiente bloque: **FASE 6 — Progreso pedagógico real** (no solo counts).

## 13. FASE 6 — Progreso pedagógico real (CERRADA)

Backend primero (F6.1–F6.2), frontend al final (F6.3). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear. Decisiones de diseño: un único endpoint nuevo
(`GET /api/progress/history`), análisis **determinista sin LLM** (premisa 12), y el frontend
**reemplaza** `ProgressSummary` por un dashboard de progreso real (responsive móvil/tablet).

| Subagente | Briefing | Estado |
|---|---|---|
| F6.1 Registro automático de eventos | `agentes/endurecimiento/f6-01-registro-eventos.md` | ✔ hecho |
| F6.2 Progreso histórico (tendencias, racha, dominio, hitos) | `agentes/endurecimiento/f6-02-progreso-historico.md` | ✔ hecho |
| F6.3 Frontend dashboard de progreso | `agentes/endurecimiento/f6-03-frontend-dashboard.md` | ✔ hecho |

### HECHO — F6.1: registro automático de eventos de aprendizaje
- `domain/learning.py`: `_MODE_TO_EVENT` (`exercises→exercise`, `grammar→correction`, resto→
  `message`) + `record_chat_activity(user_id, mode, detail)` async.
- `routers/chat.py`: `_record_activity(req)` (solo si hay `user_id`; detail = último mensaje
  truncado a 200) llamada en `chat` y `chat_stream_endpoint` tras `_system_prompt`. Sin `user_id`
  o usuario inexistente → no registra y el chat sigue con prompt base (sin ventana rota).
- `routers/pronunciation.py`: registra evento `pronunciation` (detail = `expected`).
- `routers/conversations.py`: registra evento `conversation` (detail = `conv["id"]`).
- Tests: `tests/test_activity.py` (8 tests). Total backend **136 tests**.
- La tabla `learning_events` deja de estar dormida: ahora la alimentan los endpoints reales.
  La consumirán F6.2 (backend) y F6.3 (UI).

### HECHO — F6.2: progreso histórico real (tendencias, racha, dominio, hitos)
- Nuevo endpoint `GET /api/progress/history?user_id=<id>&bucket=day|week|month` (default `week`)
  con `ProgressHistory` = `series` + `streak` + `mastery` + `milestones`. Sin romper
  `/api/progress` ni `/api/profile`.
- `schemas/progress.py`: `Bucket`, `SeriesPoint`, `Streak`, `ErrorMastery`, `Milestone`,
  `ProgressHistory`.
- `services/trends.py` (puro): `daily_activity`, `active_days`, `aggregate_series` (day/week/
  month), `compute_streak` (racha actual + mejor).
- `services/mastery.py` (puro): `classify_errors` (activos vs resueltos por `last_seen`,
  umbral 14 días) y `compute_milestones` (catálogo de 10 hitos).
- `repositories/progress.py`: `activity_events` (mensajes con modo + pronunciaciones).
- `domain/progress.py`: `get_progress_history` compone repo + servicios puros.
- Tests: `test_trends.py` (7) + `test_mastery.py` (3) + `test_progress_history.py` (5).
  Total backend **151 tests**.

### HECHO — F6.3: frontend dashboard de progreso real
- `components/ProgressDashboard.tsx` reemplaza a `ProgressSummary.tsx` (eliminado): racha,
  gráfico de actividad (por día/semana/mes), dominio de errores (activos/resueltos), hitos y
  timeline de eventos recientes. **Responsive total**: tablet (`@media 1024px`) + móvil
  (`@media 768px`), según premisa 14.
- `api/progress.ts::getProgressHistory`, `api/learning.ts::getEvents`; tipos nuevos en
  `types/api.ts`; helpers `bucketLabel`/`eventLabel` en `utils/progress.ts`.
- `useChat` expone `history`/`events`/`bucket` y refresca tras cada envío y pronunciación.
- Tests: `api/progress.test.ts` (2) + `utils/progress.test.ts` (2) + `api/learning.test.ts` (1).
  Total frontend **56 tests**.

**Estado al cierre de Fase 6:** backend `151 tests` + `ruff` limpio; frontend `56 tests` +
`tsc`/`build` OK. El progreso dejó de ser "counts estáticos": ahora hay tendencias temporales,
racha, dominio de errores (activos vs resueltos) e hitos, deterministas y sin LLM.

## 14. FASE 7 — Pronunciación fonética (CERRADA)

Sustituir el evaluador único (`difflib` a nivel de caracteres) por un **evaluador compuesto
determinista** (sin LLM): precisión por palabra + similitud fonética (Soundex) + caracteres.
El breakdown viaja solo en la respuesta (sin migración). Decisiones: Soundex (sí), persistencia
solo en respuesta (sí).

### HECHO — F7.1: evaluador compuesto (backend)
- `services/phonetics.py` (puro): `tokenize`, `soundex` (variante simplificada, sin deps),
  `word_alignment` (correct/missing/extra/substituted + total), `word_accuracy`,
  `phonetic_similarity` (greedy por Soundex) y `composite_score`
  (pesos `word 0.6 / phonetic 0.3 / char 0.1`).
- `services/pronunciation.py::score_pronunciation` delega en `composite_score` y amplía el
  contrato: `score`, `level`, `ok`, `word_accuracy`, `phonetic_score`, `breakdown`. Umbrales
  `good ≥80` / `fair ≥50` intactos.
- `schemas/pronunciation.py`: `WordSubstitution`, `PronunciationBreakdown` y
  `PronunciationResponse` ampliado. `routers/pronunciation.py` sin cambios.
- Sin migración de `pronunciation_attempts` (sigue guardando `score`/`level` agregados).
- Tests: `test_phonetics.py` (12). Total backend **163 tests**.

### PENDIENTE — F7.2: frontend feedback fonético
`PronunciationPractice.tsx` mostrará el breakdown (palabras correctas/omitidas/sustituidas +
score fonético) vía `utils/pronunciationFeedback.ts` (puro) y tipos nuevos en `types/api.ts`.

### HECHO — F7.2: frontend feedback fonético
- `types/api.ts`: `WordSubstitution`, `PronunciationBreakdown` y `PronunciationResponse`
  ampliado (`word_accuracy`, `phonetic_score`, `breakdown`).
- `utils/pronunciationFeedback.ts` (puro): `joinWords`, `feedbackHints`, `wordsCorrectLabel`.
- `PronunciationPractice.tsx`: muestra precisión por palabra, similitud fonética, resumen de
  aciertos y avisos (omitidas/sustituidas/de más). Responsive con tokens.
- Tests: `utils/pronunciationFeedback.test.ts` (9). Total frontend **65 tests**.

**Estado al cierre de Fase 7:** backend `163 tests` + `ruff` limpio; frontend `65 tests` +
`tsc`/`build` OK. La pronunciación pasó de un único `difflib` a un evaluador compuesto
(precisión por palabra + Soundex + caracteres) con feedback por palabra, determinista y sin LLM.

## 15. FASE 8 — Listening / Speaking / CEFR (CERRADA)

Backend primero (F8.1–F8.3), frontend al final (F8.4). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear. Decisiones: CEFR **multi-señal rico** (bandas por
destreza + descriptor); fluidez **con duración** (STT expone `info.duration`); **listening**
incluido ya (banco estático + TTS existente). Todo determinista, sin LLM.

| Subagente | Briefing | Estado |
|---|---|---|
| F8.1 CEFR multi-señal (backend) | `agentes/endurecimiento/f8-01-cefr-multisenial.md` | ✔ hecho |
| F8.2 Fluidez oral (backend) | `agentes/endurecimiento/f8-02-fluidez-oral.md` | ✔ hecho |
| F8.3 Listening (backend) | `agentes/endurecimiento/f8-03-listening.md` | ✔ hecho |
| F8.4 Frontend CEFR + fluidez + listening | `agentes/endurecimiento/f8-04-frontend.md` | ✔ hecho |

### HECHO — F8.1: evaluación CEFR multi-señal (backend)
- `services/cefr.py`: `evaluate_cefr` (punto-sum: vocab + pron + ejercicios + gramática +
  fluidez) + bandas `vocabulary_band`/`grammar_band`/`fluency_band`/`pronunciation_band` +
  `_LEVEL_DESCRIPTORS`/`level_descriptor`; `estimate_cefr` delega (compat v1). `recommendations`
  intacta.
- `schemas/profile.py`: `CefrBands` + `LearningProfile.cefr_bands`/`cefr_descriptor`.
- `domain/profile.py::_compute_profile` calcula `grammar_error_rate` + `messages` y usa
  `evaluate_cefr`.
- Tests: `test_cefr_evaluation.py` (9). Total backend **172 tests**.

### HECHO — F8.2: fluidez oral con duración (backend)
- `services/fluency.py` (puro): `compute_fluency` (WPM = palabras/min; `fluent ≥120`,
  `good 60–119`, `slow <60`, `—` sin audio válido).
- `services/stt.py`: `transcribe_with_timing` (devuelve `{text, duration}` con `info.duration`);
  `transcribe` delega (contrato de string intacto para `voz.py`).
- `schemas/pronunciation.py`: `FluencyStats` + `PronunciationResponse.fluency`.
- `routers/pronunciation.py`: usa `transcribe_with_timing` + `compute_fluency`.
- Se actualizaron 2 monkeypatch de tests existentes (`test_activity.py`, `test_api_security.py`)
  para devolver `{text, duration}`. Tests: `test_fluency.py` (6). Total backend **178 tests**.

### HECHO — F8.3: listening (banco + preguntas, backend)
- `services/listening.py` (puro): `QUESTION_BANK` (8 preguntas A1–B1, opción múltiple) +
  `get_question`/`pick_next_question`/`score_answer`.
- `schemas/listening.py`: `ListeningQuestion`, `ListeningAnswerRequest`, `ListeningAnswerResponse`,
  `ListeningStats`.
- `repositories/listening.py`: tabla `listening_attempts` + `record_attempt`/`seen_question_ids`/
  `get_stats`; `domain/listening.py`: `next_question`/`submit_answer`/`get_stats`.
- `routers/listening.py`: `GET /api/listening/question`, `POST /api/listening/answer`,
  `GET /api/listening/stats` (registra evento `exercise`). `db.py` (tabla+índice) y `main.py`
  (registro router) solo aditivos.
- Tests: `test_listening.py` (13). Total backend **191 tests**.

### HECHO — F8.4: frontend CEFR + speaking + listening
- `types/api.ts`: `FluencyStats`, `CefrBands`, `PronunciationResponse.fluency`,
  `LearningProfile.cefr_bands/cefr_descriptor`, tipos de listening.
- `utils/cefr.ts` (`bandLabel`), `utils/fluency.ts` (`wpmLabel`, `fluencyLevelLabel`),
  `api/listening.ts` (3 funciones).
- `LearningProfile.tsx`: descriptor CEFR + bandas por destreza. `PronunciationPractice.tsx`:
  línea de fluidez (nivel · WPM). `ListeningPractice.tsx` (nuevo): TTS + opciones + feedback +
  stats + "Siguiente". `App.tsx` lo monta; `index.css` con estilos responsive.
- Tests: `utils/fluency.test.ts` (4) + `utils/cefr.test.ts` (+2) + `api/listening.test.ts` (3).
  Total frontend **74 tests**.

**Estado al cierre de Fase 8:** backend `191 tests` + `ruff` limpio + `import main` OK;
frontend `74 tests` + `tsc`/`build` OK. CEFR dejó de ser una heurística plana: ahora hay
evaluación multi-señal con bandas por destreza y descriptor; la pronunciación añade fluidez
(WPM) con la duración del audio; y hay ejercicios de comprensión auditiva (banco + preguntas)
reproducidos con el TTS local.

## 16. FASE 9 — Evaluación objetiva del tutor (CERRADA)

Backend primero (F9.1–F9.2), frontend al final (F9.3). Un commit `feat:` por subagente, cada
uno verificado en verde antes de commitear. Evaluación determinista y sin LLM-juez (premisa 12).

| Subagente | Briefing | Estado |
|---|---|---|
| F9.1 Evaluador objetivo del tutor (backend) | `agentes/endurecimiento/f9-01-evaluador-tutor.md` | ✔ hecho |
| F9.2 Informe agregado + script por lotes (backend) | `agentes/endurecimiento/f9-02-informe-agregado.md` | ✔ hecho |
| F9.3 Panel de calidad del tutor (frontend) | `agentes/endurecimiento/f9-03-panel-calidad-tutor.md` | ✔ hecho |

### HECHO — F9.1: evaluador objetivo del tutor (backend, puro)
- `services/evaluation.py` (puro, sin LLM-juez): `SPANISH_WORDS`, `FRIENDLY_MARKERS`,
  `EVAL_CASES` (8 casos canónicos A1–B1), `normalize`, `_words`, `contains_fragment`,
  `contains_any_fragment`, `spanish_word_ratio`, `english_word_ratio`, `conciseness_score`,
  `engagement_score`, `evaluate_tutor_reply` (señales `correction`/`english`/`conciseness`/
  `engagement` + `total` ponderado) y `summarize` (medias por señal).
- Tests: `test_evaluation.py` (16). Total backend **207 tests**.

### HECHO — F9.2: informe agregado + script por lotes (backend)
- `services/evaluation.py`: `TUTOR_PROMPTS` + `build_tutor_prompt`, `build_report`
  (resumen + desglose por caso + `verdict`), `format_report` (texto legible).
- `scripts/eval_tutor.py` (CLI): `--model` + `--json`; envía `EVAL_CASES` al modelo, puntúa
  cada respuesta y emite el informe agregado. No persiste nada en BD.
- Tests: `test_evaluation_report.py` (10). Total backend **217 tests**.

### HECHO — F9.3: panel de calidad del tutor (frontend)
- `utils/tutorEvaluation.ts` (puro, espejo del evaluador): `normalize`, `words`,
  `spanishWordRatio`, `englishWordRatio`, `concisenessScore`, `engagementScore`,
  `evaluateTutorReply`, `averageEvaluations`.
- `components/TutorQualityPanel.tsx` (presentacional): medias de `Inglés`/`Concisión`/
  `Engagement`/`Total` + últimos 3 turnos del tutor. Responsive móvil/tablet. `App.tsx` lo
  monta tras `LearningProfile`; estilos `.tutor-quality` en `index.css`.
- Tests: `utils/tutorEvaluation.test.ts` (14). Total frontend **88 tests**.

**Estado al cierre de Fase 9:** backend `217 tests` + `ruff` limpio + `import main` OK;
frontend `88 tests` + `tsc`/`build` OK. El tutor ya se puede evaluar objetivamente (sin
LLM-juez): por corpus en backend (script por lotes) y en vivo en el frontend (panel de calidad
sobre la conversación actual).

## 17. FASE 10 — Release 1.0 estable + Launcher de escritorio (CERRADA)

Versión unificada `1.1.0`, gate verde completo y nuevo componente `launcher/`.

| Subagente | Briefing | Estado |
|---|---|---|
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |

### HECHO — Launcher de escritorio (`launcher/`)
- `core.py` (puro): rutas (`REPO_ROOT`, `BACKEND_DIR`, `FRONTEND_DIR`, `DB_PATH`), comandos
  (`backend_command`, `frontend_command`), URLs y normalización (`app_summary`,
  `health_status`, `db_summary`, `user_overview`).
- `process_manager.py`: `ProcessManager` (arranca/para backend `uvicorn` y frontend `npm run
  dev`; matado del árbol de procesos en Windows con `taskkill /T /F`; logs en `launcher/logs/`).
- `status.py`: `fetch_health`/`fetch_frontend` (HTTP) y `read_db_counts`/`read_users`
  (SQLite solo lectura).
- `launcher.py`: GUI `tkinter` (servicios, BD, usuarios; botones Iniciar/Detener/Abrir/
  Actualizar; refresco en hilo de fondo). No duplica servicios ya activos al iniciar.
- `make_icon.ps1` (genera `icon.ico`) y `install_shortcut.ps1` (crea `English Tutor.lnk`
  en el escritorio).
- Tests: `test_core.py` (13) + `test_status.py` (7) + `test_process_manager.py` (2) = **22 tests**.

### HECHO — Versión 1.1.0
- `backend/config.py::VERSION = "1.1.0"`; expuesta en `/api/health` y en `/`; `main.py`
  (`FastAPI(version=VERSION)`); `frontend/package.json` → `1.1.0`.
- Tests de versión en `test_health.py` (`test_root` y `test_health`).

**Estado al cierre de Fase 10:** backend `217 tests` + `ruff` limpio; frontend `88 tests` +
`tsc`/`build` OK; launcher `22 tests` + `ruff` limpio. Versión `1.1.0` unificada y lanzador
de escritorio con acceso directo e icono.

## 18. M14 — GUI responsive a ancho completo + personalización + acceso en red (HECHO)

Requisito del usuario: que la GUI sea más atractiva y **responsive** (adaptarse a tablets/móvil
y, en escritorio, **aprovechar todo el ancho** en vez de concentrar el contenido en una columna
central), con **zonas redimensionables** al gusto, **persistencia por usuario** de todos los
ajustes (incluido el modelo), aspecto **100% profesional**, **personalización visual del
perfil** (avatar/imagen/icono/color) y **acceso desde toda la red local** mostrando la URL de
acceso en la propia web y en el launcher.

### Layout multi-panel responsive y redimensionable
- `App.tsx`: la zona principal pasa de una columna centrada a un `workspace` flex con tres
  paneles: `pane--sidebar` (conversaciones), `pane--main` (chat) y `pane--insights`
  (dashboard de progreso + perfil + calidad del tutor + listening). El ancho se aprovecha al
  máximo en escritorio.
- `components/ResizeHandle.tsx`: asa de redimensionado horizontal (pointer events + teclado
  ←/→, `role="separator"`, `aria-*`) entre paneles.
- `utils/layout.ts`: `LAYOUT_DEFAULTS`, `clampSidebar`/`clampRight` (mín/máx), `parseLayout`/
  `serializeLayout`. Tests en `utils/layout.test.ts`.
- `index.css`: clases `workspace`/`pane`/`pane--*`/`resize-handle`; en ≤1024px los paneles
  laterales pasan a **drawers superpuestos** (hamburguesa/insights-toggle + backdrop), y en
  ≤768px se compacta el header. El chat usa `chat-scroll` + `chat-inner` (máx 860px, centrado).

### Persistencia de preferencias por usuario (modelo, modo, layout)
- Backend: tabla `settings` (clave/valor, PK `user_id+key`, upsert) en `repositories/db.py`;
  `repositories/settings.py`, `domain/settings.py`, `schemas/settings.py` y
  `routers/settings.py` (`GET/PUT /api/settings`). El modelo (`qwen3.5:9b` por defecto), el
  modo y las dimensiones del layout se guardan por usuario y se restauran al reabrir.
- Frontend: `api/settings.ts` + `hooks/useChat.ts` (`persistSettings`, `selectModel`,
  `selectMode`, `setLayout` cargan/guardan por `currentUserId`).

### Personalización del perfil (avatar/imagen/icono/color)
- Backend: columnas `avatar_color`/`avatar_emoji`/`avatar_image` en `users` (migración
  idempotente), `schemas/users.py` (`UserUpdate`), `repositories/users.py::update_user`,
  `domain/users.py`, y `PATCH /api/users/{id}` en `routers/users.py`.
- Frontend: `components/UserAvatar.tsx` (imagen → emoji → iniciales con color determinista),
  `components/ProfileDialog.tsx` (nombre, icono, color, subir/quitar imagen con
  `utils/image.ts::resizeImageToDataUrl`), `components/UserMenu.tsx` (selector de perfil,
  crear/editar). `UserSelect.tsx` eliminado (sustituido por `UserMenu`).

### Acceso en red local (LAN)
- Backend: `config.py` añade `ALLOWED_ORIGIN_REGEX` (IPs privadas IPv4) y `main.py` la usa en
  `CORSMiddleware` (`allow_origin_regex`). `services/network.py::get_lan_ip` +
  `routers/network.py::GET /api/network` (IP + URLs).
- Launcher: `core.py::backend_command` enlaza uvicorn a `0.0.0.0`; `core.py::lan_ip`/`lan_url`;
  `launcher.py` añade el recuadro "Acceso a la app" (URL local y LAN).
- Frontend: `components/NetworkBadge.tsx` muestra la URL LAN y permite copiarla.

### Tests añadidos
- Backend: `test_settings.py`, `test_user_profile.py`, `test_network.py`, +`test_cors.py`
  (caso LAN). Total backend **260 tests**.
- Frontend: `utils/layout.test.ts`, `utils/avatar.test.ts` (más los tests existentes). Total
  frontend **106 tests**.
- Launcher: `test_core.py` (+`test_backend_command_binds_lan`, `test_lan_url`). Total **24 tests**.

### Decisión de modelo (respuesta al usuario)
Se mantiene **`qwen3.5:9b`** como modelo por defecto (mejor calidad como tutor, ver sección 5);
`llama3.1:8b` queda instalado y seleccionable. La elección ahora es persistente por usuario.

## 19. M15 — Launcher: UI moderna con iconos, paneles colapsables y logs (HECHO)

Requisito del usuario: hacer el programa de arranque de escritorio más atractivo y completo,
con iconos en la UI y más información en paneles colapsables.

- **`launcher/ui.py`** (nuevo, puro y testeable): `COLORS` (paleta claro con acento índigo),
  `SERVICE_ICONS`/`SECTION_ICONS`/`ACTION_ICONS` (emoji), `status_dot()` (punto de estado por
  color) y `read_log_tail()` (últimas N líneas de `logs/*.log`).
- **`launcher/status.py`**: `fetch_version()` (versión desde `/api/health`) y
  `read_db_details()` (contadores de tablas opcionales — vocabulario, errores, eventos,
  pronunciación, listening, preferencias — tolerante a tablas inexistentes vía `sqlite_master`).
- **`launcher/launcher.py`** (reescrito):
  - Tema `clam` personalizado (`ttk.Style`) con banner de cabecera (logo "EN" + título +
    versión + píldora de estado "En marcha/Detenida" con punto de color).
  - Botones con iconos (Iniciar/Detener/Abrir/Actualizar).
  - **Paneles colapsables** reutilizables (`class Collapsible`): Servicios, Acceso a la app,
    Base de datos (con detalle de tablas), Usuarios y Registros (logs de backend/frontend en
    un `Notebook`, colapsado por defecto).
  - Contenido desplazable (Canvas + Scrollbar) y footer de estado. Lógica de concurrencia
    (cola + hilos + `ProcessManager`) intacta.
- **Tests**: `tests/test_ui.py` (nuevo, 5) + `tests/test_status.py` (+4). Total launcher
  **33 tests** + `ruff` limpio.

> Nota de arranque en red: el frontend (Vite) ahora escucha en `0.0.0.0` (`vite.config.ts`
> `host: true`), igual que el backend, para que la app sea accesible desde otros equipos de la
> LAN (antes solo respondía `localhost` y el puerto 5173 no era alcanzable).

## 20. HECHO (V1.8) — Loop diario: placement adaptativo + objetivo + Session Engine

> **Origen.** Auditoría pedagógica: faltaba un "loop diario" integrado. Este bloque cierra ese
> hueco cableando a la UI el placement adaptativo ya existente en backend, añadiendo un objetivo
> personal editable y un **Session Engine** que unifica las señales CEFR y de listening en una
> sesión diaria priorizada.

### 20.1 Placement adaptativo cableado a la UI
- `frontend/src/components/Academy.tsx`: el placement pasó de batch (`getPlacement` +
  `submitPlacement`) a adaptativo (`startAdaptivePlacement` + `nextAdaptivePlacement`), con
  estado `placementItem`/`placementSessionId`/`placementAnswers`/`placementAnswered`.
- `frontend/src/api/academy.ts`: `startAdaptivePlacement`, `nextAdaptivePlacement`.
- `frontend/src/types/api.ts`: `PlacementStart`, `PlacementAdaptive`.

### 20.2 Objetivo personal editable
- **DB** (`backend/repositories/db.py`): tabla `learning_goal`
  (`user_id PK, goal_type, minutes_per_day, days_per_week, target_level, updated_at`, FK a users).
- **Repo** (`backend/repositories/academy.py`): `get_goal`, `upsert_goal`.
- **Schemas** (`backend/schemas/academy.py`): `LearningGoalIn` (`GoalType` literal, minutos 5–180,
  días 1–7, `target_level` CEFR), `LearningGoalOut`.
- **Domain** (`backend/domain/academy.py`): `DEFAULT_GOAL`, `get_learning_goal`, `set_learning_goal`;
  `get_today_plan` y `get_student_model` usan el objetivo (`minutes_per_day` y `target_level`).
- **Routers** (`backend/routers/academy.py`): `GET/PUT /api/academy/goal`.
- **Frontend**: `getGoal`/`putGoal` en `api/academy.ts`; editor de objetivo (tipo, meta CEFR,
  min/día, días/semana) en `components/TodayPlan.tsx`, con `putGoal` + recarga de modelo/sesión.
- **Tests**: `backend/tests/test_academy_goal.py` (repo + endpoints); `frontend/src/api/academy.test.ts`.

### 20.3 Session Engine (backend puro)
- `backend/services/adaptive.py`:
  - Refactor `_assign_minutes(items, budget, mix=None)` para repartir minutos con un `mix` por
    categoría (antes pesos fijos).
  - `SESSION_MIX` = `{review: .30, listening: .15, weakness: .30, new: .15, easy_wins: .10}`.
  - `SESSION_CAPS` = `{review: 3, listening: 2, weakness: 2, new: 1, easy_wins: 1}`.
  - `session_plan(profile, level, remediation, mastered_ids, next_objective_id, listening_weak,
    budget_minutes)`: secuencia priorizada review → listening → debilidad → nuevo → refuerzo,
    con `level_id` y `skills` en los pasos con objetivo (para arrancar la lección).
  - `steps_of(steps, kind)` y `session_summary(steps)` → `{review_count, practice_count}`.
- `backend/schemas/academy.py`: `SessionStepOut` (`kind, skill, subskill, objective_id, level_id,
  skills, title, reason, minutes`) y `SessionOut` (`items, total_minutes, review_count,
  practice_count`).
- `backend/domain/academy.py`: `get_session(user_id)` une el perfil CEFR (`list_objective_mastery`,
  `mastered_objective_ids`, `remediation_plan`, `recommend_next`) con el diagnóstico de listening
  (`listening_repo.list_attempts` + `listening_diagnostic`) y llama a `session_plan` con el
  presupuesto del objetivo.
- `backend/routers/academy.py`: `GET /api/academy/session`.
- **Tests**: `backend/tests/test_adaptive.py` (session_plan/session_summary, pasos con
  level_id/skills) + `test_academy_goal.py` (endpoint session).

### 20.4 Frontend: sesión en "Hoy" + enrutado por paso
- `frontend/src/types/api.ts`: `SessionStep`, `Session`, `LearningGoal`, `LearningGoalType`.
- `frontend/src/api/academy.ts`: `getSession`.
- `frontend/src/components/TodayPlan.tsx`:
  - Muestra `Session` (no `TodayPlan`): cabecera `total_minutes` + "repasa N · practica M" y
    lista `SessionStepRow` (botón accionable) con `KIND_LABELS`/`SUBSKILL_LABELS`/`SKILL_LABELS`.
  - Botón "Empezar la sesión de hoy" lanza el primer paso.
  - Nueva prop `refreshKey` que recarga modelo+sesión al cambiar (para reflejar pasos completados).
- `frontend/src/App.tsx`:
  - `handleSessionStep(step)`: listening → abre insights + scroll a `#listening-practice`;
    objetivo → `startLesson(...)`; skill → cambia `mode` vía `SKILL_MODE`.
  - `sessionVersion` state: `onAttempt` y "Terminar lección" lo incrementan; se pasa como
    `refreshKey` a `TodayPlan` para que el paso completado desaparezca al recargar la sesión.
- `frontend/src/index.css`: estilos `.goal-editor`, `.session-headline`, `.today-item-action`
  (botón de paso), `.kind-listening`.

### 20.5 Pendiente / siguiente incremento natural
- **P3–P6 de Etapa 2** (vocabulario, listening competencia, CEFR evidencia, pronunciación fonémica):
  ver `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 21. HECHO (V1.8.1) — Marcar pasos de la sesión como "hechos"

Cierra el hueco de `review`/`easy_wins` (que solo cambiaban de modo): ahora cualquier
paso se puede marcar como completado y desaparece de la sesión de hoy, con reseteo diario.

- **`services/adaptive.py`**: `step_key(step)` (clave estable: `listening:<subskill>`,
  `<weakness|new>:<level>:<objective>`, `<review|easy_wins>:<skill>`) y
  `session_plan(..., exclude_keys=...)` que anota cada paso con `step_key`, filtra los
  ya completados y **reparte los minutos solo entre los pasos restantes**.
- **`repositories/db.py`**: tabla `session_completions` (`PK (user_id, step_key)`,
  `completed_on` para el reseteo diario, FK a users).
- **`repositories/academy.py`**: `mark_session_step(user_id, step_key, completed_on)`
  (upsert) y `list_session_steps(user_id, completed_on) -> set[str]`.
- **`schemas/academy.py`**: `SessionStepOut.step_key` + `SessionCompleteRequest`.
- **`domain/academy.py`**: `_today()` (fecha UTC `YYYY-MM-DD`); `get_session` excluye los
  pasos de hoy (`exclude_keys`); `set_session_step_done(user_id, step_key)` → devuelve la
  sesión actualizada.
- **`routers/academy.py`**: `POST /api/academy/session/complete` (`{step_key}`) → `SessionOut`.
- **Frontend**: `SessionStep.step_key`, `completeSessionStep` en `api/academy.ts`; en
  `TodayPlan.tsx` cada paso tiene un botón "✓" (`.today-item-done`) que llama al endpoint
  y sustituye la sesión con la respuesta (el paso marcado desaparece). Estilos en `index.css`.
- **Tests**: `test_adaptive.py` (+`step_key`, +`exclude_keys`), `test_academy_goal.py`
  (+repo mark/list y +endpoint complete), `api/academy.test.ts` (+`completeSessionStep`).

### Verificación rápida del estado sin commitear
```powershell
cd backend && .venv\Scripts\python.exe -m pytest -q && .venv\Scripts\python.exe -m ruff check .
cd frontend && npx tsc --noEmit && npx vitest run
```

## 22. EN CURSO (sin commitear) — P3: vocabulario exposure / production / mastery

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P3: hoy `vocabulary` solo medía producción
> (`appearances` = mensajes en los que el alumno escribió la palabra). Este incremento separa los
> tres conceptos: **exposición** (palabras que lee en las respuestas del tutor), **producción**
> (palabras que escribe) y **dominio** (producción repetida y espaciada en el tiempo).

### 22.1 Modelo de datos (exposición vs producción)
- **`repositories/db.py`**: migración idempotente en `vocabulary`:
  - `exposures INTEGER NOT NULL DEFAULT 0` (mensajes del tutor en los que apareció la palabra).
  - `last_exposed_at TEXT NOT NULL DEFAULT ''`.
  - `production_days INTEGER NOT NULL DEFAULT 0` (días distintos con producción = espaciado).
  - Backfill: `UPDATE vocabulary SET production_days = 1 WHERE appearances > 0 AND production_days = 0`.

### 22.2 Señal de dominio (pura)
- **`services/vocabulary.py`**: `classify(appearances, production_days)` → `"exposed"` (nunca
  producida) | `"learning"` (producida, sin consolidar) | `"mastered"` (≥3 producciones y ≥2 días
  distintos). Constantes `MASTERY_MIN_PRODUCTIONS = 3`, `MASTERY_MIN_DAYS = 2`.

### 22.3 Repositorio
- **`repositories/vocabulary.py`**:
  - `record_words` ahora también incrementa `production_days` cuando la producción cae en un día
    distinto al último (`_day(iso)` → `iso[:10]`).
  - `record_exposures(user_id, words)` (nuevo): upsert con `appearances = 0` para crear filas
    solo-expuestas.
  - `get_vocabulary` devuelve `exposures`, `last_exposed_at`, `production_days`.

### 22.4 Schemas + dominio
- **`schemas/vocabulary.py`**: `VocabularyItem` gana `exposures`, `last_exposed_at`,
  `production_days`, `status: Literal["exposed","learning","mastered"]`.
- **`domain/vocabulary.py`**: `record_exposure(user_id, text)` (nuevo) y `get_vocabulary` calcula
  `status` por palabra vía `classify`.

### 22.5 Captura de exposición en el chat
- **`routers/chat.py`**: tras la respuesta del tutor (`chat` y `chat_stream`), si hay `user_id` se
  llama `vocabulary_service.record_exposure(user_id, reply)`; en el stream se acumulan los chunks y
  se registra al final.

### 22.6 Perfil separa producido / expuesto / dominado
- **`domain/profile.py`**: `vocab_size` (para CEFR y recomendaciones) ahora cuenta solo palabras
  producidas (`appearances > 0`), no las solo-expuestas; calcula `vocabulary_mastered` y
  `vocabulary_exposed`.
- **`schemas/profile.py`**: `LearningProfile` gana `vocabulary_exposed` y `vocabulary_mastered`.

### 22.7 Frontend
- **`frontend/src/types/api.ts`**: `LearningProfile.vocabulary_exposed`/`vocabulary_mastered`.
- **`frontend/src/components/LearningProfile.tsx`**: bloque Vocabulario muestra "N dominadas · M
  vistas" (`.learning-sub`).

### 22.8 Tests
- `test_vocabulary.py`: `classify` (5 casos), `record_exposures` (crea/acumula/unknown),
  `production_days` con días controlados (monkeypatch `_now`), endpoint `status`, migración P3
  (drop column + backfill).
- `test_profile.py`: perfil separa `vocabulary_size`/`vocabulary_exposed`/`vocabulary_mastered`.
- `test_chat_profile.py`: `chat` y `chat_stream` registran la exposición del tutor.

### 22.9 Siguiente incremento natural
- **P5–P6 de Etapa 2** (CEFR por evidencia, pronunciación fonémica): ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 23. HECHO (V1.10) — P4: listening como competencia

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P4: el listening ya medía `difficulty`,
> `response_time_ms` y `replay_count`, pero no distinguía **tema**, ni precisión por
> dificultad/tema, ni tendencia reciente, ni reincidencia. Este incremento lo convierte en
> una señal de **competencia**.

### 23.1 Tema (`topic`)
- **`services/listening.py`**: `LISTENING_TOPICS` (10 temas canónicos), campo `topic` en
  `ListeningAsset` y en los 23 ítems de `QUESTION_BANK`; `validate_listening_bank` exige
  `topic` válido.

### 23.2 Métricas de competencia (puras y deterministas)
- `accuracy_by_difficulty(rows)`, `accuracy_by_topic(rows)`, `recent_trend(rows, window=10)` y
  `recurrence_stats(rows)`; `listening_diagnostic` expone `by_difficulty`, `by_topic`, `trend`
  y `recurrence`.

### 23.3 Persistencia + dominio + esquemas
- `repositories/db.py`: migración idempotente `topic` en `listening_attempts`.
- `repositories/listening.py`: `record_attempt(..., topic=...)` y `list_attempts` incluyen `topic`.
- `domain/listening.py`: `submit_answer` pasa el tema de la pregunta.
- `schemas/listening.py`: `topic` en `ListeningQuestion` + `ListeningDifficultyOut`,
  `ListeningTopicOut`, `ListeningTrend`, `ListeningRecurrence` en `ListeningDiagnostic`.

### 23.4 Frontend
- `types/api.ts` (nuevos tipos) y `ListeningPractice.tsx` (precisión por tema/dificultad,
  tendencia reciente y reincidencia). Estilos en `index.css`.

### 23.5 Tests
- `test_listening.py` (+11) y `test_listening_architecture.py` (+2). Total backend
  **556 tests**; frontend **143 tests**.

### 23.6 Pendiente / siguiente incremento natural
- **P5–P6 de Etapa 2** (CEFR por evidencia, pronunciación fonémica): ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 24. HECHO (V1.11) — P5: CEFR basado en evidencia

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P5: `services/cefr.py::evaluate_cefr` sumaba puntos
> (`_vocab_points`, `_pron_points`, `_exercise_points`, `_grammar_points`, `_fluency_points`) y
> mapeaba la suma a un nivel. Era un "contador": subías de nivel con vocabulario aunque no
> tuvieras ni una muestra de pronunciación, listening o gramática. Este incremento lo sustituye
> por un modelo de **evidencia** y expone la **confianza** del nivel.

### 24.1 Modelo de evidencia (`services/cefr.py`)
- `MIN_SAMPLES` (mínimo de muestras por destreza): `vocabulary=50`, `grammar=5`,
  `fluency=5`, `pronunciation=3`, `listening=5`; `TRACKED_SKILLS` con ese orden.
- `listening_band(accuracy)` (umbrales 85/70/50, `"—"` si `None`) y `_band_rank`.
- `evaluate_cefr` reescrito: por destreza calcula `band` + `samples` + `confidence`
  (`min(1, samples/required)`); el nivel es la **banda más baja entre las destrezas con
  evidencia suficiente** (`confidence >= 1` y `band != "—"`), o `A1` si no hay ninguna;
  devuelve `{level, bands, evidence, confidence, descriptor}`.
- Eliminadas las funciones privadas de puntos (`_vocab_points`, `_pron_points`,
  `_exercise_points`, `_grammar_points`, `_fluency_points`, `_level_from_points`).
- `estimate_cefr` sigue delegando en `evaluate_cefr(signals)["level"]` (API v1 intacta).

### 24.2 Dominio (`domain/profile.py`)
- `_compute_profile` ahora obtiene `listening_repo.get_stats` y pasa a `evaluate_cefr` las
  señales nuevas: `pronunciation_attempts`, `user_messages`, `listening_accuracy`,
  `listening_attempts`. Expone `estimated_confidence` y `estimated_evidence`.

### 24.3 Esquemas (`schemas/profile.py`)
- `EstimatedBands` + `listening`; nueva `CefrEvidence` (`skill`, `band`, `samples`,
  `required`, `confidence`); `LearningProfile` + `estimated_confidence` y `estimated_evidence`.

### 24.4 Frontend
- `types/api.ts` (nuevos tipos), `utils/cefr.ts` (`bandLabel("listening")`),
  `components/LearningProfile.tsx` (banda de listening + barra de confianza + detalle por
  destreza) y estilos en `index.css`.

### 24.5 Tests
- `test_cefr_evaluation.py` (casos de evidencia, `listening_band`, 5 destrezas en `evidence`)
  y `test_profile.py` (nuevos niveles B1/C1 y `estimated_confidence`/`estimated_evidence`).
  Total backend **558 tests**; frontend **143 tests**.

### 24.6 Pendiente / siguiente incremento natural
- **V1.12 — Student Model unificado + Assessment Loop** (P6 speaking + P7 unificación): ver
  sección 25 y `agentes/pedagogia/p6-speaking-2.0.md` / `p7-student-model-unificado.md`.
- El P6 original (pronunciación fonémica) queda **diferido** a favor de esta unificación.

## 25. HECHO (V1.12) — Student Model unificado + Assessment Loop

> **Origen.** La auditoría externa de V1.11 detectó dos estimadores CEFR paralelos que se
> contradicen (`/api/profile` con banda mínima vs `/api/academy/student-model` con nivel continuo
> ponderado), 4 defectos de scoring en Speaking y la falta de histórico de evaluación. V1.12
> convierte el **Student Model de la Academy en la fuente de verdad única**, corrige los P0 y añade
> **snapshots de evaluación** reproducibles. Dos subagentes (`p6`, `p7`), cada uno su `feat:`.

### 25.1 P6 — Speaking scoring 2.0 + higiene de release
- **`services/speaking.py`**: `task_achievement` usa `task_achieved` del LLM en flujo libre
  (el solapamiento de tokens es solo cota inferior con `expected`); `lexical_resource` mide
  diversidad léxica (TTR) con `lexical_diversity(tokens)`; `coherence` usa el `coherence` del LLM
  + marcadores discursivos (eliminado `len(heard)/len(expected)`); `pronunciation` devuelve
  `observed=false`/`score=None` sin audio y `_weighted_overall` recalcula solo criterios
  observados. Añade `observed` y `confidence` por criterio; penalizaciones discursivas
  (`self_corrections`, `hesitations`, `repetitions`) reducen `fluency`.
- **`services/speaking_llm.py`**: `SPEAKING_EVIDENCE_FIELDS` ampliada con `cohesion`,
  `discourse_markers`, `self_corrections`, `hesitations`, `repetitions`; helpers
  `_parse_float_field`/`_parse_count_field` con fallback.
- **`config.py`** → `VERSION = "1.11.0"`; **`README.md`** → "v1.11.0".
- **`schemas/academy.py`** / **`domain/academy.py`**: `observed` en speaking, `criteria` con
  `float | None`.
- Tests: `test_speaking.py` (observed, diversidad, sin audio, penalizaciones),
  `test_speaking_llm.py` (campos opcionales + fallback).

### 25.2 P7 — Student Model fuente única + snapshots + naming CEFR
- **`domain/academy.py`**: `build_student_model(user_id) -> dict` como única fuente de verdad
  (reutiliza `build_skill_profile` + `adaptive.estimated_level` + `readiness` +
  `reassessment_due`); `get_student_model` proyecta a `StudentModelOut`.
- **`domain/profile.py`**: `_compute_profile` delega en `build_student_model` (adiós al min-band
  propio); helpers puros extraídos (`_bands_from_skills`, `_skill_states`, `_activity_stats`,
  `_maybe_record_snapshot`). `get_profile_summary` incluye `cefr_history`.
- **`repositories/db.py`**: tabla idempotente `cefr_assessment_snapshots` + índice.
- **`repositories/profile.py`**: `record_cefr_snapshot`, `list_cefr_history`,
  `last_cefr_snapshot`.
- **`services/cefr.py`**: `estimate_cefr` (API v1) intacta; bandas documentadas como
  "heuristic CEFR-aligned band"; `CEFR_MODEL_VERSION` y `heuristic_band(score)`. `evaluate_cefr`
  deja de ser la fuente del perfil global.
- **`schemas/profile.py`**: `EstimatedBands` con 7 destrezas (`speaking`, `reading`, `writing`);
  nuevas `SkillState` y `CefrSnapshot`; `LearningProfile` con `overall_ability`, `target_level`,
  `skills`, `readiness` y `cefr_history`.
- **Frontend**: `types/api.ts` (nuevos tipos, adiós `CefrEvidence`), `utils/cefr.ts`
  (`bandLabel` speaking/reading/writing), `utils/modes.ts` (`conversation` → `speaking`),
  `components/LearningProfile.tsx` (barra `overall_ability`, `readiness` con `blocking_skills`,
  desglose por destreza con muestras/confianza/tendencia, histórico CEFR), estilos en `index.css`.
- Tests: `test_profile.py` (nuevo shape + snapshot una sola vez), `test_cefr_evaluation.py`
  (`heuristic_band`, `CEFR_MODEL_VERSION`), frontend `cefr.test.ts`/`modes.test.ts`.

### 25.3 Verificación
- Backend `566 tests` + `ruff` limpio; frontend `143 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 25.4 Pendiente / siguiente incremento natural
- **V1.13** — Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2): ver sección 26.
- **V1.14** — Listening Evidence & Adaptive Selection: ver sección 27.
- **V1.15** — Speaking 3.0 (sobre el mismo Student Model). Ver sección 28.

## 26. V1.13 — Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2)

> **Origen.** `agentes/pedagogia/p8-listening-3.0.md`. El listening tenía arquitectura sólida
> (banco versionado, vector 8D, 15 sub-destrezas, métricas de competencia) pero **sin audio
> pre-renderizado**: el frontend sintetizaba `script` en vivo con la voz Piper única, ignorando
> `speech_rate`/`accent`. Además faltaba `b2.json` (el banco ya tenía ítems B2: `l16`, `l17`, `l20`,
> `l21`). V1.13 sirve **audio TTS pre-renderizado por ítem**, cierra **A1→B2** y garantiza evidencia
> independiente por sub-destreza. Honesto con el límite local: Piper es una sola voz; acentos/ruido/
> hablantes son límite de **contenido**, no de código.

### 26.1 Audio TTS pre-renderizado por ítem
- **`services/tts.py`**: `synthesize(text, length_scale=1.0)` ahora acepta velocidad vía
  `SynthesisConfig(length_scale=...)`.
- **`services/listening.py`**: `length_scale_for_rate(speech_rate)` (mapea wpm → `length_scale`,
  clamp `[0.6, 1.6]`), `audio_text(question)` (`transcript` con fallback a `script`), y
  `LEVEL_ORDER = ["A1", "A2", "B1", "B2"]`.
- **`domain/listening.py`**: `get_audio(question_id)` sintetiza y cachea en `DATA_DIR/listening/`
  (primera petición) y sirve del caché después; `audio_ready(question)` y `_public` exponen
  `audio_ready`.
- **`routers/listening.py`**: `GET /api/listening/audio/{question_id}` → `audio/wav` (404/503).
- **`schemas/listening.py`**: `ListeningQuestion.audio_ready`.

### 26.2 Cierre A1→B2
- **`curriculum/b2.json`**: nivel B2 (8 objetivos, checks de opción múltiple cubriendo sus
  destrezas evaluables — invariante curricular verde).
- **`services/curriculum.py`**: `LISTENING_BANK_VERSION` → `3.0.0`.
- **`scripts/generate_listening_audio.py`**: pre-renderiza todo el banco (idempotente, `--force`).

### 26.3 Evidencia por sub-destreza
- `test_new_subskills_generate_independent_evidence` cubre `fast_speech`, `connected_speech`,
  `multiple_speakers`, `dictation`, `shadowing`, `speaker_intention` en `listening_diagnostic`.

### 26.4 Frontend
- **`api/listening.ts`**: `getListeningAudioUrl(questionId, userId)`.
- **`types/api.ts`**: `audio_ready: boolean`.
- **`components/ListeningPractice.tsx`**: reproduce audio TTS pre-renderizado cuando `audio_ready`,
  degrada a TTS en vivo con aviso "audio de referencia no disponible"; respeta `replayCount`.
- **`index.css`**: estilo `.listening-audio-degraded`.

### 26.5 Higiene de release
- `config.py`/`README.md`/`PLAN.md`/`package.json`/`package-lock.json` → `1.13.0`; `CHANGELOG.md`
  con entrada 1.13.0.

### 26.6 Verificación
- Backend `576 tests` + `ruff` limpio; frontend `144 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 26.7 Pendiente / siguiente incremento natural
- **V1.14** — Listening Evidence & Adaptive Selection: ver sección 27.
- **V1.15** — Speaking 3.0 (sobre el mismo Student Model): fluency/grammar/lexical/
  pronunciation/coherence/interaction medidos longitudinalmente. Ver sección 28.

## 27. HECHO (commiteado) — V1.14: Listening Evidence & Adaptive Selection

> **Origen.** Auditoría externa de V1.13 (commit `37ac52b9…`, 2026-08-26). Veredicto: arquitectura
> muy buena, pero el "audio real" era en realidad **TTS Piper de una sola voz**, y la metadata
> (`accent`/`speaker_count`/`noise`/`connected_speech`) podía generar **evidencia pedagógica falsa**
> en el Student Model. V1.14 añade una capa de **AudioRealization** + **Evidence Integrity** y hace
> que el **selector consuma de verdad el Student Model**, sin rehacer V1.13.

### 27.1 Modelo de realización del audio
- **`services/listening.py`**: `AUDIO_TYPES` (`tts`/`recorded`/`mixed`/`synthetic_multispeaker`/
  `real_world`), `realized_vector` (qué factor realiza el audio servido), `realization_status`
  (`declared`/`realized`/`verified`), `realized_difficulty`, `realization_gap_factors` y
  `subskill_realization_gap` (mapa `SUBSKILL_REALIZATION_FACTOR`).
- Para una voz Piper única: `vocabulary`/`syntactic`/`length` se realizan; `speed` solo con
  `speech_rate`; `connected_speech` solo si el texto escribe la reducción; `accent`/
  `speaker_count`/`noise` no se realizan (quedan en 1).
- `audio_digest` (hash texto + velocidad + repetición) para invalidar el cache.

### 27.2 Integridad de evidencia
- `listening_diagnostic` añade `realization_gap` por sub-destreza y resumen `realization`
  (`attempts`/`verified`/`gap`). El Student Model no debe tratar como dominio real una
  sub-destreza entrenada con audio que no respalda su factor.
- `schemas/listening.py`: `ListeningQuestion` expone `audio_type`, `realized_difficulty`,
  `realization`; `ListeningSubskillOut.realization_gap`; `ListeningDiagnostic.realization`.
- `repositories/listening.py` + migración `realized_difficulty` en `listening_attempts`.

### 27.3 Selector adaptativo
- `pick_next_question(..., weak_subskills=...)` prioriza, **dentro del nivel de trabajo** del alumno,
  las sub-destrezas débiles con realización auditiva válida (no entrena `multiple_speakers` con una
  sola voz). `domain.next_question` lo alimenta con `listening_diagnostic(attempts)["weak"]`.

### 27.4 Cache de audio versionado (P1.1)
- `domain/listening.py`: `_audio_cache_dir()` → `DATA_DIR/listening/{bank_version}/{voice}` y
  `_audio_path()` → `{id}-{digest}.wav`. `scripts/generate_listening_audio.py` usa el mismo path.

### 27.5 Frontend
- `types/api.ts`: `audio_type`, `realized_difficulty`, `realization`, `realization_gap`,
  `ListeningRealizationSummary`.
- `components/ListeningPractice.tsx`: etiqueta honesta del tipo de audio (voz sintética local vs.
  grabación real), aviso cuando `realized_difficulty < difficulty`, y marca `realization_gap` en
  el diagnóstico. Estilos en `index.css`.

### 27.6 Higiene de release
- `config.py`/`README.md`/`PLAN.md`/`package.json`/`package-lock.json` → `1.14.0`; `CHANGELOG.md`
  con entrada 1.14.0. Renombrado "audio real" → "audio TTS pre-renderizado" en CHANGELOG, README,
  PLAN, RELEVO y comentarios de código.

### 27.7 Verificación
- Backend `592 tests` + `ruff` limpio; frontend `144 tests` + `tsc` OK.

### 27.8 Pendiente / siguiente incremento natural (P1/P2 de la auditoría)
- **Delayed retention** (P1.2): `immediate_accuracy` vs `delayed_accuracy` (Day 0/2/7/30).
- **True listening tasks** (P1.3–P1.8): shadowing con grabación/alineamiento, dictado real,
  varios hablantes, connected speech real, acentos reales, ruido real.
- **Audio variants / difficulty ladder** (P1.9): variantes de un mismo contenido (slow/clean →
  natural → fast → noise → accent).
- **V1.15** — Speaking 3.0 sobre el mismo Student Model: ver sección 28.

## 28. HECHO (commiteado) — V1.15: Speaking 3.0

> **Origen.** `agentes/pedagogia/p9-speaking-3.0.md`. El speaking ya tenía un rubric determinista
> (fluency/grammar/lexical/pronunciation/coherence) y evidencia por intento, pero **no medía la
> evolución longitudinal por criterio** (a diferencia de `listening_diagnostic`), ni contemplaba la
> **interacción** como dimensión. V1.15 añade `speaking_diagnostic` espejo del de listening, integra
> `interaction` como séptimo criterio y expone el diagnóstico en el Student Model y en el frontend.

### 28.1 Diagnóstico longitudinal por criterio (S1)
- **`services/speaking.py`**: `speaking_diagnostic(evidence_rows)` agrupa por criterio
  (`attempts`/`mean`/`min`/`max`/`review_due`), deriva `weak` (`mean < 0.7`) y `recommendation`
  (criterio con menor media), y `trend` global sobre las filas `overall`/`overall_mean`.
  Umbrales `SPEAKING_WEAK_THRESHOLD`/`SPEAKING_MIN_ATTEMPTS`/`SPEAKING_TREND_WINDOW`.
- **`schemas/academy.py`**: `SpeakingCriterionOut`, `SpeakingTrend`, `SpeakingDiagnostic`.
- **`domain/academy.py`**: `get_speaking_diagnostic(user_id)` + puente de criterios de speaking
  como `subskills` en `_annotated_profile` (espejo de listening).
- **`routers/academy.py`**: `GET /api/academy/speaking/diagnostic`.

### 28.2 Criterio `interaction` (S2)
- **`services/speaking.py`**: `SPEAKING_CRITERIA` pasa a 7 (`interaction`), `CRITERION_WEIGHTS`
  rebalanceado (`interaction` 0.05); `score_speaking` trata `interaction` como `None` cuando no es
  observable (read-aloud).
- **`services/speaking_llm.py`**: `build_speaking_prompt` pide `interaction`, `parse_speaking_evidence`
  lo extrae, `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` lo incluye.

### 28.3 Frontend (S3)
- **`types/api.ts`**: `SpeakingCriterionProgress`, `SpeakingTrend`, `SpeakingDiagnostic`.
- **`api/academy.ts`**: `getSpeakingDiagnostic(userId)`.
- **`components/SpeakingDiagnostic.tsx`**: desglose por criterio, tendencia global y puntos a
  revisar. Integrado en `App.tsx` (panel de insights). Estilos en `index.css`.

### 28.4 Higiene de release
- `config.py`/`package.json` → `1.15.0`; `CHANGELOG.md` con entrada 1.15.0; `PLAN.md`,
  `PLAN-ETAPA-PEDAGOGICA.md` y `ARQUITECTURA.md` actualizados.

### 28.5 Verificación
- Backend `602 tests` + `ruff` limpio; frontend `145 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 28.6 Pendiente / siguiente incremento natural
- **Writing 3.0** sobre el mismo Student Model (espejo del patrón listening/speaking).
- Retomar los **P1 de listening** de la auditoría V1.14: delayed retention (P1.2), shadowing real
  (P1.3), dictado real, varios hablantes, acentos y ruido reales, variantes de dificultad.

## 29. HECHO (commiteado) — V1.16: Speaking Assessment & Evidence 2.0

> **Origen.** Auditoría externa de V1.15. Veredicto: arquitectura 9.3/10, pero **validez
> pedagógica ~7.5–8/10** — el "Longitudinal Speaking Competence" seguía siendo un agregador
> `mean/min/max + trend`, no un modelo de competencia, y varios criterios eran demasiado toscos.
> V1.16 se divide en **6 piezas (S1–S6)** más **3 bloques de cierre** ejecutados con subagentes.
> Filosofía intacta: el LLM sigue siendo **solo extractor de evidencia**; todo el scoring es
> determinista; un criterio no observado NO se inventa (`score=None`).

### 29.1 S1 — task_achievement continuo + GrammarEvidence 2.0 (P0-1, P0-2, P2)
- `services/speaking.py`: docstrings "6→7 dimensiones"; `TASK_SUBDIM_WEIGHTS` (task_completion/
  task_relevance/task_coverage/task_appropriateness) + `_task_achievement_score` (graduado, con
  fallback binario `task_achieved`); `_GRAMMAR_PENALTY_MINOR/MAJOR/CRITICAL` + `_grammar_score`
  (severidad en vez de `1 - 0.25·errores`).
- `services/speaking_llm.py`: extrae `grammar_error_details` (type + severity) y las 4
  sub-dimensiones de tarea.

### 29.2 S2 — SpeakingTaskProfile + dificultad declared/realized/verified + pesos por task_type (P0-1)
- `services/speaking.py`: `SpeakingTaskProfile` (task_type, cefr_target, duration_target,
  difficulty_vector, `difficulty`), `TASK_TYPES`, `SPEAKING_DIFFICULTY_FACTORS`,
  `CONVERSATIONAL_TASK_TYPES`, `difficulty_from_vector`, `weights_for_task_type`, `realized_vector`,
  `realized_difficulty`, `realization_gap_factors`; `scores_from_evidence(..., task_type=...)`
  ajusta pesos; `evidence_from_speaking(..., difficulty=...)` registra la dificultad.
- `schemas/academy.py` + `domain/academy.py` + `routers/academy.py`: `task_type`, `difficulty`,
  `difficulty_vector`, `expected` propagados.

### 29.3 S3 — LexicalEvidence 2.0 + FluencyEvidence 2.0 (P1-2, P1-3)
- Léxico: TTR puro → MSTTR por segmentos + `range` (mínimo de tipos) + sophistication/precision/
  collocations del LLM (`LEXICAL_SUBDIM_WEIGHTS`, `_msttr`, `lexical_evidence`, `_lexical_score`).
- Fluidez: `fluency ≠ speed` — bandas CEFR de WPM (`_speech_rate_score`) + smoothness/rhythm del
  LLM (`FLUENCY_SMOOTHNESS_WEIGHT`/`FLUENCY_RHYTHM_WEIGHT`, `_fluency_score`).

### 29.4 S4 — InteractionEvidence 2.0 + pronunciación integrada (P1-4, P1-5)
- `INTERACTION_SUBDIM_WEIGHTS` (5 sub-dimensiones semánticas del LLM) + `_interaction_score`.
- `expected` integra `pronunciation` en flujo libre (solo si hay referencia; sin `expected` sigue
  `observed=false`).

### 29.5 S5 — Student Model ownership del diagnóstico (P1-6, P1-7)
- `speaking_diagnostic` pasa de `mean/min/max` a **vista** sobre señales del Student Model:
  `recent_score` (EMA α=0.5), `lifetime_score`, `confidence`, `stability`, `review_due` por
  olvido/fallo reciente/decaimiento (`_ema`, `SPEAKING_EMA_ALPHA`). `SpeakingCriterionOut` y
  `SpeakingDiagnostic.overall_recent` ampliados.

### 29.6 S6 — Speaking level continuo + Speaking Journey (CEFR)
- `services/speaking.py`: `speaking_level` (nivel continuo `numeric = 1.0 + 5.0·score` + confianza)
  y `speaking_journey` (steps cronológicos con nivel + confianza).
- `schemas/academy.py`: `SpeakingLevelOut`, `SpeakingJourneyStep`, `SpeakingJourneyOut`.
- `domain/academy.py`: `get_speaking_level`, `get_speaking_journey`.
- `routers/academy.py`: `GET /api/academy/speaking/level`, `GET /api/academy/speaking/journey`.

### 29.7 Tres bloques de cierre (subagentes)
- **InteractionEvidence objetiva** (P1-4): `services/interaction.py` (puro: `interaction_evidence`
  → turn_balance/avg_response_latency_ms/turn_completion/student_turns/assistant_turns/
  interruptions, con umbrales nombrados); fusión objetiva+semántica en `_interaction_score` vía
  `INTERACTION_OBJECTIVE_WEIGHT=0.5` (clave `evidence["interaction_objective"]`, backward-compatible);
  columnas `duration_ms`/`latency_ms` en `messages` (migración idempotente); telemetría TTFB/duración
  en `POST /api/chat/stream`; `GET /api/conversations/{id}/interaction`.
- **Speaking Assessment 1.0**: instrumento `curriculum/speaking_assessment.json` (4 partes:
  interview → individual task → interaction → follow-up); tabla trazable
  `speaking_assessment_sessions`; `services/speaking_assessment.py` (`load_speaking_assessment`,
  `assessment_parts`, `aggregate_assessment` — reutiliza `speaking_level`+`speaking_diagnostic`);
  dominio + endpoints `/api/academy/speaking/assessment/{start,part,finish}` y
  `GET /api/academy/speaking/assessment/{session_id}`.
- **Frontend**: tipos + API (`getSpeakingLevel`/`getSpeakingJourney`), `utils/speaking.ts`
  (`numericToCefr`, `formatConfidence`, `formatTrendDelta`, `nextFocus`, `criterionLabel`),
  `components/SpeakingPanel.tsx` (NEXT FOCUS + PRACTICE NOW) y `components/SpeakingJourney.tsx`
  (barra A2→B1→B2 con marcador "YOU"), CSS en `index.css`, montaje en `App.tsx`.

### 29.8 Pendiente → HECHO en V1.17
1. ✅ **UI del flujo de Speaking Assessment** — `components/SpeakingAssessment.tsx` (sección 30.1).
2. ✅ **Puente conversación→speaking** — telemetría objetiva cableada de extremo a extremo (sección 30.2).
3. ✅ **Writing 3.0** sobre el Student Model (sección 30.3). Queda **P1 de listening** (V1.14).

## 30. HECHO (commiteado) — V1.17: Speaking Assessment UI + puente + Writing 3.0

> **Origen.** Cierre de los tres incrementos naturales que dejó V1.16 (sección 29.8), lanzados
> como subagentes autocontenidos en orden: (1) la pantalla del Speaking Assessment, (2) el puente
> conversación→speaking y (3) Writing 3.0. Filosofía intacta: el LLM solo extrae evidencia; todo
> el scoring determinista; un criterio no observado no se inventa.

### 30.1 UI del flujo de Speaking Assessment (commit `012ec01`)
- `frontend/src/types/api.ts`: `SpeakingAssessmentPartInfo`, `SpeakingAssessmentPartScores`,
  `SpeakingAssessmentStart`, `SpeakingAssessmentPart`, `SpeakingAssessmentResult`,
  `SpeakingAssessmentState` (espejo de `schemas/academy.py`).
- `frontend/src/api/academy.ts`: `startSpeakingAssessment`, `submitSpeakingAssessmentPart`,
  `finishSpeakingAssessment`, `getSpeakingAssessment`.
- `frontend/src/components/SpeakingAssessment.tsx`: flujo `idle → part → result`; micrófono
  (`getUserMedia`+`MediaRecorder`+`transcribe`, `duration_seconds` con `performance.now()`) y
  entrada manual por `<textarea>` (usable sin micrófono).
- `frontend/src/utils/speaking.ts`: `formatScorePct`, `formatDurationTarget`; CSS `.speaking-assessment*`;
  montaje en `App.tsx`; tests en `utils/speaking.test.ts` y `api/academy.test.ts`.

### 30.2 Puente conversación→speaking (commit `e679300`)
- `backend/schemas/chat.py`: `duration_ms`/`latency_ms` en `ChatMessage` (persistidos vía
  `save_conversation`).
- `backend/domain/academy.py`: helper `_inject_interaction_objective`; `conversation_id` opcional
  en `submit_speaking_assessment_part` y `submit_speaking_task` → `conversations_repo.get_turns` →
  `services.interaction.interaction_evidence` → `evidence["interaction_objective"]` antes de
  `scores_from_evidence` (fusionado por `_interaction_score`).
- `backend/schemas/academy.py` + `routers/academy.py`: `conversation_id` en
  `SpeakingAssessmentPartSubmit`/`SpeakingTaskSubmitRequest` y propagación en endpoints.
- Frontend: `utils/telemetry.ts` (`turnTelemetry`), `api/chat.ts` (`conversationId`/`messageId`),
  `hooks/useChat.ts` (captura `duration_ms`/`latency_ms` del turno del alumno y envía
  `conversation_id`/`message_id` en `/api/chat/stream`).
- Tests: `test_speaking.py` (fusión objetiva+semántica, backward-compat, E2E con `conversation_id`);
  `utils/telemetry.test.ts`; `api/chat.test.ts`.

### 30.3 Writing 3.0 (commit `34e32e6`)
- `backend/services/writing.py`: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de
  `speaking.py`) sobre `WRITING_CRITERIA`, con `_ema`/`_mean_trend` y constantes
  `WRITING_EMA_ALPHA`/`WRITING_WEAK_THRESHOLD`/`WRITING_CONFIDENCE_THRESHOLD`/`WRITING_TREND_WINDOW`.
- `backend/schemas/academy.py`: `WritingCriterionOut`, `WritingTrend`, `WritingDiagnostic`,
  `WritingLevelOut`, `WritingJourneyStep`, `WritingJourneyOut`.
- `backend/domain/academy.py`: `get_writing_diagnostic`/`get_writing_level`/`get_writing_journey`;
  `backend/routers/academy.py`: `GET /api/academy/writing/diagnostic|level|journey`.
- Frontend: tipos + `getWriting*`, `utils/writing.ts` (`writingCriterionLabel`), `WritingPanel.tsx`
  + `WritingJourney.tsx`, CSS `.writing-*`, montaje en `App.tsx`; tests `test_writing.py`,
  `utils/writing.test.ts`, `api/academy.test.ts`.

### 30.4 Pendiente → HECHO en V1.18
- ✅ **P1 de listening** (auditoría V1.14): delayed retention (P1.2), dictado real (P1.4),
  shadowing real (P1.3) y escalera de variantes de velocidad (P1.9). Ver sección 31.
- ⏳ **P1.5–P1.8** (varios hablantes, connected speech real, acentos reales, ruido real) requieren
  **biblioteca de audio humano** (límite de contenido, no de código).
- ⏳ (Opcional) Integrar el **turn-taking real del chat** en la parte "Interaction" del Speaking
  Assessment.
- ⏳ **P6** (pronunciación fonémica) sigue diferido.

## 31. HECHO (commiteado) — V1.18: P1 de listening (retention + dictado/shadowing + variantes)

> **Origen.** Retoma los P1 de listening que dejó pendientes la auditoría V1.14 (§27.8), lanzados
> como subagentes autocontenidos en orden: (1) delayed retention (P1.2), (2) dictado + shadowing
> reales (P1.3/P1.4) y (3) escalera de variantes de audio (P1.9). Filosofía intacta: el LLM solo
> extrae evidencia (aquí ni siquiera puntúa); todo el scoring determinista y local (Whisper + Piper).

### 31.1 Delayed retention (P1.2) — commit `6071bca`
- `services/listening.py`: `delayed_retention(attempt_rows, now="")` (pura) — agrupa por
  `question_id`, la primera exposición es `immediate` y las re-exposiciones a ≥2 días son
  `delayed`, con buckets `0-2`/`2-7`/`7-30`/`30+` días y `retention_rate` (delayed/immediate).
  Reutiliza `services.forgetting.days_since`. Integrada en `listening_diagnostic` (kwarg `now` +
  clave `retention`).
- `schemas/listening.py`: `ListeningRetentionBucket`/`ListeningRetention` + `retention` en
  `ListeningDiagnostic`; `domain/listening.py` pasa `now=db._now()`.
- Frontend: tipos + bloque de retention en `ListeningPractice.tsx` + CSS. Tests
  `test_listening_retention.py`.

### 31.2 Dictado y shadowing reales (P1.3/P1.4) — commit `2183849`
- Migración idempotente: `task_type TEXT NOT NULL DEFAULT 'mcq'` y `score REAL` en
  `listening_attempts`; `record_attempt`/`list_attempts` las manejan.
- `services/listening.py`: `PRODUCTION_PASS_SCORE=80`, `production_score` (delega en
  `phonetics.composite_score`) y `production_reference` (`transcript → clean_transcript → script`);
  `mean_score` por sub-destreza en `listening_diagnostic`.
- `domain/listening.py`: `submit_production(user_id, question_id, transcript, task_type)` (valida
  skill, persiste `answer_index=-1` + score continuo). `routers/listening.py`:
  `POST /api/listening/dictation` y `/api/listening/shadowing`.
- Frontend: `ListeningPractice.tsx` bifurca por `skill` (dictado → textarea; shadowing →
  MediaRecorder + `transcribe(blob)`); tipos, API (`submitListeningDictation/Shadowing`) y CSS.
  Tests `test_listening_production.py` + `api/listening.test.ts`.

### 31.3 Escalera de variantes de velocidad (P1.9) — commit `26ae6c4`
- `services/listening.py`: `AUDIO_VARIANTS=("slow","normal","fast")`,
  `VARIANT_SPEED_FACTORS={slow:.75, normal:1.0, fast:1.25}`, `variant_speech_rate`,
  `variant_length_scale`, `audio_variants`, y `audio_digest(question, variant="normal")` que
  **preserva** el digest de `normal` (no invalida cache).
- `domain/listening.py`: `_audio_path(question, variant)`, `get_audio(question_id, variant)` (400
  si variante inválida), `_public` expone `variants` + `default_variant`. Router: query param
  `variant`. `schemas/listening.py`: `ListeningAudioVariant`.
- Frontend: botones Slow/Normal/Fast en `ListeningPractice.tsx` + `getListeningAudioUrl(..., variant)`.
  Tests `test_listening_variants.py` + `api/listening.test.ts`.

### 31.4 Pendiente / siguiente incremento natural
- **P1.5–P1.8** — varios hablantes, connected speech real, acentos reales, ruido real: requieren
  **biblioteca de audio humano** (grabaciones reales o sintetizador multi-voz). Límite de
  **contenido**, no de código; hoy Piper es una única voz.
- (Opcional) Integrar el **turn-taking real del chat** en la parte "Interaction" del Speaking
  Assessment (señal objetiva en vivo, no solo `conversation_id` manual).
- **P6** (pronunciación fonémica) sigue diferido.

## 32. HECHO (commiteado) — V1.19: Refresco UI profesional (frontend)

> **Origen.** Petición explícita de tomar el control de la interfaz y dejarla "100% profesional y
> más atractiva" conservando el diseño responsivo y el sistema de apariencia existente
> (`data-theme`/`data-accent`/`data-font`/`data-density` → variables CSS). Solo frontend, sin
> cambios de backend ni de lógica de negocio. Ejecutado desde un plan Cursor
> (`refresco_ui_profesional`) en vez de un subagente `agentes/*.md`.

### 32.1 Fundamento: tokens y primitivas CSS
- `index.css`: tokens `--color-surface-3` y `--shadow-card` (dark + light); escala tipográfica
  por defecto afinada (`--text-sm` 13→14px, `--text-xs` 12→12.5px); `data-font` sigue escalando
  por encima.
- Primitivas reutilizables: `.card`, `.card__header`, `.card__toggle`, `.card__icon`,
  `.card__title`, `.card__chevron`, `.card__actions`, `.card__body`, `.badge`, `.pill` y
  `.section-divider`.

### 32.2 Header
- Sticky con `backdrop-filter: blur(12px) saturate(1.4)` + fondo translúcido
  (`color-mix(in srgb, var(--color-bg) 80%, transparent)`) y borde inferior sutil.
- Alturas de control uniformes (36px) en `.icon-button`, `.hands-free-toggle` y `.model-trigger`.
- A ≤768px los controles secundarios (apariencia/ayuda) se repliegan en un menú desplegable
  (`.header-secondary` + `.header-more`) con cierre al hacer clic fuera.

### 32.3 Chat principal
- Estado vacío más rico: kicker (`empty-kicker`) + badge mayor (64px) y `active` en las
  sugerencias.
- Burbujas del tutor con avatar circular (`tutor-avatar`) en `ChatMessage.tsx`.
- Composer intacto (ya tenía foco y padding móvil); sin cambios de lógica.

### 32.4 Panel de análisis: tarjetas colapsables (mayor impacto)
- Nuevo `components/InsightCard.tsx`: cabecera con título + chevron, `aria-expanded`/
  `aria-controls`, cuerpo colapsable y slot de `actions` (p. ej. `BucketToggle`).
- `App.tsx` envuelve los 11 paneles; expandidos por defecto `ProgressDashboard`, `TodayPlan` y
  `ListeningPractice`, el resto colapsados. Los paneles internos pierden su título externo (se
  centraliza en `InsightCard`) y su "cromo" de tarjeta se neutraliza con `.card__body > section`.
- `BucketToggle` se exporta desde `ProgressDashboard` y se monta como `actions` de su tarjeta.

### 32.5 Responsive + accesibilidad
- Nuevo breakpoint `@media (max-width: 480px)`: header compacto (se ocultan labels de modo/
  modelo/manos libres/nombre), `composer` compacto y drawer de análisis a 100vw.
- `aria-expanded`/`aria-controls` en las tarjetas colapsables; `:focus-visible` y
  `prefers-reduced-motion` conservados. Breakpoints 1024/768 verificados sin roturas.

### 32.6 Verificación
- `npx tsc --noEmit` OK y `npx vitest run` → 25 archivos / 198 tests en verde. Sin tests nuevos:
  no se añadió ninguna util nueva (el colapso usa `useState` local dentro de `InsightCard`).

### 32.7 Pendiente / siguiente incremento natural
- **P1.5–P1.8** — varios hablantes, connected speech real, acentos reales, ruido real: requieren
  **biblioteca de audio humano** (grabaciones reales o sintetizador multi-voz). Límite de
  **contenido**, no de código; hoy Piper es una única voz.
- (Opcional) Integrar el **turn-taking real del chat** en la parte "Interaction" del Speaking
  Assessment (señal objetiva en vivo, no solo `conversation_id` manual).
- **P6** (pronunciación fonémica) sigue diferido.

## 33. HECHO (commiteado) — V1.20: P6 fonémica + turn-taking real + audio humano

> **Origen.** Cierra los tres incrementos naturales que dejó pendientes V1.19 (§32.7), lanzados
> como subagentes autocontenidos en orden: (1) P6 pronunciación fonémica, (2) turn-taking real del
> chat en la parte "Interaction" del Speaking Assessment y (3) infraestructura de biblioteca de
> audio humano (P1.5–P1.8). Filosofía intacta: el LLM solo extrae evidencia; todo el scoring
> determinista y local.

### 33.1 Pronunciación fonémica (P6)
- `services/phonemes.py`: `phoneme_alignment(expected, heard)` (alineación de fonemas con
  `difflib.SequenceMatcher`, espejo de `word_alignment`), `syllables(word)` (grupos vocálicos) y
  `prosody_score(expected, heard)` (proxy de ritmo por nº de sílabas).
- `services/phonetics.py::composite_score`: pesos rebalanceados `W_WORD=0.35`, `W_PHONEME=0.35`,
  `W_PHONETIC=0.15`, `W_PROSODY=0.15` (se elimina `W_CHAR`); devuelve `prosody_score` y
  `phoneme_breakdown`.
- `services/pronunciation.py`: `PRONUNCIATION_CRITERIA` pasa a 4 (añade `prosody`),
  `PRONUNCIATION_WEIGHTS` rebalanceado; `score_pronunciation`/`score_pronunciation_cefr` exponen
  `prosody`.
- `schemas/pronunciation.py`: `PhonemeSubstitution`/`PhonemeBreakdown`; `PronunciationResponse`
  con `prosody_score` + `phoneme_breakdown`.
- Frontend: tipos + `PronunciationPractice.tsx` muestra "Precisión de fonemas" y "Prosodia
  (ritmo)". Tests `test_phonemes.py`/`test_phonetics.py`/`test_pronunciation.py`/
  `test_pronunciation_academy.py`.

### 33.2 Turn-taking real del chat → Interaction
- `utils/speaking.ts`: `CONVERSATIONAL_TASK_TYPES`, `isConversationalTaskType`, `rolePlaySetup`.
- `api/academy.ts`: `submitSpeakingAssessmentPart` acepta `conversationId` opcional y lo envía
  como `conversation_id`.
- `components/SpeakingRolePlay.tsx` (nuevo): role-play en vivo dentro del assessment (`streamChat` +
  persistencia de conversación + `turnTelemetry` con `duration_ms`/`latency_ms`).
- `components/SpeakingAssessment.tsx`: bifurca por `task_type` conversacional para renderizar
  `SpeakingRolePlay`; `index.css` con `.speaking-roleplay*`. El puente backend
  (`conversation_id` → `interaction_objective`) ya existía desde V1.17.
- Tests `utils/speaking.test.ts` + `api/academy.test.ts`.

### 33.3 Infraestructura de biblioteca de audio humano (P1.5–P1.8)
- `services/audio_library.py` (nuevo): `AUDIO_LIBRARY_VERSION`, `AudioLibraryEntry`/
  `AudioLibraryManifest`, `load_manifest`, `entry_for`, `resolve_file` (rechaza rutas fuera de la
  biblioteca), `is_recorded`, `recorded_audio_path`, `library_summary`, `validate_manifest`.
- `backend/audio_library/manifest.json` (nuevo): manifest versionado vacío (límite de contenido).
- `domain/listening.py`: `audio_ready` ya no depende solo de Piper (para `recorded` basta el WAV);
  `get_audio` sirve el WAV grabado del manifest y devuelve 404 (no TTS) si falta.
- Tests `test_audio_library.py` (21 tests: manifest, resolución segura, servido y `audio_ready`).

### 33.4 Higiene de release
- `config.py`/`package.json`/`package-lock.json`/`README.md` → `1.20.0`; `CHANGELOG.md` con
  entrada 1.20.0; `PLAN.md` y este `RELEVO.md` actualizados.

### 33.5 Verificación
- Backend `755 tests` + `ruff` limpio; frontend `202 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 33.6 Pendiente / siguiente incremento natural
- **Contenido** de la biblioteca de audio humano: incorporar WAV reales (varios hablantes,
  connected speech real, acentos reales, ruido real) y añadir sus entradas al manifest. La
  infraestructura ya está lista.
- (Opcional) Ajustar la UI de variantes de velocidad (`ListeningPractice.tsx`) para no mostrar la
  escalera slow/normal/fast en ítems `recorded` (su velocidad es la real, no sintetizable).

## 34. HECHO (commiteado) — V1.23: UI 2.0 (incremento 1)

> **Origen.** Adopción de un *design system* real (Tailwind CSS v4 + shadcn/ui + Motion) para
> sustituir el CSS custom (~6.450 líneas) por primitivas y microinteracciones. Cambio solo-frontend.

- **Stack de diseño**: `tailwindcss` + `@tailwindcss/vite`, `motion`, `lucide-react` y dependencias
  shadcn; alias `@/*` → `src/*`; `components.json` y `lib/utils.ts` (`cn`).
- **Tokens**: `index.css` con tokens semánticos shadcn mapeados al sistema de apariencia; `legacy.css`
  aislado en `@layer base`.
- **Primitivas**: `Button`, `Card`, `Badge`, `Progress` + `SkillBar`, `LevelBadge`, `JourneyNode`,
  `Milestone`.
- **Reestilizados**: `AppShell`/`Header`/`Navigation` (nav inferior móvil + píldora animada), `Home`,
  `Course`.
- **Higiene**: versión → `1.23.0`.

## 35. HECHO (commiteado) — V1.24: Analysis redesign + responsive 100%

> **Origen.** El panel ANALYSIS apilaba 10 acordeones colapsables y cortaba texto en el drawer
> estrecho; el usuario pidió rediseño total por pestañas + pasada responsive completa de la app +
> tests visuales. Se añaden las premisas 19–21.

### 35.1 Panel ANALYSIS por pestañas
- **`components/AnalysisPanel.tsx`** (nuevo): contenedor de 7 pestañas (Overview, Today, Profile,
  Speaking, Writing, Assessment, Tutor) con iconos `lucide-react`, indicador activo animado
  (`layoutId` de Motion), transición de contenido (`AnimatePresence`) y scroll vertical propio por
  pestaña (sin `text-overflow: ellipsis` ni `overflow: hidden`). Speaking agrupa Diagnostic+Panel+
  Journey; Writing agrupa Panel+Journey (se elimina el título "Speaking" duplicado).
- **`app/PracticeView.tsx`**: sustituye las 10 `InsightCard` por `<AnalysisPanel />`.
- **`components/InsightCard.tsx`**: eliminado (quedó huérfano, verificado con `rg`).
- Accesibilidad: `role="tablist"/"tab"/"tabpanel"`, `aria-selected`, `aria-controls`.

### 35.2 Pasada responsive completa
- `ProgressScreen`, `ListeningPractice`, `ReadingPractice`, `PronunciationPractice`,
  `SpeakingAssessment`, `SpeakingRolePlay`, `SettingsDialog`, `ProfileDialog`, `HelpDialog`,
  `Composer`, `HandsFreeToggle`: correcciones de overflow, `flex-wrap`, `min-w-0`, tap targets
  ≥40px (`min-h-10`), pestañas con scroll horizontal. Sin tocar `legacy.css` (usando utilidades
  Tailwind con sufijo `!` donde el cascade legacy lo exigía).

### 35.3 Tests visuales Playwright
- **`@playwright/test`** (devDependency) + **`playwright.config.ts`** con 3 proyectos (desktop
  1280×800, tablet 768×1024, móvil 390×844) y `webServer` que reutiliza el dev server de Vite.
- **`tests/visual/smoke.spec.ts`**: recorre Home, Course, Progress, Chat (+ panel ANALYSIS abierto)
  y Learn, capturando un screenshot por ruta en `tests/visual/screenshots/<proyecto>/`.
- **`scripts/visual.ps1`** + script npm **`test:visual`** (`playwright test`).
- `.gitignore`: excluye `playwright-report/`, `test-results/`, `.artifacts/` y `screenshots/`.

### 35.4 Verificación
- Frontend `206 tests` + `tsc` OK; `playwright test` → 3 passed (18 screenshots). Backend sin cambios.

### 35.5 Pendiente / siguiente incremento natural
- **Fases 3–6 del rediseño UI 2.0**: listening (entorno auditivo), speaking (estudio de conversación),
  progress (dashboard pedagógico), móvil específico y **retirada de `legacy.css`**.
- **Contenido** de la biblioteca de audio humano (grabaciones reales).

## 36. HECHO (commiteado) — V1.25: paneles del chat redimensionables + persistentes

> **Origen.** Los tres paneles del CHAT (conversaciones, zona central y Análisis) ya tenían
> infraestructura de redimensionado (`ResizeHandle` + `layout.sidebarWidth`/`rightWidth` persistido
> en settings por usuario), pero el asa era un carril de 6px transparente casi invisible, no era
> accesible y persistía en cada `pointermove` (spam de `PUT`). Se mejora la usabilidad, la
> accesibilidad y la eficiencia de la persistencia.

### 36.1 Asa visible y accesible
- **`components/ResizeHandle.tsx`** reescrito con Tailwind: asa de 8px (`w-2`) con *grip* central
  visible (`w-0.5 bg-border`, `bg-primary` al hover/foco vía `group`), `cursor-col-resize`,
  `touch-none`, `hidden lg:flex` (oculta en móvil/tablet donde los paneles son drawers).
- Añadidos `role="separator"`, `aria-orientation="vertical"`, `aria-valuenow/min/max` y soporte de
  teclado (←/→ = ±24px). `PracticeView` pasa `value`/`min`/`max` desde `layout` y los límites
  (`SIDEBAR_MIN/MAX`, `RIGHT_MIN/MAX`).

### 36.2 Persistencia eficiente por usuario
- **`hooks/useChat.ts`**: `setLayout` actualiza el estado inmediatamente (preview en vivo) pero
  persiste con **debounce de 400ms** (`layoutPersistTimer`), de modo que un arrastre produce un único
  `PUT /api/settings` en lugar de uno por movimiento. La carga inicial (`parseLayout`) no cambia.

### 36.3 Limpieza CSS
- **`styles/legacy.css`**: eliminadas las reglas huérfanas de `.resize-handle` (base + `display:none`
  en `≤1024px`); se conserva `body.is-resizing`.

### 36.4 Test visual
- **`tests/visual/resize.spec.ts`** (nuevo): normaliza el ancho al mínimo por teclado, lo agranda con
  flechas, comprueba el cambio y verifica la persistencia tras `reload`. Solo desktop (skip en
  móvil/tablet).

### 36.5 Verificación
- Frontend `206 tests` + `tsc` OK; `playwright test` → 4 passed + 2 skipped (18 screenshots +
  redimensionado). Backend sin cambios funcionales (solo `VERSION` → `1.25.0`).

### 36.6 Pendiente / siguiente incremento natural
- Ver **sección 37** (consolidado de todos los próximos incrementos).

## 37. PRÓXIMOS INCREMENTOS (consolidado)

> **Punto de partida del siguiente chat.** Todo lo que queda por hacer, en orden sugerido. La
> regla sigue siendo la premisa 6 (poco a poco, un incremento a la vez) y la 5/7/8 (subagentes
> autocontenidos, relevo al saturar). Cada incremento cierra con: build + tests frontend
> (`npm test`, `tsc`) + backend (`pytest`, `ruff`) + Playwright (`npm run test:visual`) + bump de
> versión en `config.py`/`package.json`/`package-lock.json`/`README.md` + `CHANGELOG` + esta sección.

### 37.1 HECHO (V1.26) — Rediseño UI 2.0 fases 3–6 (solo frontend)
- ✅ **Fase 3** — `features/listening/ListeningPractice.tsx`: entorno auditivo inmersivo (reproductor
  con onda Motion, variantes 0.8x/1.0x/1.2x). Reutiliza `SkillBar`/`Badge`/`Card`.
- ✅ **Fase 4** — `features/speaking/*` + `PronunciationPractice`: "estudio de conversación" (mic que
  pulsa, feedback de fluidez/coherencia con `SkillBar`/`Badge`).
- ✅ **Fase 5** — `features/progress/ProgressScreen.tsx`: dashboard pedagógico limpio.
- ✅ **Fase 6** — Móvil específico (tap targets ≥40px, sin overflow) + poda de `legacy.css`
  (~1.400 líneas huérfanas retiradas). `legacy.css` NO se retira aún: quedan en uso los bloques de
  chat/shell/header/composer y `.journey-*` (fuera del scope de este incremento).
- Briefing: `agentes/ui2/u1-rediseno-ui2-fases3-6.md`. Ver CHANGELOG 1.26.0.

### 37.2 HECHO (V1.27) — Code-splitting (frontend)
- ✅ Dividido por rutas con `React.lazy`/`Suspense` (`HomeScreen`, `CourseScreen`, `ProgressScreen`,
  `PracticeView`) + `AnalysisPanel` diferido. Chunk inicial **537 kB → 425 kB** (gzip 134 kB) y ya
  sin aviso de bundle >500 kB.
- Briefing: `agentes/ui2/u2-code-splitting.md`. Ver CHANGELOG 1.27.0.

### 37.3 PARCIAL — Contenido: biblioteca de audio humano (P1.5–P1.8)
- ✅ **Código hecho**: la infraestructura (manifest + resolución + servido + validación), el
  importador `backend/scripts/import_audio.py`, la escalera de velocidad oculta en ítems `recorded`
  (`ListeningPractice.tsx`) y, desde **V1.35**, la **gestión en-app** (Ajustes → Audio) para
  subir/reemplazar/quitar WAV con metadatos.
- ⏳ **Contenido pendiente del usuario**: incorporar **WAV reales** de varios hablantes (connected
  speech real, acentos reales, ruido real). Ahora se hace desde la propia app: **Ajustes → Audio →
  subir WAV** (sin terminal). El agente **no** puede fabricar audio real (premisa 2/21).
- **Notas**: el corpus ya reserva 9 slots (`l15`–`l23` → `audio-l15`…`audio-l23`) con `transcript`,
  `clean_transcript`, `speech_rate`, `noise_level` y `duration` declarados en
  `services/listening.py::QUESTION_BANK`. Los WAV deben ser **PCM sin comprimir** (el backend usa
  `wave`; no hay `ffmpeg`). Subir un WAV convierte el ítem de TTS a grabado automáticamente (el
  manifest es la fuente de verdad); borrarlo lo revierte. Empezar por el subconjunto que el usuario
  aporte.

### 37.4 (Diferido por decisión) Vercel / despliegue
- **Vercel** se barajó para la **UI** (previews, hosting estático), **no** para sustituir el backend
  (que es y seguirá siendo 100% local). Aún no se ha ejecutado; se retomará cuando el usuario lo pida.
- El backend local implica que Vercel solo serviría el frontend; las llamadas `/api` seguirían
  apuntando a `127.0.0.1:8000` (requiere decidir CORS/entorno, `ALLOWED_ORIGINS`/`ALLOWED_ORIGIN_REGEX`).

### 37.5 Notas de contexto para el nuevo chat
- Versión estable actual: **2.0.0** (Beta 1.0; todo verificado: backend 926 tests, frontend 240 tests,
  launcher 64 tests, `ruff` limpio, `tsc`/`build` OK, `check_release_consistency` OK; CI ampliado
  con jobs `content-validation` y `playwright`; gates de salida 10/10 en `docs/BETA_GATES.md`).
- Pendiente: **37.3 contenido** (requiere WAV reales del usuario; el pipeline de grabación,
  importación masiva y QA acústica ya están listos en V1.36–V1.37) y **37.4 Vercel** (diferido por
  decisión).
- Premisas relevantes: 19 (análisis por pestañas), 20 (responsive 100% + tests visuales), 21 (IA
  evidencia / Mastery Engine decide), 22 (paneles redimensionables persistentes).

### 37.6 HECHO (V1.29) — Fiabilidad LAN/HTTPS + audio móvil (P0) + launcher [commit `cb4eec5`]
- ✅ `utils/browserCapabilities.ts` + `useAudioCapabilities.ts` (detección reactiva de capacidades
  de audio + `MicUnavailableNotice`), `/api/network` (`hostname`/`local_url`), HTTPS en la LAN
  (`@vitejs/plugin-basic-ssl`), launcher con estado en color + reinicio + reloj.

### 37.7 HECHO (V1.30) — FASE 1: LAN + Mobile 100%
- ✅ mDNS real (`local_url_available` en `/api/network` + `mdns_available()` en launcher),
  recuperación de permisos (`watchMicrophoneAvailability`), test de micrófono con medidor de nivel
  (`MicrophoneTest.tsx` + `utils/microphoneLevel.ts`), tarjeta de conexión QR (`ConnectDeviceCard`),
  página `/help/connect` (`features/help/ConnectHelp.tsx`), E2E móvil (`tests/visual/mobile.spec.ts`)
  y `docs/DEVICE_MATRIX.md`.

### 37.8 HECHO (V1.31) — FASE 2: Adaptive Engine 2.0
- ✅ Priority Engine (`services/adaptive.py`: `priority_signals`/`priority_score`/`explain_priority`)
  + `signals`/`why` en `NextBestActivityOut` + "Why this activity?" en `NextBestCard`.

### 37.9 HECHO (V1.32) — FASE 3: Curriculum 2.0
- ✅ `curriculum/cefr_descriptors.json` + `services/cefr_descriptors.py` (escalera Pre-A1→C2 con
  bandas "plus" + Can-Do por 9 dimensiones), `/api/academy/cefr-ladder`, visualización en `CourseScreen`.

### 37.10 HECHO (V1.33) — FASE 4: Listening 2.0
- ✅ `listening_resilience` (precisión por condición de escucha: clara→natural→conectada→rápida→
  ruido→acentos) + `context` del corpus (`LISTENING_CONTEXTS` + `AudioLibraryEntry.context`) y
  `resilience` en `ListeningDiagnostic`.

### 37.11 HECHO (V1.34) — FASE 5: Speaking 2.0
- ✅ `pronunciation` marcado como `proxy` (`PROXY_CRITERIA`), `interaction_quality` por
  sub-dimensión (initiation/response/follow_up/repair/turn_taking), `conversation_endurance`
  (hitos 30s–180s) + `/api/academy/speaking/endurance`, campo LLM `initiation`, y render en
  `SpeakingDiagnostic` (insignia "proxy" + desglose + hitos). Test visual `tests/visual/speaking.spec.ts`.

### 37.12 HECHO (V1.35) — Gestión en-app de la biblioteca de audio humano
- ✅ Subir/reemplazar/quitar WAV desde **Ajustes → Audio** (`components/AudioLibrary.tsx`): preview
  del WAV, edición de metadatos (transcripción, hablante, acento, CEFR, velocidad, ruido, género,
  región, contexto), subida multipart y borrado.
- ✅ Router `/api/audio-library` (`routers/audio_library.py`): `GET /slots`, `POST /upload`,
  `GET /{audio_id}/audio` (preview) y `DELETE /{audio_id}`.
- ✅ `is_recorded` ahora consulta el manifest (switch runtime TTS↔grabado sin tocar el banco de
  preguntas); `write_entry`/`remove_entry`/`wav_probe_bytes` en `services/audio_library.py`; y
  `domain/listening.py` expone `audio_type="recorded"` cuando el manifest respalda el ítem.
  Ver CHANGELOG 1.35.0.

### 37.13 HECHO (V1.36) — Audio Corpus 1.0 (autorar + pipeline)
- ✅ **Corpus versionado en JSON** (`backend/curriculum/listening_corpus.json`, versión `1.0.0`): 40
  ítems grabables (`c001`–`c040`, A1/A2/B1/B2) con la matriz multidimensional del auditor (nivel ×
  hablante × contexto × condiciones de escucha): `gender`, `age_band`, `region`, `accent`,
  `speaker_count`, `noise_level`, `speech_rate`, `spontaneity`, `recording_environment`, `overlap`,
  `connected_speech`, `prosody`, `task_type`, `cefr` y `context`. Diversidad real: 10 hablantes, 8
  acentos/regiones, 8 contextos y 6+ tipos de tarea.
- ✅ **Loader del corpus** (`services/listening.py`): `_LEGACY_BANK` (l1–l23) + `_load_corpus_items()`
  → `QUESTION_BANK` fusionado; los ítems del corpus son `tts` hasta que el manifest respalda su
  `audio_id`. `LISTENING_BANK_VERSION` → `4.0.0`. `curriculum.py` excluye `listening_corpus.json`
  de los niveles (`_NON_LEVEL_FILES`).
- ✅ **Pack de grabación** (`backend/scripts/generate_recording_pack.py`): CSV de guiones por hablante
  + `recording_pack_summary.json` con el objetivo A1 30–40 / A2 40–50 / B1 60–80 / B2 60–80 y la
  convención `{cefr}/{speaker_id}/{audio_id}.wav`.
- ✅ **Importación masiva** (`backend/scripts/import_audio.py --batch`): localiza los WAV por
  convención, mide su duración real y rellena el manifest (`entry_from_item` mapea los metadatos
  ampliados; `cefr` deriva del `level`).
- ✅ **Higiene de release** (`scripts/check_release_consistency.py`): comprueba backend/frontend/
  README/CHANGELOG/PLAN contra `config.py::VERSION`; añadido como job de CI. `PLAN.md` corregido
  (dejó de declarar `1.34.0`). Ver CHANGELOG 1.36.0.
- ⏳ **Pendiente del usuario**: grabar los WAV reales (usar el CSV como guion) e importarlos con
  `import_audio.py --batch` o desde **Ajustes → Audio**. El agente no fabrica audio real (premisa 2).

### 37.14 HECHO (V1.37) — Audio QA + Content Audit
- ✅ **QA acústica** (`services/audio_library.py`, solo stdlib): `acoustic_metrics` (decodifica PCM
  con `array`/`struct`) calcula `peak`, `RMS`, `clipping %`, `DC offset` y `silence ratio`, y
  `classify_quality` emite `PASS`/`WARNING`/`REJECT`. `wav_quality_bytes`/`wav_quality` devuelven el
  panel completo (formato, sample rate, canales, duración + métricas + `grade`). `POST /upload`
  devuelve el panel "AUDIO QUALITY" y aplica límites de MIME (`_WAV_MIME`), duración
  (`MAX_AUDIO_DURATION_SECONDS`) y tamaño (`MAX_AUDIO_BYTES` via `read_audio_limited`).
- ✅ **Content integrity check** (`services/content_validation.py` +
  `scripts/content_validation.py`): recorre `question → audio_id → manifest → WAV → metadata →
  CEFR → difficulty → subskills` y emite el "CONTENT INTEGRITY CHECK" (ítems, grabados vs TTS,
  referencias rotas, ids duplicados, transcripciones ausentes, desfase CEFR y desfase de duración).
  Sale con código 1 si hay issues `error` (guard de CI).
- ✅ **Content Audit Dashboard** (frontend): pestaña "Content audit" en `AudioLibrary.tsx` con
  resumen (ítems/grabados/TTS) e issues por severidad.
- ✅ **Candado admin (PIN local)** (`dependencies.require_admin` + `config.ADMIN_PIN`): protege
  `POST /upload`, `DELETE /{audio_id}`, `GET /{audio_id}/audio` y `GET /audit`; `GET /status`
  expone `admin_required`. UI con PIN y desbloqueo en `AudioLibrary.tsx`. Sin OAuth/cloud.
- ✅ **Backup + auditoría de borrado** (`services/audio_library.py`): `write_entry`/`remove_entry`
  registran en `audit.log` (JSONL) y `_backup_entry` copia el WAV + su entrada a `_backups` antes
  de borrar.
- ✅ **CI**: jobs `content-validation` (script de integridad) y `playwright` (E2E visual) añadidos a
  `.github/workflows/ci.yml`. Ver CHANGELOG 1.37.0.

### 37.15 HECHO (V1.38) — Course Engine + progreso visible "¿dónde estoy?"
- ✅ **Course Engine** (`services/course.py`): secuenciación explícita Course→Unit→Lesson→Practice→
  Assessment→Review→Mastery a partir de `curriculum/a1.json` (y a2/b1/b2). `gate_objective_ids`
  identifica los objetivos evaluables que actúan como gates; `objective_gated_status` emite
  `mastered`/`review`/`available`/`locked` (gating lineal, premisa 21); `unit_sequence` construye la
  estructura de unidades/lecciones con progreso y estado (`done`/`current`/`locked`).
- ✅ **Posición en el curso** (`current_position` + `course_map`): calcula la unidad y lección
  actuales, `mastered/total`, progreso y `complete`.
- ✅ **Endpoint** `GET /api/academy/course/{level_id}` (`routers/academy.py` → `CourseMapOut`),
  protegido por `enrollment_blocked`; `domain/academy.py::_objective_state` consume ahora el estado
  gated de `course_svc` (fuente única de gating) y se añadió `get_course_map`.
- ✅ **Frontend** (`CourseScreen.tsx` + `api/academy.ts` + `types/api.ts` + `utils/i18n.ts`): barra
  de unidades (✓/●/🔒) y lección actual "¿dónde estoy?" con el porcentaje del nivel.
- ✅ **Tests**: `backend/tests/test_course.py` (gates, gating de objetivos, secuencia de unidades,
  posición, forma del course map y endpoint) + ajuste en `test_academy.py` (segundo objetivo `locked`).
  Ver CHANGELOG 1.38.0.

### 37.16 HECHO (V1.39) — Mastery 2.0 (MasteryRecord transversal + CEFR readiness)
- ✅ **`MasteryRecord` transversal** (`services/mastery.py`): una sola abstracción de dominio para
  las 9 destrezas (`MASTERY_SKILLS`: vocabulary/grammar/pronunciation/listening/speaking/reading/
  writing/interaction/mediation). Cada registro porta `score`, `confidence`, `evidence_count`,
  `retention`, `stability`, `review_due`, `review_in_days`, `transfer_count`, `novel_count` y
  `stage`. `mastery_records()` devuelve siempre las 9 destrezas (sin datos → `acquire`).
- ✅ **Curva de olvido conectada a todo el currículo**: `review_interval_days(score, confidence)`
  (SRS corto derivado de `forgetting.stability_days`) y `mastery_stage(...)` (timeline
  acquire→practice→retrieve→transfer→novel→retention).
- ✅ **CEFR readiness sin media simple** (`services/adaptive.py`): `readiness_band(overall, ready)`
  emite `developing`/`approaching`/`ready`; `readiness()` ahora incluye `band`. Combina mastery +
  evidencia + transfer + retención + confianza + gates mínimos.
- ✅ **Exposición**: `MasteryRecordOut` + `StudentModelOut.mastery`; `/api/academy/student-model`
  devuelve la vista transversal y la banda; `/api/profile` hereda `band` vía `ReadinessOut`.
- ✅ **UI de progreso**: banda "B1 developing" (con % secundario) en `ProgressScreen`, `HomeScreen`,
  `TodayPlan`, `LearningProfile` y `CourseScreen`; "Repasar en N días" desde el `MasteryRecord` en
  el detalle de destreza de `ProgressScreen`.
- ✅ **Tests**: `tests/test_mastery.py` (9 destrezas en orden, intervalos de repaso, timeline,
  anotación desde perfil) + `tests/test_adaptive.py` (`readiness_band`). Ver CHANGELOG 1.39.0.

### 37.17 HECHO (V1.40) — Speaking 3.0 (escenarios comunicativos + proxy honesto)
- ✅ **Catálogo de escenarios comunicativos** (`curriculum/speaking_scenarios.json` + nuevo
  `services/speaking_scenarios.py`): 8 escenarios (Restaurant, Doctor, Travel, Telephone,
  Work meeting, Small talk, Problem solving, Interview) versionados como contenido fuera del código.
  Cada escenario declara `communicative_objective` y las métricas que observa
  (`task_completion`/`interaction`/`fluency`/`repair`/`turn_taking`), mapeadas a los criterios del
  rubric ya existentes (`services/speaking` + `services/interaction`). `validate_scenarios()`
  comprueba `task_type` ∈ `TASK_TYPES` y métricas ∈ `SCENARIO_METRICS`.
- ✅ **Endpoint** `GET /api/academy/speaking/scenarios` (`routers/academy.py` →
  `SpeakingScenariosOut`/`SpeakingScenarioOut`; `domain/academy.py::list_speaking_scenarios`).
  Registrado `SPEAKING_SCENARIOS_VERSION = "1.0.0"` y el archivo en `_NON_LEVEL_FILES`.
- ✅ **UI de escenarios** (`features/speaking/SpeakingScenarios.tsx`): pestaña "Speaking scenarios"
  en el panel de análisis; tarjetas con título/nivel/categoría/objetivo/métricas; al practicar
  reutiliza `SpeakingRolePlay` (telemetría de turnos `duration_ms`/`latency_ms` → señal objetiva de
  interacción) y al terminar muestra objetivo + métricas observadas.
- ✅ **Honestidad del proxy de pronunciación** (`SpeakingDiagnostic.tsx`): el criterio
  `pronunciation` (`proxy` desde V1.34) muestra ahora "Confidence: alta/media/baja · automated
  proxy" y una nota que distingue fonética real de la alineación speech/transcript.
- ✅ **Tests**: `tests/test_speaking_scenarios.py` (catálogo 8 escenarios, métricas canónicas,
  `validate_scenarios` vacío, `get_scenario` por id y endpoint). Ver CHANGELOG 1.40.0.

### 37.18 HECHO (V1.41) — Beta Hardening (backup/seguridad LAN/a11y/performance)
- ✅ **Backup/restore/export local** (`services/backup.py` + `routers/system.py`): ZIP determinista
  del estado local (SQLite `tutor.db` + `audio_library/` con `backup.json` de metadatos). Endpoints
  admin: `GET /api/system/backup/status`, `POST /api/system/backup`, `GET /api/system/backups`,
  `GET /api/system/backup/export`, `POST /api/system/restore`. `restore_backup` valida el ZIP,
  exige `data/tutor.db`, checkpoint de WAL y limpia `-wal`/`-shm`; límite 512 MB y MIME ZIP.
- ✅ **Auto-backup diario** (keep 7): `_auto_backup_daemon` en el lifespan de `main.py` crea una
  copia si no hay ninguna del día UTC y poda a `KEEP_BACKUPS = 7` (nombres con microsegundos).
- ✅ **Seguridad LAN** (`security.py::SecurityMiddleware`, ASGI puro): `origin_allowed` (rechaza
  métodos no seguros con origen no permitido, CSRF-like) y `_rate_limit_ok` en memoria por IP con
  límites estrictos en endpoints sensibles; registrado en `main.py`.
- ✅ **Panel de backup en UI** (`components/BackupPanel.tsx` + `api/system.ts`): Ajustes → Sistema,
  crear/listar/descargar/restaurar usando el PIN de administración (`X-Admin-Pin`).
- ✅ **A11y**: skip-link al contenido principal (`AppShell` + `.skip-link`) y sincronización de
  `document.documentElement.lang` con el idioma (`hooks/useI18n.tsx`).
- ✅ **Matriz de dispositivos** (`docs/DEVICE_MATRIX.md`): ampliada a PC/Android/iPhone/iPad con
  columnas HTTPS/mDNS/Mic/Audio/Listening/Speaking/Recuperación.
- ✅ **Performance**: `manualChunks` en `vite.config.ts` (React, `motion`, `lucide-react`), el
  bundle principal baja ~505→393 kB (gzip ~160→124 kB) y desaparece el aviso de chunk grande.
- ✅ **Tests**: `tests/test_backup.py` (create/list/restore roundtrip/rechazo no-backup/prune a 7/
  auto-if-due/endpoints) y `tests/test_security.py` (origin_allowed, unsafe/safe/no-origin,
  rate limit). Fixture autouse en `tests/conftest.py` que limpia el estado del rate limiter entre
  tests (evita 429 espurios). Ver CHANGELOG 1.41.0.

### 37.19 HECHO (Beta 1.0) — 5 gates de salida 10/10
- ✅ **`docs/BETA_GATES.md`**: evaluación de los 5 gates con evidencia por criterio y puntuación
  10/10 en cada uno — G1 Infrastructure, G2 Curriculum, G3 Listening+Speaking, G4 Adaptive+Mastery,
  G5 UX+Reliability.
- ✅ **Bump de versión mayor** `1.41.0` → `2.0.0` en `config.py`/`package.json`/`package-lock.json`/
  `README.md`/`CHANGELOG.md`/`PLAN.md` (la app ya tenía `1.0.0` como release inicial en el changelog,
  por lo que Beta 1.0 se marca con la mayor `2.0.0` para no reutilizar ni retroceder la secuencia).
- ✅ **CHANGELOG `[2.0.0]`** y **`docs/RELEVO.md`** (posición, notas de contexto y sección 37.19).
- ✅ **Pre-auditoría interna** (security-review + Bugbot): 1 hallazgo medio corregido (path
  traversal en `export_backup` → `read_backup` confinado a `backups_dir()`) y 1 bajo corregido
  (restore ahora reemplaza de verdad, no solo superpone). Tests añadidos: `test_read_backup_rejects_path_traversal`,
  `test_export_rejects_path_traversal` y `test_restore_removes_stale_files` (backend 929 tests).
- ✅ **Verificación final**: `check_release_consistency` OK (2.0.0); backend 929 tests + `ruff`
  limpio; frontend `tsc` + `vitest` 240 tests + `build` OK. El roadmap V1.36 → Beta 1.0 queda cerrado.

### 37.20 HECHO (V2.3) — Personal Dictionary + evidencia por ítem léxico
- ✅ **Bajar el modelo de evidencia de "destreza" a "palabra/estructura"**: la tabla `vocabulary`
  gana contexto curricular (`cefr`/`level_id`/`objective_id`/`source`/`lemma`/`kind`) vía migración
  idempotente en `repositories/db.py` (solo contexto; no toca `appearances`/`exposures`).
- ✅ **Siembra desde el currículo** (`services/lexicon.items_from_objective` +
  `repositories/vocabulary.seed_curriculum_items`): `objective.vocabulary` + `objective.concepts`
  (estructuras "I am"/"My name is" como `kind=structure`) pueblan el diccionario al avanzar, cableada
  en `submit_objective_assessment` y `record_lesson_completed`.
- ✅ **Servicio puro `services/lexicon.py`**: `item_mastery`, `item_recall` (reutiliza
  `forgetting.retrieval_probability`), `item_status` determinista (`mastered`/`known`/`learning`/`weak`),
  `next_review_days` (reutiliza `mastery.review_interval_days`), `cefr_distribution`, `summary` y
  `recognized_not_produced` (señal *speaking micro-drill*, sin generación automática — queda V2.4).
- ✅ **Endpoint `GET /api/vocabulary/lexicon`** → `LexiconOut { summary, items }` con `status`, `recall`
  y `next_review_days` por ítem (`schemas/vocabulary.py` + `routers/vocabulary.py`).
- ✅ **Frontend `PersonalDictionary.tsx`**: totales Known/Learning/Weak/Mastered, barra "Vocabulary by
  CEFR" (A1→C2), lista de ítems con `recall %` y "next review", sección "Recognized but not produced";
  ruta `vocabulary` + entrada en la navegación + i18n ES/EN (`api/vocabulary.ts`, `dictionary.ts`).
- ✅ **Tests**: `backend/tests/test_lexicon.py` (invariantes: seed sin incrementar producción, estado
  determinista, recall monótono, distribución CEFR, señal micro-drill) + `test_vocabulary.py` ampliado
  (endpoint lexicon); frontend `vocabulary.test.ts` + `dictionary.test.ts`. Backend 962 tests + `ruff`
  limpio; frontend `tsc` + `vitest` 245 tests + `build` OK; `check_release_consistency` OK (2.3.0).

### 37.21 HECHO (V2.4) — Auditoría de cobertura curricular
- ✅ **Servicio puro `services/curriculum_coverage.py`**: `coverage_sections(level)` (conteo por las 7
  secciones a nivel de curso completo), `bank_intersection()` (cruce del banco de listening por `level`
  y de los escenarios de speaking por `cefr_target` contra A1..C2), tri-estado
  `complete`/`partial`/`empty`, `level_coverage(level_id)`, `coverage_metric()` (TOTAL CURRICULUM
  COVERAGE sobre la matriz 7 niveles × 7 secciones = 49 celdas) y `curriculum_coverage_report()`.
- ✅ **Métrica "TOTAL CURRICULUM COVERAGE"** integrada en `content_stats()` junto a
  `total_validated_learning_items` (dos métricas que conviven: contenido validado vs. cobertura).
- ✅ **CLI `scripts/curriculum_coverage.py`**: JSON completo + resumen nivel×sección + `--strict`
  (exit 1 si hay huecos `empty` en una sección con curso).
- ✅ **Tests** `test_curriculum_coverage.py` (9 invariantes: 7 niveles × 7 secciones, Pre-A1 banda sin
  curso, cruce con bancos, determinismo, coexistencia de métricas). Backend **971 tests** + `ruff`
  limpio; `check_release_consistency` OK (2.4.0).
- ✅ **Mapa `docs/CURRICULUM_COVERAGE.md`**: tabla Pre-A1→C2 × 7 secciones + huecos priorizados.

**Resultado de la auditoría (37/49 celdas = 75,5%):** huecos reales — Pre-A1 sin curso (marcado);
interaction 1/7 (solo B1); listening desconectado (29 checks en curso vs 100 en banco) y sin C1/C2;
speaking declarado sin evaluación y sin C2; review/assessment solo en módulos Final; C1/C2 muy finos
(7 y 5 objetivos vs 23 en A1). **Estos huecos alimentan V2.5 (contenido)**.

### 37.22 HECHO (V2.5-C1) — Listening C1/C2 (corpus 100→140, LEVEL_ORDER A1..C2)
- ✅ **Corpus de listening 100 → 140** (`curriculum/listening_corpus.json` v1.1.0): 20 ítems C1
  (`c101`–`c120`) y 20 C2 (`c121`–`c140`) con registro/temática avanzados (inferencia, intención,
  actitud, ironía, hablantes múltiples, connected speech, habla rápida). Diversidad mantenida.
- ✅ **Motor**: `LEVEL_ORDER` → A1..C2 (`services/listening.py`), `LISTENING_BANK_VERSION` 5.0.0 →
  6.0.0 (`services/curriculum.py`), `QUALITY_THRESHOLDS["min_items_per_level"]` añade C1/C2 (20).
- ✅ **Métrica**: TOTAL VALIDATED LEARNING ITEMS 143 → 183 (163 listening: 140 corpus + 23 legacy;
  20 speaking), reflejada en README/CHANGELOG/PLAN y `docs/CURRICULUM_COVERAGE.md`.
- ✅ **Tests**: `test_curriculum_coverage.py` (hueco C1/C2 invertido + invariante ≥20/nivel),
  `test_content_quality.py` (umbrales + 6 niveles), `test_listening_corpus.py` (niveles C1/C2),
  `test_listening.py` (tope C2). Backend 972 tests + `ruff` limpio.
- Verificado: `content_validation` OK (14/14), `curriculum_coverage` OK (`bank_count` C1/C2 > 0),
  `check_release_consistency` OK (2.4.0). Sin bump de versión.

### 37.23 HECHO (V2.5-C2) — Speaking C2 (escenarios 20→26, cefr_target C2)
- ✅ **Escenarios de speaking 20 → 26** (`curriculum/speaking_scenarios.json` v1.0.0 → v2.0.0): 6
  escenarios C2 (`persuasion`, `conflict_mediation`, `academic_defence`, `abstract_conversation`,
  `stakes_negotiation`, `diplomatic_talk`) con objetivo comunicativo C2 (persuasión sutil, mediación
  de conflicto, defensa con evidencia, temas abstractos, negociación delicada y tacto diplomático).
  Todos usan `task_type` conversacional (invariante de la UI de escenarios).
- ✅ **`SPEAKING_SCENARIOS_VERSION` 2.0.0 → 3.0.0** (`services/curriculum.py`), alineando la
  discrepancia JSON↔constante (JSON 1.0.0 → 2.0.0; constante 2.0.0 → 3.0.0).
- ✅ **Métrica**: TOTAL VALIDATED LEARNING ITEMS 183 → 189 (163 listening + 26 speaking), reflejada
  en README/CHANGELOG/PLAN y `docs/CURRICULUM_COVERAGE.md`.
- ✅ **Tests**: `test_curriculum_coverage.py` (hueco C2 invertido), `test_speaking_scenarios.py`
  (catálogo 26 + invariante ≥1 escenario por `cefr_target` A1..C2). Backend 973 tests + `ruff` limpio.
- Verificado: `curriculum_coverage` OK (`bank_count` speaking C2 > 0), `check_release_consistency`
  OK (2.4.0). Sin bump de versión.

### 37.24 HECHO (V2.5-C3) — Interaction A1/A2/B2/C1/C2 (subskills interaction+turn_taking)
- ✅ **Subskills de interacción en 5 niveles** (`curriculum/a1.json`, `a2.json`, `b2.json`, `c1.json`,
  `c2.json`): 39 objetivos que declaran `speaking` con actividad `dialogue` añaden
  `subskills: ["interaction", "turn_taking"]` (18 en A1, 11 en A2, 2 en B2, 5 en C1, 3 en C2). La
  sección `interaction` deja de estar `empty` en A1/A2/B2/C1/C2 (solo Pre-A1, banda sin curso, queda
  vacía). Sin tocar `services/course.py` ni el scoring de speaking.
- ✅ **Métrica**: TOTAL CURRICULUM COVERAGE 37/49 → 42/49 (75,5% → 85,7%); interaction pasa de 1/7 a
  6/7 poblado. `TOTAL VALIDATED LEARNING ITEMS` sigue en 189 (sin ítems nuevos: interaction se cuenta
  por subskill, no por check).
- ✅ **Test invariante nuevo** (`test_curriculum_coverage.py`): `interaction` con `count > 0` y
  `status != empty` en A1/A2/B2/C1/C2.
- ✅ **Docs**: `docs/CURRICULUM_COVERAGE.md` (interaction 6/7, cobertura 42/49), CHANGELOG, PLAN,
  README y este RELEVO actualizados. Backend 974 tests + `ruff` limpio.
- Verificado: `validate_level` vacío para los 6 niveles, `curriculum_coverage` OK (interaction
  A1/A2/B2/C1/C2 con `count > 0`), `check_release_consistency` OK (2.4.0). Sin bump de versión.

### 37.25 HECHO (V2.5-C4) — Wiring curso↔bancos (listening_items + scenario_ids por objetivo)
- ✅ **Modelo `Objective`** (`services/curriculum.py`): dos campos retrocompatibles con default `[]`:
  `listening_items: list[str]` (IDs del banco de listening) y `scenario_ids: list[str]` (IDs de
  escenarios de speaking). `load_all_levels()` sigue parseando los 6 niveles sin cambios de firma.
- ✅ **Conteo** (`services/course.py::unit_sections`): `listening` suma `len(listening_items)` y
  `speaking` suma `len(scenario_ids)`, de modo que la sección refleja las referencias reales al banco
  y no solo el `skill` declarado (sin tocar `CourseMapOut`/endpoints). `coverage_sections` lo refleja
  por delegación (usa `unit_sections`).
- ✅ **Wiring de contenido** en los 6 niveles (`curriculum/a1.json`–`c2.json`): 18 objetivos con
  `listening` referencian 4 ítems del banco de su nivel (`c001`–`c140` + legacy `l1`–`l23`); 50
  objetivos con `speaking` referencian 1 escenario de su `cefr_target` (26 escenarios). Solo
  referencias por ID (sin duplicar ítems del banco dentro del JSON de nivel).
- ✅ **Validación** (`services/curriculum.py::validate_level`): cada `listening_items` debe existir y
  su `level` coincidir con el nivel; cada `scenario_ids` debe existir y su `cefr_target` coincidir.
  Imports diferidos (anti-ciclo, porque `listening`/`speaking_scenarios` importan `curriculum`).
- ✅ **Test invariante nuevo** (`tests/test_bank_wiring.py`, 7 tests): conteo con referencias,
  referencia rota y desfase de nivel (listening y speaking), listening/speaking no `empty` en niveles
  con curso y `validate_level` vacío para los 6 niveles.
- ✅ **Docs**: `docs/CURRICULUM_COVERAGE.md` (listening/speaking pasan de "desconectado" a "cableado
  por unidad", `count` actualizado), CHANGELOG, PLAN, README y este RELEVO. Backend **981 tests** +
  `ruff` limpio.
- Verificado: `validate_level` vacío para los 6 niveles, `curriculum_coverage --strict` exit 0 (sin
  huecos `empty`; `count` de listening/speaking crecido), `check_release_consistency` OK (2.4.0). Sin
  bump de versión y **sin UI** (la consumición visual de los ítems referenciados es un incremento
  posterior).

### 37.26 HECHO (V2.6-C1) — Capa de medición: Unit Coverage + CEFR Depth + Unit Learning Loop + Dashboard
- ✅ **Hallazgo conceptual (auditoría externa):** "cobertura" ≠ "profundidad". `42/49 celdas` no
  significa "curso al 85,7%": una celda cuenta como poblada si *alguna* unidad tiene contenido en esa
  sección. Se añaden métricas con grano fino en `services/curriculum_coverage.py`:
  - `unit_coverage(level)`: por unidad, cuántas de las 7 secciones están pobladas (`coverage_pct`,
    `missing`, `by_section` con `units`/`with_content`). Media A1..C2 = **61,7%**.
  - `depth_score(level)` — **CEFR DEPTH SCORE** (0..100): 4 componentes ponderados y auditables
    (`objective_density` 0.20, `objective_volume` 0.35, `section_coverage` 0.35, `subskill_breadth`
    0.10; pesos en `DEPTH_WEIGHTS`, suma 1.0). Media **55,7**; por nivel: A1 74,2 · A2 52,3 · B1 55,7
    · B2 61,7 · C1 48,0 · C2 42,5. Ajuste V2.6-C1b: se sube el peso del *volumen* y se baja el de la
    *densidad* (la densidad sola premiaba a B2, denso pero con solo 9 objetivos, por encima de A2).
  - `unit_learning_loop(level, unit)` + `loop_coverage(level)` — **UNIT LEARNING LOOP** (9 fases:
    introduce, practice, listen, speak, interact, retrieve, transfer, assess, review). Mide qué fases
    cubre cada unidad. Media **50,6%**; introduce/practice 100%, listen 45,2%, speak 90,3%,
    interact 83,9%, **retrieve/transfer 0%**, assess/review 19,4% (solo módulos "Final").
  - `unit_detail(level_id, unit_id)`: drill-down LEVEL → UNIT → LESSON → OBJECTIVE (skills, subskills,
    activities, checks, `listening_items`, `scenario_ids`) + 7 secciones.
  - `curriculum_quality_report()` — **Curriculum Quality Dashboard**: 7 dimensiones (coverage, depth,
    listening, speaking, interaction, assessment, review) + `overall` + `by_level` + bloque `learning_loop`.
    Overall **56,8**; dimensiones: coverage 85,7 · depth 55,7 · listening 47,8 · speaking 84,7 ·
    interaction 76,4 · assessment 23,5 · review 23,5.
  - `quality_report_delta(before, after)`: delta antes/después por dimensión y nivel.
- ✅ **CLI** (`scripts/curriculum_coverage.py`): imprime dashboard + loop legibles y `--quality` vuelca
  el JSON completo.
- ✅ **Hallazgo de datos:** el recuento real de objetivos es A1 23 → A2 11 → B1 10 → B2 9 → C1 7 →
  C2 5. La caída es más abrupta de lo que sugería la auditoría previa (no solo C1/C2 son finos; A2 y
  B1/B2 también). Los puntos débiles medidos: Review/Assessment (23,5, solo en módulos "Final"),
  Listening (47,8, integrado en parte de las unidades) y las fases de cierre del loop (retrieve/transfer
  0%, assess/review 19,4%).
- ✅ **Tests** `test_curriculum_quality.py` (18 invariantes: unit coverage, pesos del depth, drill-down,
  dashboard determinista, delta identidad, 6 del loop). Backend **999 tests** + `ruff` limpio;
  `content_validation` OK; `check_release_consistency` OK (2.4.0).
- Verificado: `curriculum_coverage` OK (dashboard + loop), `--strict` exit 0. Sin bump de versión y
  **sin UI** (la visualización del dashboard/loop es un incremento posterior).

### 37.27 HECHO (V2.6-C2) — Marcador de fase del Unit Learning Loop (`Activity.phase` + validación)
- ✅ **Modelo** (`services/curriculum.py`): `LEARNING_PHASES` (9 fases canónicas) como fuente de verdad
  y `Activity.phase: str = ""` (default vacío = `practice`, retrocompatible). `validate_level()` rechaza
  `phase` no canónico.
- ✅ **Medición** (`services/curriculum_coverage.py`): re-exporta `LEARNING_LOOP_PHASES = LEARNING_PHASES`
  (anti-drift) y `unit_learning_loop()` lee `retrieve`/`transfer`/`review`/`assess` desde el `phase` de
  las actividades (además del módulo Final para assess/review). El hueco deja de ser un 0 hardcodeado y
  pasa a ser **datos etiquetables**: con el contenido actual sigue en 0 (retrieve/transfer) y 19,4%
  (assess/review), porque ningún JSON usa aún el marcador.
- ✅ **Briefing de contenido separado** `agentes/curriculum/c5-loop-phases.md`: etiquetar las fases de
  cierre por unidad (piloto A1 → escalar), actualizar los invariantes de snapshot y subir el loop de
  50,6% → ≥ 77%.
- ✅ **Tests**: `test_bank_wiring.py` (validación: phase no canónico rechazado, canónico y vacío
  aceptados) + `test_curriculum_quality.py` (medición: retrieve/transfer/review/assess leídos del
  marcador en unidad no Final, y alias de taxonomía anti-drift). Backend **1005 tests** + `ruff` limpio.
- Verificado: `curriculum_coverage --strict` exit 0, `validate_level` vacío para los 6 niveles. Sin bump
  de versión y **sin UI**.

### 37.28 HECHO (V2.6-C5) — Etiquetado de fases del Unit Learning Loop en el contenido
- ✅ **Contenido** (`backend/curriculum/a1.json`…`c2.json`): las 25 unidades normales (no módulo
  "Final") etiquetan las 4 fases de cierre con el marcador `phase`:
  - `retrieve` (recuperación espaciada) y `transfer` (can-do en contexto nuevo): 25/31 unidades (80,6%).
  - `review` (micro-repaso del can-do) y `assess` (auto-evaluación de cierre): 31/31 (100%), ya no solo
    en los módulos "Final".
- ✅ **Loop por unidad**: media **50,6% → 84,7%** (objetivo ≥ 77%). Las 9 fases: introduce/practice
  100%, listen 45,2%, speak 90,3%, interact 83,9%, retrieve/transfer 80,6%, assess/review 100%.
- ✅ **Invariantes de snapshot** (`tests/test_curriculum_quality.py`): los 2 tests que codificaban el
  hueco se actualizan — `test_loop_retrieve_and_transfer_are_tagged` (covered_units > 0) y
  `test_loop_assess_and_review_cover_every_unit` (covered_units == total_units).
- Verificado: `curriculum_coverage --strict` exit 0, `validate_level` vacío para los 6 niveles, backend
  **1005 tests** + `ruff` limpio. Sin bump de versión y **sin UI** (solo contenido + invariantes).

### 37.29 NUEVO (V3.2.x, docs) — Auditoría pedagógica del modelo de nivelación + Constitución CEFR
- **Dossier desk** `docs/audit/H-NIVELACION-PEDAGOGICA.md` (2026-09-03): inventario del
  modelo de nivelación (modelo heurístico legacy `services/cefr.py` vs Student Model vivo),
  hallazgos H1–H7 y veredicto ("el modelo no sabe responder qué ha demostrado el alumno").
- **Constitución pedagógica** `docs/CONSTITUCION-PEDAGOGICA.md`: especificación normativa
  Pre-A1→C2. Separa **Practice Level / Mastery / Estimated CEFR / Demonstrated CEFR** con 4
  estados por competencia (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), define
  cobertura léxica como indicador (no puerta), Lexical Units, la progresión de listening y el
  Mastery Gate general (coverage + accuracy + subskills + retención ≥7d + checkpoint).
- **Incrementos de código siguientes** (solo documentados; no ejecutados en esta iteración):
  - P0: eliminar la interpretación palabras→nivel y sus tests; estados Estimado/Demostrado por
    competencia con una sola fuente de mastery; coherencia Pre-A1 en bandas por destreza.
  - P0: cablear la práctica de listening al Student Model y consolidar `route_gate` como gate de
    la competencia Listening (con retención retardada).
  - P1: extender `cefr_matrix.json` a C1/C2 y 8 destrezas; retención en la certificación;
    Lexical Units en el Personal Dictionary.
  - P2: UI de "Entrenamiento A1" vs "A1 — demonstrated"; etiquetado del nivel estimado;
    eliminar `modeCefrLevel`/`modeCefrBand`.

### 37.30 NUEVO (V3.13, docs) — Calibración de evidencia pedagógica (normativa)
- **Constitución pedagógica ampliada** (`docs/CONSTITUCION-PEDAGOGICA.md`): nuevas **Reglas
  inmutables R1–R7** (Practice≠Mastery, Mastery≠CEFR certification, Vocabulary≠nivel,
  One skill≠Overall, Recognition≠Production, Éxito inmediato≠Retención, Small sample≠
  Competencia demostrada), **§6.4 Evidence depth** (LOW/MEDIUM/HIGH contra `cefr_matrix.json`;
  bancos cortos ≤ 12 checks solo declaran "practice coverage · evidence depth LOW") y **§7**
  reescrita por modalidades (recognition / controlled production / free production) con lo que
  exige "demostrado" por destreza.
- **Incrementos de código de la iteración V3.13** (ver §9 de la constitución): P0 (evidence
  depth por destreza/nivel, claims honestos para bancos cortos, suelo de "demostrado" con
  mínimo de muestras y producción, `current_level` como sugerencia de material, invariantes
  pedagógicas) · P1 (Grammar en 3 niveles con producción controlada, cross-skill evidence B1,
  golden pedagogical dataset) · P2 (LearnRoutePage compartido, parity i18n automática).

### 37.31 HECHO (V3.13) — Calibración de evidencia pedagógica (implementación)
- **P0 — Motor de evidencia + claims honestos** (`v3.13.0`): nuevo
  `backend/services/evidence_depth.py` (pure, depth LOW/MEDIUM/HIGH vs
  `cefr_matrix.json`, expuesto en `/api/profile` vía `domain/profile.py`);
  evidencia `academy_evidence` con columna `level` en filas nuevas
  (retrocompatible). Rutas quiz: `stats` por nivel con `bank_size` y
  `evidence_depth`; UI Grammar/Vocabulary muestra "practice coverage · evidence
  depth LOW" en bancos cortos (claves i18n nuevas). `services/competence.py`:
  `demonstrated` = gate funcional + `minimum_evidence` + retención retardada
  estable ≥7d + producción en grammar/speaking/writing (solo MC nunca
  demuestra); vocabulary es `SUPPORT_SKILL`, techado en `functional`.
  `current_level` = sugerencia de material con fallback `review_due`.
  `backend/tests/test_pedagogical_invariants.py` (R1–R7).
- **P1 — Producción de Grammar + cross-skill + golden**: ítems
  `controlled_production` (prompt + `accepted_answers`, corrección determinista
  `normalize_typed`/`typed_matches`) en currículo A2–C1 y motor `quiz_routes.py`
  (submit con `typed_answer`); UI "type the answer". Cross-skill B1:
  `backend/services/cross_skill.py` (registro por estructura, canales
  recognition/production/listening/speaking/transfer), `/api/cross-skill`,
  `frontend/src/features/evidence/CrossSkillMatrix.tsx` en Grammar B1. Golden
  `backend/tests/golden/pedagogy/evidence_depth_cases.json` +
  `test_golden_pedagogy.py`.
- **P2 — LearnRoutePage compartido + parity i18n**: shell
  `frontend/src/features/routes/QuizRoutePage.tsx` (config por skill: API,
  i18n, LevelPanel, `scene` personalizada, `trailing`, assessment ladder o
  speaking) + máquina consolidada `features/routes/routeSession.ts` + tipos
  `quizRouteTypes.ts`. Migradas por oleadas Grammar+Vocabulary (1),
  Pronunciation+Conversation (2), Speaking con extras y bloques contextuales
  (3); cada oleada validada con `tsc --noEmit`, vitest y su spec Playwright
  desktop. Listening (4) **no migra por diseño**: es la única práctica del hub
  servida dentro del runner `PracticeView` del workspace (línea
  `WORKSPACE_ACTIVITIES` de `Workspace.tsx`), no una página de ruta standalone.
  `frontend/src/utils/i18n.parity.test.ts` (claves en/es no vacías, sin
  duplicados, usadas resueltas).
- **Cierre**: bump único `3.13.0` (backend `config.py` fuente única, validado
  con `scripts/check_release_consistency.py`), `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.31 en `docs/RELEVO.md`, `release-notes-v3.13.0.md`.
  §9 de la constitución marcada "implementado en v3.13.0". Tests: **pytest
  1290**, **vitest 382** y Playwright desktop verde.

### 37.32 HECHO (V3.14) — Registro cross-skill A1–C2 (implementación)
- **Contenido — ítems CP en A1 y C2** (`backend/curriculum/a1.json`,
  `c2.json`): A1 gana `a1-cp-01..06` (`to be`, present simple 3.ª persona,
  adverbios de frecuencia, `have/has got`, preposiciones de lugar, past simple;
  dianas `a1-m01-u01-l01-o01`, `a1-m02-u01-l01-o01/-o03`, `a1-m03-u01-l01-o01`,
  `a1-m04-u01-l01-o02`, `a1-m08-u01-l01-o02`) y C2 gana `c2-cp-01..04`
  (inversión enfática + cleft en `c2-m01-u01-l01-o04`, mixed conditional en
  `c2-m03-u01-l01-o01`, pasiva formal de registro en `c2-m02-u01-l01-o01`),
  con `accepted_answers` deterministas. El banco Grammar crece (A1 38→44, C2
  4→8); C2 sigue en banco corto ≤12 → su claim "evidence depth LOW" se
  conserva (tests pedagógicos actualizados: docstrings 4 MC → 4 MC + 4 CP).
- **Motor — registro generalizado** (`backend/services/cross_skill.py`):
  `CROSS_SKILL_LEVELS = ("a1".."c2")`; `structure_registry(level)` sirve
  cualquier nivel (objetivos con checks MC de grammar); constantes
  `A1..C2_PRODUCTION_BINDINGS` + `PRODUCTION_BINDINGS_BY_LEVEL` completos
  (A2/B2/C1 validados contra `can_do`; B1 intacto). Un objetivo agrupa varios
  CP y `production.evidence` cuenta CP superados. Sin `proto`.
- **API/schema** (`backend/schemas/cross_skill.py`,
  `backend/routers/cross_skill.py`): `proto` eliminado de `CrossSkillMatrixOut`;
  endpoint valida `level ∈ CROSS_SKILL_LEVELS` (400
  `cross_skill.level_unknown`); default `"b1"` inofensivo se mantiene.
- **Tests backend** (`backend/tests/test_cross_skill.py` reescrito):
  invariantes por nivel (registro == objetivos grammar con MC; bindings
  normativos sin CP huérfanos; oferta de listening/speaking según wiring del
  currículo; matriz cuenta recognition/transfer/listening/speaking por
  objetivo y producción por CP superado); invariante de contenido A1/C2;
  endpoint 200 en los seis niveles + 400 en nivel inválido.
  `test_grammar_routes.py::test_production_pool_items_present_in_every_level`
  (todos los niveles aportan CP).
- **UI** (`frontend`): `GrammarLevelPanel.tsx` monta `CrossSkillMatrix` para
  cualquier nivel (fuera el gate `B1`); `CrossSkillMatrix.tsx` sin pie de
  prototipo y copia generalizada; `types/api.ts` sin `proto`; `api/crossSkill.ts`
  con `level` requerido; `i18n.ts` sin `crossSkill.protoNote`, título/nota
  genéricos. Playwright `grammarRoutesReview.spec.ts` mockea `/api/cross-skill`
  (respuesta vacía determinista para el panel A1).
- **Cierre**: bump único `3.14.0` (backend `config.py` fuente única, validado
  con `scripts/check_release_consistency.py`), `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.32 en `docs/RELEVO.md`,
  `release-notes-v3.14.0.md`. Tests: **pytest 1293**, **vitest 382** y
  Playwright desktop verde.

### 37.33 HECHO (V3.15) — C1/C2 depth avanzado (implementación)
- **Contenido — volumen a 20 objetivos en C1 y C2** (`backend/curriculum/c1.json`,
  `c2.json`): +6 objetivos por nivel con evidencia completa (checks MC + 5
  activities con fases y wiring conservado). C1: `c1-m02-u01-l01` +2 (matiz e
  idioms de registro), `c1-m02-u01-l02` +1 y `c1-m03-u01-l01` +3
  (argumentación: concesión y discourse markers). C2: `c2-m02-u01-l01` +2
  (Register shifts formal/informal) y lección nueva `c2-m02-u01-l03` +4
  (elipsis, gramática formal, cohesion discursiva). Módulos Final intactos
  (`c1-m04` y `c2-m03` con su único objetivo). Activities 68→98 en ambos
  niveles; checks C1 45→63 y C2 38→57.
- **Motor — taxonomía avanzada** (`backend/services/curriculum.py`): `SUBSKILLS`
  añade la capa C1/C2 `register`/`pragmatics`/`discourse`/`nuance`/
  `argumentation` a speaking, listening, writing, grammar, reading y vocabulary
  (pronunciation intacta; orden alfabético conservado). Re-etiquetado de
  objetivos C1/C2 solo donde el contenido lo justifica (C1 3→16 y C2 7→20
  objetivos con subskill avanzada); A1–B2 sin tocar. `validate_level` vacío en
  los 6 niveles.
- **Banco grammar C2 normalizado**: 8 → 15 ítems (11 MC + 4 CP en 3 temas:
  Register & Cultural Fluency, Rhetoric & Persuasion, C2 Final). Ningún banco
  real es ya corto (< `QUIZ_SHORT_BANK` 12) y `practice_depth` real deja de
  leer `low`. La regla R7 (muestra pequeña ≠ competencia) se mantiene
  verificada con un banco corto **sintético** construido en los propios tests,
  sin contenido artificial.
- **Tests**: `test_curriculum_quality.py` reformula el snapshot V2.6
  (`test_depth_c1_c2_reach_deep_target_after_v315`: depth(C1/C2) ≥ 90 y >
  depth(A1)); `test_pedagogical_invariants.py` re-apunta R7 a banco sintético
  (`test_synthetic_short_bank_cannot_prove_level`,
  `test_short_bank_coverage_does_not_lift_to_medium`); `test_grammar_routes.py`
  actualiza conteos (8 → 15) con helpers `_synthetic_short_bank`; textos
  "C2 = 4" retirados de `quiz_routes.py` y `schemas/grammar_routes.py`.
- **Métricas** (CLI `python -m scripts.curriculum_coverage --strict --quality`,
  exit 0): `depth(C1) = 93.1`, `depth(C2) = 92.5` (A1 89.4, A2 81.9, B1 89.0,
  B2 81.0; overall 96.2); unit coverage 100 % (31/31) y Unit Learning Loop
  100 % en las 9 fases; sin huecos `empty`.
- **Cierre**: bump único `3.15.0` (backend `config.py` fuente única, validado
  con `scripts/check_release_consistency.py`), `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.33 en `docs/RELEVO.md`,
  `release-notes-v3.15.0.md`. Tests: **pytest 1293**, **vitest 382** y build
  frontend OK (sin cambios de frontend/launcher ni de la CONSTITUCIÓN).

### 37.34 HECHO (V3.16) — Review/SRS por unidad (micro-review + ventanas 7/30/90)
- **Motor puro** `backend/services/unit_review.py` (determinista, sin BD/FastAPI):
  ventanas fijas `UNIT_REVIEW_WINDOWS_DAYS = (7, 30, 90)` desde el ancla de la
  unidad (D4: completada = todos sus objetivos `mastered`; ancla =
  `max(updated_at)` de sus filas de mastery); estados
  `upcoming/due_now/passed/failed` con `now` inyectable (D3: la ventana es un
  hito fijo, el grade no la recalendariza); `sample_micro_review` determinista
  y balanceado (semilla `user|unit|window`; máx. 2 ítems/objetivo; target 8;
  reintento prioriza `failed_items` del último intento); `score_micro_review`
  puntúa en servidor contra `correct_index` (el cliente solo envía respuestas,
  premisa 21) y `passed = accuracy ≥ 0.7` (D6). Contenido: checks MC
  **oficiales** del currículo (D8, cero contenido artificial).
- **Siembra FSRS `objective`** (`sync_fsrs_cards`, `backend/domain/academy.py`):
  cartas `target_type="objective"` para los objetivos de las unidades
  completadas del nivel actual (`_current_level_id`, D2); cartas con `reps > 0`
  solo refrescan `why`/`label`; nuevas se siembran desde el mastery del objetivo
  (`fsrs.seed_card_from_evidence`) y se fuerzan a due si su ventana más próxima
  está `due_now`/`failed`. `fsrs.why_for_objective` añadido (puro):
  `unit-window-N` / `unit-maintenance`. `TARGET_TYPES` intacto.
- **Persistencia**: tabla idempotente `unit_review_attempts`
  (`backend/repositories/db.py`; PK autoincrement, índice de lookup
  `user/level/unit/window/created_at`) con `per_objective` + `failed_items` en
  JSON, y repos `insert/list/latest_unit_review_attempt`
  (`backend/repositories/academy.py`); `list_objective_mastery` ahora expone
  `updated_at`. El micro-review **no** crea evidencia de mastery/currículo ni
  declara dominio (D5, E3).
- **API** (`backend/routers/academy.py` + `backend/domain/academy.py` +
  schemas en `backend/schemas/academy.py`): `GET /api/academy/review/unit-plan`
  (unidades completadas o con plan activo + `due_count`), `GET
  /api/academy/review/unit/{unit_id}/micro-review` (ítems SIN `correct_index`;
  400 si la ventana no está `due_now`/`failed`, 404 si la unidad es ajena al
  nivel) y `POST /api/academy/review/unit/{unit_id}/micro-review` (puntúa,
  persiste el intento y reprograma las cartas FSRS `objective` con el grade por
  objetivo derivado de su precisión).
- **UI (INICIO)**: `UnitReviewPanel` (`frontend/src/features/review/`) montado
  en `HomeScreen.tsx` junto a `FsrsReviewPanel`: lista de unidades con chips de
  ventana 7/30/90 y color por estado, contador de unidades por repasar, y
  micro-review por tarjetas (una pregunta a la vez, feedback inmediato y
  respuesta correcta revelada al terminar) con la nota honesta "Repaso de
  retención · no cuenta como demostración de dominio". Lógica pura extraída a
  `unitReviewLogic.ts` (testeable sin DOM); tipos espejo en `types/api.ts`,
  cliente en `api/academy.ts`, i18n `en`/`es` completa con parity.
- **Tests**: `backend/tests/test_unit_review.py` (servicio puro: 18 tests),
  `backend/tests/test_unit_review_endpoints.py` (siembra solo en unidades
  completadas + idempotencia, sin `correct_index` en GET, D5 sin evidencia
  nueva, gating passed/upcoming → 400 y failed → reintento, aislamiento entre
  usuarios); `frontend/src/features/review/unitReviewLogic.test.ts` y tests del
  cliente API. Backend **pytest 1318** + ruff limpio; frontend **vitest 392** +
  `tsc`/`vite build` OK.
- **Cierre**: bump único `3.16.0` (backend `config.py` fuente única, validado
  con `scripts/check_release_consistency.py`), `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.34 en `docs/RELEVO.md`,
  `release-notes-v3.16.0.md` (untracked). Sin cambios de CONSTITUCIÓN (v3.16 es
  mecanismo, no norma) ni de launcher.
- **Auditoría externa (2026-09-06, read-only)**: veredicto **APROBADO CON
  OBSERVACIONES** — D1–D8 y criterios 1–8 cumplidos (pytest 1318, ruff,
  consistencia de release verificados en vivo). Fix aplicado del hallazgo
  **I1** (bug real: `selected_index` serializaba `-1` al elegir la opción A,
  índice 0, en `domain/academy.py`; corregido con `item.get("selected_index",
  -1)` + test de regresión `test_micro_review_audit_keeps_index_zero`). El
  resto queda como deuda priorizada para v3.17 (ver candidato abierto abajo).

### 37.35 HECHO (V3.17) — Knowledge Graph + Daily Adaptive Plan
- **D1b — el plan diario deriva del grafo**: `services/evidence_graph.py`
  gana dos funciones puras — `rank_weakness_objectives` (reordena los
  candidatos de cada destreza débil: primero los objetivos cuyo nodo declara
  esa destreza como factor limitante o con la dimensión `missing`, después por
  `mastery` ascendente, empates estables, ids sin nodo al final) y
  `enrich_item` (aditivo: copia del ítem que gana
  `can_do`/`limiting_factor`/`graph_mastery`/`because[]` solo si hay nodo). En
  `domain/academy.py::_session_steps` se construye el mapa de nodos con la
  MISMA lectura de perfil/evidencia que el resto del flujo
  (`_objective_nodes_for` + una única `list_evidence`) y se reordena cada
  `remediation[].objective_ids` antes de `session_plan`; los pasos con objetivo
  y nodo se enriquecen. `get_next_best_activity` ya no re-enriquece aparte:
  copia los campos del primer paso enriquecido → `/session` y `/next-best`
  nunca divergen (test `test_next_best_graph_fields_never_diverge_from_session`).
- **D2 — vista de grafo real**: nuevo componente reutilizable
  `ObjectiveNodeCard.tsx` que consume `getEvidenceGraphNode(userId,
  objectiveId, levelId?)` con estados loading/error/vacío y sin declarar
  dominio (refleja la puntuación del servidor). Montado en el **curso**
  (`Milestone` expansible bajo demanda, con el `level_id` real del detalle de
  la unidad) y en el **perfil** (Habilidades: el detalle del nodo seleccionado
  del `EvidenceGraphPanel` pasa por `ObjectiveNodeCard`). Sin endpoint nuevo
  (D2 backend no añade API). i18n reutilizada de `evidenceGraph.*`.
- **D3 — `/api/academy/today` eliminado**: endpoint, `get_today_plan`,
  `TodayPlanOut`/`TodayItemOut`, `adaptive.today_plan` + `TODAY_MIX` y cliente
  `getTodayPlan` + tipos `TodayPlan`/`TodayItem` fuera; la Home consume solo
  `/session`. Tests migrados con rationale honesto:
  `test_endpoint_today_empty…` → `test_endpoint_session_empty…`; los 4 tests
  puros de `today_plan` pasaron a `session_plan` (ajuste honesto de claves y de
  la aserción weakness ≥ review, ahora ambos 0.30 en `SESSION_MIX`);
  `test_today_plan_uses_goal_budget` se retiró porque su invariante ya lo
  cubre `test_endpoint_session_uses_goal_budget`. Referencia stale en
  `docs/UI_V3.1.md:160` corregida en el cierre.
- **Deuda v3.16 (D4b)**: M2 ✅ — `validate_micro_review_answers`
  (`unit_review.py`) valida claves ⊆ muestra e índices en rango antes de
  puntuar (`ValueError unit_review.invalid_answers` → 400, sin persistir); M3 ✅
  — prefijos dinámicos `unitReview.window.`/`unitReview.state.`/`skill.`/
  `fsrs.whyReason.` registrados en `DYNAMIC_KEY_PREFIXES`; O2 ✅ — test de
  reintento parcial GET==POST (muestra idéntica entre llamadas y fallidos
  primero). M1 ✅ **en el cierre** — infraestructura DOM aprobada por el
  gerente: devDeps `jsdom` + `@testing-library/react` (+`@testing-library/dom`)
  en `frontend/package.json`, `vitest.config.ts` ampliado a `*.test.tsx` (con
  alias `@` → `src`; jsdom por archivo vía `// @vitest-environment jsdom`) y 6
  vitest de componente nuevos: `UnitReviewPanel.test.tsx` (4: vacío, ventana
  due, submit+refresh con plan mutable, error de red) y `TodayPlan.test.tsx`
  (2: micro-línea D6 con can-do + chip `%`, y silencio D7 sin nodo).
- **D5 — versionado**: `GRAPH_VERSION` permanece `"2.12.0"` (helpers nuevos +
  contrato opcional; no se altera la salida de `objective_node`/
  `build_level_graph`).
- **D6 — UI del plan**: `TodayPlan.tsx` pinta en cada fila de sesión con
  `can_do` + `limiting_factor` dos micro-líneas estáticas informativas dentro
  de la fila-botón (can-do en itálica + chip del factor limitante con `%` o
  `missing` vía tokens warning); el `because[]` completo sigue solo en
  `NextBestCard`. CSS en `legacy.css` (`.today-item-graph`).
- **D7 — ítems sin nodo**: `enrich_item(nodo=None)` devuelve copia intacta; en
  `/session` los pasos sin `objective_id` (p. ej. listening) no ganan campos y
  el esquema los serializa `null`/`[]` (`SessionStepOut` ampliado con campos
  opcionales); el ranking nunca bloquea (sin nodo → orden original al final).
- **Tests**: `test_graph_plan.py` (9 puros de `rank_weakness_objectives`/
  `enrich_item`, incl. fallback D7 y paridad con `enrich_next_best`),
  `test_session_graph.py` (5 endpoint: campos del grafo en `/session`
  coherentes con el can-do real del currículo, silencio en pasos sin objetivo,
  paridad `/next-best`==`/session`, y los 2 de la auditoría v3.17 — camino REAL
  de remediación enriquecido y paridad con el primer paso CON nodo); migrados
  `test_academy.py`, `test_academy_goal.py`, `test_adaptive.py`; M2/O2 en
  `test_unit_review.py`/`test_unit_review_endpoints.py`. Backend **pytest
  1335** + ruff limpio; frontend **vitest 398** (392 + 6 DOM) +
  `tsc`/`vite build` OK; `check_release_consistency` exit 0.
- **Cierre**: bump único `3.17.0` (backend `config.py` fuente única) +
  `frontend/package.json`/`package-lock.json` (bump + devDeps DOM de M1),
  `README`, `CHANGELOG`, `PLAN`, Nota superior + entrada 37.35 en
  `docs/RELEVO.md`, `release-notes-v3.17.0.md` (untracked). Sin cambios de
  CONSTITUCIÓN (v3.17 conecta el grafo existente al plan: motor + UI, no
  norma) ni de launcher.
- **Auditoría externa (2026-09-06, read-only sobre `989658e`)**: veredicto
  **APROBADO CON OBSERVACIONES** — D1b/D2c/D3a/D4b/D5a/D6a/D7a cumplidos y
  reproducidos en vivo (pytest 1333, vitest 398, ruff, tsc, consistencia).
  Fix aplicados tras el veredicto: **H1** — 2 tests de endpoint que fijan el
  camino REAL de remediación de D1b (paso `weakness` de un examen suspendido
  enriquecido con el can-do real del currículo, y paridad
  `/next-best`==`/session` cuando el primer paso CON nodo — antes solo se
  cubría el null==null de usuario nuevo); **H2** — el panel de Habilidades ya
  no recorta a 12 nodos (listado completo, criterio 5 de D2); **H3** — el
  `Milestone` no expande objetivos `locked`; **H4** — typo docs («10 puros» →
  «9»). Deuda menor (sin fix, decidida por el gerente) → candidato v3.18:
  **H5** y **H6**.

### 37.36 HECHO (V3.18) — Knowledge Graph remainder + deuda del grafo (P3)

- **I2 — ancla congelada al completar**: nueva tabla `unit_review_anchors`
  (`user_id/level_id/unit_id` PK, `anchor`, `created_at/updated_at`, índice de
  lookup por `(user_id, level_id)`) en `repositories/db.py` + repos
  `get_unit_anchor`/`set_unit_anchor_if_absent` (`INSERT OR IGNORE`, nunca
  sobrescribe). El servicio puro `build_unit_review_plan` gana `anchor:
  str | None = None` (ventanas sobre el ancla persistida si viene; si no, lo
  deriva como antes). `domain/academy.py` persiste el ancla en la primera
  detección de completitud (backfill lazy en `get_unit_review_plan`,
  `_unit_review_context` y `sync_fsrs_cards`); una segunda lectura tras tocar
  `updated_at` devuelve las mismas `due_at` (test de dominio).
- **O1 — cascade 7→30→90**: `window_due_at` recibe los intentos de la unidad
  (todas las ventanas) y filtra internamente el "intento propio"; sin intento
  propio, la ventana queda `passed` si existe un intento superado de la unidad
  con `created_at >= due_at` de esa ventana. Un intento propio mandado fallido de
  la 30 gana sobre un superado de la 7; resolver la 7 tarde cierra la 30 vencida
  y deja la 90 `upcoming`/`due_now` según `now`. Tests puros en
  `test_unit_review.py` (el que fijaba "otras ventanas no afectan" se retiró con
  rationale honesto).
- **M4 — cartas `objective` fuera del panel autograduable (single writer)**:
  `sync_fsrs_cards` crea cartas `objective` solo si la primera ventana no
  superada de la unidad está `due_now`/`failed` **o** la carta ya existe con
  `reps > 0` (continuidad de scheduling), barriendo los niveles del plan
  agregado; `get_fsrs_due` excluye `objective` de cola y `due_count`;
  `get_fsrs_summary` conserva `by_type` completo pero excluye `objective` del
  `due_count`; `review_fsrs_card` rechaza `objective` (devuelve `None` → el
  router responde 400). El contenido `objective` se repasa solo vía
  `UnitReviewPanel`; `FsrsReviewPanel` recibe únicamente skill/lexicon.
- **O3 — plan agregado por niveles**: `UnitReviewPlanOut` evoluciona a
  `{levels: [UnitReviewLevelOut{level_id, level, due_count, units}], due_count}`
  (nivel actual + anteriores matriculados con unidades completadas o con plan
  activo, ordenados asc); `get_unit_micro_review`/`submit_unit_micro_review`
  aceptan `level_id: str | None = None` y validan la unidad con
  `_find_review_unit` **en el nivel donde vive** (`MicroReviewSubmitIn` gana
  `level_id`; routers GET/POST lo aceptan). Frontend: tipos espejo,
  `flattenReviewLevels` en `unitReviewLogic`, `UnitReviewPanel` agrupa por nivel
  (cabecera + contador por nivel), micro-review recuerda el `level_id` de la
  unidad, i18n es/en con parity. Aislamiento por usuario verificado.
- **H5 — etiquetas humanas de dimensiones del grafo**: `GRAPH_DIMENSION_LABELS`
  (7 dimensiones en inglés de inmersión, convención V3.6.1) + `dimensionLabel`
  en `frontend/src/utils/learningLabels.ts`; sustituye `SKILL_LABELS[id] ?? id`
  y los ids en crudo en el chip del factor limitante de `TodayPlan`,
  `NextBestCard`, `ObjectiveNodeCard` (dimensiones y `recommended_focus`) y
  `EvidenceGraphPanel`. `transfer`/`discourse`/`interaction` muestran
  Transfer/Discourse/Interaction.
- **H6 — coste lazy de `/session` y `/next-best`**: en `_session_steps` el
  ranking y la construcción de nodos se limitan a los grupos de remediación que
  pueden producir pasos (`remediation[:SESSION_CAPS["weakness"]]`, importado de
  `adaptive`); `list_evidence` se lee una sola vez y solo si `needs_nodes`
  (grupos con candidatos o `next_objective_id`). Payloads idénticos: la paridad
  `/next-best`==`/session` y el fallback sin nodo (D7 de v3.17) siguen verdes.
- **Observaciones auditoría v3.17**: (1) `getJsonNullable` (404 → `null`) en el
  cliente y `getEvidenceGraphNode` lo usa; `ObjectiveNodeCard` distingue
  `error` (copia `evidenceGraph.error` + botón reintento con `RotateCcw`) de
  `empty` (404/sin-datos, copia actual) — vitest del componente; (2) helper
  `_as_float` con fallback `0.0` en `rank_weakness_objectives` (tolerante a
  `mastery: None`/`"n/a"`, empate estable) + test puro; (3) Playwright: la spec
  `homeGraphChip.spec.ts` nueva mockea la red (sesión con `limiting_factor.id =
  "transfer"`) y fija el chip "Transfer"; ejecutada en desktop junto a
  `smoke.spec.ts` → verdes, captura `tests/visual/screenshots/desktop/
  home-graph-chip.png` nueva.
- **Tests**: `test_unit_review.py` (cascade + ancla override), `test_unit_review_endpoints.py`
  (plan multi-nivel, ancla congelada tras refuerzo, siembra gated M4, micro-review
  con `level_id` de nivel anterior, 400 `/fsrs/review` objective, exclusión
  objective en due/summary), `test_session_graph.py` (coste H6: delta de
  `list_evidence` 0 vs 1), `test_graph_plan.py` (`_as_float`); frontend
  `learningLabels.test.ts`, `TodayPlan.test.tsx`, `academy.test.ts`,
  `client.test.ts`, `ObjectiveNodeCard.test.tsx` (nuevo), `UnitReviewPanel.test.tsx`,
  `FsrsReviewPanel.test.tsx` (nuevo), `unitReviewLogic.test.ts`. Backend **pytest
  1345** + ruff limpio; frontend **vitest 414** (52 archivos) + `tsc`/`vite
  build` OK; Playwright región Home/grafo desktop OK;
  `check_release_consistency` exit 0.
- **Cierre**: bump único `3.18.0` (backend `config.py` fuente única) +
  `frontend/package.json`/`package-lock.json`, `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.36 en `docs/RELEVO.md`,
  `release-notes-v3.18.0.md` (untracked). Sin cambios de CONSTITUCIÓN (v3.18 es
  mecanismo/UI, no norma) ni de launcher; `GRAPH_VERSION` permanece `2.12.0`.

### 37.37 HECHO (V3.19) — Léxico por destreza + Speaking micro-drill

- **Refactor previo (CAP-01/REFAC-01)**: `record_words` se generaliza en
  `repositories/vocabulary.py` a `record_production(user_id, words, channel)`
  (misma semántica de `appearances`/`first_seen`/`last_seen`/`production_days`/
  `item_status` + suma de la columna `<channel>_prod`); `analyze_text` la llama
  con `channel="chat"`. En `domain/vocabulary.py` nace
  `record_production_text(user_id, text, channel)` (fire-and-forget, registra y
  no lanza) y en `domain/academy.py` el helper compartido `_capture_production_text`
  sustituye los ≥7 bloques duplicados y se inserta en los 7 writers.
- **P0 — modelo (LEX-01) y volcado por destreza**: migración idempotente en
  `repositories/db.py` (4 columnas `INTEGER NOT NULL DEFAULT 0`) con backfill
  `UPDATE vocabulary SET chat_prod = appearances WHERE chat_prod = 0 AND
  appearances > 0` (todo el histórico es chat libre, verificado). Canales:
  `speaking` ← speaking assessment/misión/routes/task + pronunciación libre y
  rutas + drill; `writing` ← `submit_writing(_task)`/`objective/writing`;
  `conversation` ← `submit_attempt` de conversación guiada (texto reconstruido
  de los turnos, volcado antes del guard de longitud); `chat` ← chat libre.
  `LexicalItemOut` gana los 4 campos. Test puro: canales mixtos conservan
  `item_status`/coverage y `sum(columnas) == appearances`; dos canales el mismo
  día cuentan `production_days` una sola vez.
- **P1 — speaking micro-drill (1 nivel honesto, sin claims D5/E3)**: en
  `services/lexicon.py`, `drill_candidates(rows, limit=8)` = `exposures > 0 AND
  speaking_prod == 0` ordenada por recuerdo ascendente (misma semántica para
  `recognized_not_produced`; la UI deja de recalcular la señal — premisa 21).
  Endpoints `GET /api/vocabulary/drill/candidates` (determinista por `user_id`)
  y `POST /api/vocabulary/drill/attempt` (multipart `word` + audio: transcribe
  con el helper Whisper y puntúa con `score_pronunciation(expected=word,
  heard)`; éxito = `ok` y palabra en `breakdown.correct` →
  `record_production(channel="speaking")`). Sin evidence ni FSRS.
- **Frontend**: `PersonalDictionary` gana chips con acción real que lanzan el
  drill in-line (captura de micrófono + feedback de pronunciación existentes);
  estado de error + reintento (A6-03); al producir, la palabra sale de la lista
  y el léxico se refresca; el estado del drill vive en el panel para no
  desmontar la UI al vaciarse las candidatas. `dictionary.ts` elimina el
  recálculo cliente `recognizedNotProduced`; tipos `DrillCandidates`/`DrillAttempt`
  y `api/vocabulary.ts` (`getDrillCandidates`/`submitDrillAttempt`); i18n es/en
  del drill + copy SIGNAL-01 ("aún no producida en práctica de speaking") con
  parity; `SUBSKILL_LABELS` con los tokens de foco de listening.
- **R6-01 — retención R6 enforcement**: en `start_assessment_v2`/`submit_assessment_v2`,
  la retención exige ventana ≥ `RETENTION_MIN_DAYS` (7) desde la sesión formal
  origen y ratio estable ≥ `RETENTION_STABLE_RATIO` (0.9) antes de escribir la
  evidencia `delayed`; si no, `RetentionNotDueError` → HTTP 409 (CONSTITUCIÓN
  §6.3 impuesta en servidor; test HTTP de rechazo + re-apuntado del que fijaba
  200 el mismo día).
- **GATE-01 — objetivo `locked` no evaluable**: `_ensure_objective_evaluable`
  (punto único, usa `objective_gated_status`) antes de evaluar/completar en los
  8 writers de `domain/academy.py`; `ObjectiveLockedError` → HTTP 409 (test de
  rechazo + re-apuntado del que fijaba 200).
- **CLAIM-01/SIGNAL-01 — copy**: Speaking/Pronunciation/Conversation re-etiquetan
  "nivel oral actual (examen)" con calificador estimado (claves `speaking.*`,
  `pronRoutes.*`, `convRoutes.*`, `dictionary.recognizedNotProduced*`); la pista
  del diccionario deja de afirmar producción "al hablar" sobre un modelo de teclado.
- **ERR-01 — 404→503 transitorio**: los 5 flujos de speaking (assessment parts,
  misiones attempt/retry, speaking task, writing task) propagan
  `EvidenceExtractionError` en vez de devolver `None`, traducido a 503 en
  `routers/academy.py`; el 404 queda para estados reales (tests nuevos +
  re-apuntados).
- **LIST-01/02/03 — tokens de foco + corpus**: `word_recognition`/
  `sound_recognition`/`phrase_recognition` entran en `LISTENING_SUBSKILLS` con
  test ≥1 ítem servible por nivel del foco; corpus re-etiquetado donde el guion
  no respaldaba la etiqueta (c007/c141/c316 → detail; c021 → phrase_recognition;
  c041 → word_recognition; c042 → sound_recognition; c324 → word_recognition) y
  pares cuasi-duplicados resueltos re-autorando c079 (vs c027) y c086 (vs c031);
  `normalized_script_key` + unicidad de `script` en `validate_listening_bank`
  (test de detección). Muestras `golden/listening/samples.json` alineadas.
- **CONV-01 — reconstrucción por `mode`**: `get_turns` expone `mode` de cada
  mensaje; `interaction_evidence(turns, typed_modes=frozenset())` excluye la
  telemetría de duración/latencia/interrupciones de los turnos TECLEADOS (el
  tiempo es de redacción, no de habla) sin tocar el balance ni los recuentos;
  en la conversación guiada (`mode="conversation"` en el mini-chat) los segundos
  de habla y la señal objetiva solo computan turnos orales, y el transcripto
  sigue alimentando el volcado `conversation`.
- **Deuda externa — ADMIN-01 + BOOL-01**: `require_admin` fail-closed
  (`ADMIN_PIN=""` ⇒ 401, nunca abiertos); tests de admin re-apuntados con PIN de
  test + cabecera. `unit_review.py` endurece a `type(selected) is int`
  (bool-as-int rechazado; test nuevo).
- **Tests**: pytest **1371** (migración/backfill, desglose por canales,
  `drill_candidates`, integración HTTP "exponer → drill → producir → sale de la
  lista", rechazos 409, 503, fail-closed, BOOL-01, LIST, CONV-01) + ruff limpio;
  vitest **417** (53 archivos, `PersonalDictionary.test.tsx` del chip/drill)
  + `tsc`/`vite build` OK; `check_release_consistency` **3.19.0** exit 0;
  curriculum `--strict --quality` exit 0; i18n parity verde.
- **Cierre**: bump único `3.19.0` (backend `config.py` fuente única) +
  `frontend/package.json`/`package-lock.json`, `README`, `CHANGELOG`, `PLAN`,
  Nota superior + entrada 37.37 en `docs/RELEVO.md`,
  `release-notes-v3.19.0.md` (untracked). Sin cambios de CONSTITUCIÓN (R8/R9
  siguen como propuesta abierta) ni de launcher; `GRAPH_VERSION` permanece
  `2.12.0`. Fuera de alcance V3.19 (decisión (b)/futura): micro-drill 3 niveles
  + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo,
  WR-UI-01, LEX-03 (siembra FSRS sin señal).

### Próximos incrementos (candidatos abiertos, auditados)

> Lista de candidatos con su estado REAL auditado (2026-09-05, subagentes
> read-only sobre el código y las métricas en vivo). Los que ya se entregaron en
> V2.7–V2.9 se marcan cerrados abajo; los abiertos se ejecutan en orden con un
> subagente y un release cada uno (premisa 6: un incremento a la vez).

- ~~**🔴 P0 — Unit Coverage 100%**~~ ✅ **cerrado (V2.7/V2.8)**: las 31 unidades
  A1–C2 integran hoy las 7 secciones (unit coverage 100 %, Unit Learning Loop
  100 % 31/31, CLI `--strict --quality` exit 0). Candidato remanente de la era
  V2.6 pre-V2.7. Caveat: ningún test fija el 100 %; un futuro contenido
  incompleto lo bajaría sin fallar (`--strict` solo aborta en `empty`).
- ~~**🔴 P0 — C1/C2 depth avanzado**~~ ✅ **cerrado (V3.15, entrada 37.33)**:
  densidad avanzada entregada — C1/C2 a 20 objetivos con evidencia completa,
  `SUBSKILLS` con capa avanzada (`register`/`pragmatics`/`discourse`/`nuance`/
  `argumentation`) y re-etiquetado honesto de C1/C2, banco grammar C2
  normalizado a 15 ítems (≥ 12; deja de leer `low`) y `depth(C1) 93.1` /
  `depth(C2) 92.5` (CLI `--strict --quality` exit 0, unit coverage y loop
  100 %). La profundidad *estructural* (≥80, V2.7) ya estaba cerrada.
- ~~**🟠 P1 — Speaking Performance Evidence**~~ ✅ **cerrado (V2.9)**: el bucle
  attempt → evaluation → weakness → targeted drill → retry → improvement está
  completo, persistido y testeado como Speaking Mission Performance
  (`docs/SPEAKING_MISSION.md`, endpoints `/api/academy/speaking/mission/*`).
  Matices no imprescindibles: audio dentro de la misión (hoy texto), drills
  dinámicos (hoy plantillas por criterio), puente criterio-débil → plan.
- ~~**🟠 P1 — Listening Progression**~~ ✅ **cerrado (V2.8)**: progresión
  A1 recognition → C2 pragmatic interpretation definida
  (`docs/LISTENING_CURRICULUM.md`), alineación 38/38, operativa por rutas +
  diagnóstico + UI. Residuo de contenido abierto (B2/B3 de
  `docs/audit/B-LISTENING-CEFR.md`): re-etiquetar ítems corpus A1/A2
  (`attitude`/`speaker_intention` vs foco recognition) y techo `fast_speech`
  180–200 wpm en C2.
- ~~**🟠 P1 — Review/SRS por unidad**~~ ✅ **cerrado (V3.16, entrada 37.34)**:
  micro-review + ventanas 7/30/90 días sobre la base FSRS ya operativa. Nuevo
  `services/unit_review.py` puro (ventanas fijas desde el ancla de la unidad,
  estados upcoming/due_now/passed/failed, muestreo determinista de checks MC
  oficiales con reintento priorizando fallidos, puntuación en servidor);
  `sync_fsrs_cards` siembra/refresca cartas `objective` solo para objetivos de
  unidades completadas del nivel actual (sin pisar `reps > 0`); tabla
  `unit_review_attempts` + repos; `/api/academy/review/unit-plan` y
  `micro-review` GET/POST con gating; `UnitReviewPanel` en INICIO con i18n
  es/en. El micro-review no declara dominio ni crea evidencia (D5, E3).
  Tests: pytest 1318, vitest 392, build OK.
- ~~**🟡 P2 — Knowledge Graph + Daily Adaptive Plan**~~ ✅ **cerrado (V3.17,
  entrada 37.35)**: el plan diario deriva del grafo (D1b), vista de grafo real
  en curso y perfil (`ObjectiveNodeCard`, D2), `/api/academy/today` eliminado
  de extremo a extremo (D3), deuda v3.16 M2/M3/O2 ✅ y M1 ✅ en el cierre
  (infra DOM + 6 vitest de componente), D6 micro-líneas en la fila de sesión y
  D7 fallback silencioso sin nodo. Tests: pytest 1333, vitest 398, ruff/build/
  consistencia OK. Deuda restante del grafo + auditoría v3.17 → candidato
  abierto v3.18 abajo.
- ~~**🟡 P3 — Knowledge Graph remainder + deuda del grafo**~~ ✅ **cerrado (V3.18,
  entrada 37.36)**: resto del candidato P2 + deuda de la auditoría externa v3.16
  (37.34) + deuda de la auditoría v3.17 (37.35). **I2** ✅ — ancla de unidad
  congelada al completar (tabla `unit_review_anchors` de escritura única +
  backfill lazy; los refuerzos/decay ya no desplazan las ventanas 7/30/90) ·
  **M4** ✅ — cartas `objective` fuera del panel autograduable (single writer con
  el micro-review: siembra solo en ventana due/failed o con `reps > 0`;
  `get_fsrs_due`/`due_count` las excluyen y `/fsrs/review` → 400) · **O1** ✅ —
  cascade 7→30→90 (un intento superado tardío cierra las ventanas vencidas sin
  intento propio; el propio manda) · **O3** ✅ — plan de repaso agregado por
  niveles (`{levels, due_count}`; micro-review valida la unidad donde vive; UI
  agrupada por nivel) · **H5** ✅ — etiquetas humanas de las dimensiones del
  grafo (`GRAPH_DIMENSION_LABELS` + `dimensionLabel` en chip/`NextBestCard`/
  `ObjectiveNodeCard`/`EvidenceGraphPanel`) · **H6** ✅ — `/session`/`/next-best`
  lazy (una sola `list_evidence` y solo si hay nodos; payloads idénticos) ·
  **auditoría v3.17** ✅ — `ObjectiveNodeCard` error vs 404/sin-datos con
  reintento, `_as_float` defensivo, spec Playwright `homeGraphChip` nueva. Tests:
  pytest 1345, vitest 414, ruff/build/Playwright región desktop/consistencia OK.
- ~~**🟢 Candidato V3.19 — Léxico por destreza + Speaking micro-drill**~~ ✅
  **cerrado (V3.19, entrada 37.37, 2026-09-07)**: implementado con las
  decisiones cerradas de diseño del gerente — LEX-01 (contadores por destreza,
  no ledger), backfill idempotente `chat_prod = appearances`, micro-drill de 1
  nivel honesto con señal determinista en servidor, fixes P1 del dossier
  (R6-01/GATE-01/CLAIM-01/SIGNAL-01/ERR-01/LIST-01/02/03/CONV-01) y deuda
  ADMIN-01/BOOL-01; liberado como backend `3.18.0 → 3.19.0` (detalle completo y
  tests en la entrada 37.37, `release-notes-v3.19.0.md` y la Nota superior).
  Historia del problema que lo motivó (verificado en el código): la producción
  al léxico solo la volcaba el **chat libre** —
  `useChat.sendText` → `/api/vocabulary/analyze` →
  `domain.vocabulary.analyze_text` → `record_words` (`routers/vocabulary.py`) —
  y las **exposiciones** solo llegan de la respuesta del tutor
  (`routers/chat.py` → `record_exposure`). Ningún `submit_*` de speaking ni de
  writing vuelca el texto del alumno (`heard`/`text`) y la tabla `vocabulary`
  **no tiene columna de destreza** (`source` solo distingue
  user/curriculum/imported). Por tanto `recognized_not_produced`
  (`services/lexicon.py`, señal hoy sin consumidor) se calcula sobre producción
  *tecleada*, no *oral*: una palabra que el alumno escribió en el chat ya no
  aparece como candidata aunque jamás la haya pronunciado.
  **P0 — volcado de producción por destreza**: representación a decidir en la
  implementación (columna/contadores por destreza o ledger de eventos); el
  **invariante** es que la producción agregada (`appearances`/`production_days`),
  `item_status` y `coverage_indicator` actuales **no cambian** de semántica y el
  desglose por destreza queda derivable. Puntos de inserción naturales —las
  funciones de dominio que ya reciben el texto del alumno—:
  `submit_speaking`/`submit_speaking_task`/assessment/mission en
  `domain/academy.py`, `submit_attempt` en `domain/speaking_routes.py`,
  `domain/conversation_routes.py` (reconstruye los turnos) y
  `domain/pronunciation_routes.py`, y `submit_writing`/`submit_writing_task` en
  `domain/academy.py`; el chat queda etiquetado `chat`. Caveat honesto: los
  flujos reales de práctica oral del frontend son rutas/assessment/mission/
  conversación guiada (los endpoints `objective/speaking`/`objective/writing`
  hoy no se llaman desde la UI).
  **P1 — Speaking micro-drill** (consumidor honesto de la señal): los
  candidatos pasan a ser "expuestas y **nunca producidas oralmente**"
  (exposures > 0 y spoken == 0); generador determinista en servidor (premisa
  21) que sirve una mini-práctica reutilizando el scorer de pronunciación
  existente (`POST /api/pronunciation`, texto esperado + audio) y, al producir
  la palabra, la marca como producida por speaking y sale de la lista (cierra
  el bucle exposición → producción). El drill **no** declara dominio ni crea
  evidencia curricular (mecanismos separados, igual que el micro-review — D5/E3
  de v3.16). UI: los chips de `recognizedNotProduced` en `PersonalDictionary`
  (hoy inertes) ganan una acción real de práctica.
  **Tests/verificación**: puros backend del desglose y del generador,
  integración "exponer → drill → producir → sale de la lista", endpoints y
  vitest de la UI; gate igual que v3.18 (hoy pytest 1345, vitest 414, ruff/
  `tsc`/build limpios y `check_release_consistency`). **Caveats**: sin el
  desglose el micro-drill no puede distinguir hablar de teclear; el histórico
  previo a la migración no tiene destreza (etiquetado por defecto o excluido
  del drill, a decidir en implementación).
  > **Auditoría profunda V3.18 (2026-09-07)**: el alcance P0/P1 de este candidato
  > queda **congelado** hasta cerrar el diseño apoyado en el dossier
  > `docs/audit/I-AUDITORIA-PROFUNDA-V318.md` (eventos léxicos → destreza →
  > transfer gap → micro-drill 3 niveles → integración con el grafo). La
  > implementación debe incluir los fixes P1 marcados **(a)** en el dossier:
  > **R6-01** (retención R6), **GATE-01** (gating de objetivo), **CLAIM-01**
  > (copy "demostrado" oral), **SIGNAL-01**, **ERR-01**, **LIST-01/02**,
  > **CONV-01**, más la deuda externa **ADMIN-01** (`ADMIN_PIN=""` fail-closed,
  > `config.py:47` + `dependencies.py:19`) y **BOOL-01** (bool-as-int,
  > `unit_review.py:325/356/371`). Precondición de diseño: **CAP-01/REFAC-01**
  > (captura y punto único del volcado del texto producido). Sin cambios de
  > código ni de CONSTITUCIÓN (R8/R9 propuesta abierta).
> *(Histórico: requerimientos superados por la implementación V3.19 — entrada
> 37.37 y Nota superior.)*

---

## 38. RELEVO HACIA V3.24 — pendientes consolidados (2026-09-08)

> ⛔ **CERRADO (2026-09-08, release v3.24.0 = `8970634`).** Sección histórica:
> el alcance V3.24 (F-K1 + F-K2 + F-K8) se implementó, verificó y publicó. Ver
> Nota superior (13:35). Los P2/P3 del dossier K (F-K3…F-K7) quedan como
> candidatos del siguiente incremento.

> **Para el agente/contexto que retome ahora.** Condensa TODO lo pendiente
> conocido para avanzar de v3.23.0 a v3.24. Fuentes: dossier K
> (`docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md`, Eje 1, nuevo), dossier J
> (`docs/audit/J-AUDITORIA-TOTAL-V323.md`, total v3.23), dossier I
> (`docs/audit/I-AUDITORIA-PROFUNDA-V318.md`, profunda V3.18), `PARKED.md` y las
> notas superiores de este documento. Leer primero la Nota superior (12:30).

### 38.1 Posición actual (verificada 2026-09-08)

- HEAD `main` = **`bb3f253`** (fix documental P1-04→P1-03) sobre release
  **v3.23.0 = `f3739a9`**; versión declarada `3.23.0` (`backend/config.py`).
- Gates en verde reproducidos: pytest total **1455** (dossier J G1) ·
  baterías del Eje 1 **G1 310** + **G2 328** (dossier K, 638 tests del eje) ·
  vitest **450**/57 archivos · ruff · `tsc`/`vite build` ·
  `check_release_consistency` 3.23.0 exit 0 · CI GitHub Actions success.
- Árbol limpio; única escritura de la auditoría = dossier K (untracked).
- Estado del árbol a 2026-09-08 13:35: **release v3.24.0 `8970634` publicado**
  en `main` con CI green (sección 38 cerrada como histórico). Suite backend
  **1457 passed** · Eje 1 **G1 311** + **G2 329** (640, +2 tests e2e) · ruff
  limpio. Detalle: Nota superior y `agentes/v324-calibracion-salida.md`.
- CONSTITUCIÓN sin cambios V3.19→V3.23; **R8/R9 siguen como propuesta abierta**
  (no tocar código si no se cierra la propuesta).

### 38.2 Veredicto que motiva V3.24

El dossier K **NO aprueba el cierre del Eje 1**: cadena actividad →
`academy_evidence` → mastery por objetivo → perfil → CEFR determinista y sólida
(escritor único, kinds canónicos, no contagio, certificación con `delayed`
≥7 días), pero **F-K1** y **F-K2** (P1) deben decidirse antes de cerrar el
Student Model. `PLAN.md` ("Siguiente incremento") sigue sin briefing: el
candidato V3.24 sale de este bloque.

### 38.3 Alcance P1 recomendado para V3.24 (decisión del gerente)

| # | Problema (1 línea) | Evidencia clave | Opciones / acción | Test que fija hoy |
|---|---|---|---|---|
| **F-K1** | `novel` sin emisor: solo se emiten `familiar`/`transfer`/`delayed`, pero MASTERED, readiness B2+ y el grafo exigen `novel` → `mastery_missing: novel` permanente en la escalera Assessment 2.0 | `assessment_v2.py:543-548`; `adaptive.py:177-206`; `cefr_matrix.json` (`novel_required`); `AssessmentLadder.tsx:155-157`; dossier K G1/G2 | (a) crear emisor real de `novel` (modalidad de escalera/tarea = uso en contexto nunca practicado); o (b) relajar/renombrar gate + matriz CEFR a lo emisible y documentar frontera. Premisa 12: test e2e del emisor | `test_assessment_v2.py:156-164` (solo pasa con `novel` inyectado a mano) |
| **F-K2** | El estimado vive en un único nivel con escala `numeric = 1 + 5·overall` no calibrada y re-basa al matricular nivel nuevo | `domain/academy.py:580-591,619-627`; `adaptive.py:59-88`; dossier K **G4** (dominar A1 → **B2**; aprobar examen A1 → **Pre-A1**) | Anclar la etiqueta a niveles completados/certificados + tramo actual (no proyección lineal del mastery de un nivel). Tests e2e: (a) dominar A1 completo no estima ≥ B2; (b) aprobar A1 no baja de A1 | `test_academy.py:1389-1408` (solo usuario vacío; no fija el salto) |

Opcionales ampliables al mismo release (P2, dossier K): **F-K3** separar por
`source` la evidencia de speaking assessment/misión (hoy `objective_id=""`) y
persistir `cefr_target`; **F-K4** marcar la etiqueta por destreza
(`SkillState.band`) como `estimated_band`. **F-K8** (tests del salto de nivel)
es prerequisito del fix F-K2.

### 38.4 Backlog consolidado de pendientes

#### Eje 1 — dossier K (todos abiertos)

| ID | Sev | Qué es (resumen) | Dónde (clave) | Nota para V3.24 |
|---|---|---|---|---|
| F-K1 | P1 | `novel` sin emisor; gates que lo exigen | ver 38.3 | alcance P1 recomendado |
| F-K2 | P1 | escala del estimado por nivel + rebase | ver 38.3 | alcance P1 recomendado |
| F-K3 | P2 | doble vía speaking assessment/misión no mueve `score` por objetivos | `academy.py:968-973,1167-1174`; `services/academy.py:398-445` | decidir con F-K1/K2 o release siguiente |
| F-K4 | P2 | `band` por destreza = estimado sin marca | `profile.py:65-110`; `schemas/profile.py` | renombrar a `estimated_band` |
| F-K5 | P2 | colisión semántica `transfer`/`retention` léxica (señal) vs académica (gate §6.3) | `lexicon.py:442-495` vs `assessment_v2.py:370-410,543-548` | documentar en schemas/tooltips |
| F-K6 | P2 | modelo léxico agregado sin historia de eventos fina | `repositories/vocabulary.py`; deuda `lexicon.py:468-472` | = frontera `support_level` por evento |
| F-K7 | P3 | nomenclatura heredada `appearances`/`exposures` | `lexicon.py:470-471`; `schemas/vocabulary.py` | renombrado conceptual no destructivo |
| F-K8 | P3 | sin test de salto de nivel | `test_academy.py:1389-1408` | prerequisito de F-K2 |

#### Dossier J — observaciones abiertas (total v3.23)

| ID | Sev | Qué es | Dónde | Acción |
|---|---|---|---|---|
| H1 | baja | docstrings P1-04→P1-03 | `lexicon.py:229-231`, `test_lexicon.py:148-149` | ✅ **cerrado por `bb3f253`** (no reabrir) |
| H2 | baja | umbrales léxicos de 1 día acreditan chip "Retention" (≠ §6.3 ≥7 días) | `lexicon.py:44-63`; i18n tooltip | documentar distinción señal vs gate; calibrar con datos |
| H3 | informativa | 190 claves i18n "sin uso" (higiene, no error) | `generated/i18n-report.md` | deuda de higiene opcional |
| H4 | informativa | warning deprecación upstream (`httpx`→`httpx2`) en pytest | salida G1 (warnings summary) | revisar en la próxima subida de dependencias |

#### Dossier I — ítems abiertos que tocan el eje (estado verificado en K)

| Ítem | Estado en v3.23 | Nota |
|---|---|---|
| GRAPH-01 | abierta | grafo no distingue REC de producción; `transfer` = kind, no modalidad (`evidence_graph.py:159-240`); subirá GRAPH_VERSION cuando se toque |
| CP-01 | abierta | doble vía de "producción" (relacionada con F-K3) |
| LEX-02 | abierta (parcial) | la práctica académica no genera `record_exposure` (solo chat); sí hay volcados de producción/retrievals |
| LEX-03 | mitigada parcial | la siembra curricular (`seed_objective_vocabulary`) crea filas `learning` sin señal tras lección/assessment; decidir si no sembrar sin evento |
| TOK-01/USE-01 | abiertas | `lexical_tokens` del LLM se descartan; frontera V3.24 (support_level) |
| SKILL-01 | abierta (ver F-K3) | misión+assessment mezcladas en el pool `skill=speaking` |
| CONV-02 | abierta | conversación guiada sin evidencia formal de interaction (decisión: emitir o documentar como práctica D5/E3) |

> Ítems del dossier I **fuera del eje** (A1-04/A1-05, A2-06/A2-07, A3-06/
> A3-07, A5-05/A5-06, A6-04, WR-UI-01…): muchos se cubrieron en V3.19–V3.23
> (p. ej. A2-07 → endpoint `drill_candidates`, A6-03 → estado error del
> diccionario, R6-01/GATE-01/CLAIM-01/SIGNAL-01/ERR-01/LIST-01/02/03/CONV-01/
> ADMIN-01/BOOL-01 en V3.19). **Estado no re-verificado en v3.23**: comprobar
> contra el árbol antes de implementar cualquiera de ellos.

#### Fronteras V3.24 y deuda declarada (no son bugs)

- **`support_level` por evento** (copied/guided/cued/independent/spontaneous):
  inferible tras el mapeo de actividades; frontera explícita en release-notes
  v3.23, dossieres J/K y PARKED. Si V3.24 lo aborda, resolver antes F-K6
  (ledger léxico por evento) y TOK-01/USE-01.
- **Backfill de retrieval histórico**: NO (decisión firme, ancla retrospectiva
  injusta; ver Nota 11:15 v3.23).
- **Telemetría ASR persistente + frontera `LANGUAGE_MISMATCH`**: fuera de
  alcance desde V3.22 (Nota 10:30).
- **Superficie de "recuerdo de significado"** (Recall → Sentence → Context →
  Free Transfer): preparación de la escalera, fuera de alcance V3.22.
- **Renombre `appearances → production_count`**: frontera asumida (F-K7).
- **Micro-drill 3 niveles + integración con el grafo** y **flag de modalidad
  oral/tecleo**: fuera de alcance V3.19.
- **F6.3 Contexto/Transfer libre** (Speaking/Listening): aplazado a auditoría
  pedagógica (Nota V3.21).
- **R8/R9 de la CONSTITUCIÓN**: propuesta abierta (documento, sin código).
- **PARKED** (`docs/audit/PARKED.md`): calibración con alumnos reales, FSRS por
  tipo de memoria, KPI de transfer, audio humano real, 50 claves i18n huérfanas
  (candidatas legacy), patrón loading/error en paneles profundos (F4), sesgo
  posicional MC en corpus/checks (fix mecánico pendiente de tu aprobación),
  matriz de dispositivos (G) y variabilidad LLM de speaking con Ollama real.

### 38.5 Reglas de proceso (premisas 5/6/12/21)

- Un incremento a la vez, con su release; briefing de subagente en `agentes/`.
- **Premisa 12**: cualquier fix de F-K1/F-K2 va precedido de test de extremo a
  extremo que falle hoy; read-only durante auditorías.
- **Premisa 21**: las señales se deciden en servidor; la UI no recalcula.
- Cierre de release: bump `backend/config.py` (fuente única) + frontend
  `package.json`/lock, `README`, `CHANGELOG`, `PLAN`, Nota superior + entrada
  en `docs/RELEVO.md`, `release-notes-v3.24.0.md`, `check_release_consistency`.

### 38.6 Primeros pasos sugeridos para la sesión que retome

> ✅ **CERRADO (2026-09-08, release v3.24.0 `8970634`).** Lista histórica; el
> siguiente incremento parte de los P2/P3 del dossier K (F-K3…F-K7).

1. Leer: Nota superior de este documento (13:00) → sección 38 → dossier K
   (Hallazgos, Veredicto, G4) → dossier J (si se quiere el contexto total).
2. **Estado de V3.24 (2026-09-08 13:00):** alcance cerrado (F-K1 b relajar +
   F-K2 a anclaje + F-K8) e implementado en el árbol — decisiones, tests-first y
   detalle en `agentes/v324-calibracion-salida.md` y el PLAN. Suite backend
   completa **1457 passed** + ruff limpio (sin commit ni bump).
3. Siguiente paso: cerrar el release V3.24 — baterías G1/G2 del dossier K (638)
   + frontend (sin cambios de código) + CI y la higiene de cierre de la sección
   38.5 (bump `3.23.0 → 3.24.0`, `README`, `CHANGELOG`, `PLAN`, entrada en este
   documento, `release-notes-v3.24.0.md`).




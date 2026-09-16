# Plan de proyecto — English Tutor (100% local)

> Mantenido por el gerente del proyecto (yo). Los subagentes se ejecutan desde
> agentes locales: cada tarea se describe en `agentes/<nombre>.md`.
>
> **Premisas y reglas:** `docs/PREMISAS.md` · **Arquitectura:** `docs/ARQUITECTURA.md` ·
> **Guía de desarrollo:** `docs/DESARROLLO.md`.

## Estado actual

- ✅ **V3.70.0 — Auditoría pedagógica + CEFR (2026-09-15)** (**Versión estable `3.70.0`**, app `3.69.0 → 3.70.0`). **Release de MEDICIÓN, no de capacidad: SIN migración, SIN bump de `GENERATOR_VERSION`, SIN tocar el banco, SIN tocar el currículum y SIN tocar el argmax del Planner.** Igual que V3.69 validó la **arquitectura** del Adaptive Engine, V3.70 mide la **pedagogía real** del contenido y de los instrumentos en **cinco ejes** (AA→AE) más una síntesis (AF). **El único diff fuera de tests y documentación son cinco subcomandos NUEVOS y de SOLO LECTURA en `backend/scripts/audit_dossier.py`**, declarados como herramienta de medición, no ruta de producto. **(A) Eje 1 — adecuación CEFR (`AA`):** **un P0, el 89,4 % de los 368 checks del currículum tiene la correcta en la posición 0** (329/368); A1 entero por encima de su banda de velocidad (86/200) y C1/C2 casi enteros por debajo (18/20, 19/20); `connected_speech: true` sin reducción real en **C1 14/14 y C2 20/20**; escalera de velocidad no monótona; 4 de 5 `inference` de A2 resolubles por palabra literal; **deriva de `docs/audit/generated/` corregida** (declaraba C1 = 14 y C2 = 14 objetivos frente a 20 y 20). Limpio: 0/490 ítems fuera de banda de dificultad y 0 checks fuera de las `skills` de su objetivo. **(B) Eje 2 — cobertura (`AB`):** corpus B1–C2 al **13,9–20,0 %** de su objetivo declarado; `reading` sin `services/reading.py` pese a 15 objetivos y 18 checks; **manifest de audio humano versionado y vacío** (`entries: []`); `mediation` sin competencias, corpus, canal, scorer ni UI; `interaction` sin competencias ni canal; escenarios A1 = 1 y C1 = 1. **(C) Eje 3 — feedback (`AC`):** **4 de 7 reglas de grammar nunca pueden confirmarse** (`confidence < 0.8`) y **solo 2 pueden alcanzar la racha de dominio** (patrón positivo); `reading` y `mediation` sin canal de corrección; el error detectado dentro de las rúbricas solo resta nota y **no genera la explicación**; fijado por test que **la nota la decide el scorer determinista, nunca el LLM**. **(D) Eje 4 — maestría (`AD`):** **9 modalidades · 8 en matriz · 7 canales**; `interaction` y `mediation` **no pueden acreditar evidencia por ninguna vía**; **`novel_required = 0` en las 48 celdas** pese a que el emisor existe desde V3.26; **las filas sin `objective_id` no acreditan éxito** (medido: `result 1,0` → `success False`, F-K3). Fijado: sin evidencia no se afirma nada y `transfer_required` crece 0 → 4. **(E) Eje 5 — instrumentos (`AE`):** el criterio de parada del placement **es inalcanzable** (`SE ≥ 0,7071 > 0,5`, cota analítica del 1PL declarado); el **examen de B1 tiene los 12 ítems en dificultad 1** igual que el de A1; **cuatro de seis niveles sin examen final**; sesgo de forma del placement (correcta = más larga única en 50 %, 70,8 % en posición 1, posición 3 nunca correcta). Fijado: los tres estimadores de banda coinciden (0 desacuerdos) y el banco no tiene huecos de dificultad. **(F) Síntesis (`AF`):** **1 P0 · 15 P1 · 12 P2 · 5 P3** (33 hallazgos abiertos) y **4 propiedades positivas**; cruces: `reading` roto en 3 planos y `mediation` en 5, la forma de los ítems como patrón más extendido, lo declarado superando a lo realizado en 5 instancias, y el producto **más completo donde el alumno empieza que donde debería llegar**. **(G) Tests:** 5 ficheros nuevos, **48 tests** que fijan cada hallazgo (si se cierra un hueco, el test falla y obliga a re-auditar); backend **2600 passed** (2552 → +48). **Honestidad:** no demuestra eficacia pedagógica (se midió adecuación declarada frente a `docs/audit/CEFR-REFERENCE.md`, **que no es un documento CEFR normativo**), no valida el nivel real de un alumno, no audita la calidad acústica (no hay audio humano grabado: todo es metadato declarado) ni el texto del LLM en ejecución, no audita el frontend, **no cierra los 6 P2 de la auditoría de V3.69** y **no corrige nada**: asigna cada insuficiencia a su fase (contenido → V4.0.x · motor/acreditación → Planner 4.0 · instrumentos → V4.0.x/V3.72). Ver `release-notes-v3.70.0.md`.

- ✅ **V3.69.0 — E2E + Adaptive Engine Validation (2026-09-15)** (**Versión estable `3.69.0`**, app `3.68.0 → 3.69.0`). **Release de VALIDACIÓN, no de capacidad: SIN migración, SIN bump de `GENERATOR_VERSION`, SIN tocar el banco, SIN capacidad pedagógica nueva, SIN tocar el argmax del Planner y con **cero líneas de lógica de PRODUCTO** (solo tests, bumps de versión y documentación).** Demuestra **experimentalmente y por HTTP** que la cadena `Evidence → Student State → Decision Projection → Task selection → Decision → Serving → Attempt → Outcome → Evidence` funciona como **una sola pieza**, que es lo que la auditoría externa `Y` de V3.68 (§19–§20) pedía antes de entrar en cualquier componente probabilístico (calibración real, ELG real). **Regla dura respetada:** ningún escenario E2E ha demostrado que la arquitectura sea insuficiente, así que **no se ha tocado producción**; las desviaciones medidas se registran como **deuda declarada**. **(A) Batería E2E (`backend/tests/test_adaptive_e2e_v369.py` nuevo, 20 tests HTTP reales):** `TestClient` sobre `main.app` con BD en `tmp_path`, fechas fijas y sin `random()` — E01 alumno nuevo (arranque en frío **sin** provenance y circuito completo con estado medible) · E02 skill débil sube su prioridad · E03 retención elige repaso · E04 hueco de transferencia elige producción · E05 misma tarea en dos contextos ⇒ mismo `task_key` y distinto `task_instance_key` · E06 `ok, ok, ko` baja el `p_success` · E07 `unclear` no penaliza mastery y queda fuera de la calibración · E08 abandono no contamina `ko` · E09 `GET ×3` no duplica decisiones · E10 doble submit idempotente · E11 submit contradictorio rechazado · E12 usuario ajeno no cambia nada · E13 target ajeno rechazado · E14 transición inválida rechazada · E15 servida caducada (nunca `completed`) · E16 **determinismo del Planner** (nivel puro **y** nivel HTTP, comparación byte a byte) · E17 hueco de andamiaje (aserción **diferencial**) · E18 evidencia entrando DURANTE la decisión (frescura por HTTP + reproducción determinista del TOCTOU) · E19 dos alumnos activos sin mezcla **en ambas direcciones** · E16b contrato completo del endpoint huérfano `GET /api/learning/decisions` (calibración, `provenance_health`, filtros y paginación), que no tenía ninguna cobertura HTTP. **(B) Contrato de frontend con red mockeada (`frontend/tests/visual/drillProvenance.spec.ts` nuevo, 2 specs de navegador):** sobre el navegador **real** y con el job `playwright` (que corre **sin backend**) fija que el drill envía el `decision_id` en el GET del peldaño (query) y en el POST del intento (body), que declara `started` **después** de que el peldaño esté cargado (la FSM rechaza `computed → started`), que declara `abandoned` al desmontar y que **sin** `decision_id` **no declara nada**. **(C) Hallazgos registrados (tabla §«Hallazgos E2E» de la release note; los cinco ACEPTADOS como deuda, ninguno exige tocar producción):** E01(a) el arranque en frío no tiene provenance (degradación declarada de V3.64); E08 `abandoned_count` cuenta filas `completed` con `outcome = "abandoned"` (inalcanzables por el camino público) y el abandono del lifecycle queda fuera del denominador pero **invisible** en el informe; E15 una servida caducada se **reabre** (`provenance_status = "reopened"`) en vez de quedar `abandoned` (el registro representa el estado final, no la historia ⇒ P2-04); E17 `SCAFFOLDING_PENALTY` **suma** al hueco de la modalidad limitante, de modo que el alumno con dependencia de apoyo recibe un valor esperado **MAYOR**, no menor (nombre engañoso ⇒ Planner 4.0 / P2-06); §F-1 el doble montaje de `StrictMode` (el launcher sirve `npm run dev`) declara un `abandoned` **prematuro** que la FSM rechaza con contador `invalid_transition` (no corrompe nada, pero ensucia la señal de salud; arreglo mínimo propuesto para V3.70). **Tests:** backend **2552** (2532 → **+20**) · Vitest **659** (sin cambios) · nuevas **2** specs de navegador · `ruff` limpio. **Honestidad:** es una release de **validación**: el valor está en lo que **mide** y en lo que **declara** (incluidos cinco hallazgos incómodos), no en lo que añade; el `decision_id` determinista, la FSM y la calibración descriptiva siguen con la misma deuda declarada (P2-01…P2-06, P3-01/P3-02). Ver `release-notes-v3.69.0.md`.

- ✅ **V3.68.0 — Adaptive Engine Hardening & Integrity (2026-09-15)** (**Versión estable `3.68.0`**, app `3.67.0 → 3.68.0`). **Release SIN migración destructiva (migración ADITIVA e idempotente: dos columnas en `decision_records`), SIN bump de `GENERATOR_VERSION`, SIN tocar el banco, SIN capacidad pedagógica nueva y SIN tocar el argmax del Planner que cierra los TRES P1 de segunda generación de la auditoría de V3.67 más el P2-08. Es la PRIMERA release de la serie que toca el frontend por un motivo de MEDICIÓN y no de UI.** **(A) Task Definition vs Task Instance (P1-01, `services/observed_difficulty.py`):** `task_key_parts(target_id, activity, support_level, served_difficulty, assessed_skill)` es la identidad de la DEFINICIÓN (cinco componentes, **sin contexto**) — lo que el Planner puede calcular ANTES de elegir instancia — y `task_instance_key_parts(..., context)` la del caso concreto; `empirical_success_by_task(rows)` pasa a agrupar por **`task_key`** y se añade `empirical_success_by_task_instance(rows)`; `task_signature_parts`/`task_signature` se ELIMINAN (rename, no alias). **Cierre del P1-01:** hasta V3.67 la firma incluía el contexto mientras el candidato lo construía vacío, así que una tarea de transferencia del ledger NUNCA resolvía `p_success_source = "task_empirical"`. **(B) FSM real (P1-02, `repositories/decision_records.py`):** tabla DECLARADA `_ALLOWED_TRANSITIONS` (`computed → served`, `served → served`/`started`/`completed`/`abandoned`, `started → started`/`completed`/`abandoned`, `completed → completed` solo con outcome IDÉNTICO, `abandoned → abandoned`; todo lo demás rechazado con contador) y `_transition()` pasa de `UPDATE` ciego a **compare-and-set** racional sobre `decision_id + user_id + estados de origen válidos`; `close_stale(user_id, *, before_iso)` barre `served`/`started` antiguas a `abandoned`. **(C) Integridad y propiedad (P1-03):** guardas de `user_id` (propiedad) y `target_id` con fallo **best-effort no-op silencioso + contador** (el rechazo se ve en `transition_health()`, jamás rompe la cola ni el drill); la ACTIVIDAD no es puerta — se REGISTRA como `executed_activity` y se deriva `activity_match`, porque el drill degrada peldaños legítimamente. **(D) Re-servicio (`provenance_status` vivo):** el upsert REABRE una fila terminal SIN outcome medible (`abandoned`, o `completed` con `unclear`/`''`) a `computed` con `provenance_status = "reopened"`, mientras que una fila con medición real (`ok`/`ko`) NO se sobrescribe (cuenta como `closed_decision`); `build_decision_id` hashea `task_key` y `DECISION_POLICY_VERSION = "v3.68.0"` (cambia el hash: las filas de V3.67 quedan en `computed`). **(E) Migración aditiva (`db.py`):** `task_key` y `executed_activity` con defaults vía `PRAGMA table_info`. **(F) Calibración honesta (P2-08, `calibration_report`):** solo entran en las bandas las filas MEDIDAS (`outcome ∈ {ok, ko}`); `unclear` y `abandoned` salen del denominador y del `calibration_error`; contadores explícitos `completed_count`/`measured_count`/`unclear_count`/`abandoned_count`; `list_decisions` expone `task_key`/`task_instance_key`/`executed_activity`/`activity_match`/`outcome_measured`. **(G) Barrido y salud (`domain/review.py`):** `DECISION_ABANDON_AFTER_HOURS = 24` y `close_stale` best-effort por construcción de cola; `provenance_health()` devuelve `{record_failures, transition_health}`. **(H) Endpoints (`routers/vocabulary.py`):** los helpers llevan `user_id`/`target_id`/`activity`; `drill_transfer_context` mueve su `mark_served` DESPUÉS de resolver el contexto (declara la instancia realmente servida); `drill_write_attempt` declara `served` al inicio; nuevo `POST /api/vocabulary/drill/decision-lifecycle` (`event ∈ {"started","abandoned"}` validado por `Literal`). **(I) Frontend, el eslabón que hace REAL el ciclo:** hasta V3.67 el cliente NUNCA devolvía `decision_id` (cero ocurrencias en `frontend/src`), así que el ciclo de vida era código muerto en producción; `ReviewQueueItem` gana `decision_id`/`task_key`/`task_instance_key`, TODAS las funciones del drill reenvían `decisionId?` (query en los GET, body/FormData en los POST), nuevas `markDrillStarted`/`markDrillAbandoned`, `wordDrill.tsx` declara `started` cuando el peldaño YA está cargado (evita la carrera con el GET que la FSM rechazaría) y `abandoned` al desmontar, y `ReviewQueueSection` pasa `decisionId={active.decision_id}`. **Tests:** `test_decision_v368.py` (**29**, test-first) fija el `task_key` vs `task_instance_key` con la regresión del P1-01, la FSM completa con rechazos contados, la propiedad y el target, el re-servicio, el barrido, la calibración honesta y el round-trip del router; actualizados `test_decision_v367.py`/`test_decision_v366.py` y los tests de frontend. **Honestidad:** es un arreglo de MEDICIÓN (no cambia ninguna decisión de tarea); la FSM es declarada y probada; los fallos de integridad son no-op contabilizados; una medición real nunca se sobrescribe; `DECISION_POLICY_VERSION` cambia el hash y las filas de V3.67 se quedan en `computed`. Ver `release-notes-v3.68.0.md`.

- ✅ **V3.67.0 — Task Identity 2.0 + Decision Lifecycle + Provenance Analytics (2026-09-15)** (**Versión estable `3.67.0`**, app `3.66.0 → 3.67.0`). **Release SIN migración destructiva (migración ADITIVA e idempotente sobre `decision_records`), SIN bump de `GENERATOR_VERSION`, SIN tocar el banco y SIN cambios de UI que cierra los DOS P1 de la auditoría de V3.66: (P1-01) la identidad de tarea deja de ser el `target_id` y pasa a ser `task_signature` (la firma canónica de SEIS componentes), de modo que el MISMO ítem con distinta actividad, apoyo o carga servida es OTRA tarea, y (P1-02) el Decision Provenance deja de ser append-only escrito en el GET y pasa a ser un UPSERT idempotente con `decision_id` DETERMINISTA y ciclo de vida `computed → served → started → completed/abandoned`, con round-trip del cliente por los GET/POST del drill.** **(A) Task Identity 2.0 (`services/observed_difficulty.py`):** `task_signature_parts()` (pura, determinista) combina `(target_id, activity, support_level, served_difficulty, context, assessed_skill)` con `difficulty.format_vector` y normaliza los componentes ausentes a `""`; `task_signature(row)` deriva la firma de una FILA del estado usando `task_semantics.assessed_skill_for(activity)` (NO el `modality` canónico) para que la firma del ledger y la del candidato CASEN; nueva `empirical_success_by_task(rows)` que agrupa por FIRMA (Nivel `task_empirical`) con la MISMA puerta espaciada de V3.54. **(B) Estadística honesta (P2-06/07):** `_empirical_entry()` devuelve `p_success_observed` (nombre honesto), `raw_rate` = `long_term_rate` (tasa global cruda) y `recent_rate` (últimos `RECENT_ATTEMPTS = 5` intentos, descriptiva, sin suavizado ni ML); `p_success` se CONSERVA como alias retrocompatible de V3.66. **(C) Jerarquía de CUATRO niveles (`services/planner.py`):** `expected_learning_value`/`select_task_by_elv` ganan `target_empirical_success` y resuelven `p_success` con el orden `task_empirical` > `target_empirical` > `skill_empirical` > `margin`; `_task_empirical_for(by_activity, activity)` resuelve la tasa por TAREA por ACTIVIDAD del drill (y acepta un payload escalar retrocompatible); el payload añade `p_success_source = "target_empirical"` y `target_p_success`. **(D) Decision Lifecycle (P1-02, `repositories/decision_records.py` + `db.py`):** `decision_id` pasa de `uuid4` a hash determinista (`build_decision_id`: sha256 de `user_id`/`target_id`/`task_signature`/`decision_start_fingerprint`/`policy_version`) y `record_decision()` pasa de INSERT a UPSERT (`ON CONFLICT(decision_id) DO UPDATE`) con índice único `idx_decision_records_decision_id` (el ciclo GET→GET→GET ya no duplica filas); transiciones `mark_served`/`mark_started`/`mark_completed(decision_id, outcome)` sobre `computed`/`served`/`started`/`completed`/`abandoned`; `DECISION_POLICY_VERSION = "v3.67.0"`. **(E) Migración aditiva e idempotente (`db.py`):** se elimina el alias confuso `evidence_fingerprint` (P3-09) con guarda para SQLite sin `DROP COLUMN` y se añaden 12 columnas con defaults (`task_signature`, `context_id`, `context_instance`, `served_load_json`, `support_level`, `assessment_mode`, `decision_status`, `served_at`, `started_at`, `completed_at`, `outcome`, `provenance_status`); las filas legacy quedan con los defaults. **(F) Snapshot coherente (P2, `domain/decision.py`):** `_recompute()` devuelve el estado y AMBOS mapas empíricos DENTRO del mismo lazo de sellado, de modo que `state_fingerprint` y el mapa describen el MISMO snapshot de evidencia; `project_state` expone la clave aditiva `empirical_success_by_target`. **(G) Léxico (`services/lexicon.py`):** `_task_empirical_by_activity()` resuelve la firma del candidato por actividad y `_task_signature_for()` produce la firma de la tarea FINAL servida (la MISMA que agrupa el ledger); el ítem expone `task_signature`/`served_load`/`assessment_mode`. **(H) Round-trip del ciclo de vida (`domain/review.py` + `routers/vocabulary.py` + esquemas):** el `decision_id` se propaga a cada ítem servido; los GET de peldaño llaman `mark_served` y los POST de intento `mark_completed(decision_id, outcome)` (`ok`/`ko`/`unclear`); los esquemas de intento ganan `decision_id` opcional. Todo best-effort (nunca rompe la cola). **(I) Analítica del provenance (P3-10/11/12):** nuevo `GET /api/learning/decisions` con `list_decisions` (filtros `status`/`target_id`, paginación) y `calibration_report` (predicted vs observed por bandas de 0.2 sobre las filas `completed`, con `calibration_error` medio y ponderado); `review.provenance_health()` expone el contador local de pérdida silenciosa (`record_failures`). **Tests:** `test_decision_v367.py` (**12**, test-first) fija el determinismo y la sensibilidad de la firma, la firma distinguiendo DOS actividades del MISMO `target_id`, la puerta espaciada, las tasas `raw`/`recent`/`long_term`, la jerarquía completa, `_task_empirical_for`, la idempotencia del UPSERT, la metadata de tarea, las transiciones del ciclo de vida y el informe de calibración; actualizados `test_decision_v366.py` (ítem → `target_empirical`) y `test_decision_projection_v364.py` (nueva aridad de `_recompute`). **Honestidad:** la identidad de tarea es AHORA la firma completa (P1-01 cerrado) y el provenance es idempotente y con ciclo de vida (P1-02 cerrado); el informe de calibración es DESCRIPTIVO (sin ML ni suavizado) y la `recent_rate` es una tasa cruda de la cola reciente, no una tendencia. Ver `release-notes-v3.67.0.md`.

- ✅ **V3.66.0 — Task-Level Empirical Success + Decision Provenance (2026-09-15)** (**Versión estable `3.66.0`**, app `3.65.0 → 3.66.0`). **Release SIN migración destructiva (una tabla append-only idempotente `decision_records`), SIN bump de `GENERATOR_VERSION`, SIN tocar el banco y SIN cambios de UI que cierra los DOS P1 de la auditoría de V3.65: (P1-01) el estimador que gobierna el Planner 3.0 pasa a ser `P(éxito | alumno, tarea)` POR TAREA (`target_id`), no agregado por skill, y (P1-02) la huella de snapshot se desdobla en DOS campos explícitos (`decision_start_fingerprint` + `state_fingerprint`) con invariante declarado. Añade Decision Provenance: cada carta servida por el Planner 3.0 se registra append-only con su evidencia y su política.** **(A) Estimador puro por ITEM (`services/observed_difficulty.py`):** `empirical_success_by_target(rows)` agrupa las filas canónicas SOLO por `target_id` (la granularidad por pareja que V3.65 aún colapsaba) → `{successes, attempts, p_success, days}` con la MISMA puerta espaciada de V3.54; sin muestra espaciada o sin `target_id` el ítem NO aparece. **(B) Decision Projection (`domain/decision.py`):** `_task_empirical_success()` lee `list_attempt_rows` en una lectura INDEPENDIENTE de la caché del estado y `project_state` expone `empirical_success_by_task` (`{target_id: estimación}`); el camino del perfil lo deja vacío. **(C) Planner 3.0 (`services/planner.py`):** `expected_learning_value`/`select_task_by_elv` ganan `task_empirical_success` y resuelven `p_success` con el orden `task_empirical` > `skill_empirical` > `margin`; el payload añade `p_success_source` y `task_p_success` (auditabilidad). **(D) Léxico (`services/lexicon.py`):** `review_queue_item` extrae la estimación del `target_id` del ítem y la propaga por `recommend_review_activity`/`_task_decision`/`_learning_value`; sin proyección degrada byte-idéntico a V3.65. **(E) Huellas explícitas (P1-02, `domain/decision.py`):** `decision_start_fingerprint` (huella al INICIO de la decisión; `snapshot_fingerprint` queda como alias retrocompatible) SEPARADO de `state_fingerprint` (la huella del estado efectivamente proyectado). **(F) Decision Provenance (`repositories/decision_records.py` nuevo + `db.py` + `review.py`):** tabla append-only `decision_records` y `record_decision()` con `DECISION_POLICY_VERSION = "v3.66.0"`; `get_review_queue` registra una fila best-effort por cada ítem con bloque `decision` (nunca rompe la cola). **Tests:** `test_decision_v366.py` (**13**, test-first) fija el A-vs-B fundamental (dos tareas con distinto `target_id` y distinta tasa; el planner elige por la tasa POR ÍTEM), el agrupado por ítem + puerta espaciada, la política de resolución, la honestidad de las dos huellas y la persistencia de `record_decision`. **Honestidad:** la granularidad por pareja AHORA SÍ gobierna `p_success`; el provenance es escritura best-effort para auditoría en bruto (la lectura/agregación de `decision_records` es V3.67+). Ver `release-notes-v3.66.0.md`.

- ✅ **V3.65.0 — Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica) (2026-09-15)** (**Versión estable `3.65.0`**, app `3.64.1 → 3.65.0`). **Release SIN migración de BD, SIN bump de `GENERATOR_VERSION`, SIN tocar el banco y SIN cambios de UI** que convierte la dificultad observada de MEDIDA DECLARADA (V3.63) en una ESTIMACIÓN EMPÍRICA por pareja que, cuando existe, gobierna el `p_success` del Planner 3.0 — sin romper la pureza del planner ni la degradación byte-idéntica. **(A) Telemetría completa (`repositories/evidence.py`):** nuevo lector `list_attempt_rows` (éxitos Y fallos + `target_id`/`surface_form`); `list_observed_rows` queda intacto (hasta V3.64 el léxico devolvía SIEMPRE `success_rate = 1.0`). **(B) Fila canónica (`services/skill_state.py`):** `_row` gana `target_id` (aditivo) y `_lexicon_rows` procesa fallos como INTENTOS (la puerta espaciada sigue leyendo SOLO `success`). **(C) Estimador puro (`services/observed_difficulty.py`):** `empirical_success(rows)` agrupa por clave de tarea (`target_id`/`actividad`/`dificultad servida`) → `{successes, attempts, p_success, days}` con la MISMA puerta espaciada de V3.54; puro, determinista, sin umbrales nuevos. **(D) Decision Projection (`services/decision_projection.py` + `domain/decision.py`):** la celda expone `empirical_success` (de la `confidence` ya calculada, NO `assessment_confidence`) y `empirical_success_by_skill` por eje léxico; `project_state` añade la clave aditiva. **(E) Planner 3.0 (`services/planner.py` + `services/lexicon.py`):** `expected_learning_value`/`select_task_by_elv` ganan el parámetro opcional `empirical_success` que, si es válido (0..1), gobierna `p_success` (marcado `p_success_empirical`); sin él, byte-idéntico a V3.64. **Tests:** `test_observed_difficulty_v365.py` (18, test-first) fija la tasa empírica < 1.0 con fallos, la agrupación, la pureza y la degradación byte-idéntica. **Honestidad:** la estimación se inyecta al NIVEL DE SKILL (cómo decide el planner), no por ítem; la granularidad por pareja fina (`empirical_success` por `target_id`) queda disponible para V3.66 (Adaptive Instance Selection). Ver `release-notes-v3.65.0.md`.

- ✅ **V3.64.1 — Consistencia snapshot/fingerprint del re-sellado (2026-09-15)** (**Versión estable `3.64.1`**, app `3.64.0 → 3.64.1`). **Patch SIN migración de BD, SIN bump de `GENERATOR_VERSION`, SIN tocar el banco y SIN cambios de UI** que corrige los dos P1 de la auditoría de V3.64: **(P1-01)** la carrera durante el recálculo/sellado del estado (la huella se tomaba DESPUÉS de leer las fuentes, así que una evidencia que entrara en la ventana quedaba en el sello pero no en el estado sellado y `skill_state_is_fresh()` podía servir estado viejo como fresco) y **(P1-02)** el TOCTOU de la caché, formalizado declarando la huella observada al inicio de la decisión. **(A) Sellado estable (`domain/decision.py`):** `_recompute` toma la huella ANTES y DESPUÉS de leer/calcular y solo sella si coinciden (`_SEAL_MAX_ATTEMPTS = 3`); si no coinciden devuelve la huella ANTERIOR (más vieja que el estado) → caché reportada no fresca. **(B) Sello del perfil (`domain/profile.py`):** el sello se lee ANTES de `_compute_profile` (garantiza huella ≤ estado) y se corrige el comentario invertido. **(C) Snapshot de decisión (`domain/decision.py`):** `project_state`/`decision_projection` exponen `snapshot_fingerprint` (huella observada al inicio; token de trazabilidad, no sello de caché; el camino del perfil lo deja vacío). **Tests:** sellado estable + snapshot fingerprint en `test_decision_projection_v364.py`; los 27 existentes verdes. **Honestidad:** no es V3.65 (Observed Difficulty 3.0) ni Decision Provenance; los P2 de calibración pedagógica quedan para V3.65+. Ver `release-notes-v3.64.1.md`.

- ✅ **V3.64.0 — Decision Projection + Planner 3.0 (cierre del P1-01) (2026-09-14)** (**Versión estable `3.64.0`**, app `3.63.0 → 3.64.0`). **Release SIN migración de BD, SIN bump de `GENERATOR_VERSION`, SIN tocar el banco, SIN umbrales nuevos (el único cambio de UI es la línea de motivos DECLARADOS en la cola de repaso, con i18n en/es) que CIERRA el P1-01 de las auditorías de V3.62/V3.63: el Student Skill State deja de ser DESCRIPTIVO y pasa a GOBERNAR la decisión de tareas — pero SIEMPRE por la capa declarada `Student Skill State → DECISION PROJECTION → Planner 3.0`, NUNCA `skill_state → planner` (el planner sigue siendo un módulo puro y ciego al estado persistido). Cierra además por contrato los P2-02 (dificultad ≠ esfuerzo), P2-03 (error de tarea ≠ incertidumbre de MEDIDA) y P2-04 (la carga máxima demostrada se llama como lo que es) de la auditoría `W` de V3.63. **NO convierte `observed_task_difficulty_2` en `P(éxito | alumno, tarea)` empírica (eso es V3.65), NO parametriza el gate por pareja, NO toca el banco ni `GENERATOR_VERSION` y NO introduce ningún umbral nuevo**: reutiliza las bandas ya declaradas (`P_SUCCESS_LOW`/`P_SUCCESS_HIGH`, `assessment_confidence`, la puerta espaciada 2/2 y las tablas de `observed_difficulty.py`).** **(A) Módulo puro `services/decision_projection.py` (nuevo):** mismo contrato que `observed_difficulty.py` (sin I/O, sin reloj, sin `random()`/`hash()`, nunca lanza). `project(state)` proyecta cada celda `{modalidad, competencia}` con la CARGA (`highest_demonstrated_load` —nombrado como lo que es: carga máxima DEMOSTRADA, no dificultad empírica—, `served_ceiling`, `credited_ceiling`, `scaffolding_gap = servido − acreditado`) y el ESFUERZO (nivel declarado + carga EXTRA `experimentado − servido`) en **dos grupos separados** (P2-02), con `confidence` (estadística) y `assessment_confidence` (banda + motivos) **sin fusionar** (V3.63) y `retention`/`transfer`/`novelty` como señales de primera clase. `error_type` se reparte con una tabla DECLARADA en error de TAREA (sube dificultad, `wrong_word`…) e INCERTIDUMBRE DE MEDIDA (baja `assessment_confidence`, **nunca** sube dificultad: `low_confidence`, `empty`, …) (P2-03). `capacity_by_skill` es el **reemplazo directo** de `lexicon._capacity_by_skill` (mismas cuatro claves de `LEXICAL_SKILLS`), con una celda PROVISIONAL (banda mínima) **fuera de la comparabilidad** para que el argmax no premie la ignorancia (invariante de V3.57). `skill_values` pondera `gap`/`retention`/`transfer`/`effort` con pesos DECLARADOS que suman 1.0 (`assessment_confidence` **no** es un peso: es filtro). `drivers(projection, skill)` produce el bloque explicable del punto 26 del informe y `has_comparable_capacity` declara la condición de degradación. **(B) Hechos ADITIVOS del estado (`services/skill_state.py`):** `_entry` expone lo que YA calculaba y no publicaba — `kinds`, `production_count`, `last_evidence`, `contexts`, `error_types` y `review_due`—, con cero recálculo y cero cambio de semántica; el estado solo DECLARA los hechos, clasificarlos es de la proyección. **(C) Planner 3.0 aditivo (`services/planner.py`):** `select_task_by_elv` gana `skill_values`/`drivers` OPCIONALES y devuelve, además del contrato de V3.39, un bloque `decision` (`expected_learning_value`, `p_success`, `margin`, `value`, `capacity_skill`, `comparable`, `source` `argmax`/`cascade`, `projected`, `difficulty_fit` —el encaje declarado con las bandas YA existentes de V3.56—, `drivers`, `why` y las alternativas puntuadas), más `explain_drivers` (frases declaradas en inglés) y `explain_priority` extendido de forma aditiva. **Invariante de no-regresión: sin `skill_values`/`drivers` no se añade NINGUNA clave y la respuesta es byte-idéntica a V3.63.** **(D) `domain/decision.py` (nuevo, I/O):** `decision_projection(user_id, level, now)` lee el perfil (que ya trae `skill_state` y su sello), usa la caché **solo** si `skill_state_is_fresh` la valida y, si está VIEJA, vacía o es legacy sin sello, **recomputa UNA vez** desde las CUATRO fuentes canónicas —con el helper `canonical_sources` COMPARTIDO con `domain/profile.py`, sin duplicar la secuencia— y la re-sella; `source` (`cached`/`recomputed`) hace el comportamiento auditable. `project_state` es el único punto donde el payload se ensambla (puro). **(E) Recableado declarado (`domain/review.py` + `services/lexicon.py`):** la cola construye la proyección UNA vez y la pasa a sus DOS pasadas; `review_queue_item(..., projection=None)` usa `capacity_by_skill`/`skill_values`/`drivers` de la proyección y añade `decision` al ítem. **Degradación declarada y probada:** si la proyección NO declara capacidad comparable, se conserva EXACTAMENTE el camino de V3.54/V3.63 (estimador anterior, `skill_priorities` como valor y sin bloque `decision`), de modo que **ninguna petición pierde señal ni cambia de tarea por el solo hecho de existir la proyección**; sin `projection` el camino es el de V3.63, byte a byte. **(F) Contrato aditivo:** `schemas/learning.py` (ítem → `decision`), `schemas/profile.py` (`/api/profile` → `decision_projection`) y espejo en `frontend/src/types/api.ts` (`ReviewDecision`, `ReviewDecisionDrivers`, `DifficultyFit`). **UI mínima declarada:** la cola de repaso muestra una línea con las bandas de la proyección (encaje, hueco, transferencia, retención, esfuerzo y confianza de evaluación) con su alcance en el `title`, y **nada** cuando el estado no declara medida; claves i18n `dictionary.review.decision.*` en en/es. **Tests:** nuevo `backend/tests/test_decision_projection_v364.py` (**27**) que fija pureza/determinismo del módulo, la forma de la proyección (carga vs esfuerzo, error vs incertidumbre), la paridad de claves y el filtro de comparabilidad, el valor de retención como señal de primera clase, los drivers, la degradación EXACTA a V3.63 sin proyección, la **contraprueba positiva de que el estado AHORA SÍ gobierna** (la tarea servida cambia y se explica), la frescura/recompute-once y el contrato aditivo e2e HTTP. **`test_skill_state_v362.py` y `test_planner_argmax_v357.py` siguen verdes SIN TOCARSE.** Verificación local: `pytest` **2458 passed**, `ruff` limpio, launcher **75 passed**, `tsc` OK, `vitest` **653 passed** (76 ficheros), `npm run build` OK, `check_release_consistency` **3.64.0**, `check_beta_v3` OK, `content_validation` OK y `transfer_validation` **OK** (esta release NO toca el banco). **Honestidad:** NO se convierte `observed_task_difficulty_2` en `P(éxito | alumno, tarea)` empírica (V3.65 — Observed Difficulty 3.0), `highest_demonstrated_load` **no** es dificultad empírica (P2-04), el fingerprint de frescura sigue siendo `COUNT(*) + MAX(id)` (P2-01, suficiente si las tablas son append-only por contrato) y el gate por pareja sigue sin parametrizar. **CERRADA (2026-09-15):** commit de release `aa52d55`, **CI 6/6** (run [34903883846](https://github.com/jvelasca/english-tutor/actions/runs/34903883846)) y etiqueta anotada `v3.64.0` creada y empujada.

- ✅ **V3.63.0 — Observed Task Difficulty 2.0 + honestidad del Student Skill State (2026-09-14)** (**Versión estable `3.63.0`**, app `3.62.0 → 3.63.0`). **Release SIN migración destructiva (una columna aditiva idempotente), SIN bump de `GENERATOR_VERSION` y SIN cambios de UI que cierra la deuda de HONESTIDAD que V3.62 dejó declarada por escrito más los hallazgos P1-02 y P2-11/P2-12/P2-13/P2-14/P2-18/P2-19/P2-20 de la auditoría `U` de V3.62. La DECISIÓN de tareas sigue BYTE-IDÉNTICA: el guard estructural de V3.62 sigue verde sin tocarse. NO toca `expected_learning_value`, `planner`, `difficulty`, `transfer.py`, `transfer_state` ni sus umbrales, el scoring, FSRS, la escalera de recall ni la UI/i18n.** **(A) Identidad y OCASIONES (P2-13):** la fila canónica gana `evidence_id`/`activity_id`/`assessment_id` y `occasion_key`: una evaluación expandida a N competencias son N muestras y **UNA** ocasión, y el dedup **solo puede acreditar menos** (sin identidad declarada la degradación es EXACTA a V3.62). **(B) Canal OBSERVADO (P1-02):** `MODALITIES_BY_ASSESSED_CHANNEL` (derivado de `LEXICAL_MODALITY` × `ASSESSMENT_MODE_MODALITY`, sin vocabulario nuevo) con las dos entradas explícitas `("spontaneous_use", "written") → interaction` y `("spontaneous_use", "spoken") → speaking`, resueltas desde la actividad DECLARADA en el evento; sin canal declarado cae al mapa por skill. **(C) Observed Task Difficulty 2.0 (P2-20, núcleo):** módulo **puro** `services/observed_difficulty.py` (`served_ceiling`, `credited_ceiling`, `scaffolding_gap`, `experienced_load` y `observed_task_difficulty_2`) sobre las filas canónicas, con tablas DECLARADAS y monótonas (latencia con `planner.SLOW_RECALL_MS`/`LATENCY_CEILING_MS`, error, repeticiones, transcripción y audio ralentizado), la MISMA puerta espaciada de V3.54 y sin reloj: un coste desconocido **no modula** y sin muestra espaciada no se declara ninguna medida. **(D) Confianza de EVALUACIÓN (P2-19):** `assessment_confidence` (banda mínima + motivos) derivada SOLO de hechos persistidos (canal, `support_level`, transcripción, audio lento, repeticiones, instancia de transfer) y SEPARADA de la `confidence` estadística, que no cambia de fórmula. **(E) Pronunciación con criterio declarado (P2-11):** `item_id` es la competencia cuando la ruta ya puntúa un criterio; la práctica libre mantiene `""` con motivo escrito. **(F) Capas declaradas de listening (P2-12):** `COMPETENCE_LAYERS_BY_MODALITY` REUTILIZA `SKILL_LAYER`/`LISTENING_LAYERS` sin vocabulario nuevo (16 de 18; `dictation`/`shadowing` fuera con motivo) y el resumen gana `layers`. **(G) Seam del gate (P2-14):** `CompetenceGate` + `gate_for` con la tabla de políticas VACÍA y un test que lo fija: cero umbrales nuevos. **(H) Frescura (P2-18):** `evidence_fingerprint` sobre las cuatro fuentes, columna aditiva `learning_profile.skill_state_source` y `skill_state_is_fresh`: una caché vieja NUNCA se sirve como fresca. **Contrato aditivo:** la entrada del estado gana `observations`, `occasions`, `assessment_confidence` y `observed_task_difficulty_2`; el resumen gana `layers`; todas las claves de V3.62 intactas, con espejo en `schemas/profile.py` y `types/api.ts`. Tests: nuevo `test_observed_task_difficulty_v363.py` (**26**, escrito antes del código), `pytest` **2430 passed** en local, `ruff` limpio, launcher **75 passed**, `tsc` OK, `vitest` **651**, `npm run build` OK, `check_release_consistency` **3.63.0**, `check_beta_v3`/`content_validation` OK y `transfer_validation` OK (la release NO toca el banco). **`test_skill_state_v362.py` sigue verde SIN TOCARSE.** Fuera de alcance (V3.64): **P1-01** —`Student Skill State → Decision Projection → Planner` (nunca `skill_state → planner` directamente) y `Planner 3.0`, comprometido y fechado también en `docs/RELEVO.md` y en el briefing `agentes/v363-observed-task-difficulty-2.md`. **Honestidad:** V3.63 hace el estado más honesto, pero el estado nuevo sigue SIN gobernar la tarea. Ver `release-notes-v3.63.0.md`.

- ✅ **V3.62.0 — Student Skill State 4.0 (modalidad × competencia) (2026-09-14)** (**Versión estable `3.62.0`**, app `3.61.0 → 3.62.0`). **Release SIN migración explícita de BD (columna aditiva idempotente), SIN bump de `GENERATOR_VERSION` y SIN cambios de UI que unifica los DOS modelos del alumno que hasta V3.61 convivían sin tocarse (el adaptativo léxico `LEXICAL_SKILLS` × `DIFFICULTY_DIMENSIONS`, cuya única fuente es `learning_evidence` y que alimenta el ELV/planner/`transfer.context_for`; y el curricular `MASTERY_SKILLS` × 4 estados pedagógicos, que solo llegaba a `/api/profile`) en UN estado `{modalidad: {competencia: entry}}` alimentado por TODA la evidencia registrada. Cierra el P1-03 de la auditoría `S` de V3.60 con dos matices declarados: las cuatro «dimensiones» del modelo léxico son CARGA de contenido, no competencia (`syntax` NO es `grammar`, y no hay eje fonológico, ortográfico ni pragmático), y la evidencia no léxica (grammar, listening por subdestreza, pronunciation, reading, writing, speaking) era INERTE para el estado. Es estrictamente ADITIVA: la decisión de tareas sigue leyendo EXACTAMENTE el estado de V3.61 y se prueba byte a byte. NO toca `evidence.observed_signals` (se consume), `expected_learning_value`, `planner`, `difficulty`, `transfer.py`, `transfer_state` ni sus umbrales, el scoring, FSRS, la escalera de recall ni la UI/i18n.** **(A) Taxonomía (`services/skill_axis.py`, nuevo):** una sola fuente de verdad que MAPEA los ~15 vocabularios del árbol sin refactorizarlos: `SKILL_MODALITIES` (9, de `MASTERY_SKILLS`), `MODALITY_BY_VOCABULARY` (mapa preciso por vocabulario, con totalidad verificada en import para `LEXICAL_SKILLS`), el aplanado `MODALITY_OF` con `AMBIGUOUS_STRINGS` explícitas (`register`/`discourse`/`nuance`/`pragmatics`… pertenecen a VARIAS destrezas, así que el estado NUNCA resuelve competencia con el aplanado), `COMPETENCES_BY_MODALITY` (derivadas de `curriculum.SUBSKILLS` + rúbricas), `canonical_competence` (casefold + strip, **sin** fuzzy matching: lo desconocido devuelve `""` en lugar de inventarse) y `objective_competences_index()` (con `lru_cache`). Decisiones por escrito: `recall → vocabulary`, `written_production → writing`, `spoken_production → speaking`, **`spontaneous_use → interaction`** (su único emisor es `chat`, que es TEXTO: no se declara producción oral sin canal oral), `interaction`/`mediation` sin competencias y **`receptive` en `UNMAPPED` con motivo**. La discrepancia `LISTENING_SUBSKILLS` (18) vs `SUBSKILLS["listening"]` (19) se resuelve como UNIÓN explícita y probada. **(B) Agregador (`services/skill_state.py`, nuevo):** `skill_state_sources(...)` normaliza las CUATRO fuentes (`learning_evidence`, `academy_evidence`, `listening_attempts`, `pronunciation_attempts`) a filas canónicas (una por hecho observable, con `kind`/`production` porque el gate reutilizado los lee) y `skill_state(rows, level=, now=)` agrupa por `(modalidad, competencia)` con la MISMA puerta de V3.54 (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS` de `learner_skill`) y deriva `state` con `competence.competence_state(...)`, **sin un solo umbral nuevo**; devuelve todas las modalidades canónicas (`{}` sin evidencia), igual que `floor_level_by_skill`. **(C) Nada se inventa:** el camino léxico aporta entradas de modalidad CON sus `dimensions` y SIN competencia; la competencia la declara la fuente (subdestrezas del objetivo, restringidas a las de la modalidad de la fila; subdestreza de `listening_attempts`; `""` donde no la hay) y una fila de `academy_evidence` sin objetivo resoluble (hueco F-K3) no acredita éxito, la MISMA frontera del Student Model. **(D) Paridad probada:** el léxico se lee con la proyección EXACTA de `evidence.observed_signals` (`assessed_skill` → `skill`, `earned_difficulty`), así que sus `dimensions` son idénticos a `observed_skill_capacity`; el éxito de academia usa el umbral declarado de su objetivo y la pronunciación normaliza el 0..100 de su esquema contra su `PASS_THRESHOLD`. **(E) Persistencia y contrato aditivos:** `learning_profile.skill_state TEXT NOT NULL DEFAULT ''` (CREATE + `ALTER TABLE` idempotente), escritor DEDICADO `set_skill_state` (sin tocar la firma del escritor caliente) y lector nuevo `pronunciation.list_attempts`; `LearningProfile.skill_state`/`skill_state_summary` con espejo TS (sin cambio visual ni de i18n) y `skill_state_summary` como resumen DERIVADO. Determinismo: sin reloj en la función pura, sin `hash()`/`random()` y JSON con `sort_keys=True`. **(F) La invariante central:** con un `skill_state` rico persistido, `learner_level_state`, el payload del drill (`review_queue_item` con su `learning_value`), `select_task_by_elv` + `expected_learning_value` y `transfer.context_for` devuelven EXACTAMENTE lo de V3.61, y un test estructural fija que ningún módulo del camino de decisión menciona el estado nuevo. Tests: nuevo `test_skill_state_v362.py` (**31**), `pytest` **2404 passed** en local, `ruff` limpio, launcher **75 passed**, `tsc` OK, `vitest` **651**, `npm run build` OK, `check_release_consistency` **3.62.0**, `check_beta_v3`/`content_validation` OK y `transfer_validation` **20 familias / 1020 superficies / 0 errores** (la release NO toca el banco). Fuera de alcance (V3.63+): el RECABLEADO de la decisión de tareas al eje de competencia (ELV/planner/ELU por modalidad), Observed Task Difficulty 2.0, Planner 3.0 y rotación adaptativa, Instance Generator 2.0, WSD real, la división de `transfer.py` en paquete y el arrastre de V3.59. **Honestidad:** V3.62 construye, persiste y expone el modelo unificado, pero el estado nuevo todavía NO cambia ninguna tarea (por diseño explícito, alcance cerrado con el gerente). Ver `release-notes-v3.62.0.md`.

- ✅ **V3.61.0 — Instance-aware Evidence + Anti-spoiler Guard (2026-09-14)** (**Versión estable `3.61.0`**, app `3.60.0 → 3.61.0`). **Release SIN migración explícita de BD (columna aditiva idempotente), SIN bump de `GENERATOR_VERSION` y SIN cambios de UI que cierra los DOS defectos funcionales de la auditoría `T` de V3.60 y la parte determinista de los P1 de la auditoría `S`: (T-01) la superficie servida podía NOMBRAR la unidad objetivo —la familia `shopping` servía en el 7.º uso «You are in a supermarket …», así que la recuperación espontánea se convertía en producción GUIADA y la evidencia de transferencia quedaba contaminada— y (T-02) la evidencia podía guardar la dificultad de OTRA instancia, porque `TransferAttemptIn` no identificaba la superficie emitida y el POST recalculaba la rotación con el contador actual (dos respuestas simultáneas o un reintento de red persistían la carga de la siguiente superficie). V3.61 añade un GUARD anti-spoiler léxico y determinista sobre la superficie que se sirve (sin LLM ni WSD: premisa 21), una IDENTIDAD INMUTABLE de instancia de GET a POST (el slug estable viaja en el contrato y el POST persiste la carga de la superficie RESPONDIDA), `context_instance` ADITIVO en `learning_evidence` (sin fragmentar `context_id` = FAMILIA) y tres cierres deterministas de P1: cap ESTRATIFICADO del producto cartesiano (en lugar del prefijo, que sesgaba a las últimas variables), rotación NO SECUENCIAL desde el 3.er intento sembrada por `(familia, unidad)` y un VALIDADOR de contenido del espacio (`difficulty_delta` justificado con `scenario`/`goal`, `register` de instancia = familia, `skill_delta` del vocabulario, slots consumidos por la plantilla y tarea asegurada para la unidad) con perfil de demanda advisory. NO toca `context_difficulty`, `CONTEXT_DIMENSIONS`, `context_distance`, `context_diversity`, `_novelty_score`, `transfer_state` ni sus umbrales, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Sense Engine.** **(A) Guard anti-spoiler (`services/transfer.py`):** `reveals_target(text, target)` normaliza y compara por TOKEN con variantes inflexivas acotadas (`-s`/`-es`/`-d`/`-ed`/`-ing`/`-er`/`-ers` y recorte) y no aplica guard por debajo de 3 caracteres; `available_instance_details(context, target)` es el espacio SIN las superficies que nombran la unidad en `prompt`/`scenario`/`goal`/`register`; `context_for` retira del pool las familias sin superficie servible **solo** si queda alternativa segura y, con el banco patológico en que NINGUNA la tiene, degrada a V3.60 y lo declara (`instance_guarded=False`); `instance_suppressed`/`instance_guarded` son aditivas y explicativas. En el banco real `shopping` retira 12 superficies con la unidad `supermarket` y conserva 39 servibles. **(B) Identidad inmutable (**`schemas/vocabulary.py`**, **`services/transfer.py`**):** `TransferAttemptIn.context_instance` (slug servido) y `serve_instance(context_id, slug, attempts_by_context, target=, unit=)` → `{instance, index, count, matched, difficulty, suppressed}`; con slug reconocido devuelve la carga de ESA superficie y sin él (`"", None`, desconocido, retirado por el guard) cae a la rotación actual con `matched=False`; `served_difficulty_for_instance` es la fachada del ledger y `TransferAttemptOut` expone `context_instance`/`instance_index`/`instance_count`/`instance_matched`/`instance_suppressed`. **(C) Ledger aditivo (`repositories/db.py`, **`repositories/evidence.py`**, **`domain/vocabulary.py`**):** `context_instance TEXT NOT NULL DEFAULT ''` por el camino idempotente de `ALTER TABLE`, kw-only en `record_evidence`/`record_evidence_bulk`, devuelta por `list_evidence` y persistida por `_record_transfer_evidence`; `context_id` sigue siendo `transfer:<id>` (nunca `transfer:<id>:<slug>`) y los agregados no cambian. **(D) P1-01 — espacio no memorizable:** `_stratified_indices`/`_partial_at` sustituyen el recorte por prefijo con posiciones equiespaciadas sobre el producto completo (idéntico por debajo del techo), `_rotated_index` permuta el ciclo desde el 3.er intento con `zlib.crc32` de `(familia, unidad)` (biyección: se visita todo el espacio) y el banco gana un tercer eje `constraint` por familia: **358 → 1020 superficies** sin escribir consignas a mano. **(E) P1-02 — validador (`services/transfer_audit.py`, **`scripts/transfer_validation.py`**):** invariantes deterministas de contenido + perfil de demanda heurístico advisory (sin WSD la equivalencia pedagógica solo se cierra parcialmente); CLI de CI dentro del job Backend. **(F) Contrato aditivo:** 38 claves en `TransferContextOut`, espejo en `frontend/src/types/api.ts`, `submitDrillTransferAttempt` envía `context_instance` y `wordDrill.tsx` lo pasa desde el contexto servido; sin cambio visual ni de i18n. **(G) Auditorías archivadas:** `docs/audit/S-AUDITORIA-TOTAL-V360.md` y `docs/audit/T-AUDITORIA-TOTAL-V360.md` con el conflicto de veredictos explícito y el CI 6/6 de V3.60 declarado **documentado, no verificado de forma independiente**; veredicto consolidado en `docs/RELEVO.md` y `agentes/README.md`. Tests: nuevo `test_context_engine_v361.py` (**38**, incluida la reproducción de los dos defectos y su no-regresión), `pytest` **2373 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.61.0**. Fuera de alcance (V3.62+): Student Skill State 3.0, Observed Task Difficulty 2.0, Planner 3.0/rotación adaptativa, Instance Generator 2.0, WSD real, la división de `transfer.py` en paquete y el arrastre de V3.59 (generación de sentidos con bump de `GENERATOR_VERSION` y ponderación de la adecuación en `transfer_confidence`). Ver `release-notes-v3.61.0.md`.

- ✅ **V3.60.0 — Context Engine 4.0: Instance Specification → Parameterized Instance (2026-09-14)** (**Versión estable `3.60.0`**, app `3.59.0 → 3.60.0`). **Release SIN migración de BD, SIN bump de `GENERATOR_VERSION` y SIN cambios de UI que cierra los cuatro hallazgos de la auditoría externa R de V3.59: P1-1 «3 superficies deterministas siguen siendo memorizables» (una familia se agotaba en tres intentos), P1-2 «la instancia puede cambiar la dificultad real sin poder declararlo» (`CONTEXT_INSTANCE_KEYS = ("instance", "prompt")` no dejaba expresar escenario/goal/register/delta), P2-6 «Context Engine todavía manual/finito» (20 × 3 = 60 consignas a mano) y P2-7 «la instancia no genera dificultad» (la superficie era solo `presentation_surface`). V3.60 no añade redacciones a mano NI usa un LLM en el camino de la evidencia (premisa 21): parametriza la COMBINACIÓN de contenido DECLARADO. Cada familia declara `instance_space` (`template` + slots + `selection` + `difficulty_delta`) y de ahí se GENERAN superficies DETERMINISTAS de la MISMA identidad: FAMILIA → ESPECIFICACIÓN → INSTANCIA. La FAMILIA (los 20 contextos, su `id` incluido) sigue siendo la identidad pedagógica y la unidad de EVIDENCIA (`context_id` del ledger), así que NINGUNA clave nueva entra en `CONTEXT_DIMENSIONS`, `context_distance`, `context_diversity`, `_novelty_score`, `transfer_state` ni sus umbrales, y `context_difficulty()` (la carga de la familia) NO cambia. NO toca `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Sense Engine. Determinista: expansión en orden declarado, `_slug` estable (nunca `hash()`) y rotación `attempts % len(espacio)`.** **(A) Lista blanca ampliada, NO identitaria (`services/transfer.py`):** `CONTEXT_INSTANCE_KEYS` pasa a `("instance", "prompt", "scenario", "goal", "register", "difficulty_delta", "skill_delta")`; lo que sigue PROHIBIDO es la identidad (`id`, 6 dimensiones core, `cefr`, `difficulty_vector`, `skills`, `lexical_environment`, `syntactic_focus`) y `_surface_details` **lee solo** esas siete claves y descarta el resto (garantía de no-fragmentación del ledger). Un test fija que la intersección con las claves de familia es exactamente `{"prompt"}`. **(B) Espacio mínimo y techo:** `CONTEXT_INSTANCE_SPACE_MIN = 12` superficies TOTALES por familia (invariante anti-memorización, verificado sobre el banco real) y `CONTEXT_INSTANCE_SPACE_MAX = 96` de techo; el recorte deja un PREFIJO del producto cartesiano en orden declarado. **(C) Especificación → superficie (núcleo puro):** `context_instance_spec` (normaliza y declara INSERVIBLE una especificación sin placeholders válidos o sin valores), `_instance_value` (`value` OBLIGATORIA: sin texto el valor se DESCARTA, no se inventa contenido), `_skill_delta` (restringido al vocabulario `CONTEXT_SKILLS`), `_slug`, `_template_fields`, `_slot_order` (el `selection` fija el orden de MEZCLA, así que los slots principales entran siempre aunque el techo recorte), `_merge_partial`, `_render_template`, `_expand_spec`, `_surface_details`, `context_instance_details` (espacio COMPLETO en un orden: histórica → declaradas de V3.59 → generadas, dedup por consigna, claves siempre presentes) y `context_instances` como VISTA de 2 claves sobre él. **(D) Dificultad efectiva (`services/difficulty.py`):** `normalize_delta` (enteros por dimensión canónica, clamp ±2, ignora basura) y `apply_delta` (base + delta recortado a 1..5; un delta sobre una dimensión que la base no declara se IGNORA; con delta vacío devuelve `normalize_vector(vector)` EXACTO). La familia declara la carga ABSOLUTA y la superficie solo el MATIZ: esa es la frontera que impide reinterpretar la identidad. **(E) Degradación EXACTA:** sin intentos la superficie es la 0 histórica byte a byte y el delta efectivo `{}`; `space[:3]` reproduce byte a byte las tres superficies de V3.59 (la rotación no cambia, se PROLONGA); la familia servida es idéntica con y sin `attempts_by_context` (test clave por clave). **(F) Banco:** `instance_space` en las 20 familias con 2 slots y deltas SOLO donde son reales (`discourse +1` en `debate`/`mediation`/`academic`, `interaction +1` con audiencia crítica, `skill_delta: written_production` en la contribución escrita formal); las dos `instances` de V3.59 conservadas tal cual en los índices 1–2 y el `template` sin llaves sueltas ni unidad objetivo. **El banco pasa de 60 a 358 superficies** (16–19 por familia) sin tocar ninguna `id`. **(G) Ledger (`domain/vocabulary.py`, sin migración):** `_record_transfer_evidence` persiste `transfer.served_difficulty(context_id, attempts_by_context)` —con el MISMO resumen de evidencia que el GET/POST— en las columnas aditivas de V3.55, así que la carga guardada corresponde a la tarea REALMENTE servida, incluida su superficie; `observed_difficulty` sigue siendo la proyección legacy y las superficies sin delta escriben bytes IDÉNTICOS a V3.59. **(H) Contrato aditivo:** 8 claves nuevas en TODOS los retornos, incluido el de banco vacío (`instance_scenario`/`instance_goal`/`instance_register`/`instance_difficulty_delta`/`instance_difficulty_vector`/`instance_difficulty`/`instance_skills`/`instance_generated`), 36 en total, con `TransferContextOut` y espejo TS opcional; las 28 de V3.59 intactas y fijadas por test. Tests: nuevo `test_context_engine_v360.py` (23, con **equivalencia pedagógica** de las superficies de una familia, robustez de `details`/`metadata` y end-to-end HTTP de la superficie generada con el vector efectivo persistido), `pytest` **2335 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.60.0**. **CI 6/6 en verde** (run [34814504063](https://github.com/jvelasca/english-tutor/actions/runs/34814504063) sobre `2c79040`: Release consistency 3.60.0, Backend con ruff + pytest **2333 passed + 2 skipped**, Frontend con tsc + vitest **76 ficheros/651 tests** + build, Playwright E2E **23 passed**, Beta V3.0 gate y Content validation) y etiqueta anotada `v3.60.0`. Fuera de alcance (V3.61+): `context_instance` en el ledger (evidencia instance-aware), el motor de política de instancia (spacing/fallo/dificultad), Student Skill State 3.0, WSD real, `P(success | learner, task)`, Observed Task Difficulty 2.0, Planner 3.0 y el arrastre de V3.59 (generación de sentidos y ponderación de la adecuación en `transfer_confidence`). Ver `release-notes-v3.60.0.md`.

- ✅ **V3.59.0 — Context Engine 3.0: Context Bank Family/Instance (2026-09-13)** (**Versión estable `3.59.0`**, app `3.58.0 → 3.59.0`). **Release SIN migración de BD, SIN bump de `GENERATOR_VERSION`, SIN cambios de UI y SIN tocar el ledger que cierra el candidato diferido desde V3.48 (`Context Bank Family/Instance`) y el hallazgo P2-04 de la auditoría de V3.43: un banco finito de consignas FIJAS se MEMORIZA; al agotarlo el alumno repite la misma consigna y puede reciclar una respuesta aprendida en lugar de transferir. V3.59 separa FAMILIA de INSTANCIA. La FAMILIA (los 20 contextos, su `id` incluido) sigue siendo la identidad pedagógica y la unidad de EVIDENCIA —el `id` es el `context_id` del ledger—, así que el banco NO se fragmenta y no cambian los umbrales, la escalera `transfer_state`, `context_distance`, `context_diversity`, la novedad ni el Difficulty Engine. La INSTANCIA es una superficie DECLARADA de la misma familia (otra redacción del mismo escenario): la superficie 0 es SIEMPRE la consigna histórica, byte a byte, y las siguientes se sirven por ROTACIÓN de intentos (el intento N sobre esa familia recibe la superficie `N % nº_superficies`). Sin evidencia la degradación es EXACTA a V3.58. NO toca `transfer_state`, sus umbrales, `context_signals`, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Sense Engine. Determinista, sin LLM en el camino de la evidencia (premisa 21).** **(A) FAMILIA vs INSTANCIA (`services/transfer.py`):** cada contexto declara `instances` (superficies adicionales `{instance, prompt}`), `CONTEXT_INSTANCE_KEYS = ("instance", "prompt")` es una lista BLANCA y `CONTEXT_INSTANCES_MIN = 2` el mínimo por familia: una instancia NO puede declarar `topic`/`communicative_goal`/`discourse_type`/`social_relation`/`time_reference`/`interaction_type`/`register`/`cefr`/`difficulty_vector`/`skills`/`lexical_environment`/`syntactic_focus`/`id`/`prompt`, así que no puede reinterpretar evidencia registrada. El banco pasa de 20 consignas a **60 superficies** sin fragmentar el ledger. **(B) Núcleo puro:** `context_instances(context)` (dict del banco, `id` o `context_id` → `({"instance": "", "prompt": <histórica>}, *declaradas)`; normaliza, descarta basura y nunca lanza) y `context_instance_index(context, attempts)` (rotación `attempts % nº_superficies` con `_count` tolerante —bool, negativos, texto y el bucket `{"attempts": n}`— y 0 sin intentos); `_attempts_for` acepta el mapa `contexts` del resumen, un mapa de enteros o nada. **(C) La elección NO cambia:** la superficie no entra en `_within_level`, `_filter_skill`, `select_by_difficulty`, `_novelty_score` ni `_stable_index`, así que la familia servida es la de V3.58 (test que compara el payload clave por clave con y sin `attempts_by_context`). **(D) Contrato aditivo:** `context_for(..., attempts_by_context)` expone `context_instance`/`instance_index`/`instance_count` en TODOS los retornos (incluido el de banco vacío), con `TransferContextOut` y espejo TS; las 25 claves de V3.58 quedan intactas y fijadas por test. **(E) Cableado:** los dos caminos de `domain/vocabulary.py` (GET y derivación del `context_id` al registrar) pasan el mismo `summary["contexts"]`, así que la superficie servida y la registrada no pueden divergir. **(F) Guardas:** la única clave nueva del banco es `instances`; superficie 0 byte a byte; consignas limpias, sin llaves y distintas; invariantes del banco (20 familias, distribución CEFR, distancia mínima, `story`/`work` = 5) y end-to-end HTTP de la rotación con el pool agotado. Tests: nuevo `test_context_engine_v359.py` (16), `pytest` **2312 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.59.0**. Fuera de alcance (V3.60+): el contrato/prompt de generación de sentidos y su bump de `GENERATOR_VERSION`, la ponderación de la adecuación en `transfer_confidence` y cualquier uso del LLM en el camino de la evidencia. Ver `release-notes-v3.59.0.md`.

- ✅ **V3.58.0 — Sense Engine 2.0: `surface → lemma → sense → semantic_fit` (2026-09-13)** (**Versión estable `3.58.0`**, app `3.57.0 → 3.58.0`). **Release SIN migración de BD, SIN bump de `GENERATOR_VERSION` y SIN cambios de UI que cierra la mitad que V3.44 dejó abierta: desde V3.44 el diccionario declara los SENTIDOS de la unidad (`[{pos, gloss}]`) y los cachea, pero el juicio sobre el uso comparaba FAMILIAS POS y la `gloss` NO la leía nadie —dato INERTE—. Con `bank` declarando dos sentidos de la MISMA familia («financial place» / «river side») el motor no podía separarlos: era un límite del CONTRATO, no de los datos. V3.58 añade las patas `surface → lemma` y `lemma → sense` y hace que la glosa RESUELVA qué sentido se entendió. FRONTERA DECLARADA: la glosa decide el SENTIDO, nunca el VEREDICTO —`semantic_adequacy` conserva la adecuación de V3.44 EXACTA (solo `incorrect` bloquea el clean success y no se amplía), porque la AUSENCIA de solapamiento no demuestra incompatibilidad—. NO toca `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Difficulty Engine. Determinista, sin LLM en el camino de la evidencia (premisa 21).** **(A) `surface → lemma` (`services/semantics.py`):** `lemma_of` (morfología REGULAR declarada, sin diccionario ni lematizador: `-s`/`-ies`, sibilantes `-ches`/`-shes`/`-xes`/`-zes`, `-ed`, `-ing` con consonante doble `running`→`run`; por debajo de 4 caracteres no se toca) y `lemma_variants` (superficie + lema + la variante con la `e` muda restaurada, `making`→`make`, que es lo que permite que una glosa-etiqueta solape con texto flexionado). Es PARCIAL a propósito: las irregulares (`went`/`gone`) no se tocan y solo alimenta una señal SUAVE que no decide el veredicto. **(B) `lemma → sense`:** `gloss_tokens` (tokens de CONTENIDO de la glosa con `GLOSS_STOPWORDS` declaradas), `context_window` (`CONTEXT_WINDOW = 4` a cada lado, recortada en los bordes), `sense_overlap` (parecido medido entre VARIANTES DE LEMA de las dos partes, así `decides` solapa con «to decide») y `select_sense` con clave de orden declarada y estable: familia del rol sintáctico (señal MAYOR) → solapamiento con la glosa (DESEMPATE dentro de la misma familia: el hueco de V3.44) → orden declarado; devuelve `{index, pos, gloss, score, role, strength, reasons}`. **(C) `sense_fit` y la frontera:** `_adequacy` es la regla LITERAL de V3.44 extraída sin cambios y `semantic_adequacy` delega en ella (firma, taxonomía y veredicto idénticos, las dos rutas no pueden divergir); `sense_fit` añade ADITIVAMENTE el sentido resuelto por (familia, solapamiento, orden) entre todas las ocurrencias. La glosa NO amplía `incorrect` (`"The bank is closed"` no comparte una palabra con «a financial place» y es un uso correcto): `score` es CONFIANZA, no prueba. **(D) Contrato aditivo:** `score_transfer_attempt` expone `sense_index`/`sense_pos`/`sense_gloss`/`sense_score` sin alterar `passed`, `lexical_transfer`, `adequacy`, `semantic_fit` ni `error_type`; `TransferAttemptOut` los declara con espejo opcional en `frontend/src/types/api.ts`, así que el sentido resuelto deja de ser dato inerte y viaja en la respuesta HTTP (sin cambio de UI). **(E) Sin migración ni regeneración:** la `gloss` ya estaba cacheada con `GENERATOR_VERSION = "1.4.0"`; V3.58 la RE-INTERPRETA (mismo patrón que V3.57 con `skill_priorities`). Tests: nuevo `test_semantics_sense_engine_v358.py` (30, con equivalencia parametrizada del veredicto contra los literales históricos de V3.44 y end-to-end HTTP), `pytest` **2296 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.58.0**. **CI 6/6 en verde** (run [34780694687](https://github.com/jvelasca/english-tutor/actions/runs/34780694687) sobre `82f17c4`), con la etiqueta anotada `v3.58.0` creada y empujada. Fuera de alcance (V3.59+): el prompt/contrato de generación de sentidos y su bump de versión, la ponderación de la adecuación en `transfer_confidence` y el Context Engine 3.0. Ver `release-notes-v3.58.0.md`.

- ✅ **V3.57.0 — Planner 2.0: argmax `(skill, actividad)` sobre ELV (2026-09-13)** (**Versión estable `3.57.0`**, app `3.56.0 → 3.57.0`). **Release SIN migración de BD y SIN cambios de UI que cierra la segunda mitad del Planner 2.0: el planner deja de solo ORDENAR la cola por valor esperado de aprendizaje y pasa a ELEGIR la tarea, entre las candidatas admisibles, por argmax de ELV. Release CONSERVADORA: el argmax solo actúa CON estado del alumno; sin él la decisión es EXACTAMENTE la de V3.56.0 (`select_task`). Resuelve dos deudas del planner (el valor POR MODALIDAD `skill_priorities` como `value` del ELV en lugar del `priority_score` global, y el doble conteo de `written_production`: EJE de `transfer` vs. CANAL que `write`/`transfer` MIDEN). NO toca `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, `CEFR_CAPACITY`, el scoring, FSRS ni el Difficulty Engine de V3.52/V3.54/V3.55. Determinista, sin LLM.** **(A) Núcleo puro (`services/planner.py`):** `capacity_skill` (mapea el EJE de la tarea al CANAL que la actividad MIDE vía `task_semantics.assessed_skill_for`: `spontaneous_use` → `written_production`; sin actividad declarada cae al propio eje, vacío → `""`), `task_candidates` (candidatas ADMISIBLES en orden canónico: `error_prone` —que gana sobre `slow_recall`— → `recall`; huecos de producción accionables en `GAP_CANDIDATE_ORDER`, oral antes que escrito, → `skill_gap`; `transfer_gap` → `spontaneous_use` solo con su gate; una por modalidad, mismo contrato que `select_task`, `[]` sin directriz, nunca lanza) y `select_task_by_elv` (argmax de `expected_learning_value` entre candidatas, con `value` por modalidad y margen del canal medido; SOLO compiten las candidatas con margen comparable, porque una modalidad sin datos tiene `p = 0.5` → deseabilidad `1.0`, el MÁXIMO, y competiría premiada por ignorancia). **(B) Degradación neutra EXACTA:** sin `capacity_by_skill`, sin candidatas o sin ningún margen comparable, `select_task_by_elv` devuelve `select_task` clave por clave (sin estado del alumno la tarea servida es la de V3.56.0); el empate lo rompe el orden canónico de `task_candidates`, no el de `PRODUCTION_SKILLS`. **(C) Deuda 1:** el ELV del argmax usa `skill_priorities(signals)[skill]` (con el `priority_score` global como respaldo). **(D) Deuda 2:** EJE (lo que la tarea quiere provocar) y CANAL (lo que la actividad MIDE) se separan, así que `write` y `transfer` no son dos mediciones de `written_production` sino una misma LECTURA. **(E) Contrato aditivo:** `expected_learning_value` gana `value`/`capacity_skill` OPCIONALES y su payload gana `capacity_skill` (informativo); los llamadores de V3.56 no cambian. **(F) Cableado (`services/lexicon.py`):** `_capacity_by_skill(learner_state)` calcula UNA vez la capacidad por dimensión de cada modalidad canónica y la MISMA dificultad declarada y capacidad alimentan las dos rutas de decisión (actividad del ítem y `task`) y la predicción servida, de modo que argmax y `learning_value` no pueden divergir; `_task_decision` usa `select_task_by_elv` y `_learning_value` resuelve el canal con `capacity_skill`. Tests: nuevo `test_planner_argmax_v357.py` (24), `pytest` **2266 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.57.0**. **CI 6/6 en verde** (run [34763651640](https://github.com/jvelasca/english-tutor/actions/runs/34763651640) sobre `a40b58d`), con la etiqueta anotada `v3.57.0` creada y empujada. Fuera de alcance (V3.58+): Sense Engine 2.0 (`surface→lemma→sense→semantic_fit`) y Context Engine 3.0.

- ✅ **V3.56.0 — Planner 2.0 / `expected_learning_value` (2026-09-13)** (**Versión estable `3.56.0`**, app `3.55.0 → 3.56.0`). **Release SIN migración de BD que convierte la prioridad del planner de una suma de urgencia en un VALOR ESPERADO de aprendizaje (`ELV = dificultad_deseable(P) × value`) y ordena la cola de repaso por ELV. NO reescribe `select_task` (la cascada de razones queda intacta), NO decide todavía la tarea por argmax `(skill, actividad)` (V3.57) y NO toca `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, `CEFR_CAPACITY`, el scoring, FSRS ni el Difficulty Engine de V3.52/V3.54/V3.55. Determinista, sin LLM.** **(A) Núcleo puro (`services/planner.py`):** tabla DECLARADA `SUCCESS_BY_MARGIN` (monótona no decreciente, `margen −3…+3` → `p 0.05…0.95`), `success_probability` (clamp fuera de rango; neutro `P_SUCCESS_UNKNOWN = 0.5` sin dato y ante entradas no numéricas/bool), `capacity_margin` (MÍNIMO de las dimensiones declaradas por la tarea que existen en la capacidad; una sin capacidad NO cuenta como 0 y sin comparables devuelve `None`), `desirability(p) = 4·p·(1−p)` (máximo `1.0` en `p = 0.5`) y `expected_learning_value` → `{expected_learning_value, p_success, desirability, value, margin, skill}` con `value = priority_score` (mismos pesos). **(B) Degradación neutra EXACTA:** sin estado del alumno o sin dificultad declarada, `p = 0.5` → `desirability = 1.0` → `ELV = priority`, orden IDÉNTICO al de V3.55.0. **(C) Cableado (`lexicon.review_queue_item`):** parámetro opcional `learner_state`; resuelve la modalidad de la tarea, el suelo por modalidad (`student_state.skill_floor`), la capacidad (`learner_skill.skill_capacity`) y la dificultad declarada (`difficulty.declared_difficulty`); expone aditivos `expected_learning_value` y `learning_value` sin alterar `priority`/`signals`/`why`/`task`/`skill_priorities`, con frases de capacidad en `explain_priority` solo si hay predicción. **(D) Una sola lectura del estado:** nuevo `domain/learner_state.py` (la lectura O(1) de la caché del Student Model, compartida por cola y drill; `domain.vocabulary` delega y `_skill_floor` pasa a `services.student_state.skill_floor`; no se ubica en `domain.profile` por el ciclo `vocabulary → profile → academy → vocabulary`). **(E) Orden de cola:** `_queue_sort_key = (-expected_learning_value, -priority, retrievability, word)`, con el estado leído UNA vez por cola y pasado a las DOS pasadas de `review_queue_item`. **(F) Contrato aditivo:** `ReviewQueueItem.expected_learning_value`/`learning_value` con espejo TS opcional; sin cambio de UI ni de `due_count`. Tests: nuevo `test_expected_learning_value_v356.py` (19), `pytest` **2242 passed** en local, launcher **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.56.0**. Fuera de alcance (V3.57+): argmax `(skill, actividad)` sobre ELV, Sense Engine 2.0 y Context Engine 3.0.

- ✅ **V3.55.0 — Task Difficulty 3.0 (2026-09-13)** (**Versión estable `3.55.0`**, app `3.54.0 → 3.55.0`). **Release ADITIVA (tres columnas de BD) que da nombres honestos a la dificultad de la tarea en el ledger (`declared`/`served`/`observed_task_difficulty`), hace que la capacidad observada acredite lo SUPERADO y no lo SERVIDO (descuento por andamiaje) y cablea la dificultad en las CUATRO vías del drill léxico. SIN tocar `level_from_capacity` (gate CEFR global de V3.53.1), `observed_skill_capacity`, `learner_capacity`, `CEFR_CAPACITY`, `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el scoring, el planner ni FSRS. Determinista, sin LLM.** Cierra los P2-01 y P2-02 de la auditoría de V3.53.1. **(A) P2-01 — tres dificultades:** `learning_evidence.observed_difficulty` (V3.53) guardaba en realidad el vector del contexto SERVIDO y solo lo escribía Transfer (`recall`/`sentence`/`write` lo dejaban `''`, así que `written_production`, `spoken_production` y `recall` no acumulaban capacidad nunca). Nuevas columnas aditivas (`CREATE` + `ALTER TABLE` idempotente) `declared_difficulty` (lo que declara el ÍTEM — su CEFR en la única dimensión que puede declarar, `lexical` — o la actividad), `served_difficulty` (lo servido) y `observed_task_difficulty` (lo ACREDITADO, solo en el éxito); `observed_difficulty` se conserva escrita como PROYECCIÓN LEGACY de `served_difficulty` (V3.53/V3.54 leen lo mismo). **(B) P2-02 — descuento por andamiaje:** nueva tabla pura `SUPPORT_DISCOUNT_STEPS` monótona con la escalera `copied → guided → cued → independent → spontaneous` (`guided` −2, `cued` −1, `independent`/`spontaneous` 0, `copied`/desconocido sin crédito); `evidence.observed_signals` lee la carga acreditada (`difficulty.earned_difficulty`, con `served_difficulty` como marca de fila V3.55 y `observed_difficulty` como fallback legacy) sin cambiar el contrato del resumen y manteniendo la paridad pura↔SQL por construcción. **(C) Núcleo puro:** `difficulty.declared_difficulty` (el `0` de `lexicon.cefr_difficulty` = no declarado, no carga 1), `observed_task_difficulty`, `task_difficulty_vectors` (serializa las tres + la proyección legacy en un solo sitio) y `earned_difficulty`. **(D) Cableado:** Word/Sentence (`guided`, −2), Recall (`cued`/`guided` según `RECALL_CUE_SUPPORT`), Write (`independent`) y Transfer (`spontaneous`; `declared` = carga léxica del ítem, `served` = vector del contexto), con el helper compartido `domain.vocabulary._item_task_difficulty`; el volcado de producción del chat libre queda fuera de alcance y documentado (recibe formas, no filas). Tests: nuevo `test_task_difficulty_v355.py` (17), `pytest` **2223 passed** en local, `ruff` limpio, `tsc` OK, `vitest` **651** y `check_release_consistency` **3.55.0**. **CI 6/6 en verde** (run [34757345417](https://github.com/jvelasca/english-tutor/actions/runs/34757345417) sobre `e9b5689`: Backend ruff + pytest **2221 passed + 2 skipped**, Frontend tsc + vitest **651** + build, Release consistency **3.55.0**, Beta V3.0 gate, Content validation y Playwright **23**) con la etiqueta anotada `v3.55.0` creada y empujada. Fuera de alcance (V3.56+): `expected_learning_value` y el Planner 2.0 (P1-03), la dificultad en el volcado del chat libre, latencia/errores como moduladores de la capacidad, Sense Engine y Context Engine.

- ✅ **V3.54.0 — Student Skill State 3.0 (2026-09-13)** (**Versión estable `3.54.0`**, app `3.53.1 → 3.54.0`). **Release ADITIVA (una columna de BD) que conserva la MODALIDAD en la capacidad observada (`skill × dimensión`), deriva el nivel CEFR POR SKILL con la regla de cobertura completa de V3.53.1, añade el suelo por modalidad y activa un gate de cobertura que impide que una capacidad PARCIAL eleve tareas multidimensionales. SIN tocar `level_from_capacity` (gate CEFR global de V3.53.1), `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el scoring, el planner ni FSRS. Determinista, sin LLM.** **(A) Estado por skill × dimensión:** `services.evidence.observed_signals` ya agregaba por modalidad, pero `learner_skill.observed_capacity` tomaba el MÁXIMO entre modalidades (una producción escrita B2 elevaba el reto de una tarea oral nunca producida). Nuevo `observed_skill_capacity` (`{skill: {dimension: load}}`, muestra espaciada por skill × dimensión) es la FUENTE de verdad y `observed_capacity` queda como proyección legacy; `level_from_skill_capacity` aplica la cobertura dimensional COMPLETA por skill (`""` con cobertura parcial) y `skill_coverage`/`skill_capacity` exponen la cobertura y las `covered_dimensions`. **(B) Suelo por modalidad:** `student_state.floor_level_for_skill` (`demostrado > observado del SKILL > estimado > declarado`) no hereda el observado global de otra modalidad; sin estado por skill (caché legacy) delega en el comportamiento de V3.53.1. **(C) Gate de cobertura:** `difficulty.challenge_for` + `select_by_difficulty(..., covered_dimensions, floor_challenge)` solo aplican la subida observada a contextos cuyas dimensiones son SUBCONJUNTO de las cubiertas; `transfer.context_for(..., learner_skill_capacity, capacity_skill)` resuelve la capacidad de la modalidad que la tarea mide. **(D) Persistencia y contrato aditivos:** `learning_profile.observed_skill_capacity` (CREATE + `ALTER TABLE` idempotente, JSON determinista) cacheada en `get_profile_summary` y preservada por `set_cefr`; `LearningProfile.observed_skill_capacity`/`observed_skill_level`/`skill_coverage` y `TransferContextOut.capacity_skill`, con espejo TS. Tests: nuevo `test_learner_skill_v354.py` (19) + ajuste del estado neutro; `ruff` limpio y `check_release_consistency` **3.54.0**. **CI 6/6 en verde** (run [34755745179](https://github.com/jvelasca/english-tutor/actions/runs/34755745179) sobre `b2929e1`: Backend ruff + pytest **2204 passed + 2 skipped**, Frontend tsc + vitest **651** + build, Release consistency **3.54.0**, Beta V3.0 gate, Content validation y Playwright **23**) con la etiqueta anotada `v3.54.0` creada y empujada. Fuera de alcance (V3.55+): `declared`/`served`/`observed_task_difficulty`, `expected_learning_value`, Planner 2.0, Sense Engine y Context Engine.

- ✅ **V3.53.1 — Observed CEFR Safety Gate (2026-09-13)** (**Versión estable `3.53.1`**, app `3.53.0 → 3.53.1`). **Patch SIN migración de BD, SIN cambios de contrato y SIN tocar `observed_capacity`, `learner_capacity`, `CEFR_CAPACITY`, el planner ni FSRS. Determinista, sin LLM.** Cierra el **P1-01** de la auditoría externa de V3.53.0: `services.learner_skill.level_from_capacity` iteraba las dimensiones CON muestra y una dimensión sin muestra «no bloqueaba», así que `observed_capacity = {"lexical": 5}` producía un `observed_level = "C2"` — convertía «capacidad léxica compatible con C2» en un CEFR GLOBAL. Ahora recorre las dimensiones que exige el NIVEL candidato (no las observadas), cuenta 0 en las sin muestra y exige **cobertura dimensional COMPLETA** para cualquier etiqueta global: `observed_capacity` sigue siendo la fuente de verdad por dimensión y `observed_level` pasa a ser un RESUMEN DERIVADO. Casos: `{"lexical": 5}` → `""`; `{"lexical": 5, "syntax": 3, "discourse": 4, "interaction": 3}` → `"B2"`; envolvente de C1 → `"C1"` (C2 bloqueado por `lexical 4 < 5`); cobertura 3/4 → `""`. `learner_capacity` sigue subiendo el reto SOLO en las dimensiones observadas sin bajar el suelo declarado. Tests: `test_level_from_capacity_requires_full_dimensional_coverage` (reescrito) + dos tests de aceptación multidimensional y uno de no-regresión; sin cambios en esquema (`observed_level`/`observed_capacity`), contratos ni espejo TS. **CI 6/6 en verde** (run [34748988008](https://github.com/jvelasca/english-tutor/actions/runs/34748988008) sobre `6d8af47`: Backend ruff + pytest **2185 passed + 2 skipped**, Frontend tsc + vitest **651** + build, Release consistency, Beta V3.0 gate, Content validation y Playwright **23**) con la etiqueta anotada `v3.53.1` creada y empujada. Fuera de alcance (V3.54+): P2-01 (desdoblar `served_/observed_task_difficulty`), P2-02 (capacidad con apoyo/transfer/latencia/errores), P2-03 (`skill × dimension`) y el Planner 2.0 / `expected_learning_value` (P1-03).

- ✅ **V3.53.0 — Learner Skill State 2.0 + `observed_difficulty` (2026-09-11)** (**Versión estable `3.53.0`**, app `3.52.2 → 3.53.0`). **Release ADITIVA (tres columnas de BD) que cierra el P1-02 diferido desde V3.52 y monta el primer Student Skill State OBSERVADO, SIN tocar `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, `score_transfer_attempt`, el planner ni FSRS. Determinista, sin LLM.** **(A) `observed_difficulty` por evento:** nueva columna `learning_evidence.observed_difficulty` (CREATE + `ALTER TABLE` idempotente) con el VECTOR de la TAREA servida serializado por el nuevo puro `services.difficulty.format_vector` (inversa tolerante `parse_vector`, `''` = no declarada); `services.transfer.context_difficulty` (dict/`id`/`context_id` → vector) es el espejo de `context_skills`; el drill de transferencia escribe el vector del contexto SERVIDO y el resto de drills lo dejan `''`; plumbing en `record_evidence`/lote/`list_evidence`/`EVIDENCE_FIELDS`. **(B) Learner Skill State 2.0:** nuevo módulo PURO `services/learner_skill.py` (`observed_capacity` con muestra ESPACIADA —2 éxitos en 2 días naturales distintos—, `level_from_capacity` conservador sobre la envolvente del banco y `learner_capacity` = máximo por dimensión entre el suelo del nivel y lo observado, sin bajar nunca el suelo declarado); nuevo puro `services.evidence.observed_signals` (`observed_samples`/`observed_days`/`observed_capacity`; atribución `assessed_skill` → `skill`; solo ÉXITOS con vector) con claves en `summarize_evidence`/`empty_summary` y **paridad pura↔SQL por construcción** (`summarize_by_target` delega en la MISMA función), más `repositories.evidence.list_observed_rows`. **(C) Suelo y contrato:** `student_state.LEVEL_SOURCES` inserta `observed` entre `demonstrated` y `estimated` (`CERTIFIED_SOURCES` NO cambia: `observed` usa el margen amplio); `learning_profile.observed_level`/`observed_capacity` aditivas, derivadas del ledger y cacheadas en `get_profile_summary`, leídas en O(1) por `_learner_level_state` y pasadas a `context_for(..., learner_capacity=...)` en GET y POST (paridad intacta); con `None`/`{}` el resultado es EXACTAMENTE V3.52.2. Contratos aditivos `TransferContextOut.learner_capacity` y `LearningProfile.observed_level`/`observed_capacity`, con espejo opcional en `types/api.ts`. **(D) P3 incluido:** corregido el comentario obsoleto de B1 `interaction` en `difficulty.py` (decía 2; la tabla tiene 3), sin cambio funcional. Tests: pytest **2185 passed** en local (+19: `test_observed_difficulty_v353.py` y `test_learner_skill_v353.py`, más ajustes de contrato), `ruff` limpio, `tsc --noEmit` en verde, `check_release_consistency` **3.53.0** exit 0. **CI 6/6 en verde** (run [34747380090](https://github.com/jvelasca/english-tutor/actions/runs/34747380090) sobre `e4bd577`: Backend ruff + pytest **2183 passed + 2 skipped**, Frontend tsc + vitest **651** + build, Release consistency, Beta V3.0 gate, Content validation y Playwright **23**) con la etiqueta anotada `v3.53.0` creada y empujada. Fuera de alcance (V3.54+): cablear el skill state al planner (P1-03, Planner 2.0 / `expected_learning_value`); no se tocan `CEFR_CAPACITY`, `transfer_state`, `context_signals`, `context_diversity`, el scoring ni FSRS.

- ✅ **V3.52.2 — Cierre de los P2 de la auditoría Q (2026-09-11)** (**Versión estable `3.52.2`**, app `3.52.1 → 3.52.2`). **Release SIN migración de BD y SIN cambios de contrato que recalibra el Difficulty Engine al banco real; NO toca la escalera `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el scoring ni FSRS.** **(A) P2-01 — `CEFR_CAPACITY` = envelope monótono del banco:** la tabla declarada se quedaba corta en la `interaction` de A1/A2 (1 frente al máximo real 2/3) y larga en léxico/sintaxis de B2/C1 (4/4 y 5/5 frente a 3/4) pese a afirmar que estaba «calibrada con la distribución real del banco»; con la tolerancia ESTRICTA un alumno A2 **certificado** quedaba fuera de `directions`/`shopping` —2 de los 4 contextos A2— (`overshoot` 2 > tolerancia 1), de modo que el alumno con más confianza recibía el conjunto más plano. La tabla pasa a ser el máximo acumulado por dimensión de los `difficulty_vector` reales (A1 interaction 2, A2 3, B1 3, B2 léxico/sintaxis 3, C1 léxico 4), monótona por construcción, con `test_capacity_is_the_monotone_envelope_of_the_bank` que la recalcula desde `TRANSFER_CONTEXTS`; **impacto medido: 15 de 48 combinaciones (nivel de ítem × nivel de alumno; 49 posibles, una sin reto) cambian de contexto servido y el patrón es el esperado por el envelope** (el alumno A2 **demostrado** pasa por fin a `directions`/`shopping` —interaction 3— en vez de `story`/`future` —interaction 1—, el alumno C1 pasa de `academic` —C2— a `mediation` —C1— y los empates que la tabla inflada «diluía» se estrechan al contexto que encaja exacto: B1 4→1, B2 3→1, C1 2→1). Nuevo invariante `test_every_bank_context_fits_its_own_level_under_strict_tolerance`. **(B) P2-02 — tolerancia documentada como red de seguridad:** el docstring afirmaba que el margen amplio era «conservador… más margen en lugar de más exigencia» cuando un margen mayor admite MÁS `overshoot`; sobre el banco real la distinción estricta/amplia no cambia ninguna selección (0 de 48), así que `tolerance_for` y el bloque de constantes quedan como red de seguridad para bancos que declaren por encima de la envolvente, con `test_tolerance_bites_only_when_a_context_declares_above_the_envelope` que fija la inercia y verifica que SÍ discrimina con un contexto sintético. **(C) Proceso:** etiqueta anotada `v3.52.1` creada y empujada sobre `89eff0b` (P3-04 de la auditoría). Tests: pytest **2166 passed** en local (+2 netos), `ruff` limpio, vitest **76 ficheros/651 tests**, `tsc --noEmit` en verde, `check_release_consistency` **3.52.2** exit 0. Fuera de alcance (V3.53+): P1-02 (Learner Skill State 2.0 + `observed_difficulty`) y P1-03 (Planner 2.0 / Expected Learning Value); P3-01 y P3-02 siguen abiertos y aceptados.

- ✅ **V3.52.1 — Hotfix de producto + cierre del P1-01 (2026-09-11)** (**Versión estable `3.52.1`**, app `3.52.0 → 3.52.1`). **Hotfix ADITIVO (una columna de BD) que arregla tres bugs de producto y cierra el P1-01 de la auditoría externa de V3.52, SIN cambiar el comportamiento de producción del motor de dificultad (los 20 contextos reales declaran las 4 dimensiones: cobertura 4/4).** **(A) Usuarios fantasma «Visual Tester»:** la raíz era el find-or-create **no atómico** de `frontend/tests/visual/gateHelper.ts` contra la BD real (9 specs × 3 proyectos en paralelo → inserciones duplicadas); ahora `tests/visual/globalSetup.ts` crea **un** perfil marcado `is_test` en proceso único y `globalTeardown.ts` lo borra, con `gateHelper.ts` solo mockeando `GET /api/users`. Migración aditiva `users.is_test` (CREATE TABLE + `ALTER TABLE` idempotente), `GET /api/users` filtra por defecto (`include_test=true` lo usan los tests), `DELETE /api/users/{id}` acotado a `is_test=1` (borra las filas con `user_id` enumeradas dinámicamente), filtro `is_test` en `launcher/status.py` con degradación tolerante si la columna no existe, y `scripts/purge_virtual_testers.py --is-test`; los 2 perfiles existentes quedaron purgados (copia `tutor.db.bak-<ts>`). **(B) Listening «RUTA ACTUAL»:** el anillo pasa de `stats.level` a `resolveRouteLevel(sesión > ruta seleccionada > recomendada)` y el efecto de carga depende de `[userId, selectedLevel]` (cambiar de ruta recarga la pregunta). **(C) Bucle A/B:** nuevo módulo PURO `features/listening/abLoop.ts` (única fuente de verdad UI↔controller), `AudioController.play(url)` no recarga si la URL ya está cargada (preserva el bucle y reanuda sin reiniciar; repite si terminó), `loop`/`rewindIfPastSegmentEnd` con `>=` y `onCurrentTime` al rebobinar, marca tomada de `audioController.currentTime`, hint con el B marcado y controles centrados (`self-center`). **(D) P1-01:** `difficulty.fit` expone `dimensions_expected`/`dimensions_compared`/`coverage` y exige cobertura COMPLETA para `within` (un contexto sin `difficulty_vector` ya no gana con `distance=0`); `select_by_difficulty` degrada por mayor cobertura y luego por distancia; `difficulty_fit` y `DrillDifficultyFit` ganan las claves. **(E)** Normalizada la cifra de CI (2156+2 skipped primario) en CHANGELOG/PLAN/RELEVO/release notes. Tests: pytest **2164 passed** en local (+6), vitest **76 ficheros/651 tests** (+11), lanzador 76, `ruff`/`tsc`/`build` limpios, `check_release_consistency` **3.52.1** exit 0. **CI 6/6 en verde** (run [34622637688](https://github.com/jvelasca/english-tutor/actions/runs/34622637688) sobre `89eff0b`): Release consistency, Backend (ruff + pytest, 2162 passed + 2 skipped), Frontend (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content validation. Fuera de alcance (V3.53+): P1-02 (Learner Skill State 2.0 + `observed_difficulty`) y P1-03 (Planner 2.0 / Expected Learning Value).

- ✅ **V3.52.0 — Student Skill State + Difficulty Engine 2.0 (2026-09-11)** (**Versión estable `3.52.0`**, app `3.51.0 → 3.52.0`). **Release ADITIVA (dos columnas de BD) que cierra los dos P1 de la auditoría externa de V3.51 SIN tocar `transfer_state`, sus umbrales, `context_signals`, el scoring ni FSRS. Determinista, sin LLM.** **Parte A — Student level state (P1-01):** nuevo módulo puro `services/student_state.py` (`LEVEL_SOURCES`, `level_state`, `floor_level`, `is_certified`, `empty_state`) que separa `practice_level`/`estimated_cefr`/`demonstrated_cefr` y deriva el SUELO con la política `demostrado > estimado > declarado > ninguno`; solo el demostrado (certificación con retención) usa tolerancia estricta. Migración aditiva: `learning_profile.estimated_level`/`demonstrated_level` (CREATE TABLE + `ALTER TABLE` idempotente) conservando `cefr_level`; `repositories.profile.get_profile` devuelve las dos columnas y nueva `set_level_state` (`set_cefr` queda de wrapper que no pisa el demostrado). `domain.profile.get_profile_summary` escribe AMBOS niveles y expone `demonstrated_level` (aditivo en `schemas/profile.py`); `domain.vocabulary._learner_level_state` lee la caché en O(1) y pasa `learner_level` + `learner_level_source` a `context_for` (paridad GET↔POST). **Parte B — Difficulty Engine 2.0 (P1-02):** nuevo módulo puro `services/difficulty.py` (`DIFFICULTY_DIMENSIONS`, `CEFR_CAPACITY` monótona con `interaction` retrasada en A1–B1, `capacity_for`, `challenge_vector` = máximo por dimensión, `fit` con distancia/`max_overshoot`/`within`, `select_by_difficulty` = conserva los `within` y, entre ellos, los de menor distancia, degradando al más cercano si ninguno encaja; tolerancias `DIFFICULTY_TOLERANCE = 1` demostrado / `DIFFICULTY_TOLERANCE_ESTIMATED = 2`). `services/transfer.py` sustituye `_difficulty_floor`/`_within_band` escalares por el motor (el TECHO lingüístico del ítem sigue en `_within_level`; `TRANSFER_DIFFICULTY_BAND` queda deprecada, `TRANSFER_DIFFICULTY_KEYS` pasa a alias) y su retorno gana `difficulty_fit` + `learner_level_source`. **Contratos aditivos:** `TransferContextOut` y `DrillTransferContext` (`learner_level_source`, `difficulty_fit`/`DrillDifficultyFit`). **Deuda confirmada y diferida (V3.55):** `assessed_skill` → decisión del planner y `skill_priorities` → `select_task` (evitar el doble conteo de `written_production` con el drill `write`). Tests: pytest **2156 passed + 2 skipped en CI** (2158 passed en local con el modelo Whisper; +39: `test_student_state_v352.py` 15, `test_difficulty_engine_v352.py` 24; ajuste de `test_learner_level_raises_the_difficulty_floor` a `difficulty_fit`), `ruff` limpio, `check_release_consistency` **3.52.0** exit 0. **CI 6/6 en verde** (run [34604654412](https://github.com/jvelasca/english-tutor/actions/runs/34604654412) sobre `23cbad7`; los 2 skipped son `backend/tests/test_stt_asr_integration.py`, opt-in del modelo Whisper no descargado en el runner). Fuera de alcance: Sense Engine 2.0, `observed_difficulty` persistido, entrega oral real del transfer, `expected_learning_value`/Adaptive Planner 2.0, Context Bank Family/Instance, offline TTS y code splitting del frontend.

- ✅ **V3.51.0 — Task/Skill semantics + learner-level difficulty matching (2026-09-11)** (**Versión estable `3.51.0`**, app `3.50.0 → 3.51.0`). **Release ADITIVA (una columna de BD) que cierra los tres P1 de la auditoría externa de V3.50 SIN tocar la escalera `transfer_state`, sus umbrales, FSRS ni el scoring.** **Parte A — Semántica explícita de tarea (P1-01):** nuevo módulo puro `services/task_semantics.py` con `TASK_SEMANTICS` (`target_skill`/`assessed_skill`/`assessment_mode`/`evidence_skill` por actividad), `ASSESSMENT_MODES` y helpers que nunca lanzan; el drill **Transfer**, que se entrega por TEXTO, declara `target_skill="spontaneous_use"`, `assessed_skill="written_production"`, `assessment_mode="written"` y conserva `evidence_skill="spontaneous_use"`. **Parte B — Ledger honesto (migración aditiva):** `learning_evidence.assessed_skill` (CREATE TABLE + `ALTER TABLE` idempotente), persistido en `record_evidence`/`record_evidence_bulk`/`list_evidence` y agregado en `summarize_evidence`/`summarize_by_target`/`empty_summary` (`assessed_skill_attempts`/`assessed_skill_successes`, paridad pura↔SQL); las cinco vías del drill registran las dos dimensiones (`skill` no cambia, `assessed_skill` dice qué se evaluó). **Parte C — Vector de prioridades (P1-03):** `planner.skill_priorities(signals)` expone el vector completo en orden canónico y `limiting_skill` pasa a ser su argmax; `_transfer_target_skill` elige solo entre `task_semantics.assessable_skills("transfer")` (nunca `spoken_production`); `context_for` y la cola de repaso exponen `skill_priorities` (aditivo). **Parte D — Dificultad por nivel del alumno (P1-02):** `context_for(..., learner_level="")`; el CEFR del ítem es el TECHO (`_within_level`) y el nivel DEMOSTRADO del alumno (`domain.vocabulary._learner_level`, caché del Student Model en `learning_profile.cefr_level`) el SUELO de reto de `_difficulty_floor`; sin nivel conocido el resultado es idéntico a V3.50. **Contratos aditivos:** `TransferContextOut`/`TransferAttemptOut` (target/assessed/mode/item_level/learner_level/skill_priorities) y `ReviewQueueItem.skill_priorities`, con espejo opcional en `types/api.ts`. Tests: pytest **2119 passed** (+20: `test_task_semantics_v351.py`; ajuste del contrato exacto de `empty_summary` en `test_learning_evidence_v336.py`), vitest **75 ficheros/641 tests**, `ruff`/`tsc` limpios, `npm run build`, `check_beta_v3`, `content_validation` y `check_release_consistency` **3.51.0** exit 0. **CI 6/6 en verde** (run [34599637351](https://github.com/jvelasca/english-tutor/actions/runs/34599637351) sobre `c056546`). **P3-01:** corregida la cifra documental de V3.50 (2099 → 2097 passed, la de CI). Fuera de alcance (V3.52+): Sense Engine 2.0, entrega oral real del transfer, `observed_difficulty` por evento, `expected_learning_value`/Adaptive Planner 2.0, Context Bank Family/Instance y offline TTS.

- ✅ **V3.50.0 — Context→Skill mapping + difficulty matching (2026-09-11)** (**Versión estable `3.50.0`**, app `3.49.0 → 3.50.0`). **Release ADITIVA y SIN migración de BD que NO cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS**: cierra el candidato diferido por V3.49.0 (los datos de dificultad del banco de contextos V3.47/V3.48 y la modalidad limitante del planner dejan de ser inertes al elegir la tarea). **Parte A — Context→Skill mapping:** nuevo vocabulario declarado `CONTEXT_SKILLS` (espejo verificado de `services.evidence.LEXICAL_SKILLS`, declarado en `transfer.py` para no crear el ciclo `evidence → transfer → evidence`), `skills` curado en los 20 contextos del banco (subconjunto no vacío con al menos una modalidad de producción; los 6 originales conservan `id` y valores core congelados y solo ganan `skills`) y helper puro `context_skills` (acepta dict/`id`/`context_id`, normaliza y nunca lanza). **Parte B — Difficulty matching:** `TRANSFER_DIFFICULTY_BAND = 1`, `_difficulty_floor` (objetivo = mayor del techo real alcanzable y la posición del nivel en la escala 1..6; sin él un ítem B1 seguía recibiendo contextos A1) y `_within_band` (degrada con gracia a lo más difícil disponible). `context_for` gana la firma aditiva `skill=""` y un pipeline determinista: usados → `_within_level` → mínimo sobre todo el alcance → preferencia por modalidad limitante → banda → novedad (V3.43) → `_stable_index`; el retorno añade `skills`. Consumo en `domain/vocabulary.py` con `_transfer_target_skill` (`planner.limiting_skill(planned_signals(...))`, `""` sin segmentación por modalidad) en GET y en el fallback del POST, con paridad de `context_id`. Contratos aditivos `TransferContextOut.skills`/`DrillTransferContext.skills?`; sin cambio de UI. Tests: pytest **2097** (+15: `test_context_skill_v350.py`; ajuste en `test_transfer_cefr_v347.py`), vitest **75 ficheros/641 tests** (sin cambios), `ruff`/`tsc` limpios, `npm run build`, `check_beta_v3`, `content_validation` y `check_release_consistency` **3.50.0** exit 0. **CI 6/6 en verde** (run [34594042697](https://github.com/jvelasca/english-tutor/actions/runs/34594042697) sobre `1c8d6e0`). Fuera de alcance (V3.51+): Sense Engine 2.0, semantic appropriateness, `expected_learning_value`/Adaptive Planner 2.0 y la persistencia de la dificultad por evento.

- ✅ **V3.49.0 — Transfer Evidence 3.0: confianza explicable del eje de transferencia (2026-09-11)** (**Versión estable `3.49.0`**, app `3.48.1 → 3.49.0`). **Release ADITIVA y SIN migración de BD que NO cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS**: cierra el punto 8 de la auditoría `docs/audit/P-AUDITORIA-TOTAL-V343.md` («los nombres de los estados pueden sugerir más evidencia de la disponible»). Nueva función pura `services.evidence.transfer_confidence` (`{score, level, sample, drivers, recency_days}`): `score` = suma ponderada de seis `drivers` 0..1 declarados (`contexts`/`successes`/`diversity`/`independence`/`variety`/`spacing`, `TRANSFER_CONFIDENCE_WEIGHTS` suman 1.0), `level` ∈ `none`/`low`/`medium`/`high` calibrado para que `transfer_stable` caiga en `high`, y `recency_days` informativo FUERA del `score` (sin reloj). Monótona no decreciente al añadir evidencia no andamiada y conservadora (`none`, nunca inflada) en resúmenes legacy/parciales; se deriva en la MISMA frontera pura↔SQL (`with_transfer_state`), expuesta en `planner.planned_signals` y `lexicon.review_item`, con contrato aditivo `ReviewQueueItem.transfer_confidence` (`schemas/learning.py`, `types/api.ts`) y etiqueta honesta en `ReviewQueueSection` (aclara que es «transferencia contextual demostrada bajo el protocolo interno», no generalizada). Claves i18n `dictionary.review.transfer.level.*`/`scope` con paridad es/en. Tests: pytest **2084** (+9: `test_transfer_confidence_v349.py`), vitest **75 ficheros/641 tests** (+2), `ruff`/`tsc` limpios y `check_release_consistency` **3.49.0** exit 0. **CI 6/6 en verde** (run [34591158824](https://github.com/jvelasca/english-tutor/actions/runs/34591158824) sobre `034da5c`). Fuera de alcance (V3.50+): Context→Skill mapping y difficulty matching por `difficulty_vector`, Sense Engine 2.0, semantic appropriateness y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.48.1 — APRENDER más limpio + ruta CEFR seleccionada (2026-09-11)** (**Versión estable `3.48.1`**, app `3.48.0 → 3.48.1`). **Patch SOLO-FRONTEND (más un script de mantenimiento), sin cambios de contrato ni migración de BD.** **(A) Listening sin «Antes de escuchar»:** `microFlow` salta los pasos `stage === "pre"` (`firstRenderableIndex`), el flujo arranca en `while1`; la tarjeta y las claves `listening.flow.preTitle`/`preHint`/`begin` se eliminan y el contexto del ítem pasa a caption compacta bajo el botón de audio (el backend sigue sirviendo `pre` por contrato, sin alterar `transcript_policy`). **(B) Notas CEFR plegables:** nuevo `components/InfoDisclosure.tsx` (`button` + `aria-expanded` + `MoreHorizontal`, montado solo al abrir; variantes `inline`/`corner`) que pliega `routeNote`/`routeCertNote`/`routeRingHelp`/`routesMapHint` en Listening y en el mapa de rutas de las cinco destrezas, y la prosa explicativa (`demonstrateNote`/`demonstrateFormal`/`extraHonestNote`) en los seis paneles de nivel, dejando visibles los estados accionables (gate/`demoNotYet`). **(C) Ruta CEFR seleccionada persistente:** `utils/selectedRoute.ts` (validación `A1..C2`, parseo tolerante, `resolveRouteLevel`) y `hooks/useSelectedRoute.ts` (persistencia doble `localStorage` + `selected_route_level` vía `GET/PUT /api/settings`, sin cambios de backend); prioridad **sesión > ruta seleccionada > nivel recomendado**, pulsar un anillo selecciona y abre su panel (anillo resaltado + «Ruta seleccionada»), chip «Auto» para volver al motor y `exitSession` que conserva la selección. **(D) Limpieza:** `scripts/purge_virtual_testers.py` (dry-run por defecto; `--apply` con copia `tutor.db.bak-<ts>` y borrado transaccional enumerando tablas con `user_id`) y eliminación de los 6 perfiles `Visual Tester` (quedan los 2 reales). Tests: vitest **75 ficheros/639 tests** (+3/+16), `check_i18n_coverage` 0 indefinidas/0 duplicadas, `tsc`/`build`/`check_release_consistency` **3.48.1** en verde. **CI 6/6 en verde** (run [34588975928](https://github.com/jvelasca/english-tutor/actions/runs/34588975928) sobre `6a0a757`). Fuera de alcance (V3.49): Sense Engine 2.0, Context→Skill mapping, difficulty matching y Transfer evidence 3.0; no se tocan FSRS, Evidence Ledger ni el gate.

- ✅ **V3.48.0 — Context Bank 2.0 + diversidad 2.0 (2026-09-11)** (**Versión estable `3.48.0`**, app `3.47.0 → 3.48.0`). **Release ADITIVA y SIN migración de BD que cierra los dos P2 abiertos por la auditoría externa de V3.43.0 sobre la transferencia**, sin tocar la escalera `transfer_state`, el scoring ni FSRS. **Parte A — Context Bank 2.0:** `TRANSFER_CONTEXTS` pasa de 6 a 20 contextos (14 nuevos: `introductions`, `routine`, `directions`, `shopping`, `health`, `travel_plan`, `work_problem`, `community`, `debate`, `review`, `mediation`, `academic`, `negotiation`, `keynote`) con cobertura A1:3 / A2:4 / B1:4 / B2:3 / C1:3 / C2:3; cada uno declara los 6 atributos core, `cefr`, `difficulty_vector` y los ejes de variedad, y ningún `prompt` contiene `{word}`. Los **6 contextos originales se congelan** (mismos `id` y valores core; guardia por test) para no reinterpretar la evidencia histórica. **Parte B — Diversidad 2.0 informativa:** nuevos `CONTEXT_VARIETY_DIMENSIONS` (`register`/`lexical_environment`/`syntactic_focus`), función pura `context_variety` (`{dimensions, varied_dimensions, score}`) y `context_dimensions(..., dimensions=...)` generalizada vía `_normalize_dimensions`; `context_diversity` conserva sus cuatro claves históricas y añade `variety`. **El gate NO cambia** (`CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score`, `diverse_dimensions` y `CONTEXT_DIVERSITY_MIN = 2`; distancia mínima entre pares `>= 2`); `empty_summary()["context_diversity"]` gana el default `variety` por paridad pura↔SQL. Contrato aditivo `ContextDiversity.variety` (`types/api.ts`), **sin cambio de UI**. Tests: pytest **2075** (+12: `test_context_bank_v348.py`; ajustes en `test_transfer_v343.py` y `test_learning_evidence_v336.py`), vitest **72 ficheros/623 tests** (sin cambios), `ruff`/`tsc` limpios y `check_release_consistency` **3.48.0** exit 0. Fuera de alcance (V3.49): TTS/offline (auto-descarga implícita de voces), Sense Engine 2.0, `transfer_state` enriquecido y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.47.0 — Transfer Evidence 2.0 + CEFR/`difficulty_vector` del contexto (2026-09-11)** (**Versión estable `3.47.0`**, app `3.46.0 → 3.47.0`). **Release doble y ADITIVA, SIN migración de BD, que cierra los dos P1 abiertos por la auditoría de V3.46.0 sobre la transferencia**, sin tocar el scoring (`score_transfer_attempt`) ni FSRS. **Parte A — Transfer Evidence 2.0 (P1-02):** `services/evidence.py` endurece la escalera: `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED = 2` (2 éxitos limpios NO andamiados para `transfer_demonstrated`, antes 1), `TRANSFER_STABLE_MIN_DAYS` `2 → 3` y nuevo `TRANSFER_STABLE_MIN_GOALS = 2` (objetivos comunicativos distintos); `TRANSFER_STABLE_MIN_CONTEXTS = 3` se mantiene. `context_signals` expone la evidencia fina (`unscaffolded_clean_success_contexts`/`_days`, `clean_success_goals` derivados de la dimensión `communicative_goal`, `last_clean_success_at`/`last_unscaffolded_clean_success_at`; la decisión NO usa reloj) y `empty_summary` los defaults neutros. Fallback legacy intacto: sin datos de condición se conserva la regla anterior y la paridad pura↔SQL sigue siendo por construcción (`repositories/evidence.py` reutiliza la MISMA `context_signals`). **Parte B — CEFR/`difficulty_vector` del contexto:** los 6 contextos de `services/transfer.py` declaran `cefr` (`services.cefr.CEFR_LEVELS`) y `difficulty_vector` (`lexical`/`syntax`/`discourse`/`interaction`, 1..5, convención de listening/speaking); nuevos helpers puros `difficulty_from_vector` (media redondeada, clamp 1..6) y `cefr_index`; `context_for(..., level="")` (retrocompatible) prefiere contextos de nivel ≤ al del alumno y, si ninguno es alcanzable, cae al nivel más cercano por arriba; `context_for` devuelve además `cefr`/`difficulty_vector`/`difficulty`, expuestos por `TransferContextOut` y `DrillTransferContext` (`types/api.ts`). `domain/vocabulary.py` pasa `level=row.get("cefr")` en el GET y en el registro. **Sin cambio de UI.** Tests: pytest **2063** (+16: `test_transfer_evidence_v347.py` y `test_transfer_cefr_v347.py`), vitest **72 ficheros/623 tests** (sin cambios), `ruff`/`tsc` limpios y `check_release_consistency` **3.47.0** exit 0. Fuera de alcance (V3.47.1/V3.48): TTS/offline (auto-descarga implícita de voces), Sense Engine 2.0, Context Bank 2.0, `transfer_state` enriquecido y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.46.0 — Condición de recuperación en la transferencia (`transfer_condition`) (2026-09-11)** (**Versión estable `3.46.0`**, app `3.45.0 → 3.46.0`). **Cierre quirúrgico del P1 `transfer_condition` de la auditoría de V3.43.0**, release ADITIVA y SIN migración destructiva. Hasta ahora TODO intento de transferencia era `spontaneous_use` con `support_level="spontaneous"`, sin distinguir si la unidad se usó porque se pidió (`prompted`), porque el escenario la insinuaba (`cued_context`), por decisión propia en un escenario abierto (`open_context`), por elección libre (`free_choice`) o porque surgió sola (`naturally_emergent`); sin esa dimensión `transfer_demonstrated` podía declararse con tareas andamiadas. `services/transfer.py` define `TRANSFER_CONDITIONS` (orden de andamiaje decreciente), `SERVABLE_CONDITIONS`, `UNSCAFFOLDED_CONDITIONS`, `REQUIRED_TARGET_CONDITIONS`, `CONDITION_INSTRUCTIONS`, `normalize_condition` y la escalera pura `condition_for_state` (`not_ready` con intentos → `prompted`; `not_ready` sin intentos y `emerging` → `cued_context`, comportamiento de V3.43; `contextualized`+ → `open_context`, unidad NO obligatoria). Persistencia aditiva `transfer_condition TEXT NOT NULL DEFAULT ''` en `learning_evidence` (ALTER idempotente) con plumbing en `record_evidence`/lote/`list_evidence`/SELECT de detalle. `services/evidence.py` agrega `transfer_conditions`, `success_conditions` y `unscaffolded_clean_successes`, y **endurece `transfer_demonstrated`**: además de 2 contextos limpios con diversidad real, exige ≥1 éxito limpio NO andamiado (fallback legacy sin datos de condición). `domain/vocabulary.py` deriva la condición del resumen (el cliente NO la declara), la sirve, la persiste, y un intento de `open_context` que NO usa la unidad no se registra (`required_target=false`). Contratos aditivos (`condition`/`required_target`/`unscaffolded`) y UI del drill con la condición visible y aviso neutro `transferNotRequired`. Tests: pytest **2047**, vitest **72 ficheros/623 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.46.0** exit 0. Fuera de alcance (V3.47+): CEFR/`difficulty_vector` del contexto (P1 restante), Context Bank 2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.45.0 — Traductor de viaje práctico + voz española real (2026-09-11)** (**Versión estable `3.45.0`**, app `3.44.0 → 3.45.0`). Cierra la experiencia del Traductor de viaje. **(A) Voz española real:** la salida en español sonaba a «un inglés hablando español» porque `language="es"` degradaba a la voz inglesa (no había voces `es_*` instaladas, `download_models.py` solo bajaba la inglesa y `resolve_voice` caía al fallback global). Ahora `SPANISH_VOICE = "es_ES-davefx-medium"` y `DEFAULT_VOICES = {"en": ..., "es": ...}`, `default_voice_for(language)` (pura) y `resolve_voice` priorizan el default del idioma; `ensure_voice_for_language(language)` auto-descarga la voz del idioma en `/api/tts` (no-op si ya está, `False` sin red con caché negativa de 300 s, nunca lanza) y `download_models.py` instala también la española reutilizando el catálogo curado. `VoicesResponse.defaults` expone el mapa idioma → voz (aditivo). **(B) Modo Conversación:** `TranslatorScreen` gana dos pestañas (Conversación por defecto, Escribir intacto). Nuevos `useVoiceTurn.ts` (MediaRecorder + AnalyserNode + VAD + transcripción; helper PURO `nextTurnVadState` que cierra por silencio y descarta picos; auto-stop 120 s), `BigMicButton.tsx` (botón `size-24` con anillo según nivel), `ConversationPanel.tsx` (por idioma, repetir audio, avisos, rotación) y `ConversationTranslator.tsx` (dos paneles, traduce y auto-reproduce cada turno, historial en `english-tutor.translator-conversation`, toggles auto-play/«cara a cara», tamaño de texto y aviso/descarga de la voz española). i18n `translator.mode.*`/`translator.conversation.*` con paridad es/en. El Traductor sigue siendo AUXILIAR: no registra evidencia. Tests: pytest **2030**, vitest **72 ficheros/621 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.45.0** exit 0. Fuera de alcance (V3.46+): `transfer_condition` + CEFR/`difficulty_vector` del contexto (P1), Context Bank 2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.44.0 — Lexicón sense-aware + scoring semántico 2.0 (2026-09-11)** (release `3.44.0`, app `3.43.0 → 3.44.0`). **Cierre quirúrgico de los dos P1 conceptuales de la auditoría de V3.43.0** (9,6/10), sin migración de datos y con contratos aditivos. **P1-01 (sense-aware):** el contrato de contenido gana `senses` (`GENERATOR_VERSION` `1.3.0 → 1.4.0`) con el helper puro `normalize_senses`; migración aditiva `senses_json` en `dictionary_entries`/`dictionary_reverse_entries` (idempotente, también en la tabla inversa ya creada); nuevo módulo PURO `services/semantics.py` con `pos_family`, `families_from_senses`, `occurrence_role` y `semantic_adequacy` (función de la ocurrencia vs familias POS de los sentidos). **P1-02 (scoring robusto):** `score_transfer_attempt(word, text, *, pos="", senses=())` devuelve `adequacy` ∈ `fit`/`suspect`/`incorrect`/`unknown`; `incorrect` → `semantic_mismatch` es el ÚNICO que bloquea el clean success y `suspect` → `semantic_doubt` (nueva en `TRANSFER_ERROR_TYPES`) es advisory; sin sentidos → `unknown`. `passed`/`lexical_transfer`/`semantic_fit` conservan su semántica y `score_write_attempt` no cambia. Contratos aditivos (`DictionaryEntryOut.senses`, `adequacy` admite `incorrect`) y feedback de `wordDrill` para `incorrect`. Tests: pytest **2020**, vitest **70 ficheros/608 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.44.0** exit 0. Fuera de alcance (V3.45+): `transfer_condition`, CEFR/`difficulty_vector` del contexto, Context Bank 2.0 y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.43.0 — Transfer 2.0: target oculto, semanticidad, diversidad y `transfer_state` (2026-09-11)** (**Versión estable `3.43.0`**, app `3.42.0 → 3.43.0`). **Cierre quirúrgico de los 4 P1 de la auditoría de V3.42.0** sobre la evidencia de transferencia, sin migración y con contratos HTTP aditivos. **P1-01:** `services/transfer.py` reescribe el banco de contextos con atributos (`topic`/`communicative_goal`/`discourse_type`/…) y consignas que NUNCA contienen el target; el drill oculta la palabra también en `transfer` y la cola deja de mostrarla. **P1-02:** `score_transfer_attempt(word, text, *, pos)` separa el transfer léxico (`lexical_transfer`) de la adecuación semántica (`semantic_fit`/`adequacy` = `fit`/`suspect`/`unknown`) con un proxy DETERMINISTA (POS `noun` usada como verbo o `verb` tras determinante → `suspect`); el uso sospechoso mantiene `passed=True` y guarda `error_type="semantic_mismatch"` (nueva `TRANSFER_ERROR_TYPES`), sin bloquear la evidencia léxica. **P1-03:** `context_signals` mide diversidad contextual REAL (`context_diversity` con `diverse_dimensions`, `CONTEXT_DIVERSITY_MIN = 2`) sobre ÉXITOS LIMPIOS (sin `semantic_mismatch`), y `context_for` prioriza el contexto más distante de los ya logrados. **P1-04:** `transfer_state` (`not_ready` → `emerging` → `contextualized` → `transfer_demonstrated` → `transfer_stable` → `automatic`) sustituye al booleano `transfer`; `has_contextual_transfer` y `transfer_gap` leen el estado y `planned_signals` expone `transfer_state`/`context_diversity`. Contratos aditivos (`TransferContextOut`/`TransferAttemptOut`/`ReviewQueueItem`) y `spontaneous` justificado al ocultarse el target. Tests: pytest **1989**, vitest **70 ficheros/607 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.43.0** exit 0. Fuera de alcance (V3.44): modelo *sense-aware*, Context Bank a escala y `expected_learning_value`.

- ✅ **V3.42.0 — Transferencia contextual real + actividad `spontaneous_use` + gobierno por unidad léxica (2026-09-10)** (**Versión estable `3.42.0`**, app `3.41.0 → 3.42.0`). **Fase 4 y CIERRE del plan maestro V3.39+** (diccionario reversible → Traductor → motor de tarea óptima → transferencia real). La auditoría de V3.38.1 había separado dos cosas que el sistema confundía: `situation` es recuperación **contextualizada** y transferir es usar la unidad en un contexto **DISTINTO** del de aprendizaje. `services/transfer.py` (puro) aporta un banco curado de contextos y la elección determinista del que toca (`context_for`, filtrado por los `context_id` ya usados + hash estable `zlib.crc32`, rotación con `exhausted=True` al agotarse), `services/evidence.py::context_signals` agrupa el ledger por `context_id` (`contexts`, `context_attempts`, `success_contexts`, `home_context`, `transfer` con `CONTEXT_TRANSFER_MIN = 2`) y `planner.transfer_gap` decide cuándo pedir la tarea (≥ 2 éxitos en ≥ 1 contexto y < 2 contextos), añadiendo `transfer_gap` al orden de `EVIDENCE_REASON_ORDER`. La modalidad `spontaneous_use` deja de medirse sin tarea: **nueva actividad `transfer`** con `score_transfer_attempt`, `GET /api/vocabulary/drill/transfer-context` (solo lectura) y `POST /api/vocabulary/drill/transfer-attempt` (evidencia `spontaneous_use` + `activity_id="drill:transfer"` + `context_id` del contexto NUEVO). **Gobierno por unidad léxica:** `lexicon.unit_evidence` agrega el estado por `lexical_unit` (suma de contadores/mapas, `success_rate` recalculada del total, `automatic`/`automatic_skills`/`success_contexts` unidos, `transfer` derivado) para que `go/went/gone/going` no sean cuatro estados independientes; la cola expone `units` y cada ítem `unit_surfaces`/`transfer`/`success_contexts` (aditivos, la evidencia por forma no cambia). **Descomposición de `wordDrill.tsx`:** peldaños presentacionales extraídos a `wordDrillSteps.tsx` (`RecognitionStep`/`RecallStep`/`ProductionTextarea`/`TransferStep`) sin cambiar el contrato, escalera de 5 peldaños. Frontend: actividad `transfer` en la cola (palabra como recurso) y paso Transfer en el drill. Tests: pytest **1975**, vitest **70 ficheros/606 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.42.0** exit 0. **Plan maestro V3.39+ completo: sin fases pendientes.**

- ✅ **V3.41.0 — Motor de tarea óptima por skill + actividad de escritura + robustez de señales (2026-09-10)** (**Versión estable `3.41.0`**, app `3.40.0 → 3.41.0`). Fase 3 del plan maestro V3.39+ (diccionario reversible → Traductor → motor de tarea óptima → transferencia real). El planner pasa de "¿qué palabra repaso?" a **"¿qué modalidad limita, qué actividad la cierra y con qué apoyo?"**: `skill_priority`/`limiting_skill` (argmax con desempate canónico) y `select_task` (`{skill, activity, reason, support_level}`, orden `error_prone` → `skill_gap` → `slow_recall`) separan la **selección de actividad** de la **puntuación de prioridad**. El hueco simétrico `spoken ✓ / written ✗` deja de ser un diagnóstico muerto: nueva actividad **`write`** con scoring determinista y sin LLM (`score_write_attempt`, `unit_produced` + `WRITE_MIN_WORDS = 4`, taxonomía `WRITE_ERROR_TYPES`) y endpoint `POST /api/vocabulary/drill/write-attempt` que acredita `written_production`. **Señales robustas:** `recency_signals` (ventana de los 10 eventos más recientes + `median`/`p75`/`p90`/`latency_trend`, reutilizada por el resumen SQL), fallo grave y `error_prone` sobre la ventana, `is_automatic` **unificado** con `automatic_skills` cuando hay segmentación (con el criterio global como fallback de resúmenes parciales) y ledger encadenado al evento **cronológicamente anterior**. `example_for_many` batchea los ejemplos del `cloze` en una sola pasada al banco. Frontend: paso `write` en el drill y actividad `write` en la cola. Contratos HTTP **aditivos** (`limiting_skill`/`task` en `ReviewQueueItem`). Tests: pytest **1960**, vitest **70 ficheros/602 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.41.0** exit 0. Siguiente: Fase 4 (transferencia contextual real y gobierno por `lexical_unit`).

- ✅ **V3.40.0 — Traductor de viaje bidireccional ES↔EN (2026-09-10)** (**Versión estable `3.40.0`**, app `3.39.0 → 3.40.0`). Fase 2 del plan maestro V3.39+
  (diccionario reversible → Traductor → motor de tarea óptima → transferencia
  real). **Nuevo destino AUXILIAR `translator`** (`/traductor`, 5.º en la
  navegación tras el separador, icono `Languages`, `grid-cols-5` en la
  bottom-nav) con `TranslatorScreen`: conmutador ES→EN / EN→ES (defecto ES→EN,
  el caso del viajero), botón ⇄ que intercambia sentido y textos, entrada por
  voz (`MicButton` con idioma) o texto, panel de resultado con altavoz por
  idioma (`ListenButton` con `language`) e historial reciente en
  `localStorage`. Es una ayuda de apoyo: **no registra evidencia** y funciona sin
  perfil. **Backend:** `services/translate.py` pasa a bidireccional con prompt
  por dirección y caché por `(direction, text)`, `/api/translate` gana
  `direction` (defecto `"en-es"`), `/api/tts` gana `language` y
  `resolve_voice(prefs, language)` elige la voz del idioma (preferida del idioma
  → default del idioma → primera instalada del idioma → fallback). El catálogo
  Piper añade tres voces `es_*` medium descargables. Contratos HTTP aditivos y
  retrocompatibles. Tests: pytest **1924**, vitest **70 ficheros/597 tests**,
  `ruff`/`tsc` limpios y `check_release_consistency` **3.40.0** exit 0.
  Siguiente: Fase 3 (motor de tarea óptima por skill).

- ✅ **V3.39.0 — Diccionario reversible EN↔ES + persistencia de la pestaña
  (2026-09-10)** (**Versión estable `3.39.0`**, app `3.38.1 → 3.39.0`). Fase 1 del
  plan maestro V3.39+ (diccionario reversible → Traductor → motor de tarea óptima
  → transferencia real). **Diccionario ES→EN:** inversa instantánea sobre las
  traducciones cacheadas (`services/dictionary_reverse.py`, puro: glosa múltiple,
  acentos plegados con la eñe conservada, ranking exacto > parcial) y generación
  con el modelo local solo si no hay coincidencia, cacheada en la tabla propia
  `dictionary_reverse_entries` (aislada de `dictionary_entries` para no
  contaminar el banco de distractores del MCQ). `GENERATOR_VERSION` 1.2.1 →
  **1.3.0** (política de frescura única para ambas direcciones) y fontanería de
  generación (single-flight, negative cache, rate limit) indexada por
  `(direction, word)`. Contrato HTTP aditivo: `direction` (defecto `"en-es"`) en
  la petición y `direction`/`alternatives` en la respuesta. La consulta sigue
  siendo SOLO LECTURA (D3). **Frontend:** conmutador EN↔ES, tarjeta reetiquetada
  y puente de práctica que practica el término INGLÉS. **Persistencia de la
  pestaña Personal/Consultar:** `useDictionaryView` con patrón doble
  (`localStorage` `english-tutor.dictionary-view` + settings `dictionary_view`),
  integrado en `DictionaryScreen` y en `QuizRoutePage`. Tests: pytest **1910**,
  vitest **68 ficheros/578**, `ruff`/`tsc` limpios y
  `check_release_consistency` **3.39.0** exit 0. Siguiente: Fase 2 (Traductor).

- ✅ **V3.38.1 — Cierre quirúrgico de los P1 del Planner + UI de diccionario y
  estado (2026-09-10)** (**Versión estable `3.38.1`**, app `3.38.0 → 3.38.1`).
  Release ADITIVA que cierra los 4 P1 de la auditoría de V3.38.0 y endurece
  `situation`, sin funcionalidad nueva, sin migración de BD y sin tocar scoring,
  FSRS ni la semántica del intervalo de evidencia. **(P1-01) Planner globalmente
  óptimo:** `domain/review.py` separa la cota de CANDIDATOS
  (`REVIEW_QUEUE_CANDIDATE_LIMIT = 500`) del límite de PRESENTACIÓN
  (`REVIEW_QUEUE_*_LIMIT`) y el recorte se aplica DESPUÉS del ranking global por
  `priority`; las cues se resuelven solo para los ítems servidos (arregla de paso
  el coste de `example_for` por todas las vencidas). **(P1-02) Señales por
  modalidad:** `summarize_evidence`/`summarize_by_target` (paridad exacta pura↔SQL)
  añaden `skill_attempts` y `skill_mean_response_time_ms`, `planned_signals` gana
  el bloque `skills` (attempts/successes/success_rate/weakness/support/latency por
  modalidad) y `is_slow_recall` deja de leer la media GLOBAL: mide la latencia de
  `recall` y exige un éxito de recall. **(P1-03) `skill_gap` parcial accionable:**
  basta con que falte `spoken_production` (caso `written ✓ / spoken ✗`) para
  dirigir la siguiente tarea a `sentence`. **(P1-04) Automaticidad robusta:**
  `AUTOMATIC_MIN_INDEPENDENT` 2 → **3**, nueva ratio mínima
  `AUTOMATIC_MIN_SUCCESS_RATIO = 0.80` y ausencia de fallo grave
  (`wrong_word` > `AUTOMATIC_MAX_WRONG_WORD_ERRORS`), aplicado a `is_automatic` y
  a `automatic_skills`. **(P2-01) `situation` endurecida:** nuevo módulo puro
  `services/situation.py` (única fuente de verdad) exige UN hueco, UNA sola frase
  y sin fuga morfológica regular de la diana; lo usan la generación
  (`GENERATOR_VERSION` 1.2.0 → **1.2.1**, regeneración lazy de la caché) y la
  lectura de la escalera. **UI:** ruta dedicada `/diccionario`
  (`DICTIONARY_PATH`, `routeMap`, cuarto destino tras separador, `DictionaryScreen`
  con vistas Personal/Consultar) y el indicador de conexión se integra en la
  cabecera (`ConnectionIndicator` con popover `SystemStatus`), eliminando la barra
  de estado inferior. Tests: pytest **1890**, vitest (**67 ficheros/568**),
  `ruff`/`tsc` limpios y `check_release_consistency` **3.38.1** exit 0. Diferido a
  V3.39: prioridad completa por skill, routing de escritura para
  `written_production`, `sense`/CEFR/contexto y refactor de `wordDrill.tsx`.

- ✅ **V3.38 — La siguiente tarea óptima: `situación`, planner y automaticidad por
  skill (2026-09-10)** (**Versión estable `3.38.0`**, app `3.37.1 → 3.38.0`). Cierra
  el incremento que V3.37 dejó abierto en tres frentes. **(1) P1-03 — automaticidad
  por modalidad.** El `skill` del ledger léxico deja de ser `""`: cada evento
  declara su MODALIDAD con el vocabulario canónico `LEXICAL_SKILLS` (`recall`,
  `written_production`, `spoken_production`, `spontaneous_use`); `summarize_evidence`
  (puro) y `summarize_by_target` (SQL, con paridad exacta fijada por test) añaden
  `skill_successes`/`skill_success_days`/`skill_independent_successes`/
  `skill_independent_days`, y `automatic_skills` segmenta `is_automatic` por
  modalidad: un ítem ya no es "automático" porque mezcle aciertos de reconocimiento
  con producción. **(2) Planner (Optimal Next Task).** Nuevo servicio puro
  `services/planner.py`: `planned_signals` combina olvido (1 − `retrievability`),
  hueco (`gap`), debilidad (`weakness`), dependencia de apoyo (`support`) y latencia
  (`latency`) con pesos declarados y calibrables (`PRIORITY_WEIGHTS`);
  `priority_score` los agrega y `evidence_reason` añade razones dirigidas por la
  evidencia fina (`error_prone`, `skill_gap`, `slow_recall`). La cola de repaso
  (`GET /api/learning/review`) pasa a ordenarse por esa prioridad —desempate por
  `retrievability` y palabra— y cada ítem expone `priority`/`signals`/`why`/
  `automatic_skills` (aditivos, sin spoiler). **(3) `situación`.** El contrato de
  contenido de la caché sube `GENERATOR_VERSION` 1.1.0 → **1.2.0** y gana
  `dictionary_entries.situation` (migración aditiva e idempotente): un enunciado
  situacional con un único hueco `_____`, validado de forma determinista (un solo
  hueco, sin spoiler, ≤ `MAX_SITUATION_CHARS`) y descartado —sin invalidar
  definición/traducción— si no cumple. `recall.RECALL_CUES` gana `situation` como
  TECHO de la escalera con apoyo `guided`; `next_recall_rung` solo llega a él con
  `cloze` consolidado y `resolve_recall_cue` sigue degradando solo hacia más apoyo.
  El GET/POST del drill lo sirven y lo declaran (`drill:recall:situation`), y la
  cola lo recomienda cuando hay contenido. Contrato HTTP aditivo; sin tocar scoring
  ni FSRS. Tests: pytest **1880** (+56: nuevos `test_skill_segmentation_v338.py`,
  `test_planner_v338.py` y `test_situational_cue_v338.py`), vitest (65
  ficheros/**560**), `ruff`/`tsc` limpios y `check_release_consistency` **3.38.0**
  exit 0. Diferidos a V3.39: deudas de V3.30 + transferencia por contexto V3.23 +
  `cloze_coverage` de corpus + `example_for_many` + refactor de `wordDrill.tsx`.

- ✅ **V3.37.1 — Política de consolidación y regresión de la escalera de recall
  (2026-09-10)** (**Versión estable `3.37.1`**, app `3.37.0 → 3.37.1`). Patch
  quirúrgico que cierra los dos P1 pedagógicos de la auditoría de V3.37.0, sin
  migración de BD (el peldaño ya se declaraba en `activity_id` desde V3.37.0) y
  sin tocar scoring ni FSRS. **P1-01 (consolidación):** un peldaño
  (`translation`/`definition`/`cloze`) solo se da por SUPERADO con
  `RECALL_RUNG_PASS_MIN_SUCCESSES = 2` éxitos en
  `RECALL_RUNG_PASS_MIN_DAYS = 2` días naturales distintos; la progresión pasa a
  ser EVIDENCIA → CONSOLIDACIÓN → MÁS EXIGENCIA (el umbral se mide sobre los
  éxitos del propio peldaño, no sobre `independent_successes`, porque
  `cued`/`guided` nunca son `independent` y exigir automaticidad bloquearía la
  escalera). **P1-02 (regresión):** si el peldaño ideal acumula
  `RECALL_REGRESSION_FAILURES = 2` fallos SIN ningún éxito, la recomendación
  baja al peldaño inmediatamente inferior (más apoyo); nunca por debajo de
  `translation`, y fallar jamás hace subir (el peldaño inferior ya está
  consolidado, así que no hay oscilación). `resolve_recall_cue` sigue
  degradando SOLO hacia más apoyo. El resumen de evidencia añade
  `recall_rung_days`/`recall_rung_failures` (puros y con paridad pura↔SQL en
  `summarize_by_target`), consumiendo el `activity_id` `drill:recall:<peldaño>`
  que V3.37 ya escribía; la evidencia legacy `drill:recall` no alimenta ninguna
  política. Contrato aditivo: `LexicalEvidence` amplía esos dos histogramas.
  Tests: pytest **1824** (+11, nuevo `test_recall_policy_v3371.py` con la matriz
  éxito/fallo/regresión/legacy/paridad), vitest (65 ficheros/**560**), `ruff`/
  `tsc` limpios y `check_release_consistency` **3.37.1** exit 0. Diferidos a
  V3.38/V3.39: P1-03 (automaticidad por skill), `cloze_coverage` y el refactor de
  `wordDrill.tsx`.

- ✅ **V3.37 — Learning Evidence 3.0: cues graduados y automaticidad (2026-09-10)**
  (**Versión estable `3.37.0`**, app `3.36.0 → 3.37.0`). La escalera del peldaño
  `2 · Recall` deja de ser un *fallback* (traducción y, si no, definición) y pasa
  a ser una PROGRESIÓN declarada `translation (cued) < definition (cued) <
  cloze (guided)`: `services/recall.py` sirve el peldaño PEDIDO (o el de V3.34
  cuando no se pide ninguno), `next_recall_rung` decide el siguiente por los
  ÉXITOS ya registrados por peldaño (`drill:recall:<peldaño>` → histograma
  `recall_rungs`) y `resolve_recall_cue` separa la decisión pedagógica de la
  disponibilidad real degradando SIEMPRE hacia más apoyo (nunca al revés). Cada
  peldaño declara su `support_level` en el ledger, así que `independent_successes`
  (V3.36) por fin tiene de dónde salir, y la **automaticidad** (`is_automatic`)
  exige ≥2 éxitos sin apoyo en DÍAS NATURALES distintos: un acierto suelto no
  consolida (D5/E3). El cloze es determinista desde el banco de pronunciación
  (`blank_out`, con reglas de honestidad: si queda alguna aparición de la
  palabra, el cue se descarta) y **ningún peldaño llama a un LLM**. La cola de
  repaso expone `recommended_cue`/`automatic` sin spoilear la palabra (P1-03 de
  V3.35.1 intacto). Sin migración de BD (`support_level`/`activity_id` ya
  existían) y sin tocar scoring, FSRS ni la semántica del intervalo de evidencia.
  Contrato HTTP aditivo: `cue` opcional en GET/POST, `support_level` en
  `RecallPromptOut`, `independent_success_days`/`recall_rungs` en
  `LexicalEvidence`. Fuera de alcance: `situación` (exige contenido autorado) y
  el planner (V3.38). Tests: pytest **1813** (+22), vitest (65
  ficheros/**560**, +1), `ruff`/`tsc` limpios, build OK y
  `check_release_consistency` **3.37.0** exit 0.

- ✅ **V3.36 — Learning Evidence 2.0 (2026-09-10)** (**Versión estable `3.36.0`**,
  app `3.35.1 → 3.36.0`). El ledger longitudinal aprende el **CÓMO** de cada
  evento, con migración aditiva e idempotente y contrato HTTP aditivo:
  `support_level` (eje `copied → guided → cued → independent → spontaneous`, el
  MISMO de `academy_evidence`; hay test de paridad entre ambos), `difficulty`
  (CEFR 1-6, escala compartida con listening; `0.0` = no declarada),
  `context_id`/`activity_id` (contexto y actividad concreta), `response_time_ms`
  (latencia medida en cliente) y `error_type` (taxonomía determinista del
  intento). Captura end-to-end: recall → `cued`/`drill:recall` con clasificación
  del intento; retrieval → `guided`/`drill:word`|`drill:sentence` con la duración
  convertida a ms; producción por canal → apoyo real del canal (`chat` →
  `spontaneous`, `conversación guiada` → `guided`, `speaking`/`writing` →
  `independent`) y contexto `lexicon:<canal>`. `summarize_evidence` y
  `summarize_by_target` añaden `success_rate`, `independent_successes`,
  `support_levels`, `error_types` y `mean_response_time_ms` con paridad pura↔SQL
  fijada por test. **Decisión de alcance (`error_type` observacional):**
  clasificar NO toca scoring, ni evidencia, ni FSRS — una errata sigue siendo
  `correct=false`, pero el tutor ya distingue "no lo sabe" de "lo sabe y lo
  escribió mal" (el clasificador es conservador a propósito: `cat`/`cut` es otra
  palabra, no una errata). Fuera de alcance: cues graduados y planner (V3.37).
  Tests: pytest **1791** (+22), vitest (65 ficheros/**559**, +1), `ruff`/`tsc`
  limpios y `check_release_consistency` **3.36.0** exit 0.

- ✅ **V3.35.1 — Cierre de la auditoría V3.35.0 (2026-09-10)**
  (**Versión estable `3.35.1`**, app `3.35.0 → 3.35.1`). Patch quirúrgico de
  integridad del modelo longitudinal, sin cambios de esquema ni de arquitectura:
  **P1-01** `interval_since_last_evidence` deja de recibir el `interval_days` de
  la decisión de retención (ancla FSRS) y lo deriva SIEMPRE `record_evidence` de
  la evidencia anterior del ledger (`learning_evidence → learning_evidence`):
  dos conceptos distintos que ya no se mezclan; **P1-02** los `intervals` del
  resumen conservan el orden CRONOLÓGICO (se retira el `sort()` de
  `summarize_evidence` y el `summarize_by_target` ordena por
  `occurred_at, id`, no por valor del intervalo): la secuencia real del
  scheduler no se pierde; **P1-03** la cola «Repaso de hoy» solo muestra la
  palabra en `recognition` — en `recall`/`sentence` la oculta (el drill ya la
  ocultaba) para no spoilear la recuperación; **P2-02**
  `record_evidence_bulk` deduplica eventos idénticos y encadena el intervalo de
  eventos distintos del mismo target dentro del lote. Tests: pytest **1769**
  (+5), vitest (65 ficheros/**558**, +1), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.35.1** exit 0.

- ✅ **V3.35 — Longitudinal Learning Evidence 1.0 (2026-09-10)**
  (**Versión estable `3.35.0`**, app `3.34.0 → 3.35.0`). Cierra los **dos P1**
  de la auditoría de V3.34.0 y sienta el modelo de evidencia longitudinal, sin
  rehacer arquitectura y sin migración destructiva.
  **P1-1 (ancla):** la recuperación demorada deja de estar anclada a la primera
  exposición. `services/lexicon.py::delayed_retrieval_decision` (pura) encadena
  `evento_n → intervalo → evento_{n+1}`: el ancla es la última recuperación
  válida (`max(last_retrieval_at, last_recall_at)`) y el intervalo exigido lo
  calcula FSRS (`due_at` de la carta `lexicon`); sin carta, suelo
  `RETENTION_MIN_INTERVAL_DAYS`. `D0 → D+3` acredita; `D+3 → D+4` ya no si FSRS
  no ha vencido. **P1-2 (cola):** el repaso espaciado sale del speaking
  micro-drill — nuevo `GET /api/learning/review` con cartas FSRS `lexicon`
  vencidas ordenadas por urgencia y actividad óptima por hueco de competencia
  (`recommend_review_activity`: recognition/recall/sentence); se retira
  `due_words` de `drill_candidates`. **Evidencia:** tabla append-only
  `learning_evidence` (+ `event_role` en `learning_events`), repositorio
  `evidence.py` y servicio puro `services/evidence.py` (roles +
  `summarize_evidence`), contador aditivo `recall_attempts` y bloque `evidence`
  (`attempts`/`successes`/`days`/`intervals`) expuesto en el léxico y en la cola
  de repaso. UI: sección «Repaso de hoy» (`ReviewQueueSection`) + `initialStep`
  del `WordDrill`. Tests: pytest **1764** (+21), vitest (65 ficheros/**557**,
  +2 ficheros/+8 tests), `ruff`/`tsc` limpios y `check_release_consistency`
  **3.35.0** exit 0.

- ✅ **V3.34 — Dictionary → Learning Bridge, eslabón 3: Recall 2.0 (texto)
  (2026-09-10)** (**Versión estable `3.34.0`**, app `3.33.1 → 3.34.0`). El
  peldaño intermedio del drill deja de ser una repetición oral de la palabra y
  pasa a ser recuperación REAL por texto: el alumno ve el SIGNIFICADO (cue =
  traducción o definición sin spoiler) y teclea la palabra. A diferencia de
  Recognition (informativo), el acierto deja señal léxica PROPIA
  (`recall_successes`/`recall_days` + ledger `recalled`) sin acreditar
  producción, acredita la recuperación demorada existente si supera el
  intervalo (`retrieval_*`) y reprograma la carta FSRS `lexicon` con intervalos
  reales (Good/Easy/Again). La escalera queda en tres peldaños
  (`1 · Recognize` · `2 · Recall` · `3 · Sentence`) con el micrófono reservado a
  Sentence; si Recall no tiene cue, degrada a Sentence sin romperla. Endpoints
  `GET /api/vocabulary/drill/recall` y `POST …/recall-attempt`; migración
  idempotente y sin backfill de la capa de recall. Tests: pytest **1743** (+20),
  vitest (63 ficheros/**549**, +2), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.34.0** exit 0.

- ✅ **V3.33.1 — Hardening de Recognition (auditoría V3.33.0) (2026-09-10)**
  (**Versión estable `3.33.1`**, app `3.33.0 → 3.33.1`). Dos correcciones P1 de
  la auditoría externa, sin tocar la evidencia (sigue SOLO informativa) ni la
  seguridad del scoring (el GET nunca expone la correcta):
  **P1-01** la permutación deja de depender solo de la palabra —
  `recognition_options_for(word, entries, seed="")` mezcla `palabra + seed` y el
  `GET drill/recognition` entrega un nonce por intento (`question_id`) que el
  `POST` reenvía para reconstruir la misma permutación (premisa 21: sin estado
  servidor), de modo que reintentar `cat` rebaraja las opciones y no se puede
  memorizar la posición; **P2** `_stable_int` pasa a `SHA-256` (mejor dispersión;
  `listening_bottom_up` conserva el suyo por compatibilidad de ítems publicados);
  **P1-02** `WordDrill` arranca en `1 · Recognize` y degrada a Recall si
  `available=false` (`Practicar → Recognize → Recall → Sentence`). Contrato
  aditivo (`question_id` opcional en GET/POST). Tests: pytest **1723** (+1),
  vitest (63 ficheros/**547**, +1), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.33.1** exit 0.

- ✅ **V3.33 — Dictionary → Learning Bridge, eslabón 2: Recognition (MCQ
  definición ↔ palabra) (2026-09-09)** (**Versión estable `3.33.0`**, app
  `3.32.0 → 3.33.0`). La escalera compartida de drill (`wordDrill.tsx`, lookup
  Y hub) pasa a **`1 · Recognize` · `2 · Word` · `3 · Sentence`**: el primer
  peldaño pide el significado de la palabra entre opciones que sirve el
  backend. La pregunta es **pura y determinista por palabra** (premisa 21, sin
  estado servidor): `services/dictionary_mcq.py` la deriva de la caché global
  `dictionary_entries` (`list_entries()` nuevo en `repositories/dictionary.py`)
  — correcta = significado real de la diana en un modo consistente
  (`translation` si hay distractores, si no `definition`), distractores de
  otras entradas preferir mismo `pos`, deduplicados, barajado estable ocultando
  la correcta; sin distractores → `available=false` (degradación con aviso) — y
  el servidor la RECOMPUTA al puntuar (`GET drill/recognition` nunca expone la
  correcta; `POST drill/recognition-attempt` devuelve
  `{correct, correct_index, selected_index}`). **Evidencia SOLO informativa**
  (V3.13: el MC de reconocimiento no demuestra destrezas productivas): un
  evento `learning_events` `drill:<word>:recognition:ok|ko`; cero cambios en
  `vocabulary`/`vocabulary_events`, FSRS, mastery, usage ni candidatas (el
  acierto no dispara `onProduced`/`refreshEntry`). Sin etiquetas de origen ni
  estados servidor; sin cambios de esquema de BD. Tests: pytest **1722** (+11
  del nuevo `test_dictionary_recognition_v333.py`: determinismo y GET sin la
  correcta · acierto/fallo solo informativos con cero efectos · modo definition
  y dedupe · eventos recognition que no alteran `drill_ok_days`/candidates ·
  aislamiento A/B · sin entrada/sin distractores → 409/`available=false` ·
  normalización), ruff limpio, vitest (63 ficheros/546) y `tsc --noEmit`
  limpios y `check_release_consistency` **3.33.0** exit 0. Pendiente hacia
  **V3.34**: recall demorado con FSRS, transferencia por contexto de actividad
  V3.23 y los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat).

- ✅ **V3.32 — Dictionary → Learning Bridge, primer eslabón (2026-09-09)**
  (**Versión estable `3.32.0`**, app `3.31.1 → 3.32.0`). Convierte la
  consulta del diccionario (V3.30, D3: solo lectura) en puerta a la práctica
  real: la tarjeta del lookup gana **«Practicar esta palabra»**, que monta
  in-line la escalera de drill existente (Recall → Sentence) para la palabra
  consultada — también si `usage.tracked=false` (sin fila previa en
  `vocabulary`): el éxito crea producción pura igual que fuera del
  diccionario. Refactor de extracción neutro: `WordDrill`,
  `SpeakingDrillSection`, `DrillStep` e `isSentenceAttempt` pasan de
  `PersonalDictionary.tsx` al módulo compartido `wordDrill.tsx` (misma UI,
  mismo comportamiento). Sin backend nuevo (los endpoints de drill ya aceptan
  palabras arbitrarias) ni etiquetas de origen en la evidencia: un éxito llama
  `record_production_text(speaking, as_unit=True, activity="drill")` +
  `learning_events` `drill:<word>:ok`, con fila idéntica a practicar fuera del
  diccionario (verificado por aceptación A/B). D3 intacto: el lookup sigue sin
  escribir; solo la acción explícita «Practicar» y su resultado escriben en el
  Student Model. Tests: pytest **1711** (+3 del nuevo
  `test_dictionary_bridge_v332.py`: lookup read-only + práctica con evidencia
  idéntica entre usuarios A/B, paso frase equivalente con cierre D3 y
  aislamiento entre usuarios), ruff limpio, vitest y `tsc --noEmit` limpios y
  `check_release_consistency` **3.32.0** exit 0. Pendiente hacia **V3.33**:
  los diferidos de V3.30 — consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat — y los siguientes eslabones del puente (escaleras por
  destreza, recall demorado FSRS).

- ✅ **V3.31.1 — Hardening del diccionario tras la auditoría V3.31.0
  (2026-09-09)** (**Versión estable `3.31.1`**, app `3.31.0 → 3.31.1`; solo
  backend + docs, sin cambios de UI ni de esquema de BD). Cierra el **P1-01
  residual** y los **P2** de robustez del diccionario: **`pick_model` exige un
  modelo explícito INSTALADO** (`services/translate.py`: antes bastaba con que
  no estuviera en `UNUSABLE_MODELS` para llegar a Ollama; ahora consulta
  `installed_models()` y solo devuelve el explícito si está instalado y es
  utilizable, si no cae al fallback automático) · **negative cache del
  generador** (`domain/vocabulary.py`: un fallo marca la palabra en memoria
  durante `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS` 30 s — las consultas
  siguientes degradan a `definition_source="none"` sin reintentar en bucle — y
  la marca expira o se limpia al conseguir una generación) · **rate limit de
  generación nueva** por usuario (10/min) y global (40/min) con degradación
  normal (nunca 5xx); solo el dueño de un vuelo genera y lo cacheado no
  consume cupo · **tope servidor del dueño del vuelo**
  (`DICTIONARY_GENERATION_TIMEOUT_SECONDS` 90 s con `asyncio.wait_for`: un
  Ollama colgado degrada, libera el vuelo y marca negative cache) ·
  **semántica documentada del contenido canónico** (la caché es global y sin
  `model_id`; `model` solo influye en la generación de contenido nuevo).
  Tests: pytest **1708** (+11: +3 en `test_translate.py` de explícito no
  instalado y +8 en el nuevo `test_dictionary_hardening_v3311.py`),
  ruff limpio, vitest y `tsc --noEmit` limpios y `check_release_consistency`
  **3.31.1** exit 0. Pendiente hacia **V3.32**: Dictionary → Learning Bridge
  (`agentes/v332-dictionary-learning-bridge.md`), consumo de
  `word_breakdown_json` en agregados/práctica dirigida de las falladas y
  palabras tocables en transcripts/chat.

- ✅ **V3.31 — Cierre de la auditoría V3.30.1: robustez y contrato del
  diccionario (2026-09-09)** (**Versión estable `3.31.0`**, app
  `3.30.1 → 3.31.0`). Cierra los hallazgos residuales de la auditoría profunda
  de V3.30.1: **single-flight robusto a cancelación** (`domain/vocabulary.py`:
  el `CancelledError` del dueño del vuelo resuelve el Future con None antes de
  propagar — los waiters ya no cuelgan — y tope defensivo de 60 s en los
  waiters) · **invalidación del contenido de caché previo a V3.31**
  (`GENERATOR_VERSION` `1.0.0 → 1.1.0` en `services/dictionary_content.py`;
  `DICTIONARY_LEGACY_VERSION = "1.0.0"` en `repositories/db.py`, marca
  deliberadamente distinta de la actual que la migración aplica a las filas sin
  versión: el contenido del parser greedy de V3.30 regenera una vez) · **tests**
  de la migración de upgrade desde una BD V3.30.0 (aditiva + backfill +
  conservación + idempotencia), del path real del diccionario con modelo
  explícito no utilizable (`qwen3.5:9b` nunca llega a Ollama) y de la
  cancelación del líder · **contrato frontend**: tipo `DictionaryLookupRequest`,
  body tipado y test del `POST /api/vocabulary/dictionary?user_id=` (método,
  query, header y body) + timeout de cliente de 120 s. Tests: pytest **1697**
  (+4), ruff limpio, vitest y `tsc --noEmit` limpios y
  `check_release_consistency` **3.31.0** exit 0. Pendiente hacia **V3.32**:
  Dictionary → Learning Bridge (`agentes/v332-dictionary-learning-bridge.md`),
  consumo de `word_breakdown_json` en agregados/práctica dirigida de las
  falladas y palabras tocables en transcripts/chat.

- ✅ **V3.30.1 — Endurecimiento del diccionario de consulta (2026-09-09)**:
  patch de la auditoría V3.30.0 sobre v3.30.0 (**Versión estable `3.30.1`**,
  app `3.30.0 → 3.30.1`; solo backend + docs, sin cambios de UI). Cierra los
  tres P1: **P1-01** una sola generación LLM por palabra en concurrencia
  (`domain/vocabulary.py`: single-flight por palabra con Future — N consultas
  simultáneas → 1 llamada al modelo y 1 fila; el `INSERT OR IGNORE` protegía la
  fila pero no la generación; los waiters reciben el mismo resultado y un fallo
  no reintenta en cascada) · **P1-02** la política `UNUSABLE_MODELS` ya no se
  salta con un modelo explícito (`services/translate.py` `pick_model`: el
  explícito no utilizable cae al fallback automático, único punto de política
  para diccionario y traducción) · **P1-03** caché versionada
  (`dictionary_entries.generator_version` aditiva + migración idempotente con
  backfill `'1.0.0'` del contenido V3.30; `save_entry` upsert `ON CONFLICT DO
  UPDATE` con `updated_at` real; el dominio solo sirve caché con la
  `generator_version` actual y regenera/sobrescribe la obsoleta). P2: parser
  JSON con `raw_decode` que toma el PRIMER objeto válido (la regex greedy
  `{.*}` se tragaba `{…} texto {…}`). Tests: pytest **1693** (+9: concurrencia
  misma palabra y dos usuarios, fallo concurrente sin reintentos, regeneración
  por versión obsoleta, reuso de versión fresca, parser multi-objeto y llaves
  en prosa, `pick_model` con explícito no utilizable), ruff limpio y
  `check_release_consistency` **3.30.1** exit 0. Pendiente entonces: candidatos
  hacia V3.32 (Dictionary → Learning Bridge, palabras tocables en
  transcripts/chat).

- ✅ **V3.30 — Diccionario de consulta con marcas de uso y aprendizaje
  (2026-09-09)**: cerrado e implementado sobre v3.29.0 (**Versión estable `3.30.0`**, app `3.29.0 → 3.30.0`) con el dossier
  `docs/DISENO-V330-DICCIONARIO-CONSULTA.md` (decisiones **D1** LLM local a
  demanda con caché persistente en `dictionary_entries` · **D2** entrada = hub
  Vocabulario, vista «Consultar» · **D3** la consulta es solo lectura, sin
  evidencia ni impacto en mastery): **endpoint `POST /api/vocabulary/dictionary`**
  — marca de uso/aprendizaje por forma y por `lexical_unit` (estado, recall,
  contadores, matriz de competencia, agregado de unidad), frase de ejemplo
  determinista del banco (`services/example_sentences.py`) y definición/
  traducción generadas por el modelo local (`services/dictionary_content.py`:
  prompt JSON, parseo tolerante, `INSERT OR IGNORE` idempotente, degradación a
  `definition_source="none"` y fallback en memoria si la BD falla) ·
  **UI «Consultar»** (`DictionaryLookup.tsx`, conmutador con el diccionario
  personal en la vista alterna de `QuizRoutePage`; solo Vocabulario la declara),
  cliente `lookupDictionaryWord` + tipo `DictionaryEntry`, claves
  `dictionary.lookup.*` es/en. Tests: pytest **1684** (39 tests del diccionario
  en `test_dictionary_lookup.py` + `test_dictionary_content_v330.py`), ruff
  limpio, vitest **538** (63 archivos; `DictionaryLookup.test.tsx`), `tsc
  --noEmit` limpio y `check_release_consistency` **3.30.0** exit 0. Pendiente:
  candidatos V3.31 (palabras tocables en transcripts/chat, consumo de
  `word_breakdown_json` en agregados / práctica dirigida de las falladas).

- ✅ **V3.29 — Listening Engine 4.0, Fase 3 (núcleo, 2026-09-09)**: cerrado e
  implementado sobre v3.28.1 (**Versión estable `3.29.0`**, app `3.28.1 →
  3.29.0`) con el plan `v3.29_nucleo_fase_3…plan.md` (P1–P6): **motor de
  alineación por palabra offline** (`services/word_alignment_proxy.py` +
  `transcribe_words` con `word_timestamps=True`; sidecar `{wav}.words.json`
  etiquetado `asr_word_proxy` con cobertura mínima ~80 %, nunca verdad
  acústica; hooks en `generate_listening_audio.py`/`get_audio`/
  `import_audio.py` + script de backfill) · **`word_timings` servidos en el
  payload** (`word_timings_for`; asignación palabra→frase por tiempo contra
  `coarse_sentence_timings`; funciona con `repetition_policy="twice"` y ítems
  derivados `d-`; slow/fast se escalan en cliente por `speech_rate`) · **karaoke
  palabra a palabra** (`KaraokeTranscript`: revelado por frase, palabra activa,
  toque→seek; degrada a `CoarseTranscript` sin sidecar/cobertura baja) ·
  **controles de audio precisos** (duración vía `loadedmetadata`, bucle con
  scheduler `requestAnimationFrame` inyectable, seek slider + bucle A/B en la
  tarjeta) · **salto a la palabra fallada** (`failedWordTiming`, botones
  «repetir palabra fallada» normal/slow en dictado y cloze incorrecto) ·
  **evidencia `word_breakdown_json`** (columna aditiva nullable, migración
  idempotente; se persiste el breakdown del dictado fallido y el target del
  cloze/segmentation incorrecto; sin consumo en agregados — V3.30). El
  diccionario de consulta se reprioriza a V3.30 (siguiente candidato).

- ✅ **V3.28.1 — patch de la auditoría V3.28.0 (2026-09-09)**: cerrado e
  implementado sobre v3.28.0 (**Versión estable `3.28.1`**, app `3.28.0 →
  3.28.1`) con el plan `v3.28.1_patch_auditado_e76303f2.plan.md`: **P1-01**
  dictado parcial derivado servible — `derived_catalog` expone
  `DERIVED_PRODUCTION_POOL` y `pick_next_question` lo sirve en sesiones
  bottom-up (Caso A) con señal de `dictation` débil, tras agotar
  cloze/segmentación del nivel, nunca en puerta/certificación · **P1-02**
  scoring exacto por token del dictado escrito (`dictation_score` sin
  Soundex/phoneme/prosodia; `submit_production` lo aplica a todo
  `task_type=dictation`; fila fonética oculta en la UI) · **P1-03**
  Gonnago/reducciones por token y frontera (`contains_word_token` compartido
  en `_reductions_in`/`_is_eligible_token`/`_connected_speech_realized`;
  contenido de `l16` corregido, audio digest regenerado) · **P1-04/P2-01**
  AudioController integrado verificado (play/pausa/variantes operativas;
  seek/setRate fino/loop/replay/markSegment sin UI → V3.29 Fase 3) y `seek()`
  notifica `onCurrentTime` en pausa. Tests: pytest **1693** (backend 1619 +
  launcher 74), ruff limpio, vitest **506** (61 archivos), `tsc --noEmit`
  limpio y `check_release_consistency` **3.28.1** exit 0. Pendiente: dossier de
  auditoría del candidato v3.28.0 (letra P) y Fase 3 del engine en V3.29.
- ✅ **V3.28 — Listening Engine 4.0 Fase 2 (2026-09-09)**: cerrado e
  implementado sobre v3.27.0 (**Versión estable `3.28.0`**, app `3.27.0 →
  3.28.0`) con el plan
  `v3.28_listening_engine_fase_2_…plan.md` y los Bloques A-F de la Fase 2 de
  `docs/LISTENING_ENGINE_4.0.md` (§14, **Fase 2 cerrada**; el diccionario de
  consulta se reprioriza a V3.29, candidato). **Bloque A — micro-flujo
  unificado (P1-01)**: `next_question` sirve `flow`/`transcript_policy` también
  en rutas por nivel (`level=X`) y drill (`mode=failed`) vía el helper
  `_public_with_flow`; solo `mastered` conserva el modo compacto sin flow
  (contrato E2E-04) · **Bloque B — AudioController 4.0**:
  `features/listening/audioController.ts` (clase pura sobre
  `HTMLAudioElement`: `play/pause/seek/setRate` con `preservesPitch` y selección
  de la variante de URL más cercana, `loopSegment`, `replayCurrent`,
  `markSegment`, suscripción de `currentTime`/`ended`/`ratechange`) + hook
  `useAudioController` consumido por `ListeningPractice.tsx` (while1/while2/
  replay ya no crean `new Audio()` sueltos) · **Bloque C — Bottom-up derivado
  (P1-02/P1-03 parcial)**: `services/listening_bottom_up.py` deriva ítems
  deterministas del corpus existente (`cloze` auditivo MCQ con banco de
  distractores por nivel, `partial_dictation` de producción con scoring por
  tokens, `segmentation` de pares contraídos solo donde el corpus los realiza;
  regla «si no hay candidato fiable no se emite»); los derivados (`derived=True`)
  se sirven en práctica adaptativa/por nivel con perfil Caso A pero se filtran
  siempre del pool de ruta y la certificación · **Bloque D — transcript
  dinámico con sync grueso**: timings de frase heurísticos y proporcionales a
  `clean_transcript`/`duration` (etiquetados `coarse_heuristic`, nunca
  alineación acústica) en el payload; frontend con `CoarseTranscript`
  (hidden/partial/full + resaltado de la frase activa por `currentTime` del
  AudioController) · **Bloque E — Shadowing 2.0**: playback real de la grabación
  del alumno en el paso shadowing (`RecordingPlayButton` reutilizado) y señales
  auxiliares no bloqueantes (`shadowing_duration_ms`, `shadowing_speech_rate`)
  calculadas en cliente y persistidas con migración aditiva idempotente —sin
  peso de mastery ni gate— · **Bloque F — E2E adaptativos y negativos**:
  `test_listening_e2e_v328.py` recorre el ciclo completo con `TestClient`
  (E2E-01 Caso A recognition→bottom_up con flow de 5 etapas · E2E-02 Caso D
  connected speech que obliga al shadowing en B2 · E2E-03 Caso C top-down ·
  E2E-04 `mastered` compacto) + negativos del contrato pedagógico (derivado
  nunca certifica, `transcript_used` fiable, B2 sin reveal manual pre-Post).
  Tests: pytest **1683** (backend + launcher), ruff limpio, vitest **505** (61
  archivos), `tsc --noEmit` limpio y `check_release_consistency` **3.28.0**
  exit 0. Pendiente: dossier de auditoría del candidato v3.28.0 (letra P) y
  Fase 3 del engine (karaoke palabra a palabra) en V3.29.
- ✅ **V3.27 — Listening Engine 4.0 Fase 1 (2026-09-09)**: cerrado e
  implementado sobre v3.26.0 (**Versión estable `3.27.0`**, app `3.26.0 →
  3.27.0`) con el plan
  `docs/PLAN-V327-LISTENING-ENGINE-4.md` y la especificación
  `docs/LISTENING_ENGINE_4.0.md`. **Backend = fuente única de la política
  pedagógica** (`services/listening_flow.py`: `flow` pre/while1/while2/post/
  shadowing + `transcript_policy` servidos por pregunta; el frontend ejecuta
  una máquina de presentación en `features/listening/microFlow.ts`, sin reglas
  propias) · **Perfil auditivo visible en UI**: `services/auditory_profile.py`
  (casos A-D) + `AuditoryProfileCard` persistente y no bloqueante (sin datos →
  needsMore → intervención), y `next_question` prioriza la capa recomendada
  (`pick_next_question(layer=...)`) · **Evidencia ampliada**: 5 columnas nuevas
  en `listening_attempts` (`layer`/`speed_used`/`stage`/`transcript_used`/
  `segments_replayed`) con migración idempotente y persistencia en
  `submit_answer`/`submit_production`, contrato opcional y backward compatible
  en schemas/routers/tipos/API. Tests: pytest **1647**, vitest **472** (59
  archivos), ruff/`tsc` limpios, `check_release_consistency` **3.27.0** exit 0.
  Pendiente: auditoría externa del candidato v3.27.0 y Fase 2 del engine
  (reproductor rico/karaoke; calibración de umbrales del perfil).

- ✅ **V3.19 — Léxico por destreza + Speaking micro-drill (2026-09-07)**: cerrado
  e implementado sobre v3.18.0 (backend `3.18.0 → 3.19.0`) con las decisiones
  del gerente y el dossier de la auditoría profunda V3.18. **P0 — volcado por
  destreza**: `record_words` → `record_production(user, words, channel)`; la
  tabla `vocabulary` gana `chat_prod`/`speaking_prod`/`writing_prod`/
  `conversation_prod` (backfill idempotente `chat_prod = appearances`;
  invariante `sum(columnas) == appearances`) y las 7 superficies de producción
  vuelcan por un único helper compartido (CAP-01/REFAC-01) · **P1 — Speaking
  micro-drill**: señal en servidor `exposures > 0 AND speaking_prod == 0`
  (`GET /api/vocabulary/drill/candidates`) + `POST /api/vocabulary/drill/attempt`
  reutilizando el scorer de pronunciación (sin evidence/FSRS, D5/E3); chips de
  `PersonalDictionary` con acción real · **Fixes P1 del dossier**: R6-01
  retención impuesta en servidor (409), GATE-01 objetivo `locked` no evaluable
  (409), CLAIM-01 copy "nivel oral actual (examen)", SIGNAL-01 semántica oral +
  copy, ERR-01 404→503, LIST-01/02/03 tokens de foco servibles + corpus
  re-etiquetado + unicidad de script, CONV-01 reconstrucción por `mode` (el
  tecleo no es tiempo oral) · **Deuda externa**: ADMIN-01 fail-closed
  (`ADMIN_PIN=""` → 401) y BOOL-01 (`type(selected) is int`). Tests: pytest
  **1371**, vitest **417**, ruff/`tsc`/`vite build` limpios,
  `check_release_consistency` **3.19.0** exit 0 y curriculum `--strict --quality`
  exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta abierta).
- ✅ **Auditoría profunda V3.18 pre-V3.19 (2026-09-07, read-only)**: auditado
  código por código en 6 áreas (A1 academy/dominio · A2 evidence graph/FSRS/
  léxico · A3 speaking/pronunciación · A4 writing/conversación/cross-skill ·
  A5 assessment/contenido CEFR · A6 frontend claims) con dossier consolidado
  `docs/audit/I-AUDITORIA-PROFUNDA-V318.md` y lista P0/P1/P2 mapeada a
  decisiones V3.19. Sin P0 confirmado; P1 clave: **R6-01** retención R6 sin
  enforcement en servidor, **GATE-01** gating de objetivo no validado en
  endpoints, **CLAIM-01** UI "demostrado" oral sin gate, **SIGNAL-01**
  `recognized_not_produced` con semántica de teclado, **PROD-01/WR-UI-01**
  producción oral/escrita nunca llega al léxico (confirma el P0 del candidato
  V3.19). Deuda de la auditoría externa diferida a V3.19: **ADMIN-01**
  (`ADMIN_PIN=""` → fail-closed) y **BOOL-01** (bool-as-int en
  `unit_review.py`). Árbol sin cambios de código; `backend/config.py` sigue
  `3.18.0`; CONSTITUCIÓN sin cambios (R8/R9 siguen como propuesta abierta).
- ✅ **Preparado para auditoría TOTAL externa (2026-09-07, read-only):** árbol de
  trabajo limpio (v3.18.0 en HEAD, release-notes v3.10–v3.18 versionadas),
  todos los gates automáticos en verde (pytest 1345, ruff, vitest 414,
  `tsc`/`vite build`, consistencia 3.18.0, i18n exit 0, Beta V3.0, curriculum
  `--strict --quality`, content validation) y briefing autocontenido en
  `agentes/auditoria-total-externa.md` con el runbook y el mapa claim→código.
- ✅ Backend FastAPI + Pydantic (chat + voz + progreso + listening + CEFR + evaluación del tutor).
- ✅ Frontend Vite + React + TypeScript (chat, voz continua, dashboard de progreso, listening, calidad del tutor).
- ✅ Lanzador de escritorio (`launcher/`, GUI tkinter) con acceso directo e icono.
- ✅ Versión estable `3.26.0` — **Hoja de ruta completa: Ejes A + B + C** (los
  P2 de las auditorías externas V3.24/V3.25; dossier `docs/audit/O-AUDITORIA-TOTAL-V326.md`):
  **Eje A — retención longitudinal y gate MASTERED** (F-A1 initial/practice
  espaciado, F-A2 ancla `delayed` a su origen formal con `event_age` vs
  `retention_interval`, F-A3 ≥2 reassessment points estables por destreza con
  fix del escritor `kind=level`) · **Eje B — emisor real de `novel`** (F-B1:
  primera misión B2+ jamás practicada; requisito `novel_required=0` intacto) +
  **historia léxica por superficie** (F-B2: ledger `vocabulary_events`
  append-only, sin backfill) · **Eje C — Listening real y calibración** (F-C1
  taxonomía recognition/comprehension/inference con reporte `by_layer`,
  F-C2 escalera CEFR monótona unificada de extremos matriz 2.1.0, F-C3
  `blocked_by` con motivo traducido en la UI, F-C4 marcas de legacy sin
  `context_id` por destreza/global/ladder). Verificación íntegra: pytest
  backend **1538 passed** + ruff, vitest **450 passed** (57 archivos) + tsc;
  `check_release_consistency` 3.26.0 exit 0.
- ✅ Versión estable `3.25.1` — **Cierre de P1 de la auditoría externa V3.25**
  (patch correctivo sobre v3.25.0; dossier `docs/audit/N-AUDITORIA-TOTAL-V3251.md`,
  evidencia de cierre: los 6 tests negativos del gate): **certification_gate
  real** — baseline formal (`task_type="exam"`) + eventos `delayed` por
  `context_id`, con ventana ≥ `RETENTION_MIN_DAYS` y ratio ≥
  `RETENTION_STABLE_RATIO` verificados desde las propias filas (sin examen no
  se certifica; `retention_report` informa `interval_days`/`initial_score`/
  `rate`/`baseline_date`) · **agregación real por `lexical_unit`** —
  `units_from_rows`/`summary_units` en `services/lexicon.py` (cada superficie
  conserva su estado; aditivo en schemas/domain/frontend `types`) ·
  **`support_level` pondera la evidencia de dominio** —
  `SUPPORT_LEVEL_WEIGHTS` (copied .5 / guided .7 / cued .9 / independent 1.0 /
  spontaneous 1.0) en `generalized_mastery_score`, con legacy neutral 1.0.
  Tests: `release-notes-v3.25.1.md` y CHANGELOG `[3.25.1]`.
- ✅ Versión estable `3.25.0` — **Calibración del Student Model: contexto en la
  evidencia, transfer por experiencias y semántica demostrado/estimado** (cierra
  el plan V3.25 del dossier L — auditoría TOTAL verificada de V3.24.0 — que
  absorbe los pendientes F-K3…F-K7): **F1 — modelo de eventos con contexto** —
  `academy_evidence` gana `context_id`/`activity_id`/`task_type`/`support_level`
  (migración idempotente + índice `idx_evidence_context`) y
  `evidence_from_items`/`record_evidence` enriquecen cada evento sin romper
  agregados · **F2 — `support_level` canónico** — enumerados
  `copied/guided/cued/independent/spontaneous` y persistidos por emisor
  (formative → guided/cued; objective assessment → cued; speaking
  assessment/misión y chat libre → independent; read-aloud → guided); el perfil
  expone `support_levels`/`independent_count` por destreza · **F3 — transfer por
  contextos/tareas distintos** — `mastery_evidence_gate`, `adaptive.readiness`,
  el unit gate de `course` y evidence_graph consumen contextos efectivos
  (`effective_evidence_context_count`, con fallback legacy a nº de filas); se
  desambigua `transfer`/`retention` académica vs léxica (F-K5) · **F4 —
  retention longitudinal** — `certification_gate` verifica `created_at` de las
  filas `delayed` (robustez) y emite `retention_report` con intervalos
  D+1/D+3/D+7/D+21 · **F5 — semántica UI demostrado vs estimado** — el Student
  Model separa `demonstrated_level`/`estimated_level`/`level_progress` y el
  header de Progreso los muestra sin ambigüedad (F-K4 parcial: `estimated_band`
  ya existe por destreza) · **F6 — renombrado canónico + unidad léxica** —
  migración idempotente `occurrences→appearances→production_count` y
  `exposures→exposure_count` en toda la pila (DB/schemas/servicios/frontend) y
  columna `lexical_unit` (lema/superficie normalizada) para no tratar
  `go/going/went` como conocimientos independientes (F-K7/P2-01/P2-02); decisión
  `novel` confirmada: reservado hasta emisor real · **F7 — doble vía speaking
  (F-K3)** — `cefr_target` persistido en columna de
  `speaking_mission_sessions` (migración + backfill desde `mission_json`); la
  vía assessment y la misión declaran evidencia `independent`. Tests:
  `release-notes-v3.25.0.md`.
- ✅ Versión estable `3.24.0` — **Calibración de salida del Student Model**
  (cierra el plan V3.24 del dossier K — auditoría profunda Eje 1 sobre v3.23.0 —
  con los dos P1 por decisión del gerente y sus tests e2e previos: **F-K1 —
  MASTERED relajado a lo emisible** — el kind `novel` no tiene emisor real y
  `mastery_evidence_gate` lo exigía (bloqueo permanente de la escalera
  Assessment 2.0): `MASTERY_EVIDENCE_REQUIREMENTS` pasa a `initial 1 +
  practice 2 + transfer 2 + delayed 1` y `novel_required = 0` en las 12 celdas
  macro de `cefr_matrix.json`; `novel` queda **reservado** hasta que exista un
  emisor real; frontera documentada en `ASSESSMENT_2.md` y CONSTITUCIÓN §2.1/§6 ·
  **F-K2 — nivel estimado anclado sin rebase** — `estimated_level` recibe
  `current_level` + `completed_levels` y ancla `numeric` (0.5–6.0) al nivel
  completado más alto + progreso del tramo actual (fin del escenario G4:
  dominar A1 ya no estima B2, aprobar el examen A1 ya no devuelve a Pre-A1);
  `build_student_model` deriva ambos de las matrículas `completed` · **F-K8 —
  tests e2e del salto A1→A2** en `test_academy.py` (dominio A1 → estimado A1,
  nunca ≥ B2; examen A1 → matrícula A2, estimado A1 con numeric 1.0) ·
  **tests**: backend pytest **1457** + ruff limpio; Eje 1 G1 **311** + G2
  **329** (640); frontend sin cambios; `check_release_consistency` 3.24.0
  exit 0). Base: `3.23.0`
- ✅ Versión estable `3.23.0` — **Student Model Calibration (parte 2): Retention
  real y Transfer por contexto** (implementa el plan V3.23 del dossier de la
  auditoría externa V3.22.0: **P1-02 — retention por recuperación DEMORADA** —
  migración idempotente en `vocabulary`: `retrieval_successes`/
  `retrieval_days`/`last_retrieval_at` (sin backfill: ancla retrospectiva
  injusta), `record_retrievals` cuenta éxitos ≥ `RETENTION_MIN_INTERVAL_DAYS`
  tras el ancla `min(first_exposed_at, first_seen)`, hook solo en micro-drill
  (`submit_drill_attempt` si `produced`, `submit_sentence_attempt` si
  `passed`), y la matriz exige `retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS`
  con `spaced_exposure`/`spaced_production` como señales independientes ·
  **P1-04 — transfer por contexto de actividad** — migración `context_tags`
  (CSV `channel:activity` único y ordenado), `record_production(..., activity)`
  con merge canónico, `activity` propagada por todas las superficies
  (`free_chat`/`speaking_assessment`/`speaking_mission`/`speaking_controlled`/
  `writing_controlled`/`speaking_task`/`writing_task`/`read_aloud`/`drill`/
  `speaking_route`/`guided_conversation`), y `production_contexts(row)` con
  fallback `channel:other` para legacy; `transfer`/`transfer_contexts` por
  contextos · **quick fixes base (auditoría externa V3.22)**: P1-01 `item_recall`
  con `_last_activity_at` (max de `last_seen`/`last_exposed_at`); P1-03
  `item_mastery` con pesos de reconocimiento (0.4 volumen / 0.6
  `exposure_days`) y `no_speech` antes que `low_confidence` en el ASR ·
  **tests**: backend pytest **1455** + ruff limpio; frontend vitest **450** (57
  archivos) + `tsc`/`vite build` OK; curriculum `--strict --quality` y content
  validation OK; `check_release_consistency` 3.23.0 exit 0; CONSTITUCIÓN sin
  cambios). Base: `3.22.0`
- ✅ Versión estable `3.22.0` — **ASR Calibration + Student Model (léxico)**
  (implementa el plan V3.22 del dossier de la auditoría externa V3.21.0:
  **ASR-01 — calibración ASR por segmentos** — `aggregate_asr_segments`
  materializa los `Segment` de faster-whisper y agrega `mean_logprob`/
  `min_logprob`/`max_no_speech_prob`/`no_speech_ratio`/`speech_ratio`/
  `compression_ratio`/`segment_count` (V3.21 los leía de `TranscriptionInfo`,
  que no los expone: `no_speech` y `low_confidence` eran inalcanzables);
  `classify_asr_status(*, text, metrics)` con política explícita
  (`MIN_SPEECH_ATTEMPT_SECONDS` 0.5 s; texto vacío con 0 segmentos y audio
  corto → `unintelligible`, con audio ≥ 0.5 s → `no_speech`; texto alucinado
  sobre no-habla — `no_speech_ratio` alto — → `no_speech`; `mean_logprob` bajo
  → `low_confidence`) y telemetría emitida sin clasificar (frontera
  `LANGUAGE_MISMATCH` documentada) · **Student Model léxico (P1-04/05)** —
  migración idempotente `exposure_days`/`first_exposed_at` en `vocabulary`
  (backfill 1 día + `first_exposed_at = last_exposed_at`), `record_exposures`
  cuenta días distintos de exposición y fija el alta, y la matriz
  `item_competence_matrix` **separa Retention de Transfer**: `transfer` =
  producción en ≥ 2 canales (`transfer_contexts`), `retention` = espaciado
  receptivo (`_spaced_exposure`) o productivo (`_spaced_production`);
  `production_gap` (reconocida-nunca-producida, antes `gap`) y `transfer_gap`
  (producida-sin-transferir) independientes en la matriz y el summary; la UI
  del diccionario pasa a 6 contadores · **tests**: backend pytest **1440** +
  integración ASR opt-in (`test_stt_asr_integration.py`, Whisper real) + ruff
  limpio; frontend vitest **450** (57 archivos) + `tsc`/`vite build` OK;
  `check_release_consistency` 3.22.0 exit 0; CONSTITUCIÓN sin cambios). Base:
  `3.21.0`
- ✅ Versión estable `3.21.0` — **Speaking & Evidence Calibration**
  (cierra el plan V3.21 del dossier de la auditoría externa V3.20.0, calibrando
  la verdad del micro-drill y el feedback ASR honesto: **F1 P0 — verdad del
  drill** — la producción se decide por **alineación secuencial**
  (`unit_produced` en `services/phonetics.py`, misma normalización
  `tokenize`, nunca `.split()`): palabra alineada `equal`, frase multi-palabra
  contigua — "get it up" NO es "get up", "my living room is nice" sí produce
  "living room" · las unidades multi-palabra se acreditan a SÍ MISMAS
  (`record_production_text(as_unit=True)`, invariante
  `sum(channel_prod)==appearances` por fila) · **F2 P1 — feedback honesto +
  ASR** — `transcribe_with_timing` captura `no_speech_prob`/`avg_logprob`/
  `language_probability` y clasifica `asr_status ∈ {ok, no_speech,
  unintelligible, low_confidence}`; gating de NO-penalización en drill/
  read-aloud/speaking/pronunciación (`asr_status != ok` → ni KO ni fallo,
  evento `unclear`); chips re-etiquetados ("Reconocida correctamente" no "Bien
  dicha"), mensajes por `asr_status` en las escenas y estado `unclear` en
  manos-libres · **F3 quick wins** — `DEFAULT_MODEL` fuente única
  (`GET /api/models` → `default_model` + `utils/models.ts`
  `resolveDefaultChatModel`, sustituye las 3 constantes), comentario
  `ADMIN_PIN` fail-closed, hook `useRecordingSession` (cronómetro + auto-stop
  120 s) y red de seguridad backend de duración (400), aviso de audio no
  reconocido · **F4 — semántica de superficie Speaking** — títulos por modo
  (Micro-práctica/Acento/Diálogo) y pies de stats con la competencia real
  (Pronunciación/Conversación/Producción oral) · **F5 — matriz de competencia
  léxica** — `item_competence_matrix` pura
  (Recognition/Production/Transfer/Retention/gap por ítem, sin migrar
  columnas), expuesta en el léxico y el diccionario, y **Transfer Gap para
  FSRS** (razón `transfer-gap` en el "why" de cartas lexicon de objetivos con
  producción, `recognition-only` si no) · **F6 — drill escalera MVP** — paso
  **Sentence determinista sin LLM** (`sentence_context_for`: frase del banco de
  read-aloud del nivel que contiene la unidad o plantilla neutra; endpoints
  `GET/POST /api/vocabulary/drill/sentence(-context|-attempt)`, `passed =
  produced AND phrase_ok`) con la UI Recall → Sentence en la misma tarjeta de
  `WordDrill`, y **graduación espaciada** (V20-06: una producción del día no
  elimina de la lista "pendiente"; se sale con 2 días de éxito de drill —
  eventos `drill:<word>[:sentence]:ok` — u otra señal de speaking espaciada;
  sin declarar dominio D5/E3) · F6.3 (Contexto/Transfer libre) queda APLAZADO
  a la auditoría pedagógica de Speaking/Listening · **tests**: backend pytest
  **1424** + ruff limpio; frontend vitest **450** (57 archivos) + `tsc` limpio;
  `check_release_consistency` 3.21.0 exit 0; CONSTITUCIÓN sin cambios). Base:
  `3.20.0`
- ✅ Versión estable `3.20.0` — **Speaking único + feedback oral**
  (cierra el candidato V3.20, definido 2026-09-07 frontend-only, F1 de
  `docs/DISENO-SPEAKING-UNICO.md` + feedback oral: **F1** — consolidación de la
  práctica oral en una sola superficie **Speaking** — hub de APRENDER a 4
  tarjetas, Pronunciation/Conversation reutilizadas como modos internos
  Micro-conversación / Acento / Diálogo guiado (`SpeakingRoutesPractice` +
  `modeTabs` en `QuizRoutePage`, configs exportadas), `/aprender/pronunciacion`
  y `/aprender/conversar` degradan al hub, NextBest/Recorridos navegan a
  Speaking · texto «Cada nivel es una ruta…» plegado tras el botón (i) «Cómo
  funcionan las rutas» · **se reproduce la grabación real del alumno**
  (`RecordingPlayButton`, blob en memoria: el backend solo transcribe) en
  Micro-conversación y Acento · **F3 frontend** — Diálogo guiado con turnos
  hablados reales (`ConversationVoiceButton` + `mode="voice"` + telemetría con
  duración real) · **chips palabra a palabra en Acento**
  (`utils/pronunciationAlignment.ts`, puerto TS del `SequenceMatcher` con
  paridad con el backend) · **F4** — modos por URL + redirección de URLs
  heredadas · **fix** botón traducir del interlocutor y de la respuesta modelo
  en Micro-conversación (pintaba el inglés crudo en vez de `display`) ·
  **tests**: vitest 434 + `tsc`/`vite build` OK; backend sin cambios (impl
  V3.19 sin release previo incluida en este commit) · `check_release_consistency`
  3.20.0 exit 0; CONSTITUCIÓN sin cambios). Base: `3.19.0`
- ✅ Versión estable `3.19.0` — **Léxico por destreza + Speaking micro-drill**
  (cierra el candidato V3.19, definido 2026-09-07: **P0** — la producción del
  alumno se vuelca al léxico etiquetada por destreza — `record_production(user,
  words, channel)` + 4 columnas contadoras en `vocabulary` con backfill
  `chat_prod = appearances` y punto único de captura en `domain/academy.py`
  (CAP-01/REFAC-01); speaking/pronunciación/writing/conversación guiada ya no
  descartan `heard`/`text` · **P1** — speaking micro-drill de 1 nivel honesto:
  candidatos reales `exposures > 0 AND speaking_prod == 0` servidos por
  endpoint determinista y practicados sobre el scorer de pronunciación; sin
  evidence/FSRS (D5/E3); chips del diccionario con acción · **Fixes P1 del
  dossier**: R6-01 retención (409), GATE-01 objetivo locked (409), CLAIM-01
  copy oral "examen estimado", SIGNAL-01, ERR-01 404→503, LIST-01/02/03,
  CONV-01 reconstrucción por `mode` · **Deuda externa**: ADMIN-01 fail-closed y
  BOOL-01 · **tests**: pytest 1371 + ruff limpio, vitest 417 + `tsc`/`vite
  build` OK, `check_release_consistency` 3.19.0 exit 0, curriculum
  `--strict --quality` exit 0; CONSTITUCIÓN sin cambios). Base: `3.18.0`
- ✅ Versión estable `3.18.0` — **Knowledge Graph remainder + deuda del grafo (P3)**
  (cierra el candidato P3, auditado ABIERTO en 2026-09-06. **P3-I2**: ancla de
  unidad congelada al completar — tabla `unit_review_anchors` de escritura única
  (`INSERT OR IGNORE`, backfill lazy) + `build_unit_review_plan(anchor=)`; los
  refuerzos/decay posteriores ya no desplazan las ventanas 7/30/90 · **P3-O1**:
  cascade de ventanas — una ventana sin intento propio se cierra con un intento
  superado de la unidad posterior a su `due_at`; el intento propio manda siempre
  · **P3-M4**: cartas FSRS `objective` fuera del panel autograduable (single
  writer con el micro-review: siembra solo en ventana `due_now`/`failed` o con
  `reps > 0`; `get_fsrs_due` y el `due_count` de resumen las excluyen y
  `/fsrs/review` las rechaza con 400) · **P3-O3**: plan de repaso agregado por
  niveles — `/unit-plan` devuelve `{levels, due_count}` (nivel actual +
  anteriores matriculados), el micro-review acepta `level_id` y valida la unidad
  en el nivel donde vive, `UnitReviewPanel` agrupa por nivel · **P3-H5**: etiquetas
  humanas de las dimensiones del grafo — `GRAPH_DIMENSION_LABELS` + `dimensionLabel`
  en chip de factor limitante/`NextBestCard`/`ObjectiveNodeCard`/`EvidenceGraphPanel`
  (Transfer/Discourse/Interaction, nunca el id en crudo) · **P3-H6**: coste lazy
  de `/session` y `/next-best` — nodos solo para los grupos de remediación que
  pueden convertirse en paso (≤ `SESSION_CAPS.weakness`) y `list_evidence` una
  sola vez y solo si hay nodos que construir (payloads idénticos, sin cambio de
  API) · **P3-auditoría v3.17**: `ObjectiveNodeCard` distingue error real (copia +
  reintento) de 404/sin-datos, `float()` defensivo en `rank_weakness_objectives`,
  spec Playwright `homeGraphChip` nueva con mock determinista (chip "Transfer")
  · **tests**: pytest 1345 + ruff limpio, vitest 414 + build OK, Playwright de la
  región Home/grafo en desktop OK). Base: `3.17.0`
- ✅ Versión estable `3.17.0` — **Knowledge Graph + Daily Adaptive Plan**
  (cierra el candidato P2: el plan diario ahora deriva del Evidence Graph.
  **P0-grafo→plan (D1b)**: `rank_weakness_objectives` + `enrich_item` en
  `services/evidence_graph.py` (puros); `_session_steps` reordena los candidatos
  de cada destreza débil por su nodo y enriquece los pasos con
  `can_do`/`limiting_factor`/`graph_mastery`/`because[]` (una única lectura de
  evidencia; `/session` y `/next-best` nunca divergen) · **P0-vista (D2)**:
  `ObjectiveNodeCard` consume `getEvidenceGraphNode` en el curso (hitos
  expansibles) y en el perfil (Habilidades); sin endpoint nuevo · **P0-muerte
  de `/today` (D3)**: endpoint, `get_today_plan`, schemas, `adaptive.today_plan`
  + `TODAY_MIX`, cliente y tipos frontend eliminados; la Home consume solo
  `/session`; tests migrados con rationale · **P0-deuda v3.16 (D4b)**: M2/M3/O2
  ✅ con test y M1 ✅ en el cierre (devDeps DOM `jsdom` + `@testing-library/react`,
  vitest a `*.test.tsx` y 6 vitest de componente de `UnitReviewPanel`/`TodayPlan`)
  · **P0-UI (D6)**: micro-líneas del can-do/factor limitante en las filas de la
  sesión · **P0-fallback (D7)**: sin nodo la práctica nunca se bloquea
  · **tests**: `test_graph_plan.py` + `test_session_graph.py` nuevos y suites
  migradas; backend pytest 1333 + ruff, frontend vitest 398 + build OK).
  Base: `3.16.0`
- ✅ Versión estable `3.16.0` — **Review/SRS por unidad: micro-review + ventanas de retención fijas 7/30/90 días sobre la base FSRS**
  (cierra el candidato P1 "Review/SRS por unidad" auditado como abierto 2026-09-05:
  el motor FSRS ya soportaba `target_type="objective"` pero no se sembraba; no
  había plan de repaso por unidad ni ventanas fijas. **P0-motor**: nuevo
  `backend/services/unit_review.py` puro y determinista — ventanas `(7, 30, 90)`
  desde el ancla de la unidad (completada = todos sus objetivos `mastered`),
  estados `upcoming/due_now/passed/failed`, micro-review con muestreo
  balanceado de los checks MC **oficiales** del currículo (cero contenido
  artificial; reintento prioriza fallidos) y puntuación en servidor (premisa 21)
  · **P1-siembra**: `sync_fsrs_cards` siembra/refresca cartas `objective` solo
  para objetivos de unidades completadas del nivel actual, sin pisar `reps > 0`
  y sin tocar `TARGET_TYPES`; `why_for_objective` en `fsrs.py` · **P1-datos**:
  tabla idempotente `unit_review_attempts` (`per_objective` + `failed_items`) y
  repos; el micro-review NO crea evidencia de mastery ni declara dominio (D5,
  mecanismos separados E3) · **P2-API**: `GET /api/academy/review/unit-plan` y
  `GET/POST /api/academy/review/unit/{unit_id}/micro-review` con gating de
  ventanas (400/404) · **P2-UI**: `UnitReviewPanel` en INICIO con chips de
  ventana 7/30/90, micro-review por tarjetas y nota honesta "no cuenta como
  demostración de dominio"; lógica pura en `unitReviewLogic.ts` e i18n es/en con
  parity · **tests**: `test_unit_review.py` + `test_unit_review_endpoints.py`
  (siembra, idempotencia, sin `correct_index`, aislamiento entre usuarios),
  vitest de lógica y API; backend pytest 1318 + ruff, frontend vitest 392 +
  build OK). Base: `3.15.0`
- ✅ Versión estable `3.15.0` — **Profundidad avanzada C1/C2: densidad, taxonomía avanzada y banco grammar C2 normalizado**
  (cierra el candidato P0 "C1/C2 depth" auditado como abierto 2026-09-05:
  **P0-contenido**: C1 y C2 pasan de 14 a 20 objetivos con evidencia completa
  (checks MC + activities con fases; +30 activities y +18/+19 checks por nivel),
  en `c1-m02-u01`/`c1-m03-u01` y `c2-m02-u01` (+2 en `l01` "Register shifts" y
  lección nueva `l03` con elipsis/gramática formal), dejando intactos los
  módulos Final · **P0-taxonomía**: `SUBSKILLS` gana la capa avanzada
  (`register`/`pragmatics`/`discourse`/`nuance`/`argumentation`) en speaking/
  listening/writing/grammar/reading/vocabulary y los objetivos C1/C2 se
  re-etiquetan solo donde el contenido lo justifica (C1 3→16 y C2 7→20 con
  subskill avanzada) · **P0-banco**: grammar C2 normalizado a 15 ítems (11 MC +
  4 CP en 3 temas) — deja de ser el único banco corto real y su práctica deja
  de leer `low`; la regla R7 se verifica con banco corto sintético en los tests
  · **tests**: snapshot depth V2.6 reformulado (`depth(C1) 93.1`, `depth(C2)
  92.5` ≥ 90), R7 re-apuntada, conteos C2 actualizados, textos "C2 = 4"
  retirados; `validate_level` vacío en 6 niveles y CLI `--strict --quality`
  exit 0 con unit coverage y loop 100 %). Base: `3.14.0`
- ✅ Versión estable `3.14.0` — **Registro cross-skill de B1 a los 6 niveles (A1–C2): producción controlada en todos los niveles y panel sin marca de prototipo**
  (escala el registro cross-skill por estructura de V3.13 P1.2 del prototipo B1 a
  `a1..c2`: **P0-contenido**: ítems `controlled_production` nuevos en A1 (6:
  `to be`, present simple 3.ª persona, adverbios de frecuencia, `have/has got`,
  preposiciones de lugar, past simple) y C2 (4: inversión enfática, cleft,
  mixed conditional, pasiva formal); el banco Grammar crece (A1 38→44, C2 4→8)
  y C2 conserva su etiqueta honesta de banco corto (≤12) · **P0-motor**:
  `cross_skill.py` generalizado (`CROSS_SKILL_LEVELS = a1..c2`), bindings
  normativos CP → estructura en los seis niveles (`PRODUCTION_BINDINGS_BY_LEVEL`,
  verificado por test: sin CP huérfanos), producción por objetivo agrupando CP ·
  **P1-API**: sin `proto` en esquema/tipos, `/api/cross-skill` valida `a1..c2`
  (400 `cross_skill.level_unknown`) · **P2-UI**: `CrossSkillMatrix` en el panel
  Grammar de cualquier nivel, copia generalizada sin "prototipo B1" y clave
  `crossSkill.protoNote` eliminada de i18n · tests backend por nivel +
  invariantes de contenido A1/C2 + Playwright `grammarRoutesReview` con mock
  determinista). Base: `3.13.0`
- ✅ Versión estable `3.13.0` — **Calibración de evidencia pedagógica: del "¿está implementada la actividad?" al "¿la evidencia demuestra competencia?"**
  (iteración que recalibra el modelo pedagógico en un único documento normativo
  (`docs/CONSTITUCION-PEDAGOGICA.md`) con reglas inmutables R1–R7 y §6.4
  evidence depth. **P0**: `services/evidence_depth.py` clasifica la evidencia en
  LOW/MEDIUM/HIGH contra `cefr_matrix.json` y se expone en `/api/profile`;
  claims honestos —bancos cortos ≤12 checks (Grammar B2/C2) muestran "practice
  coverage · evidence depth LOW" con techo `functional`—; suelo de "demostrado"
  con mínimo de muestras + retención ≥7d + producción en destrezas productivas
  (vocabulary techado en `functional`); `current_level` como sugerencia de
  material con fallback por `review_due`; suite de invariantes pedagógicas.
  **P1**: Grammar en 3 niveles con ítems `controlled_production` (typed answers
  deterministas, A2–C1); cross-skill evidence B1 (matriz por estructura +
  endpoint + panel); golden pedagogical dataset. **P2**: LearnRoutePage
  compartido (QuizRoutePage + routeSession: Grammar/Vocabulary/Pronunciation/
  Conversation/Speaking migradas, ~1.600 líneas menos) y parity i18n
  automática). Base: `3.12.0`
- ✅ Versión estable `3.12.0` — **Grammar por rutas CEFR: página única de checks MC del currículo**
  (APRENDER → Grammar deja el chat del tutor (que sigue en `/chat`) y pasa a una
  página única como el resto: arriba el escenario de práctica —un check MC de
  grammar del currículo del nivel recomendado, con feedback inmediato y la
  respuesta correcta revelada al fallar— y debajo el mapa de rutas A1–C2 con
  anillos y el panel del nivel (Practicar el nivel / Repetir fallidas / Repasar
  aprendidas + «Demostrar el nivel» → exámenes y escalera de evaluaciones del
  curso). El banco son los checks MC de la destreza grammar del currículo
  oficial (97 checks; sin contenido nuevo) sobre el motor compartido
  `backend/services/quiz_routes.py`; los bancos cortos (B2 = 8 y C2 = 4)
  adaptan la puerta automáticamente. Intento determinista persistido en
  `grammar_route_attempts`; endpoints `/api/grammar/routes/*`. La ruta es un
  hito de práctica —`functional` como techo, nunca certifica—; demostrar el
  nivel exige los instrumentos formales del curso. Con Grammar, las 6
  actividades de APRENDER comparten la misma página única de rutas CEFR).
  Base: `3.11.0`
- ✅ Versión estable `3.11.0` — **Vocabulary por rutas CEFR: página única de checks MC del currículo + diccionario a mano**
  (APRENDER → Vocabulary deja de ser solo el diccionario personal y pasa a una
  página única como el resto: arriba el escenario de práctica —un check MC de
  vocabulary del currículo del nivel recomendado, con feedback inmediato y la
  respuesta correcta revelada al fallar— y debajo el mapa de rutas A1–C2 con
  anillos y el panel del nivel (Practicar el nivel / Repetir fallidas / Repasar
  aprendidas + «Demostrar el nivel» → exámenes y escalera de evaluaciones del
  curso). El banco son los checks MC de la destreza vocabulary del currículo
  oficial (sin contenido nuevo) sobre el motor compartido de rutas quiz
  `backend/services/quiz_routes.py` (lo reutilizará Grammar, v3.12); el intento
  es determinista y se persiste en `vocabulary_route_attempts`. La ruta es un
  hito de práctica —`functional` como techo, nunca certifica—; demostrar el
  nivel exige los instrumentos formales del curso. El diccionario personal se
  integra en la página). Base: `3.10.0`
- ✅ Versión estable `3.10.0` — **Conversation por rutas CEFR: página única de mini-diálogos guiados multi-turno**
  (APRENDER → Conversation deja el chat libre (ahora en su propia raíz `/chat`,
  accesible desde la propia página) y pasa a una página única como Speaking:
  el escenario de práctica —un mini-diálogo guiado multi-turno con el tutor:
  situación, roles y metas comunicativas, y se conversa por texto o micrófono
  hasta cumplirlas— vive arriba y, debajo, el mapa de rutas A1–C2 con anillos y
  sus modos (Practicar el nivel / Repetir fallidos / Repasar aprendidos). Banco
  oficial nuevo y auditable `curriculum/conversation_corpus.json` (v1.0.0: 11
  mini-diálogos por nivel) y el intento se evalúa sobre el transcripto completo
  con el pipeline LLM de evidencia (task_type conversation) fusionado con la
  señal objetiva de interacción. La ruta es un hito de práctica —`functional`
  como techo, nunca certifica—; demostrar el nivel sigue siendo del Speaking
  Assessment + evidencia + retención). Base: `3.9.0`
- ✅ Versión estable `3.9.0` — **Pronunciation por rutas CEFR: página única read-aloud con operativa tipo Listening/Speaking**
  (APRENDER → Pronunciation deja la práctica libre de 3 frases hardcodeadas y
  pasa a una página única como Speaking/Listening: la frase modelo a leer en voz
  alta vive arriba —la escuchas con TTS local y te grabas leyéndola— y debajo el
  mapa de rutas A1–C2 con anillos y el panel del nivel (Repetir fallidas /
  Repasar aprendidas / Practicar o repasar el nivel). Banco oficial nuevo y
  auditable `curriculum/pronunciation_corpus.json` (v1.0.0: 20 frases por nivel)
  y la evaluación es determinista y barata: Whisper + `score_pronunciation`
  (score ≥80 = superada), sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, nunca certifica—; demostrar el nivel sigue siendo del
  Speaking Assessment + evidencia + retención). Base: `3.8.0`
- ✅ Versión estable `3.8.0` — **Speaking por micro-conversaciones guiadas, con operativa tipo Listening**
  (APRENDER → Speaking es ahora una página única con scroll como Listening: el
  escenario de práctica —tarjeta de micro-conversación guiada con situación, rol
  y línea del interlocutor con voz, a la que respondes hablando— vive arriba y,
  bajo él, el mapa de rutas A1–C2 con anillos y sus modos (practicar el nivel,
  repetir fallidas, repasar aprendidas, añadir práctica extra) más el acceso al
  Speaking Assessment. El banco oficial `speaking_corpus.json` se regenera como
  tarjetas `{setup, you, app_line, model_response}` (v2.0.0: A1 36 / A2 32 / B1
  28 / B2 22 / C1 16 / C2 14) y el intento deja de ser read-aloud: cada respuesta
  se evalúa como respuesta abierta con el pipeline LLM+evidencia existente
  (`extract_speaking_evidence` + `scores_from_evidence`), con error transitorio
  503 si el extractor falla (nunca se puntúa en falso). El audio TTS se sirve por
  tipo con caché (`?kind=opening|model`). La ruta sigue siendo un hito de
  práctica —`functional` como techo, nunca certifica—; demostrar el nivel sigue
  siendo del Speaking Assessment + escenarios/misiones + retención). Base: `3.7.0`
- ✅ Versión estable `3.7.0` — **Speaking por rutas CEFR + fuente compacta en logs del lanzador**
  (APRENDER → Speaking es ahora un mapa de rutas A1–C2 con frases modelo
  read-aloud y banco curado oficial nuevo (`speaking_corpus.json`): practicar el
  nivel, repetir fallidas, repasar aprendidas y añadir práctica extra generada,
  todo puntuado en local sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, puerta con cobertura/precisión/checkpoint sobre el
  banco oficial—; demostrar el nivel sigue siendo del Speaking Assessment +
  escenarios/misiones + retención, nunca de la ruta. El lanzador muestra los
  logs con fuente compacta monospace). Base: `3.6.2`
- ✅ Versión estable `3.6.2` — **Estado del servidor en el lanzador + corrección del 429 espurio**
  (el «Demasiadas peticiones» lo devolvía el rate limiter propio
  (`SecurityMiddleware`), no Ollama, cuando el servidor local se saturaba:
  las sondas `/api/health` quedan exentas de cupo y de 429, los topes suben
  para el uso local razonable, cada rechazo queda registrado y visible en el
  nuevo `GET /api/system/status` —generación de práctica extra en curso por
  nivel + rechazos del último minuto—, el mensaje de error 429 se localiza en
  la lengua de la UI (`errors.rateLimited`) y el launcher gana la sección
  «Actividad del servidor» con la píldora de cabecera en ámbar
  («En marcha · generando…» / «saturado») cuando el backend trabaja o
  rechaza). Base: `3.6.1`
- ✅ Versión estable `3.6.1` — **Atajos de APRENDER + coherencia de idioma**
  (la franja superior de cada práctica de APRENDER conserva la flecha al hub y
  añade un atajo directo entre las 6 actividades —Listening/Speaking/
  Pronunciation/Conversation/Vocabulary/Grammar—; los nombres de actividad se
  unifican en inglés en ambos idiomas y se localiza el chrome que se pintaba en
  inglés con la UI en español: tipos de audio y buckets de retención en
  listening, fluidez y avisos de pronunciación, píldoras y estabilidad del plan
  del día, foco/acción de Writing, título/pts de Speaking, PASS/DUE del curso y
  skip-link). Base: `3.6.0`
  — **Listening: práctica ilimitada + repaso por ruta**
  (cada ruta A1..C2 se puede ampliar con práctica generada por IA local —nunca
  contenido oficial: la puerta, el estado functional/demonstrated y el routing
  adaptativo siguen anclados al banco curado, así que añadir extras no revoca ni
  encarece certificar—; el anillo crece con el desglose "oficiales + extra" y
  cada ruta permite "Repasar lo aprendido", no solo las falladas). Base: `3.5.8`
  — **Auditoría de UI: contraste claro/oscuro + QR**
  (QR visible en modo oscuro sobre tarjeta blanca fija, contraste WCAG corregido
  en insignias CEFR, avisos ámbar, fechas/texto tenue y avatar "?" sin perfil; la
  ProfileGate de V3.5.7 se estabiliza en tests visuales con perfil de test
  mockeado). Base: `3.5.0` — **P2 de la Constitución pedagógica en UI**
  (pantallas honestas: la práctica de listening se lee por estado de ruta
  —`functional` es hito de práctica y solo `demonstrated` (puerta + retención
  retardada estable ≥7 días) muestra «A1 Listening — demonstrated»—, todo badge
  de nivel estimado lleva el calificador «estimado · no certificado» y se eliminó
  el código muerto `modeCefrLevel`/`modeCefrBand`; ver `CHANGELOG.md` y
  Constitución §9). Base: `3.4.0` — **P1 de la Constitución pedagógica en código**
  (matriz CEFR a C1/C2 × las 8 destrezas con evidencia por kind, certificación de
  nivel con retención —*completado ≠ certificado*— y Lexical Units con Vocabulary
  Coverage Indicator receptivo/productivo). Base: `3.3.0` — **P0 de la
  Constitución pedagógica en código** (sin
  interpretación palabras→nivel, registro por competencia Estimado/Demostrado con
  `competence_states`, listening como evidencia del Student Model con retención).
  Base: `3.2.1` — **Auditoría pedagógica del modelo de nivelación** (solo
  documentación; ver `docs/audit/H-NIVELACION-PEDAGOGICA.md` y
  `docs/CONSTITUCION-PEDAGOGICA.md`). Base: `3.2.0` — **Calibración pedagógica de
  niveles** (nivel estimado global honesto con `Pre-A1`, Listening como rutas con
  puerta de evidencia y corpus A1/A2 → 200 ítems c/u). Sobre la base de **V3.1 UI**
  (release de interfaz y navegación; ver `docs/UI_V3.1.md`). El stack
  pedagógico previo sigue en `3.0.0` — **V3.0
  Beta freeze** tras el stack pedagógico
  V2.7–V2.12 (Depth → Listening → Speaking Mission → Assessment 2.0 → FSRS →
  Evidence Graph). Gates en `docs/BETA_V3.md` + `docs/BETA_GATES.md`. Base previa:
  **FASE 1–5** de la auditoría externa a V1.29 (LAN/HTTPS/audio móvil):
  **V1.30** LAN + Mobile 100% (mDNS real, test de micrófono con medidor, QR de conexión,
  `/help/connect`), **V1.31** Adaptive Engine 2.0 (Priority Engine + "Why this activity?"),
  **V1.32** Curriculum 2.0 (escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones),
  **V1.33** Listening 2.0 (Listening Resilience + `context` del corpus), **V1.34** Speaking 2.0
  (pronunciation proxy + Interaction Quality + Conversation Endurance), **V1.35** gestión en-app
  de la biblioteca de audio humano (Ajustes → Audio), **V1.36** Audio Corpus 1.0 (corpus de audio
  humano versionado + pipeline de grabación + importación masiva), **V1.37** Audio QA + Content
  Audit (QA acústica + content integrity check + Content Audit Dashboard + candado admin/PIN),
  **V1.38** Course Engine (secuenciación Course→Unit→Lesson→Practice→Review→Assessment con gating
  por objetivo + progreso visible "¿dónde estoy?") y **V1.39** Mastery 2.0 (`MasteryRecord`
  transversal para las 9 destrezas + CEFR readiness con banda cualitativa "B1 developing" en lugar
  de media simple + curva de olvido/review_due conectada a todo el currículo), y **V1.40** Speaking 3.0
  (catálogo de 8 escenarios comunicativos con objetivo comunicativo y métricas declaradas
  task_completion/interaction/fluency/repair/turn_taking + honestidad del proxy de pronunciación en la
  UI: "Confidence: medium · automated proxy"), y **V1.41** Beta Hardening (sin features nuevas: backup
  local completo SQLite+perfil+progreso+evidencia+manifest+WAV+settings con restore/export y
  auto-backup diario "keep 7", endpoints admin con PIN local, middleware de seguridad LAN
  origin-check + rate limiting, panel de backup en Ajustes → Sistema, matriz de dispositivos
  actualizada PC/Android/iPhone/iPad con HTTPS/mDNS/mic/audio/listening/speaking/recovery, a11y
  skip-link + `lang` sincronizado y code-splitting de vendors React/motion/iconos), y **Beta 1.0**
  (5 gates de salida 10/10: Infra/Curriculum/Listening+Speaking/Adaptive+Mastery/UX — ver
  `docs/BETA_GATES.md`). Sobre la base **V1.21**
  (cierre de la auditoría pedagógica A1→B2: corpus de audio humano 1.0 + validación determinista
  audio↔metadata + separación del proxy de pronunciación del audio real + evidencia
  familiar/transfer/novel + Interaction 3.0 + matriz de assessment CEFR; y nueva UI de 3 paneles
  con barra de estado y navegación por destrezas, más el **Learning Home** como pantalla central)
  y **V1.20** (pronunciación fonémica P6, turn-taking real e infraestructura de biblioteca de
  audio humano).
- **V3.2.x (2026-09-03) — Auditoría pedagógica del modelo de nivelación (solo documentación)**:
  dossier desk `docs/audit/H-NIVELACION-PEDAGOGICA.md` (hallazgos H1–H7: palabras→nivel aún en el
  modelo legacy, sin par Estimado/Demostrado, listening sin evidencia en el Student Model, matriz
  CEFR solo hasta B2, retención fuera de la certificación, mastery duplicado, estimado crudo en la
  UI) y especificación normativa **`docs/CONSTITUCION-PEDAGOGICA.md`**: separa Practice Level /
  Mastery / Estimated CEFR / Demonstrated CEFR con 4 estados por competencia
  (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), define cobertura léxica como indicador
  (no puerta), Lexical Units, progresión de listening y el Mastery Gate general (coverage +
  accuracy + subskills + retención ≥ 7 días + checkpoint). Los incrementos de código derivados
  (P0/P1/P2) quedan priorizados en la sección 9 de la constitución; no se ejecutan en esta iteración.
- ✅ **V2.0 Beta 1.0** (5 gates de salida 10/10), **V2.1 Content** (Content Quality Gate + corpus de
  listening 40→100 + escenarios de speaking 8→20 + niveles C1/C2), **V2.2 Academy/Course Engine**
  (métrica única "TOTAL VALIDATED LEARNING ITEMS" = 143, plantilla fija de 7 secciones por unidad,
  Mastery Gates por unidad, tríada Progress/Mastery/Readiness y pantalla Learning Journey) y
  **V2.3 Personal Dictionary + evidencia por ítem léxico** (siembra de vocabulario/estructuras desde
  el currículo, estado `known`/`learning`/`weak`/`mastered` + `recall` por ítem reutilizando la
  curva de olvido, endpoint `/api/vocabulary/lexicon` y pantalla Personal Dictionary) y
  **V2.4 Curriculum Coverage** (auditoría de cobertura curricular: recorre Pre-A1→C2 × 7 secciones,
  cruza el contenido del curso con los bancos de listening/speaking y genera
  `curriculum_coverage_report.json` con la métrica "TOTAL CURRICULUM COVERAGE", distinta de
  "TOTAL VALIDATED LEARNING ITEMS").
- ✅ **V2.5 Curriculum Completion** (completado; cierra los huecos de la auditoría V2.4). Hecho:
  **C1 listening C1/C2** (corpus 100→140, `c101`–`c140`), **C2 speaking C2** (escenarios 20→26),
  **C3 interaction A1/A2/B2/C1/C2** (subskills `interaction`+`turn_taking` en 39 objetivos,
  TOTAL VALIDATED 143→189, cobertura 37/49→42/49) y **C4 wiring curso↔bancos**
  (`listening_items` + `scenario_ids` por objetivo, 18 objetivos de listening y 50 de speaking
  cableados a los bancos; conteo y validación reflejan las referencias).
- ✅ **V2.6-C1 Capa de medición** (en curso): "cobertura" ≠ "profundidad". Nuevas métricas en
  `services/curriculum_coverage.py`: **UNIT COVERAGE** por unidad, **CEFR DEPTH SCORE** (0..100,
  4 componentes auditables), **UNIT LEARNING LOOP** (9 fases por unidad), drill-down
  LEVEL→UNIT→LESSON→OBJECTIVE y **Curriculum Quality Dashboard** (7 dimensiones + before/after).
  Overall **56,8**; puntos débiles medidos: review/assessment 23,5, listening 47,8 y las fases de
  cierre del loop (retrieve/transfer 0%, assess/review 19,4%). Loop etiquetado por unidad (V2.6-C5:
  50,6% → 84,7%); queda ampliar C1/C2 depth y subir unit coverage.
- ✅ **V2.7 Curriculum Depth (piloto B1)** (hecho). "Cobertura ≠ profundidad" convertido en acción
  con dos hilos: **(1) alineación de medición** — `unit_sections()` cuenta review/assessment por
  marcadores `phase` (consistente con `unit_learning_loop()`), no solo en el módulo Final — y
  **(2) contenido B1 real** — de 10 a 18 objetivos (interaction, listening, speaking y discourse
  markers por unidad, loop cerrado en todas las unidades). Dashboard: Overall **56,8 → 84,0**,
  Depth media 55,7 → 68,0, review/assessment 23,5 → 100, loop 84,7 → 88,4%; **B1 depth 55,7 → 90,4**
  (meta ≥82 cumplida). Plantilla maestra en `docs/UNIT_ARCHITECTURE.md` y briefings de escalado
  `agentes/curriculum/v27-depth-{a2,b2,c1,c2}.md`. Delta en `docs/CURRICULUM_COVERAGE.md`.
- ✅ **V2.7 Curriculum Depth (escalado A2–C2)** (hecho). La plantilla de "Unit Architecture"
  se aplicó al resto de niveles: **A2 11→17 objetivos (depth 60,9→82,6), B2 9→13 (68,4→82,7),
  C1 7→14 (55,5→82,6), C2 5→14 (49,2→82,2)**, cerrando el loop de aprendizaje y añadiendo
  listening/grammar/speaking/interaction por unidad. Dashboard: Overall **84,0 → 94,5**,
  Depth media 68,0 → 84,0, Listening 56,2 → 91,7, Speaking/Interaction 88,9 → 100, loop
  88,4 → 98,7%. Todos los niveles con curso superan depth 80. Queda como hueco real
  **Listening en A1** (5 unidades) → objetivo de V2.8.
- ✅ **V2.8 Listening Curriculum** (hecho). Cierre del listening en **A1** (+5 objetivos,
  loop Final) → **listening por unidad 100%** y **fase `listen` 100%** en todos los
  niveles. Progresión CEFR por subskill (`LISTENING_FOCUS_BY_LEVEL` en
  `services/curriculum.py`): A1 word recognition → A2 information → B1 natural speech
  → B2 inference → C1/C2 nuance/pragmatics. Métrica `listening_curriculum()` (alineación
  foco/subskill **100%** en 38 objetivos). Dashboard: Overall **95,7**, Listening **100%**,
  loop **100%**. Referencia en `docs/LISTENING_CURRICULUM.md`.
- ✅ **V2.9 Speaking Mission Performance** (hecho). Loop
  **Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement**:
  motor puro (`speaking_mission.py`), sesión trazable, API Academy y panel UI.
  Mejora visible (delta overall + por criterio). Referencia en
  `docs/SPEAKING_MISSION.md`.
- ✅ **V2.10 Assessment 2.0** (hecho). Escalera
  **formative → unit → progress → level → retention** + readiness derivado
  y mastery gate (initial/practice/transfer/novel/delayed). Motor
  `assessment_v2.py`, sesiones, API y UI en pestaña Assessment.
  Referencia en `docs/ASSESSMENT_2.md`.
- ✅ **V2.11 SRS / FSRS** (hecho). Scheduler FSRS-lite sobre el Evidence Model:
  cartas skill/lexicon, cola due auditable (What/Why/When/How strong/Last/Next),
  grades Again/Hard/Good/Easy. Referencia en `docs/FSRS.md`.
- ✅ **V2.12 Knowledge / Evidence Graph** (hecho). Can-do → dimensiones →
  limiting factor → mastery; Adaptive Engine con `because[]` estructurado.
  Referencia en `docs/EVIDENCE_GRAPH.md`.
- ✅ **V3.0 Beta freeze** (hecho). Funcionalidad congelada tras V2.7–V2.12;
  fase abierta: contenido + calibración + UX + pruebas reales.
  Gate `scripts/check_beta_v3.py` + `docs/BETA_V3.md`.
- ✅ Diálogo real probado con `qwen3.5:9b`.
- ✅ Documentación (`docs/`, premisas, arquitectura, guía de desarrollo, relevo, changelog).

## Hitos (roadmap)

### M0 — Esqueleto modular  [HECHO ✔]
- Refactor sin cambios de comportamiento: separar backend (`routers/`, `services/`, `schemas/`)
  y frontend (`api/`, `components/`, `hooks/`, `types/`) según `docs/ARQUITECTURA.md`.
- Verificado: backend arranca y responde, frontend compila (`tsc`), chat funciona de punta a punta.
- Subagente (ejecutado por el gerente): `agentes/m0-esqueleto-modular.md`.

### M1 — Streaming de respuestas  [HECHO ✔]
- El texto aparece mientras se genera (SSE/streaming), en vez de esperar la respuesta completa.
- Backend: `POST /api/chat/stream` (SSE). Frontend: `streamChat` consume e incrementa la burbuja.
- Verificado: múltiples `data: {"content":...}` + `data: {"done":true}`; `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m1-backend-streaming.md`, `agentes/m1-frontend-streaming.md`.

### M2 — Voz 100% local  [HECHO ✔]
- **Oído (STT):** voz → texto con **Whisper** (`faster-whisper`, `small`, CPU). ✔
- **Boca (TTS):** texto → voz con **Piper** (`en_US-lessac-medium`, CPU). ✔
- Backend: `POST /api/transcribe` y `POST /api/tts` (modelos en `backend/models/`).
- Frontend: botón micrófono (grabar → transcribir) y altavoz (escuchar respuesta).
- Verificado: TTS genera WAV válido; Whisper transcribe el audio generado correctamente.
- Subagentes (ejecutados por el gerente): `agentes/m2-backend-voz.md`, `agentes/m2-frontend-voz.md`.

### M3 — Memoria e historial  [HECHO ✔]
- Guardar conversaciones, poder retomarlas, contexto persistente.
- Backend: `services/store.py` (SQLite) + CRUD `/api/conversations`.
- Frontend: sidebar con lista de conversaciones, nuevo chat, cargar y eliminar.
- Verificado: crear → guardar → leer → listar → borrar funciona.
- Subagente (ejecutado por el gerente): sin briefing previo; implementación directa del gerente.

### M4 — Modo profesor de inglés  [HECHO ✔]
- **Modos de tutor**: `conversation`, `grammar`, `exercises`, `pronunciation` (system prompts por modo).
- **Corrección de pronunciación**: `POST /api/pronunciation` (audio + texto esperado → score).
- Frontend: selector de modo + tarjeta de práctica de pronunciación (grabar → evaluar).
- Verificado: backend 13 tests, frontend 10 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m4-backend-modo.md`, `agentes/m4-frontend-modo.md`.

### M5 — Modelo conversacional  [HECHO ✔]
- Evaluar cambiar a un modelo no-coder (ej. `llama3.1:8b` o `mistral`) para mejor calidad de tutor.
- Criterio: calidad como profesor (correcciones, explicaciones, tono) + tamaño/VRAM (RTX 4060 Ti 4 GB).
- Entregable: script de evaluación repetible + decisión documentada del modelo por defecto.
- Subagente (ejecutado por el gerente): `agentes/m5-modelo-conversacional.md`.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. Tras evaluar ambos con
  `scripts/eval_model.py` (4 prompts de tutor), `qwen3.5:9b` gana en calidad como tutor:
  correcciones más estructuradas, ejercicios con contexto y una guía de pronunciación IPA
  mucho más detallada y **correcta**. `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde la fricativa sorda /θ/ de *through* con la
  sonora /ð/ de *this/that*), así que **no es claramente mejor**. `llama3.1:8b` queda
  instalado como alternativa selectable en el frontend.
- **Descarga desbloqueada:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min.
  Al **quitar la VPN** la descarga terminó en ~1 min a 52 MB/s y sin error de certificado
  (el MITM del ISP ya no afectaba a esa conexión). `ollama pull llama3.1:8b` completado.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

### M6 — Release a GitHub  [HECHO ✔]
- Repositorio **público**: https://github.com/jvelasca/english-tutor
- V1.0 (tag `v1.0.0`) subida con release e issues de seguimiento.

### M7 — Multi-usuario  [HECHO ✔]
- Perfiles locales con **seguimiento independiente** (conversaciones, progreso, puntuaciones, ajustes).
- Selección simple de perfil al abrir; aislamiento total de datos entre usuarios (premisa 13).
- Backend: tabla `users`, columna `user_id` en `conversations` (migración idempotente no
  destructiva con usuario por defecto `Usuario`), `GET/POST /api/users` y CRUD de
  conversaciones filtrado por `user_id` (query param).
- Frontend: selector de perfil (`UserSelect`) en la cabecera, creación de usuarios, y
  aislamiento al cambiar de perfil (resetea conversación y recarga la lista del nuevo usuario).
- Verificado: backend 20 tests, frontend 14 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

### M8 — Diseño y UX nivel top  [HECHO ✔]
- Rediseño al nivel de apps líderes (ChatGPT/Duolingo): sistema de tokens, tema claro/oscuro,
  responsive, micro-interacciones y estados vacíos/carga/error (premisa 14).
- Sistema de **tokens** en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion). Tema **claro/oscuro** (`data-theme`, hook `useTheme`,
  toggle accesible, persistencia en `localStorage`, anti-FOUC en `index.html`).
- **Responsive** (≤768px): sidebar drawer + hamburguesa. **a11y**: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Verificado: frontend 19 tests (5 nuevos de tema), `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m8-diseno-ux.md`.

### M9 — Seguimiento de progreso del alumno  [HECHO ✔]
- Registrar el progreso por usuario: nº de ejercicios, correcciones y puntuaciones de
  pronunciación; mostrar un resumen en el frontend (issue #2, pendiente diferido de M4).
- Backend: tabla `pronunciation_attempts` + columna `mode` en `messages` (migración
  idempotente), `GET /api/progress?user_id=<id>` y `POST /api/pronunciation` con `user_id`
  opcional. Frontend: panel `ProgressSummary` + api `progress.ts`.
- Verificado: backend 27 tests, frontend 26 tests, `tsc` sin errores, `npm run build` OK.
- Subagentes (ejecutados por el gerente): `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

### M10 — Conversación por voz continua (manos libres)  [HECHO ✔]
- Modo continuo: VAD (detección de silencio vía Web Audio API), transcripción automática y
  respuesta hablada sin pulsar botones (issue #3). Sin cambios de backend
  (transcribe/tts/stream ya existían).
- Frontend: refactor `useChat.sendText(text): Promise<string>`, `utils/vad.ts` (RMS +
  `shouldEndUtterance`), `hooks/useHandsFree.ts` (bucle de estados + VAD por energía),
  `components/HandsFreeToggle.tsx` (toggle + indicador de estado accesible).
- Verificado: frontend 37 tests, `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m10-voz-continua.md`.

### M11 — Lanzador de escritorio + release estable  [HECHO ✔]
- Lanzador de escritorio (`launcher/`, GUI `tkinter` sin dependencias nuevas) que arranca/detiene
  la app (backend + frontend) y muestra el estado de servicios, base de datos y usuarios.
- Acceso directo del escritorio con icono (`launcher/install_shortcut.ps1` + `make_icon.ps1`).
- Versión unificada `1.1.0` (backend `config.py::VERSION` expuesta en `/api/health` y `/`, y
  frontend `package.json`).
- Verificado: launcher 22 tests + ruff limpio; backend 217 tests, frontend 88 tests, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/a1-launcher-core.md`,
  `agentes/endurecimiento/a2-launcher-gui.md`.

### M12 — Release Audit 1.1 + versión 1.1.1  [HECHO ✔]
- Cierre de los 6 puntos señalados por la auditoría externa antes de congelar la arquitectura.
  1. Unificar `current_user` en todos los endpoints sensibles.
  2. Fluidez ya expuesta como `FluencyStats` en `PronunciationResponse` (verificado, sin cambios).
  3. Renombrar "CEFR estimate" → `estimated_level/bands/descriptor`.
  4. Corregir semántica de vocabulario: `occurrences` → `appearances` (+ migración idempotente).
  5. Añadir `confidence`/`source`/`confirmed` a gramática y filtrar el prompt a errores confirmados.
  6. Tests de aislamiento cross-user + tests del Learning Context/Prompt.
- Selector de perfil: no auto-seleccionar el primer usuario si hay varios.
- Versión unificada `1.1.1`.
- Verificado: backend 231 tests, frontend 92 tests, launcher 22 tests, ruff limpio, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/ra-*.md` (RA1–RA7).

### M13 — Etapa 2: Pedagogía (Learning Engine v2)  [EN CURSO]
- Arquitectura congelada; solo se añade rigor pedagógico a lo ya medido (ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`).
- **Cierre del motor adaptativo (V3.68, 2026-09-15):** tras V3.68 el **diseño**
  del motor adaptativo queda **CONGELADO** (decisión de la auditoría de V3.67,
  **confirmada por la auditoría externa `Y` de V3.68**: 9,3/10, **0 P1**, y
  ningún hallazgo que justifique otra gran modificación arquitectónica del
  Adaptive Engine). El camino declarado hasta el producto terminado ya **no**
  añade capas arquitectónicas: **V3.68** cierre de la arquitectura adaptativa
  (hecho) → **V3.69** **E2E + Adaptive Engine Validation** (**HECHO** el
  2026-09-15: batería **E01–E19** por HTTP en
  `backend/tests/test_adaptive_e2e_v369.py`, **20 tests**, más el contrato de
  frontend con red mockeada en `frontend/tests/visual/drillProvenance.spec.ts`;
  **cero líneas de lógica de producto** y **cinco hallazgos aceptados como deuda**
  en la release note) → **V3.70** auditoría pedagógica (CEFR/competencias)
  (**HECHA** el 2026-09-15: **cinco ejes AA–AE + síntesis AF**, **1 P0 · 15 P1 ·
  12 P2 · 5 P3** y **4 propiedades positivas**; **5 subcomandos de medición solo
  lectura** en `audit_dossier.py` y **48 tests** nuevos; **cero líneas de lógica
  de producto**; los tracks P1–P6 quedan **medidos y acotados, no cerrados**) →
  **V3.71** runtime/offline/instalación **(siguiente)** → **V3.72**
  UX/product completion → **V3.73** auditoría final técnica → **V4.0** release
  final —«English Tutor, primera versión completa y estable»— y a partir de ahí
  `V4.0.x` de mantenimiento (bug fixes, calibración, UX, contenido,
  rendimiento).
- Tracks (un subagente a la vez): P1 política pedagógica formal, P2 error mastery,
  P3 vocabulario exposure/production/mastery, P4 listening como competencia, P5 CEFR basado
  en evidencia, P6 pronunciación fonémica.
- **Auditoría pedagógica de V3.70 (2026-09-15):** los seis tracks se **midieron**
  por primera vez con instrumentos deterministas y **solo lectura** (dossiers
  `docs/audit/AA…AF-*.md`). El resultado es que **el hueco es real y está
  acotado**: de los 33 hallazgos (1 P0 · 15 P1 · 12 P2 · 5 P3), los que tocan
  **contenido** (adecuación CEFR del banco, corpus de listening, forma de los
  ítems) se asignan a **V4.0.x**, y los que tocan **motor y acreditación**
  (validez de la maestría, `novel_required`, canales de evidencia de `interaction`
  y `mediation`, feedback que no genera explicación) a **Planner 4.0**; los
  **instrumentos** de nivelación, a **V4.0.x/V3.72**. Es decir: la etapa
  pedagógica **no se cierra en V3.70**, se cierra **sabiendo exactamente qué
  falta**.
- Subagentes (ejecutados por el gerente): `agentes/pedagogia/p-*.md` (P1–P6) y, para
  la auditoría, `agentes/v370-a1..a5-*.md`.

### M14 — Evidence & Performance + Listening + Placement  [HECHO ✔]
- **Evidence & Performance Engine (V1.3)**: ciclo `Evidence → Mastery → Skill Profile →
  Remediación` para speaking, writing y pronunciation (scorer determinista + extracción de
  evidencia con LLM + puente a mastery). CEFR Skill Profile (`/api/academy/profile`) y
  remediación adaptativa (`/api/academy/remediation`); el tutor lee el perfil CEFR.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (retrieval_probability + `review_due`
  real en función del tiempo).
- **Listening Engine**: sub-destrezas + dificultad + diagnóstico adaptativo
  (`/api/listening/diagnostic`).
- **Placement Engine (V1.5)**: IRT-lite adaptativo (`POST /api/academy/placement/next`).
- Verificado: backend 406 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M15 — Listening 2.0 + Placement 2.0  [HECHO ✔]
- **Listening 2.0 (V1.6)**: audio como entidad de primer nivel (`ListeningAsset` con metadatos
  de audio), vector de dificultad de 8 dimensiones con dificultad derivada por construcción,
  15 sub-destrezas (9 nuevas) y métrica de automaticidad (fluidez procesal).
- **Placement 2.0 (V1.7)**: calibración observacional de ítems (tabla
  `placement_item_calibration` con contadores poblacionales) y perfil **multiskill**
  (θ/nivel/confianza por destreza) sobre el motor IRT-lite/1PL. Endpoint
  `POST /api/academy/placement/profile` y banco de placement ampliado a las 7 destrezas.
- Verificado: backend 480 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M16 — FASE 1–5 de la auditoría externa (LAN/móvil → Speaking 2.0)  [HECHO ✔]
> Ejecutadas **directamente por el gerente** (sin briefings separados); ver `CHANGELOG.md` y
> `docs/RELEVO.md` (sección 37.6–37.11).
- **V1.30 LAN + Mobile 100%**: mDNS real (`local_url_available`), recuperación de permisos de
  micrófono, test de micrófono con medidor, QR de conexión y `/help/connect`.
- **V1.31 Adaptive Engine 2.0**: Priority Engine (`priority_signals`/`priority_score`/
  `explain_priority`) + "Why this activity?" en la tarjeta de siguiente mejor actividad.
- **V1.32 Curriculum 2.0**: escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones
  (`/api/academy/cefr-ladder`).
- **V1.33 Listening 2.0**: Listening Resilience por condición de escucha + `context` del corpus.
- **V1.34 Speaking 2.0**: pronunciation proxy + Interaction Quality por sub-dimensión +
  Conversation Endurance (`/api/academy/speaking/endurance`).
- Verificado: backend 843 tests + ruff limpio; frontend 234 tests + `tsc`/`build` OK; launcher 64
  tests; Playwright 14 passed + 10 skipped.

## Decisiones tomadas

- Hitos M1 y M2 en paralelo (tras M0).
- STT → Whisper (`faster-whisper`). TTS → Piper.
- Ritmo: poco a poco, hito a hito.
- Requisitos nuevos (premisas 13 y 14): **multi-usuario** y **diseño nivel top**. Quedan como M7 y M8.

## Tablero de subagentes

| Subagente | Archivo | Estado |
|---|---|---|
| M0 Esqueleto modular | `agentes/m0-esqueleto-modular.md` | ✔ hecho |
| M1 Backend streaming | `agentes/m1-backend-streaming.md` | ✔ hecho |
| M1 Frontend streaming | `agentes/m1-frontend-streaming.md` | ✔ hecho |
| M2 Backend voz | `agentes/m2-backend-voz.md` | ✔ hecho |
| M2 Frontend voz | `agentes/m2-frontend-voz.md` | ✔ hecho |
| M4 Backend modo profesor | `agentes/m4-backend-modo.md` | ✔ hecho |
| M4 Frontend modo profesor | `agentes/m4-frontend-modo.md` | ✔ hecho |
| M5 Modelo conversacional | `agentes/m5-modelo-conversacional.md` | ✔ hecho |
| M7 Backend multi-usuario | `agentes/m7-backend-multiusuario.md` | ✔ hecho |
| M7 Frontend multi-usuario | `agentes/m7-frontend-multiusuario.md` | ✔ hecho |
| M8 Diseño y UX | `agentes/m8-diseno-ux.md` | ✔ hecho |
| M9 Backend progreso | `agentes/m9-backend-progreso.md` | ✔ hecho |
| M9 Frontend progreso | `agentes/m9-frontend-progreso.md` | ✔ hecho |
| M10 Voz continua | `agentes/m10-voz-continua.md` | ✔ hecho |
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |
| RA1–RA7 Release Audit 1.1 | `agentes/endurecimiento/ra-*.md` | ✔ hecho |
| P1 Política pedagógica formal | `agentes/pedagogia/p1-politica-pedagogica.md` | ✔ hecho |
| P2 Error Mastery | `agentes/pedagogia/p2-error-mastery.md` | ✔ hecho |
| P3–P6 Etapa pedagógica | `agentes/pedagogia/p-*.md` | ✔ hecho |
| V1.15 Speaking 3.0 | `agentes/pedagogia/p9-speaking-3.0.md` | ✔ hecho |
| V1.18 P1 listening (retention + dictado/shadowing + variantes) | `agentes/pedagogia/p13-p15.md` | ✔ hecho |
| V1.19 Refresco UI profesional (frontend) | plan Cursor `refresco_ui_profesional` | ✔ hecho |
| V1.21 UI Learning Home (HOME como centro) | plan Cursor `v1.21_ui_learning_home` | ✔ hecho |
| V1.30–V1.34 FASE 1–5 auditoría (LAN/móvil → Speaking 2.0) | directo del gerente (sin briefings) | ✔ hecho |
| V2.7 Depth B1 (piloto) | directo del gerente (plan Cursor `v2.7_curriculum_depth`) | ✔ hecho |
| V2.7 Depth A2 | `agentes/curriculum/v27-depth-a2.md` | ✔ hecho |
| V2.7 Depth B2 | `agentes/curriculum/v27-depth-b2.md` | ✔ hecho |
| V2.7 Depth C1 | `agentes/curriculum/v27-depth-c1.md` | ✔ hecho |
| V2.7 Depth C2 | `agentes/curriculum/v27-depth-c2.md` | ✔ hecho |
| V2.8 Listening Curriculum | directo del gerente | ✔ hecho |
| V2.9 Speaking Mission Performance | directo del gerente | ✔ hecho |
| V2.10 Assessment 2.0 | directo del gerente | ✔ hecho |
| V2.11 SRS / FSRS | directo del gerente | ✔ hecho |
| V2.12 Evidence Graph | directo del gerente | ✔ hecho |
| V3.0 Beta freeze | directo del gerente | ✔ hecho |
| V3.18 Deuda del grafo (P3) | directo del gerente | ✔ hecho |
| V3.19 Léxico por destreza + Speaking micro-drill | directo del gerente (plan Cursor `v3.19_lexico_microdrill`) | ✔ hecho |
| V3.20–V3.52 (Dictionary→Learning Bridge, Listening 3.0/4.0, Transfer 2.0 y posteriores) | briefings en `agentes/` (`v324`, `v332`–`v352`) | ✔ hecho (histórico; fuente de verdad `CHANGELOG.md` + `docs/RELEVO.md`) |
| Auditoría profunda V3.18 pre-V3.19 (6 áreas) | `agentes/auditoria-profunda-v318.md` | ✔ hecho (dossier `docs/audit/I-AUDITORIA-PROFUNDA-V318.md`) |
| Auditoría TOTAL externa (v3.18.0) | `agentes/auditoria-total-externa.md` | ⚠️ sin dossier propio; la serie TOTAL continuó con `agentes/auditoria-total-externa-v321/v322/v323.md` y los dossiers `docs/audit/J-…`, `L-…`–`P-…` |
| Auditoría EXTERNA de V3.52.0 | `agentes/auditoria-externa-v352.md` | ✔ hecho (dossier `docs/audit/Q-AUDITORIA-TOTAL-V352.md`) |
| Auditorías de V3.60 | `agentes/auditoria-externa-v360.md`, `agentes/auditoria-externa-v359.md` | ✔ archivadas (`docs/audit/S-…` y `T-…`; la `R` de V3.59 sigue sin publicar) |
| Auditoría profunda de V3.62 + entrada externa | `docs/audit/U-AUDITORIA-TOTAL-V362.md`, `agentes/auditoria-externa-v362.md` | ✔ archivada (9,5/10 APROBADA); informe externo esperado en `docs/audit/V-AUDITORIA-TOTAL-V362.md` |
| V3.63 Observed Task Difficulty 2.0 + honestidad del modelo | `agentes/v363-observed-task-difficulty-2.md` | ✔ hecho (2026-09-14; release `v3.63.0`) |
| V3.64 Decision Projection + Planner 3.0 (cierre de P1-01) | directo del gerente | ✔ hecho (2026-09-14; release `v3.64.0`) |
| V3.65 Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica) | `agentes/v365-observed-difficulty-3.md` | ✔ hecho (2026-09-15; release `v3.65.0`) |
| V3.66 Task-Level Empirical Success + Decision Provenance | directo del gerente | ✔ hecho (2026-09-15; release `v3.66.0`) |
| V3.67 Task Identity 2.0 + Decision Lifecycle + Provenance Analytics | directo del gerente | ✔ hecho (2026-09-15; release `v3.67.0`) |
| V3.68 Adaptive Engine Hardening & Integrity (cierre de los P1 de 2.ª generación + P2-08) | directo del gerente (plan Cursor `v3.68_adaptive_engine_hardening`) | ✔ hecho (2026-09-15; release `v3.68.0`; auditada por `docs/audit/Y-AUDITORIA-TOTAL-V368.md`: 9,3/10, 0 P1) |
| V3.69 E2E + Adaptive Engine Validation (batería E01–E19; validación, no capacidad nueva) | `agentes/v369-e2e-adaptive-validation.md` | ✔ hecho (2026-09-15; release `v3.69.0`; **20 tests E2E** + 2 specs de navegador; diff de producto **CERO en lógica** (solo los bumps de versión de `config.py`/`package.json`); 5 hallazgos aceptados) |
| V3.70 Auditoría pedagógica + CEFR (cinco ejes AA–AE + síntesis AF; medición, no capacidad nueva) | `agentes/v370-auditoria-pedagogica.md` + `agentes/v370-a1-contenido-cefr.md`, `v370-a2-cobertura-destrezas.md`, `v370-a3-feedback-correccion.md`, `v370-a4-validez-maestria.md`, `v370-a5-instrumentos-nivelacion.md` | ✔ hecho (2026-09-15; release `v3.70.0`; **5 subcomandos de medición solo lectura** en `audit_dossier.py` + 6 dossiers `AA…AF` + **48 tests** nuevos; diff de producto **CERO en lógica**); hallazgos: **1 P0 · 15 P1 · 12 P2 · 5 P3** y 4 propiedades positivas. **Publicada (2026-09-16):** commit `9ba9c49` (+ docs `2db93ba`), tag `v3.70.0`, **CI 6/6** run `35062382562` |
| Auditoría EXTERNA de DISEÑO de V3.69 (pre-implementación: briefing + batería E01–E19 + derivación P2/P3) | `agentes/auditoria-externa-v369.md` | ⏳ lanzada (informe esperado en `docs/audit/Z-AUDITORIA-DISENO-V369.md`); **la implementación ya está cerrada** (commit `9a4e70a`, tag `v3.69.0`, CI 6/6 en `34978215154`), así que el dictamen se aplicará como corrección documental o se trasladará a V3.70+, y el punto de entrada de `agentes/auditoria-externa-v369.md` lleva un bloque **ACTUALIZACIÓN** con el estado de entrega para poder falsar el diseño **contra el código publicado** |
| Auditoría EXTERNA de V3.69 (post-implementación, sobre el código y los 5 hallazgos) | `agentes/auditoria-externa-release-v369.md` | ⏳ **lanzada** (informe esperado en `docs/audit/Z2-AUDITORIA-RELEASE-V369.md`): punto de entrada autocontenido con el estado de entrega (commit `9a4e70a`, tag `v3.69.0`, CI 6/6 `34978215154`), **15 afirmaciones falsables** con `archivo:línea`, comandos de reproducción y **13 preguntas de alto valor**; instruye a dictaminar los 5 hallazgos de §C uno a uno y a distinguir «el test no demuestra» de «el motor no cumple» |
| Auditoría EXTERNA de la RELEASE de V3.70 (post-implementación, sobre los cinco ejes AA–AF, los 48 tests y los 5 subcomandos de medición) | `agentes/auditoria-externa-release-v370.md` | ⏳ **entregada (2026-09-16)** (informe esperado en `docs/audit/AG-AUDITORIA-RELEASE-V370.md`; el prefijo `AG` evita colisión con los dossiers `AA`–`AF` del propio incremento): punto de entrada autocontenido con el estado de entrega (commit `9ba9c49`, tag `v3.70.0`, CI 6/6 `35062382562`), **12 afirmaciones falsables** con `archivo:línea`, comandos de reproducción (incluida la regeneración determinista de los 10 subcomandos) y **10 preguntas de alto valor**; instruye a dictaminar los 48 tests (demuestran vs describen), el P0 y las 4 propiedades positivas |
| Seguimiento de las auditorías EXTERNAS de V3.69 (`Z` y `Z2`, sin informe recibido) | `agentes/auditoria-externa-v369-seguimiento.md` | ⏳ **entregado (2026-09-16)**: registro del estado, verificación del hueco (`Z`/`Z2` no existen), objeto de cada informe, **texto de reclamo listo para enviar** y protocolo de acuse/triaje |
| V3.71 Runtime real, offline verificado e instalación limpia (ejes RA–RF; verificación con endurecimiento mínimo) | `agentes/v371-runtime-offline-instalacion.md` | 🔄 **en curso (2026-09-16)**: briefing redactado y **cuatro decisiones de alcance resueltas** por el gerente (medir y declarar la frontera de `npm run dev` · verificar y guiar el bootstrap de Ollama · corregir la documentación a favor de `config.py` · añadir el job del launcher al CI). **Eje RE cerrado** (el más barato y de efecto inmediato): job `launcher` en CI, 4 derivas documentales corregidas, 8 tests que las fijan (`docs/audit/RE-GATES-DERIVA.md`) |
| Eje RE de V3.71 (gates/CI/deriva documental) — evidencia interna | `docs/audit/RE-GATES-DERIVA.md` | ✅ **cerrado (2026-09-16)**: 7/7 jobs de CI (entra `launcher` con los 75 tests), derivas D1–D4 corregidas y **pinchadas por test** (`backend/tests/test_docs_drift_v371.py`, 8 tests), nota de corrección en `docs/BETA_GATES.md` y **G5 declarado abierto**; hallazgos P0 = 0 · P1 = 0 · P2 = 2 · P3 = 4 (1 deuda aceptada) |
| Eje RA de V3.71 (runtime y offline real) — evidencia interna | `docs/audit/RA-RUNTIME-OFFLINE.md` | 🔄 **instrumento + protocolo entregados (2026-09-16)**; **eje ABIERTO**: falta ejecutar los 12 flujos de `Y` §22 con la red cortada (RA-05). Hallazgos P0 = 0 · P1 = 0 · **P2 = 5** (2 cerrados por RD, 1 trasladado a RB, 1 abierto, 1 bloquea el cierre) · P3 = 2. Nuevo subcomando de solo lectura `runtime-audit` (determinista, con guard por test de 11 tests) y **3 dependencias de Internet no declaradas en ruta de producto** (RA-01) |
| Eje RD de V3.71 (dependencias ocultas y degradación) — evidencia interna | `docs/audit/RD-DEPENDENCIAS-OCULTAS.md` | ✅ **cerrado con alcance acotado (2026-09-16)**: cierra el **P1 de TTS/offline** diferido en 4 sitios desde V3.46 (**2 de 3 vectores**; el de UI se re-declara con fase a V3.72) y con él **RA-03** y parte de **RA-01**. Hallazgos P0 = 0 · **P1 = 1 (cerrado)** · P2 = 3 (2 cerrados, 1 con fase) · P3 = 3. El hallazgo central: el `timeout` de la descarga de voces era **código muerto** (`urlretrieve` no lo acepta) ⇒ la única dependencia de Internet en ruta de producto estaba **sin límite**; ahora es real y acotado, con verificación de tamaño y degradación declarada (`X-TTS-Voice`/`X-TTS-Degraded`). **6 tests nuevos**, todos fallan sin el cambio |

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

## Siguiente incremento (planificado)

- **✅ V3.70 — Auditoría pedagógica + CEFR (cinco ejes AA–AE + síntesis AF)**
  (**release `v3.70.0`, 2026-09-15**): **HECHA** (release de **medición**, no de
  capacidad). Con el motor adaptativo **cerrado y validado** por V3.69 (cadena
  completa demostrada por HTTP y **diff de producto cero**), el foco pasó del
  núcleo adaptativo al **rigor pedagógico de lo que ese núcleo sirve**. Se auditó
  en cinco ejes con instrumentos **deterministas y solo lectura** (5 subcomandos
  nuevos en `backend/scripts/audit_dossier.py`, salida regenerable en
  `docs/audit/generated/`): **AA · contenido/CEFR**, **AB · cobertura de
  destrezas**, **AC · feedback/corrección**, **AD · validez de la maestría**,
  **AE · instrumentos de nivelación**, más la síntesis **AF**. Resultado:
  **1 P0 · 15 P1 · 12 P2 · 5 P3** (33 hallazgos abiertos) y **4 propiedades
  positivas** verificadas, con **48 tests** nuevos que fijan cada hallazgo
  (si alguien cierra un hueco, el test falla y obliga a re-auditar el eje).
  Los 6 P2 de la auditoría de V3.69 **siguen abiertos** por decisión de alcance.
  **V3.70 no corrige nada**: asigna cada insuficiencia a su fase (contenido →
  V4.0.x · motor y acreditación → Planner 4.0 · instrumentos → V4.0.x/V3.72).
  Dossiers: `docs/audit/AA-PED-CONTENIDO-CEFR.md` … `AF-SINTESIS-PEDAGOGICA-V370.md`.

- **🔄 V3.71 — Runtime / offline / instalación**: **incremento en curso**
  declarado por el roadmap (**sin cambios**; auditoría `X` de V3.67, confirmada
  por la `Y` de V3.68). **Briefing redactado (2026-09-16)** en
  `agentes/v371-runtime-offline-instalacion.md` (seis ejes **RA–RF**: offline real
  con red desconectada · instalación limpia desde cero · runtime de producto y
  salud honesta · dependencias ocultas y degradación · gates/CI/deriva documental
  · síntesis), con las **cuatro decisiones de alcance ya resueltas** por el
  gerente: **(A)** medir y **declarar** la frontera de `npm run dev` (servir
  `frontend/dist` solo si la verificación demuestra un bloqueo duro) · **(B)**
  verificar y **guiar** el bootstrap de Ollama (descarga explícita opcional; la
  descarga inicial es la única excepción admitida) · **(C)** corregir la
  documentación **a favor de `config.py`** (fuente de verdad) y declarar la
  política · **(D)** añadir el **job del launcher al CI**.
  **Eje RE cerrado (2026-09-16)**: el launcher deja de ser el único subsistema
  sin gate (el CI pasa a **7/7 jobs**) y las **cuatro derivas documentales** (árbol
  del launcher en `ARQUITECTURA.md`, modelo por defecto en `PREMISAS.md`/`README.md`,
  los ✅ falsos de `BETA_GATES.md` y la fecha/versión del mismo documento) quedan
  corregidas, **anotadas sin reescribir el histórico** y **fijadas por 8 tests**
  (`backend/tests/test_docs_drift_v371.py`) que fallan si vuelven; evidencia en
  `docs/audit/RE-GATES-DERIVA.md`. **G5 (matriz de dispositivos) queda declarado
  ABIERTO** (acción humana). **Eje RD cerrado (2026-09-16)**: se cierra el
  **P1 de TTS/offline** diferido en 4 sitios desde V3.46 — su `timeout` de
  descarga era **código muerto**, así que la única dependencia de Internet en
  ruta de producto estaba **sin límite**; ahora es real y acotado, con
  verificación de tamaño y degradación declarada (`X-TTS-Voice`/`X-TTS-Degraded`),
  y con ello caen **RA-03** y parte de **RA-01** (6 tests nuevos); evidencia en
  `docs/audit/RD-DEPENDENCIAS-OCULTAS.md`. **Eje RA entregado pero ABIERTO**
  (instrumento `runtime-audit` de solo lectura + protocolo de los 12 flujos;
  falta el corte de red real): `docs/audit/RA-RUNTIME-OFFLINE.md`. Los ejes
  **RB/RC/RF siguen pendientes**. Los
  tracks **P1–P6 de M13** (política pedagógica formal,
  error mastery, vocabulario exposure/production/mastery, listening como
  competencia, CEFR basado en evidencia y pronunciación fonémica) quedan
  **medidos y acotados** por V3.70 pero **no cerrados**: su corrección se asignó
  a **V4.0.x** (contenido) y **Planner 4.0** (motor y acreditación). Roadmap
  posterior: **V3.72** UX/product completion → **V3.73** auditoría final técnica
  → **V4.0** release final («English Tutor, primera versión completa y estable»)
  y a partir de ahí `V4.0.x` (mantenimiento y calibración, **no** construcción
  del núcleo).

- **✅ V3.69 — E2E + Adaptive Engine Validation (el circuito completo de una
  pieza)** (**release `v3.69.0`, 2026-09-15**): **HECHA**. Origen: roadmap
  acordado en la auditoría `X` de V3.67 y **revisado por la auditoría `Y` de
  V3.68**, tras **congelar el diseño del motor adaptativo** (0 P1 y ningún
  hallazgo que justifique otra capa arquitectónica). La prioridad **no** era
  añadir funcionalidad, sino **demostrar experimentalmente** que el circuito
  funciona como uno solo:
  `Evidence → Student State → Decision Projection → Task selection → Decision →
  Serving → Attempt → Outcome → Evidence`.
  **Regla dura declarada (auditoría `Y` §28):** *V3.69 no debe introducir
  arquitectura nueva salvo que una prueba E2E demuestre que la arquitectura
  actual es insuficiente.* **Resultado: ningún escenario la demostró
  insuficiente ⇒ no se tocó producción** (el diff de producto es **cero en lógica**:
  solo los bumps de versión); las
  cinco desviaciones medidas se registran como **deuda aceptada** en la release
  note.
  **Batería obligatoria E01–E19, escrita y verde** (briefing ejecutable
  `agentes/v369-e2e-adaptive-validation.md`): E01 alumno nuevo · E02 skill débil
  (`speaking` débil/`writing` fuerte) · E03 retención (`mastered` → review due →
  repaso) · E04 brecha de transferencia (reconocimiento/recall fuertes y
  producción débil) · E05 transferencia de contexto (misma tarea, dos contextos →
  `task_key` igual, `task_instance_key` distinto) · E06 fallo (`ok, ok, ko` →
  cambia el `p_success`) · E07 incertidumbre ASR (`unclear` no penaliza mastery,
  no entra en calibración, conserva provenance) · E08 abandono (no contamina
  `ko`) · E09 refresh (`GET ×3` → un solo `decision_id`, sin duplicar decisiones)
  · E10 doble submit (idempotente) · E11 submit contradictorio (rechazado) · E12
  usuario ajeno (no modifica nada) · E13 target ajeno (rechazado) · E14
  transición inválida (`computed → completed`, rechazada) · E15 serving stale
  (`> 24 h` → `abandoned`) · **E16 determinismo del Planner** (mismo estado +
  fingerprint + candidatos + política → mismo task, `p_success`, ELV, razón y
  `decision_id`, **siempre**) · **E17 dependencia de apoyo** (hueco servido −
  acreditado → penalización declarada `SCAFFOLDING_PENALTY = 0.2`, aserción
  **diferencial**) · **E18 evidencia entrando DURANTE la decisión** (frescura por
  HTTP + reproducción determinista del TOCTOU de V3.64.1) · **E19 dos alumnos
  activos** (coexistencia sin mezcla de estado/cola/`decision_id`, **en ambas
  direcciones**; E12 cubre el rechazo de propiedad ajena). Con E17/E18/E19 el
  mapeo con los **10 casos originales** de la auditoría `X` queda **completo**
  (casos (3), (8) y (10), que la batería inicial no cubría o cubría solo
  parcialmente). Se cierra además el endpoint huérfano
  `GET /api/learning/decisions` (calibración + provenance health), que **ya
  tiene cobertura HTTP** (`test_e16b_decisions_endpoint_reports_calibration_and_health`),
  y el contrato del cliente queda fijado con red mockeada en
  `frontend/tests/visual/drillProvenance.spec.ts` (2 specs de navegador).
  **Entregado:** `backend/tests/test_adaptive_e2e_v369.py` (**20 tests**,
  2552 backend en total), 2 specs de navegador, `release-notes-v3.69.0.md` con
  la tabla de los **5 hallazgos aceptados** (E01(a), E08, E15, E17 y §F-1).
  Roadmap posterior declarado (**sin cambios**):
  **V3.70** auditoría pedagógica/CEFR (**siguiente**) →
  **V3.71** runtime/offline/instalación →
  **V3.72** UX/product completion → **V3.73** auditoría final técnica →
  **V4.0** release final («English Tutor, primera versión completa y estable») y
  a partir de ahí `V4.0.x` (mantenimiento y calibración, **no** construcción del
  núcleo).

- **✅ V3.68 — Adaptive Engine Hardening & Integrity**
  (**release `v3.68.0`, 2026-09-15**): plan Cursor
  `v3.68_adaptive_engine_hardening` ejecutado. Origen: la auditoría de V3.67
  (tres P1 de segunda generación + P2-08). Entregado: **Task vs Task Instance**
  (`task_key` de definición, sin contexto, que es lo que el Planner puede
  calcular antes de elegir instancia, frente a `task_instance_key` de
  instancia: el cierre real del P1-01, porque la firma de V3.67 incluía el
  contexto y el candidato lo construía vacío, de modo que una tarea de
  transferencia del ledger **nunca** casaba), **FSM real y probada** del ciclo
  de vida (`_ALLOWED_TRANSITIONS` + compare-and-set + `close_stale`),
  **integridad y propiedad** del provenance (guardas de `user_id`/`target_id`
  con fallo best-effort no-op contabilizado en `transition_health()`),
  **calibración honesta** (P2-08: `unclear`/`abandoned` fuera del denominador)
  y — por primera vez en la serie — el **eslabón de FRONTEND** que hace que el
  ciclo se ejecute de verdad (`decision_id` en cada GET/POST del peldaño y
  `started`/`abandoned` al cargar/desmontar el drill). Detalle en
  `release-notes-v3.68.0.md`.

- **✅ V3.65 — Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica)**
  (**release `v3.65.0`, 2026-09-15**): briefing `agentes/v365-observed-difficulty-3.md`
  ejecutado. Origen: el roadmap de la auditoría `W` de V3.63 y
  `release-notes-v3.64.0.md` §«Honestidad». Entregado: lector de telemetría
  completa (`list_attempt_rows`, éxitos + fallos + `target_id`), identidad de tarea
  en la fila canónica, estimador puro `empirical_success(rows)` por pareja (misma
  puerta espaciada de V3.54) y seam aditivo en Decision Projection + Planner 3.0
  (`p_success` empírico cuando la pareja lo declara, **byte-idéntico** si no).
  Detalle en `release-notes-v3.65.0.md`.

- **🗄️ V3.66 — Adaptive Instance Selection (histórico, superado por V3.67)**:
  bloque **obsoleto** conservado solo como traza del plan: V3.66 se entregó
  finalmente como **Task-Level Empirical Success + Decision Provenance**
  (`release-notes-v3.66.0.md`) y la **selección adaptativa de instancia** quedó
  declarada **fuera de alcance** en V3.68 (el nivel de instancia se **nombra,
  deriva y observa** con `task_instance_key`/`empirical_success_by_task_instance`,
  pero **no puntúa el argmax**). Candidatos que siguen abiertos de aquella lista:
  el **Sense Engine** (`surface ≠ sense`), el **Decision Provenance completo**
  (identidad lógica `serving_id`/`attempt_id`, P2-03/P2-04 de la auditoría `Y`) y
  la **calibración real** con datos (P2-05).

- **✅ V3.63 — Observed Task Difficulty 2.0 y honestidad del Student Skill State**
  (**release `v3.63.0`, 2026-09-14**): briefing autocontenido y ejecutado
  `agentes/v363-observed-task-difficulty-2.md`. Origen: la auditoría profunda de
  V3.62 (`docs/audit/U-AUDITORIA-TOTAL-V362.md`, 9,5/10 APROBADA) y su punto de
  entrada externo (`agentes/auditoria-externa-v362.md`). Alcance entregado:
  dificultad **empírica** de la tarea (`declared → served → outcome → observed`)
  con tablas declaradas sobre las filas canónicas, **identidad de
  evidencia y ocasiones** (observaciones vs ocasiones independientes), **canal
  observado** (P1-02: `spontaneous_use` escrito → `interaction`, oral → `speaking`),
  **confianza de evaluación** separada de la estadística, **criterio declarado de
  pronunciación** (lo que la ruta ya puntúa, sin inventar rúbrica), **eje declarado
  de capas de listening** (reutilizando `SKILL_LAYER`), **frescura de la caché del
  estado** (fingerprint + columna aditiva `skill_state_source`) y el **seam de
  política del gate**. **La decisión de tareas siguió intacta** (ELV, planner,
  `difficulty` y `transfer.context_for` byte-idénticos; guard estructural de V3.62
  verde **sin tocarse**). Detalle en `release-notes-v3.63.0.md`.

- **⏳ V3.53+ — candidatos abiertos (histórico; auditoría externa de V3.52 EJECUTADA
  y sus P2 CERRADOS en V3.52.2)**: informe en `docs/audit/Q-AUDITORIA-TOTAL-V352.md`
  (→ sin P0/P1). **Cerrados en V3.52.2:** P2-01 (`CEFR_CAPACITY` = envelope
  monótono del banco + invariante de encaje por nivel) y P2-02 (tolerancia
  documentada como red de seguridad con test de inercia y de discriminación
  sintética); etiqueta `v3.52.1` creada (P3-04). **Siguen abiertos y aceptados:**
  P3-01 (fila legacy etiquetada `practice` en vez de `estimated`) y P3-02
  (`_context_vector` trata un contexto sin vector como vector). Candidatos de
  producto ya documentados: **Sense Engine 2.0**
  (`surface→lemma→sense→semantic_fit`), **P1-02 Learner Skill State 2.0 +
  `observed_difficulty` persistido por evento** (**briefing listo para lanzar:
  `agentes/v353-learner-skill-state.md`**), **P1-03 Planner 2.0 /
  `expected_learning_value`**, **deuda de planner confirmada**
  (`assessed_skill` → decisión del planner y `skill_priorities` → `select_task`,
  con el doble conteo de `written_production` por resolver; V3.55), **entrega
  oral real del transfer** (audio + STT), Context Bank Family/Instance, offline
  TTS y code splitting del frontend. Del backlog histórico siguen abiertos los
  P2/P3 del dossier K (F-K3…F-K7) y los ítems de `docs/audit/PARKED.md`;
  comprobar su estado contra el árbol antes de adoptarlos.

- ~~**⏳ V3.38 — `situación` + planner (Optimal Next Task)**~~ ✅ **cerrado
  (2026-09-10, v3.38.0 + v3.38.1)**: implementado y publicado (ver «Estado
  actual» arriba, `release-notes-v3.38.0.md`/`v3.38.1.md` y
  `agentes/v338-situacion-planner.md`). El enunciado situacional, el planner
  (Optimal Next Task) y la automaticidad por skill están en producción; la
  historia posterior a V3.38 vive en `CHANGELOG.md` y `docs/RELEVO.md`.

- ~~**⏳ V3.37 — Cues graduados y planner sobre la evidencia**~~ ✅ **cerrado
  (2026-09-10, v3.37.0)**: implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.37.0.md`). La escalera graduada
  (`translation < definition < cloze`), la automaticidad espaciada y la cola de
  repaso con `recommended_cue`/`automatic` ya están en producción; `situación` y
  el planner se rebasan a V3.38.

- ~~**⏳ V3.36 — Learning Evidence 2.0**~~ ✅ **cerrado (2026-09-10, v3.36.0)**:
  implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.36.0.md`). `support_level`, `difficulty`, `response_time_ms`,
  `error_type`, `context_id`/`activity_id` ya se capturan y agregan. Los cues
  graduados y el planner se rebasan a V3.37.

- ✅ **V3.29 — Listening Engine 4.0 Fase 3 (núcleo) cerrado (2026-09-09,
  v3.29.0)**: implementado (ver "Estado actual" arriba,
  `release-notes-v3.29.0.md`). Núcleo de la Fase 3 de
  `docs/LISTENING_ENGINE_4.0.md` cerrado (alineación por palabra offline
  `word_alignment_proxy`, karaoke, controles precisos, salto a la palabra
  fallada y evidencia `word_breakdown_json`). El diccionario de consulta se
  reprioriza a V3.30 (siguiente candidato).

- ~~**⏳ V3.30 — Diccionario de consulta con marcas de uso y aprendizaje**~~ ✅
  **cerrado (2026-09-09, v3.30.0)**: implementado y publicado (ver «Estado
  actual» arriba, `release-notes-v3.30.0.md` y `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`).
  Quedan abiertos hacia **V3.31** los candidatos que V3.30 había diferido:
  consumo de `word_breakdown_json` en agregados / práctica dirigida de las
  palabras falladas y palabras tocables en transcripts/chat.

- ~~**⏳ V3.30.1 — Endurecimiento del diccionario (auditoría V3.30.0)**~~ ✅
  **cerrado (2026-09-09, v3.30.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.30.1.md`). Cierra los tres P1 de la
  auditoría (single-flight de generación, política `UNUSABLE_MODELS` frente al
  modelo explícito, caché versionada con `generator_version`) y el P2 del
  parser JSON. **Próximo candidato (rebasado a V3.32 por el cierre de V3.31)**:
  Dictionary → Learning Bridge (borrador en `agentes/v332-dictionary-learning-bridge.md`)
  — convertir la consulta en puerta al aprendizaje con «Practicar» explícito
  sin contaminar evidencia (D3 intacta), más los diferidos de V3.30.

- ~~**⏳ V3.31 — Cierre de la auditoría V3.30.1 (robustez y contrato del
  diccionario)**~~ ✅ **cerrado (2026-09-09, v3.31.0)**: implementado y
  publicado (ver «Estado actual» arriba y `release-notes-v3.31.0.md`). Cierra
  los hallazgos residuales de la auditoría de V3.30.1: cancelación del dueño
  del vuelo sin colgar a los waiters + tope de espera defensivo, invalidación
  del contenido de caché previo a V3.31 (`GENERATOR_VERSION` `1.1.0` + marca
  `DICTIONARY_LEGACY_VERSION` en la migración), tests de la migración de
  upgrade y del path real con modelo no utilizable, y contrato frontend del
  diccionario (tipo `DictionaryLookupRequest`, test del endpoint y timeout de
  cliente). **Próximo candidato V3.32**: Dictionary → Learning Bridge
  (borrador en `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.31.1 — Hardening del diccionario (cierre de la auditoría V3.31.0)**~~ ✅
  **cerrado (2026-09-09, v3.31.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.31.1.md`). Cierra el P1-01 residual y los
  P2 de robustez del diccionario: `pick_model` con explícito instalado +
  utilizable, negative cache con TTL de generación, rate limit de generación
  nueva por usuario/global y tope servidor del dueño del vuelo (90 s), más la
  semántica documentada del contenido canónico. **Próximo candidato V3.32**:
  Dictionary → Learning Bridge (borrador en
  `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.32 — Dictionary → Learning Bridge (primer eslabón)**~~ ✅ **cerrado
  (2026-09-09, v3.32.0)**: implementado y publicado (ver «Estado actual» arriba
  y `release-notes-v3.32.0.md`). Primer eslabón del puente: «Practicar esta
  palabra» en la tarjeta del lookup reutiliza la escalera de drill existente
  (Recall → Sentence) con evidencia idéntica a practicar fuera del diccionario
  (D3 intacta). Siguiente incremento hacia **V3.33**: los diferidos de V3.30
  (consumo de `word_breakdown_json` en agregados/práctica dirigida de las
  falladas y palabras tocables en transcripts/chat) y los siguientes eslabones
  del puente (escaleras por destreza — reconocimiento MCQ, recall demorado con
  FSRS — y transferencia por contexto, según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.33 — Recognition (MCQ definición ↔ palabra), eslabón 2 del
  puente**~~ ✅ **cerrado (2026-09-09, v3.33.0)**: implementado y publicado
  (ver «Estado actual» arriba y `release-notes-v3.33.0.md`). Segundo eslabón
  del Dictionary → Learning Bridge: peldaño `1 · Recognize` en la escalera
  compartida con pregunta determinista servida y puntuada por el backend y
  evidencia SOLO informativa. Siguiente incremento hacia **V3.34**: los
  diferidos de V3.30 (consumo de `word_breakdown_json` en agregados/práctica
  dirigida de las falladas y palabras tocables en transcripts/chat) y los
  eslabones restantes del puente — recall demorado con FSRS y transferencia
  por contexto de actividad V3.23 (según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.34 — Recall 2.0 (recuperación por texto + FSRS), eslabón 3 del
  puente**~~ ✅ **cerrado (2026-09-10, v3.34.0)**: implementado y publicado
  (ver «Estado actual» arriba, `release-notes-v3.34.0.md` y
  `agentes/v334-recall-2.0.md`). El peldaño intermedio del drill pasa a ser
  recuperación real por texto (cue = significado, nunca la palabra): señal de
  recall propia (`recall_successes`/`recall_days` + ledger `recalled`),
  recuperación demorada si supera el intervalo y reprogramación FSRS `lexicon`
  con intervalos reales; la escalera queda `1 · Recognize` · `2 · Recall` ·
  `3 · Sentence`, con el micrófono solo en Sentence. Siguiente incremento hacia
  **V3.35**: los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat), la transferencia por contexto de actividad V3.23 y el
  Lexical Evidence Engine / Evidence Graph como fuente longitudinal.

- ~~**⏳ V3.19 — Léxico por destreza + Speaking micro-drill**~~ ✅ **cerrado
  (2026-09-07, v3.19.0)**: implementado con las decisiones cerradas de diseño
  (ver "Estado actual" arriba, `release-notes-v3.19.0.md` y la entrada 37.37 de
  `docs/RELEVO.md`). Tests: pytest 1371 + ruff limpio, vitest 417 + `tsc`/
  `vite build` OK, `check_release_consistency` 3.19.0 exit 0, curriculum
  `--strict --quality` exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta
  abierta). Fuera de alcance de V3.19 (decisión (b)/futura): micro-drill 3
  niveles + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo,
  WR-UI-01, siembra FSRS sin señal (LEX-03).
- **V3.24 — Calibración de salida del Student Model (diseño cerrado
  2026-09-08)**: alcance decidido por el gerente = los 2 hallazgos **P1** del
  dossier `docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md` + **F-K8** (prerequisito
  de test de F-K2). Decisiones cerradas:
  - **F-K1 (decisión b) — relajar a lo emisible**: `MASTERY_EVIDENCE_REQUIREMENTS`
    queda `familiar×2 + transfer×2 + delayed` (sin `novel`); `novel_required=0`
    en las 12 celdas macro (B2/C1/C2 × listening/speaking/reading/writing) de
    `cefr_matrix.json`; el kind `novel` queda **reservado** y la frontera se
    documenta (sin emisor real, ningún gate debe exigirlo).
  - **F-K2 (decisión a) — anclaje por niveles completados + progreso en el
    tramo actual**: `adaptive.estimated_level` deja de proyectar `1 + 5·overall`
    y pasa a anclar: con niveles completados, el suelo es `CEFR_NUMERIC[mayor
    completado]`; sin completados, el suelo es el centro Pre-A1 (0.5, tramo
    A1) y la etiqueta nunca supera el nivel actual sin certificación previa.
    `build_student_model` pasa `current_level` + `completed_levels`.
  - **F-K8**: tests e2e del salto A1→A2 (premisa 12 del dossier K), escritos
    primero (fallan hoy) y que fijan: (a) dominar A1 no estima ≥ B2; (b) aprobar
    el examen A1 no baja el estimado por debajo de A1.
  El briefing autocontenido (rol/tarea/aceptación) vive en
  `agentes/v324-calibracion-salida.md`. **Todo lo pendiente hacia V3.24 queda
  consolidado en `docs/RELEVO.md` → sección 38** (backlog completo, fronteras y
  primeros pasos). El dossier K supera en contexto al briefing antiguo de
  auditoría TOTAL v3.18 (`agentes/auditoria-total-externa.md`).


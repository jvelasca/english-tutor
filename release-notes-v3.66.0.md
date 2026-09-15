# v3.66.0 — Task-Level Empirical Success + Decision Provenance

> Release **SIN migración destructiva** (una tabla append-only idempotente),
> **SIN bump de `GENERATOR_VERSION`**, **SIN tocar el banco** y **SIN cambios de
> UI** que cierra los DOS P1 de la auditoría de V3.65: el estimador que de verdad
> gobierna el Planner 3.0 pasa a ser `P(éxito | alumno, tarea)` **POR TAREA**
> (`target_id`), y la huella de snapshot se desdobla en DOS campos explícitos.
> Añade además **Decision Provenance**: cada decisión servida queda registrada
> append-only con su evidencia y su política.

## Contexto

V3.65 ya implementó y probó el estimador `P(éxito | alumno, tarea)` por pareja,
pero la decisión del Planner 3.0 acababa usando una tasa agregada **por
skill/eje** (`empirical_success_by_skill`). El estimador fino por pareja existía
sin gobernar la decisión (P1-01). Además, `snapshot_fingerprint` de V3.64.1
mezclaba dos conceptos: la huella observada al INICIO de la decisión y la huella
del estado efectivamente proyectado (P1-02). V3.66 cierra ambos de forma aditiva,
sin romper la pureza del planner ni la degradación byte-idéntica.

## Cambios

### A · Estimador puro por ITEM (`services/observed_difficulty.py`)

`empirical_success_by_target(rows)` agrupa las filas canónicas **SOLO** por
`target_id` (sin colapsar por actividad ni dificultad servida) y devuelve
`{successes, attempts, p_success, days}` reutilizando la MISMA puerta espaciada
de V3.54 (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`). Sin muestra espaciada el
ítem NO aparece (no se declara estimación); un ítem sin `target_id` no aporta
clave. Puro, determinista, sin reloj/random/hash; nunca lanza.

### B · Seam aditivo en la Decision Projection (`domain/decision.py`)

`_task_empirical_success()` lee `list_attempt_rows` (éxitos Y fallos con
identidad de ítem) y deriva las filas canónicas léxicas con
`skill_state_sources`, en una lectura **INDEPENDIENTE** de la caché del estado
(un read por construcción de la proyección: describe el ledger del candidato, no
la celda agregada). `project_state` expone la clave aditiva
`empirical_success_by_task` (`{target_id: estimación}`); el camino del perfil la
deja vacía (no es una decisión).

### C · Política de resolución en el Planner 3.0 (`services/planner.py`)

`expected_learning_value` y `select_task_by_elv` ganan `task_empirical_success`
y resuelven `p_success` con el orden declarado:

1. `task_empirical` — tasa empírica por ITEM (la observación más específica);
2. `skill_empirical` — tasa empírica por SKILL (base rate de V3.65);
3. `margin` — margen declarado de capacidad (V3.64).

El payload añade `p_success_source` (`task_empirical` | `skill_empirical` |
`margin`) y `task_p_success` (la tasa por ítem cuando está declarada), para que
la decisión sea auditable. Sin estimación la salida es EXACTAMENTE la de
V3.64/V3.65.

### D · Seam del léxico (`services/lexicon.py`)

`review_queue_item` extrae `empirical_success_by_task` de la proyección para el
`target_id` del ítem actual y lo propaga por `recommend_review_activity`,
`_task_decision` y `_learning_value`. Sin proyección (o sin estimación por ítem)
degrada byte-idéntico a V3.65.

### E · Huellas explícitas (P1-02, `domain/decision.py`)

`project_state` separa DOS huellas en vez de una sola mal etiquetada:

- `decision_start_fingerprint` — huella de las cuatro fuentes observada al
  INICIO de la decisión (lo que V3.64.1 llamaba `snapshot_fingerprint`).
  `snapshot_fingerprint` se conserva como alias retrocompatible.
- `state_fingerprint` — la huella que DESCRIBE el estado efectivamente
  proyectado (sello de la caché fresca validada, o sello del recálculo).

Invariante declarado: `state_fingerprint` representa el MISMO conjunto de
evidencia que `state`. El camino del perfil (no es una decisión) deja ambas
vacías.

### F · Decision Provenance (`repositories/decision_records.py` + `db.py` + `review.py`)

Nueva tabla append-only `decision_records` (`decision_id`, `target_id`,
`evidence_fingerprint`, `decision_start_fingerprint`, `state_fingerprint`,
`policy_version`, `selected_skill`/`selected_activity`/`selected_reason`,
`p_success`, `p_success_source`, `expected_learning_value`, `candidates_json`,
`drivers_json`) y el repositorio `record_decision()` con
`DECISION_POLICY_VERSION = "v3.66.0"`. `get_review_queue` registra una fila
best-effort por cada ítem servido con bloque `decision` (las alternativas
puntuadas y los drivers se serializan como JSON determinista; nunca rompe la
cola). Es el provenance que V3.65 dejó pendiente: permite reconstruir la
decisión sin mezclarse con la evidencia del alumno.

## Tests

Nuevo `backend/tests/test_decision_v366.py` (**13**, escritos antes del código):

- El test fundamental A-vs-B: dos tareas con distinto `target_id` y distinta
  tasa empírica; el planner elige en función de la tasa POR ÍTEM (la señal de
  V3.65 agregada por skill no distinguiría).
- `empirical_success_by_target` agrupa por ítem y reutiliza la puerta espaciada;
  no declara sin muestra ni sin `target_id`.
- Política de resolución `task_empirical` > `skill_empirical` > `margin`, y
  degradación exacta con estimados inválidos/ausentes.
- Honestidad de huellas: `decision_start_fingerprint` ≠ `state_fingerprint` y
  `snapshot_fingerprint` como alias; `state_fingerprint` coincide con el sello de
  la caché (fresca) y con el sello del recálculo.
- `record_decision` persiste la fila con su `policy_version` y devuelve `None`
  para un usuario inexistente.

## Honestidad

La granularidad por pareja (`target_id`) AHORA SÍ gobierna el `p_success` del
Planner 3.0 (P1-01). La resolución es determinista y audible vía
`p_success_source`. El provenance registra la decisión servida, pero **no** se
relee desde negocio todavía: es escritura best-effort para auditoría en bruto
(la lectura/agregación de `decision_records` es V3.67+). Adaptive Instance
Selection (elegir la INSTANCIA dentro de la tarea por pareja) sigue fuera de
alcance.

## Fuera de alcance

Adaptive Instance Selection, Sense Engine 2.0, lectura/agregación de
`decision_records` en el perfil, y los P2 de calibración pedagógica.

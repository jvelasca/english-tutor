# v3.65.0 — Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica)

> Release **SIN migración de BD**, **SIN bump de `GENERATOR_VERSION`**, **SIN
> tocar el banco** y **SIN cambios de UI** que convierte la dificultad observada
> de MEDIDA **DECLARADA** (V3.63) en una ESTIMACIÓN **EMPÍRICA** por pareja que,
> cuando existe, gobierna el `p_success` del Planner 3.0 — sin romper la pureza
> del planner ni la degradación byte-idéntica.

## Contexto

Hasta V3.64 el léxico devolvía **siempre** `success_rate = 1.0`: el lector
`list_observed_rows` filtraba `success = 1` y `_lexicon_rows` fijaba
`success = True`. La capa empírica de V3.63 declaraba la **dificultad** de la
tarea, pero nunca el **resultado** (`P(éxito)`). V3.65 cierra ese hueco con tres
piezas **aditivas**.

## Cambios

### A · Telemetría completa (`repositories/evidence.py`)

Nuevo lector `list_attempt_rows` (éxitos **y** fallos, con identidad
`target_id`/`surface_form`). `list_observed_rows` queda **intacto** (sigue
alimentando V3.53/V3.54 con solo éxitos). Fuera del camino caliente del drill.

### B · Identidad de tarea y fallos en la fila canónica (`services/skill_state.py`)

`_row` gana `target_id` (aditivo, vacío si la fuente no lo declara).
`_lexicon_rows` procesa el fallo como **INTENTO** (`score 0.0`, `dimensions {}`)
y propaga `target_id`/`surface_form`. La puerta espaciada del estado sigue
leyendo **SOLO** `success` (el gate 2/2 no cambia).

### C · Estimador puro por pareja (`services/observed_difficulty.py`)

`empirical_success(rows)` agrupa las filas canónicas por clave de tarea
(`target_id`/`actividad`/`dificultad servida`) y devuelve
`{successes, attempts, p_success, days}`, reutilizando la **MISMA** puerta
espaciada de V3.54 (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`). Sin muestra
espaciada la clave **no** aparece (no se declara estimación). El `p_success` es la
tasa empírica cruda acotada a `[0, 1]`. Puro, determinista, sin reloj/random/hash,
sin umbrales nuevos; nunca lanza.

### D · Seam aditivo en la Decision Projection (`services/decision_projection.py`, `domain/decision.py`)

Cada celda expone `empirical_success` (`{attempts, successes, p_success, days,
declared}`) derivado de la `confidence` **ya calculada** — no se confunde con
`assessment_confidence` (banda + motivos). `empirical_success_by_skill(projection)`
mapea por eje léxico (las 4 claves de `LEXICAL_SKILLS`). `project_state` añade la
clave aditiva `empirical_success`.

### E · Seam aditivo en el Planner 3.0 (`services/planner.py`, `services/lexicon.py`)

`expected_learning_value` y `select_task_by_elv` ganan el parámetro opcional
`empirical_success`. Si la estimación es **válida** (número en `0..1`), gobierna
`p_success` y se marca con `p_success_empirical`. Si no (ausente, inválida o fuera
de rango), la predicción es **EXACTAMENTE** la de V3.64 (margen declarado). El
margen declarado no cambia. `lexicon.py` propaga la estimación desde la proyección
solo en la rama con capacidad comparable; sin ella degrada exacto a V3.64.

## Tests

Nuevo `backend/tests/test_observed_difficulty_v365.py` (**18**, escritos antes
del código):

- La tasa empírica con un fallo + un éxito es `< 1.0` (premisa 12: fallaba en
  V3.64, donde el léxico daba `1.0`).
- `empirical_success` agrupa por tarea, distingue ítems/dificultad servida,
  reutiliza la puerta espaciada y no declara sin muestra.
- Pureza y determinismo byte a byte; `p_success` acotado a `[0, 1]`.
- El planner usa la estimación cuando se aporta y la **ignora** cuando es inválida
  (degradación byte-idéntica).
- Cableado proyección → planner; no-regresión de los ficheros de guard
  (`test_planner_argmax_v357.py`, `test_skill_state_v362.py`,
  `test_decision_projection_v364.py` sin tocar).

## Honestidad

La estimación se inyecta al **nivel de skill** (la granularidad con la que decide
el Planner 3.0), no por ítem. La granularidad fina por pareja
(`empirical_success` por `target_id`) queda **disponible** en el módulo puro para
V3.66 (Adaptive Instance Selection).

## Fuera de alcance

Adaptive Instance Selection, Sense Engine 2.0, Decision Provenance completo y los
P2 de calibración pedagógica (pesos de `skill_values`, `capacity_by_skill`
lexical, `review_due` en tiempo real) quedan para V3.66+.

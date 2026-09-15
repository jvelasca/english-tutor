# Briefing de subagente — V3.65 (Observed Difficulty 3.0)

> **Estado:** briefing entregado 2026-09-15; **pendiente de ejecución**.
> **Qué cierra:** la **dificultad empírica** `P(éxito | alumno, tarea)` —la
> estimación por pareja que V3.63/V3.64 declararon explícitamente como
> **inexistente y no simulada**—, y con ella la **frontera de degradación** que
> V3.64 dejó escrita («la proyección solo gobierna cuando el estado tiene algo que
> decir»).
> **Qué NO cierra (compromiso fechado / deuda):** **V3.66 Adaptive Instance
> Selection**, **V3.67+ Sense Engine 2.0**, **Decision Provenance completo**
> (fingerprint de contenido + trazabilidad fila-a-fila), los **P2 de calibración
> pedagógica** (pesos de `skill_values`, `capacity_by_skill` rica no-lexical,
> `review_due` en tiempo real desde FSRS) y el **P2-01** (`evidence_fingerprint`
> = `COUNT(*) + MAX(id)`, suficiente hoy por contrato append-only).
> **Auditoría/roadmap que lo motivan:** `docs/audit/W-AUDITORIA-TOTAL-V363.md`
> (roadmap recomendado: **V3.65 → Observed Difficulty 3.0** → V3.66 Adaptive
> Instance Selection → V3.67+ Sense Engine 2.0) y
> `release-notes-v3.64.0.md` §«Honestidad: qué NO cierra V3.64».
> **Base de partida:** árbol `v3.64.1` (commit `71f558e`, tag `v3.64.1`).

## Rol

Backend puro: un estimador empírico de éxito por pareja (módulo puro nuevo o
extensión de `observed_difficulty.py`), un lector de telemetría **completa**
(éxitos + fallos, con identidad de ítem) para las filas canónicas, y un **seam
aditivo** que inyecta la estimación en la Decision Projection y en el Planner.
**Sin** migración destructiva, **sin** bump de `GENERATOR_VERSION`, **sin** tocar
el banco, **sin** umbrales nuevos sin declarar y **sin** cambios de UI.

## Objetivo

Convertir `observed_task_difficulty_2` (medida **DECLARADA** con tablas
monótonas, V3.63) en una estimación **empírica** `P(éxito | alumno, tarea)` por
pareja —agrupando por `(alumno, ítem, actividad, dificultad servida)`— y hacer que
esa estimación, cuando exista, **gobierne** el `p_success` del Planner 3.0,
**sin** romper la pureza del planner ni la degradación byte-idéntica.

Reglas escritas por la auditoría `W` que **no se pueden relajar** (fijadas por
`release-notes-v3.64.0.md` y `docs/RELEVO.md`):

1. `highest_demonstrated_load` **no es** dificultad empírica y **no** debe
   renombrarse como tal (P2-04).
2. Separar **dificultad** (hecho de la tarea) de **esfuerzo** (coste observado)
   (P2-02) y **error de tarea** de **incertidumbre de medida** (P2-03).
3. **Sin umbrales nuevos sin declarar**: reutilizar la puerta espaciada de V3.54
   (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`) y las tablas ya declaradas.

## Estado de partida verificado (árbol v3.64.1)

- **Medida declarada, no probabilidad** — `services/observed_difficulty.py`:
  `served_ceiling` (`:136`), `credited_ceiling` (`:148`), `scaffolding_gap`
  (`:160`), `experienced_load` (`:171`), `observed_task_difficulty_2` (`:203`).
  Su docstring (`:24-33`) fija que **nada se estima de los datos**: las
  modulaciones son tablas declaradas (`LATENCY_STEP`, `ERROR_TYPE_STEP`,
  `REPLAY_STEP`, `SUPPORT_STEP`). Puerta espaciada reutilizada de V3.54.
- **La proyección expone `load`/`effort` separados** — `services/decision_projection.py`:
  `_cell` (`:221`) con `highest_demonstrated_load` (`:277` = `dict(capacity)`),
  `served_ceiling`, `credited_ceiling`, `scaffolding_gap`, `effort`, y
  `confidence`/`assessment_confidence` sin fusionar. Frontera declarada (`:40-42`):
  «`P(éxito | alumno, tarea)` es V3.65 y **no se simula aquí**».
- **El planner fija `p_success` por margen declarado** — `services/planner.py`:
  `expected_learning_value` (`:276`) → `margin = capacity_margin(...)` →
  `p_success = success_probability(margin)` → tabla `SUCCESS_BY_MARGIN` (`:80`).
  `select_task_by_elv` (`:757`) recibe `skill_values`/`drivers` **opcionales** y
  devuelve el bloque aditivo `decision`.
- **El outcome sí está persistido, pero la capa canónica lo recorta** —
  `repositories/evidence.py::list_observed_rows` (`:380-414`) filtra `success = 1`
  y **no** selecciona `target_id`; `summarize_by_target` (`:444`) agrupa por ítem
  pero **no** por `(ítem, actividad, dificultad servida)`. Consecuencia: en
  `services/skill_state.py::_lexicon_rows` (`:286-289`) el léxico fija
  `success = True`, así que `observed_task_difficulty_2` devuelve
  `success_rate = 1.0` **siempre** para el léxico (no hay fallos léxicos en el
  camino del estado, y no hay identidad de ítem: todo el léxico colapsa en
  `(modality, "")`).
- **Fronteras duras que no se pueden romper** (fijadas por test):
  - Pureza del planner (`test_decision_projection_v364.py:230-257`) y de
    `observed_difficulty.py` (`test_observed_task_difficulty_v363.py:424-437`):
    sin `import time/datetime/random`, sin `hash(`, sin I/O, nunca lanza.
  - Degradación byte-idéntica sin proyección (`planner._has_projection` `:858`,
    `_attach_decision` `:979`; probado en `test_decision_projection_v364.py:510`
    y `:627`).
  - Guard estructural (`test_skill_state_v362.py:841-856`): `planner.py`,
    `difficulty.py`, `transfer.py`, `lexicon.py`, `learner_state.py`,
    `vocabulary.py` **no** deben contener la subcadena `skill_state`.
  - `test_planner_argmax_v357.py` y `test_skill_state_v362.py` verdes **sin
    tocarse**.

## Decisiones de alcance (CERRADAS)

1. **La probabilidad empírica se calcula en un módulo puro aparte** (extensión de
   `observed_difficulty.py` o módulo nuevo `observed_success.py`), **nunca** en
   `planner.py` ni leyendo el estado persistido. Determinista, sin reloj, sin
   `random()`/`hash()`, sin umbrales nuevos.
2. **La estimación entra al planner como parámetro opcional**, exactamente como
   `skill_values`/`drivers` (patrón `_has_projection`): con estimación, `p_success`
   sustituye `success_probability(margin)`; sin estimación, **byte-idéntico** a
   V3.64.
3. **La telemetría completa no reescribe los lectores existentes**: se añade un
   lector nuevo (variante sin filtro `success = 1`, con `target_id`/`activity_id`)
   y la identidad de tarea se añade **aditivamente** a la fila canónica, dejando
   intactos `list_observed_rows` y el camino V3.53/V3.54.
4. **El cálculo se hace desde las filas canónicas**, nunca desde la caché como
   fuente de verdad (misma regla que la proyección de V3.64).
5. **Honestidad de nombre**: la nueva medida se llama lo que es (p. ej.
   `empirical_success` / `observed_success_by_task`), y `highest_demonstrated_load`
   **no** cambia de nombre.
6. **Sin migración destructiva** (columnas aditivas solo si hace falta) y **sin
   bump de `GENERATOR_VERSION`**.

## Diseño

### A · Estimador puro de éxito por pareja (módulo nuevo o extensión de `observed_difficulty.py`)

- `empirical_success(rows, *, now="")` → agrupa por clave de tarea
  (`target_id`/`activity_id` + `served_difficulty`) y devuelve por tarea
  `{successes, attempts, p_success, days}` con la **misma puerta espaciada** de
  V3.54 (sin 2 muestras en 2 días naturales → no se declara estimación).
- Tabla declarada de agrupación `(actividad, canal) → dimensión de dificultad`,
  sin vocabulario nuevo (reutilizar `LEXICAL_MODALITY` × `ASSESSMENT_MODE_MODALITY`
  y `SKILL_LAYER`).
- **Sin umbrales nuevos**: el `p_success` es la tasa empírica cruda acotada; el
  `margin`/`difficulty_fit` del planner sigue usando las bandas ya declaradas.

### B · Lector de telemetría completa (`repositories/evidence.py`)

- `list_observed_rows(..., include_failures=True, with_target=True)` o una función
  nueva `list_attempt_rows(user_id)` que **no** filtre `success = 1` y que
  seleccione `target_id`/`activity_id`/`served_difficulty`/`success`.
- **No** se toca `list_observed_rows` (sigue alimentando V3.53/V3.54 intacto).

### C · Identidad de tarea en la fila canónica (aditiva)

- `services/skill_state.py::_row`/`_lexicon_rows` ganan `task_key` (o
  `target_id`), **aditiva** y vacía si la fuente no la declara (misma degradación
  que `evidence_id`/`assessment_id` en V3.63).

### D · Seam de inyección en la Decision Projection

- `services/decision_projection.py::project` / `domain/decision.py::project_state`
  ganan una clave nueva (`empirical_success` por tarea, o por celda) calculada
  desde las filas canónicas e inyectada al planner.

### E · Seam aditivo en el planner (`services/planner.py`)

- `expected_learning_value` (`:276`) y `select_task_by_elv` (`:757`) ganan un
  parámetro opcional (p. ej. `empirical_success`). Con él, `p_success` sale de la
  tasa empírica (cuando la pareja la declara) y `decision`/`drivers` se extienden
  **aditivamente**; sin él, byte-idéntico (guard `_has_projection`).

## Tests (nuevo `backend/tests/test_observed_difficulty_v365.py`, **antes del código**)

- **Test que falla hoy (premisa 12):** sembrar evidencia léxica con **un fallo y
  un éxito** espaciados y afirmar que la fila canónica / `observed_task_difficulty_2`
  refleja `success_rate < 1.0` para el léxico. Hoy falla porque `list_observed_rows`
  filtra `success = 1` y el léxico siempre da `1.0`.
- Pureza y determinismo del estimador (sin reloj/`random`/`hash`/I/O).
- Puerta espaciada reutilizada (sin muestra espaciada → sin estimación).
- Agrupación por pareja y `p_success` acotado; **sin umbrales nuevos**.
- Inyección en el planner: con `empirical_success`, `p_success` cambia y se
  explica; sin él, **degradación byte-idéntica** a V3.64.
- **No-regresión:** `test_planner_argmax_v357.py`, `test_skill_state_v362.py` y
  `test_decision_projection_v364.py` verdes **sin tocarse**; el guard de la
  subcadena `skill_state` sigue verde.

## Fuera de alcance (deuda declarada)

- **V3.66 Adaptive Instance Selection** (`learner state + instances + failure/success
  + difficulty + transfer + novelty → next instance`).
- **V3.67+ Sense Engine 2.0** (WSD real).
- **Decision Provenance completo** (fingerprint de contenido + trazabilidad
  fila-a-fila); opcional una *provenance ligera* (enlazar `evidence_id`s al bloque
  `decision`) si hay holgura, si no se difiere entera a V3.66+.
- **P2 de calibración pedagógica** (pesos de `skill_values`, `capacity_by_skill`
  rica no-lexical, `review_due` en tiempo real desde FSRS) — requieren datos
  reales de alumnos.
- **P2-01** (`evidence_fingerprint` = `COUNT(*) + MAX(id)`) y **P2-14** (gate por
  pareja) — aceptados como deuda de largo plazo; no bloquean.

## Cierre (higiene de release, cuando se ejecute)

Bump `3.64.1 → 3.65.0` en `backend/config.py` + `frontend/package.json`/lock +
`README.md` + `CHANGELOG.md` + `PLAN.md` + nota superior de `docs/RELEVO.md` +
entrada en la sección correspondiente + `release-notes-v3.65.0.md` +
`check_release_consistency` **3.65.0**. Verificación local completa antes de
commitear (pytest/ruff/launcher/tsc/vitest/build/check_beta_v3/content_validation/
transfer_validation).

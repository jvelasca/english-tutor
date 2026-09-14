# Briefing de subagente — V3.64 (Decision Projection + Planner 3.0)

> **Estado:** briefing entregado 2026-09-14; **EN EJECUCIÓN**.
> **Qué cierra:** **P1-01** de la auditoría `U` de V3.62 —el Skill State es
> DESCRIPTIVO y debe volverse DECISIONAL por una capa intermedia
> (`Student Skill State → Decision Projection → Planner`, **nunca**
> `skill_state → planner` directamente)— y, **por contrato**, los hallazgos
> **P2-02** (coste ≠ dificultad), **P2-03** (`error_type` homogéneo) y **P2-04**
> (máximo por dimensión sobreestima capacidad) de la auditoría `W` de V3.63.0.
> **Qué NO cierra (compromiso fechado):** la **dificultad empírica**
> `P(éxito | alumno, tarea)` es **V3.65 — Observed Difficulty 3.0**; el gate por
> pareja (P2-14) y el fingerprint `COUNT+MAX(id)` (P2-01) quedan como deuda
> declarada. **No hay V3.63.1.**
> **Auditoría que lo motiva:** `docs/audit/W-AUDITORIA-TOTAL-V363.md`
> (**9,6 / 10 APROBADA**, 0 P0, 1 P1 conceptual, 4 P2, 2 P3).
> **Verificación:** pendiente de la ejecución (ver «Cierre»).

## Rol

Backend (módulo puro nuevo + recableado del camino de decisión + contrato aditivo)
con espejo mínimo de tipos en el frontend y una superficie visual **opcional y
diferible**. Sin migración de BD, sin bump de `GENERATOR_VERSION` y sin tocar el
banco.

## Objetivo

Convertir el **Student Skill State 4.0** (V3.62/V3.63) en la **entrada real** de
la decisión de tareas, a través de una **Decision Projection** pura que sustituye
la lectura V3.54 (`observed_skill_capacity`) que hoy alimenta el ELV, **sin**
romper ningún guard anterior y **sin** que el planner deje de ser un módulo puro y
ciego al estado.

La forma del incremento es una **frontera dura**: el planner **nunca** lee
`skill_state`; lee `capacity_by_skill` / `skill_values` / `drivers`, que son
**proyecciones** calculadas por un módulo propio. Eso es exactamente lo que pedía
el auditor y lo que el guard estructural de V3.62 (`test_skill_state_v362.py`)
fija en el código.

## Estado de partida verificado (árbol v3.63.0, `73cebb4`, cierre `07c130b`)

- **El planner es puro y ciego.** `services/planner.py`:
  `PRIORITY_WEIGHTS` (`:48`), `SLOW_RECALL_MS` (`:57`), `LATENCY_CEILING_MS`
  (`:60`), `SUCCESS_BY_MARGIN` (`:80`), `success_probability` (`:207`),
  `capacity_margin` (`:232`), `desirability` (`:258`),
  `expected_learning_value` (`:274`), `capacity_skill` (`:323`),
  `task_candidates` (`:711`), `select_task_by_elv` (`:755`),
  `planned_signals` (`:819`), `priority_score` (`:914`),
  `explain_priority`/`_capacity_phrases` (`:927`/`:954`).
- **El único punto de recableado real** es
  `services/lexicon.py::_capacity_by_skill` (`:805`), que lee
  `learner_state["observed_skill_capacity"]` (columna de V3.54) y construye la
  capacidad por **canal evaluado** con `student_state.skill_floor` (`:182`) +
  `learner_skill.skill_capacity` (`:268`).
- **Llamadores del planner:** `recommend_review_activity` (`lexicon.py:605`),
  `_task_decision` (`lexicon.py:824`), `_learning_value` (`lexicon.py:863`) y el
  orquestador `domain/review.py::get_review_queue` (`:73`), que lee el estado
  **una vez** (`:137`) y lo pasa a las **dos pasadas** de `review_queue_item`
  (`:150` y `:180`); el orden lo fija `_queue_sort_key` (`review.py:49`) =
  ELV → `priority` → `retrievability` → palabra.
- **El estado (V3.62/V3.63)** vive en `services/skill_state.py`:
  `_row` (`:174`), `occasion_key` (`:215`), `_lexicon_rows` (`:264`),
  `_academy_rows` (`:316`), `_listening_rows` (`:402`),
  `_pronunciation_rows` (`:441`), `skill_state_sources` (`:471`),
  `_capacity` (`:498`), `assessment_confidence` (`:535`),
  `_aggregate_assessment_confidence` (`:589`), `_entry` (`:602`),
  `skill_state` (`:686`), `skill_state_summary` (`:727`),
  `normalize_skill_state` (`:797`). La entrada ya expone `state`, `samples`,
  `days`, `score`, `confidence`, `dimensions`, `sources`, `observations`,
  `occasions`, `assessment_confidence` y `observed_task_difficulty_2`
  (`:661-682`); `by_kind` / `last` / `production_count` se calculan y **no se
  exponen**.
- **Dificultad empírica (V3.63)**: `services/observed_difficulty.py` con
  `served_ceiling` (`:136`), `credited_ceiling` (`:147`), `scaffolding_gap`
  (`:160`), `experienced_load` (`:171`) y `observed_task_difficulty_2` (`:206`).
- **Caché y frescura (ya existentes)**: `repositories/profile.py::get_profile`
  (`:11`) **ya expone** `skill_state` y `skill_state_source`;
  `set_skill_state` (`:99`), `skill_state_is_fresh` (`:139`);
  `repositories/evidence.py::evidence_fingerprint` (`:416`). La caché se escribe
  en `domain/profile.py::get_profile_summary` (`:305-323`) **después** de leer las
  fuentes, y las filas canónicas se ensamblan en `domain/profile.py:159-187`.
- **Frontera vigente que NO debe romperse**: `test_skill_state_v362.py:842-857`
  exige que ningún módulo del camino de decisión (`services/planner.py`,
  `services/difficulty.py`, `services/transfer.py`, `services/lexicon.py`,
  `domain/learner_state.py`, `domain/vocabulary.py`) contenga la subcadena
  `skill_state`. `test_decision_path_is_blind_to_the_persisted_state` (`:748`),
  `test_elv_and_argmax_are_unchanged_by_the_new_column` (`:802`) y
  `test_learner_capacity_is_unchanged_by_the_new_column` (`:859`) fijan además el
  no-op **byte a byte** del camino V3.54.

## Decisiones de alcance (CERRADAS)

1. **El planner sigue puro y ciego.** Ningún módulo de
   `services/planner.py` lee el estado persistido. La proyección entra por
   parámetro, exactamente como hoy entra `capacity_by_skill`.
2. **La proyección se deriva de las MISMAS filas canónicas**, nunca de la caché
   como fuente de verdad: la caché sellada (`skill_state_source`) es **solo** una
   optimización O(1) y **siempre** se valida con `skill_state_is_fresh` antes de
   usarse. Si está vieja (o es legacy sin sello), se **recomputa una sola vez**
   desde las cuatro fuentes y se **re-sella**.
3. **El guard de V3.62 no se toca.** Como la capa intermedia se llama
   `decision_projection` (no contiene la cadena `skill_state` en
   `planner.py`/`lexicon.py`/`domain/learner_state.py`) y el recableado real vive
   en `domain/decision.py` (que **no** está en la lista guardada), el guard sigue
   verde **sin modificarse** y sigue siendo literalmente cierto: el camino de
   decisión **no lee `skill_state`**, lee la proyección.
4. **Aditividad estricta.** Sin `projection`, `lexicon.review_queue_item` es
   **byte-idéntico** a V3.63; `select_task_by_elv` sin `skill_values`/`drivers` es
   **byte-idéntico** a V3.57/V3.63. Eso es lo que mantiene verde,
   **sin editarlos**, los tests de no-op anteriores.
5. **Frontera `load` vs `effort` (P2-02/P2-03).** La proyección expone dos grupos
   **separados**; `error_type` se clasifica con una tabla **declarada** en error de
   tarea (dificultad) e incertidumbre de medida (baja `assessment_confidence`,
   **nunca** sube dificultad). Cero umbrales nuevos.
6. **Nombre honesto (P2-04).** La carga máxima demostrada se llama
   `highest_demonstrated_load`; la dificultad **empírica** (`P(éxito | alumno,
   tarea)`) es **V3.65** y **no** se simula aquí.
7. **Sin migración y sin bump de `GENERATOR_VERSION`.** La proyección es
   **derivada**; las columnas aditivas ya existen desde V3.63.
8. **Nada de UI obligatoria.** La superficie de los `drivers` es opcional y
   diferible; el contrato debe estar cerrado y probado por e2e HTTP.

## Diseño

### A · Nuevo módulo puro `backend/services/decision_projection.py`

Mismo contrato de estilo que `services/observed_difficulty.py`: puro,
determinista, sin I/O, sin reloj propio (recibe `now`), sin `random()`/`hash()`,
sin LLM, nunca lanza.

- `project(state, *, level="", now="")` → `{modality: {competence: entry}}`. Por
  celda:
  - `capacity`: vector por dimensión (reutiliza la lectura del estado; la puerta ya
    la aplicó `_capacity`);
  - `highest_demonstrated_load`: **nombre explícito** de lo que hoy se llama
    "dificultad" (P2-04);
  - `served_ceiling` / `credited_ceiling` / `scaffolding_gap` (delega en
    `observed_difficulty`);
  - `load` (grupo: dificultad servida/acreditada) y `effort` (grupo: latencia,
    repeticiones, apoyo) **separados** (P2-02);
  - `confidence` (estadística) y `assessment_confidence` (banda + motivos) como
    **campos distintos** (P2-19 de V3.62, ya cerrado: no se re-fusionan);
  - `retention` (`review_due`, `last_evidence`), `transfer` (`kinds`, contextos),
    `novelty`, `samples`, `occasions`, `declared_channel`, `provisional`.
- `capacity_by_skill(projection)` → `{canal_evaluado: vector}`, con **el mismo
  espacio de claves que `lexicon._capacity_by_skill`** (las cuatro de
  `LEXICAL_SKILLS`) para ser un reemplazo directo. Una dimensión cuya evidencia es
  `assessment_confidence == "low"` se marca `provisional` y **no** cuenta como
  capacidad comparable: así el argmax no premia la ignorancia (invariante de
  V3.57).
- `skill_values(projection)` → `{eje: 0..1}` con `PROJECTION_WEIGHTS` **declarados
  y sumando 1.0** sobre `gap`, `retention`, `transfer`, `effort`. `difficulty` es
  el hecho servido, `effort` el coste, y `assessment_confidence` **no** es un peso:
  es un filtro de comparabilidad.
- `drivers(projection, skill)` → bloque explicable:
  `{gap, retention_due, transfer_gap, difficulty_fit, assessment_confidence,
  recent_failure, novelty}`.

### B · `services/skill_state.py` — hechos aditivos en la entrada

En `_entry` (`:602-682`) se **exponen** hechos ya calculados: `kinds` (el `by_kind`
actual), `production_count`, `last_evidence` (el `last` actual) y `contexts`
(instancias/contextos distintos). Cero recálculo, cero cambio de semántica,
contrato aditivo.

### C · Planner 3.0 en `services/planner.py` (aditivo, puro y sin estado)

- `select_task_by_elv(...)` gana parámetros **opcionales** `skill_values` y
  `drivers`, y devuelve además un bloque aditivo `decision` con
  `expected_learning_value`, `p_success`, `margin`, `drivers` y las alternativas
  puntuadas.
- Nueva función pura `explain_drivers(drivers)` (frases declaradas en inglés,
  mismo registro que `explain_priority`); `explain_priority` **se extiende** de
  forma aditiva.
- **Invariante**: sin los argumentos nuevos, byte-idéntico a V3.63.

### D · `backend/domain/decision.py` (I/O) + `domain/review.py`

- `domain/decision.py::decision_projection(user_id, *, level, now)`:
  1. lee `profile_repo.get_profile` (ya trae `skill_state` + `skill_state_source`);
  2. si `skill_state_is_fresh(user_id)` → `normalize_skill_state` de la caché;
  3. si no → **recomputa una sola vez** desde las cuatro fuentes canónicas
     (helper compartido con `domain/profile.py`, **sin duplicar** la secuencia),
     `set_skill_state(uid, json, evidence_fingerprint(uid))` y proyecta;
  4. devuelve `{state, projection, capacity_by_skill, skill_values, source}`
     (`source ∈ {cached, recomputed}`).
- `domain/review.get_review_queue` construye la proyección **una vez** y la pasa a
  las dos pasadas. `learner_state_domain.learner_level_state` **se conserva** para
  el suelo de nivel (`student_state.skill_floor`), que **no** cambia.

### E · `lexicon.review_queue_item(..., projection=None)` — aditivo y degradable

- Con `projection`: `capacity_by_skill` y `skill_values` de la proyección, más la
  clave aditiva `decision`.
- Sin `projection`: **camino V3.63 exacto** (`_capacity_by_skill` intacto).

### F · Contrato aditivo

- `schemas/learning.py::ReviewQueueItem` (`:44-100`) gana `decision`; `why` se
  conserva.
- `schemas/profile.py` gana `decision_projection` (aditivo; útil para la auditoría
  externa y para fijarlo por e2e).
- Espejo en `frontend/src/types/api.ts` (`:955-985`).

## Tests (nuevo `backend/tests/test_decision_projection_v364.py`, antes del código)

Pureza/determinismo (fuente sin reloj/`random`/`hash`/I/O); proyección por celda;
`highest_demonstrated_load` nombrado como tal; `scaffolding_gap = served −
credited`; `confidence` y `assessment_confidence` **nunca** fusionadas; `load` y
`effort` separados; un `error_type` de incertidumbre **no** sube dificultad;
`capacity_by_skill` con paridad de claves con `LEXICAL_SKILLS` y canal↔modalidad
correcto; degradación **exacta** sin `projection`/sin puerta 2-2/dimensión
`provisional`; **contraprueba positiva**: ahora el estado **sí** gobierna (la
tarea/ELV/orden cambia con evidencia espaciada real); frescura (fresca → no
recomputa; vieja/legacy → recomputa **una vez** y re-sella); explicabilidad
(`drivers` + `why` aditivo, claves de V3.63 presentes); e2e HTTP de
`GET /api/learning/review` y `GET /api/profile`.

## Fuera de alcance (deuda declarada)

- **V3.65 — Observed Difficulty 3.0**: `P(éxito | alumno, tarea)` empírica
  (`highest_demonstrated_load` ≠ dificultad empírica), sin convertir el LLM en
  autoridad.
- Fingerprint de contenido/versión (P2-01) y gate por pareja (P2-14).
- WSD/semántica real (Sense Engine 2.0) y selección adaptativa de instancia.

## Cierre

Pendiente de ejecución: bump a `3.64.0` en los seis orígenes que valida
`scripts/check_release_consistency.py`, `release-notes-v3.64.0.md`, nota superior
en `docs/RELEVO.md`, relevo a V3.65 y commit de release con **CI 6/6** y etiqueta
anotada `v3.64.0`.

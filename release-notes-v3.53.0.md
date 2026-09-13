# v3.53.0 — Learner Skill State 2.0 + `observed_difficulty`

> Primera release que separa la dificultad de la **TAREA servida** de la del
> **ítem léxico** y la convierte en un **Student Skill State OBSERVADO** por
> dimensión. Release **ADITIVA** (tres columnas de BD) que **NO toca** la
> escalera `transfer_state`, sus umbrales, `context_signals`,
> `context_diversity`, el scoring (`score_transfer_attempt`), el planner ni
> FSRS. Determinista, sin LLM.

## Contexto
    10|
La auditoría externa de V3.52.2 (🟢 9,6/10, sin P0/P1/P2) señaló dos deudas
evolutivas y recomendó **no seguir parcheando `difficulty.py`**:

- **La dificultad persistida era la del ítem, no la de la tarea.** El ledger
  guardaba `lexicon.cefr_difficulty`, así que un drill de transferencia que
  servía un contexto `discourse` 4 quedaba registrado con la carga léxica del
  ítem. La consecuencia: no se podía saber qué carga había **superado** el
  alumno de verdad.
- **`CEFR_CAPACITY` es la capacidad del BANCO, no la del ALUMNO.** El suelo de
  dificultad era una etiqueta CEFR global y no podía representar a un alumno B1
  global con `lexical` B2 y `syntax` A2.

V3.53.0 cierra el **P1-02 diferido desde V3.52** con las Partes A y B del
briefing [`agentes/v353-learner-skill-state.md`](agentes/v353-learner-skill-state.md),
más el P3 del comentario obsoleto de B1.

## Cambios

### A. `observed_difficulty`: la dificultad de la TAREA servida, por evento

Nueva columna aditiva `learning_evidence.observed_difficulty TEXT NOT NULL
DEFAULT ''` (CREATE TABLE + bucle `PRAGMA table_info` idempotente):

- `services.difficulty.format_vector` serializa un vector a `dim:load,dim:load`
  en el ORDEN canónico `DIFFICULTY_DIMENSIONS`, y `parse_vector` es su inversa
  **tolerante** (ignora pares mal formados, claves desconocidas y cargas fuera de
  1..5; devuelve `{}` ante basura; nunca lanza). Invariante:
  `format_vector(parse_vector(x)) == x` para todo vector canónico.
- `services.transfer.context_difficulty` (espejo de `context_skills`) acepta el
  dict del banco, un `id` (`"story"`) o un `context_id` (`"transfer:story"`) y
  devuelve el vector normalizado.
- El drill de **transferencia** persiste el vector del contexto **SERVIDO** (no
  del ítem ni una media). El resto de drills lo dejan `''` (no declaran banco de
  contextos).
- Plumbing en `record_evidence` / `record_evidence_bulk` / `list_evidence` y
  `EVIDENCE_FIELDS`.

### B. Learner Skill State 2.0: capacidad OBSERVADA por dimensión

    40|Nuevo módulo PURO `services/learner_skill.py`:

- `observed_capacity(signals)` — mayor carga SUPERADA por dimensión, exigiendo
  **muestra espaciada** (`OBSERVED_MIN_SAMPLES = 2` éxitos en `OBSERVED_MIN_DAYS
  = 2` días naturales distintos). Un acierto suelto no asciende y dos el mismo
  día tampoco: mismo rigor que `independent_success_days`/`recall_rung_days`.
- `level_from_capacity(observed)` — mayor nivel CEFR cuya `CEFR_CAPACITY`
  (envolvente del banco) queda **dominada** por la capacidad observada en las
  dimensiones CON muestra. Una dimensión sin muestra no bloquea, pero tampoco
  asciende: conservador por construcción.
- `learner_capacity(floor_level, observed)` — suelo efectivo por dimensión:
  máximo entre la capacidad del nivel de suelo y lo observado. Sube el reto solo
  donde hay evidencia y **nunca baja** el suelo declarado.

La señal se agrega en el nuevo puro `services.evidence.observed_signals`:

- `observed_samples` / `observed_days` / `observed_capacity` por modalidad
  (`LEXICAL_SKILLS`) y dimensión;
- atribución `assessed_skill` → `skill` (la modalidad que la tarea REALMENTE
  evaluó);
- solo ÉXITOS con vector declarado: un fallo o un drill sin contexto no
  acreditan capacidad.

Las claves viajan en `summarize_evidence`/`empty_summary` con **paridad
pura↔SQL por construcción** (`summarize_by_target` delega en la MISMA función) y
`repositories.evidence.list_observed_rows` alimenta el agregado por usuario.

### C. El suelo `observed` y su contrato

- `services.student_state.LEVEL_SOURCES` intercala `observed` entre
  `demonstrated` y `estimated`: `demostrado > observado > estimado > declarado >
  ninguno`. `CERTIFIED_SOURCES` **no** cambia, así que `observed` usa el margen
  amplio de `difficulty.tolerance_for` (un desempeño medido es más fuerte que una
  estimación, menos que una certificación).
- `learning_profile.observed_level` / `observed_capacity` (aditivas,
  idempotentes). `domain.profile` deriva el estado observado del ledger y lo
  cachea en `get_profile_summary`; `domain.vocabulary._learner_level_state` lo
  lee en **O(1)** (fila única) y pasa `learner_capacity` a `context_for` en GET y
  POST, con paridad intacta.
- `services.transfer.context_for(..., learner_capacity=None)`: la capacidad
  observada **sustituye** el suelo del nivel conservando el máximo por dimensión
  con la capacidad del ítem (el techo lingüístico no se rebaja). Con `None`/`{}`
  el resultado es **exactamente** el de V3.52.2.
- Contratos aditivos: `TransferContextOut.learner_capacity`,
  `LearningProfile.observed_level`/`observed_capacity`, con espejo opcional en
  `frontend/src/types/api.ts`. Sin cambios de UI obligatorios.

### D. P3 — comentario obsoleto de B1

El comentario de `services/difficulty.py` afirmaba que «B1 declara `interaction`
2» cuando la tabla vigente tiene 3. Reescrito para describir el envelope real.
Sin cambio funcional.

## Verificación

- Backend: `ruff` limpio y `pytest` **2185 passed** en local (+19:
  `test_observed_difficulty_v353.py` 8 y `test_learner_skill_v353.py` 11, más el
  ajuste del contrato exacto de `empty_summary` y de `student_state`).
- **No-regresión exhaustiva:** con `observed_capacity` vacío, `context_for` es
  idéntico a V3.52.2 en `context_id`, `difficulty_fit` y tolerancia para todas
  las combinaciones (nivel de ítem × nivel de alumno × fuente de suelo).
- **Paridad pura↔SQL** del estado observado verificada en
  `test_summarize_by_target_matches_the_pure_observed_signals`.
- Frontend: `tsc --noEmit` en verde (espejo de tipos aditivo, sin cambios de
  comportamiento).
- Scripts: `check_release_consistency.py` (**3.53.0**), `check_beta_v3.py`,
  `content_validation.py` y `check_i18n_coverage` exit 0.

## Qué NO cambia

- La escalera `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` y FSRS.
- `CEFR_CAPACITY` (es la envolvente del banco, recalibrada en V3.52.2) y el techo
  lingüístico del ítem (`_within_level`).
- La política de suelo: `observed` se **suma** a la prioridad ya existente, sin
  desplazar a `demonstrated`; sin muestra, el comportamiento es el de V3.52.2.
- El planner (`planner.skill_signals`/`select_task`) sigue sin consumir el skill
  state.
- Cero cambio de comportamiento con `observed_capacity` vacío (filas legacy y
  usuarios sin evidencia de transferencia).

## Fuera de alcance (V3.54+)

- **P1-03 / Planner 2.0 (`expected_learning_value`)**: cablear el skill state
  observado al planner es el siguiente candidato; hoy queda intacto a propósito
  para no mezclar la decisión pedagógica con la captura de señal.
- Sense Engine 2.0 (`surface → lemma → lexical_unit → sense`), Transfer 3.0,
  Context Bank Family/Instance y offline/TTS.
- P3-02 (`_context_vector` interpreta un contexto sin vector como vector) y P3-03
  (`is_test` marcable por el cliente): abiertos y aceptados, sin impacto de
  comportamiento.

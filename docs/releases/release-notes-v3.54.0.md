# v3.54.0 — Student Skill State 3.0

> Release **ADITIVA (una columna de BD)** que conserva la MODALIDAD en la
> capacidad observada (`skill × dimensión`), deriva el nivel CEFR **por skill**
> con la regla de cobertura completa de V3.53.1, añade el **suelo por modalidad**
> y activa un **gate de cobertura** que impide que una capacidad PARCIAL eleve
> tareas multidimensionales. **NO toca** `level_from_capacity` (el gate CEFR
> global de V3.53.1), `transfer_state`, sus umbrales, `context_signals`,
> `context_diversity`, el scoring, el planner ni FSRS. Determinista, sin LLM.

## Contexto

V3.53.1 dejó el Student Model en un punto sólido: la capacidad observada por
dimensión es la fuente de verdad y una sola dimensión ya no puede fabricar un
CEFR global. Pero ese estado **colapsaba las modalidades**: `observed_capacity`
tomaba el máximo entre todas ellas por dimensión. Un alumno con producción
ESCRITA B2 y sin ninguna muestra de producción ORAL podía ver elevado el reto de
una tarea oral, y una capacidad parcial (solo `lexical`) podía elevar una tarea
multidimensional (que exige también `syntax`, `discourse` e `interaction`).

El propio `services.evidence.observed_signals` ya agregaba por modalidad y
dimensión; la pérdida ocurría después, en `services.learner_skill`.

## Cambio

```text
EVIDENCE
   ↓
SKILL × DIMENSIÓN            # observed_skill_capacity (fuente de verdad)
   ↓
CAPACIDAD OBSERVADA          # nivel por skill (cobertura COMPLETA) + proyección legacy
   ↓
SUELO POR SKILL              # floor_level_for_skill (no hereda otra modalidad)
   ↓
GATE DE COBERTURA            # subconjunto → reto elevado; si no, suelo declarado
   ↓
TAREA SERVIDA
```

### A. Núcleo puro — `services/learner_skill.py`

- `observed_skill_capacity(signals)` — `{skill: {dimension: load}}` con la muestra
  ESPACIADA (`OBSERVED_MIN_SAMPLES` éxitos en `OBSERVED_MIN_DAYS` días) por
  (skill, dimensión). Es la fuente de verdad.
- `observed_capacity(signals)` — **proyección legacy** (máximo entre skills) que
  V3.53 exponía y la caché conserva; se implementa sobre la anterior.
- `level_from_skill_capacity` — nivel CEFR por skill con la regla de V3.53.1
  (envolvente del banco dominada en TODAS sus dimensiones). `""` con cobertura
  parcial. `level_from_capacity` NO cambia.
- `skill_coverage` — `none`/`partial`/`full` por skill.
- `skill_capacity` — `{capacity, coverage, covered_dimensions}` de un skill.
- `observed_skill_state` / `normalize_skill_capacity` / `empty_state` — estado
  cacheable y su parseo tolerante desde JSON.

### B. Suelo por modalidad — `services/student_state.py`

`floor_level_for_skill` aplica `demostrado > observado del SKILL > estimado >
declarado`. Una modalidad SIN muestra no hereda el observado global de otra; con
la caché legacy (sin estado por skill) delega en el comportamiento de V3.53.1.

### C. Gate de cobertura — `services/difficulty.py` y `services/transfer.py`

- `difficulty.challenge_for(context_vector, challenge, covered_dimensions,
  floor_challenge)`: el reto elevado solo aplica a contextos cuyas dimensiones
  declaradas son SUBCONJUNTO de las observadas; el resto se evalúa contra el
  suelo declarado.
- `difficulty.select_by_difficulty(..., covered_dimensions, floor_challenge)`:
  parámetros aditivos; sin ellos el comportamiento es el de V3.52/V3.53.
- `transfer.context_for(..., learner_skill_capacity, capacity_skill)`: resuelve
  la capacidad de la modalidad que la tarea puede MEDIR (`assessed_skill`; hoy
  `written_production` para Transfer) y devuelve `capacity_skill` (aditivo).

### D. Persistencia y contrato

- `learning_profile.observed_skill_capacity` (CREATE + `ALTER TABLE` idempotente,
  JSON determinista por `sort_keys`), derivada del ledger en `domain.profile` y
  cacheada en `get_profile_summary`; `set_cefr` la preserva.
- `LearningProfile.observed_skill_capacity`/`observed_skill_level`/`skill_coverage`
  y `TransferContextOut.capacity_skill` (aditivos), con espejo en
  `frontend/src/types/api.ts`.
- `_learner_level_state` lee el JSON en O(1) y expone el suelo por skill
  (`floor_level_by_skill`/`floor_source_by_skill`); GET y POST comparten el MISMO
  camino (paridad del `context_id` intacta).

## Qué NO cambia

- `level_from_capacity` y el gate CEFR global de V3.53.1.
- `observed_capacity` (proyección) y `learner_capacity` (suelo plano legacy).
- `CEFR_CAPACITY` (envolvente del BANCO), `transfer_state` y sus umbrales,
  `context_signals`, `context_diversity`, `score_transfer_attempt`, FSRS.
- El planner (sigue siendo el scorer de V3.38-V3.51).

## Verificación

- Nuevo `backend/tests/test_learner_skill_v354.py` (19 tests): estado por skill ×
  dimensión, aislamiento entre modalidades, nivel por skill con cobertura
  completa, cobertura, suelo por skill, gate de subconjunto en `challenge_for` y
  `select_by_difficulty`, integración de `context_for`, migración aditiva
  idempotente, caché del perfil, contrato HTTP y paridad GET↔POST.
- Ajuste de `test_learner_level_state_without_profile_is_neutral` (estado neutro
  por skill) y cero regresión en `test_learner_skill_v353.py`,
  `test_observed_difficulty_v353.py`, `test_student_state_v352.py`,
  `test_difficulty_engine_v352.py`, `test_task_semantics_v351.py` y
  `test_transfer_*.py`.
- `ruff` limpio; `check_release_consistency` (**3.54.0**).
- **CI 6/6 en verde** (run
  [34755745179](https://github.com/jvelasca/english-tutor/actions/runs/34755745179)
  sobre `b2929e1`): Backend (ruff + pytest, **2204 passed + 2 skipped**), Frontend
  (tsc + vitest **76 ficheros/651 tests** + build), Release consistency
  (**3.54.0**), Beta V3.0 gate, Content validation y Playwright E2E (visual,
  **23 passed**). Los 2 skipped son `backend/tests/test_stt_asr_integration.py`
  (modelo Whisper no descargado en el runner, opt-in); con el modelo disponible en
  local el mismo árbol da **2206 passed**. Etiqueta anotada `v3.54.0` creada y
  empujada sobre `b2929e1`.

## Fuera de alcance (V3.55+)

- P2-01: desdoblar `observed_difficulty` en
  `declared_difficulty`/`served_difficulty`/`observed_task_difficulty`.
- P2-02: enriquecer la capacidad observada con apoyo, independencia,
  transferencia, latencia, errores y novedad contextual.
- `expected_learning_value` y el Planner 2.0 (P1-03): el verdadero siguiente
  salto. Después, Sense Engine 2.0 y Context Engine 3.0.

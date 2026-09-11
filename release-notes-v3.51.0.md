# v3.51.0 — Task/Skill semantics + learner-level difficulty matching

**Release ADITIVA con UNA columna de BD que NO cambia la escalera
`transfer_state`, sus umbrales, el scoring ni FSRS. Cierra los tres P1 de la
auditoría externa de V3.50 separando lo que la tarea *quiere provocar* de lo que
realmente *puede medir*, exponiendo el vector completo de prioridades por
modalidad y anclando la dificultad del contexto al nivel DEMOSTRADO del alumno
(suelo de reto) sin renunciar al CEFR del ítem (techo lingüístico).
Determinista, sin LLM y con degradación con gracia.**

Versión de app `3.50.0 → 3.51.0`. Backend (`services/task_semantics.py` nuevo,
`services/transfer.py`, `services/planner.py`, `services/evidence.py`,
`services/lexicon.py`, `domain/vocabulary.py`, `repositories/db.py`,
`repositories/evidence.py`, `schemas/vocabulary.py`, `schemas/learning.py`) +
tipo del contrato en frontend (`types/api.ts`) + tests y docs.

## Contexto

V3.50 consiguió que la modalidad limitante del ítem y la dificultad declarada del
banco dejaran de ser inertes. La auditoría externa señaló, con razón, tres
ambigüedades de fondo:

- **P1-01 — el contexto no ES la evaluación.** El planner elegía el contexto por
  la modalidad limitante (`spoken_production` → contexto oral), pero el peldaño
  `transfer` se entrega por **textarea** y registraba siempre
  `skill="spontaneous_use"`. Se podía afirmar «hemos servido un contexto adecuado
  para hablar» sin que la actividad midiera producción oral.
- **P1-02 — la dificultad era del ÍTEM, no del ALUMNO.** `context_for(level=row
  ["cefr"])` usaba el CEFR curricular de la unidad léxica. Un alumno C1 con un
  ítem B1 seguía recibiendo los contextos más planos de su alcance.
- **P1-03 — el argmax descartaba información.** `limiting_skill` elegía una sola
  modalidad: con `written_production=0.62` y `spoken_production=0.60`, la segunda
  desaparecía de la decisión.

Fuera de alcance (diferido y documentado): entrega oral real del transfer
(audio+STT), Sense Engine 2.0 (`surface→lemma→sense→semantic_fit`),
`observed_difficulty` persistido por evento, `expected_learning_value` / Adaptive
Planner 2.0, Context Bank Family/Instance y offline TTS.

## Qué cambia

### Semántica explícita de tarea (`services/task_semantics.py`, nuevo)

Módulo **puro** (sin I/O, sin LLM, sin reloj, sin aleatoriedad) con:

- `ASSESSMENT_MODES = ("written", "spoken", "receptive")`.
- `TASK_SEMANTICS`, tabla declarativa por actividad del drill:

  | actividad | target_skill | assessed_skill | assessment_mode | evidence_skill |
  |---|---|---|---|---|
  | `word` | `spoken_production` | `spoken_production` | `spoken` | `spoken_production` |
  | `sentence` | `spoken_production` | `spoken_production` | `spoken` | `spoken_production` |
  | `write` | `written_production` | `written_production` | `written` | `written_production` |
  | `recall` | `recall` | `recall` | `written` | `recall` |
  | `transfer` | `spontaneous_use` | **`written_production`** | **`written`** | `spontaneous_use` |

- Helpers que **nunca lanzan**: `semantics_for`, `target_skill_for`,
  `assessed_skill_for`, `assessment_mode_for`, `evidence_skill_for`,
  `assessable_skills` (= `{target_skill, assessed_skill}` en orden canónico),
  `is_assessable`, `activity_for_target` y `activity_from_activity_id`.

`evidence_skill` **reproduce literalmente** lo que hoy escriben las cinco vías del
drill en `domain/vocabulary.py`. El gate de transferencia no se altera: el
contrato histórico de `learning_evidence.skill` sigue intacto y un test de
paridad lo fija.

El drill **Transfer** declara así el «split honesto»: su eje es
`spontaneous_use` (lo que acredita la transferencia) pero la modalidad que puede
**evaluar** es `written_production` (se entrega por texto).

### Ledger honesto: `assessed_skill` (migración aditiva)

- `repositories/db.py`: `assessed_skill TEXT NOT NULL DEFAULT ''` en el
  `CREATE TABLE learning_evidence` y en el bucle idempotente de `ALTER TABLE ...
  ADD COLUMN` (mismo patrón que V3.36/V3.46). Las filas legacy quedan en `''`.
- `repositories/evidence.py`: nuevo kwarg `assessed_skill=""` en
  `record_evidence` y en cada entrada de `record_evidence_bulk`; se incluye en el
  `INSERT`, en el dict devuelto y en el `SELECT` de `list_evidence`.
- `services/evidence.py`: `summarize_evidence` y `empty_summary` añaden
  `assessed_skill_attempts`/`assessed_skill_successes` (mismo criterio que los
  histogramas por `skill`: intentos = todos los eventos, éxitos = clave creada en
  el éxito).
- `repositories/evidence.py`: `summarize_by_target` añade los mismos campos
  (`GROUP BY LOWER(assessed_skill)`) con **paridad exacta** frente a la capa pura.
- `domain/vocabulary.py`: las cinco vías registran las dos dimensiones —
  `_record_retrieval` (word/sentence), `_record_write_evidence`,
  `_record_transfer_evidence`, la escalera de recall y el volcado de producción
  (`production_skill(channel)`)—. La columna `skill` conserva su valor; la nueva
  columna dice qué se evaluó.

### Vector de prioridades (`services/planner.py`, P1-03)

- Nueva función pública `skill_priorities(signals) -> dict[str, float]`: devuelve
  TODAS las prioridades por modalidad en orden canónico (`LEXICAL_SKILLS`),
  seguido de cualquier clave no canónica. Vacío sin bloque `skills`.
- `limiting_skill` se implementa sobre el vector (su argmax): mismo
  comportamiento y un único dialecto.
- `domain/vocabulary._transfer_target_skill` deja de devolver la limitante sin
  más y elige el máximo **solo entre `task_semantics.assessable_skills("transfer")`**
  (`written_production`, `spontaneous_use`): un ítem limitado en
  `spoken_production` ya no orienta el transfer a contextos orales (el planner lo
  envía a `sentence`).
- `context_for` y la cola de repaso (`ReviewQueueItem`) exponen `skill_priorities`
  (aditivo) para explicabilidad.

### Dificultad por nivel del alumno (`services/transfer.py`, P1-02)

- `context_for(..., learner_level="")` (kwarg aditivo). `level` sigue siendo el
  **techo** CEFR del ítem (`_within_level`); `learner_level` alimenta el **suelo**
  de reto de `_difficulty_floor`, que usa el MAYOR de los dos índices. Sin
  `learner_level` reconocible, el resultado es **idéntico a V3.50**.
- `domain/vocabulary._learner_level(user_id)`: lee el nivel cacheado del Student
  Model (`learning_profile.cefr_level`, la caché que escribe `/api/profile`) sin
  recalcular el modelo en el camino caliente del drill. Devuelve `""` si falta o
  no es CEFR reconocible.
- `get_transfer_context` y el fallback de `submit_transfer_attempt` pasan la
  MISMA expresión (mismo `skill` derivado y mismo `learner_level`), preservando la
  paridad GET↔POST del `context_id`.

### Contratos (estrictamente aditivos)

- `TransferContextOut`: `target_skill`, `assessed_skill`, `assessment_mode`,
  `item_level`, `learner_level`, `skill_priorities: dict[str, float]`.
- `TransferAttemptOut`: `target_skill`, `assessed_skill`, `assessment_mode`.
- `ReviewQueueItem`: `skill_priorities: dict[str, float]`.
- `types/api.ts`: espejo opcional de los mismos campos. Sin cambios de UI
  obligatorios.

## Verificación

- Backend: `ruff` limpio y `pytest` **2119 passed** (+20: `test_task_semantics_v351.py`
  y el ajuste del contrato exacto de `empty_summary` en `test_learning_evidence_v336.py`);
  cero regresión de `test_context_skill_v350.py`, `test_optimal_task_v339.py`,
  `test_transfer_*` y las suites de evidencia.
- Frontend: `vitest` **75 ficheros / 641 tests**, `tsc --noEmit` y `npm run build`
  en verde (el warning de bundle >500 kB es deuda preexistente).
- Scripts: `check_release_consistency.py` (**3.51.0**), `check_beta_v3.py` y
  `content_validation.py` exit 0.

## P3-01 (corrección documental)

La cifra declarada de V3.50 era `2099 passed`; el CI real verificó **2097
passed** (+2 skipped). Corregido en `release-notes-v3.50.0.md`, `docs/RELEVO.md`,
`CHANGELOG.md`, `PLAN.md` y `agentes/auditoria-externa-v350.md`.

## Qué NO cambia

`transfer_state` ni sus umbrales, `context_signals`, `context_diversity`, el
scoring (`score_transfer_attempt`), FSRS, el vocabulario de `learning_evidence.skill`
(su contrato histórico) y la CONSTITUCIÓN (R8/R9 sigue como propuesta abierta).

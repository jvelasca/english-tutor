# v3.52.0 — Student Skill State + Difficulty Engine 2.0

**Release ADITIVA con DOS columnas de BD que NO cambia la escalera
`transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el
scoring (`score_transfer_attempt`) ni FSRS. Cierra los dos P1 de la auditoría
externa de V3.51: separa explícitamente el nivel ESTIMADO del DEMOSTRADO (y del
declarado) para que el suelo de dificultad no se apoye en una banda de práctica,
y sustituye el ajuste escalar de dificultad por un motor que compara VECTOR
contra VECTOR por dimensión. Determinista, sin LLM y con degradación con
gracia.**

Versión de app `3.51.0 → 3.52.0`. Backend (`services/student_state.py` nuevo,
`services/difficulty.py` nuevo, `services/transfer.py`,
`repositories/db.py`, `repositories/profile.py`, `domain/profile.py`,
`domain/vocabulary.py`, `schemas/vocabulary.py`, `schemas/profile.py`) + tipo del
contrato en frontend (`types/api.ts`) + tests y docs.

## Contexto

V3.51 hizo explícito QUÉ evalúa cada tarea y ancló la dificultad al nivel del
alumno. La auditoría externa confirmó dos P1 de fondo:

- **P1-01 — `learner_level` no era el nivel demostrado.** `learning_profile.
  cefr_level` lo escribe `domain.profile` con `estimated_level`: una banda de
  PRÁCTICA continua (suelo por niveles completados + progreso ponderado), no una
  certificación. El nivel DEMOSTRADO ya existía (`domain.academy.
  _demonstrated_level` + `certification_gate`, expuesto en `StudentModelOut`),
  pero el drill nunca lo usaba y su docstring lo llamaba «demostrado».
- **P1-02 — el difficulty floor mezclaba escalas.** `_difficulty_floor`
  comparaba `cefr_index` (0..5) contra `difficulty_from_vector` (media 1..6) y
  colapsaba el vector de 4 dimensiones antes de comparar: un `(5,1,5,1)` y un
  `(3,3,3,3)` eran indistinguibles (misma media).

Deuda confirmada y **diferida** (documentada, no se arregla aquí): `assessed_skill_*`
se persiste y agrega pero ningún planner lo lee, y `skill_priorities` no entra en
`planner.select_task` (su parámetro `signals` está muerto); solo orienta el
*contexto* de transferencia. Cablearlo sin más haría que el transfer contase como
`written_production` junto al drill `write` (doble conteo), así que requiere su
propio diseño (**V3.55**).

## Qué cambia

### Student level state (`services/student_state.py`, nuevo — P1-01)

Módulo **puro** (sin I/O, sin reloj, sin aleatoriedad) con:

- `LEVEL_SOURCES = ("demonstrated", "estimated", "practice", "none")`.
- `floor_level(practice_level, estimated_cefr, demonstrated_cefr) -> (nivel, fuente)`:
  `demonstrated` reconocido → `estimated` → `practice` → `("", "none")`. Reutiliza
  `transfer.cefr_index` para validar (import unidireccional; `transfer` no importa
  este módulo). Un valor no CEFR o `None` no participa: no se inventa un suelo.
- `level_state(*, practice_level="", estimated_cefr="", demonstrated_cefr="") ->
  {practice_level, estimated_cefr, demonstrated_cefr, floor_level, floor_source}`.
- `is_certified(source)` y `empty_state()`.

**Política de confianza:** solo `demonstrated_cefr` exige `certification_gate`
(retención retardada) y merece la tolerancia estricta del motor; `estimated_cefr`
es un proxy de práctica y `practice_level` el nivel declarado/legacy (ambos con
margen amplio).

### Migración aditiva del estado de nivel (`repositories/db.py`, `repositories/profile.py`)

- `learning_profile` gana `estimated_level TEXT NOT NULL DEFAULT ''` y
  `demonstrated_level TEXT NOT NULL DEFAULT ''` en el `CREATE TABLE` **y** en el
  bucle idempotente `ALTER TABLE ... ADD COLUMN` (patrón V3.36/V3.46/V3.51).
  `cefr_level` se conserva intacto.
- Las filas legacy quedan en `''` y siguen alimentando el suelo como nivel
  **declarado** (`practice`), de modo que la migración no pierde la señal de
  V3.51 (con la tolerancia amplia, la honesta para un dato no certificado).
- `get_profile` devuelve `estimated_level` y `demonstrated_level`.
- Nueva `set_level_state(user_id, *, estimated_level, demonstrated_level,
  cefr_level=None)` (upsert). `set_cefr` pasa a ser un **wrapper** que actualiza
  el estimado sin pisar un `demonstrated_level` certificado.

### Caché y lectura en O(1) (`domain/profile.py`, `domain/vocabulary.py`)

- `get_profile_summary` escribe AMBOS niveles (`estimated_level` y
  `demonstrated_level or ""`) junto al `cefr_level` histórico, y expone
  `demonstrated_level` en el perfil (`schemas/profile.py`, aditivo y opcional,
  `None` mientras no haya certificación).
- Nuevo `_learner_level_state(user_id)`: lee la caché (fila única, O(1), sin
  recalcular el Student Model) y aplica `student_state.level_state`. `_learner_level`
  se conserva devolviendo el string del `floor_level`.
- `get_transfer_context` y el fallback de `submit_transfer_attempt` pasan
  `learner_level` **y** `learner_level_source` con la MISMA expresión (paridad
  GET↔POST del `context_id`, blindada por test).

### Difficulty Engine 2.0 (`services/difficulty.py`, nuevo — P1-02)

Módulo **puro** con:

- `DIFFICULTY_DIMENSIONS = ("lexical", "syntax", "discourse", "interaction")`
  (vocabulario canónico; `TRANSFER_DIFFICULTY_KEYS` pasa a ser su alias).
- `CEFR_CAPACITY`: capacidad de reto declarada por nivel y dimensión (1..5),
  **monótona no decreciente** y calibrada con el banco real (`interaction` crece
  más despacio en A1–B1). Tabla declarativa y calibrable.
- `capacity_for(level)` (copia; `{}` si no se reconoce).
- `challenge_vector(item_level, learner_level)`: **máximo por dimensión** entre la
  capacidad del ítem (techo lingüístico) y la del alumno (suelo de reto);
  generaliza el `max(item_index, learner_index)` de V3.51 sin mezclar escalas.
- `fit(context_vector, challenge, *, tolerance) -> {dimensions, distance,
  max_overshoot, within}`: `distance` = suma de distancias absolutas por
  dimensión; `max_overshoot` = mayor exceso sobre la capacidad;
  `within = max_overshoot <= tolerance`.
- `select_by_difficulty(pool, challenge, *, tolerance)`: conserva los contextos
  `within` y, entre ellos, los de **menor `distance`**; si ninguno lo está,
  **degrada a los de menor `distance` del pool** (nunca deja el pool vacío y
  nunca sirve el más difícil por defecto).
- `DIFFICULTY_TOLERANCE = 1` (suelo demostrado) y
  `DIFFICULTY_TOLERANCE_ESTIMATED = 2` (estimado/declarado/ausente), declaradas y
  calibrables. `tolerance_for(source)`.

### Recableado de la transferencia (`services/transfer.py`)

- `_difficulty_floor` y `_within_band` (escalares) se **sustituyen** por el motor:
  tras `_within_level` (techo del ítem, sin cambios) y `_filter_skill` (modalidad
  limitante) se calcula `challenge = challenge_vector(level, learner_level)` y se
  aplica `select_by_difficulty` con la tolerancia según `learner_level_source`. Si
  el reto está vacío, el pool no se filtra (comportamiento de V3.46/V3.47).
- `TRANSFER_DIFFICULTY_BAND` queda **deprecada** (declarada, sin consumidores).
- El retorno gana `difficulty_fit` (`{challenge, dimensions, distance,
  max_overshoot, within, tolerance}`) y `learner_level_source`; `difficulty`
  (escalar) y `difficulty_vector` se conservan por compatibilidad. Todos los
  retornos tempranos llevan las claves nuevas.
- **El TECHO lingüístico del ítem sigue mandando:** una unidad A1 con un alumno C2
  NO recibe contextos por encima de A1 (`_within_level`), blindado por test.

### Contratos (estrictamente aditivos)

- `TransferContextOut`: `learner_level_source: str = ""` y
  `difficulty_fit: dict = {}`.
- `LearningProfile`: `demonstrated_level: str | None = None`.
- `types/api.ts`: espejo opcional de los mismos campos (`DrillTransferContext.
  learner_level_source?`, `difficulty_fit?` y nuevo `DrillDifficultyFit`). Sin
  cambios de UI obligatorios.

## Verificación

- Backend: `ruff` limpio y `pytest` **2156 passed + 2 skipped en CI** (2158 passed
  en local con el modelo Whisper; +39: `test_student_state_v352.py`
  15 y `test_difficulty_engine_v352.py` 24; ajuste de
  `test_learner_level_raises_the_difficulty_floor` para comparar `difficulty_fit`
  en lugar de escalares); cero regresión de `test_context_skill_v350.py`,
  `test_transfer_cefr_v347.py`, `test_context_bank_v348.py`, `test_transfer_*`,
  `test_optimal_task_v339.py`, `test_learning_evidence_v336.py`,
  `test_profile.py` y `test_academy.py`.
- Frontend: `vitest` (**75 ficheros/641 tests**), `tsc --noEmit` y `npm run build` en verde.
- Scripts: `check_release_consistency.py` (**3.52.0**), `check_beta_v3.py` y
  `content_validation.py` exit 0.
- **CI 6/6 en verde** (run
  [34604654412](https://github.com/jvelasca/english-tutor/actions/runs/34604654412)
  sobre `23cbad7`): Release consistency, Backend (ruff + pytest), Frontend
  (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content
  validation. Los 2 skipped son `backend/tests/test_stt_asr_integration.py`
  (opt-in del modelo Whisper no descargado en el runner).

## Qué NO cambia

`transfer_state` ni sus umbrales, `context_signals`, `context_diversity`, el
scoring (`score_transfer_attempt`), FSRS, el contrato histórico de
`learning_evidence.skill`, `cefr_level` (compatibilidad) y la CONSTITUCIÓN
(R8/R9 sigue como propuesta abierta).

## Fuera de alcance (documentado)

`assessed_skill` → decisión del planner y `skill_priorities` → `select_task`
(requiere su propio diseño para no doble contar `written_production`; V3.55),
Sense Engine 2.0 (`surface→lemma→sense→semantic_fit`), `observed_difficulty`
persistido por evento, entrega oral real del transfer (audio+STT),
`expected_learning_value` / Adaptive Planner 2.0, Context Bank Family/Instance,
offline TTS y code splitting del frontend.

# Briefing de subagente — V3.53 (Learner Skill State 2.0 + `observed_difficulty`)

> **Estado:** incremento V3.53 **LISTO PARA LANZAR** (escrito 2026-09-11 sobre el
> árbol de `v3.52.2`, tag `v3.52.2` = commit `22ea6b4`). Es el primer candidato
> de la lista «V3.53+» que dejó abierta la auditoría externa (P1-02, diferido en
> V3.52.0/V3.52.1/V3.52.2). Antes de empezar, **verifica el estado real del
> árbol** (premisa 8): las líneas y los nombres de abajo se citan del árbol de
> `v3.52.2` y pueden haber cambiado.

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) del proyecto English
Tutor, con foco en el **Student Model** (`Student Skill State`), el **Evidence
Ledger** (`learning_evidence`) y el **Difficulty Engine 2.0**
(`services/difficulty.py`).

## Objetivo

Convertir el «estado del alumno» de un **nivel CEFR** (una etiqueta por origen:
`practice`/`estimated`/`demonstrated`, V3.52) en un **estado de capacidad
OBSERVADA por dimensión**, derivado de la dificultad de las tareas que el alumno
ha SUPERADO de verdad, y persistir esa dificultad **por evento**:

- **Parte A — `observed_difficulty` persistido por evento.** Hoy
  `learning_evidence.difficulty` guarda la dificultad LÉXICA del ítem
  (`lexicon.cefr_difficulty`, un escalar 1..6 del diccionario), **no** la
  dificultad de la TAREA servida. Un evento de transfer ya conoce el
  `difficulty_vector` del contexto del banco (`services/transfer.py`), pero lo
  tira: no se persiste. Persistirlo (vector canónico, aditivo) es la mitad del
  P1-02.
- **Parte B — Learner Skill State 2.0.** Con esa señal, derivar una **capacidad
  observada** por modalidad y dimensión (`skill × lexical/syntax/discourse/
  interaction`) y usarla como SUELO de reto del Difficulty Engine, conservadora
  (muestra espaciada mínima, nunca un acierto suelto) y con **cero regresión**
  cuando no hay datos.

Todo es **aditivo en el contrato y en el esquema** (dos columnas de BD),
determinista, sin LLM en la decisión (premisa 21) y sin tocar la escalera
`transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el
scoring (`score_transfer_attempt`) ni FSRS.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.13, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Premisa 6:** un incremento a la vez, con su release (`v3.53.0`).
- **Premisa 18:** docstrings en todo lo nuevo, explicando el PORQUÉ.
- **Arranque y gates** (desde la raíz, todo debe salir 0):
  - `cd backend; ..\backend\.venv\Scripts\python.exe -m ruff check .` y
    `..\backend\.venv\Scripts\python.exe -m pytest -q`;
  - lo mismo en `launcher/` (tiene su propio `pyproject.toml` y sus tests);
  - `cd frontend; npm test; npx tsc --noEmit; npm run build`;
  - `backend\.venv\Scripts\python.exe scripts\check_release_consistency.py`
    (**3.53.0**), `scripts\check_beta_v3.py`,
    `backend\.venv\Scripts\python.exe scripts\content_validation.py` (desde
    `backend/`) y `scripts\check_i18n_coverage.py`.

## Estado de partida verificado (árbol `v3.52.2`)

- **Ledger** `learning_evidence` (`repositories/db.py`): columna
  `difficulty REAL NOT NULL DEFAULT 0` (dificultad LÉXICA, escritas en
  `domain/vocabulary.py` como `difficulty=lexicon.cefr_difficulty(row)`).
  **No existe** ninguna columna con la dificultad de la tarea servida.
  `repositories/evidence.py` expone `record_evidence` / `record_evidence_bulk` /
  `list_evidence` y `summarize_by_target` (agregado SQL).
- **Difficulty Engine 2.0** (`services/difficulty.py`): `DIFFICULTY_DIMENSIONS`,
  `CEFR_CAPACITY` (= envelope monótono del banco, V3.52.2), `capacity_for`,
  `challenge_vector(item, learner)` = máximo por dimensión, `fit`,
  `select_by_difficulty`, `tolerance_for` (estricta SOLO si la fuente es
  `demonstrated`), `normalize_vector`, `normalize_level`. **No hay**
  serialización de vectores ni capacidad por dimensiones del ALUMNO.
- **Estado de nivel** (`services/student_state.py`): `LEVEL_SOURCES =
  (demonstrated, estimated, practice, none)`, `CERTIFIED_SOURCES =
  {demonstrated}`, `floor_level`, `level_state`, `is_certified`,
  `empty_state`. Es PURO.
- **Caché O(1)** `learning_profile` (`repositories/db.py`): `cefr_level`
  (legacy), `estimated_level`, `demonstrated_level`. La escribe
  `domain/profile.get_profile_summary` → `_compute_profile` (que llama a
  `academy.build_student_model`) vía `profile_repo.set_level_state`; la lee
  `repositories/profile.get_profile`.
- **Camino caliente del drill** (`domain/vocabulary.py`):
  `_learner_level_state(user_id)` lee `learning_profile` (fila única, O(1),
  **sin recalcular el Student Model**) y llama a `student_state.level_state`;
  su resultado viaja a `transfer.context_for(..., learner_level=,
  learner_level_source=)` en el GET (`get_transfer_context`) y en el POST del
  transfer, con **paridad GET↔POST** garantizada por test.
- **Reto en el banco** (`services/transfer.py`): `_challenge_and_tolerance`
  (llama a `difficulty.challenge_vector` + `difficulty.tolerance_for`),
  `_difficulty_fit_for`, `context_for(...)` (devuelve `difficulty_vector`,
  `cefr`, `difficulty_fit`, `learner_level`, `learner_level_source`…),
  `_CONTEXTS_BY_ID`, y helpers puros que aceptan dict o id
  (`context_id_for`, `context_attributes`, `context_skills`,
  `context_dimensions`, `difficulty_from_vector`).
- **Agregados de evidencia** (`services/evidence.py`): `summarize_evidence`
  (puro) y `empty_summary` comparten contrato con `summarize_by_target` (SQL) —
  **paridad pura↔SQL verificada por test**, y es un invariante del proyecto. Ya
  existen `skill_attempts`, `skill_successes`, `skill_independent_successes`,
  `skill_mean_response_time_ms`, `assessed_skill_attempts/successes`,
  `context_signals`, `recency_signals`, `with_transfer_state`.
- **Transfer registra**: `_record_transfer_evidence` escribe
  `skill="spontaneous_use"`, `assessed_skill=written_production` (task
  semantics), `activity_id="drill:transfer"`, `context_id`, `condition`,
  `difficulty=lexicon.cefr_difficulty(row)`.

## Decisiones de alcance (cerradas)

1. **La dificultad que se persiste es la de la TAREA SERVIDA, no la del ítem.**
   Y se persiste como **vector canónico**, no como media escalar: colapsar
   dimensiones es exactamente el P1 que cerraron V3.52/V3.52.2
   (`(5,1,5,1)` y `(3,3,3,3)` no pueden volver a ser indistinguibles).
2. **Solo se atribuye a modalidades canónicas** (`LEXICAL_SKILLS`), usando
   `assessed_skill` y cayendo a `skill` cuando aquel está vacío — misma
   convención que los histogramas por modalidad ya existentes.
3. **Muestra espaciada mínima.** Una dimensión solo declara capacidad observada
   con `OBSERVED_MIN_SAMPLES` (2) éxitos **y** `OBSERVED_MIN_DAYS` (2) días
   naturales distintos: un acierto suelto no asciende (mismo rigor que
   `independent_success_days`/`recall_rung_days`). Declarado y calibrable.
4. **La capacidad observada es una COTA, no un nivel.** `learner_capacity[dim] =
   max(capacity_for(floor_level)[dim], observed_capacity[dim])`: sube el reto
   SOLO en las dimensiones demostradas y **nunca** baja el suelo declarado. No se
   reescribe `CEFR_CAPACITY` (tabla del BANCO, ver P2-01 de V3.52.2).
5. **La fuente `observed` entra en `LEVEL_SOURCES` entre `demonstrated` y
   `estimated`**: `demostrado > observado > estimado > declarado > ninguno`. Una
   certificación con retención sigue siendo la garantía más fuerte; el
   rendimiento observado es más fuerte que una estimación.
   `CERTIFIED_SOURCES` **no cambia**: solo `demonstrated` usa la tolerancia
   estricta; `observed` usa el margen amplio (menos confianza que una
   certificación). Documentarlo en el docstring.
6. **Nivel equivalente, para no inventar un dialecto.** `observed_level` es el
   mayor nivel CEFR cuya `CEFR_CAPACITY` (envelope del banco) queda **dominada**
   por la capacidad observada en las dimensiones CON muestra; sin muestra no
   bloquea pero se reporta (cobertura/explicabilidad). Así `challenge_vector` y
   `tolerance_for` siguen funcionando sin cambios.
7. **O(1) en el camino caliente.** La capacidad observada se DERIVA en el
   refresco del perfil (`get_profile_summary`) y se **cachea** en
   `learning_profile`; el drill la lee en fila única. Prohibido agregar el ledger
   léxico dentro de `get_transfer_context`/POST.
8. **Cero regresión con datos ausentes.** Con `observed_capacity` vacío (filas
   legacy, o alumno sin muestra suficiente) **todo** —selección, payload y
   tolerancia— es IDÉNTICO a V3.52.2. Se prueba de forma exhaustiva, no por
   muestreo.
9. **El planner NO consume esto todavía.** `planner.skill_signals`/`select_task`
   siguen como están: cablearlo ahora es el candidato **P1-03 (Planner 2.0 /
   `expected_learning_value`)** y tiene su propio diseño (incluido el doble
   conteo de `written_production`). Fuera de alcance.
10. **Alternativas rechazadas (documentar en el docstring):** persistir la media
    escalar del vector (§1); derivar el estado en caliente dentro del drill
    (sería por ÍTEM, no por alumno, y rompe O(1)); ascender con un solo éxito
    (§3); dar tolerancia estricta a `observed` (§5); tocar `CEFR_CAPACITY`(§4).

## Archivos clave

**Parte A — persistencia**

- `backend/services/difficulty.py` — nuevos puros `format_vector` (canónico:
  orden `DIFFICULTY_DIMENSIONS`, `dim:load` separados por `,`) y `parse_vector`
  (tolerante: entradas no canónicas/fuera de rango se ignoran; nunca lanza).
- `backend/services/transfer.py` — nuevo puro `context_difficulty(context)`
  (dict o id → vector normalizado, espejo de `context_skills`).
- `backend/repositories/db.py` — columna aditiva
  `learning_evidence.observed_difficulty TEXT NOT NULL DEFAULT ''` (CREATE TABLE
  + bucle `PRAGMA table_info` idempotente).
- `backend/repositories/evidence.py` — `record_evidence`,
  `record_evidence_bulk` y `list_evidence` aceptan/devuelven
  `observed_difficulty`.
- `backend/domain/vocabulary.py` — `_record_transfer_evidence` escribe el vector
  del contexto SERVIDO (`observed_difficulty=difficulty.format_vector(
  transfer.context_difficulty(context_id))`); el resto de drills lo dejan `''`
  (documentado: solo el banco de contextos declara vector).

**Parte B — estado y suelo**

- `backend/services/evidence.py` — puro `observed_signals(rows)` (por modalidad
  canónica y dimensión: `samples`, `days`, `capacity`) y sus claves en
  `summarize_evidence` + `empty_summary`; `repositories/evidence.py`
  (`summarize_by_target`) lee las filas necesarias y **delega en la MISMA
  función pura** (paridad por construcción) + agregado por usuario para el
  perfil.
- `backend/services/learner_skill.py` — **núcleo nuevo y puro**:
  `OBSERVED_MIN_SAMPLES`, `OBSERVED_MIN_DAYS`, `observed_capacity`,
  `level_from_capacity`, `learner_capacity(floor_level, observed)`,
  `empty_state`.
- `backend/services/student_state.py` — `LEVEL_SOURCES` con `observed`;
  `floor_level`/`level_state` aceptan `observed_cefr`/`observed_capacity`.
- `backend/repositories/db.py` — columnas aditivas
  `learning_profile.observed_level` / `observed_capacity` (idempotentes).
- `backend/repositories/profile.py` — `set_level_state(..., observed_level=,
  observed_capacity=)` y `get_profile` devuelve ambas.
- `backend/domain/profile.py` — `_compute_profile`/`get_profile_summary`
  derivan la capacidad observada (vía el agregado del ledger léxico) y la
  persisten.
- `backend/domain/vocabulary.py` — `_learner_level_state` lee las columnas
  nuevas y devuelve `learner_capacity`; GET/POST pasan
  `learner_capacity=...` a `context_for`.
- `backend/services/transfer.py` — `context_for(..., learner_capacity=None)`,
  `_challenge_and_tolerance`/`_difficulty_fit_for` con el override de capacidad
  (máximo por dimensión con `capacity_for(item_level)`).
- `backend/schemas/learning.py` y `backend/schemas/vocabulary.py` +
  `frontend/src/types/api.ts` — campos aditivos (`observed_capacity`,
  `learner_capacity`), opcionales en el espejo TS.
- Tests nuevos: `backend/tests/test_observed_difficulty_v353.py` y
  `backend/tests/test_learner_skill_v353.py` (+ paridad y no-regresión).

## Tarea detallada

1. `format_vector`/`parse_vector` puros con round-trip y tolerancia a basura.
2. Migración aditiva de `learning_evidence.observed_difficulty` y de
   `learning_profile.observed_level`/`observed_capacity`.
3. Escritura del vector en el evento de transferencia (y `''` en el resto),
   documentando la semántica de `''` = no declarada.
4. `context_difficulty` puro en `transfer.py` + test de equivalencia
   dict↔id↔`_CONTEXTS_BY_ID`.
5. `observed_signals` puro (muestra/días por modalidad y dimensión, atribución
   por `assessed_skill or skill`) + integración en `summarize_evidence` y en el
   agregado SQL con **paridad exacta**.
6. `services/learner_skill.py` (capacidad → nivel equivalente → capacidad del
   alumno) puro, determinista y que nunca lanza.
7. `student_state` con `observed` en la política de suelo y su docstring.
8. Derivación + caché en `get_profile_summary`; lectura O(1) en
   `_learner_level_state`; paso por contrato hasta `context_for` (GET y POST).
9. Contratos aditivos backend + espejo TS (opcionales).
10. Tests de aceptación, paridad pura↔SQL y **no-regresión exhaustiva**.

## Criterios de aceptación

- `format_vector(parse_vector(x)) == x` para todo vector canónico y
  `parse_vector` devuelve `{}` (nunca lanza) con entradas vacías/basura/valores
  fuera de 1..5.
- Un evento de transfer persiste el `difficulty_vector` del contexto SERVIDO
  (no el del ítem, no una media); los demás drills dejan `''`.
- `observed_capacity` NO asciende con un solo éxito ni con dos éxitos el MISMO
  día; sí con 2 éxitos en 2 días naturales distintos.
- `level_from_capacity` es conservador: nunca declara un nivel cuya envolvente
  no esté dominada en las dimensiones con muestra (caso A2: `directions`/
  `shopping`, `interaction` 3, sobreviven a la tolerancia estricta).
- `floor_level` respeta `demostrado > observado > estimado > declarado >
  ninguno`; un demostrado sigue ganando a un observado superior.
- **No-regresión: con `observed_capacity` vacío, las 48 combinaciones (nivel de
  ítem × nivel de alumno, 49 menos la que no reconoce ningún nivel) × 20
  contextos del banco eligen EXACTAMENTE el mismo `context_id`, con el mismo
  `difficulty_fit` y la misma tolerancia que en V3.52.2.**
- Paridad pura↔SQL exacta para `observed_capacity`/`observed_samples`.
- Ninguna consulta extra en el camino caliente del drill (sigue siendo la fila
  única de `learning_profile`); paridad GET↔POST del `context_id` intacta.
- Cero regresión de `test_difficulty_engine_v352.py`,
  `test_student_state_v352.py`, `test_transfer_v343.py`,
  `test_transfer_evidence_v347.py`, `test_learning_evidence_v336.py`,
  `test_planner_v338.py`, `test_optimal_task_v339.py`,
  `test_context_bank_v348.py`, `test_context_skill_v350.py`,
  `test_task_semantics_v351.py`, `test_user_profile.py` y `test_profile.py`.

## Restricciones

- No tocar `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` ni FSRS.
- No tocar `CEFR_CAPACITY` (es la tabla del BANCO, recalibrada en V3.52.2) ni
  `tolerance_for` salvo añadir la fuente `observed` con el margen amplio.
- No introducir LLM, reloj propio ni aleatoriedad en la decisión (`occurred_at`
  ya viene en las filas).
- Migración estrictamente aditiva e idempotente; las filas legacy quedan en `''`
  y NO alimentan ninguna capacidad observada (no se inventa evidencia).
- El planner no consume la capacidad observada en este incremento.
- `ruff`/`pytest`/`vitest`/`tsc`/`build` en verde y `check_release_consistency`
  en `3.53.0`.

## Salida esperada

Diff del backend + tipo del frontend + tests + `release-notes-v3.53.0.md` y
actualización de `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md` y
`agentes/README.md`. Subir `BUILD` en `backend/config.py` (autoincremental) y
`VERSION = "3.53.0"` en backend + `package.json`/`package-lock.json`.

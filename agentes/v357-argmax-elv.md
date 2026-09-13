# Briefing de subagente — V3.57 (Planner 3.0: argmax `(skill, actividad)` sobre ELV)

> **Estado:** incremento V3.57 **EJECUTADO** (2026-09-13, release **v3.57.0**),
> escrito sobre el árbol de `v3.56.0` (commit `0c33709`). Es el candidato que
> V3.56 dejó **explícitamente diferido**: hasta V3.56 el planner **ordena** (ELV)
> pero la TAREA la decide la cascada de razones `select_task` (V3.39). V3.57 hace
> que el planner **elija** la tarea por **argmax de ELV** cuando hay estado del
> alumno. Resultado verificado: `pytest` **2266 passed**, `ruff` limpio, launcher
> **75 passed**, `tsc` OK, `vitest` **651**, `check_release_consistency`
> **3.57.0**; ver `release-notes-v3.57.0.md`. **Histórico.**
> Antes de reutilizar este briefing, **verifica el estado real del árbol**
> (premisa 8): los nombres y las líneas de abajo se citan del árbol de `v3.56.0`
> y pueden haber cambiado.

## Rol

Ingeniero de backend del proyecto English Tutor, con foco en el **planner del
repaso léxico** (`services/planner.py`), la **decisión de tarea del ítem**
(`services/lexicon.py`) y el **Student Skill State** de V3.52–V3.56
(`services/learner_skill.py`, `services/difficulty.py`, `services/evidence.py`,
`domain/learner_state.py`).

## Objetivo

Cerrar la segunda mitad del Planner 2.0: el ELV de V3.56 **puntúa y ordena**, pero
la actividad la seguía eligiendo la **cascada de razones** (`select_task`). V3.57
introduce el **argmax `(skill, actividad)` sobre ELV**: entre las tareas
**pedagógicamente admisibles** (las que la cascada ya sabía justificar), elige la
de mayor valor esperado de aprendizaje. Es la diferencia entre "¿cuánto urge
repasar?" y "¿qué conviene practicar AHORA?".

```text
candidatas   = razones admisibles hoy (error_prone, skill_gap, slow_recall, transfer_gap)
ELV(cand)    = desirability(P(éxito | skill)) × skill_priorities(signals)[skill]
tarea        = argmax ELV(cand)   ← NUEVO (solo con capacidad del alumno)
```

**Alcance CERRADO con el gerente (opción conservadora):** el argmax **solo
decide cuando hay estado del alumno** (capacidad por modalidad que produce un
margen comparable); **sin él, degradación neutra EXACTA a `select_task`**, de modo
que la tarea servida hoy sin perfil es byte a byte la de V3.56.0. El incremento
incluye resolver la **deuda de planner** declarada en `PLAN.md`:
`skill_priorities` → `select_task` (el vector completo de prioridad por modalidad
pasa a alimentar la decisión) y el **doble conteo de `written_production`**
(política declarada: el EJE manda el valor y el hueco; el CANAL EVALUADO manda la
capacidad). **SIN migración de BD y SIN cambios de UI.**

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.13, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`), lanzador Tkinter
  (`launcher/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia ni planifica.
- **Premisa 12:** cada pieza va precedida de un test; tests rápidos y sin red.
- **Premisa 6:** un incremento a la vez, con su release (`v3.57.0`).
- **Premisa 10/18:** responsabilidades claras y docstrings que expliquen el PORQUÉ
  de cada tabla y umbral.
- **Arranque y gates** (todo debe salir 0):
  - `cd backend; ..\backend\.venv\Scripts\python.exe -m ruff check .` y
    `..\backend\.venv\Scripts\python.exe -m pytest -q`;
  - lo mismo en `launcher/` (tiene su propio `pyproject.toml` y sus tests);
  - `cd frontend; npm test; npx tsc --noEmit; npm run build`;
  - desde la raíz: `backend\.venv\Scripts\python.exe scripts\check_release_consistency.py`
    (**3.57.0**), `backend\.venv\Scripts\python.exe scripts\check_beta_v3.py`,
    `backend\.venv\Scripts\python.exe backend\scripts\content_validation.py` y
    `backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py`.

## Estado de partida verificado (árbol `v3.56.0`)

- **Planner** (`services/planner.py`, puro): `PRIORITY_WEIGHTS` declarados;
  `planned_signals`; `priority_score`; `skill_signals`/`skill_priority`/
  `skill_priorities`/`limiting_skill` (**hoy solo los consume la explicación y el
  fallback, NO la cascada**); `SUCCESS_BY_MARGIN`/`success_probability`/
  `capacity_margin`/`desirability`/`expected_learning_value` (V3.56, con
  `value = priority_score(signals)`); la cascada `select_task` (`error_prone` →
  `skill_gap` → `slow_recall` → `transfer_gap`) con `ACTIVITY_FOR_SKILL`,
  `ACTIVITY_SUPPORT_LEVEL`, `_task`; `explain_priority(signals, reason,
  learning_value=None)`.
- **Ítem de cola** (`services/lexicon.py`): `recommend_review_activity(row,
  competence, now, evidence)` resuelve la escalera y, si hay directriz, delega en
  `planner.select_task` (línea ~588); `_task_decision(matrix, evidence, signals,
  recommendation)` (línea ~759) vuelve a delegar en `select_task`; `_learning_value`
  (línea ~785) calcula el ELV del ítem con el suelo de la modalidad del EJE
  (`task["skill"]`) y `learner_skill.skill_capacity`. `review_queue_item` pasa
  `learner_state` a `_learning_value` pero **no** a `_task_decision`.
- **Semántica de tarea** (`services/task_semantics.py`, puro): `TASK_SEMANTICS`
  separa `target_skill` (eje) / `assessed_skill` (lo que la entrega MIDE) /
  `assessment_mode` / `evidence_skill` (lo que persiste el ledger). Clave del
  doble conteo: `transfer` tiene eje `spontaneous_use` pero **canal evaluado
  `written_production`** (su entrega es texto); `write` es eje y canal
  `written_production`; `sentence`/`word` son `spoken_production`; `recall` es
  `recall`.
- **Capacidad** (`services/evidence.observed_signals`): atribuye la carga
  superada por **`assessed_skill` con caída a `skill`**, así que los éxitos de
  `transfer` acreditan capacidad de `written_production` (el canal que mide), NO
  de `spontaneous_use` (el eje). El resumen `summarize_evidence` también emite
  `assessed_skill_attempts`/`assessed_skill_successes`, que **hoy no consume
  nadie**.
- **Estado del alumno en O(1)**: `domain/learner_state.learner_level_state(user_id)`
  (V3.56), compartido por cola y drill; `student_state.skill_floor(state, skill)`
  da el suelo de una modalidad; `learner_skill.skill_capacity(floor,
  observed_skill_capacity, skill)["capacity"]` da la capacidad por dimensión.
- **Contrato de la cola**: `schemas/learning.ReviewQueueItem` con `priority`,
  `signals`, `why`, `limiting_skill`, `skill_priorities`, `task`,
  `expected_learning_value`, `learning_value`… y su espejo en
  `frontend/src/types/api.ts`. **No cambia en V3.57** (el argmax solo cambia el
  VALOR de `task`, no su forma).

## Decisiones de alcance (CERRADAS con el gerente)

1. **Argmax SOLO con estado del alumno.** Sin `learner_state` (o sin ninguna
   candidata con margen comparable) la decisión es **exactamente** `select_task`:
   invariante de no-regresión, probado por igualdad literal, no por aproximación.
2. **Candidatas = las razones ADMISIBLES de hoy, no un producto cartesiano.** El
   argmax solo arbitra entre las tareas que la cascada ya sabe justificar
   (`error_prone`→`recall`; `skill_gap`→la/s modalidad/es de producción sin éxito;
   `slow_recall`→`recall`; `transfer_gap`→`transfer`). **No** se inventan tareas:
   ni transferencia sin base, ni producción sin logro previo, ni escritura sin
   reconocimiento. Si solo hay una candidata, el argmax devuelve esa (mismo
   resultado que la cascada).
3. **Una candidata SIN margen comparable no participa.** `p = 0.5` da
   `desirability = 1.0` (el MÁXIMO): dejar competir a una modalidad sin datos la
   premiaría por ignorancia. Solo entran las candidatas con margen `!= None`; si
   ninguna lo tiene → `select_task` exacto.
4. **`value` por modalidad = `skill_priorities(signals)[skill]`** (mismos pesos
   declarados, señales por modalidad). Resuelve la deuda `skill_priorities →
   select_task`. El `expected_learning_value` de V3.56 conserva su `value =
   priority_score(signals)` por defecto: el ORDEN de la cola no cambia.
5. **Resolución del doble conteo de `written_production`.** Política declarada:
   - el **EJE** (`skill`, la segmentación `skill_successes` del planner) manda el
     VALOR y el HUECO: `transfer` compite como `spontaneous_use` y acredita su
     hueco de transferencia;
   - el **CANAL EVALUADO** (`task_semantics.assessed_skill_for(activity)`) manda
     la CAPACIDAD del margen: `transfer` y `write` LEEN la misma capacidad de
     `written_production` **sin sumarla** dos veces. Se expone `capacity_skill` en
     el payload del ELV (aditivo) y se prueba que un éxito de transfer sube la
     capacidad de `written_production` pero **no** la prioridad de eje de
     `written_production`.
6. **SIN migración de BD ni contrato nuevo.** Todo se deriva en memoria; `task`
   mantiene su forma `{skill, activity, reason, support_level}` y el ELV del ítem
   sigue en `expected_learning_value`/`learning_value`.
7. **`select_task` NO se toca.** Se conserva literal como el camino neutro y como
   vocabulario de razones; se añade `select_task_by_elv` **encima**.

## Diseño del núcleo (qué tiene que existir y con qué contrato)

### A. Piezas puras nuevas en `services/planner.py`

```python
CAPACITY_FALLBACK = ""   # canal evaluado no reconocido → se usa el eje

def capacity_skill(skill: object) -> str:
    """Modalidad cuyo CANAL EVALUADO mide esta modalidad de EJE (V3.57, pura)."""

def task_candidates(matrix: dict | None, evidence: dict | None) -> list[dict]:
    """Tareas ADMISIBLES hoy (skill/activity/reason/support_level), orden canónico."""

def select_task_by_elv(
    matrix, evidence, signals, *, capacity_by_skill=None, task_difficulty=None
) -> dict:
    """argmax (skill, activity) por ELV; sin margen → select_task EXACTO (V3.57)."""
```

- `capacity_skill(skill)` — `skill` (eje) → actividad (`ACTIVITY_FOR_SKILL`) →
  `task_semantics.assessed_skill_for(activity)`, con caída al propio eje si no se
  reconoce. `spontaneous_use → written_production`; `sentence`/`spoken_production
  → spoken_production`; `write`/`written_production → written_production`;
  `recall → recall`. Nunca lanza.
- `task_candidates(matrix, evidence)` — lista determinista (sin duplicados) en
  orden canónico, con las MISMAS guardas que la cascada:
  - `recall` con razón `error_prone` si `error_prone(evidence)`, o `slow_recall`
    si `is_slow_recall(evidence)` (solo si alguna de las dos aplica);
  - cada modalidad de `skill_gaps(evidence)` accionable (`ACTIVITY_FOR_SKILL`) y
    con `matrix["production"]`, con razón `skill_gap`;
  - `spontaneous_use` con razón `transfer_gap` si `transfer_gap(evidence)`.
  Lista vacía sin evidencia; nunca lanza.
- `expected_learning_value(..., value=None, capacity_skill="")` — dos parámetros
  **opcionales** (aditivos): `value` por defecto `None → priority_score(signals)`
  (V3.56 intacto); el payload gana `capacity_skill` (informativo). El resto igual.
- `select_task_by_elv(...)`:
  1. `candidates = task_candidates(matrix, evidence)`;
  2. para cada candidata, `cap = capacity_by_skill.get(capacity_skill(s["skill"]))`
     y `value = skill_priorities(signals).get(s["skill"], priority_score(signals))`;
     se calcula `expected_learning_value(..., learner_capacity=cap, value=value)`;
  3. **solo compiten las de `margin != None`**; si no queda ninguna →
     `return select_task(matrix, evidence, signals)` (exacto);
  4. **argmax** por `expected_learning_value`, desempate **estable** por el orden
     canónico de `task_candidates` (no por diccionario);
  5. devuelve la candidata (`{skill, activity, reason, support_level}`).

### B. Cableado en el ítem (`services/lexicon.py`)

- Helper puro `_capacity_by_skill(learner_state) -> dict[str, dict]`: para cada
  modalidad canónica, `skill_capacity(skill_floor(state, skill),
  state["observed_skill_capacity"], skill)["capacity"]`; `{}` sin estado. Se
  calcula **una vez** por ítem.
- `task_difficulty` (`difficulty.declared_difficulty(cefr_difficulty(row))`) se
  calcula una vez en `review_queue_item` y se pasa a las dos funciones.
- `recommend_review_activity(..., capacity_by_skill=None, task_difficulty=None)` y
  `_task_decision(..., capacity_by_skill=None, task_difficulty=None)` llaman
  **ambas** a `planner.select_task_by_elv` con los MISMOS argumentos, de modo que
  la actividad del ítem (`item["activity"]`) y su `task["activity"]` no puedan
  divergir (lo fija `test_optimal_task_v339.py`).
- `_learning_value` reutiliza el MISMO `capacity_by_skill` y el MISMO
  `task_difficulty`, y usa `capacity_skill(task["skill"])` para el margen. Sin
  estado, `capacity_by_skill = {}` → neutro exacto.
- `review_queue_item` sigue recibiendo `learner_state` (V3.56) y ahora lo propaga
  a la decisión de tarea.

### C. Contrato

- **Sin cambios**: `task` conserva su forma; `learning_value` gana solo
  `capacity_skill` (aditivo y opcional en el espejo TS, que no se toca si no hace
  falta). Si se toca `frontend/src/types/api.ts`, será un campo opcional nuevo.

## Archivos clave

- `backend/services/planner.py` — núcleo puro (A).
- `backend/services/lexicon.py` — cableado (B): `_capacity_by_skill`,
  `recommend_review_activity`, `_task_decision`, `_learning_value`.
- `backend/services/task_semantics.py` — se **consume** (`assessed_skill_for`); no
  se toca.
- `backend/services/learner_skill.py`, `backend/services/difficulty.py`,
  `services/evidence.py` — se consumen tal cual; no se tocan.
- `backend/tests/test_planner_argmax_v357.py` — tests nuevos (aceptación,
  no-regresión exacta y doble conteo).
- `backend/config.py` + `frontend/package.json`/`package-lock.json` — bump
  `3.56.0 → 3.57.0`.
- `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md`, `agentes/README.md` y
  `release-notes-v3.57.0.md` — cierre documental.

## Tarea detallada

1. Tests-first de `capacity_skill`, `task_candidates`, `select_task_by_elv` y su
   **degradación neutra exacta** (igualdad con `select_task`).
2. `expected_learning_value` con `value`/`capacity_skill` opcionales (V3.56
   intacto por defecto).
3. Núcleo puro (A) con docstrings que expliquen el PORQUÉ de cada guarda y del
   desempate.
4. Cableado (B) en las DOS rutas de decisión + `_learning_value`, sin tocar
   `select_task` ni el orden de la cola.
5. Test de doble conteo (política eje/canal) y de consistencia
   `item["task"]["activity"] == item["activity"]`.
6. No-regresión de las baterías de planner/cola/transfer/drill.
7. Cierre de release (bump + documentación + gates) y commit.

## Criterios de aceptación

- `capacity_skill("spontaneous_use") == "written_production"`,
  `capacity_skill("recall") == "recall"`, `capacity_skill("nope") == "nope"` (cae
  al eje, no inventa) y nunca lanza.
- `task_candidates` respeta las guardas: sin evidencia → `[]`; `error_prone` →
  `recall`; `skill_gap` con producción oral y escrita pendientes → ambas
  candidatas; `transfer_gap` → `spontaneous_use`; orden canónico estable.
- **Sin `capacity_by_skill` (o sin estado), `select_task_by_elv(m, e, s)` es
  IGUAL a `select_task(m, e, s)`** en toda la matriz de casos probados (incluido
  basura: `None`, `{}`, tipos raros).
- Con capacidad, el argmax elige la candidata en la **zona de desarrollo próximo**
  (margen `0`) frente a una por encima (margen `-2`) y una por debajo (margen
  `+2`); con ELV empatado gana la primera del orden canónico.
- `value` por candidata = `skill_priorities(signals)[skill]` (deuda 1 resuelta):
  un cambio de prioridad por modalidad cambia la tarea elegida.
- Doble conteo (deuda 2): un éxito de `transfer` sube la capacidad de
  `written_production` (`observed_signals`) y **no** la prioridad de eje de
  `written_production`; `transfer` y `write` LEEN la misma capacidad.
- `review_queue_item` sin `learner_state` conserva `task`, `priority`, `signals`,
  `why` y `skill_priorities` de V3.56 (no-regresión); con estado, `task` se elige
  por ELV y `item["task"]["activity"] == item["activity"]`.
- `GET /api/learning/review` sirve lo mismo sin romper el contrato ni el
  `due_count`.
- Cero regresión de `test_planner_v338.py`, `test_optimal_task_v339.py`,
  `test_transfer_v340.py`, `test_review_queue_v335.py`,
  `test_expected_learning_value_v356.py` y las baterías de drill.

## Restricciones

- **No** tocar `select_task`, `ACTIVITY_FOR_SKILL`, `ACTIVITY_SUPPORT_LEVEL`,
  `EVIDENCE_REASON_ORDER` ni la cascada: es el camino neutro.
- **No** reordenar la cola ni cambiar `expected_learning_value` por defecto (el
  `value` por modalidad es SOLO para el argmax de la tarea).
- **No** proponer candidatas fuera de las razones admisibles de hoy (nada de
  transferencia sin base ni producción sin logro).
- **No** tocar `PRIORITY_WEIGHTS` ni los umbrales de
  `transfer_state`/`context_signals`/`context_diversity`/`CEFR_CAPACITY`/
  `DIFFICULTY_TOLERANCE*`/`SUPPORT_DISCOUNT_STEPS` ni el scoring ni FSRS.
- **No** añadir migraciones ni columnas; PROHIBIDO agregar el ledger al camino
  caliente.
- **No** introducir LLM, reloj propio ni aleatoriedad: todo puro y determinista.
- Vigila el tamaño de las líneas (`ruff`, 88 columnas) y no dejes código muerto.

## Salida esperada

Diff del backend + tests, más `release-notes-v3.57.0.md` y actualización de
`CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md` y `agentes/README.md`;
`VERSION = "3.57.0"` en `backend/config.py` y las mismas versiones en
`frontend/package.json` y `frontend/package-lock.json` (sin desfase: lo verifica
`scripts/check_release_consistency.py`). Verifica `ruff`, `pytest`, `tsc`,
`vitest`, `build` y los scripts de contenido/gates antes de dar el incremento por
cerrado, y deja este briefing en el árbol como histórico del método.

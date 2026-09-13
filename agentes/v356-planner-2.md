# Briefing de subagente — V3.56 (Planner 2.0: `expected_learning_value`)

> **Estado:** incremento V3.56 **LISTO PARA LANZAR** (escrito 2026-09-13 sobre el
> árbol de `v3.55.0`, tag `v3.55.0` = commit `afb13ff`). Es el candidato
> **P1-03** de la lista «V3.53+» que dejó abierta la auditoría externa de V3.52
> (Planner 2.0 / Expected Learning Value), ya sin los P2 de V3.53.1 encima
> (**P2-01 y P2-02 cerrados en V3.55.0**). Antes de empezar, **verifica el estado
> real del árbol** (premisa 8): los nombres y las líneas de abajo se citan del
> árbol de `v3.55.0` y pueden haber cambiado.

## Rol

Ingeniero de backend (+ espejo del contrato en frontend) del proyecto English
Tutor, con foco en el **planner del repaso léxico** (`services/planner.py`), la
**cola de repaso** (`domain/review.py`, `services/lexicon.py`) y el **Student
Skill State** que V3.53–V3.55 dejaron montado (`services/learner_skill.py`,
`services/evidence.py`, `services/difficulty.py`).

## Objetivo

Convertir la prioridad del planner de una **suma de urgencia** en un **VALOR
ESPERADO DE APRENDIZAJE** (`expected_learning_value`), la pieza que hoy no
existe: el planner sabe cuánto urge repasar algo, pero **no predice si el alumno
podrá con la tarea**. El ELV combina por primera vez las dos mitades:

```text
P(éxito)        ← capacidad del alumno vs. dificultad declarada de la tarea (NUEVA)
V( valor)       ← valor pedagógico declarado de la tarea (el priority_score actual)
ELV             = dificultad_deseable(P) × V          (máximo en P ≈ 0.5)
```

y la cola de repaso pasa a ordenarse por ELV. Es el núcleo **puro** del Planner
2.0: **NO** se reescribe `select_task` (la cascada de razones se queda intacta),
**NO** se decide todavía la tarea por argmax `(skill, actividad)` (eso es V3.57),
**NO** hay migración de BD y **NO** se toca la escalera `transfer_state`, sus
umbrales, `context_signals`, `context_diversity`, el scoring, FSRS ni el
Difficulty Engine (tablas y gates de V3.52/V3.54/V3.55 intactos). Determinista,
sin LLM (premisa 21).

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.13, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`), lanzador Tkinter
  (`launcher/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada pieza va precedida de un test; tests rápidos y sin red.
- **Premisa 6:** un incremento a la vez, con su release (`v3.56.0`).
- **Premisa 10/18:** responsabilidades claras y docstrings que expliquen el
  PORQUÉ de cada tabla y umbral.
- **Arranque y gates** (todo debe salir 0):
  - `cd backend; ..\backend\.venv\Scripts\python.exe -m ruff check .` y
    `..\backend\.venv\Scripts\python.exe -m pytest -q`;
  - lo mismo en `launcher/` (tiene su propio `pyproject.toml` y sus tests);
  - `cd frontend; npm test; npx tsc --noEmit; npm run build`;
  - desde la raíz: `backend\.venv\Scripts\python.exe scripts\check_release_consistency.py`
    (**3.56.0**), `backend\.venv\Scripts\python.exe scripts\check_beta_v3.py`,
    `backend\.venv\Scripts\python.exe backend\scripts\content_validation.py` y
    `backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py`.

## Estado de partida verificado (árbol `v3.55.0`)

- **Planner** (`services/planner.py`, puro): `PRIORITY_WEIGHTS` declarados
  (`forgetting` 0.35, `gap` 0.30, `weakness` 0.20, `support` 0.10, `latency`
  0.05); `planned_signals(evidence, matrix, retrievability=)`; `priority_score`
  (suma ponderada); `skill_signals`/`skill_priority`/`skill_priorities`/
  `limiting_skill`; la cascada `select_task` (`error_prone` → `skill_gap` →
  `slow_recall` → `transfer_gap`) con `ACTIVITY_FOR_SKILL`,
  `ACTIVITY_SUPPORT_LEVEL`, `_task`; `explain_priority(signals, reason)`
  (frases cortas en inglés); `evidence_reason` (fachada de `select_task`).
  **No existe ninguna predicción de éxito.**
- **Cola de repaso** (`domain/review.py`): `get_review_queue(user_id, limit)`
  lee TODAS las cartas vencidas (`REVIEW_QUEUE_CANDIDATE_LIMIT = 500`), resume la
  evidencia por palabra (`evidence_repo.summarize_by_target`), construye los
  ítems con `lexicon.review_queue_item` (dos pasadas: ranking global y luego
  re-resolución de lo SERVIDO con `available_cues`) y ordena con
  `_queue_sort_key = (-priority, retrievability, word)`.
  **Hoy NO lee `learning_profile`: la cola no conoce el estado del alumno.**
- **Ítem de cola** (`services/lexicon.review_queue_item`, puro): recibe `row`,
  `card`, `now`, `evidence`, `available_cues`, `unit_surfaces`; deriva
  `recommend_review_activity` (hueco → escalera, con `planner.select_task` como
  decisión dirigida por evidencia), `_task_decision` (`{skill, activity, reason,
  support_level}`), `signals`, `priority`, `why`, `limiting_skill`,
  `skill_priorities`, `competence`. **No conoce la capacidad del alumno.**
- **Estado del alumno en O(1)** (`domain/vocabulary.py`):
  `_learner_level_state(user_id)` lee `learning_profile` (fila única) y devuelve
  `{..., observed_skill_capacity, observed_skill_level, skill_coverage,
  floor_level, floor_source, floor_level_by_skill, floor_source_by_skill,
  learner_capacity}`; `_skill_floor(state, skill)` resuelve el suelo de UNA
  modalidad (cae al global si no está el mapa). Es la MISMA caché que ya usa el
  drill de transferencia: **no se recalcula el Student Model en el camino
  caliente**.
- **Capacidad por modalidad** (`services/learner_skill.skill_capacity(floor_level,
  observed_skill_capacity, skill)`): devuelve `{capacity, coverage,
  covered_dimensions}` con `capacity[d] = max(capacity_for(floor)[d],
  observado[skill][d])`. `capacity_for` (`services/difficulty.py`) es el envelope
  del BANCO (`CEFR_CAPACITY`, 1..5, recalibrado en V3.52.2).
- **Dificultad declarada del ítem** (`services/difficulty.declared_difficulty`,
  V3.55): recibe `lexicon.cefr_difficulty(row)` — posición CEFR 1..6, `0.0` sin
  CEFR — y devuelve `{lexical: carga}` (recorte 1..5; `0` = no declarado).
- **Contrato de la cola**: `schemas/learning.ReviewQueueItem` (con `priority`,
  `signals`, `why`, `limiting_skill`, `skill_priorities`, `task`,
  `transfer_confidence`…) y su espejo `ReviewQueueItem` en
  `frontend/src/types/api.ts` (campos opcionales). El frontend **no muestra**
  `priority` hoy: este incremento no cambia UI, solo el contrato aditivo.
- **Ledger** (`learning_evidence`): dificultad en tres columnas honestas
  (`declared_difficulty`/`served_difficulty`/`observed_task_difficulty`, V3.55),
  apoyo (`support_level`), latencia, tipo de error, contexto y `assessed_skill`.
  El planner ya las consume vía `summarize_evidence`/`planned_signals`.

## Decisiones de alcance (CERRADAS con el gerente)

1. **Alcance = núcleo ELV + orden de la cola.** `select_task` (la cascada de
   razones) se queda **intacta**: el ELV **puntúa y ordena**, no elige todavía la
   tarea. El **argmax `(skill, actividad)` sobre ELV** es el candidato de
   **V3.57** y **NO** entra aquí.
2. **`P(éxito)` = margen de CAPACIDAD declarado.** Nada de parámetros estimados
   por datos ni de `retrievability` metido en `p`: el margen sale de comparar la
   dificultad declarada de la TAREA con la capacidad del alumno en la MODALIDAD
   que la tarea evalúa, y `p` de una **tabla declarada por tramos**
   (`SUCCESS_BY_MARGIN`), monótona y acotada. El olvido (`retrievability`) sigue
   influyendo donde ya influía: dentro del **valor** (`forgetting` de
   `priority_score`).
3. **SIN migración de BD.** Todo se deriva en memoria por la cola (puro, O(1)
   sobre lo que ya se lee). No hay columnas nuevas, ni en `learning_evidence` ni
   en `learning_profile`.
4. **`priority` NO se elimina**: se conserva exacto como proyección legacy y
   sigue siendo el primer desempate. `PRIORITY_WEIGHTS` no se toca (se reutiliza
   como `value`).
5. **Degradación neutra EXACTA.** Sin estado del alumno (o sin dificultad
   declarada del ítem) `p = P_SUCCESS_UNKNOWN = 0.5`,
   `desirability(0.5) = 4·0.5·0.5 = 1.0` y por tanto `ELV = priority`: el orden
   de la cola es **IDÉNTICO al de V3.55.0**, clave por clave. Es el invariante de
   no-regresión de este incremento y se prueba de forma exhaustiva.
6. **Una sola implementación del estado del alumno.** Si para leer el estado en
   `domain/review.py` hace falta extraer `_learner_level_state` de
   `domain/vocabulary.py`, se extrae a un único sitio (`domain/profile.py` es el
   candidato natural) y `domain/vocabulary` pasa a delegar. Prohibido duplicar la
   derivación (premisa 10). `domain/vocabulary.py` no importa `domain/review.py`,
   así que importar en sentido contrario no crea ciclo, pero la duplicación no se
   acepta.

## Diseño del núcleo (qué tiene que existir y con qué contrato)

### A. Piezas puras nuevas en `services/planner.py`

```python
# Probabilidad de éxito por MARGEN de capacidad (capacidad del alumno −
# dificultad declarada de la tarea, en la dimensión limitante). Tabla DECLARADA,
# monótona no decreciente, sin parámetros estimados por datos.
SUCCESS_BY_MARGIN: dict[int, float] = {
    -3: 0.05, -2: 0.15, -1: 0.35, 0: 0.55, 1: 0.75, 2: 0.90, 3: 0.95,
}
P_SUCCESS_UNKNOWN = 0.5   # sin capacidad o sin dificultad declarada: neutro
P_SUCCESS_LOW = 0.35      # umbrales de la explicación (`why`), declarados
P_SUCCESS_HIGH = 0.75
```

Valores resultantes de la curva (para los tests, exactos):

| margen |  −3  |  −2  |  −1  |  0   |  +1  |  +2  |  +3  |
| ------ | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| `p`    | 0.05 | 0.15 | 0.35 | 0.55 | 0.75 | 0.90 | 0.95 |
| `desirability` | 0.19 | 0.51 | 0.91 | **0.99** | 0.75 | 0.36 | 0.19 |

Con `P_SUCCESS_UNKNOWN` (`0.5`) la deseabilidad es **1.00** exacta: es el ancla de
la degradación neutra.

- `success_probability(margin)` — `margin` entero o `None`: `None` →
  `P_SUCCESS_UNKNOWN`; fuera de la tabla, **clamp** al extremo más cercano
  (`-3` y menos → `0.05`; `3` y más → `0.95`). Nunca lanza.
- `capacity_margin(task_difficulty, learner_capacity) -> int | None` — normaliza
  ambos vectores (`difficulty.normalize_vector`); si la tarea no declara nada, o
  ninguna dimensión declarada por la tarea existe en la capacidad, devuelve
  `None` (**una dimensión sin capacidad NO se cuenta como 0**: no se inventa un
  margen negativo sin evidencia). Si hay dimensiones comparables, devuelve el
  **MÍNIMO** margen (la restricción limitante: la tarea falla por su eslabón más
  débil). Nunca lanza.
- `desirability(p)` — `round(clamp(4·p·(1−p), 0, 1), 4)`: máximo `1.0` en
  `p = 0.5`, `0` en los extremos. Es el factor de **dificultad deseable** (zona
  de desarrollo próximo): lo trivial y lo inalcanzable valen poco.
- `expected_learning_value(signals, *, skill="", task_difficulty=None,
  learner_capacity=None) -> dict` — devuelve
  `{expected_learning_value, p_success, desirability, value, margin, skill}`:
  - `value = priority_score(signals)` (los MISMOS pesos declarados; no se añade
    ninguno);
  - `margin = capacity_margin(task_difficulty, learner_capacity)`;
  - `p_success = success_probability(margin)`;
  - `expected_learning_value = round(desirability(p_success) * value, 4)`.
  Nunca lanza y es determinista.

### B. Cableado de la decisión en el ítem (`services/lexicon.review_queue_item`)

- Añade un parámetro **opcional** `learner_state: dict | None = None` (misma
  forma que devuelve `_learner_level_state`; sin él, todo degrada al
  comportamiento actual).
- Resuelve la modalidad de la tarea que el ítem servirá (`_task_decision(...)`
  ya se calcula: `task["skill"]`, con caída a `limiting_skill(signals)`), el
  suelo de ESA modalidad (`floor_level_by_skill` con caída al global, misma
  política que `domain.vocabulary._skill_floor`), la capacidad por dimensión
  (`services.learner_skill.skill_capacity(floor, observed_skill_capacity, skill)
  ["capacity"]`) y la dificultad declarada del ítem
  (`difficulty.declared_difficulty(cefr_difficulty(row))`).
- Expone, **aditivos**: `expected_learning_value: float` (clave de orden) y
  `learning_value: dict` (el payload explicable del núcleo). `priority` y el
  resto de campos **no cambian de valor**.
  - **Limitación documentada:** para la tarea `transfer` el vector real es el del
    CONTEXTO, que aún no está elegido en la cola (lo elige el GET del peldaño);
    se usa la dificultad léxica declarada del ítem y se explica en el docstring.
- `explain_priority(signals, reason, learning_value=None)` gana frases
  **aditivas** y solo cuando `p` está predicho (margen no `None`), usando
  `P_SUCCESS_LOW`/`P_SUCCESS_HIGH`:
  - `p <= P_SUCCESS_LOW` → `"currently above your observed capacity"`;
  - `P_SUCCESS_LOW < p < P_SUCCESS_HIGH` → `"challenging but achievable (about
    NN% expected success)"`;
  - `p >= P_SUCCESS_HIGH` → `"well within your observed capacity"`.
  Sin `learning_value` (o con margen `None`) las frases son las de V3.55.

### C. Orden de la cola (`domain/review.py`)

- Extrae la lectura O(1) del estado del alumno a UN único sitio y úsala **una
  vez** por `get_review_queue`, pasándola a las DOS pasadas de
  `review_queue_item` (ranking y servido), para que orden y payload no puedan
  divergir.
- Orden nuevo:

  ```python
  (-expected_learning_value, -priority, retrievability, word)
  ```

  con `retrievability` ausente tratada como `1.0` (igual que hoy) y `word` como
  último desempate. El recorte de presentación sigue aplicándose DESPUÉS del
  ranking global.
- `_queue_sort_key` deja de mirar solo `priority`; documenta el porqué (el ELV
  manda, la urgencia y el scheduler siguen explicando).

### D. Contrato

- `backend/schemas/learning.py::ReviewQueueItem`: `expected_learning_value:
  float = 0.0` y `learning_value: dict = Field(default_factory=dict)`, con
  comentario de versión (V3.56) y semántica.
- `frontend/src/types/api.ts::ReviewQueueItem`: espejo **opcional**
  (`expected_learning_value?: number; learning_value?: Record<string, unknown>;`).
  **Sin cambio de UI** (el frontend no muestra `priority` hoy); los tests
  visuales/Playwright no deben cambiar.

## Archivos clave

- `backend/services/planner.py` — núcleo puro (A) + frase de `explain_priority`.
- `backend/services/lexicon.py` — `review_queue_item(... learner_state=None)` (B).
  Necesita consumir `services.difficulty` y `services.learner_skill`: añádelos a
  su import de `services` (no hay ciclo: `learner_skill` solo importa
  `difficulty` y `cefr`, y ninguno importa `lexicon`).
- `backend/domain/review.py` — lectura única del estado (C) + `_queue_sort_key`.
- `backend/domain/profile.py` (o el sitio que elijas) — lectura O(1) del estado
  del alumno, **una sola implementación**; `domain/vocabulary.py` delega.
- `backend/services/learner_skill.py` y `backend/services/difficulty.py` — se
  **consumen** tal cual (`skill_capacity`, `declared_difficulty`); no se tocan.
- `backend/schemas/learning.py` + `frontend/src/types/api.ts` — contrato (D).
- Tests nuevos: `backend/tests/test_expected_learning_value_v356.py`.

## Tarea detallada

1. `SUCCESS_BY_MARGIN`, `P_SUCCESS_UNKNOWN`, `P_SUCCESS_LOW/HIGH`,
   `success_probability`, `capacity_margin`, `desirability` y
   `expected_learning_value` puros, con docstrings que expliquen la elección
   (curva declarada, mínimo por dimensión, degradación neutra en `0.5`).
2. `review_queue_item(..., learner_state=None)` que expone `expected_learning_value`
   y `learning_value` sin alterar ningún campo existente.
3. Estado del alumno en la cola: una lectura O(1), UNA implementación, dos
   consumidores (cola y drill); test de equivalencia entre ambos consumidores.
4. Orden de la cola por ELV con `priority` como primer desempate; documentar el
   invariante de degradación neutra.
5. Frases aditivas de `why` con los umbrales declarados.
6. Contrato aditivo backend + espejo TS opcional.
7. Tests de aceptación, paridad de orden y **no-regresión exhaustiva**.

## Criterios de aceptación

- `success_probability(None) == 0.5`; la tabla es monótona no decreciente y
  acotada en `(0, 1)`; fuera de rango hace clamp (nunca lanza).
- `desirability(0.5) == 1.0` y es máxima exactamente ahí; `desirability(0.0) ==
  desirability(1.0) == 0.0`.
- `capacity_margin` devuelve el **mínimo** de los márgenes de las dimensiones
  declaradas por la tarea **que existan** en la capacidad; devuelve `None` sin
  dimensiones comparables (una dimensión sin capacidad NO se cuenta como 0) y
  `None` con dificultad de tarea vacía.
- **Con `learner_state=None` la cola queda ordenada EXACTAMENTE como en V3.55.0**
  (mismo `expected_learning_value == priority` para todo ítem y misma secuencia
  `(-priority, retrievability, word)`) y cada ítem conserva `priority`, `signals`,
  `why`, `task` y `skill_priorities` con los valores anteriores.
- **Con estado del alumno**, dos ítems con el MISMO `priority` pero distinto
  margen se ordenan por ELV: el de margen `0` (p ≈ 0.55, deseabilidad ≈ 0.99)
  va primero, después el de margen `−2` (p = 0.15, deseabilidad = 0.51) y por
  último el de margen `+2` (p = 0.90, deseabilidad = 0.36). Test explícito.
- Un alumno con capacidad observada en la modalidad que la tarea evalúa obtiene
  `p_success` MAYOR que el mismo ítem con el suelo declarado solo (el observado
  sube el margen): test con `observed_skill_capacity`.
- `learning_value` expone `{expected_learning_value, p_success, desirability,
  value, margin, skill}` coherentes entre sí
  (`expected_learning_value == desirability * value`).
- `GET` de la cola (`/api/learning/review`, `routers/learning.py`) sirve
  los campos nuevos sin romper el contrato y sin cambiar el número de ítems ni
  el `due_count`.
- Paridad pura↔SQL de la evidencia intacta (la cola la consume sin tocarla).
- Cero regresión de `test_planner_v338.py`, `test_optimal_task_v339.py`,
  `test_review_queue_v335.py`, `test_graduated_cues_v337.py`,
  `test_recall_policy_v3371.py`, `test_situational_cue_v338.py`,
  `test_skill_segmentation_v338.py`, `test_learning_evidence_v336.py`,
  `test_profile.py` y `test_user_profile.py`.

## Restricciones

- **No** tocar `select_task`, `ACTIVITY_FOR_SKILL`, `ACTIVITY_SUPPORT_LEVEL`,
  `EVIDENCE_REASON_ORDER` ni la cascada de razones: la decisión de tarea no
  cambia en V3.56.
- **No** hacer el argmax `(skill, actividad)` (V3.57) ni consumir
  `assessed_skill` en el planner ni corregir el doble conteo de
  `written_production` (deuda de planner, fuera de alcance).
- **No** tocar `PRIORITY_WEIGHTS` ni los umbrales de
  `transfer_state`/`context_signals`/`context_diversity`/`CEFR_CAPACITY`/
  `DIFFICULTY_TOLERANCE*`/`SUPPORT_DISCOUNT_STEPS` ni el scoring ni FSRS.
- **No** añadir migraciones ni columnas; PROHIBIDO agregar el ledger al camino
  caliente (la cola sigue leyendo el resumen ya construido y la caché O(1)).
- **No** introducir LLM, reloj propio ni aleatoriedad: todo puro y determinista.
- Vigila el tamaño de las líneas (`ruff`, 88 columnas) y no dejes código muerto.

## Salida esperada

Diff del backend + espejo del tipo TS + tests, más
`release-notes-v3.56.0.md` y actualización de `CHANGELOG.md`, `PLAN.md`,
`README.md`, `docs/RELEVO.md` y `agentes/README.md`; `VERSION = "3.56.0"` en
`backend/config.py` y las mismas versiones en `frontend/package.json` y
`frontend/package-lock.json` (sin desfase: lo verifica
`scripts/check_release_consistency.py`). Verifica `ruff`, `pytest`, `tsc`,
`vitest`, `build` y los scripts de contenido/gates antes de dar el incremento por
cerrado, y deja el briefing `agentes/v356-planner-2.md` en el árbol como histórico
del método.

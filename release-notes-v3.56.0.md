# v3.56.0 — Planner 2.0 (`expected_learning_value`)

> Release **SIN migración de BD y SIN cambios de UI** que convierte la prioridad
> del planner de una **suma de urgencia** en un **VALOR ESPERADO DE
> APRENDIZAJE**, y pasa a ordenar la cola de repaso por él. Hasta V3.55 el
> planner sabía cuánto **urge** repasar algo, pero **no predecía si el alumno
> podrá con la tarea**. El ELV combina, por primera vez, las dos mitades:
> `P(éxito)` (capacidad del alumno vs. dificultad declarada de la tarea) y
> `V(valor)` (el `priority_score` de siempre), con la **dificultad deseable**
> como factor (`ELV = dificultad_deseable(P) × V`, máximo en `P ≈ 0.5`).
> **NO** reescribe `select_task` (la cascada de razones se queda **intacta**),
> **NO** decide todavía la tarea por argmax `(skill, actividad)` (eso es V3.57) y
> **NO** toca `transfer_state`, sus umbrales, `context_signals`,
> `context_diversity`, `CEFR_CAPACITY`, el scoring, FSRS ni el Difficulty Engine
> de V3.52/V3.54/V3.55. Es el **P1-03** de la lista «V3.53+» de la auditoría
> externa de V3.52. Determinista, sin LLM.

## Contexto

V3.38–V3.55 construyeron un planner explicable (`planned_signals`,
`priority_score`, `select_task`, `skill_priorities`) y un Student Skill State
observado por modalidad y dimensión (`learner_skill`, `student_state`,
`difficulty`). Pero el planner **no consumía el estado del alumno**: una tarea
que el alumno ya domina y una inalcanzable podían recibir la misma prioridad si
su urgencia coincidía. La pieza que faltaba era el **valor esperado de
aprendizaje**: premiar la tarea que enseña (ni trivial ni imposible).

## Cambio

```text
señales del ítem (olvido + hueco + debilidad + apoyo + latencia)
   ↓ priority_score(signals)                       = V (valor pedagógico)

estado del alumno (O(1), caché del Student Model)
   ↓ suelo de la modalidad que la tarea evalúa + capacidad por dimensión
   ↓ capacity_margin(tarea, capacidad) = capacidad − dificultad (mínimo)
   ↓ success_probability(margen)  = P(éxito)        [tabla declarada]
   ↓ desirability(P) = 4·P·(1−P)  (máx. en P = 0.5)

ELV = desirability(P) × V     →  orden de la cola (priority = primer desempate)
```

### A. Núcleo puro — `services/planner.py`

- `SUCCESS_BY_MARGIN` — tabla **declarada**, monótona no decreciente y acotada en
  `(0, 1)`: margen `−3…+3` → `p` `0.05…0.95`. Nada de parámetros estimados por
  datos ni de meter `retrievability` en `p` (el olvido sigue pesando donde ya
  pesaba, dentro del valor).
- `success_probability(margin)` — `None` (o entrada no numérica / bool-as-int)
  degrada al **neutro** `P_SUCCESS_UNKNOWN = 0.5`; fuera de la tabla **clamp** al
  extremo más cercano. Nunca lanza.
- `capacity_margin(task_difficulty, learner_capacity)` — normaliza ambos vectores
  (`difficulty.normalize_vector`) y devuelve el **MÍNIMO** de las dimensiones que
  la tarea declara y existen en la capacidad (la tarea falla por su eslabón más
  débil). Una dimensión declarada pero **sin capacidad NO se cuenta como 0**: sin
  evidencia no se inventa un margen negativo. Sin dimensiones comparables (o sin
  dificultad declarada) devuelve `None`.
- `desirability(p_success)` — `round(clamp(4·p·(1−p), 0, 1), 4)`: máximo exacto
  `1.0` en `p = 0.5` (dificultad deseable) y `0` en los extremos.
- `expected_learning_value(signals, *, skill, task_difficulty, learner_capacity)`
  — devuelve `{expected_learning_value, p_success, desirability, value, margin,
  skill}` con `value = priority_score(signals)` (los **mismos** pesos
  declarados; no se añade ninguno). Nunca lanza y es determinista.

Valores exactos de la curva (usados por los tests):

| margen | −3 | −2 | −1 | 0 | +1 | +2 | +3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `p` | 0.05 | 0.15 | 0.35 | 0.55 | 0.75 | 0.90 | 0.95 |
| `desirability` | 0.19 | 0.51 | 0.91 | **0.99** | 0.75 | 0.36 | 0.19 |

Con el neutro `p = 0.5` la deseabilidad es **1.00** exacta: es el ancla de la
degradación neutra.

### B. Degradación neutra EXACTA

Sin estado del alumno o sin dificultad declarada del ítem:
`margin = None` → `p = 0.5` → `desirability = 1.0` → **`ELV = priority`**, y la
cola queda ordenada **exactamente** como en V3.55.0 (misma secuencia
`(-priority, retrievability, word)`), con cada ítem conservando sus valores
previos. Es el invariante de no-regresión del incremento.

### C. Cableado del ítem — `services/lexicon.review_queue_item`

- Nuevo parámetro **opcional** `learner_state` (misma forma que
  `domain.learner_state.learner_level_state`; sin él, todo degrada al
  comportamiento actual).
- Resuelve la modalidad que la tarea evalúa (`task["skill"]`, con caída a
  `limiting_skill`), el suelo de ESA modalidad (`student_state.skill_floor`), la
  capacidad por dimensión (`learner_skill.skill_capacity`) y la dificultad
  declarada del ítem (`difficulty.declared_difficulty` sobre
  `lexicon.cefr_difficulty`).
- Expone, **aditivos**: `expected_learning_value` (clave de orden) y
  `learning_value` (payload explicable del núcleo). `priority` y el resto de
  campos **no cambian de valor**.
- `explain_priority` gana frases **aditivas** y solo cuando `p` está predicho
  (margen no `None`), con `P_SUCCESS_LOW`/`P_SUCCESS_HIGH`: por debajo, «above
  your observed capacity»; en medio, «challenging but achievable (about NN%
  expected success)»; por encima, «well within your observed capacity».
- **Limitación documentada:** para la tarea `transfer` el vector real es el del
  CONTEXTO, que aún no está elegido en la cola (lo elige el GET del peldaño); se
  usa la dificultad léxica declarada del ítem y se explica en el docstring.

### D. Una sola lectura del estado del alumno — `domain/learner_state.py`

La lectura O(1) de la caché del Student Model (`empty_learner_level_state`,
`learner_level_state`) se extrae a **un único sitio** para que la cola de repaso
y el drill no puedan divergir (premisa 10). `domain.vocabulary` pasa a delegar y
`_skill_floor` a `services.student_state.skill_floor` (misma política, también
un único sitio). **No** se ubica en `domain.profile` (el candidato natural)
porque `domain.academy` importa `domain.vocabulary` y se crearía el ciclo
`vocabulary → profile → academy → vocabulary`.

### E. Orden de la cola — `domain/review.py`

- `_queue_sort_key` pasa a
  `(-expected_learning_value, -priority, retrievability, word)`: el ELV manda,
  `priority` sigue como primer desempate y un ítem legacy sin ELV cae a su
  prioridad (con la degradación neutra ambos coinciden).
- El estado del alumno se lee **una vez** por `get_review_queue` y se pasa a las
  **dos pasadas** de `review_queue_item` (ranking y servido), de modo que orden y
  payload no pueden divergir. El recorte de presentación sigue aplicándose
  DESPUÉS del ranking global.

### F. Contrato

- `backend/schemas/learning.py::ReviewQueueItem`: `expected_learning_value:
  float = 0.0` y `learning_value: dict = Field(default_factory=dict)`.
- `frontend/src/types/api.ts::ReviewQueueItem`: espejo **opcional**
  (`expected_learning_value?: number; learning_value?: Record<string, unknown>;`).
  **Sin cambio de UI** (el frontend no muestra `priority` hoy); los tests
  visuales/Playwright no cambian.

## Qué NO cambia

- `select_task`, `ACTIVITY_FOR_SKILL`, `ACTIVITY_SUPPORT_LEVEL`,
  `EVIDENCE_REASON_ORDER` ni la cascada de razones: la decisión de tarea no
  cambia en V3.56.
- `PRIORITY_WEIGHTS` ni los umbrales de
  `transfer_state`/`context_signals`/`context_diversity`/`CEFR_CAPACITY`/
  `DIFFICULTY_TOLERANCE*`/`SUPPORT_DISCOUNT_STEPS`, ni el scoring ni FSRS.
- El ledger: sin migraciones ni columnas nuevas; la cola sigue leyendo el resumen
  ya construido y la caché O(1).
- El argmax `(skill, actividad)` sobre ELV, el Sense Engine 2.0 y el Context
  Engine 3.0 quedan fuera de alcance (V3.57+).

## Verificación

- Nuevo `backend/tests/test_expected_learning_value_v356.py` (19 tests): tabla
  monótona/acotada y clamp, `desirability` (máximo en 0.5, cero en extremos),
  `capacity_margin` (mínimo por dimensión comparable, ignora dimensiones sin
  capacidad, `None` sin comparables), degradación neutra (`ELV = priority`),
  combinación `desirability × value`, frases de `why`, ítem de cola con y sin
  estado, capacidad observada que sube `p_success`, orden por
  ELV/priority/scheduler/palabra, lectura única del estado (equivalencia entre
  consumidores) y paridad HTTP sin perfil (orden V3.55.0) y con perfil.
- Cero regresión en el bloque V3.51–V3.55 (260 tests verdes) y en el resto de la
  suite: `pytest` **2242 passed** (151,3 s).
- `ruff` limpio (backend y launcher); launcher **75 passed**; `tsc --noEmit` OK;
  `vitest` **651 passed** (76 archivos); `npm run build` OK;
  `check_release_consistency` (**3.56.0**) exit 0.
- **CI: pendiente de ejecución tras el push** (6/6 esperado: Backend ruff +
  pytest, Frontend tsc + vitest + build, Release consistency **3.56.0**, Beta
  V3.0 gate, Content validation y Playwright).

## Fuera de alcance (V3.57+)

- El **argmax `(skill, actividad)`** sobre ELV: el planner elige la tarea además
  de ordenarla.
- Consumir `assessed_skill` en el planner y corregir el doble conteo de
  `written_production` (deuda de planner).
- **Sense Engine 2.0** (`surface → lemma → sense → semantic_fit`) y **Context
  Engine 3.0**.

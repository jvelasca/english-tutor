# v3.57.0 — Planner 2.0: argmax `(skill, actividad)` sobre ELV

> Segunda mitad del **Planner 2.0**, **SIN migración de BD y SIN cambios de UI**.
> V3.56 convirtió la prioridad del planner en un **VALOR ESPERADO DE
> APRENDIZAJE** (`ELV = dificultad_deseable(P) × value`) y pasó a **ordenar** la
> cola de repaso por él; la tarea, sin embargo, la seguía eligiendo la cascada
> `select_task`. V3.57 cierra esa mitad: el planner **elige** la tarea por
> **argmax de ELV** entre las candidatas admisibles. Es el candidato que V3.56
> dejó explícitamente diferido.
> La release es **CONSERVADORA**: el argmax solo actúa **con estado del alumno**;
> **sin él la decisión es EXACTAMENTE la de V3.56.0** (`select_task`). Además
> resuelve **dos deudas** del planner: el `value` **por modalidad**
> (`skill_priorities`) en lugar del `priority_score` global, y el **doble conteo
> de `written_production`** (el EJE de `transfer` frente al CANAL que
> `write`/`transfer` realmente miden). Determinista, sin LLM. **NO** toca
> `transfer_state`, sus umbrales, `context_signals`, `context_diversity`,
> `CEFR_CAPACITY`, el scoring, FSRS ni el Difficulty Engine de V3.52/V3.54/V3.55.

## Contexto

V3.38–V3.55 construyeron un planner explicable (`planned_signals`,
`priority_score`, `select_task`, `skill_priorities`) y un Student Skill State
observado por modalidad y dimensión (`learner_skill`, `student_state`,
`difficulty`). V3.56 le dio la pieza que le faltaba —el valor esperado— pero la
usó **solo para ordenar**: dos ítems con el mismo valor esperado y una tarea
elegida por la cascada de razones podían dejar sobre la mesa la tarea que más
habría enseñado. Faltaba el **argmax**: dada la evidencia del ítem y el estado
del alumno, elegir la pareja `(skill, actividad)` de mayor valor esperado.

## Cambio

```text
evidencia del ítem + matriz de competencia
   ↓ task_candidates: admisibles HOY, en orden canónico
     error_prone > slow_recall → recall
     huecos de producción (oral antes que escrita) → skill_gap
     transfer_gap → spontaneous_use
   ↓ por candidata:
     value   = skill_priorities(signals)[eje]        (prioridad POR modalidad)
     canal   = capacity_skill(eje)                   (lo que la actividad MIDE)
     P(éxito)= success_probability(                    (tabla declarada)
                 capacity_margin(dificultad, capacidad[canal]))
     ELV     = desirability(P) × value
   ↓ argmax ELV  (solo candidatas con margen COMPARABLE)
```

Sin capacidad, sin candidatas o sin ningún margen comparable → `select_task`
**exacto**: sin estado del alumno la tarea servida es la de V3.56.0.

### A. Núcleo puro — `services/planner.py`

- `capacity_skill(skill)` — mapea el **EJE** de la tarea (lo que quiere
  provocar) al **CANAL** que la actividad efectivamente **MIDE**, vía
  `task_semantics.assessed_skill_for`: `transfer` tiene eje `spontaneous_use`
  pero se entrega por texto y se evalúa como producción **escrita**
  (`written_production`). Una modalidad sin actividad declarada cae a su propio
  eje (**no se inventa canal**) y vacío devuelve `""`. Nunca lanza.
- `task_candidates(matrix, evidence)` — las tareas **admisibles hoy**, en orden
  canónico: `error_prone` (gana sobre `slow_recall`) → `recall`; cada hueco de
  producción accionable que la matriz declare, en `GAP_CANDIDATE_ORDER`
  (`spoken_production` **antes** que `written_production`, la preferencia
  histórica de V3.38.1) → `skill_gap`; y `transfer_gap` → `spontaneous_use`
  (solo con su propio gate: base previa y menos contextos de los exigidos). Una
  candidata por modalidad, `support_level` declarado por la actividad (mismo
  contrato que `select_task`). Sin directriz devuelve `[]` y nunca lanza.
- `select_task_by_elv(matrix, evidence, signals, *, capacity_by_skill,
  task_difficulty)` — puntúa cada candidata con `expected_learning_value` y
  devuelve la de mayor ELV. `value` sale del valor **por modalidad**
  (`skill_priorities(signals)[skill]`, con el `priority_score` global como
  respaldo) y el margen se mide sobre el **canal** que la actividad mide
  (`capacity_skill`). **Solo compiten las candidatas con margen comparable**:
  una modalidad sin datos tiene `p = 0.5` → deseabilidad `1.0`, el **máximo**, y
  competiría **premiada por ignorancia**. El empate lo rompe el orden canónico de
  `task_candidates` (comparación `>` estricta), no el orden de
  `PRODUCTION_SKILLS`.
- `expected_learning_value` gana dos parámetros **opcionales** (`value`,
  `capacity_skill`) y su payload gana `capacity_skill` (informativo). Los
  llamadores de V3.56 **no cambian**: `value = None` reproduce el
  `priority_score` global de siempre.

### B. Degradación neutra EXACTA (invariante de no-regresión)

Sin `capacity_by_skill`, sin candidatas o sin **ningún** margen comparable,
`select_task_by_elv` devuelve `select_task` **clave por clave**. Sin estado del
alumno (o sin dificultad declarada del ítem) el `p` de cada candidata es `0.5` →
`desirability = 1.0` → `ELV = value`, y el invariante se cumple por
construcción: **la tarea servida sin perfil es la de V3.56.0** y se prueba de
forma explícita, parametrizada sobre varios pares matriz/evidencia.

### C. Deuda 1 — `skill_priorities` como `value`

Hasta V3.56 el ELV se calculaba siempre con el `priority_score` **global**. La
señal que el planner ya sabía producir —la prioridad **por modalidad**— no se
consumía en la elección. En el argmax, `value` pasa a ser
`skill_priorities(signals)[skill]`, de modo que dos candidatas distintas de la
misma evidencia se comparan por lo que **a cada modalidad** le corresponde, no
por un escalar común.

### D. Deuda 2 — doble conteo de `written_production`

`transfer` declara eje `spontaneous_use`, pero el ledger acredita la capacidad
**por canal** (producción escrita). Si el margen se hubiera medido con el eje:

1. `spontaneous_use` no tendría capacidad observada (se leería como
   desconocida), y
2. `write` y `transfer` se habrían leído como **dos mediciones distintas** de
   `written_production`, sumando dos veces la misma capacidad y contando dos
   veces la prioridad del eje escrito.

Con `capacity_skill`, EJE (valor y hueco) y CANAL (capacidad y margen) quedan
separados: `write` y `transfer` son **una misma LECTURA** de
`written_production`. Se prueba que un éxito de `transfer` alimenta la capacidad
escrita **sin** tocar la prioridad del eje escrito, y que ambos leen **la misma**
capacidad escrita.

### E. Cableado — `services/lexicon.py`

- `_capacity_by_skill(learner_state)` — calcula **una sola vez** la capacidad por
  dimensión de **cada** modalidad canónica (`learner_skill.skill_capacity` sobre
  su suelo de `student_state.skill_floor`). Sin estado devuelve `{}` (la decisión
  degrada exacta a `select_task`). Nunca lanza.
- `review_queue_item` calcula **una vez** la dificultad declarada del ítem y la
  capacidad por canal, y las pasa a las **dos** rutas de decisión (actividad del
  ítem y `task`) y a la predicción servida: el argmax y el `learning_value` del
  payload **no pueden divergir**.
- `_task_decision` usa `select_task_by_elv` (que sin estado colapsa a
  `select_task`); `_learning_value` resuelve el canal con `capacity_skill` y
  reporta el `capacity_skill` medido.

## NO cambia

- `select_task` (la cascada de razones), `ACTIVITY_FOR_SKILL`,
  `EVIDENCE_REASON_ORDER`, `GAP_CANDIDATE_ORDER` (solo ordena el desempate del
  argmax) ni `PRIORITY_WEIGHTS`.
- `transfer_state` y sus umbrales, `context_signals`, `context_diversity`,
  `CEFR_CAPACITY`, `DIFFICULTY_TOLERANCE*`, `SUPPORT_DISCOUNT_STEPS`.
- El scoring, FSRS y el Difficulty Engine; sin migraciones ni columnas nuevas.
- El contrato previo del ítem de cola: `priority`, `signals`, `why`, `task` y
  `skill_priorities` se conservan; `learning_value` gana `capacity_skill`
  (**aditivo**).

## Tests

Nuevo `backend/tests/test_planner_argmax_v357.py` (**24**):

- `capacity_skill`: mapea el eje al canal evaluado, cae al eje sin canal
  declarado y nunca lanza.
- `task_candidates`: exige una razón admisible, ordena los huecos de producción
  (oral primero), incluye `transfer` solo con su propio gate y no lanza ante
  basura.
- `select_task_by_elv`: **degradación EXACTA** a `select_task` sin capacidad
  (parametrizada), caída cuando ningún margen es comparable, preferencia por la
  dificultad deseable y `value` **por modalidad**.
- Deudas: el éxito de `transfer` alimenta la capacidad escrita **sin** tocar la
  prioridad del eje escrito; `write` y `transfer` leen **la misma** capacidad
  escrita.
- Payload y cola: `capacity_skill` con y sin estado; tarea de cola sin estado
  (cascada) y con estado (argmax); dificultad declarada = vector léxico del ítem.
- Paridad **HTTP**: con perfil elige por ELV; sin perfil conserva la cascada.

## Verificación

| Gate | Resultado |
| --- | --- |
| `pytest` (backend) | **2266 passed** (147,8 s) |
| `ruff check` | limpio |
| `launcher` tests | **75 passed** |
| `tsc --noEmit` | OK |
| `vitest` | **651 passed** |
| `npm run build` | OK |
| `check_release_consistency` | **3.57.0** |
| CI (6/6) | verde — [run 34763651640](https://github.com/jvelasca/english-tutor/actions/runs/34763651640) sobre `a40b58d` |

Cero regresión en el bloque V3.51–V3.56 (incluye los 19 tests de V3.56 y su
invariante de orden) y en el resto de la suite.

## Fuera de alcance (V3.58+)

- **Sense Engine 2.0** (`surface→lemma→sense→semantic_fit`).
- **Context Engine 3.0**.

# v3.53.1 — Observed CEFR Safety Gate

> Patch que cierra el **P1-01** de la auditoría externa de V3.53.0: la capacidad
> observada de UNA dimensión ya no puede convertirse en un nivel CEFR **global**.
> Release **SIN migración de BD y SIN cambios de contrato** que **NO toca**
> `observed_capacity`, `learner_capacity`, `CEFR_CAPACITY`, la escalera
> `transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el
> scoring, el planner ni FSRS. Determinista, sin LLM.

## Contexto

V3.53.0 dio el salto arquitectónico correcto: pasar de «sé qué nivel CEFR tiene
el alumno» a «sé qué dificultad ha demostrado y en qué dimensiones». Pero
precisamente porque el Student Model empezaba a ser serio, apareció un problema
semántico en el corazón de la nueva funcionalidad.

`services.learner_skill.level_from_capacity` derivaba el nivel CEFR equivalente
iterando las dimensiones **con muestra** y trataba una dimensión sin muestra
como «no bloquea»:

```text
observed_capacity = {"lexical": 5}
        ↓
lexical 5 domina el léxico de C1/C2; el resto no se compara
        ↓
observed_level = "C2"   # demasiado fuerte
```

El alumno no había demostrado C2: había demostrado una **capacidad léxica
compatible con C2**. Un nivel CEFR global exige capacidades multidimensionales,
así que el resultado era el mismo error que V3.52/V3.52.2 cerraron al otro lado
(colapsar el vector), ahora en la derivación del nivel.

## Cambio

`level_from_capacity` recorre las dimensiones que exige el **nivel candidato**
(no las observadas), cuenta `0` en las que no tienen muestra y exige
**cobertura dimensional COMPLETA** para declarar cualquier etiqueta global:

- `observed_capacity` sigue siendo la **fuente de verdad** por dimensión.
- `observed_level` pasa a ser un **RESUMEN DERIVADO** que nunca se declara con
  evidencia parcial.
- El docstring del módulo y de la función documentan la jerarquía y el gate; se
  elimina la afirmación «conservador por construcción», que era falsa.

### Casos de aceptación (envolvente actual del banco)

| `observed_capacity` | Antes | Ahora |
| --- | --- | --- |
| `{"lexical": 5}` | `"C2"` | `""` |
| `{"lexical": 5, "syntax": 3, "discourse": 4, "interaction": 3}` | `"B2"` | `"B2"` |
| `capacity_for("C1")` (`lexical` 4, resto 5) | `"C1"` | `"C1"` |
| cobertura 3/4 (`{"lexical": 5, "syntax": 5, "discourse": 5}`) | alta | `""` |

`learner_capacity` NO cambia de forma: sigue siendo el máximo por dimensión entre
el suelo declarado y lo observado, así que el reto sube SOLO donde hay evidencia
y el suelo declarado nunca baja. Con cobertura parcial no hay nivel global, pero
las dimensiones demostradas siguen elevando el reto.

## Qué NO cambia

- Esquema de BD: `learning_profile.observed_level`/`observed_capacity` siguen
  iguales (misma semántica de caché; solo cambia el valor derivado del resumen).
- Contratos: `TransferContextOut`, `LearningProfile` y el espejo
  `frontend/src/types/api.ts` intactos. Sin cambios de UI.
- `observed_capacity`, `OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`,
  `learner_capacity`, `observed_signals`, `student_state`, `transfer` y
  `CEFR_CAPACITY` (envolvente del BANCO, recalibrada en V3.52.2).

## Verificación

- `test_level_from_capacity_requires_full_dimensional_coverage` (reescrito) +
  dos tests de aceptación multidimensional y uno de no-regresión
  (`observed_capacity` intacta y `learner_capacity` subiendo solo lo observado).
- Cero regresión de `test_difficulty_engine_v352.py`,
  `test_student_state_v352.py`, `test_observed_difficulty_v353.py`,
  `test_transfer_*.py` y `test_user_profile.py`.
- `ruff` y `pytest` en verde; `frontend` `vitest`/`tsc`/`build`; y
  `check_release_consistency` (**3.53.1**), `check_beta_v3`,
  `content_validation` y `check_i18n_coverage` exit 0.
- **CI 6/6 en verde** (run
  [34748988008](https://github.com/jvelasca/english-tutor/actions/runs/34748988008)
  sobre `6d8af47`): Backend (ruff + pytest, **2185 passed + 2 skipped**),
  Frontend (tsc + vitest **76 ficheros/651 tests** + build), Release consistency,
  Beta V3.0 gate, Content validation y Playwright E2E (visual, **23 passed**). Los
  2 skipped son `backend/tests/test_stt_asr_integration.py` (modelo Whisper no
  descargado en el runner, opt-in); con el modelo disponible en local el mismo
  árbol da **2187 passed**. Etiqueta anotada `v3.53.1` creada y empujada sobre
  `6d8af47`.

## Fuera de alcance (V3.54+)

- P2-01: desdoblar `observed_difficulty` en
  `served_difficulty`/`observed_task_difficulty`.
- P2-02: enriquecer la capacidad observada con apoyo, independencia,
  transferencia, latencia, errores y novedad contextual.
- P2-03: Student Skill State `skill × dimension`.
- Residual: la «fuga» de un nivel global hacia `learner_capacity` cuando la
  cobertura es parcial (desaparece con cobertura completa, que es lo que hoy
  sirven los vectores de transferencia).
- Planner 2.0 / `expected_learning_value` (P1-03), el verdadero siguiente salto.

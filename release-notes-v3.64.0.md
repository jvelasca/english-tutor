# v3.64.0 — Decision Projection + Planner 3.0 (cierre del P1-01)

> Release **SIN migración de BD**, **SIN bump de `GENERATOR_VERSION`**, **SIN
> tocar el banco** y **SIN umbrales nuevos** (el único cambio de UI es la línea de
> motivos DECLARADOS en la cola de repaso, con i18n en/es) que **CIERRA el P1-01**
> de las auditorías de V3.62/V3.63 y, por contrato, los **P2-02/P2-03/P2-04** de la
> auditoría `W` de V3.63.
>
> **La invariante central cambia aquí, pero con una frontera declarada:** el
> Student Skill State deja de ser **descriptivo** y **pasa a gobernar la decisión
> de tareas** — SIEMPRE por la capa explícita
>
>     Student Skill State  →  DECISION PROJECTION  →  Planner 3.0
>
> y **NUNCA** `skill_state → planner`. El planner sigue siendo un módulo **puro**
> y **ciego** al estado persistido: recibe `capacity_by_skill`, `skill_values` y
> `drivers`, que son **proyecciones** calculadas a partir de las **MISMAS filas
> canónicas** que alimentan el estado.

## Contexto

La auditoría `W` de V3.63.0 dio **9,6 / 10 APROBADA** (0 P0, **1 P1**, 4 P2, 2 P3)
y su veredicto operativo fue explícito: **no hacer V3.63.1** y concentrar el
esfuerzo en **V3.64 = Decision Projection + Planner 3.0**, que ya estaba
comprometido y fechado. El P1-01 heredado (V3.62) tenía dos mitades:

1. **El estado nuevo no gobernaba nada.** `lexicon._capacity_by_skill` leía la
   columna de V3.54 (`observed_skill_capacity`) y el estado unificado de
   V3.62/V3.63 se construía, se sellaba y se exponía… para nadie.
2. **No existía un punto declarado donde el estado pudiera gobernar sin romper la
   pureza del planner.** Un recableado directo habría metido I/O, caché y reloj en
   el planner y habría borrado la frontera que hace auditable la decisión.

V3.64 construye ese punto (la **proyección**) y cierra el P1-01. Y, en el mismo
movimiento, ataca por contrato los tres P2 del informe que eran exactamente
fronteras de la proyección: **dificultad ≠ esfuerzo** (P2-02), **error de tarea ≠
incertidumbre de medida** (P2-03) y **la carga máxima demostrada se llama como lo
que es** (P2-04).

## Cambio

### A · Módulo puro `services/decision_projection.py` (nuevo)

Mismo contrato de estilo que `observed_difficulty.py`: **puro**, **determinista**,
sin I/O, sin reloj propio (recibe el estado ya calculado), sin `random()`/`hash()`
y **nunca lanza**.

- `project(state)` → `{modalidad: {competencia: celda}}` con la MISMA forma de
  modalidades que el estado (el contrato no cambia de forma al degradar). Cada
  celda declara, **en grupos separados**:
  - **`load`** — hechos de la TAREA: `highest_demonstrated_load` (**nombrado
    explícitamente**: es carga máxima DEMOSTRADA, no dificultad empírica —
    P2-04), `served_ceiling`, `credited_ceiling` y
    `scaffolding_gap = servido − acreditado`.
  - **`effort`** — coste OBSERVADO: nivel declarado por los motivos de
    `assessment_confidence` y carga EXTRA (`experimentado − servido`).
  - `retention` (`review_due`, `last_evidence`), `transfer` (contextos distintos
    declarados y reparto por `kind`) y `novelty`: señales de **primera clase**
    del Planner 3.0.
  - `confidence` (estadística) y `assessment_confidence` (banda + motivos)
    **nunca se fusionan** (V3.63).
- **Frontera P2-03:** `error_type` se reparte con una **tabla declarada** en error
  de **TAREA** (`wrong_word`, `orthographic_error`, `partial`… → señal de
  dificultad, enciende `recent_failure`) e **INCERTIDUMBRE DE MEDIDA**
  (`low_confidence`/ASR, `empty`, `semantic_doubt`… → baja la confianza de
  evaluación y **NUNCA** sube la carga).
- `capacity_by_skill(projection)` — **reemplazo directo** de
  `lexicon._capacity_by_skill`: mismo espacio de claves (las cuatro de
  `LEXICAL_SKILLS`) y mismo contrato de valor (vector de dimensiones). La regla de
  honestidad: una celda **PROVISIONAL** (banda de evaluación mínima) **no cuenta
  como capacidad comparable**, así el argmax no premia la ignorancia (invariante
  de V3.57).
- `skill_values(projection)` — valor pedagógico por eje con pesos **declarados**
  (`PROJECTION_WEIGHTS`, suma 1.0) sobre `gap`, `retention`, `transfer` y `effort`.
  `assessment_confidence` **no** es un peso: es un **filtro de comparabilidad**.
- `drivers(projection, skill)` — bloque explicable del punto 26 del informe
  (`gap`, `retention_due`, `transfer_gap`, `effort`, `assessment_confidence`,
  `recent_failure`, `novelty`, `contexts`) y `has_comparable_capacity`, que declara
  la condición de degradación.
- **`difficulty_fit` NO vive aquí**: depende de la dificultad de la TAREA, así que
  lo añade el planner con el `margin` que ya mide.

### B · Hechos ADITIVOS del estado (`services/skill_state.py`)

`_entry` **expone** hechos que **ya calculaba** y no publicaba: `kinds` (el
`by_kind` del gate), `production_count`, `last_evidence`, `contexts` y
`error_types` (declarados por las filas, dedup con orden determinista) y
`review_due`. **Cero recálculo y cero cambio de semántica**: el estado solo
**DECLARA** los hechos; clasificarlos es de la proyección.

### C · Planner 3.0 aditivo (`services/planner.py`)

- `select_task_by_elv(...)` gana `skill_values` y `drivers` **opcionales** y, con
  ellos, un bloque aditivo `decision`: `expected_learning_value`, `p_success`,
  `margin`, `value`, `capacity_skill`, `comparable`, `source`
  (`argmax`/`cascade`), `projected`, **`difficulty_fit`** (encaje declarado;
  reutiliza las bandas YA existentes `P_SUCCESS_LOW`/`P_SUCCESS_HIGH` de V3.56,
  **sin umbrales nuevos**), `drivers`, `why` y las **alternativas puntuadas**
  (auditables).
- Nueva función pura `explain_drivers(drivers)` → frases declaradas en inglés
  (mismo registro que `explain_priority`, el contrato `why` del proyecto) y
  `difficulty_fit(p_success, margin)`.
- `explain_priority` se extiende de forma **aditiva** con esas frases.
- **Invariante de no-regresión:** `_has_projection` fija en el código que **sin
  `skill_values`/`drivers` no se añade ninguna clave** y la respuesta es
  **byte-idéntica** a V3.63. `test_planner_argmax_v357.py` sigue verde **sin
  tocarse**.

### D · `domain/decision.py` (nuevo, I/O; nunca lanza)

`decision_projection(user_id, *, level, now)`:

1. lee `profile_repo.get_profile` (que ya trae `skill_state` y su sello);
2. si `skill_state_is_fresh(user_id)` → normaliza la caché sellada con
   `normalize_skill_state` (`source = "cached"`);
3. si **no** es fresca (o no hay caché, o es **legacy sin sello**) → **recomputa
   UNA vez** desde las **cuatro fuentes canónicas** con el helper
   `canonical_sources`, **compartido con `domain/profile.py`** (la secuencia vive
   en un solo sitio y no puede divergir del perfil), y **re-sella** con
   `set_skill_state(uid, json, evidence_fingerprint(uid))`;
4. devuelve `{state, projection, capacity_by_skill, skill_values, drivers,
   source: cached|recomputed, sealed}`.

`project_state(state, source=, sealed=)` es el **único** punto donde el payload se
ensambla (puro), y por eso el perfil lo reutiliza sin releer nada.

**Invariante:** la proyección se deriva de las **filas canónicas**; la caché
sellada es solo la optimización O(1) y **siempre** se valida antes de usarse. Sin
fila de perfil **no se inventa caché**.

### E · Recableado declarado y degradable (`domain/review.py` + `services/lexicon.py`)

- `domain/review.get_review_queue` construye la proyección **UNA vez** por cola y
  la pasa a sus **DOS** pasadas (ranking y servido): orden y payload no pueden
  divergir.
- `lexicon.review_queue_item(..., projection=None)`: con proyección,
  `capacity_by_skill`/`skill_values`/`drivers` salen de ella y el ítem gana
  `decision`; sin proyección, el camino es el de V3.63 **exacto**.
- **Degradación declarada (y probada):** si la proyección **no declara capacidad
  comparable** (el estado calla: su puerta espaciada o una banda de evaluación
  mínima), se conserva **EXACTAMENTE** el camino de V3.54/V3.63 —estimador
  anterior, `skill_priorities` como valor y **sin** bloque `decision`—. Así
  **ninguna petición pierde señal ni cambia de tarea por el solo hecho de existir
  la proyección**.
- `_queue_sort_key` **no cambia**: sigue ELV → priority → retrievability →
  palabra; lo que cambia es **de dónde sale el valor**.

### F · Contrato aditivo

- `schemas/learning.py`: el ítem de la cola gana `decision` (y `why` se conserva
  tal cual).
- `schemas/profile.py`: `/api/profile` gana `decision_projection` (aditivo; útil
  para la auditoría externa y para fijarlo por e2e).
- Espejo en `frontend/src/types/api.ts` (`ReviewDecision`,
  `ReviewDecisionAlternative`, `ReviewDecisionDrivers`, `DifficultyFit`).
- **UI mínima declarada** (`features/vocabulary/ReviewQueueSection.tsx`): bajo el
  motivo del ítem se muestra **una línea** con las bandas DECLARADAS de la
  proyección — encaje de la tarea (`difficulty_fit`), hueco, hueco de
  transferencia, retención vencida, esfuerzo y confianza de **evaluación** —, con
  el alcance en el `title` («no son probabilidades, y no son una declaración de
  dominio»). **Sin medida declarada (`measured: false`) no se muestra nada**: la
  interfaz no inventa motivos que el estado no declara. Claves nuevas
  `dictionary.review.decision.*` en **en/es** y `ReviewQueueSection.test.tsx`
  **+2** (una con proyección y bandas, otra con el estado en silencio).

## Tests

Nuevo `backend/tests/test_decision_projection_v364.py` (**27**):

- **Pureza** — el módulo es determinista byte a byte y su fuente no contiene
  `import time`/`datetime`/`random`, `hash(`, `open(`, `sqlite` ni `requests`.
- **Proyección** — carga y esfuerzo en grupos **disjuntos**;
  `highest_demonstrated_load` == las dimensiones acreditadas == `capacity`;
  `scaffolding_gap = served − credited`; `confidence` y `assessment_confidence`
  nunca fusionadas; un `error_type` de **incertidumbre** deja la carga **idéntica**
  y **no** enciende `recent_failure`, mientras `wrong_word` sí.
- **Capacidad** — paridad de claves con `LEXICAL_SKILLS` y mapeo canal↔modalidad
  (incluida la política declarada de V3.57: `spontaneous_use` se MIDE por
  `written_production`); una celda provisional **no** es capacidad comparable;
  `has_comparable_capacity` exige alguna dimensión.
- **Valor** — pesos declarados que suman 1.0 y sin `assessment_confidence` entre
  ellos; acotado a 0..1 y definido para **todos** los ejes; la **retención**
  (vencimiento declarado por el llamador, nunca leído del reloj) **sube** el valor.
- **Drivers** — claves declaradas, `measured` honesto, contextos contados **sin
  inventar** ninguno y `explain_drivers` que **no inventa texto**.
- **Degradación exacta** — `select_task_by_elv` **sin** proyección conserva el
  contrato de V3.39 sin ninguna clave nueva; la cascada devuelve EXACTO
  `select_task`; `explain_priority` se extiende de forma aditiva (la salida de
  V3.63 es prefijo de la nueva).
- **Contraprueba positiva** — con el MISMO `learner_state` y dos proyecciones, la
  tarea servida **cambia** y la decisión lo explica (`projected`, `drivers`,
  `margin`); y una proyección **silenciosa** degrada byte a byte al camino V3.63.
- **Frescura** — caché fresca → **no** recomputa (contador sobre `_recompute`);
  legacy sin sello → recomputa **una vez**, re-sella y la segunda llamada no
  recomputa; evidencia nueva → caché vieja → recomputa una vez y vuelve a quedar
  fresca; sin perfil no se inventa caché.
- **e2e HTTP** — `GET /api/learning/review` con `decision` (y todas las claves de
  V3.63 intactas) y `GET /api/profile` con `decision_projection`.

**No-regresión:** `test_skill_state_v362.py` (guard estructural de no-recableado y
byte-identidad del camino de decisión) y `test_planner_argmax_v357.py` siguen
**PASANDO SIN TOCARSE**.

## Verificación

```
backend:  ruff check .                        → All checks passed
backend:  pytest -q                           → 2458 passed
launcher: pytest launcher/tests -q            → 75 passed
frontend: npx tsc --noEmit                    → OK
frontend: npm run test                        → 76 ficheros / 653 passed
frontend: npm run build                       → OK
scripts:  python scripts/check_release_consistency.py   → OK: Release consistency (3.64.0)
scripts:  python scripts/check_beta_v3.py     → OK: Beta V3.0 gate
backend:  python backend/scripts/content_validation.py  → OK=True quality=True
backend:  python -m scripts.transfer_validation         → OK=True (esta release NO toca el banco)
```

## Honestidad: qué NO cierra V3.64

- **La dificultad empírica sigue sin existir.** `observed_task_difficulty_2` es una
  **medida** declarada y `highest_demonstrated_load` es carga máxima **DEMOSTRADA**,
  no `P(éxito | alumno, tarea)`: la estimación empírica por pareja es **V3.65 —
  Observed Difficulty 3.0** y aquí **no se simula**.
- **La proyección solo gobierna cuando el estado tiene algo que decir** (su puerta
  espaciada 2/2 y una banda de evaluación por encima de la mínima). Mientras
  calla, la decisión es la de V3.54/V3.63: es una **degradación declarada, probada
  y visible** en `decision.source`/`projected`, no un descuido, y es exactamente
  la frontera que V3.65 debe cerrar.
- **El `margin` sigue comparando dificultad DECLARADA contra capacidad
  observada**: no hay parámetros ajustados por datos en ninguna parte.
- **Los `drivers` son motivos declarados**, no probabilidades ni pesos estimados.
- **P2-01 sigue como deuda declarada**: el fingerprint de frescura es
  `COUNT(*) + MAX(id)`, suficiente mientras las tablas sean append-only por
  contrato.
- **El gate sigue sin parametrizar por pareja** (`COMPETENCE_GATE_POLICIES` vacía,
  con su test) y **el banco y `GENERATOR_VERSION` no se tocan**.
- **La línea de motivos de la UI muestra BANDAS declaradas**, no probabilidades ni
  pesos estimados: no hay ajuste por datos en ninguna parte de V3.64.

## Roadmap

V3.65 → **Observed Difficulty 3.0** (`highest_demonstrated_load` vs dificultad
empírica, con la frontera de V3.64 ya declarada) → V3.66 Adaptive Instance
Selection → V3.67+ Sense Engine 2.0. Confirmado por el auditor en la auditoría `W`
de V3.63.0.

# v3.55.0 — Task Difficulty 3.0 (`declared` / `served` / `observed_task`)

> Release **ADITIVA (tres columnas de BD)** que da nombres honestos a la
> dificultad de la tarea en el ledger y hace que la capacidad observada acredite
> lo que el alumno **superó de verdad**, no lo que se le sirvió. Cierra los
> **P2-01** y **P2-02** de la auditoría de V3.53.1 y cablea la dificultad de la
> tarea en las **cuatro vías del drill léxico** (hasta ahora solo Transfer la
> escribía, así que `written_production`, `spoken_production` y `recall` no
> acumulaban capacidad nunca). **NO toca** `level_from_capacity`, el gate CEFR
> global de V3.53.1, `observed_skill_capacity`, `learner_capacity`,
> `CEFR_CAPACITY`, `transfer_state`, sus umbrales, `context_signals`,
> `context_diversity`, el scoring, el planner ni FSRS. Determinista, sin LLM.

## Contexto

V3.53 añadió `learning_evidence.observed_difficulty`, pero el nombre mentía: la
columna guardaba el vector de carga del contexto **SERVIDO** — lo que el alumno
tenía delante —, no la carga que había **superado** (P2-01). Y solo la escribía
el drill de Transfer: `recall`, `sentence` y `write` la dejaban `''`, de modo que
la capacidad observada de V3.53/V3.54 solo aprendía de transferencias.

Además, `services.evidence.observed_signals` acreditaba **igual** cualquier éxito
con vector, ignorando el `support_level` que el ledger ya guardaba: repetir una
palabra tras un modelo (`guided`) engordaba la capacidad tanto como producir una
frase propia (`independent`) o usar la unidad en un contexto nuevo
(`spontaneous`) — P2-02.

## Cambio

```text
EVENTO DEL DRILL
   ↓
DECLARED            # lo que declara el ÍTEM (su CEFR léxico) o la ACTIVIDAD
   ↓
SERVED              # lo que la actividad SIRVIÓ (vector del contexto, o lo declarado)
   ↓
SUPPORT_DISCOUNT    # el andamiaje declarado descuenta pasos de carga
   ↓
OBSERVED_TASK       # lo ACREDITADO (solo en el ÉXITO)
   ↓
CAPACIDAD OBSERVADA # observed_signals / learner_skill (V3.53/V3.54 intactos)
```

### A. Núcleo puro — `services/difficulty.py`

- `SUPPORT_DISCOUNT_STEPS` — tabla declarada y monótona con la escalera canónica
  (`guided` −2, `cued` −1, `independent`/`spontaneous` 0). `copied` y cualquier
  apoyo desconocido **no acreditan carga**: sin apoyo declarado no se inventa
  capacidad.
- `declared_difficulty(lexical_load)` — la única dimensión que un ítem puede
  declarar: `{lexical: n}` (1..5). Trata el `0` de `lexicon.cefr_difficulty`
  (ítem sin CEFR) como **no declarado**, no como carga 1.
- `observed_task_difficulty(served, support_level)` — lo servido descontado por
  el andamiaje; las dimensiones que caen por debajo de la carga mínima no
  acreditan.
- `task_difficulty_vectors(...)` — serializa las tres dificultades y la
  **proyección legacy** `observed_difficulty` (= `served`) en un solo sitio, de
  modo que ninguna vía de escritura puede divergir.
- `earned_difficulty(row)` — el vector ACREDITADO de una fila: `served_difficulty`
  no vacía marca una fila V3.55 y manda `observed_task_difficulty` (aunque sea
  `''`); sin la marca, fila legacy → `observed_difficulty` (paridad exacta).

### B. Ledger aditivo e idempotente

`learning_evidence.declared_difficulty`, `served_difficulty` y
`observed_task_difficulty` (`CREATE TABLE` + bucle `ALTER TABLE`, `''` en las
filas legacy). `observed_difficulty` se conserva **escrita como proyección legacy
de `served_difficulty`** y el plumbing llega a
`record_evidence`/`record_evidence_bulk`/`list_evidence`/`list_observed_rows` y a
`EVIDENCE_FIELDS`. `declared`/`served` se escriben siempre (también en el fallo:
son hechos de la tarea); `observed_task` solo en el éxito.

### C. Capacidad honesta (P2-02) — `services/evidence.py`

`observed_signals` lee la carga ACREDITADA (`difficulty.earned_difficulty`) en
lugar de la servida. Un éxito `guided` acredita menos que uno `independent` con
la MISMA carga servida, y un `copied` no acredita nada. El contrato del resumen
no cambia (mismas claves) y la paridad pura↔SQL se mantiene por construcción
(`summarize_by_target` sigue delegando en la MISMA función pura).

### D. Cableado de las cuatro vías — `domain/vocabulary.py`

- **Word/Sentence** (`guided`): −2 pasos.
- **Recall** (`cued`/`guided` según `RECALL_CUE_SUPPORT`): −1 / −2 pasos.
- **Write** (`independent`): carga completa.
- **Transfer** (`spontaneous`): carga completa; `declared` es la carga léxica del
  ítem y `served` el vector del contexto elegido.

El volcado de producción del chat libre (`_record_production_evidence`) queda
**explícitamente fuera de alcance**: recibe solo las formas producidas, así que
declarar la carga léxica exigiría una consulta extra por palabra en el camino
caliente. Sus eventos siguen con `''`.

## Qué NO cambia

- `level_from_capacity` y el gate CEFR global de V3.53.1.
- `observed_skill_capacity` / `observed_capacity` / `learner_capacity` y el gate
  de cobertura de V3.54: consumen el mismo contrato de `observed_signals`.
- `CEFR_CAPACITY`, `transfer_state` y sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt`, FSRS.
- El planner, que sigue siendo el scorer de V3.38-V3.51 (`expected_learning_value`
  es el siguiente bloque).

## Verificación

- Nuevo `backend/tests/test_task_difficulty_v355.py` (17 tests): tabla de
  descuento y monotonicidad, `declared_difficulty` (incluido el `0` sin CEFR),
  serialización de las tres dificultades y del fallo, marca V3.55 vs. legacy en
  `earned_difficulty`, capacidad acreditada por apoyo, suelo alcanzado por
  `guided` vs. `independent` vía `learner_skill`, helper compartido del drill
  léxico, escritura y transferencia de punta a punta, caché del perfil con
  capacidad léxica de `written_production`, migración idempotente y paridad
  pura↔SQL.
- Cero regresión en el bloque V3.51-V3.54 (236 tests verdes en local).
- `ruff` limpio; `check_release_consistency` (**3.55.0**).

## Fuera de alcance (V3.56+)

- `expected_learning_value` y el **Planner 2.0** (P1-03): es el siguiente salto.
- Declarar la dificultad en el volcado de producción del chat libre.
- Latencia y errores como moduladores de la capacidad (hoy son señales del
  planner, no de la carga acreditada), transferencia y novedad contextual.
- Sense Engine 2.0 y Context Engine 3.0.

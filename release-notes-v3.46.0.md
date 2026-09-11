# v3.46.0 — Condición de recuperación en la transferencia (`transfer_condition`)

**Cierre quirúrgico del P1 `transfer_condition` que la auditoría externa de
V3.43.0 deja abierto sobre la evidencia longitudinal: TODO intento de
transferencia era `spontaneous_use` con `support_level="spontaneous"`, sin
distinguir si la unidad se usó porque se pidió (`prompted`), porque el escenario
la insinuaba (`cued_context`), por decisión propia en un escenario abierto
(`open_context`), por elección libre (`free_choice`) o porque surgió sola
(`naturally_emergent`). Sin esa dimensión, el Student Model no puede ponderar la
evidencia y `transfer_demonstrated` podía declararse con tareas ANDAMIADAS.
Release ADITIVA y SIN migración destructiva: columna
`transfer_condition TEXT NOT NULL DEFAULT ''` en `learning_evidence` (ALTER
idempotente) y contratos HTTP estrictamente aditivos. La condición la DERIVA el
servidor de la evidencia (premisa 21): el cliente nunca la declara.**

Versión de app `3.45.0 → 3.46.0`. Backend (`services/transfer.py`,
`services/evidence.py`, `repositories/db.py`, `repositories/evidence.py`,
`domain/vocabulary.py`, `schemas/vocabulary.py`) + frontend (`types/api.ts`,
`features/vocabulary/wordDrill.tsx`, `features/vocabulary/wordDrillSteps.tsx`,
`utils/i18n.ts`) + tests y docs.

## Contexto

La V3.43.0 separó el transfer LÉXICO de la adecuación semántica y añadió
`transfer_state` (`not_ready` → `emerging` → `contextualized` →
`transfer_demonstrated` → `transfer_stable` → `automatic`), pero dejó una
ambigüedad de fondo: **todos** los intentos se registraban igual, así que una
tarea que NOMBRA o INSINÚA la palabra objetivo pesaba lo mismo que un escenario
abierto donde el alumno decide libremente usarla. La auditoría de V3.43.0 lo
señaló como P1: sin la CONDICIÓN DE RECUPERACIÓN, `transfer_demonstrated` podía
declararse con apoyo.

Fuera de alcance (diferido a V3.47): CEFR/`difficulty_vector` del contexto (el
otro P1 restante) y el resto de P2 (Context Bank 2.0, diversidad 2.0, semantic
appropriateness, transfer_state enriquecido y Adaptive Planner 2.0 /
`expected_learning_value`).

## Qué cambia

- **Taxonomía `transfer_condition` (`services/transfer.py`).** `TRANSFER_CONDITIONS`
  en orden de andamiaje decreciente: `prompted` > `cued_context` > `open_context`
  > `free_choice` > `naturally_emergent`. `SERVABLE_CONDITIONS` son las que sirve
  el drill (`prompted`/`cued_context`/`open_context`); `UNSCAFFOLDED_CONDITIONS`
  (`open_context`/`free_choice`/`naturally_emergent`) son las que ni dan ni exigen
  la unidad; `REQUIRED_TARGET_CONDITIONS` son las que sí la exigen.
  `CONDITION_INSTRUCTIONS` documenta la instrucción de cada condición y el
  `prompt` servido se compone como escenario del banco + instrucción (el
  escenario nunca contiene la unidad salvo en `prompted`, que la nombra a
  propósito y por eso queda registrada como la condición más débil).
  `normalize_condition` sanea valores desconocidos a `""` (legacy).
- **Escalera por evidencia (`condition_for_state`, PURA).** `not_ready` con
  intentos previos → `prompted` (el alumno no recupera ni con contexto: se
  nombra); `not_ready` sin intentos y `emerging` → `cued_context` (comportamiento
  de V3.43, sin regresión); `contextualized` o superior → `open_context`
  (escenario abierto, unidad NO obligatoria). La condición se DERIVA del resumen
  del ledger, nunca la declara el cliente.
- **Persistencia aditiva (`repositories/db.py`, `repositories/evidence.py`).**
  Columna `transfer_condition TEXT NOT NULL DEFAULT ''` en `learning_evidence`
  (ALTER idempotente con `PRAGMA table_info`), con plumbing en `record_evidence`,
  `record_evidence_bulk`, `list_evidence` y el SELECT de detalle de
  `summarize_by_target`. La paridad pura↔SQL se mantiene por construcción: el
  resumen SQL reutiliza la MISMA `context_signals`.
- **Evidencia endurecida (`services/evidence.py`).** `context_signals` agrega
  `transfer_conditions` (`{condición: {attempts, clean_successes}}`),
  `success_conditions` (condiciones con ≥1 éxito limpio, en orden de andamiaje
  decreciente) y `unscaffolded_clean_successes`. `transfer_state` mantiene la
  regla de V3.43 (2 contextos limpios + `diverse_dimensions >= 2`) y
  `transfer_demonstrated` exige ADEMÁS ≥1 éxito limpio en una condición NO
  andamiada. Sin datos de condición (resumen legacy/parcial, o intentos previos a
  V3.46) la regla anterior se conserva: nunca hay regresión. `empty_summary`
  expone los campos nuevos.
- **Dominio y contratos aditivos (`domain/vocabulary.py`, `schemas/vocabulary.py`).**
  `get_transfer_context` deriva la condición del resumen y la sirve;
  `submit_transfer_attempt` la RE-deriva (el cliente no la declara) y la persiste.
  Un intento de `open_context` que NO usa la unidad no se registra como evidencia
  (no hay nada que observar sobre el objetivo) y el contrato lo expone
  (`required_target=false`). `TransferContextOut` añade `condition`,
  `required_target` y `unscaffolded`; `TransferAttemptOut` añade `condition` y
  `required_target`.
- **UI e i18n (`wordDrillSteps.tsx`, `wordDrill.tsx`, `utils/i18n.ts`).** El paso
  Transfer muestra la condición servida (`transferConditionLabel` +
  `transferConditionPrompted`/`Cued`/`Open`/`Free`/`Natural`) y, cuando la unidad
  no es obligatoria, un aviso NEUTRO (`transferNotRequired`) en lugar del aviso
  de objetivo ausente. Paridad es/en.

## Tests

- Backend pytest **2047 passed** (+17): nuevo `test_transfer_condition_v346.py`
  cubre la taxonomía, `normalize_condition`/`condition_instruction`/
  `condition_for_state`, `context_for` por condición, la agregación de
  `context_signals`, el endurecimiento de `transfer_state` con fallback legacy,
  la persistencia aditiva, la paridad pura↔SQL y el comportamiento de los
  endpoints.
- Se ajustan `test_learning_evidence_v336.py` (contrato del resumen vacío) y
  `test_transfer_v340.py`: regresión fijada — un éxito solo en `cued_context` NO
  declara `transfer_demonstrated`; el mismo éxito en `open_context` sí.
- Frontend vitest **72 ficheros/623 tests** (+2 en `wordDrill.test.tsx`: condición
  visible y aviso neutro cuando no era obligatorio usar la palabra).
- Verificación: `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.46.0**
  exit 0.

## Fuera de alcance (V3.47+)

- CEFR/`difficulty_vector` del contexto (P1 restante).
- Context Bank 2.0, diversidad 2.0, semantic appropriateness y transfer_state
  enriquecido (`confidence`/`evidence_count`/`recency`).
- `expected_learning_value` / Adaptive Planner 2.0 y Student Model
  multidimensional.

## Decisiones de diseño

- **El servidor deriva la condición, el cliente no la declara.** La condición se
  calcula del `transfer_state` del resumen del ledger (premisa 21): el LLM no
  decide evidencia y el cliente no puede declarar un éxito como «espontáneo».
- **El andamiaje no se toca, se mide.** `support_level` sigue declarando el
  andamiaje de la ACTIVIDAD (`spontaneous`); `transfer_condition` es la dimensión
  FINA de la recuperación y la que decide si un éxito limpio puede acreditar
  transferencia.
- **No usar la palabra en un escenario abierto no es un error.** En
  `open_context` (y en el resto de condiciones no andamiadas) la unidad no es
  obligatoria: no se registra evidencia ni se muestra el aviso de objetivo
  ausente, sino un mensaje neutro que invita a intentarlo la próxima vez.
- **Cero regresión en datos legacy.** Sin datos de condición, `transfer_state`
  aplica la regla de V3.43; los intentos anteriores a V3.46 quedan como `""` y no
  bloquean el estado que ya tenían.

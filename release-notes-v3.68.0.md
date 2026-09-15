# v3.68.0 — Adaptive Engine Hardening & Integrity

> Release **SIN migración destructiva** (migración ADITIVA e idempotente:
> dos columnas nuevas en `decision_records`), **SIN bump de
> `GENERATOR_VERSION`**, **SIN tocar el banco**, **SIN capacidad pedagógica
> nueva** y **SIN tocar el argmax del Planner** que cierra los TRES P1 de
> segunda generación de la auditoría de V3.67 más el P2-08. Es la **primera
> release de la serie que toca el frontend por un motivo de MEDICIÓN y no de
> UI**: el eslabón de cliente que V3.67 dejó fuera hace que el ciclo de vida
> del provenance se ejecute de verdad end-to-end.

## Contexto

V3.67 cerró los P1 de V3.66 pero dejó tres deudas de segunda generación que la
auditoría de V3.67 encontró **en el código**, no en el diseño:

1. **P1-01 — tarea ≠ tarea+contexto.** La identidad de tarea
   (`task_signature`) incluía el contexto entre sus seis componentes, y el
   candidato del Planner se construía con `context=""` (el contexto se elige
   en el GET del peldaño). Resultado: una tarea de transferencia registrada en
   el ledger **nunca casaba** con el candidato, así que el nivel
   `task_empirical` de la jerarquía era inalcanzable justo para la actividad
   que más lo necesita.
2. **P1-02 — lifecycle de mentira.** `mark_served`/`mark_completed` existían
   desde V3.67, pero **el cliente nunca devolvía `decision_id`** (cero
   ocurrencias en `frontend/src`). En producción el ciclo de vida **no se
   ejecutaba nunca**, todas las filas quedaban en `computed` y
   `calibration_report` devolvía siempre `completed_count = 0`. Además
   `mark_started`/`mark_abandoned` no tenían **ningún** llamador y
   `_transition()` hacía `UPDATE ... WHERE decision_id = ?` sin guard de estado
   previo ni de usuario (aceptaba `completed → served`, `computed → completed`,
   etc.).
3. **P1-03 — provenance sin propiedad ni target.** Las columnas
   `context_id`, `context_instance` y `provenance_status` existían desde V3.67
   y **nunca se escribían**: nada ligaba una fila al usuario que la ejecutó ni
   al target realmente servido. Un `decision_id` filtrado o adivinado podía
   mover la decisión de otro alumno.
4. **P2-08 — denominador sucio.** El ledger **no** contamina sus tasas con
   `unclear` (el ASR fallido "no se registra fallo"), pero `calibration_report`
   sí lo contaba como no-éxito, mezclando *no medido* con *fallado*.

## Cambios

### A · Task Definition vs Task Instance (P1-01, `services/observed_difficulty.py`)

Renombrado honesto de la firma y separación en dos niveles:

- `task_key_parts(target_id, activity, support_level, served_difficulty, assessed_skill)`
  — pura: identidad de la **DEFINICIÓN** (cinco componentes, **sin contexto**).
  Es la identidad que el Planner **puede** calcular antes de elegir instancia.
- `task_instance_key_parts(..., context)` — pura: `task_key` + separador +
  contexto (los seis componentes de V3.67).
- `task_key(row)` / `task_instance_key(row)` — adaptadores de fila (leían
  `facts.context_instance`/`facts.context_id` y
  `task_semantics.assessed_skill_for(activity)`).
- `empirical_success_by_task(rows)` pasa a agrupar por **`task_key`**
  (definición) y se añade `empirical_success_by_task_instance(rows)`.
- `task_signature_parts`/`task_signature` se **eliminan** (rename, no alias):
  actualizados `services/lexicon.py`, `domain/review.py`, `domain/decision.py`
  y los tests.

**Este es el cierre del P1-01**: el nivel `task_empirical` de la jerarquía de
resolución ya es alcanzable por una tarea de transferencia, porque el contexto
—que se resuelve vacío en la cola— **ya no forma parte de la identidad de la
tarea**. La identidad de INSTANCIA se conserva y se expone, pero **no puntúa**
(ver «Fuera de alcance»).

### B · FSM real del ciclo de vida (P1-02, `repositories/decision_records.py`)

Tabla de transiciones **declarada** (`_ALLOWED_TRANSITIONS`) y probada:

| Origen | Destino | ¿Válida? |
|---|---|---|
| `computed` | `served` | sí |
| `served` | `served` | sí (idempotente: refresh de la cola) |
| `served` | `started` | sí |
| `served` | `completed` | **sí y declarada** (best-effort: sin declaración de inicio no se pierde el outcome) |
| `served` / `started` | `abandoned` | sí |
| `started` | `started` | sí (idempotente) |
| `started` | `completed` | sí |
| `completed` | `completed` | solo si el `outcome` es **idéntico** |
| `abandoned` | `abandoned` | sí (idempotente) |
| `computed → started/completed/abandoned`, `completed → *`, `abandoned → *` | — | **rechazo con contador** |

`_transition()` pasa de un `UPDATE` ciego a un **compare-and-set** racional:

```python
UPDATE ... WHERE decision_id = ? AND user_id = ?
  AND decision_status IN (<estados de origen válidos>)
# rowcount > 0  -> "ok"
# rowcount == 0 -> SELECT de diagnóstico -> clasifica el rechazo y suma contador
```

`close_stale(user_id, *, before_iso)` barre `served`/`started` con
`COALESCE(served_at, created_at) < before_iso` a `abandoned` (nunca toca
`computed`, `completed` ni `abandoned`).

### C · Integridad y propiedad del provenance (P1-03)

Guardas con fallo **best-effort NO-OP silencioso + contador** (decisión
declarada: nunca rompe la cola ni el drill, el estado no cambia y el rechazo
queda visible en el informe):

- `decision_records.user_id == user_id` → **propiedad** (un `decision_id` de
  otro alumno no mueve nada).
- `decision_records.target_id == target_id` cuando llega `target_id`.
- La **actividad** NO es puerta: se **registra** como hecho
  (`executed_activity`) y se deriva `activity_match`. Motivo declarado: el
  drill degrada peldaños (recognition → recall → sentence) y el alumno puede
  cambiar de rung, así que una actividad distinta es un hecho legítimo y
  además señal de auditoría del Planner; rechazarla perdería medición.

`transition_health()` expone contadores **separados** (`missing`,
`wrong_owner`, `target_mismatch`, `invalid_transition`, `closed_decision`,
`duplicate_outcome`) junto al `record_failures` de V3.67.

### D · Re-servicio y `provenance_status` vivo

El `decision_id` es determinista, así que una decisión **puede re-servirse**.
Regla declarada:

- El upsert **reabre** una fila terminal **sin outcome medible** (`abandoned`,
  o `completed` con `unclear`/`''`) → `decision_status = 'computed'`,
  timestamps y `outcome` limpiados, `provenance_status = "reopened"`.
- Una fila terminal **con outcome medible** (`ok`/`ko`) **no se sobrescribe**:
  la medición manda y el nuevo servicio se cuenta como `closed_decision`.

`provenance_status` deja de ser una columna muerta (`recorded` | `reopened`).

`build_decision_id` pasa a hashear `task_key` (definición) en vez de la firma
de instancia, y `DECISION_POLICY_VERSION = "v3.68.0"`. **Cambia el hash**: los
`decision_id` nuevos no coinciden con los de V3.67 (las filas de V3.67 quedan
en `computed`, que es su estado real).

### E · Migración aditiva e idempotente (`repositories/db.py`)

Mismo patrón `PRAGMA table_info` de V3.67, dos columnas nuevas:

- `task_key TEXT NOT NULL DEFAULT ''`
- `executed_activity TEXT NOT NULL DEFAULT ''`

### F · Calibración honesta (P2-08, `calibration_report`)

- Solo entran en las bandas las filas **MEDIDAS** (`outcome ∈ {ok, ko}`):
  `unclear` y `abandoned` quedan **fuera del denominador** y del
  `calibration_error`.
- Contadores explícitos: `completed_count` (todas las `completed`),
  `measured_count`, `unclear_count`, `abandoned_count`.
- `list_decisions`/`_row_to_decision` exponen además `task_key`,
  `task_instance_key` (derivada con la función pura cuando hay contexto),
  `executed_activity`, `activity_match` y `outcome_measured`.

### G · Barrido y salud (`domain/review.py`)

- Constante declarada `DECISION_ABANDON_AFTER_HOURS = 24`: una decisión
  servida y no completada en 24 h queda abandonada.
- `get_review_queue` ejecuta `close_stale(...)` una vez por construcción de
  cola, best-effort (un fallo nunca rompe la cola).
- `provenance_health()` pasa a devolver
  `{"record_failures": N, "transition_health": {...}}` (contadores
  monotónicos en memoria; `0` es lo sano).

### H · Endpoints (`routers/vocabulary.py` + esquemas)

- `_mark_served`/`_mark_completed` llevan `user["id"]`, el `target_id` (la
  palabra del peldaño) y la `activity` del peldaño
  (`recognition`/`recall`/`sentence`/`write`/`transfer`).
- `drill_transfer_context` mueve su `mark_served` **después** de resolver el
  contexto, para declarar `context_id`/`context_instance` de la instancia
  realmente servida.
- `drill_write_attempt` declara `served` al inicio (no tiene GET).
- Nuevo `POST /api/vocabulary/drill/decision-lifecycle` con
  `DecisionLifecycleIn {decision_id, event}` y
  `event ∈ {"started", "abandoned"}` validado por `Literal`: el eslabón que
  hoy no existía. Best-effort, nunca rompe el drill.

### I · Frontend, el eslabón que hace REAL el ciclo (P1-02)

- `frontend/src/types/api.ts`: `ReviewQueueItem` gana `decision_id?`,
  `task_key?` y `task_instance_key?`.
- `frontend/src/api/vocabulary.ts`: **todas** las funciones del drill aceptan
  `decisionId?` y lo reenvían (query en los GET, body/FormData en los POST):
  `getDrillSentenceContext`, `submitDrillSentenceAttempt`,
  `getDrillRecognitionQuestion`, `submitDrillRecognitionAttempt`,
  `getDrillRecallPrompt`, `submitDrillRecallAttempt`,
  `submitDrillWriteAttempt`, `getDrillTransferContext`,
  `submitDrillTransferAttempt`. Nuevas `markDrillStarted` /
  `markDrillAbandoned` contra el endpoint H.
- `frontend/src/features/vocabulary/wordDrill.tsx`: nueva prop opcional
  `decisionId?`. **Al cargar el peldaño** (el GET resolvió) declara `started`:
  la FSM rechaza `computed → started`, así que declararlo al montar competiría
  con el GET y el evento se perdería por una carrera. **Al desmontar** declara
  `abandoned`; el servidor lo rechaza si la decisión ya está `completed`, así
  que la terminalidad la decide la FSM, no el cliente. Sin `decisionId` (drill
  abierto desde el diccionario) no se llama nada.
- `frontend/src/features/vocabulary/ReviewQueueSection.tsx`: pasa
  `decisionId={active.decision_id}` a `WordDrill`.

## Tests

Nuevo `backend/tests/test_decision_v368.py` (**29**, escritos antes del
código):

- **A** · `task_key` ignora el contexto y `task_instance_key` lo incluye;
  **regresión del P1-01**: el ledger con dos filas de la MISMA definición en
  contextos distintos produce UNA entrada de tarea con `attempts = 2` y el
  candidato del Planner (`context` vacío) **casa**; el nivel de instancia las
  separa.
- **B** · FSM: transiciones válidas, `served → completed` declarada, rechazos
  (`computed → completed`, `completed → started`, `completed → served`) con
  contador, idempotencia (`served → served`, `completed` con outcome idéntico)
  y rechazo con outcome distinto.
- **C** · Integridad: `decision_id` de otro usuario → sin cambio +
  `wrong_owner`; target distinto → sin cambio + `target_mismatch`;
  `list_decisions` de A nunca devuelve filas de B; `executed_activity` y
  `activity_match` registrados.
- **D** · Re-servicio: fila `abandoned` reabierta con
  `provenance_status = "reopened"`; fila `completed` con `ok` **no** se
  sobrescribe y el nuevo servicio cuenta como `closed_decision`.
- **E** · Barrido: `close_stale` cierra `served`/`started` antiguas y no toca
  `computed`/`completed`/`abandoned` recientes.
- **F** · Calibración: `unclear` y `abandoned` fuera de bandas y del
  denominador; `measured_count`/`unclear_count`/`abandoned_count` correctos.
- **G** · Router (`TestClient` de drill): el `decision_id` devuelto por la
  cola, enviado en el GET del peldaño y en el POST del intento, deja la fila
  en `served` y luego en `completed` con `outcome`; el endpoint
  `decision-lifecycle` marca `started`.

Actualizados `test_decision_v367.py` (rename de la firma y nuevas aridades de
`mark_served`/`mark_completed`), `test_decision_v366.py` y los tests de
frontend (`vocabulary.test.ts`, `wordDrill.test.tsx`,
`ReviewQueueSection.test.tsx`): el `decision_id` viaja en las URLs y el ciclo
de vida se dispara al montar/desmontar.

## Honestidad

- El ciclo de vida **ahora se ejecuta**: hasta V3.67 era código muerto en
  producción porque el cliente no devolvía el `decision_id`. Es un arreglo de
  MEDICIÓN, no de pedagogía (no cambia ninguna decisión de tarea).
- La FSM es **declarada y probada**: cada transición válida y cada rechazo
  tiene nombre y contador. `served → completed` es válida a propósito
  (best-effort: preferimos un outcome medido a un rechazo burocrático).
- Los fallos de integridad son **no-op silenciosos contabilizados**: la
  propiedad y el target se defienden, pero nunca a costa de romper la cola o
  el drill; el rechazo se ve en `transition_health()`, no en el flujo del
  alumno.
- El re-servicio es **explícito**: una medición real (`ok`/`ko`) nunca se
  sobrescribe; solo se reabre lo que no medía nada.
- `DECISION_POLICY_VERSION` cambia el hash: los `decision_id` de V3.68 no
  coinciden con los de V3.67. Las filas de V3.67 se quedan en `computed` (su
  estado real) y no se migran a la fuerza.

## Fuera de alcance (declarado)

- **Adaptive Instance Selection**: el nivel de instancia se **nombra, deriva y
  observa** (`task_instance_key`, `empirical_success_by_task_instance`), pero
  **no puntúa** el argmax en V3.68. El Planner sigue decidiendo por tarea.
- La formalización `decision → serving → attempt` en tablas separadas (§6 de
  la auditoría): V3.68 la resuelve con la regla de re-servicio y **un outcome
  por decisión** — el del PRIMER intento de la sesión; los siguientes se
  registran en el ledger y cuentan como `closed_decision`.
- **Snapshot único** (retention + planner dentro del mismo `Decision
  Snapshot`) y **calibración real (ML)**: siguen en fases posteriores. El
  informe de calibración sigue siendo **descriptivo**.

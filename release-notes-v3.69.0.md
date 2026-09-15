# v3.69.0 — E2E + Adaptive Engine Validation

> **Release de VALIDACIÓN, no de capacidad.** **SIN migración**, **SIN bump de
> `GENERATOR_VERSION`**, **SIN tocar el banco**, **SIN capacidad pedagógica
> nueva**, **SIN tocar el argmax del Planner** y **con cero líneas de LÓGICA de
> producto** (el único diff en rutas de producto son los **bumps de versión**:
> `backend/config.py` y `frontend/package.json` + `package-lock.json`): lo que
> entra son **tests** (20 escenarios E2E por HTTP + 2 specs de navegador) y
> **documentación**. No cierra ningún P de la auditoría
> `Y` de V3.68; **convierte en evidencia** lo que hasta ahora era una
> afirmación: que la cadena `Evidence → Student State → Decision Projection →
> Task selection → Decision → Serving → Attempt → Outcome → Evidence` funciona
> **como una sola pieza**.
>
> **Regla dura declarada (auditoría `Y` §28):** *V3.69 no debe introducir
> arquitectura nueva salvo que una prueba E2E demuestre que la arquitectura
> actual es insuficiente.* **Resultado: ningún escenario la demostró
> insuficiente ⇒ no se ha tocado producción.** Las cinco desviaciones que la
> batería **sí** ha destapado se registran en §«Hallazgos E2E», **todas
> aceptadas como deuda declarada**.

## Contexto

La auditoría externa `Y` de V3.68 (`docs/audit/Y-AUDITORIA-TOTAL-V368.md`, §19–§20)
dio el veredicto **9,3/10 con 0 P0 · 0 P1** y pidió, antes de entrar en
cualquier componente probabilístico (calibración real, Expected Learning Gain
real), **demostrar experimentalmente** el circuito completo. El estado de
partida tenido en cuenta:

1. **Ningún test recorría el circuito completo por HTTP.** El precedente más
   cercano (`test_decision_v368.py:755`) hacía el GET del peldaño con
   `decision_id` y comprobaba `decision_status == "served"`: **no había POST ni
   outcome**. La calibración se probaba a nivel de repositorio, no por API.
2. **`GET /api/learning/decisions` era un endpoint huérfano**: sin una sola
   ocurrencia en los tests, a pesar de ser la ventana pública a la calibración
   y a la salud del provenance.
3. **El eslabón de cliente de V3.68** (el `decision_id` viajando por los GET/POST
   del drill y el ciclo `started`/`abandoned`) solo estaba cubierto con mocks de
   módulo en Vitest, **nunca** en un navegador real.

V3.69 ataca los tres frentes con **tests escritos antes** de cualquier
corrección (regla de la casa), y con una decisión de método explícita: **si un
escenario falla, primero se decide si el contrato está bien y el test mal, o al
revés**; nunca se diseña producción para que el test pase.

## A · Batería E2E (`backend/tests/test_adaptive_e2e_v369.py`, 20 tests)

`TestClient` sobre `main.app` con BD en `tmp_path` (`monkeypatch`), fechas
**fijas** derivadas de un ancla, sin `random()` y sin reloj real. Cada escenario
tiene su nombre literal para que el mapeo con la auditoría sea 1:1.

| Id | Test | Qué se afirma (respuesta HTTP / estado observable) |
|---|---|---|
| **E01** | `test_e01_new_learner_closes_the_loop` | (a) arranque en frío: la cola sirve tarea **sin** `decision` ni `decision_id`; (b) con estado medible: `decision_id` → GET (`served`) → POST (`completed`, `ok`) → evidencia escrita → la reconstrucción de la cola **no** reabre la medición. |
| **E02** | `test_e02_weak_skill_raises_its_priority` | La skill débil domina el diagnóstico: `limiting_skill` y `skill_priorities` mueven la cola en la dirección declarada. |
| **E03** | `test_e03_retention_chooses_review` | Carta FSRS vencida ⇒ el Planner elige **repaso** para ese ítem. |
| **E04** | `test_e04_transfer_gap_raises_production` | Reconocer/recuperar fuertes y producción débil ⇒ aparece actividad de **producción**. |
| **E05** | `test_e05_same_task_two_contexts_are_two_instances` | Misma tarea en dos contextos por HTTP ⇒ **mismo `task_key`**, **distinto `task_instance_key`** (la separación de V3.68, ejercitada desde el cliente). |
| **E06** | `test_e06_failure_changes_p_success` | `ok, ok, ko` espaciado ⇒ el `p_success` **baja** y `why` lo declara con el `p_success_source` coherente. |
| **E07** | `test_e07_unclear_does_not_punish_mastery` | `unclear` **no** penaliza mastery, **no** entra en el denominador de calibración (`unclear_count` sube, `measured_count` no) y **conserva** la fila del provenance. |
| **E08** | `test_e08_abandon_does_not_contaminate_ko` | Abandono del lifecycle ⇒ `decision_status = "abandoned"`, `outcome = ""`, sin `ko` fantasma en la calibración (ver hallazgo **E08**). |
| **E09** | `test_e09_repeated_refresh_does_not_duplicate` | `GET /api/learning/review` ×3 ⇒ mismo `decision_id` por ítem y **una sola fila** en el ledger. |
| **E10** | `test_e10_double_submit_is_idempotent` | `completed(ok)` ×2 ⇒ la segunda no altera ni duplica; contador `duplicate_outcome`. |
| **E11** | `test_e11_contradictory_submit_is_rejected` | `completed(ok)` y luego `completed(ko)` ⇒ **rechazado** (la medición manda). |
| **E12** | `test_e12_wrong_user_changes_nothing` | Otro alumno intenta cerrar la decisión ⇒ **no-op** + `wrong_owner`. |
| **E13** | `test_e13_wrong_target_is_rejected` | Intento sobre otro ítem ⇒ **rechazado** + `target_mismatch`. |
| **E14** | `test_e14_invalid_transition_is_rejected` | `computed → completed` (sin `served`) ⇒ **rechazado** + `invalid_transition`. |
| **E15** | `test_e15_stale_serving_becomes_abandoned` | Servida de >24 h ⇒ cerrada como **`abandoned`** por `close_stale` y **nunca** contada como `completed` (ver hallazgo **E15**). |
| **E16** | `test_e16_planner_is_deterministic` | Mismos matriz/evidencia/fingerprint/candidatos/política ⇒ **mismo task, `p_success`, ELV, `why` y `decision_id`**, en el nivel **puro** y en el nivel **HTTP**, comparados byte a byte. |
| **E16b** | `test_e16b_decisions_endpoint_reports_calibration_and_health` | Contrato **completo** de `GET /api/learning/decisions`: `{decisions, calibration, provenance_health}`, contadores, bandas, y **filtros** (`status`, `target_id`) + **paginación** (`limit`/`offset`). |
| **E17** | `test_e17_scaffolding_gap_penalizes_the_task` | Hueco servido − acreditado ⇒ mueve la decisión (**aserción diferencial** entre dos gemelos) con respaldo puro de `scaffolding_gap` (ver hallazgo **E17**). |
| **E18** | `test_e18_evidence_arriving_during_the_decision_is_not_sealed_stale` | (a) evidencia nueva entre dos lecturas ⇒ **cambia** decisión y sello; (b) TOCTOU reproducido **en proceso** ⇒ con huella anterior ≠ posterior el sello **nunca** se declara fresco. |
| **E19** | `test_e19_two_active_learners_do_not_mix_state` | Dos alumnos intercalando `cola(A) → cola(B) → completo(A) → completo(B)` ⇒ **cero mezcla** de estado, cola, `decision_id`, `decisions` y `calibration`, **en ambas direcciones**. |

**Mapeo con los 10 casos de la auditoría `X` de V3.67:** (1) nuevo → E01; (2)
skill débil → E02; (3) dependencia de apoyo → E17; (4) mala retención → E03;
(5) fallos repetidos → E06; (6) no transfiere → E04; (7) ASR `unclear` → E07;
(8) dos usuarios → E12 + E19; (9) refresh repetido → E09; (10) evidencia
durante la decisión → E18. **Cobertura completa**, con E05/E08/E10/E11/E13/E14/
E15/E16 como aportaciones nuevas exigidas por las auditorías `X`/`Y`.

## B · Contrato de frontend con red mockeada (`frontend/tests/visual/drillProvenance.spec.ts`)

El job `playwright` de CI arranca **solo** el dev server de Vite (sin backend),
así que el contrato del cliente se fija con `page.route` sobre el navegador
**real** (Chrome del sistema, proyecto `desktop`; los proyectos `tablet` y
`mobile` las saltan por breakpoint, como el resto de specs de layout):

1. **`decision_id` en el transporte.** El GET del peldaño lo lleva en la
   **query** (`…/drill/recall?…&decision_id=d-recall`) y el POST del intento en
   el **body**.
2. **`started` se declara DESPUÉS** de que el peldaño esté cargado (la FSM
   rechaza `computed → started`), y su body lleva `decision_id` **y**
   `target_id` del ítem servido.
3. **`abandoned` al desmontar** el drill (navegación SPA), con el mismo
   `decision_id`. La terminalidad la decide el **servidor**: el cliente declara
   y la FSM acepta o rechaza.
4. **Sin `decision_id` no se declara nada**: ni query en el GET ni una sola
   llamada al endpoint del ciclo de vida, tampoco al desmontar.

**Nota de implementación (para futuras specs):** el matcher de `page.route` debe
excluir `/src/api/*.ts` — los **módulos** de la app. Un glob `**/api/**` los
captura y deja la aplicación sin arrancar (el síntoma es un `#root` vacío con la
consola limpia). Aquí se usa `^https?://[^/]+/api/`.

## C · Hallazgos E2E (tabla obligatoria de §E del briefing)

Los cinco hallazgos están **medidos** (no deducidos), fijados por un test y
**aceptados como deuda declarada**: ninguno justifica tocar producción en una
release de validación, y ningún escenario ha demostrado que la arquitectura sea
insuficiente.

| Id | Comportamiento observado | Comportamiento esperado (según el contrato declarado) | Decisión tomada | Test que lo fija |
|---|---|---|---|---|
| **E01(a)** | Con un alumno **sin ninguna celda medida**, la cola sirve la tarea de la cascada pero **sin** bloque `decision` y **sin** `decision_id`: el provenance no existe todavía. | La auditoría `Y` daba el circuito por cubierto «de un extremo al otro» desde el primer minuto. | **Aceptado como deuda/declaración** (es la degradación declarada de V3.64: `has_comparable_capacity` es la puerta del Planner 3.0). Queda **escrito** en el briefing y aquí: el circuito es observable **desde que hay estado medible**. | `test_e01_new_learner_closes_the_loop` (mitad (a)) |
| **E08** | El abandono del lifecycle deja la fila en `decision_status = "abandoned"` y **no entra** en el informe de calibración (que solo carga `completed`). El `abandoned_count` del informe cuenta **otra cosa**: filas `completed` con `outcome = "abandoned"`, hoy **inalcanzables** por el camino público. | «El abandono se ve en el informe». | **Aceptado como deuda** (asimetría de **observabilidad**, no de cálculo: el abandono está correctamente **fuera del denominador**). Se traslada a la fase de analítica/calibración (P2-05). | `test_e08_abandon_does_not_contaminate_ko` |
| **E15** | Una servida caducada se cierra como `abandoned`… y la **siguiente** construcción de cola la **reabre** (`provenance_status = "reopened"`) porque la misma decisión vuelve a servirse; sigue sin outcome. | «Una servida caducada queda abandonada y no vuelve». | **Aceptado como deuda** (consecuencia deliberada del `decision_id` determinista y del re-servicio de V3.68): el registro representa el **estado final**, no la **historia** (P2-04, `decision_events` append-only). Lo que el contrato **sí** prohíbe — y el test afirma — es que acabe contando como `completed`. | `test_e15_stale_serving_becomes_abandoned` |
| **E17** | `SCAFFOLDING_PENALTY` **engorda el `gap`** de la modalidad limitante en `decision_projection.skill_components`, así que el alumno **con** hueco servido − acreditado recibe un `expected_learning_value` **MAYOR** y un `why` que declara el hueco grande. | «El hueco de andamiaje **penaliza la tarea**» (nombre de la constante: *penalty*). | **Aceptado como deuda + pregunta al auditor**: la dirección real es *perjuicio en el diagnóstico* (el hueco pesa en la elección de modalidad), **no** *descuento en la puntuación*. Es un problema de **nombre/semántica**, no de argmax; se traslada a **Planner 4.0** (P2-06). | `test_e17_scaffolding_gap_penalizes_the_task` |
| **§F-1** | El doble montaje de **`StrictMode`** (el launcher sirve `npm run dev`, es decir build de **desarrollo**, así que ocurre en el producto) declara un `abandoned` **prematuro** antes de que el peldaño se sirva. La FSM lo **rechaza** (`computed → abandoned` es inválida) y lo contabiliza como `invalid_transition`. | «El cliente solo declara el abandono de lo que llegó a servirse». | **Aceptado como deuda** (no corrompe nada: la fila no se toca y la medición posterior se cierra bien). Ensucia un contador de salud en cada montaje de drill. **Arreglo mínimo propuesto para V3.70** (2 líneas, no arquitectura): declarar el abandono solo si el peldaño llegó a cargarse (`startedDeclaredRef`), con su aserción en `wordDrill.test.tsx`. | `drillProvenance.spec.ts` (spec 1) |

**Dos decisiones de método declaradas (sometidas a dictamen externo):**

- **E15** invoca `close_stale(user_id, *, before_iso=…)` **directamente** para
  controlar el reloj del barrido. Es la **excepción declarada** a la regla «solo
  HTTP» del briefing (§A.3) y está motivada: la alternativa era inyectar un reloj
  nuevo en producción, y la regla dura lo prohíbe. El resto del escenario es HTTP.
- **E18(b)** es la mitad que **toca internals** (intercala una fila durante la
  lectura con `monkeypatch`). No es alcanzable por HTTP de forma determinista y
  el briefing lo declaraba así: se reproduce el TOCTOU en proceso y se afirma la
  regla de V3.64.1. Si esta mitad hubiera obligado a cambiar producción, **no**
  se habría implementado (regla dura).

## D · Determinismo como contrato (E16)

El motor es determinista **por diseño**, y esta release lo fija como contrato
verificable en los dos niveles: **puro** (`select_task_by_elv` +
`expected_learning_value` con entradas fijas, comparados `==` sobre el `dict`
completo) y **HTTP** (`GET /api/learning/review` repetido sobre la misma BD sin
mutación intermedia ⇒ mismo `decision_id` y mismo orden, garantizado por el
desempate canónico `-ELV, -priority, retrievability, word`). Una regresión de
determinismo —el enemigo real de la calibración futura— **rompe la batería**.

## Tests y verificación

- **Backend:** `ruff check .` (el gate de lint que corre el CI) → **All checks
  passed**; `pytest -q` → **2552 passed** (2532 → **+20**), 0 fallos;
  `python -m scripts.transfer_validation` → `OK=True`. Los tres se han corrido
  **en secuencia**, no en paralelo, para que ningún número quede contaminado por
  contención de CPU.
- **Frontend:** `vitest` → **659 passed** (sin cambios: no se tocó código de
  producto). `tsc --noEmit` y `build` OK.
- **Navegador:** Playwright **+2 specs** (`drillProvenance.spec.ts`), verdes en
  `desktop`; en `tablet`/`mobile` salen **saltadas** porque la spec se declara
  «solo desktop» con `test.skip` sobre el viewport.
- **Launcher:** **75 passed** (sin cambios: no se tocó el launcher).
- **Gates de script:** `check_release_consistency` (**3.69.0** en los 6 sitios),
  `check_beta_v3`, `content_validation` y `transfer_validation`.

**§G-1 · Deriva de formato PREEXISTENTE (no es un gate, y no se declara limpia).**
`ruff format --check .` **no** forma parte del CI (`ci.yml` corre solo
`ruff check .`), y en este árbol **no está limpio**: se reformatearían ficheros
que V3.69 **no ha tocado** (`services/transfer_audit.py`,
`services/decision_projection.py`, `config.py`…). Se ha comprobado contra el
arbol sin cambios (`git status` limpio en esos ficheros, `ruff format --check`
sobre ellos → *would be reformatted*): es **previo** al diff de esta release. Se
deja tal cual —arrastrar un reformateo masivo a una release de validación sería
ruido, no valor— pero queda **medido y escrito** en vez de declarado limpio.

**§G-2 · Intermitencia LOCAL de un spec preexistente (ajena a V3.69).**
`resize.spec.ts` (preexistente) falla de forma **intermitente en local** por
`element(s) not found` en el separador del panel Analysis: pasa **aislado** y
falla en tandas completas. Se ha reproducido **excluyendo** la spec nueva
(`npx playwright test --grep-invert decision_id` → 1 failed: el mismo
`resize.spec.ts`), así que **no** lo provoca esta release. Es sensible a la
carga de la máquina y al estado del dev server local (el backend :8000 no está
levantado y el proxy devuelve `ECONNREFUSED`). El job `playwright` del CI **sí
ha salido verde en el run de release** (**25 passed + 26 skipped**, sin fallos),
así que la intermitencia queda **acotada al entorno local** y el CI es la
referencia válida.
- **CI (medido, con enlace verificable):** commit `9a4e70a`, tag anotado
  `v3.69.0`, **6/6 workflows verdes** en el run
  [34978215154](https://github.com/jvelasca/english-tutor/actions/runs/34978215154):
  Backend ruff + pytest (**2550 passed + 2 skipped**), Frontend tsc + vitest
  (**76 ficheros / 659 tests**) + build, Playwright E2E (**25 passed + 26
  skipped**: las **+2 specs nuevas**, verdes), Release consistency (**3.69.0**),
  Beta V3.0 gate y Content validation. Los 2 `skipped` son
  `test_stt_asr_integration.py` (modelo Whisper opt-in no descargado en el
  runner); en local el mismo árbol da **2552 passed**. Es un resultado **del
  run**, comprobable por su enlace: sigue **sin ser una verificación
  independiente del auditor**.

## Honestidad

- **No se ha tocado una sola línea de LÓGICA de producto.** Verificado sobre el
  árbol publicado: `git diff v3.68.0 v3.69.0 --stat -- backend frontend
  ':!backend/tests' ':!frontend/tests'` → **2 ficheros, 2 líneas**, y son los
  **bumps de versión** (`backend/config.py` `3.68.0 → 3.69.0` y
  `frontend/package.json`, más su `package-lock.json`). El valor de esta
  release está en lo que **mide** y en lo que **declara**, no en lo que añade: si
  esta release se juzgara por su diff de producto, sería vacía; si se juzga por
  lo que su batería demuestra y por los cinco hallazgos que destapa, es la
  release que convierte la confianza en evidencia.
- **Cinco hallazgos incómodos, todos aceptados.** Ninguno se ha «arreglado»
  retocando el test ni cambiando producción: se han dejado **fijos con su
  comportamiento real** y documentados. Dos de ellos (E17 y §F-1) llevan
  propuesta concreta para V3.70.
- **Lo que esta release NO demuestra:** que la calibración sea *buena* (sigue
  siendo **descriptiva** por bandas de 0,2 y requiere tráfico real), que el
  Planner use recencia o Expected Learning Gain real (sigue siendo heurístico,
  P2-06), que exista identidad lógica `serving_id`/`attempt_id` (P2-03), ni que
  el lifecycle no pierda eventos (sigue **best-effort**, P2-01). Nada de eso se
  declara cubierto aquí.
- **Los tests son de contrato, no de implementación:** se afirma sobre la
  **respuesta HTTP** y el estado observable por API, con las dos excepciones
  declaradas de E15 y E18(b).
- **`DECISION_POLICY_VERSION` y `GENERATOR_VERSION` no se tocan** (sería
  contradecir el alcance de validación): la política de decisión y el contenido
  siguen siendo los de V3.68.

## Fuera de alcance (deuda declarada, sin cambios respecto a V3.68)

- **P2-01** *provenance failure rate* como release health metric · **P2-02**
  normalización de `decision_records` · **P2-03** identidad `serving_id`/
  `attempt_id` · **P2-04** `decision_events` append-only (historia vs estado
  final: es la raíz del hallazgo **E15**) · **P2-05** calibración real (*Brier*,
  *log loss*, *ECE*, *reliability diagram*; incluye el hallazgo **E08**) ·
  **P2-06** recencia + Expected Learning Gain real (**Planner 4.0**; incluye el
  hallazgo **E17**).
- **P3-01** `planner_execution_fidelity` · **P3-02** **Sense Engine** · el
  arreglo mínimo del hallazgo **§F-1** (V3.70).
- **V3.70** auditoría pedagógica/CEFR (siguiente incremento) → **V3.71**
  runtime/offline/instalación → **V3.72** UX/product completion → **V3.73**
  auditoría final técnica → **V4.0** release final y `V4.0.x` de mantenimiento.

## Higiene de release

- `backend/config.py` → `VERSION = "3.69.0"` (fuente única) · `frontend/package.json`
  y `frontend/package-lock.json` (2 sitios) · `README.md` · `CHANGELOG.md`
  (entrada `## [3.69.0]` en cabecera) · `PLAN.md` (bullet de «Estado actual», M13
  y tablero de briefings) · `docs/RELEVO.md` (nota nueva + «0. START HERE»).
- `release-notes-v3.69.0.md` (este documento).
- Commit de release `9a4e70a` + tag anotado `v3.69.0` + push a `main`; run de CI
  [`34978215154`](https://github.com/jvelasca/english-tutor/actions/runs/34978215154)
  registrado con **6/6** jobs verdes.

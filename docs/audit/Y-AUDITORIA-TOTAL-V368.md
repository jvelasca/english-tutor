# Y — Auditoría total de V3.68.0 (Adaptive Engine Hardening & Integrity)

> **Posición auditada:** release **`v3.68.0`** → commit
> `8acee38396aaf38c4e7846bbc6e78025fe20de54`. Commit posterior de documentación:
> `d5311cc3e338b9cd1540e84f6d9a23aefb2e6f49`.
> **Comparación:** `v3.67.0` `150186adb84d43c72c507a4917ae5f762cc7daa7` →
> `v3.68.0` `8acee38396aaf38c4e7846bbc6e78025fe20de54`.
> **Autor:** auditoría externa (agente con acceso solo al repositorio).
> **Fecha:** 2026-09-15.
> **Relación con las letras reservadas:** la letra `V` sigue reservada para el
> informe externo de V3.62 (`agentes/auditoria-externa-v362.md`) y la `W` quedó
> usada por V3.63; la `X` la usó V3.67; de ahí que esta auditoría use la `Y`
> (la `Z` queda libre).
> **Respuesta del proyecto:** sección «Respuesta del proyecto — roadmap
> actualizado (post-V3.68)» al final de este documento, más la nota de cabecera
> de `docs/RELEVO.md` y el briefing `agentes/v369-e2e-adaptive-validation.md`.

## Alcance

- **Se audita:** el salto `v3.67.0 → v3.68.0` —`services/observed_difficulty.py`
  (Task Definition vs Task Instance), `repositories/decision_records.py` (FSM
  `_ALLOWED_TRANSITIONS`, compare-and-set, `close_stale`, `transition_health`),
  `repositories/db.py` (migración aditiva de dos columnas),
  `routers/vocabulary.py` + `schemas/vocabulary.py` (contrato del `decision_id`
  y endpoint de lifecycle), `calibration_report` y el **frontend del drill**
  (`api/vocabulary.ts`, `wordDrill.tsx`, `ReviewQueueSection.tsx`)—, más la
  arquitectura acumulada V3.64→V3.68 donde V3.68 la toca.
- **No se audita:** el banco de contextos, el scoring, FSRS, la UI/i18n y el
  detalle interno de V3.52–V3.67 salvo en lo que el delta de V3.68 afecta.

## Veredicto

V3.68 es, en términos arquitectónicos, **la mejor versión del motor adaptativo
hasta ahora**. Por primera vez la auditoría **no encuentra ningún P1** que
justifique otra gran modificación arquitectónica del Adaptive Engine.

| Área | Valoración |
|---|---|
| Arquitectura | 9,8/10 |
| Task Identity | 9,7/10 |
| Decision Lifecycle | 9,4/10 |
| Provenance | 9,2/10 |
| Integridad de datos | 9,2/10 |
| Snapshot/consistencia | 9,1/10 |
| Planner | 9,3/10 |
| Testing | 9,2/10 |
| Pedagogía/adaptación | 8,9/10 |
| Preparación para congelar arquitectura | 9,5/10 |
| **Global** | **9,3/10** |

**Hallazgos: P0 = 0 · P1 = 0 · P2 = 6 · P3 = 5.**

V3.68 declara como objetivo cerrar los tres P1 de segunda generación de V3.67 y
el problema de calibración asociado, **sin introducir nueva capacidad
pedagógica ni alterar el argmax del Planner**. La auditoría confirma que lo
consigue.

## 1. Objetivo declarado y qué ha conseguido realmente V3.68

La release declara «Adaptive Engine Hardening & Integrity»: **endurecer** lo ya
construido, no ampliarlo. La evolución V3.64 → V3.65 → V3.66 → V3.67 → V3.68 ya
tiene coherencia interna:

```
Evidence → Student Skill State → Decision Projection → Task Identity →
Empirical Success → Planner → Decision Provenance → Task Attempt → Outcome →
Calibration
```

Y con V3.68 aparecen, por primera vez y de forma explícita, las tres fronteras
que faltaban:

```
TASK DEFINITION ≠ TASK INSTANCE
DECISION → SERVING → ATTEMPT → OUTCOME
PROVENANCE anclado a (user_id, target_id)
```

## 2. P1-01 de V3.67 — Task vs Task Instance: **CERRADO correctamente**

Este era el problema más delicado de V3.67. Antes:

```
task_signature =
  target + activity + support + difficulty + assessed_skill + context
```

pero el Planner todavía no conocía el contexto. Por tanto:

```
ledger:
  apple|transfer|spontaneous|...|context-A

planner:
  apple|transfer|spontaneous|...|<sin contexto>
```

no coincidían. V3.68 lo separa correctamente:

```
TASK DEFINITION =
  target_id + activity + support_level + served_difficulty + assessed_skill

TASK INSTANCE =
  TASK DEFINITION + context
```

`empirical_success_by_task()` trabaja sobre la **definición** y
`empirical_success_by_task_instance()` sobre la **instancia**. Los tests
verifican explícitamente que dos contextos distintos son **dos instancias de una
misma tarea**.

**Consecuencia:** `P(success | learner, task)` puede calcularse **antes** de
elegir el contexto, y `P(success | learner, task_instance)` podrá existir cuando
haya información suficiente.

**Estado: 🟢 CERRADO.** *No se recomienda tocar más la identidad en V3.69.*

## 3. Muy buena decisión — no mezclar contexto con `decision_id`

`build_decision_id()` utiliza `user_id`, `target_id`, `task_key`,
`decision_start_fingerprint` y `policy_version`, y **no** la instancia/contexto.
Eso es lo correcto porque el orden real es:

```
Planner → decide TASK → GET → selecciona INSTANCE
```

y no al revés. Si se hubiera metido el contexto en el `decision_id` se habrían
vuelto a mezclar dos niveles semánticos. **Correcto.**

## 4. P1-02 de V3.67 — Lifecycle: **CERRADO técnicamente**

V3.68 mejora muchísimo aquí. Existe una **FSM declarada**:

```
computed → served → started → completed
                                ↘
                              abandoned
```

y además contempla `served → completed` para no perder mediciones si el cliente
no consigue declarar `started`. La tabla `_ALLOWED_TRANSITIONS` es la **fuente
única de verdad** y las escrituras utilizan **compare-and-set**.

Eso elimina el antiguo problema:

```
completed → served
computed  → completed
abandoned → completed
```

**Estado: 🟢 CERRADO.**

## 5. Buena decisión — `served → completed`

A primera vista podría parecer que rompe una FSM estricta. **No.** En este
sistema el `frontend lifecycle` es **best-effort**. Si se obligase
`served → started → completed` y fallase la llamada `started`, se perdería un
outcome que sí se tiene. Por tanto `served → completed` es una **transición
válida de tolerancia operacional**, y la documentación y los tests lo declaran
expresamente. **Decisión correcta.**

## 6. P1-03 de V3.67 — Ownership/integrity: **CERRADO**

Las transiciones son `mark_*(user_id, decision_id, ...)` y la consulta utiliza
**ambos** (`decision_id AND user_id`); además `target_id` es comprobado. La
**actividad, correctamente, no es una barrera dura**: el drill puede degradar
`recognition → recall → sentence → write → transfer` y esa degradación es un
**hecho de ejecución** que debe medirse, no necesariamente un error. V3.68
registra `executed_activity` y `activity_match` **en lugar de destruir la
medición**.

**Estado: 🟢 CERRADO.**

## 7. Frontend: se ha solucionado un problema REAL, no cosmético

En V3.67 el backend exponía `mark_started()`/`mark_abandoned()` pero **el
cliente no completaba el round-trip** en producción. V3.68 añade `decisionId` al
`WordDrill`, lo transmite por GET/POST y añade `markDrillStarted()` /
`markDrillAbandoned()`. La propia release identifica correctamente que antes el
lifecycle podía quedar como **código muerto** en producción. Ahora:

```
GET task → served → task loaded → started → attempt → completed
```

**Exactamente lo que se necesitaba.**

## 8. P2 — El lifecycle todavía es best-effort

El backend hace `try: mark_... except Exception: logger.debug(...)`. Es decir:
**si falla el provenance, no falla el aprendizaje**. Para una aplicación
educativa local es una decisión razonable, pero significa que el sistema puede
tener *learning evidence* correcta y *provenance* perdida.

La release añade `transition_health()` para contar `missing`, `wrong_owner`,
`target_mismatch`, `duplicate_outcome` e `invalid_transition`, lo que permite
detectarlo.

**Recomendación de la auditoría:** no convertirlo en P1. En la fase final, el
**provenance failure rate** debería ser una *release health metric*: `0` →
perfecto; `>0` → warning; significativo → **bloquear release**.

## 9. P2 — El provenance todavía mezcla Decision y Serving

Aunque ahora está mucho mejor, se sigue almacenando todo en `decision_records`.
Conceptualmente hay cuatro cosas:

```
DECISION · SERVING · ATTEMPT · OUTCOME
```

y no cuatro entidades independientes. **No se recomienda normalizarlo ahora**:
para una aplicación local sobre SQLite sería probablemente sobreingeniería. Pero
debe fijarse este modelo conceptual:

```
Decision
  1
  │
  └── N Servings
          │
          └── 0..N Attempts
```

aunque físicamente se siga utilizando una única tabla de provenance.

**Estado: P2 arquitectónico menor.** No debería convertirse en una V3.69.

## 10. P2 importante — `decision_id` no identifica un serving

Este es el matiz más importante que queda. El `decision_id` es determinista:

```
user + target + task + snapshot + policy
```

Por tanto una misma decisión puede:

```
computed → served → abandoned → reopened → served
```

Eso es correcto, **pero** entonces `decision_id` identifica **la decisión**, no
cada vez que esa decisión fue servida. Para análisis posteriores hay que
distinguir:

```
decision_id · serving_id · attempt_id
```

No necesariamente mediante tres tablas, pero **sí mediante una identidad
lógica**, porque en el futuro se querrá preguntar «¿cuántas veces recomendamos
esta tarea?» y no «¿cuántas decisiones únicas existen?».

**Estado: P2.**

## 11. P2 — La reapertura de decisiones es correcta, pero requiere cuidado

V3.68 hace:

```
terminal + sin medición  → reopened → computed
terminal + ok/ko         → NO sobrescribir
```

Esta regla es buena, pero tiene un efecto secundario:

```
decision A → abandoned → reopened → completed
```

sigue teniendo el **mismo** `decision_id`. Para auditoría histórica, el
`decision_records` actual representa el **estado final**, no necesariamente la
**historia completa** de cada ciclo. Esto limita `time-to-start`,
`number_of_reopens` y `number_of_servings`.

**Solución futura** (no ahora): una tabla append-only `decision_events`
(`decision_id`, `event`, `timestamp`, `metadata`). Es funcionalidad de
**analítica posterior**.

## 12. P2 — `unclear` ya está correctamente separado: **CERRADO**

Ahora `ok`/`ko` son outcomes medibles, mientras que `unclear` y `abandoned`
**no entran** en la calibración. El informe distingue `completed_count`,
`measured_count`, `unclear_count` y `abandoned_count`, y la release lo documenta
explícitamente. **Exactamente lo que se necesitaba.**

**Estado: 🟢 CERRADO.**

## 13. P2 — La calibración sigue siendo muy básica

Se tiene `predicted` vs `observed` por bandas de 0,2. Es útil, pero todavía no
hay *reliability diagram*, *Brier score*, *log loss*, *ECE* ni *sample size
confidence*.

**Pero NO debe hacerse todavía**, porque no hay suficiente tráfico real:

```
primero collect → después observe → después calibrate
```

**No al revés.**

## 14. P2 — El Planner sigue usando tasas empíricas sin recencia

La jerarquía actual:

```
task_empirical → target_empirical → skill_empirical → margin
```

es correcta, pero `task_empirical` es esencialmente *todos los intentos medidos
históricamente*. `recent_rate` existe como **estadística descriptiva**, pero
**no gobierna** todavía la decisión. Eso significa que un alumno con `90 %` hace
20 meses puede seguir pesando junto con los últimos `5 : 20 %`. Será
especialmente relevante para aprendizaje real.

**Solución futura** (Planner 4.0, no V3.69): *long-term evidence* + *recent
evidence* + retención FSRS + intervalo + recencia, y posteriormente calibración.

## 15. P2 — Todavía no existe Expected Learning Gain real

Existe `expected_learning_value`, pero sigue siendo esencialmente una función
**heurística**. No se está midiendo:

```
Δ skill · Δ retention · Δ transfer · Δ automaticity
```

producido por una tarea. Por eso el Planner sabe «probablemente esta tarea tenga
una probabilidad X de éxito», pero todavía **no** sabe «esta tarea produce Y
unidades de aprendizaje esperado». Es probablemente **la mayor deuda conceptual
restante** del motor adaptativo — y precisamente por eso **no debe
implementarse ahora**: hacen falta datos.

## 16. P2 — `activity_match` puede ser una señal muy valiosa

V3.68 introduce `selected_activity`, `executed_activity` y `activity_match`. Es
excelente para la fase de análisis: permitirá descubrir que el Planner
recomienda `sentence` y el sistema ejecuta `transfer`, o que recomienda `recall`
y el sistema degrada a `sentence`. Eso puede revelar que el Planner está
seleccionando tareas que el sistema **no puede servir** en determinadas
circunstancias. Debería convertirse posteriormente en una métrica
`planner_execution_fidelity`, pero no hace falta otro motor ahora.

## 17. P2 — `target_id` sigue siendo una pieza fuerte de identidad

Aunque ahora existe `task_key`, el `target_id` sigue funcionando como **puerta de
integridad**. Está bien, pero hay que vigilar la evolución del sistema hacia:

```
lexical unit · sense · task · instance
```

porque `apple` no necesariamente significa una única unidad pedagógica
(`apple` = fruta / `Apple` = compañía). Una misma superficie puede representar
sentidos diferentes. Esto conecta con la deuda histórica del **Sense Engine**,
que **sigue pendiente**.

## 18. Lo que NO debe entrar en V3.69

Después de V3.68 **no se recomienda continuar inmediatamente con otra gran
modificación del Planner**. El propio release declara ya el motor adaptativo
como **congelado**, con el roadmap:

```
V3.69 E2E → V3.70 pedagogía → V3.71 runtime/offline → V3.72 UX →
V3.73 auditoría final → V4.0
```

La auditoría está de acuerdo con ese planteamiento.

## 19. El cambio respecto al plan anterior — V3.69 como VALIDACIÓN

Sí hay un cambio, y es de matiz: **V3.69 no debe añadir funcionalidad**. Debe
**comprobar experimentalmente** el circuito completo:

```
Evidence → Student State → Decision Projection → Task selection →
Decision → Serving → Attempt → Outcome → Evidence
```

demostrándolo con **escenarios controlados**. Es decir: V3.69 pasa de
«E2E Adaptive Engine (circuito completo)» a
**«E2E + Adaptive Engine Validation»**.

## 20. V3.69 — batería E2E obligatoria

| Id | Escenario | Qué debe demostrar |
|---|---|---|
| **E01** | Alumno nuevo | sin evidencia → tarea inicial → intento → evidencia → nueva decisión |
| **E02** | Weak skill | `speaking` débil y `writing` fuerte → debe aumentar correctamente la prioridad de `speaking` |
| **E03** | Retention | `mastered` → pasa el tiempo → `review due` → el Planner elige repaso |
| **E04** | Transfer gap | `recognition` fuerte, `recall` fuerte, `production` débil → debe aparecer producción |
| **E05** | Context transfer | misma tarea, contextos distintos → debe distinguir **task** vs **instance** |
| **E06** | Failure | `success, success, failure` → el `p_success` debe cambiar correctamente |
| **E07** | ASR uncertainty | `unclear` → **no** penalizar mastery indebidamente, **no** entrar en calibración, **conservar** provenance |
| **E08** | Abandon | `served → started → abandoned` → **no** debe contaminar `ko` |
| **E09** | Refresh | `GET/GET/GET` → debe conservar `decision_id` **sin duplicar** decisiones |
| **E10** | Double submit | `completed(ok)` dos veces → debe ser **idempotente** |
| **E11** | Contradictory submit | `completed(ok)` + `completed(ko)` → debe **rechazarse** |
| **E12** | Wrong user | `user B` con `decision_id` de `A` → **no** debe modificar nada |
| **E13** | Wrong target | decision `target = apple`, attempt `target = orange` → debe **rechazarse** |
| **E14** | Invalid transition | `computed → completed` → debe **rechazarse** |
| **E15** | Stale serving | `served > 24 h` → debe terminar como `abandoned` |
| **E16** | **Planner determinism** | mismo Student State + fingerprint + candidatos + política → mismo `selected task`, `p_success`, `ELV`, `reason` y `decision_id` **siempre** |

E16 es especialmente importante: **se está construyendo un motor determinista
antes de entrar en cualquier componente probabilístico.**

## 21. V3.70 — Auditoría pedagógica

Aquí cambia por completo el tipo de auditoría. Ya no se mira tanto
*Python / TypeScript / SQLite* como:

```
CEFR · curriculum · activities · difficulty · assessment · evidence ·
mastery · retention · transfer
```

comprobando la correspondencia `A1…C2` contra `Vocabulary · Grammar ·
Listening · Reading · Writing · Speaking · Pronunciation · Interaction ·
Mediation`. Será probablemente **el trabajo más grande que queda**, porque el
motor puede estar perfectamente construido y aun así el contenido no ser
suficientemente bueno para enseñar inglés de verdad.

## 22. V3.71 — Offline real

El proyecto declara **100 % local**, así que habrá que probar con **Internet
desconectado** que funcionan `frontend`, `backend`, `SQLite`, `Ollama`,
`Whisper`, `Piper`, `dictionary`, `TTS`, `STT`, `course`, `practice` y `review`.
**No basta con que «normalmente» funcione offline.**

## 23. V3.72 — UX final

`Onboarding · Dashboard · Course · Practice · Review · Speaking · Listening ·
Dictionary · Progress · Profile · Settings`, y especialmente:
**«¿entiende el alumno qué está haciendo y por qué?»**.

## 24. V3.73 — Auditoría final

Debe ser una auditoría de **cierre**, no de desarrollo: `P0/P1` → **0
permitido**; `P2` → solo los imprescindibles; `P3` → backlog de mantenimiento.

## 25. V4.0

V4.0 **no** debe significar «otra versión con nuevas funcionalidades». Debe
significar: **English Tutor — primera versión completa y estable**. Después,
`V4.0.1`, `V4.0.2`, … para bugs, UX, calibración, contenido, rendimiento,
accesibilidad y pequeños ajustes pedagógicos.

## 26. Estado real del proyecto después de V3.68

| Subsistema | Estado |
|---|---|
| Evidence model | 🟢 |
| Student Skill State | 🟢 |
| Retention/FSRS | 🟢 |
| Transfer | 🟢 |
| Context Engine | 🟢/🟡 |
| Task Identity | 🟢 |
| Task Instance | 🟢 |
| Empirical success | 🟢 |
| Decision Projection | 🟢 |
| Planner 3.x | 🟢 |
| Decision Provenance | 🟢 |
| Lifecycle FSM | 🟢 |
| Ownership | 🟢 |
| Calibration | 🟡 |
| Expected Learning Gain | 🟡 |
| Sense Engine | 🟡 |
| Curriculum | 🟡 |
| Listening corpus | 🟡 |
| Speaking assessment | 🟡 |
| E2E | 🟡 |
| Offline | 🟡 |
| UX | 🟡 |

## 27. Conclusión de la auditoría

V3.68 consigue algo que la auditoría considera fundamental: **se ha llegado al
punto en el que ya no hace falta seguir complicando el núcleo adaptativo para
que sea arquitectónicamente defendible.** Existen `TASK ≠ TASK INSTANCE`,
`DECISION → SERVING → ATTEMPT → OUTCOME`, `USER OWNERSHIP`, `SNAPSHOT`,
`EMPIRICAL SUCCESS`, `PROVENANCE` y `CALIBRATION` (aunque todavía descriptiva),
implementados de forma coherente. La nueva FSM y la separación
`task_key`/`task_instance_key` están además **respaldadas por tests
específicos**, no solamente por documentación.

**El riesgo mayor del proyecto ya no es arquitectónico.** Ahora es:

1. que el flujo **E2E** no funcione perfectamente;
2. que el **contenido pedagógico** no tenga la calidad/progresión necesaria;
3. que el funcionamiento **100 % offline** tenga alguna dependencia oculta;
4. que la **UX** no haga comprensible todo este modelo al alumno.

Ese es exactamente el terreno en el que deben concentrarse las próximas
versiones.

## 28. Plan recomendado a partir de ahora

```
                         V3.68
                           │
             ┌─────────────┴─────────────┐
             │  ADAPTIVE ENGINE           │
             │  CONGELADO                 │
             └─────────────┬─────────────┘
                           ▼
                    V3.69 E2E
                           │
                           ▼
              VALIDAR QUE REALMENTE
                 FUNCIONA COMO UNO
                           │
                           ▼
              V3.70 PEDAGOGÍA / CEFR
                           │
                           ▼
              V3.71 OFFLINE / RUNTIME
                           │
                           ▼
                  V3.72 UX FINAL
                           │
                           ▼
                V3.73 AUDITORÍA FINAL
                           │
                           ▼
                         V4.0
                           │
              ┌────────────┴────────────┐
              │                         │
           BUG FIXES              CALIBRACIÓN
              │                         │
              └────────────┬────────────┘
                           ▼
                    MANTENIMIENTO
```

**Regla dura para las próximas versiones:** *V3.69 no debe introducir
arquitectura nueva salvo que una prueba E2E demuestre que la arquitectura actual
es insuficiente.* Eso protege del ciclo «encontramos una mejora teórica → hacemos
otra versión → encontramos otra mejora teórica → hacemos otra versión…».

## 29. Verificación del cierre declarado

La documentación de V3.68 afirma **2532 tests backend y 659 Vitest**, además de
los restantes gates; el commit de documentación registra el **CI como 6/6**. La
auditoría **no obtuvo una lista de workflow runs verificable** mediante la API de
GitHub, por lo que considera esos resultados **declarados por el release, no
verificación independiente**. Esa distinción se mantendrá también en las
siguientes auditorías.

## 30. Tabla de hallazgos

> **Nota de trazabilidad.** El informe del auditor declara la cuenta
> `P0 = 0 · P1 = 0 · P2 = 6 · P3 = 5` y desarrolla cada hallazgo en el texto,
> pero **no entrega una lista enumerada con identificadores**. La numeración
> `P2-0x` / `P3-0x` de esta tabla es una **derivación del proyecto** a partir del
> texto (§8 a §17 y §29), y se marca como tal: queda **pendiente de validación
> por el auditor**. Las severidades y el contenido no se reinterpretan.
>
> **Criterio de derivación aplicado** (para que la cuenta cuadre con la
> declarada sin reescribir el informe):
>
> 1. Se parte de los **diez** apartados que el informe trata explícitamente como
>    **P2** (§8 lifecycle best-effort, §9 provenance mezcla, §10 `decision_id` sin
>    serving, §11 reapertura, §12 `unclear` —que el propio informe declara
>    **cerrado**—, §13 calibración básica, §14 Planner sin recencia, §15 sin
>    Expected Learning Gain real, §16 `activity_match` y §17 `target_id`), de los
>    que quedan **nueve abiertos** al descontar §12.
> 2. Donde la cuenta de 6 obliga a consolidar, se consolidan los dos apartados
>    que describen **la misma deuda subyacente** (§14 sin recencia y §15 sin
>    Expected Learning Gain real: ambas afirman que el Planner sigue siendo
>    heurístico y que falta evidencia real), en una sola fila `P2-06`.
> 3. Los dos apartados que el informe presenta como **mejora futura de
>    observabilidad** y **deuda histórica ya conocida** —`activity_match` como
>    `planner_execution_fidelity` (§16) y `target_id` frente al Sense Engine
>    (§17)— se registran como **P3**, que es la severidad que el propio informe
>    les da en su recomendación explícita («posteriormente», «sigue pendiente»,
>    «no hace falta implementar otro motor ahora»).
>
> Si el auditor confirma otra frontera P2/P3, esta tabla se corrige sin más
> discusión: la fuente de verdad es su informe, no esta derivación.

### P2 (6)

| # | Hallazgo | Sección | Estado |
|---|---|---|---|
| **P2-01** | Lifecycle **best-effort**: el provenance puede perderse sin afectar al aprendizaje. Falta el *provenance failure rate* como release health metric (`0` OK · `>0` warning · significativo → bloquear release). | §8 | abierto · aceptado |
| **P2-02** | `decision_records` sigue mezclando **DECISION / SERVING / ATTEMPT / OUTCOME** en una sola entidad física. Se fija el modelo conceptual `Decision 1—N Servings 1—N Attempts` **sin** normalizar ahora. | §9 | abierto · aceptado (no V3.69) |
| **P2-03** | `decision_id` identifica **la decisión**, no cada serving/attempt: falta la identidad lógica `serving_id`/`attempt_id`. | §10 | abierto |
| **P2-04** | La **reapertura** conserva el `decision_id` y el registro representa el **estado final**, no la historia: no son derivables `time-to-start`, `number_of_reopens` ni `number_of_servings`. Solución futura (no ahora): `decision_events` append-only. | §11 | abierto · aceptado |
| **P2-05** | **Calibración básica** por bandas de 0,2: sin *reliability diagram*, *Brier*, *log loss*, *ECE* ni confianza por muestra. **Deliberadamente aplazada**: primero *collect*, luego *observe*, después *calibrate*. | §13 | abierto · aceptado |
| **P2-06** | El **Planner usa tasas empíricas sin recencia** (`task_empirical` = todos los intentos medidos; `recent_rate` no gobierna) y **no existe Expected Learning Gain real** (`expected_learning_value` sigue siendo heurística y no mide Δ skill / Δ retention / Δ transfer / Δ automaticity). Es la mayor deuda conceptual restante; pertenece a Planner 4.0. | §14, §15 | abierto · aceptado |

### P3 (5)

| # | Hallazgo | Sección | Estado |
|---|---|---|---|
| **P3-01** | `activity_match` es una señal valiosa pero **sin métrica agregada**: debería convertirse en `planner_execution_fidelity`. | §16 | abierto · mejora futura |
| **P3-02** | `target_id` sigue siendo puerta de identidad léxica: `apple` (fruta) ≠ `Apple` (compañía). Deuda pendiente del **Sense Engine** (`surface ≠ sense`). | §17 | abierto (deuda histórica) |
| **P3-03** | El **CI (6/6) y los recuentos de tests** quedan como **declarados por el release, no verificados de forma independiente** por el auditor. | §29 | declarado · no verificable |
| **P3-04** | **Hallazgo documental detectado por el proyecto al archivar esta auditoría:** la sección «0. START HERE — para el gerente que retoma ahora» de `docs/RELEVO.md` sigue anclada en `v3.65.0`, desfasada desde V3.66. | — (nuevo) | corregido en esta actualización |
| **P3-05** | `close_stale(...)` se ejecuta **una vez por construcción de cola** (`domain/review.py`): un alumno inactivo conserva servings `served` sin barrer hasta que vuelve a pedir la cola. | — (nuevo) | abierto · menor |

**Recordatorio explícito de la auditoría:** los hallazgos §12 (`unclear`
correctamente separado) queda **cerrado** y no vuelve a contarse como P2; el
P2-08 de V3.67 está **cerrado**.

---

# Respuesta del proyecto — roadmap actualizado (post-V3.68)

El proyecto **acepta el veredicto** y **no abre ninguna modificación
arquitectónica** del motor adaptativo: los tres P1 de segunda generación de V3.67
y el P2-08 quedan cerrados y confirmados por la auditoría.

**Cambios de roadmap aplicados (2026-09-15):**

| Elemento | Antes | Ahora |
|---|---|---|
| Naturaleza de V3.69 | «E2E Adaptive Engine (circuito completo)», 10 casos, **sin briefing** | **«E2E + Adaptive Engine Validation»**: **validación experimental**, batería **E01–E16**, con briefing `agentes/v369-e2e-adaptive-validation.md` |
| Regla dura | — | **V3.69 no introduce arquitectura nueva salvo que un escenario E2E demuestre que la arquitectura actual es insuficiente** |
| Diseño del motor adaptativo | congelado tras V3.68 (declarado) | **congelado y confirmado por la auditoría externa** |
| Resto del roadmap | `V3.70` pedagógica → `V3.71` runtime/offline → `V3.72` UX → `V3.73` auditoría final → `V4.0` | **sin cambios** |
| `V4.0` | release final | **«English Tutor, primera versión completa y estable»**, seguida de `V4.0.x` de mantenimiento |

**Hallazgos P2/P3 incorporados al backlog declarado** (no a V3.69):
`provenance failure rate` como release health metric (P2-01), identidad lógica
`serving_id`/`attempt_id` (P2-03), `decision_events` append-only (P2-04),
calibración real con datos (P2-05), recencia + ELG real en **Planner 4.0**
(P2-06) y `planner_execution_fidelity` (P3-01). El **Sense Engine** (P3-02) sigue
siendo la deuda histórica pendiente.

**Correcciones documentales aplicadas en esta actualización:** nota de cabecera
de `docs/RELEVO.md` (P3-04: nota nueva de esta auditoría y corrección de
«START HERE», que declaraba `v3.65.0`), `PLAN.md` (tablero de briefings, bloque
de «Siguiente incremento» con E01–E16 y M13) y briefing de V3.69.

Detalle de la ejecución de V3.68 en `release-notes-v3.68.0.md`.

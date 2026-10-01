# X — Auditoría total de V3.67.0 (Task Identity 2.0 + Decision Lifecycle + Provenance Analytics)

> **Posición auditada:** release **`v3.67.0`** → commit
> `150186adb84d43c72c507a4917ae5f762cc7daa7`. `README.md` y `PLAN.md` ya
> declaraban `3.67.0` como versión estable.
> **Autor:** auditoría externa (agente con acceso solo al repositorio).
> **Fecha:** 2026-09-15.
> **Relación con las letras reservadas:** la letra `V` sigue reservada para el
> informe externo de V3.62 (`agentes/auditoria-externa-v362.md`) y la `W` quedó
> usada por V3.63; de ahí que esta auditoría use la `X`.
> **Respuesta del proyecto:** sección «Respuesta a esta auditoría (V3.68.0)» al
> final de este documento. Detalle de la ejecución en
> `release-notes-v3.68.0.md`.

## Alcance

- **Se audita:** el salto `v3.66.0 → v3.67.0` —`services/observed_difficulty.py`
  (firma de seis componentes y `empirical_success_by_task`),
  `services/planner.py` (jerarquía de cuatro niveles de `p_success`),
  `services/lexicon.py` (seam del candidato y de la tarea servida),
  `domain/decision.py` (mapas empíricos dentro del lazo de sellado),
  `repositories/decision_records.py` (identidad determinista, UPSERT y
  transiciones), `repositories/db.py` (migración aditiva), `domain/review.py`
  (round-trip del `decision_id`) y `routers/learning.py` (analítica del
  provenance)—, más la arquitectura acumulada V3.64→V3.67 donde V3.67 la toca.
- **No se audita:** el banco de contextos, el scoring, FSRS, la UI/i18n y el
  detalle interno de V3.52–V3.66 salvo en lo que el delta de V3.67 afecta.

## Veredicto

V3.67.0 es una versión importante y, conceptualmente, cierra una etapa. **No se
declara todavía «Feature Complete».**

| Área | Valoración |
|---|---|
| Arquitectura | 9,7/10 |
| Modelo de decisión | 9,3/10 |
| Task Identity | 9,0/10 |
| Provenance | 8,5/10 |
| Consistencia de datos | 8,8/10 |
| Seguridad/integridad | 8,3/10 |
| Testing | 8,8/10 |
| Adaptación pedagógica | 8,7/10 |
| Preparación para cierre | 8,8/10 |
| **Global** | **9,0/10** |

**Hallazgos: P0 = 0 · P1 = 3 · P2 = 6 · P3 = 5.**

V3.67 cierra correctamente los dos P1 de V3.66 **en su intención
arquitectónica**, pero al implementarlos aparecen **tres problemas de segunda
generación** que deben cerrarse antes de congelar el motor adaptativo.

## 1. Qué ha conseguido realmente V3.67

La evolución V3.64 → V3.65 → V3.66 → V3.67 ya tiene coherencia:

```
Evidence → Student Skill State → Decision Projection → Task Identity →
Empirical Success → Planner → Decision Provenance → Task Attempt → Outcome →
Calibration
```

V3.67 introduce la cadena de resolución:

```
TARGET → TASK SIGNATURE → TASK EMPIRICAL → TARGET EMPIRICAL →
SKILL EMPIRICAL → CAPACITY MARGIN
```

La firma tiene seis componentes (`target_id`, `activity`, `support_level`,
`served_difficulty`, `context`, `assessed_skill`) y está construida de forma
determinista. Esto **sí** corrige el problema fundamental de V3.66: `target_id`
ya no pretende representar una tarea completa.

## 2. P1-01 — La Task Identity todavía tiene una incompatibilidad importante

**Este es el principal hallazgo conceptual de V3.67.**

La firma incluye `context`, pero el contexto **todavía no existe** cuando el
Planner selecciona la tarea. La propia implementación lo reconoce: el contexto
se deja vacío porque se selecciona en el GET del peldaño.

- `_task_empirical_by_activity()` genera la firma candidata con `context = ""`.
- `task_signature(row)` **puede** incorporar `context_instance` o `context_id`
  del ledger.
- `_task_signature_for()` vuelve a generar la firma final dejando también el
  contexto vacío.

**El problema.** Para una tarea de transferencia:

```
target = apple
activity = transfer
support = spontaneous
difficulty = ...
context = restaurant_negotiation
assessed_skill = spontaneous_use
```

el ledger puede acabar teniendo:

```
apple|transfer|spontaneous|...|restaurant_negotiation|spontaneous_use
```

mientras el Planner, al elegirla, busca:

```
apple|transfer|spontaneous|...||spontaneous_use
```

Son firmas diferentes. Por tanto `task_empirical` **puede no estar disponible
precisamente en las tareas donde el contexto forma parte de la identidad**: la
afirmación `P(success | learner, task)` todavía es **parcialmente** cierta.

**Qué recomienda la auditoría.** No volver a meter simplemente `context_id` en
el Planner, sino separar con más limpieza:

- **TASK DEFINITION** (`task_signature`): `target`, `activity`, `support`,
  `difficulty`, `assessment_mode`, `assessed_skill`.
- **TASK INSTANCE**: `context_family`, `context_instance`, `scenario`, `topic`,
  `register`, `interaction_type`…

De modo que `P(success | learner, task)` **pueda existir antes de elegir la
instancia**, y `P(success | learner, task_instance)` llegue después, cuando haya
datos suficientes. Encaja exactamente con el siguiente nivel evolutivo ya
identificado (**Adaptive Instance Selection**).

**Clasificación: P1** — no se cerraría después de Feature Complete.

## 3. P1-02 — El lifecycle existe, pero no está implementado como lifecycle completo

V3.67 declara `computed → served → started → completed / abandoned`. Es
correcto conceptualmente, pero en el código hay una diferencia importante:
**`mark_started()` existe pero no está integrado en el flujo real.**

Los endpoints llaman `mark_served()` y posteriormente `mark_completed()`, pero
no hay paso operativo que haga `mark_started()`. El ciclo real es
`computed → served → completed`, **no**
`computed → served → started → completed`.

Además, las transiciones hacen un `UPDATE ... WHERE decision_id = ?` **sin
comprobar el estado anterior**. Eso permite conceptualmente
`completed → served`, `completed → started`, `computed → completed` o
`abandoned → completed`, porque **no hay una máquina de estados** que imponga
las transiciones válidas.

**Por qué importa.** El provenance pretende ser la futura fuente para responder
«¿la decisión del Planner fue buena?». Para eso no basta con guardar estados:
los estados tienen que ser **semánticamente fiables**. Hay que convertirlo en
una **FSM real** y rechazar `completed → *`, `abandoned → *`,
`computed → completed` y `computed → started`, salvo que se decida
explícitamente que alguna transición es válida.

**Clasificación: P1.**

## 4. P1-03 — Integridad/autorización del Decision Provenance

Nuevo y más importante de lo que parece. El endpoint usa `current_user`
correctamente, pero `mark_served(decision_id)` y `mark_completed(decision_id)`
reciben **solo** `decision_id`: no reciben `user_id` ni verifican
`decision_records.user_id == current_user.id`.

Por tanto la capa de repositorio permite conceptualmente que el usuario A
conozca el `decision_id` de B, llame a `mark_completed(decision_id)` y **modifique
el provenance de B**. Además, el endpoint que recibe `decision_id` no comprueba
que corresponda al `target`, a la `activity` o al tipo de tarea que se está
ejecutando: una decisión generada para `recall` podría recibir un POST
correspondiente a `write` si alguien suministra ese `decision_id`.

En una aplicación local esto no es una vulnerabilidad remota grave, pero **sí
es un fallo de integridad del modelo de datos**, y se está construyendo
precisamente una infraestructura de medición.

**Solución recomendada.** Todas las operaciones deberían ser
`mark_served(user_id, decision_id)` y la consulta `WHERE decision_id = ? AND
user_id = ?`; además conviene verificar `decision.activity == submitted_activity`
y `decision.target_id == submitted_target`.

**Resultado esperado:** el provenance pasa de «registro que confiamos que el
cliente devuelve correctamente» a «registro **servidor-autenticado** del ciclo
de vida de una decisión».

**Clasificación: P1.**

## 5. El `decision_id` determinista está bien diseñado

Aquí V3.67 hizo exactamente lo que debía. La identidad
(`user_id`, `target_id`, `task_signature`, `decision_start_fingerprint`,
`policy_version`) se convierte en SHA-256 determinista: `GET`/`GET`/`GET` sobre
la misma decisión dan el mismo `decision_id` y el mismo registro, y el UPSERT
evita duplicados. Es una mejora real sobre V3.66.

## 6. Cuestión importante con el significado de «decisión»

Ahora hay dos conceptos bastante bien separados: **decision computation** (el
Planner calcula «para apple la mejor tarea es recall») y **decision serving**
(el usuario recibe realmente «haz este recall»).

Pero todavía falta distinguir **decision**, **task serving** y **attempt**.
Actualmente una decisión puede recibir un resultado. Para la fase final habría
que formalizar:

```
Decision → Serving → Attempt → Evidence
```

No hace falta crear tres tablas ahora, pero **sí debe existir conceptualmente
esa separación**, porque una decisión puede ser `computed → served →
abandoned` **sin intento** y otra `computed → served → started → completed`
**con intento**. Eso será muy importante para medir *Planner recommendation
quality* frente a *Learner performance*.

## 7. La jerarquía de `p_success` está bien, pero no es una probabilidad calibrada

La jerarquía `task_empirical → target_empirical → skill_empirical →
capacity_margin` es conceptualmente correcta, pero `p_success = 1.0` con `2/2` y
`p_success = 1.0` con `200/200` siguen considerándose iguales. V3.67 es honesta y
reconoce que son **tasas descriptivas crudas**, no probabilidades calibradas.
**La auditoría no recomienda hacer ML todavía**: primero hacen falta suficientes
`decision → prediction → attempt → outcome`, y solo después
`raw rate → calibrated probability` con datos reales.

## 8. P2 importante — `unclear` contamina la calibración

Los intentos pueden terminar en `ok`, `ko` o `unclear`. Pero la calibración
calcula `outcome == "ok"` como éxito y, por tanto, **cualquier otro outcome se
interpreta como no éxito**: convierte `unclear` en `failure`, y pedagógicamente
no son lo mismo (fallo de ASR, ausencia de habla, ininteligible, incertidumbre
de MEDIDA).

Debería ser `ok` / `ko` / `unclear` / `abandoned`, y la calibración debería
**excluir `unclear` y `abandoned` del denominador**.

**Clasificación: P2, pero recomienda subirlo a P1 si esta analítica se va a usar
para recalibrar el Planner.**

## 9. P2 — El `recent_rate` no es temporalmente comparable

`RECENT_ATTEMPTS = 5` («últimos 5 intentos») es correcto como estadística
descriptiva, pero «5 intentos en 2 días» y «5 intentos en 60 días» se presentan
igual. No es un problema para V3.67 porque se declara explícitamente como
descriptivo, pero **no debe usarse después como señal de retención sin añadir
tiempo**. Para el futuro: `recent_attempt_rate`, `recent_time_window`,
`recent_success_days`, `interval_distribution`.

## 10. El snapshot coherente ha mejorado mucho

`_recompute()` obtiene `state`, `empirical_by_task` y `empirical_by_target`
dentro del mismo ciclo de sellado y verifica la huella antes/después. Resuelve
buena parte del problema detectado en V3.64/V3.65. **Sin P1 nuevo aquí.**

## 11. P2 — Limitación de snapshot en caché

Con `source = cached` los mapas empíricos se vuelven a obtener del ledger
actual: se puede tener `Student State` con huella `F1` y el mapa empírico con
huella `F2` si entra evidencia entre la validación de caché y la lectura del
ledger. La documentación ya reconoce que en el camino `cached` los mapas son
derivados del ledger actual y best-effort. **No es P1** porque el sistema degrada
razonablemente y la proyección sigue siendo auditable, pero para la versión final
**estado + mapas empíricos + retention + planner deben pertenecer a un único
`Decision Snapshot`**.

## 12. La analítica de Provenance es buena, pero todavía no debe gobernar nada

`GET /api/learning/decisions` con decisiones, filtros, paginación, calibración y
provenance health es correcto **como observabilidad**. Pero no debe cometerse el
siguiente error: `calibration_error → cambiar pesos automáticamente`, **todavía
no**. Primero OBSERVE, después VALIDATE, después CALIBRATE y solo entonces
ADAPT.

## 13. Deuda interesante — no existe todavía aprendizaje del Planner

Ahora podemos medir «el Planner dijo `p_success = 0.65`» y después «el alumno:
OK». Pero **todavía no** tenemos *expected learning gain*, *actual learning
gain*, *retention gain* ni *transfer gain*. Por eso todavía no podemos decir
«esta fue una buena decisión **pedagógica**», solo «la predicción de éxito fue
aproximadamente correcta». Son cosas diferentes.

## 14. Diseño final del Adaptive Engine (lo que NO debería seguir ampliándose)

```
LEARNING EVIDENCE
      ↓
STUDENT MODEL (skill, retention, transfer, difficulty, automaticity)
      ↓
DECISION SNAPSHOT
      ↓
TASK CANDIDATES
      ↓
TASK IDENTITY
      ↓
p(success) · difficulty fit · retention urgency · transfer gap · learning value
      ↓
PLANNER
      ↓
DECISION + PROVENANCE
      ↓
TASK INSTANCE
      ↓
ATTEMPT
      ↓
OUTCOME
      ↓
NEW EVIDENCE
```

Este debería ser el objetivo final.

## 15. Lo más importante: ya estamos cerca de cerrar el desarrollo arquitectónico

Hasta V3.67 prácticamente cada versión ha cerrado una deuda conceptual del
motor. **No conviene continuar inventando nuevas capas sin límite.** La
auditoría propone:

**Fase A — V3.68 Adaptive Engine Hardening.** Cerrar únicamente:

- P1 Task vs Task Instance.
- P1 lifecycle FSM.
- P1 provenance ownership/integrity.
- `unclear` fuera de calibración.
- Tests de regresión correspondientes.

**No añadir nuevas capacidades pedagógicas.**

Y después **congelar el diseño del motor adaptativo** con este roadmap:

```
V3.68 → cerrar arquitectura adaptativa
V3.69 → E2E completo
V3.70 → auditoría pedagógica
V3.71 → runtime/offline/instalación
V3.72 → UX/product completion
V3.73 → auditoría final
V4.0  → producto terminado
```

### 16. V3.69 — E2E Adaptive Engine

La prioridad es **probar el circuito completo**:

```
alumno nuevo → evidencia → Student State → Planner → decision_id → queue →
task → attempt → outcome → learning evidence → Student State actualizado →
siguiente decisión
```

Casos declarados: (1) alumno sin historial; (2) recall fuerte / speaking débil;
(3) alta dependencia de apoyo; (4) mala retención; (5) fallos repetidos;
(6) domina una tarea pero no transfiere; (7) ASR `unclear`; (8) dos usuarios
simultáneos; (9) refresh repetido de la cola; (10) evidencia entrando durante la
decisión. «Esto será muchísimo más valioso que añadir otra capa teórica.»

### 17. V3.70 — Pedagogical Validation

Dejar de mirar principalmente código y auditar niveles (Pre-A1 → C2) y
competencias (Vocabulary, Grammar, Listening, Speaking, Pronunciation,
Interaction, Reading, Writing, Mediation), comprobando la cadena
`contenido → práctica → evidencia → mastery → retention → transfer →
assessment`. Un motor adaptativo técnicamente excelente puede estar tomando
decisiones sobre un corpus pedagógicamente mediocre.

### 18. V3.71 — Offline / Runtime / Installation

Auditoría de producto real 100 % local (Ollama, Whisper, Piper, SQLite,
frontend, backend, launcher) **sin dependencia accidental de Internet**;
instalación limpia, BD vacía, primer usuario, descarga de modelos, arranque,
micrófono, TTS, STT, LAN, HTTPS, móvil.

### 19. V3.72 — UX / Product Completion

Onboarding, diagnóstico inicial, Course, Practice, Review, Speaking, Listening,
Dictionary, Progress, Profile, Adaptive plan, errores, loading, offline, móvil,
accesibilidad — y comprobar que el usuario **entiende por qué** se le propone
cada actividad.

### 20. V3.73 — Final Technical Audit

Última auditoría transversal (Architecture, Security, Database, Concurrency,
API, Frontend, Tests, CI, Documentation, Performance, Offline, Pedagogy, CEFR,
Adaptive Engine). Ya no se diseñan funcionalidades: **solo FIX**.

### 21. V4.0 — Release final

**NO MÁS DESARROLLO ARQUITECTÓNICO.** A partir de ahí: bug fixing, calibración
de contenido, calibración pedagógica, mejoras de UX, rendimiento y pruebas con
alumnos reales. Mantenimiento y evolución, no construcción del núcleo.

## 22. Mapa de deuda en el momento de la auditoría

| Elemento | Estado |
|---|---|
| Student Skill State | 🟢 |
| Decision Projection | 🟢 |
| Snapshot/fingerprint | 🟢 |
| Empirical success | 🟢 |
| Task Identity | 🟡 |
| **Task vs Instance** | 🔴 |
| Planner | 🟢/🟡 |
| Decision Provenance | 🟡 |
| **Lifecycle FSM** | 🔴 |
| **Provenance authorization** | 🔴 |
| Calibration | 🟡 |
| Retention | 🟡 |
| Transfer | 🟢/🟡 |
| Context Engine | 🟡 |
| Sense Engine | 🟡 |
| Curriculum | 🟢/🟡 |
| Listening | 🟢/🟡 |
| Speaking | 🟢/🟡 |
| E2E adaptive loop | 🟡 |
| Offline/runtime | 🟡 |
| UX final | 🟡 |

## 23. Conclusión de la auditoría

V3.67 es buena, pero **no se aceptaría todavía la frase «los dos P1 están
cerrados» sin matices**. La implementación ha cerrado correctamente el problema
original (`target_id ≠ task`) y ha convertido el provenance en una
infraestructura mucho más seria; la propia release documenta correctamente sus
límites estadísticos y que la calibración todavía es descriptiva.

Pero aparecen **tres problemas de segunda generación**:

1. **P1-01** — Task Signature incluye información que el Planner todavía no
   conoce: el contexto/instancia.
2. **P1-02** — El lifecycle no es todavía una máquina de estados real y
   `started` no está integrado en el flujo efectivo.
3. **P1-03** — El provenance no está suficientemente ligado al usuario y a la
   tarea que realmente se está ejecutando.

Y hay algo especialmente positivo: por primera vez existe el mecanismo necesario
para medir retrospectivamente si el Planner toma buenas decisiones. El endpoint
de provenance y la calibración descriptiva son la infraestructura para pasar de
«creemos que el adaptive engine funciona» a «podemos demostrar con datos que
funciona».

---

# Respuesta a esta auditoría (V3.68.0)

**V3.68.0 — Adaptive Engine Hardening & Integrity** (2026-09-15) cierra los
cuatro puntos de la «Fase A» propuesta por la auditoría, **sin añadir ninguna
capacidad pedagógica nueva** y **sin tocar el argmax del Planner**:

| Hallazgo | Resolución en V3.68.0 |
|---|---|
| **P1-01** Task vs Task Instance | `task_key_parts(...)` (5 componentes, **sin contexto**) es la identidad de la **DEFINICIÓN** — la que el Planner **puede** calcular antes de elegir instancia — y `task_instance_key_parts(..., context)` la de la **INSTANCIA**. `empirical_success_by_task` agrupa por `task_key` y se añade `empirical_success_by_task_instance`. `task_signature_parts`/`task_signature` se **eliminan**. **La tarea de transferencia del ledger YA casa con el candidato** (test de regresión explícito del P1-01). |
| **P1-02** Lifecycle FSM | Tabla **declarada** `_ALLOWED_TRANSITIONS` y `_transition()` convertido en **compare-and-set** (`decision_id + user_id + estados de origen válidos`), con rechazos **contados**. `mark_started`/`mark_abandoned` ganan **llamadores reales**: nuevo `POST /api/vocabulary/drill/decision-lifecycle` y **el eslabón de frontend que faltaba** (el cliente nunca devolvía `decision_id`: el ciclo era código muerto en producción). `close_stale(...)` barre `served`/`started` antiguas a `abandoned`. Declarado: `served → completed` es válida (best-effort: no se pierde el outcome si el cliente no declaró el inicio); `computed → completed` sigue siendo inválida. |
| **P1-03** Integridad/propiedad | Todas las transiciones son ya `mark_*(user_id, decision_id, ...)` y la consulta filtra por `user_id` (**propiedad**); el `target_id` es **puerta**; la **actividad NO es puerta** — se **registra** (`executed_activity`) y se deriva `activity_match`, con motivo declarado (el drill degrada peldaños legítimamente y rechazarla perdería medición). El fallo es best-effort **no-op + contador** visible en `transition_health()`. |
| **P2-08** `unclear` en calibración | `unclear` y `abandoned` quedan **fuera del denominador** y del `calibration_error`; el informe gana `completed_count`/`measured_count`/`unclear_count`/`abandoned_count`. |

**Queda declarado fuera de alcance en V3.68.0** (y **es** el siguiente nivel ya
identificado por la auditoría):

- **Adaptive Instance Selection**: el nivel de instancia se **nombra, deriva y
  observa** (`task_instance_key`, `empirical_success_by_task_instance`) pero **no
  puntúa** el argmax. El Planner sigue decidiendo por **tarea**.
- **`decision → serving → attempt` en tablas separadas** (§6 de esta auditoría):
  V3.68 lo resuelve con la regla de **re-servicio** y **un outcome por decisión**
  (el del PRIMER intento de la sesión; los siguientes cuentan como
  `closed_decision`).
- **`Decision Snapshot` único** (§11) y **calibración real / ML** (§7): siguen
  en fases posteriores. La calibración sigue siendo **descriptiva** y **no
  gobierna** nada (§12).
- Los P2 §9 (`recent_rate` no temporalmente comparable) y §13 (learning gain)
  siguen abiertos y aceptados.
- **V3.69 → E2E completo** es el siguiente incremento declarado, con los diez
  casos de esta auditoría, seguido del roadmap §15 hasta **V4.0**.

El **diseño del motor adaptativo queda CONGELADO** tras V3.68.0, tal como
recomienda esta auditoría.

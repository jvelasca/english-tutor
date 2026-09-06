# V3.17 — v317-knowledge-graph-adaptive-plan: Knowledge Graph + Daily Adaptive Plan

## Decisiones de diseño para aprobar (resumen para el gerente)

> El gerente revisa estas decisiones ANTES de ejecutar el briefing. La implementación
> asume las marcadas como *(recomendado)*.

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D1 | Fusión Knowledge Graph ↔ plan diario | (a) enriquecer los ítems del plan con el nodo del grafo (explicativo); (b) enriquecer **y derivar** la selección de la debilidad desde el nodo; (c) reconstruir todo el plan desde el grafo | **(b)** — conecta Can-Do ↔ destrezas ↔ dominio de verdad (la debilidad se elige por su factor limitante en el can-do) sin romper el contrato `/session` (consumidor real de la Home): mismo esqueleto Session Engine (mix/caps/presupuesto), categorías review/new/easy_wins intactas, solo cambia qué objetivo concreto de la destreza débil se propone y por qué |
| D2 | "Vista de grafo real": consumidor de `GET /evidence-graph/objective/{id}` | (a) solo en el curso (Milestone); (b) solo en el panel de Habilidades/Evidence; (c) componente reutilizable en ambos | **(c) para v1** — un detalle de nodo reutilizable ("¿por qué está así este can-do?") consumiendo el endpoint huérfano, abierto desde el curso (objetivo con evidencia) y desde el perfil; la vista literal (grafo dibujado/SVG) se difiere por coste y premisa 6 |
| D3 | `/api/academy/today` sin consumidor | (a) eliminar endpoint + `get_today_plan` + `TodayPlanOut` + `adaptive.today_plan`/`TODAY_MIX` + cliente/tipos frontend (tests migrados con honestidad); (b) re-apuntar la UI de TodayPlan a `/today`; (c) mantener y documentar deprecated | **(a)** — la Home real consume `/session` (Session Engine); mantener dos motores de plan diario (today vs session) garantiza deriva y código muerto; los 2 tests que ejercen `/today` se migran a `/session` (mismo presupuesto del objetivo) con rationale honesto; `docs/UI_V3.1.md:160` (referencia stale a `/today`) se señala en el informe para el cierre del gerente, NO se edita en el incremento |
| D4 | Deuda heredada de v3.16 (I2/M1–M4/O1–O3) en v3.17 | (a) toda la deuda; (b) solo el lote de endurecimiento (M1, M2, M3, O2); (c) ninguna | **(b)** — M1 (vitest de `UnitReviewPanel`), M2 (validar `answers` ⊆ muestra), M3 (registrar prefijos dinámicos), O2 (test GET==POST con reintento parcial) son endurecimiento de tests/validación sin cambiar comportamiento ni contenido: cierran la auditoría 37.34 sin secuestrar el foco P2. I2 (congelar ancla: cambia la semántica de D3 y pide columna/tabla de ancla), M4 (decisión de producto sobre doble escritor FSRS) y O1/O3 (cadena 7→30→90, plan multinivel) se difieren a un incremento de limpieza dedicado (v3.18+). Si D1/D2 hacen inevitable tocar esas zonas, el implementador lo documenta y para (no lo resuelve por su cuenta) |
| D5 | Versionado de cambios de motor | (a) bump semántico por motor (`GRAPH_VERSION` 2.12.0 → 2.13.0) solo cuando cambia la salida de funciones existentes del grafo; si el cambio es aditivo (helpers nuevos, contrato nuevo opcional) se mantiene y se documenta; (b) bump siempre que se toque el grafo; (c) sin versionado interno | **(a)** — con D1(b) se añaden helpers puros y campos opcionales **sin alterar** la salida de `objective_node`/`dimension_scores`/`build_level_graph`, así que v3.17 **no sube** `GRAPH_VERSION` y los goldens (`test_golden_evidence_graph.py`, aserciones `startswith("2.12")`) siguen verdes. Si el implementador descubre que debe cambiar semántica de nodo, para y lo reporta (decisión de bump + actualización de goldens). La versión de app (3.17.0) la cierra el gerente |
| D6 | UI del plan diario enriquecido | (a) cada fila con objetivo muestra micro-líneas no interactivas del can-do y su factor limitante (chip); el `because[]` completo queda solo en `NextBestCard`; (b) filas sin cambios (solo backend) | **(a)** — "TU OBJETIVO DE HOY" es la superficie diaria real y debe conectar el can-do con la destreza/dominio sin saturar: dos líneas estáticas por fila; las filas son botones que lanzan la lección, así que nada anidable dentro del botón; claves i18n nuevas en es/en con parity |
| D7 | Ítems del plan sin nodo construible (sin `objective_id` o sin datos de grafo) | (a) fallback silencioso: el ítem se queda como hoy, sin campos de grafo; (b) omitir el ítem o fallar | **(a)** — review (curva de olvido), easy_wins y listening no tienen can-do asociado; un objetivo sin evidencia construye nodo de ceros pero se sigue mostrando honesto (dimensión missing); nunca se omite práctica por falta de datos de grafo |

## Rol

Implementador **full-stack** (backend servicios/domain/repos/schemas/routers + frontend + tests).
Cierras el frente abierto del candidato "🟡 P2 — Knowledge Graph + Daily Adaptive Plan" (v3.17,
ABIERTO en `docs/RELEVO.md`, entrada 37.34 y nota superior). NO haces bump de versión ni docs de
release (README/CHANGELOG/PLAN/RELEVO/release-notes): eso lo cierra el gerente tras tu informe,
replicando el patrón del commit `9db2f4b`.

## Pre-auditorías obligatorias del implementador (antes de tocar nada)

Lee y verifica con el código real (los números de línea del briefing son una guía; confírmalos):

1. **`docs/PREMISAS.md`** — 6 (un incremento a la vez), 12 (tests = definición de terminado),
   13 (aislamiento por usuario), 18 (docstrings), 19/20 (UI con estados y responsive + visuales),
   21 (el servidor puntúa; el frontend nunca declara dominio).
2. **`docs/RELEVO.md`** — nota superior (posición 3.16.0) y entrada **37.34**: veredicto de la
   auditoría externa v3.16, fix I1 y deuda I2/M1–M4/O1–O3; candidato P2 abierto (líneas ~2657–2669).
3. **`docs/EVIDENCE_GRAPH.md`** — qué conecta el grafo (V2.12) y su API/frontend declarados.
4. **`docs/ARQUITECTURA.md`** — separación estricta routers → domain → repositories/servicios →
   schemas; frontend api/features/hooks/types.
5. **`docs/UI_V3.1.md`** — zonas de INICIO (la Home real: "TU OBJETIVO DE HOY" = `/session`;
   línea ~160 referencia stale a `/today`; NO editar, señalar en el informe).
6. **`docs/audit/D-ASSESSMENT-READINESS.md`** y **`backend/tests/golden/evidence_graph/profiles.json`**
   — origen y escenarios dorados del Evidence Graph (reglas del limiting factor).
7. Código motor: **`backend/services/evidence_graph.py`** (funciones puras, `GRAPH_VERSION`),
   **`backend/services/adaptive.py`** (`today_plan` :464, `TODAY_MIX` :403, `session_plan` :592,
   `SESSION_MIX`/`SESSION_CAPS`, `next_best_activity` ~:886, Priority Engine 2.0),
   **`backend/services/unit_review.py`** (solo lectura salvo D4b), **`backend/services/fsrs.py`**
   (solo lectura: `why_for_objective`/`TARGET_TYPES`/`schedule`).
8. Orquestación **`backend/domain/academy.py`** — `_current_level_id` (:533), `_annotated_profile`,
   `_session_steps` (~:2307), `get_session`, `get_next_best_activity` (:2366), `get_today_plan`
   (:2280), `get_evidence_graph` (:2409), `get_evidence_graph_node` (:2439), `submit_unit_micro_review`
   (:2116, para M2 si D4b), `sync_fsrs_cards` (:1654, solo lectura).
9. Contratos **`backend/schemas/academy.py`** — `SessionStepOut` (:1176), `SessionOut` (:1193),
   `TodayPlanOut`/`TodayItemOut` (:1171/:1162, solo si D3=a), `NextBestActivityOut` (:1200),
   `EvidenceGraphNodeOut` (:1248), `ObjectiveStateOut.can_do` (:53).
10. Frontend — **`frontend/src/features/home/HomeScreen.tsx`** (bloques TodayPlan :219, NextBestCard
    :232, FsrsReviewPanel, UnitReviewPanel), **`frontend/src/components/TodayPlan.tsx`** (consume
    `getStudentModel` + `getSession` + `getGoal`; NO llama a `getTodayPlan`),
    **`frontend/src/api/academy.ts`** (`getTodayPlan` :512 **sin consumidor**, `getSession` :516,
    `getNextBestActivity` :520, `getEvidenceGraph` :529, `getEvidenceGraphNode` :540 **sin consumidor**),
    **`frontend/src/types/api.ts`** (espejos: `SessionStep`/`Session`, `TodayPlan`, `NextBestActivity`,
    `EvidenceGraphNode`, `CurriculumObjective`), `frontend/src/components/NextBestCard.tsx`,
    `frontend/src/features/evidence/EvidenceGraphPanel.tsx` (corta a 12 nodos),
    `frontend/src/features/course/CourseScreen.tsx` + `components/Milestone.tsx`,
    `frontend/src/utils/i18n.ts` + `i18n.parity.test.ts` (`DYNAMIC_KEY_PREFIXES` :31, M3),
    `frontend/src/features/review/` (para M1 y contexto M4).
11. Tests que fijan el estado actual — `backend/tests/test_evidence_graph.py`,
    `backend/tests/test_golden_evidence_graph.py`, `backend/tests/test_adaptive.py`,
    `backend/tests/test_academy.py` (:1398 `/today`), `backend/tests/test_academy_goal.py` (:131
    `/today`), `backend/tests/test_unit_review_endpoints.py`, `frontend/src/api/academy.test.ts`,
    `frontend/src/features/review/unitReviewLogic.test.ts`.

Baseline reportado en el cierre v3.16: **pytest 1318**, **vitest 392**, build OK. Ejecuta tus
propios números antes de tocar nada (Fase E) y repórtalos.

## Contexto técnico (resumen verificado)

- **Evidence Graph V2.12 operativo y por usuario** (`backend/services/evidence_graph.py`,
  `GRAPH_VERSION = "2.12.0"`, puro): `dimension_scores`, `limiting_factor`, `mastery_from_dimensions`,
  `recommended_focus`, `objective_node`, `explain_because`, `build_level_graph`, `enrich_next_best`.
  Endpoints en `backend/routers/academy.py`: `GET /api/academy/evidence-graph` (:219, domain
  `get_evidence_graph` :2409), `GET /api/academy/evidence-graph/objective/{id}` (:231, domain
  `get_evidence_graph_node` :2439), `GET /api/academy/next-best` (:214, domain :2366, el ÚNICO que
  enriquece hoy con `because[]`/`limiting_factor`/`graph_mastery`/`can_do`). UI: `EvidenceGraphPanel`
  (perfil → Habilidades, `HabilidadesTab.tsx:187`) y `NextBestCard`.
- **`backend/services/adaptive.py`** (puro): `today_plan` (:464, `TODAY_MIX` weakness .40/review .30/
  new .20/easy_wins .10), `session_plan` (:592, `SESSION_MIX` con listening, `SESSION_CAPS`, filtro
  `exclude_keys` por `step_key`), `session_summary`, `next_best_activity` + Priority Engine 2.0
  (`priority_signals` :772, `priority_score` :818, `explain_priority` :853). Los ítems del plan son
  `{kind, skill, subskill?, objective_id?, level_id?, skills[], title, reason, minutes, step_key}`
  **sin** `can_do`/`limiting_factor`/`because`/`graph_mastery`. `adaptive.py` NO importa
  `evidence_graph`.
- **Consumidores reales**: la Home (`TodayPlan.tsx`) usa `getStudentModel`+`getSession`+`getGoal`
  (`/api/academy/session`); `getNextBestActivity` sí se consume (HomeScreen :12/:116, LearnHub,
  NextStep). `getTodayPlan` (api/academy.ts:512) y `getEvidenceGraphNode` (api/academy.ts:540) **no
  tienen consumidor frontend**. `HomeScreen` monta TodayPlan (:219), `NextBestCard` (:232),
  `FsrsReviewPanel` y `UnitReviewPanel`.
- **`Objective.can_do`** está poblado en el currículo (`services/curriculum.py`, `backend/curriculum/*.json`)
  y se expone en `ObjectiveStateOut.can_do` y `EvidenceGraphNodeOut.can_do`. `limiting_factor` NO
  existe como lógica de nivel ni en currículo: es solo del grafo/schemas de evidencia.
- **Remediación actual** (`services/academy.py remediation_plan` :566): por destreza débil
  (`review_due`), ordena objetivos que la declaran y no están dominados por su score local ascendente.
  `session_plan` toma `r["objective_ids"][0]`. El grafo puede **reordenar** esos candidatos (D1b)
  sin tocar `remediation_plan`.
- **Deuda heredada** (registrada en el candidato P2 del RELEVO, 37.34): I2 ancla no congelada
  (`unit_anchor` = `max(updated_at)` de filas vivas, `unit_review.py:99`); M1 sin vitest `.test.tsx`
  de `UnitReviewPanel`; M2 sin validar claves de `answers` en el POST micro-review (⊆ muestra);
  M3 `DYNAMIC_KEY_PREFIXES` sin `unitReview.window.`/`unitReview.state.`/`skill.`; M4 cartas
  `objective` visibles y autograduables en `FsrsReviewPanel` (doble escritor con el micro-review);
  O1 sin cadena 7→30→90; O2 sin test de reintento parcial GET==POST; O3 plan de repaso solo del
  nivel actual.

## Decisiones de diseño (detalle y justificación)

### D1 — Fusión Knowledge Graph ↔ plan diario *(recomendado: b)*

El P2 pide que el plan diario "derive del grafo" manteniendo `/session` como motor real de la Home.

- **(a)** Solo enriquecer: el dominio adjunta a cada paso con `objective_id` los campos del nodo
  (`can_do`, `limiting_factor`, `graph_mastery`, `because[]`) calculados con `objective_node` +
  `explain_because` — el mismo patrón que hoy usa `get_next_best_activity` solo para el primer paso,
  generalizado a todos los pasos de la sesión. El plan "muestra" el grafo pero no cambia su selección.
- **(b)** Enriquecer **y** derivar la debilidad: además de (a), la elección del objetivo concreto de
  cada destreza débil pasa por una **función pura nueva** que reordena los candidatos usando su nodo:
  primero los objetivos cuyo `limiting_factor.id` == la destreza débil (o cuya dimensión está
  `missing`), después por `graph_mastery` ascendente, empates estables por el orden curricular ya
  recibido. El esqueleto del Session Engine (orden review>listening>weakness>new>easy_wins, mix,
  caps, presupuesto, `exclude_keys`) NO cambia; tampoco `remediation_plan` ni `recommend_next`.
- **(c)** Reconstruir el plan desde el grafo (ordenar objetivos abiertos por nodo y repartir
  presupuesto sin `session_plan`): rompe el contrato `/session`, el Priority Engine de `/next-best`
  y la UI TodayPlan; máximo acoplamiento para un incremento.

Por qué (b): conecta Can-Do ↔ destrezas ↔ dominio (el objetivo que se practica es el can-do cuyo
factor limitante es la destreza débil) sin reescribir la UX; el cambio es aditivo (contrato) + una
ordenación pura (tests); determinista y sin LLM.

### D2 — "Vista de grafo real": consumidor del endpoint de nodo *(recomendado: c, acotado)*

`GET /api/academy/evidence-graph/objective/{id}` y su cliente `getEvidenceGraphNode` no tienen
consumidor. El panel actual de Evidence corta a 12 nodos y no permite navegar a un can-do concreto
desde el curso.

- **(a)** Solo curso: hacer clic en un Milestone (objetivo) del `CourseScreen` abre el nodo.
- **(b)** Solo perfil: convertir `EvidenceGraphPanel` en un explorador que usa el endpoint por nodo.
- **(c)** Componente reutilizable (`evidence/ObjectiveNodeCard` o drawer "¿Por qué este can-do?")
  que consume `getEvidenceGraphNode(userId, objectiveId, levelId)` y muestra can-do, dimensiones con
  barras, factor limitante y `because[]`; montado en: (1) `CourseScreen` — cada objetivo de unidad
  con estado `available`/`review`/`mastered` ofrece abrir su detalle; (2) `HabilidadesTab` —
  `EvidenceGraphPanel` pasa a usar el mismo componente y a poder abrir cualquier objetivo (se elimina
  el corte a 12; scroller/paginación). Estados 404 (objetivo no encontrado) y "sin evidencia"
  manejados; copia honesta (muestra mastery/evidencia, no declara dominio).

Por qué (c) para v1: da consumidor real al endpoint huérfano en las dos superficies donde el alumno
ve progreso; la vista literal de grafo (nodos/aristas dibujados, SVG) se difiere — es cara y no
aporta a la decisión diaria, que ya cubren D1/D6.

### D3 — `/api/academy/today` sin consumidor *(recomendado: a)*

- **(a)** Eliminar: endpoint (`routers/academy.py:194`), `get_today_plan` (`domain/academy.py:2280`),
  `TodayPlanOut`/`TodayItemOut` (`schemas/academy.py:1171/:1162`), `adaptive.today_plan` + `TODAY_MIX`
  (`adaptive.py:464/:403`, quedan sin consumidor), cliente `getTodayPlan` (`api/academy.ts:512`) y
  tipos `TodayPlan`/`TodayItem` (`types/api.ts`). Migrar con honestidad los 2 tests que lo ejercen:
  `test_academy.py:1398` (plan no vacío con `kind=new` para usuario nuevo) y
  `test_academy_goal.py:131` (`test_today_plan_uses_goal_budget`: el presupuesto del objetivo 45 min
  debe reflejarse en `total_minutes`) → re-apuntarlos a `/api/academy/session`, que ya aplica el
  mismo `budget_minutes = goal.minutes_per_day`. Señalar en el informe la línea stale
  `docs/UI_V3.1.md:160` (el implementador no edita esa doc).
- **(b)** Re-apuntar la UI: la Home perdería el Session Engine (listening, exclude_keys, contadores
  review/practice) — involución.
- **(c)** Mantener + doc deprecated: código muerto y dos motores de "hoy" que derivarán (today con
  TODAY_MIX no derivará del grafo, session sí) → confusión garantizada.

Por qué (a): sin consumidor en una app 100% local, dos motores de plan diario derivan y el muerto
se pudre; la migración de tests es pequeña y honesta (el presupuesto del objetivo ya se testea en
`/session`).

### D4 — Línea de corte de la deuda v3.16 *(recomendado: b)*

- **(b)** Entran en v3.17, como fase corta de endurecimiento: **M1** (vitest `.test.tsx` de
  `UnitReviewPanel`, render + ventana due + submit/refresh con fetch mockeado), **M2** (validar en el
  POST micro-review que las claves de `answers` ⊆ ids de la muestra y valores índice válidos → 400),
  **M3** (añadir a `DYNAMIC_KEY_PREFIXES`: `unitReview.window.`, `unitReview.state.`, `skill.`; añade
  también `fsrs.whyReason.` que descubrirás dinámico en `FsrsReviewPanel`), **O2** (test GET==POST con
  reintento parcial: misma muestra determinista y priorización de fallidos).
- Se difieren (v3.18+ o incremento de limpieza): **I2** (congelar el ancla exige diseño de columna/
  tabla de ancla y cambia D3 de v3.16), **M4** (decisión de producto sobre el doble escritor de las
  cartas `objective`), **O1** (cadena 7→30→90), **O3** (plan de repaso multinivel, D2(b) de v3.16).

Por qué (b): cierra la auditoría 37.34 con quick wins de bajo riesgo (tests/validación/i18n) y no
secuestra el foco P2. Si durante D1/D2/D3 tocas una zona diferida, párala y documéntalo en el
informe con la alternativa; no la resuelvas por tu cuenta.

### D5 — Versionado de cambios de motor *(recomendado: a)*

- **(a)** Bump semántico por motor: `GRAPH_VERSION` solo sube si cambia la salida de funciones
  existentes del grafo. Con D1(b) el cambio es aditivo (helpers puros + campos opcionales en
  `SessionOut`): `GRAPH_VERSION` se mantiene en `2.12.0`, los tests que aseveran el prefijo
  (`test_evidence_graph.py`, golden) siguen verdes, y el informe justifica por qué no se bumpa.
  `TODAY_MIX` no es una versión: si D3=a desaparece con `today_plan`; si algún mix cambia, se
  documenta con su test (no hay constante de versión de adaptive). La versión de release (3.17.0)
  la cierra el gerente.
- **(b)** Bump siempre que se toque el grafo: falsos positivos de versionado y churn de goldens.
- **(c)** Sin versionado: imposible auditar qué motor produjo cada payload.

Por qué (a): versionar solo cambios semánticos mantiene los goldens como red de seguridad y el
`graph_version` del payload como dato honesto.

### D6 — UI del plan diario enriquecido *(recomendado: a)*

- **(a)** En `TodayPlan.tsx`, cada fila (`SessionStepRow`) con `can_do` muestra bajo el título dos
  micro-líneas **estáticas**: el can-do en itálica (o ya es el `title` si coincide) y, si existe
  `limiting_factor`, un chip `{dimensión} · {pct|missing}` con los tokens de color existentes
  (amarillo warning, patrón de `EvidenceGraphPanel`). El `because[]` completo se queda solo en
  `NextBestCard` (acción protagonista). Nuevas claves i18n es/en (`today.*`) con parity; cero cadenas
  hardcodeadas.
- **(b)** Solo backend: el dato viaja en `/session` pero la Home no lo muestra — el alumno no ve la
  conexión Can-Do ↔ destreza en su plan diario.

Por qué (a): las filas son botones que lanzan la lección (no se anidan controles); dos líneas
estáticas conectan el can-do con el dominio sin saturar la lista; los estados vacíos/carga/error de
la Home ya existen y no cambian.

### D7 — Ítems sin nodo *(recomendado: a)*

Review (curva de olvido), easy_wins y listening no tienen `objective_id`/can-do: se quedan como hoy.
Un objetivo con evidencia construye nodo (dimensión `missing` cuando toque) y el fallback ante
cualquier ausencia de datos es **no adjuntar campos** (el ítem sigue siendo accionable). Nunca se
omite práctica por falta de datos de grafo ni se bloquea el plan.

## Tarea

### Fase A — Motor puro (servicios; sin FastAPI ni BD)

En `backend/services/evidence_graph.py` (o, si el patrón lo pide mejor, un módulo puro nuevo
`graph_plan.py` que importe `evidence_graph` — decide con tus tests; NO dupliques la lógica de
nodo):

1. `rank_weakness_objectives(*, objective_ids: list[str], nodes_by_objective: dict[str, dict],
   skill: str) -> list[str]` — regla de D1(b): primero candidatos cuyo nodo tiene
   `limiting_factor.id == skill` o su dimensión `skill` está `missing`; después `graph_mastery`
   ascendente; empates estables por el orden recibido. Determinista. `nodes_by_objective` puede ser
   parcial: los ids sin nodo se dejan al final en orden original (fallback D7).
2. Helper de enriquecimiento de ítems del plan: reutiliza `enrich_next_best` (ya pone
   `because[]`/`limiting_factor`/`graph_mastery`/`can_do`) o extrae un alias genérico
   `enrich_item(item, node)` **sin cambiar** la salida de `enrich_next_best` (hay tests que la fijan).
   El ítem enriquecido gana esos 4 campos; un ítem sin nodo no se toca.
3. `explain_because` se reutiliza tal cual: las viñetas ya referencian el limiting factor, las
   destrezas sólidas y el foco de la actividad (idioma de inmersión, como `why` de next-best).
4. Docstrings completos (premisa 18). Tests puros (nuevo `backend/tests/test_graph_plan.py` o ampliar
   `test_evidence_graph.py`): regla de ordenación (caso controlado donde la destreza débil es el
   limiting factor del objetivo B pero no del A → B primero; desempate por mastery; estabilidad),
   enriquecimiento aditivo (campos solo cuando hay nodo; ítem sin objetivo intacto), fallback con
   `nodes_by_objective` parcial. NO cambies la salida de las funciones existentes (si un test te lo
   exige, para y reporta — decisión D5).

### Fase B — Backend: dominio + schemas (+ micro-review si D4=b)

En `backend/domain/academy.py` y `backend/schemas/academy.py`:

1. **Enriquecimiento de la sesión (D1b)**: añade a `SessionStepOut` los campos opcionales
   `can_do: str | None = None`, `limiting_factor: dict | None = None`,
   `graph_mastery: float | None = None`, `because: list[str] = Field(default_factory=list)`
   (docstrings; espejo en `frontend/src/types/api.ts`). En `_session_steps` (~:2307):
   - reordena los `objective_ids` de cada entrada de remediación con `rank_weakness_objectives`
     ANTES de llamar a `session_plan` (solo cuando haya nodos; sin nodos → comportamiento actual);
   - tras obtener los pasos, construye UNA VEZ un mapa `nodes_by_objective` para los `objective_id`
     presentes en los pasos (reutilizando `obj_mastery` y las `evidence_rows` ya leídas; añade la
     lectura de evidencia si el flujo actual no la tiene) y enriquece cada paso con la Fase A.
   - el mismo helper de enriquecimiento lo usa `get_next_best_activity` para no duplicar lógica
     (hoy construye el nodo del primer paso con perfil anotado: mantenlo consistente — mismo perfil,
     mismas filas, mismo nodo → `/session` y `/next-best` nunca divergen).
2. **D3 (si se aprueba a)**: elimina `get_today_plan`, el endpoint `/api/academy/today`, los schemas
   `TodayPlanOut`/`TodayItemOut` y (si queda sin consumidor) `adaptive.today_plan` + `TODAY_MIX`.
   Migra con rationale honesto los tests de `/today` a `/api/academy/session`.
3. **D2 backend**: sin endpoints nuevos (el de nodo ya existe); si hace falta, permites `level_id`
   en la llamada de curso (ya soportado por `get_evidence_graph_node`).
4. **M2 (si D4=b)**: en `submit_unit_micro_review` (o en el servicio puro), valida `answers` ⊆ ids de
   la muestra y valores índice enteros en rango → `ValueError("unit_review.invalid_answers")` que el
   router convierte en 400 (patrón existente). O2: test GET==POST con reintento parcial (la muestra
   del reintento es idéntica y prioriza los fallidos del último intento).
5. Schemas Pydantic con docstrings; routers sin lógica de negocio; aislamiento por usuario en toda
   consulta (premisa 13). Tests de dominio/endpoint: `/session` devuelve campos de grafo solo en
   pasos con objetivo; usuario A no ve datos de B; presupuesto del objetivo intacto; migración de
   `/today` si D3=a; M2/O2 según D4.

### Fase C — Frontend: plan diario enriquecido (+ deuda elegida)

- **Tipos** en `frontend/src/types/api.ts` (espejo de `SessionStepOut` nuevo) y **cliente** en
  `frontend/src/api/academy.ts` (nada nuevo para sesión; si D3=a borra `getTodayPlan` y los tipos
  `TodayPlan`/`TodayItem`).
- **`frontend/src/components/TodayPlan.tsx`**: en `SessionStepRow`, cuando el ítem trae `can_do`/
  `limiting_factor` añade las micro-líneas estáticas de D6 (can-do en itálica y chip de factor
  limitante con `{pct|missing}`, tokens warning ya usados en `EvidenceGraphPanel`). Las filas siguen
  siendo botones (sin anidar controles); estados vacío/carga/error y responsive intactos.
- **i18n** (`frontend/src/utils/i18n.ts`): claves nuevas en **es y en** (el parity test rompe si
  falta una); reutiliza donde existan (`home.because`/`home.limitingFactor` si aplican).
- **M3 (si D4=b)**: añade a `DYNAMIC_KEY_PREFIXES` en `i18n.parity.test.ts` los prefijos
  `unitReview.window.`, `unitReview.state.`, `skill.` (+ `fsrs.whyReason.`) con comentario de motivo.
- **M1 (si D4=b)**: vitest de componente `UnitReviewPanel` (`frontend/src/features/review/`),
  render con estado vacío, con ventana due y submit/refresh, con fetch mockeado.
- **Tests**: vitest de `TodayPlan`/fila enriquecida (fetch mockeado), parity i18n verde. Si hay
  specs Playwright de la región tocada (Home), confirma que siguen verdes o actualiza goldens según
  convención; si no hay cobertura de esa región, indícalo en el informe.

### Fase D — Frontend: vista de grafo por can-do (D2)

- **Cliente**: `getEvidenceGraphNode` ya existe en `api/academy.ts:540` (usa `userQuery` +
  `level_id`); se convierte en el consumidor del nuevo componente.
- **Componente reutilizable** `frontend/src/features/evidence/ObjectiveNodeCard.tsx` (o dentro de una
  carpeta `evidence/`): recibe `userId` + `objectiveId` + `levelId`, hace fetch del nodo, y renderiza
  can-do, `graph_version`, dimensiones con barras (patrón visual de `EvidenceGraphPanel`), factor
  limitante destacado y `because[]`; estados loading/error/404/empty cuidados (premisa 19). No
  declara dominio: copia honesta tipo "tu dominio en este can-do".
- **Integración**:
  1. `frontend/src/features/course/CourseScreen.tsx` — en los objetivos de una unidad (donde hoy se
     listan `Milestone`), ofrece abrir el detalle del nodo para estados `available`/`review`/
     `mastered` (botón "Por qué este can-do"/icono, aria-expanded; drawer o sección colapsable con
     scroll propio, respetando la premisa 19/20; sin `text-overflow` para truncar contenido).
  2. `frontend/src/features/progress/HabilidadesTab.tsx` + `EvidenceGraphPanel.tsx` — el panel pasa a
     renderizar el detalle con el mismo componente y permite abrir cualquier objetivo del nivel (se
     elimina el recorte a 12: lista con scroll/paginación por módulo si procede).
- **i18n**: claves nuevas en es/en (`evidenceGraph.openNode`, etc.) con parity; docstrings/JSDoc.
- **Tests**: vitest del componente (loading, con nodo, 404/sin datos) y de la integración del curso
  (fetch mockeado); parity verde; si se toca layout de rutas principales, Playwright de la región.

### Fase E — Verificación local (obligatoria, misma secuencia que los cierres previos)

- Backend (desde `backend/`): `python -m pytest tests/ -q` → TODO verde (baseline 1318 + deltas de
  Fases A/B; si D3=a el conteo neto puede bajar por tests migrados) y `ruff check .` limpio.
- Frontend (desde `frontend/`): `npm test` (vitest) verde (baseline 392 + deltas), `npm run build`
  (tsc + vite) OK.
- Si tocas layout de Home/Course o añades una región visual nueva (D2), ejecuta los specs Playwright
  que cubren esas rutas y revisa screenshots en ≥3 viewports (premisa 20); si no hay cobertura de la
  región, indícalo en el informe.
- Reporta números reales y toda actualización honesta de tests preexistentes con su porqué.

## Criterios de aceptación

1. Motor puro con `rank_weakness_objectives` (o equivalente) y enriquecimiento aditivo de ítems,
   deterministas y testeado; **no cambian** las salidas de las funciones existentes del Evidence
   Graph (si cambian, se para y se reporta, decisión D5).
2. `/api/academy/session` devuelve `can_do`/`limiting_factor`/`graph_mastery`/`because` en los pasos
   con objetivo del nivel cuando hay nodo; pasos sin objetivo y fallback (D7) intactos; aislamiento
   por usuario verificado por test.
3. Con los mismos inputs, la selección de debilidad elige un objetivo cuyo nodo declara la destreza
   débil como factor limitante antes que uno que no (test puro controlado); sin nodos → el
   comportamiento previo (primer candidato de remediación).
4. Frontend: la Home (`TodayPlan`) muestra las micro-líneas de can-do/factor limitante de D6 en filas
   con nodo, con estados cuidados y responsive; i18n es/en con parity verde; vitest verdes.
5. D2: componente reutilizable que consume `getEvidenceGraphNode` montado en curso y en el panel de
   Habilidades; sin recorte a 12 nodos; estados 404/sin datos manejados; no declara dominio.
6. D3 (si se aprueba): `/api/academy/today`, `get_today_plan`, `TodayPlanOut`/`TodayItemOut`,
   `adaptive.today_plan`/`TODAY_MIX` y cliente/tipos frontend eliminados; tests migrados a `/session`
   con rationale honesto; `docs/UI_V3.1.md:160` señalado en el informe.
7. Deuda D4=b cumplida: M1 (vitest de `UnitReviewPanel`), M2 (400 si `answers` fuera de la muestra o
   índice inválido), M3 (prefijos en `DYNAMIC_KEY_PREFIXES`), O2 (test GET==POST con reintento
   parcial) — todos con test.
8. Docstrings en todo código nuevo/modificado (premisa 18); capas estrictas; sin LLM; puntuación en
   servidor (premisa 21); i18n es/en; aislamiento por usuario (premisa 13).
9. Fase E verde y reportada con números; versionado D5 coherente y justificado en el informe.

## Restricciones

- NO tocar: bump de versión (`backend/config.py`), `README.md`, `CHANGELOG.md`, `PLAN.md`,
  `docs/RELEVO.md`, release-notes (cierre del gerente). NO tocar `docs/CONSTITUCION-PEDAGOGICA.md`
  (v3.17 es motor/UX, no norma). `docs/UI_V3.1.md` no se edita en el incremento (solo señalar en el
  informe).
- NO cambiar la semántica de `objective_node`/`dimension_scores`/`limiting_factor`/
  `build_level_graph`/`explain_because`/`enrich_next_best` ni sus tests; sin bump de `GRAPH_VERSION`
  salvo decisión explícita (D5). NO tocar `fsrs.py` (ni `TARGET_TYPES`), `unit_review.py` (salvo
  D4=b en el router/dominio), ni el motor de mastery/evidencia (`remediation_plan`/`recommend_next`
  se consumen, no se modifican).
- El esqueleto del plan (`/session`, `session_plan`, Priority Engine, `/next-best`) se conserva: los
  cambios son aditivos (contrato) + la ordenación pura de candidatos de debilidad. `/next-best` y
  `/session` deben compartir el mismo nodo para el mismo paso (nunca divergir).
- Cero contenido curricular artificial; sin LLM; determinista; puntuación en servidor (premisa 21).
- Capas estrictas: routers sin lógica; services puros sin FastAPI/BD; repos sin negocio; schemas
  Pydantic con docstrings; frontend api/features/types separados.
- i18n completa es/en con parity (test obligatorio); sin cadenas hardcodeadas en componentes.
- Aislamiento por usuario en toda consulta nueva (premisa 13); UI con estados vacío/carga/error y
  responsive (premisas 14/19/20).

## Salida

Informe final que reporte:
1. Archivos nuevos/modificados (ruta + función/rol de 1 línea).
2. Números de la Fase E (pytest/ruff/vitest/build/Playwright) y toda actualización honesta de tests
   preexistentes (p. ej. migración de `/today` → `/session`) con su porqué.
3. Confirmación explícita de cada criterio de aceptación (1–9).
4. Justificación de D5 (qué se versionó y por qué) y señalamiento de la línea stale de
   `docs/UI_V3.1.md` para el cierre del gerente.
5. Cualquier desviación de las decisiones D1–D7 (si una decisión se revela inviable en código,
   párala y documéntala en el informe con la alternativa; NO la resuelvas por tu cuenta).

# V3.18 — v318-knowledge-graph-deuda: Knowledge Graph remainder + deuda del grafo (P3)

## Decisiones de diseño aprobadas (resumen para el gerente)

> Aprobadas por el gerente el 2026-09-07 vía AskQuestion. La implementación las
> asume en firme; cada una fija una opción de las que el candidato P3 deja abiertas
> en `docs/RELEVO.md` (líneas ~2788–2805).

| # | Deuda | Opciones | Aprobada |
|---|---|---|---|
| D1 | I2 — Congelar el ancla de la unidad al alcanzar la completitud | (a) tabla persistida `unit_review_anchors` escrita la 1ª vez que la unidad se detecta completa (`INSERT ... ON CONFLICT DO NOTHING`, nunca sobrescribe), lectura autoritativa desde la tabla con backfill lazy al desplegar; (b) sin migración: ancla aproximada | **(a)** — tabla persistida |
| D2 | O1 — Cadena 7→30→90 ante resolución tardía | (a) ventanas independientes; (b) cascade: una ventana SIN intento propio se considera `passed` si existe un intento superado de la unidad con `created_at >= due_at` de esa ventana; el intento propio manda siempre | **(b)** — cascade |
| D3 | M4 — Papel de las cartas FSRS `objective` frente al `FsrsReviewPanel` autograduable (doble escritor con el micro-review) | (a) mantenerlas visibles y autograduables; (b) fuera del panel — single writer: se siembran/actualizan solo en ventana due_now/failed o con `reps > 0` (continuidad de scheduling); `get_fsrs_due` las excluye y el POST `/fsrs/review` las rechaza; (c) informativas con CTA | **(b)** — single writer (micro-review) |
| D4 | O3 — Plan de repaso más allá del nivel actual (D2(b)) | (a) agregado: `UnitReviewPlanOut` evoluciona a `{levels: [...], due_count}` (nivel actual + anteriores matriculados con unidades completadas/activas) y el micro-review valida la unidad en el nivel donde vive; (b) aditivo retrocompatible; (c) por nivel con llamadas extra | **(a)** — payload evolucionado + UI agrupada |
| D5 | H5 — Etiqueta del chip de factor limitante para dimensiones no-skill (`transfer`/`discourse`/`interaction`) | (a) mapa compartido de etiquetas en inglés de inmersión (convención V3.6.1) consumido por chip/`NextBestCard`/`ObjectiveNodeCard`; (b) i18n es/en; (c) backend envía la etiqueta | **(a)** — mapa compartido `GRAPH_DIMENSION_LABELS` + helper |
| D6 | H6 — Coste de `/session` y `/next-best` | (a) mínimo preservador: rankear/construir nodos solo para los grupos de remediación que pueden convertirse en paso (≤ `SESSION_CAPS["weakness"]`) y leer `list_evidence` solo si habrá ≥1 nodo; payloads idénticos, sin cambios de API; (b) además memoizar; (c) además caché | **(a)** — lazy minimal |
| D7 | Observaciones auditoría v3.17 (37.35) | (a) las tres en v3.18: `ObjectiveNodeCard` distingue error real (copia + reintento) de 404/sin-datos (copia vacía); `float()` defensivo en `rank_weakness_objectives`; ejecutar/extender la spec Playwright de la región tocada; (b) solo las dos primeras | **(a)** — las tres |

## Rol

Implementador **full-stack** (backend servicios/domain/repos/schemas/routers + frontend + tests).
Cierras el frente abierto del candidato "🟡 P3 — Knowledge Graph remainder + deuda del grafo"
(v3.18, ABIERTO en `docs/RELEVO.md`, entrada 37.35 y nota superior). Al terminar, **tú** haces
también el cierre de release (bump `backend/config.py` `3.17.0 → 3.18.0` + `frontend/package.json`/
`package-lock.json`, `README`, `CHANGELOG`, `PLAN`, nota superior + entrada 37.36 en `docs/RELEVO.md`,
`release-notes-v3.18.0.md`), replicando el patrón de los cierres previos. Si alguna decisión D1–D7
se revela inviable en código, **para y documenta** la alternativa; no la resuelves por tu cuenta.

## Pre-auditorías obligatorias (antes de tocar nada)

Lee y verifica con el código real (los números de línea son una guía; confírmalos):

1. **`docs/PREMISAS.md`** — 6 (un incremento a la vez), 12 (tests = definición de terminado),
   13 (aislamiento por usuario), 18 (docstrings), 19/20 (UI con estados y responsive + visuales),
   21 (el servidor puntúa; el frontend nunca declara dominio).
2. **`docs/RELEVO.md`** — nota superior (posición 3.17.0) y entrada **37.35**: veredicto APROBADO
   CON OBSERVACIONES, fix H1–H4, deuda H5/H6; candidato P3 abierto (líneas ~2788–2805).
3. **`agentes/curriculum/v317-knowledge-graph-adaptive-plan.md`** — por qué I2/M4/O1/O3 se
   difirieron (D4 de v3.17) y qué tocó v3.17 del grafo/plan.
4. **`docs/audit/E-FSRS-RETENTION.md`** y **`docs/EVIDENCE_GRAPH.md`** — separación de mecanismos
   (ventanas fijas vs scheduler FSRS) y contrato del grafo.
5. **`docs/ARQUITECTURA.md`** — separación estricta routers → domain → repositories/servicios →
   schemas; frontend api/features/hooks/types.
6. Código motor — **`backend/services/unit_review.py`** (puro; `unit_anchor` :99, `window_due_at`
   :118, `build_unit_review_plan` :161, `UNIT_REVIEW_WINDOWS_DAYS` :33, `MICRO_REVIEW_PASS_RATIO`),
   **`backend/services/fsrs.py`** (`why_for_objective` :394, `TARGET_TYPES` :40, `schedule`,
   `is_due`, `due_queue`), **`backend/services/evidence_graph.py`** (`rank_weakness_objectives` :439,
   `enrich_item` :487, `GRAPH_DIMENSIONS` :33).
7. Orquestación **`backend/domain/academy.py`** — `sync_fsrs_cards` (:1652), `get_fsrs_due` (:1836),
   `get_fsrs_summary` (:1847), `review_fsrs_card` (:1869), `_unit_review_context` (:2040),
   `get_unit_review_plan` (:1982), `get_unit_micro_review` (:2060), `submit_unit_micro_review`
   (:2113), `_session_steps` (:2312), `get_session` (:2408), `get_next_best_activity` (:2425),
   `_current_level_id` (:531), `_objective_nodes_for` (:2278).
8. Persistencia **`backend/repositories/db.py`** (`fsrs_cards` :418, `unit_review_attempts` :449,
   `init_db` :29, patrón de índices/migraciones idempotentes) y **`backend/repositories/academy.py`**
   (`list_unit_review_attempts` :1120, `insert_unit_review_attempt` :1060, `list_fsrs_cards`,
   `get_fsrs_card` :1030, `upsert_fsrs_card`, `list_enrollments` :40, `list_objective_mastery` :190).
9. Contratos **`backend/schemas/academy.py`** — `FsrsDueOut`/`FsrsSummaryOut`/`FsrsReviewRequest`
   (:916/:922/:930), `UnitReviewWindowOut`/`UnitReviewPlanUnitOut`/`UnitReviewPlanOut` (:947–:980),
   `MicroReviewSessionOut`/`MicroReviewSubmitIn`/`MicroReviewResultOut` (:996–:1060).
10. Frontend — **`frontend/src/features/review/UnitReviewPanel.tsx`**, `unitReviewLogic.ts` +
    `unitReviewLogic.test.ts`, **`frontend/src/features/review/FsrsReviewPanel.tsx`**,
    **`frontend/src/components/TodayPlan.tsx`** (`SessionStepRow` :317, chip `SKILL_LABELS[limit.id]`
    :353), **`frontend/src/components/NextBestCard.tsx`** (`next.limiting_factor.id` :89),
    **`frontend/src/components/ObjectiveNodeCard.tsx`** (estados :60/:75, dimensiones `dim.id` :107,
    foco :120), **`frontend/src/api/academy.ts`** (`getUnitReviewPlan` :387, `getUnitMicroReview` :394,
    `submitUnitMicroReview` :409, `getEvidenceGraphNode` :535), **`frontend/src/api/client.ts`**
    (`request`/`getJson`, errores como `Error(texto)` sin `.status`), `frontend/src/types/api.ts`
    (`UnitReviewPlan` :1649), `frontend/src/utils/learningLabels.ts` (`SKILL_LABELS`, decisión V3.6.1),
    `frontend/src/utils/i18n.ts` + `i18n.parity.test.ts`.
11. Tests que fijan el estado actual — **`backend/tests/test_unit_review.py`** (puro: `window_due_at`
    :127–:213, `unit_anchor` :229, `build_unit_review_plan` :243), **`backend/tests/test_unit_review_endpoints.py`**
    (siembra y plan :120–:180, micro-review), `frontend/src/features/review/unitReviewLogic.test.ts`,
    `frontend/src/components/TodayPlan.test.tsx` (D6), `frontend/src/api/academy.test.ts`,
    `frontend/src/utils/learningLabels.test.ts`, specs Playwright de la región Home en
    `frontend/tests/visual/` (gateHelper + smoke + specs de rutas).

Baseline reportado en el cierre v3.17: **pytest 1335**, **vitest 398**, ruff/tsc/build/
`check_release_consistency` OK. Ejecuta tus propios números antes de tocar nada (Fase F) y repórtalos.

## Contexto técnico (resumen verificado)

- **Ventanas fijas V3.16** (`services/unit_review.py`, puro): `unit_anchor(rows)` =
  `max(updated_at)` de las filas de mastery vivas → un refuerzo/decay post-completitud **mueve** el
  ancla y erosiona la fijeza de D3 (deuda I2). `window_due_at(anchor, wd, now, attempts)` deriva el
  estado de la ventana **solo** de intentos de ESA ventana → una resolución tardía de la 7 no cierra
  la 30 ya vencida (deuda O1). `build_unit_review_plan` ancla desde filas y no desde persistencia.
- **Cartas FSRS `objective`** (V3.16): `sync_fsrs_cards` siembra cartas para objetivos de unidades
  completadas del nivel actual; se siembran también en ventanas `upcoming`; `get_fsrs_due` las mete
  en la cola del `FsrsReviewPanel` autograduable y `review_fsrs_card` las acepta → doble escritor con
  el micro-review (deuda M4). `unit_review_attempts` guarda `level_id` por intento.
- **Plan por nivel (O3)**: `get_unit_review_plan` resuelve UN nivel (`_current_level_id` o el pedido);
  al subir de nivel, las unidades completadas de niveles anteriores quedan fuera del plan y el
  micro-review (`_find_review_unit(lv, ...)` con `lv = _levels_by_id[_current_level_id]`) no puede
  repasarlas → ventanas huérfanas.
- **Coste `/session` y `/next-best` (H6)**: `_session_steps` (compartida por ambos endpoints) hace
  `list_evidence` SIEMPRE (:2354) y construye nodos para TODOS los candidatos de remediación de TODAS
  las destrezas débiles (:2357–:2375) aunque solo las primeras `SESSION_CAPS["weakness"]` (2) entradas
  de remediación puedan convertirse en paso (`adaptive.session_plan` :573–:589 usa solo
  `r["objective_ids"][0]` de cada grupo, con cap = 2).
- **Chip de factor limitante (H5)**: `TodayPlan.tsx` y `NextBestCard.tsx` resuelven la etiqueta con
  `SKILL_LABELS[id] ?? id`; `transfer`/`discourse`/`interaction` no están en `SKILL_LABELS` → id en
  crudo. `ObjectiveNodeCard` imprime `dim.id` y `recommended_focus.dimension` en crudo. Convención
  V3.6.1: las etiquetas pedagógicas van en inglés de inmersión también en la UI en español.
- **Auditoría v3.17**: `getEvidenceGraphNode` (frontend) lanza `Error(texto)` sin `.status` en
  cualquier no-2xx; el `ObjectiveNodeCard` pinta la copia de "sin datos" tanto para 404 como para
  error real. `rank_weakness_objectives` hace `float(node["mastery"])` sin salvaguarda.
  Región visual tocada en v3.17 (micro-líneas del plan, `ObjectiveNodeCard`) tiene cobertura
  Playwright parcial vía specs de Home/`smoke`.

## Decisiones de diseño (detalle y justificación)

### D1 — I2: ancla persistida y congelada (tabla `unit_review_anchors`)

**Problema**: hoy el ancla es `max(updated_at)` de filas vivas; cualquier refuerzo/decay posterior a
la completitud desplaza las ventanas 7/30/90.

**Diseño**:
- **Tabla nueva** `unit_review_anchors` (`backend/repositories/db.py`, `init_db` idempotente):
  `user_id TEXT`, `level_id TEXT`, `unit_id TEXT`, `anchor TEXT NOT NULL`, `created_at TEXT NOT NULL`,
  `updated_at TEXT NOT NULL`, `PRIMARY KEY (user_id, level_id, unit_id)`, FK `user_id →
  users(id)`. Índice de búsqueda por `(user_id, level_id)` si procede.
- **Repos** (`backend/repositories/academy.py`): `get_unit_anchor(user_id, level_id, unit_id) →
  str | None`; `set_unit_anchor_if_absent(user_id, level_id, unit_id, anchor)` → inserta solo si no
  existe (semántica `INSERT OR IGNORE`, nunca sobrescribe).
- **Helper de dominio** `_ensure_unit_anchors(user_id, lv, obj_mastery, mastered_ids)` (async): para
  cada unidad del nivel que esté **completada** y sin ancla persistida, deriva
  `unit_review.unit_anchor(rows)` y persiste con `set_unit_anchor_if_absent`. Se llama una vez por
  flujo, tras calcular `mastered`, en: `get_unit_review_plan`, `_unit_review_context`, `sync_fsrs_cards`.
  Es el **backfill lazy** de despliegue: la primera lectura de una unidad ya completa la congela con
  el ancla derivada de ese momento; a partir de ahí la tabla manda y los refuerzos no la mueven.
- **`services/unit_review.py`** sigue puro: `unit_anchor(rows)` se conserva como derivación de
  backfill (sus tests no cambian de semántica). `build_unit_review_plan` gana parámetro opcional
  `anchor: str | None = None` y, si se pasa, usa ese ancla para las ventanas en lugar de derivar de
  las filas (docstring: "ancla congelada si el llamador la tiene persistida; si no, derivada").
- **Orquestación**: `_unit_review_plan_dict` y `sync_fsrs_cards` resuelven el ancla con un helper
  `_frozen_anchor(user_id, lv, unit, obj_mastery)` que consulta la tabla y, si no hay ancla pero la
  unidad está completa, la persiste (misma lógica que `_ensure_unit_anchors`, sin duplicar: un único
  helper usado por ambos caminos).

**Comportamiento acordado**: el ancla se escribe UNA vez, en la primera detección de completitud;
nunca se reescribe (ni si la unidad decae y se re-domina después — determinismo y simplicidad D3).

### D2 — O1: cadena de ventanas 7→30→90 (resolución tardía)

**Problema**: si el alumno resuelve la ventana 7 el día 40 (porque no estudió), la 30 ya venció;
hoy la 30 sigue abierta aunque el alumno acabe de demostrar retención ≥ 30 días con su intento
superado de la 7.

**Diseño** (cascade, regla determinista):
- En `window_due_at`, los intentos recibidos pasan a ser **los de la unidad** (todas las ventanas) y
  la función filtra internamente por `window_days` para el "intento propio". Regla de estado:
  1. Si la ventana tiene intento propio (cualquier ventana): `passed`/`failed` según el último,
     como hoy (el intento propio manda siempre).
  2. Si NO tiene intento propio: `passed` si existe un intento **superado** (`passed == True`) de la
     unidad, de cualquier ventana, con `created_at >= due_at` de esta ventana.
  3. Si no: `due_now` si `now >= due_at`, si no `upcoming` (como hoy).
- `build_unit_review_plan` ya recibe los intentos de la unidad; deja de pre-filtrarlos por ventana al
  llamar a `window_due_at` (o se lo pasa todo y el filtrado vive dentro). La función pura se actualiza
  con tests nuevos: intento de la 7 superado el día 40 → la 30 queda `passed` y la 90 queda
  `upcoming`/`due_now` según `now`; un intento propio fallido de la 30 manda sobre un superado de la
  7 aunque sea posterior; intento superado de la 30 el día 32 también cierra la 7 sin intento propio.
- **Consecuencias en `why_for_objective`**: los estados cascade alimentan `windows`; un intento
  superado tardío puede llevar la ventana siguiente a `passed` y acelerar la llegada a
  `unit-maintenance`. No cambia la función: solo recibe estados ya resueltos.
- **Consecuencias en `FsrsReviewPanel`/`get_fsrs_due`**: ninguna directa (los estados de ventana no
  gobiernan la cola FSRS).

### D3 — M4: cartas `objective` fuera del panel autograduable (single writer)

**Problema**: una carta `objective` de una unidad completada puede recibir grade de DOS vías: el
micro-review de la ventana (que la puntúa con la precisión real por objetivo en servidor) y el
autograde manual del `FsrsReviewPanel`.

**Diseño**:
- `get_fsrs_due` (domain :1836): tras `sync_fsrs_cards` + `due_queue`, **excluye**
  `target_type == "objective"` de la cola devuelta y de `due_count`. El `FsrsReviewPanel` nunca
  recibe cartas `objective` (su contenido se repasa vía `UnitReviewPanel`).
- `get_fsrs_summary` (:1847): `by_type` sigue mostrando totales por tipo (diagnóstico, incluye
  `objective`), pero `due_count` excluye `objective` (misma regla que la cola: "pendientes" = lo que
  la UI puede repasar).
- `review_fsrs_card` (:1869): rechaza `target_type == "objective"` devolviendo `None` → el router
  responde 400 ("Review FSRS no válido"). Con esto el doble escritor queda cerrado a nivel de API.
- `sync_fsrs_cards` (:1652): **creación** de carta `objective` solo cuando la primera ventana no
  superada de su unidad está `due_now`/`failed` **o** la carta ya existe con `reps > 0` (continuidad
  de scheduling entre ventanas). En ventana `upcoming` y carta inexistente → no se crea. Cartas
  existentes (`reps > 0`) siguen refrescándose en `why`/`label` y, si `due_now`, en `due_at`.
- El seeding se amplía al conjunto de niveles del plan agregado (D4): la continuidad de scheduling de
  los objetivos acompaña a las ventanas de la unidad **en el nivel donde viven** (actual o anterior).
- Frontend `FsrsReviewPanel.tsx`: sin cambios funcionales (el servidor ya garantiza que no recibe
  `objective`); el copy de "nada pendiente" ahora es honesto porque los objetivos se repasan en la
  pestaña de unidades.

### D4 — O3: plan de repaso agregado por niveles (actual + anteriores)

**Diseño** (payload evolucionado):
- **Schemas** (`backend/schemas/academy.py`): nuevo `UnitReviewLevelOut { level_id, level,
  due_count, units: list[UnitReviewPlanUnitOut] }`; `UnitReviewPlanOut` pasa a
  `{ levels: list[UnitReviewLevelOut], due_count: int }` (due_count global). Docstrings.
- **Domain** `get_unit_review_plan(user_id, level_id=None)`: si `level_id` viene, restringe a ese
  nivel (mantiene el 404 del test actual para ids desconocidos del currículo); si no, itera los
  niveles matriculados (`list_enrollments` ordenados asc) desde el primero hasta el actual
  (`_current_level_id`) e incluye por nivel solo las unidades completadas o con intentos (misma regla
  de filtrado de hoy por nivel); `_ensure_unit_anchors` por nivel antes de construir planes.
- **Micro-review** (`get_unit_micro_review` :2060 y `submit_unit_micro_review` :2113): parámetro
  `level_id: str | None = None` que resuelve el nivel del repaso (por defecto el actual); la unidad
  se valida con `_find_review_unit(lv_nivel, unit_id)` **en el nivel donde vive** (no solo el actual);
  `submit` persiste el intento con `level_id` del nivel resuelto y `_unit_review_context(user_id,
  lv_nivel)`. Los routers de GET/POST micro-review aceptan `level_id` query/body opcional
  (`MicroReviewSubmitIn` gana `level_id: str | None = None`).
- **Frontend**: `frontend/src/types/api.ts` espeja `UnitReviewPlan { levels: UnitReviewLevel[];
  due_count }`. `UnitReviewPanel` agrupa por nivel (cabecera `A1 · 3 unidades por repasar`, etc.),
  filtra el conjunto aplanado para el contador `dueCount` global y el "review" del micro-review
  recuerda el `level_id` de la unidad para `getUnitMicroReview`/`submitUnitMicroReview` (que ganan
  `levelId?`). `unitReviewLogic` añade helpers para contar/aplanar por nivel manteniendo los puros
  existentes; `HomeScreen` sin cambios (misma prop `userId`).
- **i18n**: cabeceras de nivel y copys nuevos en es/en con parity (`unitReview.levelDue` o similar);
  los códigos de nivel (`A1`, `B2`…) no se traducen.

### D5 — H5: etiquetas humanas compartidas para dimensiones del grafo

**Diseño**:
- `frontend/src/utils/learningLabels.ts`: exportar `GRAPH_DIMENSION_LABELS: Record<string, string>`
  con las 7 dimensiones (`vocabulary`, `grammar`, `discourse`, `listening`, `speaking`,
  `interaction`, `transfer`) en inglés de inmersión (convención V3.6.1) y helper
  `dimensionLabel(id: string): string` que devuelve la etiqueta del mapa o `id` en crudo si es
  desconocida. (No i18n: rompería V3.6.1.)
- Sustituir en todos los puntos que pintan ids del grafo por `dimensionLabel(...)`:
  - `TodayPlan.tsx` chip del factor limitante (:353, hoy `SKILL_LABELS[limit.id] ?? limit.id`).
  - `NextBestCard.tsx` `limiting_factor.id` (:89).
  - `ObjectiveNodeCard.tsx` dimensiones `dim.id` (:107) y `recommended_focus.dimension` (:120).
  - `EvidenceGraphPanel.tsx` `top_limiting_factor.id` si lo pinta en crudo (verificar).
- Tests: `learningLabels.test.ts` (mapa + helper + fallback), `TodayPlan.test.tsx` (chip con
  `transfer` pinta "Transfer" no el id).

### D6 — H6: coste de `/session` y `/next-best` (lazy minimal)

**Diseño** (payloads idénticos; sin cambios de API; D7 del plan intacto):
- En `_session_steps` (:2312), **antes** de leer evidencia y construir nodos:
  1. Calcular el subconjunto de remediación que puede producir pasos `weakness`:
     `groups = remediation[:SESSION_CAPS["weakness"]]` (importar `adaptive.SESSION_CAPS`); solo las
     `objective_ids` de esos grupos son candidatas a ranking por nodo.
  2. `needs_nodes = bool(groups) or bool(next_objective_id)`; si es `False`, **no** llamar a
     `list_evidence` ni construir nodos: los pasos salen sin campos de grafo (fallback D7), igual que
     hoy cuando no hay nodos.
  3. Si `needs_nodes`, UNA lectura de `list_evidence` (como hoy) y nodos solo para: candidatos de
     `groups` (ranking) + objetivos de los pasos resultantes que tengan `objective_id` (enriquecido;
     reutiliza el mapa `nodes` con `setdefault`).
- `get_session` y `get_next_best_activity` no cambian su lógica: comparten `_session_steps`, así que
  nunca divergen y cada uno paga una sola lectura de evidencia.
- Tests de regresión de coste: (1) endpoint con estado que no produce pasos con objetivo → se
  monkeypatchea `academy_repo.list_evidence` para que falle si se llama (o se cuenta llamadas = 0);
  (2) estado con debilidad → `list_evidence` se llama **una** vez por petición (no una por destreza);
  (3) paridad `/next-best` == `/session` se conserva (tests D1b existentes siguen verdes).

### D7 — Observaciones de la auditoría v3.17 (37.35)

1. **`ObjectiveNodeCard` error vs sin-datos**: `getEvidenceGraphNode` (frontend) distingue 404 del
   resto: ampliar `request` de `frontend/src/api/client.ts` con un modo "404 → null" (parámetro
   interno `notFoundAsNull` o un `getJsonNullable`) y usarlo en `getEvidenceGraphNode`. El
   componente pasa a tres estados: `node == null` → copia vacía actual (`evidenceGraph.empty`);
   error real (red/5xx) → nueva copia `evidenceGraph.error` + botón reintento; loading intacto.
   Test del cliente (404 → null) y del componente (error vs vacío).
2. **`float()` defensivo en `rank_weakness_objectives`** (`evidence_graph.py:439`): helper
   `_as_float(value)` con `try/except` y fallback `0.0` para `mastery` (y cualquier score) en la
   ordenación; no cambia salida con nodos bien formados. Test puro con nodo `mastery: None` y
   `mastery: "n/a"` → no lanza y ordena al final de su grupo (empate estable).
3. **Playwright de la región tocada**: los cambios de H5/D4 tocan la Home (`TodayPlan`, chips) y el
   curso/Habilidades (`ObjectiveNodeCard`). Se ejecutan los specs existentes de Home
   (`frontend/tests/visual/smoke.spec.ts` y compañeros) y se **extiende o añade** la cobertura de la
   región del grafo con mock de red determinista (un ítem de sesión con `limiting_factor.id =
   "transfer"` → el chip muestra "Transfer"; `ObjectiveNodeCard` con nodo y con 404) siguiendo la
   arquitectura de `gateHelper.ts`/specs V3.9. Si un golden cambia, se actualiza según convención.

## Plan de fases

### Fase A — Backend puro: ancla congelada + cascade + siembra (tests primero)

En `backend/services/unit_review.py` (y sus tests `test_unit_review.py`):
1. `build_unit_review_plan` acepta `anchor: str | None = None` (docstring); ventanas usan ese ancla
   cuando se pasa.
2. `window_due_at`: contrato cascade (intentos de la unidad, filtrado interno por ventana propia;
   intento propio manda; si no, `passed` por intento superado de la unidad con `created_at >=
   due_at`). Actualizar con honestidad los tests puros que fijaban "otras ventanas no afectan" al
   nuevo significado.
3. Tests puros nuevos:
   - ancla: `build_unit_review_plan(..., anchor=fijo)` no deriva de filas posteriores;
   - cascade: 7 superada tarde cierra 30 y deja 90 abierta (o due_now según `now`); fallido propio
     de 30 manda; superado de 30 también cierra 7 sin intento propio; `upcoming` futura no se cierra.

En `backend/services/fsrs.py` (sin cambiar `TARGET_TYPES`/`schedule`): solo si hace falta un helper
de filtrado de estados para la siembra; si no, la lógica vive en el dominio.

### Fase B — Backend persistencia + dominio

En `backend/repositories/db.py` + `backend/repositories/academy.py`:
1. Tabla `unit_review_anchors` idempotente en `init_db` (patrón existente) + índice.
2. Repos `get_unit_anchor`/`set_unit_anchor_if_absent`.

En `backend/domain/academy.py`:
3. `_ensure_unit_anchors` / `_frozen_anchor` y uso en `get_unit_review_plan`, `_unit_review_context`,
   `sync_fsrs_cards` (ancla persistida mandando; backfill lazy en la primera lectura de unidades ya
   completadas).
4. **M4 (D3)**: `get_fsrs_due` excluye `objective` de cola y `due_count`; `get_fsrs_summary`
   mantiene `by_type` completo pero excluye `objective` del `due_count`; `review_fsrs_card` rechaza
   `objective`; `sync_fsrs_cards` gating de creación (due_now/failed o `reps>0`) y barrido de niveles
   del plan agregado.
5. **O3 (D4)**: `get_unit_review_plan` agregado por niveles; `get_unit_micro_review` y
   `submit_unit_micro_review` aceptan `level_id` y validan la unidad en su nivel real.
6. **H6 (D6)**: `_session_steps` lazy (grupos ≤ `SESSION_CAPS["weakness"]`, `list_evidence` solo si
   `needs_nodes`, una sola lectura).

En `backend/schemas/academy.py` y routers (`backend/routers/academy.py`):
7. Schemas nuevos/actualizados (docstrings); router micro-review con `level_id` opcional;
   `/fsrs/review` → 400 para `objective` (sin cambio de código: `None` ya mapea a 400).

**Tests de Fase B** (nuevos + honestos): endpoint del plan agregado (usuario con unidades completas
en A1 y cursando A2 → `levels` con A1+A2 y `due_count` global); micro-review de unidad de nivel
anterior con `level_id` explícito (y 404 si la unidad no está en ese nivel); aislamiento usuario
(premisa 13); siembra objective solo due_now/failed o con `reps>0` (revisar y actualizar
`test_unit_review_endpoints.py:120` con el nuevo gating); `get_fsrs_due`/`summary` sin `objective`
en cola/due_count pero presente en `by_type`; `review_fsrs_card("objective", ...)` → 400; coste H6
(0 llamadas a `list_evidence` sin pasos con objetivo; 1 llamada cuando hay); ancla congelada en
dominio (refuerzo posterior a la primera lectura no mueve las ventanas del plan).

### Fase C — Frontend: tipos, cliente y H5

1. `frontend/src/utils/learningLabels.ts`: `GRAPH_DIMENSION_LABELS` + `dimensionLabel`; aplicar en
   `TodayPlan.tsx`, `NextBestCard.tsx`, `ObjectiveNodeCard.tsx`, `EvidenceGraphPanel.tsx` (H5/D5).
2. `frontend/src/api/client.ts`: modo 404→`null` (parámetro interno); `getEvidenceGraphNode` lo usa.
   `ObjectiveNodeCard`: estado `error` con copia nueva (`evidenceGraph.error`) + reintento; `null` →
   copia vacía actual; loading intacto (D7.1).
3. i18n es/en con parity para las claves nuevas.
4. Tests: `learningLabels.test.ts`, `TodayPlan.test.tsx` (chip transfer/discourse/interaction),
   `academy.test.ts` (404→null), vitest del componente `ObjectiveNodeCard` (error/404/empty/nodo).

### Fase D — Frontend: plan de repaso agregado (O3/D4)

1. `frontend/src/types/api.ts`: `UnitReviewPlan { levels: UnitReviewLevel[]; due_count }`.
2. `frontend/src/api/academy.ts`: `getUnitMicroReview`/`submitUnitMicroReview` aceptan `levelId?`;
   `getUnitReviewPlan` sin cambios de firma.
3. `UnitReviewPanel.tsx` + `unitReviewLogic.ts`: agrupación por nivel con cabecera, contador global
   y micro-review con `level_id` de la unidad; copys nuevos en i18n (es/en).
4. Tests: `unitReviewLogic.test.ts` actualizado (aplanar/contar por nivel), vitest de `UnitReviewPanel`
   con payload multi-nivel (fetch mockeado); parity verde.

### Fase E — Frontend: `FsrsReviewPanel` (D3, solo verificación)

El servidor ya excluye `objective`; verificar que el panel no muestra tarjetas `objective` con un
mock de `getFsrsDue` que incluya cartas de los tres tipos (solo skill/lexicon en la cola) y que el
copy de vacío no se rompe cuando solo hay `objective` pendientes.

### Fase F — Verificación local (obligatoria, misma secuencia que los cierres previos)

- Backend (desde `backend/`): `python -m pytest tests/ -q` → TODO verde (baseline 1335 + deltas) y
  `ruff check .` limpio.
- Frontend (desde `frontend/`): `npm test` (vitest) verde (baseline 398 + deltas), `npm run build`
  (tsc + vite) OK.
- Playwright: specs de la región Home/curso tocada verdes o goldens actualizados según convención
  (D7.3).
- `python scripts/check_release_consistency.py` (o el nombre real) → exit 0.
- Reporta números reales y toda actualización honesta de tests preexistentes con su porqué.

## Criterios de aceptación

1. **I2 (D1)**: el ancla de una unidad completada queda persistida en `unit_review_anchors` la
   primera vez que se detecta la completitud; refuerzos/decay posteriores NO mueven las ventanas 7/30/90
   (test de dominio: segunda lectura tras tocar `updated_at` → mismas `due_at`). Tabla idempotente;
   backfill lazy para unidades ya completadas al desplegar.
2. **O1 (D2)**: ventana sin intento propio se cierra por un intento superado de la unidad con
   `created_at >= due_at` (test puro); el intento propio manda siempre; la cadena 7→30→90 resuelve
   la resolución tardía.
3. **M4 (D3)**: `get_fsrs_due`/`due_count` (due y summary) excluyen `objective`; `by_type` conserva
   totales; `POST /fsrs/review` con `target_type=objective` → 400; `sync_fsrs_cards` crea cartas
   `objective` solo en ventana due_now/failed o con `reps > 0`; la continuidad de scheduling cubre
   los niveles del plan agregado. El `FsrsReviewPanel` no puede recibir cartas `objective`.
4. **O3 (D4)**: `/unit-plan` devuelve `levels[]` (actual + anteriores matriculados con unidades
   completadas/activas) con `due_count` global; el micro-review acepta `level_id` y valida la unidad
   en su nivel real; `UnitReviewPanel` agrupa por nivel; i18n es/en con parity; aislamiento usuario.
5. **H5 (D5)**: el chip del factor limitante y las dimensiones del grafo muestran etiqueta humana
   (`Transfer`/`Discourse`/`Interaction`), nunca el id en crudo; mapa compartido con helper y tests.
6. **H6 (D6)**: `/session` y `/next-best` no llaman a `list_evidence` cuando no hay nodos que
   construir y, cuando hay, la llaman una sola vez por petición; los payloads son idénticos a antes
   (paridad `/next-best` == `/session` y D7 intactos).
7. **Observaciones v3.17 (D7)**: `ObjectiveNodeCard` distingue error real (copia + reintento) de
   404/sin-datos; `rank_weakness_objectives` tolera `mastery` no numérico sin lanzar (test);
   cobertura Playwright de la región tocada ejecutada (y extendida si procede).
8. Docstrings en todo código nuevo/modificado (premisa 18); capas estrictas; sin LLM; puntuación en
   servidor (premisa 21); i18n es/en; aislamiento por usuario (premisa 13); UI con estados
   vacío/carga/error y responsive (premisas 19/20).
9. Fase F verde y reportada con números; cierre de release hecho (bump 3.18.0, docs, release-notes).

## Restricciones

- NO tocar: semántica de `objective_node`/`dimension_scores`/`limiting_factor`/`build_level_graph`/
  `explain_because`/`enrich_next_best` (si un test lo exige, para y reporta); `GRAPH_VERSION`
  (v3.18 no cambia la salida del grafo; solo añade un helper de etiquetas y un `float()` defensivo);
  `fsrs.TARGET_TYPES`/`schedule`/`grade_from_score`; el motor de mastery/evidencia
  (`remediation_plan`/`recommend_next`/`apply_objective_evidence`); `docs/CONSTITUCION-PEDAGOGICA.md`.
- El esqueleto del plan (`/session`, `session_plan`, Priority Engine, `/next-best`) se conserva:
  H6 cambia solo el coste (nodos/evidencia lazy), nunca los pasos ni su orden.
- El micro-review NO crea evidencia de mastery/currículo ni declara dominio (D5 de v3.16); la ventana
  sigue siendo un hito fijo que un grade no recalendariza.
- Cero contenido curricular artificial; sin LLM; determinista; puntuación en servidor (premisa 21).
- Capas estrictas: routers sin lógica; services puros sin FastAPI/BD; repos sin negocio; schemas
  Pydantic con docstrings; frontend api/features/types separados.
- i18n completa es/en con parity (test obligatorio); sin cadenas hardcodeadas en componentes
  (las etiquetas pedagógicas en inglés de inmersión siguen la convención V3.6.1 documentada en
  `learningLabels.ts`).
- Aislamiento por usuario en toda consulta nueva (premisa 13); UI con estados vacío/carga/error y
  responsive (premisas 14/19/20).

## Salida

Informe final que reporte:
1. Archivos nuevos/modificados (ruta + función/rol de 1 línea).
2. Números de la Fase F (pytest/ruff/vitest/build/Playwright/consistencia) y toda actualización
   honesta de tests preexistentes con su porqué.
3. Confirmación explícita de cada criterio de aceptación (1–9).
4. Cierre de release v3.18.0: bump único (`backend/config.py` `3.17.0 → 3.18.0` +
   `frontend/package.json`/`package-lock.json`), `README`, `CHANGELOG`, `PLAN`, nota superior +
   entrada 37.36 en `docs/RELEVO.md`, `release-notes-v3.18.0.md`.
5. Cualquier desviación de las decisiones D1–D7 (si una se revela inviable en código, párala y
   documéntala con la alternativa; NO la resuelvas por tu cuenta).

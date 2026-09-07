# v3.17.0 — Knowledge Graph + Daily Adaptive Plan

**El candidato P2 se cierra: la infra del grafo (`evidence_graph.py` v2.12 + `adaptive.py`) existía, pero el plan diario no derivaba del grafo, había un motor muerto (`/api/academy/today`) sin consumidor y no existía vista de grafo real. Ahora la debilidad se practica sobre el objetivo que su nodo señala, los pasos de la sesión explican su can-do con su dominio y el detalle del nodo se ve en el curso y en el perfil.**

## Qué cambia

- **El plan diario deriva del Evidence Graph (D1b).** La destreza débil de la sesión se practica reordenando sus objetivos candidatos con el grafo: primero los que su nodo declara como factor limitante (o con la dimensión de la destreza sin evidencia), después por `mastery` ascendente. Cada paso de la sesión con objetivo y nodo gana `can_do`, `limiting_factor`, `graph_mastery` y las viñetas `because[]` — calculados con la misma lectura de perfil/evidencia que `/next-best`, así ambos nunca divergen.
- **Vista de grafo real (D2).** Nuevo componente `ObjectiveNodeCard` (reutilizable, consume `getEvidenceGraphNode`) que pinta el detalle de un can-do: su nodo, dimensiones con el factor limitante resaltado y el foco recomendado. Se abre **en el curso** (cada hito de objetivo de la unidad en curso es expansible bajo demanda) y **en el perfil** (el detalle del nodo seleccionado del panel de Habilidades pasa por la tarjeta). La UI no declara dominio: solo refleja lo que el servidor puntúa.
- **`/api/academy/today` eliminado (D3).** El motor de plan paralelo (`get_today_plan`, `TodayPlanOut`/`TodayItemOut`, `adaptive.today_plan` + `TODAY_MIX`, cliente `getTodayPlan` y sus tipos) desaparece de extremo a extremo: la Home consume solo `/session` (Session Engine). Sus tests se migran a `/session` con rationale honesto (el presupuesto del objetivo ya lo cubre el test del Session Engine).
- **Deuda de la auditoría v3.16 (D4b).** M2: el POST del micro-review valida que las respuestas pertenezcan a la muestra servida y que los índices estén en rango (400 sin persistir nada). M3: prefijos dinámicos (`unitReview.window.`/`unitReview.state.`/`skill.`/`fsrs.whyReason.`) registrados en el escáner de paridad i18n. O2: test de reintento parcial — GET==POST, muestra idéntica entre llamadas y fallidos primero. M1: infraestructura DOM y vitest de componente (ver Técnica).
- **Micro-líneas del plan (D6).** Cuando un paso de la sesión trae nodo, su fila muestra el can-do en itálica y un chip del factor limitante con su porcentaje (o `missing`) — información, dentro de la fila-botón, sin controles anidados.
- **Fallback silencioso (D7).** Un paso sin objetivo (p. ej. listening) o sin nodo construible no gana campos de grafo y la práctica nunca se bloquea por falta de datos.

## Técnica

- Backend (`3.16.0 → 3.17.0`, fuente única `backend/config.py`):
  - `backend/services/evidence_graph.py`: `rank_weakness_objectives` y `enrich_item` (puros, deterministas; `enrich_item` reutiliza `enrich_next_best` → mismo nodo, mismo resultado).
  - `backend/domain/academy.py`: `_objective_nodes_for` (mapa de nodos con una única lectura de evidencia), `_session_steps` reordena candidatos y enriquece pasos; `get_next_best_activity` copia los campos del primer paso enriquecido (sin re-leer); `get_today_plan` eliminado.
  - `backend/routers/academy.py`: endpoint `/api/academy/today` eliminado; `backend/schemas/academy.py`: `TodayPlanOut`/`TodayItemOut` eliminados y `SessionStepOut` ampliado con `can_do`/`limiting_factor`/`graph_mastery`/`because[]` opcionales.
  - `backend/services/unit_review.py` (M2): `validate_micro_review_answers` validando claves ⊆ muestra e índices en rango antes de puntuar.
  - Tests nuevos `test_graph_plan.py` y `test_session_graph.py`; migraciones de `/today` a `/session` en `test_academy.py`, `test_academy_goal.py`, `test_adaptive.py`; M2/O2 en `test_unit_review*.py`.
- Frontend:
  - `components/ObjectiveNodeCard.tsx` (nuevo), `Milestone` expansible en el curso, `EvidenceGraphPanel` reutiliza la tarjeta en Habilidades.
  - `TodayPlan.tsx`: micro-líneas D6 (can-do + chip del factor limitante) con CSS en `legacy.css`; cliente `getTodayPlan` y tipos `TodayPlan`/`TodayItem` eliminados.
  - **M1 (cierre)**: devDeps DOM `jsdom` + `@testing-library/react` (+ `@testing-library/dom`) en `frontend/package.json`; `vitest.config.ts` ampliado a `*.test.tsx` con el alias `@` (jsdom por archivo); 6 vitest de componente nuevos — `UnitReviewPanel.test.tsx` (estado vacío, ventana due, apertura del micro-review + submit + refresh con plan mutable, error de red con reintento) y `TodayPlan.test.tsx` (fila enriquecida D6 con can-do y chip `%`, y silencio D7 sin nodo).
- Sin cambios de CONSTITUCIÓN pedagógica (v3.17 conecta el grafo existente al plan: motor + UI, no norma) ni de launcher. `GRAPH_VERSION` permanece `2.12.0` (cambio aditivo).

## Tests

- Backend: **1333 pytest en verde**; `ruff check .` limpio.
- Frontend: **398 vitest en verde** (392 + 6 DOM) y build de producción (`tsc` + `vite build`) OK.
- `scripts/check_release_consistency.py` exit 0.

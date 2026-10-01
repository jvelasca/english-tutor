# v3.18.0 — Knowledge Graph remainder + deuda del grafo

**El candidato P3 (auditado ABIERTO en 2026-09-06) se cierra: la deuda del grafo que v3.17 dejó diferida queda implementada con las decisiones del gerente (2026-09-07). El ancla de repaso se congela (I2), las ventanas 7/30/90 encadenan ante la resolución tardía (O1), las cartas FSRS `objective` dejan de ser autograduables (M4, single writer con el micro-review), el plan de repaso agrega los niveles anteriores matriculados (O3), el grafo habla en etiquetas humanas (H5) y `/session`/`/next-best` dejan de pagar nodos/evidencia que no usan (H6).**

## Qué cambia

- **Ancla congelada (I2).** Nueva tabla `unit_review_anchors` (escritura única `INSERT OR IGNORE`, nunca sobrescribe) + repos `get_unit_anchor`/`set_unit_anchor_if_absent`. El ancla se persiste la primera vez que la unidad se detecta completa (backfill lazy en `get_unit_review_plan`, `_unit_review_context` y `sync_fsrs_cards`); un refuerzo o decay posterior ya no desplaza las ventanas 7/30/90 (`build_unit_review_plan` acepta `anchor=` para usar la congelada).
- **Cadena de ventanas 7→30→90 (O1).** `window_due_at` aplica cascade: una ventana sin intento propio queda `passed` si existe un intento superado de la unidad con `created_at >= due_at`; el intento propio manda siempre. Resolver la 7 tarde cierra la 30 ya vencida.
- **Cartas `objective` fuera del panel autograduable (M4).** `sync_fsrs_cards` crea cartas `objective` solo en ventana `due_now`/`failed` o con `reps > 0` (continuidad de scheduling), barriendo los niveles del plan agregado; `get_fsrs_due` y el `due_count` de resumen las excluyen (`by_type` conserva totales); `review_fsrs_card` las rechaza → 400. Los objetivos se repasan solo vía `UnitReviewPanel`.
- **Plan de repaso agregado por niveles (O3).** `/api/academy/review/unit-plan` devuelve `{levels: [{level_id, level, units, due_count}], due_count}` (nivel actual + anteriores matriculados); el micro-review acepta `level_id` y valida la unidad en el nivel donde vive; `UnitReviewPanel` agrupa por nivel con contador por nivel e i18n es/en.
- **Etiquetas humanas de dimensiones del grafo (H5).** `GRAPH_DIMENSION_LABELS` (7 dimensiones, inglés de inmersión V3.6.1) + `dimensionLabel`; aplicadas en el chip del factor limitante (`TodayPlan`), `NextBestCard`, `ObjectiveNodeCard` y `EvidenceGraphPanel`. `transfer`/`discourse`/`interaction` ya no caen al id en crudo.
- **Coste lazy de `/session` y `/next-best` (H6).** Nodos solo para los grupos de remediación que pueden convertirse en paso (≤ `SESSION_CAPS["weakness"]`) y `list_evidence` una sola vez y solo si hay nodos que construir o enriquecer. Payloads idénticos (sin cambio de API; `/next-best` nunca diverge).
- **Observaciones auditoría v3.17.** `ObjectiveNodeCard` distingue error real (copia + reintento) de 404/sin-datos (`getJsonNullable`); `float()` defensivo (`_as_float`) en `rank_weakness_objectives`; spec Playwright `homeGraphChip` nueva con mock de red determinista ejecutada en desktop.

## Técnica

- Backend (`3.17.0 → 3.18.0`, fuente única `backend/config.py`):
  - `repositories/db.py`: tabla `unit_review_anchors` + índice (idempotente).
  - `repositories/academy.py`: `get_unit_anchor`, `set_unit_anchor_if_absent`, `list_unit_anchors`.
  - `services/unit_review.py`: `build_unit_review_plan(anchor=)` (I2) y cascade en `window_due_at` (O1), puros.
  - `services/evidence_graph.py`: helper `_as_float` en `rank_weakness_objectives`.
  - `domain/academy.py`: `_review_scope_levels`/`_resolve_unit_anchors`/`_resolve_micro_review_level` (O3+I2), `_sync_objective_cards_for_level` con gating M4, exclusión de `objective` en `get_fsrs_due`/`get_fsrs_summary`/`review_fsrs_card`, `_session_steps` lazy (H6).
  - `schemas/academy.py`: `UnitReviewLevelOut` + `UnitReviewPlanOut{levels, due_count}` + `level_id` en `MicroReviewSubmitIn`; routers con `level_id` opcional.
  - Tests: `test_unit_review.py`, `test_unit_review_endpoints.py`, `test_session_graph.py`, `test_graph_plan.py`.
- Frontend:
  - `utils/learningLabels.ts`: `GRAPH_DIMENSION_LABELS` + `dimensionLabel` (H5), aplicadas en `TodayPlan`/`NextBestCard`/`ObjectiveNodeCard`/`EvidenceGraphPanel`.
  - `api/client.ts`: `getJsonNullable` (404 → `null`); `api/academy.ts`: `getEvidenceGraphNode` nullable + micro-review con `levelId`.
  - `components/ObjectiveNodeCard.tsx`: estados `error` (copia + reintento) vs `empty`.
  - `features/review`: tipos espejo `UnitReviewPlan{levels, due_count}`, `flattenReviewLevels`, `UnitReviewPanel` agrupado por nivel con `level_id` real.
  - Tests: `learningLabels.test.ts`, `TodayPlan.test.tsx`, `academy.test.ts`, `client.test.ts`, `ObjectiveNodeCard.test.tsx` (nuevo), `UnitReviewPanel.test.tsx`, `FsrsReviewPanel.test.tsx` (nuevo), `unitReviewLogic.test.ts`.
- Sin cambios de CONSTITUCIÓN pedagógica (v3.18 es mecanismo/UI, no norma) ni de launcher. `GRAPH_VERSION` permanece `2.12.0` (cambio aditivo + helper).

## Tests

- Backend: **1345 pytest en verde**; `ruff check .` limpio.
- Frontend: **414 vitest en verde** (52 archivos) y build de producción (`tsc` + `vite build`) OK.
- Playwright: `smoke.spec.ts` + `homeGraphChip.spec.ts` (región Home/grafo, desktop) verdes; captura nueva `tests/visual/screenshots/desktop/home-graph-chip.png`.
- `scripts/check_release_consistency.py` exit 0.

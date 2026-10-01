# v3.16.0 — Review/SRS por unidad (micro-review + ventanas de retención 7/30/90 días)

**El candidato P1 "Review/SRS por unidad" (auditado abierto 2026-09-05) se cierra: el motor FSRS ya soportaba `target_type="objective"` pero nada lo sembraba y no existía plan de repaso por unidad ni ventanas fijas. Completar una unidad abre ahora un calendario de repaso de recuperación con micro-review de los checks oficiales — práctica, nunca declaración de dominio.**

## Qué cambia

- **Ventanas de retención fijas por unidad.** Al completar una unidad (todos sus objetivos `mastered`), su ancla temporal (`max(updated_at)` de las filas de mastery) abre tres ventanas **7 / 30 / 90 días**. Cada ventana es un hito fijo (estados `upcoming / due_now / passed / failed`): un grade nunca la recalendariza; solo la marca como superada o fallida.
- **Micro-review de recuperación.** Cuando una ventana toca (`due_now`) o falla (`failed`), se puede repasar con un mini-quiz determinista de hasta 8 checks **MC oficiales del currículo** de la unidad (muestreo balanceado por objetivo, máximo 2 por objetivo; cero contenido artificial). En un reintento se priorizan las preguntas falladas la última vez. Se aprueba con aciertos ≥ 70 %; el servidor puntúa las respuestas (el cliente solo envía índices, nunca puntuaciones) y revela la respuesta correcta al terminar.
- **El repaso es práctica, no evidencia.** El micro-review persiste su propio intento (`unit_review_attempts`, separado del currículo) y reprograma las cartas FSRS `objective` de la unidad con el grade derivado de la precisión por objetivo. **No crea evidencia de mastery ni declara dominio** (los mecanismos siguen etiquetados por separado, como marca el hallazgo E3 de `docs/audit/E-FSRS-RETENTION.md`); la UI lo dice con honestidad.
- **Cartas FSRS `objective` sembradas.** `sync_fsrs_cards` siembra/refresca cartas `target_type="objective"` para los objetivos de las unidades completadas del nivel actual, sin pisar cartas ya revisadas (`reps > 0`) y sin tocar `fsrs.TARGET_TYPES`. Nueva razón pedagógica `why_for_objective` (`unit-window-N` / `unit-maintenance`).

## Técnica

- Backend (`3.15.0 → 3.16.0`, fuente única `backend/config.py`):
  - Nuevo `backend/services/unit_review.py` — servicio puro y determinista (sin FastAPI ni BD): `UNIT_REVIEW_WINDOWS_DAYS = (7, 30, 90)`, `MICRO_REVIEW_PASS_RATIO = 0.7`, `MICRO_REVIEW_TARGET_ITEMS = 8`, `MICRO_REVIEW_MAX_PER_OBJECTIVE = 2`; `window_due_at`, `sample_micro_review` (semilla `user|unit|window`, reintento priorizando `failed_items`), `score_micro_review`, `grade_for_accuracy`.
  - `backend/domain/academy.py`: siembra `objective` en `sync_fsrs_cards` + orquestación `get_unit_review_plan` / `get_unit_micro_review` / `submit_unit_micro_review` (patrón de `get_today_plan`, nivel actual).
  - `backend/repositories/db.py`: tabla idempotente `unit_review_attempts` (con `per_objective` y `failed_items` en JSON) + índice de lookup; `backend/repositories/academy.py`: `insert/list/latest_unit_review_attempt` y `list_objective_mastery` expone `updated_at`.
  - `backend/services/fsrs.py`: `why_for_objective` (puro).
  - API en `backend/routers/academy.py`: `GET /api/academy/review/unit-plan`, `GET /api/academy/review/unit/{unit_id}/micro-review` (sin `correct_index` antes de responder), `POST /api/academy/review/unit/{unit_id}/micro-review`. Gating: 400 si la ventana no está `due_now`/`failed` o `window_days` inválido; 404 si la unidad es ajena al nivel.
  - Tests: `test_unit_review.py` (puro) y `test_unit_review_endpoints.py` (siembra solo en unidades completadas, idempotencia, sin `correct_index`, D5 sin evidencia nueva, gating de ventanas, aislamiento entre usuarios).
- Frontend:
  - `UnitReviewPanel` en INICIO (junto a `FsrsReviewPanel`): unidades con chips de ventana 7/30/90 y color por estado, contador de unidades por repasar, micro-review por tarjetas (una pregunta a la vez con feedback inmediato) y nota honesta "Repaso de retención · no cuenta como demostración de dominio".
  - Lógica pura en `unitReviewLogic.ts` (testeable sin DOM), tipos espejo en `types/api.ts`, cliente en `api/academy.ts` (envía respuestas, nunca puntuaciones), i18n `en`/`es` completa con parity.
- Sin cambios de CONSTITUCIÓN pedagógica (v3.16 es mecanismo, no norma) ni de launcher.

## Tests

- Backend: **1318 pytest en verde**; `ruff check .` limpio.
- Frontend: **392 vitest en verde** y build de producción (`tsc` + `vite build`) OK.

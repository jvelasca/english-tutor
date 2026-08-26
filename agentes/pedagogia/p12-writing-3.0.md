# V1.17 (3/3) — Writing 3.0 sobre el Student Model (espejo de speaking/listening)

## Rol
Subagente **full-stack** que convierte el writing en una señal de competencia **longitudinal**
sobre el Student Model, espejando exactamente el patrón ya implementado para speaking
(`V1.15`/`V1.16`) y listening. El writing hoy tiene scorer determinista y evidencia registrada,
pero **no** tiene diagnóstico por criterio, ni nivel continuo, ni journey, ni panel en el
frontend. Este incremento añade todo eso **sin cambiar el scoring actual**.

## Contexto (contratos exactos, NO romper)

### Backend — estado actual del writing
- `backend/services/writing.py`:
  - `WRITING_CRITERIA = ("task_completion", "grammatical_accuracy", "lexical_resource",
    "organization", "coherence", "register")` (6 dimensiones).
  - `CRITERION_WEIGHTS` (task_completion .25, grammatical_accuracy .20, lexical_resource .20,
    organization .15, coherence .10, register .10).
  - `score_writing(text, expected)`, `scores_from_evidence(evidence)`, `evidence_from_writing(...)`
    que registra una fila por criterio (`item_id = criterio`) + una fila `item_id="overall"`,
    todas con `skill="writing"`, `item_type="writing"`, `source="writing"`.
- `backend/services/writing_llm.py`: `extract_writing_evidence(task, text, model)` →
  dict normalizado; `parse_writing_evidence`.
- `backend/domain/academy.py`:
  - `submit_writing(...)`, `submit_writing_task(...)` registran evidencia vía
    `writing_svc.evidence_from_writing(...)` → `_record_evidence_validated(...)`.
  - `get_speaking_diagnostic`/`get_speaking_level`/`get_speaking_journey` (líneas ~556-580) son
    el patrón exacto a espejar: leen `academy_repo.list_evidence(user_id)`, filtran por
    `skill == "speaking"` y llaman a `speaking_svc.speaking_diagnostic/speaking_level/
    speaking_journey`.
- `backend/routers/academy.py`: `GET /api/academy/speaking/diagnostic|level|journey` (líneas
  337-349) son el patrón de endpoint a espejar.
- `backend/schemas/academy.py`: `SpeakingCriterionOut`, `SpeakingTrend`, `SpeakingDiagnostic`,
  `SpeakingLevelOut`, `SpeakingJourneyStep`, `SpeakingJourneyOut` (líneas 368-421) son el
  patrón de schema a espejar.

### El patrón a espejar (backend/services/speaking.py)
- `speaking_diagnostic(evidence_rows, now="")`: por criterio expone `attempts`, `mean`,
  `recent_score` (EMA α=0.5), `lifetime_score`, `confidence` (EMA de "supera umbral"),
  `stability` (`adaptive.skill_stability`), `min`/`max`, `review_due` (`forgetting.review_due`
  + fallo reciente + confianza baja). Devuelve `criteria`, `weak`, `recommendation`,
  `attempts`, `overall_mean`, `overall_recent`, `trend` (`_mean_trend`), `rubric_version`.
- `speaking_level(evidence_rows, now="")`: EMA de filas `item_id=="overall"` → `score`,
  `confidence`, `numeric = 1.0 + 5.0*score`, `level = adaptive.numeric_to_level(numeric)`,
  `attempts`.
- `speaking_journey(evidence_rows, now="")`: snapshots cronológicos `{at, numeric, level,
  confidence}` + estado actual.
- Constantes a espejar: `SPEAKING_EMA_ALPHA = 0.5`, `SPEAKING_WEAK_THRESHOLD = 0.6`,
  `SPEAKING_CONFIDENCE_THRESHOLD = 0.6`, `SPEAKING_TREND_WINDOW = 5`.

### Frontend — patrón a espejar
- `frontend/src/types/api.ts`: `SpeakingCriterionProgress`, `SpeakingTrend`,
  `SpeakingDiagnostic`, `SpeakingLevelOut`, `SpeakingJourneyStep`, `SpeakingJourneyOut`
  (líneas 347-404).
- `frontend/src/api/academy.ts`: `getSpeakingDiagnostic`, `getSpeakingLevel`,
  `getSpeakingJourney`.
- `frontend/src/components/SpeakingPanel.tsx` y `SpeakingJourney.tsx`: paneles de resumen
  (NEXT FOCUS + PRACTICE NOW) y de trayectoria (barra A2→B1→B2 con marcador "YOU").
- `frontend/src/utils/speaking.ts`: `criterionLabel`, `numericToCefr`, `formatConfidence`,
  `formatTrendDelta`, `nextFocus`. `frontend/src/utils/cefr.ts`: `cefrTone`, `cefrLabel`,
  `bandLabel`.
- `frontend/src/App.tsx`: los paneles se montan en el `aside` de insights (`.insights-scroll`,
  ~líneas 399-418), después de `SpeakingDiagnostic`/`SpeakingPanel`/`SpeakingJourney` y antes
  de `ListeningPractice`.

## Objetivo
Añadir `writing_diagnostic`, `writing_level` y `writing_journey` (backend) + endpoint +
esquemas + frontend (`WritingPanel`/`WritingJourney`), espejando speaking de forma consistente.

## Tarea

### 1. Backend — `services/writing.py`
Añade (espejando `speaking.py`, adaptando a 6 criterios):
- Constantes: `WRITING_EMA_ALPHA = 0.5`, `WRITING_WEAK_THRESHOLD = 0.6`,
  `WRITING_CONFIDENCE_THRESHOLD = 0.6`, `WRITING_TREND_WINDOW = 5`.
- `_ema(values, alpha)` (copia exacta de la de speaking), `_mean_trend(rows, window)` (copia
  adaptada), `_clamp`.
- `writing_diagnostic(evidence_rows: list[dict], now: str = "") -> dict`: idéntico en estructura
  a `speaking_diagnostic`, pero sobre `WRITING_CRITERIA`. Reutiliza
  `from services.curriculum import RUBRIC_VERSION`, `from services import adaptive`,
  `from services.forgetting import review_due`. Devuelve `criteria`, `weak`, `recommendation`,
  `attempts`, `overall_mean`, `overall_recent`, `trend`, `rubric_version`.
  - `recommendation` en inglés, mismo estilo: "All writing criteria look strong." /
    "Focus on: …".
- `writing_level(evidence_rows: list[dict], now: str = "") -> dict`: espejo de
  `speaking_level`; `numeric = round(1.0 + 5.0 * score, 2)`, `level = adaptive.numeric_to_level(numeric)`.
- `writing_journey(evidence_rows: list[dict], now: str = "") -> dict`: espejo de
  `speaking_journey` (`current_level`, `current_numeric`, `current_confidence`, `attempts`,
  `steps`).

### 2. Backend — `schemas/academy.py`
Añade (espejo de los de speaking):
- `WritingCriterionOut` (mismos campos que `SpeakingCriterionOut`).
- `WritingTrend` (mismos campos que `SpeakingTrend`).
- `WritingDiagnostic { criteria, weak, recommendation, attempts, overall_mean, overall_recent,
  trend, rubric_version }`.
- `WritingLevelOut { level, numeric, score, confidence, attempts }`.
- `WritingJourneyStep { at, numeric, level, confidence }`.
- `WritingJourneyOut { current_level, current_numeric, current_confidence, attempts, steps }`.

### 3. Backend — `domain/academy.py`
Añade, espejando `get_speaking_*`:
- `get_writing_diagnostic(user_id)`: `list_evidence(user_id)` → filtra `skill == "writing"` →
  `writing_svc.writing_diagnostic(rows, now=...)`.
- `get_writing_level(user_id)`: idem → `writing_svc.writing_level(rows)`.
- `get_writing_journey(user_id)`: idem → `writing_svc.writing_journey(rows)`.

### 4. Backend — `routers/academy.py`
Añade tres GET, espejando los de speaking (líneas 337-349):
- `GET /api/academy/writing/diagnostic` → `WritingDiagnostic`
- `GET /api/academy/writing/level` → `WritingLevelOut`
- `GET /api/academy/writing/journey` → `WritingJourneyOut`

### 5. Frontend — `types/api.ts`
Añade `WritingCriterionProgress` (mismos campos que `SpeakingCriterionProgress`), `WritingTrend`,
`WritingDiagnostic`, `WritingLevelOut`, `WritingJourneyStep`, `WritingJourneyOut`.

### 6. Frontend — `api/academy.ts`
Añade `getWritingDiagnostic(userId)`, `getWritingLevel(userId)`, `getWritingJourney(userId)`
(espejo de las de speaking).

### 7. Frontend — `utils/writing.ts` (nuevo) + `utils/speaking.ts`
- Crea `utils/writing.ts` con helpers equivalentes a los de speaking para los 6 criterios de
  writing: `writingCriterionLabel(criterion)` (p. ej. `task_completion` → "Task completion",
  `grammatical_accuracy` → "Grammatical accuracy", `lexical_resource` → "Lexical resource",
  `organization` → "Organization", `coherence` → "Coherence", `register` → "Register") y, si
  conviene, reexporta/usa `numericToCefr`/`formatConfidence`/`formatTrendDelta` de
  `utils/speaking.ts` (o muévelas a un util compartido si lo ves limpio, sin romper imports).
- Si añades helpers nuevos, testéalos en `utils/writing.test.ts`.

### 8. Frontend — componentes
- `components/WritingPanel.tsx` (props `{ userId: string | null }`): espejo de `SpeakingPanel`.
  Muestra nivel CEFR continuo (`cefr-badge` + `cefrTone`), `score` como %, confianza
  (`formatConfidence`), y lista de criterios (`writingCriterionLabel` + % + marca ⚠/✓ según
  `review_due`). Reutiliza los tokens/estilos existentes.
- `components/WritingJourney.tsx` (props `{ userId: string | null }`): espejo de
  `SpeakingJourney` (trayectoria con marcador "YOU").
- Monta ambos en `frontend/src/App.tsx` en el `aside` de insights, después de los paneles de
  speaking y antes de `ListeningPractice`.

### 9. Frontend — `index.css`
Añade clases `.writing-*` (o reutiliza las de `.speaking-*`) coherentes con tokens, tema
claro/oscuro y responsive (premisa 14).

### 10. Tests

#### Backend (pytest)
- Nuevo `backend/tests/test_writing.py` (o amplía el existente si lo hay): tests de
  `writing_diagnostic`, `writing_level`, `writing_journey` con fixtures de filas de evidencia
  (p. ej. sin filas → None/0.0; con una fila `overall` → nivel/score correctos; con criterios
  → `weak`/`review_due`/`trend`). Verifica que `numeric = 1.0 + 5.0*score` y que
  `adaptive.numeric_to_level` mapea bien.

#### Frontend (vitest)
- `utils/writing.test.ts` para `writingCriterionLabel` y helpers nuevos.
- Si existe `api/academy.test.ts`, añade tests de `getWritingDiagnostic`/`getWritingLevel`/
  `getWritingJourney` (URL y método, mock de fetch).

## Criterios de aceptación
- Backend: `pytest` en verde + `ruff` limpio. Frontend: `npx tsc --noEmit` + `npx vitest run`
  en verde.
- El writing expone diagnóstico por criterio, nivel continuo y journey en el Student Model,
  idénticos en *forma* a los de speaking (mismas señales: EMA, lifetime, confidence, stability,
  review_due).
- No se cambia el scoring determinista de writing existente (solo se añade la vista
  longitudinal encima).
- Frontend muestra `WritingPanel` + `WritingJourney` con estados vacío/carga/error, responsive.
- Todo nuevo con docstrings/JSdoc (premisa 18).

## Restricciones
- Espeja speaking: no reinventes nombres ni formas. Si dudas, copia la estructura de
  `speaking.py`/`speaking_*` y renombra.
- No rompas tests existentes; no introduzcas dependencias nuevas.
- El LLM no puntúa; solo extrae evidencia (ya está así; no lo toques).
- Crea **un único commit `feat:`** descriptivo (no hagas push).

## Salida
- Diff backend + frontend, y salida de pytest/ruff, tsc y vitest en verde.

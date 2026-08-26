# V1.17 (1/3) — UI del flujo de Speaking Assessment (start → 4 partes → resultado)

## Rol
Subagente **frontend** que construye la pantalla/flujo del Speaking Assessment usando los
endpoints backend **ya existentes y commiteados** en V1.16. No se toca el backend en este
incremento. La UI cubre: iniciar el assessment, mostrar cada una de las 4 partes (prompt +
instrucción de grabación), enviar la respuesta oral transcrita, avanzar entre partes y mostrar
el resultado final (nivel CEFR continuo, score, confianza y desglose por criterio).

## Contexto

El instrumento Speaking Assessment 1.0 ya existe en backend (`backend/curriculum/speaking_assessment.json`,
4 partes fijas: `Interview` → `Individual task` → `Interaction` → `Follow-up`) y sus endpoints
están en `backend/routers/academy.py` (ya commiteados). Contrato exacto (NO cambiar):

- `POST /api/academy/speaking/assessment/start` (sin body; `user_id` en query)
  → `{ session_id: int, assessment_version: str, total_parts: int, part: PartInfo | null }`
- `POST /api/academy/speaking/assessment/part`
  body `{ session_id: int, heard: string (1..2000), duration_seconds?: number|null, model?: string }`
  → `{ session_id, part_index, task_type, cefr_target, prompt, part_scores: { overall, criteria, observed }, done: bool, next_part: PartInfo | null }`
- `POST /api/academy/speaking/assessment/finish`
  body `{ session_id: int }`
  → `{ session_id, level: string|null, numeric: number|null, score: number|null, confidence: number, attempts: number, criteria: Criterion[], weak: string[], recommendation: string, assessment_version: string, rubric_version: string }`
- `GET /api/academy/speaking/assessment/{session_id}`
  → `{ session_id, status, assessment_version, total_parts, next_part_index, final_result: Result|null }`

`PartInfo` = `{ id, part_index, title, task_type, cefr_target, duration_target, prompt, difficulty }`.
`Criterion` (mismo shape que `SpeakingCriterionProgress` ya tipado) = `{ criterion, attempts, mean|null, min|null, max|null, review_due, recent_score?, lifetime_score?, confidence?, stability? }`.

Patrón de UI a imitar:
- Grabación de micrófono + transcripción: `frontend/src/components/PronunciationPractice.tsx`
  (`getUserMedia` + `MediaRecorder` + `api/voz.ts::transcribe(blob)`). Para `duration_seconds`
  (que `transcribe` NO devuelve) mide con `performance.now()` entre el inicio y el fin de la
  grabación y envía `(stopTime - startTime) / 1000`.
- Helpers de speaking ya existentes en `frontend/src/utils/speaking.ts`: `criterionLabel`,
  `formatConfidence`, `formatTrendDelta`, `nextFocus`, `numericToCefr`. En `utils/cefr.ts`:
  `cefrTone`.
- Los tipos de speaking ya existen en `frontend/src/types/api.ts` (`SpeakingCriterionProgress`,
  `SpeakingLevelOut`, `SpeakingJourneyOut`, `SpeakingDiagnostic`). Faltan los del assessment.
- Los paneles se montan en el `aside` de insights de `frontend/src/App.tsx` (ver
  `SpeakingPanel`, `SpeakingJourney`, `SpeakingDiagnostic`, `ListeningPractice`). Los paneles
  reciben `userId={currentUserId}` y, cuando corresponde, `onAttempt={onAttempt}` para refrescar
  el resto del dashboard tras un intento.
- Estilos en `frontend/src/index.css` con tokens (`.speaking-panel`, `.pronunciation`,
  `.listening`, `.cefr-badge`, etc.). Tema claro/oscuro y responsive (premisa 14).

## Objetivo
Crear un componente `SpeakingAssessment.tsx` que permita al alumno completar las 4 partes del
Speaking Assessment de punta a punta y ver su resultado, usando solo los endpoints ya existentes.

## Tarea

### 1. Tipos (`frontend/src/types/api.ts`)
Añade (espejo exacto de los schemas backend):
- `SpeakingAssessmentPartInfo`
- `SpeakingAssessmentPartScores { overall: number; criteria: Record<string, number | null>; observed: Record<string, boolean> }`
- `SpeakingAssessmentStart { session_id: number; assessment_version: string; total_parts: number; part: SpeakingAssessmentPartInfo | null }`
- `SpeakingAssessmentPart { session_id: number; part_index: number; task_type: string; cefr_target: string; prompt: string; part_scores: SpeakingAssessmentPartScores; done: boolean; next_part: SpeakingAssessmentPartInfo | null }`
- `SpeakingAssessmentResult { session_id: number; level: string | null; numeric: number | null; score: number | null; confidence: number; attempts: number; criteria: SpeakingCriterionProgress[]; weak: string[]; recommendation: string; assessment_version: string; rubric_version: string }`
- `SpeakingAssessmentState { session_id: number; status: string; assessment_version: string; total_parts: number; next_part_index: number; final_result: SpeakingAssessmentResult | null }`

### 2. API (`frontend/src/api/academy.ts`)
Añade las funciones tipadas (usa `postJson`/`getJson` y `userQuery` ya definidos):
- `startSpeakingAssessment(userId): Promise<SpeakingAssessmentStart>`
- `submitSpeakingAssessmentPart(userId, sessionId, heard, durationSeconds?): Promise<SpeakingAssessmentPart>`
- `finishSpeakingAssessment(userId, sessionId): Promise<SpeakingAssessmentResult>`
- `getSpeakingAssessment(userId, sessionId): Promise<SpeakingAssessmentState>`

### 3. Componente `frontend/src/components/SpeakingAssessment.tsx`
Props `{ userId: string | null; onAttempt: () => void }`. Estados del flujo:
`idle → part → result`, con estado de carga y de error (alert o aviso inline accesible). Detalle:

- **Idle**: botón principal "Iniciar Speaking Assessment" (deshabilitado si `!userId`). Al pulsar
  llama `startSpeakingAssessment` y guarda `sessionId`, `totalParts` y la primera `part`.
- **Part**: muestra `part.title`, `part.prompt`, badge de `cefr_target` (con `cefrTone`), progreso
  "Parte X de N" y `duration_target` (segundos sugeridos). Ofrece DOS vías de respuesta:
  1. **Micrófono** (patrón de `PronunciationPractice`): grabar → detener → `transcribe(blob)` →
     enviar `heard` + `duration_seconds` medido con `performance.now()`.
  2. **Entrada manual**: un `<textarea>` para escribir la respuesta hablada y un botón "Enviar"
     (sin `duration_seconds`), de modo que el flujo funcione aunque no haya micrófono.
  Tras enviar, muestra el score de la parte (`part_scores.overall` como % y, opcionalmente, el
  desglose de criterios observados con `criterionLabel`). Si `done === false`, muestra "Siguiente
  parte"; si `done === true`, muestra "Ver resultado".
- **Result**: al terminar la última parte, llama `finishSpeakingAssessment` (o, si `done` ya era
  true, usa `next_part` para saber que acabó) y muestra: nivel CEFR (`cefr-badge` + `cefrTone`),
  `score` como %, `formatConfidence(confidence)`, lista de criterios (`criterionLabel` + % + marca
  ⚠/✓ reutilizando la lógica de `SpeakingPanel`), y `recommendation`. Llama `onAttempt()` al
  finalizar para refrescar los paneles de speaking del dashboard.
- El botón de micrófono debe reflejar estados `recording`/`processing` con `aria-*` y
  `disabled` correcto (ver `PronunciationPractice`).

### 4. Montaje (`frontend/src/App.tsx`)
Monta `<SpeakingAssessment userId={currentUserId} onAttempt={onAttempt} />` en el `aside` de
insights, junto a `SpeakingPanel`/`SpeakingJourney` (después de ellos es un buen sitio).

### 5. Estilos (`frontend/src/index.css`)
Añade clases `.speaking-assessment*` coherentes con los tokens y con el estilo de los paneles
existentes (tema claro/oscuro, responsive ≤1024/768px, estados vacío/carga/error, `:focus-visible`).

### 6. Tests (frontend, vitest)
- `frontend/src/api/academy.test.ts`: añade tests de las 4 funciones nuevas (mock de fetch,
  verifica URL, método y body).
- Si introduces algún helper puro nuevo (p. ej. formateo de progreso o de `duration_target`),
  ponlo en `utils/speaking.ts` y testéalo en `utils/speaking.test.ts` (si no existe, créalo).

## Criterios de aceptación
- `npx tsc --noEmit` sin errores y `npx vitest run` (o `npm test`) en verde en `frontend/`.
- No se modifica ningún archivo del backend.
- El flujo funciona de punta a punta con los endpoints existentes (start → 4×part → finish) y es
  usable sin micrófono (entrada manual).
- UI responsive y con estados de carga/error/vacío; docstrings/JSdoc en todo lo nuevo (premisa 18).

## Restricciones
- Solo frontend. No cambies contratos del backend ni su versión.
- No rompas tests existentes. No introduzcas dependencias nuevas.
- Tests rápidos y deterministas (sin red, mock de fetch).
- Sigue el estilo visual de los paneles existentes (tokens, tema claro/oscuro).

## Salida
- Diff frontend (tipos, api, componente, App.tsx, index.css, tests) + salida de
  `npx tsc --noEmit` y `npx vitest run` en verde. Crea **un único commit `feat:`** con mensaje
  descriptivo (no hagas push).

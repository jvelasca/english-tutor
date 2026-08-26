# V1.21 — Turn-taking real del chat → parte "Interaction" del Speaking Assessment

## Rol
Subagente **frontend** que cierra el pendiente (opcional) de V1.17: integrar el
**turn-taking real del chat** en la parte **Interaction** del Speaking Assessment. El
puente backend ya existe (`conversation_id` → `interaction_objective`); falta la pieza
frontend que captura la **señal objetiva en vivo** (no un `conversation_id` manual) y la
envía al enviar la parte.

**No se toca el backend.** Toda la lógica de scoring ya está cableada (V1.17 §30.2).

## Contexto (contratos exactos, NO romper)

### Backend — ya hecho (verificar, no modificar)
- `backend/repositories/conversations.py::get_turns(cid, user_id)` → lista de turnos
  `{role, duration_ms, latency_ms, created_at}` (role `user`→`student`).
- `backend/services/interaction.py::interaction_evidence(turns)` → sub-dimensiones
  objetivas `{turn_balance, turn_completion, avg_response_latency_ms, student_turns,
  assistant_turns, interruptions}`.
- `backend/domain/academy.py::_inject_interaction_objective(evidence, conversation_id,
  user_id)` → si `conversation_id` presente y hay `turn_balance`/`turn_completion`,
  asigna `evidence["interaction_objective"]`. Se llama en `submit_speaking_assessment_part`
  (y `submit_speaking_task`).
- `backend/routers/academy.py::objective_speaking_assessment_part` recibe
  `SpeakingAssessmentPartSubmit` con campo `conversation_id: str | None = None`.
- `backend/routers/chat.py::chat_stream_endpoint`: persiste la telemetría del turno del
  **asistente** (`duration_ms`/`latency_ms`) vía `save_message` cuando `conversation_id`
  y `message_id` vienen en `/api/chat/stream`.
- `backend/schemas/chat.py`: `ChatRequest` ya tiene `conversation_id`/`message_id`.
- La telemetría del turno del **alumno** la captura el frontend y se persiste con
  `save_conversation` (columnas `duration_ms`/`latency_ms` de `messages`).

### Frontend — estado actual
- `frontend/src/api/academy.ts::submitSpeakingAssessmentPart(userId, sessionId, heard,
  durationSeconds?)` — NO envía `conversation_id`.
- `frontend/src/api/chat.ts::streamChat(messages, model, mode, callbacks, userId?,
  objectiveId?, conversationId?, messageId?)` — ya soporta `conversationId`/`messageId`.
- `frontend/src/api/conversations.ts`: `createConversation`, `saveConversation`,
  `getConversation`, `listConversations`.
- `frontend/src/utils/telemetry.ts::turnTelemetry({sentAt, composeStartedAt,
  lastAssistantAt})` → `{duration_ms, latency_ms}` (puro, ya testeado).
- `frontend/src/hooks/useChat.ts::sendText` — patrón de referencia: captura telemetría del
  turno del alumno, llama `streamChat` con `conversationId`/`messageId` y persiste con
  `saveConversation`.
- `frontend/src/components/SpeakingAssessment.tsx` — flujo `idle → part → result`; para
  cada parte usa micrófono (`getUserMedia`+`MediaRecorder`+`transcribe`) o `<textarea>`
  manual. NO distingue las partes conversacionales.
- `frontend/src/types/api.ts`: `SpeakingAssessmentPartInfo` tiene `task_type`;
  `Message` tiene `id?`, `role`, `content`, `mode?`, `duration_ms?`, `latency_ms?`.
- `frontend/src/utils/speaking.ts`: helpers de formato (`criterionLabel`,
  `formatScorePct`, …) ya testeado en `utils/speaking.test.ts`.

## Objetivo
1. Añadir un helper puro `isConversationalTaskType(taskType)` que detecte las partes de
   interacción (`role_play`, `conversation`, `discussion`, `interview`), espejo del
   `CONVERSATIONAL_TASK_TYPES` del backend.
2. Extender `submitSpeakingAssessmentPart` para enviar `conversation_id` opcional.
3. En `SpeakingAssessment`, para las partes conversacionales, sustituir mic/textarea por
   un **chat de role-play en vivo** (`SpeakingRolePlay`) que crea una conversación real,
   captura la telemetría de turnos del alumno y persiste la conversación.
4. Al terminar el role-play, enviar la parte con `heard` (turnos del alumno unidos),
   `duration_seconds` (duración total) y `conversation_id` (para que el backend inyecte
   `interaction_objective`).

## Tarea

### 1. Frontend — `utils/speaking.ts`
Añade (puro, con JSDoc):
- `CONVERSATIONAL_TASK_TYPES: ReadonlyArray<string> = ["role_play", "conversation",
  "discussion", "interview"]`.
- `isConversationalTaskType(taskType: string): boolean`.
- `rolePlaySetup(scenario: string): string`: mensaje semilla para el tutor (texto en
  inglés que le pide adoptar el otro papel del escenario y mantenerse en personaje).
  Ej.: `Role-play. You are the other speaker in this scenario and must stay in character.
  ${scenario} Start the conversation.`

### 2. Frontend — `api/academy.ts`
- `submitSpeakingAssessmentPart(userId, sessionId, heard, durationSeconds?, conversationId?)`:
  incluye `body.conversation_id = conversationId` solo si está definido (no vacío).

### 3. Frontend — `components/SpeakingRolePlay.tsx` (nuevo)
Componente autocontenido de role-play. Props: `{ userId: string; scenario: string;
onFinish(heard: string, durationSeconds: number, conversationId: string): void }`.
- `DEFAULT_MODEL = "qwen3.5:9b"` y `ROLEPLAY_MODE: TutorMode = "conversation"` locales.
- Al montar: `createConversation(userId)` → guarda `conversationId`; `startedAt` =
  `performance.now()`.
- Telemetría del turno del alumno con `turnTelemetry` (refs `composeStartedAt`,
  `lastAssistantAt`), espejo de `useChat.sendText`.
- `send()`: construye el mensaje del alumno con `duration_ms`/`latency_ms`, llama
  `streamChat` con `messages = [rolePlaySetup(scenario) como rol "user", ...historial real]`,
  `model`, `mode`, `conversationId`, `messageId` (id del asistente). Al terminar, persiste
  con `saveConversation(conversationId, userId, deriveTitle(historial), historial)`.
  Acumula el contenido de cada turno del alumno en `studentTurns`.
- `finish()`: `onFinish(studentTurns.join(" ").trim().slice(0, 2000),
  (performance.now() - startedAt) / 1000, conversationId)`.
- UI mínima y accesible: lista de burbujas (`role` user/assistant), input + botón Enviar
  (Enter envía), botón "Terminar interacción" deshabilitado si no hay turnos del alumno o
  `loading`. La semilla de escenario se muestra como texto de ayuda encima del chat (no
  como turno).
- El mensaje semilla (`rolePlaySetup`) NO se muestra ni se persiste (solo se envía al LLM
  como primer mensaje para que el tutor adopte el papel).

### 4. Frontend — `components/SpeakingAssessment.tsx`
- `submitResponse(heard, durationSeconds?, conversationId?)` pasa `conversationId` a
  `submitSpeakingAssessmentPart`.
- En la rama `!submitted`, si `part && isConversationalTaskType(part.task_type)`, renderiza
  `<SpeakingRolePlay key={part.id} userId={userId} scenario={part.prompt}
  onFinish={(h, d, cid) => submitResponse(h, d, cid)} />` en lugar de mic/textarea.
  El `key={part.id}` remonta el chat por parte (una conversación nueva por parte).
- Las partes no conversacionales conservan el flujo actual (mic + textarea) sin cambios.

### 5. Frontend — `index.css`
Clases `.speaking-roleplay*` (mensajes, burbujas user/assistant, composer, botón
terminar) coherentes con tokens/tema (premisa 14). Reutiliza patrones existentes de
`.speaking-assessment*` y del chat principal.

### 6. Tests (vitest)
- `frontend/src/utils/speaking.test.ts`: `isConversationalTaskType` (true para
  `role_play`/`conversation`/`discussion`/`interview`, false para `monologue`/`read_aloud`/
  `story`) y `rolePlaySetup` (contiene el escenario).
- `frontend/src/api/academy.test.ts`: `submitSpeakingAssessmentPart` incluye
  `conversation_id` en el body cuando se pasa, y lo omite cuando no (mantén los tests
  existentes de duration en verde).

## Criterios de aceptación
- Backend: `pytest` (sin cambios) + `ruff` limpios. Frontend: `npx tsc --noEmit` +
  `npx vitest run` en verde.
- La parte Interaction (task_type conversacional) usa chat de role-play en vivo; envía
  `conversation_id` junto con `heard` y `duration_seconds`.
- No se rompen los flujos de partes no conversacionales (mic + textarea).
- No se toca backend ni scoring. Sin dependencias nuevas.
- Todo nuevo con JSDoc (premisa 18).

## Restricciones
- No modificar backend: el puente `conversation_id` → `interaction_objective` ya existe.
- No inventar señal: el turno del alumno sin `composeStartedAt`/`lastAssistantAt` queda con
  `duration_ms`/`latency_ms` `null` (y el backend no la observa).
- Un único commit `feat:` descriptivo (no hagas push). No incluir el briefing en el commit.

## Salida
- Diff frontend y salida de tsc + vitest en verde (y pytest/ruff backend confirmando que
  nada se rompió).

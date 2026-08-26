# V1.17 (2/3) — Puente conversación→speaking (telemetría objetiva de interacción)

## Rol
Subagente **full-stack** que cierra el puente entre la telemetría objetiva de interacción
(ya implementada y commiteada en V1.16) y la evaluación de speaking. Hoy la señal objetiva
existe pero **nadie la alimenta ni la consume de extremo a extremo**:

- El backend `POST /api/chat/stream` **sí** mide TTFB/duración del turno del *asistente* y la
  persiste, pero solo si el request trae `conversation_id`/`message_id`… y el frontend **no los
  envía** (no-op hoy).
- El turno del **alumno** (`duration_ms`/`latency_ms`) no se captura en ningún sitio.
- El scorer de speaking sabe fusionar `evidence["interaction_objective"]` (ver
  `_interaction_score` en `backend/services/speaking.py`), pero ningún flujo lo inyecta.

Este incremento **captura** la telemetría de extremo a extremo y **cablea** su consumo en el
scorer de speaking vía un `conversation_id` opcional.

## Contexto (contratos exactos, NO romper)

### Backend ya existente (commiteado)
- `backend/services/interaction.py` → `interaction_evidence(turns) -> dict` con
  `turn_balance`, `avg_response_latency_ms`, `turn_completion`, `student_turns`,
  `assistant_turns`, `interruptions`. Turno = `{role ("student"/"assistant"),
  duration_ms: int|None, latency_ms: int|None, created_at}`.
- `backend/repositories/conversations.py` → `get_turns(cid, user_id)` (devuelve los turnos
  normalizados a `student`/`assistant`) y `save_message(..., duration_ms, latency_ms)`.
  La tabla `messages` ya tiene columnas `duration_ms` y `latency_ms` (migración idempotente hecha).
- `backend/routers/chat.py` → `POST /api/chat/stream` mide `latency_ms` (TTFB) y `duration_ms`
  del asistente y llama `conversation_service.save_message(...)` **si** `req.conversation_id`
  y `req.message_id` vienen.
- `backend/schemas/chat.py` → `ChatMessage(role, content, mode, id)`; `ChatRequest` ya tiene
  `conversation_id: str | None` y `message_id: str | None`.
- `backend/domain/conversations.py` → `get_turns(cid, user_id)` async (run_in_threadpool).
- `backend/services/speaking.py` → `scores_from_evidence(evidence, heard, duration_seconds,
  task_type, expected)`. `_interaction_score(evidence)` fusiona `evidence["interaction_objective"]`
  (objetivo) con la señal semántica del LLM (`INTERACTION_OBJECTIVE_WEIGHT=0.5`). La clave es
  backward-compatible: sin `interaction_objective`, todo sigue igual que hoy.
- `backend/domain/academy.py`:
  - `submit_speaking_assessment_part(user_id, session_id, heard, duration_seconds, model)` llama
    `speaking_llm.extract_speaking_evidence(...)` → `speaking_svc.scores_from_evidence(...)`.
  - `submit_speaking_task(user_id, level_id, objective_id, task, heard, model, duration_seconds,
    task_type, difficulty, difficulty_vector, expected)` → `scores_from_evidence(...)`.
- `backend/schemas/academy.py` → `SpeakingAssessmentPartSubmit(session_id, heard,
  duration_seconds, model)`; `SpeakingTaskSubmitRequest` (buscar el nombre exacto del schema
  JSON de la tarea de speaking si existe; si solo existe el endpoint multipart audio, NO lo
  toques y aplica el puente solo al assessment part + `submit_speaking_task`).

### Frontend ya existente
- `frontend/src/hooks/useChat.ts` → `sendText` crea el turno del alumno, llama
  `streamChat(history, model, mode, callbacks, currentUserId, activeObjective?.id)` y luego
  `persist(cid, ...)`. **No** captura telemetría ni pasa `conversation_id`/`message_id`.
- `frontend/src/api/chat.ts` → `streamChat(messages, model, mode, callbacks, userId, objectiveId)`
  construye el body `{model, messages, mode, objective_id?}`. **No** envía `conversation_id`
  ni `message_id`.
- `frontend/src/api/conversations.ts` → `saveConversation(id, userId, title, messages)` (el
  `persist` de useChat). `save_conversation` del repo ya propaga `duration_ms`/`latency_ms`
  desde cada mensaje (`m.get("duration_ms")`), así que basta con que `Message` los lleve.
- `frontend/src/types/api.ts` → `Message { id?, role, content, mode? }`.

## Objetivo
1. **Backend**: admitir `duration_ms`/`latency_ms` en el `ChatMessage` persistido y añadir
   `conversation_id` opcional al flujo de scoring de speaking para inyectar
   `interaction_objective`.
2. **Frontend**: capturar la telemetría del turno del alumno y enviar `conversation_id`/
   `message_id` en `/api/chat/stream`, de modo que ambos turnos queden con telemetría.

## Tarea

### 1. Backend — `schemas/chat.py`
Añade a `ChatMessage`:
- `duration_ms: int | None = None`
- `latency_ms: int | None = None`

(Este schema se usa en `ConversationUpsert.messages`, de modo que `save_conversation` ya podrá
persistir la telemetría del turno del alumno que el frontend envíe.)

### 2. Backend — inyección de `interaction_objective` (domain/academy.py)
Añade un parámetro opcional `conversation_id: str | None = None` a:
- `submit_speaking_assessment_part(...)`
- `submit_speaking_task(...)`

En ambos, justo **después** de obtener `evidence` y **antes** de `scores_from_evidence`, si
`conversation_id` está presente:
1. `turns = await run_in_threadpool(conversations_repo.get_turns, conversation_id, user_id)`
2. Si `turns` no es `None` y `interaction_evidence(turns)` tiene al menos una sub-dimensión
   observable (`turn_balance` o `turn_completion` no `None`), asigna
   `evidence["interaction_objective"] = interaction_evidence(turns)`.

Importa `from repositories import conversations as conversations_repo` y
`from services import interaction` (o `from services.interaction import interaction_evidence`).
No hagas I/O síncrono directo: usa `run_in_threadpool` como el resto del dominio.

### 3. Backend — schemas y router de academy
- `schemas/academy.py`: añade `conversation_id: str | None = None` a
  `SpeakingAssessmentPartSubmit`. Si existe un schema JSON para la tarea de speaking
  (`SpeakingTaskSubmitRequest` o similar), añádele también `conversation_id: str | None = None`.
- `routers/academy.py`: propaga `body.conversation_id` en las llamadas correspondientes
  (`speaking_assessment_part` y, si aplica, el endpoint JSON de speaking task).
- **No** cambies el endpoint multipart de audio (`objective/speaking/task/audio`) salvo que
  quieras añadir `conversation_id` como `Form(...)` opcional; es opcional y no bloqueante.

### 4. Frontend — `types/api.ts`
Añade a `Message`: `duration_ms?: number;` y `latency_ms?: number;`.

### 5. Frontend — util pura `utils/telemetry.ts` (nuevo)
Crea una función pura y testeable:
- `turnTelemetry(input: { sentAt: number; composeStartedAt: number | null; lastAssistantAt: number | null }): { duration_ms: number | null; latency_ms: number | null }`
  - `duration_ms` = `sentAt - composeStartedAt` redondeado a entero, o `null` si no hay `composeStartedAt`.
  - `latency_ms` = (`composeStartedAt ?? sentAt`) `- lastAssistantAt` redondeado a entero, o `null` si no hay `lastAssistantAt`.
  - Clamp a >= 0 y rechaza `NaN`. Devuelve `null` si el resultado no es finito.
(Todos los timestamps en `performance.now()` ms.)

### 6. Frontend — `api/chat.ts`
Extiende `streamChat` con dos parámetros opcionales al final: `conversationId?: string | null`
y `messageId?: string | null`. Inclúyelos en el body solo si están presentes:
`...(conversationId ? { conversation_id: conversationId } : {})` y
`...(messageId ? { message_id: messageId } : {})`. Mantén la firma backward-compatible (los
argumentos nuevos van al final y son opcionales).

### 7. Frontend — `hooks/useChat.ts`
En `sendText`:
- Genera `assistantId` **antes** de `streamChat` (hoy se crea dentro; muévelo arriba).
- Mide con `performance.now()`:
  - `sentAt` al inicio del envío.
  - `lastAssistantAt` desde un `useRef<number | null>` que se actualiza cada vez que se completa
    una respuesta del asistente (en `onDone`, `onError` y el `finally`).
  - `composeStartedAt` desde un `useRef<number | null>` que se actualiza con un `useEffect` sobre
    `input`: cuando `input` pasa de vacío a no-vacío, `composeStartedAt.current = performance.now()`.
- Calcula `{duration_ms, latency_ms}` con `turnTelemetry(...)`.
- Añade `duration_ms` y `latency_ms` al mensaje del alumno dentro de `history`.
- Llama a `streamChat(..., currentUserId, activeObjective?.id, cid, assistantId)`.
- Tras el envío, resetea `composeStartedAt.current = null`.
- Al terminar el turno del asistente, `lastAssistantAt.current = performance.now()`.

Nota sobre idempotencia (ya garantizada por el repo): el backend persiste el turno del
asistente con `message_id = assistantId`; luego `persist` re-guarda la historia completa y el
repo usa `INSERT OR IGNORE` sobre `(conversation_id, message_id)`, así que no hay duplicados.

### 8. Tests

#### Backend (pytest)
- En `backend/tests/test_speaking.py`: añade un test que verifique que
  `scores_from_evidence(evidence, heard, duration_seconds, task_type="conversation")` **con**
  `evidence["interaction_objective"] = {"turn_balance": 0.8, "turn_completion": 0.6}` produce un
  criterio `interaction` observado (`observed["interaction"] is True`) y un valor fusionado
  (entre el semántico y el objetivo). Verifica también backward-compat: sin
  `interaction_objective` el resultado no cambia respecto al comportamiento actual.
- Si existe un patrón de test de dominio con BD en memoria para academy, añade un test de
  `submit_speaking_assessment_part`/`submit_speaking_task` con `conversation_id`; si no existe
  patrón, NO lo inventes (cúbrelo con los tests puros + suite verde).

#### Frontend (vitest)
- `frontend/src/utils/telemetry.test.ts`: casos con/sin `composeStartedAt`/`lastAssistantAt`,
  clamp a 0, y entradas `NaN`.
- Si `frontend/src/api/chat.test.ts` existe, añade un test de que `streamChat` incluye
  `conversation_id`/`message_id` en el body cuando se pasan y NO cuando no se pasan.

## Criterios de aceptación
- Backend: `pytest` (o `python -m pytest backend`) en verde + `ruff` limpio (si el proyecto lo
  usa). Frontend: `npx tsc --noEmit` + `npx vitest run` (o `npm test`) en verde.
- El scoring de speaking, con `conversation_id` presente, fusiona señal objetiva de turnos en el
  criterio `interaction`; sin `conversation_id` el comportamiento es idéntico al actual.
- La telemetría del turno del alumno y del asistente se persiste en `messages` y es visible vía
  `GET /api/conversations/{id}/interaction`.
- No se rompen tests existentes; no se introducen dependencias nuevas; todo nuevo con
  docstrings/JSdoc (premisa 18).

## Restricciones
- Mantén los contratos existentes backward-compatible (nuevos campos opcionales, nunca
  obligatorios).
- El LLM sigue siendo solo extractor de evidencia; todo el scoring determinista.
- No toques `backend/services/interaction.py` (ya está correcto y testeado); solo consúmelo.
- Crea **un único commit `feat:`** descriptivo (no hagas push).

## Salida
- Diff backend + frontend, y la salida de las suites (pytest/ruff, tsc, vitest) en verde.

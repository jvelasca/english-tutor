# Documento de relevo (handoff)

> **Propósito:** permitir que un agente/contexto **nuevo** retome el proyecto desde cero
> sin perder el hilo (premisa 8 y 12). Si el chat del gerente se satura o hay riesgo de
> alucinación, este documento es el ancla para reanudar.
> Actualizado por última vez: 2026-08-26 13:00 (UTC+2).

## 0. START HERE — para el gerente que retoma ahora

**Posición actual (2026-08-26):** `v1.18` **commiteada** (P1 de listening de la auditoría V1.14:
delayed retention + dictado/shadowing reales + escalera de variantes de velocidad). Cerradas
hasta ahora: Release Audit 1.1 (M12), M14–M16, Academy v2 + integridad curricular, hardening,
Evidence & Performance Engine, Listening 1.0/2.0/3.0, Placement 1.0/2.0, Etapa 2 (pedagogía)
**P1–P5**; **V1.12** (Student Model unificado + Assessment Loop), **V1.13** (Listening 3.0),
**V1.14** (Listening Evidence & Adaptive Selection), **V1.15** (Speaking 3.0), **V1.16** (Speaking
Assessment & Evidence 2.0), **V1.17** (Speaking Assessment UI + puente conversación→speaking +
Writing 3.0) y **V1.18** (P1 listening: retention + dictado/shadowing + variantes). Quedan
pendientes los P1 de listening que requieren **biblioteca de audio humano** (varios hablantes,
connected speech real, acentos reales, ruido real — P1.5–P1.8), el **P6** (pronunciación fonémica)
y (opcional) integrar el turn-taking real del chat en la parte "Interaction" del Speaking
Assessment.

**Últimos commits:**
- `feat: V1.18 P1.9 - escalera de variantes de velocidad en listening`
- `feat: V1.18 P1.3/P1.4 - dictado y shadowing reales en listening`
- `feat: V1.18 P1.2 - delayed retention en diagnostico de listening`
- `docs: V1.17 higiene de release + documentacion (1.17.0)`
- `feat: V1.17 - Writing 3.0 (diagnostico por criterio, nivel continuo y journey longitudinales)`
- `feat: puente conversacion -> speaking con telemetria objetiva de interaccion`
- `feat: add speaking assessment UI flow (start to 4 parts to result)`
- `docs: V1.16 higiene de release + documentacion (1.16.0)`
- `feat: V1.16 - Speaking panel y journey (frontend)`
- `feat: V1.15 S3 - panel de diagnostico de speaking`
- `feat: V1.15 S2 - Speaking 3.0 criterio interaction`
- `feat: V1.15 S1 - Speaking 3.0 diagnostico longitudinal`
- `feat: V1.14 - Listening Evidence & Adaptive Selection (AudioRealization + Evidence Integrity + selector adaptativo)`
- `feat: V1.13 - Listening 3.0 (audio TTS pre-renderizado + cierre A1-B2 + evidencia por sub-destreza)`
- `feat: V1.12 - Student Model unificado + Assessment Loop`
- `feat: V1.11 - CEFR basado en evidencia (muestras por destreza + confianza)`

**V1.15 commiteada** (S1 `2a182a8`, S2 `42602ca`, S3 `9be0f7f`) — Speaking 3.0. Ver sección 28.
Resumen:
- **Diagnóstico longitudinal** (`services/speaking.py::speaking_diagnostic`): agrupa la evidencia
  de speaking por criterio (attempts/mean/min/max/review_due), deriva `weak` + `recommendation` y
  expone `trend` global sobre las filas `overall` + `overall_mean`.
- **`interaction` como séptimo criterio** del rubric: extraído del LLM en el flujo libre, no
  observable en read-aloud.
- **Endpoint** `GET /api/academy/speaking/diagnostic` + puente de sub-destrezas de speaking en el
  Student Model (`_annotated_profile`).
- **Frontend**: `SpeakingDiagnostic.tsx` (desglose por criterio + tendencia + a revisar).
- **Higiene de release**: `config.py`/`package.json` → `1.15.0`; CHANGELOG con entrada 1.15.0.

**V1.16 commiteada** (`c9021e3` backend S1-S6 + assessment, `399ce52` interaction, `fbd91fc`
frontend, + `docs:` higiene 1.16.0) — Speaking Assessment & Evidence 2.0. Ver sección 29.
Resumen:
- **Scoring determinista S1–S6**: task_achievement continuo, GrammarEvidence 2.0, SpeakingTaskProfile
  (dificultad declared/realized/verified + pesos por task_type), LexicalEvidence 2.0 (MSTTR),
  FluencyEvidence 2.0 (WPM + smoothness/rhythm), InteractionEvidence 2.0 y diagnóstico por criterio
  como vista del Student Model (EMA/confidence/stability).
- **Speaking Assessment 1.0**: instrumento versionado (4 partes) + sesión trazable + endpoints
  `/api/academy/speaking/assessment/*`.
- **Interaction Evidence objetiva**: `services/interaction.py` + telemetría de turnos
  (`duration_ms`/`latency_ms`) + `GET /api/conversations/{id}/interaction`.
- **Speaking level + journey**: `GET /api/academy/speaking/level` y `/journey`.
- **Frontend**: `SpeakingPanel` (NEXT FOCUS + PRACTICE NOW) + `SpeakingJourney` (barra A2→B1→B2).
- **Higiene de release**: `config.py`/`package.json` → `1.16.0`; CHANGELOG con entrada 1.16.0.

**V1.17 commiteada** (`012ec01` UI, `e679300` puente, `34e32e6` Writing 3.0) — cierre de tres
incrementos naturales. Ver sección 30. Resumen:
- **UI del Speaking Assessment** (`components/SpeakingAssessment.tsx`): start → 4 partes →
  resultado, con micrófono y entrada manual (sin micrófono), sobre los endpoints ya existentes.
- **Puente conversación→speaking**: `duration_ms`/`latency_ms` en `ChatMessage`; captura de la
  telemetría del turno del alumno (`utils/telemetry.ts` + `useChat`) y envío de
  `conversation_id`/`message_id` en `/api/chat/stream`; `conversation_id` opcional en
  `submit_speaking_assessment_part`/`submit_speaking_task` inyecta
  `evidence["interaction_objective"]` (señal objetiva de turnos) en el scorer.
- **Writing 3.0**: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de speaking)
  + endpoints `/api/academy/writing/diagnostic|level|journey` + frontend `WritingPanel`/
  `WritingJourney`.
- **Higiene de release**: `config.py`/`package.json` → `1.17.0`; CHANGELOG con entrada 1.17.0.

**V1.18 commiteada** (`6071bca` retention, `2183849` dictado/shadowing, `26ae6c4` variantes) —
P1 de listening de la auditoría V1.14. Ver sección 31. Resumen:
- **Delayed retention (P1.2)**: `delayed_retention` (inmediata vs. retardada, buckets
  0-2/2-7/7-30/30+ días) integrado en `listening_diagnostic` (clave `retention`) + frontend.
- **Dictado y shadowing reales (P1.3/P1.4)**: sub-destrezas `dictation`/`shadowing` servidas como
  tareas de producción (escribir/grablar) con scoring determinista vía `phonetics.composite_score`;
  columnas `task_type`/`score`, `mean_score` en el diagnóstico y endpoints
  `/api/listening/dictation|shadowing`.
- **Escalera de variantes (P1.9)**: `slow`/`normal`/`fast` con cache por variante y botones en el
  frontend (solo velocidad; acento/ruido quedan como límite de contenido).
- **Higiene de release**: `config.py`/`package.json` → `1.18.0`; CHANGELOG con entrada 1.18.0.

**Estado verde:** backend `726 tests` + `ruff` limpio; frontend `198 tests` + `tsc` OK;
launcher `55 tests` + `ruff` limpio.

**Acciones del nuevo gerente (en orden):**
1. Leer `docs/PREMISAS.md` (fuente de verdad de reglas).
2. Leer la **sección 31** de este documento (V1.18 — commiteada) y su **lista de pendientes**
   (31.4).
3. Atacar los pendientes listados en 31.4: los P1 de listening que requieren **biblioteca de
   audio humano** (varios hablantes, connected speech real, acentos reales, ruido real — P1.5–P1.8),
   el **P6** (pronunciación fonémica) y (opcional) el turn-taking real del chat en la parte
   "Interaction" del Speaking Assessment.
4. Verificar en verde antes de cada commit `feat:` (backend `pytest` + `ruff`, frontend
   `tsc` + `vitest`, launcher `pytest` + `ruff`).

## 1. Qué es el proyecto

Profesor de inglés **100% local** (sin Internet, sin cuentas, sin costes). Conversa por
texto y voz con un LLM local (Ollama), con modos de tutor y corrección de pronunciación.

- **Fuente de verdad de reglas:** `docs/PREMISAS.md` (14 premisas). Léelas primero.
- **Arquitectura:** `docs/ARQUITECTURA.md` (estructura modular y responsabilidades).
- **Guía de desarrollo:** `docs/DESARROLLO.md` (arranque, flujo con subagentes, Git/GitHub).
- **Roadmap y estado:** `PLAN.md`.

## 2. Stack (fijado, premisa 3-4)

- Backend: Python + FastAPI + Pydantic (tipado fuerte).
- Frontend: Vite + React + TypeScript (modo estricto).
- LLM: Ollama (local). Modelo inicial `qwen3.5:9b`.
- Voz: `faster-whisper` (STT, CPU) y `piper-tts` (TTS, CPU).
- Persistencia: SQLite (`backend/data/tutor.db`).

## 3. Estado actual (qué funciona)

Hecho y verificado (tests verdes):

- **M0** esqueleto modular · **M1** streaming (SSE) · **M2** voz local · **M3** memoria/historial.
- **M4** modo profesor: 4 modos de tutor (`conversation`, `grammar`, `exercises`, `pronunciation`)
  + corrección de pronunciación (`POST /api/pronunciation`).
- **M5** modelo conversacional: evaluado `llama3.1:8b` vs `qwen3.5:9b`; se mantiene
  `qwen3.5:9b` (mejor calidad de tutor). `llama3.1:8b` queda instalado como alternativa.
- **M6** release a GitHub.
- **M7** multi-usuario: tabla `users` + columna `user_id` en `conversations` (migración
  idempotente, usuario por defecto `Usuario`), `GET/POST /api/users`, CRUD de conversaciones
  filtrado por `user_id`, selector de perfil en frontend con aislamiento al cambiar.
- **M8** diseño y UX: tokens en `index.css`, tema claro/oscuro (`useTheme`, `ThemeToggle`,
  anti-FOUC), responsive (drawer + hamburguesa ≤768px), a11y y micro-interacciones.
- **M9** seguimiento de progreso: `GET /api/progress?user_id=<id>` (`ProgressSummary`:
  conversaciones, mensajes, ejercicios, correcciones, pronunciación) + `POST /api/pronunciation`
  con `user_id` opcional para persistir intentos (`pronunciation_attempts` + columna `mode`).
  Frontend: panel colapsable `ProgressSummary` + `api/progress.ts`.
- **M10** voz continua / manos libres: modo conversación por voz sin pulsar botones. VAD en
  cliente (RMS + silencio ≥1.2s vía Web Audio API), bucle escuchar → transcribir → responder →
  leer en voz alta → volver a escuchar. Frontend: `useChat.sendText`, `utils/vad.ts`,
  `hooks/useHandsFree.ts`, `components/HandsFreeToggle.tsx`. Sin cambios de backend.
- Tests: backend `pytest tests/ -q` (27 tests), frontend `npm test` (vitest, 37 tests) + `tsc --noEmit`.

## 4. GitHub

- Repo **público**: https://github.com/jvelasca/english-tutor
- Rama por defecto: `main`. Última versión estable: tag `v1.5.2` (release publicado).
- Issues de seguimiento:
  - #1 M5 modelo conversacional
  - #2 Seguimiento de progreso del alumno
  - #3 Conversación por voz continua
  - #4 M7 multi-usuario
  - #5 M8 diseño y UX nivel top

## 5. HECHO — M5: modelo conversacional (se mantiene qwen3.5:9b)

**Tarea:** evaluar `llama3.1:8b` como reemplazo de `qwen3.5:9b` para el rol de tutor.

- Script: `backend/scripts/eval_model.py` (`--model <m>` envía 4 prompts de tutor).
- Briefing: `agentes/m5-modelo-conversacional.md`.
- **Descarga:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min. Al
  **quitar la VPN** (2026-08-24) la descarga terminó en ~1 min a 52 MB/s y sin error de
  certificado (el MITM de DigiMobil ya no afectaba a esa conexión). `llama3.1:8b` instalado.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. `qwen3.5:9b` gana en
  calidad como tutor (correcciones estructuradas, ejercicios con contexto, guía IPA de
  pronunciación detallada y correcta). `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde /θ/ con /ð/), así que **no es claramente
  mejor**. Queda instalado como alternativa selectable en el frontend.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

## 6. HECHO — M7: multi-usuario

**Implementado y verificado** (backend 20 tests, frontend 14 tests, `tsc` sin errores).

- Backend: `services/store.py` ahora gestiona `users` y `conversations` con `user_id`
  (migración idempotente; usuario por defecto `Usuario` y reasignación de huérfanas).
  `routers/users.py` (`GET/POST /api/users`), `routers/conversations.py` filtra por `user_id`
  (query param). `schemas/users.py` (`User`, `UserCreate`).
- Frontend: `api/users.ts`, `components/UserSelect.tsx`, `utils/users.ts` (`nextDefaultUserName`),
  hook `useChat.ts` con estado de usuario y aislamiento al cambiar de perfil.
- Briefings: `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

## 7. HECHO — M8: diseño y UX nivel top

**Implementado y verificado** (frontend 19 tests, `tsc` sin errores, `npm run build` OK).

- Tokens de diseño en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion), tema claro en `:root[data-theme="light"]`.
- Tema claro/oscuro: `hooks/useTheme.ts` + `utils/theme.ts` (`resolveInitialTheme`) +
  `components/ThemeToggle.tsx`; persistencia en `localStorage` y anti-FOUC en `index.html`.
- Responsive ≤768px: sidebar drawer + hamburguesa + backdrop. a11y: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Briefing: `agentes/m8-diseno-ux.md`.

## 7b. HECHO — M9: seguimiento de progreso del alumno

**Implementado y verificado** (backend 27 tests, frontend 26 tests, `tsc` sin errores,
`npm run build` OK).

- Backend: `schemas/progress.py` (`PronunciationStats`, `ProgressSummary`),
  `routers/progress.py` (`GET /api/progress?user_id=<id>` con 404 si no existe el usuario),
  `services/store.py` (tabla `pronunciation_attempts`, columna `mode` en `messages` con
  migración idempotente, `record_pronunciation`, `get_progress`), `routers/pronunciation.py`
  (`user_id: str = Form(None)` persistente), `ChatMessage.mode: str | None = None`.
- Frontend: `api/progress.ts`, `components/ProgressSummary.tsx` (panel colapsable con 4
  stats + sección de pronunciación y estados vacíos), `utils/progress.ts`
  (`formatScore`/`formatAverage`/`pronunciationLevelLabel`, tolerantes a `null`),
  `types/api.ts` (`PronunciationStats`/`ProgressSummary` con campos anulables),
  `hooks/useChat.ts` (estado `progress` + `refreshProgress`, `mode` adjuntado a los mensajes),
  `PronunciationPractice.tsx` (pasa `user_id` y refresca), `App.tsx` (renderiza el panel).
- Nota de tipado: los campos `best`/`average`/`last_score`/`last_level` son `null` si no hay
  intentos (reflejado en frontend como anulables).
- Briefings: `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

## 7c. HECHO — M10: conversación por voz continua (manos libres)

**Implementado y verificado** (frontend 37 tests, `tsc` sin errores, `npm run build` OK;
backend intacto, `import main` OK).

- **Sin cambios de backend:** reutiliza `POST /api/transcribe`, `POST /api/tts` y
  `POST /api/chat/stream` ya existentes.
- Frontend: `hooks/useChat.ts` extrae y exporta `sendText(text): Promise<string>` (el `send`
  actual se apoya en él). `utils/vad.ts` (`rms`, `shouldEndUtterance`, constantes
  `SILENCE_THRESHOLD=0.02`, `SILENCE_MS=1200`, `MIN_SPEECH_MS=300`, `MAX_CHUNK_MS=15000`).
  `hooks/useHandsFree.ts` (un `MediaStream` persistente, `AnalyserNode` para energía,
  `MediaRecorder` por chunk; estados `idle/listening/transcribing/thinking/speaking`).
  `components/HandsFreeToggle.tsx` (toggle accesible + indicador de estado con `role="status"`).
  `App.tsx` lo conecta en `header-controls`. Estilos en `index.css` (tokens, tema claro/oscuro).
- **VAD:** muestreo cada 50 ms con `getByteTimeDomainData`; si `rms > 0.02` marca habla; al
  llegar silencio ≥1.2 s tras habla (y duración ≥0.3 s para descartar clics) cierra el chunk;
  tope de seguridad 15 s. Sin barge-in (fuera de alcance en esta iteración).
- **Limitaciones conocidas:** autoplay (el `AudioContext`/mic se lanzan dentro del clic),
  umbral fijo (podría calibrarse), sin interrupción de la voz del asistente.
- Briefing: `agentes/m10-voz-continua.md`.

## 8. Notas de diseño de M7 (para no romper en M8)

- Contrato de la API (no cambiar sin coordinar frontend):
  - `GET /api/users` → `User[]`; `POST /api/users` con `{ name }` → `User`.
  - `GET /api/conversations?user_id=<id>` y `POST /api/conversations?user_id=<id>`.
  - `ConversationMeta` incluye `user_id`.
- El usuario por defecto se llama `Usuario`; el frontend genera nombres sin colisión con
  `nextDefaultUserName` (`Usuario`, `Usuario 2`, ...).

## 8. Cómo arrancar y verificar desde cero

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests/ -q

# Frontend
cd frontend
npm install
npm test            # vitest
npx tsc --noEmit    # tipos

# Arranque integrado: F5 en Cursor (configuración "English Tutor (F5)")
#   backend :8000 + frontend :5173
```

## 9. Reglas de oro para continuar (premisas clave)

- **Todo se descompone en subagentes autocontenidos** en `agentes/<nombre>.md` (premisa 5).
- **Antes de alucinar, reiniciar el contexto** apoyándose en `docs/` (premisa 12).
- **Documentación VITAL:** todo cambio actualiza `docs/`, `PLAN.md`, `README.md` (premisa 8).
- **Tests obligatorios:** ninguna feature se da por acabada sin sus tests (premisa 12).
- **Ritmo:** hito a hito, un cambio a la vez (premisa 6).

## 10. Fase de endurecimiento (FASES 1, 2 Y 3 CERRADAS — post v1.0.0)

**Motivo:** auditoría interna + externa. La app es un MVP/RC arquitectónico; NO rehacer, pero
sí endurecer antes de seguir con features. Hallazgo crítico: **el aislamiento multiusuario
(M7) no está realmente garantizado** — el CRUD de conversaciones por `cid` no comprueba el
propietario, y `/api/pronunciation` no valida el usuario. M7 no debe considerarse "terminado".

- Plan completo y secuencia de subagentes: `docs/PLAN-ENDURECIMIENTO.md`.
- Prioridades: P0 aislamiento · P1 robustez · P2 Learning Profile · P3 pronunciación real.
- Briefings en `agentes/endurecimiento/` (uno por subagente, autocontenidos).

### Estado de subagentes (FASE 1 · P0) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E1.1 Store ownership + routers | `agentes/endurecimiento/e1-01-store-ownership.md` | ✔ hecho |
| E1.2 Frontend propagar user_id | `agentes/endurecimiento/e1-02-frontend-userid.md` | ✔ hecho |
| E1.3 LocalUserContext + tests seguridad API | `agentes/endurecimiento/e1-03-context-security-tests.md` | ✔ hecho |
| E1.4 Contratos y límites | `agentes/endurecimiento/e1-04-contratos-limites.md` | ✔ hecho |
| E1.5 Límites de audio + sanitización de errores | `agentes/endurecimiento/e1-05-audio-errores.md` | ✔ hecho |

> **Fase 1 (P0) cerrada.** Aislamiento multiusuario extremo a extremo, `system` fuera del
> input externo, límites de payload (chat/messages/TTS/audio) y sanitización de errores.
> **Fase 2 (P1) cerrada** (store no bloqueante, health real, chat integrable, CI + deps + CORS).
> **Fase 3 (persistencia y dominio) cerrada** (mensajes append-only, capa de dominio, FKs reales).
> **Fase 4 (Learning Profile) cerrada** (ver sección 11).
> **Fase 5 (Tutor Policy + Context Builder) cerrada** (ver sección 12).
> Siguiente bloque: **FASE 6 (Progreso pedagógico real)** — ver
> `docs/PLAN-ENDURECIMIENTO.md`.

### HECHO — E1.1: aislamiento real en store y routers

- `services/store.py`: `get_conversation(cid, user_id)`, `save_conversation(cid, user_id, …)`,
  `delete_conversation(cid, user_id)` con `AND user_id = ?`; `record_pronunciation(...) -> bool`
  (valida usuario); índices `idx_conversations_user_id` y `idx_pronunciation_user_id`.
- `routers/conversations.py` y `routers/pronunciation.py`: exigen/validan `user_id`.
- Tests: `test_store_isolation.py` (5 tests nuevos); total backend **32 tests verdes**.
- **ATENCIÓN:** el contrato de la API cambió (GET/PUT/DELETE y pronunciación ahora exigen
  `user_id`). El frontend queda temporalmente roto para cargar/guardar/borrar conversaciones
  hasta cerrar E1.2 (siguiente subagente).

### HECHO — E1.2: frontend propaga user_id (cierra el par de contrato)

- `api/conversations.ts`: `getConversation(id, userId)`, `saveConversation(id, userId, …)`,
  `deleteConversation(id, userId)` con `user_id` en la query vía `URLSearchParams`.
- `api/pronunciation.ts`: `checkPronunciation(blob, expected, userId)` con `userId` obligatorio.
- `hooks/useChat.ts`: `loadConversation`/`removeConversation`/`persist` pasan `currentUserId`
  con guard `if (!currentUserId) return;` y deps actualizadas.
- `components/PronunciationPractice.tsx`: guard `!userId` + `disabled={processing || !userId}`.
- Test nuevo `api/conversations.test.ts` (3 tests, mock de fetch). Frontend: **40 tests verdes**,
  `tsc` sin errores, `npm run build` OK.
- **Contrato cerrado:** la app queda funcional de nuevo y con aislamiento extremo a extremo
  (backend exige `user_id`, frontend lo envía).

### HECHO — E1.3: LocalUserContext + tests canónicos de seguridad API

- `dependencies.py`: dependencia `current_user(user_id: str = Query(...))` que resuelve y
  valida el perfil activo (`store.get_user`), `404` si no existe.
- `routers/conversations.py` y `routers/progress.py`: `get_one`/`save`/`delete`/`progress`
  usan `Depends(current_user)` (DRY) en lugar de recibir `user_id` crudo.
- Tests: `tests/test_api_security.py` (aislamiento por API: no leer/actualizar/borrar la
  conversación de otro usuario, pronunciación con usuario desconocido → 404). Total backend
  **38 tests verdes**.

### HECHO — E1.4: contratos (quitar `system`) y límites de payload

- `schemas/chat.py`: `Role = Literal["user", "assistant"]` (fuera `system`); `content`
  con `max_length=MAX_CONTENT_CHARS`; `messages` con `max_length=MAX_CHAT_MESSAGES`.
- `schemas/voz.py`: `TTSRequest.text` con `max_length=MAX_TTS_CHARS`.
- `config.py`: constantes `MAX_CHAT_MESSAGES=100`, `MAX_CONTENT_CHARS=8000`, `MAX_TTS_CHARS=4000`.
- Tests: `tests/test_schemas.py` (rechaza `system`, rechaza content/messages/TTS fuera de
  límite). Total backend **43 tests verdes**.

### HECHO — E1.5: límites de subida de audio + sanitización de errores

- `config.py`: `MAX_AUDIO_BYTES = 25 * 1024 * 1024` (25 MB).
- `dependencies.py`: `read_audio_limited(file) -> bytes` (415 si el content-type no es audio,
  413 si excede `MAX_AUDIO_BYTES`, lectura por chunks de 1 MB).
- `routers/voz.py`: `/api/transcribe` usa `read_audio_limited`; errores de transcribir/TTS
  sanitizados (`logger.exception` + `500` genérico).
- `routers/pronunciation.py`: usa `read_audio_limited`; error de transcripción sanitizado.
- `routers/chat.py`: `/api/chat` → `502` "No se pudo completar la respuesta"; `/api/chat/stream`
  emite `{"error": "..."}` sin filtrar `exc`.
- `routers/models.py`: `/api/models` → `502` "No se pudo contactar con Ollama".
- Tests: `tests/test_robustness.py` (413, 415, models/chat no filtran `exc`). Total backend
  **47 tests verdes**.

### Estado de subagentes (FASE 2 · P1) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E2.1 Store no bloqueante (threadpool) | `agentes/endurecimiento/e2-01-store-no-bloqueante.md` | ✔ hecho |
| E2.2 Health real (live/ready/dependencies) | `agentes/endurecimiento/e2-02-health-real.md` | ✔ hecho |
| E2.3 Chat integrable + tests Ollama mockeado | `agentes/endurecimiento/e2-03-chat-integrable.md` | ✔ hecho |
| E2.4 CI + deps + CORS | `agentes/endurecimiento/e2-04-ci-deps-cors.md` | ✔ hecho |

### HECHO — E2.4: CI + dependencias reproducibles + CORS

- CORS: `config.py` `ALLOWED_ORIGINS` (solo `localhost:5173`/`127.0.0.1:5173`); `main.py` la usa
  (antes `["*"]`). Test `tests/test_cors.py` (3 tests).
- Deps: `requirements.in` (intención) + `requirements.txt` y `requirements-dev.txt` pineados
  (versiones exactas verificadas) + `ruff` en dev.
- Ruff determinista: `pyproject.toml` (`select E,F,W,I,B`, `ignore B008`, `line-length 88`).
  Se arreglaron issues preexistentes (F401/I001/E501/B904) con cambios mecánicos sin alterar
  comportamiento (reenvuelto de líneas y `raise ... from None`).
- CI: `.github/workflows/ci.yml` (backend: ruff + pytest; frontend: tsc + vitest + build).
- Total backend **62 tests verdes**; frontend **40 tests** + tsc + build OK; `ruff` limpio.

### HECHO — E2.3: chat integrable (DI del cliente Ollama) + tests

- `services/llm.py`: cliente Ollama inyectable (`_client`, `get_client()`, `set_client()`);
  `chat_once`, `chat_stream`, `list_models`, `ping` usan `get_client()` en vez de instanciar
  `ollama.AsyncClient()`. Firmas y comportamiento público sin cambios.
- Tests: `tests/test_chat_integration.py` (7 tests con `FakeOllamaClient`): system prompt +
  modo correcto, fallback a conversación con modo desconocido, stream OK, role inválido 422,
  mensajes vacíos 422, Ollama caído 502 sin fuga, error en stream → evento `error` sin fuga.
  Total backend **59 tests verdes**.

### HECHO — E2.2: health real (live / ready / dependencies)

- `services/store.py` (`ping()`), `services/llm.py` (`ping()` async), `services/stt.py`
  (`is_ready()`), `services/tts.py` (`is_ready()`): checks de cada dependencia.
- `routers/health.py` (nuevo): `/api/health` (compat), `/api/health/live`,
  `/api/health/dependencies` (estado por dependencia), `/api/health/ready` (200/503).
- `routers/models.py`: eliminado el `/api/health` estático. `main.py`: registra `health_router`.
- Tests: `tests/test_health.py` +4 (live, dependencies ok, ready 200, ready 503 con Ollama
  caído, todo con monkeypatch). Total backend **52 tests verdes**.

### HECHO — E2.1: store no bloqueante (threadpool)

- `services/store_async.py` (nuevo): 11 envolturas `async` que delegan en `store` vía
  `starlette.concurrency.run_in_threadpool` (referencias resueltas en runtime → compatible con
  `monkeypatch`). `store.py` síncrono queda **intacto**.
- `dependencies.py`: `current_user` pasa a corrutina (`await store_async.get_user`).
- `routers/users.py`, `conversations.py`, `progress.py`, `pronunciation.py`: usan `store_async`
  (`await`). Firmas y contratos (200/404) sin cambios; `create`/`list_all` conservan `user_id: str`.
- Tests: `tests/test_store_async.py` (delega igual que el store síncrono). Total backend
  **48 tests verdes**.

**Línea base (pre-fase):** backend `27 tests` verdes, `import main` OK. Entorno de este
workspace: Python 3.13.7 (global), dependencias de runtime ya instaladas
(`ollama`, `faster-whisper`, `piper-tts`, `python-multipart`).

### Estado de subagentes (FASE 3 · persistencia y dominio) — COMPLETA ✔

| Subagente | Briefing | Estado |
|---|---|---|
| E3.1 Mensajes append-only (backend) | `agentes/endurecimiento/e3-01-mensajes-append-only.md` | ✔ hecho |
| E3.2 Mensajes con id (frontend) | `agentes/endurecimiento/e3-02-mensajes-id-frontend.md` | ✔ hecho |
| E3.3 Capa de dominio (Service → Repository) | `agentes/endurecimiento/e3-03-capa-dominio.md` | ✔ hecho |
| E3.4 FK reales | `agentes/endurecimiento/e3-04-fk-reales.md` | ✔ hecho |

### HECHO — E3.1: mensajes append-only (backend)

- `schemas/chat.py`: `ChatMessage.id: str | None = None` (opcional, no rompe `/api/chat`).
- `repositories/db.py` (antes `services/store.py`): columna `message_id` + índice único
  `(conversation_id, message_id)`; `get_conversation` devuelve `id` (= `message_id`);
  `save_conversation` append-only (`INSERT OR IGNORE`) cuando todos los mensajes traen `id`,
  y fallback legacy (replace-all) si no.
- Test `tests/test_store_append_only.py` (3 tests). Total backend **65 tests verdes**.

### HECHO — E3.2: mensajes con id estable (frontend)

- `types/api.ts`: `Message.id?: string`.
- `hooks/useChat.ts`: `id` (`crypto.randomUUID()`) en mensaje de usuario y en el de asistente
  (un único `assistantId` por envío, reutilizado en `onDelta` y `persist`); las ramas de error
  usan su propio id. `App.tsx`: `key={m.id ?? ...}`.
- Frontend: **40 tests verdes**, `npm run build` OK. El backend ya recibe todos los mensajes
  con `id` → persistencia append-only activa.

### HECHO — E3.3: capa de dominio (Router → Service → Repository)

- **Refactor puro, sin cambio de comportamiento** (65 tests verdes).
- Nuevo `repositories/` (acceso a datos puro): `db.py` (conexión/esquema/migraciones/ping),
  `users.py`, `conversations.py`, `pronunciation.py`.
- Nuevo `domain/` (servicios async vía `run_in_threadpool`): `users.py`, `conversations.py`,
  `pronunciation.py`.
- Recableados `routers/{users,conversations,progress,pronunciation,health}.py`, `dependencies.py`
  y `main.py` para depender de `domain/` y `repositories.db`.
- Eliminados `services/store.py` y `services/store_async.py` (sustituidos).
- Tests re-apuntados (cambio mecánico de imports); `test_store_async.py` → `test_domain_async.py`.

### HECHO — E3.4: FKs reales (user_id → users.id)

- `repositories/db.py`: `_conn(foreign_keys=True)`; en `init_db` se añade una **fase 2** que
  reconstruye `conversations` y `pronunciation_attempts` (idempotente, con `foreign_keys OFF`)
  para añadir `FOREIGN KEY user_id → users(id)`. Sentencias `CREATE TABLE IF NOT EXISTS`
  intactas.
- Test `tests/test_foreign_keys.py` (6 tests: presencia de FK, enforcement con `IntegrityError`,
  idempotencia, migración desde esquema legacy). Total backend **71 tests verdes**.

**Estado global al cierre de Fase 3:** backend `71 tests` + `ruff` limpio + `import main` OK;
frontend `40 tests` + `tsc`/`build` OK. Arquitectura ahora `Router → Service (domain) →
Repository (repositories) → SQLite`, con mensajes append-only y FKs reales. Siguiente bloque:
**FASE 4 — Learning Profile** (CEFR, gramática, vocabulario, errores recurrentes, eventos).

## 11. FASE 4 — Learning Profile (CERRADA ✔)

Backend primero (F4.1–F4.4), frontend al final (F4.5). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear.

| Subagente | Briefing | Estado |
|---|---|---|
| F4.1 Eventos de aprendizaje | `agentes/endurecimiento/f4-01-eventos-aprendizaje.md` | ✔ hecho |
| F4.2 Vocabulario | `agentes/endurecimiento/f4-02-vocabulario.md` | ✔ hecho |
| F4.3 Errores gramaticales recurrentes | `agentes/endurecimiento/f4-03-gramatica.md` | ✔ hecho |
| F4.4 CEFR + recomendaciones | `agentes/endurecimiento/f4-04-cefr-perfil.md` | ✔ hecho |
| F4.5 Frontend Learning Profile | `agentes/endurecimiento/f4-05-frontend-perfil.md` | ✔ hecho |

### HECHO — F4.1: eventos de aprendizaje
- `schemas/learning.py` (`LearningEventType`, `LearningEvent`, `LearningEventCreate`),
  `repositories/learning.py` (`record_event`, `list_events`), `domain/learning.py`,
  `routers/learning.py` (`POST/GET /api/learning/events`).
- `repositories/db.py`: tabla `learning_events` con FK inline + índice. Total backend **79 tests**.

### HECHO — F4.2: vocabulario
- `services/vocabulary.py` (`EN_STOPWORDS`, `extract_words` puro), `repositories/vocabulary.py`
  (`record_words` upsert, `get_vocabulary`), `domain/vocabulary.py`, `schemas/vocabulary.py`,
  `routers/vocabulary.py` (`POST /api/vocabulary/analyze`, `GET /api/vocabulary`).
- `repositories/db.py`: tabla `vocabulary` (`UNIQUE(user_id, word)` + FK). Total **89 tests**.

### HECHO — F4.3: errores gramaticales recurrentes
- `services/grammar.py` (7 reglas regex deterministas + `find_errors`), `repositories/grammar.py`
  (`record_errors` upsert, `get_recurring_errors`), `domain/grammar.py`, `schemas/grammar.py`,
  `routers/grammar.py` (`POST /api/grammar/analyze`, `GET /api/grammar/errors`).
- `repositories/db.py`: tabla `grammar_errors` (`UNIQUE(user_id, rule)` + FK). Total **102 tests**.

### HECHO — F4.4: CEFR + recomendaciones
- `services/cefr.py` (`CEFR_LEVELS`, `estimate_cefr`, `recommendations` puras),
  `repositories/profile.py` (`get_profile`, `set_cefr`), `domain/profile.py` (compone
  vocabulario + errores + pronunciación + CEFR), `schemas/profile.py`, `routers/profile.py`
  (`GET /api/profile`).
- `repositories/db.py`: tabla `learning_profile` (PK `user_id` + FK). Total **114 tests**.
- Nota: se simplificó el plan (`GET /api/profile` recalcula la estimación en cada consulta;
  no se creó `POST /api/profile/assess` por ser redundante).

### HECHO — F4.5: frontend Learning Profile
- `types/api.ts` (`CefrLevel`, `GrammarRecurringError`, `LearningProfile`),
  `api/learning.ts` (`getProfile`, `analyzeText`), `utils/cefr.ts` (`cefrTone`, `cefrLabel`),
  `components/LearningProfile.tsx` (badge CEFR + vocabulario + errores + recomendaciones).
- `hooks/useChat.ts`: estado `profile` + `refreshProfile` (aislamiento al cambiar de usuario) y
  `analyzeText(trimmed, currentUserId)` tras cada envío del alumno. `App.tsx` renderiza el panel.
- `index.css`: sección `.learning-profile` con tokens + responsive. Total frontend **48 tests**.

**Estado global al cierre de Fase 4:** backend `114 tests` + `ruff` limpio + `import main` OK;
frontend `48 tests` + `tsc`/`build` OK. La tabla `learning_events` queda lista pero aún sin
consumidor de UI (se cableará en Fase 5/6). Siguiente bloque: **FASE 5 — Tutor Policy +
Context Builder** (el perfil del alumno entra al prompt del tutor).

## 12. FASE 5 — Tutor Policy + Context Builder (CERRADA ✔)

Backend primero (F5.1–F5.2), frontend al final (F5.3). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear.

| Subagente | Briefing | Estado |
|---|---|---|
| F5.1 Tutor Policy (correctness policy) | `agentes/endurecimiento/f5-01-politica-correccion.md` | ✔ hecho |
| F5.2 Context Builder + perfil al prompt | `agentes/endurecimiento/f5-02-context-builder.md` | ✔ hecho |
| F5.3 Frontend propagar user_id al chat | `agentes/endurecimiento/f5-03-frontend-user-id.md` | ✔ hecho |

### HECHO — F5.1: política de corrección (correctness policy)
- `services/policy.py` (`CORRECTNESS_GUIDANCE` por nivel CEFR + `correctness_guidance(cefr_level)`,
  pura y determinista, sin LLM). Tests `test_policy.py` (4). Total backend **118 tests**.

### HECHO — F5.2: Context Builder + perfil al prompt
- `services/context.py` (`build_system_prompt(mode, profile)`: prompt base + política por CEFR +
  errores recurrentes + áreas de enfoque).
- `schemas/chat.py`: `ChatRequest.user_id: str | None = None` (opcional → sin ventana rota).
- `services/llm.py`: `_messages`/`chat_once`/`chat_stream` aceptan `system_prompt` inyectable.
- `domain/profile.py`: extrae `_compute_profile` y añade `get_profile_context` (lectura sin
  persistir CEFR; `get_profile_summary` intacto y con mismo comportamiento).
- `routers/chat.py`: `_system_prompt(req)` resuelve el perfil vía `get_profile_context` y pasa el
  prompt a `chat_once`/`chat_stream`. Sin `user_id` (o usuario inexistente) → prompt base.
- Tests `test_context.py` (6) + `test_chat_profile.py` (4). Total backend **128 tests**.

### HECHO — F5.3: frontend propaga user_id al chat
- `api/chat.ts`: `sendChat`/`streamChat` envían `user_id` (`null` si no hay usuario).
- `hooks/useChat.ts`: `sendText` pasa `currentUserId` a `streamChat`.
- Test `api/chat.test.ts` (3). Total frontend **51 tests**.

**Estado global al cierre de Fase 5:** backend `128 tests` + `ruff` limpio + `import main` OK;
frontend `51 tests` + `tsc`/`build` OK. El perfil del alumno (CEFR + errores recurrentes +
recomendaciones) ya entra al system prompt del tutor; sin `user_id` el chat queda como antes.
Siguiente bloque: **FASE 6 — Progreso pedagógico real** (no solo counts).

## 13. FASE 6 — Progreso pedagógico real (CERRADA)

Backend primero (F6.1–F6.2), frontend al final (F6.3). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear. Decisiones de diseño: un único endpoint nuevo
(`GET /api/progress/history`), análisis **determinista sin LLM** (premisa 12), y el frontend
**reemplaza** `ProgressSummary` por un dashboard de progreso real (responsive móvil/tablet).

| Subagente | Briefing | Estado |
|---|---|---|
| F6.1 Registro automático de eventos | `agentes/endurecimiento/f6-01-registro-eventos.md` | ✔ hecho |
| F6.2 Progreso histórico (tendencias, racha, dominio, hitos) | `agentes/endurecimiento/f6-02-progreso-historico.md` | ✔ hecho |
| F6.3 Frontend dashboard de progreso | `agentes/endurecimiento/f6-03-frontend-dashboard.md` | ✔ hecho |

### HECHO — F6.1: registro automático de eventos de aprendizaje
- `domain/learning.py`: `_MODE_TO_EVENT` (`exercises→exercise`, `grammar→correction`, resto→
  `message`) + `record_chat_activity(user_id, mode, detail)` async.
- `routers/chat.py`: `_record_activity(req)` (solo si hay `user_id`; detail = último mensaje
  truncado a 200) llamada en `chat` y `chat_stream_endpoint` tras `_system_prompt`. Sin `user_id`
  o usuario inexistente → no registra y el chat sigue con prompt base (sin ventana rota).
- `routers/pronunciation.py`: registra evento `pronunciation` (detail = `expected`).
- `routers/conversations.py`: registra evento `conversation` (detail = `conv["id"]`).
- Tests: `tests/test_activity.py` (8 tests). Total backend **136 tests**.
- La tabla `learning_events` deja de estar dormida: ahora la alimentan los endpoints reales.
  La consumirán F6.2 (backend) y F6.3 (UI).

### HECHO — F6.2: progreso histórico real (tendencias, racha, dominio, hitos)
- Nuevo endpoint `GET /api/progress/history?user_id=<id>&bucket=day|week|month` (default `week`)
  con `ProgressHistory` = `series` + `streak` + `mastery` + `milestones`. Sin romper
  `/api/progress` ni `/api/profile`.
- `schemas/progress.py`: `Bucket`, `SeriesPoint`, `Streak`, `ErrorMastery`, `Milestone`,
  `ProgressHistory`.
- `services/trends.py` (puro): `daily_activity`, `active_days`, `aggregate_series` (day/week/
  month), `compute_streak` (racha actual + mejor).
- `services/mastery.py` (puro): `classify_errors` (activos vs resueltos por `last_seen`,
  umbral 14 días) y `compute_milestones` (catálogo de 10 hitos).
- `repositories/progress.py`: `activity_events` (mensajes con modo + pronunciaciones).
- `domain/progress.py`: `get_progress_history` compone repo + servicios puros.
- Tests: `test_trends.py` (7) + `test_mastery.py` (3) + `test_progress_history.py` (5).
  Total backend **151 tests**.

### HECHO — F6.3: frontend dashboard de progreso real
- `components/ProgressDashboard.tsx` reemplaza a `ProgressSummary.tsx` (eliminado): racha,
  gráfico de actividad (por día/semana/mes), dominio de errores (activos/resueltos), hitos y
  timeline de eventos recientes. **Responsive total**: tablet (`@media 1024px`) + móvil
  (`@media 768px`), según premisa 14.
- `api/progress.ts::getProgressHistory`, `api/learning.ts::getEvents`; tipos nuevos en
  `types/api.ts`; helpers `bucketLabel`/`eventLabel` en `utils/progress.ts`.
- `useChat` expone `history`/`events`/`bucket` y refresca tras cada envío y pronunciación.
- Tests: `api/progress.test.ts` (2) + `utils/progress.test.ts` (2) + `api/learning.test.ts` (1).
  Total frontend **56 tests**.

**Estado al cierre de Fase 6:** backend `151 tests` + `ruff` limpio; frontend `56 tests` +
`tsc`/`build` OK. El progreso dejó de ser "counts estáticos": ahora hay tendencias temporales,
racha, dominio de errores (activos vs resueltos) e hitos, deterministas y sin LLM.

## 14. FASE 7 — Pronunciación fonética (CERRADA)

Sustituir el evaluador único (`difflib` a nivel de caracteres) por un **evaluador compuesto
determinista** (sin LLM): precisión por palabra + similitud fonética (Soundex) + caracteres.
El breakdown viaja solo en la respuesta (sin migración). Decisiones: Soundex (sí), persistencia
solo en respuesta (sí).

### HECHO — F7.1: evaluador compuesto (backend)
- `services/phonetics.py` (puro): `tokenize`, `soundex` (variante simplificada, sin deps),
  `word_alignment` (correct/missing/extra/substituted + total), `word_accuracy`,
  `phonetic_similarity` (greedy por Soundex) y `composite_score`
  (pesos `word 0.6 / phonetic 0.3 / char 0.1`).
- `services/pronunciation.py::score_pronunciation` delega en `composite_score` y amplía el
  contrato: `score`, `level`, `ok`, `word_accuracy`, `phonetic_score`, `breakdown`. Umbrales
  `good ≥80` / `fair ≥50` intactos.
- `schemas/pronunciation.py`: `WordSubstitution`, `PronunciationBreakdown` y
  `PronunciationResponse` ampliado. `routers/pronunciation.py` sin cambios.
- Sin migración de `pronunciation_attempts` (sigue guardando `score`/`level` agregados).
- Tests: `test_phonetics.py` (12). Total backend **163 tests**.

### PENDIENTE — F7.2: frontend feedback fonético
`PronunciationPractice.tsx` mostrará el breakdown (palabras correctas/omitidas/sustituidas +
score fonético) vía `utils/pronunciationFeedback.ts` (puro) y tipos nuevos en `types/api.ts`.

### HECHO — F7.2: frontend feedback fonético
- `types/api.ts`: `WordSubstitution`, `PronunciationBreakdown` y `PronunciationResponse`
  ampliado (`word_accuracy`, `phonetic_score`, `breakdown`).
- `utils/pronunciationFeedback.ts` (puro): `joinWords`, `feedbackHints`, `wordsCorrectLabel`.
- `PronunciationPractice.tsx`: muestra precisión por palabra, similitud fonética, resumen de
  aciertos y avisos (omitidas/sustituidas/de más). Responsive con tokens.
- Tests: `utils/pronunciationFeedback.test.ts` (9). Total frontend **65 tests**.

**Estado al cierre de Fase 7:** backend `163 tests` + `ruff` limpio; frontend `65 tests` +
`tsc`/`build` OK. La pronunciación pasó de un único `difflib` a un evaluador compuesto
(precisión por palabra + Soundex + caracteres) con feedback por palabra, determinista y sin LLM.

## 15. FASE 8 — Listening / Speaking / CEFR (CERRADA)

Backend primero (F8.1–F8.3), frontend al final (F8.4). Un commit `feat:` por subagente, cada uno
verificado en verde antes de commitear. Decisiones: CEFR **multi-señal rico** (bandas por
destreza + descriptor); fluidez **con duración** (STT expone `info.duration`); **listening**
incluido ya (banco estático + TTS existente). Todo determinista, sin LLM.

| Subagente | Briefing | Estado |
|---|---|---|
| F8.1 CEFR multi-señal (backend) | `agentes/endurecimiento/f8-01-cefr-multisenial.md` | ✔ hecho |
| F8.2 Fluidez oral (backend) | `agentes/endurecimiento/f8-02-fluidez-oral.md` | ✔ hecho |
| F8.3 Listening (backend) | `agentes/endurecimiento/f8-03-listening.md` | ✔ hecho |
| F8.4 Frontend CEFR + fluidez + listening | `agentes/endurecimiento/f8-04-frontend.md` | ✔ hecho |

### HECHO — F8.1: evaluación CEFR multi-señal (backend)
- `services/cefr.py`: `evaluate_cefr` (punto-sum: vocab + pron + ejercicios + gramática +
  fluidez) + bandas `vocabulary_band`/`grammar_band`/`fluency_band`/`pronunciation_band` +
  `_LEVEL_DESCRIPTORS`/`level_descriptor`; `estimate_cefr` delega (compat v1). `recommendations`
  intacta.
- `schemas/profile.py`: `CefrBands` + `LearningProfile.cefr_bands`/`cefr_descriptor`.
- `domain/profile.py::_compute_profile` calcula `grammar_error_rate` + `messages` y usa
  `evaluate_cefr`.
- Tests: `test_cefr_evaluation.py` (9). Total backend **172 tests**.

### HECHO — F8.2: fluidez oral con duración (backend)
- `services/fluency.py` (puro): `compute_fluency` (WPM = palabras/min; `fluent ≥120`,
  `good 60–119`, `slow <60`, `—` sin audio válido).
- `services/stt.py`: `transcribe_with_timing` (devuelve `{text, duration}` con `info.duration`);
  `transcribe` delega (contrato de string intacto para `voz.py`).
- `schemas/pronunciation.py`: `FluencyStats` + `PronunciationResponse.fluency`.
- `routers/pronunciation.py`: usa `transcribe_with_timing` + `compute_fluency`.
- Se actualizaron 2 monkeypatch de tests existentes (`test_activity.py`, `test_api_security.py`)
  para devolver `{text, duration}`. Tests: `test_fluency.py` (6). Total backend **178 tests**.

### HECHO — F8.3: listening (banco + preguntas, backend)
- `services/listening.py` (puro): `QUESTION_BANK` (8 preguntas A1–B1, opción múltiple) +
  `get_question`/`pick_next_question`/`score_answer`.
- `schemas/listening.py`: `ListeningQuestion`, `ListeningAnswerRequest`, `ListeningAnswerResponse`,
  `ListeningStats`.
- `repositories/listening.py`: tabla `listening_attempts` + `record_attempt`/`seen_question_ids`/
  `get_stats`; `domain/listening.py`: `next_question`/`submit_answer`/`get_stats`.
- `routers/listening.py`: `GET /api/listening/question`, `POST /api/listening/answer`,
  `GET /api/listening/stats` (registra evento `exercise`). `db.py` (tabla+índice) y `main.py`
  (registro router) solo aditivos.
- Tests: `test_listening.py` (13). Total backend **191 tests**.

### HECHO — F8.4: frontend CEFR + speaking + listening
- `types/api.ts`: `FluencyStats`, `CefrBands`, `PronunciationResponse.fluency`,
  `LearningProfile.cefr_bands/cefr_descriptor`, tipos de listening.
- `utils/cefr.ts` (`bandLabel`), `utils/fluency.ts` (`wpmLabel`, `fluencyLevelLabel`),
  `api/listening.ts` (3 funciones).
- `LearningProfile.tsx`: descriptor CEFR + bandas por destreza. `PronunciationPractice.tsx`:
  línea de fluidez (nivel · WPM). `ListeningPractice.tsx` (nuevo): TTS + opciones + feedback +
  stats + "Siguiente". `App.tsx` lo monta; `index.css` con estilos responsive.
- Tests: `utils/fluency.test.ts` (4) + `utils/cefr.test.ts` (+2) + `api/listening.test.ts` (3).
  Total frontend **74 tests**.

**Estado al cierre de Fase 8:** backend `191 tests` + `ruff` limpio + `import main` OK;
frontend `74 tests` + `tsc`/`build` OK. CEFR dejó de ser una heurística plana: ahora hay
evaluación multi-señal con bandas por destreza y descriptor; la pronunciación añade fluidez
(WPM) con la duración del audio; y hay ejercicios de comprensión auditiva (banco + preguntas)
reproducidos con el TTS local.

## 16. FASE 9 — Evaluación objetiva del tutor (CERRADA)

Backend primero (F9.1–F9.2), frontend al final (F9.3). Un commit `feat:` por subagente, cada
uno verificado en verde antes de commitear. Evaluación determinista y sin LLM-juez (premisa 12).

| Subagente | Briefing | Estado |
|---|---|---|
| F9.1 Evaluador objetivo del tutor (backend) | `agentes/endurecimiento/f9-01-evaluador-tutor.md` | ✔ hecho |
| F9.2 Informe agregado + script por lotes (backend) | `agentes/endurecimiento/f9-02-informe-agregado.md` | ✔ hecho |
| F9.3 Panel de calidad del tutor (frontend) | `agentes/endurecimiento/f9-03-panel-calidad-tutor.md` | ✔ hecho |

### HECHO — F9.1: evaluador objetivo del tutor (backend, puro)
- `services/evaluation.py` (puro, sin LLM-juez): `SPANISH_WORDS`, `FRIENDLY_MARKERS`,
  `EVAL_CASES` (8 casos canónicos A1–B1), `normalize`, `_words`, `contains_fragment`,
  `contains_any_fragment`, `spanish_word_ratio`, `english_word_ratio`, `conciseness_score`,
  `engagement_score`, `evaluate_tutor_reply` (señales `correction`/`english`/`conciseness`/
  `engagement` + `total` ponderado) y `summarize` (medias por señal).
- Tests: `test_evaluation.py` (16). Total backend **207 tests**.

### HECHO — F9.2: informe agregado + script por lotes (backend)
- `services/evaluation.py`: `TUTOR_PROMPTS` + `build_tutor_prompt`, `build_report`
  (resumen + desglose por caso + `verdict`), `format_report` (texto legible).
- `scripts/eval_tutor.py` (CLI): `--model` + `--json`; envía `EVAL_CASES` al modelo, puntúa
  cada respuesta y emite el informe agregado. No persiste nada en BD.
- Tests: `test_evaluation_report.py` (10). Total backend **217 tests**.

### HECHO — F9.3: panel de calidad del tutor (frontend)
- `utils/tutorEvaluation.ts` (puro, espejo del evaluador): `normalize`, `words`,
  `spanishWordRatio`, `englishWordRatio`, `concisenessScore`, `engagementScore`,
  `evaluateTutorReply`, `averageEvaluations`.
- `components/TutorQualityPanel.tsx` (presentacional): medias de `Inglés`/`Concisión`/
  `Engagement`/`Total` + últimos 3 turnos del tutor. Responsive móvil/tablet. `App.tsx` lo
  monta tras `LearningProfile`; estilos `.tutor-quality` en `index.css`.
- Tests: `utils/tutorEvaluation.test.ts` (14). Total frontend **88 tests**.

**Estado al cierre de Fase 9:** backend `217 tests` + `ruff` limpio + `import main` OK;
frontend `88 tests` + `tsc`/`build` OK. El tutor ya se puede evaluar objetivamente (sin
LLM-juez): por corpus en backend (script por lotes) y en vivo en el frontend (panel de calidad
sobre la conversación actual).

## 17. FASE 10 — Release 1.0 estable + Launcher de escritorio (CERRADA)

Versión unificada `1.1.0`, gate verde completo y nuevo componente `launcher/`.

| Subagente | Briefing | Estado |
|---|---|---|
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |

### HECHO — Launcher de escritorio (`launcher/`)
- `core.py` (puro): rutas (`REPO_ROOT`, `BACKEND_DIR`, `FRONTEND_DIR`, `DB_PATH`), comandos
  (`backend_command`, `frontend_command`), URLs y normalización (`app_summary`,
  `health_status`, `db_summary`, `user_overview`).
- `process_manager.py`: `ProcessManager` (arranca/para backend `uvicorn` y frontend `npm run
  dev`; matado del árbol de procesos en Windows con `taskkill /T /F`; logs en `launcher/logs/`).
- `status.py`: `fetch_health`/`fetch_frontend` (HTTP) y `read_db_counts`/`read_users`
  (SQLite solo lectura).
- `launcher.py`: GUI `tkinter` (servicios, BD, usuarios; botones Iniciar/Detener/Abrir/
  Actualizar; refresco en hilo de fondo). No duplica servicios ya activos al iniciar.
- `make_icon.ps1` (genera `icon.ico`) y `install_shortcut.ps1` (crea `English Tutor.lnk`
  en el escritorio).
- Tests: `test_core.py` (13) + `test_status.py` (7) + `test_process_manager.py` (2) = **22 tests**.

### HECHO — Versión 1.1.0
- `backend/config.py::VERSION = "1.1.0"`; expuesta en `/api/health` y en `/`; `main.py`
  (`FastAPI(version=VERSION)`); `frontend/package.json` → `1.1.0`.
- Tests de versión en `test_health.py` (`test_root` y `test_health`).

**Estado al cierre de Fase 10:** backend `217 tests` + `ruff` limpio; frontend `88 tests` +
`tsc`/`build` OK; launcher `22 tests` + `ruff` limpio. Versión `1.1.0` unificada y lanzador
de escritorio con acceso directo e icono.

## 18. M14 — GUI responsive a ancho completo + personalización + acceso en red (HECHO)

Requisito del usuario: que la GUI sea más atractiva y **responsive** (adaptarse a tablets/móvil
y, en escritorio, **aprovechar todo el ancho** en vez de concentrar el contenido en una columna
central), con **zonas redimensionables** al gusto, **persistencia por usuario** de todos los
ajustes (incluido el modelo), aspecto **100% profesional**, **personalización visual del
perfil** (avatar/imagen/icono/color) y **acceso desde toda la red local** mostrando la URL de
acceso en la propia web y en el launcher.

### Layout multi-panel responsive y redimensionable
- `App.tsx`: la zona principal pasa de una columna centrada a un `workspace` flex con tres
  paneles: `pane--sidebar` (conversaciones), `pane--main` (chat) y `pane--insights`
  (dashboard de progreso + perfil + calidad del tutor + listening). El ancho se aprovecha al
  máximo en escritorio.
- `components/ResizeHandle.tsx`: asa de redimensionado horizontal (pointer events + teclado
  ←/→, `role="separator"`, `aria-*`) entre paneles.
- `utils/layout.ts`: `LAYOUT_DEFAULTS`, `clampSidebar`/`clampRight` (mín/máx), `parseLayout`/
  `serializeLayout`. Tests en `utils/layout.test.ts`.
- `index.css`: clases `workspace`/`pane`/`pane--*`/`resize-handle`; en ≤1024px los paneles
  laterales pasan a **drawers superpuestos** (hamburguesa/insights-toggle + backdrop), y en
  ≤768px se compacta el header. El chat usa `chat-scroll` + `chat-inner` (máx 860px, centrado).

### Persistencia de preferencias por usuario (modelo, modo, layout)
- Backend: tabla `settings` (clave/valor, PK `user_id+key`, upsert) en `repositories/db.py`;
  `repositories/settings.py`, `domain/settings.py`, `schemas/settings.py` y
  `routers/settings.py` (`GET/PUT /api/settings`). El modelo (`qwen3.5:9b` por defecto), el
  modo y las dimensiones del layout se guardan por usuario y se restauran al reabrir.
- Frontend: `api/settings.ts` + `hooks/useChat.ts` (`persistSettings`, `selectModel`,
  `selectMode`, `setLayout` cargan/guardan por `currentUserId`).

### Personalización del perfil (avatar/imagen/icono/color)
- Backend: columnas `avatar_color`/`avatar_emoji`/`avatar_image` en `users` (migración
  idempotente), `schemas/users.py` (`UserUpdate`), `repositories/users.py::update_user`,
  `domain/users.py`, y `PATCH /api/users/{id}` en `routers/users.py`.
- Frontend: `components/UserAvatar.tsx` (imagen → emoji → iniciales con color determinista),
  `components/ProfileDialog.tsx` (nombre, icono, color, subir/quitar imagen con
  `utils/image.ts::resizeImageToDataUrl`), `components/UserMenu.tsx` (selector de perfil,
  crear/editar). `UserSelect.tsx` eliminado (sustituido por `UserMenu`).

### Acceso en red local (LAN)
- Backend: `config.py` añade `ALLOWED_ORIGIN_REGEX` (IPs privadas IPv4) y `main.py` la usa en
  `CORSMiddleware` (`allow_origin_regex`). `services/network.py::get_lan_ip` +
  `routers/network.py::GET /api/network` (IP + URLs).
- Launcher: `core.py::backend_command` enlaza uvicorn a `0.0.0.0`; `core.py::lan_ip`/`lan_url`;
  `launcher.py` añade el recuadro "Acceso a la app" (URL local y LAN).
- Frontend: `components/NetworkBadge.tsx` muestra la URL LAN y permite copiarla.

### Tests añadidos
- Backend: `test_settings.py`, `test_user_profile.py`, `test_network.py`, +`test_cors.py`
  (caso LAN). Total backend **260 tests**.
- Frontend: `utils/layout.test.ts`, `utils/avatar.test.ts` (más los tests existentes). Total
  frontend **106 tests**.
- Launcher: `test_core.py` (+`test_backend_command_binds_lan`, `test_lan_url`). Total **24 tests**.

### Decisión de modelo (respuesta al usuario)
Se mantiene **`qwen3.5:9b`** como modelo por defecto (mejor calidad como tutor, ver sección 5);
`llama3.1:8b` queda instalado y seleccionable. La elección ahora es persistente por usuario.

## 19. M15 — Launcher: UI moderna con iconos, paneles colapsables y logs (HECHO)

Requisito del usuario: hacer el programa de arranque de escritorio más atractivo y completo,
con iconos en la UI y más información en paneles colapsables.

- **`launcher/ui.py`** (nuevo, puro y testeable): `COLORS` (paleta claro con acento índigo),
  `SERVICE_ICONS`/`SECTION_ICONS`/`ACTION_ICONS` (emoji), `status_dot()` (punto de estado por
  color) y `read_log_tail()` (últimas N líneas de `logs/*.log`).
- **`launcher/status.py`**: `fetch_version()` (versión desde `/api/health`) y
  `read_db_details()` (contadores de tablas opcionales — vocabulario, errores, eventos,
  pronunciación, listening, preferencias — tolerante a tablas inexistentes vía `sqlite_master`).
- **`launcher/launcher.py`** (reescrito):
  - Tema `clam` personalizado (`ttk.Style`) con banner de cabecera (logo "EN" + título +
    versión + píldora de estado "En marcha/Detenida" con punto de color).
  - Botones con iconos (Iniciar/Detener/Abrir/Actualizar).
  - **Paneles colapsables** reutilizables (`class Collapsible`): Servicios, Acceso a la app,
    Base de datos (con detalle de tablas), Usuarios y Registros (logs de backend/frontend en
    un `Notebook`, colapsado por defecto).
  - Contenido desplazable (Canvas + Scrollbar) y footer de estado. Lógica de concurrencia
    (cola + hilos + `ProcessManager`) intacta.
- **Tests**: `tests/test_ui.py` (nuevo, 5) + `tests/test_status.py` (+4). Total launcher
  **33 tests** + `ruff` limpio.

> Nota de arranque en red: el frontend (Vite) ahora escucha en `0.0.0.0` (`vite.config.ts`
> `host: true`), igual que el backend, para que la app sea accesible desde otros equipos de la
> LAN (antes solo respondía `localhost` y el puerto 5173 no era alcanzable).

## 20. HECHO (V1.8) — Loop diario: placement adaptativo + objetivo + Session Engine

> **Origen.** Auditoría pedagógica: faltaba un "loop diario" integrado. Este bloque cierra ese
> hueco cableando a la UI el placement adaptativo ya existente en backend, añadiendo un objetivo
> personal editable y un **Session Engine** que unifica las señales CEFR y de listening en una
> sesión diaria priorizada.

### 20.1 Placement adaptativo cableado a la UI
- `frontend/src/components/Academy.tsx`: el placement pasó de batch (`getPlacement` +
  `submitPlacement`) a adaptativo (`startAdaptivePlacement` + `nextAdaptivePlacement`), con
  estado `placementItem`/`placementSessionId`/`placementAnswers`/`placementAnswered`.
- `frontend/src/api/academy.ts`: `startAdaptivePlacement`, `nextAdaptivePlacement`.
- `frontend/src/types/api.ts`: `PlacementStart`, `PlacementAdaptive`.

### 20.2 Objetivo personal editable
- **DB** (`backend/repositories/db.py`): tabla `learning_goal`
  (`user_id PK, goal_type, minutes_per_day, days_per_week, target_level, updated_at`, FK a users).
- **Repo** (`backend/repositories/academy.py`): `get_goal`, `upsert_goal`.
- **Schemas** (`backend/schemas/academy.py`): `LearningGoalIn` (`GoalType` literal, minutos 5–180,
  días 1–7, `target_level` CEFR), `LearningGoalOut`.
- **Domain** (`backend/domain/academy.py`): `DEFAULT_GOAL`, `get_learning_goal`, `set_learning_goal`;
  `get_today_plan` y `get_student_model` usan el objetivo (`minutes_per_day` y `target_level`).
- **Routers** (`backend/routers/academy.py`): `GET/PUT /api/academy/goal`.
- **Frontend**: `getGoal`/`putGoal` en `api/academy.ts`; editor de objetivo (tipo, meta CEFR,
  min/día, días/semana) en `components/TodayPlan.tsx`, con `putGoal` + recarga de modelo/sesión.
- **Tests**: `backend/tests/test_academy_goal.py` (repo + endpoints); `frontend/src/api/academy.test.ts`.

### 20.3 Session Engine (backend puro)
- `backend/services/adaptive.py`:
  - Refactor `_assign_minutes(items, budget, mix=None)` para repartir minutos con un `mix` por
    categoría (antes pesos fijos).
  - `SESSION_MIX` = `{review: .30, listening: .15, weakness: .30, new: .15, easy_wins: .10}`.
  - `SESSION_CAPS` = `{review: 3, listening: 2, weakness: 2, new: 1, easy_wins: 1}`.
  - `session_plan(profile, level, remediation, mastered_ids, next_objective_id, listening_weak,
    budget_minutes)`: secuencia priorizada review → listening → debilidad → nuevo → refuerzo,
    con `level_id` y `skills` en los pasos con objetivo (para arrancar la lección).
  - `steps_of(steps, kind)` y `session_summary(steps)` → `{review_count, practice_count}`.
- `backend/schemas/academy.py`: `SessionStepOut` (`kind, skill, subskill, objective_id, level_id,
  skills, title, reason, minutes`) y `SessionOut` (`items, total_minutes, review_count,
  practice_count`).
- `backend/domain/academy.py`: `get_session(user_id)` une el perfil CEFR (`list_objective_mastery`,
  `mastered_objective_ids`, `remediation_plan`, `recommend_next`) con el diagnóstico de listening
  (`listening_repo.list_attempts` + `listening_diagnostic`) y llama a `session_plan` con el
  presupuesto del objetivo.
- `backend/routers/academy.py`: `GET /api/academy/session`.
- **Tests**: `backend/tests/test_adaptive.py` (session_plan/session_summary, pasos con
  level_id/skills) + `test_academy_goal.py` (endpoint session).

### 20.4 Frontend: sesión en "Hoy" + enrutado por paso
- `frontend/src/types/api.ts`: `SessionStep`, `Session`, `LearningGoal`, `LearningGoalType`.
- `frontend/src/api/academy.ts`: `getSession`.
- `frontend/src/components/TodayPlan.tsx`:
  - Muestra `Session` (no `TodayPlan`): cabecera `total_minutes` + "repasa N · practica M" y
    lista `SessionStepRow` (botón accionable) con `KIND_LABELS`/`SUBSKILL_LABELS`/`SKILL_LABELS`.
  - Botón "Empezar la sesión de hoy" lanza el primer paso.
  - Nueva prop `refreshKey` que recarga modelo+sesión al cambiar (para reflejar pasos completados).
- `frontend/src/App.tsx`:
  - `handleSessionStep(step)`: listening → abre insights + scroll a `#listening-practice`;
    objetivo → `startLesson(...)`; skill → cambia `mode` vía `SKILL_MODE`.
  - `sessionVersion` state: `onAttempt` y "Terminar lección" lo incrementan; se pasa como
    `refreshKey` a `TodayPlan` para que el paso completado desaparezca al recargar la sesión.
- `frontend/src/index.css`: estilos `.goal-editor`, `.session-headline`, `.today-item-action`
  (botón de paso), `.kind-listening`.

### 20.5 Pendiente / siguiente incremento natural
- **P3–P6 de Etapa 2** (vocabulario, listening competencia, CEFR evidencia, pronunciación fonémica):
  ver `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 21. HECHO (V1.8.1) — Marcar pasos de la sesión como "hechos"

Cierra el hueco de `review`/`easy_wins` (que solo cambiaban de modo): ahora cualquier
paso se puede marcar como completado y desaparece de la sesión de hoy, con reseteo diario.

- **`services/adaptive.py`**: `step_key(step)` (clave estable: `listening:<subskill>`,
  `<weakness|new>:<level>:<objective>`, `<review|easy_wins>:<skill>`) y
  `session_plan(..., exclude_keys=...)` que anota cada paso con `step_key`, filtra los
  ya completados y **reparte los minutos solo entre los pasos restantes**.
- **`repositories/db.py`**: tabla `session_completions` (`PK (user_id, step_key)`,
  `completed_on` para el reseteo diario, FK a users).
- **`repositories/academy.py`**: `mark_session_step(user_id, step_key, completed_on)`
  (upsert) y `list_session_steps(user_id, completed_on) -> set[str]`.
- **`schemas/academy.py`**: `SessionStepOut.step_key` + `SessionCompleteRequest`.
- **`domain/academy.py`**: `_today()` (fecha UTC `YYYY-MM-DD`); `get_session` excluye los
  pasos de hoy (`exclude_keys`); `set_session_step_done(user_id, step_key)` → devuelve la
  sesión actualizada.
- **`routers/academy.py`**: `POST /api/academy/session/complete` (`{step_key}`) → `SessionOut`.
- **Frontend**: `SessionStep.step_key`, `completeSessionStep` en `api/academy.ts`; en
  `TodayPlan.tsx` cada paso tiene un botón "✓" (`.today-item-done`) que llama al endpoint
  y sustituye la sesión con la respuesta (el paso marcado desaparece). Estilos en `index.css`.
- **Tests**: `test_adaptive.py` (+`step_key`, +`exclude_keys`), `test_academy_goal.py`
  (+repo mark/list y +endpoint complete), `api/academy.test.ts` (+`completeSessionStep`).

### Verificación rápida del estado sin commitear
```powershell
cd backend && .venv\Scripts\python.exe -m pytest -q && .venv\Scripts\python.exe -m ruff check .
cd frontend && npx tsc --noEmit && npx vitest run
```

## 22. EN CURSO (sin commitear) — P3: vocabulario exposure / production / mastery

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P3: hoy `vocabulary` solo medía producción
> (`appearances` = mensajes en los que el alumno escribió la palabra). Este incremento separa los
> tres conceptos: **exposición** (palabras que lee en las respuestas del tutor), **producción**
> (palabras que escribe) y **dominio** (producción repetida y espaciada en el tiempo).

### 22.1 Modelo de datos (exposición vs producción)
- **`repositories/db.py`**: migración idempotente en `vocabulary`:
  - `exposures INTEGER NOT NULL DEFAULT 0` (mensajes del tutor en los que apareció la palabra).
  - `last_exposed_at TEXT NOT NULL DEFAULT ''`.
  - `production_days INTEGER NOT NULL DEFAULT 0` (días distintos con producción = espaciado).
  - Backfill: `UPDATE vocabulary SET production_days = 1 WHERE appearances > 0 AND production_days = 0`.

### 22.2 Señal de dominio (pura)
- **`services/vocabulary.py`**: `classify(appearances, production_days)` → `"exposed"` (nunca
  producida) | `"learning"` (producida, sin consolidar) | `"mastered"` (≥3 producciones y ≥2 días
  distintos). Constantes `MASTERY_MIN_PRODUCTIONS = 3`, `MASTERY_MIN_DAYS = 2`.

### 22.3 Repositorio
- **`repositories/vocabulary.py`**:
  - `record_words` ahora también incrementa `production_days` cuando la producción cae en un día
    distinto al último (`_day(iso)` → `iso[:10]`).
  - `record_exposures(user_id, words)` (nuevo): upsert con `appearances = 0` para crear filas
    solo-expuestas.
  - `get_vocabulary` devuelve `exposures`, `last_exposed_at`, `production_days`.

### 22.4 Schemas + dominio
- **`schemas/vocabulary.py`**: `VocabularyItem` gana `exposures`, `last_exposed_at`,
  `production_days`, `status: Literal["exposed","learning","mastered"]`.
- **`domain/vocabulary.py`**: `record_exposure(user_id, text)` (nuevo) y `get_vocabulary` calcula
  `status` por palabra vía `classify`.

### 22.5 Captura de exposición en el chat
- **`routers/chat.py`**: tras la respuesta del tutor (`chat` y `chat_stream`), si hay `user_id` se
  llama `vocabulary_service.record_exposure(user_id, reply)`; en el stream se acumulan los chunks y
  se registra al final.

### 22.6 Perfil separa producido / expuesto / dominado
- **`domain/profile.py`**: `vocab_size` (para CEFR y recomendaciones) ahora cuenta solo palabras
  producidas (`appearances > 0`), no las solo-expuestas; calcula `vocabulary_mastered` y
  `vocabulary_exposed`.
- **`schemas/profile.py`**: `LearningProfile` gana `vocabulary_exposed` y `vocabulary_mastered`.

### 22.7 Frontend
- **`frontend/src/types/api.ts`**: `LearningProfile.vocabulary_exposed`/`vocabulary_mastered`.
- **`frontend/src/components/LearningProfile.tsx`**: bloque Vocabulario muestra "N dominadas · M
  vistas" (`.learning-sub`).

### 22.8 Tests
- `test_vocabulary.py`: `classify` (5 casos), `record_exposures` (crea/acumula/unknown),
  `production_days` con días controlados (monkeypatch `_now`), endpoint `status`, migración P3
  (drop column + backfill).
- `test_profile.py`: perfil separa `vocabulary_size`/`vocabulary_exposed`/`vocabulary_mastered`.
- `test_chat_profile.py`: `chat` y `chat_stream` registran la exposición del tutor.

### 22.9 Siguiente incremento natural
- **P5–P6 de Etapa 2** (CEFR por evidencia, pronunciación fonémica): ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 23. HECHO (V1.10) — P4: listening como competencia

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P4: el listening ya medía `difficulty`,
> `response_time_ms` y `replay_count`, pero no distinguía **tema**, ni precisión por
> dificultad/tema, ni tendencia reciente, ni reincidencia. Este incremento lo convierte en
> una señal de **competencia**.

### 23.1 Tema (`topic`)
- **`services/listening.py`**: `LISTENING_TOPICS` (10 temas canónicos), campo `topic` en
  `ListeningAsset` y en los 23 ítems de `QUESTION_BANK`; `validate_listening_bank` exige
  `topic` válido.

### 23.2 Métricas de competencia (puras y deterministas)
- `accuracy_by_difficulty(rows)`, `accuracy_by_topic(rows)`, `recent_trend(rows, window=10)` y
  `recurrence_stats(rows)`; `listening_diagnostic` expone `by_difficulty`, `by_topic`, `trend`
  y `recurrence`.

### 23.3 Persistencia + dominio + esquemas
- `repositories/db.py`: migración idempotente `topic` en `listening_attempts`.
- `repositories/listening.py`: `record_attempt(..., topic=...)` y `list_attempts` incluyen `topic`.
- `domain/listening.py`: `submit_answer` pasa el tema de la pregunta.
- `schemas/listening.py`: `topic` en `ListeningQuestion` + `ListeningDifficultyOut`,
  `ListeningTopicOut`, `ListeningTrend`, `ListeningRecurrence` en `ListeningDiagnostic`.

### 23.4 Frontend
- `types/api.ts` (nuevos tipos) y `ListeningPractice.tsx` (precisión por tema/dificultad,
  tendencia reciente y reincidencia). Estilos en `index.css`.

### 23.5 Tests
- `test_listening.py` (+11) y `test_listening_architecture.py` (+2). Total backend
  **556 tests**; frontend **143 tests**.

### 23.6 Pendiente / siguiente incremento natural
- **P5–P6 de Etapa 2** (CEFR por evidencia, pronunciación fonémica): ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`.

## 24. HECHO (V1.11) — P5: CEFR basado en evidencia

> **Origen.** `PLAN-ETAPA-PEDAGOGICA.md` P5: `services/cefr.py::evaluate_cefr` sumaba puntos
> (`_vocab_points`, `_pron_points`, `_exercise_points`, `_grammar_points`, `_fluency_points`) y
> mapeaba la suma a un nivel. Era un "contador": subías de nivel con vocabulario aunque no
> tuvieras ni una muestra de pronunciación, listening o gramática. Este incremento lo sustituye
> por un modelo de **evidencia** y expone la **confianza** del nivel.

### 24.1 Modelo de evidencia (`services/cefr.py`)
- `MIN_SAMPLES` (mínimo de muestras por destreza): `vocabulary=50`, `grammar=5`,
  `fluency=5`, `pronunciation=3`, `listening=5`; `TRACKED_SKILLS` con ese orden.
- `listening_band(accuracy)` (umbrales 85/70/50, `"—"` si `None`) y `_band_rank`.
- `evaluate_cefr` reescrito: por destreza calcula `band` + `samples` + `confidence`
  (`min(1, samples/required)`); el nivel es la **banda más baja entre las destrezas con
  evidencia suficiente** (`confidence >= 1` y `band != "—"`), o `A1` si no hay ninguna;
  devuelve `{level, bands, evidence, confidence, descriptor}`.
- Eliminadas las funciones privadas de puntos (`_vocab_points`, `_pron_points`,
  `_exercise_points`, `_grammar_points`, `_fluency_points`, `_level_from_points`).
- `estimate_cefr` sigue delegando en `evaluate_cefr(signals)["level"]` (API v1 intacta).

### 24.2 Dominio (`domain/profile.py`)
- `_compute_profile` ahora obtiene `listening_repo.get_stats` y pasa a `evaluate_cefr` las
  señales nuevas: `pronunciation_attempts`, `user_messages`, `listening_accuracy`,
  `listening_attempts`. Expone `estimated_confidence` y `estimated_evidence`.

### 24.3 Esquemas (`schemas/profile.py`)
- `EstimatedBands` + `listening`; nueva `CefrEvidence` (`skill`, `band`, `samples`,
  `required`, `confidence`); `LearningProfile` + `estimated_confidence` y `estimated_evidence`.

### 24.4 Frontend
- `types/api.ts` (nuevos tipos), `utils/cefr.ts` (`bandLabel("listening")`),
  `components/LearningProfile.tsx` (banda de listening + barra de confianza + detalle por
  destreza) y estilos en `index.css`.

### 24.5 Tests
- `test_cefr_evaluation.py` (casos de evidencia, `listening_band`, 5 destrezas en `evidence`)
  y `test_profile.py` (nuevos niveles B1/C1 y `estimated_confidence`/`estimated_evidence`).
  Total backend **558 tests**; frontend **143 tests**.

### 24.6 Pendiente / siguiente incremento natural
- **V1.12 — Student Model unificado + Assessment Loop** (P6 speaking + P7 unificación): ver
  sección 25 y `agentes/pedagogia/p6-speaking-2.0.md` / `p7-student-model-unificado.md`.
- El P6 original (pronunciación fonémica) queda **diferido** a favor de esta unificación.

## 25. HECHO (V1.12) — Student Model unificado + Assessment Loop

> **Origen.** La auditoría externa de V1.11 detectó dos estimadores CEFR paralelos que se
> contradicen (`/api/profile` con banda mínima vs `/api/academy/student-model` con nivel continuo
> ponderado), 4 defectos de scoring en Speaking y la falta de histórico de evaluación. V1.12
> convierte el **Student Model de la Academy en la fuente de verdad única**, corrige los P0 y añade
> **snapshots de evaluación** reproducibles. Dos subagentes (`p6`, `p7`), cada uno su `feat:`.

### 25.1 P6 — Speaking scoring 2.0 + higiene de release
- **`services/speaking.py`**: `task_achievement` usa `task_achieved` del LLM en flujo libre
  (el solapamiento de tokens es solo cota inferior con `expected`); `lexical_resource` mide
  diversidad léxica (TTR) con `lexical_diversity(tokens)`; `coherence` usa el `coherence` del LLM
  + marcadores discursivos (eliminado `len(heard)/len(expected)`); `pronunciation` devuelve
  `observed=false`/`score=None` sin audio y `_weighted_overall` recalcula solo criterios
  observados. Añade `observed` y `confidence` por criterio; penalizaciones discursivas
  (`self_corrections`, `hesitations`, `repetitions`) reducen `fluency`.
- **`services/speaking_llm.py`**: `SPEAKING_EVIDENCE_FIELDS` ampliada con `cohesion`,
  `discourse_markers`, `self_corrections`, `hesitations`, `repetitions`; helpers
  `_parse_float_field`/`_parse_count_field` con fallback.
- **`config.py`** → `VERSION = "1.11.0"`; **`README.md`** → "v1.11.0".
- **`schemas/academy.py`** / **`domain/academy.py`**: `observed` en speaking, `criteria` con
  `float | None`.
- Tests: `test_speaking.py` (observed, diversidad, sin audio, penalizaciones),
  `test_speaking_llm.py` (campos opcionales + fallback).

### 25.2 P7 — Student Model fuente única + snapshots + naming CEFR
- **`domain/academy.py`**: `build_student_model(user_id) -> dict` como única fuente de verdad
  (reutiliza `build_skill_profile` + `adaptive.estimated_level` + `readiness` +
  `reassessment_due`); `get_student_model` proyecta a `StudentModelOut`.
- **`domain/profile.py`**: `_compute_profile` delega en `build_student_model` (adiós al min-band
  propio); helpers puros extraídos (`_bands_from_skills`, `_skill_states`, `_activity_stats`,
  `_maybe_record_snapshot`). `get_profile_summary` incluye `cefr_history`.
- **`repositories/db.py`**: tabla idempotente `cefr_assessment_snapshots` + índice.
- **`repositories/profile.py`**: `record_cefr_snapshot`, `list_cefr_history`,
  `last_cefr_snapshot`.
- **`services/cefr.py`**: `estimate_cefr` (API v1) intacta; bandas documentadas como
  "heuristic CEFR-aligned band"; `CEFR_MODEL_VERSION` y `heuristic_band(score)`. `evaluate_cefr`
  deja de ser la fuente del perfil global.
- **`schemas/profile.py`**: `EstimatedBands` con 7 destrezas (`speaking`, `reading`, `writing`);
  nuevas `SkillState` y `CefrSnapshot`; `LearningProfile` con `overall_ability`, `target_level`,
  `skills`, `readiness` y `cefr_history`.
- **Frontend**: `types/api.ts` (nuevos tipos, adiós `CefrEvidence`), `utils/cefr.ts`
  (`bandLabel` speaking/reading/writing), `utils/modes.ts` (`conversation` → `speaking`),
  `components/LearningProfile.tsx` (barra `overall_ability`, `readiness` con `blocking_skills`,
  desglose por destreza con muestras/confianza/tendencia, histórico CEFR), estilos en `index.css`.
- Tests: `test_profile.py` (nuevo shape + snapshot una sola vez), `test_cefr_evaluation.py`
  (`heuristic_band`, `CEFR_MODEL_VERSION`), frontend `cefr.test.ts`/`modes.test.ts`.

### 25.3 Verificación
- Backend `566 tests` + `ruff` limpio; frontend `143 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 25.4 Pendiente / siguiente incremento natural
- **V1.13** — Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2): ver sección 26.
- **V1.14** — Listening Evidence & Adaptive Selection: ver sección 27.
- **V1.15** — Speaking 3.0 (sobre el mismo Student Model). Ver sección 28.

## 26. V1.13 — Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2)

> **Origen.** `agentes/pedagogia/p8-listening-3.0.md`. El listening tenía arquitectura sólida
> (banco versionado, vector 8D, 15 sub-destrezas, métricas de competencia) pero **sin audio
> pre-renderizado**: el frontend sintetizaba `script` en vivo con la voz Piper única, ignorando
> `speech_rate`/`accent`. Además faltaba `b2.json` (el banco ya tenía ítems B2: `l16`, `l17`, `l20`,
> `l21`). V1.13 sirve **audio TTS pre-renderizado por ítem**, cierra **A1→B2** y garantiza evidencia
> independiente por sub-destreza. Honesto con el límite local: Piper es una sola voz; acentos/ruido/
> hablantes son límite de **contenido**, no de código.

### 26.1 Audio TTS pre-renderizado por ítem
- **`services/tts.py`**: `synthesize(text, length_scale=1.0)` ahora acepta velocidad vía
  `SynthesisConfig(length_scale=...)`.
- **`services/listening.py`**: `length_scale_for_rate(speech_rate)` (mapea wpm → `length_scale`,
  clamp `[0.6, 1.6]`), `audio_text(question)` (`transcript` con fallback a `script`), y
  `LEVEL_ORDER = ["A1", "A2", "B1", "B2"]`.
- **`domain/listening.py`**: `get_audio(question_id)` sintetiza y cachea en `DATA_DIR/listening/`
  (primera petición) y sirve del caché después; `audio_ready(question)` y `_public` exponen
  `audio_ready`.
- **`routers/listening.py`**: `GET /api/listening/audio/{question_id}` → `audio/wav` (404/503).
- **`schemas/listening.py`**: `ListeningQuestion.audio_ready`.

### 26.2 Cierre A1→B2
- **`curriculum/b2.json`**: nivel B2 (8 objetivos, checks de opción múltiple cubriendo sus
  destrezas evaluables — invariante curricular verde).
- **`services/curriculum.py`**: `LISTENING_BANK_VERSION` → `3.0.0`.
- **`scripts/generate_listening_audio.py`**: pre-renderiza todo el banco (idempotente, `--force`).

### 26.3 Evidencia por sub-destreza
- `test_new_subskills_generate_independent_evidence` cubre `fast_speech`, `connected_speech`,
  `multiple_speakers`, `dictation`, `shadowing`, `speaker_intention` en `listening_diagnostic`.

### 26.4 Frontend
- **`api/listening.ts`**: `getListeningAudioUrl(questionId, userId)`.
- **`types/api.ts`**: `audio_ready: boolean`.
- **`components/ListeningPractice.tsx`**: reproduce audio TTS pre-renderizado cuando `audio_ready`,
  degrada a TTS en vivo con aviso "audio de referencia no disponible"; respeta `replayCount`.
- **`index.css`**: estilo `.listening-audio-degraded`.

### 26.5 Higiene de release
- `config.py`/`README.md`/`PLAN.md`/`package.json`/`package-lock.json` → `1.13.0`; `CHANGELOG.md`
  con entrada 1.13.0.

### 26.6 Verificación
- Backend `576 tests` + `ruff` limpio; frontend `144 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 26.7 Pendiente / siguiente incremento natural
- **V1.14** — Listening Evidence & Adaptive Selection: ver sección 27.
- **V1.15** — Speaking 3.0 (sobre el mismo Student Model): fluency/grammar/lexical/
  pronunciation/coherence/interaction medidos longitudinalmente. Ver sección 28.

## 27. HECHO (commiteado) — V1.14: Listening Evidence & Adaptive Selection

> **Origen.** Auditoría externa de V1.13 (commit `37ac52b9…`, 2026-08-26). Veredicto: arquitectura
> muy buena, pero el "audio real" era en realidad **TTS Piper de una sola voz**, y la metadata
> (`accent`/`speaker_count`/`noise`/`connected_speech`) podía generar **evidencia pedagógica falsa**
> en el Student Model. V1.14 añade una capa de **AudioRealization** + **Evidence Integrity** y hace
> que el **selector consuma de verdad el Student Model**, sin rehacer V1.13.

### 27.1 Modelo de realización del audio
- **`services/listening.py`**: `AUDIO_TYPES` (`tts`/`recorded`/`mixed`/`synthetic_multispeaker`/
  `real_world`), `realized_vector` (qué factor realiza el audio servido), `realization_status`
  (`declared`/`realized`/`verified`), `realized_difficulty`, `realization_gap_factors` y
  `subskill_realization_gap` (mapa `SUBSKILL_REALIZATION_FACTOR`).
- Para una voz Piper única: `vocabulary`/`syntactic`/`length` se realizan; `speed` solo con
  `speech_rate`; `connected_speech` solo si el texto escribe la reducción; `accent`/
  `speaker_count`/`noise` no se realizan (quedan en 1).
- `audio_digest` (hash texto + velocidad + repetición) para invalidar el cache.

### 27.2 Integridad de evidencia
- `listening_diagnostic` añade `realization_gap` por sub-destreza y resumen `realization`
  (`attempts`/`verified`/`gap`). El Student Model no debe tratar como dominio real una
  sub-destreza entrenada con audio que no respalda su factor.
- `schemas/listening.py`: `ListeningQuestion` expone `audio_type`, `realized_difficulty`,
  `realization`; `ListeningSubskillOut.realization_gap`; `ListeningDiagnostic.realization`.
- `repositories/listening.py` + migración `realized_difficulty` en `listening_attempts`.

### 27.3 Selector adaptativo
- `pick_next_question(..., weak_subskills=...)` prioriza, **dentro del nivel de trabajo** del alumno,
  las sub-destrezas débiles con realización auditiva válida (no entrena `multiple_speakers` con una
  sola voz). `domain.next_question` lo alimenta con `listening_diagnostic(attempts)["weak"]`.

### 27.4 Cache de audio versionado (P1.1)
- `domain/listening.py`: `_audio_cache_dir()` → `DATA_DIR/listening/{bank_version}/{voice}` y
  `_audio_path()` → `{id}-{digest}.wav`. `scripts/generate_listening_audio.py` usa el mismo path.

### 27.5 Frontend
- `types/api.ts`: `audio_type`, `realized_difficulty`, `realization`, `realization_gap`,
  `ListeningRealizationSummary`.
- `components/ListeningPractice.tsx`: etiqueta honesta del tipo de audio (voz sintética local vs.
  grabación real), aviso cuando `realized_difficulty < difficulty`, y marca `realization_gap` en
  el diagnóstico. Estilos en `index.css`.

### 27.6 Higiene de release
- `config.py`/`README.md`/`PLAN.md`/`package.json`/`package-lock.json` → `1.14.0`; `CHANGELOG.md`
  con entrada 1.14.0. Renombrado "audio real" → "audio TTS pre-renderizado" en CHANGELOG, README,
  PLAN, RELEVO y comentarios de código.

### 27.7 Verificación
- Backend `592 tests` + `ruff` limpio; frontend `144 tests` + `tsc` OK.

### 27.8 Pendiente / siguiente incremento natural (P1/P2 de la auditoría)
- **Delayed retention** (P1.2): `immediate_accuracy` vs `delayed_accuracy` (Day 0/2/7/30).
- **True listening tasks** (P1.3–P1.8): shadowing con grabación/alineamiento, dictado real,
  varios hablantes, connected speech real, acentos reales, ruido real.
- **Audio variants / difficulty ladder** (P1.9): variantes de un mismo contenido (slow/clean →
  natural → fast → noise → accent).
- **V1.15** — Speaking 3.0 sobre el mismo Student Model: ver sección 28.

## 28. HECHO (commiteado) — V1.15: Speaking 3.0

> **Origen.** `agentes/pedagogia/p9-speaking-3.0.md`. El speaking ya tenía un rubric determinista
> (fluency/grammar/lexical/pronunciation/coherence) y evidencia por intento, pero **no medía la
> evolución longitudinal por criterio** (a diferencia de `listening_diagnostic`), ni contemplaba la
> **interacción** como dimensión. V1.15 añade `speaking_diagnostic` espejo del de listening, integra
> `interaction` como séptimo criterio y expone el diagnóstico en el Student Model y en el frontend.

### 28.1 Diagnóstico longitudinal por criterio (S1)
- **`services/speaking.py`**: `speaking_diagnostic(evidence_rows)` agrupa por criterio
  (`attempts`/`mean`/`min`/`max`/`review_due`), deriva `weak` (`mean < 0.7`) y `recommendation`
  (criterio con menor media), y `trend` global sobre las filas `overall`/`overall_mean`.
  Umbrales `SPEAKING_WEAK_THRESHOLD`/`SPEAKING_MIN_ATTEMPTS`/`SPEAKING_TREND_WINDOW`.
- **`schemas/academy.py`**: `SpeakingCriterionOut`, `SpeakingTrend`, `SpeakingDiagnostic`.
- **`domain/academy.py`**: `get_speaking_diagnostic(user_id)` + puente de criterios de speaking
  como `subskills` en `_annotated_profile` (espejo de listening).
- **`routers/academy.py`**: `GET /api/academy/speaking/diagnostic`.

### 28.2 Criterio `interaction` (S2)
- **`services/speaking.py`**: `SPEAKING_CRITERIA` pasa a 7 (`interaction`), `CRITERION_WEIGHTS`
  rebalanceado (`interaction` 0.05); `score_speaking` trata `interaction` como `None` cuando no es
  observable (read-aloud).
- **`services/speaking_llm.py`**: `build_speaking_prompt` pide `interaction`, `parse_speaking_evidence`
  lo extrae, `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` lo incluye.

### 28.3 Frontend (S3)
- **`types/api.ts`**: `SpeakingCriterionProgress`, `SpeakingTrend`, `SpeakingDiagnostic`.
- **`api/academy.ts`**: `getSpeakingDiagnostic(userId)`.
- **`components/SpeakingDiagnostic.tsx`**: desglose por criterio, tendencia global y puntos a
  revisar. Integrado en `App.tsx` (panel de insights). Estilos en `index.css`.

### 28.4 Higiene de release
- `config.py`/`package.json` → `1.15.0`; `CHANGELOG.md` con entrada 1.15.0; `PLAN.md`,
  `PLAN-ETAPA-PEDAGOGICA.md` y `ARQUITECTURA.md` actualizados.

### 28.5 Verificación
- Backend `602 tests` + `ruff` limpio; frontend `145 tests` + `tsc` OK; launcher `55 tests` +
  `ruff` limpio.

### 28.6 Pendiente / siguiente incremento natural
- **Writing 3.0** sobre el mismo Student Model (espejo del patrón listening/speaking).
- Retomar los **P1 de listening** de la auditoría V1.14: delayed retention (P1.2), shadowing real
  (P1.3), dictado real, varios hablantes, acentos y ruido reales, variantes de dificultad.

## 29. HECHO (commiteado) — V1.16: Speaking Assessment & Evidence 2.0

> **Origen.** Auditoría externa de V1.15. Veredicto: arquitectura 9.3/10, pero **validez
> pedagógica ~7.5–8/10** — el "Longitudinal Speaking Competence" seguía siendo un agregador
> `mean/min/max + trend`, no un modelo de competencia, y varios criterios eran demasiado toscos.
> V1.16 se divide en **6 piezas (S1–S6)** más **3 bloques de cierre** ejecutados con subagentes.
> Filosofía intacta: el LLM sigue siendo **solo extractor de evidencia**; todo el scoring es
> determinista; un criterio no observado NO se inventa (`score=None`).

### 29.1 S1 — task_achievement continuo + GrammarEvidence 2.0 (P0-1, P0-2, P2)
- `services/speaking.py`: docstrings "6→7 dimensiones"; `TASK_SUBDIM_WEIGHTS` (task_completion/
  task_relevance/task_coverage/task_appropriateness) + `_task_achievement_score` (graduado, con
  fallback binario `task_achieved`); `_GRAMMAR_PENALTY_MINOR/MAJOR/CRITICAL` + `_grammar_score`
  (severidad en vez de `1 - 0.25·errores`).
- `services/speaking_llm.py`: extrae `grammar_error_details` (type + severity) y las 4
  sub-dimensiones de tarea.

### 29.2 S2 — SpeakingTaskProfile + dificultad declared/realized/verified + pesos por task_type (P0-1)
- `services/speaking.py`: `SpeakingTaskProfile` (task_type, cefr_target, duration_target,
  difficulty_vector, `difficulty`), `TASK_TYPES`, `SPEAKING_DIFFICULTY_FACTORS`,
  `CONVERSATIONAL_TASK_TYPES`, `difficulty_from_vector`, `weights_for_task_type`, `realized_vector`,
  `realized_difficulty`, `realization_gap_factors`; `scores_from_evidence(..., task_type=...)`
  ajusta pesos; `evidence_from_speaking(..., difficulty=...)` registra la dificultad.
- `schemas/academy.py` + `domain/academy.py` + `routers/academy.py`: `task_type`, `difficulty`,
  `difficulty_vector`, `expected` propagados.

### 29.3 S3 — LexicalEvidence 2.0 + FluencyEvidence 2.0 (P1-2, P1-3)
- Léxico: TTR puro → MSTTR por segmentos + `range` (mínimo de tipos) + sophistication/precision/
  collocations del LLM (`LEXICAL_SUBDIM_WEIGHTS`, `_msttr`, `lexical_evidence`, `_lexical_score`).
- Fluidez: `fluency ≠ speed` — bandas CEFR de WPM (`_speech_rate_score`) + smoothness/rhythm del
  LLM (`FLUENCY_SMOOTHNESS_WEIGHT`/`FLUENCY_RHYTHM_WEIGHT`, `_fluency_score`).

### 29.4 S4 — InteractionEvidence 2.0 + pronunciación integrada (P1-4, P1-5)
- `INTERACTION_SUBDIM_WEIGHTS` (5 sub-dimensiones semánticas del LLM) + `_interaction_score`.
- `expected` integra `pronunciation` en flujo libre (solo si hay referencia; sin `expected` sigue
  `observed=false`).

### 29.5 S5 — Student Model ownership del diagnóstico (P1-6, P1-7)
- `speaking_diagnostic` pasa de `mean/min/max` a **vista** sobre señales del Student Model:
  `recent_score` (EMA α=0.5), `lifetime_score`, `confidence`, `stability`, `review_due` por
  olvido/fallo reciente/decaimiento (`_ema`, `SPEAKING_EMA_ALPHA`). `SpeakingCriterionOut` y
  `SpeakingDiagnostic.overall_recent` ampliados.

### 29.6 S6 — Speaking level continuo + Speaking Journey (CEFR)
- `services/speaking.py`: `speaking_level` (nivel continuo `numeric = 1.0 + 5.0·score` + confianza)
  y `speaking_journey` (steps cronológicos con nivel + confianza).
- `schemas/academy.py`: `SpeakingLevelOut`, `SpeakingJourneyStep`, `SpeakingJourneyOut`.
- `domain/academy.py`: `get_speaking_level`, `get_speaking_journey`.
- `routers/academy.py`: `GET /api/academy/speaking/level`, `GET /api/academy/speaking/journey`.

### 29.7 Tres bloques de cierre (subagentes)
- **InteractionEvidence objetiva** (P1-4): `services/interaction.py` (puro: `interaction_evidence`
  → turn_balance/avg_response_latency_ms/turn_completion/student_turns/assistant_turns/
  interruptions, con umbrales nombrados); fusión objetiva+semántica en `_interaction_score` vía
  `INTERACTION_OBJECTIVE_WEIGHT=0.5` (clave `evidence["interaction_objective"]`, backward-compatible);
  columnas `duration_ms`/`latency_ms` en `messages` (migración idempotente); telemetría TTFB/duración
  en `POST /api/chat/stream`; `GET /api/conversations/{id}/interaction`.
- **Speaking Assessment 1.0**: instrumento `curriculum/speaking_assessment.json` (4 partes:
  interview → individual task → interaction → follow-up); tabla trazable
  `speaking_assessment_sessions`; `services/speaking_assessment.py` (`load_speaking_assessment`,
  `assessment_parts`, `aggregate_assessment` — reutiliza `speaking_level`+`speaking_diagnostic`);
  dominio + endpoints `/api/academy/speaking/assessment/{start,part,finish}` y
  `GET /api/academy/speaking/assessment/{session_id}`.
- **Frontend**: tipos + API (`getSpeakingLevel`/`getSpeakingJourney`), `utils/speaking.ts`
  (`numericToCefr`, `formatConfidence`, `formatTrendDelta`, `nextFocus`, `criterionLabel`),
  `components/SpeakingPanel.tsx` (NEXT FOCUS + PRACTICE NOW) y `components/SpeakingJourney.tsx`
  (barra A2→B1→B2 con marcador "YOU"), CSS en `index.css`, montaje en `App.tsx`.

### 29.8 Pendiente → HECHO en V1.17
1. ✅ **UI del flujo de Speaking Assessment** — `components/SpeakingAssessment.tsx` (sección 30.1).
2. ✅ **Puente conversación→speaking** — telemetría objetiva cableada de extremo a extremo (sección 30.2).
3. ✅ **Writing 3.0** sobre el Student Model (sección 30.3). Queda **P1 de listening** (V1.14).

## 30. HECHO (commiteado) — V1.17: Speaking Assessment UI + puente + Writing 3.0

> **Origen.** Cierre de los tres incrementos naturales que dejó V1.16 (sección 29.8), lanzados
> como subagentes autocontenidos en orden: (1) la pantalla del Speaking Assessment, (2) el puente
> conversación→speaking y (3) Writing 3.0. Filosofía intacta: el LLM solo extrae evidencia; todo
> el scoring determinista; un criterio no observado no se inventa.

### 30.1 UI del flujo de Speaking Assessment (commit `012ec01`)
- `frontend/src/types/api.ts`: `SpeakingAssessmentPartInfo`, `SpeakingAssessmentPartScores`,
  `SpeakingAssessmentStart`, `SpeakingAssessmentPart`, `SpeakingAssessmentResult`,
  `SpeakingAssessmentState` (espejo de `schemas/academy.py`).
- `frontend/src/api/academy.ts`: `startSpeakingAssessment`, `submitSpeakingAssessmentPart`,
  `finishSpeakingAssessment`, `getSpeakingAssessment`.
- `frontend/src/components/SpeakingAssessment.tsx`: flujo `idle → part → result`; micrófono
  (`getUserMedia`+`MediaRecorder`+`transcribe`, `duration_seconds` con `performance.now()`) y
  entrada manual por `<textarea>` (usable sin micrófono).
- `frontend/src/utils/speaking.ts`: `formatScorePct`, `formatDurationTarget`; CSS `.speaking-assessment*`;
  montaje en `App.tsx`; tests en `utils/speaking.test.ts` y `api/academy.test.ts`.

### 30.2 Puente conversación→speaking (commit `e679300`)
- `backend/schemas/chat.py`: `duration_ms`/`latency_ms` en `ChatMessage` (persistidos vía
  `save_conversation`).
- `backend/domain/academy.py`: helper `_inject_interaction_objective`; `conversation_id` opcional
  en `submit_speaking_assessment_part` y `submit_speaking_task` → `conversations_repo.get_turns` →
  `services.interaction.interaction_evidence` → `evidence["interaction_objective"]` antes de
  `scores_from_evidence` (fusionado por `_interaction_score`).
- `backend/schemas/academy.py` + `routers/academy.py`: `conversation_id` en
  `SpeakingAssessmentPartSubmit`/`SpeakingTaskSubmitRequest` y propagación en endpoints.
- Frontend: `utils/telemetry.ts` (`turnTelemetry`), `api/chat.ts` (`conversationId`/`messageId`),
  `hooks/useChat.ts` (captura `duration_ms`/`latency_ms` del turno del alumno y envía
  `conversation_id`/`message_id` en `/api/chat/stream`).
- Tests: `test_speaking.py` (fusión objetiva+semántica, backward-compat, E2E con `conversation_id`);
  `utils/telemetry.test.ts`; `api/chat.test.ts`.

### 30.3 Writing 3.0 (commit `34e32e6`)
- `backend/services/writing.py`: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de
  `speaking.py`) sobre `WRITING_CRITERIA`, con `_ema`/`_mean_trend` y constantes
  `WRITING_EMA_ALPHA`/`WRITING_WEAK_THRESHOLD`/`WRITING_CONFIDENCE_THRESHOLD`/`WRITING_TREND_WINDOW`.
- `backend/schemas/academy.py`: `WritingCriterionOut`, `WritingTrend`, `WritingDiagnostic`,
  `WritingLevelOut`, `WritingJourneyStep`, `WritingJourneyOut`.
- `backend/domain/academy.py`: `get_writing_diagnostic`/`get_writing_level`/`get_writing_journey`;
  `backend/routers/academy.py`: `GET /api/academy/writing/diagnostic|level|journey`.
- Frontend: tipos + `getWriting*`, `utils/writing.ts` (`writingCriterionLabel`), `WritingPanel.tsx`
  + `WritingJourney.tsx`, CSS `.writing-*`, montaje en `App.tsx`; tests `test_writing.py`,
  `utils/writing.test.ts`, `api/academy.test.ts`.

### 30.4 Pendiente → HECHO en V1.18
- ✅ **P1 de listening** (auditoría V1.14): delayed retention (P1.2), dictado real (P1.4),
  shadowing real (P1.3) y escalera de variantes de velocidad (P1.9). Ver sección 31.
- ⏳ **P1.5–P1.8** (varios hablantes, connected speech real, acentos reales, ruido real) requieren
  **biblioteca de audio humano** (límite de contenido, no de código).
- ⏳ (Opcional) Integrar el **turn-taking real del chat** en la parte "Interaction" del Speaking
  Assessment.
- ⏳ **P6** (pronunciación fonémica) sigue diferido.

## 31. HECHO (commiteado) — V1.18: P1 de listening (retention + dictado/shadowing + variantes)

> **Origen.** Retoma los P1 de listening que dejó pendientes la auditoría V1.14 (§27.8), lanzados
> como subagentes autocontenidos en orden: (1) delayed retention (P1.2), (2) dictado + shadowing
> reales (P1.3/P1.4) y (3) escalera de variantes de audio (P1.9). Filosofía intacta: el LLM solo
> extrae evidencia (aquí ni siquiera puntúa); todo el scoring determinista y local (Whisper + Piper).

### 31.1 Delayed retention (P1.2) — commit `6071bca`
- `services/listening.py`: `delayed_retention(attempt_rows, now="")` (pura) — agrupa por
  `question_id`, la primera exposición es `immediate` y las re-exposiciones a ≥2 días son
  `delayed`, con buckets `0-2`/`2-7`/`7-30`/`30+` días y `retention_rate` (delayed/immediate).
  Reutiliza `services.forgetting.days_since`. Integrada en `listening_diagnostic` (kwarg `now` +
  clave `retention`).
- `schemas/listening.py`: `ListeningRetentionBucket`/`ListeningRetention` + `retention` en
  `ListeningDiagnostic`; `domain/listening.py` pasa `now=db._now()`.
- Frontend: tipos + bloque de retention en `ListeningPractice.tsx` + CSS. Tests
  `test_listening_retention.py`.

### 31.2 Dictado y shadowing reales (P1.3/P1.4) — commit `2183849`
- Migración idempotente: `task_type TEXT NOT NULL DEFAULT 'mcq'` y `score REAL` en
  `listening_attempts`; `record_attempt`/`list_attempts` las manejan.
- `services/listening.py`: `PRODUCTION_PASS_SCORE=80`, `production_score` (delega en
  `phonetics.composite_score`) y `production_reference` (`transcript → clean_transcript → script`);
  `mean_score` por sub-destreza en `listening_diagnostic`.
- `domain/listening.py`: `submit_production(user_id, question_id, transcript, task_type)` (valida
  skill, persiste `answer_index=-1` + score continuo). `routers/listening.py`:
  `POST /api/listening/dictation` y `/api/listening/shadowing`.
- Frontend: `ListeningPractice.tsx` bifurca por `skill` (dictado → textarea; shadowing →
  MediaRecorder + `transcribe(blob)`); tipos, API (`submitListeningDictation/Shadowing`) y CSS.
  Tests `test_listening_production.py` + `api/listening.test.ts`.

### 31.3 Escalera de variantes de velocidad (P1.9) — commit `26ae6c4`
- `services/listening.py`: `AUDIO_VARIANTS=("slow","normal","fast")`,
  `VARIANT_SPEED_FACTORS={slow:.75, normal:1.0, fast:1.25}`, `variant_speech_rate`,
  `variant_length_scale`, `audio_variants`, y `audio_digest(question, variant="normal")` que
  **preserva** el digest de `normal` (no invalida cache).
- `domain/listening.py`: `_audio_path(question, variant)`, `get_audio(question_id, variant)` (400
  si variante inválida), `_public` expone `variants` + `default_variant`. Router: query param
  `variant`. `schemas/listening.py`: `ListeningAudioVariant`.
- Frontend: botones Slow/Normal/Fast en `ListeningPractice.tsx` + `getListeningAudioUrl(..., variant)`.
  Tests `test_listening_variants.py` + `api/listening.test.ts`.

### 31.4 Pendiente / siguiente incremento natural
- **P1.5–P1.8** — varios hablantes, connected speech real, acentos reales, ruido real: requieren
  **biblioteca de audio humano** (grabaciones reales o sintetizador multi-voz). Límite de
  **contenido**, no de código; hoy Piper es una única voz.
- (Opcional) Integrar el **turn-taking real del chat** en la parte "Interaction" del Speaking
  Assessment (señal objetiva en vivo, no solo `conversation_id` manual).
- **P6** (pronunciación fonémica) sigue diferido.



# Documento de relevo (handoff)

> **Propósito:** permitir que un agente/contexto **nuevo** retome el proyecto desde cero
> sin perder el hilo (premisa 8 y 12). Si el chat del gerente se satura o hay riesgo de
> alucinación, este documento es el ancla para reanudar.
> Actualizado por última vez: 2026-08-24 08:50 (UTC+2).

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
- Rama por defecto: `main`. Última versión estable: tag `v1.0.0` (release publicado).
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

## 10. Fase de endurecimiento (FASE 1 P0 Y FASE 2 P1 CERRADAS — post v1.0.0)

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
> Siguiente bloque: **FASE 3 (persistencia y dominio)** — ver `docs/PLAN-ENDURECIMIENTO.md`.

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

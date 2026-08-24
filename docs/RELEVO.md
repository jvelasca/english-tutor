# Documento de relevo (handoff)

> **Propósito:** permitir que un agente/contexto **nuevo** retome el proyecto desde cero
> sin perder el hilo (premisa 8 y 12). Si el chat del gerente se satura o hay riesgo de
> alucinación, este documento es el ancla para reanudar.
> Actualizado por última vez: 2026-08-24 13:05 (UTC+2).

## 0. START HERE — para el gerente que retoma ahora

**Posición actual (2026-08-24):** Fases 0–8 del plan de endurecimiento **completas, verificadas
y commiteadas**. Working tree limpio. Últimos commits:
- `feat: fase 8.4` — UI CEFR multi-señal + fluidez + listening.
- `feat: fase 8.3` — listening (banco de preguntas + evaluación determinista).
- `feat: fase 8.2` — fluidez oral con duración (WPM) en pronunciación.
- `feat: fase 8.1` — evaluación CEFR multi-señal (bandas por destreza + descriptor).

**Estado verde:** backend `191 tests` + `ruff` limpio + `import main` OK; frontend `74 tests`
+ `tsc`/`build` OK.

**Siguiente paso: FASE 9 — Evaluación objetiva del tutor.** Ver
`docs/PLAN-ENDURECIMIENTO.md`.

**Acciones del nuevo gerente (en orden):**
1. Leer `docs/PREMISAS.md` (fuente de verdad de reglas).
2. Leer `docs/PLAN-ENDURECIMIENTO.md` (hoja de ruta Fase 4→10 y protocolo anti-saturación).
3. Leer las secciones 10–12 de este documento (estado de Fases 1–5 y arquitectura resultante).
4. Diseñar los subagentes F7.x en `agentes/endurecimiento/` (autocontenidos, uno a la vez),
   respetando la arquitectura `Router → Service (domain) → Repository (repositories) → SQLite`.
5. Lanzarlos de uno en uno, verificando (backend `pytest` + `ruff`, frontend `tsc` + `vitest`)
   antes de cada commit `feat: ...`.

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

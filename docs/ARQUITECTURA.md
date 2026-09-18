# Arquitectura — English Tutor

> Objetivo: proyecto **modular, estructurado y con responsabilidades claras**.
> Cualquier programador que lea esto debe saber dónde va cada cosa.

## Principio de capas

Separación estricta entre **capa HTTP** (routers), **lógica de negocio** (services),
**contratos de datos** (schemas/types) y **presentación** (components). Una capa no conoce
los detalles internos de otra.

## Backend (`backend/`)

```
backend/
├── main.py              # PUNTO DE ENTRADA: crea la app, monta los routers. Código mínimo.
├── config.py            # Configuración: URLs, rutas de modelos, defaults, versión.
├── dependencies.py      # current_user: el perfil activo sale de la **sesión firmada** (V3.75)
├── routers/             # Capa HTTP: endpoints + validación. SIN lógica de negocio.
│   ├── __init__.py
│   ├── academy.py       # GET/POST /api/academy/levels, enroll, mastery, next, attempts, lessons, objective/assessment, speaking/{level,journey,assessment}
│   ├── assessment.py    # /api/academy/placement*, /api/academy/exam/{level_id}*, /api/academy/level-completions
│   ├── chat.py          # POST /api/chat, POST /api/chat/stream (mode; perfil de la sesión)
│   ├── conversations.py # CRUD /api/conversations (filtrado por el perfil de la sesión) + /{cid}/interaction
│   ├── grammar.py       # POST /api/grammar/analyze, GET /api/grammar/errors (F4)
│   ├── health.py        # /api/health/live, /ready, /dependencies
│   ├── learning.py      # POST/GET /api/learning/events (F4)
│   ├── listening.py     # GET /api/listening/question, POST /api/listening/answer, GET /api/listening/stats (F8; progresión A1→A2→B1)
│   ├── models.py        # GET /api/health, GET /api/models
│   ├── network.py       # GET /api/network (IP, URLs de acceso y modo LAN)
│   ├── profile.py       # GET /api/profile (F4)
│   ├── progress.py      # GET /api/progress, GET /api/progress/history (F6; perfil de la sesión)
│   ├── pronunciation.py # POST /api/pronunciation (audio + texto → score)
│   ├── session.py       # POST/GET/DELETE /api/session (V3.75: firma la cookie et_session)
│   ├── settings.py      # GET/PUT /api/settings (preferencias; solo las del propio perfil)
│   ├── users.py         # GET/POST /api/users, PATCH /api/users/{id} (solo el propio perfil)
│   ├── vocabulary.py    # POST /api/vocabulary/analyze, GET /api/vocabulary (F4)
│   └── voz.py           # POST /api/transcribe, POST /api/tts
├── schemas/             # Contratos de datos (Pydantic).
│   ├── __init__.py
│   ├── academy.py       # Enrollment*, Level*, Objective*, Mastery*, Assessment*, Attempt*
│   ├── chat.py          # ChatMessage, ChatRequest, ChatResponse
│   ├── conversations.py # Conversation, ConversationMeta (con user_id), ConversationUpsert
│   ├── curriculum.py    # CurriculumActivityOut/ObjectiveOut/ModuleOut/LevelOut (vista del contenido)
│   ├── grammar.py       # GrammarAnalyze*, GrammarFinding, GrammarRecurringError (F4)
│   ├── learning.py      # LearningEventType, LearningEvent, LearningEventCreate (F4)
│   ├── listening.py     # ListeningQuestion, ListeningAnswer*, ListeningStats + ListeningLevelOut (F8)
│   ├── profile.py       # LearningProfile, EstimatedBands (F4/F8)
│   ├── pronunciation.py # PronunciationResponse, FluencyStats, PronunciationBreakdown (F7/F8)
│   ├── progress.py      # PronunciationStats, ProgressSummary, Bucket, ProgressHistory (F6)
│   ├── settings.py      # Settings* (preferencias por usuario)
│   ├── users.py         # User, UserCreate, UserUpdate, SessionCreate
│   ├── vocabulary.py    # VocabularyAnalyze*, VocabularyItem (F4)
│   └── voz.py           # TTSRequest, TranscribeResponse
├── domain/              # Servicios de dominio (async, orquestan la lógica).
│   ├── __init__.py
│   ├── academy.py       # orquestación Academy: niveles, mastery, examen, gating (async)
│   ├── conversations.py
│   ├── grammar.py       # análisis de errores + persistencia (F4)
│   ├── learning.py      # eventos de aprendizaje (F4)
│   ├── listening.py     # next_question + submit_answer + stats (con progresión por nivel, F8)
│   ├── pronunciation.py
│   ├── profile.py       # get_profile_summary + get_profile_context (compone el perfil) (F4/F5)
│   ├── progress.py      # get_progress_history: series + racha + dominio + hitos (F6)
│   ├── settings.py      # leer/guardar preferencias por usuario
│   ├── users.py
│   └── vocabulary.py    # extracción + persistencia (F4)
├── repositories/        # Acceso a datos puro (SQLite). Sin reglas de negocio.
│   ├── __init__.py
│   ├── db.py            # conexión, esquema, migraciones, ping
│   ├── academy.py       # enrollments, objective/skill mastery, assessments, level_completions
│   ├── conversations.py
│   ├── grammar.py       # grammar_errors (F4)
│   ├── learning.py      # learning_events (F4)
│   ├── listening.py     # listening_attempts + correct_question_ids (F8)
│   ├── profile.py       # learning_profile (F4)
│   ├── pronunciation.py
│   ├── progress.py      # activity_events (mensajes con modo + pronunciaciones) (F6)
│   ├── settings.py      # tabla settings (clave/valor por usuario)
│   ├── users.py
│   └── vocabulary.py    # vocabulary (F4)
├── services/            # Lógica pura y clientes de infra (llm, voz, análisis).
│   ├── __init__.py
│   ├── academy.py       # mastery determinista (EMA+racha), gating, progresión, evaluación (puro)
│   ├── cefr.py          # constantes CEFR + corte único de banda (level_for_numeric) + recommendations (puros)
│   ├── context.py       # build_system_prompt: modo + perfil → prompt del tutor (F5)
│   ├── curriculum.py    # carga/validación del currículum JSON + ASSESSABLE/PERFORMANCE_SKILLS
│   ├── evaluation.py    # evaluador objetivo del tutor + informe agregado (puros, F9)
│   ├── fluency.py       # compute_fluency: WPM + nivel (puro, F8)
│   ├── grammar.py       # reglas de errores deterministas (F4)
│   ├── interaction.py   # evidencia objetiva de interacción (turnos/latencia) (puro, V1.16)
│   ├── listening.py     # banco de preguntas + score_answer + progresión por nivel (puro, F8)
│   ├── llm.py           # cliente Ollama (chat + streaming; system prompt inyectable)
│   ├── mastery.py       # classify_errors + compute_milestones (puros, F6)
│   ├── network.py       # get_lan_ip + URLs de acceso LAN
│   ├── policy.py        # correctness_guidance por nivel CEFR (puro, F5)
│   ├── phonetics.py     # evaluador compuesto: word_alignment + soundex + composite_score (F7)
│   ├── pronunciation.py # score_pronunciation (puro, delega en phonetics)
│   ├── sessions.py      # firma/verificación de la sesión (HMAC, stdlib; V3.75)
│   ├── speaking.py      # rubric + scoring determinista de speaking + speaking_diagnostic (puro, V1.16)
│   ├── speaking_llm.py  # extracción de evidencia de speaking con LLM (tarea libre)
│   ├── speaking_assessment.py # instrumento Speaking Assessment 1.0 (versionado + agregación)
│   ├── stt.py           # faster-whisper
│   ├── trends.py        # daily_activity + aggregate_series + compute_streak (puros, F6)
│   ├── tts.py           # piper-tts
│   └── vocabulary.py    # extract_words (puro, F4)
├── curriculum/          # contenido curricular versionado como JSON (a1.json, a2.json, assessments.json, speaking_assessment.json)
├── models/              # pesos descargados (Whisper/Piper). GITIGNORED.
├── data/                # base SQLite (tutor.db). GITIGNORED.
├── tests/               # pruebas (pytest).
│   ├── conftest.py      # asegura el import desde backend/
│   ├── test_academy.py  # currículum, mastery por objetivo, gating, examen
│   ├── test_activity.py # F6
│   ├── test_api_security.py
│   ├── test_cefr_evaluation.py # F8
│   ├── test_chat_integration.py
│   ├── test_chat_profile.py # F5
│   ├── test_context.py      # F5
│   ├── test_cors.py
│   ├── test_cross_user_isolation.py
│   ├── test_domain_async.py
│   ├── test_evaluation.py # F9
│   ├── test_evaluation_report.py # F9
│   ├── test_fluency.py  # F8
│   ├── test_foreign_keys.py
│   ├── test_grammar.py  # F4
│   ├── test_health.py
│   ├── test_identity_source.py # la identidad no la elige el cliente (V3.75)
│   ├── test_learning_events.py # F4
│   ├── test_listening.py # F8
│   ├── test_mastery.py # F6
│   ├── test_modes.py
│   ├── test_network.py
│   ├── test_phonetics.py # F7
│   ├── test_policy.py   # F5
│   ├── test_profile.py  # F4
│   ├── test_progress.py
│   ├── test_progress_history.py # F6
│   ├── test_pronunciation.py
│   ├── test_public_surface.py # la superficie sin sesión, declarada (V3.75)
│   ├── test_robustness.py
│   ├── test_schemas.py
│   ├── test_sessions.py # firma, cookie y 401 de la sesión (V3.75)
│   ├── test_settings.py
│   ├── test_store.py
│   ├── test_store_append_only.py
│   ├── test_store_isolation.py
│   ├── test_supply_chain_v375.py # pines por SHA, auditoría y Dependabot (V3.75)
│   ├── test_trends.py  # F6
│   ├── test_user_profile.py
│   ├── test_users.py
│   ├── test_users_self_only.py # cada uno edita lo suyo (V3.75)
│   └── test_vocabulary.py # F4
├── scripts/             # scripts de utilidad.
│   ├── eval_model.py    # evalúa un modelo como tutor (M5)
│   ├── eval_tutor.py    # evalúa un modelo con el corpus canónico (F9)
│   ├── listening_check.py # verificación determinista de la progresión de listening (sin red)
│   └── smoke_test.py    # verifica el servidor en ejecución
├── download_models.py   # script de descarga de modelos de voz (1ª vez)
├── requirements.txt
└── requirements-dev.txt # incluye pytest + httpx + ruff
```

### Responsabilidades backend
- **`main.py`**: solo crear la app y registrar routers. Nada de lógica.
- **`routers/`**: parsear la petición, validar con schemas, llamar a un service de `domain/`.
- **`domain/`**: servicios asíncronos que orquestan la lógica (delegan en `repositories/` vía
  `run_in_threadpool`).
- **`repositories/`**: acceso a datos puro (SQLite); sin reglas de negocio.
- **`services/`**: lógica pura/testable (scoring, análisis determinista, motor de mastery) y
  clientes de infra (Ollama, whisper, piper). No importa FastAPI.
- **`schemas/`**: tipos Pydantic. Son el contrato de la API.
- **`config.py`**: constantes de entorno/configuración, sin lógica.

### Academy (currículum CEFR + Mastery Engine)

La Academy separa **contenido** (qué debe aprender) de **evidencia** (qué sabe), con un motor
de mastery determinista que decide el dominio sin LLM-juez.

- **Contenido**: `backend/curriculum/*.json` (`a1.json`, `a2.json`, `assessments.json`) como
  fuente de verdad, editable sin tocar lógica. `services/curriculum.py` lo carga y valida
  (Pydantic) y define `CANONICAL_SKILLS`, `ASSESSABLE_SKILLS` (grammar/vocabulary/reading/
  listening) y `PERFORMANCE_SKILLS` (speaking/writing/pronunciation).
- **Mastery Engine** (`services/academy.py`, puro): `next_mastery_state` (EMA + `confidence` +
  `streak`; sin `MAX`, con decay), `objective_progress` (exige `score ≥ threshold` **y**
  `attempts ≥ minimum_attempts`), `mastered_objective_ids` (dominio por `(user, level, objective,
  skill)`), `unlock_state` (gating secuencial) y `exam_result`.
- **Orquestación** (`domain/academy.py`, async): compone currículum + repositorios y aplica el
  gating (`enroll`, `submit_exam`) sin saltarse la progresión CEFR (A1 → A2 → B1 → ...).
- **Persistencia** (`repositories/academy.py`): `academy_enrollments`, `academy_objective_mastery`,
  `academy_skill_mastery`, `academy_assessment_results`, `academy_level_completions`.
- **HTTP** (`routers/academy.py` + `routers/assessment.py`): exponen niveles, mastery, evaluación
  de objetivo, examen de nivel y completitud. El gating se valida **en el backend**, no solo en
  el frontend.

Principio rector: **la IA genera evidencia; el Mastery Engine determinista decide el dominio.**

**Modelo conceptual de nivel (V3.2.x):** la especificación normativa de qué significa
"estar en un nivel" y cómo se demuestra por competencia vive en
`docs/CONSTITUCION-PEDAGOGICA.md` (Practice Level / Mastery / Estimated CEFR /
Demonstrated CEFR, 4 estados por competencia, Mastery Gate general). Ninguna capa
debe leer "cantidad de ítems o palabras → nivel CEFR" (auditoría en
`docs/audit/H-NIVELACION-PEDAGOGICA.md`, hallazgos H1–H7).

## Frontend (`frontend/src/`)

```
frontend/src/
├── main.tsx
├── App.tsx              # Orquesta: compone la página (workspace multi-panel redimensionable).
├── api/                 # Cliente HTTP (única capa que habla con el backend).
│   ├── client.ts        # fetch base (manejo de errores, JSON).
│   ├── academy.ts       # niveles, enroll, mastery, examen, attempts, objective/assessment.
│   ├── chat.ts          # chat normal + streaming (envía mode; el perfil va en la sesión).
│   ├── conversations.ts # CRUD de conversaciones (el perfil va en la sesión).
│   ├── learning.ts      # getProfile + analyzeText + getEvents (F4/F6).
│   ├── listening.ts     # getListeningQuestion + submitListeningAnswer + getListeningStats (F8).
│   ├── pronunciation.ts # checkPronunciation (audio + texto → score).
│   ├── progress.ts      # getProgress + getProgressHistory (resumen + histórico) (F6).
│   ├── session.ts       # openSession + getSession + closeSession (V3.75).
│   ├── settings.ts      # getSettings + putSettings (preferencias del perfil de la sesión).
│   ├── users.ts         # listUsers, createUser, updateUser.
│   └── voz.ts           # transcribe + tts.
├── components/          # Presentación pura (reciben props, no hacen fetch).
│   ├── Academy.tsx      # currículum CEFR: niveles, objetivos, mastery y examen (núcleo Academy)
│   ├── AppearancePanel.tsx # panel de apariencia: tema, acento, tamaño, densidad (M16)
│   ├── ChatMessage.tsx
│   ├── Composer.tsx
│   ├── HandsFreeToggle.tsx  # activar/parar modo manos libres + estado (M10)
│   ├── HelpDialog.tsx   # ayuda para no ingenieros enlazada a docs/ (M16)
│   ├── LearningProfile.tsx  # panel del perfil: CEFR + bandas por destreza + recomendaciones (F4/F8)
│   ├── ListeningPractice.tsx # comprensión auditiva: TTS + responder + nivel/progreso (F8)
│   ├── MicButton.tsx
│   ├── ModeBar.tsx      # selector de modo de tutor
│   ├── ProfileDialog.tsx # editar perfil: nombre, avatar, color (M14)
│   ├── ProgressDashboard.tsx # dashboard de progreso real: tendencias, racha, dominio, hitos (F6)
│   ├── PronunciationPractice.tsx # feedback fonético + fluidez (WPM) (F7/F8)
│   ├── ResizeHandle.tsx # asa redimensionable entre paneles (M14)
│   ├── Sidebar.tsx      # lista de conversaciones
│   ├── SpeakButton.tsx
│   ├── TutorQualityPanel.tsx # panel de calidad del tutor (F9)
│   ├── UserAvatar.tsx   # avatar (imagen → emoji → iniciales) (M14)
│   └── UserMenu.tsx     # selector/perfil de usuario (M14)
├── hooks/               # Estado y lógica de UI.
│   ├── useAppearance.ts # apariencia por usuario: tema/acento/tamaño/densidad + persistencia (M16)
│   ├── useChat.ts       # incluye estado de usuario y aislamiento por perfil
│   └── useHandsFree.ts  # bucle de voz continua + VAD por energía (M10)
├── types/               # Tipos compartidos (espejo de los schemas del backend).
│   └── api.ts           # incluye User y user_id en ConversationMeta
├── utils/               # Funciones puras (testables, con su *.test.ts junto).
│   ├── appearance.ts    # presets de acento/tamaño/densidad + parse/serialize (M16)
│   ├── avatar.ts        # color/emoji/iniciales deterministas (M14)
│   ├── cefr.ts          # cefrTone, cefrLabel, bandLabel (F4/F8)
│   ├── fluency.ts       # wpmLabel, fluencyLevelLabel (F8)
│   ├── image.ts         # resizeImageToDataUrl (M14)
│   ├── layout.ts        # dimensiones de paneles + clamp/parse/serialize (M14)
│   ├── modes.ts         # MODES + isTutorMode
│   ├── progress.ts      # formatScore/formatAverage/pronunciationLevelLabel + bucketLabel/eventLabel (M9/F6)
│   ├── pronunciationFeedback.ts # joinWords/feedbackHints/wordsCorrectLabel (puros, F7)
│   ├── session.ts       # planSession: adoptar o abrir sesión al arrancar (puro, V3.75)
│   ├── sse.ts           # parseo de eventos SSE
│   ├── theme.ts         # resolveInitialTheme (M8)
│   ├── title.ts         # deriveTitle
│   ├── tutorEvaluation.ts # evaluador del tutor: ratios + scores + medias (puro, F9)
│   ├── users.ts         # nextDefaultUserName
│   └── vad.ts           # VAD: rms + shouldEndUtterance + constantes (M10)
├── scripts/             # scripts de utilidad.
│   └── check.ps1        # tsc + vitest
├── vitest.config.ts
└── index.css             # tokens de diseño, tema claro/oscuro, responsive (M8)
```

> **Sistema de diseño (M8/M16):** los tokens viven en `:root` de `index.css`
> (`--color-*`, `--font-*`, `--text-*`, `--space-*`, `--radius-*`, `--shadow-*`),
> con el tema claro sobrescrito en `:root[data-theme="light"]`. El tema, el acento,
> el tamaño de letra y la densidad se controlan desde `hooks/useAppearance.ts` +
> `utils/appearance.ts` y se aplican vía `data-theme`/`data-accent`/`data-font`/`data-density`
> en `<html>`. La apariencia se persiste por usuario (backend `settings` + `localStorage`).

### Responsabilidades frontend
- **`api/`**: único lugar donde se hace `fetch`. Expone funciones tipadas.
- **`components/`**: solo renderizar y emitir eventos vía props. No hacen peticiones.
- **`hooks/`**: manejan estado (mensajes, loading) y llaman a `api/`.
- **`types/`**: interfaces TypeScript compartidas.
- **`App.tsx`**: composición de alto nivel, mínimo estado.

## Launcher (`launcher/`)

```
launcher/
├── launcher.py          # PUNTO DE ENTRADA: GUI mínima (tkinter), prepara y arranca/para la app
├── ui.py                # paleta, iconos, dots de estado y lectura de logs (puro, sin tkinter)
├── core.py              # lógica pura: rutas, comandos de arranque, normalización de estado
├── process_manager.py   # prepara el entorno (cert TLS + build si falta) y gestiona uvicorn
├── status.py            # lectura de estado: HTTP (health) + SQLite (contadores/usuarios)
├── browser_cookies.py   # diagnóstico de cookies de Chrome/Edge/Brave/Vivaldi/Opera/Firefox
├── state_store.py       # persistencia visual: tamaño/posición de ventana y paneles
├── make_icon.ps1        # genera icon.ico (System.Drawing, Windows)
├── install_shortcut.ps1 # crea el acceso directo del escritorio (English Tutor.lnk)
├── allow-firewall.ps1   # abre TCP 8000 (API + UI) en el firewall (requiere admin)
├── icon.ico             # icono del acceso directo
├── pyproject.toml       # configuración de ruff (mismas reglas que el backend)
├── logs/                # logs de backend/UI (gitignored)
├── state.json           # estado de la UI persistido (gitignored)
└── tests/               # pytest (conftest.py + test_core/test_status/test_browser_cookies/
                         #         test_ui/test_state_store/test_process_manager/
                         #         test_preflight_v373/test_lan_ip_v373/test_lan_mode) — 125
                         #         funciones de test (142 casos con parametrización), en CI
                         #         (job `launcher`)
```

### Responsabilidades launcher
- **`launcher.py`**: GUI `tkinter` (ventana de estado con servicios, BD y usuarios; botones
  Iniciar/Detener/Abrir/Actualizar; paneles colapsables). Solo orquesta; no contiene lógica de
  negocio.
- **`ui.py`**: constantes de estilo (colores, iconos, puntos de estado) y lectura de logs.
- **`core.py`**: funciones puras y testables (resolver rutas, construir comandos, normalizar
  estado de salud y contadores).
- **`process_manager.py`**: prepara el entorno (genera el certificado TLS autofirmado y
  compila `frontend/dist` si falta) y gestiona el ciclo de vida del **proceso de
  producto** (uvicorn), con matado del árbol de procesos en Windows (`taskkill /T /F`).
- **`status.py`**: obtiene el estado real: `/api/health/dependencies` (HTTP) y consultas de
  solo lectura a la BD SQLite (contadores globales y usuarios).
- **`browser_cookies.py`**: diagnóstico (solo lectura) de las cookies de los navegadores
  soportados, para orientar problemas de acceso local. Informa de **si hay sesión**
  (`et_session`) y **enmascara su valor**: es un token firmado y verlo en pantalla sería
  poder usarlo (V3.75).
- **`state_store.py`**: persistencia de la disposición visual (tamaño/posición de ventana y
  paneles colapsados) en `state.json`.
- **`*.ps1`**: utilidades de Windows para generar el icono, crear el acceso directo y abrir el
  puerto en el firewall.

### Runtime de producto (re-declarado en V3.72, eje UA — cierre de RC-01)

El producto se ejecuta como **un solo proceso** que arranca el launcher:

| Pieza | Se sirve con | Dónde |
|---|---|---|
| API + UI | `uvicorn main:app --host <127.0.0.1\|0.0.0.0> --port 8000 --ssl-certfile … --ssl-keyfile …` (un solo proceso, **sin** `--reload`) | `launcher/core.py::backend_command` |
| UI compilada (`frontend/dist`) | *StaticFiles* en `/assets` + *fallback* SPA, servidos por el backend | `backend/services/frontend_dist.py::mount_frontend` |
| Certificado TLS autofirmado | Generado (idempotente) antes de arrancar | `backend/scripts/ensure_tls_cert.py` |

- `npm run build` (`tsc && vite build`) produce `frontend/dist`, que **no se versiona**:
  el launcher lo compila la primera vez si falta (`process_manager.ensure_frontend_dist`).
- **Consecuencia declarada:** **Node + npm son requisito de COMPILACIÓN/instalación, no de
  EJECUCIÓN**. `RC-01` queda **cerrado**; ver `docs/audit/RC-RUNTIME-PRODUCTO.md`.
- `npm run dev` (dev server de Vite en `:5173` con proxy `/api`) se conserva como **modo de
  desarrollo** con HMR (`.vscode/launch.json`), no como runtime de producto.
- **Modo desarrollo vs. producto (V3.73):** sin `dist` el backend arranca igual (solo API)
  **cuando se lanza a mano** (`uvicorn main:app`, fail-open). El launcher, en cambio,
  arranca el producto con `ENGLISH_TUTOR_REQUIRE_UI=1` y **no lo arranca** si falta el
  artefacto: es **fail-closed** y no puede parecer listo sin interfaz.
- Fijado por test en `backend/tests/test_docs_drift_v372.py`,
  `backend/tests/test_serve_frontend_v373.py` y `launcher/tests/test_preflight_v373.py`.

### Red local declarada (V3.73)

- **Descubrimiento de la IP de LAN:** `backend/services/net_interfaces.py` enumera
  las direcciones del propio equipo (`getaddrinfo`/`gethostbyname_ex` del nombre
  local) y `select_lan_ipv4` elige la primera utilizable prefiriendo rangos
  privados. **No consulta ninguna dirección pública**: hasta V3.72 se usaba un
  socket UDP «connect» a `8.8.8.8`, perezoso y sin paquetes, pero con una
  referencia externa dentro de una app 100 % local. Override declarado:
  `ENGLISH_TUTOR_LAN_IP` (equipos con varias NIC o VPN).
- Delegan en él `services/network.py::get_lan_ip` y `services/tls_cert.py::_local_ip`;
  el launcher replica el algoritmo puro (no puede importar el backend).
- Fijado por test en `backend/tests/test_net_interfaces_v373.py`,
  `launcher/tests/test_lan_ip_v373.py` y `backend/tests/test_docs_drift_v373.py`.

### Frontera de red: loopback por defecto, LAN opt-in (V3.73.x)

- **Por defecto la app escucha en `127.0.0.1`** y **no** acepta orígenes de red
  privada. Hasta V3.73.6 se enlazaba siempre a `0.0.0.0` y la regex de CORS
  aceptaba cualquier IP privada: exponerse a la LAN era el comportamiento por
  defecto sin que nadie lo hubiera pedido.
- **El modo LAN se declara con `ENGLISH_TUTOR_LAN=1`** —o con el botón «Activar red
  local» del panel de acceso del launcher, que lo declara y **reinicia el servidor**
  para aplicarlo— y lo propaga el launcher en el entorno del backend
  (`launcher/core.py::backend_env`), de modo que la interfaz a la que se enlaza uvicorn
  (`backend_host`) y la política de orígenes salen de la **misma** decisión (`lan_mode`)
  y no pueden discrepar. Se lee **fail-closed**: ausente o no afirmativo ⇒ cerrado.
- Las dos mitades de la política de origen son `security.origin_allowed` (la que
  corta con **403** en métodos no seguros) y el patrón de `CORSMiddleware`; un
  candado comprueba que dicen lo mismo sobre los mismos orígenes. El propio
  equipo (loopback) entra en los dos modos: la frontera es la LAN, no lo local.
- Mientras no exista autenticación por perfil (**P0 abierto**, ver
  `docs/audit/PARKED.md`), cualquiera que alcance el puerto ve y escribe los datos
  del alumno: por eso exponerse es una decisión explícita. `/api/network` informa
  del modo, y ni el panel del launcher ni `ConnectDeviceCard` anuncian una URL de
  LAN cuando no responde.
- Fijado por test en `backend/tests/test_lan_mode.py` y
  `launcher/tests/test_lan_mode.py` (incluida la deriva documental: si esta
  frontera desaparece de README/`PREMISAS.md`/este documento, fallan).

### Identidad: la firma el servidor (V3.75)

- **Hasta V3.74 la identidad la elegía el cliente.** El perfil activo viajaba en
  **cada** URL (`?user_id=…`), así que quien alcanzara la API —otro equipo de la
  LAN, con la Frontera de red arriba— leía y escribía los datos de cualquier
  perfil. Además la cookie que recordaba la elección (`et_user_id`, hoy retirada)
  la escribía **JavaScript**, no el servidor.
- **Ahora la emite el servidor.** `POST /api/session` (`routers/session.py`)
  comprueba que el perfil existe y devuelve una cookie `et_session`: token
  `base64url(payload).base64url(hmac_sha256(secreto, payload))` (`services/sessions.py`,
  stdlib, comparación en tiempo constante) con **`HttpOnly`**, `SameSite=Lax` y
  `Secure` cuando la página va por HTTPS. `dependencies.current_user` la verifica
  en cada petición: sin cookie, manipulada o caducada ⇒ **401 `SESSION_REQUIRED`**.
  El `?user_id=` de la URL ya **no** significa nada.
- **Qué cierra y qué no.** Cierra el **alcance** (el cliente no elige ni puede
  forjar la identidad), **no** el acceso: `POST /api/session` acepta cualquier
  `user_id` existente y `GET/POST /api/users` siguen sin credencial —el producto es
  «sin cuentas, sin contraseñas» por diseño—. Autenticar de verdad es la Fase 3 del
  P0, una decisión de producto (`docs/audit/PLAN-P0-IDENTIDAD.md`).
- **Bordes de autorización:** `PATCH /api/users/{id}` y `PUT /api/settings` exigen
  sesión y que el id coincida con el de la sesión del propio perfil (si no, **403**).
- **El secreto de firma** vive en `backend/data/session.secret` (gitignored) y
  **no** viaja en los backups: un ZIP restaurado no puede firmar sesiones. Restaurar
  **no** borra el secreto del equipo receptor.
- **El launcher** informa de **si hay sesión** en el navegador, con el valor
  **enmascarado**: es un token y verlo en pantalla sería poder usarlo.
- Fijado por test en `backend/tests/test_sessions.py` (firma, caducidad, atributos
  de cookie, 401), `test_identity_source.py` (el `?user_id=` no manda) y
  `test_users_self_only.py` (403 al editar lo ajeno). El adaptador de
  `backend/tests/conftest.py` traduce el `?user_id=` de las suites históricas a una
  sesión firmada, para que las 109 suites prueben el camino nuevo sin reescribirse.

### Superficie sin sesión: declarada y acotada (V3.75, cierra VG-N6)

La auditoría de V3.73 dejó abierto (`VG-N6`) que tres endpoints respondían **sin
credencial**: `/api/system/status`, `/api/network` y `/api/models`. Se **aceptan de
forma explícita** —y se fijan por test— por tres razones: (1) son **reconocimiento
barato** (modelos instalados, IP/hostname de LAN, trabajos de generación en curso,
rechazos por rate limit de 60 s) que **no** permite leer ni escribir datos de ningún
alumno; (2) quien puede alcanzarlas ya está dentro para todo lo demás —la frontera
real es la **red** (loopback por defecto, LAN opt-in), no esta lista—; y (3) el
producto **no tiene cuentas** que exigirles (Fase 3 del P0).

**Responden sin sesión** (y deben seguir haciéndolo: el launcher y la puerta de
perfil las usan antes de que exista ningún perfil): `/` · `/api` · `/api/health` ·
`/api/health/live` · `/api/health/ready` · `/api/health/dependencies` ·
`/api/models` · `/api/network` · `/api/system/status` · `GET/POST /api/users` ·
`POST /api/session` (abrir sesión es justo lo que aún no existe).

**Exigen sesión firmada** (401 `SESSION_REQUIRED`): todo lo que lee o escribe datos
del alumno (`/api/settings`, `/api/profile`, `/api/progress`, `/api/conversations`,
`/api/vocabulary`, `/api/grammar/errors`, `/api/academy/*`, `/api/listening/*`,
`/api/pronunciation`, `/api/chat`…). **Exigen PIN de administración**
(`X-Admin-Pin`, fail-closed sin `ADMIN_PIN`): `/api/system/backup*` y
`/api/system/restore`.

Cuando llegue la **Fase 3** (autenticación real), cada ruta de la primera lista
recibe su credencial o pasa a admin; hasta entonces la lista está escrita aquí y
`backend/tests/test_public_surface.py` la comprueba en las dos direcciones (que lo
declarado sin sesión siga respondiendo, y que lo declarado con sesión **no** salga
sin ella), además de fallar si esta sección desaparece del documento.

## Regla de oro
> Si vas a añadir una feature, su código va en su módulo. No se "pega" lógica nueva en
> `main.py` ni en `App.tsx`. Un archivo = una responsabilidad.

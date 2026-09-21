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
│   └── voz.py           # POST /api/transcribe, POST /api/tts (voz opcional validada; V3.75.5)
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
│   └── voz.py           # TTSRequest (text/language/voice), TranscribeResponse
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
│   ├── tts.py           # piper-tts (pick_requested_voice: valida la voz pedida; V3.75.5)
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
│   ├── listening.ts     # getListeningQuestion + audio por voz + submitListeningAnswer (F8, V3.75.5).
│   ├── pronunciation.ts # checkPronunciation (audio + texto → score).
│   ├── progress.ts      # getProgress + getProgressHistory (resumen + histórico) (F6).
│   ├── session.ts       # openSession + getSession + closeSession (V3.75).
│   ├── settings.ts      # getSettings + putSettings (preferencias del perfil de la sesión).
│   ├── users.ts         # listUsers, createUser, updateUser.
│   └── voz.ts           # transcribe + tts (envía la voz pedida, validada en el backend).
├── components/          # Presentación pura (reciben props, no hacen fetch).
│   ├── Academy.tsx      # currículum CEFR: niveles, objetivos, mastery y examen (núcleo Academy)
│   ├── AppearancePanel.tsx # panel de apariencia: tema, acento, tamaño, densidad (M16)
│   ├── ChatMessage.tsx
│   ├── Composer.tsx
│   ├── HandsFreeToggle.tsx  # activar/parar modo manos libres + estado (M10)
│   ├── HelpDialog.tsx   # ayuda para no ingenieros enlazada a docs/ (M16)
│   ├── ItemReplayButton.tsx # altavoz de después de responder: ítem compuesto (texto+pregunta+opciones+clave) en acento A o B, con STOP (V3.75.5/V3.75.6)
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
│   └── VoicePicker.tsx  # elige voz A (perfil), voz B (segundo acento), prueba A/B y lectura al repetir (V3.75.5/V3.75.6)
├── hooks/               # Estado y lógica de UI.
│   ├── useAppearance.ts # apariencia por usuario: tema/acento/tamaño/densidad/esquema de niveles + persistencia (M16)
│   ├── useChat.ts       # incluye estado de usuario y aislamiento por perfil
│   ├── useHandsFree.ts  # bucle de voz continua + VAD por energía (M10)
│   └── useVoiceChoice.ts # store de módulo: catálogo + pareja A/B del perfil + lectura al repetir + persistencia (V3.75.5/V3.75.6)
├── types/               # Tipos compartidos (espejo de los schemas del backend).
│   └── api.ts           # incluye User y user_id en ConversationMeta
├── utils/               # Funciones puras (testables, con su *.test.ts junto).
│   ├── appearance.ts    # presets de acento/tamaño/densidad/esquema de niveles + parse/serialize (M16)
│   ├── avatar.ts        # color/emoji/iniciales deterministas (M14)
│   ├── cefr.ts          # cefrLevelKey/levelClass/bandToLevelKey, cefrLabel, bandLabel (F4/F8)
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
│   ├── vad.ts           # VAD: rms + shouldEndUtterance + constantes (M10)
│   └── voices.ts        # locale/acento/etiqueta de voz, sugerencia de la B y texto de repetición con alcance (V3.75.5/V3.75.6)
├── scripts/             # scripts de utilidad.
│   └── check.ps1        # tsc + vitest
├── vitest.config.ts
└── index.css             # tokens de diseño, tema claro/oscuro, responsive (M8)
```

> **Sistema de diseño (M8/M16):** los tokens viven en `:root` de
> `styles/legacy.css` (histórico) e `index.css` —`--color-*`, `--font-*`,
> `--text-*`, `--space-*`, `--radius-*`, `--shadow-*`—, con el tema claro
> sobrescrito en `:root[data-theme="light"]`. El tema, el acento, el tamaño de
> letra, la densidad y el **esquema de color de los niveles** se controlan desde
> `hooks/useAppearance.ts` + `utils/appearance.ts` y se aplican vía
> `data-theme`/`data-accent`/`data-font`/`data-density`/`data-levels` en `<html>`.
> La apariencia se persiste por usuario (backend `settings` + `localStorage`); el
> backend no tiene que saber nada de estos campos: `PUT /api/settings` guarda
> clave/valor libre.
>
> **Rampa de niveles (V3.75.4):** cada nivel CEFR —Pre-A1, A1, A2, B1, B2, C1, C2
> y el cajón «sin dato»— tiene su propio color. `utils/cefr.ts::levelClass(nivel)`
> devuelve la clase **estática** (`.lv-a2`) que consume tres tokens declarados por
> paso (`--level-<paso>-fg/bg/border`); el relleno y el borde se **derivan** de la
> tinta con `color-mix()`, así que un esquema nuevo son 7 hexes y no 21. Los tres
> esquemas son `traffic` (por defecto, `data-levels` ausente), `spectrum` y `mono`
> (siete intensidades del acento, sin un solo hex propio). Las clases `.lv-*` se
> declaran **sin capa** al final de `legacy.css` a propósito: el color del nivel
> no debe poder perderse frente a una utilidad de Tailwind de la misma línea.
> `scripts/contrast_audit.mjs` mide cada paso sobre su relleno compuesto en los 3
> esquemas, los 2 temas y los 7 acentos de «Monocromo», y es guarda de CI.

> **Pantallas de característica (V3.75.3):** las prácticas y pantallas que crecieron
> más allá de un componente viven en `frontend/src/features/<área>/` (p. ej.
> `features/listening/`, `features/progress/`), no en `components/`. Ahí está la
> nueva `features/analysis/AnalysisScreen.tsx`: el **análisis de evolución global**
> (posición CEFR, actividad real con su agrupación temporal, tríada, destrezas y
> escalera), en la ruta auxiliar `/analisis` (`router/paths.ts::ANALYSIS_PATH`),
> abierta desde la cabecera junto al usuario. Sustituye al panel flotante
> `components/AnalysisPanel.tsx`, **borrado** en esta versión: en V3.1 se había
> quedado sin analítica propia (calidad del tutor y un enlace a MI PROGRESO) y solo
> se encontraba dentro del ejercicio. Consume los endpoints que ya existían
> (`student-model`, `progress/history`, `learning/events`, `cefr-ladder`) y el
> `TutorQualityPanel` recibe los turns de la sesión en curso, que era lo único en
> vivo que aportaba el panel retirado.

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
├── admin.py             # escritura de administración: cliente de `/api/admin/*` (V3.77)
├── browser_cookies.py   # diagnóstico de cookies de Chrome/Edge/Brave/Vivaldi/Opera/Firefox
├── state_store.py       # persistencia visual: tamaño/posición de ventana y paneles
├── config_store.py      # persistencia de preferencias: modo LAN + PIN admin (config.json)
├── make_icon.ps1        # genera icon.ico (System.Drawing, Windows)
├── install_shortcut.ps1 # crea el acceso directo del escritorio (English Tutor.lnk)
├── allow-firewall.ps1   # abre TCP 8000 (API + UI) en el firewall (requiere admin)
├── icon.ico             # icono del acceso directo
├── pyproject.toml       # configuración de ruff (mismas reglas que el backend)
├── logs/                # logs de backend/UI (gitignored)
├── state.json           # estado de la UI persistido (gitignored)
├── config.json          # preferencias: modo LAN + PIN admin (gitignored, V3.77)
└── tests/               # pytest (conftest.py + test_core/test_status/test_browser_cookies/
                         #         test_ui/test_state_store/test_config_store/
                         #         test_process_manager/test_preflight_v373/
                         #         test_lan_ip_v373/test_lan_mode/
                         #         test_admin_pin/test_admin_client) — 188
                         #         funciones de test (205 casos con parametrización), en CI
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
- **`admin.py`** (V3.77): el **único** sitio del launcher que escribe en el producto. Habla
  con `/api/admin/*` con el PIN en la cabecera `X-Admin-Pin`, y devuelve `AdminResult` en vez
  de lanzar, para que la GUI pueda enseñar «no se pudo» sin que se le caiga el hilo. No toca
  la BD directamente aunque tenga el fichero a mano: el borrado de un perfil tiene que pasar
  por el mismo sitio que el resto (validación, copia previa, tabla de solicitudes) o habría dos
  definiciones de «purgar» y la del launcher sería la que nadie prueba.
- **`browser_cookies.py`**: diagnóstico (solo lectura) de las cookies de los navegadores
  soportados, para orientar problemas de acceso local. Informa de **si hay sesión**
  (`et_session`) y **enmascara su valor**: es un token firmado y verlo en pantalla sería
  poder usarlo (V3.75).
- **`state_store.py`**: persistencia de la disposición visual (tamaño/posición de ventana y
  paneles colapsados) en `state.json`.
- **`config_store.py`** (V3.75.3): persistencia de las **preferencias** del launcher en
  `config.json`, separada del estado visual a propósito. Hoy guarda dos: el modo LAN
  (`{"lan": false}` por defecto, fail-closed) y el **PIN de administración** (`{"admin_pin":
  ""}`, también fail-closed, V3.77). Se lee **al arrancar**, antes de construir la interfaz
  (`LauncherApp.__init__` → `core.apply_lan_config` / `core.apply_admin_config`), y se escribe
  **en cada cambio** (`toggle_lan_mode`, `set_admin_pin`), no al cerrar: reabrir el launcher
  conserva el modo declarado y el panel de acceso ya lo muestra. El PIN se declara además en el
  entorno para que `backend_env()` lo herede al arrancar uvicorn: sin eso, el launcher tendría
  un PIN y el backend otro. Reexpone la decisión de §5.8 de
  `docs/audit/PLAN-P0-IDENTIDAD.md`; el detalle y su porqué están ahí.
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
`/api/pronunciation`, `/api/chat`…) y **`PUT /api/session/pin`** (V3.76: cambiar un
secreto del perfil). **Exigen PIN de administración**
(`X-Admin-Pin`, fail-closed sin `ADMIN_PIN`): `/api/system/backup*` y
`/api/system/restore`.

**V3.77 — la única escritura sin sesión, y por qué se acepta.**
`POST /api/profile-requests` responde **sin sesión** porque quien pide un perfil
todavía no tiene ninguno: exigirle identidad para pedir identidad sería un círculo.
Se acepta con cuatro acotaciones, todas activas y con test propio
(`backend/tests/test_profile_requests_v377.py`): cupo estrecho por IP
(`security._PATH_LIMITS`, 5/min), tope de pendientes (20), una petición por nombre
y longitudes máximas. Y sobre todo: **es inerte** — registra una fila y **no crea
ningún perfil**, no toca la evidencia de nadie y solo el webmaster, desde el
lanzador, la resuelve. Lo peor que consigue quien la llame es que el webmaster vea
una petición que puede rechazar. La de baja (`POST /api/profile-requests/delete`)
**sí** exige sesión, y no lleva `{id}` en la ruta: no existe la forma de pedir la
baja del perfil de otro.

**V3.77 — la administración de perfiles es local por construcción.**
`/api/admin/*` (crear, desactivar, purgar y resolver solicitudes) exige **dos**
llaves: el PIN de administración **y** que la petición llegue del propio equipo
(`dependencies.require_admin_local`). El PIN, además, deja de salir solo de una
constante sin fuente: `config.admin_pin()` lee `ENGLISH_TUTOR_ADMIN_PIN`, que es
como lo declara el lanzador al arrancar el backend. Sigue siendo **fail-closed**:
sin PIN declarado, la administración está deshabilitada, no abierta. Y `POST
/api/users` deja de ser un alta abierta por LAN: crear un perfil es una decisión
del webmaster; por la red se pasa a **solicitar**.

Cuando llegue la **Fase 3** (autenticación real), cada ruta de la primera lista
recibe su credencial o pasa a admin; hasta entonces la lista está escrita aquí y
`backend/tests/test_public_surface.py` la comprueba en las dos direcciones (que lo
declarado sin sesión siga respondiendo, y que lo declarado con sesión **no** salga
sin ella), además de fallar si esta sección desaparece del documento.
`PUT /api/session/pin` se comprueba en un **test aparte** y no en esa lista: se
recorre con `GET` y esa ruta responde **405**, no 401, así que mezclarlas habría
debilitado el candado.

### PIN opcional por perfil (V3.76 · Fase 3 del P0, mitigación y no autenticación)

`POST /api/session` acepta un `pin` **opcional**. Si el perfil tiene PIN
(`users.pin_hash != ''`) y no se envía o no cuadra, responde **`401
PIN_REQUIRED` / `401 PIN_INVALID`**; con el freno de intentos activo,
**`429 PIN_THROTTLED`** con `Retry-After`. Un perfil **sin** PIN abre como siempre:
es una **mitigación opt-in**, no un cambio del modelo de identidad.

- **El hash**: `backend/services/pins.py`, **PBKDF2-HMAC-SHA256** (200 000
  iteraciones, sal por perfil, iteraciones dentro del valor) y comparación con
  `hmac.compare_digest`. Stdlib puro. `User.has_pin` es lo único que viaja; el
  repositorio **saca el hash** del diccionario del perfil (`_row_to_user`) para que
  no pueda serializarse por descuido.
- **El freno**: 5 fallos no frenan; después el retardo dobla (1 s, 2 s, 4 s…) con
  techo de 300 s, **por perfil** y **se limpia al acertar**. Es la pieza que
  sostiene un PIN de 4-6 dígitos; `/api/session` entra además en `_PATH_LIMITS`
  (120/min) como primera valla, no como defensa.
- **Poner, cambiar y retirar**: `PUT /api/session/pin`, **bajo la sesión** y sin
  `{id}` en la ruta; cambiar o retirar **exige el PIN anterior**. El hash **sí**
  viaja en el backup (es estado del perfil, dentro de la BD) mientras
  `session.secret` seguirá sin viajar.
- **Lo que NO es** (y está declarado en `docs/audit/PARKED.md`): no hay identidad de
  persona ni recuperación, la cookie de un año protege ante otro equipo sin la
  cookie y no ante quien use tu equipo desbloqueado, `GET /api/users` sigue
  enumerando nombres, el freno vive en memoria del proceso y el **P0 sigue abierto
  para el producto** porque quien no active el PIN entra sin credencial.
- Fijado por test en `backend/tests/test_pin.py` (31 casos), y en frontend por
  `api/session.test.ts`, `utils/session.test.ts`, `utils/pin.test.ts`,
  `components/ProfileGate.test.tsx` y `hooks/useChat.test.tsx`.

### Voz: el cliente puede pedir una voz, y sólo una instalada (V3.75.5)

- **Hasta V3.75.4 la voz la decidía el servidor.** `/api/tts` recibía `text`/`language` y
  `/api/listening/audio/{id}` sólo `variant`; ambos resolvían la voz con
  `tts.resolve_voice(prefs)` —la del perfil—. El «…» de la tarjeta de audio sólo podía
  **mostrarla**, y no había forma de oír un ítem con otro acento.
- **Ahora la petición puede pedir una voz, validada en el servidor.** `TTSRequest.voice`
  (`schemas/voz.py`) y el query param `voice` de `/api/listening/audio` viajan hasta
  `tts.pick_requested_voice`, que **sólo** acepta una voz *instalada* (`list_voices()`) **y**
  del **mismo idioma** pedido. Si no pasa el filtro se ignora en silencio y manda
  `resolve_voice`: una preferencia vieja no puede romper la reproducción (ni provocar un 400
  que dejaría la UI muda).
- **Por qué la validación no es negociable:** el id de voz **entra en rutas del disco** —
  `PIPER_DIR / f"{voice_id}.onnx"` y la caché `data/listening/{banco}/{voz}/{id}-{digest}.wav`.
  Aceptar un id arbitrario del cliente sería path traversal por construcción.
- **El header sigue declarando la verdad.** `X-TTS-Voice` / `X-TTS-Degraded` dicen lo que
  **realmente** sonó, no lo que se pidió: la UI puede ser honesta cuando degrada.
- **Dos acentos, una sola lectura del catálogo.** La pareja A/B vive en el **store de módulo**
  `hooks/useVoiceChoice.ts` (patrón de `useVoiceDownload`, `useSyncExternalStore`): una sola
  lectura de `GET /api/voices` + `GET /api/settings` para toda la app aunque haya varios
  altavoces en pantalla, y persistencia con el `PUT /api/settings` que ya existía
  (`tts_voice` = A, `tts_voice_alt` = B). Un cambio de perfil **vacía** el store antes de
  releer: la voz de un alumno no puede quedarse a la vista de otro.
- **La caché no cambia de forma, sí de tamaño.** Cada ítem × voz × variante es un WAV propio
  (~100 KB), y la primera vez que se pide la voz B hay que sintetizar **y** alinear (ASR) ese
  WAV. Es el precio declarado de la función: unos segundos la primera vez, después cacheado, y
  se puede borrar sin romper nada.
- Fijado por test en `backend/tests/test_voices.py` (la voz pedida se honra; una no instalada o
  de otro idioma se ignora) y `test_listening_audio.py` (voz por URL y **caché separada por
  voz**), y en frontend por `hooks/useVoiceChoice.test.tsx`, `utils/voices.test.ts`,
  `components/VoicePicker.test.tsx`, `components/ItemReplayButton.test.tsx` y
  `components/ListenButton.test.tsx` (con `accent` se manda `voice`; **sin** `accent`, nada).

### Repetición: STOP, una locución a la vez y la lectura que elige el perfil (V3.75.6)

- **La locución en curso vive en un registro de módulo.** `api/voz.ts` guarda el
  `<audio>` y su `AbortController` en `speaking` y expone `stopSpeaking()` /
  `isSpeaking()`. Parar **pausa** el audio, **cancela** la síntesis si aún no había
  sonado y **resuelve** la promesa en curso: cortar no es un error, así que el
  botón que esperaba apaga su spinner sin tratarlo como fallo.
- **Una sola locución a la vez.** `speak()` corta la anterior al empezar: antes dos
  componentes podían solaparse (dos voces hablando encima). Es el mismo
  comportamiento que ya se esperaba del PLAY, ahora garantizado en la capa HTTP.
- **Un ítem tiene cuatro piezas y la lectura es una composición.** Texto del ítem
  (el `script`, lo que suena), pregunta, opciones y respuesta correcta. `replay_scope`
  elige la composición y vive en el mismo `PUT /api/settings` que las voces:
  `"item"` (**por defecto**: texto + pregunta + respuesta), `"withOptions"` (texto +
  pregunta + opciones + respuesta) y `"correct"` (pregunta + respuesta). El valor
  histórico `"all"` —la única lectura que existió— se conserva como `"withOptions"`
  para no cambiarle la elección a quien ya la había hecho.
- **La composición vive en una función pura y con salvaguardas.**
  `utils/voices.ts::buildReplayText` es el único sitio que decide el texto, y descarta
  piezas ausentes en vez de inventarlas: sin `correct_index` no hay respuesta (no se
  inventa), sin `script` la pregunta hace de texto, y si el alcance elegido dejara la
  lectura vacía se cae a la composición completa —**nunca** una repetición muda—. Un
  ítem cuyo script *es* la pregunta (habitual en A1) se lee una sola vez.
- **Nunca puede filtrar la clave antes de tiempo.** Todo lo que suena sale de
  `buildReplayText`, y su entrada `correct_index` sólo la aportan los sitios que ya
  han respondido; hasta entonces el altavoz de repetición ni existe (`ListenButton`
  es otra pieza).
- **El corpus deja de mentir sobre sus destrezas.** `c071` y `c084` (los dos únicos
  ítems etiquetados `dictation`/`shadowing`) estaban autorados como pregunta de
  opción múltiple con `options` + `answer_index`, y `flow_for_skill` los llevaba al
  flujo de **producción** tirando ese contenido. Reetiquetados a `numbers` y
  `phrase_recognition` (corpus `3.0.1`): B1 se sirve como las otras cinco rutas.
  El test `test_corpus_production_items_do_not_carry_multiple_choice_options`
  impide que vuelva a colarse por etiqueta. Precio declarado: hoy **no hay ningún
  ítem autorado de dictado** — el flujo y su endpoint siguen vivos y probados, pero
  el esquema del corpus exige opciones y no puede representarlo.
- **El arnés visual lo cubre de punta a punta.** `tests/visual/listeningReplayStop.spec.ts`
  (3 breakpoints) navega a la RUTA B1, comprueba que no hay tarjeta de producción y que
  el «…» ofrece las tres lecturas, responde, repite con el acento A y **lee del cuerpo
  real del `POST /api/tts`** el texto compuesto (texto + pregunta + opciones + clave)
  antes de cortar con el STOP. Medido: STOP 32×32 dentro del viewport y sin
  desbordamiento horizontal en 390/768/1280.


## Regla de oro
> Si vas a añadir una feature, su código va en su módulo. No se "pega" lógica nueva en
> `main.py` ni en `App.tsx`. Un archivo = una responsabilidad.

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
├── dependencies.py      # current_user (perfil activo) y lectura de audio con límites.
├── routers/             # Capa HTTP: endpoints + validación. SIN lógica de negocio.
│   ├── __init__.py
│   ├── academy.py       # GET/POST /api/academy/levels, enroll, mastery, next, attempts, lessons, objective/assessment, speaking/{level,journey,assessment}
│   ├── assessment.py    # /api/academy/placement*, /api/academy/exam/{level_id}*, /api/academy/level-completions
│   ├── chat.py          # POST /api/chat, POST /api/chat/stream (mode + user_id opcional)
│   ├── conversations.py # CRUD /api/conversations (filtrado por user_id) + /{cid}/interaction
│   ├── grammar.py       # POST /api/grammar/analyze, GET /api/grammar/errors (F4)
│   ├── health.py        # /api/health/live, /ready, /dependencies
│   ├── learning.py      # POST/GET /api/learning/events (F4)
│   ├── listening.py     # GET /api/listening/question, POST /api/listening/answer, GET /api/listening/stats (F8; progresión A1→A2→B1)
│   ├── models.py        # GET /api/health, GET /api/models
│   ├── network.py       # GET /api/network (IP + URLs de acceso en LAN)
│   ├── profile.py       # GET /api/profile (F4)
│   ├── progress.py      # GET /api/progress?user_id=<id>, GET /api/progress/history (F6)
│   ├── pronunciation.py # POST /api/pronunciation (audio + texto → score)
│   ├── settings.py      # GET/PUT /api/settings (preferencias por usuario)
│   ├── users.py         # GET /api/users, POST /api/users, PATCH /api/users/{id}
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
│   ├── users.py         # User, UserCreate, UserUpdate
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
│   ├── cefr.py          # evaluate_cefr (multi-señal) + bandas + recommendations (puros, F4/F8)
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
│   ├── test_robustness.py
│   ├── test_schemas.py
│   ├── test_settings.py
│   ├── test_store.py
│   ├── test_store_append_only.py
│   ├── test_store_isolation.py
│   ├── test_trends.py  # F6
│   ├── test_user_profile.py
│   ├── test_users.py
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
│   ├── chat.ts          # chat normal + streaming (envía mode + user_id).
│   ├── conversations.ts # CRUD de conversaciones (pasa user_id).
│   ├── learning.ts      # getProfile + analyzeText + getEvents (F4/F6).
│   ├── listening.ts     # getListeningQuestion + submitListeningAnswer + getListeningStats (F8).
│   ├── pronunciation.ts # checkPronunciation (audio + texto → score; user_id opcional).
│   ├── progress.ts      # getProgress + getProgressHistory (resumen + histórico) (F6).
│   ├── settings.ts      # getSettings + putSettings (preferencias por usuario).
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
│   ├── cookie.ts        # cookies del launcher
│   ├── fluency.ts       # wpmLabel, fluencyLevelLabel (F8)
│   ├── image.ts         # resizeImageToDataUrl (M14)
│   ├── layout.ts        # dimensiones de paneles + clamp/parse/serialize (M14)
│   ├── modes.ts         # MODES + isTutorMode
│   ├── progress.ts      # formatScore/formatAverage/pronunciationLevelLabel + bucketLabel/eventLabel (M9/F6)
│   ├── pronunciationFeedback.ts # joinWords/feedbackHints/wordsCorrectLabel (puros, F7)
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
├── launcher.py          # PUNTO DE ENTRADA: GUI mínima (tkinter), arranca/para la app
├── ui.py                # paleta, iconos, dots de estado y lectura de logs (puro)
├── core.py              # lógica pura: rutas, comandos de arranque, normalización de estado
├── process_manager.py   # subprocesos: arrancar/parar backend (uvicorn) y frontend (Vite)
├── status.py            # lectura de estado: HTTP (health) + SQLite (contadores/usuarios)
├── make_icon.ps1        # genera icon.ico (System.Drawing, Windows)
├── install_shortcut.ps1 # crea el acceso directo del escritorio (English Tutor.lnk)
├── icon.ico             # icono del acceso directo
├── pyproject.toml       # configuración de ruff (mismas reglas que el backend)
└── tests/               # pytest (conftest.py + test_core/test_status/test_process_manager/test_ui)
```

### Responsabilidades launcher
- **`launcher.py`**: GUI `tkinter` (ventana de estado con servicios, BD y usuarios; botones
  Iniciar/Detener/Abrir/Actualizar; paneles colapsables). Solo orquesta; no contiene lógica de
  negocio.
- **`ui.py`**: constantes de estilo (colores, iconos, puntos de estado) y lectura de logs.
- **`core.py`**: funciones puras y testables (resolver rutas, construir comandos, normalizar
  estado de salud y contadores).
- **`process_manager.py`**: ciclo de vida de los dos subprocesos (backend/frontend), con
  matado del árbol de procesos en Windows (`taskkill /T /F`).
- **`status.py`**: obtiene el estado real: `/api/health/dependencies` (HTTP) y consultas de
  solo lectura a la BD SQLite (contadores globales y usuarios).
- **`*.ps1`**: utilidades de Windows para generar el icono y crear el acceso directo.

## Regla de oro
> Si vas a añadir una feature, su código va en su módulo. No se "pega" lógica nueva en
> `main.py` ni en `App.tsx`. Un archivo = una responsabilidad.

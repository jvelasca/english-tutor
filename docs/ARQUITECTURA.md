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
├── config.py            # Configuración: URLs, rutas de modelos, defaults.
├── routers/             # Capa HTTP: endpoints + validación. SIN lógica de negocio.
│   ├── __init__.py
│   ├── chat.py          # POST /api/chat, POST /api/chat/stream (mode + user_id opcional)
│   ├── conversations.py # CRUD /api/conversations (filtrado por user_id)
│   ├── grammar.py       # POST /api/grammar/analyze, GET /api/grammar/errors (F4)
│   ├── health.py        # /api/health/live, /ready, /dependencies
│   ├── learning.py      # POST/GET /api/learning/events (F4)
│   ├── models.py        # GET /api/health, GET /api/models
│   ├── profile.py       # GET /api/profile (F4)
│   ├── progress.py      # GET /api/progress?user_id=<id>, GET /api/progress/history (F6)
│   ├── pronunciation.py # POST /api/pronunciation (audio + texto → score)
│   ├── users.py         # GET /api/users, POST /api/users
│   ├── vocabulary.py    # POST /api/vocabulary/analyze, GET /api/vocabulary (F4)
│   └── voz.py           # POST /api/transcribe, POST /api/tts
├── schemas/             # Contratos de datos (Pydantic).
│   ├── __init__.py
│   ├── chat.py          # ChatMessage, ChatRequest, ChatResponse
│   ├── conversations.py # Conversation, ConversationMeta (con user_id), ConversationUpsert
│   ├── grammar.py       # GrammarAnalyze*, GrammarFinding, GrammarRecurringError (F4)
│   ├── learning.py      # LearningEventType, LearningEvent, LearningEventCreate (F4)
│   ├── profile.py       # LearningProfile (F4)
│   ├── pronunciation.py # PronunciationResponse
│   ├── progress.py      # PronunciationStats, ProgressSummary, Bucket, ProgressHistory (F6)
│   ├── users.py         # User, UserCreate
│   ├── vocabulary.py    # VocabularyAnalyze*, VocabularyItem (F4)
│   └── voz.py           # TTSRequest, TranscribeResponse
├── domain/              # Servicios de dominio (async, orquestan la lógica).
│   ├── __init__.py
│   ├── conversations.py
│   ├── grammar.py       # análisis de errores + persistencia (F4)
│   ├── learning.py      # eventos de aprendizaje (F4)
│   ├── pronunciation.py
│   ├── profile.py       # get_profile_summary + get_profile_context (compone el perfil) (F4/F5)
│   ├── progress.py      # get_progress_history: series + racha + dominio + hitos (F6)
│   ├── users.py
│   └── vocabulary.py    # extracción + persistencia (F4)
├── repositories/        # Acceso a datos puro (SQLite). Sin reglas de negocio.
│   ├── __init__.py
│   ├── db.py            # conexión, esquema, migraciones, ping
│   ├── conversations.py
│   ├── grammar.py       # grammar_errors (F4)
│   ├── learning.py      # learning_events (F4)
│   ├── profile.py       # learning_profile (F4)
│   ├── pronunciation.py
│   ├── progress.py      # activity_events (mensajes con modo + pronunciaciones) (F6)
│   ├── users.py
│   └── vocabulary.py    # vocabulary (F4)
├── services/            # Lógica pura y clientes de infra (llm, voz, análisis).
│   ├── __init__.py
│   ├── cefr.py          # estimate_cefr, recommendations (puros, F4)
│   ├── context.py       # build_system_prompt: modo + perfil → prompt del tutor (F5)
│   ├── grammar.py       # reglas de errores deterministas (F4)
│   ├── llm.py           # cliente Ollama (chat + streaming; system prompt inyectable)
│   ├── mastery.py       # classify_errors + compute_milestones (puros, F6)
│   ├── policy.py        # correctness_guidance por nivel CEFR (puro, F5)
│   ├── pronunciation.py # score_pronunciation (puro, difflib)
│   ├── stt.py           # faster-whisper
│   ├── trends.py        # daily_activity + aggregate_series + compute_streak (puros, F6)
│   ├── tts.py           # piper-tts
│   └── vocabulary.py    # extract_words (puro, F4)
├── models/              # pesos descargados (Whisper/Piper). GITIGNORED.
├── data/                # base SQLite (tutor.db). GITIGNORED.
├── tests/               # pruebas (pytest).
│   ├── conftest.py      # asegura el import desde backend/
│   ├── test_activity.py # F6
│   ├── test_api_security.py
│   ├── test_chat_integration.py
│   ├── test_chat_profile.py # F5
│   ├── test_context.py      # F5
│   ├── test_cors.py
│   ├── test_domain_async.py
│   ├── test_foreign_keys.py
│   ├── test_grammar.py  # F4
│   ├── test_health.py
│   ├── test_learning_events.py # F4
│   ├── test_mastery.py # F6
│   ├── test_modes.py
│   ├── test_policy.py   # F5
│   ├── test_profile.py  # F4
│   ├── test_progress.py
│   ├── test_progress_history.py # F6
│   ├── test_pronunciation.py
│   ├── test_robustness.py
│   ├── test_schemas.py
│   ├── test_store.py
│   ├── test_store_append_only.py
│   ├── test_store_isolation.py
│   ├── test_trends.py  # F6
│   ├── test_users.py
│   └── test_vocabulary.py # F4
├── scripts/             # scripts de utilidad.
│   ├── eval_model.py    # evalúa un modelo como tutor (M5)
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
- **`services/`**: lógica pura/testable (scoring, análisis determinista) y clientes de infra
  (Ollama, whisper, piper). No importa FastAPI.
- **`schemas/`**: tipos Pydantic. Son el contrato de la API.
- **`config.py`**: constantes de entorno/configuración, sin lógica.

## Frontend (`frontend/src/`)

```
frontend/src/
├── main.tsx
├── App.tsx              # Orquesta: compone la página.
├── api/                 # Cliente HTTP (única capa que habla con el backend).
│   ├── client.ts        # fetch base (manejo de errores, JSON).
│   ├── chat.ts          # chat normal + streaming (envía mode + user_id).
│   ├── conversations.ts # CRUD de conversaciones (pasa user_id).
│   ├── learning.ts      # getProfile + analyzeText + getEvents (F4/F6).
│   ├── pronunciation.ts # checkPronunciation (audio + texto → score; user_id opcional).
│   ├── progress.ts      # getProgress + getProgressHistory (resumen + histórico) (F6).
│   ├── users.ts         # listUsers, createUser.
│   └── voz.ts           # transcribe + tts.
├── components/          # Presentación pura (reciben props, no hacen fetch).
│   ├── ChatMessage.tsx
│   ├── Composer.tsx
│   ├── HandsFreeToggle.tsx  # activar/parar modo manos libres + estado (M10)
│   ├── LearningProfile.tsx  # panel del perfil: CEFR, vocabulario, errores, recomendaciones (F4)
│   ├── MicButton.tsx
│   ├── ModeSelect.tsx   # selector de modo de tutor
│   ├── PronunciationPractice.tsx
│   ├── ProgressDashboard.tsx # dashboard de progreso real: tendencias, racha, dominio, hitos (F6)
│   ├── Sidebar.tsx      # lista de conversaciones
│   ├── SpeakButton.tsx
│   ├── ThemeToggle.tsx  # toggle claro/oscuro (M8)
│   └── UserSelect.tsx   # selector de perfil de usuario
├── hooks/               # Estado y lógica de UI.
│   ├── useChat.ts       # incluye estado de usuario y aislamiento por perfil
│   ├── useHandsFree.ts  # bucle de voz continua + VAD por energía (M10)
│   └── useTheme.ts      # tema claro/oscuro + persistencia (M8)
├── types/               # Tipos compartidos (espejo de los schemas del backend).
│   └── api.ts           # incluye User y user_id en ConversationMeta
├── utils/               # Funciones puras (testables).
│   ├── title.ts         # deriveTitle
│   ├── title.test.ts
│   ├── cefr.ts          # cefrTone, cefrLabel (F4)
│   ├── cefr.test.ts
│   ├── sse.ts           # parseo de eventos SSE
│   ├── sse.test.ts
│   ├── modes.ts         # MODES + isTutorMode
│   ├── modes.test.ts
│   ├── users.ts         # nextDefaultUserName
│   ├── users.test.ts
│   ├── progress.ts      # formatScore/formatAverage/pronunciationLevelLabel + bucketLabel/eventLabel (M9/F6)
│   ├── progress.test.ts
│   ├── theme.ts         # resolveInitialTheme (M8)
│   ├── theme.test.ts
│   ├── vad.ts           # VAD: rms + shouldEndUtterance + constantes (M10)
│   └── vad.test.ts
├── scripts/             # scripts de utilidad.
│   └── check.ps1        # tsc + vitest
├── vitest.config.ts
└── index.css             # tokens de diseño, tema claro/oscuro, responsive (M8)
```

> **Sistema de diseño (M8):** los tokens viven en `:root` de `index.css`
> (`--color-*`, `--font-*`, `--text-*`, `--space-*`, `--radius-*`, `--shadow-*`),
> con el tema claro sobrescrito en `:root[data-theme="light"]`. El tema se controla
> desde `hooks/useTheme.ts` + `utils/theme.ts` y se aplica en `<html data-theme="...">`.

### Responsabilidades frontend
- **`api/`**: único lugar donde se hace `fetch`. Expone funciones tipadas.
- **`components/`**: solo renderizar y emitir eventos vía props. No hacen peticiones.
- **`hooks/`**: manejan estado (mensajes, loading) y llaman a `api/`.
- **`types/`**: interfaces TypeScript compartidas.
- **`App.tsx`**: composición de alto nivel, mínimo estado.

## Regla de oro
> Si vas a añadir una feature, su código va en su módulo. No se "pega" lógica nueva en
> `main.py` ni en `App.tsx`. Un archivo = una responsabilidad.

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
│   ├── chat.py          # POST /api/chat, POST /api/chat/stream (aceptan mode)
│   ├── conversations.py # CRUD /api/conversations
│   ├── models.py        # GET /api/health, GET /api/models
│   ├── pronunciation.py # POST /api/pronunciation (audio + texto → score)
│   └── voz.py           # POST /api/transcribe, POST /api/tts
├── schemas/             # Contratos de datos (Pydantic).
│   ├── __init__.py
│   ├── chat.py          # ChatMessage, ChatRequest, ChatResponse
│   ├── conversations.py # Conversation, ConversationMeta, ConversationUpsert
│   ├── pronunciation.py # PronunciationResponse
│   └── voz.py           # TTSRequest, TranscribeResponse
├── services/            # Lógica de negocio. NO conoce HTTP.
│   ├── __init__.py
│   ├── llm.py           # cliente Ollama (chat normal + streaming; system prompt por modo)
│   ├── pronunciation.py # score_pronunciation (puro, difflib)
│   ├── stt.py           # faster-whisper
│   ├── store.py         # persistencia SQLite (conversaciones)
│   └── tts.py           # piper-tts
├── models/              # pesos descargados (Whisper/Piper). GITIGNORED.
├── data/                # base SQLite (tutor.db). GITIGNORED.
├── tests/               # pruebas (pytest).
│   ├── conftest.py      # asegura el import desde backend/
│   ├── test_health.py
│   ├── test_modes.py    # modos de tutor (prompts)
│   ├── test_pronunciation.py
│   ├── test_schemas.py
│   └── test_store.py
├── scripts/             # scripts de utilidad.
│   ├── eval_model.py    # evalúa un modelo como tutor (M5)
│   └── smoke_test.py    # verifica el servidor en ejecución
├── download_models.py   # script de descarga de modelos de voz (1ª vez)
├── requirements.txt
└── requirements-dev.txt # incluye pytest + httpx
```

### Responsabilidades backend
- **`main.py`**: solo crear la app y registrar routers. Nada de lógica.
- **`routers/`**: parsear la petición, validar con schemas, llamar a un service, devolver respuesta.
- **`services/`**: toda la lógica real (hablar con Ollama, transcribir, sintetizar). No importa FastAPI.
- **`schemas/`**: tipos Pydantic. Son el contrato de la API.
- **`config.py`**: constantes de entorno/configuración, sin lógica.

## Frontend (`frontend/src/`)

```
frontend/src/
├── main.tsx
├── App.tsx              # Orquesta: compone la página.
├── api/                 # Cliente HTTP (única capa que habla con el backend).
│   ├── client.ts        # fetch base (manejo de errores, JSON).
│   ├── chat.ts          # chat normal + streaming (envía mode).
│   ├── conversations.ts # CRUD de conversaciones.
│   ├── pronunciation.ts # checkPronunciation (audio + texto → score).
│   └── voz.ts           # transcribe + tts.
├── components/          # Presentación pura (reciben props, no hacen fetch).
│   ├── ChatMessage.tsx
│   ├── Composer.tsx
│   ├── MicButton.tsx
│   ├── ModeSelect.tsx   # selector de modo de tutor
│   ├── PronunciationPractice.tsx
│   ├── Sidebar.tsx      # lista de conversaciones
│   └── SpeakButton.tsx
├── hooks/               # Estado y lógica de UI.
│   └── useChat.ts
├── types/               # Tipos compartidos (espejo de los schemas del backend).
│   └── api.ts
├── utils/               # Funciones puras (testables).
│   ├── title.ts         # deriveTitle
│   ├── title.test.ts
│   ├── sse.ts           # parseo de eventos SSE
│   ├── sse.test.ts
│   ├── modes.ts         # MODES + isTutorMode
│   └── modes.test.ts
├── scripts/             # scripts de utilidad.
│   └── check.ps1        # tsc + vitest
├── vitest.config.ts
└── index.css
```

### Responsabilidades frontend
- **`api/`**: único lugar donde se hace `fetch`. Expone funciones tipadas.
- **`components/`**: solo renderizar y emitir eventos vía props. No hacen peticiones.
- **`hooks/`**: manejan estado (mensajes, loading) y llaman a `api/`.
- **`types/`**: interfaces TypeScript compartidas.
- **`App.tsx`**: composición de alto nivel, mínimo estado.

## Regla de oro
> Si vas a añadir una feature, su código va en su módulo. No se "pega" lógica nueva en
> `main.py` ni en `App.tsx`. Un archivo = una responsabilidad.

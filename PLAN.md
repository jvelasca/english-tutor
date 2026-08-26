# Plan de proyecto — English Tutor (100% local)

> Mantenido por el gerente del proyecto (yo). Los subagentes se ejecutan desde
> agentes locales: cada tarea se describe en `agentes/<nombre>.md`.
>
> **Premisas y reglas:** `docs/PREMISAS.md` · **Arquitectura:** `docs/ARQUITECTURA.md` ·
> **Guía de desarrollo:** `docs/DESARROLLO.md`.

## Estado actual

- ✅ Backend FastAPI + Pydantic (chat + voz + progreso + listening + CEFR + evaluación del tutor).
- ✅ Frontend Vite + React + TypeScript (chat, voz continua, dashboard de progreso, listening, calidad del tutor).
- ✅ Lanzador de escritorio (`launcher/`, GUI tkinter) con acceso directo e icono.
- ✅ Versión estable `1.21.0` (cierre de la auditoría pedagógica A1→B2: corpus de audio humano 1.0 +
  validación determinista audio↔metadata + separación del proxy de pronunciación del audio real +
  evidencia familiar/transfer/novel + Interaction 3.0 + matriz de assessment CEFR; y nueva UI de 3
  paneles con barra de estado y navegación por destrezas). Sobre la base V1.20 de pronunciación
  fonémica P6, turn-taking real e infraestructura de biblioteca de audio humano.
- ✅ Diálogo real probado con `qwen3.5:9b`.
- ✅ Documentación (`docs/`, premisas, arquitectura, guía de desarrollo, relevo, changelog).

## Hitos (roadmap)

### M0 — Esqueleto modular  [HECHO ✔]
- Refactor sin cambios de comportamiento: separar backend (`routers/`, `services/`, `schemas/`)
  y frontend (`api/`, `components/`, `hooks/`, `types/`) según `docs/ARQUITECTURA.md`.
- Verificado: backend arranca y responde, frontend compila (`tsc`), chat funciona de punta a punta.
- Subagente (ejecutado por el gerente): `agentes/m0-esqueleto-modular.md`.

### M1 — Streaming de respuestas  [HECHO ✔]
- El texto aparece mientras se genera (SSE/streaming), en vez de esperar la respuesta completa.
- Backend: `POST /api/chat/stream` (SSE). Frontend: `streamChat` consume e incrementa la burbuja.
- Verificado: múltiples `data: {"content":...}` + `data: {"done":true}`; `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m1-backend-streaming.md`, `agentes/m1-frontend-streaming.md`.

### M2 — Voz 100% local  [HECHO ✔]
- **Oído (STT):** voz → texto con **Whisper** (`faster-whisper`, `small`, CPU). ✔
- **Boca (TTS):** texto → voz con **Piper** (`en_US-lessac-medium`, CPU). ✔
- Backend: `POST /api/transcribe` y `POST /api/tts` (modelos en `backend/models/`).
- Frontend: botón micrófono (grabar → transcribir) y altavoz (escuchar respuesta).
- Verificado: TTS genera WAV válido; Whisper transcribe el audio generado correctamente.
- Subagentes (ejecutados por el gerente): `agentes/m2-backend-voz.md`, `agentes/m2-frontend-voz.md`.

### M3 — Memoria e historial  [HECHO ✔]
- Guardar conversaciones, poder retomarlas, contexto persistente.
- Backend: `services/store.py` (SQLite) + CRUD `/api/conversations`.
- Frontend: sidebar con lista de conversaciones, nuevo chat, cargar y eliminar.
- Verificado: crear → guardar → leer → listar → borrar funciona.
- Subagente (ejecutado por el gerente): sin briefing previo; implementación directa del gerente.

### M4 — Modo profesor de inglés  [HECHO ✔]
- **Modos de tutor**: `conversation`, `grammar`, `exercises`, `pronunciation` (system prompts por modo).
- **Corrección de pronunciación**: `POST /api/pronunciation` (audio + texto esperado → score).
- Frontend: selector de modo + tarjeta de práctica de pronunciación (grabar → evaluar).
- Verificado: backend 13 tests, frontend 10 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m4-backend-modo.md`, `agentes/m4-frontend-modo.md`.

### M5 — Modelo conversacional  [HECHO ✔]
- Evaluar cambiar a un modelo no-coder (ej. `llama3.1:8b` o `mistral`) para mejor calidad de tutor.
- Criterio: calidad como profesor (correcciones, explicaciones, tono) + tamaño/VRAM (RTX 4060 Ti 4 GB).
- Entregable: script de evaluación repetible + decisión documentada del modelo por defecto.
- Subagente (ejecutado por el gerente): `agentes/m5-modelo-conversacional.md`.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. Tras evaluar ambos con
  `scripts/eval_model.py` (4 prompts de tutor), `qwen3.5:9b` gana en calidad como tutor:
  correcciones más estructuradas, ejercicios con contexto y una guía de pronunciación IPA
  mucho más detallada y **correcta**. `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde la fricativa sorda /θ/ de *through* con la
  sonora /ð/ de *this/that*), así que **no es claramente mejor**. `llama3.1:8b` queda
  instalado como alternativa selectable en el frontend.
- **Descarga desbloqueada:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min.
  Al **quitar la VPN** la descarga terminó en ~1 min a 52 MB/s y sin error de certificado
  (el MITM del ISP ya no afectaba a esa conexión). `ollama pull llama3.1:8b` completado.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

### M6 — Release a GitHub  [HECHO ✔]
- Repositorio **público**: https://github.com/jvelasca/english-tutor
- V1.0 (tag `v1.0.0`) subida con release e issues de seguimiento.

### M7 — Multi-usuario  [HECHO ✔]
- Perfiles locales con **seguimiento independiente** (conversaciones, progreso, puntuaciones, ajustes).
- Selección simple de perfil al abrir; aislamiento total de datos entre usuarios (premisa 13).
- Backend: tabla `users`, columna `user_id` en `conversations` (migración idempotente no
  destructiva con usuario por defecto `Usuario`), `GET/POST /api/users` y CRUD de
  conversaciones filtrado por `user_id` (query param).
- Frontend: selector de perfil (`UserSelect`) en la cabecera, creación de usuarios, y
  aislamiento al cambiar de perfil (resetea conversación y recarga la lista del nuevo usuario).
- Verificado: backend 20 tests, frontend 14 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

### M8 — Diseño y UX nivel top  [HECHO ✔]
- Rediseño al nivel de apps líderes (ChatGPT/Duolingo): sistema de tokens, tema claro/oscuro,
  responsive, micro-interacciones y estados vacíos/carga/error (premisa 14).
- Sistema de **tokens** en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion). Tema **claro/oscuro** (`data-theme`, hook `useTheme`,
  toggle accesible, persistencia en `localStorage`, anti-FOUC en `index.html`).
- **Responsive** (≤768px): sidebar drawer + hamburguesa. **a11y**: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Verificado: frontend 19 tests (5 nuevos de tema), `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m8-diseno-ux.md`.

### M9 — Seguimiento de progreso del alumno  [HECHO ✔]
- Registrar el progreso por usuario: nº de ejercicios, correcciones y puntuaciones de
  pronunciación; mostrar un resumen en el frontend (issue #2, pendiente diferido de M4).
- Backend: tabla `pronunciation_attempts` + columna `mode` en `messages` (migración
  idempotente), `GET /api/progress?user_id=<id>` y `POST /api/pronunciation` con `user_id`
  opcional. Frontend: panel `ProgressSummary` + api `progress.ts`.
- Verificado: backend 27 tests, frontend 26 tests, `tsc` sin errores, `npm run build` OK.
- Subagentes (ejecutados por el gerente): `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

### M10 — Conversación por voz continua (manos libres)  [HECHO ✔]
- Modo continuo: VAD (detección de silencio vía Web Audio API), transcripción automática y
  respuesta hablada sin pulsar botones (issue #3). Sin cambios de backend
  (transcribe/tts/stream ya existían).
- Frontend: refactor `useChat.sendText(text): Promise<string>`, `utils/vad.ts` (RMS +
  `shouldEndUtterance`), `hooks/useHandsFree.ts` (bucle de estados + VAD por energía),
  `components/HandsFreeToggle.tsx` (toggle + indicador de estado accesible).
- Verificado: frontend 37 tests, `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m10-voz-continua.md`.

### M11 — Lanzador de escritorio + release estable  [HECHO ✔]
- Lanzador de escritorio (`launcher/`, GUI `tkinter` sin dependencias nuevas) que arranca/detiene
  la app (backend + frontend) y muestra el estado de servicios, base de datos y usuarios.
- Acceso directo del escritorio con icono (`launcher/install_shortcut.ps1` + `make_icon.ps1`).
- Versión unificada `1.1.0` (backend `config.py::VERSION` expuesta en `/api/health` y `/`, y
  frontend `package.json`).
- Verificado: launcher 22 tests + ruff limpio; backend 217 tests, frontend 88 tests, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/a1-launcher-core.md`,
  `agentes/endurecimiento/a2-launcher-gui.md`.

### M12 — Release Audit 1.1 + versión 1.1.1  [HECHO ✔]
- Cierre de los 6 puntos señalados por la auditoría externa antes de congelar la arquitectura.
  1. Unificar `current_user` en todos los endpoints sensibles.
  2. Fluidez ya expuesta como `FluencyStats` en `PronunciationResponse` (verificado, sin cambios).
  3. Renombrar "CEFR estimate" → `estimated_level/bands/descriptor`.
  4. Corregir semántica de vocabulario: `occurrences` → `appearances` (+ migración idempotente).
  5. Añadir `confidence`/`source`/`confirmed` a gramática y filtrar el prompt a errores confirmados.
  6. Tests de aislamiento cross-user + tests del Learning Context/Prompt.
- Selector de perfil: no auto-seleccionar el primer usuario si hay varios.
- Versión unificada `1.1.1`.
- Verificado: backend 231 tests, frontend 92 tests, launcher 22 tests, ruff limpio, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/ra-*.md` (RA1–RA7).

### M13 — Etapa 2: Pedagogía (Learning Engine v2)  [EN CURSO]
- Arquitectura congelada; solo se añade rigor pedagógico a lo ya medido (ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`).
- Tracks (un subagente a la vez): P1 política pedagógica formal, P2 error mastery,
  P3 vocabulario exposure/production/mastery, P4 listening como competencia, P5 CEFR basado
  en evidencia, P6 pronunciación fonémica.
- Subagentes (ejecutados por el gerente): `agentes/pedagogia/p-*.md` (P1–P6).

### M14 — Evidence & Performance + Listening + Placement  [HECHO ✔]
- **Evidence & Performance Engine (V1.3)**: ciclo `Evidence → Mastery → Skill Profile →
  Remediación` para speaking, writing y pronunciation (scorer determinista + extracción de
  evidencia con LLM + puente a mastery). CEFR Skill Profile (`/api/academy/profile`) y
  remediación adaptativa (`/api/academy/remediation`); el tutor lee el perfil CEFR.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (retrieval_probability + `review_due`
  real en función del tiempo).
- **Listening Engine**: sub-destrezas + dificultad + diagnóstico adaptativo
  (`/api/listening/diagnostic`).
- **Placement Engine (V1.5)**: IRT-lite adaptativo (`POST /api/academy/placement/next`).
- Verificado: backend 406 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M15 — Listening 2.0 + Placement 2.0  [HECHO ✔]
- **Listening 2.0 (V1.6)**: audio como entidad de primer nivel (`ListeningAsset` con metadatos
  de audio), vector de dificultad de 8 dimensiones con dificultad derivada por construcción,
  15 sub-destrezas (9 nuevas) y métrica de automaticidad (fluidez procesal).
- **Placement 2.0 (V1.7)**: calibración observacional de ítems (tabla
  `placement_item_calibration` con contadores poblacionales) y perfil **multiskill**
  (θ/nivel/confianza por destreza) sobre el motor IRT-lite/1PL. Endpoint
  `POST /api/academy/placement/profile` y banco de placement ampliado a las 7 destrezas.
- Verificado: backend 480 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

## Decisiones tomadas

- Hitos M1 y M2 en paralelo (tras M0).
- STT → Whisper (`faster-whisper`). TTS → Piper.
- Ritmo: poco a poco, hito a hito.
- Requisitos nuevos (premisas 13 y 14): **multi-usuario** y **diseño nivel top**. Quedan como M7 y M8.

## Tablero de subagentes

| Subagente | Archivo | Estado |
|---|---|---|
| M0 Esqueleto modular | `agentes/m0-esqueleto-modular.md` | ✔ hecho |
| M1 Backend streaming | `agentes/m1-backend-streaming.md` | ✔ hecho |
| M1 Frontend streaming | `agentes/m1-frontend-streaming.md` | ✔ hecho |
| M2 Backend voz | `agentes/m2-backend-voz.md` | ✔ hecho |
| M2 Frontend voz | `agentes/m2-frontend-voz.md` | ✔ hecho |
| M4 Backend modo profesor | `agentes/m4-backend-modo.md` | ✔ hecho |
| M4 Frontend modo profesor | `agentes/m4-frontend-modo.md` | ✔ hecho |
| M5 Modelo conversacional | `agentes/m5-modelo-conversacional.md` | ✔ hecho |
| M7 Backend multi-usuario | `agentes/m7-backend-multiusuario.md` | ✔ hecho |
| M7 Frontend multi-usuario | `agentes/m7-frontend-multiusuario.md` | ✔ hecho |
| M8 Diseño y UX | `agentes/m8-diseno-ux.md` | ✔ hecho |
| M9 Backend progreso | `agentes/m9-backend-progreso.md` | ✔ hecho |
| M9 Frontend progreso | `agentes/m9-frontend-progreso.md` | ✔ hecho |
| M10 Voz continua | `agentes/m10-voz-continua.md` | ✔ hecho |
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |
| RA1–RA7 Release Audit 1.1 | `agentes/endurecimiento/ra-*.md` | ✔ hecho |
| P1 Política pedagógica formal | `agentes/pedagogia/p1-politica-pedagogica.md` | ✔ hecho |
| P2 Error Mastery | `agentes/pedagogia/p2-error-mastery.md` | ✔ hecho |
| P3–P6 Etapa pedagógica | `agentes/pedagogia/p-*.md` | ✔ hecho |
| V1.15 Speaking 3.0 | `agentes/pedagogia/p9-speaking-3.0.md` | ✔ hecho |
| V1.18 P1 listening (retention + dictado/shadowing + variantes) | `agentes/pedagogia/p13-p15.md` | ✔ hecho |
| V1.19 Refresco UI profesional (frontend) | plan Cursor `refresco_ui_profesional` | ✔ hecho |

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

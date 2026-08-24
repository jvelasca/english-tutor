# Plan de endurecimiento — English Tutor

> **Propósito:** convertir el MVP/RC actual en una versión estable. Es la hoja de ruta
> secuencial que sigue a la auditoría de seguridad/robustez (interna + externa).
> No se rehace la arquitectura; se endurece por fases, un subagente a la vez.
> Mantenido por el gerente del proyecto. Fuente de verdad de reglas: `docs/PREMISAS.md`.

## Estado

- **Fase 1 (P0) CERRADA** el 2026-08-24: aislamiento multiusuario extremo a extremo,
  `system` fuera del input, límites de payload y sanitización de errores.
- **Fase 2 (P1) CERRADA** el 2026-08-24: store no bloqueante (threadpool), health real,
  chat integrable (DI + tests con Ollama mockeado), CI + deps reproducibles + CORS restringido.
- **Fase 3 (persistencia y dominio) CERRADA** el 2026-08-24: mensajes append-only (con `id`),
  capa de dominio (`Router → Service → Repository`) y FKs reales `user_id → users(id)`.
- **Fase 4 (Learning Profile) CERRADA** el 2026-08-24: eventos de aprendizaje, vocabulario,
  errores gramaticales recurrentes, estimación CEFR + recomendaciones (backend) y panel de
  perfil en el frontend.
- **Fase 5 (Tutor Policy + Context Builder) CERRADA** el 2026-08-24: política de corrección por
  CEFR, Context Builder (el perfil del alumno entra al system prompt) y propagación de `user_id`
  al chat en el frontend.
- **Fase 6 (Progreso pedagógico real) CERRADA** el 2026-08-24: F6.1 (registro automático de
  eventos), F6.2 (progreso histórico: tendencias, racha, dominio, hitos) y F6.3 (dashboard
  frontend responsive móvil/tablet).
- **Fase 7 (Pronunciación fonética) CERRADA** el 2026-08-24: F7.1 (evaluador compuesto
  word+Soundex+char) y F7.2 (frontend feedback fonético).
- **Fase 8 (Listening / Speaking / CEFR) CERRADA** el 2026-08-24: F8.1 (CEFR multi-señal con
  bandas por destreza), F8.2 (fluidez oral con duración/WPM), F8.3 (listening: banco de
  preguntas + evaluación) y F8.4 (frontend: CEFR + fluidez + listening UI).
- **Fase 9 (Evaluación objetiva del tutor) CERRADA** el 2026-08-24: F9.1 (evaluador objetivo
  del tutor, puro y determinista), F9.2 (informe agregado + script por lotes) y F9.3 (panel
  de calidad del tutor en el frontend).
- **Fase 10 (Release 1.0 estable) CERRADA** el 2026-08-24: versión unificada `1.1.0`, gate
  verde completo y **lanzador de escritorio** (`launcher/`, GUI `tkinter` + acceso directo
  con icono).
- Backend `217 tests` verdes + `ruff` limpio, `import main` OK; frontend `88 tests` verdes,
  `tsc`/`build` OK; launcher `22 tests` verdes + `ruff` limpio.
- Línea base inicial: backend `27 tests`, frontend `npm test`/`tsc` verdes, 13 commits,
  tag `v1.0.0`.

## Verificación de la auditoría (resumen)

La auditoría externa fue verificada archivo por archivo y es **correcta**. Hallazgos
críticos confirmados:

- **P0-1** CRUD de conversaciones por `cid` sin comprobar propietario
  (`routers/conversations.py`, `services/store.py::get_conversation/save_conversation/delete_conversation`).
- **P0-2** `/api/pronunciation` acepta `user_id` opcional y no valida existencia ni pertenencia.
- **P0-3** El frontend envía `currentUserId` y el backend confía en él como mecanismo de "seguridad".
- **P0-4** `Role` externo incluye `system` en el backend, mientras el frontend solo usa `user|assistant`.
- **P0-5** Sin límites de tamaño: `messages`, `content`, texto TTS, subida de audio.
- **P1** SQLite síncrono en endpoints `async`; `health` estático; errores filtran `exc`;
  `CORS *`; versiones incoherentes; deps `>=` abiertas; sin CI; sin tests de seguridad de API.

## Prioridades

| Nivel | Alcance |
|---|---|
| 🔴 P0 | Aislamiento real (conversaciones + pronunciación), quitar `system` del input, validación de ownership, límites de payload, tests de seguridad. |
| 🟠 P1 | Store no bloqueante, health real, manejo de errores, límites STT/TTS, tests de API, CI, deps reproducibles, CORS restringido. |
| 🟡 P2 | Learning Profile, errores gramaticales persistentes, vocabulario, estimación CEFR, eventos de aprendizaje, recomendaciones. |
| 🟢 P3 | Evaluación fonética real, prosodia, VAD adaptativo, AEC/control de eco, Tutor Policy avanzada, evaluación de modelos. |

## Fases y subagentes (secuencia)

Cada subagente es **autocontenido** (`agentes/endurecimiento/<id>-<nombre>.md`), tiene una
única responsabilidad, escribe sus propios tests y termina verde antes de pasar al siguiente.

### FASE 0 — Baseline (hecha)
Auditoría completa + línea base verde. Ver arriba.

### FASE 1 — Seguridad y aislamiento multiusuario (P0)

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| E1.1 | Store ownership + routers | `store.py` (firmas con `user_id`, `AND user_id = ?`, `record_pronunciation` valida usuario, índices), `routers/conversations.py` y `routers/pronunciation.py` (exigen/validan `user_id`), tests de aislamiento de store. | `agentes/endurecimiento/e1-01-store-ownership.md` |
| E1.2 | Frontend propagar user_id | `api/conversations.ts`, `api/pronunciation.ts`, `hooks/useChat.ts`, `types/api.ts` (enviar `user_id` en GET/PUT/DELETE y pronunciación) + tests de `api/`. | `agentes/endurecimiento/e1-02-frontend-userid.md` |
| E1.3 | LocalUserContext + tests de seguridad API | Dependencia `backend/dependencies.py` (`current_user`, 404 si no existe), refactor DRY de `progress.py` y `conversations.py`, tests canónicos de aislamiento por API. | `agentes/endurecimiento/e1-03-context-security-tests.md` |
| E1.4 | Contratos (quitar `system`, límites de payload) | `Role = user|assistant`, `max_length` en content/messages, `MAX_TTS_CHARS`, constantes en `config.py`. | `agentes/endurecimiento/e1-04-contratos-limites.md` |
| E1.5 | Límites de audio + sanitización de errores | Tamaño/MIME de subida de audio, errores sin filtrar `exc` (log interno + mensaje genérico). | `agentes/endurecimiento/e1-05-audio-errores.md` |

> **Nota de secuencia:** E1.1 y E1.2 son un "par de contrato" (el backend exige `user_id`,
> el frontend lo envía); se ejecutan consecutivamente para minimizar la ventana en la que
> la UI de conversaciones queda temporalmente rota.

### FASE 2 — Robustez API e infraestructura (P1)

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| E2.1 | Store no bloqueante | Ejecutar `store.*` vía `run_in_threadpool` (opción A, riesgo mínimo). `aiosqlite` se difiere a la fase de dominio. | `agentes/endurecimiento/e2-01-store-no-bloqueante.md` |
| E2.2 | Health real | `/api/health/live`, `/api/health/ready`, `/api/health/dependencies` (sqlite, ollama, whisper, piper). | `agentes/endurecimiento/e2-02-health-real.md` |
| E2.3 | Chat integrable + tests | Inyección de cliente Ollama (DI) en `llm.py`; tests de `/api/chat` y `/api/chat/stream` con Ollama mockeado. | `agentes/endurecimiento/e2-03-chat-integrable.md` |
| E2.4 | CI + deps + CORS | GitHub Actions (pytest/ruff + tsc/vitest/build), deps reproducibles (`requirements.in`), CORS restringido a `localhost`. | `agentes/endurecimiento/e2-04-ci-deps-cors.md` |

### FASE 3 — Persistencia y dominio (detallada)

`Router → Service → Repository`, mensajes append-only y FK reales. Secuencia:

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| E3.1 | Mensajes append-only (backend) | Añadir `id` a `ChatMessage`; columna `message_id` + índice único en `messages`; `save_conversation` append-only cuando hay ids (fallback legacy); `get_conversation` devuelve `id`. | `agentes/endurecimiento/e3-01-mensajes-append-only.md` |
| E3.2 | Mensajes con id (frontend) | Generar `id` (`crypto.randomUUID()`) en `useChat`; añadir `id` al tipo `Message`; propagar en persistencia. | `agentes/endurecimiento/e3-02-mensajes-id-frontend.md` |
| E3.3 | Capa de dominio (Service → Repository) | Separar `store` en `repositories/` (users, conversations, pronunciation) + `domain/` (servicios async); routers dependen de `domain/`. | `agentes/endurecimiento/e3-03-capa-dominio.md` |
| E3.4 | FK reales | `FOREIGN KEY user_id → users(id)` en `conversations` y `pronunciation_attempts` con migración idempotente (reconstrucción de tabla). | `agentes/endurecimiento/e3-04-fk-reales.md` |

### FASE 4 — Learning Profile (detallada)

Eventos de aprendizaje, vocabulario, errores gramaticales recurrentes, estimación CEFR y
recomendaciones. Secuencia (backend primero, frontend al final):

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F4.1 | Eventos de aprendizaje | Tabla `learning_events` (append-only, FK) + CRUD + `POST/GET /api/learning/events`. | `agentes/endurecimiento/f4-01-eventos-aprendizaje.md` |
| F4.2 | Vocabulario | Extractor determinista + tabla `vocabulary` (UNIQUE user_id+word, upsert) + `POST /api/vocabulary/analyze`, `GET /api/vocabulary`. | `agentes/endurecimiento/f4-02-vocabulario.md` |
| F4.3 | Errores gramaticales recurrentes | Reglas regex deterministas + tabla `grammar_errors` (UNIQUE user_id+rule, upsert) + `POST /api/grammar/analyze`, `GET /api/grammar/errors`. | `agentes/endurecimiento/f4-03-gramatica.md` |
| F4.4 | CEFR + recomendaciones | `estimate_cefr`/`recommendations` puras + tabla `learning_profile` + `GET /api/profile` (compone todo). | `agentes/endurecimiento/f4-04-cefr-perfil.md` |
| F4.5 | Frontend Learning Profile | Tipos + `api/learning` + `utils/cefr` + componente `LearningProfile` + integración en `useChat` (analiza el texto tras cada envío). | `agentes/endurecimiento/f4-05-frontend-perfil.md` |

> **Notas de Fase 4:** el análisis (vocabulario/gramática) es **determinista, sin LLM** (premisa
> 12). La estimación CEFR es **heurística v1** (la evaluación CEFR real es la Fase 8). La tabla
> `learning_events` queda lista pero aún sin consumidor de UI (se cableará en Fase 6).

### FASE 5 — Tutor Policy + Context Builder (detallada)

Política de corrección (correctness policy) por nivel CEFR y Context Builder que inyecta el
perfil del alumno al system prompt del tutor. Secuencia (backend primero, frontend al final):

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F5.1 | Tutor Policy (correctness policy) | `services/policy.py` (`correctness_guidance(cefr_level)` pura) + tests. | `agentes/endurecimiento/f5-01-politica-correccion.md` |
| F5.2 | Context Builder + perfil al prompt | `services/context.py` (`build_system_prompt`), `ChatRequest.user_id` opcional, `llm.py` acepta `system_prompt`, router resuelve el perfil vía `domain/profile`. | `agentes/endurecimiento/f5-02-context-builder.md` |
| F5.3 | Frontend propagar user_id | `api/chat.ts` + `hooks/useChat.ts` envían `user_id` al chat. | `agentes/endurecimiento/f5-03-frontend-user-id.md` |

> **Notas de Fase 5:** `user_id` es **opcional** en `ChatRequest` (sin ventana rota); si falta o
> el usuario no existe, se usa el prompt base. La política de corrección es determinista y sin
> LLM (premisa 12).

### FASE 6 — Progreso pedagógico real (detallada)

Pasar de "cuánto" a "cómo evoluciona en el tiempo": **tendencias**, **racha/constancia**,
**dominio** (errores que se resuelven vs. persisten) e **hitos**. Todo determinista, sin LLM.
Decisiones: un único endpoint nuevo `GET /api/progress/history`; no se rompen `/api/progress` ni
`/api/profile`; el frontend **reemplaza** `ProgressSummary` por un dashboard (responsive total
móvil/tablet). Se reutiliza la tabla `learning_events` (F4) que F6.1 activa.

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F6.1 | Registro automático de eventos | Activar `learning_events`: `chat` (message/exercise/correction por modo), `pronunciation` (pronunciation), `conversations` (conversation). | `agentes/endurecimiento/f6-01-registro-eventos.md` |
| F6.2 | Progreso histórico (backend) | `services/trends.py` + `services/mastery.py` (puros), `repositories/progress.py`, `domain/progress.py`, `schemas/progress.py` (SeriesPoint, Streak, ErrorMastery, Milestone, ProgressHistory), `routers/progress.py` (`GET /api/progress/history`). | `agentes/endurecimiento/f6-02-progreso-historico.md` |
| F6.3 | Frontend dashboard | Tipos + `api/progress.ts` (`getProgressHistory`) + `api/learning.ts` (`getEvents`), helpers `utils/progress.ts`, `components/ProgressDashboard.tsx` (reemplaza `ProgressSummary`), `hooks/useChat.ts`, `App.tsx`, `index.css`. | `agentes/endurecimiento/f6-03-frontend-dashboard.md` |

### FASE 7 — Pronunciación fonética (detallada)

Sustituir el evaluador único actual (`difflib` a nivel de caracteres) por un **evaluador
compuesto determinista** (sin LLM, premisa 12): precisión por palabra (alineación) + similitud
fonética (Soundex) + similitud de caracteres, ponderado. El **breakdown** (detalle por palabra)
viaja **solo en la respuesta** (sin migración de `pronunciation_attempts`). Backend primero,
frontend al final.

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F7.1 | Evaluador compuesto (backend) | `services/phonetics.py` (puro: `tokenize`, `soundex`, `word_alignment`, `word_accuracy`, `phonetic_similarity`, `composite_score`), `services/pronunciation.py` delega, `schemas/pronunciation.py` (`WordSubstitution`, `PronunciationBreakdown`, `PronunciationResponse` ampliado). | `agentes/endurecimiento/f7-01-evaluador-compuesto.md` |
| F7.2 | Frontend feedback fonético | Tipos + `utils/pronunciationFeedback.ts` (puro) + `components/PronunciationPractice.tsx` (muestra el breakdown). | `agentes/endurecimiento/f7-02-frontend-feedback.md` |

> **Notas de Fase 7:** pesos compuestos `word 0.6 / phonetic 0.3 / char 0.1`; umbrales
> `good ≥80`, `fair ≥50` intactos. Soundex es una variante simplificada determinista (sin deps).

### FASE 8 — Listening / Speaking / CEFR (detallada)

CEFR real (evaluador multi-señal), fluidez oral (speaking con duración) y listening
(banco + preguntas). Todo determinista, sin LLM (premisa 12). Backend primero (F8.1–F8.3),
frontend al final (F8.4). Decisiones: evaluador CEFR **multi-señal rico** con bandas por
destreza; fluidez **con duración** (el STT expone timestamps/duración); **incluir listening**
ya (banco estático + TTS ya existente en `/api/tts`).

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F8.1 | CEFR real multi-señal (backend) | `services/cefr.py` (`evaluate_cefr` + bandas + descriptor; `estimate_cefr` delega), `schemas/profile.py` (`CefrBands`), `domain/profile.py`. | `agentes/endurecimiento/f8-01-cefr-multisenial.md` |
| F8.2 | Fluidez oral / speaking (backend) | `services/fluency.py` (`compute_fluency` WPM), `services/stt.py` (`transcribe_with_timing`), `schemas/pronunciation.py` (`FluencyStats`), `routers/pronunciation.py`. | `agentes/endurecimiento/f8-02-fluidez-oral.md` |
| F8.3 | Listening: banco + preguntas (backend) | `services/listening.py` (banco + `score_answer`), `schemas/listening.py`, `repositories/listening.py`, `domain/listening.py`, `routers/listening.py`, tabla `listening_attempts` en `db.py`, registro en `main.py`. | `agentes/endurecimiento/f8-03-listening.md` |
| F8.4 | Frontend: CEFR + speaking + listening UI | Tipos, `api/listening.ts`, `utils/fluency.ts`, `utils/cefr.ts` (`bandLabel`), `LearningProfile` (bandas+descriptor), `PronunciationPractice` (fluidez), `ListeningPractice.tsx`, `App.tsx`, `index.css`. | `agentes/endurecimiento/f8-04-frontend.md` |

> **Notas de Fase 8:** la fluidez se calcula con `info.duration` de faster-whisper (WPM =
> palabras / minutos); niveles `fluent ≥120`, `good 60–119`, `slow <60`. El CEFR global es un
> punto-sum ponderado con bandas por destreza (vocabulario, gramática, fluidez, pronunciación)
> y un descriptor descriptivo. Listening es un banco estático de 8 preguntas A1–B1 (opción
> múltiple, evaluación determinista) reproducidas con el TTS existente.

### FASE 9 — Evaluación objetiva del tutor (detallada)

Evaluar al tutor de forma **objetiva y determinista** (sin LLM-juez, premisa 12) con señales
medibles: si corrige el error conocido (`correction`), cuánto habla en inglés (`english`), la
concisión (`conciseness`) y si invita a seguir (`engagement`). Backend primero (F9.1–F9.2),
frontend al final (F9.3, opcional). Decisiones: evaluador puro en `services/evaluation.py` con
corpus canónico; script por lotes para puntuar un modelo; panel de calidad en el frontend que
evalúa las respuestas del tutor en local.

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| F9.1 | Evaluador objetivo del tutor (backend) | `services/evaluation.py` (`evaluate_tutor_reply`, `summarize`, corpus `EVAL_CASES`) + tests. | `agentes/endurecimiento/f9-01-evaluador-tutor.md` |
| F9.2 | Informe agregado + script por lotes (backend) | `build_report`/`format_report`/`build_tutor_prompt` en `services/evaluation.py`, `scripts/eval_tutor.py` (CLI), tests. | `agentes/endurecimiento/f9-02-informe-agregado.md` |
| F9.3 | Panel de calidad del tutor (frontend) | `utils/tutorEvaluation.ts` (puro) + `components/TutorQualityPanel.tsx` + integración en `App.tsx` + estilos responsive. | `agentes/endurecimiento/f9-03-panel-calidad-tutor.md` |

> **Notas de Fase 9:** el evaluador es determinista y sin LLM-juez (premisa 12); la señal
> `correction` requiere el caso con `expected_fragments` (el panel frontend usa solo las
> señales libres de contexto). El script `scripts/eval_tutor.py` es un CLI de utilidad: puntúa
> un modelo contra el corpus y no persiste nada en BD.

### FASE 10 — Release 1.0 realmente estable (CERRADA)

Versión unificada, gate verde completo y entrega del lanzador de escritorio.

| # | Subagente | Responsabilidad | Briefing |
|---|---|---|---|
| A.1 | Launcher: núcleo puro | `launcher/core.py` (rutas, comandos, normalización de estado) + tests pytest. | `agentes/endurecimiento/a1-launcher-core.md` |
| A.2 | Launcher: GUI + procesos + atajo | `launcher/launcher.py` (GUI `tkinter`), `process_manager.py`, `status.py`, `make_icon.ps1`, `install_shortcut.ps1`, `icon.ico` + tests. | `agentes/endurecimiento/a2-launcher-gui.md` |

> **Notas de Fase 10:** la versión `1.1.0` vive en `backend/config.py::VERSION` y se expone en
> `/api/health` y en la raíz `/`; el frontend la refleja en `package.json`. El launcher es un
> tercer componente (`launcher/`) con su propio `pyproject.toml` (ruff) y tests pytest, que
> arranca/para backend y frontend y muestra el estado de servicios, BD y usuarios. El acceso
> directo del escritorio se crea con `launcher/install_shortcut.ps1`.

## Protocolo anti-saturación y documentos de paso

1. **Contexto limpio por subagente.** Cada subagente arranca con su briefing y no depende
   del historial (premisa 5). Si alucina (inventa rutas/APIs, contradice `docs/`), se detiene
   y se relanza con contexto limpio.
2. **Documento de paso maestro.** `docs/RELEVO.md` se actualiza tras cada subagente:
   qué se hizo, archivos tocados, tests, y el siguiente paso. Es el ancla ante un reinicio.
3. **Cambio de agente (gerente).** Cuando el contexto del gerente se acerque a saturación
   (respuestas incoherentes, repetir decisiones, inventar rutas), se abre un gerente nuevo y
   se le pasa `docs/RELEVO.md` + el briefing del siguiente subagente. Avisar explícitamente
   al usuario antes de hacerlo.
4. **Gates entre fases.** `pytest tests/ -q`, `npx tsc --noEmit`, `npm test`, `npm run build`
   verdes antes de avanzar. Un commit por subagente con mensaje `tipo: descripción`.
5. **Anti-pérdida de código.** Un cambio se integra y verifica antes del siguiente; nada se
   mezcla (premisa 6). Los briefings viven en `agentes/endurecimiento/` y quedan en git.

## Reglas que se respetan siempre

- No PostgreSQL/Redis/microservicios/Docker complejo/auth cloud/LangChain/RAG. (premisa 2)
- No tocar código no relacionado con el subagente en curso.
- Tipado fuerte en ambos lados; tests obligatorios como parte de "terminado".

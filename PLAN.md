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
- ✅ Versión estable `3.10.0` — **Conversation por rutas CEFR: página única de mini-diálogos guiados multi-turno**
  (APRENDER → Conversation deja el chat libre (ahora en su propia raíz `/chat`,
  accesible desde la propia página) y pasa a una página única como Speaking:
  el escenario de práctica —un mini-diálogo guiado multi-turno con el tutor:
  situación, roles y metas comunicativas, y se conversa por texto o micrófono
  hasta cumplirlas— vive arriba y, debajo, el mapa de rutas A1–C2 con anillos y
  sus modos (Practicar el nivel / Repetir fallidos / Repasar aprendidos). Banco
  oficial nuevo y auditable `curriculum/conversation_corpus.json` (v1.0.0: 11
  mini-diálogos por nivel) y el intento se evalúa sobre el transcripto completo
  con el pipeline LLM de evidencia (task_type conversation) fusionado con la
  señal objetiva de interacción. La ruta es un hito de práctica —`functional`
  como techo, nunca certifica—; demostrar el nivel sigue siendo del Speaking
  Assessment + evidencia + retención). Base: `3.9.0`
- ✅ Versión estable `3.9.0` — **Pronunciation por rutas CEFR: página única read-aloud con operativa tipo Listening/Speaking**
  (APRENDER → Pronunciation deja la práctica libre de 3 frases hardcodeadas y
  pasa a una página única como Speaking/Listening: la frase modelo a leer en voz
  alta vive arriba —la escuchas con TTS local y te grabas leyéndola— y debajo el
  mapa de rutas A1–C2 con anillos y el panel del nivel (Repetir fallidas /
  Repasar aprendidas / Practicar o repasar el nivel). Banco oficial nuevo y
  auditable `curriculum/pronunciation_corpus.json` (v1.0.0: 20 frases por nivel)
  y la evaluación es determinista y barata: Whisper + `score_pronunciation`
  (score ≥80 = superada), sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, nunca certifica—; demostrar el nivel sigue siendo del
  Speaking Assessment + evidencia + retención). Base: `3.8.0`
- ✅ Versión estable `3.8.0` — **Speaking por micro-conversaciones guiadas, con operativa tipo Listening**
  (APRENDER → Speaking es ahora una página única con scroll como Listening: el
  escenario de práctica —tarjeta de micro-conversación guiada con situación, rol
  y línea del interlocutor con voz, a la que respondes hablando— vive arriba y,
  bajo él, el mapa de rutas A1–C2 con anillos y sus modos (practicar el nivel,
  repetir fallidas, repasar aprendidas, añadir práctica extra) más el acceso al
  Speaking Assessment. El banco oficial `speaking_corpus.json` se regenera como
  tarjetas `{setup, you, app_line, model_response}` (v2.0.0: A1 36 / A2 32 / B1
  28 / B2 22 / C1 16 / C2 14) y el intento deja de ser read-aloud: cada respuesta
  se evalúa como respuesta abierta con el pipeline LLM+evidencia existente
  (`extract_speaking_evidence` + `scores_from_evidence`), con error transitorio
  503 si el extractor falla (nunca se puntúa en falso). El audio TTS se sirve por
  tipo con caché (`?kind=opening|model`). La ruta sigue siendo un hito de
  práctica —`functional` como techo, nunca certifica—; demostrar el nivel sigue
  siendo del Speaking Assessment + escenarios/misiones + retención). Base: `3.7.0`
- ✅ Versión estable `3.7.0` — **Speaking por rutas CEFR + fuente compacta en logs del lanzador**
  (APRENDER → Speaking es ahora un mapa de rutas A1–C2 con frases modelo
  read-aloud y banco curado oficial nuevo (`speaking_corpus.json`): practicar el
  nivel, repetir fallidas, repasar aprendidas y añadir práctica extra generada,
  todo puntuado en local sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, puerta con cobertura/precisión/checkpoint sobre el
  banco oficial—; demostrar el nivel sigue siendo del Speaking Assessment +
  escenarios/misiones + retención, nunca de la ruta. El lanzador muestra los
  logs con fuente compacta monospace). Base: `3.6.2`
- ✅ Versión estable `3.6.2` — **Estado del servidor en el lanzador + corrección del 429 espurio**
  (el «Demasiadas peticiones» lo devolvía el rate limiter propio
  (`SecurityMiddleware`), no Ollama, cuando el servidor local se saturaba:
  las sondas `/api/health` quedan exentas de cupo y de 429, los topes suben
  para el uso local razonable, cada rechazo queda registrado y visible en el
  nuevo `GET /api/system/status` —generación de práctica extra en curso por
  nivel + rechazos del último minuto—, el mensaje de error 429 se localiza en
  la lengua de la UI (`errors.rateLimited`) y el launcher gana la sección
  «Actividad del servidor» con la píldora de cabecera en ámbar
  («En marcha · generando…» / «saturado») cuando el backend trabaja o
  rechaza). Base: `3.6.1`
- ✅ Versión estable `3.6.1` — **Atajos de APRENDER + coherencia de idioma**
  (la franja superior de cada práctica de APRENDER conserva la flecha al hub y
  añade un atajo directo entre las 6 actividades —Listening/Speaking/
  Pronunciation/Conversation/Vocabulary/Grammar—; los nombres de actividad se
  unifican en inglés en ambos idiomas y se localiza el chrome que se pintaba en
  inglés con la UI en español: tipos de audio y buckets de retención en
  listening, fluidez y avisos de pronunciación, píldoras y estabilidad del plan
  del día, foco/acción de Writing, título/pts de Speaking, PASS/DUE del curso y
  skip-link). Base: `3.6.0`
  — **Listening: práctica ilimitada + repaso por ruta**
  (cada ruta A1..C2 se puede ampliar con práctica generada por IA local —nunca
  contenido oficial: la puerta, el estado functional/demonstrated y el routing
  adaptativo siguen anclados al banco curado, así que añadir extras no revoca ni
  encarece certificar—; el anillo crece con el desglose "oficiales + extra" y
  cada ruta permite "Repasar lo aprendido", no solo las falladas). Base: `3.5.8`
  — **Auditoría de UI: contraste claro/oscuro + QR**
  (QR visible en modo oscuro sobre tarjeta blanca fija, contraste WCAG corregido
  en insignias CEFR, avisos ámbar, fechas/texto tenue y avatar "?" sin perfil; la
  ProfileGate de V3.5.7 se estabiliza en tests visuales con perfil de test
  mockeado). Base: `3.5.0` — **P2 de la Constitución pedagógica en UI**
  (pantallas honestas: la práctica de listening se lee por estado de ruta
  —`functional` es hito de práctica y solo `demonstrated` (puerta + retención
  retardada estable ≥7 días) muestra «A1 Listening — demonstrated»—, todo badge
  de nivel estimado lleva el calificador «estimado · no certificado» y se eliminó
  el código muerto `modeCefrLevel`/`modeCefrBand`; ver `CHANGELOG.md` y
  Constitución §9). Base: `3.4.0` — **P1 de la Constitución pedagógica en código**
  (matriz CEFR a C1/C2 × las 8 destrezas con evidencia por kind, certificación de
  nivel con retención —*completado ≠ certificado*— y Lexical Units con Vocabulary
  Coverage Indicator receptivo/productivo). Base: `3.3.0` — **P0 de la
  Constitución pedagógica en código** (sin
  interpretación palabras→nivel, registro por competencia Estimado/Demostrado con
  `competence_states`, listening como evidencia del Student Model con retención).
  Base: `3.2.1` — **Auditoría pedagógica del modelo de nivelación** (solo
  documentación; ver `docs/audit/H-NIVELACION-PEDAGOGICA.md` y
  `docs/CONSTITUCION-PEDAGOGICA.md`). Base: `3.2.0` — **Calibración pedagógica de
  niveles** (nivel estimado global honesto con `Pre-A1`, Listening como rutas con
  puerta de evidencia y corpus A1/A2 → 200 ítems c/u). Sobre la base de **V3.1 UI**
  (release de interfaz y navegación; ver `docs/UI_V3.1.md`). El stack
  pedagógico previo sigue en `3.0.0` — **V3.0
  Beta freeze** tras el stack pedagógico
  V2.7–V2.12 (Depth → Listening → Speaking Mission → Assessment 2.0 → FSRS →
  Evidence Graph). Gates en `docs/BETA_V3.md` + `docs/BETA_GATES.md`. Base previa:
  **FASE 1–5** de la auditoría externa a V1.29 (LAN/HTTPS/audio móvil):
  **V1.30** LAN + Mobile 100% (mDNS real, test de micrófono con medidor, QR de conexión,
  `/help/connect`), **V1.31** Adaptive Engine 2.0 (Priority Engine + "Why this activity?"),
  **V1.32** Curriculum 2.0 (escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones),
  **V1.33** Listening 2.0 (Listening Resilience + `context` del corpus), **V1.34** Speaking 2.0
  (pronunciation proxy + Interaction Quality + Conversation Endurance), **V1.35** gestión en-app
  de la biblioteca de audio humano (Ajustes → Audio), **V1.36** Audio Corpus 1.0 (corpus de audio
  humano versionado + pipeline de grabación + importación masiva), **V1.37** Audio QA + Content
  Audit (QA acústica + content integrity check + Content Audit Dashboard + candado admin/PIN),
  **V1.38** Course Engine (secuenciación Course→Unit→Lesson→Practice→Review→Assessment con gating
  por objetivo + progreso visible "¿dónde estoy?") y **V1.39** Mastery 2.0 (`MasteryRecord`
  transversal para las 9 destrezas + CEFR readiness con banda cualitativa "B1 developing" en lugar
  de media simple + curva de olvido/review_due conectada a todo el currículo), y **V1.40** Speaking 3.0
  (catálogo de 8 escenarios comunicativos con objetivo comunicativo y métricas declaradas
  task_completion/interaction/fluency/repair/turn_taking + honestidad del proxy de pronunciación en la
  UI: "Confidence: medium · automated proxy"), y **V1.41** Beta Hardening (sin features nuevas: backup
  local completo SQLite+perfil+progreso+evidencia+manifest+WAV+settings con restore/export y
  auto-backup diario "keep 7", endpoints admin con PIN local, middleware de seguridad LAN
  origin-check + rate limiting, panel de backup en Ajustes → Sistema, matriz de dispositivos
  actualizada PC/Android/iPhone/iPad con HTTPS/mDNS/mic/audio/listening/speaking/recovery, a11y
  skip-link + `lang` sincronizado y code-splitting de vendors React/motion/iconos), y **Beta 1.0**
  (5 gates de salida 10/10: Infra/Curriculum/Listening+Speaking/Adaptive+Mastery/UX — ver
  `docs/BETA_GATES.md`). Sobre la base **V1.21**
  (cierre de la auditoría pedagógica A1→B2: corpus de audio humano 1.0 + validación determinista
  audio↔metadata + separación del proxy de pronunciación del audio real + evidencia
  familiar/transfer/novel + Interaction 3.0 + matriz de assessment CEFR; y nueva UI de 3 paneles
  con barra de estado y navegación por destrezas, más el **Learning Home** como pantalla central)
  y **V1.20** (pronunciación fonémica P6, turn-taking real e infraestructura de biblioteca de
  audio humano).
- **V3.2.x (2026-09-03) — Auditoría pedagógica del modelo de nivelación (solo documentación)**:
  dossier desk `docs/audit/H-NIVELACION-PEDAGOGICA.md` (hallazgos H1–H7: palabras→nivel aún en el
  modelo legacy, sin par Estimado/Demostrado, listening sin evidencia en el Student Model, matriz
  CEFR solo hasta B2, retención fuera de la certificación, mastery duplicado, estimado crudo en la
  UI) y especificación normativa **`docs/CONSTITUCION-PEDAGOGICA.md`**: separa Practice Level /
  Mastery / Estimated CEFR / Demonstrated CEFR con 4 estados por competencia
  (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), define cobertura léxica como indicador
  (no puerta), Lexical Units, progresión de listening y el Mastery Gate general (coverage +
  accuracy + subskills + retención ≥ 7 días + checkpoint). Los incrementos de código derivados
  (P0/P1/P2) quedan priorizados en la sección 9 de la constitución; no se ejecutan en esta iteración.
- ✅ **V2.0 Beta 1.0** (5 gates de salida 10/10), **V2.1 Content** (Content Quality Gate + corpus de
  listening 40→100 + escenarios de speaking 8→20 + niveles C1/C2), **V2.2 Academy/Course Engine**
  (métrica única "TOTAL VALIDATED LEARNING ITEMS" = 143, plantilla fija de 7 secciones por unidad,
  Mastery Gates por unidad, tríada Progress/Mastery/Readiness y pantalla Learning Journey) y
  **V2.3 Personal Dictionary + evidencia por ítem léxico** (siembra de vocabulario/estructuras desde
  el currículo, estado `known`/`learning`/`weak`/`mastered` + `recall` por ítem reutilizando la
  curva de olvido, endpoint `/api/vocabulary/lexicon` y pantalla Personal Dictionary) y
  **V2.4 Curriculum Coverage** (auditoría de cobertura curricular: recorre Pre-A1→C2 × 7 secciones,
  cruza el contenido del curso con los bancos de listening/speaking y genera
  `curriculum_coverage_report.json` con la métrica "TOTAL CURRICULUM COVERAGE", distinta de
  "TOTAL VALIDATED LEARNING ITEMS").
- ✅ **V2.5 Curriculum Completion** (completado; cierra los huecos de la auditoría V2.4). Hecho:
  **C1 listening C1/C2** (corpus 100→140, `c101`–`c140`), **C2 speaking C2** (escenarios 20→26),
  **C3 interaction A1/A2/B2/C1/C2** (subskills `interaction`+`turn_taking` en 39 objetivos,
  TOTAL VALIDATED 143→189, cobertura 37/49→42/49) y **C4 wiring curso↔bancos**
  (`listening_items` + `scenario_ids` por objetivo, 18 objetivos de listening y 50 de speaking
  cableados a los bancos; conteo y validación reflejan las referencias).
- ✅ **V2.6-C1 Capa de medición** (en curso): "cobertura" ≠ "profundidad". Nuevas métricas en
  `services/curriculum_coverage.py`: **UNIT COVERAGE** por unidad, **CEFR DEPTH SCORE** (0..100,
  4 componentes auditables), **UNIT LEARNING LOOP** (9 fases por unidad), drill-down
  LEVEL→UNIT→LESSON→OBJECTIVE y **Curriculum Quality Dashboard** (7 dimensiones + before/after).
  Overall **56,8**; puntos débiles medidos: review/assessment 23,5, listening 47,8 y las fases de
  cierre del loop (retrieve/transfer 0%, assess/review 19,4%). Loop etiquetado por unidad (V2.6-C5:
  50,6% → 84,7%); queda ampliar C1/C2 depth y subir unit coverage.
- ✅ **V2.7 Curriculum Depth (piloto B1)** (hecho). "Cobertura ≠ profundidad" convertido en acción
  con dos hilos: **(1) alineación de medición** — `unit_sections()` cuenta review/assessment por
  marcadores `phase` (consistente con `unit_learning_loop()`), no solo en el módulo Final — y
  **(2) contenido B1 real** — de 10 a 18 objetivos (interaction, listening, speaking y discourse
  markers por unidad, loop cerrado en todas las unidades). Dashboard: Overall **56,8 → 84,0**,
  Depth media 55,7 → 68,0, review/assessment 23,5 → 100, loop 84,7 → 88,4%; **B1 depth 55,7 → 90,4**
  (meta ≥82 cumplida). Plantilla maestra en `docs/UNIT_ARCHITECTURE.md` y briefings de escalado
  `agentes/curriculum/v27-depth-{a2,b2,c1,c2}.md`. Delta en `docs/CURRICULUM_COVERAGE.md`.
- ✅ **V2.7 Curriculum Depth (escalado A2–C2)** (hecho). La plantilla de "Unit Architecture"
  se aplicó al resto de niveles: **A2 11→17 objetivos (depth 60,9→82,6), B2 9→13 (68,4→82,7),
  C1 7→14 (55,5→82,6), C2 5→14 (49,2→82,2)**, cerrando el loop de aprendizaje y añadiendo
  listening/grammar/speaking/interaction por unidad. Dashboard: Overall **84,0 → 94,5**,
  Depth media 68,0 → 84,0, Listening 56,2 → 91,7, Speaking/Interaction 88,9 → 100, loop
  88,4 → 98,7%. Todos los niveles con curso superan depth 80. Queda como hueco real
  **Listening en A1** (5 unidades) → objetivo de V2.8.
- ✅ **V2.8 Listening Curriculum** (hecho). Cierre del listening en **A1** (+5 objetivos,
  loop Final) → **listening por unidad 100%** y **fase `listen` 100%** en todos los
  niveles. Progresión CEFR por subskill (`LISTENING_FOCUS_BY_LEVEL` en
  `services/curriculum.py`): A1 word recognition → A2 information → B1 natural speech
  → B2 inference → C1/C2 nuance/pragmatics. Métrica `listening_curriculum()` (alineación
  foco/subskill **100%** en 38 objetivos). Dashboard: Overall **95,7**, Listening **100%**,
  loop **100%**. Referencia en `docs/LISTENING_CURRICULUM.md`.
- ✅ **V2.9 Speaking Mission Performance** (hecho). Loop
  **Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement**:
  motor puro (`speaking_mission.py`), sesión trazable, API Academy y panel UI.
  Mejora visible (delta overall + por criterio). Referencia en
  `docs/SPEAKING_MISSION.md`.
- ✅ **V2.10 Assessment 2.0** (hecho). Escalera
  **formative → unit → progress → level → retention** + readiness derivado
  y mastery gate (initial/practice/transfer/novel/delayed). Motor
  `assessment_v2.py`, sesiones, API y UI en pestaña Assessment.
  Referencia en `docs/ASSESSMENT_2.md`.
- ✅ **V2.11 SRS / FSRS** (hecho). Scheduler FSRS-lite sobre el Evidence Model:
  cartas skill/lexicon, cola due auditable (What/Why/When/How strong/Last/Next),
  grades Again/Hard/Good/Easy. Referencia en `docs/FSRS.md`.
- ✅ **V2.12 Knowledge / Evidence Graph** (hecho). Can-do → dimensiones →
  limiting factor → mastery; Adaptive Engine con `because[]` estructurado.
  Referencia en `docs/EVIDENCE_GRAPH.md`.
- ✅ **V3.0 Beta freeze** (hecho). Funcionalidad congelada tras V2.7–V2.12;
  fase abierta: contenido + calibración + UX + pruebas reales.
  Gate `scripts/check_beta_v3.py` + `docs/BETA_V3.md`.
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

### M16 — FASE 1–5 de la auditoría externa (LAN/móvil → Speaking 2.0)  [HECHO ✔]
> Ejecutadas **directamente por el gerente** (sin briefings separados); ver `CHANGELOG.md` y
> `docs/RELEVO.md` (sección 37.6–37.11).
- **V1.30 LAN + Mobile 100%**: mDNS real (`local_url_available`), recuperación de permisos de
  micrófono, test de micrófono con medidor, QR de conexión y `/help/connect`.
- **V1.31 Adaptive Engine 2.0**: Priority Engine (`priority_signals`/`priority_score`/
  `explain_priority`) + "Why this activity?" en la tarjeta de siguiente mejor actividad.
- **V1.32 Curriculum 2.0**: escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones
  (`/api/academy/cefr-ladder`).
- **V1.33 Listening 2.0**: Listening Resilience por condición de escucha + `context` del corpus.
- **V1.34 Speaking 2.0**: pronunciation proxy + Interaction Quality por sub-dimensión +
  Conversation Endurance (`/api/academy/speaking/endurance`).
- Verificado: backend 843 tests + ruff limpio; frontend 234 tests + `tsc`/`build` OK; launcher 64
  tests; Playwright 14 passed + 10 skipped.

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
| V1.21 UI Learning Home (HOME como centro) | plan Cursor `v1.21_ui_learning_home` | ✔ hecho |
| V1.30–V1.34 FASE 1–5 auditoría (LAN/móvil → Speaking 2.0) | directo del gerente (sin briefings) | ✔ hecho |
| V2.7 Depth B1 (piloto) | directo del gerente (plan Cursor `v2.7_curriculum_depth`) | ✔ hecho |
| V2.7 Depth A2 | `agentes/curriculum/v27-depth-a2.md` | ✔ hecho |
| V2.7 Depth B2 | `agentes/curriculum/v27-depth-b2.md` | ✔ hecho |
| V2.7 Depth C1 | `agentes/curriculum/v27-depth-c1.md` | ✔ hecho |
| V2.7 Depth C2 | `agentes/curriculum/v27-depth-c2.md` | ✔ hecho |
| V2.8 Listening Curriculum | directo del gerente | ✔ hecho |
| V2.9 Speaking Mission Performance | directo del gerente | ✔ hecho |
| V2.10 Assessment 2.0 | directo del gerente | ✔ hecho |
| V2.11 SRS / FSRS | directo del gerente | ✔ hecho |
| V2.12 Evidence Graph | directo del gerente | ✔ hecho |
| V3.0 Beta freeze | directo del gerente | ✔ hecho |

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

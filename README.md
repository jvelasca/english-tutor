# English Tutor (100% local)

App para conversar con un modelo de IA **local** (Ollama), pensada para convertirse en un
profesor de inglés totalmente local. Sin Internet, sin cuentas, sin costes.

## Documentación (leer primero)

- **`docs/PREMISAS.md`** — premisas y reglas del proyecto (fuente de verdad).
- **`docs/ARQUITECTURA.md`** — estructura modular y responsabilidades por capa.
- **`docs/DESARROLLO.md`** — cómo arrancar y trabajar desde 0, flujo con subagentes, Git/GitHub.
- **`PLAN.md`** — hoja de ruta y tablero de subagentes.

## Repositorio

- **GitHub (público):** https://github.com/jvelasca/english-tutor — seguimiento con issues, PR y releases.
- Última versión estable: **v3.73.4**.

## Estructura

- `backend/` — API en Python con **FastAPI + Pydantic** (tipado fuerte). Habla con Ollama.
- `frontend/` — Interfaz web con **Vite + React + TypeScript**.
- `launcher/` — lanzador de escritorio (GUI `tkinter`): arranca/para la app y muestra su estado.
- `agentes/` — briefings autocontenidos de subagentes (premisa 5: todo trabajo se descompone en subagentes).
- `docs/` — documentación del proyecto.

## Funcionalidades

- **Chat por texto** con streaming (SSE) contra Ollama.
- **Voz 100% local**: transcripción (Whisper) y síntesis (Piper).
- **Memoria e historial**: conversaciones guardadas en SQLite (sidebar).
- **Modo profesor (M4)**: 4 modos de tutor (conversación, gramática, ejercicios, pronunciación)
  y **corrección de pronunciación** (graba y recibe una puntuación).
- **Multi-usuario (M7)**: perfiles locales con conversaciones e historial **independientes**
  (selector de perfil en la cabecera, aislamiento total de datos entre usuarios).
- **Diseño y UX (M8)**: tema claro/oscuro, responsive (móvil/escritorio), accesibilidad
  y sistema de tokens de diseño.
- **Voz continua / manos libres (M10)**: modo conversación por voz sin pulsar botones
  (VAD por silencio vía Web Audio API, transcripción y respuesta hablada automáticas).
- **Progreso pedagógico real (F6)**: dashboard con tendencias, racha, dominio de errores e hitos.
- **Pronunciación fonética (F7)**: evaluador compuesto (palabras + Soundex + caracteres) con fluidez (WPM).
- **Listening / nivel estimado (F8)**: ejercicios de comprensión auditiva y **nivel estimado** multi-señal (heurístico, no certificación CEFR).
- **Listening Engine 4.0 (V3.27-V3.29)**: micro-flujo pedagógico por ítem servido por el backend (`flow` pre/while1/while2/post/shadowing + `transcript_policy`, perfil auditivo casos A-D) · **Fase 2**: AudioController rico (play/seek/rate con pitch/loop/segmentos), tareas bottom-up derivadas del corpus (cloze auditivo, dictado parcial, segmentación — nunca en certificación), transcript dinámico con sync grueso de frase y Shadowing 2.0 con playback de la grabación del alumno · **Fase 3 (núcleo)**: karaoke palabra a palabra (`word_alignment_proxy` offline con faster-whisper), controles precisos (seek + bucle A/B), salto a la palabra fallada (normal/slow) y evidencia de palabra fallada. Detalle en `docs/LISTENING_ENGINE_4.0.md`.
- **Evaluación objetiva del tutor (F9)**: métricas deterministas del tutor (backend + panel).
- **Lanzador de escritorio**: GUI que arranca/detiene la app y muestra estado, BD y usuarios.
- **Acceso LAN / móvil**: HTTPS autofirmado en la red local, QR de conexión, verificación real de
  mDNS (`<host>.local`), test de micrófono con medidor de nivel y página `/help/connect` para
  confiar el certificado en Windows, Android e iPhone/iPad.
- **Adaptive Engine 2.0**: siguiente mejor actividad con prioridad explicable y "¿por qué?"
  (recencia, retención, confianza, evidencia, transferencia/novedad) en la tarjeta de inicio.
  **V3.72**: ese «por qué» (frase del motor, `because[]` y factor limitante) se pinta también en el
  pie «Next» que aparece al terminar cualquier práctica y en las filas de la cola de repaso, con una
  sola pieza compartida (`components/WhyThisActivity.tsx`) y sin recalcular señales en el cliente.
  **Knowledge Graph + Daily Adaptive Plan (V3.17)**: el plan diario deriva del Evidence Graph —
  la destreza débil se practica sobre el objetivo que su nodo señala, los pasos de la sesión
  traen `can_do`/`limiting_factor`/`graph_mastery` y el detalle del can-do con su nodo se ve
  en el curso (hitos expansibles) y en el perfil (Habilidades).
- **Currículum CEFR 2.0**: escalera completa Pre-A1 → C2 (con bandas "plus" A2+/B1+/B2+) y
  descriptores Can-Do por dimensión (listening, speaking, reading, writing, grammar, vocabulary,
  pronunciation, interaction, mediation) en el Course.
- **Speaking 2.0**: pronunciación marcada como *proxy* (similitud fonética, no acústica real),
  desglose de **Interaction Quality** (initiation, response, follow-up, repair, turn-taking) y
  **Conversation Endurance** (cuánto puede sostener una conversación el alumno), visibles en el
  diagnóstico de speaking.
- **Academy / Course Engine (V2.2)**: curso CEFR completo (`Course → Unit → Lesson → Objective`)
  con Mastery Gates por unidad, contrato CEFR conectado al dominio, tríada
  Progress/Mastery/Readiness y pantalla **Learning Journey** (escalera Pre-A1→C2).
- **Personal Dictionary (V2.3)**: diccionario personal por ítem léxico (palabra/estructura)
  sembrado automáticamente desde el currículo, con estado determinista
  (`known`/`learning`/`weak`/`mastered`), `recall` por ítem (curva de olvido), distribución CEFR
  y señal "reconoce pero no produce" para practicar hablando.
- **Diccionario reversible + Traductor de viaje (V3.39-V3.40)**: el diccionario de consulta
  funciona en ambos sentidos (**EN→ES y ES→EN**, con la pestaña Personal/Consultar recordada entre
  sesiones) y se añade el 5.º destino **Traductor** (`/traductor`): utilidad de viaje por voz o
  texto en ES↔EN, con voces Piper en español descargables, historial reciente y sin registrar
  evidencia (no es núcleo de aprendizaje).
- **Motor de tarea óptima + transferencia real (V3.41-V3.42)**: el planner pasa de "¿qué palabra
  repaso?" a **"¿qué modalidad limita, qué actividad la cierra y con qué apoyo?"**
  (`skill_priority`/`limiting_skill`/`select_task`), con actividades nuevas en el drill
  **`write`** (cierra `spoken ✓ / written ✗`) y **`transfer`** (usar la unidad en un contexto
  NUEVO, que acredita `spontaneous_use` y demuestra transferencia real cuando se logra en ≥ 2
  contextos), señales robustas (recencia de errores, percentiles de latencia, automaticidad
  unificada) y gobierno del estado pedagógico por **unidad léxica** (go/went/gone/going).
  **Context Bank 2.0 (V3.48)**: el banco curado de contextos de transferencia pasa a **20 escenarios**
  (A1–C2, con `cefr`/`difficulty_vector` por contexto) y la diversidad contextual se mide en dos capas:
  el gate de evidencia (ejes core) y una capa de variedad informativa (`register`, entorno léxico y
  foco sintáctico) que explica la cobertura sin alterar los umbrales.
- **Curriculum Coverage (V2.4) + Quality Dashboard (V2.6)**: auditoría de cobertura curricular que
  recorre Pre-A1 → C2 por las 7 secciones (vocabulary/grammar/listening/speaking/interaction/
  review/assessment), cruza el contenido del curso con los bancos de listening/speaking y genera
  `curriculum_coverage_report.json` con "TOTAL CURRICULUM COVERAGE". V2.6 añade **UNIT COVERAGE**
  por unidad, **CEFR DEPTH SCORE** por nivel y el **Curriculum Quality Dashboard** (7 dimensiones +
  before/after) para dejar de desarrollar "a sensación" (ver `docs/CURRICULUM_COVERAGE.md`).
- **Listening C1/C2 (V2.5-C1)**: corpus de listening ampliado a 140 ítems (A1→C2), con 20 ítems C1
  y 20 C2 de registro avanzado (inferencia, intención del hablante, actitud, hablantes múltiples,
  habla rápida y connected speech).
- **Calibración pedagógica de niveles (V2.9)**: nivel estimado global honesto (se introduce `Pre-A1` y
  se recalibran los umbrales de vocabulario), los donuts de Listening se releen como **rutas de práctica**
  con puerta de validación (cobertura ≥ 80 %, precisión ≥ 70 %, variedad y checkpoint) y el corpus de
  listening se **expande por pipeline reproducible a 490 ítems** (A1 y A2 → 200 c/u), con opciones
  rebalanceadas por posición (auditoría B, mc-bias, cerrado).
- **Constitución pedagógica CEFR (V3.2.x, docs)**: especificación normativa de QUÉ debe demostrar un
  alumno Pre-A1→C2 y cómo mostrarlo. Separa **Practice Level / Mastery / Estimated CEFR /
  Demonstrated CEFR** (4 estados por competencia) y declara que el vocabulario es un indicador de
  cobertura, no un criterio de nivel: nunca "X palabras → nivel CEFR". Auditoría previa en
  `docs/audit/H-NIVELACION-PEDAGOGICA.md`; especificación en `docs/CONSTITUCION-PEDAGOGICA.md`.
  Ejecución en código: P0 (v3.3.0, backend), P1 (v3.4.0, backend) y P2 (v3.5.0, UI): los badges de
  nivel estimado llevan "estimado · no certificado", el perfil por destreza se marca como
  estimación y la práctica de listening se lee por estado de ruta (`functional` = hito de práctica;
  solo `demonstrated`, puerta + retención retardada estable ≥ 7 días, muestra "A1 Listening —
  demonstrated").
- **Speaking C2 (V2.5-C2)**: catálogo de escenarios comunicativos ampliado a 26 (A1→C2), con 6
  escenarios C2 (persuasión, mediación de conflicto, defensa académica, temas abstractos,
  negociación de alto riesgo y reunión diplomática).
- **Interaction A1/A2/B2/C1/C2 (V2.5-C3)**: práctica de interacción (turnos/diálogo) declarada en
  objetivos de speaking de 5 niveles, cerrando el hueco de la sección interaction (solo Pre-A1,
  banda sin curso, queda vacía).
- **Wiring curso↔bancos (V2.5-C4)**: cada objetivo de listening referencia ítems del banco por ID
  (`listening_items`) y cada objetivo de speaking referencia un escenario (`scenario_ids`),
  cableando el curso secuencial a los bancos de destrezas (conteo y validación de integridad por
  nivel). Sin UI en este incremento.
- **Curriculum Depth (V2.7)**: "cobertura ≠ profundidad" convertido en acción. Se alinea la medición
  (review/assessment contados por marcador `phase` por unidad, no solo en el módulo Final), se pilota
  **B1 como plantilla maestra de "Unit Architecture"** (10 → 18 objetivos reales) y se **escala a
  A2 (11→17), B2 (9→13), C1 (7→14) y C2 (5→14)**, con el loop de aprendizaje cerrado y
  listening/grammar/speaking/interaction por unidad en todos los niveles. Dashboard: Overall **94,5**,
  depth media **84,0**, Listening **91,7**, Speaking/Interaction **100%**; todos los niveles con curso
  superan depth 80. Referencia en `docs/UNIT_ARCHITECTURE.md`, briefings de escalado
  `agentes/curriculum/v27-depth-*.md` y delta en `docs/CURRICULUM_COVERAGE.md`.
- **Listening Curriculum (V2.8)**: cierre del listening en **todas las unidades** (A1
  incluido), progresión CEFR por subskill (`word_recognition` → … → `inference`) y
  métrica de alineación foco/subskill **100%**. Dashboard: Overall **95,7**, Listening
  **100%**, Unit Learning Loop **100%**. Referencia en `docs/LISTENING_CURRICULUM.md`.
- **Speaking Mission Performance (V2.9)**: loop
  Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement, con
  drills por criterio débil y delta de mejora visible. Referencia en
  `docs/SPEAKING_MISSION.md`.
- **Assessment 2.0 (V2.10)**: escalera formative → unit → progress → level →
  retention, con readiness derivado y mastery gate
  (initial/practice/transfer/novel/delayed). Referencia en `docs/ASSESSMENT_2.md`.
- **SRS / FSRS (V2.11)**: scheduler FSRS-lite (cartas skill/lexicon, cola due
  auditable, grades 1..4). Referencia en `docs/FSRS.md`.
- **Evidence Graph (V2.12)**: can-do → dimensiones → limiting factor, con
  `because[]` en next-best. Referencia en `docs/EVIDENCE_GRAPH.md`.
- **Beta V3.0 (freeze)**: stack pedagógico cerrado; trabajo permitido =
  contenido / calibración / UX / pruebas reales. Ver `docs/BETA_V3.md`.

## Arranque rápido

### Con el lanzador de escritorio (recomendado)
1. Crea el acceso directo del escritorio (una sola vez):
   ```powershell
   powershell -ExecutionPolicy Bypass -File launcher/install_shortcut.ps1
   ```
2. Haz doble clic en el acceso directo **"English Tutor"** del escritorio.
3. En la ventana del lanzador pulsa **"Iniciar app"** (genera el certificado TLS, compila
   la interfaz si es la primera vez, arranca el proceso y abre el navegador) y
   **"Detener app"** para pararlo. La ventana muestra el estado de los servicios, la base
   de datos y los usuarios.

### Con F5 (recomendado en Cursor)
1. Abre el proyecto en Cursor.
2. Pulsa **F5** (o *Run > Start Debugging*).
3. Elige la configuración que quieras:
   - **"App completa HTTPS :8000 (producto)"**: un solo proceso que sirve la API y la UI
     compilada (como en producción, con `--reload` para desarrollo).
   - **"Desarrollo con HMR (Vite :5173 + API :8000)"**: dos terminales con recarga en
     caliente del frontend (`npm run dev`) y proxy `/api` hacia el backend.
4. Cursor abre el navegador automáticamente.

> Configuración en `.vscode/launch.json`. Pulsar de nuevo **F5** o el botón de stop
> detiene los servidores.

### Manual (sin F5)

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Modelos de voz (solo la 1.ª vez, requiere internet)
```powershell
cd backend
.venv\Scripts\python.exe download_models.py --check   # ver qué falta (no descarga nada)
.venv\Scripts\python.exe download_models.py           # descargar lo que falte
```
La primera vez descarga las voces Piper por defecto (inglés + español, ~60 MB por
voz en `.onnx`/`.onnx.json`) y la caché de Whisper (~930 MB). **No** se versionan
(`backend/models/` está en `.gitignore`), así que en un clon limpio hay que
ejecutar este paso. La verificación previa distingue lo que es **descarga** de lo
que es **local** (la base de datos, que se crea sola al arrancar).

### Modelo de Ollama (solo la 1.ª vez, requiere internet)
```powershell
ollama pull llama3.1:8b    # el modelo por defecto (backend/config.py::DEFAULT_MODEL)
```
Este paso es **manual y explícito** a propósito: el modelo lo gestiona el servicio
de Ollama, no el proyecto (no se descarga solo). Compruébalo con `ollama list`.

### Compilar la interfaz (solo la 1.ª vez)
```powershell
cd frontend
npm install
npm run build      # produce frontend/dist (no se versiona)
```

### Arrancar la app (un solo proceso, HTTPS :8000)
```powershell
cd backend
.venv\Scripts\python.exe -m scripts.ensure_tls_cert
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 `
    --ssl-certfile data\certs\cert.pem --ssl-keyfile data\certs\key.pem
```

Abre **https://localhost:8000** y empieza a conversar. La primera vez el navegador
avisará de que el certificado es autofirmado: es el certificado local de la app (no se
puede evitar y hace falta para que funcione el micrófono desde otros dispositivos).

### Modo desarrollo con recarga en caliente

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
# en otra terminal:
cd frontend
npm run dev         # Vite en https://localhost:5173 con proxy /api
```

## Requisitos

- [Ollama](https://ollama.com) instalado y corriendo en `http://127.0.0.1:11434`.
- Python 3.11+ y Node.js 18+.
- **Node + npm son requisito de COMPILACIÓN/instalación, no de EJECUCIÓN**: el `dist` se
  compila una vez con `npm run build` (lo hace el lanzador si falta) y después lo sirve el
  propio backend. Solo hacen falta para compilar (`npm run build`) o para el modo de
  desarrollo (`npm run dev`).
- **El launcher es fail-closed (V3.73):** arranca el producto con
  `ENGLISH_TUTOR_REQUIRE_UI=1` y **no arranca** si falta `frontend/dist/index.html`; en
  ese caso dice qué hacer (`npm run build`). Un `uvicorn main:app` a mano sigue siendo
  fail-open: sirve solo la API.
- **Descubrimiento de la LAN sin salir a la red (V3.73):** la IP con la que se anuncia la
  app se obtiene enumerando las direcciones de este equipo
  (`backend/services/net_interfaces.py`), **sin consultar ninguna dirección pública**. Si
  el equipo tiene varias tarjetas o VPN y elige la interfaz equivocada, se puede fijar a
  mano con la variable de entorno `ENGLISH_TUTOR_LAN_IP`.
- **Certificado TLS autofirmado:** el navegador avisará la primera vez; hay que aceptarlo
  para que funcione el micrófono (sin HTTPS, `getUserMedia` no existe fuera del propio
  host). Se genera solo en `backend/data/certs/` (no versionado).

## Tests

- **Backend** (pytest):
  ```powershell
  cd backend
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe -m pytest tests/ -q
  ```
- **Frontend** (vitest + tsc):
  ```powershell
  cd frontend
  npm install
  npm test
  # o todo junto (tipos + tests):
  ./scripts/check.ps1
  ```
- **Launcher** (pytest):
  ```powershell
  cd launcher
  ..\backend\.venv\Scripts\python.exe -m pytest tests/ -q
  ..\backend\.venv\Scripts\python.exe -m ruff check .
  ```
- **Smoke test** (requiere el servidor arrancado con F5):
  ```powershell
  cd backend
  .venv\Scripts\python.exe scripts/smoke_test.py
  ```
- **Evaluación de modelo** (M5; compara calidad como tutor):
  ```powershell
  cd backend
  .venv\Scripts\python.exe scripts/eval_model.py --model llama3.1:8b
  ```
- **Evaluación objetiva del tutor** (F9; puntúa un modelo contra el corpus canónico):
  ```powershell
  cd backend
  .venv\Scripts\python.exe scripts/eval_tutor.py --model qwen3.5:9b
  ```
- **Auditoría de cobertura curricular** (V2.4/V2.6; genera `curriculum_coverage_report.json`):
  ```powershell
  cd backend
  .venv\Scripts\python.exe -m scripts.curriculum_coverage
  # o en modo estricto (exit 1 si hay huecos `empty` en un nivel con curso):
  .venv\Scripts\python.exe -m scripts.curriculum_coverage --strict
  # Curriculum Quality Dashboard (V2.6; añade el JSON completo):
  .venv\Scripts\python.exe -m scripts.curriculum_coverage --quality
  ```

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz compilada (`frontend/dist`, fallback SPA); sin artefacto, 404 |
| `GET` | `/api` | Metadatos del servicio (nombre + versión) |
| `GET` | `/api/health` | Estado del servicio |
| `GET` | `/api/health/live` | Liveness |
| `GET` | `/api/health/ready` | Readiness (200/503 según dependencias) |
| `GET` | `/api/health/dependencies` | Estado por dependencia (BD, Ollama, STT, TTS) |
| `GET` | `/api/network` | Acceso en red: `ip`, `hostname`, `url` (HTTPS), `local_url` y `local_url_available` (mDNS real) |
| `GET` | `/api/models` | Modelos disponibles en Ollama |
| `POST` | `/api/chat` | Diálogo con el modelo (acepta `mode`, `user_id`) |
| `POST` | `/api/chat/stream` | Diálogo con streaming (SSE) |
| `POST` | `/api/transcribe` | Audio → texto (Whisper) |
| `POST` | `/api/tts` | Texto → audio WAV (Piper) |
| `POST` | `/api/pronunciation` | Audio + texto esperado → puntuación + fluidez |
| `GET/POST` | `/api/users` | Listar / crear perfiles de usuario |
| `GET/POST` | `/api/conversations?user_id=<id>` | Listar / crear conversaciones del usuario |
| `GET/PUT/DELETE` | `/api/conversations/{id}` | Leer / guardar / borrar una conversación |
| `POST/GET` | `/api/learning/events` | Registrar / listar eventos de aprendizaje |
| `POST` | `/api/vocabulary/analyze` · `GET /api/vocabulary` | Extraer / listar vocabulario |
| `POST` | `/api/grammar/analyze` · `GET /api/grammar/errors` | Detectar / listar errores recurrentes |
| `GET` | `/api/profile?user_id=<id>` | Perfil de aprendizaje (nivel estimado + bandas + recomendaciones) |
| `GET` | `/api/progress?user_id=<id>` | Resumen de progreso del alumno |
| `GET` | `/api/progress/history?user_id=<id>` | Historial: tendencias, racha, dominio, hitos |
| `GET` | `/api/listening/question` · `POST /api/listening/answer` · `GET /api/listening/stats` | Ejercicios de listening |
| `GET` | `/api/academy/cefr-ladder` | Escalera CEFR completa (Pre-A1 → C2) con descriptores Can-Do por dimensión |

> **Modos de tutor** (`mode` en `/api/chat`): `conversation`, `grammar`, `exercises`, `pronunciation`.

> Nota: `llama3.1:8b` es el modelo por defecto (`backend/config.py::DEFAULT_MODEL`).
> `qwen3.5:9b` está **vetado** en el código (`UNUSABLE_MODELS`: `/api/models` lo
> filtra y no se ofrece), y también hay `qwen3-coder:30b`/`qwen2.5-coder:1.5b`
> (orientados a código).

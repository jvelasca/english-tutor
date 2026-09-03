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
- Última versión estable: **v3.4.0**.

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
- **Evaluación objetiva del tutor (F9)**: métricas deterministas del tutor (backend + panel).
- **Lanzador de escritorio**: GUI que arranca/detiene la app y muestra estado, BD y usuarios.
- **Acceso LAN / móvil**: HTTPS autofirmado en la red local, QR de conexión, verificación real de
  mDNS (`<host>.local`), test de micrófono con medidor de nivel y página `/help/connect` para
  confiar el certificado en Windows, Android e iPhone/iPad.
- **Adaptive Engine 2.0**: siguiente mejor actividad con prioridad explicable y "¿por qué?"
  (recencia, retención, confianza, evidencia, transferencia/novedad) en la tarjeta de inicio.
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
3. En la ventana del lanzador pulsa **"Iniciar app"** (arranca backend + frontend y abre
   el navegador) y **"Detener app"** para pararlos. La ventana muestra el estado de los
   servicios, la base de datos y los usuarios.

### Con F5 (recomendado en Cursor)
1. Abre el proyecto en Cursor.
2. Pulsa **F5** (o *Run > Start Debugging*).
3. La primera vez, elige la configuración **"English Tutor (F5)"** en el desplegable.
4. Cursor arranca el backend (`:8000`) y el frontend (`:5173`) en dos terminales y
   abre el navegador automáticamente.

> Configuración en `.vscode/launch.json`. Pulsar de nuevo **F5** o el botón de stop
> detiene ambos servidores.

### Manual (sin F5)

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe download_models.py   # descarga Whisper + voz Piper (solo la 1ª vez)
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

Abre **http://localhost:5173** y empieza a conversar.

## Requisitos

- [Ollama](https://ollama.com) instalado y corriendo en `http://127.0.0.1:11434`.
- Python 3.11+ y Node.js 18+.

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
| `GET` | `/` | Metadatos del servicio (nombre + versión) |
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

> Nota: `qwen3.5:9b` es el modelo por defecto y funciona bien como tutor. También está
> instalado `llama3.1:8b` (más rápido, pero con menor precisión en pronunciación), y
> `qwen3-coder:30b`/`qwen2.5-coder:1.5b` (orientados a código).

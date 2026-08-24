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
- Última versión estable: **v1.1.0**.

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
- **Listening / CEFR (F8)**: ejercicios de comprensión auditiva y evaluación CEFR multi-señal.
- **Evaluación objetiva del tutor (F9)**: métricas deterministas del tutor (backend + panel).
- **Lanzador de escritorio**: GUI que arranca/detiene la app y muestra estado, BD y usuarios.

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

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Metadatos del servicio (nombre + versión) |
| `GET` | `/api/health` | Estado del servicio |
| `GET` | `/api/health/live` | Liveness |
| `GET` | `/api/health/ready` | Readiness (200/503 según dependencias) |
| `GET` | `/api/health/dependencies` | Estado por dependencia (BD, Ollama, STT, TTS) |
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
| `GET` | `/api/profile?user_id=<id>` | Perfil de aprendizaje (CEFR + bandas + recomendaciones) |
| `GET` | `/api/progress?user_id=<id>` | Resumen de progreso del alumno |
| `GET` | `/api/progress/history?user_id=<id>` | Historial: tendencias, racha, dominio, hitos |
| `GET` | `/api/listening/question` · `POST /api/listening/answer` · `GET /api/listening/stats` | Ejercicios de listening |

> **Modos de tutor** (`mode` en `/api/chat`): `conversation`, `grammar`, `exercises`, `pronunciation`.

> Nota: `qwen3.5:9b` es el modelo por defecto y funciona bien como tutor. También está
> instalado `llama3.1:8b` (más rápido, pero con menor precisión en pronunciación), y
> `qwen3-coder:30b`/`qwen2.5-coder:1.5b` (orientados a código).

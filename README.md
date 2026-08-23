# English Tutor (100% local)

App para conversar con un modelo de IA **local** (Ollama), pensada para convertirse en un
profesor de inglés totalmente local. Sin Internet, sin cuentas, sin costes.

## Documentación (leer primero)

- **`docs/PREMISAS.md`** — premisas y reglas del proyecto (fuente de verdad).
- **`docs/ARQUITECTURA.md`** — estructura modular y responsabilidades por capa.
- **`docs/DESARROLLO.md`** — cómo arrancar y trabajar desde 0, flujo con subagentes, Git/GitHub.
- **`PLAN.md`** — hoja de ruta y tablero de subagentes.

## Repositorio

- **GitHub (privado):** https://github.com/jvelasca/english-tutor — seguimiento con issues, PR y releases.
- Última versión estable: **v1.0.0**.

## Estructura

- `backend/` — API en Python con **FastAPI + Pydantic** (tipado fuerte). Habla con Ollama.
- `frontend/` — Interfaz web con **Vite + React + TypeScript**.
- `agentes/` — briefings autocontenidos de subagentes (premisa 5: todo trabajo se descompone en subagentes).
- `docs/` — documentación del proyecto.

## Funcionalidades

- **Chat por texto** con streaming (SSE) contra Ollama.
- **Voz 100% local**: transcripción (Whisper) y síntesis (Piper).
- **Memoria e historial**: conversaciones guardadas en SQLite (sidebar).
- **Modo profesor (M4)**: 4 modos de tutor (conversación, gramática, ejercicios, pronunciación)
  y **corrección de pronunciación** (graba y recibe una puntuación).

## Arranque rápido

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

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Estado del servicio |
| `GET` | `/api/models` | Modelos disponibles en Ollama |
| `POST` | `/api/chat` | Diálogo con el modelo (acepta `mode`) |
| `POST` | `/api/chat/stream` | Diálogo con streaming (SSE, acepta `mode`) |
| `POST` | `/api/transcribe` | Audio → texto (Whisper) |
| `POST` | `/api/tts` | Texto → audio WAV (Piper) |
| `POST` | `/api/pronunciation` | Audio + texto esperado → puntuación de pronunciación |
| `GET/POST` | `/api/conversations` | Listar / crear conversaciones |
| `GET/PUT/DELETE` | `/api/conversations/{id}` | Leer / guardar / borrar una conversación |

> **Modos de tutor** (`mode` en `/api/chat`): `conversation`, `grammar`, `exercises`, `pronunciation`.

> Nota: los modelos instalados (`qwen3-coder`, `qwen3.5`) son orientados a código.
> `qwen3.5:9b` funciona bien para conversación; si quieres más calidad como tutor,
> considera descargar un modelo conversacional, p. ej. `ollama pull llama3.1:8b`.

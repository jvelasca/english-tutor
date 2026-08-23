# Subagente: M2 — Backend · Voz local (Whisper STT + Piper TTS)

## Rol
Desarrollador backend senior (Python / FastAPI). Trabajas SOLO en el backend.

## Objetivo
Añadir dos endpoints de voz 100% local, dentro de la estructura modular:
- `POST /api/transcribe` — audio → texto (Whisper).
- `POST /api/tts` — texto → audio (Piper).

## Contexto del proyecto
- Repo: `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`
- Lee ANTES: `docs/ARQUITECTURA.md`, `docs/PREMISAS.md`.
- Estructura modular backend (ya existe tras M0):
  - `routers/` (capa HTTP), `services/` (lógica), `schemas/` (Pydantic), `config.py`.
- Arranque: `backend\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000`
- Hardware: RTX 4060 Ti (4 GB VRAM) + 64 GB RAM. Ollama ya usa la GPU → Whisper/Piper en **CPU**.

## Decisiones técnicas (ya tomadas)
- **STT:** `faster-whisper`, modelo `small`, idioma `en` por defecto (permitir `es`). CPU `compute_type="int8"`.
- **TTS:** `piper-tts`, voz `en_US-lessac-medium`. CPU.

## Tarea detallada
1. **Dependencias:** añade `faster-whisper` y `piper-tts` a `requirements.txt` (instala con `pip`,
   usa versiones reales, no inventes). Instálalas en el venv.
2. **Modelos:** crea `backend/models/` (añádela a `.gitignore`).
   - Whisper `small` → `backend/models/whisper-small` (usa `download_root`). Primera descarga online.
   - Voz Piper (`.onnx` + `.onnx.json`) → `backend/models/piper/` (Hugging Face `rhasspy/piper-voices`,
     `en/en_US/lessac/medium/`).
   - Carga los modelos UNA VEZ al arrancar (lifespan de FastAPI o módulo), no por petición.
3. **`services/stt.py`:** función `transcribe(audio_bytes, language)` → `str`. Convierte el audio a
   lo que faster-whisper acepta (prefiere WAV PCM 16 kHz mono).
4. **`services/tts.py`:** función `synthesize(text)` → `bytes` (WAV en BytesIO).
5. **`routers/voz.py`:**
   - `POST /api/transcribe`: `multipart/form-data` campo `file` + campo opcional `language` → `{"text": ...}`.
   - `POST /api/tts`: JSON `{"text": ...}` → `Response` con `media_type="audio/wav"`.
6. **`schemas/voz.py`:** modelos Pydantic para los cuerpos/respuestas.
7. Define estos dos handlers como `def` normales (FastAPI los mueve a threadpool; la inferencia es síncrona).

## Criterios de aceptación
- `POST /api/transcribe` con un WAV de prueba devuelve transcripción razonable.
- `POST /api/tts` con `{"text":"Hello"}` devuelve audio WAV reproducible.
- Ambos funcionan offline tras la descarga inicial.

## Restricciones
- 100% local: el audio NO sale de la máquina. Whisper/Piper en CPU (no competir con Ollama).
- No toques `frontend/`. No modifiques `/api/chat` ni `/api/chat/stream`.

## Salida esperada
- Diff de `requirements.txt`, `config.py`, `services/`, `routers/`, `schemas/`, `.gitignore`.
- Lista de modelos descargados (ruta + tamaño). Comandos de prueba de ambos endpoints.

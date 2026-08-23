# Plan de proyecto — English Tutor (100% local)

> Mantenido por el gerente del proyecto (yo). Los subagentes se ejecutan desde
> agentes locales: cada tarea se describe en `agentes/<nombre>.md`.
>
> **Premisas y reglas:** `docs/PREMISAS.md` · **Arquitectura:** `docs/ARQUITECTURA.md` ·
> **Guía de desarrollo:** `docs/DESARROLLO.md`.

## Estado actual

- ✅ Backend FastAPI + Pydantic (chat con Ollama).
- ✅ Frontend Vite + React + TypeScript (chat por texto).
- ✅ Diálogo real probado con `qwen3.5:9b`.
- ✅ Documentación base (`docs/`, premisas, arquitectura, guía de desarrollo).

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

### M5 — Modelo conversacional  [BLOQUEADO ⚠]
- Evaluar cambiar a un modelo no-coder (ej. `llama3.1:8b` o `mistral`) para mejor calidad de tutor.
- Criterio: calidad como profesor (correcciones, explicaciones, tono) + tamaño/VRAM (RTX 4060 Ti 4 GB).
- Entregable: script de evaluación repetible + decisión documentada del modelo por defecto.
- Subagente (ejecutado por el gerente): `agentes/m5-modelo-conversacional.md`.
- **Bloqueo:** `ollama pull llama3.1:8b` falla con `tls: failed to verify certificate`
  (`x509: certificate signed by unknown authority`). Causa raíz identificada: el ISP
  **DigiMobil (AS57269)** intercepta el tráfico al CDN de pesos (`r2.cloudflarestorage.com`)
  con un certificado autofirmado `CN=core1.netops.test` como efecto colateral de los bloqueos
  de IP de LaLiga (ver OONI). Solución: usar VPN u otra red para descargar el modelo.
  No es un problema del proyecto, de Windows ni del firewall.

### M6 — Release a GitHub  [HECHO ✔]
- Repositorio **público**: https://github.com/jvelasca/english-tutor
- V1.0 (tag `v1.0.0`) subida con release e issues de seguimiento.

### M7 — Multi-usuario  [NUEVO]
- Perfiles locales con **seguimiento independiente** (conversaciones, progreso, puntuaciones, ajustes).
- Selección simple de perfil al abrir; aislamiento total de datos entre usuarios (premisa 13).
- Implica migrar la persistencia (SQLite) a esquema por usuario.

### M8 — Diseño y UX nivel top  [NUEVO]
- Rediseño de la interfaz al nivel de apps líderes (ChatGPT/Duolingo): sistema de tokens,
  tema claro/oscuro, responsive, micro-interacciones y estados vacíos/carga/error (premisa 14).

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
| M5 Modelo conversacional | `agentes/m5-modelo-conversacional.md` | ⚠ bloqueado (TLS) |

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

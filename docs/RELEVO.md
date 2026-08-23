# Documento de relevo (handoff)

> **Propósito:** permitir que un agente/contexto **nuevo** retome el proyecto desde cero
> sin perder el hilo (premisa 8 y 12). Si el chat del gerente se satura o hay riesgo de
> alucinación, este documento es el ancla para reanudar.
> Actualizado por última vez: 2026-08-23 22:25 (UTC+2).

## 1. Qué es el proyecto

Profesor de inglés **100% local** (sin Internet, sin cuentas, sin costes). Conversa por
texto y voz con un LLM local (Ollama), con modos de tutor y corrección de pronunciación.

- **Fuente de verdad de reglas:** `docs/PREMISAS.md` (14 premisas). Léelas primero.
- **Arquitectura:** `docs/ARQUITECTURA.md` (estructura modular y responsabilidades).
- **Guía de desarrollo:** `docs/DESARROLLO.md` (arranque, flujo con subagentes, Git/GitHub).
- **Roadmap y estado:** `PLAN.md`.

## 2. Stack (fijado, premisa 3-4)

- Backend: Python + FastAPI + Pydantic (tipado fuerte).
- Frontend: Vite + React + TypeScript (modo estricto).
- LLM: Ollama (local). Modelo inicial `qwen3.5:9b`.
- Voz: `faster-whisper` (STT, CPU) y `piper-tts` (TTS, CPU).
- Persistencia: SQLite (`backend/data/tutor.db`).

## 3. Estado actual (qué funciona)

Hecho y verificado (tests verdes):

- **M0** esqueleto modular · **M1** streaming (SSE) · **M2** voz local · **M3** memoria/historial.
- **M4** modo profesor: 4 modos de tutor (`conversation`, `grammar`, `exercises`, `pronunciation`)
  + corrección de pronunciación (`POST /api/pronunciation`).
- **M6** release a GitHub.
- Tests: backend `pytest tests/ -q` (13+ tests), frontend `npm test` (vitest) + `tsc --noEmit`.

## 4. GitHub

- Repo **público**: https://github.com/jvelasca/english-tutor
- Rama por defecto: `main`. Última versión estable: tag `v1.0.0` (release publicado).
- Issues de seguimiento:
  - #1 M5 modelo conversacional
  - #2 Seguimiento de progreso del alumno
  - #3 Conversación por voz continua
  - #4 M7 multi-usuario
  - #5 M8 diseño y UX nivel top

## 5. EN CURSO — M5: modelo conversacional (descarga bloqueada por MITM del ISP)

**Tarea:** evaluar `llama3.1:8b` como reemplazo de `qwen3.5:9b` para el rol de tutor.

- Script listo: `backend/scripts/eval_model.py` (`--model <m>` envía 4 prompts de tutor).
- Briefing: `agentes/m5-modelo-conversacional.md`.
- **Problema resuelto:** `ollama pull` fallaba con `tls: certificate signed by unknown authority`.
  Causa raíz: MITM del ISP **DigiMobil (AS57269)** sobre el CDN de pesos
  (`r2.cloudflarestorage.com`), efecto colateral de los bloqueos de IP de LaLiga
  (certificado falso `CN=core1.netops.test`). **Solución: usar VPN.**
- **Estado al redactar esto:** descarga de `llama3.1:8b` corriendo en segundo plano con VPN,
  ~51% (2.5 GB/4.9 GB), ETA ~1h30m. La VPN es algo inestable (la descarga se reinició un par
  de veces).
- **Siguiente paso cuando termine:** `ollama pull llama3.1:8b` → `ollama list` para confirmar →
  ejecutar `eval_model.py --model qwen3.5:9b` y `--model llama3.1:8b` → comparar calidad →
  decidir `DEFAULT_MODEL` en `backend/config.py` → documentar en `PLAN.md` → commit.

## 6. PENDIENTE — M7: multi-usuario (próximo hito grande)

**Requisito (premisa 13):** varios perfiles locales, cada uno con conversaciones, progreso,
puntuaciones y ajustes **independientes**; aislamiento total de datos entre usuarios; sin
cuentas en la nube.

**Estado:** solo analizado, sin implementar. Ya se han leído los archivos afectados:

- `backend/services/store.py` — persistencia SQLite. Hoy es **global** (sin columna usuario).
- `backend/routers/conversations.py` — CRUD `/api/conversations`.
- `backend/schemas/conversations.py` — `ConversationMeta`, `Conversation`, `ConversationUpsert`.
- `frontend/src/api/conversations.ts` — cliente del CRUD.
- `frontend/src/hooks/useChat.ts` — estado; guarda `conversationId` sin concepto de usuario.
- `frontend/src/components/Sidebar.tsx` — lista de conversaciones.

**Plan propuesto (por fases, hito a hito según premisa 6):**
1. Backend: tabla `users` (id, name, created_at) + columna `user_id` en `conversations`
   (FK, con migración idempotente en `init_db`); endpoints `/api/users` (listar/crear) y
   filtrado de conversaciones por `user_id` (query param o header). Tests en `backend/tests/`.
2. Frontend: selector de perfil (crear/seleccionar usuario), pasar `user_id` al cliente de
   conversaciones y al hook. Tests con vitest.
3. Definición de terminado: tests verdes + docs actualizadas (`ARQUITECTURA.md`, `PLAN.md`,
   `README.md`).

**Nota:** es un cambio transversal (afecta núcleo de persistencia), hacerlo con cuidado y
con tests (premisa 12).

## 7. PENDIENTE — M8: diseño y UX nivel top

**Requisito (premisa 14):** rediseño al nivel de apps líderes (ChatGPT/Duolingo): sistema de
tokens (colores/tipografía/espaciado/radios), tema claro/oscuro, responsive, accesibilidad,
micro-interacciones, estados vacíos/carga/error cuidados.

- Hoy el CSS está en `frontend/src/index.css` (tema oscuro fijo, variables `--*` ya definidas
  en `:root`). No hay sistema de tokens formal ni toggle de tema.
- No iniciado.

## 8. Cómo arrancar y verificar desde cero

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests/ -q

# Frontend
cd frontend
npm install
npm test            # vitest
npx tsc --noEmit    # tipos

# Arranque integrado: F5 en Cursor (configuración "English Tutor (F5)")
#   backend :8000 + frontend :5173
```

## 9. Reglas de oro para continuar (premisas clave)

- **Todo se descompone en subagentes autocontenidos** en `agentes/<nombre>.md` (premisa 5).
- **Antes de alucinar, reiniciar el contexto** apoyándose en `docs/` (premisa 12).
- **Documentación VITAL:** todo cambio actualiza `docs/`, `PLAN.md`, `README.md` (premisa 8).
- **Tests obligatorios:** ninguna feature se da por acabada sin sus tests (premisa 12).
- **Ritmo:** hito a hito, un cambio a la vez (premisa 6).

# 37.4 (código) — Preparar despliegue a Vercel (frontend estático + backend local)

## Rol
Subagente **frontend + backend** que deja el proyecto **deploy-ready** para Vercel (solo el
frontend estático), manteniendo el backend 100% local. **No despliega** (no hay cuenta/CLI); solo
prepara la configuración de forma segura y reversible.

## Contexto (contratos exactos)
- Backend local: FastAPI en `127.0.0.1:8000`. Vercel serviría SOLO el frontend estático (Vite →
  `dist/`). No hay proxy en producción, así que el navegador debe apuntar a `http://127.0.0.1:8000`
  por URL absoluta (misma máquina).
- CORS actual en `backend/config.py`: `ALLOWED_ORIGINS = ["http://localhost:5173",
  "http://127.0.0.1:5173"]` + `ALLOWED_ORIGIN_REGEX` (localhost + IPs privadas). No admite orígenes
  de Vercel. El middleware CORS está en `backend/main.py` (usa esas constantes).
- API frontend: `frontend/src/api/client.ts` tiene `request(url)` con `fetch(url)` y rutas relativas
  `/api/...`. Además hay `fetch` directo en:
  - `frontend/src/api/chat.ts` (streaming, `fetch(\`/api/chat/stream...\`)`)
  - `frontend/src/api/pronunciation.ts` (`fetch(\`/api/pronunciation?...\`)`)
  - `frontend/src/api/voz.ts` (`fetch("/api/transcribe", ...)` y `fetch("/api/tts", ...)`)
  - `frontend/src/api/listening.ts` devuelve la URL `\`/api/listening/audio/...\`` (la consume un
    elemento `<audio>`/`new Audio`, no un fetch).
- No existe `vercel.json` ni uso de `VITE_*`.

## Objetivo
1. `frontend/vercel.json`: config Vite SPA (framework "vite", `buildCommand` = `npm run build`,
   `outputDirectory` = `dist`, y `rewrites` `/{.*}` → `/index.html`).
2. Helper `apiUrl(path)` en `frontend/src/api/client.ts`: prefija
   `import.meta.env.VITE_API_BASE_URL ?? ""` (default vacío → relativo, **mismo comportamiento en
   dev**). Aplícalo en `request()` y en los 5 sitios con `fetch`/URL directa listados arriba.
   Exponlo para reutilizarlo.
3. Backend: permitir orígenes extra vía env `ALLOWED_ORIGINS_EXTRA` (lista separada por comas) que se
   añade a `ALLOWED_ORIGINS` al montar CORS. Sin la env → comportamiento actual intacto. Mantén
   `ALLOWED_ORIGIN_REGEX` como está (cubre localhost/LAN).
4. Tests:
   - Frontend: test de `apiUrl` (default relativo; con base definida). Ajusta tests existentes si
     asumen rutas relativas (`academy.test.ts`, `listening.test.ts`, `chat.test.ts`, etc.) para que
     sigan pasando.
   - Backend: test CORS con `ALLOWED_ORIGINS_EXTRA` (sin env = actual; con env = añade el origen).
     Revisa `backend/tests/test_cors.py`.

## Criterios de aceptación
- `npx tsc --noEmit` OK; `npm test` OK; `npm run build` OK; `npm run test:visual` 4 passed + 2 skipped.
- Backend `pytest` + `ruff` en verde.
- Con `VITE_API_BASE_URL` y `ALLOWED_ORIGINS_EXTRA` sin definir, TODO sigue igual (dev no se rompe).

## Restricciones
- NO despliegues (sin cuenta/CLI). No `git push`. No bump de versión ni edición de `CHANGELOG`/
  `RELEVO` (lo integra el gerente). Sin dependencias nuevas.
- No cambies el comportamiento local/relativo por defecto.

## Salida
- Diff (frontend + backend) y salida de `tsc` / `vitest` / `build` / `playwright` + `pytest` / `ruff`
  en verde.

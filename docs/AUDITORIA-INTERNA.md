# Auditoría interna — English Tutor v1.1.0

> Realizada por el gerente del proyecto el 2026-08-24, como parte del cierre de FASE 10.
> Complementa las auditorías externas (security-review + bugbot). No sustituye el test
> automatizado: lo verifica contra las premisas y la definición de "terminado".

## 1. Resultado global

**Aprobado.** El proyecto cumple las 14 premisas y la definición de "terminado" en las tres
capas (backend, frontend, launcher). Todas las auditorías (interna y externas) completadas y
la release `v1.1.0` publicada en GitHub.

## 2. Cumplimiento de premisas

| # | Premisa | Estado | Evidencia |
|---|---|---|---|
| 1 | Visión (tutor de inglés) | ✔ | Chat por texto/voz, modos, corrección, progreso, listening, CEFR. |
| 2 | 100% local | ✔ | Ollama + faster-whisper + piper-tts + SQLite. Sin APIs cloud. |
| 3 | Stack fijado | ✔ | FastAPI+Pydantic, Vite+React+TS estricto, Ollama. |
| 4 | Voz local | ✔ | STT `small` CPU, TTS `en_US-lessac-medium` CPU. |
| 5 | Subagentes | ✔ | Todo en `agentes/` (M0–M11, F1–F10, A.1–A.2). |
| 6 | Ritmo poco a poco | ✔ | Un commit `feat:` por subagente. |
| 7 | Gestión de contexto | ✔ | `docs/RELEVO.md` como ancla. |
| 8 | Anti-saturación | ✔ | Briefings autocontenidos; relevo disponible. |
| 9 | Documentación VITAL | ✔ | README, PLAN, ARQUITECTURA, DESARROLLO, RELEVO, CHANGELOG actualizados. |
| 10 | Modularidad | ✔ | Router → Service → Repository → SQLite; `launcher/` con capas puras. |
| 11 | GitHub | ✔ | Repo público + release `v1.1.0` publicada (tag + release notes). |
| 12 | Tests y scripts | ✔ | Backend 217, frontend 88, launcher 22; scripts en `scripts/`. |
| 13 | Multi-usuario | ✔ | Perfiles locales aislados (tablas + filtro `user_id`). |
| 14 | Diseño UX top + responsive | ✔ | Tokens, tema claro/oscuro, responsive, a11y, micro-interacciones. |

## 3. Arquitectura

- **Backend:** `routers/` (HTTP) → `services/` (dominio puro) → `repositories/` (SQLite).
  Sin lógica de negocio en routers ni acceso a BD desde services.
- **Frontend:** `api/` → `hooks/` → `components/`; lógica pura en `utils/` (testeable).
- **Launcher:** `core.py` (puro) / `process_manager.py` / `status.py` / `launcher.py` (GUI).
  Sin dependencias nuevas (stdlib + tkinter).

## 4. Cobertura de tests (gate verde)

| Componente | Tests | Lint | Build |
|---|---|---|---|
| backend | 217 (pytest) | ruff limpio | `import main` OK |
| frontend | 88 (vitest) | tsc limpio | `npm run build` OK |
| launcher | 22 (pytest) | ruff limpio | `import launcher` OK |

## 5. Hallazgos internos

| # | Severidad | Hallazgo | Recomendación |
|---|---|---|---|
| 1 | Resuelta | `main` local iba ~30 commits por delante de `origin` (premisa 11). | Push + tag `v1.1.0` + release publicada el 2026-08-24. |
| 2 | Baja | El launcher solo **detiene** procesos que él mismo inició; si la app se lanzó con F5, se para con F5. | Documentado en README/DESARROLLO; aceptado como límite del MVP. |
| 3 | Baja | La GUI `tkinter` no tiene tests E2E (solo la lógica pura). | Aceptado: la GUI se verifica manualmente; la lógica está cubierta. |
| 4 | Informativa | La version `1.1.0` se expone en `/api/health` y `/`, pero el launcher no la muestra. | Opcional: añadir versión a la cabecera del launcher en una iteración futura. |

## 6. Hallazgos de auditoría externa (bugbot) — corregidos

La revisión externa con Bugbot detectó 4 hallazgos reales. Todos fueron corregidos y
verificados con tests antes del commit `f6d7558`.

| # | Severidad | Hallazgo | Corrección | Verificación |
|---|---|---|---|---|
| 1 | Alta | Condición de carrera en `launcher/launcher.py`: `start()` mutaba el `ProcessManager` desde un hilo de fondo mientras `stop()` (hilo principal) podía leerlo/limpiarlo; además `root.after()` se llamaba desde hilo no-principal antes de `mainloop()`. | Refactor a cola `queue.Queue` + `threading.Lock`; las actualizaciones de GUI se encolan y las procesa el hilo principal (`_poll_queue`). | Tests launcher verdes + arranque manual. |
| 2 | Alta | `grammar_error_rate` en `backend/domain/profile.py` dividía entre `messages` totales (incluía respuestas del asistente), reduciendo a la mitad la tasa real. | Se cuenta `user_messages` por separado en `repositories/pronunciation.py` y `profile.py` lo usa como denominador. | `test_profile_grammar_rate_uses_user_messages`. |
| 3 | Media | El marcador amistoso `"let's"` nunca coincidía: `normalize` eliminaba los apóstrofos antes de comparar con `FRIENDLY_MARKERS`. | Se normalizan los propios marcadores antes de comprobar inclusión en la respuesta normalizada (backend y frontend espejo). | `test_engagement_marker_with_apostrophe` (backend) y test espejo en frontend. |
| 4 | Informativa | La security-review externa no pudo calcular el diff inicialmente (ruta con espacios). | Reintento con base explícita `origin/main`. | Completada sin hallazgos accionables. |

## 7. Auditoría de seguridad externa (security-review) — sin hallazgos

Revisión de seguridad de la solución completa (versión 1.1.0) con base explícita `origin/main`.
Resultado: **no se identificaron vulnerabilidades accionables**.

- **CI** (`.github/workflows/ci.yml`): usa `pull_request` (no `pull_request_target`), sin
  secretos referenciados, sin input inseguro en pasos shell, acciones pineadas (`@v4`/`@v5`).
- **Launcher**: `subprocess` con listas de comandos fijas (sin `shell=True`, sin inyección);
  `taskkill` con PID numérico del proceso hijo real; SQLite en modo solo-lectura y con
  parámetros; scripts `.ps1` derivan rutas de su propia ubicación, sin input del usuario.
- **Backend**: las mejoras descritas en e1/e2/e3/f4 son endurecimiento neto (filtrado por
  `user_id`, rechazo de `role="system"`, límites de tamaño, mensajes de error genéricos, CORS
  restringido a orígenes locales, FK reales + mensajes append-only).

Elementos deliberadamente no reportados (por alcance/modelo de amenaza): sin autenticación en
la API multi-usuario (diseño explícito "100% local, sin cuentas"), `_content_type_ok` fail-open
(baja severidad, mitigado por límites + Whisper), y `-ExecutionPolicy Bypass` (script propio en
máquina propia).

## 8. Conclusión

Solución **estable y auditada**: 3 componentes con tests verdes, arquitectura respetada,
documentación al día y premisas cumplidas. Auditorías completadas: interna (gerente), externa
Bugbot (4 hallazgos corregidos) y externa security-review (sin hallazgos accionables). Release
`v1.1.0` publicada en GitHub. Proyecto cerrado.

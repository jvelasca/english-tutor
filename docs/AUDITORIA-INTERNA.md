# Auditoría interna — English Tutor v1.1.0

> Realizada por el gerente del proyecto el 2026-08-24, como parte del cierre de FASE 10.
> Complementa las auditorías externas (security-review + bugbot). No sustituye el test
> automatizado: lo verifica contra las premisas y la definición de "terminado".

## 1. Resultado global

**Aprobado con 1 acción pendiente.** El proyecto cumple las 14 premisas y la definición de
"terminado" en las tres capas (backend, frontend, launcher). La única acción pendiente es
publicar la release en GitHub (premisa 11), que requiere push del gerente.

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
| 11 | GitHub | ⚠ | Repo público existe; falta push + tag `v1.1.0` + release (acción pendiente). |
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
| 1 | Media | `main` local va ~30 commits por delante de `origin` (premisa 11). | Push + tag `v1.1.0` + release notes (decisión del gerente). |
| 2 | Baja | El launcher solo **detiene** procesos que él mismo inició; si la app se lanzó con F5, se para con F5. | Documentado en README/DESARROLLO; aceptado como límite del MVP. |
| 3 | Baja | La GUI `tkinter` no tiene tests E2E (solo la lógica pura). | Aceptado: la GUI se verifica manualmente; la lógica está cubierta. |
| 4 | Informativa | La version `1.1.0` se expone en `/api/health` y `/`, pero el launcher no la muestra. | Opcional: añadir versión a la cabecera del launcher en una iteración futura. |

## 6. Conclusión

Solución **estable y auditada**: 3 componentes con tests verdes, arquitectura respetada,
documentación al día y premisas cumplidas. Único pendiente operativo: publicar la release
v1.1.0 en GitHub.

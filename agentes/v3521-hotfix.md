# Briefing de subagente — V3.52.1 (hotfix de producto + cierre del P1-01)

> **Estado:** incremento V3.52.1 **ejecutado** el 2026-09-11 por el gerente a
> partir de bugs de uso real y del P1-01 de la auditoría externa de V3.52.0. Ver
> `release-notes-v3.52.1.md` para el resultado final y `docs/RELEVO.md` para el
> relevo. Este documento sirve como traspaso autocontenido: si hay que rehacer,
> auditar o continuar el trabajo, aquí está todo el contexto.

## Rol

Ingeniero full-stack del proyecto English Tutor, con foco en (a) el perfilado
local y los tests visuales de Playwright, (b) la pantalla de Listening
(reproductor y controles A/B) y (c) el motor PURO de dificultad
(`services/difficulty.py`).

## Objetivo

Arreglar tres bugs de producto reportados en uso real y cerrar el **P1-01** de la
auditoría externa de V3.52.0, **sin tocar la escalera `transfer_state`, sus
umbrales, `context_signals`, `context_diversity`, el scoring
(`score_transfer_attempt`) ni FSRS**, y **sin cambiar el comportamiento real del
motor de dificultad** (los 20 contextos del banco declaran las 4 dimensiones:
cobertura 4/4). Todo aditivo en el contrato HTTP (+ una columna de BD),
determinista y sin LLM en la decisión (premisa 21).

- **Bug 1 — usuarios fantasma «Visual Tester».** Aparecían 2 perfiles con ese
  nombre en la app y en la BD pese a existir un script de purga. No los creaba la
  app: los creaba `frontend/tests/visual/gateHelper.ts` con un find-or-create **no
  atómico** (GET y luego POST) contra la base de datos **real**
  (`backend/data/tutor.db`); 9 specs × 3 proyectos Playwright en paralelo hacían
  que dos workers insertaran a la vez. El script de V3.48.1 solo borró filas.
- **Bug 2 — Listening «RUTA ACTUAL».** Cambiar el nivel seleccionado (A1 → A2…)
  no actualizaba el anillo ni recargaba la pregunta.
- **Bug 3 — bucle A/B de Listening.** «Marcar inicio», «bucle A-B» y «quitar» se
  desincronizaban del audio real y el bloque estaba descentrado.
- **P1-01 — `difficulty.fit` vacuo.** Comparaba solo las dimensiones presentes en
  AMBOS vectores; una intersección vacía devolvía `within=True` «perfecto» con
  `distance=0`, así que un contexto con `difficulty_vector` parcial (o sin vector)
  podía ganar la selección.

Quedan **fuera de alcance** (diferido a V3.53+, como propone el audit): P1-02
(Learner Skill State 2.0 + `observed_difficulty`) y P1-03 (Planner 2.0 /
Expected Learning Value).

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`), lanzador Tkinter
  (`launcher/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Premisa 6:** un incremento a la vez, con su release.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m pytest -q`;
  `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`;
  `cd launcher && ..\backend\.venv\Scripts\python.exe -m pytest tests/ -q`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisiones de alcance (cerradas)

- **Raíz antes que purga (usuarios fantasma).** El perfil de prueba se crea UNA
  vez en `globalSetup` (proceso único → sin carrera) y se borra en
  `globalTeardown`; `gateHelper` deja de tocar la BD y solo mockea `GET /api/users`.
- **Guarda por marcador, no por nombre.** `users.is_test` distingue el perfil de
  prueba sin depender del nombre («Visual Tester» podría coincidir con un alumno
  real). El borrado por API está **acotado** a `is_test=1`.
- **Degradación tolerante en el lanzador.** Si la columna `is_test` aún no existe
  (BD sin migrar), `read_users` reintenta sin filtro en vez de fallar.
- **UI y controller con un único origen de verdad (A/B).** `abLoop.ts` es un
  módulo PURO: cada transición se aplica SIEMPRE al controller y a React a la vez.
- **`play(url)` idempotente por URL.** No recargar si la URL ya está cargada es lo
  que permite reanudar sin perder el bucle; solo se recarga si la URL cambia o si
  el audio terminó sin segmento activo.
- **Cobertura dimensional, no solo distancia (P1-01).** `within` exige cobertura
  completa; el selector degrada por cobertura y luego por distancia. Un reto vacío
  mantiene el encaje vacuo legítimo (`within=True`).

## Archivos clave

- `frontend/tests/visual/globalSetup.ts` / `globalTeardown.ts` — **nuevos**:
  crean/borran el perfil de prueba único (env `VISUAL_TESTER_ID`/`_NAME`).
- `frontend/tests/visual/gateHelper.ts` — solo mockea `GET /api/users`; sin
  find-or-create.
- `frontend/playwright.config.ts` — registra `globalSetup`/`globalTeardown`.
- `backend/repositories/db.py` — columna aditiva `users.is_test` (CREATE TABLE +
  `ALTER TABLE` idempotente).
- `backend/repositories/users.py` — `_COLUMNS` con `is_test`, `create_user(name,
  is_test=False)`, `list_users(include_test=False)`, `delete_test_user(uid)`.
- `backend/domain/users.py`, `backend/routers/users.py`, `backend/schemas/users.py`
  — propagan `is_test`/`include_test` y el `DELETE` acotado.
- `launcher/status.py` — `read_users` filtra `is_test` con degradación tolerante.
- `scripts/purge_virtual_testers.py` — nuevo `--is-test` (mantiene `--pattern`).
- `frontend/src/features/listening/ListeningPractice.tsx` — `stageLevel` con
  `resolveRouteLevel` (anillo/`routeNote`/`toggleLevel`), efecto de carga con
  `[userId, selectedLevel]`, estado A/B con `abLoop`, centrado `self-center`.
- `frontend/src/features/listening/abLoop.ts` — **núcleo nuevo y puro**:
  `EMPTY_AB_LOOP`, `MIN_AB_LOOP_SECONDS`, `toggleMark`, `armLoop`, `clearLoop`,
  `loopFromSegment`, `loopBounds`, `canClear`.
- `frontend/src/features/listening/audioController.ts` — `loadedUrl`, `play(url)`
  idempotente, `loop`/`rewindIfPastSegmentEnd` con `>=` y `onCurrentTime`.
- `backend/services/difficulty.py` — `_empty_fit(expected)`, `fit` con
  `dimensions_expected`/`dimensions_compared`/`coverage`, `select_by_difficulty`
  con degradación por cobertura.
- `backend/services/transfer.py` — `_difficulty_fit_for` expone las claves nuevas.
- `frontend/src/types/api.ts` — `DrillDifficultyFit` con las claves nuevas y
  `User.is_test?`.
- Tests: `backend/tests/test_users.py`, `backend/tests/test_user_profile.py`,
  `backend/tests/test_difficulty_engine_v352.py`,
  `launcher/tests/test_status.py`,
  `frontend/src/features/listening/abLoop.test.ts` (nuevo) y
  `frontend/src/features/listening/audioController.test.ts`.

## Tarea detallada (lo ejecutado)

1. Migración aditiva `users.is_test` + repositorio/schemas/router con filtro por
   defecto y `DELETE` acotado a perfiles de prueba.
2. `launcher/status.py::read_users` excluye `is_test` con degradación tolerante.
3. `globalSetup`/`globalTeardown` de Playwright + `gateHelper` sin carrera ni
   residuos.
4. `scripts/purge_virtual_testers.py --is-test` + purga de los 2 `Visual Tester`.
5. Listening: «RUTA ACTUAL» sigue al nivel seleccionado y recarga al cambiar de
   ruta.
6. Listening: máquina de estados A/B (`abLoop.ts`) + `play` idempotente +
   rebobinado con notificación + centrado.
7. `difficulty.fit` con cobertura dimensional + `select_by_difficulty` + payload y
   tests.
8. Normalización documental de la cifra de CI (2156+2 skipped primario).

## Criterios de aceptación

- `GET /api/users` no lista perfiles `is_test`; `include_test=true` sí; `DELETE`
  nunca borra un perfil real (404) y limpia las filas dependientes del de prueba.
- Tras correr la suite visual, no quedan perfiles `Visual Tester` en la BD y no
  aparecen en la app ni en el lanzador.
- En Listening, seleccionar A2 muestra «RUTA ACTUAL A2» y sirve una pregunta de
  A2; «Auto» vuelve a delegar en el motor.
- El bucle A/B sobrevive a pausa/reanudación con la misma URL, «quitar» desarma
  UI y controller, y el hint muestra el B marcado.
- `fit({}, challenge_no_vacio)` → `within=False`, `coverage=0.0`; un contexto sin
  `difficulty_vector` no gana la selección; con cobertura completa nada cambia.
- `ruff`/`pytest`/`vitest`/`tsc`/`build` en verde y `check_release_consistency` en
  `3.52.1`.

## Restricciones

- No tocar `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` ni FSRS.
- No introducir LLM, reloj ni aleatoriedad en las decisiones.
- Migración estrictamente aditiva; `cefr_level` y el resto del esquema se
  conservan.
- El borrado por API solo puede afectar a perfiles `is_test=1`.

## Salida esperada

Diff de backend + frontend + lanzador + script + tests + `release-notes-v3.52.1.md`
y actualización de `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md`,
`release-notes-v3.52.0.md` (cifra de CI) y `agentes/README.md`.

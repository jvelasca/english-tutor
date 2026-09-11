# v3.52.1 — Hotfix de producto + cierre del P1-01

**Hotfix ADITIVO (una columna de BD, `users.is_test`) que arregla tres bugs de
producto reportados sobre la V3.52.0 y cierra el P1-01 de su auditoría externa.
NO cambia la escalera `transfer_state`, sus umbrales, `context_signals`,
`context_diversity`, el scoring (`score_transfer_attempt`) ni FSRS, y tampoco
cambia el comportamiento real del motor de dificultad: los 20 contextos del banco
declaran las 4 dimensiones (cobertura 4/4), así que el endurecimiento del borde
no altera ninguna selección de producción. Determinista, sin LLM.**

Versión de app `3.52.0 → 3.52.1`. Backend (`repositories/db.py`,
`repositories/users.py`, `domain/users.py`, `routers/users.py`,
`schemas/users.py`, `services/difficulty.py`, `services/transfer.py`) + frontend
(`features/listening/ListeningPractice.tsx`, `features/listening/audioController.ts`,
`features/listening/abLoop.ts` nuevo, `types/api.ts`, tests visuales de Playwright)
+ lanzador (`launcher/status.py`) + script de purga + tests y docs.

## Contexto

Tres bugs de producto detectados en uso real y un P1 confirmado por la auditoría
externa de V3.52.0 que se acota y se cierra aquí:

- **Usuarios fantasma «Visual Tester».** Aparecían dos perfiles con ese nombre en
  la app y en la BD, pese a que existía un script de purga. La app no los creaba:
  los creaba `frontend/tests/visual/gateHelper.ts` con un find-or-create **no
  atómico** (GET y luego POST) contra la base de datos **real**
  (`backend/data/tutor.db`). Al correr 9 specs × 3 proyectos Playwright en
  paralelo, dos workers insertaban a la vez. El script de V3.48.1 solo borró
  filas: no tocó al creador.
- **Listening «RUTA ACTUAL».** Al cambiar el nivel seleccionado (A1 → A2, etc.) el
  anillo seguía mostrando «RUTA ACTUAL A1» y la pregunta no se recargaba.
- **Bucle A/B.** «Marcar inicio», «bucle A-B» y «quitar» se desincronizaban del
  audio real y el bloque de controles estaba descentrado respecto a su contenedor.
- **P1-01 (auditoría V3.52.0).** `difficulty.fit` comparaba solo las dimensiones
  presentes en ambos vectores y una intersección vacía devolvía un `within=True`
  «perfecto» con `distance=0`: un contexto con `difficulty_vector` parcial (o sin
  vector) podía ganar la selección.

P1-02 (Learner Skill State 2.0 + `observed_difficulty`) y P1-03 (Planner 2.0 /
Expected Learning Value) **quedan fuera de alcance**, como propone el audit, para
V3.53+.

## Cambios

### A. Usuarios fantasma (raíz + guarda + purga)

- **Raíz.** `tests/visual/globalSetup.ts` crea (o reutiliza) **un único** perfil de
  prueba en un proceso único —esto elimina la carrera de duplicados— y
  `tests/visual/globalTeardown.ts` lo borra al terminar. `gateHelper.ts` deja de
  hacer GET/POST: solo mockea `GET /api/users` con el perfil del setup, así que
  los 9 specs que lo llaman no cambian. En CI (sin backend) se usa un id ficticio
  y no se escribe nada.
- **Guarda `users.is_test`.** Migración aditiva (`CREATE TABLE` +
  `ALTER TABLE ... ADD COLUMN` idempotente en `repositories/db.py`). `create_user`
  acepta `is_test`; `list_users` filtra `is_test = 0` por defecto y expone
  `include_test=true` para los tests; `schemas/users.py` refleja el campo.
- **Borrado acotado.** Nuevo `DELETE /api/users/{id}` que **solo** borra perfiles
  `is_test=1` (un id real devuelve 404 y no se toca) y limpia las tablas con
  `user_id` enumeradas dinámicamente (misma estrategia que el script de purga,
  con FKs desactivadas para que el orden no importe).
- **Invisibilidad también en el lanzador.** `launcher/status.py::read_users`
  excluye los perfiles `is_test` con **degradación tolerante**: si la columna aún
  no existe (BD sin migrar), reintenta sin el filtro.
- **Purga inmediata.** `scripts/purge_virtual_testers.py` gana `--is-test`
  (borra por marcador, más seguro que `%tester%`) manteniendo `--pattern`. Se
  purgaron los 2 `Visual Tester` existentes (dry-run → `--apply`, copia
  `tutor.db.bak-<ts>`); quedan los 2 perfiles reales.

### B. Listening — «RUTA ACTUAL» sigue al nivel seleccionado

- El anillo se ataba a `stats.level` (la primera ruta no superada del backend) y
  nunca a la selección. Ahora usa `resolveRouteLevel(sesión > ruta seleccionada >
  recomendada)` —la MISMA prioridad que la carga de pregunta— en el anillo, su
  `ariaLabel`, su texto, su `toggleLevel` y el `routeNote`.
- El efecto de carga pasa de `[userId]` a `[userId, selectedLevel]`, así que
  seleccionar A2 sirve ya una pregunta de A2 (las rutas están deshabilitadas
  durante una sesión, así que no hay doble carga).
- El chip «Auto» (`null`) sigue delegando en el motor.

### C. Listening — bucle A/B (funcionamiento + centrado)

- Nuevo módulo PURO `features/listening/abLoop.ts` (máquina de estados: marcar,
  armar bucle, quitar marca, quitar bucle y reflejar un bucle externo) como
  **única fuente de verdad**; la pantalla aplica siempre el mismo estado al
  controller y a React a la vez, de modo que no pueden desincronizarse.
- `AudioController.play(url)` **no recarga** si la URL ya está cargada: preserva
  el segmento A/B y permite reanudar tras pausa sin reiniciar (si el audio
  terminó, repite desde el inicio del segmento).
- `loop()` y `rewindIfPastSegmentEnd()` usan `>=` y notifican `onCurrentTime` al
  rebobinar (el slider ya no se queda en B).
- La marca se toma del instante REAL (`audioController.currentTime`, no el estado
  React de ~4 Hz), el hint muestra el **B marcado** (no la posición viva) y
  «repetir palabra fallada» refleja su bucle en la UI (antes era invisible).
- Centrado: `self-center` en el wrapper de controles y en el caption de contexto.

### D. P1-01 — cobertura dimensional en `difficulty.fit`

- `fit` devuelve ahora `dimensions_expected` (dims del reto), `dimensions_compared`
  (intersección; `dimensions` se conserva como alias) y `coverage = compared /
  expected` (1.0 si no hay reto).
- `within` exige **cobertura completa** (`compared == expected`) y no pasarse de
  la tolerancia. Solo un reto vacío deja el encaje vacuo con `within=True`.
- `select_by_difficulty` degrada, cuando nadie encaja, por **mayor cobertura** y
  luego por menor distancia (antes solo por distancia).
- `services/transfer.py::_difficulty_fit_for` expone las claves nuevas en
  `difficulty_fit`; `DrillDifficultyFit` (`types/api.ts`) las recibe como
  opcionales.
- **Impacto real: cero.** Los 20 contextos del banco declaran las 4 dimensiones
  (cobertura 4/4). El cambio solo cierra el falso «encaje perfecto» del borde y
  prepara la reutilización del motor (speaking 2 dims / listening 0 dims).

### E. Corrección documental de la cifra de CI

`CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md` y `release-notes-v3.52.0.md` dejan
`2156 passed + 2 skipped` como cifra verificada de CI y `2158 passed` como
aclaración de local con el modelo Whisper, en lugar del titular anterior.

## Verificación

- Backend: `ruff` limpio y `pytest` **2164 passed** en local (+6: filtro
  `is_test` por defecto, `DELETE` acotado a test, borrado de filas dependientes y
  cobertura de `fit`/selector). En CI son 2162 + 2 skipped (los mismos 2 de
  `test_stt_asr_integration.py`).
- Frontend: `vitest` (**76 ficheros/651 tests**, +1 fichero/+11: `abLoop.test.ts`
  nuevo y `play` idempotente/rebobinado en `audioController.test.ts`),
  `tsc --noEmit` y `npm run build` en verde.
- Lanzador: `pytest` **76 passed** (+1: filtro `is_test` de `read_users`).
- Scripts: `check_release_consistency.py` (**3.52.1**), `check_beta_v3.py`,
  `content_validation.py` y `check_i18n_coverage` exit 0.
- Manual: los 2 `Visual Tester` purgados; la app y el lanzador muestran solo los 2
  perfiles reales; A1 → A2 en Listening actualiza «RUTA ACTUAL» y recarga la
  pregunta; los botones A/B funcionan y el bloque está centrado.
- **CI 6/6 en verde** (run
  [34622637688](https://github.com/jvelasca/english-tutor/actions/runs/34622637688)
  sobre `89eff0b`): Release consistency, Backend (ruff + pytest, **2162 passed + 2
  skipped**), Frontend (tsc + vitest + build), Playwright E2E (visual), Beta V3.0
  gate y Content validation.

## Qué NO cambia

- La escalera `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` y FSRS.
- El TECHO lingüístico del ítem (`_within_level`) y la selección real de
  contextos (cobertura 4/4 en todo el banco).
- La semántica del chip «Auto» de Listening ni la persistencia de
  `selected_route_level`.

## Fuera de alcance (V3.53+)

- **P1-02:** Learner Skill State 2.0 + `observed_difficulty` persistido.
- **P1-03:** Planner 2.0 / Expected Learning Value.
- Aislamiento total de los tests visuales con un `DATA_DIR` temporal (hoy sigue
  habiendo una escritura transitoria en local mientras corre la suite).

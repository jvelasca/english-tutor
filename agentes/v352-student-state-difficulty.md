# Briefing de subagente — V3.52 (Student Skill State + Difficulty Engine 2.0)

> **Estado:** incremento V3.52 **ejecutado** el 2026-09-11 por el gerente a
> partir de la auditoría externa de V3.51 (P1-01/P1-02). Ver
> `release-notes-v3.52.0.md` para el resultado final y `docs/RELEVO.md` para el
> relevo. Este documento sirve como traspaso autocontenido: si hay que rehacer,
> auditar o continuar el trabajo, aquí está todo el contexto.

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) del proyecto English
Tutor, con foco en el nivel del alumno (`Student Model`), la caché
`learning_profile`, el Evidence Ledger y el motor de transferencia
(`services/transfer.py`).

## Objetivo

Cerrar los dos P1 de la auditoría externa de V3.51 **sin tocar la escalera
`transfer_state`, sus umbrales, `context_signals`, `context_diversity`, el
scoring (`score_transfer_attempt`) ni FSRS**:

- **P1-01 — `learner_level` no era el nivel demostrado.** La caché
  `learning_profile.cefr_level` guardaba `estimated_level` (banda de PRÁCTICA
  continua). Separar `practice_level` / `estimated_cefr` / `demonstrated_cefr` y
  usar el DEMOSTRADO como suelo de dificultad, con política conservadora.
- **P1-02 — el difficulty floor mezclaba escalas.** `_difficulty_floor` comparaba
  `cefr_index` (0..5) contra la media del `difficulty_vector` (1..6) y colapsaba
  las 4 dimensiones: `(5,1,5,1)` y `(3,3,3,3)` eran indistinguibles. Comparar
  VECTOR contra VECTOR por dimensión.

Todo es **aditivo en el contrato HTTP** (más dos columnas de BD), determinista y
sin LLM en la decisión (premisa 21). El `context_id` servido sigue siendo el del
contexto realmente elegido y el gate de `transfer_state` no se toca.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Premisa 6:** un incremento a la vez, con su release.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m pytest -q`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisiones de alcance (cerradas)

- **Suelo en tres niveles con prioridad.** `floor_level`: `demonstrated` >
  `estimated` > `practice` > `none`. El demostrado gana **aunque su banda sea
  inferior** a la estimada: una certificación acredita retención; el estimado solo
  la intuye.
- **Solo el demostrado usa tolerancia estricta.** `DIFFICULTY_TOLERANCE = 1`
  (demostrado) vs `DIFFICULTY_TOLERANCE_ESTIMATED = 2` (estimado/declarado/ausente):
  menos confianza → más margen (conservador).
- **Migración aditiva y sin pérdida de señal.** `cefr_level` se conserva intacto y
  las filas legacy (columnas nuevas en `''`) alimentan el suelo como nivel
  DECLARADO (`practice`), no se descartan. `set_cefr` es un wrapper que no pisa un
  `demonstrated_level` certificado.
- **Lectura O(1) en el camino caliente.** `_learner_level_state` lee la caché
  (`learning_profile`, fila única); NO recalcula el Student Model en el drill.
  Paridad GET↔POST garantizada por test.
- **Reto = máximo por dimensión, techo aparte.** `challenge_vector` = max(ítem,
  alumno); el TECHO lingüístico del ítem sigue en `_within_level` (una unidad A1
  con alumno C2 NO recibe contextos > A1).
- **Degradación con gracia.** `select_by_difficulty` nunca deja el pool vacío y
  nunca sirve el más difícil por defecto: conserva los `within` y, entre ellos (o
  en su defecto en todo el pool), los de menor `distance`.
- **Diferido (V3.55).** `assessed_skill` → decisión del planner y
  `skill_priorities` → `select_task`: cablearlo sin más haría que el transfer
  contase como `written_production` junto al drill `write` (doble conteo).

## Archivos clave

- `backend/services/student_state.py` — **núcleo nuevo y puro**: `LEVEL_SOURCES`,
  `CERTIFIED_SOURCES`, `floor_level`, `level_state`, `is_certified`,
  `empty_state`.
- `backend/services/difficulty.py` — **núcleo nuevo y puro**:
  `DIFFICULTY_DIMENSIONS`, `CEFR_CAPACITY`, `DIFFICULTY_TOLERANCE`,
  `DIFFICULTY_TOLERANCE_ESTIMATED`, `normalize_vector`, `normalize_level`,
  `capacity_for`, `challenge_vector`, `fit`, `select_by_difficulty`,
  `tolerance_for`.
- `backend/repositories/db.py` — columnas aditivas `estimated_level` y
  `demonstrated_level` en `learning_profile` (CREATE TABLE + `ALTER TABLE`
  idempotente).
- `backend/repositories/profile.py` — `get_profile` (devuelve las columnas
  nuevas), `set_level_state` (upsert) y `set_cefr` (wrapper).
- `backend/domain/profile.py` — `get_profile_summary` escribe ambos niveles y
  `_compute_profile` expone `demonstrated_level`.
- `backend/domain/vocabulary.py` — `_learner_level_state` (O(1)) y
  `_learner_level` (compat); paso de `learner_level_source` en el GET y el POST.
- `backend/services/transfer.py` — `TRANSFER_DIFFICULTY_KEYS` alias,
  `TRANSFER_DIFFICULTY_BAND` deprecada, `_challenge_and_tolerance`,
  `_difficulty_fit_for`, `_normalize_source`; `context_for(...,
  learner_level_source="")` con el motor por dimensión y retorno con
  `difficulty_fit` + `learner_level_source`.
- `backend/schemas/vocabulary.py` — `TransferContextOut.learner_level_source` /
  `difficulty_fit`.
- `backend/schemas/profile.py` — `LearningProfile.demonstrated_level`.
- `frontend/src/types/api.ts` — `DrillTransferContext.learner_level_source?` /
  `difficulty_fit?` y `DrillDifficultyFit`.
- `backend/tests/test_student_state_v352.py` (15 tests) y
  `backend/tests/test_difficulty_engine_v352.py` (24 tests); ajuste de
  `test_task_semantics_v351.py::test_learner_level_raises_the_difficulty_floor`.

## Tarea detallada (lo ejecutado)

1. `services/student_state.py` con `floor_level`/`level_state` puros y robustos.
2. Migración aditiva de `learning_profile` + `get_profile`/`set_level_state`/
   `set_cefr` en `repositories/profile.py`.
3. `domain/profile.get_profile_summary` escribe `estimated_level` y
   `demonstrated_level` (`or ""`); `_compute_profile` expone `demonstrated_level`
   (`schemas/profile.py`).
4. `domain/vocabulary._learner_level_state` lee la caché y aplica
   `student_state.floor_level`; GET/POST pasan `learner_level` +
   `learner_level_source`.
5. `services/difficulty.py` con la tabla de capacidad, el reto por dimensión, el
   `fit` y el selector con degradación por mínima distancia.
6. `services/transfer.py` sustituye `_difficulty_floor`/`_within_band` por el
   motor y expone `difficulty_fit` + `learner_level_source` en todos los retornos.
7. Contratos aditivos en backend y espejo opcional en `types/api.ts`.
8. Tests nuevos + ajuste del contrato exacto de V3.51.

## Criterios de aceptación

- `floor_level` respeta `demostrado > estimado > declarado > none` y nunca lanza
  con valores no CEFR/`None`.
- `challenge_vector` es el máximo por dimensión y distingue vectores con la misma
  media (el P1-02).
- `select_by_difficulty` prefiere el encaje más cercano dentro de la tolerancia y,
  si nada encaja, degrada al más cercano (nunca al más difícil ni al vacío).
- Una unidad A1 con un alumno C2 **no** recibe un contexto por encima de A1.
- `difficulty_fit` y `learner_level_source` viajan en el contrato HTTP y el GET y
  el POST derivan el MISMO `context_id`.
- Cero regresión de `test_context_skill_v350.py`, `test_transfer_cefr_v347.py`,
  `test_context_bank_v348.py`, `test_transfer_*`, `test_learning_evidence_v336.py`,
  `test_optimal_task_v339.py`, `test_profile.py` y `test_academy.py`.

## Restricciones

- No tocar `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` ni FSRS.
- No introducir LLM, reloj ni aleatoriedad en la decisión.
- No recalcular el Student Model en el camino caliente del drill (O(1)).
- Migración estrictamente aditiva; `cefr_level` se conserva.
- `ruff`/`pytest`/`vitest`/`tsc`/`build` en verde y `check_release_consistency`
  en `3.52.0`.

## Salida esperada

Diff del backend + tipo del frontend + tests + `release-notes-v3.52.0.md` y
actualización de `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md` y
`agentes/README.md`.

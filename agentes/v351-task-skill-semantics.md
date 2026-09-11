# Briefing de subagente — V3.51 (Task/Skill semantics + learner-level difficulty)

> **Estado:** briefing del incremento V3.51, acordado por el gerente el
> 2026-09-11 a partir de la auditoría externa de V3.50 (`agentes/auditoria-externa-v350.md`).
> Ver `release-notes-v3.51.0.md` para el resultado final.

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) del proyecto English
Tutor, con foco en la semántica de tarea/skill, el Evidence Ledger longitudinal,
el planner (`services/planner.py`) y el motor de transferencia
(`services/transfer.py`).

## Objetivo

Cerrar los tres P1 de la auditoría externa de V3.50 **sin tocar la escalera
`transfer_state`, sus umbrales, el scoring (`score_transfer_attempt`) ni FSRS**:

- **P1-01 — qué se EVALÚA.** Un contexto declaraba ejercitar modalidades, pero la
  actividad podía no medirlas. El peldaño `transfer` se entrega por **textarea**:
  su eje es `spontaneous_use`, pero la modalidad que puede evaluar es
  `written_production`. Separar `target_skill` / `context_skills` /
  `assessed_skill` / `evidence_skill`.
- **P1-02 — de quién es la dificultad.** `context_for` anclaba la dificultad al
  CEFR del **ítem** (`vocabulary.cefr`). Introducir el nivel DEMOSTRADO del
  alumno como **suelo** de reto, manteniendo el CEFR del ítem como **techo**
  lingüístico.
- **P1-03 — el argmax descarta información.** Exponer el **vector completo** de
  prioridades por modalidad, no solo su máximo.

Todo es **aditivo en el contrato HTTP** (más una columna de BD), determinista y
sin LLM en el camino de la decisión (premisa 21). El `context_id` servido sigue
siendo el del contexto realmente elegido y el gate de `transfer_state` no se toca.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Premisa 6:** un incremento a la vez, con su release.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m pytest -q`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisiones de alcance (cerradas por el gerente)

- **Split honesto.** El transfer declara `assessed_skill="written_production"` y
  `assessment_mode="written"`; `spontaneous_use` se conserva como EJE de
  transferencia (y como `learning_evidence.skill`, contrato histórico del gate).
- **Migración aditiva.** El ledger gana la columna `assessed_skill`; las filas
  legacy quedan en `''` (no se inventa semántica hacia atrás).
- **`evidence_skill` reproduce el contrato actual** de las cinco vías del drill:
  un test de paridad contra los `skill=` reales lo fija. El gate NO se altera.
- **Suelo/techo separados.** `level` = CEFR del ítem (techo, `_within_level`);
  `learner_level` = nivel cacheado del Student Model (suelo, `_difficulty_floor`).
  Sin nivel de alumno conocido, el resultado es idéntico a V3.50 (regresión
  garantizada por test).
- **El transfer no se orienta a oral.** `_transfer_target_skill` elige solo entre
  `task_semantics.assessable_skills("transfer")` (`written_production`,
  `spontaneous_use`): `spoken_production` lo cubre la actividad `sentence`.
- **Sin migración de datos ni recálculo del Student Model** en el camino caliente
  del drill: `_learner_level` lee la caché `learning_profile.cefr_level` (O(1)).
- **Diferido (V3.52+):** entrega oral real del transfer (audio+STT), Sense Engine
  2.0, `observed_difficulty` por evento, `expected_learning_value` / Adaptive
  Planner 2.0, Context Bank Family/Instance y offline TTS.

## Archivos clave

- `backend/services/task_semantics.py` — **núcleo nuevo** y puro: `ASSESSMENT_MODES`,
  `TASK_SEMANTICS`, `SKILL_ORDER`, `ACTIVITY_FOR_TARGET` y los helpers.
- `backend/repositories/db.py` — `assessed_skill` en `CREATE TABLE learning_evidence`
  y en el bucle idempotente de `ALTER TABLE`.
- `backend/repositories/evidence.py` — `record_evidence`, `record_evidence_bulk`,
  `list_evidence` y los histogramas `assessed_skill_*` de `summarize_by_target`.
- `backend/services/evidence.py` — `summarize_evidence`/`empty_summary` con
  `assessed_skill_attempts`/`assessed_skill_successes`.
- `backend/domain/vocabulary.py` — las cinco vías de evidencia, `_transfer_priorities`,
  `_transfer_target_skill`, `_learner_level` y los dos puntos de uso de `context_for`.
- `backend/services/planner.py` — `skill_priorities` + `limiting_skill` sobre el vector.
- `backend/services/transfer.py` — `learner_level` en `context_for`/`_difficulty_floor`
  y las dimensiones semánticas del retorno.
- `backend/schemas/{vocabulary,learning}.py` y `frontend/src/types/api.ts` — contratos aditivos.
- Tests nuevos: `backend/tests/test_task_semantics_v351.py`.

## Tarea detallada

### 1. Módulo puro `services/task_semantics.py`

- `ASSESSMENT_MODES = ("written", "spoken", "receptive")` (vocabulario único de canales).
- `TASK_SEMANTICS` por actividad (`word`, `sentence`, `write`, `recall`, `transfer`)
  con `target_skill`/`assessed_skill`/`assessment_mode`/`evidence_skill`.
  El transfer: `spontaneous_use` / **`written_production`** / **`written`** /
  `spontaneous_use`.
- Helpers que **nunca lanzan** y devuelven COPIA / valores neutros con actividad
  desconocida: `semantics_for`, `target_skill_for`, `assessed_skill_for`,
  `assessment_mode_for`, `evidence_skill_for`, `assessable_skills` (orden
  canónico), `is_assessable`, `activity_for_target`, `activity_from_activity_id`
  (normaliza `drill:<actividad>` incl. `drill:recall:<peldaño>`).
- `SKILL_ORDER` es **espejo local** de `services.evidence.LEXICAL_SKILLS` (el
  módulo no importa el ledger); test de paridad.

### 2. Ledger honesto

- Migración ADITIVA (columnas existentes intactas; filas legacy `''`).
- `record_evidence`/`record_evidence_bulk` aceptan `assessed_skill` (kwarg /
  clave de la entrada) y lo insertan; `list_evidence` lo devuelve.
- Histogramas `assessed_skill_attempts`/`assessed_skill_successes` con el MISMO
  criterio que `skill_attempts`/`skill_successes` (intentos = todos los eventos;
  éxito = clave creada en el éxito) y **paridad exacta** pura↔SQL.
- Las cinco vías de `domain/vocabulary.py` registran ambas dimensiones; `skill`
  no cambia.

### 3. Planner

- `skill_priorities(signals) -> dict[str, float]` en orden canónico; `limiting_skill`
  pasa a ser su argmax (mismo resultado que V3.50).
- `_transfer_target_skill` restringe la orientación a las modalidades evaluables
  por el transfer.
- `lexicon.review_item` y `context_for` exponen `skill_priorities` (aditivo).

### 4. Nivel del alumno

- `context_for(..., learner_level="")`: `_difficulty_floor(pool, level, learner_level)`
  usa `max(item_index, learner_index)` como suelo, con el techo del ítem intacto.
- `_learner_level` lee `repositories.profile.get_profile(...)["cefr_level"]` vía
  threadpool, valida el CEFR y degrada a `""`.
- GET y POST derivan el `context_id` con la MISMA expresión (paridad).

### 5. Contratos y tests

- Esquemas y `types/api.ts`: campos aditivos y opcionales.
- `test_task_semantics_v351.py`: paridad del vocabulario, transfer mide escrito y
  no oral, helpers robustos, migración, persistencia y paridad pura↔SQL,
  argmax del vector, `learner_level` (eleva el suelo / degrada / regresión),
  contrato HTTP y paridad GET↔POST.
- Actualizar el contrato exacto de `empty_summary` en `test_learning_evidence_v336.py`.

## Verificación (definición de hecho)

- `ruff` limpio; `pytest -q` verde sin regresión de `test_context_skill_v350.py`,
  `test_learning_evidence_v336.py`, `test_optimal_task_v339.py`,
  `test_transfer_v343/v346/v347/v349.py`.
- `npm run test`, `npx tsc --noEmit` y `npm run build` verdes.
- `check_release_consistency.py` (imprime **3.51.0**), `check_beta_v3.py` y
  `content_validation.py` exit 0.
- Documentación: `release-notes-v3.51.0.md`, `CHANGELOG.md`, `PLAN.md`, `README.md`,
  `docs/RELEVO.md` y este briefing; corrección P3-01 (2099→2097).

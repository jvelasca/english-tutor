# P7 — Student Model unificado + snapshots + naming CEFR (P1)

## Rol
Subagente full-stack que reconcilia los **dos estimadores CEFR divergentes** en una única fuente de
verdad: el **Student Model** de la Academy. `/api/profile` pasa a ser una **proyección** de ese
modelo, se añade el **histórico inmutable** de evaluaciones y se corrige el naming CEFR
("banda heurística" vs "CEFR oficial"). Todo determinista, sin LLM ni red.

## Contexto
Hoy hay dos estimadores CEFR paralelos que se contradicen:

- `/api/profile` (`services/cefr.py` + `domain/profile.py`): 5 destrezas, `nivel = banda mínima`,
  `confidence = samples/required`.
- `/api/academy/student-model` (`services/academy.py` + `services/adaptive.py` +
  `domain/academy.py`): 7 destrezas (`CANONICAL_SKILLS`), `nivel continuo ponderado`
  (`estimated_level` → `numeric`), `confidence = EMA de consistencia`, más `stability`,
  `readiness`, `reassessment`, `subskills`.

El Student Model ya es mucho más rico y **ya existe**; la deuda no es "falta un Student Model" sino
**divergencia/duplicación**. V1.12 lo convierte en la fuente de verdad única.

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). El cambio es
aditivo en el contrato de `/api/profile` (añade campos) y **cambia la semántica del nivel** global.

## Archivos
- Backend: `services/cefr.py`, `services/academy.py` (solo lectura de contrato),
  `services/adaptive.py` (solo lectura), `domain/academy.py`, `domain/profile.py`,
  `schemas/profile.py`, `repositories/db.py`, `repositories/profile.py`.
- Tests: `backend/tests/test_profile.py`, `backend/tests/test_cefr_evaluation.py`,
  `backend/tests/test_academy.py`, `backend/tests/test_adaptive.py`.
- Frontend: `frontend/src/types/api.ts`, `frontend/src/components/LearningProfile.tsx`,
  `frontend/src/utils/cefr.ts`, `frontend/src/utils/cefr.test.ts`,
  `frontend/src/utils/modes.ts`, `frontend/src/utils/modes.test.ts`, `frontend/src/index.css`.

## Tarea

### 1. Fuente única (`domain/academy.py`)
- Extraer/centralizar `build_student_model(user_id) -> dict` como **única** fuente de verdad del
  Student Model (reutiliza `build_skill_profile` + `adaptive.estimated_level` + `readiness` +
  `reassessment_due`). `get_student_model` proyecta ese dict a `StudentModelOut`.

### 2. Proyección en `/api/profile` (`domain/profile.py`)
- Refactorizar `_compute_profile` para **delegar** en `academy_service.build_student_model` en
  lugar de su propio `services/cefr.py` min-band. Extraer helpers puros (`SkillProfileService`,
  `AssessmentService` y helpers `_bands_from_skills`/`_skill_states`/`_activity_stats`) para que
  `_compute_profile` deje de ser monolítico (god-function).
- `get_profile_summary` incluye el **histórico CEFR** (`cefr_history`) y persiste un snapshot
  cuando el nivel o la confianza cambian de forma material.

### 3. Snapshot histórico (`repositories/`)
- `repositories/db.py`: tabla idempotente `cefr_assessment_snapshots` (`id`, `user_id`, `level`,
  `numeric`, `confidence`, `instrument_version`, `curriculum_version`, `skills_json`,
  `created_at`) + índice `idx_cefr_snapshots_user_id`.
- `repositories/profile.py`: `record_cefr_snapshot(...)`, `list_cefr_history(user_id)` y
  `last_cefr_snapshot(user_id)`.

### 4. Naming CEFR (`services/cefr.py`)
- Conservar `estimate_cefr` (API v1) y las funciones de banda, renombradas/documentadas como
  **"heuristic CEFR-aligned band"** (no certificación oficial). Añadir `CEFR_MODEL_VERSION` para
  reproducibilidad de snapshots y `heuristic_band(score)`.
- `evaluate_cefr` deja de ser la fuente del perfil global (sigue para API v1).

### 5. Esquemas (`schemas/profile.py`)
- `EstimatedBands`: ampliar a 7 destrezas (`speaking`, `reading`, `writing`).
- Nuevas `SkillState` (`skill`, `band`, `score`, `samples`, `confidence`, `stability`, `trend`,
  `subskills`) y `CefrSnapshot` (`level`, `numeric`, `confidence`, `instrument_version`,
  `curriculum_version`, `skills`, `created_at`).
- `LearningProfile`: `current_level`, `overall_ability` (numeric), `target_level`, `skills`
  (lista de `SkillState`), `readiness` (`next_level`, `progress`, `blocking_skills`) y
  `cefr_history` (lista de `CefrSnapshot`).

### 6. Frontend
- `types/api.ts`: reflejar los nuevos tipos (`SkillState`, `CefrSnapshot`, `EstimatedBands` con 7
  destrezas, `LearningProfile` enriquecido). Eliminar `CefrEvidence` (modelo P5 antiguo).
- `utils/cefr.ts`: `bandLabel` para `speaking`, `reading`, `writing`.
- `utils/modes.ts`: `conversation` → banda `speaking`.
- `components/LearningProfile.tsx`: reescribir para mostrar `overall_ability` (barra continua),
  `readiness` (con `blocking_skills`), desglose por destreza con "why" (banda + muestras +
  confianza + tendencia), etiquetas "heuristic" y el histórico CEFR.
- `index.css`: estilos con tokens para ability/readiness/trend.

### 7. Tests
- `test_profile.py`: nuevo shape del endpoint (`overall_ability`, `estimated_bands` con 7
  destrezas, `skills`, `readiness`, `cefr_history`), snapshot grabado una sola vez.
- `test_cefr_evaluation.py`: `heuristic_band`, `CEFR_MODEL_VERSION`, `estimate_cefr` delegando.
- Frontend: `cefr.test.ts` (bandas nuevas) y `modes.test.ts` (`conversation` → `speaking`).

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes.
- `/api/profile` y `/api/academy/student-model` derivan del **mismo** Student Model (mismo nivel,
  mismo `overall_ability`, misma confianza).
- `/api/profile` expone `overall_ability`, `readiness` y desglose por destreza
  (muestras/confianza/tendencia), con bandas etiquetadas como heurísticas.
- Snapshots persistentes y reproducibles (con `instrument_version`).

## Restricciones
- No tocar `services/speaking.py` ni `services/speaking_llm.py` (de P6).
- No tocar `config.py` ni `CHANGELOG` (convención P3/P4: solo `docs/`).
- Mantener los docstrings (premisa 18). Todo determinista.

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.

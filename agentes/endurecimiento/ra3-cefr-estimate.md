# RA3 — Renombrar "CEFR estimate" a nivel estimado

## Objetivo
La heurística multi-señal no debe presentarse como CEFR real (no es una certificación). Renombrar
los campos para dejar clara su naturaleza estimada: `estimated_level`, `estimated_bands`,
`estimated_descriptor`.

## Cambios backend
- `backend/schemas/profile.py`: `CefrBands` → `EstimatedBands`; campos `cefr_level` →
  `estimated_level`, `cefr_bands` → `estimated_bands`, `cefr_descriptor` → `estimated_descriptor`.
- `backend/domain/profile.py`: `_compute_profile` usa los nombres nuevos; `profile_repo.set_cefr`
  usa `profile["estimated_level"]`.
- `backend/services/context.py`: `build_system_prompt` usa `profile.get("estimated_level")`.
- `backend/services/cefr.py`: conservar `evaluate_cefr`/`estimate_cefr` internas pero actualizar
  cualquier referencia pública al nombre.

## Cambios frontend
- `frontend/src/types/api.ts`: `CefrLevel` → `EstimatedLevel`, `CefrBands` → `EstimatedBands`;
  `LearningProfile` usa los nombres nuevos.
- `frontend/src/components/LearningProfile.tsx`: usar `estimated_level`/`estimated_bands`/
  `estimated_descriptor`.

## Tests
- `backend/tests/test_context.py`, `test_profile.py`, `test_cefr_evaluation.py` y los que referencien
  `cefr_*` → `estimated_*`.
- `frontend/src/api/learning.test.ts` → `estimated_level`.

## Verificación
- Backend `pytest` + `ruff`; frontend `tsc` + `vitest`.

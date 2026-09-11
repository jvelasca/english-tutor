# Briefing de subagente — V3.43 (Transfer 2.0)

> **Estado:** ejecutado por el gerente el 2026-09-11 (release `v3.43.0`). Se
> conserva como documento histórico de la tarea y como fuente de verificación.
> Ver `release-notes-v3.43.0.md` para el resultado final.

## Rol

Ingeniero de backend + frontend del proyecto English Tutor, con foco en el motor
de aprendizaje (evidencia longitudinal, planner y drill de vocabulario).

## Objetivo

Cerrar los 4 P1 de la auditoría de V3.42.0 sobre la evidencia de transferencia,
sin migración de BD y con contratos HTTP aditivos:

- **P1-01** — la consigna de transferencia no debe mostrar el target.
- **P1-02** — separar el transfer léxico de la adecuación semántica (proxy
  determinista, sin LLM: premisa 21).
- **P1-03** — medir diversidad contextual real, no `context_id A != B`.
- **P1-04** — formalizar `transfer_state` en lugar del booleano `transfer`.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local (Ollama).
- **Premisa 21:** el LLM genera contenido, nunca decide evidencia. La adecuación
  semántica es un proxy determinista y advisory.
- **Señal ≠ evidencia:** el drill no declara dominio ni toca FSRS.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Archivos clave

- `backend/services/transfer.py` — banco de contextos, `context_for`,
  `context_attributes`/`context_dimensions`/`context_distance`/`context_diversity`,
  `CONTEXT_DIVERSITY_MIN`.
- `backend/services/lexicon.py` — `score_transfer_attempt(word, text, *, pos)`,
  proxy `_semantic_fit`, `review_queue_item`.
- `backend/services/evidence.py` — `context_signals` (éxitos limpios),
  `transfer_state`, `TRANSFER_STATES`, `with_transfer_state`, `SEMANTIC_MISMATCH_ERROR`,
  `TRANSFER_ERROR_TYPES`.
- `backend/services/planner.py` — `has_contextual_transfer`, `transfer_gap`,
  `planned_signals`.
- `backend/repositories/evidence.py` — `summarize_by_target` (paridad con lo puro).
- `backend/domain/vocabulary.py` — `get_transfer_context`, `submit_transfer_attempt`.
- `backend/schemas/{vocabulary,learning}.py` — campos aditivos.
- `frontend/src/features/vocabulary/{wordDrill,ReviewQueueSection}.tsx`,
  `frontend/src/types/api.ts`, `frontend/src/utils/i18n.ts`.

## Tarea detallada

1. Reescribir `TRANSFER_CONTEXTS` con atributos y consignas sin `{word}`; añadir
   las funciones puras de diversidad.
2. Extender `score_transfer_attempt` con `pos` y la capa
   `lexical_transfer`/`semantic_fit`/`adequacy`; taxonomía `TRANSFER_ERROR_TYPES`.
3. Añadir a `context_signals` los éxitos limpios y la diversidad; crear
   `transfer_state` y sus estados.
4. Migrar `has_contextual_transfer`/`transfer_gap` al estado; exponer
   `transfer_state`/`context_diversity` en `planned_signals`.
5. Pasar `pos` y `success_contexts` en `domain/vocabulary.py`.
6. Añadir los campos aditivos en los esquemas y en `review_queue_item`.
7. Frontend: ocultar el target en `transfer`, aviso semántico, quitar `transfer`
   de `showsWord`, tipos e i18n.
8. Tests backend + frontend, bump de versión y documentación.

## Criterios de aceptación

- `pytest` 0 fallos y `ruff check backend/` limpio.
- `npm run test`, `npx tsc --noEmit` y `npm run build` limpios.
- `check_release_consistency` **3.43.0** exit 0.
- Contratos HTTP estrictamente aditivos (`passed`, `transfer`, `success_contexts`
  conservan su semántica).

## Restricciones

- **No** tocar el modelo léxico *sense-aware* ni `expected_learning_value`
  (diferido a V3.44).
- **No** añadir columnas ni migraciones: se reutiliza `error_type`.
- **No** usar un LLM para puntuar evidencia.
- Mantener la paridad pura↔SQL del resumen de evidencia.

## Salida esperada

Diff en backend y frontend, tests nuevos/ajustados y documentación de release
(`release-notes-v3.43.0.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`).

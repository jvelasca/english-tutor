# Briefing de subagente — V3.46 (Condición de recuperación en la transferencia)

> **Estado:** ejecutado por el gerente el 2026-09-11 (release `v3.46.0`). Se
> mantiene como registro del alcance acordado.
> Ver `release-notes-v3.46.0.md` para el resultado final.
> Escrito por el gerente el 2026-09-11 a partir de la auditoría externa de
> V3.43.0 (dossier `docs/audit/P-AUDITORIA-TOTAL-V343.md`, P1 `transfer_condition`).

## Rol

Ingeniero de backend + frontend del proyecto English Tutor, con foco en el motor
de evidencia longitudinal (transferencia, `transfer_state` y planner).

## Objetivo

Cerrar el P1 `transfer_condition` que la auditoría de V3.43.0 deja abierto: hoy
TODO intento de transferencia es `spontaneous_use` con `support_level
="spontaneous"`, sin distinguir si el alumno usó la unidad porque se le pidió,
porque el escenario la insinuaba, por decisión propia en un escenario abierto o
porque surgió sola en una conversación. Sin esa dimensión, el Student Model no
puede ponderar la evidencia y `transfer_demonstrated` puede declararse con
tareas andamiadas.

Taxonomía (auditoría, §15): `prompted`, `cued_context`, `open_context`,
`free_choice`, `naturally_emergent`.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia. La condición
  la DERIVA el servidor de la evidencia; el cliente no la declara.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

- **V3.46 = `transfer_condition` completo** (un solo eje). El CEFR/
  `difficulty_vector` del contexto y el Context Bank 2.0 pasan a **V3.47**.
- **Endurecer `transfer_demonstrated`**: exige al menos un ÉXITO LIMPIO en una
  condición NO andamiada (`open_context`/`free_choice`/`naturally_emergent`), con
  fallback legacy cuando el resumen no trae datos de condición.
- Migración **aditiva** (`transfer_condition TEXT NOT NULL DEFAULT ''` en
  `learning_evidence`), patrón idempotente de V3.36/V3.44.
- NO se toca `support_level` (sigue declarando el andamiaje de la ACTIVIDAD,
  `spontaneous`): la condición es la dimensión fina y la que decide la evidencia.

## Archivos clave

- `backend/services/transfer.py` — **núcleo**: `TRANSFER_CONDITIONS`,
  `SERVABLE_CONDITIONS`, `UNSCAFFOLDED_CONDITIONS`, `CONDITION_INSTRUCTIONS`,
  `normalize_condition`, `condition_for_state` (escalera por evidencia) y
  `context_for(..., condition=...)`.
- `backend/repositories/db.py` — columna aditiva `transfer_condition`.
- `backend/repositories/evidence.py` — `record_evidence`/`record_evidence_bulk`,
  `list_evidence`, `summarize_by_target` (SELECT de detalle).
- `backend/services/evidence.py` — `context_signals` agrega condiciones y
  `transfer_state` endurece `transfer_demonstrated`; `empty_summary`.
- `backend/domain/vocabulary.py` — `get_transfer_context` deriva la condición del
  resumen; `submit_transfer_attempt` la aplica (y NO registra el intento de
  `open_context` que no usa la unidad) y la persiste.
- `backend/schemas/vocabulary.py` — `TransferContextOut`/`TransferAttemptOut`
  aditivos (`condition`, `required_target`, `unscaffolded`).
- `frontend/src/types/api.ts`, `frontend/src/features/vocabulary/wordDrill*.tsx`,
  `frontend/src/utils/i18n.ts` — condición visible, mensaje neutro cuando no es
  obligatorio usar la unidad y paridad es/en.

## Tarea detallada

1. **Taxonomía pura.** Condiciones en orden de andamiaje decreciente; condiciones
   SERVIDAS por el drill (`prompted`/`cued_context`/`open_context`) y
   REGISTRABLES (las cinco); `UNSCAFFOLDED_CONDITIONS` = las que no dan la unidad
   ni la exigen. `CONDITION_INSTRUCTIONS` compone el `prompt` servido
   (escenario del banco + instrucción de la condición); el escenario nunca
   contiene la unidad salvo en `prompted`, que la nombra a propósito (condición
   más débil, y por eso queda registrada como tal).
2. **Escalera (`condition_for_state`, pura).** `not_ready` con intentos previos →
   `prompted` (el alumno no recupera ni con contexto: se nombra); `not_ready` sin
   intentos y `emerging` → `cued_context` (comportamiento de V3.43, sin
   regresión); `contextualized` o superior → `open_context` (escenario abierto,
   unidad NO obligatoria).
3. **Persistencia aditiva** de `transfer_condition` en el ledger (tabla + ALTER
   idempotente), con plumbing en `record_evidence`, el lote, `list_evidence` y el
   SELECT de detalle del resumen SQL (la paridad pura↔SQL es por construcción:
   `context_signals` es la MISMA función).
4. **Evidencia.** `context_signals` añade `transfer_conditions` (intentos y
   éxitos por condición), `transfer_condition_clean` (éxitos limpios) y
   `unscaffolded_clean_successes`. `transfer_state`: `transfer_demonstrated`
   exige, además de 2 contextos limpios con diversidad real, >= 1 éxito limpio NO
   andamiado; sin datos de condición (legacy/parcial) se conserva la regla actual.
5. **Dominio y contratos.** El GET deriva la condición del resumen y la sirve;
   el POST la re-deriva (el cliente no la declara) y la persiste. Un intento
   `open_context` que no usa la unidad NO se registra (no hay nada que observar
   sobre el objetivo) y el contrato lo expone (`required_target=false`).
6. **UI.** El drill muestra la condición servida y, cuando la unidad no es
   obligatoria, un aviso neutro en lugar del aviso de objetivo ausente; i18n es/en
   con paridad.

## Criterios de aceptación

- `pytest` 0 fallos y `ruff check backend/` limpio.
- `npm run test`, `npx tsc --noEmit` y `npm run build` limpios.
- `check_release_consistency` **3.46.0** exit 0.
- Contratos HTTP estrictamente aditivos (`passed`, `lexical_transfer`,
  `semantic_fit`, `adequacy`, `transfer` y `transfer_state` conservan semántica;
  sin condición → regla legacy).
- Regresión fijada por test: un éxito solo en `cued_context` NO declara
  `transfer_demonstrated`; el mismo éxito en `open_context` sí.
- Paridad pura↔SQL del resumen con la condición incluida.

## Restricciones

- **No** dar al cliente autoridad sobre la condición (la deriva el servidor).
- **No** tocar `support_level`, `score_write_attempt` ni el scoring semántico.
- **No** migración destructiva ni de datos: columna aditiva + idempotencia.
- Mantener la paridad pura↔SQL del resumen de evidencia.
- Fuera de alcance (V3.47): CEFR/`difficulty_vector` del contexto, Context Bank
  2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y
  `expected_learning_value` / Adaptive Planner 2.0.

## Salida esperada

Diff en backend y frontend, tests nuevos (`test_transfer_condition_v346.py`) y
ajustes de los existentes, y documentación de release
(`release-notes-v3.46.0.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`,
`agentes/README.md`).

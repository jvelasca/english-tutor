# Briefing de subagente — V3.47 (Transfer Evidence 2.0 + CEFR/`difficulty_vector` del contexto)

> **Estado:** ejecutado por el gerente el 2026-09-11 (release `v3.47.0`). Se
> mantiene como registro del alcance acordado.
> Ver `release-notes-v3.47.0.md` para el resultado final.
> Escrito por el gerente el 2026-09-11 a partir de la auditoría externa de
> V3.46.0 (ver `release-notes-v3.46.0.md` y `docs/RELEVO.md`).

## Rol

Ingeniero de backend + frontend del proyecto English Tutor, con foco en el motor
de evidencia longitudinal (transferencia, `transfer_state` y planner) y en el
banco de contextos.

## Objetivo

Cerrar los dos P1 que la auditoría de V3.46.0 deja abiertos sobre la
transferencia:

- **P1-02 — Transfer Evidence 2.0:** la escalera `transfer_state` acredita
  demasiado pronto: un único éxito limpio no andamiado declara
  `transfer_demonstrated` y `transfer_stable` se alcanza con dos días. Endurecer
  la escalera de forma gradual y explicitable, con fallback legacy.
- **P1 (sección 7) — CEFR/`difficulty_vector` del contexto:** el motor elige QUÉ
  contexto toca pero no registra CUÁNTO exige cada uno. Etiquetar el banco y usar
  el nivel del alumno en la selección.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia. Ni la escalera
  ni el etiquetado del banco usan modelo.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

- **V3.47 = Parte A + Parte B** (dos ejes acoplados por el mismo banco). Release
  **aditiva y SIN migración de BD** (las columnas de V3.46 ya existen).
- **Parte A:** `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED = 2`,
  `TRANSFER_STABLE_MIN_DAYS` `2 → 3`, nuevo `TRANSFER_STABLE_MIN_GOALS = 2`;
  `TRANSFER_STABLE_MIN_CONTEXTS = 3` se mantiene. Sin datos de condición se
  conserva la regla anterior (cero regresión).
- **Parte B:** cada contexto declara `cefr` y `difficulty_vector`
  (`lexical`/`syntax`/`discourse`/`interaction`, 1..5, convención
  listening/speaking); `context_for(..., level="")` retrocompatible.
- **NO se toca** `score_transfer_attempt` ni FSRS. **Sin cambio de UI** (evita
  churn de Playwright).
- **Diferido:** TTS/offline P1s (V3.47.1/V3.48), Sense Engine 2.0 (V3.48),
  Context Bank 2.0 (V3.48/V3.49), `transfer_state` enriquecido,
  `expected_learning_value`/Adaptive Planner 2.0 y aislamiento por usuario del
  Traductor.

## Archivos clave

- `backend/services/evidence.py` — **núcleo Parte A**: `context_signals` (señales
  finas nuevas), `transfer_state` (escalera endurecida),
  `_unscaffolded_transfer_ok`, `_clean_success_goals`, constantes y
  `empty_summary`.
- `backend/services/transfer.py` — **núcleo Parte B**: banco etiquetado,
  `TRANSFER_DIFFICULTY_KEYS`, `cefr_index`, `difficulty_from_vector`,
  `_within_level` y `context_for(..., level=...)`.
- `backend/domain/vocabulary.py` — pasa `level=row.get("cefr")` en el GET y en el
  registro.
- `backend/schemas/vocabulary.py` — `TransferContextOut` con
  `cefr`/`difficulty_vector`/`difficulty` (aditivo).
- `frontend/src/types/api.ts` — `DrillTransferContext` con los campos nuevos.
- Tests: `backend/tests/test_transfer_evidence_v347.py`,
  `backend/tests/test_transfer_cefr_v347.py` (nuevos) y ajustes en
  `test_transfer_v340.py`, `test_transfer_v343.py`,
  `test_transfer_condition_v346.py` y `test_learning_evidence_v336.py`.

## Criterios de aceptación

- Regresión fijada por test: 1 éxito no andamiado **ya no** declara
  `transfer_demonstrated`; `transfer_stable` exige 3 contextos + 3 días + 2
  objetivos.
- Todo contexto del banco declara `cefr` válido y vector con claves/rango
  correctos; `context_for` sin `level` es idéntico al de V3.46.
- Paridad pura↔SQL de todos los campos nuevos.
- `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.47.0**
  exit 0.

## Restricciones

- Contratos HTTP estrictamente aditivos; sin migración destructiva ni de datos.
- Sin LLM en el camino de la evidencia (premisa 21) y sin reloj en la decisión de
  `transfer_state` (pura y determinista).
- Un cambio grande a la vez (premisa 6): nada de TTS, Sense 2.0 ni Context Bank
  2.0 en esta release.

## Salida esperada

- Código + tests + `release-notes-v3.47.0.md` + actualización de `CHANGELOG.md`,
  `PLAN.md`, `README.md`, `docs/RELEVO.md` y bump `3.46.0 → 3.47.0` en las 6
  fuentes verificadas por `scripts/check_release_consistency.py`.
- Commit de release limpio y CI en verde.

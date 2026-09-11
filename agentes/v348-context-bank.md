# Briefing de subagente — V3.48 (Context Bank 2.0 + diversidad 2.0)

> **Estado:** briefing del incremento V3.48, acordado por el gerente el
> 2026-09-11 a partir del cierre de V3.47.0 (P2-04/P2-05 del dossier
> `docs/audit/P-AUDITORIA-TOTAL-V343.md`).
> Ver `release-notes-v3.48.0.md` para el resultado final.

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) del proyecto English
Tutor, con foco en el motor de transferencia (`services/transfer.py`), el banco
curado de contextos y la diversidad contextual que alimenta la evidencia
longitudinal.

## Objetivo

Cerrar los dos P2 que la auditoría externa de V3.43.0 deja abiertos sobre la
transferencia, sin tocar la escalera de evidencia ni el scoring:

- **Context Bank 2.0:** el banco curado tenía solo 6 contextos, insuficiente
  para rotar sin repetir y sin cobertura real de los niveles altos. Ampliarlo a
  20 contextos con cobertura A1–C2.
- **Diversidad 2.0:** la variedad contextual se medía solo con los 6 ejes core
  (`topic`/`communicative_goal`/`discourse_type`/`social_relation`/
  `time_reference`/`interaction_type`). Añadir una capa informativa
  (`register`/`lexical_environment`/`syntactic_focus`).

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia. El banco y la
  diversidad son tablas y funciones puras; no hay modelo en el camino.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

- **V3.48 = banco de 20 + variedad informativa.** Release **aditiva y SIN
  migración de BD**.
- **Los 6 contextos originales se CONGELAN** (mismos `id` y mismos valores core)
  para no alterar la evidencia ya registrada que referencia sus `context_id`.
- **La variedad NO entra en el gate de evidencia.** `CONTEXT_DIMENSIONS`,
  `context_distance`, `_novelty_score` y `diverse_dimensions` conservan la
  semántica de V3.47; `CONTEXT_DIVERSITY_MIN = 2` no cambia. Cero regresión.
- **Sin cambio de UI** (solo se declara el campo opcional en `types/api.ts`).
- **Diferido:** TTS/offline P1 (V3.47.1), Sense Engine 2.0, `transfer_state`
  enriquecido (`confidence`/`recency`) y `expected_learning_value`/Adaptive
  Planner 2.0.

## Archivos clave

- `backend/services/transfer.py` — **núcleo**: `TRANSFER_CONTEXTS` (20),
  `CONTEXT_VARIETY_DIMENSIONS`, `_normalize_dimensions`,
  `context_dimensions(..., dimensions=...)` (generalizada), `context_variety`
  (nueva, pura) y `context_diversity` (+ clave informativa `variety`).
- `backend/services/evidence.py` — `empty_summary()["context_diversity"]` con el
  default `variety` (paridad pura↔SQL). El gate (`transfer`/`transfer_state`) NO
  se toca.
- `frontend/src/types/api.ts` — `ContextDiversity.variety` (opcional).
- Tests nuevos: `backend/tests/test_context_bank_v348.py`. Ajuste de
  `backend/tests/test_transfer_v343.py` y
  `backend/tests/test_learning_evidence_v336.py` (diccionarios exactos con la
  clave `variety`).

## Criterios de aceptación

- Banco de 20 contextos con `id` únicos, cobertura A1:3 / A2:4 / B1:4 / B2:3 /
  C1:3 / C2:3, todos con atributos core y de variedad no vacíos, `cefr` válido,
  `difficulty_vector` con las 4 claves (1..5) y `prompt` sin `{word}` ni el
  target.
- Los 6 originales, congelados (guardia por test).
- Distancia mínima entre contextos del banco `>= CONTEXT_DIVERSITY_MIN`.
- `context_diversity` conserva `distinct_contexts`/`dimensions`/
  `diverse_dimensions`/`score` y añade `variety`; `diverse_dimensions` cuenta
  SOLO los ejes core.
- No regresión del gate: filas limpias no andamiadas en `story`+`future` siguen
  dando `transfer` y `transfer_demonstrated` (reglas de V3.47).
- `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.48.0**
  exit 0.

## Restricciones

- Contratos HTTP estrictamente aditivos; sin migración de BD.
- Sin LLM en el camino de la evidencia (premisa 21) y sin reloj en la decisión.
- Un cambio grande a la vez (premisa 6): nada de TTS, Sense 2.0 ni Planner 2.0.

## Salida esperada

- Código + tests + `release-notes-v3.48.0.md` + actualización de `CHANGELOG.md`,
  `PLAN.md`, `README.md`, `docs/RELEVO.md` y `agentes/README.md`, y bump
  `3.47.0 → 3.48.0` en las 6 fuentes verificadas por
  `scripts/check_release_consistency.py`.
- Commit de release limpio y CI en verde.

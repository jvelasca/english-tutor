# Briefing de subagente — V3.44 (Sense-Aware Lexicon + Semantic Scoring 2.0)

> **Estado:** ejecutado por el gerente el 2026-09-11 (release `v3.44.0`). Se
> mantiene como registro del alcance acordado.
> Ver `release-notes-v3.44.0.md` para el resultado final.
> Escrito por el gerente el 2026-09-11 a
> partir de la auditoría externa de V3.43.0 (dossier `docs/audit/P-AUDITORIA-TOTAL-V343.md`).

## Rol

Ingeniero de backend + frontend del proyecto English Tutor, con foco en el motor
de aprendizaje (léxico, evidencia longitudinal, transferencia y planner).

## Objetivo

Cerrar los dos P1 conceptuales que la auditoría de V3.43.0 deja abiertos, sin
migración destructiva y sin dar al LLM autoridad sobre la evidencia:

- **P1-01 — el proxy semántico no puede usar la `pos` GLOBAL como sustituto de
  sentido.** `travel`/`water`/`plan`/`work`/`change`/`answer`/`phone`/`email`
  son legítimamente noun y verb según contexto; declararlas de una sola familia
  produce falsos positivos (`I plan my trip` → `semantic_mismatch`) que impiden
  un clean success. La solución es el modelo `lexical_unit → sense`.
- **P1-02 — scoring semántico robusto.** La taxonomía `fit`/`suspect`/`unknown`
  confunde «parece raro» con «es incorrecto». Se añade `incorrect`, y **solo
  `incorrect` bloquea el clean success**; `suspect` es advisory (warning +
  confianza), nunca destruye evidencia léxica.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local (Ollama).
- **Premisa 21:** el LLM GENERA CONTENIDO (definición, traducción, situación,
  ahora sentidos), nunca decide evidencia. La adecuación semántica es un proxy
  DETERMINISTA y advisory.
- **Premisa 12:** cada fix va precedido de un test que falle hoy; read-only
  durante auditorías.
- **Señal ≠ evidencia:** el drill no declara dominio ni toca FSRS.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

Alcance **A**: núcleo sense-aware (P1-01) + scoring semántico (P1-02). Los
sentidos son **CONTENIDO generado por el modelo local** y cacheados (opción A2),
con **migración aditiva** en la caché del diccionario (`senses_json`), bump de
`GENERATOR_VERSION` y regeneración lazy. Fuera de alcance (V3.45+):
`transfer_condition`, CEFR/`difficulty_vector` del contexto, Context Bank 2.0,
`expected_learning_value` / Adaptive Planner 2.0 y Student Model
multidimensional.

## Archivos clave

- `backend/services/dictionary_content.py` — prompts con `senses`,
  `normalize_senses` (pura), `GENERATOR_VERSION` `1.3.0 → 1.4.0`, `MAX_SENSES`.
- `backend/repositories/db.py` — columnas `senses_json` aditivas e idempotentes
  en `dictionary_entries` y `dictionary_reverse_entries`.
- `backend/repositories/dictionary.py` — `get_entry`/`save_entry`/
  `get_reverse_entry`/`save_reverse_entry`/`_ENTRY_COLUMNS`/`_REVERSE_COLUMNS`.
- `backend/services/semantics.py` — **nuevo** módulo puro: familias POS del ítem
  desde los sentidos, rol de la ocurrencia en la frase y `semantic_adequacy`.
- `backend/services/lexicon.py` — `score_transfer_attempt(word, text, *, pos="",
  senses=())`; `_semantic_fit` delega en `services.semantics`.
- `backend/services/evidence.py` — `SEMANTIC_DOUBT_ERROR`, `TRANSFER_ERROR_TYPES`
  y la regla de ÉXITO LIMPIO (solo `semantic_mismatch` bloquea).
- `backend/domain/vocabulary.py` — `submit_transfer_attempt` pasa los sentidos
  de la caché; `_build_dictionary_entry` expone `senses` (aditivo).
- `backend/schemas/vocabulary.py` — `DictionarySenseOut` +
  `DictionaryEntryOut.senses`; documentar `adequacy`/`semantic_doubt`.
- `frontend/src/types/api.ts`, `frontend/src/features/vocabulary/wordDrill.tsx`,
  `frontend/src/utils/i18n.ts` — `adequacy` admite `incorrect`, feedback y
  paridad es/en.

## Tarea detallada

1. Contrato de contenido: prompts (directo e inverso) piden `senses`
   (`[{pos, gloss}]`), `normalize_senses` determinista (pos canónico, glosa
   acotada, deduplicado, tope `MAX_SENSES`, orden estable) y bump a `1.4.0`.
   El `pos` superior se deriva del primer sentido válido (fallback al `pos` del
   modelo) para no tener dos fuentes divergentes.
2. Migración aditiva `senses_json TEXT NOT NULL DEFAULT ''` en ambas tablas
   (patrón `PRAGMA table_info` + `ALTER TABLE`) y plumbing de repos.
3. `services/semantics.py` (puro): `pos_family`, `families_from_senses`,
   `occurrence_role` (cues fuertes: pronombre sujeto, auxiliar/`to`, flexión
   verbal; cues débiles: determinante/posesivo) y `semantic_adequacy`.
   Reglas: si ALGUNA ocurrencia encaja con las familias → `fit`; si ninguna
   encaja y hay contradicción fuerte → `incorrect`; si solo débil → `suspect`;
   sin sentidos/POS o sin rol → `unknown`. Conservador: nunca inventa.
4. `score_transfer_attempt` mantiene `passed`/`lexical_transfer` y añade
   `adequacy ∈ fit|suspect|incorrect|unknown`; `error_type`: `incorrect →
   semantic_mismatch`, `suspect → semantic_doubt`; `fit`/`unknown` no cambian
   el `error_type` léxico. `semantic_fit: bool | None` se conserva (`None` en
   `unknown`).
5. Éxito limpio en `context_signals`: excluye SOLO `semantic_mismatch`. La
   paridad pura↔SQL se mantiene por construcción (test explícito).
6. Contratos y UI: `DictionaryEntryOut.senses`, tipo TS, feedback de `incorrect`
   en el drill e i18n con paridad.

## Criterios de aceptación

- `pytest` 0 fallos y `ruff check backend/` limpio.
- `npm run test`, `npx tsc --noEmit` y `npm run build` limpios.
- `check_release_consistency` **3.44.0** exit 0.
- Contratos HTTP estrictamente aditivos (`passed`, `lexical_transfer`,
  `semantic_fit`, `transfer` y `transfer_state` conservan su semántica; sin
  `senses` → `unknown`, que nunca bloquea).
- Regresión P1-01 fijada por test: `plan` con sentidos `{noun, verb}` +
  «I plan my trip» → `fit` (sin `semantic_mismatch`).

## Restricciones

- **No** dar al LLM autoridad sobre la evidencia: los sentidos son contenido.
- **No** migración destructiva ni de datos: solo columnas aditivas + bump.
- **No** tocar `score_write_attempt` (contrato exacto de 4 claves).
- Mantener la paridad pura↔SQL del resumen de evidencia.

## Salida esperada

Diff en backend y frontend, tests nuevos (`test_senses_v344.py`,
`test_transfer_v344.py`) y ajustes de los existentes, y documentación de release
(`release-notes-v3.44.0.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`).

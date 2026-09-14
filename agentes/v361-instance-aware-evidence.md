# Briefing de subagente — V3.61 (Instance-aware Evidence + Anti-spoiler Guard)

> **Estado:** V3.61 **EJECUTADA** (2026-09-14, `v3.61.0`), escrita sobre el árbol de
> `v3.60.0` (commit `2c79040`). Este documento registra el alcance, las decisiones
> de diseño y la verificación del incremento; se conserva como **histórico del
> método** (premisa 8: verifica siempre el estado real del árbol antes de asumir
> que un nombre o una línea siguen existiendo).
>
> **Qué cierra:** los **dos defectos funcionales** de la auditoría `T` de V3.60 y
> la parte **determinista** de los P1 de la auditoría `S`. Detalle completo en
> `release-notes-v3.61.0.md`; veredicto consolidado en la nota superior de
> `docs/RELEVO.md`.

## Rol

Ingeniero de backend (+ espejo de tipos en frontend) con foco en el **Context
Engine 4.0** (`services/transfer.py`), el **Evidence Ledger**
(`learning_evidence`) y el contrato del drill de transferencia.

## Objetivo

V3.60 dejó dos agujeros verificados contra el árbol:

1. **T-01 — La superficie SERVIDA podía nombrar la unidad objetivo.** El
   anti-spoiler de V3.60 validaba el `template` y las **claves** del
   `instance_space`, pero no los **valores de slot**: `shopping` servía en el
   índice 7 «You are in **a supermarket** and cannot find what you need…»
   (`services/transfer.py:1074`, servida en `:2978`). Con la unidad `supermarket`,
   la recuperación espontánea se convertía en producción **guiada** y la evidencia
   de transferencia quedaba contaminada.
2. **T-02 — La evidencia podía guardar la carga de OTRA instancia.**
   `TransferAttemptIn` no identificaba la superficie emitida
   (`schemas/vocabulary.py:826`) y el POST recalculaba la rotación con el contador
   **actual** (`domain/vocabulary.py:850`): dos respuestas simultáneas o un
   reintento de red persistían el vector de la superficie **siguiente**.

Y de `S`, tres P1 deterministas (los otros dos P1 —equivalencia pedagógica real y
Student Skill State agregado— se aceptan como escalón siguiente, no como defecto):

- **P1-01** el espacio seguía siendo memorizable (12–19 superficies por familia y
  rotación predecible `attempts % len`),
- **P2-01** el cap recortaba un **prefijo** del producto cartesiano,
- **P1-02** el `difficulty_delta` podía declararse **sin justificar**.

## Estado de partida verificado (árbol `v3.60.0`)

- `services/transfer.py`: `TRANSFER_CONTEXTS` (20 familias, **358** superficies),
  `CONTEXT_INSTANCE_KEYS` (7), `CONTEXT_INSTANCE_SPACE_MIN = 12` /
  `CONTEXT_INSTANCE_SPACE_MAX = 96`, `context_instance_details`,
  `context_instance_index`, `context_instance_difficulty`, `served_difficulty`,
  `_expand_spec` (recorte por `[:96]`).
- `services/difficulty.py`: `normalize_vector`, `normalize_delta`, `apply_delta`.
- `schemas/vocabulary.py`: `TransferContextOut` (36 claves), `TransferAttemptIn`
  **sin** identificador de superficie.
- `repositories/evidence.py`, `repositories/db.py`: `learning_evidence` **sin**
  columna de instancia.
- Tests que blindan el banco: `test_context_engine_v359.py`,
  `test_context_engine_v360.py` (23).

## Decisiones de alcance (CERRADAS)

1. **La FAMILIA sigue siendo la identidad pedagógica Y la unidad de EVIDENCIA.**
   `context_id` es `transfer:<id>`; `context_instance` es **solo la superficie**.
   Nunca `context_id = transfer:<id>:<slug>`: el ledger **no se fragmenta**.
2. **El guard es léxico, determinista y conservador** (sin LLM ni WSD, premisa
   21): comparación por **token** con frontera de palabra y un juego acotado de
   variantes inflexivas. Un falso positivo solo puede **retirar** superficies,
   nunca dejar pasar la unidad.
3. **El guard no puede dejar al alumno sin tarea.** Una familia solo se retira del
   pool **si queda alternativa segura**; con el banco patológico (todas las
   familias delatan la unidad) se **degrada a V3.60 declarándolo**
   (`instance_guarded=False`).
4. **Identidad inmutable de instancia.** El slug es **estable por contenido**
   (`_slug` nunca usa `hash()`): el GET lo emite y el POST lo resuelve para
   persistir **su** carga. Slug ausente o desconocido degrada a la rotación
   actual con `matched=False` (nunca se miente en el ledger).
5. **Aditividad total.** `target` es **opcional** en las funciones puras (sin él
   no filtran: 100 % compatible con V3.60 y sus tests), la columna del ledger es
   aditiva e idempotente, y solo se **añaden** claves al contrato.
6. **SIN migración explícita, SIN bump de `GENERATOR_VERSION` y SIN cambios de
   UI/i18n.**
7. **Honestidad documental:** el cap estratificado y la rotación permutada
   **reducen** la memorizabilidad, no la eliminan. El cierre real es
   `Instance Generator 2.0` (V3.65+).

## Cambios

- **`services/transfer.py`** — `reveals_target`/`surface_reveals_target` (guard),
  `available_instance_details` (espacio servible), `serve_instance`,
  `served_difficulty_for_instance`, `_rotated_index` (rotación no secuencial
  sembrada por `(familia, unidad)` con `zlib.crc32`), `_stratified_indices` /
  `_partial_at` (cap estratificado), tercer eje `constraint` en las 20 familias
  (**358 → 1020** superficies) y `instance_suppressed`/`instance_guarded` en
  `context_for`.
- **`services/transfer_audit.py`** (nuevo) — `validate_instance_space` /
  `validate_bank` + `backend/scripts/transfer_validation.py` (CLI, paso nuevo del
  job Backend en `ci.yml`).
- **`schemas/vocabulary.py`** — `context_instance` en `TransferAttemptIn`;
  `instance_suppressed`/`instance_guarded` en `TransferContextOut` (38 claves) y
  cinco claves nuevas en `TransferAttemptOut`.
- **Ledger** — `repositories/db.py` (columna `context_instance` en el
  `CREATE TABLE` y en la lista idempotente de `ALTER TABLE`),
  `repositories/evidence.py` (kw-only en `record_evidence`/`record_evidence_bulk`
  y en el `SELECT` de `list_evidence`), `domain/vocabulary.py`
  (`_record_transfer_evidence` y `submit_transfer_attempt` con `serve_instance`),
  `routers/vocabulary.py`.
- **Frontend (solo contrato)** — `types/api.ts`, `api/vocabulary.ts` (envía
  `context_instance`) y `features/vocabulary/wordDrill.tsx`.

## NO cambia

`context_id`/`transfer_state`/sus umbrales, `context_distance`,
`context_diversity`, `_novelty_score`, `context_difficulty()`,
`CONTEXT_DIMENSIONS`, `CEFR_CAPACITY`, el Difficulty Engine, el scoring, el Sense
Engine, FSRS y el planner. Los agregados del ledger (`summarize_by_target`,
`list_observed_rows`) y la semántica del intervalo de evidencia quedan intactos.

## Verificación

```text
ruff check .                                  All checks passed
pytest tests/ -q                              2373 passed
pytest launcher/tests -q                      75 passed
npx tsc --noEmit                              OK
npm test                                      76 ficheros / 651 tests
npm run build                                 OK
python scripts/check_release_consistency.py   3.61.0
python scripts/check_beta_v3.py               OK
python backend/scripts/content_validation.py  OK
python -m scripts.transfer_validation         20 familias / 1020 superficies / 0 errores
```

Tests nuevos: `backend/tests/test_context_engine_v361.py` (**38**) — frontera de
palabra del guard, reproducción de **T-01** (`shopping`/`supermarket`:
`instance_suppressed == 12`, 39 superficies servibles), acuerdo GET/POST sobre la
superficie guardada, resolución de los **1020** slugs, regresión de **T-02** (el
slug conserva la carga respondida con el contador avanzado, incluido end-to-end
HTTP), degradación sin slug (`matched=False`), columna aditiva del ledger y
no-fragmentación de la familia, cap estratificado y rotación biyectiva/permutada,
y el validador (banco real + una violación sintética por invariante).

## Fuera de alcance (V3.62+)

Student Skill State 4.0 (modalidad × competencia × dimensión; V3.62), Observed
Task Difficulty 2.0 (V3.63), Planner 3.0 y rotación adaptativa (V3.64),
Instance Generator 2.0 (V3.65), WSD real, la división de `transfer.py` en paquete
y el arrastre de V3.59 (contrato/prompt de generación de sentidos con su bump de
`GENERATOR_VERSION` y la ponderación de la adecuación en `transfer_confidence`).

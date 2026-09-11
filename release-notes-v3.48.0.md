# v3.48.0 — Context Bank 2.0 + diversidad 2.0

**Release ADITIVA y SIN migración de BD que cierra los dos P2 que la auditoría
externa de V3.43.0 dejó abiertos sobre la transferencia. (A) *Context Bank 2.0*:
el banco curado de contextos pasa de 6 a 20, con cobertura real A1–C2 y los seis
contextos originales congelados. (B) *Diversidad 2.0*: se añade una capa de
variedad informativa (`register`/`lexical_environment`/`syntactic_focus`) que se
expone en `context_diversity.variety`. La variedad NO entra en el gate de
evidencia: la escalera `transfer_state` y el scoring quedan exactamente como en
V3.47.**

Versión de app `3.47.0 → 3.48.0`. Backend (`services/transfer.py`,
`services/evidence.py`) + frontend (`types/api.ts`) + tests y docs.

## Contexto

La V3.43.0 corrigió la sobreestimación de la transferencia y midió por primera
vez la diversidad contextual real, pero dejó dos P2: el banco de contextos seguía
teniendo solo 6 escenarios (rotaba en pocas sesiones y no cubría B2/C1/C2) y la
diversidad se medía con los mismos 6 ejes core, sin registrar el registro, el
entorno léxico ni el foco sintáctico de cada contexto.

Fuera de alcance (diferido y documentado): TTS/offline P1, Sense Engine 2.0,
`transfer_state` enriquecido (`confidence`/`recency`) y
`expected_learning_value`/Adaptive Planner 2.0.

## Qué cambia

### Parte A — Context Bank 2.0

- **20 contextos con cobertura A1–C2 (`services/transfer.py`).**
  `TRANSFER_CONTEXTS` pasa de 6 a 20: se añaden 14 contextos nuevos
  (`introductions`, `routine`, `directions`, `shopping`, `health`, `travel_plan`,
  `work_problem`, `community`, `debate`, `review`, `mediation`, `academic`,
  `negotiation`, `keynote`) con cobertura A1:3 / A2:4 / B1:4 / B2:3 / C1:3 / C2:3.
  Cada uno declara los 6 atributos core, `cefr`, `difficulty_vector`
  (`lexical`/`syntax`/`discourse`/`interaction`, 1..5) y los ejes de variedad.
- **Los 6 originales quedan CONGELADOS.** Mismos `id` y mismos valores core
  (`story`, `question`, `work`, `future`, `opinion`, `problem`): la evidencia ya
  registrada que referencia esos `context_id` no cambia de significado. Un test
  lo fija como guardia de regresión.
- **Las consignas siguen dando un ESCENARIO, nunca el target** (V3.43/P1-01):
  ningún `prompt` contiene `{word}`. Se verifica para los 20.

### Parte B — Diversidad 2.0 (informativa)

- **Nuevos ejes de variedad (`CONTEXT_VARIETY_DIMENSIONS`).**
  `register`, `lexical_environment` y `syntactic_focus`. `register` ya se
  declaraba en el banco (`neutral`); ahora se formaliza como eje de variedad y
  varía en los contextos nuevos (`neutral`/`informal`/`formal`).
- **`context_variety` (nueva, pura).** Gemela de `context_diversity` sobre los
  ejes de variedad: `{dimensions, varied_dimensions, score}`.
- **`context_dimensions(..., dimensions=...)` generalizada.**
  `_normalize_dimensions` permite medir cualquier conjunto de ejes sin duplicar
  lógica; sin argumento se usan los core (retrocompatible).
- **`context_diversity` mantiene su contrato y añade `variety`.** Las cuatro
  claves históricas (`distinct_contexts`, `dimensions`, `diverse_dimensions`,
  `score`) conservan la semántica de gate; `variety` es aditiva.

### El gate de evidencia NO cambia

- `CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score` y
  `diverse_dimensions` siguen midiéndose exactamente igual, y
  `CONTEXT_DIVERSITY_MIN = 2` se mantiene. La distancia mínima entre pares del
  banco ampliado es `>= 2`, así que ninguna combinación nueva relaja ni endurece
  el umbral.
- `services/evidence.py` no toca `context_signals.transfer`, `transfer_state` ni
  la escalera. Solo `empty_summary()["context_diversity"]` recibe el default
  `variety` para conservar la paridad pura↔SQL (el resumen SQL reutiliza la misma
  `context_signals`).

## Tests

- Backend pytest **2075 passed** (+12): nuevo `test_context_bank_v348.py`
  (tamaño e ids únicos del banco, cobertura CEFR objetivo, atributos core y de
  variedad no vacíos y `prompt` sin target, congelación de los 6 originales,
  distancia mínima `>= 2`, `diverse_dimensions` contando solo los ejes core,
  `context_variety` determinista, `context_dimensions` con ejes personalizados,
  `context_for` determinista/rotativo y filtrado por nivel en todo el banco, y no
  regresión del gate V3.47 con la variedad presente como información).
- Se ajustan los diccionarios exactos con la clave `variety`:
  `test_transfer_v343.py` y `test_learning_evidence_v336.py`
  (`test_empty_summary_matches_the_extended_contract`).
- Frontend vitest **72 ficheros/623 tests** (sin cambios: la release no toca UI;
  solo se declara el campo opcional `variety` en `ContextDiversity`).
- Verificación: `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.48.0**
  exit 0.
- **CI 6/6 en verde** (run
  [34583804612](https://github.com/jvelasca/english-tutor/actions/runs/34583804612)
  sobre `3438e55`): Release consistency, Backend (ruff + pytest), Frontend
  (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content
  validation.

## Fuera de alcance (V3.49+)

- TTS/offline: el P1 de la auto-descarga implícita de voces.
- Sense Engine 2.0 (selección de sentido real, no solo familias POS).
- `transfer_state` como objeto enriquecido (`confidence`/`recency`) y
  `expected_learning_value` / Adaptive Planner 2.0 (Student Model
  multidimensional).

## Decisiones de diseño

- **Ampliar sin tocar el gate.** Las dimensiones nuevas eran la tentación obvia
  para "mejorar" la diversidad, pero habrían cambiado la exigencia de la
  evidencia ya emitida: entran como información, no como umbral.
- **Congelar los originales.** El banco es contenido versionado por `id` en el
  ledger; reescribir un contexto existente habría reinterpretado evidencia
  histórica. Los seis primeros quedan intactos y los nuevos se añaden.
- **Determinismo intacto.** La elección sigue siendo pura (hash estable
  `zlib.crc32` + novedad sobre los ejes core) y la variedad no interviene en
  ella; la misma evidencia produce la misma consigna.
- **Sin LLM en la evidencia (premisa 21).** El banco y la variedad son tablas y
  funciones puras.
- **Aditivo de punta a punta.** Sin migración de BD, sin cambio de scoring, sin
  cambio de UI y sin tocar FSRS.

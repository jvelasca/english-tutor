# v3.49.0 — Transfer Evidence 3.0 (confianza del eje de transferencia)

**Release ADITIVA y SIN migración de BD que NO cambia la escalera
`transfer_state`, sus umbrales, el scoring ni FSRS. Añade una CONFIANZA
explicable al eje de transferencia para no sugerir más evidencia de la que hay
(punto 8 de la auditoría de V3.43.0): se deriva de evidencia fina ya registrada,
se computa en la misma frontera pura↔SQL y se expone en el planner, la cola de
repaso y la UI. Sin LLM y sin reloj en el `score`.**

Versión de app `3.48.1 → 3.49.0`. Backend (`services/evidence.py`,
`services/planner.py`, `services/lexicon.py`, `schemas/learning.py`) + frontend
(`types/api.ts`, `features/vocabulary/ReviewQueueSection.tsx`, `utils/i18n.ts`) +
tests y docs.

## Contexto

La auditoría externa de V3.43.0 (punto 8) avisó de que los nombres de los estados
(`transfer_demonstrated`, `transfer_stable`) pueden sugerir más evidencia de la
disponible: un criterio operacional interno correcto no equivale a «el alumno usa
la palabra espontáneamente en cualquier contexto». La evidencia fina ya estaba
registrada en `context_signals` (éxitos limpios, contextos, diversidad real,
éxitos NO andamiados, objetivos, días), pero no había forma de decir *con cuánta
evidencia* se afirmaba un estado.

Fuera de alcance (diferido y documentado): Context→Skill mapping y difficulty
matching por `difficulty_vector`, Sense Engine 2.0 (surface→lemma→sense),
semantic appropriateness (punto 7) y `expected_learning_value`/Adaptive Planner
2.0.

## Qué cambia

### Función pura `transfer_confidence` (`services/evidence.py`)

- **Contrato.** `transfer_confidence(evidence, *, now="")` devuelve
  `{score, level, sample, drivers, recency_days}`.
  - `score` — 0..1, suma ponderada de los `drivers` (`TRANSFER_CONFIDENCE_WEIGHTS`
    suman 1.0).
  - `level` — `none`/`low`/`medium`/`high` (`TRANSFER_CONFIDENCE_LEVELS`),
    umbrales `TRANSFER_CONFIDENCE_HIGH = 0.80` /
    `TRANSFER_CONFIDENCE_MEDIUM = 0.45` calibrados para que `transfer_stable`
    caiga en `high` y `transfer_demonstrated` quede por debajo.
  - `sample` — nº de éxitos LIMPIOS observados.
  - `drivers` — seis componentes 0..1 de evidencia YA registrada:
    `contexts` (contextos con éxito limpio / `TRANSFER_STABLE_MIN_CONTEXTS`),
    `successes` (`clean_successes` con techo
    `2 * TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED`), `diversity`
    (`diverse_dimensions` / nº de ejes core), `independence`
    (`unscaffolded_clean_successes` / `clean_successes`), `variety` (objetivos
    comunicativos distintos / `TRANSFER_STABLE_MIN_GOALS`) y `spacing`
    (`clean_success_days` / `TRANSFER_STABLE_MIN_DAYS`).
  - `recency_days` — INFORMATIVO (`now` opcional), NO entra en el `score`: la
    decisión no usa reloj, igual que `transfer_state`.
- **Monótona no decreciente** al añadir evidencia NO andamiada (cada `driver` lo
  es): más contextos, más éxitos, más independencia, más variedad y más
  espaciado nunca bajan el `score`.
- **Conservadora.** Un resumen legacy/parcial (sin los campos de V3.43 en
  adelante) devuelve `level: "none"` en lugar de inflar, y la función nunca
  lanza. Un uso semánticamente incorrecto (`semantic_mismatch`) no cuenta como
  éxito limpio; `semantic_doubt` sí (es advisory desde V3.44).

### Derivación, planner y contrato

- **Paridad pura↔SQL por construcción.** La confianza se deriva en la MISMA
  frontera que `transfer_state` (`with_transfer_state`), reutilizada por el
  resumen SQL (`repositories/evidence.py::summarize_by_target`).
  `empty_summary()` gana el default neutro (`level: "none"`, `drivers` a 0).
- **Planner.** `planned_signals` añade `transfer_confidence` (aditivo;
  `transfer_gap`/`has_contextual_transfer` NO cambian).
- **Cola.** `lexicon.review_item` expone `transfer_confidence`; contrato aditivo
  `ReviewQueueItem.transfer_confidence` (`schemas/learning.py`) y tipo
  `TransferConfidence` (`types/api.ts`).

### UI honesta (`ReviewQueueSection.tsx`, `utils/i18n.ts`)

- La cola muestra una etiqueta de confianza SOLO cuando hay evidencia (`level`
  distinto de `none`), con tono por nivel y `title`/`aria-label` que aclaran el
  alcance real: «transferencia contextual demostrada bajo el protocolo interno»,
  no transferencia generalizada.
- Claves nuevas `dictionary.review.transfer.level.*` y
  `dictionary.review.transfer.scope` con paridad es/en.

## Tests y verificación

- Backend pytest **2084 passed** (+9): nuevo
  `backend/tests/test_transfer_confidence_v349.py` (contrato y pesos declarados,
  calibración con la escalera, monotonicidad con evidencia no andamiada,
  conservadurismo en resúmenes legacy/parciales, `semantic_mismatch` no cuenta
  como limpio, `semantic_doubt` sí, `recency_days` fuera del `score` y paridad
  pura↔SQL); se ajusta el contrato exacto de `empty_summary` en
  `test_learning_evidence_v336.py`.
- Frontend vitest **75 ficheros/641 tests** (+2 en
  `ReviewQueueSection.test.tsx`: con evidencia y sin ella).
- `ruff check backend/` limpio, `tsc --noEmit` limpio, `npm run build` y
  `check_release_consistency` **3.49.0** exit 0.

## Fuera de alcance (V3.50+)

- Context→Skill mapping y difficulty matching por `difficulty_vector` (los datos
  declarados en V3.47/V3.48 aún no los consume el planner).
- Sense Engine 2.0 (surface→lemma→sense) y semantic appropriateness (punto 7).
- `expected_learning_value` / Adaptive Planner 2.0.
- No se tocan `transfer_state` ni sus umbrales (V3.46/V3.47), FSRS, el Evidence
  Ledger ni la CONSTITUCIÓN (R8/R9 sigue como propuesta abierta).

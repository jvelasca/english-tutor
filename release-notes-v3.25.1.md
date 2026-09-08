# v3.25.1 — Cierre de los P1 de la auditoría externa V3.25: certificación con retención real, agregación por unidad léxica y apoyo que pondera el dominio

**La auditoría externa de V3.25.0 (dossier
`docs/audit/M-AUDITORIA-TOTAL-V325.md`, verificada sobre `main`) encontró tres
P1 reales que la propia batería de V3.25 no detectaba: `certification_gate`
comprobaba la presencia de evidencia `delayed` pero **no** enforceaba la ventana
de ≥7 días ni el ratio de retención ≥0.90; `lexical_unit` se almacenaba y
exponía pero el modelo léxico **no** agregaba el conocimiento por unidad; y
`support_level` se agregaba en el perfil pero **no** ponderaba ningún cálculo de
dominio. V3.25.0 no se da por cerrada sin esta corrección: este patch cierra los
3 P1 con tests negativos explícitos y mantiene el contrato intacto (cambios
aditivos). V3.26 queda para Listening + `novel` + retención longitudinal.**

## Qué cambia

### P1-01 — Certification gate real (ventana ≥7 días + ratio ≥0.90)

`certification_gate` ([services/assessment_v2.py](backend/services/assessment_v2.py))
deja de confiar en la mera presencia de filas `delayed` (que los emisores ya
filtraban por ventana/ratio) y pasa a **verificar desde las propias filas** de
`academy_evidence`:

- **Baseline formal**: filas de examen (`task_type == "exam"`, cualquier
  `evidence_kind` distinto de `delayed`), que cubren la escalera Assessment 2.0
  (`kind=level`) y el examen legacy (`submit_exam`). El ancla formal es el
  `created_at` más reciente; `initial_score` por destreza es la media de
  `result` de esas filas. **Sin filas de examen no hay baseline y ninguna
  destreza puede certificarse** (`no-formal-baseline`).
- **Eventos `delayed`**: las filas con `evidence_kind == "delayed"` se agrupan
  por `context_id` (una sesión de retention emite una fila por ítem compartiendo
  contexto). Las filas legacy sin `context_id` son cada una su propio evento.
- **Umbral por destreza**: existe un evento `delayed` verificable (todos sus
  `created_at` parseables) con `interval_days >= RETENTION_MIN_DAYS` desde el
  ancla formal **y** `rate = delayed_score / initial_score >=
  RETENTION_STABLE_RATIO`. Solo entonces la destreza queda satisfecha.
- `retention_report` pasa a informar `interval_days` por evento (formal→delayed,
  no edad desde `now`), `initial_score`, `rate`, `best_rate`, `baseline_date` y
  las ventanas opcionales `intervals_reached` (D+1/D+3/D+7/D+21).

**Evidencia de cierre — los 6 tests negativos de la auditoría** (nuevos en
[backend/tests/test_assessment_v2.py](backend/tests/test_assessment_v2.py)):

| Caso | ¿Certifica? |
| --- | --- |
| `delayed` a D+6 (ventana < 7 días) | False |
| `delayed` a D+7 con ratio 0.89 (< 0.90) | False |
| `delayed` a D+7 con ratio 0.90 (frontera) | True |
| `delayed` a D+21 con ratio 0.50 | False |
| `delayed` con `created_at` inválido | False |
| dos eventos (`D+3`, `D+8`) sin ratio válido | False |

### P1-02 — Agregación real por `lexical_unit` (aditiva)

[backend/services/lexicon.py](backend/services/lexicon.py) gana dos funciones
puras que agrupan las filas por `lexical_unit` **sin fundir las superficies**:

- `units_from_rows(rows, now="")`: una entrada por unidad con sus superficies
  (`surfaces`) y el conocimiento derivado de unidad. Cada superficie conserva su
  **propio** `status`/`mastery`/`recall`/competencia: dominar `go` no domina
  `going`. El estado de unidad es un derivado informativo (`mastery`/`recall`
  máximos, `recognized`/`produced`/`transfer`, `production_gap`/`transfer_gap`
  por unidad), nunca un sustituto de la competencia por forma.
- `summary_units(rows, now="")`: contadores por unidad (`total`/`mastered`/
  `known`/`weak`/`learning`, competencia y CEFR) para que `go/going/went/gone`
  no cuenten como 4 conocimientos independientes.

Exposición **aditiva** (contrato intacto): `LexiconOut` gana
`units: list[LexicalUnitOut]`, `LexiconSummary` gana `units: dict` (opcional) en
[backend/schemas/vocabulary.py](backend/schemas/vocabulary.py);
[backend/domain/vocabulary.py](backend/domain/vocabulary.py) rellena ambos en
`get_lexicon`; [frontend/src/types/api.ts](frontend/src/types/api.ts) los espeja
como opcionales. La UI no cambia: el diccionario sigue consumiendo
`items`/`summary` por superficie.

### P1-03 — Support level como peso de la evidencia de dominio

[backend/services/academy.py](backend/services/academy.py) gana
`SUPPORT_LEVEL_WEIGHTS` y `generalized_mastery_score` pondera cada `result` por
el nivel de apoyo de su fila **antes** de promediar por `evidence_kind`:

- `copied 0.5 / guided 0.7 / cued 0.9 / independent 1.0 / spontaneous 1.0`
  (heurística a calibrar en V3.26, documentada como tal).
- Las filas legacy sin `support_level` (o con valor no declarado) usan peso
  **neutral 1.0**: los datos previos a V3.25 no cambian de valor (los tests
  existentes de `generalized_mastery_score` se mantienen byte a byte).

## Técnica

- Backend (versión de app `3.25.0 → 3.25.1`, fuente única `backend/config.py`):
  - `services/assessment_v2.py`: helpers `_mean_score`/`_latest_dt` y
    `certification_gate` reescrito (baseline formal + eventos `delayed` por
    `context_id` + ventana/ratio desde las filas); `now` se conserva por firma
    aunque el cálculo ya no depende del reloj.
  - `services/lexicon.py`: `units_from_rows`, `summary_units`,
    `_unit_status`, `_unit_representative`.
  - `schemas/vocabulary.py` + `domain/vocabulary.py` + `services/academy.py`:
    exposición aditiva y `SUPPORT_LEVEL_WEIGHTS`.
- Frontend: tipos espejo opcionales en `types/api.ts` (sin cambios de UI).
- Docs: `PLAN.md`, `CHANGELOG.md` (`[3.25.1]`), `README.md`, `docs/RELEVO.md`,
  dossier N (`docs/audit/N-AUDITORIA-TOTAL-V3251.md`).

## Tests

- Backend: **1495 pytest en verde** (gate con los 6 casos negativos de la
  auditoría + baseline formal + eventos por `context_id`; agregado
  go/going/went/gone con superficies independientes y `summary_units`; wiring
  del endpoint léxico; pesos de support con neutralidad legacy) + `ruff check .`
  limpio.
- Golden: `tests/test_golden_*.py` (incl. `thresholds.json`) en verde.
- Frontend: vitest **450 passed** (57 archivos); `tsc --noEmit` OK.
- `scripts/check_release_consistency.py` exit 0 (3.25.1).

## Fuera de alcance (P2 → V3.26)

- P2-01/P2-02 de la auditoría (initial/practice en los contadores del gate y
  `event_age` vs `retention_interval` en el reporte): seguimiento V3.26.
- Historial de eventos léxicos por superficie y calibración CEFR:
  V3.26+.
- V3.26 (hoja de ruta): Listening + emisor real del kind `novel` + retención
  longitudinal.

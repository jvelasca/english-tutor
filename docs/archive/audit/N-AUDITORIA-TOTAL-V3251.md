# N — Resolución de los P1 de la auditoría externa V3.25 (v3.25.1)

> Fecha: 2026-09-08 · Rol: **resolución de auditoría (cierre de P1 sobre el
> árbol de trabajo de `main`)**.
> Posición auditada: **árbol de trabajo sobre `main`** (candidato release
> **v3.25.1**, sin commit). `VERSION = "3.25.1"` confirmado en
> `backend/config.py`. La auditoría externa de v3.25.0 (dossier M,
> `docs/audit/M-AUDITORIA-TOTAL-V325.md`) declaró 3 P1 reales; este dossier
> registra su resolución y usa los **6 tests negativos del gate** como evidencia
> de cierre. Método: fijar primero el comportamiento correcto con tests
> (rojo/verde), implementar la corrección y reproducir **íntegra** la batería.
> Los P2 declarados por la auditoría quedan **fuera de alcance** (V3.26).

## Los 3 P1 y su resolución

### P1-01 — `certification_gate` no enforceaba ventana ≥7 días ni ratio ≥0.90

**Problema (auditoría):** el gate decidía con `delayed_by_skill >= 1` + fila
con `created_at` parseable. Calculaba `ages_days`/`longest_interval_days`/
`intervals_reached` pero no los usaba para `certified`, y nunca evaluaba el
ratio. La presencia de `delayed` se daba por buena porque el *emisor* ya filtraba
por ventana/ratio — el gate no lo verificaba él mismo.

**Resolución** ([backend/services/assessment_v2.py](backend/services/assessment_v2.py),
`certification_gate` + helpers `_mean_score`/`_latest_dt`):

- **Baseline formal** desde las filas: eventos `task_type == "exam"` con
  `evidence_kind != "delayed"` (cubre la escalera `kind=level` y el examen
  legacy `submit_exam`). Ancla = `max(created_at)`; `initial_score` por destreza
  = media de `result`. **Sin filas de examen no se certifica** (cada destreza
  queda pendiente, `baseline_date`/`initial_score` = `None`).
- **Eventos `delayed`** agrupados por `context_id` (una sesión de retention
  emite una fila por ítem); legacy sin contexto → cada fila es su propio evento.
- Una destreza queda satisfecha solo con un evento verificable cuya
  `interval_days >= RETENTION_MIN_DAYS` desde el ancla formal **y**
  `rate = delayed_score / initial_score >= RETENTION_STABLE_RATIO`.
- `retention_report` por destreza informa `interval_days`, `initial_score`,
  `rate`, `best_rate`, `baseline_date`, `longest_interval_days`,
  `intervals_reached` (informativo, no gate).

**Evidencia de cierre (tests que antes no existían y la auditoría pedía)** en
[backend/tests/test_assessment_v2.py](backend/tests/test_assessment_v2.py) +
adaptación de `test_evidence_context.py` y `test_academy.py` al baseline formal:

| # | Test | Resultado esperado | Estado |
|---|---|---|---|
| N1 | `delayed` a D+6 (ventana < 7 días) | `certified is False` | ✔ verde |
| N2 | `delayed` a D+7 con ratio 0.89 (< 0.90) | `certified is False` | ✔ verde |
| N3 | `delayed` a D+7 con ratio 0.90 (frontera) | `certified is True` | ✔ verde |
| N4 | `delayed` a D+21 con ratio 0.50 | `certified is False` | ✔ verde |
| N5 | `delayed` con `created_at` inválido | `certified is False` | ✔ verde |
| N6 | dos eventos (`D+3`, `D+8`) sin ratio válido | `certified is False` | ✔ verde |
| — | sin baseline formal (sin filas `task_type="exam"`) | `certified is False` | ✔ verde |
| — | sesión real (filas por ítem compartiendo `context_id`) | agrupa el evento y usa la media | ✔ verde |
| — | e2e: completar A1 sin retention; + retention ≥7 días | `demonstrated_level` None → `A1` | ✔ verde |

### P1-02 — `lexical_unit` no agregaba conocimiento por unidad

**Problema (auditoría):** `get_lexicon` construía un ítem por fila `word`;
`summary`/`coverage`/matriz operaban por superficie. La columna `lexical_unit`
existía (V3.25, fase 6) pero no agregaba nada: `go/going/went/gone` seguían
contando como conocimientos independientes a nivel de modelo.

**Resolución** (aditiva, contrato intacto):

- [backend/services/lexicon.py](backend/services/lexicon.py): `units_from_rows`
  (agrupa por `lexical_unit`; cada superficie conserva su **propio**
  status/mastery/recall/competencia; la unidad expone derivados informativos:
  mastery/recall máximos, `recognized`/`produced`/`transfer`,
  `production_gap`/`transfer_gap`, `mastered_surfaces`) y `summary_units`
  (contadores por unidad + CEFR de unidad).
- Exposición aditiva: [backend/schemas/vocabulary.py](backend/schemas/vocabulary.py)
  (`LexiconOut.units`, `LexiconSummary.units`), [backend/domain/vocabulary.py](backend/domain/vocabulary.py)
  (`get_lexicon` rellena ambos), [frontend/src/types/api.ts](frontend/src/types/api.ts)
  (tipos espejo opcionales). La UI no cambia.

**Evidencia de cierre**: `tests/test_lexicon.py` (`test_units_aggregate_go_paradigm_with_independent_surfaces`,
`test_units_surfaces_are_sorted_and_empty_rows_empty`, `test_summary_units_counts_each_unit_once`)
y wiring del endpoint en `test_vocabulary.py::test_lexicon_endpoint_exposes_units_aggregation`.
Assertión clave: con `go` dominada y `going` producida una vez, `went` solo
reconocida y `gone` sin evidencia, la unidad agrega 1 (no 4), `mastered_surfaces
== 1` y ninguna superficie se auto-masteriza.

### P1-03 — `support_level` no ponderaba el dominio

**Problema (auditoría):** `build_skill_profile` agregaba `support_levels` por
destreza pero `generalized_mastery_score` usaba solo `EVIDENCE_KIND_WEIGHTS`: el
apoyo (copiado/guíado/cued) no afectaba a ningún cálculo de dominio.

**Resolución** ([backend/services/academy.py](backend/services/academy.py)):

- `SUPPORT_LEVEL_WEIGHTS = {copied: 0.5, guided: 0.7, cued: 0.9, independent:
  1.0, spontaneous: 1.0}` (heurística documentada a calibrar en V3.26).
- `generalized_mastery_score` pondera cada `result` por el peso de su fila antes
  de promediar por `evidence_kind`. Legacy sin `support_level` (o valor no
  declarado) → peso **neutral 1.0** (los datos previos a V3.25 no cambian).

**Evidencia de cierre**: `test_academy.py::test_support_level_weights_constant_and_legacy_neutral`,
`::test_generalized_mastery_score_support_monotonic`,
`::test_generalized_mastery_score_mixes_support_levels`; los tests existentes de
`generalized_mastery_score` se mantienen byte a byte.

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Veredicto |
|---|---|---|---|
| N-G1 | `cd backend; python -m pytest -q` | **1495 passed** (vs 1481 de v3.25.0; +14 netos de la resolución) — exit 0 | ✔ reproducido |
| N-G2 | `cd backend; python -m ruff check .` | `All checks passed!` — exit 0 | ✔ reproducido |
| N-G3 | golden `tests/test_golden_*.py` (incl. `thresholds.json`) | en verde dentro de N-G1 | ✔ reproducido |
| N-G4 | `cd frontend; npx tsc --noEmit` | sin errores — exit 0 | ✔ reproducido |
| N-G5 | `cd frontend; npx vitest run` | **450 passed** (57 archivos) — exit 0 | ✔ reproducido |
| N-G6 | `python scripts/check_release_consistency.py` | `OK: Release consistency (3.25.1) en todos los orígenes` — exit 0 | ✔ reproducido |

**1495 tests en verde, 0 fallos, golden incluido, frontend intacto (450).** El
contrato por superficie y el resto de contratos (examen, completions, Student
Model, léxico, matrices) no cambian: la resolución es aditiva salvo en el
comportamiento correcto del gate (ventana + ratio desde las filas).

## Veredicto de cierre

- **P1-01 resuelto**: el gate verifica retención real (≥7 días + ratio ≥0.90)
  desde las filas; sin baseline formal no certifica. Los 6 tests negativos de la
  auditoría son evidencia de cierre.
- **P1-02 resuelto**: agregación real por `lexical_unit` (unidad + superficies
  independientes) expuesta de forma aditiva.
- **P1-03 resuelto**: `support_level` pondera `generalized_mastery_score` con
  neutralidad legacy.

**Fuera de alcance (P2 → V3.26):** initial/practice en los contadores del gate;
`event_age` vs `retention_interval` en el reporte longitudinal; historial de
eventos léxicos por superficie; calibración CEFR. V3.26 (hoja de ruta):
Listening + emisor real del kind `novel` + retención longitudinal.

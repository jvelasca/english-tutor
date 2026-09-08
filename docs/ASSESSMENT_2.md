# Assessment 2.0 (V2.10)

Escalera de evaluación formativa → sumativa → retención.

```
Lesson  → formative (micro-assessment)
Unit    → unit
~3 units → progress
Level   → level (CEFR exam)
Later   → retention (reassessment retardada)
```

Además: vista `readiness` derivada y **mastery gate** (no se considera
MASTERED solo por terminar).

## Regla MASTERED

Debe existir evidencia de:

| Requisito | Evidencia |
|---|---|
| initial | `familiar` primer encuentro ≥ 1 |
| practice | `familiar` re-encuentro espaciado ≥ 2 |
| transfer | `transfer` ≥ 2 |
| delayed | `delayed` ≥ 1 |
| ~~novel~~ | reservado (sin emisor; requisito 0, frontera V3.24) |

> **F-K1 (V3.24, dossier K):** el kind `novel` no tiene emisor real, así que el
> gate exige solo kinds emitibles. `novel` sigue siendo un kind válido (conteos,
> invariantes) pero ningún gate lo exige hasta que exista una modalidad que lo
> emita de verdad.

> **F-A1 (V3.26, P2-01):** `initial` y `practice` dejan de ser dos umbrales sobre
> el mismo contador `familiar`. Con `familiar_spaced_counts()`:
> - `initial` = contextos con al menos un encuentro `familiar` (primer encuentro).
> - `practice` = re-encuentros del MISMO contexto separados ≥
>   `SPACED_PRACTICE_MIN_DAYS` (1 día) del primer encuentro, uno por día distinto.
>
> Datos V3.25+ (context_id + fecha parseable) activan la separación; filas legacy
> sin contexto retroceden al conteo de filas (F-C4 las marca en el perfil).

Implementado en `mastery_evidence_gate()` (`services/assessment_v2.py`).

## Certificación del nivel (H5): retención sostenida

Aprobar el examen de nivel *completa* el nivel (desbloquea el siguiente); la
**certificación plena** es retención longitudinal multi-punto por cada destreza
del examen:

- ≥ `CERTIFICATION_REQUIRED_DELAYED` (2) **reassessment points estables** por
  destreza: cada punto es un evento `delayed` con ventana ≥ `RETENTION_MIN_DAYS`
  desde su sesión formal origen **y** ratio `delayed/initial ≥
  RETENTION_STABLE_RATIO`. Un único delayed puntual ya no certifica (F-A3,
  V3.26).
- Cada evento se ancla a su sesión formal origen (`delayed_origin_anchors` →
  `delayed_origins`), no al examen más reciente (F-A2, V3.26); sin origen
  resoluble se usa el examen más reciente como fallback legacy.
- El escritor espacia cada reassessment nuevo ≥ `RETENTION_MIN_DAYS` desde el
  último cerrado del mismo origen (`retention_spacing_due`, 409 si no) y un
  retention que reevalúa un examen `kind=level` puntúa contra la clave del
  examen (sus ítems no viven en el índice de checks del currículo).

Implementado en `certification_gate()` + `retention_spacing_due()` en
`services/assessment_v2.py`. El informe por destreza expone `events`,
`stable_points`, `interval_days`/`retention_interval_days` y `event_age_days`.

## Motor puro

`services/assessment_v2.py`:

- Construye instrumentos desde checks del currículo (formative/unit/progress)
  o desde `assessments.json` (level).
- `evaluate()` — pass/fail con umbrales por tipo.
- `retention_delta()` — ratio delayed/initial (+ estabilidad ≥ 0.9).
- `ladder_status()` — peldaños disponibles y siguiente recomendado.
- `evidence_kind_for()` — formative→familiar, unit/progress/level→transfer,
  retention→delayed.

## API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/academy/assessment/v2/ladder` | Escalera + readiness + mastery gate |
| POST | `/api/academy/assessment/v2/start` | Abre un peldaño |
| POST | `/api/academy/assessment/v2/submit` | Puntúa y cierra |
| GET | `/api/academy/assessment/v2/{id}` | Estado de sesión |

Persistencia: `assessment_v2_sessions`. Fuente de evidencia: `assessment_v2`
(kind `familiar` / `transfer` / `delayed`).

## Frontend

`AssessmentLadder` en la pestaña Assessment del `AnalysisPanel`: elige
peldaño → responde MCQ → ve pass/fail y, en retention, el delta.

## Tests

`backend/tests/test_assessment_v2.py` — motor puro + loops HTTP.

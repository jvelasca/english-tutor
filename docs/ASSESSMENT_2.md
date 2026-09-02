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
| initial | `familiar` ≥ 1 |
| practice | `familiar` ≥ 2 |
| transfer | `transfer` ≥ 1 |
| novel | `novel` ≥ 1 |
| delayed | `delayed` ≥ 1 |

Implementado en `mastery_evidence_gate()` (`services/assessment_v2.py`).

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

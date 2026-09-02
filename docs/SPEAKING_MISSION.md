# Speaking Mission Performance (V2.9)

Loop de rendimiento oral con mejora visible:

```
Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement
```

## Objetivo

Que el alumno no solo “haga speaking”, sino que **vea** qué falló, practique
eso concreto y mida si el reintento mejora. Reutiliza el motor existente
(escenarios + LLM extrae evidencia + scorer determinista).

## Fases

| Fase | Qué pasa |
|---|---|
| `mission` | Se elige un escenario del catálogo (`speaking_scenarios.json`) |
| `attempt` | El alumno produce (texto/audio → Whisper); se puntúa |
| `evaluation` | Overall + criterios + lista `weak` + recomendación |
| `drill` | Hasta 2 micro-prácticas dirigidas a criterios débiles |
| `retry` | Segundo intento de la misma misión |
| `improvement` | Delta overall y por criterio (`improved`, `by_criterion`) |

## Motor puro

`services/speaking_mission.py` (sin FastAPI ni red):

- `mission_from_scenario(scenario)`
- `evaluate_attempt(overall, criteria, observed?)`
- `targeted_drills(weak, cap=2)` — plantillas estáticas por criterio
- `improvement(first, retry)` — delta auditable

Umbral de debilidad: `0.6` (alineado con `SPEAKING_WEAK_THRESHOLD`).

## API

| Método | Ruta | Acción |
|---|---|---|
| POST | `/api/academy/speaking/mission/start` | `{scenario_id}` → sesión |
| POST | `/api/academy/speaking/mission/attempt` | primer intento |
| POST | `/api/academy/speaking/mission/retry` | reintento + cierre |
| GET | `/api/academy/speaking/mission/{id}` | estado completo |

Persistencia: tabla `speaking_mission_sessions` (mismo patrón que Speaking Assessment).

## Frontend

Panel `SpeakingMission` en la pestaña Speaking del `AnalysisPanel`:
elige escenario → envía intento → ve drills → reintenta → ve la mejora %.

## Tests

`backend/tests/test_speaking_mission.py` — motor puro + loop HTTP completo
(con `FakeOllamaClient`).

# E — FSRS / Retention (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** scheduler `services/fsrs.py` y la ventana de retención de Assessment 2.0 (`RETENTION_MIN_DAYS`/`retention_delta` en `services/assessment_v2.py`). Sin cambios de modelo: medición + golden + recomendación.
- **Relación con freeze:** calibración (`BETA_V3.md` §4.2).
- **Golden:** `tests/golden/fsrs/sequences.json`, `backend/tests/test_golden_fsrs.py`.

## Método

Simulación determinista de historias de review (golden) comprobando propiedades cualitativas del scheduling; medición numérica para el dossier; verificación de que la "ventana de retención ≥ 7 días" es un mecanismo **distinto** del scheduler de cartas.

## Evidencia numérica (simulada el 2026-09-02)

Secuencia `good` sobre una carta `skill` (interfaces reales de `fsrs.schedule`):

| Review | Grade | estabilidad (días) | intervalo programado (días) |
|---|---|---|---|
| 1 | good | 3.00 | 3.0 |
| 2 | good (día +3) | 5.53 | 5.5 |
| 3 | good (día +10) | 11.02 | 11.0 |
| 4 | good (día +21) | 22.20 | 22.2 |
| 5 | good (día +45) | 44.97 | 45.0 |

**No existe "Good → +7 días fijo":** el intervalo es función de la historia (3 → 5.5 → 11 → 22 → 45). La primera revisión *good* programa ~+3 días porque la estabilidad inicial es 3 (`INITIAL_STABILITY[GOOD]`), y crece ~×2 cada acierto. Un *good* no es un intervalo: es un incremento de estabilidad.

Secuencia con lapse y recuperación:

| Review | Grade | estabilidad | intervalo | estado | lapses |
|---|---|---|---|---|---|
| 1 | good | 3.00 | 3.0 | review | 0 |
| 2 | again (día +3) | 0.68 | 0.5 | relearning | 1 |
| 3 | good (día +4) | 1.28 | 1.3 | review | 1 |

El lapse **resetea** la estabilidad (3 → 0.68) y entra en `relearning`; la recuperación funciona (0.68 → 1.28) pero el coste del olvido queda reflejado (la carta nunca recupera el intervalo previo con un solo acierto).

## Verificaciones golden (comportamiento congelado)

- `good-x4-grows`: estabilidad e intervalo estrictamente crecientes; `reps 4`, `lapses 0`, estado `review`.
- `good-then-lapse-then-recovery`: lapse baja estabilidad; la recuperación la sube; `lapses 1`.
- `easy-vs-hard-after-first-good`: partiendo del mismo *good*, un *easy* programa bastante más lejos que un *hard*.
- `new-card-grade-transitions`: *good* desde `new` → `review`; *again* desde `new` → `relearning`.
- `memory-type-uniformity`: **el scheduler es hoy uniforme entre `skill` y `lexicon`**: misma historia → mismo resultado. Se documenta; no se cambia en esta fase.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| E1 | info | El modelo no es "Good → +7": ya distingue historia y grade. La sospecha inicial queda refutada con números. | simulación | — | aceptado |
| E2 | media | Scheduler uniforme por tipo de memoria: vocabulario (diccionario personal) y destrezas comparten estabilidad/dificultad a pesar de tener curvas de olvido distintas. | golden uniformity | Aparcar la diferenciación de parámetros por `target_type` hasta la fase de calibración con alumnos (PARKED). No cambiar el modelo sin datos. | aceptado (documentado) |
| E3 | info | La "ventana de retención ≥ 7 días" NO es un intervalo FSRS: es `RETENTION_MIN_DAYS` + `retention_delta` (ratio ≥ 0.9) de la escalera Assessment 2.0, y usa la misma batería (delayed evidence). Ambas conviven: FSRS programa cartas por olvido; la escalera re-testea competencias. | código | Mantener separados; el dashboard debe etiquetar cada uno. | aceptado |

## Recomendación

**No cambiar el scheduler en V3.** Está bien fundado (formulación FSRS-4.5 determinista, estabilidad/dificultad auditable). Las dos deudas (parámetros por tipo de memoria; calibración de `REQUEST_RETENTION = 0.9` y de los pesos de `next_stability`) se mueven a PARKED hasta tener datos de repaso reales.

## Regenerar / Verificar

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_golden_fsrs.py -q
```

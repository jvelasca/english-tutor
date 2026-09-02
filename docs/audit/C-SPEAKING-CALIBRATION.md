# C — Speaking Assessment Calibration (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** motor de Speaking Mission (`services/speaking_mission.py`), scorer determinista (`services/speaking.py`) y extracción LLM (`services/speaking_llm.py`). No se modifica lógica.
- **Relación con freeze:** calibración (`BETA_V3.md` §4.2).
- **Golden:** `tests/golden/speaking/mission_probes.json`, `backend/tests/test_golden_speaking.py`, harness `backend/scripts/eval_speaking_variability.py`.

## Método

1. Probes doradas del motor puro (determinismo): criterios débiles, frontera `MISSION_WEAK_THRESHOLD = 0.6`, selección de drills (orden de rúbrica + tope 2), mejora attempt→retry.
2. Determinismo del scoring: el mismo evidence normalizado produce el mismo resultado en repeticiones (verificado en CI).
3. Variabilidad de `extract_speaking_evidence`: **no es medible en CI** (depende de Ollama). Harness ejecutable para medir std/range del overall sobre la misma transcripción (probe B1 y B2).

## Evidencia (motor determinista)

Verificado por `test_golden_speaking.py` (22 tests golden en verde el 2026-09-02):

- `weak_criteria` clasifica por debajo de 0.6 exacto: fluency `0.599` → débil, `0.6` → no débil.
- Drills: se seleccionan los criterios débiles en orden de rúbrica y con tope 2 (`fluency`+`interaction` → 2 drills; `fluency` solo → 1).
- `improvement()`: `0.55 → 0.64` produce `delta 0.09, improved true`; `0.64 → 0.64` produce `improved false`. El desglose por criterio solo incluye criterios observados.
- `scores_from_evidence`: mismo evidence + misma transcripción → salida byte-idéntica (overall estable); sin referencia, `pronunciation` queda no observada (proxy honesto, no inventa nota).

## Evidencia (capa LLM) — protocolo, no resultado

El harness `python -m scripts.eval_speaking_variability` repite la misma transcripción N veces y reporta `std(overall)`, `range` y `distinct` por probe. Ejecución real requiere Ollama local con el modelo cargado:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.eval_speaking_variability --model llama3.1:8b --repeats 10 --temperature 0.0
```

Salida en `docs/audit/generated/speaking-variability.{json,md}`.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| C1 | media | La estabilidad del overall está condicionada a la extracción LLM: si la extracción varía, el overall varía aunque el scorer sea determinista. No hay hoy lógica de consistencia inter-intento ni re-extracción. | diseño + golden | Medir con el harness (temperatura 0). Si `std > 0.05` o `distinct > 2`, decidir mitigación: votación de N extracciones o re-extracción si el parse falla. **Ejecución física pendiente (requiere Ollama).** | abierto (protocolo listo) |
| C2 | baja | No hay temperatura configurada por llamada en producción (se usa 0.0 por defecto en `extract_speaking_evidence`), lo que favorece la estabilidad; debe mantenerse. | código | Documentar como política (no subir temperature en el flujo de assessment). | aceptado |
| C3 | info | Mock del harness produce std 0 por construcción (solo valida el cableado). | ejecución `--mock` | Usar solo como smoke test, nunca como medición. | aceptado |

## Veredicto

**El motor de Speaking Mission es determinista y sus umbrales están correctamente fijados** (golden). La única fuente de variabilidad real es la capa LLM y queda acotada a la fase de observación con el protocolo anterior. Hasta medir `std` real con Ollama, no se introduce ninguna mitigación ni cambio de temperatura.

## Regenerar / Verificar

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_golden_speaking.py -q
.venv\Scripts\python.exe -m scripts.eval_speaking_variability --mock   # smoke test del harness
```

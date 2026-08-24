# RA2 — Fluidez: verificar exposición en `PronunciationResponse`

## Objetivo
La auditoría externa afirmaba que `compute_fluency()` se calculaba pero no se exponía. Al
verificarlo, `PronunciationResponse.fluency` **ya estaba** en el contrato (desde F8) como
`FluencyStats` (`word_count`, `duration_seconds`, `wpm`, `level`) y `routers/pronunciation.py`
lo asigna y lo devuelve correctamente.

## Conclusión
Sin cambios de código. La fluidez ya se expone. Se mantiene el nombre `FluencyStats` (no se
renombra a `FluencyMetrics` para evitar churn innecesario y respetar la congelación de arquitectura).

## Verificación
- Confirmar `backend/schemas/pronunciation.py` (`fluency: FluencyStats`) y
  `routers/pronunciation.py` (`result["fluency"] = compute_fluency(...)`).
- Confirmar `frontend/src/types/api.ts` (`FluencyStats` + `PronunciationResponse.fluency`).
- Backend `pytest` + `ruff`; frontend `tsc` + `vitest`.

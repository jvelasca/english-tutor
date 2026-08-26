# V1.21 (3/6) — P0-3: Pronunciación real — separar proxy (transcript) del audio real

## Rol
Backend + frontend. Renombras y **etiquetas explícitamente** las señales de pronunciación que hoy son un *proxy sobre transcripción* para que el Student Model no crea que mide fonética acústica real. **No implementas análisis de audio** (eso es una versión futura). Sin dependencias nuevas.

## Contexto
La auditoría externa (puntos 16–19) identifica el mayor problema conceptual de V1.20: `phoneme_accuracy` y `prosody_score` trabajan sobre **texto** (G2P de `expected` vs `heard`), no sobre la señal acústica. Por ejemplo, si el alumno pronuncia "ship" como "sheep" y Whisper transcribe "ship", el sistema da `phoneme_accuracy = 100%` sin detectar `/ʃiːp/` vs `/ʃɪp/`.

La solución del auditor: **no eliminar** la implementación (es útil), sino cambiar el modelo conceptual:
- `phoneme_accuracy` → `phoneme_accuracy_proxy`
- `prosody_score` → `prosody_proxy`
- reservar los nombres `phoneme_accuracy` y `prosody` para la futura versión que analice audio.

Además añadir una marca explícita `pronunciation_source: "transcript"` en la respuesta.

### Contratos exactos actuales (renombra todo lo siguiente)
Los nombres a cambiar, con su ubicación exacta:

1. `backend/services/phonemes.py`
   - `def phoneme_accuracy(expected, heard)` (línea 124) → `def phoneme_accuracy_proxy(...)`
   - `def prosody_score(expected, heard)` (línea 192) → `def prosody_proxy(...)`
   - Mantén `phoneme_alignment`, `to_phonemes`, `levenshtein`, `syllables` intactas.
   - Añade una constante de módulo `PRONUNCIATION_SIGNAL_SOURCE = "transcript"`.

2. `backend/services/phonetics.py`
   - Import (línea 12): `from services.phonemes import phoneme_accuracy_proxy, phoneme_alignment, prosody_proxy`.
   - `composite_score`: `pa = phoneme_accuracy_proxy(...)`, `pro = prosody_proxy(...)`.
   - Keys de retorno (líneas 151–152): `"phoneme_accuracy_proxy"` y `"prosody_proxy"`. Añade `"pronunciation_source": "transcript"` al dict.
   - Actualiza el docstring (líneas 137–139) para reflejar los nombres nuevos.

3. `backend/services/pronunciation.py`
   - `score_pronunciation` (líneas 38–40): keys `"phoneme_accuracy_proxy"` y `"prosody_proxy"`; añade `"pronunciation_source": "transcript"`. Actualiza docstring.
   - `PRONUNCIATION_CRITERIA` (línea 48): `"phoneme_accuracy_proxy"` (en vez de `"phoneme_accuracy"`) y `"prosody_proxy"` (en vez de `"prosody"`).
   - `PRONUNCIATION_WEIGHTS` (líneas 54–59): mismas keys renombradas, **mismos valores** (0.35 / 0.35 / 0.15 / 0.15).
   - `score_pronunciation_cefr` (líneas 69–74): `"phoneme_accuracy_proxy": comp["phoneme_accuracy_proxy"] / 100`, `"prosody_proxy": comp["prosody_proxy"] / 100`. El resto igual.
   - `evidence_from_pronunciation`: usa `PRONUNCIATION_CRITERIA`, así que los `item_id` de evidencia pasan a ser `phoneme_accuracy_proxy` y `prosody_proxy` automáticamente. **No añadas campos extra a los registros de evidencia** (para no romper `record_evidence`).

4. `backend/services/listening.py`
   - `production_score` (líneas 136): `"phoneme_accuracy": int(result["phoneme_accuracy"])` → `"phoneme_accuracy_proxy": int(result["phoneme_accuracy_proxy"])`. Actualiza docstring (línea 128).

5. `backend/domain/listening.py`
   - Línea 176: `"phoneme_accuracy": result["phoneme_accuracy"]` → `"phoneme_accuracy_proxy": result["phoneme_accuracy_proxy"]`.

6. `backend/schemas/pronunciation.py`
   - `PronunciationResponse` (líneas 52–53): `phoneme_accuracy: int` → `phoneme_accuracy_proxy: int`; `prosody_score: int` → `prosody_proxy: int`. Añade `pronunciation_source: str`.

7. `backend/schemas/listening.py`
   - Línea 83: `phoneme_accuracy: int` → `phoneme_accuracy_proxy: int` (en el schema de producción de listening).

8. Frontend `frontend/src/types/api.ts`
   - Líneas 95–96 (tipo de respuesta de pronunciación): `phoneme_accuracy: number` → `phoneme_accuracy_proxy: number`; `prosody_score: number` → `prosody_proxy: number`; añade `pronunciation_source: string`.
   - Línea 307 (tipo de producción de listening): `phoneme_accuracy: number` → `phoneme_accuracy_proxy: number`.

9. Frontend `frontend/src/components/PronunciationPractice.tsx`
   - Línea 129: `result.phoneme_accuracy` → `result.phoneme_accuracy_proxy`; línea 133: `result.prosody_score` → `result.prosody_proxy`.
   - Actualiza los rótulos visibles para ser honestos: p. ej. "Precisión de fonemas (proxy de texto)" y "Ritmo silábico (proxy, sin audio)".

### Tests (renombra las referencias exactas)
- `backend/tests/test_phonemes.py`: import y llamadas de `phoneme_accuracy` → `phoneme_accuracy_proxy`, `prosody_score` → `prosody_proxy` (líneas 6–8 y todas sus apariciones).
- `backend/tests/test_phonetics.py`: `composite_score(...)["phoneme_accuracy"]` → `["phoneme_accuracy_proxy"]`, `["prosody_score"]` → `["prosody_proxy"]` (líneas 79–89). Añade una aserción de `composite_score(...)["pronunciation_source"] == "transcript"`.
- `backend/tests/test_pronunciation.py`: `"phoneme_accuracy"` → `"phoneme_accuracy_proxy"`, `"prosody_score"` → `"prosody_proxy"` (líneas 31–38). Añade aserción de `pronunciation_source`.
- `backend/tests/test_listening_production.py`: actualiza cualquier referencia a `phoneme_accuracy`.

## Criterios de aceptación
- `composite_score`, `score_pronunciation` y `score_pronunciation_cefr` exponen claves `*_proxy` + `pronunciation_source: "transcript"`.
- Los `item_id` de evidencia de pronunciación ya dicen `_proxy` (el Student Model no puede confundirlos con medición acústica).
- **No** queda ninguna clave pública llamada `phoneme_accuracy` o `prosody_score` en backend ni frontend (búscalo con `rg` para confirmarlo; las únicas apariciones restantes deben ser en docs/CHANGELOG que no tocas aquí).
- No cambias los **pesos** (0.35/0.35/0.15/0.15) ni la lógica de cálculo: es un renombrado semántico, no un cambio de scoring.
- Pasa `pytest` y `ruff`; el frontend compila (`npm run build` o el script de tu repo) sin errores de tipos.
- Crea un único commit `refactor: separar proxy de pronunciación (transcript) del audio real` (no hagas push). Deja el briefing untracked.

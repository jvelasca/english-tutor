# P6 — Speaking scoring 2.0 + higiene de release (P0)

## Rol
Subagente full-stack que corrige los 4 defectos de scoring del speaking determinista
(`services/speaking.py`), amplía la evidencia extraída por el LLM (`services/speaking_llm.py`) y
hace higiene de versión (`config.py`, `README.md`). Todo determinista: **el LLM extrae; el score
lo calcula SIEMPRE un scorer determinista** (filosofía congelada del proyecto).

## Contexto
La auditoría externa de V1.11 detectó que `services/speaking.py` tenía cuatro debilidades graves:

1. **Task Achievement mecánico** — se basa en solapamiento de tokens con `expected`. Penaliza
   producciones libres excelentes que no comparten los tokens exactos del modelo.
2. **Lexical Resource = solapamiento** — compara palabras del alumno con las esperadas (mide
   *overlap*, no *riqueza léxica*). Falta diversidad léxica (TTR/MSTTR) y sofisticación.
3. **Coherence débil** — se aproxima con `len(heard)/len(expected)`. Eso no mide coherencia.
4. **Pronunciation con "0.5" artificial** — `scores_from_evidence()` fija `pronunciation=0.5`
   cuando no hay audio; `unknown ≠ 50%` y degrada el `overall` como si fuera observación real.

Además, el `README.md` seguía diciendo `v1.7.0` y `backend/config.py` estaba desactualizado.

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). El cambio
es **interno al scorer** (no cambia el contrato HTTP) salvo la adición de `observed` por criterio.

## Archivos
- Backend: `services/speaking.py`, `services/speaking_llm.py`, `config.py`, `schemas/academy.py`,
  `domain/academy.py`.
- Tests: `backend/tests/test_speaking.py`, `backend/tests/test_speaking_llm.py`.
- Docs: `README.md`.

## Tarea

### 1. Scoring determinista (`services/speaking.py`)
- `task_achievement`: en el flujo libre (`scores_from_evidence`) manda el `task_achieved` (bool del
  LLM); en `score_speaking` (con `expected` exacto) el solapamiento actúa solo como cota inferior,
  no como única señal.
- `lexical_resource`: medir **diversidad léxica** (Type-Token Ratio) como señal principal; el
  solapamiento pasa a ser complemento. Añadir helper `lexical_diversity(tokens)`.
- `coherence`: usar `coherence` del LLM + marcadores discursivos (`discourse_markers`,
  `cohesion`); **eliminar** el ratio `len(heard)/len(expected)`.
- `pronunciation`: devolver `observed=false` / `score=None` cuando no hay audio; el `overall`
  (`_weighted_overall`) se recalcula **solo** sobre criterios observados (ponderados por su peso).
- Añadir `observed: dict[str, bool]` y `confidence` por criterio al resultado de `score_speaking`
  y `scores_from_evidence`.
- Penalizaciones discursivas: `self_corrections`, `hesitations`, `repetitions` reducen `fluency`.

### 2. Evidencia del LLM (`services/speaking_llm.py`)
- Ampliar `SPEAKING_EVIDENCE_FIELDS` con `cohesion`, `discourse_markers`, `self_corrections`,
  `hesitations`, `repetitions` (opcionales, compatibles con el JSON actual).
- `build_speaking_prompt` instruye al LLM a incluir esos campos; `parse_speaking_evidence` los
  parsea con helpers robustos (`_parse_float_field`, `_parse_count_field`) con fallback.

### 3. Higiene de release
- `backend/config.py`: `VERSION = "1.11.0"`.
- `README.md`: "Última versión estable" → `v1.11.0`.

### 4. Contrato de schemas/dominio
- `schemas/academy.py`: `SpeakingResultOut`/`SpeakingTaskResultOut` ganan `observed` y permiten
  `criteria: dict[str, float | None]` (None para criterios no observados).
- `domain/academy.py`: `submit_speaking`/`submit_speaking_task` propagan `observed`.

### 5. Tests
- `test_speaking.py`: casos de `observed` (pronunciación sin audio), diversidad léxica, sin
  `pronunciation=0.5`, y `discourse_penalties_reduce_fluency`.
- `test_speaking_llm.py`: extracción de campos opcionales del discurso y fallback ante counts
  inválidos.

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes.
- `scores_from_evidence` **no** devuelve `pronunciation=0.5` sin audio (usa `observed=false` y
  recalcula el overall solo con criterios observados).
- `config.py` y `README.md` reflejan `1.11.0`.
- Todo determinista, sin LLM ni red en los tests.

## Restricciones
- Mantener la filosofía "LLM extrae / scorer determinista calcula" (premisa 12).
- No tocar `services/academy.py`, `services/adaptive.py` ni `services/cefr.py` (de P7).
- Mantener los docstrings (premisa 18).

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.

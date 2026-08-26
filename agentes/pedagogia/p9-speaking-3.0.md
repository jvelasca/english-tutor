# V1.15 — Speaking 3.0 (medición longitudinal sobre el Student Model)

## Rol
Subagente full-stack que convierte la destreza `speaking` de un *scorer por intento* en una
señal de **competencia longitudinal**, sobre el mismo Student Model unificado de V1.12. Igual
que `listening_diagnostic` mide listening por sub-destreza/tema/tendencia/reincidencia,
`speaking_diagnostic` mide speaking por criterio de rúbrica y en el tiempo. Filosofía congelada:
**el LLM extrae evidencia; el scorer determinista calcula el score; el diagnóstico determinista
decide qué está débil.**

## Contexto

V1.12 dejó un rubric de speaking de 6 criterios (`task_achievement`, `grammatical_control`,
`lexical_resource`, `fluency`, `pronunciation`, `coherence`) con dos flujos:

- `score_speaking(heard, expected, duration)` — read-aloud determinista.
- `scores_from_evidence(evidence, heard, duration)` — tarea libre con evidencia del LLM.

Cada intento registra evidencia versionada en `academy_evidence` (una fila por criterio observable
con `item_id` = criterio, `result` = score 0..1, `source="speaking"`, más una fila `overall`). El
Student Model (`build_skill_profile`) agrega todo eso en **una** entrada `speaking` (score/confidence/
evidence_count) sin vista por criterio ni tendencia temporal. `listening` sí tiene esa vista
(`listening_diagnostic` + subskills puenteados en `_annotated_profile`). Speaking no.

El currículum (`services/curriculum.py::SUBSKILLS["speaking"]`) ya reconoce `interaction`,
`turn_taking`, `self_correction`, `intelligibility`, `lexical_retrieval` como sub-destrezas de
speaking, pero el rubric aún no puntúa `interaction` como criterio.

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). Este cambio
**no toca el contrato HTTP de scoring existente**: añade un diagnóstico y una dimensión nueva.

## Objetivo

Medir longitudinalmente los criterios de speaking (`fluency`/`grammar`/`lexical`/`pronunciation`/
`coherence`/`interaction`) y exponerlo como parte del Student Model, con `interaction` como séptimo
criterio del rubric.

## Descomposición (un commit `feat:` por subagente, verificado en verde)

### S1 — `speaking_diagnostic` longitudinal (backend)
- **`services/speaking.py`** (puro, sin FastAPI ni red):
  - `speaking_diagnostic(evidence_rows) -> dict`: agrupa las filas de evidencia de speaking
    (`skill="speaking"`) por `item_id` (criterio). Por criterio calcula `attempts`, `mean`
    (media de `result`), `min`, `max` y tendencia reciente vs previa (sobre `result`, no sobre
    `correct`). Determina `weak` (criterios con `attempts == 0` o `mean < 0.6` con `attempts >= 3`)
    y `recommendation`. Devuelve también `attempts` y `overall_mean` globales, `trend` global y
    `rubric_version`.
  - Helper puro `_mean_trend(rows, window)` (análogo a `recent_trend` de listening pero para
    medias de floats), y `SPEAKING_WEAK_THRESHOLD = 0.6`, `SPEAKING_MIN_ATTEMPTS = 3`.
- **`schemas/academy.py`**: `SpeakingCriterionOut`, `SpeakingTrend`, `SpeakingDiagnostic`.
- **`domain/academy.py`**: `get_speaking_diagnostic(user_id)` (filtra `list_evidence` por
  `skill="speaking"` y delega en `speaking_diagnostic`); puente en `_annotated_profile`: la entrada
  `speaking` del perfil recibe `subskills` = `speaking_diagnostic(...)["criteria"]` (mismo patrón
  que el puente de listening).
- **`routers/academy.py`**: `GET /api/academy/speaking/diagnostic` (response_model
  `SpeakingDiagnostic`).
- **Tests**: `test_speaking.py` (diagnóstico puro: agrupación por criterio, media, tendencia,
  weak, sin filas → todo vacío/debil) + endpoint del diagnóstico.

### S2 — criterio `interaction` (rubric de 7 dimensiones)
- **`services/speaking.py`**: `SPEAKING_CRITERIA` pasa a incluir `interaction` (7 criterios);
  `CRITERION_WEIGHTS` se re-equilibran sumando 1; `score_speaking` (read-aloud) deja `interaction`
  **no observada** (no hay turno conversacional); `scores_from_evidence` la calcula desde la
  evidencia del LLM (`interaction` 0..1) y la marca observada cuando el LLM la devuelve.
  `evidence_from_speaking` registra `interaction` como criterio observable.
- **`services/speaking_llm.py`**: `interaction` pasa a `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` y el
  prompt instruye extraerla; `parse_speaking_evidence` la parsea con `_parse_float_field`.
- **Tests**: actualizar los asserts `len(criteria) == 6` → `7` y `>= 7` → `>= 8`; caso de
  `interaction` observada/ no observada.

### S3 — frontend (panel de speaking)
- Tipos en `types/api.ts`, api `speakingDiagnostic`, y vista en `LearningProfile.tsx` o panel
  dedicado con el desglose por criterio (mean, tendencia, weak). Responsive con tokens.

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes.
- `speaking_diagnostic` es determinista y sin LLM/red.
- El Student Model expone las sub-destrezas de speaking (criterios) como ya lo hace listening.
- `interaction` queda observada solo cuando hay señal (read-aloud: no observada).

## Restricciones
- No tocar `services/academy.py`, `services/adaptive.py`, `services/cefr.py` ni el motor de mastery.
- Mantener la filosofía "LLM extrae / scorer determinista calcula" (premisa 12) y los docstrings
  (premisa 18).
- Tests rápidos y deterministas (sin red ni modelos).

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde, con commits
  `feat:` separados por subagente (S1, S2, S3).

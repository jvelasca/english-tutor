# V2.5 (2/4) — C2: Escenarios de speaking C2

## Rol
Backend (contenido de speaking). Autor del **contenido de escenarios comunicativos C2**. No tocas
frontend ni el scoring.

## Objetivo
Cerrar el hueco detectado por la auditoría V2.4: el banco de speaking (`speaking_scenarios.json`)
tiene 20 escenarios con `cefr_target` distribuido **A1=1, A2=6, B1=7, B2=5, C1=1 y C2=0**.
Debes añadir **escenarios C2** y actualizar métrica/tests.

## Contexto

### Dónde vive el contenido
- `backend/curriculum/speaking_scenarios.json` — objeto `{ "version": "1.0.0", "scenarios": [...] }`.
  Cada escenario: `id`, `title`, `category`, `cefr_target`, `task_type`, `communicative_objective`,
  `prompt`, `metrics` (lista), `difficulty_vector` (dict).
- `services/speaking_scenarios.py` → `SpeakingScenario` (Pydantic): `cefr_target: str = "B1"`,
  `task_type: str = "role_play"`, `metrics: list[str]`, `difficulty_vector: dict`.
  `list_scenarios()` devuelve todos; `validate_scenarios()` comprueba `task_type` ∈ `TASK_TYPES`
  (de `services/speaking`) y `metrics` ∈ `SCENARIO_METRICS`.
- `SCENARIO_METRICS = ("task_completion", "interaction", "fluency", "repair", "turn_taking")`.
- `SPEAKING_SCENARIOS_VERSION = "2.0.0"` en `services/curriculum.py` (atención: está desalineado del
  JSON `1.0.0`; al bump, alinea ambos).

### Restricción clave del dominio
`validate_scenarios()` exige `cefr_target` ∈ `CEFR_ORDER` (`("A1","A2","B1","B2","C1","C2")`), así
que `cefr_target: "C2"` ya es válido (C2 está en `CEFR_ORDER`). No hay que tocar `CEFR_ORDER`.

### Tests que hoy afirman el hueco (a invertir)
`backend/tests/test_curriculum_coverage.py`:
- `test_bank_intersection_exposes_speaking_gap_c2` afirma `banks["C2"]["speaking"] == 0`. Al añadir
  C2, invierte el test para afirmar `> 0`.

### Métrica única (anti-drift)
`content_stats()` calcula `total_validated_learning_items = len(QUESTION_BANK) + len(list_scenarios())`
dinámicamente, pero `README.md`/`CHANGELOG.md`/`PLAN.md` citan **143** y **"20 speaking"**. Al añadir
escenarios, actualiza esas cifras (y las de listening si la subida la comparte con el briefing C1).

## Tarea detallada

1. **Contenido** — añade al array `scenarios` de `speaking_scenarios.json` **5–6 escenarios C2**
   (`cefr_target: "C2"`), con `communicative_objective` de nivel C2 (negociación de matices, persuasión
   sutil, defensa de postura con evidencia, mediación de conflicto complejo, presentación académica,
   conversación sobre temas abstractos). `metrics` dentro de `SCENARIO_METRICS` y `difficulty_vector`
   coherente con el nivel. Reutiliza `id`/`title`/`category` siguiendo el estilo de los existentes.
2. **Bump de versión (alineando la discrepancia)**: `speaking_scenarios.json` → `version` a `2.0.0`
   y `SPEAKING_SCENARIOS_VERSION = "3.0.0"` en `services/curriculum.py` (el JSON quedó en `1.0.0` y la
   constante en `2.0.0`; sube uno cada uno y deja claro en el commit la alineación).
3. **Tests**: invierte `test_bank_intersection_exposes_speaking_gap_c2` (C2 ahora > 0). Añade un test
   de invariante: `validate_scenarios()` vacío y hay ≥1 escenario por `cefr_target` para A1..C2.
   `services/speaking_scenarios.py` ya tiene `test_speaking_scenarios.py`; amplíalo si procede.
4. **Docs**: actualiza la cifra `143` y `"20 speaking"` en `README.md`/`CHANGELOG.md`/`PLAN.md` y la
   tabla de `docs/CURRICULUM_COVERAGE.md` (speaking deja de ser hueco en C2).

## Criterios de aceptación
- `python -m scripts.curriculum_coverage` sale 0 y `bank_count` de speaking C2 > 0.
- `pytest tests/ -q` verde + `ruff check .` limpio.
- `check_release_consistency` OK (versión sigue `2.4.0`).

## Restricciones
- No toques frontend, ni el scoring (`services/speaking.py`), ni `services/course.py`.
- Los escenarios son **contenido** (JSON); no cifres lógica en Python más allá del bump de versión.
- Mantén docstrings si tocas Python.
- Un único commit `feat: speaking C2 (escenarios 20→25, cefr_target C2)`. No hagas push.

## Salida esperada
Nº de escenarios C2 añadidos, su `communicative_objective` resumido, diff de versión, tests
actualizados y la nueva cifra de `total_validated_learning_items` para docs.

# V2.5 (4/4) — C4: Integrar listening/speaking en cada unidad (wiring curso↔bancos)

## Rol
Backend (Course Engine + servicio de cobertura). Conectas el **contenido del curso** (JSON de nivel)
con los **bancos de destrezas** (corpus de listening y escenarios de speaking) mediante referencias
explícitas por ID, y haces que la medición lo refleje. **Sin UI en este incremento.**

## Objetivo
Cerrar el hueco arquitectónico de la auditoría V2.4: hay **dos fuentes de contenido desconectadas** —
el curso secuencial (que alimenta Course Engine/Mastery Gates) y los bancos de destrezas (100 ítems de
listening + 20 escenarios de speaking). Hoy `unit_sections()` cuenta listening como 0–5 checks por
unidad **aunque** existan 100 ítems en el banco. Debes cablearlos: cada unidad con listening/speaking
debe **referenciar** ítems del banco, y el conteo debe reflejarlo.

## Contexto

### Cómo se cuenta hoy
- `services/course.py`:
  - `UNIT_SECTIONS = ("vocabulary", "grammar", "listening", "speaking", "interaction", "review",
    "assessment")`.
  - `unit_sections(unit)` agrega por sección: `listening` = nº de objetivos con `skill == "listening"`
    + nº de checks con `skill == "listening"`; `speaking` = objetivos con `skill == "speaking"` +
    checks (hoy 0 checks, porque speaking es destreza de performance).
- `services/curriculum_coverage.py` (V2.4):
  - `coverage_sections(level)` agrega `unit_sections` a nivel de curso; `bank_intersection()` cruza
    `listening_corpus.json` (por `level`) y `speaking_scenarios.json` (por `cefr_target`) contra
    A1..C2, exponiendo `bank_count` (lo que existe en el banco) junto a `count` (lo que el curso usa).

### Estructura de un objetivo (nivel JSON)
`backend/curriculum/<level>.json` → `modules[] → units[] → lessons[] → objectives[]`. Cada objetivo:
`id`, `can_do`, `title`, `skills[]`, `subskills[]`, `concepts[]`, `vocabulary[]`, `activities[]`,
`checks[]`. Los checks de listening son `{"id", "skill": "listening", "prompt", "options", "correct_index"}`.

### Modelos Pydantic
`services/curriculum.py` define `Objective` (y `Level`/`Module`/`Unit`/`Lesson`). **Antes de tocar
nada, lee el modelo `Objective` exacto** para conocer sus campos y defaults (regla anti-alucinación).
Los ítems del banco de listening tienen `id` (`c001`–…), `level`, `audio_id`; los escenarios tienen
`id` (`s01`–…), `cefr_target`.

### Bancos
- Listening: `services/listening.py::QUESTION_BANK` (dicts con `id` + `level`). Acceso público por ID.
- Speaking: `services/speaking_scenarios.py::list_scenarios()` (Pydantic `SpeakingScenario`, `id` +
  `cefr_target`).

## Tarea detallada

1. **Modelo** — añade a `Objective` dos campos opcionales retrocompatibles:
   - `listening_items: list[str] = []` (IDs de ítems del banco de listening, p. ej. `["c041", "c042"]`).
   - `scenario_ids: list[str] = []` (IDs de escenarios de speaking, p. ej. `["s01"]`).
   (Si el objetivo es de otra destreza, ambos quedan vacíos. No rompes niveles existentes.)

2. **Conteo** — en `services/course.py::unit_sections` (y cualquier helper que agregue listening/
   speaking), suma `len(listening_items)` a la sección `listening` y `len(scenario_ids)` a `speaking`.
   En `services/curriculum_coverage.py::coverage_sections`, refleja lo mismo (lee su código actual y
   mantén la forma de salida). El objetivo pedagógico: la sección deja de ser `empty` cuando hay
   referencias reales al banco, no solo cuando hay un `skill` declarado.

3. **Contenido (wiring)** — en los JSON de nivel (empieza por `a1.json` como implementación de
   referencia y repite en el resto):
   - A cada objetivo con `skill == "listening"`, asígnale `listening_items` con 2–4 IDs del banco
     cuyo `level` coincida con el nivel del curso (p. ej. en `a1.json` usa ítems `level == "A1"`).
   - A cada objetivo con `skill == "speaking"`, asígnale `scenario_ids` con 1 escenario cuyo
     `cefr_target` coincida con el nivel.
   - Verifica que cada ID referenciado existe (listening en `QUESTION_BANK`, speaking en
     `list_scenarios()`); no dejes referencias rotas.

4. **Validación** — añade en `services/curriculum.py::validate_level` (o un nuevo validador) un chequeo
   de integridad: todo `listening_items` referencia un ID existente y su `level` coincide con el nivel;
   todo `scenario_ids` referencia un `id` existente y su `cefr_target` coincide. Devuelve la lista de
   issues (formato actual de `validate_level`) sin romper lo existente.

5. **Tests** — en `backend/tests/test_curriculum_coverage.py` (o nuevo `test_bank_wiring.py`):
   - `unit_sections` suma `listening_items`/`scenario_ids`.
   - El validador detecta una referencia rota y un desfase de nivel.
   - Invariante: tras el wiring, ningún nivel con curso tiene listening/speaking `empty` (salvo que
     el banco aún no tenga contenido para ese nivel — coordina con los briefings C1/C2).
   - `validate_level` sigue vacío para los 6 niveles con wiring válido.

6. **Docs** — actualiza `docs/CURRICULUM_COVERAGE.md` (listening/speaking pasan de "desconectado" a
   "cableado por unidad") y `docs/ARQUITECTURA.md` si describes la nueva relación curso↔bancos.

## Criterios de aceptación
- `python -m scripts.curriculum_coverage` muestra `count` de listening/speaking crecido (gap
  `count` vs `bank_count` reducido) y `--strict` sale 0 (o solo falla donde el banco aún no tiene C1/C2,
  pendiente de los briefings C1/C2).
- `pytest tests/ -q` verde + `ruff check .` limpio.
- `check_release_consistency` OK (sin bump; sigue `2.4.0`).

## Restricciones
- **Sin UI** en este incremento: no toques `frontend/`. La consumición visual de los ítems referenciados
  (mostrar el listening del banco dentro de la unidad) es un incremento posterior.
- No cambies la firma de `unit_sections` ni rompas `CourseMapOut`/endpoints existentes.
- Añade los campos con defaults para no romper niveles existentes; `load_all_levels()` debe seguir
  parseando los 6 niveles.
- El wiring es **contenido** (referencias por ID en JSON) + conteo + validación. No dupliques los ítems
  del banco dentro del JSON de nivel (solo referencias).
- Un único commit `feat: wiring curso↔bancos (listening_items + scenario_ids por objetivo)`. No push.

## Salida esperada
Diff del modelo (`Objective` + campos), del conteo (`unit_sections`/`coverage_sections`), del
validador, nº de objetivos cableados por nivel y el nuevo desglose listening/speaking en el reporte.

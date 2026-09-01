# V2.5 (3/4) — C3: Integrar interaction en A1/A2/B2/C1/C2

## Rol
Backend (contenido curricular). Autor del **contenido de interaction** en los niveles que hoy no lo
declaran. No tocas frontend ni el scoring.

## Objetivo
Cerrar el hueco detectado por la auditoría V2.4: la sección **interaction** está poblada solo en B1
(1/7 niveles). Debes declarar interacción en **A1, A2, B2, C1 y C2** añadiendo sub-destrezas de
interacción a objetivos existentes (o nuevos) en los JSON de nivel, de modo que `unit_sections`
cuente `interaction` en esos niveles.

## Contexto

### Cómo se cuenta interaction
`services/course.py`:
- `_INTERACTION_SUBSKILLS: tuple[str, ...] = ("interaction", "turn_taking", "repair")`.
- En `unit_sections(...)`, `counts["interaction"]` suma los objetivos cuya lista `subskills`
  contiene alguna de `_INTERACTION_SUBSKILLS`.

### Cómo se valida un subskill
`services/curriculum.py`:
- `SUBSKILLS["speaking"] = ("pronunciation", "fluency", "grammar", "vocabulary", "interaction",
  "coherence", "intelligibility", "lexical_retrieval", "self_correction", "turn_taking")`.
- `validate_level()` exige que cada subskill pertenezca a `SUBSKILLS` de una destreza **declarada**
  por el objetivo. Por tanto, para declarar `interaction`/`turn_taking`, el objetivo debe tener
  `speaking` en `skills`.
- **Ojo**: `"repair"` NO está en `SUBSKILLS` (solo en `_INTERACTION_SUBSKILLS`). NO uses `"repair"`
  como subskill salvo que además lo añadas a `SUBSKILLS["speaking"]` (no es necesario para esta tarea;
  usa `interaction` y `turn_taking`).

### Estructura de un objetivo (nivel JSON)
`backend/curriculum/<level>.json` → `modules[] → units[] → lessons[] → objectives[]`. Cada objetivo:
`id`, `can_do`, `title`, `skills[]`, `subskills[]` (opcional), `concepts[]`, `vocabulary[]`,
`activities[]`, `checks[]`. Añadir `subskills: ["interaction", "turn_taking"]` a objetivos que ya
declaran `speaking` es el camino de menor fricción (no requiere nuevo check: la sección interaction
cuenta por subskill, no por check).

### Estado actual (auditoría V2.4)
- `subskills` con interacción hoy: solo B1 (`interaction: 1`, `turn_taking: 1`). A1/A2/B2/C1/C2 no
  declaran interacción (la sección interaction es `empty` en esos niveles).
- `docs/CURRICULUM_COVERAGE.md` documenta "interaction 1/7".

### Tests que hoy afirman el estado
No hay un test que afirme "interaction vacío", pero `test_curriculum_coverage.py` valida la forma del
reporte. Añade un invariante nuevo: tras el cambio, los niveles A1/A2/B2/C1/C2 tienen `interaction`
con `count > 0` en `coverage_sections` (o `status != empty` en `level_coverage`).

## Tarea detallada

1. **Contenido** — en `a1.json`, `a2.json`, `b2.json`, `c1.json`, `c2.json`, añade
   `subskills: ["interaction", "turn_taking"]` a objetivos que ya declaren `speaking` (elige al menos
   1 objetivo con speaking por unidad donde tenga sentido comunicativo). Asegúrate de que cada objetivo
   modificado tiene `speaking` en `skills` (si no, añádelo) y de que no repites ids.
2. **Validación**: `python -c "from services.curriculum import load_all_levels, validate_level; [print(validate_level(lv)) for lv in load_all_levels()]"` → listas vacías para los 6 niveles.
3. **Tests** — añade a `backend/tests/test_curriculum_coverage.py` un test que afirme que la sección
   `interaction` deja de estar `empty` en A1/A2/B2/C1/C2 (mira `level_coverage(level_id)`).
4. **Docs** — actualiza `docs/CURRICULUM_COVERAGE.md`: la fila Interaction pasa de 1/7 a 6/7
   (solo Pre-A1 queda vacío, que es banda sin curso). Recalcula la cobertura total con
   `python -m scripts.curriculum_coverage` y actualiza el % si cambia.

## Criterios de aceptación
- `python -m scripts.curriculum_coverage` muestra `interaction` con `count > 0` en A1/A2/B2/C1/C2.
- `pytest tests/ -q` verde + `ruff check .` limpio.
- `check_release_consistency` OK (sin bump de versión; sigue `2.4.0`).

## Restricciones
- No toques frontend, ni `services/course.py`, ni el scoring de speaking.
- No cambies la plantilla `UNIT_SECTIONS` ni `_INTERACTION_SUBSKILLS` (ya son correctos).
- El cambio es **contenido** (JSON de nivel) + un test. No reescribas lógica.
- Un único commit `feat: interaction A1/A2/B2/C1/C2 (subskills interaction+turn_taking)`. No push.

## Salida esperada
Lista de objetivos modificados por nivel (id + subskills añadidos), resultado de `validate_level`
(esperado vacío) y el nuevo desglose de interaction en el reporte de cobertura.

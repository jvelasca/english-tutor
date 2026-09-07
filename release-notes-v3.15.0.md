# v3.15.0 — Profundidad avanzada C1/C2 (densidad, taxonomía avanzada y banco grammar C2 normalizado)

**El candidato P0 "C1/C2 depth" (auditado abierto 2026-09-05) se cierra con contenido y motor honestos: C1 y C2 a 20 objetivos, la capa avanzada visible a `subskill_breadth` y ningún banco de grammar corto real.**

## Qué cambia

La iteración ataca los tres deltas medidos en la auditoría previa (banco grammar C2 = 8 ítems < 12, volumen 14/20 objetivos en C1/C2, taxonomía avanzada inexistente en `SUBSKILLS` e invisible a `subskill_breadth`):

- **Volumen: C1 y C2 pasan de 14 a 20 objetivos.** +6 objetivos por nivel con evidencia completa (checks MC + 5 activities con las fases del loop): C1 amplía `c1-m02-u01` (matiz e idioms de registro en `l01`, argumentación en `l02`) y `c1-m03-u01-l01` (concesión y discourse markers, +3); C2 amplía `c2-m02-u01-l01` "Register shifts" (+2 sobre gramática formal/informal y cohesion discursiva) y estrena la lección `c2-m02-u01-l03` (+4: elipsis, gramática formal, cohesion discursiva). Los módulos Final (`c1-m04`, `c2-m03`) se mantienen intactos. Activities 68→98 en ambos niveles; checks C1 45→63 y C2 38→57.
- **Taxonomía avanzada visible (`backend/services/curriculum.py`).** `SUBSKILLS` incorpora la capa C1/C2 —`register`, `pragmatics`, `discourse`, `nuance`, `argumentation`— en speaking, listening, writing, grammar, reading y vocabulary (pronunciation intacta; cada tupla en orden alfabético). Los objetivos C1/C2 cuyo contenido ya entrenaba registro/discurso/matiz/argumentación se re-etiquetan sin inflado (C1: 3→16 objetivos con subskill avanzada; C2: 7→20); A1–B2 no se tocan.
- **Banco grammar C2 normalizado a 15 ítems (11 MC + 4 CP en 3 temas).** C2 deja de ser el único banco corto real del sistema y `practice_depth` real deja de leer `low`. La regla R7 ("muestra pequeña ≠ competencia") no se vacía: se conserva verificada con un **banco corto sintético** construido en los propios tests (helper `_synthetic_short_bank`), con ítems reales del pool de C2 por debajo de `QUIZ_SHORT_BANK`.

## Técnica

- Backend (`3.14.0 → 3.15.0`, fuente única `backend/config.py`):
  - Currículo: `c1.json` y `c2.json` con +6 objetivos por nivel (evidencia completa, sin renumerar ids ni tocar a1/a2/b1/b2). Sin ítems `controlled_production` nuevos: el banco MC crece hasta completar 15 (11 MC + 4 CP ya existentes `c2-cp-01..04`).
  - `services/curriculum.py`: solo `SUBSKILLS` ampliado (capa avanzada); `validate_level` vacío en los 6 niveles.
  - `services/quiz_routes.py` y `schemas/grammar_routes.py`: textos "C2 = 4" retirados (referencias dinámicas a `QUIZ_SHORT_BANK`).
  - Tests: `test_curriculum_quality.py` (snapshot V2.6 reformulado: `test_depth_c1_c2_reach_deep_target_after_v315`), `test_pedagogical_invariants.py` y `test_grammar_routes.py` (R7 y mecánica de banco corto sobre datos sintéticos; conteos C2 actualizados 8 → 15).
- Sin cambios de frontend, launcher ni CONSTITUCIÓN pedagógica (iteración de contenido, no normativa).

## Tests

- Backend: **1293 pytest en verde**; `ruff check .` limpio.
- CLI de calidad: `python -m scripts.curriculum_coverage --strict --quality` **exit 0** — `depth(C1) = 93.1`, `depth(C2) = 92.5` (A1 89.4, A2 81.9, B1 89.0, B2 81.0; overall 96.2), unit coverage 100 % (31/31) y Unit Learning Loop 100 % en las 9 fases, sin huecos `empty`.
- Frontend: **382 vitest en verde** y build de producción OK (sin cambios).

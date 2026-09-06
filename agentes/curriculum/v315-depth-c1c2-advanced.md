# V3.15 — v315-depth-c1c2-advanced: profundidad avanzada C1/C2 (taxonomía + volumen + banco grammar C2)

## Rol
Implementador **backend-curriculum + servicios + tests**. Cierras el frente abierto del candidato
"🔴 P0 — C1/C2 depth" (auditado 2026-09-05 como ABIERTO). NO haces frontend de producto, NO haces
bump de versión ni docs de release (eso lo cierra el gerente tras tu informe).

## Auditoría previa (deltas medibles, fuente de la verdad)
Medido en vivo (2026-09-05, mismo árbol de trabajo):

| Nivel | Módulos | Unidades | Objetivos | Depth | breadth (distintos/posibles) | Banco grammar MC+CP |
|---|---|---|---|---|---|---|
| C1 | 4 | 4 | 14 | 81.8 | 12/51 (0.235) | 18 (12 MC + 6 CP) |
| C2 | 3 | 3 | 14 | 81.7 | 11/51 (0.216) | **8 (4 MC + 4 CP)** |

Deltas a cerrar:
1. **Banco grammar C2 < 12** (hoy 8, único banco corto del sistema; `QUIZ_SHORT_BANK=12` en
   `backend/services/quiz_routes.py`, evidencia `practice_depth == "low"`). → llevar a **≥12**.
2. **Volumen**: C1 y C2 están en 14/20 (`OBJECTIVE_VOLUME_TARGET=20.0`). → subir ambos a **20**.
3. **Taxonomía avanzada inexistente**: `SUBSKILLS` (backend/services/curriculum.py) no tiene
   `pragmatics`/`discourse`/`nuance`/`argumentation`; `register` solo existe en writing/vocabulary.
   El contenido C1/C2 de registro/discurso/matiz/argumentación existe por temas pero es invisible a
   `subskill_breadth`. → añadir capa avanzada + etiquetar objetivos C1/C2 (y re-etiquetar los que ya
   entrenan esas competencias), para que breadth suba y el dashboard refleje la densidad real.

## Contexto técnico (lee antes de tocar nada)

- `docs/UNIT_ARCHITECTURE.md` — norma de 7 secciones + 9 fases del loop + evidencia por sección.
- `backend/services/curriculum.py` — `SUBSKILLS` (dict skill → tuple subskills, líneas ~58–128),
  `SKILLS`, `LISTENING_FOCUS_BY_LEVEL`. La validación (mismo fichero, ~488–494) exige que cada
  `subskill` de un objetivo pertenezca a la tupla de ALGUNA de sus `skills`.
- `backend/services/curriculum_coverage.py` — `depth_score()` (líneas ~398–472) y pesos
  `DEPTH_WEIGHTS` (densidad .20 / volumen .35 / secciones .35 / breadth .10). NO los cambies.
  - `objective_density` = min(objetivos/unidades / 3, 1) → C1/C2 ya saturado (4.67/unit).
  - `objective_volume` = min(objetivos / 20, 1) → la palanca principal (+10.5 pts con +6 objetivos).
  - `subskill_breadth` = subskills distintos declarados / subskills posibles de las destrezas
    declaradas del nivel. **Posible** se calcula sobre las destrezas declaradas por los objetivos
    del nivel; al ampliar `SUBSKILLS`, todos los niveles que declaren esa destreza cambian su
    denominador. Asume ese movimiento; el test-snapshot comparativo se actualiza (abajo).
- Plantillas de referencia de autoría en el propio árbol: objetivos de C1/C2 existentes en
  `backend/curriculum/c1.json` y `c2.json` (estructura completa: `id`, `skill`/`skills` v3.14,
  `subskills`, `checks` con kind mc + distractores, `activities` con fases del loop y wiring de
  `listening_items`/`scenario_ids` donde corresponda).
- Registro cross-skill (v3.14): `backend/services/cross_skill.py` bindings `PRODUCTION_BINDINGS_BY_LEVEL`
  y registro de estructuras por objetivo con check grammar MC. Si añades **objetivos nuevos con
  skill grammar**, aparecerán filas nuevas en la matriz (automático). Si añades **CP nuevos**
  (`c2-cp-0x`), debes sincronizar bindings y tests cross-skill: PREFIERE MC dentro de objetivos
  existentes o nuevos ANTES que CP nuevos, salvo que la sincronización sea trivial.
- C2 corpus listening disponible: ítems `c2…` (ver banco en curriculum.json); C2 scenarios:
  `persuasion`, `conflict_mediation`, `academic_defence`, `abstract_conversation`,
  `stakes_negotiation`, `diplomatic_talk` (patrón V2.7 de v27-depth-c2.md).
- Tests que fijan los conteos actuales (SE ROMPEN a propósito; actualízalos de forma honesta):
  - `backend/tests/test_curriculum_quality.py:176–184` `test_depth_flags_c1_c2_as_shallower_than_a1`:
    snapshot que exige `depth(c1)`, `depth(c2) < depth(a1)` (89.5). Su propio docstring dice que se
    retira "cuando V2.7 amplíe C1/C2". Con C1/C2 ~90+ deja de tener sentido → **reformúlalo o
    elimínalo** documentando por qué (el test-snapshot cumplió su ciclo).
  - `backend/tests/test_pedagogical_invariants.py:63–101`: `test_four_c2_questions_cannot_prove_c2`
    y `test_short_bank_coverage_does_not_lift_to_medium` fijan `len(C2) < QUIZ_SHORT_BANK` y
    `practice_depth == "low"` usando C2 como único banco corto real. Si C2 se normaliza a ≥12, el
    invariante R7 ("muestra pequeña ≠ competencia") se queda sin sujeto real → **re-apunta ambos
    tests a un banco grammar sintético corto** (construido en el propio test), de modo que la regla
    R7 siga verificada con datos artificiales y no se vacíe.
  - `backend/tests/test_grammar_routes.py:177–199 y 207–221`: supuesto `C2 = 4 MC + 4 CP = 8`.
    Actualízalos al nuevo conteo real (verifica con el CLI antes de fijar cifras).
  - Texto desactualizado que menciona "C2 = 4": `backend/services/quiz_routes.py` (~47 y ~170) y
    `backend/schemas/grammar_routes.py` (~73/99). Ponlos al día con el conteo real o hazlos
    dinámicos si es trivial.
- Dashboard docs manual `docs/CURRICULUM_COVERAGE.md`: el gerente lo regenerará al cierre; NO lo
  toques salvo que el CLI te lo pida (regenerar el informe con la misma herramienta).

## Tarea

### Fase A — Taxonomía avanzada (`backend/services/curriculum.py`, solo `SUBSKILLS`)
Añade tokens de la capa avanzada a las tuplas donde sean competencia real. Set mínimo coherente
(reutiliza los ids existentes cuando ya existan en otra destreza):
- `speaking`: añade `register`, `pragmatics`, `discourse`, `nuance`, `argumentation`.
- `listening`: añade `register`, `discourse`, `pragmatics`, `nuance`.
- `writing`: añade `pragmatics`, `discourse`, `argumentation`, `nuance` (ya tiene register/cohesion).
- `grammar`: añade `register`, `discourse`.
- `reading`: añade `register`, `pragmatics`, `discourse`, `nuance`.
- `vocabulary`: añade `discourse`, `nuance` (ya tiene register/idioms/collocations).
- `pronunciation`: sin cambios.
Mantén el orden alfabético de cada tupla. NO toques nada más del servicio. Verifica que
`validate_level` sigue pasando en los 6 niveles (el etiquetado de la fase B debe ser coherente).

### Fase B — Etiquetado avanzado en objetivos EXISTENTES de C1/C2
Re-etiqueta objetivos cuyo contenido ya entrena registro/discurso/matiz/argumentación para que
`subskill_breadth` los vea. Directrices:
- `subskills` nuevos SOLO donde el contenido del objetivo los justifique (competencias reales, no
  inflado). Regla del proyecto: cero objetivos/subskills artificiales.
- En objetivos con `listening`, conserva siempre las subskills del foco C1/C2
  (`inference`, `attitude`, `speaker_intention`) además de los tokens nuevos.
- Candidatos claros (revisa su contenido antes de etiquetar):
  - C2 `c2-m02-u01` ("Register and cultural nuance"): objetivos de speaking con
    `interaction/turn_taking/fluency` → +`register`, `discourse`, `pragmatics`; objetivos de
    listening `inference/attitude` → +`register`/`discourse`/`nuance` según contenido; el de
    writing l02-o04 → +`discourse`/`pragmatics` según contenido.
  - C1 `c1-m03-u01` ("Arguing and hedging"): speaking/vocabulary → +`argumentation`, `pragmatics`
    (hedging es pragmático); grammar o04 → +`register`, `discourse`.
  - C1 `c1-m02-u01` y C2 `c2-m01-u01` (idiomas/rhetoric): +`register`, `discourse`, `nuance` en
    los objetivos que lo justifiquen.
  - C2 `c2-m03-u01-l01-o01` (final, skills múltiples) y C1 `c1-m04-u01-l01-o01`: `discourse`/
    `nuance` si el check de grammar lo permite (revisa antes).
- No etiquetes objetivos de niveles bajos (A1–B2) con la capa avanzada; su breadth puede bajar
  unos décimas por el denominador nuevo — aceptado y se refleja en el informe.

### Fase C — Volumen: +6 objetivos por nivel (C1 y C2 → 20)
Añade objetivos NUEVOS con evidencia completa (5 activities con fases, checks con MC cuando la
destreza es auto-scorable, wiring de listening/scenario donde proceda). Requisitos duros:
- Cada **unidad** existente debe conservar sus 7 secciones y las 9 fases del loop (no elimines
  contenido; solo añades). Si un objetivo nuevo entra en una lección/unidad que ya tiene todo,
  no se degrada nada. Verifícalo con el CLI `--strict --quality` (debe seguir exit 0).
- Los objetivos nuevos deben entrenar competencias avanzadas reales de C1/C2, no duplicados.
  Orientaciones temáticas (puedes adaptar si el contenido existente ya lo cubre):
  - C1 (+6): en `c1-m02-u01` lección "Idioms in context" añade objetivos de matiz/idiom register
    (o02…) y en `c1-m02-u01-l02`/`c1-m03-u01` amplía argumentación/hedging con discourse
    markers y concesión; evita tocar el módulo Final `c1-m04`.
  - C2 (+6): amplía `c2-m02-u01-l01` "Register shifts" (hoy 1 objetivo; añade o02/o03 sobre
    formal/informal grammar y discourse cohesion) y añade en `c2-m02-u01` contenido de nuance
    cultural/humor si procede; puedes añadir una lección nueva si el patrón lo permite
    (`c2-m02-u01-l03`, ids `c2-m02-u01-l03-o0x`). Mantén `c2-m03` (Final) con su único objetivo.
- Banco grammar C2: el objetivo es **≥12 items MC+CP**. Calcula con el CLI el conteo MC grammar
  tras tus añadidos; si falta, añade checks MC `skill: grammar` a objetivos grammar existentes o
  nuevos (registro/formal vs informal, ellipsis/parallelism, cleft, nominalización, adverbios
  disjuntos) hasta alcanzar ≥12. Preferible repartirlos (no todos en un mismo objetivo).
- C1 no necesita ampliar banco grammar (18 ya); si añades objetivos grammar, verifica que el total
  MC+CP sube, no baja.
- Regla de ids: añade únicos siguiendo la convención (`c1-m02-u01-l01-o02`, …). No renumeres los
  existentes. No toques `a1.json`/`a2.json`/`b1.json`/`b2.json`.
- Registro cross-skill: si algún objetivo nuevo declara `skill: grammar` con MC, la estructura
  aparece sola en la matriz de su nivel. Si añades CP nuevos en C2 (solo si es imprescindible),
  sincroniza `PRODUCTION_BINDINGS_BY_LEVEL["c2"]` y revisa `backend/tests/test_cross_skill.py`.

### Fase D — Verificación y cierre de la implementación
1. `python -m scripts.curriculum_coverage --quality` desde `backend/` (con el venv
   `.venv\Scripts\python.exe`): registra antes/después de C1/C2. Objetivo: **depth(C1) y
   depth(C2) ≥ 90** y ambos por encima del resto de niveles (o al menos claramente por encima de
   89.5 de A1). Si no llegas a 90 tras +6 objetivos + etiquetado, repórtalo con el desglose de
   componentes; NO subas objetivos adicionales sin confirmarlo en tu informe.
2. Actualiza los tests listados en "Contexto técnico" (snapshot depth, R7 sintético, conteos C2)
   y los textos "C2 = 4" que queden obsoletos. Ejecuta y deja verde:
   - `pytest tests/ -q` (backend completo, hoy ~1293 tests) — desde `backend/`.
   - `ruff check .` en `backend/` y corrige (88 cols, imports sin usar).
3. Verifica unit coverage/loop: cada unidad A1–C2 con 7/7 y loop 100% (el CLI `--strict` debe dar
   exit 0).
4. NO toques frontend, NO bumpees de versión, NO docs de release/RELEVO/CHANGELOG/PLAN/README.

## Criterios de aceptación
- `SUBSKILLS` ampliado (capa avanzada) sin romper validación de ningún nivel.
- C1 y C2 en **20 objetivos**; depth(C1) ≥ 90 y depth(C2) ≥ 90 con el CLI de calidad.
- Banco grammar C2 **≥ 12** y `practice_depth` de C2 deja de ser `"low"`.
- Cero contenido artificial: cada objetivo nuevo con evidencia completa (checks + activities
  con fases) y cada subskill nuevo justificado por el contenido.
- `validate_level(load_level(x)) == []` para los 6 niveles.
- Suite backend verde (`pytest tests/ -q`) y `ruff check .` sin errores.
- `python -m scripts.curriculum_coverage --strict --quality` exit 0 (sin huecos `empty`).

## Restricciones
- Solo `backend/` (curriculum c1/c2, `services/curriculum.py` SUBSKILLS, textos de
  quiz_routes/schemas, y tests). NO frontend, NO versiones, NO release docs.
- No cambies `DEPTH_WEIGHTS`, `OBJECTIVE_VOLUME_TARGET`, `OBJECTIVE_DENSITY_TARGET`,
  `QUIZ_SHORT_BANK`, ni ids existentes.
- No hagas commits (el gerente cierra la release con su commit).
- Si algo entra en conflicto con un invariante pedagógico normativo de la CONSTITUCION, párate y
  repórtalo en vez de forzarlo.

## Salida esperada
Informe con: (1) tokens añadidos por destreza en `SUBSKILLS`; (2) tabla de objetivos por unidad
C1/C2 antes/después con el desglose de checks/activities; (3) cambios de re-etiquetado (objetivo →
subskills añadidas); (4) `depth_score` y conteo MC+CP grammar C1/C2 antes/después (salida del CLI);
(5) tests actualizados (cita líneas) y resultado de `pytest tests/ -q` + `ruff`; (6) cualquier
decisión que hayas tenido que tomar y que el gerente deba revisar.

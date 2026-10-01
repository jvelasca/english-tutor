# S — Auditoría total de V3.60.0 (Context Engine 4.0: Instance Specification → Parameterized Instance)

> **Posición auditada:** tag anotado **`v3.60.0`** → commit `2c79040`
> («release(v3.60.0): Context Engine 4.0 (Instance Specification ->
> Parameterized Instance)»). Cierre de V3.59: `e721fce`. Delta de la release:
> `e721fce..2c79040` (**18 ficheros, +2854 / −78**). Sobre el tag hay dos commits
> `docs(v3.60.0)` (`34622fe`, `3790907`) que **solo documentan el run de CI** y el
> briefing de auditoría: **ninguna línea de producto cambia** entre ellos.
> **Autor:** auditoría externa (agente con acceso solo al repositorio público).
> **Fecha:** 2026-09-14.

## Alcance

- **Se audita:** el salto de producto V3.59.0 → V3.60.0 sobre
  `backend/services/transfer.py` (banco + `instance_space`, frontera de
  identidad, expansión determinista, dificultad efectiva), `backend/services/difficulty.py`
  (`normalize_delta`/`apply_delta`), `backend/domain/vocabulary.py`
  (`_record_transfer_evidence`), `backend/schemas/vocabulary.py` (contrato),
  `frontend/src/types/api.ts` (espejo) y `backend/tests/test_context_engine_v360.py`.
- **No se audita:** el Student Model, `Planner`, `Sense Engine`, FSRS y el
  scoring léxico (fuera del delta de la release); el banco de contextos anterior
  a V3.59, ya auditado.
- **Relación con el freeze de `docs/BETA_V3.md`:** V3.60 no toca el freeze de
  contenido ni el gate Beta V3.0.

## Método

1. **Instrumentos:** `git diff e721fce..2c79040`, lectura del árbol del tag,
   `pytest backend/tests -q`, `ruff check backend launcher`,
   `scripts/check_release_consistency.py`, `scripts/check_beta_v3.py`,
   `backend/scripts/content_validation.py` y consultas directas al módulo puro
   (`python -c "from services import transfer as t; ..."`).
2. **Muestreo:** las **20 familias** del banco y sus **358 superficies**
   declaradas/generadas; foco en las familias con `difficulty_delta`
   (`debate`/`mediation`/`academic`) y en las de mayor espacio (`shopping`).
3. **Criterios:** `docs/PREMISAS.md` (21: nada de LLM en el camino de la
   evidencia; 8/12: verificar contra el árbol antes de creer a un documento),
   `docs/ARQUITECTURA.md` y `docs/AUDITORIA-V3.md`.

## Evidencia

| Comprobación | Cifra observada | Veredicto |
|---|---|---|
| Banco de familias | 20 | OK |
| Superficies totales (`context_instance_details`) | 358 (16–19 / familia) | OK |
| Mínimo por familia (`CONTEXT_INSTANCE_SPACE_MIN`) | 12 declarado, 16 real | OK |
| Techo (`CONTEXT_INSTANCE_SPACE_MAX`) | 96 declarado, 19 real | OK (inerte hoy) |
| Claves de contrato de `context_for` | 36 (28 de V3.59 intactas) | OK |
| Deltas de dificultad | clamp ±2, envelope 1..5 | OK |
| Backend | `pytest` 2333 passed, 2 skipped; `ruff` limpio | OK |
| Frontend | `tsc` OK, `vitest` 651, build OK | OK |
| Consistencia de release | 3.60.0 | OK |
| CI de la release | run `34814504063` **6/6 documentado** | **no verificable de forma independiente** |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| P1-01 | alta | El espacio paramétrico sigue siendo memorizable: 12–19 combinaciones por familia y una selección predecible (`attempts % len(space)`). El alumno no memoriza una frase, pero puede memorizar el conjunto. | `backend/services/transfer.py:184` (`CONTEXT_INSTANCE_SPACE_MIN = 12`), `:2460` (`context_instance_index`, rotación `% len`) | Espacio generado por muestreo determinista (no producto cartesiano cerrado); subir el espacio real por familia | abierto |
| P1-02 | alta | La equivalencia pedagógica está protegida **estructuralmente** (mismos `context_id`/`cefr`/`skills`/`difficulty_vector`) pero **no demostrada**: el sistema admite que la instancia declare `difficulty_delta`, no valida que la carga declarada corresponda al contenido. | `backend/services/transfer.py:2255` (`difficulty_delta` normalizado desde el `instance_space`), `:2504` (`context_instance_difficulty`) | Validación determinista de contenido (exigir justificación de todo delta no nulo) | abierto |
| P1-03 | alta | El Student Skill State sigue siendo demasiado agregado: `lexical`/`syntax`/`discourse`/`interaction` no distinguen modalidad, así que una capacidad escrita puede influir en la selección de una tarea oral. | `backend/services/learner_skill.py` (dimensiones sin eje de modalidad) | V3.62 — Student Skill State 3.0 (modality → skill → dimension) | aceptado, fuera del alcance de V3.60 |
| P2-01 | media | El recorte del cap deja un **prefijo** del producto cartesiano: el orden de `selection` decide qué combinaciones sobreviven, lo que sesga el espacio al crecer. | `backend/services/transfer.py:2313` (doc explícita del PREFIJO), `:2345` | Muestreo estratificado determinista en lugar de prefijo | abierto (inerte hoy) |
| P2-02 | media | La instancia no queda registrada en el ledger: se sabe `context_id = travel` pero no qué superficie se sirvió. | `backend/repositories/evidence.py:61` (sin columna de instancia) | V3.61 — `context_instance` aditivo en el ledger, sin tocar la identidad | planificado |
| P2-03 | media | La rotación no es adaptativa: la siguiente superficie no depende de éxito/fallo, tipo de error, latencia ni dificultad. | `backend/services/transfer.py:2460` | Motor de política de instancia / Planner 3.0 | aceptado, V3.61+ |
| P2-04 | media | `observed_difficulty` sigue siendo una proyección declarada/servida, no una dificultad **empíricamente** observada. | `backend/domain/vocabulary.py` (`task_difficulty_vectors`), `services/difficulty.py` | Observed Task Difficulty 2.0 | aceptado, V3.63 |
| P2-05 | media | El Sense Engine sigue siendo heurístico para corrección semántica/pragmática (no hay WSD real). | `backend/services/lexicon.py` (`score_transfer_attempt`) | Fuera de V3.60 | aceptado |
| P3-01 | baja | Tensión conceptual `register`: dimensión core de la familia **y** a la vez metadata admisible de instancia. | `backend/services/transfer.py:2385` (`_surface_details` lee `register`) | Formalizar que `family.register` es identidad y `instance.register` realización local | abierto |
| P3-02 | baja | `transfer.py` se está convirtiendo en un módulo demasiado grande (deuda de mantenibilidad, no fallo funcional). | `backend/services/transfer.py` (>3000 líneas) | Dividir en paquete `transfer/` sin cambiar la API pública | abierto |
| P3-03 | documental | El CI 6/6 se declara en la documentación pero no se verifica de forma independiente: la consulta directa devuelve `statuses: []` / `workflow_runs: []`. | `docs/RELEVO.md` (nota superior, run `34814504063`) | Mantener la etiqueta «documentado, no verificado» en auditorías sucesivas | aceptado |

## Lo que V3.60 cierra (verificado)

| Hallazgo de V3.59 | Estado | Evidencia |
|---|---|---|
| P1: 3 instancias memorizables | **cerrado estructuralmente** (3 → 16–19 por familia) | `transfer.py:2403` (espacio completo), `:184` (mínimo) |
| Instancia muda respecto a la dificultad | **cerrado** (`difficulty_delta`/`skill_delta`) | `transfer.py:2255`, `services/difficulty.py` |
| Banco manual de 60 superficies | **cerrado en arquitectura** (60 → 358) | `instance_space` en las 20 familias |
| Dificultad efectiva no registrada | **cerrado** (`served_difficulty` en el ledger) | `domain/vocabulary.py:850` |
| No fragmentar la evidencia | **cerrado y probado** (`context_id = FAMILIA`) | `transfer.py:164` (`CONTEXT_INSTANCE_KEYS`), `:2385` |

## Fortalezas verificadas (no son hallazgos)

- **Frontera de identidad:** `CONTEXT_INSTANCE_KEYS` es lista blanca (7 claves) y
  `_surface_details` descarta el resto; la intersección con las claves de familia
  es `{"prompt"}`.
- **Degradación exacta:** sin intentos, superficie 0 (consigna histórica byte a
  byte) y delta efectivo `{}`; las tres primeras superficies de V3.59 se
  conservan.
- **Determinismo:** sin `hash()`, sin `random`, sin `time` y sin LLM en el
  camino de la decisión; `_slug` derivado del contenido.
- **Anti-spoiler del `template`:** ninguna plantilla contiene la unidad objetivo
  ni deja llaves sin resolver. **Ver la salvedad de `T-AUDITORIA-TOTAL-V360.md`:
  la comprobación no cubría los VALORES de slot.**
- **Dificultad efectiva:** regla FAMILIA = carga absoluta, INSTANCIA = matiz
  relativo, con clamp ±2 y envelope 1..5.
- **Contrato aditivo:** 8 claves nuevas en todos los retornos, incluidas las del
  banco vacío; las 28 de V3.59 intactas y fijadas por test.
- **Ledger aditivo:** sin columnas nuevas, sin migración, sin bump de
  `GENERATOR_VERSION` y con bytes idénticos a V3.59 para las superficies sin
  delta.

## Veredicto

**Aprobada con matices — 9,6 / 10.** No hay P0. La arquitectura
FAMILIA → ESPECIFICACIÓN → INSTANCIA es conceptualmente correcta y resuelve el
problema fundamental de V3.59 (un banco finito y memorizable). Quedan **3 P1**
(espacio aún memorizable, equivalencia pedagógica no demostrada, Student Skill
State agregado) que son el siguiente escalón natural, no defectos de esta
release. **No se recomienda `V3.60.1`.**
**Salvedad importante:** esta auditoría validó el anti-spoiler sobre el
`template` y las claves de la especificación, **no** sobre cada valor de slot
contra la unidad objetivo; la auditoría `T` encontró ahí un defecto funcional
real. Ver `T-AUDITORIA-TOTAL-V360.md`.

## Roadmap recomendado

1. **V3.61 — Instance-aware Evidence** (`context_id` + `context_instance` en el
   ledger, sin cambiar la identidad pedagógica).
2. **V3.62 — Student Skill State 3.0** (modalidad × skill × dimensión).
3. **V3.63 — Observed Task Difficulty 2.0** (`declared` → `served` → `outcome` →
   `observed`).
4. **V3.64 — Planner 3.0** (P(success | learner, task) + ELV).
5. **V3.65+ — Instance Generator 2.0** (espacio por restricciones, validación).

> Idea rectora: **no seguir añadiendo complejidad al Context Engine antes de
> conectar correctamente `instance → evidence → skill state → planner`.** Ahí
> está el valor pedagógico pendiente, más que en pasar de 358 a 1.000 superficies.

## Regenerar / Verificar

```powershell
git clone https://github.com/jvelasca/english-tutor
cd english-tutor; git checkout v3.60.0          # 2c79040
git diff e721fce..2c79040                       # delta de la release
cd backend
python -m ruff check .
python -m pytest tests/ -q                      # 2333 passed, 2 skipped
python -c "from services import transfer as t; print(len(t.TRANSFER_CONTEXTS), sum(len(t.context_instance_details(c)) for c in t.TRANSFER_CONTEXTS))"   # 20 358
python -c "from services import transfer as t; d=t.context_instance_details('debate'); print(len(d), [s['generated'] for s in d[:4]])"                # 19 [False, False, False, True]
cd ../frontend; npx tsc --noEmit; npm test; npm run build
cd ..; python scripts/check_release_consistency.py; python scripts/check_beta_v3.py; python backend/scripts/content_validation.py
```

## Tests que respaldan

- `backend/tests/test_context_engine_v360.py` (23): frontera de identidad,
  anti-memorización, preservación de V3.59, equivalencia pedagógica, determinismo
  y end-to-end HTTP de la superficie generada con el vector efectivo persistido.
- `backend/tests/test_context_engine_v359.py`: ajuste `== 1 + MIN` → `>= 1 + MIN`.
- `backend/tests/test_task_difficulty_v355.py`: columnas `declared`/`served`/
  `observed_task_difficulty`.

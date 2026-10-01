# W — Auditoría total de V3.63.0 (Observed Task Difficulty 2.0 y honestidad del Student Skill State)

> **Posición auditada:** release **`v3.63.0`** → commit `73cebb4`
> (`release(v3.63.0): Observed Task Difficulty 2.0 y honestidad del Student Skill
> State`). Cierre documental inmediatamente posterior: `07c130b`
> (`docs(v3.63.0): registrar el cierre (commit 73cebb4, CI 6/6 y tag v3.63.0)`).
> Cierre de V3.62: `cdd0d97`/`f4bcee2` (tag `v3.62.0`). El delta auditado
> `cdd0d97..07c130b` es de **23 ficheros, +2566 / −75** (el commit de release solo:
> `cdd0d97..73cebb4`, **23 ficheros, +2509 / −75**), con una incorporación
> importante de lógica de estado/evidencia y **739 líneas nuevas** en el test
> principal de V3.63.
> **Autor:** auditoría externa (agente con acceso solo al repositorio).
> **Fecha:** 2026-09-14.
> **Relación con las letras reservadas:** la letra `R` sigue **reservada** para el
> informe pendiente de V3.59 (`docs/audit/R-AUDITORIA-TOTAL-V359.md`, nunca
> publicado) y la letra `V` para el informe externo de V3.62
> (`agentes/auditoria-externa-v362.md`); de ahí que esta auditoría use la `W`.

## Alcance

- **Se audita:** el salto `v3.62.0 → v3.63.0` —`services/observed_difficulty.py`
  (nuevo), los cambios de identidad/ocasión y confianza de evaluación en
  `services/skill_state.py`, el seam de política en `services/competence.py`, la
  columna aditiva `learning_profile.skill_state_source`, la frescura de la caché
  (`repositories.evidence.evidence_fingerprint` + `repositories.profile.skill_state_is_fresh`),
  el contrato aditivo de `/api/profile` y la frontera declarada con el camino de
  decisión—, además de la arquitectura acumulada desde V3.52 donde V3.63 la toca.
- **No se audita:** el banco de contextos, el scoring, FSRS, la UI/i18n y el
  detalle interno de V3.52–V3.62 salvo en lo que el diff de V3.63 afecta.

## Método

Revisión directa del diff `cdd0d97..07c130b`, de la nota de release
(`release-notes-v3.63.0.md`), del briefing archivado
(`agentes/v363-observed-task-difficulty-2.md`), del módulo nuevo
`services/observed_difficulty.py`, del agregador `services/skill_state.py`, del
seam `services/competence.py` y del camino de decisión real (ELV/planner/
`transfer.context_for`), contrastados contra los contratos de las cuatro fuentes
de evidencia. Suites y cifras de verificación leídas de la documentación de la
release (evidencia **documental**). Se comprobó además el estado combinado del
commit mediante la API de GitHub.

## Evidencia

| Comprobación | Resultado | Veredicto |
|---|---|---|
| Delta `cdd0d97..07c130b` | 23 ficheros, +2566 / −75 | OK |
| Test principal `test_observed_task_difficulty_v363.py` | +739 líneas | OK |
| Guion del ciclo de dificultad | `DECLARED → SERVED → OUTCOME → EXPERIENCED → OBSERVED` completo | OK |
| P0 | 0 | OK |
| P1 | 1 | abierto, aceptado (deuda V3.64+) |
| P2 | 4 | abiertos, aceptados |
| P3 | 2 | abiertos, aceptados |
| `assessment_confidence` separada de `confidence` | sí (banda mínima al agregar) | OK |
| OCASIONES (`observations` ≠ `occasions`) | sí (una evaluación expansiva = UNA ocasión) | OK |
| Canal OBSERVADO (escrito/oral) | sí (por actividad declarada, no por skill) | OK |
| Prácticas puras sin reloj/I/O/LLM/RNG | sí | OK |
| Cero umbrales nuevos (`COMPETENCE_GATE_POLICIES = {}`) | sí, con test que lo fija | OK |
| `test_skill_state_v362.py` sigue verde **sin tocarse** | sí | OK |
| CI 6/6 del run `34868713056` | `statuses = []` en la consulta directa | **documental, no verificado** |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| P1-01 | alta | `observed_task_difficulty_2()` **todavía no es** una verdadera estimación de dificultad: implementa *máxima carga servida/experimentada superada bajo una puerta de evidencia espaciada*, no una dificultad empírica. `experienced_load()` modula la carga servida con latencia, error, repeticiones y descuenta transcripción/audio lento, lo que mezcla **DIFFICULTY ≠ EFFORT** | `services/observed_difficulty.py` (`experienced_load`, `observed_task_difficulty_2`) | **No parchear ahora.** El seam (módulo puro, determinista, sin umbrales nuevos, reutilizando la puerta espaciada) es el correcto; la corrección corresponde al Planner/Decision Projection y a Observed Difficulty 3.0, no a otra tabla de heurísticas aislada | abierto (V3.64+) |
| P2-01 | media | El fingerprint `COUNT(*) + MAX(id)` no detecta todas las posibles modificaciones: un `UPDATE` (o `DELETE`+`INSERT`) que preserve `COUNT` y `MAX(id)` deja la caché reportándose fresca | `repositories/evidence.evidence_fingerprint` | Es suficiente si las tablas de evidencia son **append-only por contrato**. A largo plazo, `COUNT + MAX(id) + MAX(updated_at)` o un fingerprint de contenido/versión. **No cambiar ahora** | aceptado |
| P2-02 | media | `experienced_load()` mezcla coste con dificultad: `latency`/`replay`/`error` son **señales de esfuerzo** y algunos de dificultad, y la función las suma a la carga. Ej.: `replay_count = 3` puede significar tarea difícil, alumno distraído, audio malo o hábito del alumno — no se sabe cuál | `services/observed_difficulty.py` (`experienced_load`) | Mantener separados `task_difficulty` y `learner_effort` en la siguiente generación, y que **ambos alimenten al Planner por separado** | abierto (V3.64+) |
| P2-03 | media | `error_type` se trata como coste **homogéneo** (`error_type != "" → +1`), pero no es lo mismo `wrong_word` que `pronunciation_problem`, `low_confidence` o `grammar_error`: unos indican dificultad y otros **incertidumbre de medición** (p. ej. `ASR low_confidence` no implica "la tarea fue más difícil") | `services/observed_difficulty.py` (`ERROR_TYPE_STEP`) | Separar error de tarea (dificultad) de incertidumbre de medida. La infraestructura ya existe: `assessment_confidence` (V3.63) puede absorberlo | abierto (V3.64+) |
| P2-04 | media | El máximo por dimensión (`_ceiling()` → `max(...)`) puede **sobreestimar capacidad**: una sola experiencia exitosa a nivel 5 produce `observed = 5` aunque el alumno no haya consolidado ese nivel | `services/observed_difficulty.py` (`_ceiling`) | No es incorrecto si la semántica declarada es "highest demonstrated successful load", pero **no debería llamarse sin más "task difficulty"**: formalizar dos métricas (`highest_demonstrated_load` y `empirical_task_difficulty`, esta última con distribución y outcome) | abierto (V3.64+) |
| P3-01 | baja | **El modelo nuevo sigue sin gobernar las decisiones.** La propia V3.63 lo declara: `Student Skill State → NO → Planner`. ELV, planner, `difficulty` y `transfer.context_for` quedan byte-idénticos y el guard estructural permanece verde | nota de release (`Honestidad: qué NO cierra V3.63`) y `backend/tests/test_skill_state_v362.py` | Es deliberado y es el **P1-01 heredado**: cerrarlo con `Student Skill State → Decision Projection → Planner`, **nunca** `skill_state → planner` directamente, en V3.64 | abierto, comprometido |
| P3-02 | baja | CI 6/6 **documentado por el repositorio, no verificado de forma independiente**: la API devuelve `statuses: []` para el commit combinado. No se interpreta como fallo, simplemente no se contabiliza como verificación independiente | consulta a la API de GitHub sobre `07c130b` | Mantenerlo declarado como documental (mismo criterio que P3-02 de V3.62) | aceptado |

## Lo que V3.63 cierra (verificado)

- **Honestidad del Student Model (lo importante, por encima de `observed_difficulty.py`).**
  Cinco propiedades declarativas quedan implementadas y probadas:
  `NO SABEMOS → no inventamos`; `TENEMOS UNA OBSERVACIÓN → no la confundimos con
  una ocasión independiente`; `TENEMOS ÉXITO → no significa automáticamente alta
  confianza de evaluación`; `SABEMOS QUE FUE ESCRITO → no lo convertimos en
  speaking`; `TENEMOS UNA CARGA SERVIDA → no la confundimos automáticamente con
  competencia`.
- **`assessment_confidence` vs `confidence`.** Están separadas: `confidence` es la
  estadística (éxitos / intentos) y `assessment_confidence` responde a *¿hasta qué
  punto esa evaluación constituye evidencia fiable de la competencia?* Se deriva
  SOLO de hechos ya persistidos y, al agregar varias filas, toma la **banda
  mínima** (una evidencia débil no queda escondida detrás de varias fuertes).
  Ejemplo que el cambio hace explicable: `10/10` puede dar `confidence = 1.0` con
  `assessment_confidence = low` si el transcript era visible, el audio lento y el
  apoyo guiado. **Excelente.**
- **OCASIONES.** `observations` y `occasions` se separan, con `occasion_key()`
  derivado de identidad **ya declarada**: una evaluación expandida a N
  competencias son N observaciones y **UNA** ocasión, y el dedup **solo puede
  acreditar menos**, nunca más. Cierra el P2-13 de V3.62.
- **Degradación sin identidad.** Si la fuente no declara `assessment_id` ni
  `evidence_id`, el sistema **no inventa identidad**: `occasion = sample` y
  comportamiento EXACTO a V3.62. Sin información → menos precisión, nunca más
  evidencia. Propiedad importante para todo el Student Model.
- **Canal OBSERVADO.** `spontaneous_use + written → interaction` y
  `spontaneous_use + spoken → speaking`, con la resolución por `activity_id` →
  actividad declarada → `assessment_mode` **antes** de caer al mapa por skill. No
  se infiere ("creo que esto es oral"): se lee la declaración ("la actividad
  declaró que el canal evaluado era oral"). Cierra el P1-02 de V3.62.
- **Preparación de la conversación oral futura.** El vocabulario `speaking` puede
  alojar `lexical`/`grammar`/`fluency`/`interaction`/`pronunciation` sin
  contaminarse con `writing`, y `pronunciation` puede existir con independencia.
- **Pronunciación sin rúbrica inventada.** Si la ruta formal declara `criterion`,
  se usa; si no, `competence = ""` **con el motivo escrito**. Es preferible
  `unknown` a precisión falsa.
- **Listening por capas declaradas.** Las competencias se agrupan en
  `recognition`/`comprehension`/`inference` reutilizando `LISTENING_LAYERS`/
  `SKILL_LAYER`, sin vocabulario nuevo; `dictation`/`shadowing` quedan **fuera con
  motivo** porque son tareas de PRODUCCIÓN.
- **Seam de política del gate.** `CompetenceGate` + `gate_for(modality,
  competence, source)` con `COMPETENCE_GATE_POLICIES = {}` y un test que lo fija:
  no se introdujeron umbrales nuevos y parametrizar la puerta por pareja pasa a
  ser una **decisión explícita**.
- **Frescura de la caché.** `evidence_fingerprint()` sella las cuatro fuentes,
  `skill_state_source` guarda el sello y `skill_state_is_fresh()` compara: una
  caché vieja, vacía o **legacy sin sello** nunca se reporta fresca. Evita la
  ecuación "estado antiguo + evidencia nueva = falsa actualidad".
- **Principio "no inventar coste desconocido".** En `experienced_load()`, un
  coste desconocido **no modula**: `unknown ≠ difficult`. Muchos sistemas hacen
  `None → default` y ese default acaba convertido en "dato"; aquí no.
- **Compatibilidad hacia atrás.** No toca planner, ELV, difficulty, transfer,
  `transfer_state`, FSRS, recall ladder, UI, i18n, context bank ni
  `GENERATOR_VERSION`, y conserva las claves de V3.62 con el mismo significado.
  `test_skill_state_v362.py` pasa **sin modificaciones**.
- **Tests sobresalientes.** El test nuevo cubre identidad, ocasiones,
  deduplicación, degradación, canal observado, canal escrito/oral, dificultad
  servida, dificultad acreditada, scaffolding, carga experimentada,
  monotonicidad, límites, gate 2/2, determinismo, assessment confidence, TTS
  lento, transcript, pronunciación, listening layers, gate policy, fingerprint,
  migración y HTTP `/api/profile`. No solo se prueban resultados: se prueban las
  **fronteras epistemológicas** del modelo.

## Veredicto

**9,6 / 10 — APROBADA.** 0 P0. V3.63 es una de las versiones arquitectónicamente
más importantes del proyecto: no solo añade "observed difficulty", sino que
corrige varios problemas de **honestidad epistemológica** del Student Model que
podrían haber producido una falsa sensación de precisión.

Los dos puntos realmente importantes son **alcance consciente**, no defectos:

- **P1-01 (nuevo, conceptual):** `observed_task_difficulty_2()` sigue siendo más
  "carga máxima experimentada/demostrada" que una estimación empírica de
  dificultad. **No recomiendo parchearlo ahora** (no hay V3.63.1): V3.63 ha creado
  el **seam correcto** (módulo puro, determinista, sin I/O, sin reloj, sin
  `random()`, sin LLM, sin umbrales nuevos, reutilizando la puerta espaciada y
  consumiendo hechos ya persistidos). La solución definitiva debe llegar con la
  **Decision Projection / Planner 3.0**, no mediante otra tabla de heurísticas
  aislada.
- **P1-01 heredado (V3.62):** el nuevo Student Skill State todavía **no gobierna**
  el Planner. Se mantiene exactamente el plan documentado:
  `V3.64 = Student Skill State → Decision Projection → Planner 3.0`, **nunca**
  `skill_state → planner` directamente.

**La V3.63.0 es suficientemente sólida como para considerarla versión estable sin
V3.63.1.** El esfuerzo debe concentrarse en V3.64, porque es ahí donde todo este
trabajo de V3.60–V3.63 empezará a producir **adaptación pedagógica real** en lugar
de limitarse a describir con mucha más precisión al alumno.

### Arquitectura recomendada para V3.64 (estricta)

```text
                    RAW EVIDENCE
                         │
                         ▼
               CANONICAL EVIDENCE
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
      Skill State    Retention       Transfer
          │              │               │
          └──────────────┼───────────────┘
                         ▼
               DECISION PROJECTION
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        GAP          CAPACITY       CONFIDENCE
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                   TASK CANDIDATES
                         │
                         ▼
              Expected Learning Value
                         │
                         ▼
                       PLANNER
                         │
                         ▼
                  OPTIMAL NEXT TASK
```

Y la Decision Projection debe ser **explicable**: no un `{"priority": 0.83}` sin
motivo, sino algo como

```text
Task:
  spoken_production / travel / contextual_transfer

Why:
  speaking_gap: high
  retention_due: true
  transfer_gap: medium
  task_difficulty_fit: good
  assessment_confidence: high
  recent_failure: false
  novelty: medium

Expected learning value:
  0.81
```

de modo que el Planner sea **auditable**, no una caja negra.

### Roadmap recomendado tras V3.63

| Versión | Contenido |
|---|---|
| V3.64 | **Decision Projection + Planner 3.0** (cierre de P1-01). |
| V3.65 | **Observed Difficulty 3.0**: separar definitivamente `highest demonstrated load` de `empirical task difficulty` y empezar a estimar `P(éxito \| alumno, tarea)` **sin convertir el LLM en autoridad**. |
| V3.66 | **Adaptive Instance Selection**: ya no `attempt % N`, sino `learner state + previous instances + failure + success + difficulty + transfer + novelty → next instance`. |
| V3.67+ | **Sense Engine 2.0**: `surface → lemma → lexical_unit → sense → context → semantic fit → grammar → pragmatics`. |

### Evolución de los problemas anteriores

| Problema anterior | V3.63 |
|---|---|
| Student State demasiado agregado | cerrado en V3.62 |
| Canal oral/escrito ambiguo | cerrado |
| Evaluación expandida contaba varias ocasiones | cerrado |
| Pronunciation inventaba competencia | cerrado |
| Listening sin capas | cerrado |
| Assessment confidence confundida con confidence | cerrado |
| Cache freshness | cerrado |
| Observed difficulty no empírica | implementada, pero conceptualmente todavía limitada (P1-01) |
| Student State gobierna Planner | **pendiente V3.64** |
| Planner verdaderamente adaptativo | pendiente |
| WSD / semantic evaluation | pendiente |
| Instance adaptive generation | pendiente |
| Skill × modality × dimension completo | muy mejorado, aún evolutivo |

## Límites declarados de esta auditoría

- El **CI 6/6** del run `34868713056` es evidencia **documental**: la consulta
  directa del estado combinado del commit mediante la API devuelve
  `statuses: []`, así que no se afirma verificación independiente. No se
  interpreta como fallo.
- Los **P2** se aceptan como deuda declarada del siguiente escalón, no como
  defectos de V3.63. En particular, P2-01 (fingerprint) solo es una debilidad si
  las tablas de evidencia dejaran de ser append-only por contrato.
- No se audita el contenido pedagógico del banco ni la UI: V3.63 declara
  explícitamente que no los toca.

## Regenerar / Verificar

```powershell
git log --oneline -3                      # 07c130b / 73cebb4 / cdd0d97
git diff --stat cdd0d97 07c130b           # 23 ficheros, +2566 / -75
git show --stat --format="" 73cebb4       # test v363: +739 líneas
cd backend
python -m pytest tests/test_observed_task_difficulty_v363.py -q
python -m pytest tests/test_skill_state_v362.py -q   # debe pasar SIN tocarse
python -m pytest tests/ -q                            # 2430 passed (documental)
python -m ruff check .
```

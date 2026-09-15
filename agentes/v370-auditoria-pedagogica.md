# Briefing de subagente — V3.70 (Auditoría pedagógica + CEFR)

> **Estado:** **EN EJECUCIÓN** (2026-09-15 → release `v3.70.0`). Briefing maestro de
> la release; cada eje tiene su propio briefing autocontenido
> (`agentes/v370-a1-*` … `agentes/v370-a5-*`).
> **Qué es:** una release de **MEDICIÓN**, no de capacidad. Igual que V3.69 validó
> la **arquitectura** del Adaptive Engine, V3.70 mide la **pedagogía real** del
> contenido y de los instrumentos: ¿el contenido A1..C2 **es** de su nivel?, ¿están
> cubiertas todas las destrezas?, ¿se corrige de verdad?, ¿«demostrado» significa
> lo que dice?, ¿los instrumentos de nivelación funcionan?
> **Qué cierra:** el hueco que la propia auditoría de V3.69 declaró como
> **«🔴 PRÓXIMO GRAN FOCO»** (`Pedagogía/CEFR: todavía no auditada en profundidad`)
> y que `PLAN.md` `### M13` fija como `→ **V3.70** auditoría pedagógica
> (CEFR/competencias)`.
> **Qué NO cierra (deuda declarada):** los **6 P2 de la auditoría de V3.69**
> (cold start sin provenance, `abandoned_count` asimétrico, reopening de
> caducadas, semántica de `SCAFFOLDING_PENALTY`, `invalid_transition` por
> `StrictMode`, verificabilidad del CI), la **remediación de contenido** (volumen
> de corpus B1–C2, escenarios A1/C1, exámenes B2/C1/C2, Pre-A1), el rediseño del
> **Planner 4.0** y la **validez empírica con alumnos reales** (sigue en
> `docs/audit/PARKED.md` y `docs/BETA_V3.md` §4.2).
> **Auditoría/roadmap que lo motivan:** dictamen de V3.69 («ya no dedicaría otra
> V3.7x a perfeccionar indefinidamente el Planner; ahora toca comprobar si el
> tutor que hemos construido enseña inglés realmente bien») y `PLAN.md` `### M13`.
> **Regla dura declarada:** *V3.70 no toca producto, banco ni currículum salvo
> para AÑADIR instrumentos de medición de solo lectura. Toda insuficiencia se
> registra como P con evidencia y se traslada a su fase* (volumen de contenido →
> V4.0.x · motor/Planner → Planner 4.0 · UX → V3.72). Si un eje demuestra que la
> arquitectura **pedagógica** es insuficiente, **se documenta, no se arregla aquí**.
> **Batería:** **cinco ejes** en orden (AA→AE) + síntesis (AF), ver §Diseño.
> **Entrega:** **interna** — instrumentos en `backend/scripts/audit_dossier.py`,
> dossiers en `docs/audit/AA…AF-*.md` y métricas regenerables en
> `docs/audit/generated/`.
> **Base de partida:** árbol `v3.69.0` (commit `9a4e70a`, tag anotado `v3.69.0`;
> run de CI [`34978215154`](https://github.com/jvelasca/english-tutor/actions/runs/34978215154)).

## Rol

**Auditor pedagógico.** Extender el instrumento de dossier que ya existe
(`backend/scripts/audit_dossier.py`) con **cinco subcomandos de solo lectura**,
producir **cinco dossiers** con el formato de `docs/audit/TEMPLATE.md`, y fijar
cada hallazgo con **un test** que lo pinne. Sin migración destructiva, sin bump de
`GENERATOR_VERSION` ni `DECISION_POLICY_VERSION`, sin tocar el banco, sin tocar
el currículum y sin umbrales nuevos.

## Objetivo

Convertir «creemos que el contenido y la pedagogía son correctos» en «**está
medido, acotado y declarado**», y hacerlo **antes** de la fase offline/runtime
(V3.71) y de la fase UX (V3.72), para que V3.73 (auditoría final) audite un
producto cuyo contenido ya tiene una línea base cuantificada.

## Estado de partida verificado (árbol v3.69.0)

### Contenido real en disco (medido, no declarado)

| Fuente | Ruta | Volumen |
|---|---|---|
| Cursos A1..C2 | `backend/curriculum/a1.json … c2.json` | 31 módulos · 31 unidades · **116 objetivos** · **368 checks MC** · **512 actividades** · 34 `production_checks` |
| Instrumentos | `backend/curriculum/assessments.json` | placement `placement-v1` (24 ítems) + **solo** `a1-final` (10) y `b1-final` (12) + 5 bancos de remediación |
| Matriz CEFR | `backend/curriculum/cefr_matrix.json` (v2.1.0) | 6 niveles × 8 destrezas (`pronunciation` **fuera** a propósito) |
| Escalera Can-Do | `backend/curriculum/cefr_descriptors.json` (v1.0.0) | 9 dimensiones × **10 bandas** (incluye `A2+`, `B1+`, `B2+`) |
| Corpus listening | `backend/curriculum/listening_corpus.json` (v3.0.0) | **490 ítems** (A1 200, A2 200, B1 25, B2 25, C1 20, C2 20) |
| Corpus speaking | `backend/curriculum/speaking_corpus.json` (v2.0.0) | **148 ítems** (A1 36 → C2 14) |
| Escenarios speaking | `backend/curriculum/speaking_scenarios.json` | **26** (A1 **1**, A2 6, B1 7, B2 5, C1 **1**, C2 6) |
| Conversación / pronunciación | `conversation_corpus.json` (66) · `pronunciation_corpus.json` (120) | 11 y 20 por nivel |
| Audio **real grabado** | `backend/audio_library/manifest.json` | **`entries: []`** ⇒ todo el listening es TTS on-demand |

Cifras canónicas (`services.content_validation.content_stats()`, verificadas hoy):
`total_validated_learning_items = 539` (listening 513 = corpus 490 + legacy_tts 23,
+ 26 escenarios) · `with_audio_id = 499` · cobertura curricular 42/49 = **85,7 %**
(`pre-a1` **0/7**).

### Objetivos de expansión declarados (huecos medibles)

`services/curriculum.py` → `LISTENING_CORPUS_TARGETS = {A1:200, A2:200, B1:180,
B2:160, C1:120, C2:100}` ⇒ **B1..C2 están al 14–20 % de su objetivo**.

### Taxonomía y estimadores

- `services/skill_axis.py` → `SKILL_MODALITIES` (9) y `COMPETENCES_BY_MODALITY`;
  **`interaction` y `mediation` declaran tupla VACÍA**.
- `services/mastery.py` → `MASTERY_SKILLS` (9).
- `services/skill_state.py` → `MODALITY_CHANNEL` **no tiene entrada para
  `interaction` ni `mediation`** (⇒ `assessment_confidence = low`, `channel_unknown`).
- `services/competence.py` → 4 estados, `PRODUCTION_SKILLS = (grammar, speaking,
  writing)`, `SUPPORT_SKILLS = (vocabulary,)` (tope en `functional`).
- `services/academy.py` → `MAX_PLACEMENT_ITEMS = 8`, `PLACEMENT_MIN_ITEMS = 4`,
  `PLACEMENT_SE_THRESHOLD = 0.5`, `ability_theta`/`theta_to_level` (IRT-lite 1PL).
- `services/adaptive.py` → `numeric_to_level`; `services/cefr.py` →
  `heuristic_band`. **Tres implementaciones distintas del mismo corte de banda
  (1.5/2.5/3.5/4.5/5.5)** y solo `cefr_descriptors` conoce las sub-bandas `+`.
- `services/difficulty.py` → `CEFR_CAPACITY`, `challenge_vector(item_level,
  learner_level)`, `SUPPORT_DISCOUNT_STEPS` (guided 2 / cued 1 / independent 0).

### Instrumento de medición ya existente (a EXTENDER, no a reinventar)

`backend/scripts/audit_dossier.py` ya tiene los subcomandos `corpus-stats`,
`sample`, `curriculum-stats`, `speaking-stats`, `mc-bias`; escriben su par
`.md`/`.json` en `docs/audit/generated/` vía `_write_generated()`. **Reutilizar ese
patrón exacto** (mismo `GENERATED_DIR`, misma firma de salida, mismo
`REFERENCE_BANDS`).

**Deriva conocida:** `docs/audit/generated/curriculum-stats.{md,json}` está
**desincronizado** con el disco (declara C1 = 14 y C2 = 14 objetivos frente a los
**20 y 20** reales, y 116 totales). El eje 1 lo **regenera** y deja constancia de
la corrección.

### Criterio de referencia

`docs/audit/CEFR-REFERENCE.md` (v0.1) es la tabla normativa **interna** para
marcar desviaciones: bandas de `speech_rate` por nivel, `difficulty_vector`
típico, longitud de turno, registro léxico, connected speech real, plausibilidad
de distractores, criterios de `inference` y de pragmática C1/C2. **No es un
documento CEFR normativo** y el dossier debe repetirlo.

### Convenciones de dossier

`docs/audit/TEMPLATE.md` → `Alcance · Método · Evidencia · Hallazgos
(| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |) · Veredicto ·
Regenerar / Verificar · Tests que respaldan`.

Severidades `P0/P1/P2/P3`. Regla de la casa (auditoría `Y` §28): **distinguir «el
test no demuestra» de «el motor no cumple»**.

### Nomenclatura de las letras

La serie `A–Z` está agotada o reservada (`Z`/`Z2` pertenecen a V3.69). Los
dossiers de V3.70 usan el prefijo **`AA`–`AF`**:

| Fichero | Eje |
|---|---|
| `docs/audit/AA-PED-CONTENIDO-CEFR.md` | 1 · Adecuación CEFR real del contenido |
| `docs/audit/AB-PED-COBERTURA.md` | 2 · Cobertura de destrezas |
| `docs/audit/AC-PED-FEEDBACK.md` | 3 · Feedback y corrección |
| `docs/audit/AD-PED-MAESTRIA.md` | 4 · Validez de la afirmación de maestría |
| `docs/audit/AE-PED-INSTRUMENTOS.md` | 5 · Instrumentos de nivelación |
| `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md` | Síntesis y veredicto global |

## Decisiones de alcance (CERRADAS)

1. **Solo medición.** No se arregla ningún P2 de V3.69, no se remedia contenido,
   no se toca el argmax del Planner ni el currículum.
2. **Cinco ejes, en orden**, ejecutados por **cinco subagentes** secuenciales.
   Entre ejes, el orquestador corre los gates (`ruff` + `pytest`) para que un eje
   no herede un árbol rojo.
3. **Entrega interna**: dossiers + tests + métricas regenerables. No hay briefing
   para auditor externo (a diferencia de V3.69 `Z`/`Z2`).
4. **Instrumentos nuevos = `backend/scripts/`**, declarados honestamente en la
   release note como **herramienta de medición, no ruta de producto** (aquí **sí**
   hay diff fuera de `tests/`, a diferencia de V3.69).
5. **Goldens**: solo se amplía `backend/tests/golden/pedagogy/` si el dossier del
   eje 4 lo justifica; la regla de `backend/tests/golden/README.md` (un golden se
   edita **solo** tras re-auditoría con su id `audit:`) **no se relaja**.

## Diseño

### §A · Instrumentos de medición (se construyen primero)

Cinco subcomandos nuevos en `backend/scripts/audit_dossier.py`, **de solo
lectura** (`data/` y `curriculum/` nunca se escriben), cada uno con su
`_write_generated("nombre", md, data)`:

| Subcomando | Qué mide | Salida |
|---|---|---|
| `cefr-adequacy` | Por nivel: `difficulty_from_vector` vs banda de `CEFR-REFERENCE.md`, `speech_rate` vs `REFERENCE_BANDS`, distribución de `difficulty_vector`, **monotonía entre niveles**; por ítem: `connected_speech` declarado vs evidencia textual, distractor plausible, si un `inference` se resuelve con una palabra | `cefr-adequacy.{md,json}` |
| `skill-coverage` | Matriz `modalidad × {contenido, scorer, fuente de evidencia, estimador, UI}` con conteos reales y los huecos declarados | `skill-coverage.{md,json}` |
| `feedback-coverage` | Por destreza: canal de corrección (determinista / LLM / ninguno) y granularidad | `feedback-coverage.{md,json}` |
| `mastery-claims` | Los 4 estados, gate funcional, topes, mínimos de matriz, spacing gate y huecos de acreditación | `mastery-claims.{md,json}` |
| `assessment-instruments` | Placement, exámenes, remediación, gate de unidad y duplicación de umbrales de banda | `assessment-instruments.{md,json}` |

### §B · Eje 1 — Adecuación CEFR real del contenido

**Pregunta:** ¿los ítems A1..C2 **son** de su nivel? **Fuentes:** los 6 cursos, el
corpus de listening (490), los checks MC y los `production_checks`. **Método:**
criterios de `CEFR-REFERENCE.md` + muestreo determinista
(`sample --bank listening|objectives --level X --count N --seed 7`). **Debe
responder también:** si el contenido está **mal etiquetado**, si la **progresión**
entre niveles es monótona y si la deriva de `curriculum-stats` se corrige.

### §C · Eje 2 — Cobertura de destrezas

**Pregunta:** ¿está el alumno expuesto a las 9 modalidades? **Medir, con número:**
listening B1–C2 vs `LISTENING_CORPUS_TARGETS`; escenarios A1/C1; exámenes
únicamente A1/B1; ausencia de curso Pre-A1; `manifest.entries = []`; `reading` sin
motor propio (`backend/services/reading.py` **no existe**); `mediation` e
`interaction` sin competencias ni canal; `novel` con emisor real desde
V3.26/F-B1 pero **nunca exigido** (`novel_required = 0` en las 48 celdas).

### §D · Eje 3 — Feedback y corrección

**Pregunta:** ¿el tutor corrige bien? **Medir:** qué se corrige de forma
**determinista** (regex de `services/grammar.py` con `CONFIRMED_THRESHOLD = 0.8` y
`MASTERY_STREAK = 3`, rúbricas de `writing.py` 6 dims y `speaking.py` 7 dims,
fonética de `phonetics.py`/`pronunciation.py`, telemetría de `interaction.py`) y
qué depende del **LLM** (`policy.py` → `CORRECTNESS_GUIDANCE` por nivel +
`FEEDBACK_CATEGORIES` = CORRECT/NATURAL/OPTIONAL/STYLE/PRONUNCIATION, inyectado por
`context.build_system_prompt`). **Debe declarar** dónde el feedback es **solo
puntuación** (reading, pronunciation) y dónde es **solo prompt** (tutor chat).

### §E · Eje 4 — Validez de la afirmación de maestría

**Pregunta:** ¿«demostrado» significa lo que dice? **Medir:** los 4 estados de
`services/competence.py`, el gate funcional (readiness + retención +
`evidence_depth` vs mínimo de matriz + producción para `PRODUCTION_SKILLS`), el
tope de `SUPPORT_SKILLS`, el spacing gate `2 muestras × 2 días`
(`learner_skill.OBSERVED_MIN_SAMPLES/OBSERVED_MIN_DAYS`), los mínimos por nivel y
destreza de `cefr_matrix.json` y los **huecos de acreditación** ya documentados
(`objective_id=''` en speaking assessment/mission ⇒ la fila entra como intento
pero **no acredita éxito**; `novel` con emisor real pero requisito inerte
(`novel_required = 0`); competencias de `interaction`/
`mediation` vacías).

### §F · Eje 5 — Instrumentos

**Pregunta:** ¿los instrumentos de nivelación son suficientes? **Medir:** placement
CAT-lite (`MAX_PLACEMENT_ITEMS = 8`, `PLACEMENT_MIN_ITEMS = 4`,
`PLACEMENT_SE_THRESHOLD = 0.5` ⇒ cuántas veces se alcanza realmente la parada
adaptativa), exámenes finales **solo A1/B1** con `min_per_skill = 0.75`, los 5
bancos de remediación, el gate de unidad (`UNIT_GATE_THRESHOLDS`) y la
**triplicación de umbrales de banda** (`academy.theta_to_level` /
`adaptive.numeric_to_level` / `cefr.heuristic_band`) frente a las sub-bandas `+`
que solo existen en `cefr_descriptors`.

### §G · Síntesis (orquestador, no subagente)

`docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`: matriz consolidada
`P0/P1/P2/P3`, veredicto numérico, y sección de **honestidad**: lo que V3.70 **NO**
demuestra (discriminación empírica con alumnos, calidad acústica real, eficacia
pedagógica medida en aprendizaje).

## Tests

- **Nuevos** (uno por eje, cada hallazgo fijado por al menos un test):
  `backend/tests/test_ped_content_cefr_v370.py`,
  `test_ped_coverage_v370.py`, `test_ped_feedback_v370.py`,
  `test_ped_mastery_v370.py`, `test_ped_instruments_v370.py`.
- **Regla:** se afirma sobre **contratos observables** (constantes declaradas,
  contenido real resuelto del disco, funciones puras del motor), **nunca** sobre
  la implementación privada, y **nunca** se escribe un test que pase porque el
  contenido es pobre: si el hueco existe, el test lo **declara** como hueco
  esperado con su número.
- **No-regresión obligatoria, sin tocarse:** `test_pedagogy.py`,
  `test_pedagogical_invariants.py`, `test_competence.py`, `test_mastery.py`,
  `test_cefr_matrix.py`, `test_cefr_descriptors.py`, `test_cefr_semantics.py`,
  `test_curriculum_quality.py`, `test_curriculum_coverage.py`,
  `test_content_quality.py`, `test_golden_pedagogy.py`, `test_placement*.py`,
  `test_assessment_v2.py`, `test_golden_*`.
- **Goldens:** `backend/tests/golden/pedagogy/` solo se amplía si el dossier
  `AD` lo justifica, con su `audit: "AD-2026-09-15"` y actualizando
  `backend/tests/golden/README.md`.

## Criterios de salida

1. Los cinco dossiers `AA`–`AF` existen, siguen `docs/audit/TEMPLATE.md` y cada
   hallazgo lleva `archivo:línea` como evidencia.
2. Los cinco subcomandos de `audit_dossier` corren **sin escribir** en `data/` ni
   en `curriculum/` y regeneran sus pares en `docs/audit/generated/`
   (`curriculum-stats` incluido, ya sincronizado).
3. Los cinco ficheros de test nuevos están **verdes**, y el total de `pytest` es
   **anterior + nuevos**, sin fallos.
4. `ruff check .` limpio; `tsc --noEmit`, `vitest`, `build` y launcher sin cambios
   (V3.70 no toca frontend ni launcher: se declara así).
5. Gates de script OK: `check_release_consistency` (**3.70.0**),
   `check_beta_v3`, `content_validation` y `transfer_validation`.
6. La release note declara **honestamente** el diff fuera de `tests/`
   (los subcomandos de medición) y todo lo que la release **no** demuestra.
7. **CI 6/6** verde, registrado con su run id y declarado como **resultado del
   release**, no como verificación independiente.

## Fuera de alcance (deuda declarada)

- **Los 6 P2 de V3.69**: cold start sin provenance, `abandoned_count` asimétrico,
  reopening de caducadas, semántica de `SCAFFOLDING_PENALTY` (Planner 4.0),
  `invalid_transition` por `StrictMode` (arreglo mínimo de 2 líneas propuesto para
  V3.70 en V3.69 pero **no ejecutado aquí** por la regla dura de solo medición),
  verificabilidad del CI.
- **Remediación de contenido**: corpus listing B1–C2 hasta objetivo, escenarios
  A1/C1, exámenes B2/C1/C2, curso Pre-A1, audio humano grabado.
- **Motor**: rediseño del Planner, Expected Learning Gain real, calibración con
  tráfico real.
- **Validación empírica** con alumnos (fase de observación, `PARKED.md`).
- **V3.71** offline/runtime → **V3.72** UX/product completion → **V3.73**
  auditoría final técnica → **V4.0**.

## Cierre (higiene de release, cuando se ejecute)

`check_release_consistency.py` usa **la primera coincidencia** de cada fichero,
así que hay que insertar la entrada nueva **arriba**:

1. `backend/config.py:32` → `VERSION = "3.69.0"` → `"3.70.0"` (**fuente única**).
2. `frontend/package.json:4` → `"version"`.
3. `frontend/package-lock.json:3` (**y** la copia de `:9`).
4. `README.md:16` → «Última versión estable: **v3.70.0**».
5. `CHANGELOG.md` → nueva entrada `## [3.70.0] — <fecha>` **en la cabecera**, por
   encima de `## [3.69.0]`.
6. `PLAN.md` → nuevo bullet como **primer** item de «Estado actual» (línea 11) con
   ``**Versión estable `3.70.0`**`` y ``app `3.69.0 → 3.70.0` ``; actualizar
   `### M13` (marcar V3.70 hecho y mover la flecha a V3.71) y la fila del tablero
   de briefings.
7. `docs/RELEVO.md` → **nota nueva encima de la nota actual** + fecha de
   «Actualizado por última vez» + refrescar **«0. START HERE»** (hoy arrastra
   placeholders `COMMIT_PENDIENTE`/`RUN_PENDIENTE` de V3.69).
8. `release-notes-v3.70.0.md` (nuevo, raíz) con: contexto, los cinco ejes, tabla de
   hallazgos con severidad, tests, §«Honestidad» y §«Fuera de alcance».
9. `docs/audit/PARKED.md` → registrar lo deliberadamente **no** arreglado.
10. **No** tocar `DECISION_POLICY_VERSION` ni `GENERATOR_VERSION`.

Verificación local completa **antes** de commitear: `ruff`, `pytest`,
`tsc --noEmit`, `vitest`, `build`, launcher, `check_release_consistency`,
`check_beta_v3`, `content_validation` y `transfer_validation`. Después: commit de
release + tag anotado `v3.70.0` + push, y registrar el run de **CI** (6/6) en la
nota de `docs/RELEVO.md`.

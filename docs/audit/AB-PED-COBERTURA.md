# AB · Auditoría de cobertura de destrezas (V3.70 · Eje 2)

> **Release:** V3.70 (auditoría pedagógica + CEFR) · **Eje 2 de 5**
> **Fecha:** 2026-09-15 · **Instrumento:**
> `python -m scripts.audit_dossier skill-coverage` (solo lectura)
> **Evidencia cruda:** `docs/audit/generated/skill-coverage.{md,json}`
> **Regla dura de V3.70:** *no se toca producto, banco ni currículum*: los
> huecos de contenido se declaran con número y severidad y su remediación va a
> **V4.0.x**. Este eje mide **cobertura declarada y volumen**, no eficacia.

## Alcance

Las **9 modalidades** declaradas en `services/mastery.MASTERY_SKILLS`
(`backend/services/mastery.py:84`), que son también las de
`services/skill_axis.SKILL_MODALITIES` (`backend/services/skill_axis.py:88`):
`vocabulary`, `grammar`, `pronunciation`, `listening`, `speaking`, `reading`,
`writing`, `interaction`, `mediation`.

Para cada modalidad se audita **qué existe** de cinco cosas: competencias
declaradas, presencia en la matriz CEFR, canal de evidencia, contenido (objetivos
/ checks / corpus) y artefactos de ejecución (scorer en `backend/services/` y
feature en `frontend/src/features/`).

**No se audita** en este eje:

- la **adecuación CEFR** del contenido y de los ítems (eje 1,
  `docs/audit/AA-PED-CONTENIDO-CEFR.md`);
- el **feedback y la corrección** (eje 3, `docs/audit/AC-PED-FEEDBACK.md`);
- la **validez de la afirmación de maestría** (eje 4,
  `docs/audit/AD-PED-MAESTRIA.md`);
- los **instrumentos de nivelación** (eje 5,
  `docs/audit/AE-PED-INSTRUMENTOS.md`);
- la **calidad acústica** del audio ni el **aprendizaje** real de un alumno:
  este eje mide **cobertura declarada y volumen realizado**, que es una
  condición necesaria pero **no suficiente** de eficacia pedagógica.

> **Este eje mide cobertura DECLARADA y volumen, NO eficacia pedagógica.** Que
> una destreza tenga objetivos, corpus, scorer y UI demuestra que existe el
> **soporte** para observarla; **no** demuestra que el alumno aprenda. La
> eficacia requiere alumnos reales en el bucle y sigue fuera de alcance
> (`docs/audit/PARKED.md`, `docs/BETA_V3.md` §4.2).

## Método

1. **Instrumento de solo lectura** `skill-coverage`, que **comprueba la
   existencia de los artefactos en disco** (no se fía de lo declarado) mediante
   `Path.exists()` / `Path.is_dir()` sobre `backend/services/<módulo>.py` y
   `frontend/src/features/<feature>/`.
2. **Fuentes canónicas:** `services.mastery.MASTERY_SKILLS`,
   `services.skill_axis.COMPETENCES_BY_MODALITY`,
   `services.skill_state.MODALITY_CHANNEL`,
   `services.cefr_matrix.load_matrix()`,
   `services.curriculum.load_all_levels()` y
   `services.content_validation.content_stats()` (métrica única anti-drift).
3. **Manifest de audio** (`backend/audio_library/manifest.json`) como fuente de
   verdad de lo **grabado a voz humana**.
4. **Objetivo declarado de corpus:**
   `services.curriculum.LISTENING_CORPUS_TARGETS`
   (`backend/services/curriculum.py:223`).

## Evidencia

### 1. Matriz modalidad × artefacto

| Modalidad | Competencias | En matriz | Canal | Objetivos | Checks | Corpus | Scorer | UI |
|---|---|---|---|---|---|---|---|---|
| vocabulary | 8 | sí | written | 110 | 180 | 0 | `lexicon.py` | `vocabulary` |
| grammar | 11 | sí | written | 56 | 104 | 0 | `grammar.py` | `grammar` |
| pronunciation | 10 | **NO** | spoken | 38 | 0 | 120 | `pronunciation.py` | `pronunciation` |
| listening | 24 | sí | receptive | 38 | 66 | 490 | `listening.py` | `listening` |
| speaking | 18 | sí | spoken | 70 | 0 | 174 | `speaking.py` | `speaking` |
| reading | 10 | sí | receptive | 15 | 18 | 0 | `reading.py` **AUSENTE** | `reading` |
| writing | 15 | sí | written | 67 | 0 | 0 | `writing.py` | `writing` |
| interaction | **0** | sí | **NO** | 0 | 0 | 66 | `interaction.py` | `conversation` |
| mediation | **0** | sí | **NO** | 0 | 0 | **0** | **AUSENTE** | **AUSENTE** |

`objectives` cuenta pares (nivel, objetivo) que declaran la modalidad en
`Objective.skills`; `checks` cuenta `ObjectiveCheck.skill`; `corpus` suma el
banco correspondiente (`speaking` = 148 ítems de corpus + 26 escenarios).

Los **cinco atributos** que la matriz del dossier exige a cada modalidad son:
**competencias** declaradas, presencia en la **matriz CEFR**, **canal** de
evidencia, **scorer** de ejecución y feature de **UI**. El instrumento comprueba
scorer y UI **contra el disco** (`Path.exists()` sobre `backend/services/*.py` y
`Path.is_dir()` sobre `frontend/src/features/*`), **no** contra lo que el código
declare: un módulo prometido pero ausente cuenta como hueco. El test
`test_every_mastery_modality_is_accounted_for` fija esa matriz y la contrasta
con el disco (anti-deriva).

### 2. Las tres categorías que el eje debe separar

**(a) Declarado y operativo** — competencias, canal, contenido y artefactos
presentes: `vocabulary`, `grammar`, `listening`, `speaking` y `writing`. Se suma
`pronunciation` (10 competencias, canal `spoken`, 120 ítems, scorer y UI
presentes en disco), con una salvedad explícita: está **fuera de la matriz CEFR
a propósito**, así que no tiene requisitos de nivel (hallazgo 8).

**(b) Declarado pero sin emisor formal de evidencia**: `interaction` tiene
módulo scorer (`backend/services/interaction.py`), 66 ítems de corpus y UI
(`conversation`), pero **no declara competencias ni canal**: no aparece en
`MODALITY_CHANNEL` (`backend/services/skill_state.py:102`) y su tupla de
competencias es vacía (`backend/services/skill_axis.py:276`). Sin canal, la
evidencia que produzca no se puede atribuir formalmente a la modalidad.

**(c) Declarado pero inerte**:

- `reading`: **15 objetivos y 18 checks** lo declaran, hay feature de UI, pero
  **no existe `backend/services/reading.py`** ni corpus propio (`corpus 0`). La
  única evidencia posible de reading son checks MC servidos por la ruta genérica
  de quiz.
- `mediation`: **0 competencias** (`"mediation": ()` en
  `backend/services/skill_axis.py:277`), **0 corpus**, sin canal, sin scorer y
  sin feature de UI. Aun así, la matriz CEFR le exige requisitos en los **6**
  niveles.

### 3. Huecos medidos por el instrumento

| Modalidad | Hueco |
|---|---|
| reading | sin scorer propio |
| interaction | sin canal de evidencia |
| mediation | sin competencias ni corpus |
| mediation | sin canal de evidencia |
| mediation | sin scorer propio |
| mediation | sin feature de UI |

### 4. Volumen de listening frente al objetivo declarado

| Nivel | Corpus declarado | Objetivo (`LISTENING_CORPUS_TARGETS`) | % del objetivo |
|---|---|---|---|
| A1 | 200 | 200 | 100,0 % |
| A2 | 200 | 200 | 100,0 % |
| B1 | 25 | 180 | **13,9 %** |
| B2 | 25 | 160 | **15,6 %** |
| C1 | 20 | 120 | **16,7 %** |
| C2 | 20 | 100 | **20,0 %** |

El nivel que el producto dice enseñar en su mitad superior (B1–C2) está entre
**una séptima parte** y **una quinta parte** de su objetivo declarado. A1 y A2
lo cumplen al 100 %.

### 5. Escenarios de speaking por `cefr_target`

`A2: 6 · B1: 7 · B2: 5 · C2: 6` — y los extremos **`A1: 1` y `C1: 1`**.
Total **26** (`services/speaking_scenarios.list_scenarios()`).

### 6. Audio y cobertura curricular

- `backend/audio_library/manifest.json` versión **1.2.0** con
  **`entries: []`** ⇒ **cero ítems grabados a voz humana**. Todo el listening es
  **TTS on-demand**, mientras el *Quality Gate* de
  `services/content_validation.py:79` mide diversidad **declarada**
  (≥10 hablantes, ≥4 acentos, ruido, multi-hablante) — el propio módulo advierte
  en su docstring que **no** mide el audio realizado.
- `content_stats()`: **539** ítems de aprendizaje validados
  (listening **513** = corpus 490 + legacy 23; `with_audio_id` 499;
  escenarios 26).
- **Cobertura curricular: 42/49 celdas (85,7 %)**, con **`pre-a1` 0/7** — no
  existe curso Pre-A1 aunque `services/cefr_descriptors.py` declare la banda.

### 7. Limpio (sin hallazgo)

- **Seis modalidades operativas**: las cinco con competencias, canal y contenido
  (`vocabulary` 110 objetivos/180 checks, `grammar` 56/104, `listening` 38/66 +
  490 ítems, `speaking` 70 objetivos + 174 ítems, `writing` 67 objetivos) más
  `pronunciation` (canal `spoken`, 10 competencias, 120 ítems, scorer y UI
  presentes en disco), con la salvedad de hallazgo 8.
- **Las 8 destrezas de `cefr_matrix.json` (v2.1.0) tienen requirements
  declarados en los 6 niveles**: ninguna queda sin exigencia formal;
  `pronunciation` es la única modalidad **fuera** de la matriz, y lo está **a
  propósito** (hallazgo 8).
- **Los 6 niveles tienen corpus de listening** (mínimo 20 ítems en C1/C2):
  ningún nivel queda a cero, aunque B1–C2 estén lejos de su objetivo
  (hallazgo 2).
- **La sección `interaction` está poblada en 6 de los 7 niveles** (el séptimo,
  `pre-a1`, no tiene curso): la interacción se entrena vía subdestrezas
  (`interaction`, `turn_taking`, `repair`, `backend/services/course.py:41`), lo
  que confirma que el hueco de `interaction` es de **canal/competencias**, no de
  contenido.
- **Cero duplicidad de métricas**: el dossier usa la métrica canónica
  `content_stats()` (539 ítems validados) y contrasta la matriz generada contra
  el disco; no recalcula cifras paralelas.

### 8. Relación con los ejes vecinos

- **Eje 1 (`AA-PED-CONTENIDO-CEFR.md`)**: mide la **adecuación** de los 490
  ítems de listening (velocidad, `connected_speech`, sesgo MC); este eje mide su
  **volumen** frente al objetivo declarado. Los **3 ítems de remediación de
  contenido** que aquí se trasladan a **V4.0.x** (ampliar corpus B1–C2,
  completar escenarios A1/C1, grabar audio humano) comparten fase con los de AA
  (hallazgos #2/#3 —bandas de wpm de A1 y C1–C2— y #5 —`connected_speech`—):
  **la deuda es de contenido, no de motor**.
- **Eje 3 (`AC-PED-FEEDBACK.md`)**: confirma que `reading` y `mediation` tampoco
  tienen **canal de corrección** (coherente con la categoría (c) de este eje);
  el hueco de emisor se ve desde los dos lados.
- **Eje 4 (`AD-PED-MAESTRIA.md`)**: consume esta matriz. Si `mediation` no puede
  recibir evidencia, la afirmación de maestría sobre ella es inalcanzable por
  construcción; y si el corpus B1–C2 es escaso, los instrumentos de nivelación
  (eje 5) no tienen dónde medir esa mitad del rango. Aquí solo se **declara el
  insumo**, sin reabrir sus hallazgos.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| 1 | **P1** | `mediation` está declarada como modalidad evaluable y exigida por la matriz CEFR en los 6 niveles, pero **no tiene competencias, ni corpus, ni canal de evidencia, ni scorer, ni UI**: por construcción **nunca** puede recibir evidencia. | `skill_axis.py:277` (`"mediation": ()`), ausencia en `skill_state.py:102`, `cefr_matrix.json:12,22,32,42,52,62` (exige `minimum_evidence` 3/3/3/4/5/6 = **24 inalcanzables**), `skill-coverage.json` (`competences 0`, `corpus 0`, `scorer_exists false`, `ui_exists false`) | Retirar `mediation` de `MASTERY_SKILLS`/matriz **o** construir su emisor. Es una decisión de producto, no de auditoría → **V4.0.x / Planner 4.0** | Abierto |
| 2 | **P1** | Corpus de listening **B1–C2 al 13,9–20,0 %** de su objetivo declarado (25, 25, 20, 20 ítems frente a 180, 160, 120, 100). | `curriculum.py:223`, `skill-coverage.json` → `listening_targets` | Plan de expansión de contenido con prioridad B1→B2→C1→C2 → **V4.0.x** | Abierto |
| 3 | **P1** | **Cero audio humano grabado**: el manifest versionado declara la biblioteca y no contiene ninguna entrada; el 100 % del listening es TTS. | `backend/audio_library/manifest.json` (`entries: []`), `skill-coverage.json` → `recorded_entries: 0` | Decidir si el audio humano entra en el producto; si no, **dejar de declarar** una biblioteca de audio como infraestructura lista | Abierto |
| 4 | **P1** | `reading` declara **15 objetivos y 18 checks** y tiene UI, pero **no existe un scorer propio** (`backend/services/reading.py` ausente): la evidencia de reading solo puede ser MC genérico. | `skill-coverage.json` → `reading.scorer_exists false` y `ui_exists true` (`ui_feature chat:lectura`); directorio `backend/services/` sin `reading.py`; UI servida por `frontend/src/router/chat.ts` → `/chat/lectura` (Opción A, V3.73.1: la antigua `frontend/src/features/reading/` se retiró con `ReadingPractice`) | O bien construir el scorer de reading, o bien declarar explícitamente en `CONSTITUCION-PEDAGOGICA.md` que reading se evalúa por MC | Abierto |
| 5 | **P2** | `interaction` no tiene **competencias** ni **canal de evidencia** (`MODALITY_CHANNEL` la ignora) pese a tener módulo scorer (`interaction.py`), corpus de 66 ítems, UI (`conversation`) y requisitos en la matriz. | `skill_axis.py:276` (`"interaction": ()`), `skill_state.py:102`, `skill-coverage.json` | Añadir `(interaction, written)/(interaction, spoken)` a `MODALITY_CHANNEL` y declarar sus competencias | Abierto |
| 6 | **P2** | Escenarios de speaking: **A1 y C1 tienen 1** cada uno (frente a 6–7 en A2/B1/C2). | `skill-coverage.json` → `scenarios_by_level` | Completar escenarios de los niveles extremos → **V4.0.x** | Abierto |
| 7 | **P3** | La banda `pre-a1` existe en la escalera (`cefr_descriptors.CEFR_LADDER`) pero **no hay curso Pre-A1**: 0/7 celdas de cobertura. | `cefr-adequacy`/`content_stats()` → `by_level["pre-a1"] {populated: 0, total: 7}` | Decidir si Pre-A1 es producto o solo banda de visualización | Abierto |
| 8 | **P3** | `pronunciation` está **deliberadamente** fuera de la matriz CEFR (10 competencias, 120 ítems, scorer propio, UI). Es una decisión, no un defecto: requiere constancia documental para que no se lea como hueco. | `skill-coverage.json` → `pronunciation.declared_in_matrix false` | Dejarlo escrito en `CONSTITUCION-PEDAGOGICA.md` | Abierto |

## Veredicto

La cobertura **no** está repartida uniformemente: **seis** de las nueve
modalidades están operativas, **una** (`interaction`) tiene artefactos pero no
emisor formal de evidencia, y **dos** (`reading`, `mediation`) están
**declaradas e inertes** — `mediation` de forma total (0/0/0/0/0) y `reading` de
forma parcial (contenido y UI sí, corpus y scorer no).

Esto **no** es una insuficiencia de arquitectura: el vocabulario de modalidades,
la matriz y los canales existen y funcionan (6 modalidades operativas y 1 con
artefactos, aunque sin canal formal). El hueco de cierre es acotado pero duro:
la matriz exige **24 evidencias de `mediation`** que ningún componente puede
producir, y `reading` no tiene scorer. El resto es un **déficit de volumen de
contenido**, agravado por un corpus B1–C2 que está entre el 14 % y el 20 % de lo
que el propio proyecto se exige. La lectura correcta es «el producto cubre bien
A1–A2 y queda por construir la mitad superior»; la lectura incorrecta sería «el
tutor no enseña destrezas».

**Qué no demuestra este eje (honestidad de la medición):** mide **cobertura
declarada y volumen**, no **eficacia pedagógica**. Que existan las 9 modalidades,
el corpus y los scorers no demuestra que el alumno aprenda: no hay aprendices en
el bucle. Medir aprendizaje requiere alumnos reales y está en
`docs/audit/PARKED.md`.

## Regenerar / Verificar

```powershell
cd backend
# Evidencia del eje 2 (reproduce las tablas de este dossier).
.\.venv\Scripts\python.exe -m scripts.audit_dossier skill-coverage
# Tests de medición del eje 2.
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_coverage_v370.py
```

`skill-coverage` es de **solo lectura**: comprueba existencia de artefactos en
disco y **nunca** escribe en `backend/curriculum/` ni en `backend/data/`; solo
deja su par en `docs/audit/generated/`.

## Tests que respaldan

`backend/tests/test_ped_coverage_v370.py` (**10 tests**, verdes) — pinnean los
huecos medidos de modo que **cerrar un hueco hace fallar el test** y obliga a
re-auditar:

| Test | Qué pinnea |
|---|---|
| `test_every_mastery_modality_is_accounted_for` | las 9 modalidades en la matriz del dossier con sus 5 atributos (y anti-deriva contra el disco) |
| `test_reading_has_no_dedicated_scorer` | `services/reading.py` ausente con 15 objetivos / 18 checks, UI presente y corpus 0 |
| `test_mediation_is_declared_but_inert` | `mediation` declarada e inerte en los 5 planos |
| `test_mediation_requirements_cannot_be_met` | la matriz exige 24 evidencias de `mediation` (3/3/3/4/5/6) sin emisor |
| `test_interaction_has_no_evidence_channel` | sin canal ni competencias, pero con scorer, 66 ítems y sección en 6/7 niveles |
| `test_pronunciation_is_operative_but_outside_the_cefr_matrix` | funciona (canal, scorer, 120 ítems, UI) y no está en la matriz |
| `test_listening_corpus_meets_a1_a2_and_not_b1_c2` | objetivo declarado vs volumen real |
| `test_speaking_scenarios_extremes_are_thin` | A1 y C1 con 1 escenario |
| `test_no_recorded_human_audio` | `entries == []` y 513 ítems de listening, 499 con `audio_id` |
| `test_pre_a1_has_no_course` | `pre-a1` 0/7 y cobertura total 42/49 (85,7 %) |

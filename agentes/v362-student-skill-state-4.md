# Briefing de subagente — V3.62 (Student Skill State 4.0: modalidad × competencia)

> **Estado:** incremento **POR EJECUTAR**. Escrito sobre el árbol de `v3.61.0`
> (commit de release `1b4af42`, tag anotado `v3.61.0`).
>
> **Antes de empezar, verifica el estado real del árbol** (premisas 8 y 12):
> los nombres, líneas y cifras de abajo se citan del árbol de `v3.61.0` y pueden
> haber cambiado. Nada de lo que dice este documento sustituye a leer el código.
>
> **Nota de nomenclatura (importante).** La auditoría externa `S` de V3.60 pide
> «V3.62 — Student Skill State **3.0**», pero **ese nombre ya está usado**: V3.54
> es `Student Skill State 3.0` (`agentes/v354-student-skill-state-3.md`, columna
> `learning_profile.observed_skill_capacity`). Este incremento es **4.0** y no
> repite ni reinterpreta el alcance de V3.54.

## Rol

Ingeniero de backend (Student Model + Evidence Ledger + proyección de perfil).
Sin trabajo de UI más allá del espejo de tipos.

## Objetivo

Convertir el estado del alumno en **UN** modelo con eje de **competencia**,
alimentado por **toda** la evidencia disponible (no solo el drill léxico), sin
tocar ni una línea del camino que decide tareas.

Hoy conviven **dos** modelos del mismo alumno que **nunca se tocan**:

| Modelo | Ejes | Fuente | Consumidores | Problema |
| --- | --- | --- | --- | --- |
| **A · adaptativo (léxico)** | 4 `LEXICAL_SKILLS` × 4 `DIFFICULTY_DIMENSIONS` | **solo** `learning_evidence` con `target_type='lexicon'` | `domain/learner_state` → suelo por skill → `lexicon._capacity_by_skill` → ELV/planner → `transfer.context_for` | sus 4 «dimensiones» son **CARGA de contenido**, no competencia: `syntax` **no** es `grammar`; no hay eje fonológico, ortográfico ni pragmático; y no entra ninguna modalidad no léxica |
| **B · curricular** | 9 `MASTERY_SKILLS` × 4 estados pedagógicos | Student Model (`domain/academy.build_student_model` → `skills[].subskills`) | `/api/profile` (`competence_states`), mastery, adaptive | **no** tiene puerta de muestra espaciada por competencia, es **por nivel** (`objective_mastery` del tramo actual) y **no alimenta la adaptación** |

El P1-03 de `S` («Student Skill State demasiado agregado») apunta a esto. Ojo con
el matiz, porque **la mitad ya está cerrada**:

- **Ya cerrado desde V3.54 (no reclamarlo):** dentro del eje léxico, una capacidad
  **escrita** ya NO eleva una tarea **oral** (`floor_level_for_skill`,
  `skill_capacity`, gate de cobertura en `difficulty.challenge_for` /
  `select_by_difficulty` y `transfer.context_for`).
- **Lo que cierra V3.62:** que ese eje **no tiene competencias** y que **todo** lo
  que se mide fuera del drill léxico (grammar, listening por subdestreza,
  pronunciation, reading, writing, speaking) es **inerte** para cualquier decisión
  y para el propio estado.

## Estado de partida verificado (árbol `v3.61.0`)

Léelo tú antes de tocar nada; estas son las anclas reales:

- `services/evidence.py:136` — `LEXICAL_SKILLS = ("recall", "written_production",
  "spoken_production", "spontaneous_use")` con la nota explícita de que **NO
  incluye `receptive`** (`:132`), y `PRODUCTION_CHANNEL_SKILL:146`.
- `services/evidence.py:1095` — `observed_signals(rows)`: agrupa por
  `assessed_skill` (fallback `skill`) **restringido a `LEXICAL_SKILLS`** y por
  dimensión; devuelve `observed_samples` / `observed_days` / `observed_capacity`.
- `repositories/evidence.py:380` — `list_observed_rows(user_id,
  target_type="lexicon")`: el **único** lector del estado adaptativo, y solo lee
  `learning_evidence` con `success = 1`.
- `services/learner_skill.py` — `OBSERVED_MIN_SAMPLES = 2` / `OBSERVED_MIN_DAYS =
  2` (`:59`), `observed_skill_capacity` (`:70`, fuente de verdad),
  `observed_capacity` (`:152`, proyección legacy), `level_from_skill_capacity`
  (`:197`), `skill_coverage` (`:228`), `skill_capacity` (`:267`),
  `observed_skill_state` (`:314`).
- `domain/learner_state.py:52` — `learner_level_state(user_id)`: lectura O(1) de
  `learning_profile`; `floor_level_by_skill` / `floor_source_by_skill` sobre
  `LEXICAL_SKILLS` (`:90`). `empty_learner_level_state` (`:32`).
- `services/difficulty.py:48` — `DIFFICULTY_DIMENSIONS = ("lexical", "syntax",
  "discourse", "interaction")` (carga, **no** competencia) y `CEFR_CAPACITY:70`.
- `services/task_semantics.py:34` — `ASSESSMENT_MODES` incluye `receptive`
  **declarado y nunca producido**; `assessed_skill_for` / `evidence_skill_for`.
- `services/competence.py` — `STATE_ORDER = ("not_started", "developing",
  "functional", "demonstrated")` (`:37`), `PRODUCTION_SKILLS` (`:42`),
  `SUPPORT_SKILLS` (`:47`), `competence_state(entry, skill, level, route=)` (`:75`,
  **el gate que hay que reutilizar, no reinventar**), `competence_states` (`:172`).
- `services/mastery.py:84` — `MASTERY_SKILLS` (9) y `mastery_stage` /
  `review_interval_days`.
- `services/curriculum.py` — `CANONICAL_SKILLS` (`:23`, 7),
  `ASSESSABLE_SKILLS` (`:36`), `PERFORMANCE_SKILLS` (`:44`), `SUBSKILLS:54`
  (destreza → subdestrezas, **validado** por el cargador: todo `subskill` debe
  pertenecer a una destreza declarada del objetivo, `:514`), `Objective.subskills`
  (`:301`), `objective_index` (`:447`).
- `domain/academy.py:558` — `_annotated_profile`: **ya** puentea
  `listening_diagnostic(attempts)["subskills"]` y
  `speaking_diagnostic(rows)["criteria"]` dentro de `entry["subskills"]` del
  Student Model (`:578`), y `routes` para listening (`:584`).
  `build_student_model` (`:665`).
- `services/listening.py:2374` — `listening_diagnostic(rows)`;
  `:2223` `route_competence`; `services/listening.py:20` `LISTENING_SUBSKILLS`
  (**23**, no coincide con `SUBSKILLS["listening"]`, que tiene 19) y `:57`
  `SKILL_LAYER`.
- `services/speaking.py:892` / `services/writing.py:166` /
  `services/pronunciation.py:91` — `evidence_from_*` (evidencia de rendimiento).
- Tablas con evidencia **inerte** hoy para el estado: `academy_evidence`
  (`skill`/`objective_id`/`item_id`/`result`/`difficulty`/`created_at` + la columna
  migrada `evidence_kind` familiar/transfer/novel), `listening_attempts`
  (`skill`/`layer`/`correct`/`difficulty`/`realized_difficulty`/`task_type`/`score`/
  `response_time_ms`/`replay_count`), `pronunciation_attempts`
  (`expected`/`heard`/`score`/`level`) — ver `repositories/db.py`.
- Persistencia: `learning_profile` con `observed_capacity`,
  `observed_skill_capacity` (`db.py:275`), escritas por
  `domain/profile.py::get_profile_summary` (`:251`) y leídas por
  `repositories/profile.py` + `schemas/profile.py::LearningProfile` (`:104`).

## Decisiones de alcance (CERRADAS con el gerente)

1. **Modelo unificado, consumidores intactos.** Se construye, se persiste
   (aditivo) y se expone en `/api/profile`. **NO** se recablea el planner, ni
   `expected_learning_value`, ni `difficulty`, ni `transfer.context_for`, ni
   `learner_level_state`: la decisión de tareas sigue leyendo **exactamente** el
   estado de V3.61. El recableado es V3.63/V3.64.
2. **Todas las fuentes, con el MISMO rigor.** Entran `learning_evidence` (léxico),
   `academy_evidence`, `listening_attempts` y `pronunciation_attempts`, y **todas**
   pasan por la puerta de muestra espaciada (`OBSERVED_MIN_SAMPLES` /
   `OBSERVED_MIN_DAYS`); ninguna fuente estrena umbral propio.
3. **El eje de competencia NO se fabrica desde la carga.** `syntax`/`discourse`/…
   son **carga de dificultad** y **no** se traducen a competencias: mapear
   `syntax → grammar` inventaría evidencia que el alumno no ha producido. La
   competencia la declara **la fuente** (subdestrezas del objetivo de currículum,
   subdestreza de `listening_attempts`, criterios de rúbrica). El camino léxico
   aporta entradas **de modalidad** (con sus `dimensions`) y **sin** competencia.
4. **Reutilizar el gate, no reinventarlo.** Los 4 estados pedagógicos y sus
   umbrales salen de `services/competence.py` (score/confianza/evidencia/
   retención). Si aparece la tentación de un umbral nuevo, es señal de que el
   diseño se está desviando.
5. **Aditividad y degradación exacta.** Columna nueva idempotente con default
   `''`; sin evidencia el estado es `{}` y el resto del perfil y del drill es
   **byte a byte** el de V3.61.
6. **Determinismo.** Sin LLM, sin `random()`, sin `hash()` de proceso, sin reloj
   en la función pura: el JSON se serializa con `sort_keys=True` para que el
   contrato sea estable.
7. **SIN cambios de UI/i18n** (como V3.54–V3.61). Espejo de tipos TS opcional.

## Diseño

### A. Taxonomía declarada — `backend/services/skill_axis.py` (nuevo, puro)

Una **sola** fuente de verdad del vocabulario del estado, sin tocar los módulos
que ya tienen el suyo (V3.62 **mapea**, no refactoriza):

- `SKILL_MODALITIES: tuple[str, ...]` — modalidades canónicas del estado. Parte de
  `MASTERY_SKILLS` (9) y **declara explícitamente** cómo se sitúa el vocabulario
  léxico de V3.38 dentro de ella (`recall`, `written_production`,
  `spoken_production`, `spontaneous_use`), incluido el caso que hay que
  justificar por escrito: **`chat` es texto en esta app**
  (`PRODUCTION_CHANNEL_SKILL["chat"] = "spontaneous_use"`), así que
  `spontaneous_use` es una **condición** (sin guion) más que una modalidad.
  Documenta la decisión y fíjala con test.
- `MODALITY_OF: dict[str, str]` — mapeo **total** de cada cadena de cada
  vocabulario existente a una modalidad canónica: `LEXICAL_SKILLS`,
  `curriculum.CANONICAL_SKILLS`, `MASTERY_SKILLS`, valores de
  `PRODUCTION_CHANNEL_SKILL`, las cadenas de `academy_evidence.skill` que el
  árbol escribe de verdad (`pronunciation.py:110`, `speaking.py:920`,
  `writing.py:184`, y las de currículum), `LISTENING_SUBSKILLS` (→ `listening`),
  `SPEAKING_CRITERIA` (→ `speaking`), `WRITING_CRITERIA` (→ `writing`),
  `PRONUNCIATION_CRITERIA` (→ `pronunciation`).
- `COMPETENCES_BY_MODALITY: dict[str, tuple[str, ...]]` — competencias canónicas
  por modalidad, **derivadas** de `curriculum.SUBSKILLS` y de los vocabularios de
  rúbrica/subdestreza ya declarados. Regla dura: **toda** cadena que el estado
  vaya a consumir pertenece a esta tupla, y toda cadena fuera de ella va a
  `UNMAPPED: tuple[str, ...]` **con su motivo escrito** (mismo patrón que la nota
  de `receptive` de V3.13/V3.38). La discrepancia
  `LISTENING_SUBSKILLS` (23) vs `SUBSKILLS["listening"]` (19) se resuelve aquí de
  forma explícita, no por accidente.
- `competence_key(modality, competence)` y `canonical_competence(modality, raw)`:
  normalización determinista (casefold + strip) **sin** fuzzy matching.

**Test de totalidad (obligatorio):** para cada vocabulario del árbol, cada cadena
está en `MODALITY_OF` (y, si el estado la consume, en
`COMPETENCES_BY_MODALITY`), o en `UNMAPPED`. El test importa los vocabularios
reales, así que un vocabulario nuevo rompe el test en lugar de colarse.

### B. Agregador puro — `backend/services/skill_state.py` (nuevo, puro)

```text
FUENTES                          GATE                         ESTADO
learning_evidence (léxico)  ┐                            ┌  {modalidad: {competencia: {
academy_evidence            ├→ muestra espaciada (2/2) →┤      state, samples, days,
listening_attempts          │   + competence.state_for   │      score, confidence,
pronunciation_attempts      ┘   (MISMO gate de V3.19)   └      dimensions, sources }}}
```

- `skill_state_sources(...)` — normaliza cada fuente a **filas canónicas**
  `{modality, competence, occurred_on, success, score, dimensions, source}`. Una
  fila por hecho observable; nunca agrega dos fuentes en una fila.
  - `academy_evidence`: `skill` → modalidad; `objective_id` + `level_id` →
    objetivo de currículum → `subskills` (una fila por subdestreza declarada);
    sin `objective_id`, competencia `""`.
  - `listening_attempts`: `skill` → competencia de `listening` vía
    `canonical_competence`; filas sin `skill` → competencia `""`; `score` cuando
    `task_type` sea dictado/shadowing, `correct` para MCQ.
  - `pronunciation_attempts`: modalidad `pronunciation`, competencia `""`,
    `score = score/100` si el esquema lo declara así (**verifícalo**, no lo
    asumas), día de `created_at`.
  - `learning_evidence` (léxico): proyección **exacta** de
    `services.evidence.observed_signals`; modalidad mapeada desde
    `assessed_skill`/`skill`, competencia `""` y `dimensions` con la carga
    observada. Los valores deben ser **idénticos** a `observed_skill_capacity`
    (test de paridad).
- `skill_state(rows)` — agrupa por `(modality, competence)`, aplica la muestra
  espaciada (mínimos de `learner_skill`), calcula `score`/`confidence` con la
  misma regla que ya use el Student Model cuando exista (no inventes una nueva) y
  deriva `state` con `competence.competence_state(...)`. Devuelve
  `{modality: {competence: entry}}` con **todas** las modalidades canónicas
  presentes (`{}` si no hay evidencia) — misma convención que
  `floor_level_by_skill`, para que el contrato no cambie de forma.
- `skill_state_summary(state)` — derivado para el contrato/UI: por modalidad,
  `{state, competences_with_sample, coverage}`. Es un **resumen**, nunca la
  fuente de verdad (mismo patrón que `observed_capacity` vs
  `observed_skill_capacity`).
- `empty_skill_state()` — estado neutro con la MISMA forma.

### C. Persistencia aditiva y contrato

- `repositories/db.py`: `skill_state TEXT NOT NULL DEFAULT ''` en el `CREATE
  TABLE learning_profile` y en la lista **idempotente** de `ALTER TABLE` (patrón
  de V3.52/V3.54; dos `init_db()` seguidos no duplican nada).
- `repositories/profile.py`: **escritor dedicado** (`set_skill_state`) y lectura
  en `get_profile`. No toques la firma del escritor caliente `set_level_state`
  más de lo imprescindible.
- `domain/profile.py::_compute_profile`: calcula el estado **una vez por refresco**
  (con las cuatro fuentes ya cargadas ahí: `student_model["skills"]`,
  `list_observed_rows`, `listening_repo.list_attempts`, evidencia de
  pronunciación) y lo devuelve; `get_profile_summary` lo persiste con
  `json.dumps(..., sort_keys=True)`.
- `schemas/profile.py::LearningProfile`: `skill_state: dict[str, dict[str, dict]]`
  (o el tipo que corresponda) + `frontend/src/types/api.ts`. **Sin** claves
  existentes alteradas.

### D. Frontera (lo que NO se toca) y su prueba

La invariante central de la release: **el camino que decide tareas es
byte-identical con y sin el estado nuevo**. Test explícito: con un `skill_state`
rico persistido, `learner_level_state`, `lexicon._capacity_by_skill`,
`planner.expected_learning_value` / `select_task_by_elv`, `transfer.context_for` y
el payload del drill devuelven **exactamente** lo de V3.61.

## Plan de implementación (tests-first)

1. `backend/tests/test_skill_state_v362.py` — escribe **primero** los tests de las
   secciones «Criterios de aceptación»: totalidad de la taxonomía, puerta
   espaciada, no-invención de competencias, aislamiento entre modalidades, paridad
   del gate con `competence`, paridad del léxico con `observed_skill_capacity`,
   determinismo, degradación neutra, migración idempotente, contrato aditivo y
   **no-regresión del camino de decisión**.
2. `services/skill_axis.py` (taxonomía + mapeos + `UNMAPPED` documentado).
3. `services/skill_state.py` (fuentes → filas → estado + resumen + vacío).
4. `repositories/db.py`, `repositories/profile.py`, `domain/profile.py`,
   `schemas/profile.py`, `frontend/src/types/api.ts`.
5. Bump `3.62.0` (config/README/CHANGELOG/PLAN/package.json), `release-notes-v3.62.0.md`
   y `agentes/v362-student-skill-state-4.md` pasa a estado EJECUTADO.
6. Cierre: `ruff`, `pytest`, `launcher/tests`, `tsc`, `vitest`, `build`,
   `check_release_consistency`, `check_beta_v3`, `content_validation`,
   `transfer_validation` (debe seguir en **20 familias / 1020 superficies / 0
   errores**: esta release NO toca el banco), commit, push, **CI 6/6** y tag
   anotado `v3.62.0`.

## Criterios de aceptación

- **Taxonomía total y probada:** ninguna cadena de ningún vocabulario del árbol
  queda sin mapear o sin declarar en `UNMAPPED` con motivo. Un vocabulario nuevo
  rompe el test.
- **Puerta espaciada única:** 2 éxitos en 2 días naturales distintos por
  `(modalidad, competencia)`; con 1 muestra o 1 día **no** hay entrada (ni
  bloquea las demás).
- **Ninguna competencia inventada:** un alumno solo-léxico produce entradas de
  modalidad con `dimensions` y `competence == ""`; **no** aparece ninguna
  competencia (`grammar`, `spelling`, `sounds`…) que la evidencia no declare.
- **Aislamiento real entre modalidades:** evidencia escrita no crea ni modifica
  ninguna entrada de `speaking`/`listening`/`pronunciation` (el defecto P1-03,
  ahora a granularidad de competencia; no confundir con el cierre de V3.54).
- **Gate reutilizado:** los 4 estados y sus umbrales coinciden con
  `services/competence.py` (test de paridad, no copia de constantes).
- **Paridad del léxico:** los `dimensions` del camino léxico son idénticos a
  `observed_skill_capacity`/`learner_skill` (sin re-derivar).
- **Determinismo:** mismas filas → mismo `skill_state` (JSON idéntico con
  `sort_keys=True`); sin `hash()`/`random`/`time` en la función pura.
- **Degradación neutra:** sin evidencia, `skill_state == {}` y **todo** el payload
  de `/api/profile` coincide con V3.61.
- **Cero recableado:** los consumidores de decisión devuelven byte a byte lo de
  V3.61 con un `skill_state` rico presente.
- **Aditivo e idempotente:** columna con default `''`, filas legacy `''`,
  `init_db()` repetible, sin `GENERATOR_VERSION`, sin migración explícita.
- **Verificación completa en verde** y CI **6/6** sobre el commit de release.

## Restricciones

- **Sin LLM en el camino de la evidencia** (premisa 21): el estado sale de
  agregación determinista de hechos registrados.
- **No tocar:** `expected_learning_value`, `planner`, `difficulty` (incluido
  `CEFR_CAPACITY` y `select_by_difficulty`), `transfer.py` (banco, guard,
  identidad de instancia, `context_id = FAMILIA`), `transfer_state` y sus
  umbrales, `evidence.observed_signals` (se **consume**, no se modifica),
  `academy_evidence`/`listening_attempts`/`pronunciation_attempts` (se **leen**,
  no se migran), FSRS, la escalera de recall y la UI/i18n.
- **No refactorizar los vocabularios existentes** de otros módulos: V3.62
  **mapea** y **declara**; la consolidación de los ~15 vocabularios llega cuando
  los consumidores lo pidan (y con test). Si mapear algo te obliga a cambiar un
  módulo, para y replantea con el gerente.
- **No inventar umbrales, scores ni niveles**: reutiliza
  `learner_skill.OBSERVED_*` y `competence.STATE_ORDER`/`readiness`; un estado
  sin muestra se declara `not_started`/ausente, **nunca** un nivel por defecto.
- No añadir jobs de CI (el gate de V3.61 sigue dentro del job Backend).
- Mantén los módulos puros sin I/O, sin reloj y sin aleatoriedad; el I/O vive en
  `repositories`.

## Fuera de alcance

- **Recablear la decisión de tareas** al eje de competencia (ELV/planner/ELU por
  modalidad): V3.63/V3.64.
- **Observed Task Difficulty 2.0** (`declared → served → observed` empírico;
  V3.63), **rotación adaptativa** y **Planner 3.0** (V3.64).
- **Instance Generator 2.0** (V3.65), WSD real y el Sense Engine.
- La división de `transfer.py` en paquete y el arrastre de V3.59
  (contrato/prompt de generación de sentidos con bump de `GENERATOR_VERSION` y la
  ponderación de la adecuación en `transfer_confidence`).
- Cualquier cambio de UI más allá del espejo de tipos; no se añaden pantallas ni
  etiquetas.

## Salida esperada

- Diff de los ficheros de backend tocados, nuevos tests, contrato actualizado
  (backend + espejo TS), version bump y `release-notes-v3.62.0.md`.
- **Evidencia de verificación** pegada en texto: los comandos de la sección de
  cierre con su resultado, incluido el **no-op** probado del camino de decisión y
  el `transfer_validation` intacto.
- Un párrafo de honestidad: qué **NO** cierra V3.62 (la decisión de tareas sigue
  ciega al eje nuevo; el estado en sí no cambia ninguna tarea todavía).
- Si algo del briefing no cuadra con el árbol real, **para y repórtalo** antes de
  implementar (premisa 8).

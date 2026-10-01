# v3.62.0 — Student Skill State 4.0 (modalidad × competencia)

> Release **SIN migración explícita de BD** (columna aditiva idempotente), **SIN
> bump de `GENERATOR_VERSION` y SIN cambios de UI** que unifica los **dos** modelos
> del alumno que hasta V3.61 convivían sin tocarse:
>
> - **A · adaptativo (léxico)** — 4 `LEXICAL_SKILLS` × 4 `DIFFICULTY_DIMENSIONS`,
>   cuya única fuente es `learning_evidence` con `target_type='lexicon'` y que
>   alimenta el ELV, el planner y `transfer.context_for`.
> - **B · curricular** — 9 `MASTERY_SKILLS` × 4 estados pedagógicos, que solo
>   llegaba a `/api/profile`.
>
> El P1-03 de la auditoría `S` («Student Skill State demasiado agregado») apunta a
> que las cuatro «dimensiones» del modelo A son **CARGA de contenido, no
> competencia** (`syntax` **no** es `grammar`; no hay eje fonológico, ortográfico
> ni pragmático) y a que **toda** la evidencia no léxica (grammar, listening por
> subdestreza, pronunciation, reading, writing, speaking) es **inerte** para el
> estado. V3.62 las unifica en **UN** estado `{modalidad: {competencia: entry}}`
> alimentado por las **cuatro** fuentes con el **mismo** rigor.
>
> **La decisión de tareas NO se toca**: ELV, planner, `difficulty` y
> `transfer.context_for` siguen leyendo **exactamente** el estado de V3.61, y se
> prueba **byte a byte** con un `skill_state` rico persistido.

## Contexto

La auditoría `S` de V3.60 aprobó la arquitectura y dejó tres P1. El P1-03 se titula
«Student Skill State demasiado agregado» y su matiz importa, porque **la mitad ya
está cerrada**:

- **Ya cerrado desde V3.54 (no se re-reclama):** dentro del eje léxico, una
  capacidad **escrita** ya NO eleva una tarea **oral** (`floor_level_for_skill`,
  `skill_capacity`, el gate de cobertura de `difficulty.challenge_for` y
  `transfer.context_for`).
- **Lo que cierra V3.62:** que ese eje **no tiene competencias** y que todo lo que
  se mide fuera del drill léxico es **inerte** para cualquier decisión y para el
  propio estado.

Nota de nomenclatura: `S` lo llama «Student Skill State 3.0», pero **ese nombre ya
está usado** — V3.54 es `Student Skill State 3.0`
(`agentes/v354-student-skill-state-3.md`, columna
`learning_profile.observed_skill_capacity`). Este incremento es **4.0** y no repite
ni reinterpreta el alcance de V3.54.

## Cambio

### A. Taxonomía declarada — `services/skill_axis.py` (nuevo, puro)

Una **sola** fuente de verdad del vocabulario del estado que **mapea** los
vocabularios existentes sin refactorizarlos (V3.62 mapea y declara; la
consolidación de los ~15 vocabularios del árbol llega cuando los consumidores lo
pidan, y con test):

- `SKILL_MODALITIES` — las 9 modalidades canónicas, las de `MASTERY_SKILLS`. El eje
  de competencia vive **dentro** de la modalidad, nunca al revés.
- `MODALITY_BY_VOCABULARY` — mapa **preciso** por vocabulario
  (`evidence.LEXICAL_SKILLS`, `evidence.PRODUCTION_CHANNEL_SKILL`,
  `curriculum.CANONICAL_SKILLS`, `mastery.MASTERY_SKILLS`, `curriculum.SUBSKILLS`,
  `listening.LISTENING_SUBSKILLS`, `listening.SKILL_LAYER`,
  `speaking.SPEAKING_CRITERIA`, `writing.WRITING_CRITERIA`,
  `pronunciation.PRONUNCIATION_CRITERIA`, `task_semantics.ASSESSMENT_MODES`), y su
  aplanado `MODALITY_OF` con la precedencia declarada. El aplanado es **de
  diagnóstico y de totalidad**: varias cadenas son legítimamente ambiguas
  (`AMBIGUOUS_STRINGS`: `register`, `discourse`, `nuance`, `pragmatics`,
  `coherence`, `vocabulary`, `grammar`, `pronunciation`, `spelling`… pertenecen a
  VARIAS destrezas), así que el estado **nunca** resuelve una competencia con él:
  eso es trabajo de `COMPETENCES_BY_MODALITY`, que es **por modalidad**.
  La totalidad de `LEXICAL_SKILLS` se verifica **en tiempo de import** (fallo
  ruidoso): una skill del ledger sin modalidad declarada dejaría evidencia real
  fuera del estado.
- `COMPETENCES_BY_MODALITY` — competencias canónicas por modalidad, **derivadas**
  de `curriculum.SUBSKILLS` y de los vocabularios de rúbrica ya declarados. Regla
  dura: toda cadena que el estado consuma pertenece a esta tupla; sin coincidencia
  el consumidor declara competencia `""` y **nunca** inventa una.
- `canonical_competence(modality, raw)` — normalización determinista (casefold +
  strip) y **sin** fuzzy matching. `modality_for(raw)` es el diagnóstico.
- `objective_competences_index()` — índice `(level_id, objective_id) →
  (subskills, thresholds)` del currículum, con `lru_cache`. Contenido **declarado**
  (los JSON del currículum), no datos de alumno: el agregador puro lo recibe como
  argumento.

Decisiones declaradas (y por qué):

- `recall → vocabulary`: recuperar la forma desde el significado es práctica léxica
  sin canal de producción propio.
- `written_production → writing` y `spoken_production → speaking`: el canal **sí**
  está declarado en `PRODUCTION_CHANNEL_SKILL`.
- **`spontaneous_use → interaction`**: es una **condición** (sin guion) más que una
  modalidad, y en esta app su único emisor es `chat`, que es **TEXTO**
  (`PRODUCTION_CHANNEL_SKILL["chat"] = "spontaneous_use"`). No se puede declarar
  producción oral sin canal oral, así que se sitúa como interacción escrita
  espontánea y **no** como `speaking`.
- `interaction` y `mediation` se declaran **sin competencias**: `mediation` no
  tiene descomposición declarada en el currículum e `interaction` aparece como
  **subdestreza** de `speaking`, no como destreza con subdestrezas propias. Se
  dejan vacías en lugar de inventarlas.
- **`receptive` queda en `UNMAPPED` con su motivo escrito**: existe en
  `ASSESSMENT_MODES` para que la taxonomía admita el MCQ de Recognition el día que
  escriba evidencia, pero hoy es **informativo** (V3.13) y no toca el ledger.
  Mapearlo sugeriría una modalidad medida que no existe.
- **Discrepancia `LISTENING_SUBSKILLS` vs `SUBSKILLS["listening"]`**: se resuelve
  como **UNIÓN** explícita y probada. El currículum declara la descomposición
  «can-do» de la destreza (validada por el cargador) y el motor de listening
  **servido** declara además subdestrezas que graba de verdad en
  `listening_attempts.skill` (`numbers`, `note_taking`, `prediction`,
  `sequencing`). Descartar cualquiera de las dos dejaría evidencia real fuera del
  estado o competencias curriculares sin puerta.

### B. Agregador puro — `services/skill_state.py` (nuevo, puro)

```text
FUENTES                          FILAS                GATE              ESTADO
learning_evidence (léxico)  ┐                    ┌ muestra espaciada ┐ {modalidad:
academy_evidence            ├→ 1 fila por  ─────┤  2/2 (V3.54)      ┤  {competencia:
listening_attempts          │   HECHO observable  + competence.       │   entry}}
pronunciation_attempts      ┘                    └ competence_state ┘
```

- `skill_state_sources(lexicon=, academy=, listening=, pronunciation=,
  objectives=)` — cada fuente a **filas canónicas** `{modality, competence,
  occurred_on, occurred_at, success, score, dimensions, source, kind, production}`
  (una fila por hecho observable; **nunca** agrega dos fuentes en una fila):
  - **`learning_evidence`** — proyección **exacta** de
    `services.evidence.observed_signals`: `assessed_skill` → `skill`,
    `difficulty.earned_difficulty` y descarte de fallos y de vectores vacíos.
    Modalidad mapeada, competencia `""` y `dimensions` con la carga acreditada.
  - **`academy_evidence`** — `skill` → modalidad; `(level_id, objective_id)` →
    objetivo del currículum → **una fila por subdestreza declarada** (restringida a
    las que declara la modalidad de esa fila, para no inventar: `spelling` no es una
    competencia de `speaking`). El **éxito** lo declara el umbral del propio
    objetivo (`Objective.threshold`), el que ya usa el mastery. Sin objetivo
    resoluble ni subdestrezas la fila va a competencia `""` y **no acredita éxito**
    (hueco F-K3: speaking assessment y misión escriben `objective_id=''`); es la
    **misma** frontera que tiene hoy el Student Model, no una regla nueva.
  - **`listening_attempts`** — modalidad `listening`, competencia = subdestreza
    declarada por el intento **validada** contra su vocabulario (una no declarada
    deja `""` en lugar de inventarse); el acierto es el `correct` que el motor ya
    decide (incluye el umbral declarado de dictado/shadowing) y el `score` continuo
    se conserva cuando lo hay.
  - **`pronunciation_attempts`** — modalidad `pronunciation`, competencia `""` (la
    tabla no declara criterio, así que no se le supone ninguno) y `score = score /
    100` (el esquema guarda 0..100 con `PASS_THRESHOLD = 80`, **verificado** en el
    código, no asumido).
- `skill_state(rows, level=, now=)` — agrupa por `(modality, competence)`, aplica la
  **misma** puerta espaciada (`learner_skill.OBSERVED_MIN_SAMPLES` /
  `OBSERVED_MIN_DAYS`: **2 éxitos en 2 días naturales distintos**) y deriva el
  estado pedagógico con `services.competence.competence_state(...)` — **el gate
  reutilizado, sin umbrales nuevos**. La entrada expone `state`, `samples`, `days`,
  `score`, `confidence`, `dimensions` (carga por dimensión, con la misma puerta por
  dimensión de V3.54) y `sources`.
- `skill_state_summary(state)` — **derivado**, nunca fuente de verdad: por
  modalidad, `{state (el más alto), competences_with_sample, coverage{covered,
  total}}`. `interaction`/`mediation` no declaran competencias, así que su
  cobertura no divide por cero.
- `empty_skill_state()` / `normalize_skill_state(value)` — estado neutro con la
  **misma forma** (todas las modalidades presentes) y lectura tolerante del JSON
  cacheado (Mapping o texto; basura → estado neutro; una entrada que no sea objeto
  se descarta). Nunca lanza.

### C. Persistencia y contrato aditivos

- `repositories/db.py`: `skill_state TEXT NOT NULL DEFAULT ''` en el `CREATE TABLE
  learning_profile` y en la lista **idempotente** de `ALTER TABLE` (patrón de
  V3.52/V3.54): dos `init_db()` seguidos no duplican nada y las filas legacy quedan
  con `''`.
- `repositories/profile.py`: **escritor dedicado** `set_skill_state(user_id,
  skill_state)` (no toca ninguna otra columna ni la firma del escritor caliente
  `set_level_state`) y lectura en `get_profile`.
- `repositories/pronunciation.py`: lector nuevo `list_attempts(user_id)` (solo
  lectura; la tabla no se migra ni se toca) que alimenta la cuarta fuente.
- `domain/profile.py::_compute_profile`: calcula el estado **una vez por refresco**
  con las cuatro fuentes ya cargadas ahí y lo devuelve;
  `get_profile_summary` lo cachea con `json.dumps(..., sort_keys=True)`.
- `schemas/profile.py::LearningProfile` + `frontend/src/types/api.ts`:
  `skill_state` y `skill_state_summary`. **Ninguna** clave existente se altera y no
  hay cambio visual ni de i18n.

### D. La frontera y su prueba

La invariante central de la release: **el camino que decide tareas es
byte-identical con y sin el estado nuevo**. Con un `skill_state` rico persistido:

- `domain.learner_state.learner_level_state` — idéntico (y su
  `observed_skill_capacity` sigue saliendo de SU columna).
- El payload del drill léxico (`lexicon.review_queue_item`, con `task`, `activity`
  y `learning_value`) — idéntico.
- `planner.select_task_by_elv` + `planner.expected_learning_value` — idénticos, y el
  test comprueba que el argmax **sí** discrimina (margen comparable, no `None`),
  para no quedarse en un no-op vacío.
- `transfer.context_for` — idéntico, con el banco intacto.
- Y un test **estructural** fija que ningún módulo del camino de decisión
  (`planner`, `difficulty`, `transfer`, `lexicon`, `learner_state`,
  `domain/vocabulary`) menciona siquiera `skill_state`.

## Tests

Nuevo `backend/tests/test_skill_state_v362.py` (**31**), escrito **antes** del
código:

- **Taxonomía total y probada** — importa los vocabularios **reales** y falla si una
  cadena nueva no está mapeada ni en `UNMAPPED` con motivo (un vocabulario nuevo
  rompe la suite en lugar de colarse), incluida la unión explícita de listening y
  que lo declarado existe de verdad en el árbol.
- **No invención** — un alumno solo-léxico produce entradas de modalidad con
  `dimensions` y `competence == ""`; **no** aparece ninguna competencia que la
  evidencia no declare. La misma cadena se resuelve **por modalidad** (`register`
  existe en listening/speaking/writing, no en pronunciation).
- **Puerta espaciada única** — 2 éxitos en 2 días; con 1 muestra, 2 el mismo día o
  fallo + acierto **no** hay entrada, y una clave sin muestra **no** bloquea a las
  demás.
- **Aislamiento entre modalidades** — la evidencia escrita no crea ni modifica
  entradas de `speaking`/`listening`/`pronunciation`/`interaction`.
- **Gate reutilizado (paridad, no copia)** — el estado coincide con
  `competence.competence_state` sobre su propia entrada.
- **Paridad del léxico** — los `dimensions` del camino léxico son **idénticos** a
  `learner_skill.observed_skill_capacity` (calculado por separado) y a
  `observed_skill_capacity` servido por el perfil.
- **Determinismo** — mismas filas → mismo JSON (`sort_keys=True`); sin `now` la
  función no lee el reloj.
- **Degradación neutra** — sin evidencia el estado es el neutro y la caché queda
  escrita con él; el contrato aditivo conserva **todas** las claves de V3.61.
- **Migración idempotente** — columna con default `''`, `init_db()` repetible y el
  escritor dedicado no pisa `estimated_level` ni `cefr_level`.
- **No-regresión del camino de decisión** — los cinco puntos de la frontera, más el
  guard estructural.

## Verificación

```
backend:  ruff check .                        → All checks passed
backend:  pytest -q                           → 2404 passed
launcher: pytest launcher/tests -q            → 75 passed
frontend: npm run test                        → 76 ficheros / 651 passed
frontend: npm run build                       → tsc + vite build OK
scripts:  python scripts/check_release_consistency.py   → OK: Release consistency (3.62.0)
scripts:  python scripts/check_beta_v3.py     → OK: Beta V3.0 gate
backend:  python backend/scripts/content_validation.py  → OK=True quality=True
backend:  python -m scripts.transfer_validation         → 20 familias / 1020 superficies / 0 errores
```

## Cierre

**V3.62.0 CERRADA y publicada (2026-09-14):** commit de release `f4bcee2`, **CI
6/6** en el run
[34839206611](https://github.com/jvelasca/english-tutor/actions/runs/34839206611)
—Release consistency `3.62.0`, Backend (`ruff` + `pytest` + el paso
`python -m scripts.transfer_validation`), Frontend (`tsc` + `vitest` **76
ficheros/651 tests** + `build`), Playwright E2E, Beta V3.0 gate y Content
validation— y etiqueta anotada `v3.62.0` creada y empujada.

No-op probado del camino de decisión: con un `skill_state` **rico** persistido
(ajeno a la evidencia real) `learner_level_state`, el payload del drill, el argmax
de ELV y `transfer.context_for` devuelven **exactamente** lo de V3.61; los tests
`test_decision_path_is_blind_to_the_persisted_state`,
`test_elv_and_argmax_are_unchanged_by_the_new_column`,
`test_transfer_context_is_unchanged_by_the_new_column` y
`test_decision_modules_do_not_mention_the_new_state` lo fijan.

## Honestidad: qué NO cierra V3.62

V3.62 construye, persiste y expone el modelo unificado del alumno, pero **el estado
nuevo todavía no cambia ninguna tarea**: ELV, planner y `transfer.context_for`
siguen leyendo el estado de V3.61 y eso es **por diseño** (alcance cerrado con el
gerente). Tampoco inventa un eje CEFR por competencia (`dimensions` es carga
observada 1..5 y `state` sale del gate), ni declara éxito donde la fuente no lo
declara (las filas de `academy_evidence` sin objetivo resoluble no cruzan la
puerta), ni traduce carga a competencia (`syntax` sigue sin ser `grammar`). El
recableado de la decisión de tareas al eje de competencia es **V3.63/V3.64**.

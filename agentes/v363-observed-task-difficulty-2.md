# Briefing de subagente — V3.63 (Observed Task Difficulty 2.0 y honestidad del Student Skill State)

> **Estado:** briefing entregado 2026-09-14; **EJECUTADO y CERRADO** como
> **release `v3.63.0`** (2026-09-14).
> **Qué cierra:** la deuda de honestidad que dejó V3.62 declarada por escrito, más
> los hallazgos P1-02 y P2-11/P2-12/P2-13/P2-14/P2-18/P2-19/P2-20 de la auditoría
> profunda de V3.62 (`docs/audit/U-AUDITORIA-TOTAL-V362.md`).
> **Qué NO cierra (compromiso fechado):** **P1-01** — el recableado de la decisión
> de tareas — es **V3.64**, con **Decision Projection + Planner 3.0**.
> **Verificación local:** `pytest` **2430 passed**, `ruff` limpio, launcher **75**,
> `tsc` OK, `vitest` **651** (76 ficheros), `build` OK,
> `check_release_consistency` **3.63.0**, `check_beta_v3`/`content_validation` OK y
> `transfer_validation` OK (esta release NO toca el banco). Registrada en
> `release-notes-v3.63.0.md`.

## Rol

Backend (núcleo puro + persistencia aditiva + contrato) con espejo mínimo de tipos
en el frontend. Sin trabajo visual ni de i18n.

## Objetivo

Construir la capa **empírica** de dificultad de tarea y cerrar las **pérdidas de
información** del Student Skill State 4.0, todo **aditivo** y **sin recablear la
decisión de tareas**. La frontera es la invariante central del incremento: con el
estado nuevo rico persistido, `learner_level_state`, el payload del drill, el
argmax de ELV y `transfer.context_for` devuelven **exactamente** lo de V3.62, y el
guard estructural (`backend/tests/test_skill_state_v362.py`) sigue **verde**.

## Estado de partida verificado (árbol v3.62.0, `f4bcee2`)

- `services/skill_axis.py` — taxonomía declarada. `LEXICAL_MODALITY = {recall:
  vocabulary, written_production: writing, spoken_production: speaking,
  spontaneous_use: interaction}`; `ASSESSMENT_MODE_MODALITY = {written: writing,
  spoken: speaking}` y `receptive` en `UNMAPPED` con motivo;
  `COMPETENCES_BY_MODALITY` derivada de `curriculum.SUBSKILLS` + rúbricas;
  `canonical_competence` (casefold + strip, sin fuzzy).
- `services/skill_state.py` — fila canónica en `_row` (`modality`, `competence`,
  `occurred_on`, `occurred_at`, `success`, `score`, `dimensions`, `source`,
  `kind`, `production`); adaptadores `_lexicon_rows` (`:141`), `_academy_rows`
  (`:176`, expansión 1 fila → N competencias en `:222-235`), `_listening_rows`
  (`:240`), `_pronunciation_rows` (`:268`); puerta en `_entry` (`:361-421`, 2
  éxitos / 2 días naturales distintos, `confidence = successes/attempts`).
- `services/difficulty.py` — `DIFFICULTY_DIMENSIONS`, `normalize_vector`,
  `normalize_delta`, `apply_delta`, `format_vector`/`parse_vector`,
  `declared_difficulty` (`:315`), `observed_task_difficulty` (`:343`, descuento
  DECLARADO por andamiaje), `task_difficulty_vectors` (`:367`), `earned_difficulty`
  (`:407`), `fit`, `challenge_for`, `select_by_difficulty`.
- `services/planner.py` — `SLOW_RECALL_MS = 8000.0` (`:57`),
  `LATENCY_CEILING_MS = 20000.0` (`:60`), `SUCCESS_BY_MARGIN` (`:80`),
  `success_probability`, `capacity_margin`, `expected_learning_value`,
  `select_task_by_elv`.
- `services/competence.py` — `STATE_ORDER`, `competence_state(entry, skill,
  level, route=None)` (`:71-170`), `READINESS_MIN_EVIDENCE = 3`,
  `READINESS_MIN_CONFIDENCE = 0.6`, `READINESS_MINIMUMS`,
  `READINESS_DEFAULT_MINIMUM = 0.7` (de `services/adaptive.py`).
- Persistencia: `learning_profile.skill_state TEXT NOT NULL DEFAULT ''` (`db.py`
  CREATE `:276` y lista idempotente `:307`); escritor dedicado
  `profile_repo.set_skill_state` (`repositories/profile.py:97`); la caché SOLO se
  escribe desde `domain.profile.get_profile_summary` (`:283-315`).
- Lectores de las cuatro fuentes: `evidence.list_observed_rows` (`:380`, **no**
  selecciona `id`/`activity_id`/`context_id`), `academy.list_evidence` (`:404`,
  sí devuelve `id`/`objective_id`/`item_id`/`activity_id`/`context_id`/
  `support_level`/`evidence_kind`), `listening.list_attempts` (`:93`, **no**
  selecciona `id`; sí `response_time_ms`/`replay_count`/`speed_used`/
  `transcript_used`/`layer`/`score`), `pronunciation.list_attempts` (`:26`, **no**
  selecciona `id`).
- Frontera vigente: `test_skill_state_v362.py:841-856` exige que ningún módulo del
  camino de decisión (`services/planner.py`, `services/difficulty.py`,
  `services/transfer.py`, `services/lexicon.py`, `domain/learner_state.py`,
  `domain/vocabulary.py`) contenga la subcadena `skill_state`.

## Decisiones de alcance (CERRADAS)

1. **Orden de los releases.** Primero V3.63 (este briefing) y **después** V3.64
   (`Decision Projection + Planner 3.0`). Precipitar el recableado convertiría el
   Student Skill State en una capa de heurísticas superpuestas.
2. **La caché no es una segunda verdad.** La futura proyección de V3.64 se
   calculará desde las **MISMAS filas canónicas** que el estado, nunca desde el
   JSON cacheado.
3. **Ningún umbral nuevo.** Todo lo empírico se expresa con **tablas declaradas**
   y con las constantes ya existentes (`OBSERVED_MIN_SAMPLES`, `OBSERVED_MIN_DAYS`,
   `SUPPORT_DISCOUNT_STEPS`, `SLOW_RECALL_MS`, `LATENCY_CEILING_MS`).
4. **Un dedup solo puede acreditar menos.** La identidad de evidencia se usa para
   **no contar de más**; nunca para elevar el estado.
5. **No se inventa rúbrica de pronunciación.** Solo se conecta el criterio que la
   ruta ya puntúa y persiste (`academy_evidence.item_id`).
6. **La dificultad empírica es una MEDIDA, no un parámetro ajustado.** Sin muestra
   espaciada no se declara nada.

## Diseño

### A. Identidad de evidencia y ocasiones (P2-13)

- `_row` gana `evidence_id`, `activity_id`, `assessment_id` (los que la fuente
  declare; `""` si no declara) y `occasion_key(row)`.
- Nuevo lector aditivo de identidad: `evidence.list_observed_rows` añade `id`,
  `activity_id`, `context_id`; `listening.list_attempts` y
  `pronunciation.list_attempts` añaden `id`.
- `_entry` separa `samples` (éxitos), `days` (días naturales) y **`occasions`**
  (ocasiones distintas). Un mismo hecho que expande a N competencias cuenta **1**
  ocasión. `evidence_count` del gate sigue contando intentos como hasta ahora (no
  se toca la semántica del gate reutilizado).
- La degradación es **exacta**: si ninguna fila declara identidad,
  `occasions == samples` y el estado es byte a byte el de V3.62.

### B. Canal observado (P1-02)

- `skill_axis.MODALITY_BY_ASSESSED_CHANNEL`: mapa declarado
  `(skill, assessment_mode) → modalidad`, derivado de `LEXICAL_MODALITY` y
  `ASSESSMENT_MODE_MODALITY`, con las dos entradas explícitas:
  `("spontaneous_use", "written") → "interaction"` (el `chat` de hoy) y
  `("spontaneous_use", "spoken") → "speaking"` (el día que exista voz).
- `_lexicon_rows` resuelve el canal desde la actividad declarada de la fila
  (`task_semantics.assessment_mode_for` / `activity_from_activity_id`) y solo cae
  al mapa por skill cuando la fila no declara canal: **degradación exacta a
  V3.62**.

### C. Observed Task Difficulty 2.0 (P2-20, núcleo)

Nuevo módulo puro `backend/services/observed_difficulty.py` (sin I/O, sin reloj,
nunca lanza) sobre las filas canónicas:

- `served_ceiling(rows)` — mayor carga SERVIDA por dimensión.
- `credited_ceiling(rows)` — mayor carga ACREDITADA, reutilizando
  `difficulty.earned_difficulty`; su distancia al servido es la dependencia de
  andamiaje.
- `experienced_load(row)` — carga servida modulada por coste OBSERVADO ya
  persistido (`response_time_ms`, `error_type`, `replay_count`, `speed_used`,
  `transcript_used`), con tablas declaradas sobre `SLOW_RECALL_MS`/
  `LATENCY_CEILING_MS`; un hecho desconocido **no** modula (no se inventa).
- `observed_task_difficulty_2(rows)` — `{served_ceiling, credited_ceiling,
  experienced_load, success_rate, samples, days}`, con la MISMA puerta espaciada
  de V3.54.
- Se expone como **clave aditiva de la entrada** del estado (sin migración: viaja
  en el JSON de `learning_profile.skill_state`).

### D. Confianza de evaluación (P2-19)

- `assessment_confidence(row)` → banda declarada (`low`/`medium`/`high`) +
  `reasons`, derivada SOLO de hechos persistidos: canal, `support_level`,
  `context_instance` en transfer y, en listening, `speed_used`/`transcript_used`/
  `replay_count`/`layer`. Hechos desconocidos → banda mínima.
- La `confidence` **estadística** no cambia de fórmula (`successes/attempts`).

### E. Pronunciación con criterio declarado (P2-11)

- En `_academy_rows`, si la fila declara `item_id` y
  `canonical_competence(modality, item_id)` no es `""`, esa es la competencia **sin
  expandir** por subdestrezas del objetivo. Sin `item_id` declarado se conserva el
  comportamiento de V3.62.
- `pronunciation_attempts` (práctica libre) sigue con competencia `""` y motivo
  escrito.

### F. Capas de listening declaradas (P2-12)

- `skill_axis.COMPETENCE_LAYERS_BY_MODALITY` que **REUTILIZA**
  `services.listening.SKILL_LAYER` (recognition/comprehension/inference; 16 de 18)
  sin vocabulario nuevo, con `dictation`/`shadowing` declarados **fuera de capa**
  (son producción) y su motivo.
- `skill_state_summary` gana `layers` (derivado): cobertura por capa.

### G. Seam de política del gate (P2-14)

- `services/competence.py`: `CompetenceGate` declarado (estructura congelada) y
  `gate_for(modality, competence, source)` que devuelve **siempre** el gate por
  defecto de V3.54/V3.62. Un test fija que no hay ninguna política alternativa
  declarada y que añadirla obliga a actualizar la tabla y su docstring.

### H. Frescura del estado (P2-18)

- `evidence_fingerprint(user_id)` (una consulta con `MAX(id)`/`COUNT(*)` por cada
  una de las cuatro fuentes).
- Columna aditiva idempotente `learning_profile.skill_state_source TEXT NOT NULL
  DEFAULT ''`; `set_skill_state(user_id, skill_state, source="")` (firma extendida
  con default) y `skill_state_is_fresh(user_id)`.
- **Invariante:** una caché vieja NUNCA se reporta como fresca. `GET /api/profile`
  sigue recomputando como hoy, así que **ningún payload servido cambia**; el
  "recomputar una vez si está vieja" del camino de decisión es **V3.64**.

## Plan de implementación (tests-first)

1. `backend/tests/test_observed_task_difficulty_v363.py` con los bloques de test
   (ver abajo) y **confirmar el rojo** antes de tocar el código.
2. Bloque A (identidad y ocasiones) → verde.
3. Bloque B (canal observado) → verde.
4. Bloque C (`services/observed_difficulty.py` + exposición aditiva) → verde.
5. Bloque D (confianza de evaluación) → verde.
6. Bloque E (criterio declarado de pronunciación) → verde.
7. Bloque F (capas declaradas de listening) → verde.
8. Bloque G (seam del gate) → verde.
9. Bloque H (fingerprint + columna aditiva + frescura) → verde.
10. Contrato aditivo: `schemas/profile.py` + `frontend/src/types/api.ts`.
11. No-regresión: `test_skill_state_v362.py` **intacto y verde**.

## Criterios de aceptación

- `services/observed_difficulty.py` existe, es puro (sin I/O ni reloj) y devuelve
  la capa empírica con la puerta espaciada reutilizada.
- `skill_state` mantiene **todas** las claves de V3.62 y añade las nuevas.
- `MODALITY_BY_ASSESSED_CHANNEL[("spontaneous_use", "spoken")] == "speaking"` y
  `("spontaneous_use", "written") == "interaction"`, probado.
- Un criterio declarado de pronunciación **sí** produce competencia; la práctica
  libre sigue en `""` y con motivo.
- `COMPETENCE_LAYERS_BY_MODALITY` reutiliza `SKILL_LAYER` sin vocabulario nuevo.
- `gate_for(...)` devuelve siempre la política por defecto.
- `skill_state_is_fresh` nunca declara fresca una caché anterior a la última
  escritura de evidencia.
- El guard estructural de V3.62 sigue verde y el camino de decisión byte-idéntico.
- `ruff` limpio, `pytest` completo verde, `check_release_consistency` `3.63.0`.

## Restricciones

- **No** tocar `services/planner.py`, `services/difficulty.py`,
  `services/transfer.py`, `services/lexicon.py`, `domain/learner_state.py` ni
  `domain/vocabulary.py` de forma que introduzca la subcadena `skill_state` (el
  guard falla y, con razón, la frontera).
- **No** introducir umbrales nuevos ni parámetros estimados por datos.
- **No** usar LLM ni aleatoriedad en el camino de la evidencia (premisa 21).
- **No** bump de `GENERATOR_VERSION` ni cambios de UI/i18n (solo el espejo TS).
- **No** reinterpretar evidencia histórica: la degradación sin los datos nuevos
  debe ser **exacta**.

## Fuera de alcance

- **P1-01 / V3.64**: `Decision Projection` + `Planner 3.0` y el
  "recompute once if stale" en el camino de decisión.
- **V3.65**: `Instance Generator 2.0`. Y después WSD real.
- Rúbrica formal de pronunciación (solo se conecta lo declarado).
- División de `transfer.py` en paquete y el arrastre de V3.59.

## Salida esperada

Diff en `backend/` (núcleo puro, adaptadores, persistencia y contrato aditivos),
espejo de tipos en `frontend/src/types/api.ts`, el test nuevo
`backend/tests/test_observed_task_difficulty_v363.py`, y la actualización
documental de cierre (release notes, `CHANGELOG`, `PLAN`, `docs/RELEVO.md`,
`agentes/README.md`). En el resumen: qué se cerró, qué se degradó de forma exacta y
qué queda **explícitamente** para V3.64.

## Cierre

**V3.63.0 CERRADA y publicada (2026-09-14):** commit de release `73cebb4`, **CI
6/6** en el run
[34868713056](https://github.com/jvelasca/english-tutor/actions/runs/34868713056)
(Release consistency `3.63.0`, Backend con `ruff` + `pytest` + el paso
`python -m scripts.transfer_validation`, Frontend con `tsc` + `vitest` **76
ficheros/651 tests** + `build`, Playwright E2E, Beta V3.0 gate y Content
validation) y etiqueta anotada `v3.63.0` creada y empujada.

**Nota de honestidad sobre el alcance de V3.63 (repetida a propósito):** este
incremento hace el estado **más honesto** (ocasiones, canal observado, confianza de
evaluación, dificultad empírica y frescura), pero **no hace que gobierne ninguna
tarea**. ELV, planner, `difficulty` y `transfer.context_for` quedan
**byte-idénticos** y el guard estructural de V3.62 sigue verde **sin tocarse**. El
estado es **descriptivo**: volverlo **decisional** es exactamente **P1-01**, y su
cierre está comprometido a **V3.64** con **Decision Projection + Planner 3.0**,
calculada desde las **MISMAS filas canónicas** que el estado (nunca desde la
caché), de forma que la caché sea una optimización y no una segunda verdad.

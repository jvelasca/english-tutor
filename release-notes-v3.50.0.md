# v3.50.0 — Context→Skill mapping + difficulty matching (transferencia)

**Release ADITIVA y SIN migración de BD que NO cambia la escalera
`transfer_state`, sus umbrales, el scoring ni FSRS. Cierra el candidato diferido
por V3.49.0: los datos que el banco de contextos declara desde V3.47/V3.48
(`cefr`, `difficulty_vector`) y la modalidad limitante que ya calculaba el planner
dejaban de ser inertes al elegir la tarea. Ahora el contexto de transferencia se
orienta por la COMPETENCIA que limita al ítem y por la BANDA DE DIFICULTAD
alcanzable. Determinista y sin LLM en el camino de la decisión.**

Versión de app `3.49.0 → 3.50.0`. Backend (`services/transfer.py`,
`domain/vocabulary.py`, `schemas/vocabulary.py`) + tipo del contrato en frontend
(`types/api.ts`) + tests y docs.

## Contexto

Hasta V3.49 `context_for` elegía el escenario mirando solo tres cosas: los
contextos ya usados, el CEFR alcanzable (`_within_level`, V3.47) y la novedad
respecto a los contextos ya logrados (V3.43). Los datos de dificultad y la
modalidad limitante del ítem (`planner.limiting_skill`) se calculaban pero no
decidían nada. Dos consecuencias:

- un ítem B1 podía recibir el contexto A1 más plano del banco («Write a question
  you would like to ask a friend») aunque hubiera contextos más cercanos a su
  nivel;
- un ítem limitado en producción escrita u oral recibía el mismo escenario que
  otro limitado en recuperación, sin orientar la tarea a la competencia débil.

Fuera de alcance (diferido y documentado): Sense Engine 2.0 (surface→lemma→sense),
semantic appropriateness (punto 7), `expected_learning_value` / Adaptive Planner
2.0 y la persistencia de la dificultad del contexto por evento.

## Qué cambia

### Context→Skill mapping (`services/transfer.py`)

- **`CONTEXT_SKILLS`** — vocabulario declarado (`recall`, `written_production`,
  `spoken_production`, `spontaneous_use`) como **espejo** de
  `services.evidence.LEXICAL_SKILLS`. Se declara en `transfer.py` y NO se importa
  de `services.evidence` (ese módulo ya importa `transfer`: importarlo de vuelta
  crearía un ciclo); un test de paridad falla si divergen.
- **`skills` en los 20 contextos del banco** — cada uno declara un subconjunto no
  vacío y curado de `CONTEXT_SKILLS`, con al menos una modalidad de producción y
  `spontaneous_use` donde el escenario admite uso libre. Los seis contextos
  originales conservan `id` y valores core CONGELADOS: solo se les añade `skills`.
- **Helper puro `context_skills(context)`** — acepta el dict del banco, un `id` o
  un `context_id` de ledger; deduplica, ordena por `CONTEXT_SKILLS` e ignora
  valores fuera del vocabulario. Nunca lanza.

### Difficulty matching (`services/transfer.py`)

- **`TRANSFER_DIFFICULTY_BAND = 1`** — banda de tolerancia por debajo del objetivo
  (declarada y calibrable).
- **`_difficulty_floor(pool, level)`** — el objetivo es la MAYOR de dos
  referencias: el techo de dificultad real de los contextos alcanzables y la
  posición del nivel en la escala 1..6 (A1≈1 … C2≈6, la misma escala que
  `difficulty_from_vector`). Anclar al nivel era necesario con los datos reales del
  banco: sin él, un ítem B1 (techo alcanzable 2) seguía recibiendo contextos A1.
  El mínimo admisible es `objetivo − TRANSFER_DIFFICULTY_BAND`.
- **`_within_band(pool, floor)`** — conserva los contextos por encima del mínimo;
  si la banda pedida no existe en el pool (p. ej. la modalidad filtrada no tiene
  contextos tan difíciles), degrada con gracia a lo MÁS DIFÍCIL disponible. Nunca
  deja el pool vacío ni sirve algo más plano de lo necesario.
- Sin `level` reconocible (vacío/`Pre-A1`) el mínimo es `1`: comportamiento de
  V3.47/V3.48.

### Pipeline determinista de `context_for`

Firma aditiva y retrocompatible:
`context_for(word, used_context_ids=(), *, success_context_ids=(), condition="", level="", skill="")`.

1. filtra los contextos usados (y rota sobre el banco completo con
   `exhausted=True` si se agotaron), como en V3.46;
2. `_within_level(pool, level)` (V3.47);
3. calcula el mínimo de dificultad sobre TODO el alcance del nivel (antes de
   filtrar por modalidad, para no rebajar el objetivo) y aplica las PREFERENCIAS
   con degradación con gracia: **modalidad limitante** (`_filter_skill`) y
   **banda de dificultad** (`_within_band`);
4. novedad respecto a los contextos ya logrados (V3.43);
5. `_stable_index(word)` sobre el pool final → mismo contexto para la misma
   palabra, la misma evidencia y la misma `skill`/`level`.

El dict de retorno gana `skills` (lista, aditivo). `cefr`/`difficulty_vector`/
`difficulty` ya existían desde V3.47.

### Punto de consumo (`domain/vocabulary.py`)

- Nuevo helper puro `_transfer_target_skill(row, summary)`: devuelve la modalidad
  limitante (`planner.limiting_skill` sobre `planned_signals`, con
  `lexicon.item_competence_matrix`) o `""` si el ledger no tiene segmentación por
  modalidad (`skill_attempts` vacío). Es una PREFERENCIA, no una obligación: no se
  persiste ni cambia el scoring.
- Se pasa `skill=...` tanto en `get_transfer_context` (GET) como en el fallback de
  `submit_transfer_attempt` (POST sin `context_id`), así que ambos caminos derivan
  el MISMO `context_id`.

### Contratos (estrictamente aditivos)

- `TransferContextOut.skills: list[str] = []` (`schemas/vocabulary.py`).
- `DrillTransferContext.skills?: string[]` (`types/api.ts`).
- Sin migración de BD y sin cambios en `TransferAttemptIn`/`TransferAttemptOut`.

## Tests y verificación

- Backend pytest **2097 passed** (+15): nuevo
  `backend/tests/test_context_skill_v350.py` (paridad `CONTEXT_SKILLS` ↔
  `LEXICAL_SKILLS`; los 20 contextos declaran skills válidas y normalizadas; cada
  skill del vocabulario la ejerce algún contexto; `context_skills` con ids/dicts y
  robusto ante entradas no válidas; los seis contextos originales congelados;
  selección idéntica sin `level`/`skill` y con nivel/modalidad desconocidos;
  preferencia de modalidad con degradación; banda de dificultad que excluye A1 en
  B1 y sirve el tramo más duro en C2; determinismo; contrato HTTP y paridad
  GET↔POST con `skill_attempts` reales).
  Se ajusta `test_context_for_ignores_level_when_every_candidate_is_within_reach`
  en `test_transfer_cefr_v347.py`, que fijaba la semántica de V3.47 «con C2 la
  elección es la de sin nivel»: con V3.50 el difficulty matching cambia esa
  elección (ahora comprueba que se sirve el tramo más exigente).
- Frontend vitest **75 ficheros/641 tests** (sin cambios: la modificación es un
  campo opcional del tipo).
- `ruff check backend/` limpio, `tsc --noEmit` limpio, `npm run build` y
  `check_release_consistency` **3.50.0** exit 0.
- `scripts/check_beta_v3.py` y `scripts/content_validation.py` en verde.
- **CI 6/6 en verde** (run
  [34594042697](https://github.com/jvelasca/english-tutor/actions/runs/34594042697)
  sobre `1c8d6e0`): Release consistency, Backend (ruff + pytest), Frontend
  (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content
  validation. Tag `v3.50.0`.

## Fuera de alcance (V3.51+)

- Sense Engine 2.0 (surface→lemma→sense) y semantic appropriateness (punto 7).
- `expected_learning_value` / Adaptive Planner 2.0.
- Persistir la dificultad real del contexto servido por evento (hoy se deriva del
  `cefr` declarado del ítem).
- No se tocan `transfer_state` ni sus umbrales (V3.46/V3.47), FSRS, el Evidence
  Ledger ni la CONSTITUCIÓN (R8/R9 sigue como propuesta abierta).

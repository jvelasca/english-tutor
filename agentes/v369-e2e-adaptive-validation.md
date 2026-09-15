# Briefing de subagente — V3.69 (E2E + Adaptive Engine Validation)

> **Estado:** briefing entregado 2026-09-15; **pendiente de ejecución**.
> **Qué es:** una release de **VALIDACIÓN**, no de capacidad. **No** añade
> arquitectura ni pedagogía: **demuestra experimentalmente** que el circuito
> adaptativo construido en V3.55–V3.68 funciona **como una sola pieza**.
> **Qué cierra:** el objetivo de la auditoría externa `Y` de V3.68
> (`docs/audit/Y-AUDITORIA-TOTAL-V368.md`, §19–§20): comprobar la cadena
> `Evidence → Student State → Decision Projection → Task selection → Decision →
> Serving → Attempt → Outcome → Evidence` con escenarios controlados, y cubrir el
> único tramo del circuito que **hoy no tiene cobertura HTTP**
> (`cola → GET peldaño con decision_id → POST intento → outcome → calibración`)
> más el **endpoint huérfano `GET /api/learning/decisions`**.
> **Qué NO cierra (deuda declarada y aceptada):** identidad lógica
> `serving_id`/`attempt_id` y `decision_events` append-only (P2-03/P2-04),
> normalización de `decision_records` (P2-02), calibración real —*Brier*, *log
> loss*, *ECE*, *reliability diagram*— (P2-05), recencia + **Expected Learning
> Gain real** (P2-06 · pertenece a **Planner 4.0**), `planner_execution_fidelity`
> (P3-01), **Sense Engine** (P3-02) y el *provenance failure rate* como release
> health metric (P2-01).
> **Auditoría/roadmap que lo motivan:** auditoría `Y` de V3.68 (0 P0 · 0 P1 · **6
> P2 · 5 P3**; motor adaptativo **CONGELADO**) y la sección «Siguiente
> incremento» de `PLAN.md`.
> **Regla dura declarada:** *V3.69 no debe introducir arquitectura nueva salvo que
> una prueba E2E demuestre que la arquitectura actual es insuficiente.*
> **Base de partida:** árbol `v3.68.0` (commit `8acee38`, tag `v3.68.0`, commit de
> documentación `d5311cc`).

## Rol

**Backend de validación + contrato de frontend.** Un módulo de tests E2E nuevo
(`backend/tests/test_adaptive_e2e_v369.py`) que recorre el circuito completo por
**HTTP real** (`TestClient` sobre `main.app`) con **batería E01–E16**, y —solo si
un escenario lo exige— las **correcciones mínimas** que no cambien arquitectura.
**Sin** migración destructiva, **sin** bump de `GENERATOR_VERSION`, **sin** tocar
el banco, **sin** capacidad pedagógica nueva, **sin** tocar el argmax del Planner
y **sin** umbrales nuevos.

## Objetivo

Convertir «creemos que el motor adaptativo funciona» en «**está demostrado por
escenarios controlados**», y hacerlo **antes** de entrar en cualquier componente
probabilístico (calibración, ELG real). El motor es **determinista** por diseño y
V3.69 es la release que lo fija como contrato verificable (**E16**).

## Estado de partida verificado (árbol v3.68.0)

### Infraestructura de tests existente

- **Cliente:** `fastapi.testclient.TestClient` (síncrono, en `with`) sobre la app
  real importada de `main` (`backend/tests/test_e2e_regression.py:9-10`). **No**
  hay httpx ni `ASGITransport`.
- **BD:** **no hay fixture compartida**. Cada fichero repite su `_setup` con
  `monkeypatch` + `tmp_path`:

```startLine:19:27:backend/tests/test_e2e_regression.py
def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]
```

- **Auth:** no hay tokens; `dependencies.current_user` lee el usuario de la query
  string (`backend/dependencies.py:30-35`), así que **todo** endpoint se llama con
  `params={"user_id": uid}`.
- **Único fixture global:** `_reset_rate_limiter` (autouse) en
  `backend/tests/conftest.py:15-24`.

### Helpers de siembra reutilizables (patrón a copiar)

- `_seed_word(a, word, cefr)` → `vocabulary_repo.seed_curriculum_items(...)` +
  `record_exposures` (`backend/tests/test_drill_ladder.py:50-66`).
- `_seed_evidence(uid, skill, days, load)` →
  `evidence_repo.record_evidence(..., target_type="lexicon", target_id=...,
  assessed_skill=..., success=..., served_difficulty=..., occurred_at=...)`
  (`backend/tests/test_decision_projection_v364.py:197-209`).
- `_due_lexicon_card(uid, word, *, stability, days_ago)` →
  `academy_repo.upsert_fsrs_card(...)` con `state="review"`, `reps=2`,
  `due_at` en el pasado (`backend/tests/test_review_queue_v335.py:34-50`).
- `_record(uid, **overrides)` → `decision_records_repo.record_decision(...)`
  (`backend/tests/test_decision_v368.py:92`).
- **Fake de ASR imprescindible** para los POST de audio:

```startLine:32:36:backend/tests/test_drill_ladder.py
def _fake_transcribe(text):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake
```

  aplicado con `monkeypatch.setattr(router_mod, "transcribe_with_timing",
  _fake_transcribe(...))` y `files={"file": ("a.wav", b"...", "audio/wav")}`
  (`:200-205`).

### Endpoints del circuito (contrato del `decision_id`)

| Método | Ruta | Línea (`routers/vocabulary.py`) | Entrada | Salida |
|---|---|---|---|---|
| GET | `/api/vocabulary/drill/recognition` | 467 | `word`, `decision_id` | `RecognitionQuestionOut` |
| POST | `/api/vocabulary/drill/recognition-attempt` | 498 | `RecognitionAttemptIn{word, selected_index, question_id, decision_id}` | `RecognitionAttemptOut` |
| GET | `/api/vocabulary/drill/recall` | 542 | `word`, `cue`, `decision_id` | `RecallPromptOut` |
| POST | `/api/vocabulary/drill/recall-attempt` | 575 | `RecallAttemptIn{word, answer, cue, response_time_ms, decision_id}` | `RecallAttemptOut` |
| GET | `/api/vocabulary/drill/sentence-context` | 267 | `word`, `decision_id` | `SentenceContextOut` |
| POST | `/api/vocabulary/drill/sentence-attempt` | 281 | Form `word`, `file`, `decision_id` | `SentenceAttemptOut` |
| POST | `/api/vocabulary/drill/write-attempt` | 341 | `WriteAttemptIn{word, text, response_time_ms, decision_id}` | `WriteAttemptOut` |
| GET | `/api/vocabulary/drill/transfer-context` | 385 | `word`, `decision_id` | `TransferContextOut` |
| POST | `/api/vocabulary/drill/transfer-attempt` | 424 | `TransferAttemptIn{word, text, context_id, context_instance, response_time_ms, decision_id}` | `TransferAttemptOut` |
| POST | `/api/vocabulary/drill/decision-lifecycle` | 627 | `DecisionLifecycleIn{decision_id, event, target_id, activity}` | `DecisionLifecycleOut{applied, decision_id, event}` |
| GET | `/api/vocabulary/drill/candidates` | 206 | `limit=8` | `DrillCandidatesOut` |

Cola y analítica (`backend/routers/learning.py`):

- `GET /api/learning/review` (`:36`) → `ReviewQueueOut{due_count, items, fsrs_version, units}`;
  cada `ReviewQueueItem` (`backend/schemas/learning.py:33-124`) trae `word`,
  `activity`, `expected_learning_value`, `why`, `limiting_skill`,
  `skill_priorities`, `task_key`, `task_instance_key`, `decision_id`,
  `served_load`, `assessment_mode`.
- `GET /api/learning/decisions` (`:51`) → `{decisions, calibration,
  provenance_health}` con filtros `status`/`target_id`/`limit`/`offset`.
  **Sin cobertura en ningún test hoy** (`grep` sin resultados).

**Semántica del round-trip:** el GET del peldaño declara `served`
(`_mark_served`, `vocabulary.py:45-77`); los POST declaran `completed` con
`outcome` (`_mark_completed`, `:115-143`). `write-attempt` es el único sin GET
propio y **auto-declara `served`** antes de cerrar (`:361-370`).

### Piezas deterministas que E16 debe fijar

- `repositories/decision_records.py:61` → `DECISION_POLICY_VERSION = "v3.68.0"`.
- `repositories/decision_records.py:121-148` →
  `build_decision_id(user_id, *, target_id="", task_key="",
  decision_start_fingerprint="") -> str` (SHA-256 puro, nunca lanza).
- `services/planner.py:304-315` → `expected_learning_value(signals, *,
  skill="", task_difficulty=None, learner_capacity=None, value=None,
  capacity_skill="", empirical_success=None, task_empirical_success=None,
  target_empirical_success=None) -> dict` (devuelve `expected_learning_value`,
  `p_success`, `desirability`, `value`, `margin`, `p_success_source`, …).
- `services/planner.py:832-843` → `select_task_by_elv(matrix, evidence,
  signals=None, *, capacity_by_skill=None, task_difficulty=None,
  skill_values=None, drivers=None, empirical_success=None,
  task_empirical_success=None, target_empirical_success=None) -> dict`.
- Orden de desempate canónico de la cola: `domain/review.py:114-135`
  (`-ELV, -priority, retrievability, word`).

### El hueco exacto que hay que cerrar

**Ningún test recorre hoy el circuito completo por HTTP**:

- `test_drill_recall_roundtrip_closes_the_cycle`
  (`backend/tests/test_decision_v368.py:755`) hace GET con `decision_id` y
  comprueba `decision_status == "served"`: **no hay POST ni outcome**.
- `test_transfer_event_persists_declared_served_and_credited`
  (`backend/tests/test_task_difficulty_v355.py:331`) hace GET + POST de
  transferencia **sin `decision_id`** y sin verificar calibración.
- La calibración se prueba **a nivel de repositorio**
  (`test_decision_v367.py:329`, `test_decision_v368.py:684`), no por HTTP.
- `GET /api/learning/decisions` **no aparece en ningún test**.

## Decisiones de alcance (CERRADAS)

1. **V3.69 no cambia el motor.** Si un escenario E2E falla, se registra como
   hallazgo y se decide **explícitamente** entre (a) corregirlo **dentro** de
   V3.69 **sin cambiar arquitectura**, o (b) declarar la insuficiencia y mover la
   capacidad a **V3.70+**. **Nunca** al revés (no se diseña para que el test
   pase).
2. **La batería se escribe antes de cualquier corrección** (premisa 12): primero
   los 16 escenarios en rojo/verde que describan el comportamiento **correcto**
   según el contrato declarado; solo entonces, y solo si hace falta, el arreglo
   mínimo.
3. **Los tests son de contrato, no de implementación:** se afirma sobre la
   **respuesta HTTP** y sobre el **estado observable vía API**
   (`GET /api/learning/decisions`, `GET /api/learning/review`), no sobre
   estructuras internas, salvo donde el contrato sea declarativamente interno
   (`build_decision_id`, FSM) y no exista lectura pública equivalente.
4. **Determinismo primero:** fechas, snapshots y fingerprints **fijos**; nada de
   reloj real ni `random()`. Las fechas se controlan sembrando `occurred_at`/
   `created_at` y con `due_at` fijo en las cartas FSRS.
5. **Un escenario, un test nombrado** `test_e01_...` … `test_e16_...`, para que el
   mapeo con la tabla de la auditoría sea literal.
6. **Sin migración, sin bump de `GENERATOR_VERSION`, sin tocar el banco, sin UI
   nueva.** `DECISION_POLICY_VERSION` **no** se toca (la política de decisión no
   cambia; si hubiera que tocarla, dejaría de ser una release de validación).
7. **El contrato de frontend se verifica con red mockeada** (ver §F), porque el
   job `playwright` de CI corre **sin backend**.

## Diseño

### A · Módulo de la batería (`backend/tests/test_adaptive_e2e_v369.py`)

Cabecera con el `_setup` canónico + helpers propios (`_seed_word`,
`_due_lexicon_card`, `_seed_evidence`, `_fake_transcribe`, `_queue(uid)`,
`_complete(uid, decision_id, outcome)`), y **16 tests**:

| Id | Nombre del test | Escenario y aserción principal |
|---|---|---|
| **E01** | `test_e01_new_learner_closes_the_loop` | Usuario nuevo **sin evidencia** → `GET /api/learning/review` devuelve una primera tarea con `decision_id` → GET del peldaño → **`decision_status == "served"`** → POST del intento con `ok` → **`completed`** → la evidencia queda escrita → una **nueva** consulta de cola refleja el intento (el `p_success`/`why` cambia o la tarea avanza). Es el circuito completo de la auditoría en un solo test. |
| **E02** | `test_e02_weak_skill_raises_its_priority` | Sembrar `speaking` **débil** y `writing` **fuerte** (evidencia espaciada) → la cola sitúa `speaking` arriba: `limiting_skill == "speaking"` y/o `skill_priorities["speaking"] > skill_priorities["writing"]`. Se afirma **dirección**, nunca un valor exacto inventado. |
| **E03** | `test_e03_retention_chooses_review` | Ítem dominado + carta FSRS con `due_at` en el pasado → la cola lo marca vencido (`due_count > 0`) y el Planner elige la actividad de **repaso** para ese ítem. |
| **E04** | `test_e04_transfer_gap_raises_production` | `recognition`/`recall` fuertes y **producción** débil → aparece una actividad de **producción** (no solo reconocimiento) para el ítem. |
| **E05** | `test_e05_same_task_two_contexts_are_two_instances` | Misma tarea servida en **dos contextos** → **mismo `task_key`** y **distinto `task_instance_key`** (la separación de V3.68, ejercitada **por HTTP**, no solo en el módulo puro). |
| **E06** | `test_e06_failure_changes_p_success` | Secuencia `ok, ok, ko` espaciada → el `p_success` del candidato **baja** y `p_success_source` es coherente con el nivel que lo declara (`task_empirical` si la puerta espaciada se cumple). |
| **E07** | `test_e07_unclear_does_not_punish_mastery` | Attempt con `unclear` → **no** penaliza mastery (el estado no empeora), **no** entra en calibración (`measured_count` no sube, `unclear_count` sí) y el provenance **conserva** la fila. |
| **E08** | `test_e08_abandon_does_not_contaminate_ko` | `GET` (served) → `decision-lifecycle{started}` → `decision-lifecycle{abandoned}` → estado `abandoned`; **`abandoned_count` sube** y **`measured_count` no**, y no aparece ningún `ko` en la calibración. |
| **E09** | `test_e09_repeated_refresh_does_not_duplicate` | `GET /api/learning/review` **×3** → **mismo `decision_id`** por ítem y **una sola fila** en el ledger (contada vía `GET /api/learning/decisions`). |
| **E10** | `test_e10_double_submit_is_idempotent` | `completed(ok)` enviado **dos veces** → la segunda **no** altera el estado ni duplica la medición (`duplicate_outcome` contabilizado, resultado estable). |
| **E11** | `test_e11_contradictory_submit_is_rejected` | `completed(ok)` y después `completed(ko)` → **rechazado** (la medición manda y no se sobrescribe) y el contador correspondiente lo refleja. |
| **E12** | `test_e12_wrong_user_changes_nothing` | `user B` intenta cerrar la decisión de `user A` → **no-op**; el estado de A queda intacto y `transition_health.wrong_owner` sube. |
| **E13** | `test_e13_wrong_target_is_rejected` | Decisión sobre `apple` con intento sobre `orange` → **rechazado** y `transition_health.target_mismatch` sube. |
| **E14** | `test_e14_invalid_transition_is_rejected` | `computed → completed` (sin `served`) → **rechazado** y `transition_health.invalid_transition` sube. |
| **E15** | `test_e15_stale_serving_becomes_abandoned` | Fila `served` con `COALESCE(served_at, created_at)` **anterior a 24 h** → la siguiente construcción de cola la deja en **`abandoned`** (`DECISION_ABANDON_AFTER_HOURS = 24`), **nunca** en `completed`. |
| **E16** | `test_e16_planner_is_deterministic` | Con estado, fingerprint, candidatos y política **idénticos**: `N` repeticiones (p. ej. 5) producen **el mismo `selected task`, `p_success`, `ELV`, `why` y `decision_id`**, comparados **byte a byte**. Se comprueba a **los dos niveles**: la función pura (`select_task_by_elv` + `expected_learning_value` con entradas fijas) y la **proyección por HTTP** (misma cola repetida). |

**Notas de implementación por escenario:**

- **E01/E03/E06** requieren `_seed_word` + `_due_lexicon_card` para que el ítem
  entre en la cola, y evidencia con `occurred_at` calculado desde una fecha fija.
- **E02/E04** siembran **varias competencias**; se afirma **orden relativo**
  (`limiting_skill`, `skill_priorities`) y nunca un número concreto que la
  auditoría no haya fijado.
- **E05** necesita ejercitar el peldaño de **transferencia** (que es el que tiene
  contexto): `GET .../transfer-context` seguido de `POST
  .../transfer-attempt` con el `context_id`/`context_instance` **servidos**, y
  comparar `task_key`/`task_instance_key` de dos contextos distintos.
- **E07** puede necesitar `unclear` como outcome declarado por el POST (contrato
  ya existente en V3.67/V3.68) o vía `mark_completed(..., "unclear")`.
- **E09–E15** son escenarios de **integridad** y se apoyan sobre todo en
  `GET /api/learning/decisions` (`transition_health`, contadores y
  `calibration`) leído **después** de la acción.
- **E15** exige controlar el reloj de `close_stale`: sembrar `served_at` con
  `before_iso` anterior a 24 h respecto de la hora real del test (o usar el
  `before_iso` explícito del repositorio si el test llama al barrido
  directamente); **no** se introducen relojes inyectables nuevos.

### B · Cobertura del endpoint huérfano `GET /api/learning/decisions`

Además de servir de observabilidad a E07–E15, un test propio
(`test_e16b_decisions_endpoint_reports_calibration_and_health` o equivalente)
fija el **contrato completo** del endpoint: `{decisions, calibration,
provenance_health}`, con `calibration` exponiendo `completed_count`,
`measured_count`, `unclear_count`, `abandoned_count` y las bandas
`predicted vs observed`, y `provenance_health` exponiendo `record_failures` y
`transition_health`. Se prueban también los **filtros** (`status`, `target_id`) y
la **paginación** (`limit`/`offset`).

### C · Determinismo (E16) como contrato, no como anécdota

- A nivel **puro**: entradas fijas (`matrix`, `evidence`, `signals`,
  `task_difficulty`, `learner_capacity`, `empirical_success*`) → `N` llamadas
  comparadas con `==` sobre el `dict` completo (y opcionalmente sobre su
  serialización canónica).
- A nivel **HTTP**: dos llamadas idénticas a `GET /api/learning/review` sobre la
  **misma BD sin mutación intermedia** → mismo `decision_id` y mismo orden de
  ítems (el desempate canónico `-ELV, -priority, retrievability, word` lo
  garantiza).
- **Prohibiciones verificadas por test** (ya existen precedentes en
  `test_observed_task_difficulty_v363.py:424-437` y
  `test_decision_projection_v364.py:230-257`): los módulos puros no importan
  `time`/`datetime`/`random`, no usan `hash(` ni I/O y no lanzan excepción.

### D · Correcciones permitidas (solo si un escenario lo exige)

V3.69 **puede** tocar, con el mínimo cambio y **sin arquitectura nueva**:

- Un **bug** demostrado por un escenario (p. ej. una transición que la FSM
  admite y no debería, un contador mal incrementado, una fuga de `target_id`).
- Un **contrato de respuesta** incompleto que impida verificar el circuito por
  API (p. ej. un campo que el test necesita y ya existe en el repositorio pero no
  se expone). En ese caso, el cambio es **aditivo** y se documenta.
- **Nunca**: nuevas tablas, nuevos umbrales, cambios en el argmax, cambios en
  `DECISION_POLICY_VERSION` ni en `GENERATOR_VERSION`.

### E · Registro de hallazgos (obligatorio en la release note)

Toda desviación entre lo que el escenario espera y lo que el sistema hace se
registra en `release-notes-v3.69.0.md` §«Hallazgos E2E» con: id del escenario,
comportamiento observado, comportamiento esperado, decisión tomada
(**corregido en V3.69** / **aceptado como deuda** / **movido a V3.70+**) y
referencia al test que lo fija. Sin esta tabla, la release no está cerrada.

### F · Contrato de frontend (complementario, con red mockeada)

Una spec nueva en `frontend/tests/visual/` (o `frontend/tests/` si no necesita
navegador) que fije, **con `page.route` y respuestas simuladas**, que:

1. el drill **envía `decision_id`** en los GET del peldaño (query) y en los POST
   de intento (body/FormData);
2. se declara **`started`** cuando el peldaño **ya está cargado** (no al montar);
3. se declara **`abandoned`** al **desmontar** sin outcome;
4. sin `decisionId` (drill abierto desde el diccionario) **no** se declara nada.

Se hace con **mocks** porque el job `playwright` de CI
(`.github/workflows/ci.yml:107-125`) arranca solo el dev server de Vite
(`frontend/playwright.config.ts` `webServer`) y **no** levanta el backend; la
verificación real del round-trip contra backend es la que hacen E01–E16.

## Tests

- **Nuevo:** `backend/tests/test_adaptive_e2e_v369.py` con **E01–E16** (16 tests,
  uno por escenario, más el del endpoint de decisions) — **escritos antes** de
  cualquier corrección.
- **Nuevo (si aplica):** spec de contrato de frontend (§F).
- **No-regresión obligatoria, sin tocarse:** `test_decision_v368.py`,
  `test_decision_v367.py`, `test_decision_v366.py`,
  `test_observed_difficulty_v365.py`, `test_decision_projection_v364.py`,
  `test_planner_argmax_v357.py`, `test_skill_state_v362.py`,
  `test_observed_task_difficulty_v363.py`, `test_drill_ladder.py`,
  `test_review_queue_v335.py`, `test_e2e_regression.py` y los tests de frontend
  del drill (`vocabulary.test.ts`, `wordDrill.test.tsx`,
  `ReviewQueueSection.test.tsx`).
- **Guard estructural** (`test_skill_state_v362.py`): `planner.py`,
  `difficulty.py`, `transfer.py`, `lexicon.py`, `learner_state.py`,
  `vocabulary.py` siguen **sin** contener la subcadena `skill_state`.

## Criterios de salida

1. **E01–E16 verdes**, cada uno con su nombre `test_eXX_...`, y el mapeo
   escenario↔test documentado en la release note.
2. **Ningún cambio de arquitectura** no justificado por un hallazgo: si existe,
   está en la tabla §E con su motivo.
3. `pytest` (backend) verde con el total **anterior + nuevos**;
   `ruff` limpio; `tsc --noEmit` limpio; `vitest` verde; `build` OK; launcher OK.
4. Gates de script OK: `check_release_consistency` (**3.69.0**),
   `check_beta_v3`, `content_validation` y `transfer_validation`.
5. `check_release_consistency` verde implica la versión bumpeada en los 6 sitios
   del checklist de cierre.
6. **CI 6/6** verde, registrado con su run id (y declarado como tal en la release
   note: el proyecto **no** afirma verificación independiente).

## Fuera de alcance (deuda declarada)

- **Identidad lógica `serving_id`/`attempt_id`** (P2-03) y **`decision_events`
  append-only** (P2-04): pertenecen a la fase de analítica posterior.
- **Normalizar `decision_records`** en DECISION/SERVING/ATTEMPT/OUTCOME (P2-02):
  sobreingeniería para SQLite local; se fija solo el modelo **conceptual**.
- **Calibración real** (P2-05: *Brier*, *log loss*, *ECE*, *reliability diagram*,
  confianza por muestra): requiere tráfico real. Regla: *collect* → *observe* →
  *calibrate*.
- **Recencia + Expected Learning Gain real** (P2-06): **Planner 4.0**.
- **`planner_execution_fidelity`** (P3-01), **Sense Engine** (P3-02) y
  ***provenance failure rate* como release health metric** (P2-01).
- **V3.70 auditoría pedagógica/CEFR**, **V3.71 offline/runtime**, **V3.72 UX
  final**, **V3.73 auditoría final** y **V4.0**.

## Cierre (higiene de release, cuando se ejecute)

Checklist verificado contra el árbol v3.68.0 (`check_release_consistency.py` usa
**la primera coincidencia** de cada fichero, así que hay que insertar la entrada
nueva **arriba**):

1. `backend/config.py:32` → `VERSION = "3.68.0"` → `"3.69.0"` (**fuente única**).
2. `frontend/package.json:4` → `"version"`.
3. `frontend/package-lock.json:3` (**y** la copia de `:9`).
4. `README.md:16` → «Última versión estable: **v3.69.0**».
5. `CHANGELOG.md` → nueva entrada `## [3.69.0] — <fecha>` **en la cabecera**, por
   encima de `## [3.68.0]`.
6. `PLAN.md` → nuevo bullet como **primer** item de «Estado actual» (línea 11) con
   ``**Versión estable `3.69.0`**`` y ``app `3.68.0 → 3.69.0` ``; actualizar
   `### M13` (marcar V3.69 hecho y mover la flecha a V3.70) y la fila del tablero
   de briefings.
7. `docs/RELEVO.md` → **nota nueva encima de la nota actual** (la más reciente
   arriba) + fecha de «Actualizado por última vez» + refrescar la posición de
   **«0. START HERE»**.
8. `release-notes-v3.69.0.md` (nuevo, raíz) con: alcance, contexto, la **tabla
   E01–E16**, la **tabla de hallazgos §E**, tests, §«Honestidad» y §«Fuera de
   alcance».
9. **No** tocar `DECISION_POLICY_VERSION`
   (`backend/repositories/decision_records.py:61`) ni `GENERATOR_VERSION`: la
   política de decisión y el contenido **no** cambian en V3.69.

Verificación local completa **antes** de commitear: `ruff`, `pytest`,
`tsc --noEmit`, `vitest`, `build`, launcher, `check_release_consistency`,
`check_beta_v3`, `content_validation` y `transfer_validation`. Después: commit de
release + tag anotado `v3.69.0` + push, y registrar el run de **CI** (6/6) en la
nota de `docs/RELEVO.md` **declarándolo como resultado del release**.
